"""Project generation orchestration for Bedrock Agent Core starter projects."""

from pathlib import Path

from ..cli.common import _handle_error
from ..cli.create.prompt_util import prompt_confirm_continue
from ..utils.runtime.container import ContainerRuntime
from ..utils.runtime.schema import BedrockAgentCoreAgentSchema
from .baseline_feature import BaselineFeature
from .configure.resolve import (
    copy_src_implementation_and_docker_config_into_monorepo,
    resolve_agent_config_with_project_context,
)
from .constants import RuntimeProtocol, TemplateDirSelection
from .features import iac_feature_registry, sdk_feature_registry
from .types import CreateIACProvider, CreateSDKProvider, ProjectContext, CreateModelProvider
from .util.console_print import emit_create_completed_message
from .util.create_agentcore_yaml import write_minimal_create_runtime_yaml, write_minimal_create_with_iac_project_yaml


def _apply_baseline_and_sdk_features(ctx: ProjectContext) -> None:
    """Apply baseline and SDK features, collecting dependencies from both.

    This common method handles:
    1. Creating baseline feature for the template directory
    2. Collecting python dependencies from baseline and SDK features
    3. Applying baseline feature (renders pyproject.toml, etc.)
    4. Applying SDK feature (renders SDK-specific templates)
    """
    baseline_feature = BaselineFeature(ctx.template_dir_selection)

    # Collect python dependencies from baseline and SDK
    deps = set(baseline_feature.python_dependencies)
    sdk_feature = None
    if ctx.sdk_provider:
        # Get SDK feature instance to access its dependencies
        sdk_feature = sdk_feature_registry[ctx.sdk_provider]()
        # Call before_apply to ensure dependencies are set correctly based on model provider
        sdk_feature.before_apply(ctx)
        deps.update(sdk_feature.python_dependencies)

    ctx.python_dependencies = sorted(deps)

    # Apply baseline feature (renders common templates like pyproject.toml)
    baseline_feature.apply(ctx)

    # Apply SDK feature (renders SDK-specific templates)
    if sdk_feature:
        sdk_feature.apply(ctx)


def generate_project(
    name: str,
    sdk_provider: CreateSDKProvider,
    iac_provider: CreateIACProvider | None,
    model_provider: CreateModelProvider | None,
    agent_config: BedrockAgentCoreAgentSchema | None,
):
    """Generate a new Bedrock Agent Core project with specified SDK and IaC providers."""
    # create directory structure
    output_path = Path.cwd() / name
    output_path.mkdir(exist_ok=False)
    src_path = Path(output_path / "src")
    src_path.mkdir(exist_ok=False)

    template_dir = TemplateDirSelection.MONOREPO if iac_provider else TemplateDirSelection.RUNTIME_ONLY

    # the ProjectContext defines what is generated. It is passed into the jinja templates that are rendered.
    ctx = ProjectContext(
        # high level project config
        name=name,
        output_dir=output_path,
        src_dir=src_path,
        entrypoint_path=Path(src_path / "main.py"),
        iac_dir=None,  # updated when iac is generated
        sdk_provider=sdk_provider,
        iac_provider=iac_provider,
        model_provider=model_provider,
        deployment_type="container",
        template_dir_selection=template_dir,
        runtime_protocol=RuntimeProtocol.HTTP,
        python_dependencies=[],
        src_implementation_provided=False,
        agent_name=name + "_Agent",
        # memory
        memory_enabled=True,
        memory_name=name + "_Memory",
        memory_event_expiry_days=30,
        memory_is_long_term=False,
        # custom authorizer
        custom_authorizer_enabled=False,
        custom_authorizer_url=None,
        custom_authorizer_allowed_audience=None,
        custom_authorizer_allowed_clients=None,
        # vpc
        vpc_enabled=False,
        vpc_security_groups=None,
        vpc_subnets=None,
        # request header
        request_header_allowlist=None,
        # observability
        observability_enabled=True,
    )

    if not ctx.iac_provider:
        # Runtime-only path: apply baseline and SDK features
        _apply_baseline_and_sdk_features(ctx)
        write_minimal_create_runtime_yaml(ctx)
        return

    # resolve above defaults with the configure context if present
    if agent_config:
        resolve_agent_config_with_project_context(ctx, agent_config)

    # ctx is resolved, ready to start generating
    # console.print("[cyan] Create generating with the following configuration: [/cyan]")
    # console.print(Pretty(ctx))

    if ctx.src_implementation_provided:
        # copy over runtime code and just apply the IAC feature
        if prompt_confirm_continue(
            f"Copying source files and directories in cwd into {str(ctx.src_dir)} directory, "
            f"ignoring reserved namespaces"
        ):
            copy_src_implementation_and_docker_config_into_monorepo(agent_config, ctx)
        else:
            _handle_error(message="User stopped create generation.")
        iac_feature_registry[iac_provider]().apply(ctx)
    else:
        # Monorepo path: apply baseline, SDK, and IAC features
        _apply_baseline_and_sdk_features(ctx)
        iac_feature_registry[iac_provider]().apply(ctx)
        # create dockerfile
        ContainerRuntime().generate_dockerfile(
            agent_path=ctx.entrypoint_path,
            output_dir=ctx.src_dir,
            explicit_requirements_file=ctx.src_dir / "pyproject.toml",
            agent_name=ctx.agent_name,
            enable_observability=ctx.observability_enabled,
        )
    # write a minimal create YAML so commands like agentocore invoke can work later
    if ctx.iac_provider:
        write_minimal_create_with_iac_project_yaml(ctx)
        emit_create_completed_message(ctx)
    else:
        # write nearly empty configure YAML
        pass
