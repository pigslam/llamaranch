from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .config import (
    DEFAULT_CONFIGS_DIR,
    PROFILE_SUFFIXES,
    list_profile_paths,
    load_config_file,
    resolve_profile_path,
)
from .schema import ConfigError
from .systemd import service_state, unit_name

PROFILE_TEMPLATE = """config:
  llama_server: ~/.local/bin/llama-server

models:
  local-model:
    path: /path/to/model.gguf
    context: 32768
    defaults:
      temperature: 0.0

hardware:
  local-gpu:
    backend: vulkan
    gpu_layers: -1
    main_gpu: 0

server:
  model: local-model
  hardware: local-gpu
  host: 127.0.0.1
  port: 8080
  enabled: true
  extra_args: []
"""

RUNNING_STATES = {"active", "activating", "reloading"}
StateChecker = Callable[[str], str]


class ProfileExistsError(ConfigError):
    """Raised when a profile create/copy would overwrite an existing file."""


class ProfileInUseError(ConfigError):
    """Raised when deleting a profile that appears to be running."""


@dataclass(frozen=True)
class ProfileSummary:
    profile: str
    state: str
    port: str
    model: str
    note: str = ""


def create_profile(name: str, configs_dir: Path = DEFAULT_CONFIGS_DIR) -> Path:
    path = profile_path_for_name(name, configs_dir)
    if path.exists():
        raise ProfileExistsError(f"profile already exists: {path}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(PROFILE_TEMPLATE, encoding="utf-8")
    return path


def clone_profile(
    source: str | Path,
    destination: str,
    configs_dir: Path = DEFAULT_CONFIGS_DIR,
) -> tuple[Path, Path]:
    source_path = resolve_profile_path(source, configs_dir)
    destination_path = profile_path_for_name(destination, configs_dir)

    if source_path.resolve() == destination_path.expanduser().resolve():
        raise ConfigError("source and destination profiles are the same")
    if destination_path.exists():
        raise ProfileExistsError(f"profile already exists: {destination_path}")

    destination_path.parent.mkdir(parents=True, exist_ok=True)
    destination_path.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")
    return source_path, destination_path


def delete_profile(
    name: str | Path,
    configs_dir: Path = DEFAULT_CONFIGS_DIR,
    force: bool = False,
    state_checker: StateChecker = service_state,
) -> Path:
    path = resolve_profile_path(name, configs_dir)
    running = running_profile_services(path, state_checker)

    if running and not force:
        services = ", ".join(f"{server} ({state})" for server, state in running)
        raise ProfileInUseError(
            f"profile appears to be running as {services}; stop it first or pass --force"
        )

    path.unlink()
    return path


def profile_summaries(
    configs_dir: Path = DEFAULT_CONFIGS_DIR,
    state_checker: StateChecker = service_state,
) -> tuple[ProfileSummary, ...]:
    summaries: list[ProfileSummary] = []
    for path in list_profile_paths(configs_dir):
        summaries.extend(profile_summaries_for_path(path, state_checker))
    return tuple(summaries)


def profile_summaries_for_path(
    path: Path,
    state_checker: StateChecker = service_state,
) -> tuple[ProfileSummary, ...]:
    profile = path.stem

    try:
        config = load_config_file(path)
    except ConfigError as exc:
        return (
            ProfileSummary(
                profile=profile,
                state="invalid",
                port="-",
                model="-",
                note=str(exc),
            ),
        )

    if not config.servers:
        return (ProfileSummary(profile=profile, state="empty", port="-", model="-"),)

    summaries: list[ProfileSummary] = []
    for server_name, server in config.servers.items():
        label = profile if len(config.servers) == 1 else f"{profile}:{server_name}"
        summaries.append(
            ProfileSummary(
                profile=label,
                state=state_checker(unit_name(server_name)),
                port=str(server.port),
                model=server.model,
            )
        )

    return tuple(summaries)


def running_profile_services(
    path: Path,
    state_checker: StateChecker = service_state,
) -> tuple[tuple[str, str], ...]:
    running: list[tuple[str, str]] = []
    for server_name in profile_server_names(path):
        state = state_checker(unit_name(server_name))
        if state in RUNNING_STATES:
            running.append((server_name, state))
    return tuple(running)


def profile_server_names(path: Path) -> tuple[str, ...]:
    try:
        config = load_config_file(path)
    except ConfigError:
        return (path.stem,)

    if not config.servers:
        return (path.stem,)
    return tuple(config.servers)


def profile_path_for_name(name: str, configs_dir: Path = DEFAULT_CONFIGS_DIR) -> Path:
    profile_name = normalize_profile_name(name)
    return configs_dir.expanduser() / f"{profile_name}.yaml"


def normalize_profile_name(name: str) -> str:
    profile_name = name.strip()
    for suffix in PROFILE_SUFFIXES:
        if profile_name.endswith(suffix):
            profile_name = profile_name[: -len(suffix)]
            break

    if not profile_name:
        raise ConfigError("profile name cannot be empty")
    if profile_name in {".", ".."}:
        raise ConfigError(f"invalid profile name: {name}")
    if "/" in profile_name or "\\" in profile_name:
        raise ConfigError("profile name cannot contain path separators")

    return profile_name

