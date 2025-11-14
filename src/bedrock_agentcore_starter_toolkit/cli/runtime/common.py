"""Common utilities for runtime commands."""

from rich.panel import Panel

from ..common import console


def _show_configuration_not_found_panel():
    """Show standardized configuration not found panel."""
    console.print(
        Panel(
            "⚠️ [yellow]Configuration Not Found[/yellow]\n\n"
            "No agent configuration found in this directory.\n\n"
            "[bold]Get Started:[/bold]\n"
            "   [cyan]agentcore configure --entrypoint your_agent.py[/cyan]\n"
            "   [cyan]agentcore launch[/cyan]\n"
            '   [cyan]agentcore invoke \'{"prompt": "Hello"}\'[/cyan]',
            title="⚠️ Setup Required",
            border_style="bright_blue",
        )
    )
