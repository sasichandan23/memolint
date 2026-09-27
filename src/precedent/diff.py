"""Turn a unified diff (file, git range, or GitHub PR) into a compact, budgeted view."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .config import MAX_DIFF_CHARS

SKIP_PATTERNS = [
    r"(^|/)package-lock\.json$", r"(^|/)yarn\.lock$", r"(^|/)pnpm-lock\.yaml$", r"(^|/)poetry\.lock$",
    r"(^|/)Cargo\.lock$", r"(^|/)go\.sum$", r"\.min\.(js|css)$", r"(^|/)dist/", r"(^|/)build/",
    r"(^|/)vendor/", r"(^|/)node_modules/", r"\.(png|jpg|jpeg|gif|svg|ico|pdf|woff2?|ttf)$",
    r"(^|/)__snapshots__/", r"\.generated\.",
]
_SKIP = [re.compile(p) for p in SKIP_PATTERNS]


@dataclass
class FileDiff:
    path: str
    patch: str
    additions: int = 0
    deletions: int = 0
    skipped: bool = False


@dataclass
class DiffBundle:
    title: str
    description: str
    files: list[FileDiff] = field(default_factory=list)
    truncated: bool = False

    @property
    def paths(self) -> list[str]:
        return [f.path for f in self.files if not f.skipped]

    def to_prompt_text(self, max_chars: int = MAX_DIFF_CHARS) -> str:
        """Render the diff within a character budget, spreading it across files."""
        active = [f for f in self.files if not f.skipped]
        if not active:
            return "(no reviewable changes)"
        per_file = max(800, max_chars // len(active))
        out: list[str] = []
        for f in active:
            body = f.patch
            if len(body) > per_file:
                body = body[:per_file] + f"\n... [truncated {len(f.patch) - per_file} chars]"
                self.truncated = True
            out.append(f"### {f.path} (+{f.additions} -{f.deletions})\n```diff\n{body}\n```")
        text = "\n\n".join(out)
        if len(text) > max_chars:
            text = text[:max_chars] + "\n... [diff truncated to fit budget]"
            self.truncated = True
        return text


def _should_skip(path: str) -> bool:
    return any(p.search(path) for p in _SKIP)


def parse_unified_diff(text: str, title: str = "", description: str = "") -> DiffBundle:
    bundle = DiffBundle(title=title, description=description)
    current: FileDiff | None = None
    for line in text.splitlines():
        if line.startswith("diff --git"):
            m = re.match(r"diff --git a/(.+?) b/(.+)$", line)
            path = m.group(2) if m else line.split()[-1]
            current = FileDiff(path=path, patch="", skipped=_should_skip(path))
            bundle.files.append(current)
            continue
        if current is None:
            continue
        if line.startswith(("index ", "--- ", "+++ ", "new file mode", "deleted file mode", "similarity", "rename ")):
            if line.startswith("+++ b/"):
                current.path = line[6:]
                current.skipped = _should_skip(current.path)
            continue
        current.patch += line + "\n"
        if line.startswith("+"):
            current.additions += 1
        elif line.startswith("-"):
            current.deletions += 1
    return bundle


def from_file(path: str | Path, title: str | None = None) -> DiffBundle:
    """Load a .diff file. Leading lines starting with '# ' become title + description."""
    p = Path(path)
    text = p.read_text(encoding="utf-8", errors="replace")
    desc_lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("diff --git"):
            break
        if line.startswith("# "):
            desc_lines.append(line[2:])
    t = title or (desc_lines[0] if desc_lines else p.stem)
    return parse_unified_diff(text, title=t, description="\n".join(desc_lines[1:]))


def from_git(base: str = "main", head: str = "HEAD", repo: str | Path = ".") -> DiffBundle:
    rng = f"{base}...{head}"
    out = subprocess.run(
        ["git", "diff", rng, "--no-color"], cwd=str(repo), capture_output=True, text=True, check=True
    ).stdout
    log = subprocess.run(
        ["git", "log", "--format=%s", rng], cwd=str(repo), capture_output=True, text=True
    ).stdout.strip()
    title = log.splitlines()[0] if log else f"Changes {rng}"
    return parse_unified_diff(out, title=title, description=log)


def from_github_files(files: list[dict], title: str, description: str) -> DiffBundle:
    """Build from the GitHub 'list PR files' payload (each item has filename + patch)."""
    bundle = DiffBundle(title=title, description=description or "")
    for f in files:
        path = f.get("filename", "")
        patch = f.get("patch") or ""
        bundle.files.append(
            FileDiff(
                path=path,
                patch=patch,
                additions=f.get("additions", 0),
                deletions=f.get("deletions", 0),
                skipped=_should_skip(path) or not patch,
            )
        )
    return bundle


def new_line_numbers(patch: str) -> set[int]:
    """Line numbers on the RIGHT side present in the patch (valid targets for inline comments)."""
    valid: set[int] = set()
    new_ln = 0
    for line in patch.splitlines():
        m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
        if m:
            new_ln = int(m.group(1))
            continue
        if line.startswith("-"):
            continue
        valid.add(new_ln)
        new_ln += 1
    return valid
