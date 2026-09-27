"""The review itself: diff + recalled memory -> structured findings."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .diff import DiffBundle
from .llm import LLM, approx_tokens
from .memory import Memory, RecallBundle

SYSTEM_PROMPT = """You are a senior engineer reviewing a pull request for a specific team.
You have a memory of this team's conventions, how they responded to your past suggestions,
and incidents tied to code patterns. Use it. A generic linter is worthless to this team;
a reviewer who remembers what they care about is not.

Rules:
- Team rules and past rejections are binding. If the team rejected a kind of suggestion before,
  do not raise it again; list it under "skipped_on_purpose" with the reason instead.
- When a finding is grounded in memory (a convention, a past rejection, a past incident), say so
  in the "precedent" field, quoting the memory in one short sentence. Otherwise set it to null.
- If a change matches a pattern that caused a past incident, that finding is "high" severity and
  must name the incident.
- Be concrete. Point to the file and line. Suggest the fix, not just the problem.
- Prefer few, real findings over many nitpicks. Maximum 6 findings.
- Only comment on lines that appear in the diff.

Return ONLY a JSON object with this shape:
{
  "summary": "two sentences on what the PR does and your overall verdict",
  "findings": [
    {"file": "path/in/repo.py", "line": 42, "severity": "high|medium|low",
     "title": "short imperative title", "body": "what is wrong and how to fix it",
     "precedent": "the memory this is based on, or null"}
  ],
  "skipped_on_purpose": [
    {"what": "the suggestion you would normally make", "why": "the memory that told you not to"}
  ]
}"""


@dataclass
class Finding:
    id: str
    file: str
    line: int | None
    severity: str
    title: str
    body: str
    precedent: str | None = None


@dataclass
class Review:
    pr_ref: str
    title: str
    summary: str
    findings: list[Finding]
    skipped_on_purpose: list[dict[str, str]] = field(default_factory=list)
    memories_used: int = 0
    memory_enabled: bool = True
    usage: dict[str, int] = field(default_factory=dict)
    diff_truncated: bool = False

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


def build_recall_query(bundle: DiffBundle) -> str:
    """A short query that captures what this diff is about, for Hindsight recall."""
    added = []
    for f in bundle.files:
        if f.skipped:
            continue
        for line in f.patch.splitlines():
            if line.startswith("+") and line.strip("+ ").strip():
                added.append(line[1:].strip())
            if len(added) >= 40:
                break
    snippet = " ".join(added)[:600]
    return (
        f"Code review of '{bundle.title}' touching {', '.join(bundle.paths[:8])}. "
        f"Team conventions, past review feedback, rejected suggestions, and incidents relevant to: {snippet}"
    )


def review_diff(
    bundle: DiffBundle,
    pr_ref: str,
    llm: LLM,
    memory: Memory | None,
) -> Review:
    recalled = RecallBundle()
    if memory is not None:
        recalled = memory.recall_for_review(build_recall_query(bundle))

    diff_text = bundle.to_prompt_text()
    user = (
        f"Pull request: {bundle.title}\n"
        f"{('Description: ' + bundle.description.strip()) if bundle.description.strip() else ''}\n\n"
        f"## What you remember about this team\n{recalled.to_prompt_text()}\n\n"
        f"## Diff\n{diff_text}\n"
    )
    data = llm.complete_json(SYSTEM_PROMPT, user)

    findings: list[Finding] = []
    for i, f in enumerate(data.get("findings", []) or [], start=1):
        if not isinstance(f, dict):
            continue
        line = f.get("line")
        try:
            line = int(line) if line is not None else None
        except (TypeError, ValueError):
            line = None
        sev = str(f.get("severity", "medium")).lower()
        if sev not in ("high", "medium", "low"):
            sev = "medium"
        findings.append(
            Finding(
                id=f"F{i}",
                file=str(f.get("file", "")),
                line=line,
                severity=sev,
                title=str(f.get("title", "")).strip() or "Finding",
                body=str(f.get("body", "")).strip(),
                precedent=(str(f["precedent"]).strip() if f.get("precedent") else None),
            )
        )

    review = Review(
        pr_ref=pr_ref,
        title=bundle.title,
        summary=str(data.get("summary", "")).strip(),
        findings=findings,
        skipped_on_purpose=[s for s in (data.get("skipped_on_purpose") or []) if isinstance(s, dict)],
        memories_used=recalled.count(),
        memory_enabled=memory is not None,
        usage=dict(llm.last_usage),
        diff_truncated=bundle.truncated,
    )
    if memory is not None:
        memory.record_review(pr_ref, bundle.title, [asdict(f) for f in findings])
    return review


LEARN_PROMPT = """You extract review feedback from pull request comments so a code review agent can learn.
You are given the findings the agent posted and the human replies. For each reply that reacts to a finding
or states a team rule, output one item.

Return ONLY JSON:
{"items": [
  {"finding_id": "F2 or null", "verdict": "accepted|rejected|rule|incident",
   "note": "the human's reasoning in one sentence",
   "rule": "if verdict is rule: the convention stated as a reusable instruction, else null",
   "incident": "if verdict is incident: what broke and why, else null"}
]}
Ignore replies that are just thanks or unrelated chatter."""


def learn_from_comments(findings: list[dict[str, Any]], comments: list[str], llm: LLM) -> list[dict[str, Any]]:
    if not comments:
        return []
    f_text = "\n".join(f"{f['id']}: [{f['severity']}] {f['title']} ({f['file']}:{f.get('line')})" for f in findings)
    c_text = "\n\n".join(f"- {c[:600]}" for c in comments[:20])
    user = f"## Findings we posted\n{f_text or '(none)'}\n\n## Human comments\n{c_text}"
    data = llm.complete_json(LEARN_PROMPT, user, max_tokens=800)
    return [i for i in (data.get("items") or []) if isinstance(i, dict)]


def format_markdown(review: Review) -> str:
    """Markdown body for a GitHub review."""
    lines = [f"### Precedent review", "", review.summary or "", ""]
    if review.findings:
        for f in review.findings:
            where = f"`{f.file}`" + (f" line {f.line}" if f.line else "")
            lines.append(f"**{f.id} · {f.severity.upper()} · {f.title}** ({where})")
            lines.append(f.body)
            if f.precedent:
                lines.append(f"> Precedent: {f.precedent}")
            lines.append("")
    else:
        lines.append("No findings. Looks good.")
    if review.skipped_on_purpose:
        lines.append("<details><summary>Deliberately not raised (learned from past feedback)</summary>\n")
        for s in review.skipped_on_purpose:
            lines.append(f"- {s.get('what')} — {s.get('why')}")
        lines.append("\n</details>")
    lines.append("")
    lines.append(
        f"_Memory: {review.memories_used} memories recalled_ · reply to any comment with 'accept', 'reject', or a rule and I will remember it."
        if review.memory_enabled
        else "_Memory disabled for this review._"
    )
    return "\n".join(lines)


def estimate_prompt_tokens(bundle: DiffBundle, recalled: RecallBundle) -> int:
    return approx_tokens(SYSTEM_PROMPT) + approx_tokens(bundle.to_prompt_text()) + approx_tokens(recalled.to_prompt_text())
