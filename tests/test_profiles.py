from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from llamaranch.config import load_profile_config
from llamaranch.profiles import (
    ProfileExistsError,
    ProfileInUseError,
    clone_profile,
    create_profile,
    delete_profile,
    normalize_profile_name,
    profile_summaries,
)
from llamaranch.systemd import unit_name


class ProfileManagementTests(unittest.TestCase):
    def test_create_profile_writes_template_and_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            configs_dir = Path(tmp) / "configs"

            path = create_profile("coder", configs_dir)

            self.assertEqual(path, configs_dir / "coder.yaml")
            self.assertIn("server:", path.read_text(encoding="utf-8"))
            with self.assertRaises(ProfileExistsError):
                create_profile("coder", configs_dir)

    def test_clone_profile_copies_source_to_destination_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            configs_dir, source_path, _ = write_profile_config(Path(tmp), "fast-chat")

            copied_from, copied_to = clone_profile("fast-chat", "fast-chat2", configs_dir)
            config = load_profile_config("fast-chat2", configs_dir)

            self.assertEqual(copied_from, source_path)
            self.assertEqual(copied_to, configs_dir / "fast-chat2.yaml")
            self.assertEqual(
                copied_to.read_text(encoding="utf-8"),
                source_path.read_text(encoding="utf-8"),
            )
            self.assertIn("fast-chat2", config.servers)

    def test_delete_profile_refuses_running_profile_unless_forced(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            configs_dir, profile_path, _ = write_profile_config(Path(tmp), "coder")

            with self.assertRaises(ProfileInUseError):
                delete_profile("coder", configs_dir, state_checker=active_coder_only)

            self.assertTrue(profile_path.exists())
            deleted = delete_profile(
                "coder",
                configs_dir,
                force=True,
                state_checker=active_coder_only,
            )

            self.assertEqual(deleted, profile_path)
            self.assertFalse(profile_path.exists())

    def test_profile_summaries_include_state_port_model_and_invalid_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            configs_dir, _, _ = write_profile_config(Path(tmp), "coder")
            (configs_dir / "broken.yaml").write_text("models: []\n", encoding="utf-8")

            summaries = profile_summaries(configs_dir, state_checker=inactive)

            by_profile = {summary.profile: summary for summary in summaries}
            self.assertEqual(by_profile["coder"].state, "inactive")
            self.assertEqual(by_profile["coder"].port, "8081")
            self.assertEqual(by_profile["coder"].model, "qwen")
            self.assertEqual(by_profile["broken"].state, "invalid")
            self.assertTrue(by_profile["broken"].note)

    def test_normalize_profile_name_accepts_optional_yaml_suffix(self) -> None:
        self.assertEqual(normalize_profile_name("coder.yaml"), "coder")
        self.assertEqual(normalize_profile_name("coder.v2"), "coder.v2")
        with self.assertRaises(ValueError):
            normalize_profile_name("../coder")


def active_coder_only(service: str) -> str:
    if service == unit_name("coder"):
        return "active"
    return "inactive"


def inactive(service: str) -> str:
    return "inactive"


def write_profile_config(root: Path, profile_name: str) -> tuple[Path, Path, Path]:
    configs_dir = root / "configs"
    model_dir = root / "models"
    bin_dir = root / "bin"
    configs_dir.mkdir()
    model_dir.mkdir()
    bin_dir.mkdir()

    llama_server = bin_dir / "llama-server"
    llama_server.write_text("#!/bin/sh\n", encoding="utf-8")
    os.chmod(llama_server, 0o755)

    model_path = model_dir / "qwen.gguf"
    model_path.write_text("", encoding="utf-8")

    profile_path = configs_dir / f"{profile_name}.yaml"
    profile_path.write_text(
        f"""
config:
  llama_server: {llama_server}

models:
  qwen:
    path: {model_path}
    context: 32768
    defaults:
      temperature: 0.0

hardware:
  theridge-r9700:
    backend: vulkan
    gpu_layers: -1
    main_gpu: 0

server:
  model: qwen
  hardware: theridge-r9700
  host: 0.0.0.0
  port: 8081
  enabled: true
  extra_args: []
""",
        encoding="utf-8",
    )

    return configs_dir, profile_path, llama_server


if __name__ == "__main__":
    unittest.main()
