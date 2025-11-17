"""Create CLI Commands."""

import re
from pathlib import Path
from typing import Optional

import typer

from ...cli.common import _handle_error
from ...create.constants import ModelProvider
from ...create.generate import generate_project
from ...create.types import CreateIACProvider, CreateModelProvider, CreateSDKProvider
from ...utils.runtime.config import load_config
from ...utils.runtime.schema import BedrockAgentCoreAgentSchema, BedrockAgentCoreConfigSchema
from ..cli_ui import ask_choice, ask_text
from ..runtime.commands import configure_impl
from .prompt_util import (
    ask_text_required,
    prompt_configure,
    prompt_iac_provider,
    prompt_model_provider,
    prompt_runtime_or_monorepo,
    show_create_welcome,
)

create_app = typer.Typer(
    name="create", help="create an agent core project", invoke_without_command=True, no_args_is_help=False
)
# create arn friendly names on the shorter side (used for prefix in infra ids) no - or _ for now to deal
# with inconsistent agentcore validations
VALID_PROJECT_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9]{0,35}$")

iac_option = typer.Option(
    None,
    "--iac",
    help="Infrastructure as code provider (CDK or Terraform)",
)

sdk_option = typer.Option(
    None,
    "--sdk",
    help="SDK provider (Strands, ClaudeAgents, OpenAI, etc.)",
)

runtime_init_option = typer.Option(
    None, "--init", help="Use create to initialize the runtime agent SDK code for a project"
)

model_provider_option = typer.Option(
    None, "--model-provider", "-mp", help="Model provider to use with the Agent SDK (Bedrock, OpenAI etc.)"
)

model_provider_api_key_option = typer.Option(
    None, "--provider-api-key", "-key", help="API key for the model provider (required for non-Bedrock providers)"
)

VALID_SDK = list(CreateSDKProvider.__args__)
VALID_MODEL_PROVIDERS = list(CreateModelProvider.__args__)


@create_app.callback(invoke_without_command=True)
def create(
    ctx: typer.Context,
    project_name: Optional[str] = typer.Option(None, "--project-name", "-p", help="Project name to create"),
    iac: CreateIACProvider = iac_option,
    sdk: CreateSDKProvider = sdk_option,
    runtime_init: bool = runtime_init_option,
    model_provider: CreateModelProvider = model_provider_option,
    provider_api_key: Optional[str] = model_provider_api_key_option,
):
    """CLI Implementation for Create Command."""
    if ctx.invoked_subcommand:
        return
    # welcome command
    show_create_welcome()

    if not project_name:
        project_name = ask_text(title="Project Name (alphanumeric):")

    # Input Validation
    if not VALID_PROJECT_NAME_PATTERN.fullmatch(project_name):
        raise typer.BadParameter(
            "To ensure friendly ARN creation, project must only contain alphanumeric charcters (no '-' or '_') up to "
            "36 chars in total length"
        )
    if Path(project_name).exists():
        raise typer.BadParameter(
            f"A directory already exists with name {project_name}! Either delete that directory or choose a new "
            f"project name."
        )

    if runtime_init is None:
        runtime_init = prompt_runtime_or_monorepo() == "Runtime"

    if runtime_init:
        _runtime_only_generate(project_name, sdk, model_provider, provider_api_key)
    else:
        _monorepo_generate(project_name, sdk, iac, model_provider)


def _runtime_only_generate(
    project_name: str,
    sdk: Optional[CreateSDKProvider],
    model_provider: Optional[CreateModelProvider],
    provider_api_key: Optional[str],
):
    """Runtime code generation path."""
    if not sdk:
        sdk = ask_choice(title="Agent SDK:", choices=VALID_SDK)
    providers_map = ModelProvider.get_providers_for_context(is_runtime_only=True, sdk_provider=sdk)
    supported_providers = list(providers_map.keys())
    if not supported_providers:
        raise typer.BadParameter(f"SDK '{sdk}' is not compatible with any runtime model providers.")
    if not model_provider:
        model_provider = prompt_model_provider(sdk_provider=sdk)
    if model_provider not in supported_providers:
        raise typer.BadParameter(
            f"Model provider '{model_provider}' is not supported for SDK '{sdk}'. "
            f"Supported providers: {', '.join(supported_providers)}"
        )
    if model_provider in ModelProvider.REQUIRES_API_KEY and not provider_api_key:
        provider_api_key = ask_text_required(f"{model_provider} API Key: ", redact=True)

    generate_project(
        name=project_name,
        sdk_provider=sdk,
        model_provider=model_provider,
        provider_api_key=provider_api_key,
        iac_provider=None,
        agent_config=None,
    )


def _monorepo_generate(
    project_name: str, sdk: Optional[CreateSDKProvider], iac: Optional[CreateIACProvider], model_provider: Optional[str]
):
    """IAC generation path."""
    # consume config from configure command and perform validations
    configure_yaml = Path.cwd() / ".bedrock_agentcore.yaml"
    agent_config: BedrockAgentCoreAgentSchema | None = None

    if configure_yaml.exists():
        configure_schema: BedrockAgentCoreConfigSchema = load_config(configure_yaml)
        if len(configure_schema.agents.keys()) > 1:
            _handle_error(
                message="agentcore create does not currently support multi agent configurations. "
                "Try again with a single agent configured. Exiting."
            )
        # now assume we have just one agent configured and build the project context
        agent_config = next(iter(configure_schema.agents.values()))
        # until there are IAC constructs for direct code deployment, fail configs that aren't configured for container
        if agent_config.deployment_type != "container":
            _handle_error(
                message="agentcore create does not currently support direct code deployment. "
                "Try again with deployment_type: container"
            )

    # Interactively accept IAC/SDK if not provided
    # entrypoint provided != . means src is provided and we don't need sdk
    if not sdk and (not agent_config or agent_config.entrypoint == "."):
        sdk = ask_choice(title="Agent SDK:", choices=VALID_SDK)
        model_provider = prompt_model_provider()

    if not iac:
        iac = prompt_iac_provider()

    # prompt for agentcore configure
    configure_yaml = Path.cwd() / ".bedrock_agentcore.yaml"
    if not configure_yaml.exists():
        no_title = "No, use default settings"
        if prompt_configure(no_title) != no_title:
            configure_impl(create=True)
        pass

    generate_project(
        name=project_name,
        sdk_provider=sdk,
        iac_provider=iac,
        model_provider=model_provider,
        provider_api_key=None,  # Not supported for IAC until Identity has constructs
        agent_config=agent_config,
    )
