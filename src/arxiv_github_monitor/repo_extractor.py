from __future__ import annotations

from dataclasses import dataclass

from .models import PaperRecord
from .utils import extract_github_urls, extract_links_from_html, fetch_text, normalize_github_repo


@dataclass(slots=True)
class ExtractionResult:
    repos: list[str]
    source: str | None
    status: str


def extract_repos_for_paper(paper: PaperRecord, include_pdf_fallback: bool = False) -> ExtractionResult:
    scans: list[tuple[str, str]] = [
        ("summary", paper.summary),
        ("title", paper.title),
    ]
    for source, text in scans:
        repos = _normalize_urls(extract_github_urls(text))
        if repos:
            return ExtractionResult(repos=repos, source=source, status="found")

    html = fetch_text(paper.abs_url)
    html_repos = _normalize_urls(extract_github_urls(html))
    if html_repos:
        return ExtractionResult(repos=html_repos, source="abstract_html", status="found")

    links = extract_links_from_html(html)
    linked_repos = _normalize_urls(links)
    if linked_repos:
        return ExtractionResult(repos=linked_repos, source="abstract_links", status="found")

    if include_pdf_fallback:
        try:
            pdf_like_text = fetch_text(paper.pdf_url)
        except Exception:
            pdf_like_text = ""
        pdf_repos = _normalize_urls(extract_github_urls(pdf_like_text))
        if pdf_repos:
            return ExtractionResult(repos=pdf_repos, source="pdf_fallback", status="found")

    return ExtractionResult(repos=[], source=None, status="not_found")


def _normalize_urls(urls: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for url in urls:
        repo = normalize_github_repo(url)
        if repo and repo not in seen:
            seen.add(repo)
            normalized.append(repo)
    return normalized
