"""Utilities for writing create project YAML configuration files."""

from pathlib import Path

import yaml

from ...utils.runtime.config import save_config
from ...utils.runtime.schema import BedrockAgentCoreAgentSchema, BedrockAgentCoreConfigSchema
from ..constants import DeploymentType
from ..types import ProjectContext

CONFIG_YAML_NAME = ".bedrock_agentcore.yaml"


def write_minimal_create_with_iac_project_yaml(ctx: ProjectContext) -> Path:
    """Create and write a minimal create project YAML configuration file from the project context."""
    file_path = ctx.output_dir / CONFIG_YAML_NAME
    agent_name = ctx.agent_name

    data = {
        "default_agent": agent_name,
        "is_agentcore_create_with_iac": True,
        "agents": {
            agent_name: {
                "name": agent_name,
                "entrypoint": str(ctx.src_dir),
                "deployment_type": ctx.deployment_type,
                "aws": {"region": None},
                "bedrock_agentcore": {
                    "agent_id": None,
                    "agent_arn": None,
                    "agent_session_id": None,
                },
            }
        },
    }

    with file_path.open("w") as f:
        yaml.safe_dump(data, f, sort_keys=False)

    return file_path


def write_minimal_create_runtime_yaml(ctx: ProjectContext) -> Path:
    """Create the most simple .bedrock_agentcore.yaml for runtime projects."""
    agent_schema = BedrockAgentCoreAgentSchema(
        name=ctx.agent_name,
        entrypoint=str(ctx.entrypoint_path),
        deployment_type=DeploymentType.DIRECT_CODE_DEPLOY,
        runtime_type="PYTHON_3_10",  # todo need to decide default here
        source_path=str(ctx.src_dir),
    )
    schema = BedrockAgentCoreConfigSchema(default_agent=ctx.agent_name, agents={ctx.agent_name: agent_schema})
    save_config(schema, ctx.output_dir / CONFIG_YAML_NAME)
