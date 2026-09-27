"""Thin LLM client. Any OpenAI-compatible endpoint (Groq, Gemini, Ollama, ...).

Designed for free tiers: small prompts, JSON-mode responses, and automatic
back-off on 429s so a rate limit is a pause rather than a crash.
"""

from __future__ import annotations

import json
import re
import time
from collections import deque
from typing import Any

from openai import APIStatusError, OpenAI, RateLimitError

from .config import MAX_OUTPUT_TOKENS, LLMConfig


class LLMError(RuntimeError):
    pass


# A 429 carrying a retry-after longer than this means a daily cap, not a per-minute
# burst. Waiting it out would stall a demo, so we move to the next provider instead.
SWITCH_IF_WAIT_EXCEEDS = 90.0


class _Exhausted(Exception):
    """This provider is rate limited beyond what is worth waiting for."""


class _RateWindow:
    """Client-side pacing so we stay under a provider's tokens-per-minute cap.

    Being told to wait by a 429 costs more than waiting voluntarily: the request is
    wasted and, in a chain, it can bounce the run onto a different model mid-demo.
    """

    def __init__(self, tokens_per_min: int, *, now_fn=time.time, sleep_fn=time.sleep):
        self.limit = tokens_per_min
        self.events: deque[tuple[float, int]] = deque()
        # Injectable so tests can exercise the waiting logic without real delays.
        self._now = now_fn
        self._sleep = sleep_fn

    def _spent(self, now: float) -> int:
        while self.events and now - self.events[0][0] > 60.0:
            self.events.popleft()
        return sum(t for _, t in self.events)

    def reserve(self, projected: int, *, announce=None) -> None:
        """Wait, if needed, until this call fits inside the rolling one-minute budget."""
        if self.limit <= 0:
            return
        # Bounded: each pass either drops the oldest event or gives up, so a sleep that
        # does not advance the clock cannot spin here forever.
        for _ in range(len(self.events) + 1):
            now = self._now()
            if not self.events or self._spent(now) + projected <= self.limit:
                return
            wait = 60.0 - (now - self.events[0][0]) + 0.5
            if wait <= 0:
                self.events.popleft()
                continue
            if announce:
                announce(wait)
            self._sleep(wait)
            self.events.popleft()

    def record(self, tokens: int) -> None:
        if self.limit > 0:
            self.events.append((self._now(), tokens))


