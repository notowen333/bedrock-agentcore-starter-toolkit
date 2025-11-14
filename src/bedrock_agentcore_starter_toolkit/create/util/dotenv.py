from pathlib import Path
from ...create.constants import ModelProvider

def _write_env_file_directly(output_dir: Path, model_provider: str, api_key: str | None) -> None:
    """Write .env file with API key for non-Bedrock providers.

    This function handles sensitive data (API keys) outside of the template system
    to prevent accidental exposure through ProjectContext or logging.

    Args:
        output_dir: Directory where .env file should be created
        model_provider: Name of the model provider (e.g., "OpenAI", "Bedrock")
        api_key: API key to write to .env file (None for Bedrock or if not provided)
    """
    # Only write .env for non-Bedrock providers with an API key
    if not api_key or model_provider == ModelProvider.Bedrock:
        return

    env_path = output_dir / ".env"
    env_content = f"{model_provider.upper()}_API_KEY={api_key}\n"
    env_path.write_text(env_content)