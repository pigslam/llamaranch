from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any

import yaml

from .schema import (
    ConfigError,
    GlobalConfig,
    HardwareTarget,
    ModelConfig,
    ServerConfig,
    expect_mapping,
)

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "llamaranch"
DEFAULT_CONFIGS_DIR = DEFAULT_CONFIG_DIR / "configs"
CONFIG_FILES = ("config.yaml", "models.yaml", "hardware.yaml", "servers.yaml")
PROFILE_SUFFIXES = (".yaml", ".yml")


class ConfigNotFoundError(ConfigError):
    """Raised when a requested config profile cannot be found."""


@dataclass(frozen=True)
class RanchConfig:
    config_dir: Path
    missing_files: tuple[str, ...]
    global_config: GlobalConfig
    models: dict[str, ModelConfig]
    hardware: dict[str, HardwareTarget]
    servers: dict[str, ServerConfig]
    source: Path | None = None
    profile_name: str | None = None

    def get_server(self, name: str) -> ServerConfig:
        try:
            return self.servers[name]
        except KeyError as exc:
            raise ConfigError(f"unknown server: {name}") from exc

    def get_model(self, name: str) -> ModelConfig:
        try:
            return self.models[name]
        except KeyError as exc:
            raise ConfigError(f"unknown model: {name}") from exc

    def get_hardware(self, name: str) -> HardwareTarget:
        try:
            return self.hardware[name]
        except KeyError as exc:
            raise ConfigError(f"unknown hardware target: {name}") from exc


def load_config(config_dir: Path = DEFAULT_CONFIG_DIR) -> RanchConfig:
    """Load the legacy four-file configuration directory."""
    config_dir = config_dir.expanduser()
    loaded: dict[str, dict[str, Any]] = {}
    missing: list[str] = []

    for filename in CONFIG_FILES:
        path = config_dir / filename
        if not path.exists():
            loaded[filename] = {}
            missing.append(filename)
            continue
        loaded[filename] = _read_yaml_mapping(path)

    global_config = GlobalConfig.from_mapping(loaded["config.yaml"])
    models = _parse_named_section(
        loaded["models.yaml"], "models", "models.yaml", ModelConfig.from_mapping
    )
    hardware = _parse_named_section(
        loaded["hardware.yaml"],
        "hardware",
        "hardware.yaml",
        HardwareTarget.from_mapping,
    )
    servers = _parse_named_section(
        loaded["servers.yaml"], "servers", "servers.yaml", ServerConfig.from_mapping
    )

    return RanchConfig(
        config_dir=config_dir,
        missing_files=tuple(missing),
        global_config=global_config,
        models=models,
        hardware=hardware,
        servers=servers,
        source=config_dir,
        profile_name=None,
    )


def load_profile_config(
    config_ref: str | Path,
    configs_dir: Path = DEFAULT_CONFIGS_DIR,
) -> RanchConfig:
    """Load a single-file config profile by name or path."""
    return load_config_file(resolve_profile_path(config_ref, configs_dir))


def load_config_file(path: Path) -> RanchConfig:
    path = path.expanduser()
    if not path.exists():
        raise ConfigNotFoundError(f"config file not found: {path}")
    if not path.is_file():
        raise ConfigError(f"config path is not a file: {path}")

    data = _read_yaml_mapping(path)
    source = str(path)
    profile_name = path.stem

    global_config = GlobalConfig.from_mapping(
        _global_section(data, source),
        label=f"{source}:config",
    )
    models = _parse_named_section(
        data,
        "models",
        source,
        ModelConfig.from_mapping,
        allow_unwrapped=False,
    )
    hardware = _parse_named_section(
        data,
        "hardware",
        source,
        HardwareTarget.from_mapping,
        allow_unwrapped=False,
    )
    servers = _parse_servers_section(data, source, profile_name)

    return RanchConfig(
        config_dir=path.parent,
        missing_files=(),
        global_config=global_config,
        models=models,
        hardware=hardware,
        servers=servers,
        source=path,
        profile_name=profile_name,
    )


def resolve_profile_path(
    config_ref: str | Path,
    configs_dir: Path = DEFAULT_CONFIGS_DIR,
) -> Path:
    candidates = profile_path_candidates(config_ref, configs_dir)
    for path in candidates:
        if path.exists():
            return path

    searched = ", ".join(str(path) for path in candidates)
    raise ConfigNotFoundError(f"config profile not found: {config_ref} (searched {searched})")


def profile_path_candidates(
    config_ref: str | Path,
    configs_dir: Path = DEFAULT_CONFIGS_DIR,
) -> tuple[Path, ...]:
    text = str(config_ref)
    path = Path(text).expanduser()

    if _is_path_like_ref(text, path):
        return _yaml_candidates(path)

    return _yaml_candidates(configs_dir.expanduser() / text)


def list_profile_paths(configs_dir: Path = DEFAULT_CONFIGS_DIR) -> tuple[Path, ...]:
    configs_dir = configs_dir.expanduser()
    if not configs_dir.exists():
        return ()
    if not configs_dir.is_dir():
        raise ConfigError(f"profile config path is not a directory: {configs_dir}")

    paths: list[Path] = []
    for suffix in PROFILE_SUFFIXES:
        paths.extend(path for path in configs_dir.glob(f"*{suffix}") if path.is_file())
    return tuple(sorted(paths))


def _read_yaml_mapping(path: Path) -> dict[str, Any]:
    try:
        content = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path} is not valid YAML: {exc}") from exc

    mapping = expect_mapping(content or {}, str(path))
    return dict(mapping)


def _parse_named_section(
    data: dict[str, Any],
    section_name: str,
    filename: str,
    parser: Any,
    allow_unwrapped: bool = True,
) -> dict[str, Any]:
    if section_name in data:
        raw_section = data[section_name]
    elif allow_unwrapped:
        raw_section = data
    else:
        raw_section = {}

    section = expect_mapping(raw_section, f"{filename}:{section_name}")
    parsed: dict[str, Any] = {}

    for name, value in section.items():
        if not isinstance(name, str) or not name:
            raise ConfigError(f"{filename}:{section_name} contains an invalid name")
        item = expect_mapping(value, f"{filename}:{section_name}.{name}")
        parsed[name] = parser(name, item)

    return parsed


def _parse_servers_section(
    data: dict[str, Any],
    source: str,
    default_name: str,
) -> dict[str, ServerConfig]:
    if "server" in data and "servers" in data:
        raise ConfigError(f"{source} cannot contain both 'server' and 'servers'")

    if "server" in data:
        item = expect_mapping(data["server"], f"{source}:server")
        return {default_name: ServerConfig.from_mapping(default_name, item)}

    return _parse_named_section(
        data,
        "servers",
        source,
        ServerConfig.from_mapping,
        allow_unwrapped=False,
    )


def _global_section(data: dict[str, Any], source: str) -> dict[str, Any]:
    if "config" in data:
        return dict(expect_mapping(data["config"], f"{source}:config"))

    section_names = {"models", "hardware", "server", "servers"}
    return {key: value for key, value in data.items() if key not in section_names}


def _is_path_like_ref(text: str, path: Path) -> bool:
    return (
        path.is_absolute()
        or text.startswith("~")
        or text.startswith(".")
        or os.sep in text
        or bool(os.altsep and os.altsep in text)
    )


def _yaml_candidates(path: Path) -> tuple[Path, ...]:
    if path.suffix in PROFILE_SUFFIXES:
        return (path,)
    return (Path(f"{path}.yaml"), Path(f"{path}.yml"), path)
