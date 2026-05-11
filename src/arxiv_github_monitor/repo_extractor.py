from __future__ import annotations

from dataclasses import dataclass
import io
from urllib.request import Request, urlopen

from .models import PaperRecord
from .utils import extract_github_urls, extract_links_from_html, fetch_text, normalize_github_repo, USER_AGENT


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
        pdf_text = _extract_pdf_text(paper.pdf_url)
        pdf_repos = _extract_repo_candidates_from_pdf_text(pdf_text)
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


def _extract_pdf_text(pdf_url: str, max_pages: int = 3) -> str:
    try:
        from pypdf import PdfReader
    except Exception:
        return ""
    try:
        request = Request(pdf_url, headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=30) as response:
            pdf_bytes = response.read()
        reader = PdfReader(io.BytesIO(pdf_bytes))
    except Exception:
        return ""
    parts: list[str] = []
    for page in reader.pages[:max_pages]:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            continue
    return "\n".join(parts)


_PDF_POSITIVE_CUES = (
    "code:",
    "source code",
    "our code",
    "official code",
    "implementation",
    "repo:",
    "repository",
    "project page",
    "project:",
    "available at",
    "open-source",
)

_PDF_NEGATIVE_CUES = (
    "references",
    "baseline",
    "we compare against",
    "compare against",
    "built on",
    "based on",
    "using ",
    "we use ",
    "borrowed from",
)


def _extract_repo_candidates_from_pdf_text(pdf_text: str) -> list[str]:
    if not pdf_text:
        return []
    lowered = pdf_text.lower()
    refs_index = lowered.find("references")
    if refs_index != -1:
        pdf_text = pdf_text[:refs_index]
    matches = []
    seen: set[str] = set()
    prev_line = ""
    for raw_line in pdf_text.splitlines():
        line = raw_line.strip()
        if not line:
            prev_line = ""
            continue
        context = f"{prev_line} {line}".strip().lower()
        has_positive = any(cue in context for cue in _PDF_POSITIVE_CUES)
        has_negative = any(cue in context for cue in _PDF_NEGATIVE_CUES)
        if has_positive and not has_negative:
            for url in extract_github_urls(line):
                repo = normalize_github_repo(url)
                if repo and repo not in seen:
                    seen.add(repo)
                    matches.append(repo)
        prev_line = line
    return matches
