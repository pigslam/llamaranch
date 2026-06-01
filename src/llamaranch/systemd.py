from __future__ import annotations

import re
import shlex
import subprocess
from pathlib import Path

SYSTEMD_USER_DIR = Path.home() / ".config" / "systemd" / "user"


def unit_slug(server_name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", server_name).strip(".-")
    return slug or "server"


def unit_name(server_name: str) -> str:
    return f"llamaranch-{unit_slug(server_name)}.service"


def unit_path(server_name: str, systemd_user_dir: Path = SYSTEMD_USER_DIR) -> Path:
    return systemd_user_dir / unit_name(server_name)


def render_unit(server_name: str, command: tuple[str, ...], working_dir: Path | None = None) -> str:
    working_dir = working_dir or Path.home()
    exec_start = shlex.join(command).replace("%", "%%")

    return "\n".join(
        [
            "[Unit]",
            f"Description=LlamaRanch server {server_name}",
            "After=network-online.target",
            "",
            "[Service]",
            "Type=simple",
            f"WorkingDirectory={working_dir}",
            f"ExecStart={exec_start}",
            "Restart=on-failure",
            "RestartSec=5",
            "",
            "[Install]",
            "WantedBy=default.target",
            "",
        ]
    )


def service_state(service_name: str) -> str:
    try:
        result = subprocess.run(
            ["systemctl", "--user", "is-active", service_name],
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
