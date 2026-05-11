from __future__ import annotations

import base64
import json
import os
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from .models import RepoRecord, RepoSnapshot, utcnow, to_iso
from .utils import fetch_text, sha1_text

GITHUB_API = "https://api.github.com"


class GitHubClient:
    def __init__(self, token: str | None = None) -> None:
        self.token = token or os.getenv("GITHUB_TOKEN")

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _get_json(self, url: str) -> dict:
        request = Request(url, headers=self._headers())
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))

    def fetch_repo_metadata(self, repo: str, paper_id: str, first_seen_at: str | None = None) -> tuple[RepoRecord, RepoSnapshot]:
        doc = self._get_json(f"{GITHUB_API}/repos/{repo}")
        license_name = None
        if isinstance(doc.get("license"), dict):
            license_name = doc["license"].get("spdx_id") or doc["license"].get("name")
        captured_at = to_iso(utcnow())
        readme_hash = None
        try:
            readme_hash = self.fetch_readme_hash(repo)
        except HTTPError:
            readme_hash = None
        repo_record = RepoRecord(
            repo=repo,
            paper_id=paper_id,
            first_seen_at=first_seen_at or captured_at or "",
            current_stars=int(doc.get("stargazers_count", 0)),
            current_forks=int(doc.get("forks_count", 0)),
            current_open_issues=int(doc.get("open_issues_count", 0)),
            current_watchers=int(doc.get("subscribers_count", doc.get("watchers_count", 0))),
            language=doc.get("language"),
            license=license_name,
            archived=bool(doc.get("archived", False)),
            disabled=bool(doc.get("disabled", False)),
            default_branch=doc.get("default_branch"),
            last_pushed_at=doc.get("pushed_at"),
            description=doc.get("description"),
        )
        snapshot = RepoSnapshot(
            repo=repo,
            captured_at=captured_at or "",
            stars=repo_record.current_stars,
            forks=repo_record.current_forks,
            open_issues=repo_record.current_open_issues,
            watchers=repo_record.current_watchers,
            last_pushed_at=repo_record.last_pushed_at,
            readme_hash=readme_hash,
        )
        return repo_record, snapshot

    def fetch_readme_hash(self, repo: str) -> str | None:
        doc = self._get_json(f"{GITHUB_API}/repos/{repo}/readme")
        content = doc.get("content")
        if not content:
            return None
        decoded = base64.b64decode(content).decode("utf-8", errors="replace")
        return sha1_text(decoded)
