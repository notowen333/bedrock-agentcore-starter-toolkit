"""Classes used to reference str constants throughout the code.

Define class members in all caps so pylance treats them as literals
This structure is chosen because StrEnum is available in 3.11+ and we need to support 3.10
"""


class TemplateDirSelection:
    """Used to keep track of which directories within templates/ to render."""

    MONOREPO = "monorepo"
    COMMON = "common"
    MONOREPO_MCP_RUNTIME = "monorepo_mcp_runtime"
    RUNTIME_ONLY = "runtime_only"


class DeploymentType:
    """Deploy with docker or s3 zip."""

    CONTAINER = "container"
    DIRECT_CODE_DEPLOY = "direct_code_deploy"


class RuntimeProtocol:
    """The protocols that runtime supports.

    https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-service-contract.html#protocol-comparison
    """

    HTTP = "HTTP"
    MCP = "MCP"
    A2A = "A2A"


class IACProvider:
    """Supported IaC Frameworks for agentcore create."""

    CDK = "CDK"
    TERRAFORM = "Terraform"


class SDKProvider:
    """Supported Agent SDKs for agentcore create."""

    STRANDS = "Strands"
    LANG_GRAPH = "LangGraph"
    GOOGLE_ADK = "GoogleADK"
    OPENAI_AGENTS = "OpenAIAgents"
    AUTOGEN = "AutoGen"
    CREWAI = "CrewAI"

class ModelProvider:
    """Supported Model Providers. """
    OpenAI = "OpenAI"
    Bedrock = "Bedrock"