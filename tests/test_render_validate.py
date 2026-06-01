from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from llamaranch.config import load_config
from llamaranch.renderer import render_server
from llamaranch.systemd import (
    journalctl_args,
    render_unit,
    systemctl_args,
    unit_name,
    write_unit,
)
from llamaranch.validate import validate_config


class RenderValidateTests(unittest.TestCase):
    def test_render_server_resolves_command_and_unit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_dir, llama_server = write_valid_config(Path(tmp))

            config = load_config(config_dir)
            rendered = render_server(config, "fast-chat")
            command = list(rendered.command)

            self.assertEqual(command[0], str(llama_server))
            self.assertEqual(rendered.unit_name, "llamaranch-fast-chat.service")
            self.assertEqual(rendered.unit_path.name, "llamaranch-fast-chat.service")
            self.assert_flag_value(command, "--model", str(config.models["qwen"].path))
            self.assert_flag_value(command, "--host", "0.0.0.0")
            self.assert_flag_value(command, "--port", "8081")
            self.assert_flag_value(command, "--ctx-size", "32768")
            self.assert_flag_value(command, "--n-gpu-layers", "-1")
            self.assert_flag_value(command, "--main-gpu", "0")
            self.assert_flag_value(command, "--temp", "0.0")
            self.assert_flag_value(command, "--spec-type", "draft-mtp")
            self.assert_flag_value(command, "--spec-draft-n-max", "2")
            self.assertIn("--cache-reuse", command)

    def test_validate_accepts_complete_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_dir, _ = write_valid_config(Path(tmp))

            result = validate_config(load_config(config_dir))

            self.assertTrue(result.ok, [issue.message for issue in result.issues])

    def test_validate_reports_duplicate_ports_and_missing_references(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_dir, _ = write_valid_config(
                Path(tmp),
                servers_yaml="""
servers:
  fast-chat:
    model: qwen
    hardware: theridge-r9700
    host: 0.0.0.0
    port: 8081
  duplicate-port:
    model: qwen
    hardware: theridge-r9700
    port: 8081
  broken:
    model: missing-model
    hardware: missing-hardware
    port: 8082
""",
            )

            result = validate_config(load_config(config_dir))
            messages = "\n".join(issue.message for issue in result.issues)

            self.assertFalse(result.ok)
            self.assertIn("reuses port 8081", messages)
            self.assertIn("references unknown model: missing-model", messages)
            self.assertIn("references unknown hardware target: missing-hardware", messages)

    def test_unit_names_are_deterministic_and_sanitized(self) -> None:
        self.assertEqual(unit_name("fast-chat"), "llamaranch-fast-chat.service")
        self.assertEqual(unit_name("fast chat"), "llamaranch-fast-chat.service")

    def test_render_unit_uses_resolved_command_and_environment(self) -> None:
        unit = render_unit(
            "fast-chat",
            ("/bin/llama-server", "--model", "/models/qwen.gguf"),
            working_dir=Path("/tmp"),
            env={"GGML_VK_VISIBLE_DEVICES": "0"},
        )

        self.assertIn("Description=LlamaRanch server fast-chat", unit)
        self.assertIn("WorkingDirectory=/tmp", unit)
        self.assertIn("Environment=GGML_VK_VISIBLE_DEVICES=0", unit)
        self.assertIn("ExecStart=/bin/llama-server --model /models/qwen.gguf", unit)
        self.assertIn("Restart=on-failure", unit)
        self.assertIn("WantedBy=default.target", unit)

    def test_write_unit_writes_deterministic_user_unit_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_path = write_unit(
                "fast-chat",
                ("/bin/llama-server", "--port", "8081"),
                systemd_user_dir=Path(tmp),
            )

            self.assertEqual(unit_path, Path(tmp) / "llamaranch-fast-chat.service")
            self.assertIn(
                "ExecStart=/bin/llama-server --port 8081",
                unit_path.read_text(encoding="utf-8"),
            )

    def test_systemd_command_builders_are_explicit(self) -> None:
        service = "llamaranch-fast-chat.service"

        self.assertEqual(systemctl_args("daemon-reload"), ("systemctl", "--user", "daemon-reload"))
        self.assertEqual(
            systemctl_args("start", service),
            ("systemctl", "--user", "start", service),
        )
        self.assertEqual(
            journalctl_args(service, lines=50, follow=True),
            ("journalctl", "--user", "-u", service, "-n", "50", "-f"),
        )

    def assert_flag_value(self, command: list[str], flag: str, value: str) -> None:
        index = command.index(flag)
        self.assertEqual(command[index + 1], value)


def write_valid_config(
    root: Path,
    servers_yaml: str | None = None,
) -> tuple[Path, Path]:
    config_dir = root / "config"
    model_dir = root / "models"
    bin_dir = root / "bin"
    config_dir.mkdir()
    model_dir.mkdir()
    bin_dir.mkdir()

    llama_server = bin_dir / "llama-server"
    llama_server.write_text("#!/bin/sh\n", encoding="utf-8")
    os.chmod(llama_server, 0o755)

    model_path = model_dir / "qwen.gguf"
    model_path.write_text("", encoding="utf-8")

    (config_dir / "config.yaml").write_text(
        f"llama_server: {llama_server}\n",
        encoding="utf-8",
    )
    (config_dir / "models.yaml").write_text(
        f"""
models:
  qwen:
    path: {model_path}
    context: 32768
    defaults:
      temperature: 0.0
      spec_type: draft-mtp
      spec_draft_n_max: 2
""",
        encoding="utf-8",
    )
    (config_dir / "hardware.yaml").write_text(
        """
hardware:
  theridge-r9700:
    backend: vulkan
    gpu_layers: -1
    main_gpu: 0
""",
        encoding="utf-8",
    )
    (config_dir / "servers.yaml").write_text(
        servers_yaml
        or """
servers:
  fast-chat:
    model: qwen
    hardware: theridge-r9700
    host: 0.0.0.0
    port: 8081
    enabled: true
    extra_args:
      - --cache-reuse
""",
        encoding="utf-8",
    )

    return config_dir, llama_server


if __name__ == "__main__":
    unittest.main()
