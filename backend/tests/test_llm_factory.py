import pytest

from app.config import Settings
from app.llm.factory import describe_llm, provider_ready, resolve_provider


def test_resolve_openrouter():
    s = Settings(
        llm_provider="openrouter",
        openrouter_api_key="sk-or-test",
        openrouter_model="openrouter/free",
        llm_model="",
    )
    assert resolve_provider(s) == "openrouter"
    assert provider_ready(s) is True
    info = describe_llm(s)
    assert info["model"] == "openrouter/free"


def test_resolve_anthropic():
    s = Settings(llm_provider="anthropic", anthropic_api_key="sk-ant-test", llm_model="")
    assert resolve_provider(s) == "anthropic"
    assert provider_ready(s) is True
    assert describe_llm(s)["model"] == "claude-haiku-4-5"


def test_heuristic_not_ready():
    s = Settings(llm_provider="heuristic")
    assert provider_ready(s) is False


def test_unknown_provider():
    s = Settings(llm_provider="nope")
    with pytest.raises(ValueError):
        resolve_provider(s)
