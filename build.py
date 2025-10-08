#!/usr/bin/env python3
import sys
import os
import subprocess
import shutil
import argparse
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

console = Console()

builder_banner = """
██████╗ ██╗   ██╗██╗██╗     ██████╗ ███████╗██████╗     ███████╗ ██████╗██████╗ ██╗██████╗ ████████╗
██╔══██╗██║   ██║██║██║     ██╔══██╗██╔════╝██╔══██╗    ██╔════╝██╔════╝██╔══██╗██║██╔══██╗╚══██╔══╝
██████╔╝██║   ██║██║██║     ██║  ██║█████╗  ██████╔╝    ███████╗██║     ██████╔╝██║██████╔╝   ██║   
██╔══██╗██║   ██║██║██║     ██║  ██║██╔══╝  ██╔══██╗    ╚════██║██║     ██╔══██╗██║██╔═══╝    ██║   
██████╔╝╚██████╔╝██║███████╗██████╔╝███████╗██║  ██║    ███████║╚██████╗██║  ██║██║██║        ██║   
╚═════╝  ╚═════╝ ╚═╝╚══════╝╚═════╝ ╚══════╝╚═╝  ╚═╝    ╚══════╝ ╚═════╝╚═╝  ╚═╝╚═╝╚═╝        ╚═╝   
"""

builder_logo = """
  ________________________
 '------------------------'
  |__ '==' ------ '==' __|
    |                  |
    |__________________|
"""

def run_build(client_file: str, output_name: str, logo_file: str):
    """Run PyInstaller with live Rich logging and optional logo/output."""
    if not os.path.exists(client_file):
        console.print(f"[red]Error: {client_file} not found![/red]")
        sys.exit(1)

    cmd = [sys.executable, "-m", "PyInstaller", "--onefile", client_file]

    if output_name:
        cmd += ["--name", output_name]
    if logo_file:
        if not os.path.exists(logo_file):
            console.print(f"[yellow]Warning: Logo file '{logo_file}' not found. Skipping.[/yellow]")
        else:
            cmd += ["--icon", logo_file]

    # Startup alert panel
    console.print(
        Panel(
            f"[bold cyan]Preparing to build:[/bold cyan]\n"
            f"[green]Client file:[/green] {client_file}\n"
            f"[green]Output name:[/green] {output_name or client_file.replace('.py','')}\n"
            f"[green]Logo:[/green] {logo_file or 'None'}",
            title="Build Info",
            style="bold magenta",
        )
    )

    log_text = Text()
    panel = Panel(log_text, title="Build Output", style="cyan")

    console.print(Panel("[bold magenta]Starting client build...[/bold magenta]", style="magenta"))

    with Live(panel, refresh_per_second=4, console=console):
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
        )
        for line in process.stdout:
            log_text.append(line)
            log_text.append("\n")
        process.wait()

    if process.returncode == 0:
        console.print(
            Panel(
                f"[green]Build complete![/green]\nExecutable available in ./dist/{output_name or client_file.replace('.py','')}",
                title="Build Success",
                style="bold green",
            )
        )
    else:
        console.print(
            Panel(
                "[red]Build failed! Check above logs for details.[/red]",
                title="Build Error",
                style="bold red",
            )
        )

    # Optional cleanup
    for artifact in ["build", f"{client_file.split('.')[0]}.spec"]:
        if os.path.exists(artifact):
            if os.path.isdir(artifact):
                shutil.rmtree(artifact)
            else:
                os.remove(artifact)


def main():
    parser = argparse.ArgumentParser(
        description="Rich PyInstaller Builder",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--client", default="client.py", help="Python client file to build")
    parser.add_argument("--output", default="", help="Name of the output executable")
    parser.add_argument("--logo", default="", help="Path to icon/logo file for executable")
    args = parser.parse_args()

    # Banner + logo
    console.print(builder_banner, style="bold cyan")
    console.print(builder_logo, style="bold yellow")

    run_build(args.client, args.output, args.logo)


if __name__ == "__main__":
    main()

