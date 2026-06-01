from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    """Raised when LlamaRanch configuration is invalid."""


@dataclass(frozen=True)
class GlobalConfig:
    llama_server: Path = Path("~/.local/bin/llama-server").expanduser()
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "GlobalConfig":
        value = first_present(
            data,
            "llama_server",
            "llama_server_path",
            "llama_server_executable",
            default="~/.local/bin/llama-server",
        )
        return cls(llama_server=coerce_path(value, "config.yaml:llama_server"), raw=dict(data))


@dataclass(frozen=True)
class ModelConfig:
    name: str
    path: Path
    context: int | None = None
    defaults: dict[str, Any] = field(default_factory=dict)
    extra_args: tuple[str, ...] = ()
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, name: str, data: Mapping[str, Any]) -> "ModelConfig":
        return cls(
            name=name,
            path=coerce_path(required(data, "path", f"model {name}"), f"model {name}.path"),
            context=optional_int(data.get("context"), f"model {name}.context"),
            defaults=dict(optional_mapping(data.get("defaults"), f"model {name}.defaults")),
            extra_args=coerce_args(
                first_present(data, "extra_args", "args", default=None),
                f"model {name}.extra_args",
            ),
            raw=dict(data),
        )


@dataclass(frozen=True)
class HardwareTarget:
    name: str
    backend: str
    gpu_layers: int | None = None
    main_gpu: int | None = None
    extra_args: tuple[str, ...] = ()
    env: dict[str, str] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, name: str, data: Mapping[str, Any]) -> "HardwareTarget":
        return cls(
            name=name,
            backend=coerce_str(required(data, "backend", f"hardware {name}"), f"hardware {name}.backend"),
            gpu_layers=optional_int(data.get("gpu_layers"), f"hardware {name}.gpu_layers"),
            main_gpu=optional_int(data.get("main_gpu"), f"hardware {name}.main_gpu"),
            extra_args=coerce_args(
                first_present(data, "extra_args", "args", default=None),
                f"hardware {name}.extra_args",
            ),
            env=coerce_str_mapping(data.get("env"), f"hardware {name}.env"),
            raw=dict(data),
        )


@dataclass(frozen=True)
class ServerConfig:
    name: str
    model: str
    hardware: str
    port: int
    host: str = "127.0.0.1"
    enabled: bool = True
    context: int | None = None
    defaults: dict[str, Any] = field(default_factory=dict)
    extra_args: tuple[str, ...] = ()
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, name: str, data: Mapping[str, Any]) -> "ServerConfig":
        return cls(
            name=name,
            model=coerce_str(required(data, "model", f"server {name}"), f"server {name}.model"),
            hardware=coerce_str(
                required(data, "hardware", f"server {name}"), f"server {name}.hardware"
            ),
            port=coerce_int(required(data, "port", f"server {name}"), f"server {name}.port"),
            host=coerce_str(data.get("host", "127.0.0.1"), f"server {name}.host"),
            enabled=coerce_bool(data.get("enabled", True), f"server {name}.enabled"),
            context=optional_int(data.get("context"), f"server {name}.context"),
            defaults=dict(optional_mapping(data.get("defaults"), f"server {name}.defaults")),
            extra_args=coerce_args(
                first_present(data, "extra_args", "args", default=None),
                f"server {name}.extra_args",
            ),
            raw=dict(data),
        )


def expect_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ConfigError(f"{label} must be a mapping")
    return value


def optional_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if value is None:
        return {}
    return expect_mapping(value, label)


def required(data: Mapping[str, Any], key: str, label: str) -> Any:
    if key not in data or data[key] is None:
        raise ConfigError(f"{label} requires '{key}'")
    return data[key]


def first_present(data: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in data:
            return data[key]
    return default


def coerce_path(value: Any, label: str) -> Path:
    text = coerce_str(value, label)
    if not text:
        raise ConfigError(f"{label} cannot be empty")
    return Path(text).expanduser()


def coerce_str(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise ConfigError(f"{label} must be a string")
    if not value:
        raise ConfigError(f"{label} cannot be empty")
    return value


def coerce_bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigError(f"{label} must be true or false")
    return value


def coerce_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{label} must be an integer")
    return value


def optional_int(value: Any, label: str) -> int | None:
    if value is None:
        return None
    return coerce_int(value, label)


def coerce_args(value: Any, label: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ConfigError(f"{label} must be a list of arguments")
    return tuple(coerce_str(item, f"{label} item") for item in value)


def coerce_str_mapping(value: Any, label: str) -> dict[str, str]:
    if value is None:
        return {}
    mapping = expect_mapping(value, label)
    result: dict[str, str] = {}
    for key, item in mapping.items():
        result[coerce_str(key, f"{label} key")] = coerce_str(item, f"{label}.{key}")
    return result
