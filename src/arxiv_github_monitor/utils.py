from __future__ import annotations

import hashlib
import json
import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

USER_AGENT = "arxiv-github-monitor/0.1 (+https://github.com)"


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self.links.append(href)


def fetch_text(url: str, headers: dict[str, str] | None = None, timeout: int = 20) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    with urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


_GITHUB_RE = re.compile(r"https?://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")


def extract_github_urls(text: str) -> list[str]:
    return list(dict.fromkeys(_GITHUB_RE.findall(text or "")))


def extract_links_from_html(html: str) -> list[str]:
    parser = LinkParser()
    parser.feed(html)
    return parser.links


def normalize_github_repo(url: str) -> str | None:
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    if parsed.netloc.lower() not in {"github.com", "www.github.com"}:
        return None
    parts = [segment for segment in parsed.path.split("/") if segment]
    if len(parts) < 2:
        return None
    owner, repo = parts[0], parts[1]
    repo = repo.removesuffix(".git")
    if not owner or not repo:
        return None
    return f"{owner}/{repo}"


def sha1_text(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def pretty_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)
