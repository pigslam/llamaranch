from __future__ import annotations

import os
from pathlib import Path
import shlex
import subprocess

import typer
from rich.console import Console
from rich.table import Table

from .config import (
    DEFAULT_CONFIG_DIR,
    DEFAULT_CONFIGS_DIR,
    ConfigNotFoundError,
    RanchConfig,
    list_profile_paths,
    load_config,
    load_config_file,
    load_profile_config,
    resolve_profile_path,
)
from .renderer import render_server
from .schema import ConfigError
from .systemd import (
    SystemdError,
    run_journalctl,
    run_systemctl,
    service_state,
    unit_name,
    write_unit,
)
from .profiles import (
    ProfileSummary,
    clone_profile,
    create_profile,
    delete_profile,
    profile_summaries,
    running_profile_services,
)
from .validate import ValidationResult, validate_config

app = typer.Typer(help="LlamaRanch: llama.cpp deployment manager")
console = Console()

CONFIG_REF_HELP = "Config profile name/path, or legacy server name."
LEGACY_CONFIG_DIR_HELP = "Legacy four-file configuration directory."
PROFILE_CONFIGS_DIR_HELP = "Directory containing single-file config profiles."


@app.command("new")
def new_profile(
    name: str = typer.Argument(..., help="Profile name to create."),
    configs_dir: Path = typer.Option(
        DEFAULT_CONFIGS_DIR,
        "--configs-dir",
        help=PROFILE_CONFIGS_DIR_HELP,
    ),
) -> None:
    """Create a new profile from the built-in template."""
    try:
        path = create_profile(name, configs_dir)
    except ConfigError as exc:
        raise_error(str(exc))

    console.print(f"[green]Created[/green] {path}")


@app.command()
def edit(
    name: str = typer.Argument(..., help="Profile name/path to edit."),
    configs_dir: Path = typer.Option(
        DEFAULT_CONFIGS_DIR,
        "--configs-dir",
        help=PROFILE_CONFIGS_DIR_HELP,
    ),
) -> None:
    """Open a profile in $VISUAL, $EDITOR, or nano."""
    try:
        path = resolve_profile_path(name, configs_dir)
    except ConfigError as exc:
        raise_error(str(exc))

    command = editor_command()
    try:
        result = subprocess.run((*command, str(path)), check=False)
    except FileNotFoundError:
        raise_error(f"editor not found: {command[0]}")

    if result.returncode != 0:
        raise_error(f"editor exited with status {result.returncode}: {shlex.join(command)}")


@app.command("clone")
def clone_profile_command(
    source: str = typer.Argument(..., help="Existing profile name/path."),
    destination: str = typer.Argument(..., help="Destination profile name."),
    configs_dir: Path = typer.Option(
        DEFAULT_CONFIGS_DIR,
        "--configs-dir",
        help=PROFILE_CONFIGS_DIR_HELP,
    ),
) -> None:
    """Copy an existing profile to a new profile name."""
    try:
        source_path, destination_path = clone_profile(source, destination, configs_dir)
    except ConfigError as exc:
        raise_error(str(exc))

    console.print(f"[green]Cloned[/green] {source_path} -> {destination_path}")


