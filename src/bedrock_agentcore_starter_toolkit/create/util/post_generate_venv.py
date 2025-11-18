"""Utility to create a venv and install dependencies after generate."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from ..types import ProjectContext


def create_and_init_venv(ctx: ProjectContext) -> None:
    """Create a venv and install dependencies if uv is present."""
    project_root = ctx.output_dir
    pyproject_path = project_root / "pyproject.toml"

    if not pyproject_path.exists():
        return

    if not _has_uv():
        return

    _run(["uv", "venv", ".venv"], cwd=project_root)
    _run(["uv", "pip", "install", "."], cwd=project_root)
    _run(["uv", "lock"], cwd=project_root)


# ---------------------------------------------------------------------------
# Helpers live *after* the main function
# ---------------------------------------------------------------------------


def _has_uv() -> bool:
    return shutil.which("uv") is not None


def _run(cmd: list[str], cwd: Path) -> None:
    subprocess.run(cmd, cwd=str(cwd), check=True)
