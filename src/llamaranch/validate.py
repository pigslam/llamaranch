from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .config import CONFIG_FILES, RanchConfig
from .renderer import RenderError, render_server
from .systemd import unit_name

IssueLevel = Literal["error", "warning"]


@dataclass(frozen=True)
class ValidationIssue:
    level: IssueLevel
    message: str


@dataclass(frozen=True)
class ValidationResult:
    issues: tuple[ValidationIssue, ...]

    @property
    def ok(self) -> bool:
        return not any(issue.level == "error" for issue in self.issues)

    @property
    def errors(self) -> tuple[ValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.level == "error")


def validate_config(config: RanchConfig) -> ValidationResult:
    issues: list[ValidationIssue] = []

    for filename in CONFIG_FILES:
        if filename in config.missing_files:
            issues.append(error(f"missing config file: {config.config_dir / filename}"))

    if not config.models:
        issues.append(error("no models are configured"))
    if not config.hardware:
        issues.append(error("no hardware targets are configured"))
    if not config.servers:
        issues.append(error("no servers are configured"))

    check_executable(config.global_config.llama_server, issues)
    check_model_paths(config, issues)
    check_server_references(config, issues)
    check_ports(config, issues)
    check_unit_names(config, issues)
    check_rendering(config, issues)

    return ValidationResult(tuple(issues))


def check_executable(path: Path, issues: list[ValidationIssue]) -> None:
    if not path.exists():
        issues.append(error(f"llama-server executable does not exist: {path}"))
        return
    if not path.is_file():
        issues.append(error(f"llama-server executable is not a file: {path}"))
        return
    if not os.access(path, os.X_OK):
        issues.append(error(f"llama-server executable is not executable: {path}"))


def check_model_paths(config: RanchConfig, issues: list[ValidationIssue]) -> None:
    for model in config.models.values():
        if not model.path.exists():
            issues.append(error(f"model path does not exist for {model.name}: {model.path}"))
        elif not model.path.is_file():
            issues.append(error(f"model path is not a file for {model.name}: {model.path}"))


def check_server_references(config: RanchConfig, issues: list[ValidationIssue]) -> None:
    for server in config.servers.values():
        if server.model not in config.models:
            issues.append(error(f"server {server.name} references unknown model: {server.model}"))
        if server.hardware not in config.hardware:
            issues.append(
                error(f"server {server.name} references unknown hardware target: {server.hardware}")
            )


def check_ports(config: RanchConfig, issues: list[ValidationIssue]) -> None:
    seen: dict[int, str] = {}
    for server in config.servers.values():
        if server.port < 1 or server.port > 65535:
            issues.append(error(f"server {server.name} uses invalid port: {server.port}"))
            continue
        if server.port in seen:
            issues.append(
                error(
                    f"server {server.name} reuses port {server.port} "
                    f"from server {seen[server.port]}"
                )
            )
        else:
            seen[server.port] = server.name


def check_unit_names(config: RanchConfig, issues: list[ValidationIssue]) -> None:
    seen: dict[str, str] = {}
    for server_name in config.servers:
        name = unit_name(server_name)
        if name in seen:
            issues.append(
                error(
                    f"server {server_name} maps to duplicate systemd unit {name} "
                    f"with server {seen[name]}"
                )
            )
        else:
            seen[name] = server_name


def check_rendering(config: RanchConfig, issues: list[ValidationIssue]) -> None:
    for server_name in config.servers:
        try:
            rendered = render_server(config, server_name)
        except (RenderError, ValueError) as exc:
            issues.append(error(f"server {server_name} cannot render: {exc}"))
            continue
        if not rendered.command:
            issues.append(error(f"server {server_name} rendered an empty command"))


def error(message: str) -> ValidationIssue:
    return ValidationIssue("error", message)

