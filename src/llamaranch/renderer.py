from __future__ import annotations

import shlex
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import RanchConfig
from .schema import HardwareTarget, ModelConfig, ServerConfig
from .systemd import unit_name, unit_path


class RenderError(ValueError):
    """Raised when a server cannot be rendered into a llama-server command."""


FLAG_ALIASES = {
    "context": "--ctx-size",
    "ctx_size": "--ctx-size",
    "gpu_layers": "--n-gpu-layers",
    "n_gpu_layers": "--n-gpu-layers",
    "main_gpu": "--main-gpu",
    "temperature": "--temp",
}


@dataclass(frozen=True)
class RenderedServer:
    name: str
    model: ModelConfig
    hardware: HardwareTarget
    server: ServerConfig
    command: tuple[str, ...]
    unit_name: str
    unit_path: Path

    @property
    def command_display(self) -> str:
        return shlex.join(self.command)


def render_server(config: RanchConfig, server_name: str) -> RenderedServer:
    server = config.get_server(server_name)
    model = config.get_model(server.model)
    hardware = config.get_hardware(server.hardware)
    command = build_command(config, server, model, hardware)

    return RenderedServer(
        name=server_name,
        model=model,
        hardware=hardware,
        server=server,
        command=tuple(command),
        unit_name=unit_name(server_name),
        unit_path=unit_path(server_name),
    )


def build_command(
    config: RanchConfig,
    server: ServerConfig,
    model: ModelConfig,
    hardware: HardwareTarget,
) -> list[str]:
    executable = str(config.global_config.llama_server)
    if not executable:
        raise RenderError("llama-server executable path is empty")

    command = [
        executable,
        "--model",
        str(model.path),
        "--host",
        server.host,
        "--port",
        str(server.port),
    ]

    context = server.context if server.context is not None else model.context
    if context is not None:
        command.extend(["--ctx-size", str(context)])

    if hardware.gpu_layers is not None:
        command.extend(["--n-gpu-layers", str(hardware.gpu_layers)])
    if hardware.main_gpu is not None:
        command.extend(["--main-gpu", str(hardware.main_gpu)])

    command.extend(args_from_mapping(model.defaults))
    command.extend(args_from_mapping(server.defaults))
    command.extend(model.extra_args)
    command.extend(hardware.extra_args)
    command.extend(server.extra_args)

    return command


def args_from_mapping(values: Mapping[str, Any]) -> list[str]:
    args: list[str] = []
    for key, value in values.items():
        flag = flag_for_key(key)
        args.extend(args_for_value(flag, value))
    return args


def flag_for_key(key: str) -> str:
    if not key:
        raise RenderError("empty argument key")
    return FLAG_ALIASES.get(key, f"--{key.replace('_', '-')}")


def args_for_value(flag: str, value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, bool):
        return [flag] if value else []
    if isinstance(value, Mapping):
        raise RenderError(f"{flag} cannot be rendered from a mapping value")
    if isinstance(value, (list, tuple)):
        args: list[str] = []
        for item in value:
            args.extend(args_for_value(flag, item))
        return args
    return [flag, str(value)]

