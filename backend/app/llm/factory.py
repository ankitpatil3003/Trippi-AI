from __future__ import annotations

from typing import Any, Literal

from langchain_core.language_models.chat_models import BaseChatModel

from app.config import Settings, get_settings

ProviderName = Literal["heuristic", "openai", "anthropic", "openrouter"]


def resolve_provider(settings: Settings | None = None) -> ProviderName:
    s = settings or get_settings()
    name = (s.llm_provider or "heuristic").strip().lower()
    if name in {"heuristic", "openai", "anthropic", "openrouter"}:
        return name  # type: ignore[return-value]
    raise ValueError(
        f"Unsupported LLM_PROVIDER={s.llm_provider!r}. "
        "Use heuristic, openai, anthropic, or openrouter."
    )


def provider_ready(settings: Settings | None = None) -> bool:
    """True when the configured provider has the credentials it needs."""
    s = settings or get_settings()
    provider = resolve_provider(s)
    if provider == "heuristic":
        return False
    if provider == "openai":
        return bool(s.openai_api_key)
    if provider == "anthropic":
        return bool(s.anthropic_api_key)
    if provider == "openrouter":
        return bool(s.openrouter_api_key)
    return False


def get_chat_model(settings: Settings | None = None, temperature: float = 0) -> BaseChatModel:
    """
    Build a LangChain chat model for the active provider.

    Recommended defaults for Trippi-AI:
    - openrouter + openrouter/free: zero cost, good enough for constraint extraction
    - anthropic + claude-haiku: fast, cheap, strong structured extraction
    """
    s = settings or get_settings()
    provider = resolve_provider(s)

    if provider == "heuristic":
        raise RuntimeError("No chat model for heuristic provider")

    if provider == "anthropic":
        if not s.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic")
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=s.llm_model or s.anthropic_model,
            api_key=s.anthropic_api_key,
            temperature=temperature,
            max_tokens=1024,
        )

    if provider == "openrouter":
        if not s.openrouter_api_key:
            raise RuntimeError("OPENROUTER_API_KEY is required when LLM_PROVIDER=openrouter")
        from langchain_openai import ChatOpenAI

        model = s.llm_model or s.openrouter_model
        return ChatOpenAI(
            model=model,
            api_key=s.openrouter_api_key,
            base_url=s.openrouter_base_url,
            temperature=temperature,
            default_headers={
                "HTTP-Referer": s.openrouter_site_url,
                "X-Title": s.app_name,
            },
        )

    if provider == "openai":
        if not s.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=s.llm_model or s.openai_model,
            api_key=s.openai_api_key,
            temperature=temperature,
        )

    raise ValueError(f"Unhandled provider: {provider}")


def describe_llm(settings: Settings | None = None) -> dict[str, Any]:
    s = settings or get_settings()
    provider = resolve_provider(s)
    model = s.llm_model
    if not model:
        if provider == "anthropic":
            model = s.anthropic_model
        elif provider == "openrouter":
            model = s.openrouter_model
        elif provider == "openai":
            model = s.openai_model
        else:
            model = "none"
    return {
        "provider": provider,
        "model": model,
        "ready": provider_ready(s),
    }
