"""ProgressSink impl to surface progress to user."""

import time
from contextlib import contextmanager

from ...cli.common import console


class ProgressSink:
    """Proivde step function which shows loading in console."""

    MIN_PHASE_SECONDS = 1.0

    # Color theme
    SPINNER_STYLE = "cyan"
    MESSAGE_STYLE = "cyan"
    DONE_STYLE = "bright_blue"

    @contextmanager
    def step(self, message: str, done_message: str | None = None):
        """ex: with sink.step("Creating venv", "Created venv")."""
        start = time.time()

        # Start Rich spinner — correct API
        with console.status(
            f"[{self.MESSAGE_STYLE}]{message}...[/]",
            spinner="dots",
            spinner_style=self.SPINNER_STYLE,
        ):
            try:
                yield
            finally:
                # enforce minimum duration
                elapsed = time.time() - start
                if elapsed < self.MIN_PHASE_SECONDS:
                    time.sleep(self.MIN_PHASE_SECONDS - elapsed)

        # Success line
        if done_message:
            console.print(f"[{self.DONE_STYLE}]✓ {done_message}.[/]")
        else:
            console.print(f"[{self.DONE_STYLE}]✓ done[/]")
