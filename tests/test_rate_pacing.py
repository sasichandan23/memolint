"""Client-side pacing and provider pinning. Uses a fake clock: no real waiting."""

import pytest

from memolint.llm import LLM, LLMConfig, _RateWindow

GROQ = LLMConfig("groq", "https://groq", "k", "m", tokens_per_min=8000)
GEMINI = LLMConfig("gemini", "https://gemini", "k", "m", tokens_per_min=250000)


class Clock:
    """A clock that only moves when something sleeps."""

    def __init__(self):
        self.t = 1000.0
        self.slept: list[float] = []

    def now(self):
        return self.t

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.t += seconds


def window(limit):
    c = Clock()
    return _RateWindow(limit, now_fn=c.now, sleep_fn=c.sleep), c


def test_calls_under_the_limit_never_wait():
    w, c = window(8000)
    w.record(3000)
    w.reserve(3000)
    assert c.slept == []


def test_waits_when_the_next_call_would_exceed_the_limit():
    w, c = window(8000)
    w.record(5000)
    w.reserve(5000)
    assert len(c.slept) == 1 and 60 <= c.slept[0] <= 61


def test_spend_outside_the_window_is_forgotten():
    w, c = window(8000)
    w.record(8000)
    c.t += 61  # a minute goes by
    w.reserve(5000)
    assert c.slept == []


def test_zero_limit_disables_pacing():
    w, c = window(0)
    w.record(999_999)
    w.reserve(999_999)
    assert c.slept == []


def test_reserve_terminates_even_if_sleeping_does_not_advance_time():
    w = _RateWindow(8000, now_fn=lambda: 1000.0, sleep_fn=lambda s: None)
    w.record(5000)
    w.record(5000)
    w.reserve(8000)  # must return rather than spin


def test_announce_reports_the_wait():
    w, c = window(8000)
    w.record(7000)
    seen: list[float] = []
    w.reserve(5000, announce=seen.append)
    assert seen and seen[0] > 0


def test_pin_to_active_drops_fallbacks():
    llm = LLM([GROQ, GEMINI])
    assert [c.provider for c in llm.configs] == ["groq", "gemini"]
    llm.cfg = GEMINI
    llm.pin_to_active()
    assert [c.provider for c in llm.configs] == ["gemini"]
