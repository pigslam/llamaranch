from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import re
import shlex
import subprocess
from pathlib import Path

SYSTEMD_USER_DIR = Path.home() / ".config" / "systemd" / "user"


class SystemdError(RuntimeError):
    """Raised when a systemd or journalctl command fails."""


@dataclass(frozen=True)
class CommandResult:
    args: tuple[str, ...]
    returncode: int
    stdout: str = ""
    stderr: str = ""


def unit_slug(server_name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", server_name).strip(".-")
    return slug or "server"


def unit_name(server_name: str) -> str:
    return f"llamaranch-{unit_slug(server_name)}.service"


def unit_path(server_name: str, systemd_user_dir: Path = SYSTEMD_USER_DIR) -> Path:
    return systemd_user_dir / unit_name(server_name)


def render_unit(
    server_name: str,
    command: tuple[str, ...],
    working_dir: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> str:
    working_dir = working_dir or Path.home()
    exec_start = shlex.join(command).replace("%", "%%")
    env_lines = [
        f"Environment={shlex.quote(f'{key}={value}')}"
        for key, value in (env or {}).items()
    ]

    lines = [
        "[Unit]",
        f"Description=LlamaRanch server {server_name}",
        "After=network-online.target",
        "",
        "[Service]",
        "Type=simple",
        f"WorkingDirectory={working_dir}",
    ]
    lines.extend(env_lines)
    lines.extend(
        [
            f"ExecStart={exec_start}",
            "Restart=on-failure",
            "RestartSec=5",
            "",
            "[Install]",
            "WantedBy=default.target",
            "",
        ]
    )
    return "\n".join(lines)


def write_unit(
    server_name: str,
    command: tuple[str, ...],
    systemd_user_dir: Path = SYSTEMD_USER_DIR,
    working_dir: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> Path:
    path = unit_path(server_name, systemd_user_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        render_unit(server_name, command, working_dir=working_dir, env=env),
        encoding="utf-8",
    )
    return path


def systemctl_args(action: str, service_name: str | None = None) -> tuple[str, ...]:
    if action == "daemon-reload":
        if service_name is not None:
            raise ValueError("daemon-reload does not take a service name")
        return ("systemctl", "--user", "daemon-reload")

    if service_name is None:
        raise ValueError(f"{action} requires a service name")
    if action not in {"start", "stop", "restart", "enable", "disable", "is-active"}:
        raise ValueError(f"unsupported systemctl action: {action}")
    return ("systemctl", "--user", action, service_name)


def journalctl_args(service_name: str, lines: int = 100, follow: bool = False) -> tuple[str, ...]:
    if lines < 0:
        raise ValueError("lines cannot be negative")
    args = ["journalctl", "--user", "-u", service_name, "-n", str(lines)]
    if follow:
        args.append("-f")
    return tuple(args)


def run_systemctl(action: str, service_name: str | None = None) -> CommandResult:
    args = systemctl_args(action, service_name)
    result = subprocess.run(args, check=False, capture_output=True, text=True)
    command_result = CommandResult(
        args=tuple(args),
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )
    if result.returncode != 0:
        raise SystemdError(command_error_message(command_result))
    return command_result


def run_journalctl(service_name: str, lines: int = 100, follow: bool = False) -> CommandResult:
    args = journalctl_args(service_name, lines=lines, follow=follow)
    result = subprocess.run(args, check=False)
    command_result = CommandResult(args=tuple(args), returncode=result.returncode)
    if result.returncode != 0:
        raise SystemdError(command_error_message(command_result))
    return command_result


def service_state(service_name: str) -> str:
    try:
        result = subprocess.run(
            systemctl_args("is-active", service_name),
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return "unknown"

    stdout = result.stdout.strip()
    if stdout:
        return stdout
    return "unknown"


def command_error_message(result: CommandResult) -> str:
    detail = result.stderr.strip() or result.stdout.strip()
    command = shlex.join(result.args)
    if detail:
        return f"{command} failed with exit code {result.returncode}: {detail}"
    return f"{command} failed with exit code {result.returncode}"
