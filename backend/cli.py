#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EvoTraders CLI - Command-line interface for the EvoTraders trading system.

This module provides easy-to-use commands for running backtest, live trading,
and frontend development server.
"""

import sys
import os
import subprocess
import shutil
from pathlib import Path
from typing import Optional
from datetime import datetime

import typer
from rich.console import Console
from rich.panel import Panel
from rich import print as rprint
from rich.prompt import Confirm

from backend.config.path_config import get_logs_and_memory_dir

app = typer.Typer(
    name="evotraders",
    help="EvoTraders: A self-evolving multi-agent trading system",
    add_completion=False,
)

console = Console()


def get_project_root() -> Path:
    """Get the project root directory."""
    # Assuming cli.py is in backend/
    return Path(__file__).parent.parent


def handle_history_cleanup(config_name: str, auto_clean: bool = False) -> None:
    """
    Handle cleanup of historical data for a given config.

    Args:
        config_name: Configuration name for the run
        auto_clean: If True, skip confirmation and clean automatically
    """
    logs_and_memory_dir = get_logs_and_memory_dir()
    base_data_dir = logs_and_memory_dir / config_name

    # Check if historical data exists
    if not base_data_dir.exists() or not any(base_data_dir.iterdir()):
        console.print(
            f"\n[dim]No historical data found for config '{config_name}'[/dim]",
        )
        console.print("[dim]   Will start from scratch[/dim]\n")
        return

    console.print("\n[bold yellow]Detected existing run data:[/bold yellow]")
    console.print(f"   Data directory: [cyan]{base_data_dir}[/cyan]")

    # Show directory size
    try:
        total_size = sum(
            f.stat().st_size for f in base_data_dir.rglob("*") if f.is_file()
        )
        size_mb = total_size / (1024 * 1024)
        if size_mb < 1:
            console.print(
                f"   Directory size: [cyan]{total_size / 1024:.1f} KB[/cyan]",
            )
        else:
            console.print(f"   Directory size: [cyan]{size_mb:.1f} MB[/cyan]")
    except Exception:
        pass

    # Show last modified time
    state_dir = base_data_dir / "state"
    if state_dir.exists():
        state_files = list(state_dir.glob("*.json"))
        if state_files:
            last_modified = max(f.stat().st_mtime for f in state_files)
            last_modified_str = datetime.fromtimestamp(last_modified).strftime(
                "%Y-%m-%d %H:%M:%S",
            )
            console.print(f"   Last updated: [cyan]{last_modified_str}[/cyan]")

    console.print()

    # Determine if we should clean
    should_clean = auto_clean
    if not auto_clean:
        should_clean = Confirm.ask(
            "   ﹂ Clear historical data and start fresh?",
            default=False,
        )
    else:
        console.print("[yellow]⚠️  Auto-clean enabled (--clean flag)[/yellow]")
        should_clean = True

    if should_clean:
        console.print("\n[yellow]▩  Cleaning historical data...[/yellow]")

        # Backup important config files if they exist
        backup_files = [".env", "config.json"]
        backed_up = []
        backup_dir = None

        for backup_file in backup_files:
            file_path = base_data_dir / backup_file
            if file_path.exists():
                if backup_dir is None:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_dir = (
                        base_data_dir.parent
                        / f"{config_name}_backup_{timestamp}"
                    )
                    backup_dir.mkdir(parents=True, exist_ok=True)

                shutil.copy(file_path, backup_dir / backup_file)
                backed_up.append(backup_file)

        if backed_up:
            console.print(
                f"   💾 Backed up config files to: [cyan]{backup_dir}[/cyan]",
            )
            console.print(f"      Files: {', '.join(backed_up)}")

        # Remove the data directory
        try:
            shutil.rmtree(base_data_dir)
            console.print("   ✔ Historical data cleared\n")
        except Exception as e:
            console.print(f"   [red]✗ Error clearing data: {e}[/red]\n")
            raise typer.Exit(1)
    else:
        console.print(
            "\n[dim]  Continuing with existing historical data[/dim]\n",
        )


@app.command()
def backtest(
    start: Optional[str] = typer.Option(
        None,
        "--start",
        "-s",
        help="Start date for backtest (YYYY-MM-DD)",
    ),
    end: Optional[str] = typer.Option(
        None,
        "--end",
        "-e",
        help="End date for backtest (YYYY-MM-DD)",
    ),
    config_name: str = typer.Option(
        "backtest",
        "--config-name",
        "-c",
        help="Configuration name for this backtest run",
    ),
    host: str = typer.Option(
        "0.0.0.0",
        "--host",
        help="WebSocket server host",
    ),
    port: int = typer.Option(
        8765,
        "--port",
        "-p",
        help="WebSocket server port",
    ),
    clean: bool = typer.Option(
        False,
        "--clean",
        help="Clear historical data before starting",
    ),
):
    """
    Run backtest mode with historical data.

    Example:
        evotraders backtest --start 2025-11-01 --end 2025-12-01
        evotraders backtest --config-name my_strategy --port 9000
        evotraders backtest --clean  # Clear historical data before starting
    """
    console.print(
        Panel.fit(
            "[bold cyan]EvoTraders Backtest Mode[/bold cyan]",
            border_style="cyan",
        ),
    )

    # Validate dates if provided
    if start:
        try:
            datetime.strptime(start, "%Y-%m-%d")
        except ValueError:
            console.print(
                "[red]✗ Invalid start date format. Use YYYY-MM-DD[/red]",
            )
            raise typer.Exit(1)

    if end:
        try:
            datetime.strptime(end, "%Y-%m-%d")
        except ValueError:
            console.print(
                "[red]✗ Invalid end date format. Use YYYY-MM-DD[/red]",
            )
            raise typer.Exit(1)

    # Handle historical data cleanup
    handle_history_cleanup(config_name, auto_clean=clean)

    # Build command
    cmd = [
        sys.executable,
        "-u",
        "-m",
        "backend.servers.server",
        "--config-name",
        config_name,
        "--host",
        host,
        "--port",
        str(port),
    ]

    if start:
        cmd.extend(["--start-date", start])
    if end:
        cmd.extend(["--end-date", end])

    # Display configuration
    console.print("\n[bold]Configuration:[/bold]")
    console.print(f"   Mode: Backtest")
    console.print(f"   Config: {config_name}")
    if start:
        console.print(f"   Start Date: {start}")
    if end:
        console.print(f"   End Date: {end}")
    console.print(f"   Server: {host}:{port}")
    console.print(f"\nAccess at: [cyan]http://localhost:{port}[/cyan]")
    console.print("Press Ctrl+C to stop\n")

    # Change to project root and run
    project_root = get_project_root()
    os.chdir(project_root)

    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Backtest stopped by user[/yellow]")
    except subprocess.CalledProcessError as e:
        console.print(
            f"\n[red]Backtest failed with exit code {e.returncode}[/red]",
        )
        raise typer.Exit(1)


@app.command()
def live(
    mock: bool = typer.Option(
        False,
        "--mock",
        help="Use mock mode with simulated prices (for testing)",
    ),
    config_name: str = typer.Option(
        "live_mode",
        "--config-name",
        "-c",
        help="Configuration name for this live run",
    ),
    host: str = typer.Option(
        "0.0.0.0",
        "--host",
        help="WebSocket server host",
    ),
    port: int = typer.Option(
        8766,
        "--port",
        "-p",
        help="WebSocket server port",
    ),
    pause_before_trade: bool = typer.Option(
        False,
        "--pause-before-trade",
        help="Pause mode: complete analysis but don't execute trades",
    ),
    time_accelerator: float = typer.Option(
        1.0,
        "--time-accelerator",
        help="Time acceleration factor (e.g., 60.0 = 1 minute = 1 hour)",
    ),
    virtual_start_time: Optional[str] = typer.Option(
        None,
        "--virtual-start-time",
        help="Virtual start time for mock mode (YYYY-MM-DD HH:MM:SS)",
    ),
    clean: bool = typer.Option(
        False,
        "--clean",
        help="Clear historical data before starting",
    ),
):
    """
    Run live trading mode with real-time data.

    Example:
        evotraders live
        evotraders live --mock
        evotraders live --pause-before-trade
        evotraders live --mock --virtual-start-time "2024-11-12 22:25:00"
        evotraders live --clean  # Clear historical data before starting
    """
    mode_name = "MOCK" if mock else "LIVE"
    console.print(
        Panel.fit(
            f"[bold cyan]EvoTraders {mode_name} Mode[/bold cyan]",
            border_style="cyan",
        ),
    )

    # Check for required API key in live mode
    if not mock:
        env_file = get_project_root() / ".env"
        if not env_file.exists():
            console.print("\n[yellow]Warning: .env file not found[/yellow]")
            console.print("Creating from template...\n")
            template = get_project_root() / "env.template"
            if template.exists():
                import shutil

                shutil.copy(template, env_file)
                console.print("[green].env file created[/green]")
                console.print(
                    "\n[red]Error: Please edit .env and set FINNHUB_API_KEY[/red]",
                )
                console.print(
                    "Get your free API key at: https://finnhub.io/register\n",
                )
                raise typer.Exit(1)
            else:
                console.print("[red]Error: env.template not found[/red]")
                raise typer.Exit(1)

    # Handle historical data cleanup
    handle_history_cleanup(config_name, auto_clean=clean)

    # Build command
    cmd = [
        sys.executable,
        "-u",
        "-m",
        "backend.servers.live_server",
        "--config-name",
        config_name,
        "--host",
        host,
        "--port",
        str(port),
    ]

    if mock:
        cmd.append("--mock")
    if pause_before_trade:
        cmd.append("--pause-before-trade")
    if time_accelerator != 1.0:
        cmd.extend(["--time-accelerator", str(time_accelerator)])
    if virtual_start_time:
        cmd.extend(["--virtual-start-time", virtual_start_time])

    # Display configuration
    console.print("\n[bold]Configuration:[/bold]")
    if mock:
        console.print(f"   Mode: MOCK (Simulated prices for testing)")
        console.print(
            f"   Description: Uses randomly generated prices, no API key required",
        )
    else:
        console.print(f"   Mode: LIVE (Real-time prices via Finnhub API)")
        console.print(
            f"   Description: High-frequency real-time price updates using Finnhub Quote API",
        )
    console.print(f"   Config Name: {config_name}")
    console.print(f"   Listen Address: {host}:{port}")
    if pause_before_trade:
        console.print("   Trading Mode: Paused (analysis only, no execution)")
    else:
        console.print("   Trading Mode: Active (analysis and execution)")
    console.print(f"   Historical Data: Continue using existing data")

    console.print("\n[bold]Functionality:[/bold]")
    console.print(
        "   Real-time stock price board updates immediately after startup",
    )
    if mock and virtual_start_time:
        console.print(f"   1. System will run using virtual time as 'today'")
        console.print(f"      Reference time: {virtual_start_time}")
    else:
        console.print("   1. System will run for today's trading day")
    console.print(
        "   2. First day startup: Run pre-market analysis immediately (generate signals)",
    )
    console.print("   3. Trading cycle:")
    console.print("      - Daily at 22:30:15: Run pre-market analysis (func1)")
    console.print(
        "      - Daily at 05:05: Execute trades (func2) + update previous day agent performance",
    )
    if mock:
        console.print(
            "   4. Mock mode generates simulated price updates every 5 seconds",
        )
    else:
        console.print(
            "   4. Real-time prices update every 10 seconds (Finnhub Quote API)",
        )
    console.print(
        "   5. Real-time updates: stock prices, returns, portfolio value curve, position P&L",
    )

    console.print(f"\nAccess at: [cyan]http://localhost:{port}[/cyan]")
    console.print("Press Ctrl+C to stop\n")

    # Change to project root and run
    project_root = get_project_root()
    os.chdir(project_root)

    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Live server stopped by user[/yellow]")
    except subprocess.CalledProcessError as e:
        console.print(
            f"\n[red]Live server failed with exit code {e.returncode}[/red]",
        )
        raise typer.Exit(1)


@app.command()
def frontend(
    port: int = typer.Option(
        8765,
        "--ws-port",
        "-p",
        help="WebSocket server port to connect to",
    ),
    host_mode: bool = typer.Option(
        False,
        "--host",
        help="Allow external access (default: localhost only)",
    ),
):
    """
    Start the frontend development server.

    Example:
        evotraders frontend
        evotraders frontend --ws-port 8766
        evotraders frontend --ws-port 8766 --host
    """
    console.print(
        Panel.fit(
            "[bold cyan]EvoTraders Frontend[/bold cyan]",
            border_style="cyan",
        ),
    )

    project_root = get_project_root()
    frontend_dir = project_root / "frontend"

    # Check if frontend directory exists
    if not frontend_dir.exists():
        console.print(
            f"\n[red]Error: Frontend directory not found: {frontend_dir}[/red]",
        )
        raise typer.Exit(1)

    # Check if node_modules exists
    node_modules = frontend_dir / "node_modules"
    if not node_modules.exists():
        console.print("\n[yellow]Installing frontend dependencies...[/yellow]")
        try:
            subprocess.run(
                ["npm", "install"],
                cwd=frontend_dir,
                check=True,
            )
            console.print("[green]Dependencies installed[/green]\n")
        except subprocess.CalledProcessError:
            console.print("\n[red]Error: Failed to install dependencies[/red]")
            console.print("Make sure Node.js and npm are installed")
            raise typer.Exit(1)

    # Set WebSocket URL environment variable
    ws_url = f"ws://localhost:{port}"
    env = os.environ.copy()
    env["VITE_WS_URL"] = ws_url

    # Display configuration
    console.print("\n[bold]Configuration:[/bold]")
    console.print(f"   WebSocket URL: {ws_url}")
    console.print(f"   Frontend Port: 5173 (Vite default)")
    if host_mode:
        console.print("   Access: External allowed")
    else:
        console.print("   Access: Localhost only")
    console.print(f"\nAccess at: [cyan]http://localhost:5173[/cyan]")
    console.print("Press Ctrl+C to stop\n")

    # Choose npm command
    npm_cmd = ["npm", "run", "dev:host" if host_mode else "dev"]

    try:
        subprocess.run(
            npm_cmd,
            cwd=frontend_dir,
            env=env,
            check=True,
        )
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Frontend stopped by user[/yellow]")
    except subprocess.CalledProcessError as e:
        console.print(
            f"\n[red]Frontend failed with exit code {e.returncode}[/red]",
        )
        raise typer.Exit(1)


@app.command()
def version():
    """Show the version of EvoTraders."""
    console.print(
        "\n[bold cyan]EvoTraders[/bold cyan] version [green]0.1.0[/green]\n",
    )


@app.callback()
def main():
    """
    EvoTraders: A self-evolving multi-agent trading system

    Use 'evotraders --help' to see available commands.
    """
    pass


if __name__ == "__main__":
    app()
