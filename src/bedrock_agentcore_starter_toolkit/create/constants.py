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
    """Supported Model Providers with context-aware availability."""

    OpenAI = "OpenAI"
    Bedrock = "Bedrock"
    Anthropic = "Anthropic"
    Gemini = "Gemini"

    # Explicit ordering for UI / selection
    ORDER = [
        Bedrock,
        OpenAI,
        Anthropic,
        Gemini,
    ]

    DESCRIPTIONS = {
        "Bedrock": "Use Amazon Bedrock to provide LLM inference authenticated with AWS",
        "OpenAI": "Use an OpenAI API key to provide LLM inference. Store the credential in AgentCore Identity.",
        "Anthropic": "Foundational models from Anthropic. Store the credential in AgentCore Identity.",
        "Gemini": "Foundational models from Google. Store the credential in AgentCore Identity.",
    }

    MONOREPO_SUPPORTED = {"Bedrock"}
    RUNTIME_ONLY_SUPPORTED = {"Bedrock", "OpenAI", "Anthropic", "Gemini"}
    REQUIRES_API_KEY = {"OpenAI", "Anthropic", "Gemini"}

    SDK_COMPATIBILITY = {
        SDKProvider.OPENAI_AGENTS: {"OpenAI"},
        SDKProvider.GOOGLE_ADK: {"Gemini"},
        SDKProvider.CREWAI: {"Bedrock", "OpenAI", "Anthropic", "Gemini"},
        SDKProvider.AUTOGEN: {"Bedrock", "OpenAI", "Anthropic", "Gemini"},
        SDKProvider.STRANDS: {"Bedrock", "OpenAI", "Anthropic", "Gemini"},
        SDKProvider.LANG_GRAPH: {"Bedrock", "OpenAI", "Anthropic", "Gemini"},
    }

    @classmethod
    def get_providers_for_context(cls, is_runtime_only: bool, sdk_provider: str | None = None) -> dict[str, str]:
        """Resolve the context to a model provider selection."""
        available = cls.RUNTIME_ONLY_SUPPORTED if is_runtime_only else cls.MONOREPO_SUPPORTED

        if is_runtime_only and sdk_provider:
            runtime_map = cls.SDK_COMPATIBILITY.get("runtime_only", {})
            sdk_support = runtime_map.get(sdk_provider)
            if sdk_support:
                available = available & sdk_support

        # Sort according to ORDER, but only keep those in `available`
        ordered = [p for p in cls.ORDER if p in available]

        return {p: cls.DESCRIPTIONS[p] for p in ordered}
