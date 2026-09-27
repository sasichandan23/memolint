from pathlib import Path

from precedent.diff import from_file, new_line_numbers, parse_unified_diff
from precedent.llm import _parse_json
from precedent.memory import MemoryItem, RecallBundle
from precedent.reviewer import build_recall_query

DEMO = Path(__file__).resolve().parents[1] / "demo" / "prs"


def test_parses_demo_diffs_with_titles():
    b = from_file(DEMO / "01-coupon-validation.diff")
    assert b.title == "Add coupon validation to checkout"
    assert b.paths == ["orderflow/services/coupons.py"]
    assert b.files[0].additions == 53


def test_multi_file_diff_and_skip_rules():
    text = (DEMO / "02-order-export.diff").read_text()
    text += "\ndiff --git a/package-lock.json b/package-lock.json\n--- a/package-lock.json\n+++ b/package-lock.json\n@@ -1 +1 @@\n-a\n+b\n"
    b = parse_unified_diff(text, title="t")
    assert b.paths == ["orderflow/services/export.py", "orderflow/cli.py"]
    assert b.files[-1].skipped


def test_prompt_text_respects_budget():
    b = from_file(DEMO / "02-order-export.diff")
    out = b.to_prompt_text(max_chars=1800)
    assert len(out) <= 1900
    assert b.truncated


def test_new_line_numbers_for_inline_comments():
    b = from_file(DEMO / "03-refund-summary.diff")
    valid = new_line_numbers(b.files[0].patch)
    assert 1 in valid and 39 in valid and 40 not in valid


def test_json_parser_handles_fences_and_noise():
    assert _parse_json('{"a": 1}') == {"a": 1}
    assert _parse_json('Sure!\n```json\n{"a": 1}\n```') == {"a": 1}
    assert _parse_json('text before {"a": {"b": 2}} text after') == {"a": {"b": 2}}


def test_recall_bundle_prompt_groups_by_kind():
    rb = RecallBundle(directives=["Use guard clauses"])
    rb.feedback.append(MemoryItem(text="Reviewer rejected type hints", kind="feedback"))
    txt = rb.to_prompt_text()
    assert "Team rules" in txt and "Use guard clauses" in txt
    assert "responded to past suggestions" in txt
    assert rb.count() == 2


def test_recall_query_mentions_paths_and_code():
    b = from_file(DEMO / "03-refund-summary.diff")
    q = build_recall_query(b)
    assert "orderflow/api/refunds.py" in q
    assert "provider.get_refund" in q
