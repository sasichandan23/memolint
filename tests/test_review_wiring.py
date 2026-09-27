"""End-to-end wiring with a stub LLM and no network: diff -> review -> saved state -> feedback lookup."""

from pathlib import Path

import memolint.state as state
from memolint.diff import from_file
from memolint.reviewer import format_markdown, review_diff

DEMO = Path(__file__).resolve().parents[1] / "demo" / "prs"


class StubLLM:
    last_usage = {"prompt_tokens": 1200, "completion_tokens": 300}

    def __init__(self):
        self.calls = []

    def complete_json(self, system, user, **kw):
        self.calls.append((system, user))
        return {
            "summary": "Adds coupon validation. Works, but has style and robustness issues.",
            "findings": [
                {"file": "orderflow/services/coupons.py", "line": 16, "severity": "medium",
                 "title": "Replace print with structured logging", "body": "Use a logger.", "precedent": None},
                {"file": "orderflow/services/coupons.py", "line": "44", "severity": "HIGH",
                 "title": "Bare except swallows errors", "body": "Catch specific exceptions.", "precedent": "rule: no bare except"},
                {"file": "orderflow/services/coupons.py", "line": None, "severity": "weird",
                 "title": "Nested conditionals", "body": "Use guard clauses."},
            ],
            "skipped_on_purpose": [{"what": "type hints on _lookup", "why": "team rejected this before"}],
        }


def test_review_without_memory_and_state_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "STATE_DIR", tmp_path / ".memolint")
    bundle = from_file(DEMO / "01-coupon-validation.diff")
    llm = StubLLM()
    review = review_diff(bundle, "orderflow#1", llm, memory=None)

    assert review.memory_enabled is False and review.memories_used == 0
    assert [f.id for f in review.findings] == ["F1", "F2", "F3"]
    assert review.findings[1].line == 44 and review.findings[1].severity == "high"
    assert review.findings[2].line is None and review.findings[2].severity == "medium"
    assert review.usage["prompt_tokens"] == 1200
    _, user_prompt = llm.calls[0]
    assert "no memories yet" in user_prompt and "coupons.py" in user_prompt

    state.save_review("orderflow#1", review.to_dict())
    hit = state.find_finding("f2")
    assert hit and hit[1]["title"] == "Bare except swallows errors"
    assert state.find_finding("F9") is None

    md = format_markdown(review)
    assert "F2 · HIGH" in md and "Precedent: rule: no bare except" in md
    assert "Deliberately not raised" in md and "Memory disabled" in md
