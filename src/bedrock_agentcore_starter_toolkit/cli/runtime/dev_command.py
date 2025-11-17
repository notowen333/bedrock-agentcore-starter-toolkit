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


# TODO: Must run inside root project dir to work, should either give better error message or search/run from dir which
# contains yaml
# TODO: Test hot reloading, test what happens if yaml is removed, what happens if entrypoint file doesn't exist
def dev(
    agent: Optional[str] = typer.Option(
        None, "--agent", "-a", help="Agent name (use 'agentcore configure list' to see available agents)"
    ),
    envs: List[str] = typer.Option(  # noqa: B008
        None, "--env", "-env", help="Environment variables for agent (format: KEY=VALUE)"
    ),
):
    """Start a local development server for your agent with hot reloading."""
    config_path = Path.cwd() / ".bedrock_agentcore.yaml"

    module_path, agent_name = _get_module_path_and_agent_name(config_path, agent)

    # Setup environment and port
    local_env = _setup_dev_environment(envs)
    port = local_env["PORT"]

    # Pre-flight checks: validate entrypoint module, dependencies, and uvicorn availability
    _validate_entrypoint_module(module_path, local_env)
    _check_uvicorn_available()

    console.print("[green]🚀 Starting development server with hot reloading[/green]")
    console.print(f"[blue]Agent: {agent_name}[/blue]")
    console.print(f"[blue]Module: {module_path}[/blue]")
    console.print(f"[blue]Server will be available at: http://localhost:{port}/invocations[/blue]")
    console.print('[cyan]💡 Test your agent with: agentcore invoke --dev \'{"prompt": "Hello"}\'[/cyan]')
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
        str(port),
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


def _get_module_path_and_agent_name(config_path: Path, agent: Optional[str]) -> tuple[str, str]:
    """Get module path and agent name, handling missing YAML gracefully."""
    if not config_path.exists():
        console.print(
            "[yellow]⚠️ No configuration file found, using default module path: " + "{DEFAULT_MODULE_PATH}[/yellow]"
        )
        return DEFAULT_MODULE_PATH, "default"

    try:
        project_config = load_config(config_path)
        agent_config = project_config.get_agent_config(agent)
        module_path = _get_module_path_from_config(config_path, agent_config)
        return module_path, agent_config.name
    except Exception as e:
        console.print(
            f"[yellow]⚠️ Error loading config: {e}, using default module path: " + "{DEFAULT_MODULE_PATH}[/yellow]"
        )
        return DEFAULT_MODULE_PATH, "default"


def _get_module_path_from_config(config_path: Path, agent_config) -> str:
    """Get module path from config, with fallback to src.main:app."""
    try:
        if not agent_config or not agent_config.entrypoint or not agent_config.entrypoint.strip():
            console.print(
                "[yellow]⚠️ No entrypoint specified in configuration, using default module path: "
                + "{DEFAULT_MODULE_PATH}[/yellow]"
            )
            return DEFAULT_MODULE_PATH

        entrypoint_path = Path(agent_config.entrypoint.strip())

        # If entrypoint is a directory, look for main.py inside it
        if entrypoint_path.is_dir():
            entrypoint_path = entrypoint_path / "main.py"

        # Convert absolute path to module path
        project_root = config_path.parent
        return _convert_entrypoint_to_module_path(entrypoint_path, project_root)

    except Exception as e:
        console.print(
            f"[yellow]⚠️ Error reading configuration: {e}, using default module path: {DEFAULT_MODULE_PATH}[/yellow]"
        )
        return DEFAULT_MODULE_PATH


def _convert_entrypoint_to_module_path(entrypoint_path: Path, project_root: Path) -> str:
    """Convert absolute entrypoint path to Python module path for uvicorn.

    Args:
        entrypoint_path: Absolute path to the entrypoint file
        project_root: Project root directory (usually cwd)

    Returns:
        Module path like 'my_agent.main:app' or 'src.main:app'
    """
    try:
        # Make entrypoint relative to project root
        relative_path = entrypoint_path.relative_to(project_root)

        # Convert path to module notation (remove .py, replace / with .)
        module_parts = relative_path.with_suffix("").parts
        module_path = ".".join(module_parts)

        return f"{module_path}:app"
    except ValueError:
        # If entrypoint is outside project root, fall back to filename only
        return f"{entrypoint_path.stem}:app"


def _setup_dev_environment(envs: List[str]) -> dict:
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

    # Add src directory to Python path if it exists (for local imports)
    src_dir = Path("src")
    if src_dir.exists():
        current_pythonpath = local_env.get("PYTHONPATH", "")
        src_path = str(src_dir.absolute())
        if current_pythonpath:
            local_env["PYTHONPATH"] = f"{src_path}:{current_pythonpath}"
        else:
            local_env["PYTHONPATH"] = src_path

    # Handle port: use user-specified PORT or find available one
    if "PORT" not in local_env:
        port = _find_available_port()
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


def _validate_entrypoint_module(module_path: str, env: dict) -> None:
    """Check if the entrypoint module exists and can be imported before starting uvicorn."""
    entrypoint_module = module_path.split(":")[0]  # Extract 'src.main' from 'src.main:app'

    _check_entrypoint_file_exists(entrypoint_module)
    _check_entrypoint_dependencies(entrypoint_module, env)
    console.print(f"[green]✓ Entrypoint module '{entrypoint_module}' validated successfully[/green]")


def _check_entrypoint_file_exists(entrypoint_module: str) -> None:
    """Check if the entrypoint module file exists."""
    file_path = entrypoint_module.replace(".", "/") + ".py"
    if not Path(file_path).exists():
        _handle_error(
            f"Entrypoint file not found: {file_path}\nCreate this file with an 'app' variable containing your agent."
        )


def _check_entrypoint_dependencies(entrypoint_module: str, env: dict) -> None:
    """Check if the entrypoint module dependencies are satisfied by attempting import.

    This catches all dependency issues that would prevent uvicorn from starting:
    - Missing packages, version conflicts, syntax errors, missing env vars, etc.
    """
    try:
        result = subprocess.run(
            ["uv", "run", "python", "-c", f"import {entrypoint_module}"],
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )
        if result.returncode != 0:
            error_lines = result.stderr.strip().split("\n")
            actual_error = error_lines[-1] if error_lines else "Unknown import error"

            # Check if there's a pyproject.toml in src/ directory
            src_pyproject = Path("src/pyproject.toml")
            install_cmd = "uv pip install -e src/" if src_pyproject.exists() else "uv pip install -e ."

            _handle_error(
                f"Dependency error: {actual_error}\n"
                f"Run '{install_cmd}' to install project dependencies from pyproject.toml"
            )
    except subprocess.TimeoutExpired:
        _handle_error(f"Timeout while validating entrypoint module '{entrypoint_module}'")


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
