"""The memory layer. Everything the reviewer knows about a team lives in one Hindsight bank.

What gets retained, and how it is tagged:

  convention  - an explicit team rule ("use guard clauses, not nested ifs"). Also stored as a
                Hindsight *directive* so it is a standing instruction, not just a fact.
  feedback    - how a reviewer responded to one of our findings (accepted / rejected, and why).
                Rejections are the most valuable memory: they stop us repeating ourselves.
  incident    - a bug or outage tied to a code pattern ("N+1 query in checkout caused the
                Sept 3 outage"). Lets us flag risky patterns with a real precedent.
  review      - a summary of each review we posted, so we know what we already said.

Before every review we `recall` against the diff and inject the results into the prompt,
grouped by the tags above. That is the whole trick: the LLM is stateless, the bank is not.
"""

from __future__ import annotations

import atexit
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from hindsight_client import Hindsight

from .config import MAX_MEMORY_TOKENS, Settings

BANK_MISSION = (
    "You are the long-term memory of a code review agent for the {repo} repository. "
    "Remember the team's coding conventions, how reviewers responded to past review suggestions "
    "(what was accepted, what was rejected and why), past bugs and incidents linked to code patterns, "
    "and architectural decisions. Prefer concrete, reusable rules over vague impressions."
)


@dataclass
class MemoryItem:
    text: str
    kind: str  # convention | feedback | incident | review | other
    when: str | None = None
    tags: list[str] = field(default_factory=list)


@dataclass
class RecallBundle:
    directives: list[str] = field(default_factory=list)
    conventions: list[MemoryItem] = field(default_factory=list)
    feedback: list[MemoryItem] = field(default_factory=list)
    incidents: list[MemoryItem] = field(default_factory=list)
    reviews: list[MemoryItem] = field(default_factory=list)
    other: list[MemoryItem] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not any([self.directives, self.conventions, self.feedback, self.incidents, self.reviews, self.other])

    def count(self) -> int:
        return len(self.directives) + sum(len(x) for x in (self.conventions, self.feedback, self.incidents, self.reviews, self.other))

    def to_prompt_text(self) -> str:
        if self.is_empty():
            return "(no memories yet for this repository)"
        parts: list[str] = []

        def block(title: str, items: list[MemoryItem]) -> None:
            if items:
                lines = [f"- {i.text}" + (f" (recorded {i.when[:10]})" if i.when else "") for i in items]
                parts.append(f"{title}:\n" + "\n".join(lines))

        if self.directives:
            parts.append("Team rules (always apply):\n" + "\n".join(f"- {d}" for d in self.directives))
        block("Team conventions learned from past reviews", self.conventions)
        block("How reviewers responded to past suggestions", self.feedback)
        block("Past bugs and incidents tied to code patterns", self.incidents)
        block("Earlier reviews on this repository", self.reviews)
        block("Other context", self.other)
        return "\n\n".join(parts)


