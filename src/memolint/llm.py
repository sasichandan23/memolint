"""Thin LLM client. Any OpenAI-compatible endpoint (Groq, Gemini, Ollama, ...).

Designed for free tiers: small prompts, JSON-mode responses, and automatic
back-off on 429s so a rate limit is a pause rather than a crash.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

from openai import APIStatusError, OpenAI, RateLimitError

from .config import MAX_OUTPUT_TOKENS, LLMConfig


class LLMError(RuntimeError):
    pass


class LLM:
    def __init__(self, cfg: LLMConfig):
        self.cfg = cfg
        self.client = OpenAI(base_url=cfg.base_url, api_key=cfg.api_key, max_retries=3)
        self.last_usage: dict[str, int] = {}

    def complete_json(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int = MAX_OUTPUT_TOKENS,
        temperature: float = 0.2,
        attempts: int = 4,
    ) -> dict[str, Any]:
        """Ask for a JSON object and parse it. Retries on rate limits and on malformed JSON."""
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        last_err: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                resp = self._call(messages, max_tokens=max_tokens, temperature=temperature)
            except RateLimitError as e:
                wait = _retry_after(e) or min(60, 5 * attempt)
                print(f"[llm] rate limited by {self.cfg.provider}, waiting {wait:.0f}s (attempt {attempt}/{attempts})")
                time.sleep(wait)
                last_err = e
                continue
            except APIStatusError as e:
                raise LLMError(f"{self.cfg.provider} returned {e.status_code}: {e.message}") from e

            text = resp.choices[0].message.content or ""
            if resp.usage:
                self.last_usage = {
                    "prompt_tokens": resp.usage.prompt_tokens or 0,
                    "completion_tokens": resp.usage.completion_tokens or 0,
                }
            try:
                return _parse_json(text)
            except ValueError as e:
                last_err = e
                # Feed the error back once so the model can repair its output.
                messages = messages + [
                    {"role": "assistant", "content": text},
                    {"role": "user", "content": "That was not valid JSON. Return only the JSON object."},
                ]
        raise LLMError(f"LLM did not return usable JSON after {attempts} attempts: {last_err}")

    def _call(self, messages: list[dict[str, str]], *, max_tokens: int, temperature: float):
        kwargs: dict[str, Any] = dict(
            model=self.cfg.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        # JSON mode is supported by Groq, Gemini's OpenAI endpoint and recent Ollama.
        # Some hosts reject it; fall back silently and rely on prompt + parser.
        try:
            return self.client.chat.completions.create(response_format={"type": "json_object"}, **kwargs)
        except APIStatusError as e:
            if e.status_code == 400 and "response_format" in (e.message or ""):
                return self.client.chat.completions.create(**kwargs)
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
