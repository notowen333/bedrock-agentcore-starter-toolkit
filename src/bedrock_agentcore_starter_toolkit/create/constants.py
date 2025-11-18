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

    # Metadata for each provider
    DESCRIPTIONS = {
        "Bedrock": "Use Amazon Bedrock to provide LLM inference authenticated with AWS",
        "OpenAI": "Use an OpenAI API key to provide LLM inference. Store the credential in AgentCore Identity.",
        "Anthropic": "Foundational models from Anthropic. Store the credential in AgentCore Identity.",
        "Gemini": "Foundational models from Google. Store the credential in AgentCore Identity.",
    }

    # Which providers support which deployment types
    MONOREPO_SUPPORTED = {"Bedrock"}  # Only Bedrock for IaC deployments
    RUNTIME_ONLY_SUPPORTED = {"Bedrock", "OpenAI", "Anthropic", "Gemini"}  # All providers for runtime
    REQUIRES_API_KEY = {"OpenAI", "Anthropic", "Gemini"}

    # Compatibility configuration placeholder: map SDKs to supported providers per mode
    SDK_COMPATIBILITY = {
        "runtime_only": {
            SDKProvider.OPENAI_AGENTS: {"OpenAI"},
            SDKProvider.GOOGLE_ADK: {"Gemini"},
            SDKProvider.CREWAI: {"Bedrock","OpenAI", "Anthropic", "Gemini"},
            SDKProvider.AUTOGEN: {"Bedrock","OpenAI", "Anthropic", "Gemini"},
            SDKProvider.STRANDS: {"Bedrock", "OpenAI", "Anthropic", "Gemini"},
            SDKProvider.LANG_GRAPH: {"Bedrock","OpenAI", "Anthropic", "Gemini"},
        }
    }

    @classmethod
    def get_providers_for_context(cls, is_runtime_only: bool, sdk_provider: str | None = None) -> dict[str, str]:
        """Get available providers with descriptions for given context.

        Args:
            is_runtime_only: True for runtime-only deployments, False for monorepo (IaC)
            sdk_provider: Optional SDK identifier used to filter runtime-only providers

        Returns:
            Dictionary mapping provider names to their descriptions
        """
        available = cls.RUNTIME_ONLY_SUPPORTED if is_runtime_only else cls.MONOREPO_SUPPORTED
        if is_runtime_only and sdk_provider:
            runtime_map = cls.SDK_COMPATIBILITY.get("runtime_only", {})
            sdk_support = runtime_map.get(sdk_provider)
            if sdk_support:
                available = available & sdk_support
        return {provider: cls.DESCRIPTIONS[provider] for provider in available}
