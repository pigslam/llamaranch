from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .config import DEFAULT_CONFIG_DIR, load_config
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
from .validate import validate_config

app = typer.Typer(help="LlamaRanch: llama.cpp deployment manager")
console = Console()


@app.command()
def validate(
    config_dir: Path = typer.Option(
        DEFAULT_CONFIG_DIR,
        "--config-dir",
        "-c",
        help="Configuration directory.",
    ),
) -> None:
    """Validate LlamaRanch configuration without starting services."""
    config = load_config_or_exit(config_dir)
    result = validate_config(config)

    if result.issues:
        table = Table(title="Validation")
        table.add_column("Level")
        table.add_column("Message")
        for issue in result.issues:
            style = "red" if issue.level == "error" else "yellow"
            table.add_row(f"[{style}]{issue.level}[/{style}]", issue.message)
        console.print(table)

    if not result.ok:
        raise typer.Exit(1)

    console.print("[green]Validation passed[/green]")


@app.command()
def render(
    server: str = typer.Argument(..., help="Configured server name."),
    config_dir: Path = typer.Option(
        DEFAULT_CONFIG_DIR,
        "--config-dir",
        "-c",
        help="Configuration directory.",
    ),
    unit: bool = typer.Option(False, "--unit", help="Also print the generated systemd unit."),
) -> None:
    """Render the fully resolved llama-server command."""
    config = load_ready_config_or_exit(config_dir)
    try:
        rendered = render_server(config, server)
    except ValueError as exc:
        raise_error(str(exc))

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
    server: str = typer.Argument(..., help="Configured server name."),
    config_dir: Path = typer.Option(
        DEFAULT_CONFIG_DIR,
        "--config-dir",
        "-c",
        help="Configuration directory.",
    ),
) -> None:
    """Write the user service unit and start a server."""
    rendered = render_configured_server(config_dir, server)
    unit_file = write_unit(rendered.name, rendered.command, env=rendered.hardware.env)
    run_systemd_or_exit("daemon-reload")
    run_systemd_or_exit("start", rendered.unit_name)
    console.print(f"[green]Started[/green] {rendered.unit_name}")
    console.print(f"[dim]Unit:[/dim] {unit_file}")


@app.command()
def stop(
    server: str = typer.Argument(..., help="Configured server name."),
    config_dir: Path = typer.Option(
        DEFAULT_CONFIG_DIR,
        "--config-dir",
        "-c",
        help="Configuration directory.",
    ),
) -> None:
    """Stop a managed user service."""
    rendered = render_configured_server(config_dir, server)
    run_systemd_or_exit("stop", rendered.unit_name)
    console.print(f"[green]Stopped[/green] {rendered.unit_name}")


@app.command()
def restart(
    server: str = typer.Argument(..., help="Configured server name."),
    config_dir: Path = typer.Option(
        DEFAULT_CONFIG_DIR,
        "--config-dir",
        "-c",
        help="Configuration directory.",
    ),
) -> None:
    """Write the latest user service unit and restart a server."""
    rendered = render_configured_server(config_dir, server)
    unit_file = write_unit(rendered.name, rendered.command, env=rendered.hardware.env)
    run_systemd_or_exit("daemon-reload")
    run_systemd_or_exit("restart", rendered.unit_name)
    console.print(f"[green]Restarted[/green] {rendered.unit_name}")
    console.print(f"[dim]Unit:[/dim] {unit_file}")


@app.command()
def enable(
    server: str = typer.Argument(..., help="Configured server name."),
    config_dir: Path = typer.Option(
        DEFAULT_CONFIG_DIR,
        "--config-dir",
        "-c",
        help="Configuration directory.",
    ),
) -> None:
    """Write the user service unit and enable it for login startup."""
    rendered = render_configured_server(config_dir, server)
    unit_file = write_unit(rendered.name, rendered.command, env=rendered.hardware.env)
    run_systemd_or_exit("daemon-reload")
    run_systemd_or_exit("enable", rendered.unit_name)
    console.print(f"[green]Enabled[/green] {rendered.unit_name}")
    console.print(f"[dim]Unit:[/dim] {unit_file}")


@app.command()
def disable(
    server: str = typer.Argument(..., help="Configured server name."),
    config_dir: Path = typer.Option(
        DEFAULT_CONFIG_DIR,
        "--config-dir",
        "-c",
        help="Configuration directory.",
    ),
) -> None:
    """Disable a managed user service from login startup."""
    rendered = render_configured_server(config_dir, server)
    run_systemd_or_exit("disable", rendered.unit_name)
    console.print(f"[green]Disabled[/green] {rendered.unit_name}")


@app.command()
def logs(
    server: str = typer.Argument(..., help="Configured server name."),
    config_dir: Path = typer.Option(
        DEFAULT_CONFIG_DIR,
        "--config-dir",
        "-c",
        help="Configuration directory.",
    ),
    lines: int = typer.Option(100, "--lines", "-n", help="Number of lines to show."),
    follow: bool = typer.Option(True, "--follow/--no-follow", help="Follow log output."),
) -> None:
    """Show journal logs for a managed user service."""
    rendered = render_configured_server(config_dir, server)
    try:
        run_journalctl(rendered.unit_name, lines=lines, follow=follow)
    except (SystemdError, ValueError) as exc:
        raise_error(str(exc))


@app.command("list")
def list_servers(
    config_dir: Path = typer.Option(
        DEFAULT_CONFIG_DIR,
        "--config-dir",
        "-c",
        help="Configuration directory.",
    ),
) -> None:
    """List configured servers."""
    config = load_ready_config_or_exit(config_dir)
    print_server_table(config, include_state=False)


@app.command()
def roundup(
    config_dir: Path = typer.Option(
        DEFAULT_CONFIG_DIR,
        "--config-dir",
        "-c",
        help="Configuration directory.",
    ),
) -> None:
    """Show an operational overview of configured servers."""
    config = load_ready_config_or_exit(config_dir)
    print_server_table(config, include_state=True)


@app.command()
def status(
    server: str | None = typer.Argument(None, help="Optional configured server name."),
    config_dir: Path = typer.Option(
        DEFAULT_CONFIG_DIR,
        "--config-dir",
        "-c",
        help="Configuration directory.",
    ),
) -> None:
    """Show configured server status."""
    config = load_ready_config_or_exit(config_dir)
    if server is not None and server not in config.servers:
        raise_error(f"unknown server: {server}")

    print_server_table(config, include_state=True, only_server=server)


def print_server_table(config, include_state: bool, only_server: str | None = None) -> None:
    table = Table(title="LlamaRanch Servers")
    if include_state:
        table.add_column("State")
    table.add_column("Server")
    table.add_column("Enabled")
    table.add_column("Host")
    table.add_column("Port")
    table.add_column("Model")
    table.add_column("Hardware")

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
        table.add_row(*row)

    console.print(table)


def load_config_or_exit(config_dir: Path):
    try:
        return load_config(config_dir)
    except ConfigError as exc:
        raise_error(str(exc))


def load_ready_config_or_exit(config_dir: Path):
    config = load_config_or_exit(config_dir)
    if config.missing_files:
        missing = ", ".join(config.missing_files)
        raise_error(f"missing config files in {config.config_dir}: {missing}")
    return config


def render_configured_server(config_dir: Path, server: str):
    config = load_ready_config_or_exit(config_dir)
    try:
        return render_server(config, server)
    except ValueError as exc:
        raise_error(str(exc))


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
