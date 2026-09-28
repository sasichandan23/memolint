"""Build one copy-paste folder per team member.

    python scripts/build_submit_packs.py

Each folder gets three files that contain nothing but the text to paste, so nothing
extra can be pasted by accident. Instructions live in a separate README.
Regenerate after editing any article or the posts file.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "submit"
REPO = "https://github.com/WaifuPuller/MemoLint"
HINDSIGHT = "https://github.com/vectorize-io/hindsight"

PEOPLE = [
    {
        "folder": "team lead",
        "article": "article-memory-design.md",
        "post": "Post A",
        "subreddit": "r/llmdevs",
        "backup": "r/aimemory",
    },
    {
        "folder": "team member",
        "article": "article-ab-test.md",
        "post": "Post B",
        "subreddit": "r/aiagents",
        "backup": "r/sideproject",
    },
]


def linkedin_body(section: str) -> str:
    """Pull one post out of the combined file, stripping the blockquote markers."""
    src = (ROOT / "docs" / "linkedin-posts.md").read_text(encoding="utf-8")
    block = src.split(f"## {section}")[1]
    lines = []
    for raw in block.splitlines():
        if not raw.startswith(">"):
            if lines and raw.strip() == "---":
                break
            continue
        lines.append(raw[2:] if raw.startswith("> ") else "")
    return "\n".join(lines).strip() + "\n"


def readme(p: dict, title: str) -> str:
    return f"""# {p['folder'].title()} — what to post

Three files here. Each one contains only the text to paste. Do the steps in order,
because the LinkedIn comment and the Reddit post both need the article's URL.

## 1. article.md

Publish on Dev.to (fastest, takes a GitHub login and accepts markdown as-is), or
Medium or Hashnode. It must end up public and linkable.

Paste the whole file. Check the headings and code blocks survived, then publish and
copy the URL.

## 2. linkedin.txt

Paste the whole file as a normal LinkedIn post, not a LinkedIn article. Then add two
comments on your own post, in this order:

1. the article URL from step 1
2. {HINDSIGHT}

## 3. reddit.txt

Submit to {p['subreddit']} as a **Link** post, not a text post. The file has the title
on the first line; paste your article URL into the link field.

Use {p['subreddit']}, not the same one as your teammate. Two similar links to one
subreddit in the same hour looks like spam. Backup: {p['backup']}.

## Rules

The word "hackathon" must not appear in any of this, including hashtags. These files
are clean. If you edit them, keep it that way.

Read the article before publishing. It is written in the first person and describes
decisions as yours. Change anything that does not match what you actually did.
"""


def main() -> None:
    for p in PEOPLE:
        d = OUT / p["folder"]
        d.mkdir(parents=True, exist_ok=True)

        article = (ROOT / "docs" / p["article"]).read_text(encoding="utf-8")
        title = article.splitlines()[0].lstrip("# ").strip()
        (d / "article.md").write_text(article, encoding="utf-8")
        (d / "linkedin.txt").write_text(linkedin_body(p["post"]), encoding="utf-8")
        (d / "reddit.txt").write_text(
            f"{title}\n\n[paste your published article URL into Reddit's link field]\n",
            encoding="utf-8",
        )
        (d / "README.md").write_text(readme(p, title), encoding="utf-8")

        words = len([w for w in re.split(r"\s+", article) if w])
        chars = len((d / "linkedin.txt").read_text(encoding="utf-8").strip())
        print(f"{p['folder']:<12} article {words} words | linkedin {chars} chars | {p['subreddit']}")


if __name__ == "__main__":
    main()
