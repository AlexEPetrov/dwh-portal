from domains.ai.llm.client import _build_bearer_headers
from domains.ai.providers.factory import build_provider
from domains.ai.providers.ollama_provider import OllamaProvider
from domains.ai.providers.openai_compatible_provider import OpenAiCompatibleProvider
from settings.ai import AiSettings


def test_ai_settings_read_api_key_from_app_ai_env(monkeypatch) -> None:
    monkeypatch.setenv("APP_AI_API_KEY", "secret-token")

    settings = AiSettings()

    assert settings.api_key == "secret-token"


def test_build_provider_passes_api_key_to_ollama_provider() -> None:
    settings = AiSettings(provider="ollama", api_key="secret-token")

    provider = build_provider(settings)

    assert isinstance(provider, OllamaProvider)
    assert provider._headers() == {"Authorization": "Bearer secret-token"}


def test_build_provider_passes_api_key_to_openai_compatible_provider() -> None:
    settings = AiSettings(provider="openai_compatible", api_key="secret-token")

    provider = build_provider(settings)

    assert isinstance(provider, OpenAiCompatibleProvider)
    assert provider._headers() == {"Authorization": "Bearer secret-token"}


def test_openai_compatible_llm_headers_fall_back_to_default_token() -> None:
    assert _build_bearer_headers(None, default_api_key="ollama") == {
        "Authorization": "Bearer ollama"
    }


def test_openai_compatible_llm_headers_prefer_configured_api_key() -> None:
    assert _build_bearer_headers("secret-token", default_api_key="ollama") == {
        "Authorization": "Bearer secret-token"
    }