class LLM:
    """Calls the first working provider in a chain, failing over on rate limits.

    A team with only a Groq key gets a single-provider chain and identical behaviour.
    A team that also set a Gemini key keeps working after Groq's daily cap is hit.
    """

    def __init__(self, configs: LLMConfig | list[LLMConfig]):
        self.configs = [configs] if isinstance(configs, LLMConfig) else list(configs)
        if not self.configs:
            raise LLMError("No LLM provider configured.")
        self.cfg = self.configs[0]
        self.last_usage: dict[str, int] = {}
        self._clients: dict[str, OpenAI] = {}
        self._windows: dict[str, _RateWindow] = {
            c.provider: _RateWindow(c.tokens_per_min) for c in self.configs
        }

    def pin_to_active(self) -> None:
        """Drop the fallbacks and stay on whichever provider last answered.

        Used when several calls must be comparable: switching models halfway through
        an A/B comparison would make the two sides measure different things.
        """
        self.configs = [self.cfg]

    def _client(self, cfg: LLMConfig) -> OpenAI:
        if cfg.provider not in self._clients:
            self._clients[cfg.provider] = OpenAI(base_url=cfg.base_url, api_key=cfg.api_key, max_retries=3)
        return self._clients[cfg.provider]

    def complete_json(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int = MAX_OUTPUT_TOKENS,
        temperature: float = 0.2,
        attempts: int = 4,
    ) -> dict[str, Any]:
        """Ask for a JSON object and parse it, failing over between providers if needed."""
        last_err: Exception | None = None
        for idx, cfg in enumerate(self.configs):
            try:
                result = self._complete_with(cfg, system, user, max_tokens=max_tokens,
                                             temperature=temperature, attempts=attempts)
                self.cfg = cfg  # remember which provider actually answered
                return result
            except _Exhausted as e:
                last_err = e
                remaining = self.configs[idx + 1 :]
                if remaining:
                    print(f"[llm] {cfg.provider} is rate limited; switching to {remaining[0].provider}")
                    continue
                raise LLMError(
                    f"{cfg.provider} is rate limited and no fallback provider is configured. "
                    f"Add GEMINI_API_KEY to .env, or wait for the limit to reset."
                ) from e
            except LLMError as e:
                last_err = e
                remaining = self.configs[idx + 1 :]
                if remaining:
                    print(f"[llm] {cfg.provider} failed ({e}); switching to {remaining[0].provider}")
                    continue
                raise
        raise LLMError(f"Every configured provider failed: {last_err}")

    def _complete_with(
        self, cfg: LLMConfig, system: str, user: str, *,
        max_tokens: int, temperature: float, attempts: int,
    ) -> dict[str, Any]:
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        window = self._windows.setdefault(cfg.provider, _RateWindow(cfg.tokens_per_min))
        projected = approx_tokens(system) + approx_tokens(user) + max_tokens
        window.reserve(
            projected,
            announce=lambda w: print(f"[llm] pacing for {cfg.provider} free tier, waiting {w:.0f}s"),
        )
        last_err: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                resp = self._call(cfg, messages, max_tokens=max_tokens, temperature=temperature)
            except RateLimitError as e:
                wait = _retry_after(e) or min(60.0, 5.0 * attempt)
                if wait > SWITCH_IF_WAIT_EXCEEDS:
                    raise _Exhausted(f"{cfg.provider} asked us to wait {wait:.0f}s") from e
                print(f"[llm] rate limited by {cfg.provider}, waiting {wait:.0f}s (attempt {attempt}/{attempts})")
                time.sleep(wait)
                last_err = e
                continue
            except APIStatusError as e:
                raise LLMError(f"{cfg.provider} returned {e.status_code}: {e.message}") from e

            text = resp.choices[0].message.content or ""
            if resp.usage:
                self.last_usage = {
                    "prompt_tokens": resp.usage.prompt_tokens or 0,
                    "completion_tokens": resp.usage.completion_tokens or 0,
                }
                window.record((resp.usage.prompt_tokens or 0) + (resp.usage.completion_tokens or 0))
            else:
                window.record(projected)
            try:
                return _parse_json(text)
            except ValueError as e:
                last_err = e
                # Feed the error back once so the model can repair its output.
                messages = messages + [
                    {"role": "assistant", "content": text},
                    {"role": "user", "content": "That was not valid JSON. Return only the JSON object."},
                ]
        if isinstance(last_err, RateLimitError):
            raise _Exhausted(f"{cfg.provider} stayed rate limited for {attempts} attempts")
        raise LLMError(f"{cfg.provider} did not return usable JSON after {attempts} attempts: {last_err}")

    def _call(self, cfg: LLMConfig, messages: list[dict[str, str]], *, max_tokens: int, temperature: float):
        kwargs: dict[str, Any] = dict(
            model=cfg.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        # JSON mode is supported by Groq, Gemini's OpenAI endpoint and recent Ollama.
        # Some hosts reject it; fall back silently and rely on prompt + parser.
        client = self._client(cfg)
        try:
            return client.chat.completions.create(response_format={"type": "json_object"}, **kwargs)
        except APIStatusError as e:
            if e.status_code == 400 and "response_format" in (e.message or ""):
                return client.chat.completions.create(**kwargs)
            raise


def _retry_after(err: RateLimitError) -> float | None:
    try:
        val = err.response.headers.get("retry-after")
        return float(val) if val else None
    except Exception:
        return None


_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.S)


def _parse_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("{"):
        return json.loads(text)
    m = _FENCE.search(text)
    if m:
        return json.loads(m.group(1))
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        return json.loads(text[start : end + 1])
    raise ValueError("no JSON object found in response")


def approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)
