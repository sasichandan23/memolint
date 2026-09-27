"""Provider chain: config ordering, and failover when a provider is rate limited."""

import httpx2 as httpx
import pytest
from openai import RateLimitError

from memolint.config import load_settings
from memolint.llm import LLM, LLMConfig, LLMError

BASE_ENV = {
    "HINDSIGHT_BASE_URL": "https://hs.example",
    "GROQ_API_KEY": "gsk_test",
    "GEMINI_API_KEY": "gem_test",
}


def _env(monkeypatch, **overrides):
    for k in ("LLM_PROVIDER", "LLM_MODEL", "LLM_BASE_URL", "GROQ_API_KEY", "GEMINI_API_KEY", "OLLAMA_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    for k, v in {**BASE_ENV, **overrides}.items():
        monkeypatch.setenv(k, v)


def test_chain_puts_primary_first_and_keeps_other_configured_providers(monkeypatch):
    _env(monkeypatch)
    s = load_settings()
    assert [c.provider for c in s.llm_chain] == ["groq", "gemini"]
    assert s.llm.model == "llama-3.3-70b-versatile"


def test_primary_can_be_gemini(monkeypatch):
    _env(monkeypatch, LLM_PROVIDER="gemini")
    s = load_settings()
    assert [c.provider for c in s.llm_chain] == ["gemini", "groq"]


def test_missing_optional_key_just_shortens_the_chain(monkeypatch):
    _env(monkeypatch)
    monkeypatch.delenv("GEMINI_API_KEY")
    s = load_settings()
    assert [c.provider for c in s.llm_chain] == ["groq"]


def test_model_override_applies_to_primary_only(monkeypatch):
    _env(monkeypatch, LLM_MODEL="custom-model")
    s = load_settings()
    assert s.llm.model == "custom-model"
    assert s.llm_fallbacks[0].model == "gemini-2.5-flash"


def _rate_limit(retry_after: str | None):
    headers = {"retry-after": retry_after} if retry_after else {}
    resp = httpx.Response(429, headers=headers, request=httpx.Request("POST", "https://x"))
    return RateLimitError("rate limited", response=resp, body=None)


class FakeLLM(LLM):
    """Replaces the network call; each provider yields queued outcomes in order."""

    def __init__(self, configs, script):
        super().__init__(configs)
        self.script = script
        self.seen: list[str] = []

    def _call(self, cfg, messages, *, max_tokens, temperature):
        self.seen.append(cfg.provider)
        outcome = self.script[cfg.provider].pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeResponse:
    def __init__(self, text):
        self.choices = [type("C", (), {"message": type("M", (), {"content": text})()})()]
        self.usage = None


GROQ = LLMConfig("groq", "https://groq", "k", "m")
GEMINI = LLMConfig("gemini", "https://gemini", "k", "m")


def test_daily_cap_switches_provider_without_waiting(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: pytest.fail("should not wait out a daily cap"))
    llm = FakeLLM([GROQ, GEMINI], {
        "groq": [_rate_limit("3600")],
        "gemini": [FakeResponse('{"summary": "ok"}')],
    })
    assert llm.complete_json("sys", "user") == {"summary": "ok"}
    assert llm.seen == ["groq", "gemini"]
    assert llm.cfg.provider == "gemini"


def test_short_burst_limit_waits_and_retries_same_provider(monkeypatch):
    waits: list[float] = []
    monkeypatch.setattr("time.sleep", waits.append)
    llm = FakeLLM([GROQ, GEMINI], {
        "groq": [_rate_limit("5"), FakeResponse('{"summary": "ok"}')],
        "gemini": [],
    })
    assert llm.complete_json("sys", "user") == {"summary": "ok"}
    assert llm.seen == ["groq", "groq"]
    assert waits == [5.0]


def test_single_provider_chain_reports_actionable_error(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    llm = FakeLLM([GROQ], {"groq": [_rate_limit("3600")]})
    with pytest.raises(LLMError, match="GEMINI_API_KEY"):
        llm.complete_json("sys", "user")


def test_malformed_json_is_repaired_before_switching(monkeypatch):
    llm = FakeLLM([GROQ, GEMINI], {
        "groq": [FakeResponse("not json at all"), FakeResponse('{"summary": "fixed"}')],
        "gemini": [],
    })
    assert llm.complete_json("sys", "user") == {"summary": "fixed"}
    assert llm.seen == ["groq", "groq"]
