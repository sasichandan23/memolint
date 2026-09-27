"""Memolint CLI. `memolint --help` for the full list."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import __version__
from .config import ConfigError, Settings, bank_id_for, load_settings
from .diff import DiffBundle, from_file, from_git, from_github_files, new_line_numbers
from .github_client import GitHub, GitHubError, PRRef, parse_pr_ref
from .llm import LLM, LLMError
from .memory import Memory
from .reviewer import Review, format_markdown, learn_from_comments, review_diff
from .state import find_finding, load_review, save_review

app = typer.Typer(help="A code reviewer that remembers your team's precedents.")
console = Console()

SEV_COLOR = {"high": "red", "medium": "yellow", "low": "cyan"}


# ---------- helpers ----------

def _settings(require_llm: bool = True) -> Settings:
    try:
        return load_settings(require_llm=require_llm)
    except ConfigError as e:
        console.print(f"[red]Config error:[/] {e}")
        raise typer.Exit(2)


def _repo_slug(explicit: Optional[str]) -> str:
    if explicit:
        return explicit
    import os
    if os.getenv("MEMOLINT_REPO"):
        return os.environ["MEMOLINT_REPO"]
    try:
        url = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True, check=True).stdout.strip()
        tail = url.rstrip("/").removesuffix(".git")
        parts = tail.replace(":", "/").split("/")
        if len(parts) >= 2:
            return f"{parts[-2]}/{parts[-1]}"
    except Exception:
        pass
    return Path.cwd().name


def _memory(settings: Settings, repo_slug: str) -> Memory:
    m = Memory(settings, bank_id_for(repo_slug), repo_slug)
    m.ensure_bank()
    return m


def _print_review(review: Review) -> None:
    head = f"[bold]{review.title}[/]  [dim]({review.pr_ref})[/]"
    mem = (
        f"[green]memory on[/] · {review.memories_used} memories recalled"
        if review.memory_enabled
        else "[red]memory off[/]"
    )
    usage = review.usage
    tok = f" · {usage.get('prompt_tokens', '?')} in / {usage.get('completion_tokens', '?')} out tokens" if usage else ""
    console.print(Panel(f"{head}\n{mem}{tok}", title="Memolint review", border_style="blue"))
    if review.summary:
        console.print(review.summary, style="italic")
        console.print()
    if not review.findings:
        console.print("[green]No findings.[/]")
    for f in review.findings:
        color = SEV_COLOR.get(f.severity, "white")
        where = f"{f.file}" + (f":{f.line}" if f.line else "")
        console.print(f"[bold {color}]{f.id}  {f.severity.upper():6}[/] [bold]{f.title}[/]  [dim]{where}[/]")
        console.print(f"     {f.body}")
        if f.precedent:
            console.print(f"     [magenta]precedent:[/] {f.precedent}")
        console.print()
    if review.skipped_on_purpose:
        t = Table(title="Deliberately not raised (learned from you)", show_lines=False, border_style="dim")
        t.add_column("Would have said")
        t.add_column("Why not")
        for s in review.skipped_on_purpose:
            t.add_row(str(s.get("what", "")), str(s.get("why", "")))
        console.print(t)
    if review.diff_truncated:
        console.print("[dim]Diff was truncated to fit the token budget.[/]")


def _run_review(bundle: DiffBundle, pr_ref: str, repo_slug: str, settings: Settings, use_memory: bool) -> Review:
    llm = LLM(settings.llm)
    memory = _memory(settings, repo_slug) if use_memory else None
    try:
        review = review_diff(bundle, pr_ref, llm, memory)
    except LLMError as e:
        console.print(f"[red]LLM error:[/] {e}")
        raise typer.Exit(1)
    key = pr_ref if use_memory else f"{pr_ref}-nomem"
    save_review(key, {**review.to_dict(), "repo": repo_slug})
    return review


# ---------- commands ----------

@app.callback(invoke_without_command=True)
def _main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", help="Show version and exit."),
):
    if version:
        console.print(f"memolint {__version__}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit()


@app.command()
def init(repo: Optional[str] = typer.Option(None, help="owner/repo or any name. Defaults to git origin.")):
    """Create the memory bank for a repository."""
    settings = _settings(require_llm=False)
    slug = _repo_slug(repo)
    _memory(settings, slug)
    console.print(f"[green]Bank ready:[/] {bank_id_for(slug)}  (repo {slug})")


@app.command()
def review(
    diff: Optional[Path] = typer.Option(None, "--diff", help="A unified .diff file to review."),
    git: Optional[str] = typer.Option(None, "--git", help="Git range like main..HEAD (uses the current repo)."),
    pr: Optional[str] = typer.Option(None, "--pr", help="GitHub PR: owner/repo#12 or URL."),
    repo: Optional[str] = typer.Option(None, help="Repository slug for the memory bank."),
    name: Optional[str] = typer.Option(None, help="Label for this review (defaults to file name / PR)."),
    no_memory: bool = typer.Option(False, "--no-memory", help="Review without recalling or retaining memory."),
    post: bool = typer.Option(False, "--post", help="Post the review to the GitHub PR."),
):
    """Review a change. Recalls team memory first, retains what it said after."""
    settings = _settings()
    sources = sum(x is not None for x in (diff, git, pr))
    if sources != 1:
        console.print("[red]Pick exactly one of --diff, --git, --pr.[/]")
        raise typer.Exit(2)

    gh: GitHub | None = None
    pr_data: dict | None = None
    if diff is not None:
        bundle = from_file(diff)
        slug = _repo_slug(repo)
        pr_ref = name or diff.stem
    elif git is not None:
        base, _, head = git.partition("..")
        bundle = from_git(base or "main", head.lstrip(".") or "HEAD")
        slug = _repo_slug(repo)
        pr_ref = name or f"git:{git}"
    else:
        ref = parse_pr_ref(pr)  # type: ignore[arg-type]
        gh = GitHub(settings.github_token)
        try:
            pr_data = gh.pr(ref)
            files = gh.pr_files(ref)
        except GitHubError as e:
            console.print(f"[red]GitHub:[/] {e}")
            raise typer.Exit(1)
        bundle = from_github_files(files, pr_data.get("title", ""), pr_data.get("body") or "")
        slug = repo or ref.slug
        pr_ref = name or str(ref)

    if not bundle.paths:
        console.print("[yellow]Nothing reviewable in this change (only skipped/binary files).[/]")
        raise typer.Exit(0)

    with console.status("Recalling memory and reviewing..." if not no_memory else "Reviewing (memory off)..."):
        rev = _run_review(bundle, pr_ref, slug, settings, use_memory=not no_memory)
    _print_review(rev)

    if post:
        if gh is None or pr_data is None:
            console.print("[yellow]--post only works with --pr.[/]")
            raise typer.Exit(2)
        ref = parse_pr_ref(pr)  # type: ignore[arg-type]
        valid = {f.path: new_line_numbers(f.patch) for f in bundle.files}
        comments = [
            {"path": f.file, "line": f.line, "side": "RIGHT",
             "body": f"**{f.id} · {f.severity.upper()} · {f.title}**\n\n{f.body}" + (f"\n\n> Precedent: {f.precedent}" if f.precedent else "")}
            for f in rev.findings
            if f.line and f.line in valid.get(f.file, set())
        ]
        try:
            gh.post_review(ref, format_markdown(rev), comments, pr_data["head"]["sha"])
            console.print(f"[green]Posted review to {ref}[/] ({len(comments)} inline comments)")
        except GitHubError as e:
            console.print(f"[red]Could not post:[/] {e}")
            raise typer.Exit(1)


@app.command()
def feedback(
    finding_id: str = typer.Argument(..., help="Finding id from the last review, e.g. F2."),
    accept: bool = typer.Option(False, "--accept", help="The suggestion was right."),
    reject: bool = typer.Option(False, "--reject", help="The suggestion was wrong for this team."),
    note: Optional[str] = typer.Option(None, help="Why. This is what the agent learns from."),
    rule: Optional[str] = typer.Option(None, help="Also store a standing convention, e.g. 'Never use print; use get_logger'."),
    incident: Optional[str] = typer.Option(None, help="Link this pattern to a past bug/outage."),
    review_key: Optional[str] = typer.Option(None, "--review", help="Which review the id belongs to (default: last)."),
):
    """Tell the reviewer how it did. Rejections stop it repeating itself; rules become conventions."""
    if accept == reject:
        console.print("[red]Pass exactly one of --accept / --reject.[/]")
        raise typer.Exit(2)
    settings = _settings(require_llm=False)
    hit = find_finding(finding_id, review_key)
    if not hit:
        console.print(f"[red]No finding {finding_id} in the {'last' if not review_key else review_key} review.[/]")
        raise typer.Exit(1)
    rev, f = hit
    mem = _memory(settings, rev.get("repo") or _repo_slug(None))
    verdict = "accepted" if accept else "rejected"
    mem.record_feedback(f, verdict, note, rev["pr_ref"])
    console.print(f"[green]Remembered:[/] {verdict} '{f['title']}'" + (f" — {note}" if note else ""))
    if rule:
        mem.teach(rule)
        console.print(f"[green]Convention stored:[/] {rule}")
    if incident:
        mem.record_incident(incident, rev["pr_ref"])
        console.print(f"[green]Incident linked:[/] {incident}")


@app.command()
def teach(rule: str = typer.Argument(..., help="A team convention in plain words."),
          repo: Optional[str] = typer.Option(None)):
    """Store a standing convention without going through a review."""
    settings = _settings(require_llm=False)
    _memory(settings, _repo_slug(repo)).teach(rule)
    console.print(f"[green]Convention stored:[/] {rule}")


@app.command()
def incident(description: str = typer.Argument(..., help="What broke, and the code pattern behind it."),
             pr: Optional[str] = typer.Option(None, help="PR or commit that caused it."),
             repo: Optional[str] = typer.Option(None)):
    """Record a bug or outage tied to a code pattern, so future PRs get warned."""
    settings = _settings(require_llm=False)
    _memory(settings, _repo_slug(repo)).record_incident(description, pr)
    console.print("[green]Incident remembered.[/]")


@app.command()
def learn(pr: str = typer.Argument(..., help="GitHub PR: owner/repo#12 or URL."),
          repo: Optional[str] = typer.Option(None)):
    """Read human replies on a PR we reviewed and learn from them."""
    settings = _settings()
    ref = parse_pr_ref(pr)
    gh = GitHub(settings.github_token)
    me = settings.bot_login or gh.me()
    rev = load_review(str(ref)) or {"findings": []}
    try:
        raw = gh.review_comments(ref) + gh.issue_comments(ref)
    except GitHubError as e:
        console.print(f"[red]GitHub:[/] {e}")
        raise typer.Exit(1)
    human = [c["body"] for c in raw if c.get("user", {}).get("login") != me and c.get("body")]
    if not human:
        console.print("No human comments to learn from yet.")
        raise typer.Exit(0)
    items = learn_from_comments(rev["findings"], human, LLM(settings.llm))
    mem = _memory(settings, repo or ref.slug)
    by_id = {f["id"]: f for f in rev["findings"]}
    for it in items:
        v = it.get("verdict")
        f = by_id.get(str(it.get("finding_id") or "").upper())
        if v in ("accepted", "rejected") and f:
            mem.record_feedback(f, v, it.get("note"), str(ref))
            console.print(f"[green]{v}[/] {f['title']}: {it.get('note')}")
        elif v == "rule" and it.get("rule"):
            mem.teach(it["rule"])
            console.print(f"[green]rule[/] {it['rule']}")
        elif v == "incident" and it.get("incident"):
            mem.record_incident(it["incident"], str(ref))
            console.print(f"[green]incident[/] {it['incident']}")
    console.print(f"Learned {len(items)} items from {len(human)} comments.")


@app.command()
def memories(repo: Optional[str] = typer.Option(None), limit: int = 50):
    """Show what the reviewer remembers about this repository."""
    settings = _settings(require_llm=False)
    mem = _memory(settings, _repo_slug(repo))
    rules = mem.list_directives()
    if rules:
        console.print(Panel("\n".join(f"- {r}" for r in rules), title="Standing rules (directives)", border_style="magenta"))
    items = mem.list_all(limit=limit)
    if not items:
        console.print("[dim]No memories yet.[/]")
        return
    t = Table(title=f"Memories in {mem.bank_id}", show_lines=False)
    t.add_column("kind", style="bold", width=11)
    t.add_column("when", width=10, style="dim")
    t.add_column("memory")
    for i in items:
        t.add_row(i.kind, (i.when or "")[:10], i.text)
    console.print(t)


@app.command()
def ask(question: str = typer.Argument(...), repo: Optional[str] = typer.Option(None)):
    """Ask the memory a question (Hindsight reflect), e.g. 'what does this team care about?'."""
    settings = _settings(require_llm=False)
    with console.status("Reflecting..."):
        answer = _memory(settings, _repo_slug(repo)).reflect(question)
    console.print(Panel(answer, title="Memolint", border_style="magenta"))


@app.command()
def reset(repo: Optional[str] = typer.Option(None), yes: bool = typer.Option(False, "--yes")):
    """Wipe the memory bank for a repository."""
    settings = _settings(require_llm=False)
    slug = _repo_slug(repo)
    if not yes and not typer.confirm(f"Delete all memories for {slug} ({bank_id_for(slug)})?"):
        raise typer.Exit()
    Memory(settings, bank_id_for(slug), slug).reset()
    console.print("[green]Bank reset.[/]")


# ---------- demo ----------

DEMO_DIR = Path(__file__).resolve().parents[2] / "demo" / "prs"
DEMO_REPO = "demo/orderflow"


def _pause(auto: bool, msg: str = "Press Enter to continue") -> None:
    if auto:
        time.sleep(1.0)
    else:
        console.input(f"[dim]{msg}...[/]")


def _find_by_keywords(review: Review, *keywords: str) -> Optional[str]:
    for f in review.findings:
        hay = (f.title + " " + f.body).lower()
        if any(k in hay for k in keywords):
            return f.id
    return None


@app.command()
def demo(auto: bool = typer.Option(False, "--auto", help="Run without pausing."),
         keep: bool = typer.Option(False, "--keep", help="Do not wipe the demo bank first.")):
    """Scripted walkthrough: three PRs, watch the reviewer learn between them."""
    settings = _settings()
    mem = Memory(settings, bank_id_for(DEMO_REPO), DEMO_REPO)
    if not keep:
        mem.reset()
        console.print("[dim]Demo memory bank wiped.[/]")
    else:
        mem.ensure_bank()

    def step(title: str, body: str) -> None:
        console.rule(f"[bold blue]{title}")
        console.print(body)
        console.print()

    # PR 1
    step("PR #1: Add coupon validation", "Fresh bank. The reviewer knows nothing about this team yet.")
    _pause(auto)
    b1 = from_file(DEMO_DIR / "01-coupon-validation.diff")
    r1 = _run_review(b1, "orderflow#1", DEMO_REPO, settings, use_memory=True)
    _print_review(r1)

    step("The team responds", "A reviewer accepts some findings, rejects one, and states two conventions.")
    _pause(auto)
    fid = _find_by_keywords(r1, "print")
    if fid:
        mem.record_feedback(next(f for f in r1.findings if f.id == fid).__dict__, "accepted", "Yes, never print in services.", "orderflow#1")
    mem.teach("Never use print() for logging. Use `log = get_logger(__name__)` from orderflow.logging and log structured fields.")
    console.print("[green]✓[/] accepted 'print' finding, rule stored: structured logger, never print")

    fid = _find_by_keywords(r1, "type hint", "annotation", "typing")
    if fid:
        mem.record_feedback(next(f for f in r1.findings if f.id == fid).__dict__, "rejected", "We do not add type hints to private helpers, only to public functions.", "orderflow#1")
        console.print("[yellow]✗[/] rejected 'type hints' finding: private helpers do not get type hints here")
    else:
        mem.teach("Do not ask for type hints on private helper functions (names starting with _). Only public functions need them.")
        console.print("[yellow]✗[/] rule stored: no type hints on private helpers")

    fid = _find_by_keywords(r1, "nested", "guard", "early return", "indentation")
    if fid:
        mem.record_feedback(next(f for f in r1.findings if f.id == fid).__dict__, "accepted", "Guard clauses, always.", "orderflow#1")
    mem.teach("Prefer guard clauses and early returns over nested if/else blocks.")
    console.print("[green]✓[/] accepted 'nested ifs' finding, rule stored: guard clauses over nesting")

    # PR 2
    step("PR #2: Add order export for finance", "Different file, same team. Watch what it flags, and what it now deliberately skips.")
    _pause(auto)
    b2 = from_file(DEMO_DIR / "02-order-export.diff")
    r2 = _run_review(b2, "orderflow#2", DEMO_REPO, settings, use_memory=True)
    _print_review(r2)

    step("The team responds", "The N+1 query finding gets accepted, and linked to a real outage.")
    _pause(auto)
    fid = _find_by_keywords(r2, "n+1", "per order", "inside the loop", "in the loop", "each order", "query in a loop", "loop")
    if fid:
        mem.record_feedback(next(f for f in r2.findings if f.id == fid).__dict__, "accepted", "Good catch.", "orderflow#2")
    mem.record_incident(
        "Per-row database calls inside a loop (N+1 queries) exhausted the Postgres connection pool during the "
        "Sept 3 checkout outage (PR #212, orders service). 41 minutes of failed checkouts. Batch-load with a single query instead.",
        "orderflow#2",
    )
    console.print("[green]✓[/] accepted N+1 finding, incident linked: Sept 3 checkout outage")

    # PR 3, without and with memory
    step("PR #3: Add refund summary endpoint", "First without memory (a generic reviewer), then with memory (this team's reviewer).")
    _pause(auto)
    b3 = from_file(DEMO_DIR / "03-refund-summary.diff")
    console.rule("[red]memory OFF")
    r3a = _run_review(b3, "orderflow#3", DEMO_REPO, settings, use_memory=False)
    _print_review(r3a)
    _pause(auto)
    console.rule("[green]memory ON")
    b3 = from_file(DEMO_DIR / "03-refund-summary.diff")
    r3b = _run_review(b3, "orderflow#3", DEMO_REPO, settings, use_memory=True)
    _print_review(r3b)

    console.rule("[bold blue]What the reviewer now knows")
    for r in mem.list_directives():
        console.print(f"[magenta]rule[/] {r}")
    console.print("\nRun [bold]memolint memories --repo demo/orderflow[/] to see every memory, "
                  "or [bold]memolint ask 'what does this team care about?' --repo demo/orderflow[/].")


if __name__ == "__main__":
    app()
