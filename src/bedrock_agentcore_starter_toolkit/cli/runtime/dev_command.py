"""Development server command for Bedrock AgentCore CLI."""

import logging
import os
import socket
import subprocess
from pathlib import Path
from typing import List, Optional

import typer

from ...utils.runtime.config import load_config
from ..common import _handle_error, console

logger = logging.getLogger(__name__)

# Default module path when config is unavailable or invalid
DEFAULT_MODULE_PATH = "src.main:app"


def dev(
    port: Optional[int] = typer.Option(8080, "--port", "-p", help="Port for development server (default: 8080)"),
    envs: List[str] = typer.Option(  # noqa: B008
        None, "--env", "-env", help="Environment variables for agent (format: KEY=VALUE)"
    ),
):
    """Start a local development server for your agent with hot reloading."""
    config_path = Path.cwd() / ".bedrock_agentcore.yaml"

    module_path, agent_name = _get_module_path_and_agent_name(config_path)

    # Setup environment and port
    local_env = _setup_dev_environment(envs, port)
    devPort = local_env["PORT"]

    # Pre-flight check: ensure uvicorn is available
    _check_uvicorn_available()

    console.print("[green]🚀 Starting development server with hot reloading[/green]")
    console.print(f"[blue]Agent: {agent_name}[/blue]")
    console.print(f"[blue]Module: {module_path}[/blue]")
    console.print(f"[blue]Server will be available at: http://localhost:{devPort}/invocations[/blue]")
    console.print('[cyan]💡 Test your agent with: agentcore invoke --dev "Hello"[/cyan]')
    console.print("[yellow]Press Ctrl+C to stop the server[/yellow]\n")

    cmd = [
        "uv",
        "run",
        "uvicorn",
        module_path,
        "--reload",
        "--host",
        "0.0.0.0",  # nosec B104 - dev server intentionally binds to all interfaces
        "--port",
        str(devPort),
        "--log-level",
        "info",
    ]

    process = None
    try:
        process = subprocess.Popen(cmd, env=local_env)
        process.wait()
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down development server...[/yellow]")
        _cleanup_process(process)
        console.print("[green]Development server stopped[/green]")
    except Exception as e:
        _cleanup_process(process)
        _handle_error(f"Failed to start development server: {e}")


def _get_module_path_and_agent_name(config_path: Path) -> tuple[str, str]:
    """Get module path and agent name, handling missing YAML gracefully."""
    has_config = config_path.exists()
    has_default_entrypoint = Path("src/main.py").exists()

    # Fail fast if no project found
    if not has_config and not has_default_entrypoint:
        _handle_error(
            "No agent project found in current directory.\n\n"
            "Expected either:\n"
            "  • .bedrock_agentcore.yaml configuration file, or\n"
            "  • src/main.py entrypoint file\n\n"
            "Run 'agentcore dev' from your agent project directory."
        )

    # Try to load config if it exists
    if has_config:
        try:
            project_config = load_config(config_path, autofill_missing_aws=False)
            agent_config = project_config.get_agent_config()
            if agent_config and agent_config.entrypoint:
                module_path = _get_module_path_from_config(config_path, agent_config)
                return module_path, agent_config.name

            console.print(
                "[yellow]⚠️ No agent entrypoint specified in configuration, using default module path: "
                + "{DEFAULT_MODULE_PATH}[/yellow]"
            )
            return DEFAULT_MODULE_PATH, "default"
        except Exception as e:
            if not has_default_entrypoint:
                _handle_error(f"Failed to load configuration and no default entrypoint found: {e}")
            console.print(
                f"[yellow]⚠️ Error loading config: {e}, using default module path: {DEFAULT_MODULE_PATH}[/yellow]"
            )
            return DEFAULT_MODULE_PATH, "default"

    # Fall back to default - must have default entrypoint here
    console.print(f"[yellow]⚠️ No configuration file found, using default module path: {DEFAULT_MODULE_PATH}[/yellow]")
    return DEFAULT_MODULE_PATH, "default"


def _get_module_path_from_config(config_path: Path, agent_config) -> str:
    """Convert config entrypoint to Python module path for uvicorn."""
    entrypoint_path = Path(agent_config.entrypoint.strip())

    if entrypoint_path.is_dir():
        entrypoint_path = entrypoint_path / "main.py"

    project_root = config_path.parent
    try:
        relative_path = entrypoint_path.relative_to(project_root)
        module_path = ".".join(relative_path.with_suffix("").parts)
        return f"{module_path}:app"
    except ValueError:
        return f"{entrypoint_path.stem}:app"


def _setup_dev_environment(envs: List[str], port: Optional[int]) -> dict:
    """Parse environment variables and setup development environment with port handling."""
    env_vars = {}
    if envs:
        for env_var in envs:
            if "=" not in env_var:
                _handle_error(f"Invalid environment variable format: {env_var}. Use KEY=VALUE format.")
            key, value = env_var.split("=", 1)
            env_vars[key] = value

    # Prepare environment
    local_env = dict(os.environ)
    local_env.update(env_vars)
    local_env["LOCAL_DEV"] = "1"

    # Handle port: use CLI arg, env var, or find available one
    if port is None and "PORT" not in local_env:
        port = _find_available_port()
        local_env["PORT"] = str(port)
    elif port is not None:
        local_env["PORT"] = str(port)

    return local_env


def _find_available_port(start_port: int = 8080) -> int:
    """Find an available port starting from the given port."""
    for port in range(start_port, start_port + 100):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(("localhost", port))
                return port
        except OSError:
            continue
    _handle_error("Could not find available port in range 8080-8180")


def _check_uvicorn_available() -> None:
    """Check if uvicorn is available in the environment, exit if not."""
    try:
        result = subprocess.run(
            ["uv", "run", "python", "-c", "import uvicorn"], capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            raise RuntimeError("uvicorn import failed")
    except (subprocess.TimeoutExpired, FileNotFoundError, RuntimeError):
        _handle_error("uvicorn is required for the development server.\nInstall it with: uv add uvicorn")


def _cleanup_process(process):
    """Gracefully terminate process with fallback to kill."""
    if process:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