@app.command("delete")
def delete_profile_command(
    name: str = typer.Argument(..., help="Profile name/path to delete."),
    configs_dir: Path = typer.Option(
        DEFAULT_CONFIGS_DIR,
        "--configs-dir",
        help=PROFILE_CONFIGS_DIR_HELP,
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Delete even if the profile's service appears to be running.",
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip the confirmation prompt."),
) -> None:
    """Delete a profile after confirmation."""
    try:
        path = resolve_profile_path(name, configs_dir)
        running = running_profile_services(path)
    except ConfigError as exc:
        raise_error(str(exc))

    if running and not force:
        services = ", ".join(f"{server} ({state})" for server, state in running)
        raise_error(f"profile appears to be running as {services}; stop it first or pass --force")

    if not yes:
        prompt = f"Delete profile '{path.stem}' at {path}?"
        if running:
            services = ", ".join(f"{server} ({state})" for server, state in running)
            prompt = f"Delete running profile '{path.stem}' at {path} ({services})?"
        if not typer.confirm(prompt):
            console.print("Aborted")
            raise typer.Exit()

    try:
        deleted_path = delete_profile(path, configs_dir, force=force)
    except ConfigError as exc:
        raise_error(str(exc))

    console.print(f"[green]Deleted[/green] {deleted_path}")


@app.command()
def validate(
    config_ref: str | None = typer.Argument(None, help="Optional config profile name/path."),
    config_dir: Path = typer.Option(
        DEFAULT_CONFIG_DIR,
        "--config-dir",
        "-c",
        help=LEGACY_CONFIG_DIR_HELP,
    ),
    configs_dir: Path = typer.Option(
        DEFAULT_CONFIGS_DIR,
        "--configs-dir",
        help=PROFILE_CONFIGS_DIR_HELP,
    ),
) -> None:
    """Validate LlamaRanch configuration without starting services."""
    configs = load_validation_configs_or_exit(config_ref, config_dir, configs_dir)
    ok = True

    for config in configs:
        result = validate_config(config)
        print_validation_result(result, config)
        ok = ok and result.ok

    if not ok:
        raise typer.Exit(1)

    console.print("[green]Validation passed[/green]")


@app.command()
def render(
    config_ref: str = typer.Argument(..., help=CONFIG_REF_HELP),
    config_dir: Path = typer.Option(
        DEFAULT_CONFIG_DIR,
        "--config-dir",
        "-c",
        help=LEGACY_CONFIG_DIR_HELP,
    ),
    configs_dir: Path = typer.Option(
        DEFAULT_CONFIGS_DIR,
        "--configs-dir",
        help=PROFILE_CONFIGS_DIR_HELP,
    ),
    server: str | None = typer.Option(
        None,
        "--server",
        "-s",
        help="Server name inside a multi-server config profile.",
    ),
    unit: bool = typer.Option(False, "--unit", help="Also print the generated systemd unit."),
) -> None:
    """Render the fully resolved llama-server command."""
    rendered = render_configured_server(config_ref, config_dir, configs_dir, server)

    console.print(f"[bold]Server[/bold] {rendered.name}")
    console.print(f"[bold]Model[/bold] {rendered.model.name}")
    console.print(f"[bold]Model path[/bold] {rendered.model.path}")
    console.print(f"[bold]Hardware[/bold] {rendered.hardware.name} ({rendered.hardware.backend})")
    console.print(f"[bold]Port[/bold] {rendered.server.host}:{rendered.server.port}")
    console.print(f"[bold]Systemd unit[/bold] {rendered.unit_path}")
    console.print()
    console.print("[bold]Command[/bold]")
    console.print(rendered.command_display)

    if unit:
        from .systemd import render_unit

        console.print()
        console.print("[bold]Unit[/bold]")
        console.print(render_unit(rendered.name, rendered.command, env=rendered.hardware.env))


@app.command()
def start(
    config_ref: str = typer.Argument(..., help=CONFIG_REF_HELP),
    config_dir: Path = typer.Option(
        DEFAULT_CONFIG_DIR,
        "--config-dir",
        "-c",
        help=LEGACY_CONFIG_DIR_HELP,
    ),
    configs_dir: Path = typer.Option(
        DEFAULT_CONFIGS_DIR,
        "--configs-dir",
        help=PROFILE_CONFIGS_DIR_HELP,
    ),
    server: str | None = typer.Option(
        None,
        "--server",
        "-s",
        help="Server name inside a multi-server config profile.",
    ),
) -> None:
    """Write the user service unit and start a server."""
    rendered = render_configured_server(config_ref, config_dir, configs_dir, server)
    unit_file = write_unit(rendered.name, rendered.command, env=rendered.hardware.env)
    run_systemd_or_exit("daemon-reload")
    run_systemd_or_exit("start", rendered.unit_name)
    console.print(f"[green]Started[/green] {rendered.unit_name}")
    console.print(f"[dim]Unit:[/dim] {unit_file}")


@app.command()
def stop(
    config_ref: str = typer.Argument(..., help=CONFIG_REF_HELP),
    config_dir: Path = typer.Option(
        DEFAULT_CONFIG_DIR,
        "--config-dir",
        "-c",
        help=LEGACY_CONFIG_DIR_HELP,
    ),
    configs_dir: Path = typer.Option(
        DEFAULT_CONFIGS_DIR,
        "--configs-dir",
        help=PROFILE_CONFIGS_DIR_HELP,
    ),
    server: str | None = typer.Option(
        None,
        "--server",
        "-s",
        help="Server name inside a multi-server config profile.",
    ),
) -> None:
    """Stop a managed user service."""
    rendered = render_configured_server(config_ref, config_dir, configs_dir, server)
    run_systemd_or_exit("stop", rendered.unit_name)
    console.print(f"[green]Stopped[/green] {rendered.unit_name}")


@app.command()
def restart(
    config_ref: str = typer.Argument(..., help=CONFIG_REF_HELP),
    config_dir: Path = typer.Option(
        DEFAULT_CONFIG_DIR,
        "--config-dir",
        "-c",
        help=LEGACY_CONFIG_DIR_HELP,
    ),
    configs_dir: Path = typer.Option(
        DEFAULT_CONFIGS_DIR,
        "--configs-dir",
        help=PROFILE_CONFIGS_DIR_HELP,
    ),
    server: str | None = typer.Option(
        None,
        "--server",
        "-s",
        help="Server name inside a multi-server config profile.",
    ),
) -> None:
    """Write the latest user service unit and restart a server."""
    rendered = render_configured_server(config_ref, config_dir, configs_dir, server)
    unit_file = write_unit(rendered.name, rendered.command, env=rendered.hardware.env)
    run_systemd_or_exit("daemon-reload")
    run_systemd_or_exit("restart", rendered.unit_name)
    console.print(f"[green]Restarted[/green] {rendered.unit_name}")
    console.print(f"[dim]Unit:[/dim] {unit_file}")


@app.command()
def enable(
    config_ref: str = typer.Argument(..., help=CONFIG_REF_HELP),
    config_dir: Path = typer.Option(
        DEFAULT_CONFIG_DIR,
        "--config-dir",
        "-c",
        help=LEGACY_CONFIG_DIR_HELP,
    ),
    configs_dir: Path = typer.Option(
        DEFAULT_CONFIGS_DIR,
        "--configs-dir",
        help=PROFILE_CONFIGS_DIR_HELP,
    ),
    server: str | None = typer.Option(
        None,
        "--server",
        "-s",
        help="Server name inside a multi-server config profile.",
    ),
) -> None:
    """Write the user service unit and enable it for login startup."""
    rendered = render_configured_server(config_ref, config_dir, configs_dir, server)
    unit_file = write_unit(rendered.name, rendered.command, env=rendered.hardware.env)
    run_systemd_or_exit("daemon-reload")
    run_systemd_or_exit("enable", rendered.unit_name)
    console.print(f"[green]Enabled[/green] {rendered.unit_name}")
    console.print(f"[dim]Unit:[/dim] {unit_file}")


@app.command()
def disable(
    config_ref: str = typer.Argument(..., help=CONFIG_REF_HELP),
    config_dir: Path = typer.Option(
        DEFAULT_CONFIG_DIR,
        "--config-dir",
        "-c",
        help=LEGACY_CONFIG_DIR_HELP,
    ),
    configs_dir: Path = typer.Option(
        DEFAULT_CONFIGS_DIR,
        "--configs-dir",
        help=PROFILE_CONFIGS_DIR_HELP,
    ),
    server: str | None = typer.Option(
        None,
        "--server",
        "-s",
        help="Server name inside a multi-server config profile.",
    ),
) -> None:
    """Disable a managed user service from login startup."""
    rendered = render_configured_server(config_ref, config_dir, configs_dir, server)
    run_systemd_or_exit("disable", rendered.unit_name)
    console.print(f"[green]Disabled[/green] {rendered.unit_name}")


@app.command()
def logs(
    config_ref: str = typer.Argument(..., help=CONFIG_REF_HELP),
    config_dir: Path = typer.Option(
        DEFAULT_CONFIG_DIR,
        "--config-dir",
        "-c",
        help=LEGACY_CONFIG_DIR_HELP,
    ),
    configs_dir: Path = typer.Option(
        DEFAULT_CONFIGS_DIR,
        "--configs-dir",
        help=PROFILE_CONFIGS_DIR_HELP,
    ),
    server: str | None = typer.Option(
        None,
        "--server",
        "-s",
        help="Server name inside a multi-server config profile.",
    ),
    lines: int = typer.Option(100, "--lines", "-n", help="Number of lines to show."),
    follow: bool = typer.Option(True, "--follow/--no-follow", help="Follow log output."),
) -> None:
    """Show journal logs for a managed user service."""
    rendered = render_configured_server(config_ref, config_dir, configs_dir, server)
    try:
        run_journalctl(rendered.unit_name, lines=lines, follow=follow)
    except (SystemdError, ValueError) as exc:
        raise_error(str(exc))


@app.command("list")
def list_profiles(
    configs_dir: Path = typer.Option(
        DEFAULT_CONFIGS_DIR,
        "--configs-dir",
        help=PROFILE_CONFIGS_DIR_HELP,
    ),
) -> None:
    """List available configuration profiles."""
    try:
        summaries = profile_summaries(configs_dir)
    except ConfigError as exc:
        raise_error(str(exc))

    if not summaries:
        console.print(f"[yellow]No profiles found[/yellow] in {configs_dir.expanduser()}")
        return

    print_profile_table(summaries)


@app.command()
def roundup(
    config_ref: str | None = typer.Argument(None, help="Optional config profile name/path."),
    config_dir: Path = typer.Option(
        DEFAULT_CONFIG_DIR,
        "--config-dir",
        "-c",
        help=LEGACY_CONFIG_DIR_HELP,
    ),
    configs_dir: Path = typer.Option(
        DEFAULT_CONFIGS_DIR,
        "--configs-dir",
        help=PROFILE_CONFIGS_DIR_HELP,
    ),
    server: str | None = typer.Option(
        None,
        "--server",
        "-s",
        help="Only show one server inside the selected config.",
    ),
) -> None:
    """Show an operational overview of configured servers."""
    configs = load_overview_configs_or_exit(config_ref, config_dir, configs_dir)
    only_server = overview_server_filter(config_ref, configs, server)
    print_config_table(configs, include_state=True, only_server=only_server)


@app.command()
def status(
    config_ref: str | None = typer.Argument(None, help="Optional config profile name/path."),
    config_dir: Path = typer.Option(
        DEFAULT_CONFIG_DIR,
        "--config-dir",
        "-c",
        help=LEGACY_CONFIG_DIR_HELP,
    ),
    configs_dir: Path = typer.Option(
        DEFAULT_CONFIGS_DIR,
        "--configs-dir",
        help=PROFILE_CONFIGS_DIR_HELP,
    ),
    server: str | None = typer.Option(
        None,
        "--server",
        "-s",
        help="Only show one server inside the selected config.",
    ),
) -> None:
    """Show configured server status."""
    configs = load_overview_configs_or_exit(config_ref, config_dir, configs_dir)
    only_server = overview_server_filter(config_ref, configs, server)
    print_config_table(configs, include_state=True, only_server=only_server)


def print_validation_result(result: ValidationResult, config: RanchConfig) -> None:
    if not result.issues:
        return

    table = Table(title=f"Validation: {config_label(config)}")
    table.add_column("Level")
    table.add_column("Message")
    for issue in result.issues:
        style = "red" if issue.level == "error" else "yellow"
        table.add_row(f"[{style}]{issue.level}[/{style}]", issue.message)
    console.print(table)


def print_profile_table(summaries: tuple[ProfileSummary, ...]) -> None:
    table = Table(title="LlamaRanch Profiles")
    show_notes = any(summary.note for summary in summaries)

    table.add_column("Profile")
    table.add_column("State")
    table.add_column("Port")
    table.add_column("Model")
    if show_notes:
        table.add_column("Notes")

    for summary in summaries:
        row = [summary.profile, summary.state, summary.port, summary.model]
        if show_notes:
            row.append(summary.note)
        table.add_row(*row)

    console.print(table)


def print_config_table(
    configs: list[RanchConfig],
    include_state: bool,
    only_server: str | None = None,
) -> None:
    table = Table(title="LlamaRanch Servers")
    show_config = len(configs) > 1 or any(config.profile_name for config in configs)

    if show_config:
        table.add_column("Config")
    if include_state:
        table.add_column("State")
    table.add_column("Server")
    table.add_column("Enabled")
    table.add_column("Host")
    table.add_column("Port")
    table.add_column("Model")
    table.add_column("Hardware")

    for config in configs:
        for name, server in config.servers.items():
            if only_server is not None and name != only_server:
                continue
            row = [
                name,
                "yes" if server.enabled else "no",
                server.host,
                str(server.port),
                server.model,
                server.hardware,
            ]
            if include_state:
                row.insert(0, service_state(unit_name(name)))
            if show_config:
                row.insert(0, config_label(config))
            table.add_row(*row)

    console.print(table)


def editor_command() -> tuple[str, ...]:
    for variable in ("VISUAL", "EDITOR"):
        value = os.environ.get(variable)
        if value and value.strip():
            return tuple(shlex.split(value))
    return ("nano",)


def load_validation_configs_or_exit(
    config_ref: str | None,
    config_dir: Path,
    configs_dir: Path,
) -> list[RanchConfig]:
    if config_ref is not None:
        return [load_selected_config_or_exit(config_ref, config_dir, configs_dir)]

    profile_configs = load_all_profile_configs_or_exit(configs_dir)
    if profile_configs:
        return profile_configs

    return [load_ready_legacy_config_or_exit(config_dir)]


def load_overview_configs_or_exit(
    config_ref: str | None,
    config_dir: Path,
    configs_dir: Path,
) -> list[RanchConfig]:
    if config_ref is not None:
        return [load_selected_config_or_exit(config_ref, config_dir, configs_dir)]

    profile_configs = load_all_profile_configs_or_exit(configs_dir)
    if profile_configs:
        return profile_configs

    return [load_ready_legacy_config_or_exit(config_dir)]


def load_all_profile_configs_or_exit(configs_dir: Path) -> list[RanchConfig]:
    try:
        paths = list_profile_paths(configs_dir)
        return [load_config_file(path) for path in paths]
    except ConfigError as exc:
        raise_error(str(exc))


def load_selected_config_or_exit(
    config_ref: str,
    config_dir: Path,
    configs_dir: Path,
) -> RanchConfig:
    try:
        return load_profile_config(config_ref, configs_dir)
    except ConfigNotFoundError as profile_exc:
        legacy = load_legacy_config_for_fallback(config_dir)
        if legacy is not None and config_ref in legacy.servers:
            return legacy
        raise_error(str(profile_exc))
    except ConfigError as exc:
        raise_error(str(exc))


def load_legacy_config_for_fallback(config_dir: Path) -> RanchConfig | None:
    try:
        config = load_config(config_dir)
    except ConfigError:
        return None

    if config.missing_files:
        return None
    return config


def load_ready_legacy_config_or_exit(config_dir: Path) -> RanchConfig:
    config = load_config_or_exit(config_dir)
    if config.missing_files:
        missing = ", ".join(config.missing_files)
        raise_error(f"missing config files in {config.config_dir}: {missing}")
    return config


def load_config_or_exit(config_dir: Path) -> RanchConfig:
    try:
        return load_config(config_dir)
    except ConfigError as exc:
        raise_error(str(exc))


def render_configured_server(
    config_ref: str,
    config_dir: Path,
    configs_dir: Path,
    server: str | None,
):
    config = load_selected_config_or_exit(config_ref, config_dir, configs_dir)
    server_name = selected_server_name_or_exit(config, config_ref, server)

    try:
        return render_server(config, server_name)
    except ValueError as exc:
        raise_error(str(exc))


def selected_server_name_or_exit(
    config: RanchConfig,
    config_ref: str,
    server: str | None,
) -> str:
    try:
        return select_server_name(config, config_ref, server)
    except ConfigError as exc:
        raise_error(str(exc))


def select_server_name(config: RanchConfig, config_ref: str, server: str | None) -> str:
    if server is not None:
        config.get_server(server)
        return server

    if config.profile_name is not None and config.profile_name in config.servers:
        return config.profile_name

    if config_ref in config.servers:
        return config_ref

    if len(config.servers) == 1:
        return next(iter(config.servers))

    if not config.servers:
        raise ConfigError(f"{config_label(config)} contains no servers")

    raise ConfigError(f"{config_label(config)} contains multiple servers; pass --server NAME")


def overview_server_filter(
    config_ref: str | None,
    configs: list[RanchConfig],
    server: str | None,
) -> str | None:
    if server is not None:
        ensure_server_exists(configs, server)
        return server

    if config_ref is None or len(configs) != 1:
        return None

    config = configs[0]
    if config.profile_name is not None and config.profile_name in config.servers:
        return config.profile_name
    if config_ref in config.servers:
        return config_ref
    if len(config.servers) == 1:
        return next(iter(config.servers))
    return None


def ensure_server_exists(configs: list[RanchConfig], server: str) -> None:
    for config in configs:
        if server in config.servers:
            return
    raise_error(f"unknown server: {server}")


def config_label(config: RanchConfig) -> str:
    if config.profile_name:
        return config.profile_name
    if config.source:
        return str(config.source)
    return str(config.config_dir)


def run_systemd_or_exit(action: str, service_name: str | None = None) -> None:
    try:
        run_systemctl(action, service_name)
    except (SystemdError, ValueError) as exc:
        raise_error(str(exc))


def raise_error(message: str) -> None:
    console.print(f"[red]Error:[/red] {message}")
    raise typer.Exit(1)


if __name__ == "__main__":
    app()
