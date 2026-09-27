"""Minimal GitHub REST client: read PRs, post reviews, read reviewer replies."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import requests

API = "https://api.github.com"


class GitHubError(RuntimeError):
    pass


@dataclass
class PRRef:
    owner: str
    repo: str
    number: int

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.repo}"

    def __str__(self) -> str:
        return f"{self.slug}#{self.number}"


def parse_pr_ref(text: str) -> PRRef:
    """Accepts 'owner/repo#12' or a full PR URL."""
    m = re.match(r"^([\w.-]+)/([\w.-]+)#(\d+)$", text.strip())
    if not m:
        m = re.match(r"^https?://github\.com/([\w.-]+)/([\w.-]+)/pull/(\d+)", text.strip())
    if not m:
        raise GitHubError(f"Cannot parse PR reference {text!r}. Use owner/repo#123 or a PR URL.")
    return PRRef(m.group(1), m.group(2), int(m.group(3)))


class GitHub:
    def __init__(self, token: str | None):
        self.s = requests.Session()
        self.s.headers.update({"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"})
        if token:
            self.s.headers["Authorization"] = f"Bearer {token}"
        self._login: str | None = None

    def _get(self, path: str, **params) -> Any:
        r = self.s.get(f"{API}{path}", params=params, timeout=30)
        if r.status_code >= 400:
            raise GitHubError(f"GET {path} -> {r.status_code}: {r.text[:300]}")
        return r.json()

    def _post(self, path: str, payload: dict) -> Any:
        r = self.s.post(f"{API}{path}", json=payload, timeout=30)
        if r.status_code >= 400:
            raise GitHubError(f"POST {path} -> {r.status_code}: {r.text[:300]}")
        return r.json()

    def me(self) -> str | None:
        if self._login is None and "Authorization" in self.s.headers:
            try:
                self._login = self._get("/user").get("login")
            except GitHubError:
                self._login = ""
        return self._login or None

    def pr(self, ref: PRRef) -> dict:
        return self._get(f"/repos/{ref.owner}/{ref.repo}/pulls/{ref.number}")

    def pr_files(self, ref: PRRef) -> list[dict]:
        files: list[dict] = []
        page = 1
        while True:
            batch = self._get(f"/repos/{ref.owner}/{ref.repo}/pulls/{ref.number}/files", per_page=100, page=page)
            files.extend(batch)
            if len(batch) < 100:
                return files
            page += 1

    def post_review(self, ref: PRRef, body: str, comments: list[dict], commit_id: str) -> dict:
        """Post a review. Tries inline comments first, falls back to a body-only review."""
        payload = {"body": body, "event": "COMMENT", "commit_id": commit_id}
        if comments:
            try:
                return self._post(f"/repos/{ref.owner}/{ref.repo}/pulls/{ref.number}/reviews", {**payload, "comments": comments})
            except GitHubError as e:
                if "422" not in str(e):
                    raise
                body += "\n\n_(inline placement failed for some comments; listed above instead)_"
        return self._post(f"/repos/{ref.owner}/{ref.repo}/pulls/{ref.number}/reviews", payload)

    def review_comments(self, ref: PRRef) -> list[dict]:
        """All inline review comments on the PR (includes replies)."""
        return self._get(f"/repos/{ref.owner}/{ref.repo}/pulls/{ref.number}/comments", per_page=100)

    def issue_comments(self, ref: PRRef) -> list[dict]:
        """Top-level conversation comments on the PR."""
        return self._get(f"/repos/{ref.owner}/{ref.repo}/issues/{ref.number}/comments", per_page=100)

    def reviews(self, ref: PRRef) -> list[dict]:
        return self._get(f"/repos/{ref.owner}/{ref.repo}/pulls/{ref.number}/reviews", per_page=100)
