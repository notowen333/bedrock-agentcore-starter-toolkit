"""Create CLI Commands."""

import re
from pathlib import Path
from typing import Optional

import typer

from ...cli.common import _handle_error
from ...create.constants import ModelProvider, SDKProvider
from ...create.generate import generate_project
from ...create.types import CreateIACProvider, CreateModelProvider, CreateSDKProvider
from ...utils.runtime.config import load_config
from ...utils.runtime.schema import BedrockAgentCoreAgentSchema, BedrockAgentCoreConfigSchema
from ..cli_ui import _pause_and_new_line_on_finish, ask_choice_with_default, ask_text
from ..runtime.commands import configure_impl
from .prompt_util import (
    get_auto_generated_project_name,
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

non_interactive_flag = typer.Option(
    False, "--non-interactive", help="Run the agentcore create command in non-interactive mode"
)

venv_option = typer.Option(
    True,
    "--venv/--no-venv",
    help="Automatically create a venv and install dependencies",
)

VALID_SDK = list(CreateSDKProvider.__args__)
VALID_MODEL_PROVIDERS = list(CreateModelProvider.__args__)


@create_app.callback(invoke_without_command=True)
def create(
    ctx: typer.Context,
    project_name: Optional[str] = typer.Option(None, "--project-name", "-p", help="Project name to create"),
    iac: Optional[CreateIACProvider] = iac_option,
    sdk: CreateSDKProvider = sdk_option,
    runtime_init: bool = runtime_init_option,
    model_provider: CreateModelProvider = model_provider_option,
    provider_api_key: Optional[str] = model_provider_api_key_option,
    non_interactive_flag: Optional[bool] = non_interactive_flag,
    venv_option: bool = venv_option
):
    """CLI Implementation for Create Command."""
    if ctx.invoked_subcommand:
        return
    # welcome command
    if not non_interactive_flag:
        show_create_welcome()

    if not project_name:
        project_name = ask_text(title="Project Name (alphanumeric):", default=get_auto_generated_project_name())

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

    agent_config: BedrockAgentCoreAgentSchema | None = None
    # topline prompt to determine path
    if runtime_init is None:
        runtime_init = prompt_runtime_or_monorepo() == "Runtime"

    def _runtime_only_flow():
        """Runtime code generation path."""
        nonlocal sdk, model_provider, provider_api_key
        if not sdk:
            sdk = ask_choice_with_default(
                title="Agent SDK:", choices=VALID_SDK, empty_default_choice=SDKProvider.STRANDS
            )
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
            provider_api_key = ask_text(
                title=f"{model_provider} API Key (press Enter to skip, can be set later in .env file):",
                default="",
                redact=True,
            )

    def _monorepo_flow():
        """IAC generation path."""
        nonlocal sdk, iac, agent_config, model_provider
        # consume config from configure command and perform validations
        configure_yaml = Path.cwd() / ".bedrock_agentcore.yaml"

        if configure_yaml.exists():
            configure_schema: BedrockAgentCoreConfigSchema = load_config(configure_yaml)
            if len(configure_schema.agents.keys()) > 1:
                _handle_error(
                    message="agentcore create does not currently support multi agent configurations. "
                    "Try again with a single agent configured. Exiting."
                )
            # now assume we have just one agent configured and build the project context
            agent_config = next(iter(configure_schema.agents.values()))
            # until there are IAC constructs for direct code deployment, fail yaml if not container
            if agent_config.deployment_type != "container":
                _handle_error(
                    message="agentcore create does not currently support direct code deployment. "
                    "Try again with deployment_type: container"
                )

        # Interactively accept IAC/SDK if not provided
        # entrypoint provided != . means src is provided and we don't need sdk
        if not sdk and (not agent_config or agent_config.entrypoint == "."):
            sdk = ask_choice_with_default(
                title="Agent SDK:", choices=VALID_SDK, empty_default_choice=SDKProvider.STRANDS
            )
            model_provider = prompt_model_provider()

        if not iac:
            iac = prompt_iac_provider()

        # prompt for agentcore configure
        configure_yaml = Path.cwd() / ".bedrock_agentcore.yaml"
        if not configure_yaml.exists():
            no_title = "No, use default settings"
            if prompt_configure(no_title) != no_title:
                configure_impl(create=True)
                # pause and show the configure output so it's not jarring
                _pause_and_new_line_on_finish(sleep_override=1.0)
            pass

    if runtime_init:
        _runtime_only_flow()
    else:
        _monorepo_flow()

    # all inputs are set. Generate the project.
    generate_project(
        name=project_name,
        sdk_provider=sdk,
        model_provider=model_provider,
        provider_api_key=provider_api_key,
        iac_provider=iac,
        agent_config=agent_config,
        use_venv=venv_option,
    )
