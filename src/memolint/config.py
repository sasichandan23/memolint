"""Configuration loaded from environment / .env. Everything defaults to free tiers."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Provider presets. All speak the OpenAI chat-completions protocol, so one client
# covers every option. Add a new row to support another host.
PROVIDERS: dict[str, dict[str, str]] = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "key_env": "GROQ_API_KEY",
        "model": "llama-3.3-70b-versatile",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "key_env": "GEMINI_API_KEY",
        "model": "gemini-2.5-flash",
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "key_env": "OLLAMA_API_KEY",  # ignored by Ollama, any value works
        "model": "qwen2.5-coder:7b",
    },
    "custom": {
        "base_url": "",  # taken from LLM_BASE_URL
        "key_env": "LLM_API_KEY",
        "model": "",
    },
}

# Token budgets sized for Groq's free tier (8K tokens/min on the listed models).
MAX_DIFF_CHARS = int(os.getenv("MEMOLINT_MAX_DIFF_CHARS", "10000"))      # ~2.5K tokens
MAX_MEMORY_TOKENS = int(os.getenv("MEMOLINT_MAX_MEMORY_TOKENS", "1000"))
MAX_OUTPUT_TOKENS = int(os.getenv("MEMOLINT_MAX_OUTPUT_TOKENS", "1400"))

STATE_DIR = Path(os.getenv("MEMOLINT_STATE_DIR", ".memolint"))


class ConfigError(RuntimeError):
    pass


@dataclass
class LLMConfig:
    provider: str
    base_url: str
    api_key: str
    model: str


@dataclass
class Settings:
    hindsight_base_url: str
    hindsight_api_key: str | None
    llm: LLMConfig
    github_token: str | None
    bot_login: str | None = None
    extra: dict = field(default_factory=dict)


def _llm_config() -> LLMConfig:
    provider = os.getenv("LLM_PROVIDER", "groq").strip().lower()
    if provider not in PROVIDERS:
        raise ConfigError(f"LLM_PROVIDER must be one of {', '.join(PROVIDERS)}; got {provider!r}")
    preset = PROVIDERS[provider]
    base_url = os.getenv("LLM_BASE_URL") or preset["base_url"]
    api_key = os.getenv(preset["key_env"]) or ("ollama" if provider == "ollama" else "")
    model = os.getenv("LLM_MODEL") or preset["model"]
    if not base_url:
        raise ConfigError("LLM_BASE_URL is required when LLM_PROVIDER=custom")
    if not api_key:
        raise ConfigError(f"{preset['key_env']} is not set (needed for LLM_PROVIDER={provider})")
    if not model:
        raise ConfigError("LLM_MODEL is required when LLM_PROVIDER=custom")
    return LLMConfig(provider=provider, base_url=base_url, api_key=api_key, model=model)


def load_settings(require_llm: bool = True) -> Settings:
    base_url = os.getenv("HINDSIGHT_BASE_URL", "").strip()
    if not base_url:
        raise ConfigError("HINDSIGHT_BASE_URL is not set. See .env.example.")
    llm = _llm_config() if require_llm else LLMConfig("none", "", "", "")
    return Settings(
        hindsight_base_url=base_url.rstrip("/"),
        hindsight_api_key=os.getenv("HINDSIGHT_API_KEY") or None,
        llm=llm,
        github_token=os.getenv("GITHUB_TOKEN") or None,
        bot_login=os.getenv("MEMOLINT_BOT_LOGIN") or None,
    )


def bank_id_for(repo_slug: str) -> str:
    """One Hindsight memory bank per repository. Slug like 'owner/repo' or a local name."""
    prefix = os.getenv("MEMOLINT_BANK_PREFIX", "memolint")
    clean = re.sub(r"[^a-zA-Z0-9_-]+", "-", repo_slug).strip("-").lower()
    return f"{prefix}-{clean}"[:64]
