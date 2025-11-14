"""Utility functions for interactive CLI prompts with validation and confirmation."""

from prompt_toolkit import prompt
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.formatted_text import HTML

from ...cli.common import console
from ...create.constants import IACProvider, ModelProvider
from ..cli_ui import select_one, show_welcome, ask_text


def show_create_welcome():
    """Give a welcome message when create is run."""
    show_welcome(
        "Welcome to agentcore create!",
        [
            "Choose your Agent SDK and desired configuration to create an Amazon Bedrock AgentCore ⚙️\n",
            "project that best meets your requirements.\n",
            "",
            "👉 Press any key to continue...",
        ],
    )


def ask_text_required(title: str, redact: bool = False) -> str:
    """Prompt user for required text input, looping until non-empty value is provided."""
    while True:
        result = ask_text(title, default=None, redact=redact)
        if result and result.strip():
            return result.strip()
        # Empty input, loop and ask again


def prompt_runtime_or_monorepo():
    """Prompt user to choose between Runtime or Monorepo project type."""
    choice = select_one(
        title="Select a create project configuration:",
        options={
            "Runtime": "Lightweight. Agent SDK python runtime code deployed with `agentcore launch`",
            "Monorepo": (
                "Full featured. Monorepo with runtime code and infrastructure as code (IaC) modeling "
                "AgentCore resources"
            ),
        },
    )
    return choice

def prompt_model_providers(is_runtime_only: bool):
    """Prompt user to choose a model provider based on deployment context.

    Args:
        is_runtime_only: True for runtime-only deployments, False for monorepo (IaC)

    Returns:
        Selected model provider name
    """
    from ...create.constants import ModelProvider

    available_providers = ModelProvider.get_providers_for_context(is_runtime_only)

    choice = select_one(
        title="Select a model provider:",
        options=available_providers
    )
    return choice

def prompt_iac_provider() -> IACProvider:
    """Prompt user to choose CDK or Terraform as the IaC provider."""
    choice = select_one(
        title="Select the IaC provider for your generated monorepo project",
        options={
            IACProvider.CDK: (
                "Creates a TypeScript Node project to deploy and manage your AgentCore resources in AWS CloudFormation"
            ),
            IACProvider.TERRAFORM: (
                "Creates a Terraform project to deploy and manage your AgentCore resources with Terraform"
            ),
        },
    )
    return choice


def prompt_model_provider() -> ModelProvider:
    """Prompt user to choose an LLM model provider."""
    choice = select_one(
        title="Model provider selection:",
        options={
            ModelProvider.Bedrock: ("Use Amazon Bedrock to provide LLM inference authenticated with AWS"),
            ModelProvider.OpenAI: (
                "Use an OpenAI API key to provide LLM inference. Store the credential in AgentCore Identity."
            ),
        },
    )
    return choice


def prompt_configure(no_title: str):
    """Prompt user to decide if they want to run agentcore configure."""
    choice = select_one(
        title="Use existing resource configuration?",
        options={
            no_title: ("Start fresh and deploy new resources for your project."),
            "Yes, define existing resources and configuration settings": (
                "I have existing resources (JWT authorizers, IAM roles, VPC, or AgentCore Memory) "
                "that I want to import."
            ),
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
