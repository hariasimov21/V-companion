from app.ai.base import AIProvider
from app.ai.providers.mock import MockAIProvider
from app.ai.providers.ollama_provider import OllamaProvider, parse_think_setting
from app.ai.providers.openai_provider import OpenAIProvider
from app.config.settings import AIProviderName, Settings
from app.core.errors import ConfigError


def create_ai_provider(settings: Settings) -> AIProvider:
    match settings.ai_provider:
        case AIProviderName.MOCK:
            return MockAIProvider()
        case AIProviderName.OPENAI:
            key = settings.openai_api_key
            if key is None or not key.get_secret_value():
                raise ConfigError("AI_PROVIDER=openai requires OPENAI_API_KEY in .env")
            return OpenAIProvider(api_key=key, model=settings.openai_model)
        case AIProviderName.OLLAMA:
            return _create_ollama_provider(settings)


def _create_ollama_provider(settings: Settings) -> OllamaProvider:
    if not settings.ollama_model:
        raise ConfigError("AI_PROVIDER=ollama requires OLLAMA_MODEL in .env")
    try:
        think = parse_think_setting(settings.ollama_think)
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc
    return OllamaProvider(
        base_url=settings.ollama_url,
        model=settings.ollama_model,
        timeout_seconds=settings.ai_timeout_seconds,
        think=think,
        keep_alive=settings.ollama_keep_alive,
        num_ctx=settings.ollama_num_ctx,
    )