class Memory:
    def __init__(self, settings: Settings, bank_id: str, repo_slug: str):
        self.client = Hindsight(base_url=settings.hindsight_base_url, api_key=settings.hindsight_api_key)
        self.bank_id = bank_id
        self.repo_slug = repo_slug
        # The client holds an aiohttp session; without this, Python prints
        # "Unclosed client session" over our output at interpreter shutdown.
        atexit.register(self.close)

    def close(self) -> None:
        try:
            self.client.close()
        except Exception:
            pass

    # ---------- bank lifecycle ----------

    def ensure_bank(self) -> None:
        """Create the bank with a mission if it does not exist. Safe to call repeatedly."""
        try:
            self.client.create_bank(
                bank_id=self.bank_id,
                name=f"Memolint: {self.repo_slug}",
                mission=BANK_MISSION.format(repo=self.repo_slug),
            )
        except Exception as e:  # already exists, or server rejects re-create
            if "exist" not in str(e).lower() and "409" not in str(e):
                raise

    def reset(self) -> None:
        try:
            self.client.delete_bank(self.bank_id)
        except Exception:
            pass
        self.ensure_bank()

    # ---------- retain ----------

    def _retain(self, content: str, kind: str, extra_tags: list[str] | None = None, context: str | None = None) -> None:
        tags = [f"kind:{kind}", f"repo:{self.repo_slug}"] + (extra_tags or [])
        self.client.retain(
            bank_id=self.bank_id,
            content=content,
            context=context or f"{kind} for {self.repo_slug}",
            tags=tags,
            timestamp=datetime.now(timezone.utc),
        )

    def teach(self, rule: str, source: str = "reviewer") -> None:
        """An explicit convention. Stored as a directive (standing rule) and as a memory."""
        name = rule[:60]
        try:
            self.client.create_directive(bank_id=self.bank_id, name=name, content=rule, priority=10, tags=["convention"])
        except Exception:
            pass  # directives are a nicety; the retained fact still carries the rule
        self._retain(f"Team convention ({source}): {rule}", kind="convention", extra_tags=["convention"])

    def record_feedback(self, finding: dict[str, Any], verdict: str, note: str | None, pr_ref: str) -> None:
        """How a human responded to one of our findings. verdict is 'accepted' or 'rejected'."""
        where = f"{finding.get('file')}:{finding.get('line')}" if finding.get("file") else "the change"
        text = (
            f"Reviewer {verdict} the suggestion '{finding.get('title')}' on {where} in {pr_ref}. "
            f"Suggestion was: {finding.get('body', '')[:300]}"
        )
        if note:
            text += f" Reviewer said: {note}"
        if verdict == "rejected":
            text += " Do not raise this kind of suggestion again for this team unless the rule changes."
        self._retain(text, kind="feedback", extra_tags=["feedback", verdict, f"pr:{pr_ref}"])

    def record_incident(self, description: str, pr_ref: str | None = None) -> None:
        text = f"Incident precedent: {description}"
        if pr_ref:
            text += f" (linked to {pr_ref})"
        self._retain(text, kind="incident", extra_tags=["incident"] + ([f"pr:{pr_ref}"] if pr_ref else []))

    def record_review(self, pr_ref: str, title: str, findings: list[dict[str, Any]]) -> None:
        if not findings:
            summary = "no findings"
        else:
            summary = "; ".join(f"[{f.get('severity')}] {f.get('title')} in {f.get('file')}" for f in findings[:8])
        self._retain(
            f"Reviewed {pr_ref} ('{title}'). Findings raised: {summary}.",
            kind="review",
            extra_tags=["review", f"pr:{pr_ref}"],
        )

    # ---------- recall ----------

    def recall_for_review(self, query: str, max_tokens: int = MAX_MEMORY_TOKENS) -> RecallBundle:
        bundle = RecallBundle()
        try:
            for d in self.client.list_directives(bank_id=self.bank_id).items:
                if d.is_active:
                    bundle.directives.append(d.content)
        except Exception:
            pass
        resp = self.client.recall(bank_id=self.bank_id, query=query, max_tokens=max_tokens, budget="mid")
        for r in resp.results or []:
            tags = r.tags or []
            kind = next((t.split(":", 1)[1] for t in tags if t.startswith("kind:")), "other")
            item = MemoryItem(text=r.text, kind=kind, when=r.occurred_start or r.mentioned_at, tags=tags)
            getattr(bundle, {"convention": "conventions", "feedback": "feedback", "incident": "incidents", "review": "reviews"}.get(kind, "other")).append(item)
        return bundle

    def reflect(self, question: str) -> str:
        resp = self.client.reflect(bank_id=self.bank_id, query=question, budget="low")
        return resp.text

    def list_all(self, limit: int = 100) -> list[MemoryItem]:
        resp = self.client.list_memories(bank_id=self.bank_id, limit=limit)
        out: list[MemoryItem] = []
        for m in resp.items or []:
            tags = m.tags or []
            kind = next((t.split(":", 1)[1] for t in tags if t.startswith("kind:")), m.fact_type or "other")
            out.append(MemoryItem(text=m.text or "", kind=kind, when=m.mentioned_at or m.var_date, tags=tags))
        return out

    def list_directives(self) -> list[str]:
        try:
            return [d.content for d in self.client.list_directives(bank_id=self.bank_id).items if d.is_active]
        except Exception:
            return []
