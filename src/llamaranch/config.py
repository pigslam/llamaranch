from __future__ import annotations

from dataclasses import dataclass
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
CONFIG_FILES = ("config.yaml", "models.yaml", "hardware.yaml", "servers.yaml")


@dataclass(frozen=True)
class RanchConfig:
    config_dir: Path
    missing_files: tuple[str, ...]
    global_config: GlobalConfig
    models: dict[str, ModelConfig]
    hardware: dict[str, HardwareTarget]
    servers: dict[str, ServerConfig]

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
    )


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
) -> dict[str, Any]:
    raw_section = data.get(section_name, data)
    section = expect_mapping(raw_section, f"{filename}:{section_name}")
    parsed: dict[str, Any] = {}

    for name, value in section.items():
        if not isinstance(name, str) or not name:
            raise ConfigError(f"{filename}:{section_name} contains an invalid name")
        item = expect_mapping(value, f"{filename}:{section_name}.{name}")
        parsed[name] = parser(name, item)

    return parsed
