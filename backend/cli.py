#!/usr/bin/env python3
"""
EvoTraders CLI - Command-line interface for the EvoTraders trading system.

This module provides easy-to-use commands for running backtest, live trading,
and frontend development server.
"""

import sys
import os
import subprocess
from pathlib import Path
from typing import Optional
from datetime import datetime

import typer
from rich.console import Console
from rich.panel import Panel
from rich import print as rprint

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
):
    """
    Run backtest mode with historical data.
    
    Example:
        evotraders backtest --start 2025-11-01 --end 2025-12-01
        evotraders backtest --config-name my_strategy --port 9000
    """
    console.print(Panel.fit(
        "[bold cyan]EvoTraders Backtest Mode[/bold cyan]",
        border_style="cyan"
    ))
    
    # Validate dates if provided
    if start:
        try:
            datetime.strptime(start, "%Y-%m-%d")
        except ValueError:
            console.print("[red]❌ Invalid start date format. Use YYYY-MM-DD[/red]")
            raise typer.Exit(1)
    
    if end:
        try:
            datetime.strptime(end, "%Y-%m-%d")
        except ValueError:
            console.print("[red]❌ Invalid end date format. Use YYYY-MM-DD[/red]")
            raise typer.Exit(1)
    
    # Build command
    cmd = [
        sys.executable,
        "-u",
        "-m",
        "backend.servers.server",
        "--backtest",
        "--config-name", config_name,
        "--host", host,
        "--port", str(port),
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
        console.print(f"\n[red]Backtest failed with exit code {e.returncode}[/red]")
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
):
    """
    Run live trading mode with real-time data.
    
    Example:
        evotraders live
        evotraders live --mock
        evotraders live --pause-before-trade
        evotraders live --mock --virtual-start-time "2024-11-12 22:25:00"
    """
    mode_name = "MOCK" if mock else "LIVE"
    console.print(Panel.fit(
        f"[bold cyan]EvoTraders {mode_name} Mode[/bold cyan]",
        border_style="cyan"
    ))
    
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
                console.print("\n[red]Error: Please edit .env and set FINNHUB_API_KEY[/red]")
                console.print("Get your free API key at: https://finnhub.io/register\n")
                raise typer.Exit(1)
            else:
                console.print("[red]Error: env.template not found[/red]")
                raise typer.Exit(1)
    
    # Build command
    cmd = [
        sys.executable,
        "-u",
        "backend/servers/live_server.py",
        "--config-name", config_name,
        "--host", host,
        "--port", str(port),
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
    console.print(f"   Mode: {mode_name}")
    console.print(f"   Config: {config_name}")
    console.print(f"   Server: {host}:{port}")
    if pause_before_trade:
        console.print("   Trading: Paused (analysis only)")
    else:
        console.print("   Trading: Active")
    if mock:
        console.print("   Data: Simulated prices")
        if virtual_start_time:
            console.print(f"   Virtual Time: {virtual_start_time}")
    else:
        console.print("   Data: Real-time (Finnhub API)")
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
        console.print(f"\n[red]Live server failed with exit code {e.returncode}[/red]")
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
    console.print(Panel.fit(
        "[bold cyan]EvoTraders Frontend[/bold cyan]",
        border_style="cyan"
    ))
    
    project_root = get_project_root()
    frontend_dir = project_root / "frontend"
    
    # Check if frontend directory exists
    if not frontend_dir.exists():
        console.print(f"\n[red]Error: Frontend directory not found: {frontend_dir}[/red]")
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
        console.print(f"\n[red]Frontend failed with exit code {e.returncode}[/red]")
        raise typer.Exit(1)


@app.command()
def version():
    """Show the version of EvoTraders."""
    console.print("\n[bold cyan]EvoTraders[/bold cyan] version [green]0.1.0[/green]\n")


@app.callback()
def main():
    """
    EvoTraders: A self-evolving multi-agent trading system
    
    Use 'evotraders --help' to see available commands.
    """
    pass


if __name__ == "__main__":
    app()

