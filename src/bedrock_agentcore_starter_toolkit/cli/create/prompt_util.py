"""Utility functions for interactive CLI prompts with validation and confirmation."""

from prompt_toolkit import prompt
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.formatted_text import HTML

from ...cli.common import console
from .pretty_selector import select_one


def prompt_runtime_or_monorepo():
    """Prompt user to choose between Runtime or Monorepo project type."""
    choice = select_one(
        title="Select a create project configuration:",
        options={
            "Runtime": "Agent SDK python runtime code deployed with `agentcore launch`",
            "Monorepo": ("Monorepo with runtime code and infrastructure as code (IaC) modeling AgentCore resources"),
        },
    )
    return choice


def prompt_iac_provider():
    """Prompt user to choose CDK or Terraform as the IaC provider."""
    choice = select_one(
        title="Select the IaC provider for your generated monorepo project",
        options={
            "CDK": (
                "Creates a TypeScript Node project to deploy and manage your AgentCore resources in AWS CloudFormation"
            ),
            "Terraform": ("Creates a Terraform project to deploy and manage your AgentCore resources with Terraform"),
        },
    )
    return choice


def prompt_choice_until_valid_input(label: str, choices: list[str]) -> str:
    """Prompt with autocomplete until user enters a valid choice."""
    completer = WordCompleter(choices, ignore_case=True)
    while True:
        answer = prompt(
            f"{label} ({'/'.join(choices)}): ",
            completer=completer,
            complete_while_typing=True,
        ).strip()

        for choice in choices:
            if answer.lower() == choice.lower():
                return choice

        print(f"Invalid choice. Please enter one of: {', '.join(choices)}")


def prompt_bool_until_valid_input(label: str) -> bool:
    """Prompt repeatedly for a boolean value, accepting common synonyms."""
    true_vals = ["true", "t", "yes", "y", "1"]
    false_vals = ["false", "f", "no", "n", "0"]

    completer = WordCompleter(true_vals + false_vals, ignore_case=True)

    while True:
        entered = prompt(f"{label} (y/n): ", completer=completer).strip().lower()
        if entered in true_vals:
            return True
        if entered in false_vals:
            return False
        console.print("[yellow]Please enter yes or no[/yellow]")


def prompt_confirm_continue(warn_str: str) -> bool:
    """Display a warning and ask user for confirmation to proceed."""
    response = prompt(HTML(f"<ansiyellow><b>⚠ {warn_str}: Do you want to continue [y/N]: </b></ansiyellow>")).strip()
    return response.lower() in {"y", "yes"}
