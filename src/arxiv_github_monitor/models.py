from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Any

ISO_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def to_iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime(ISO_FORMAT)


def from_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.strptime(value, ISO_FORMAT).replace(tzinfo=timezone.utc)


@dataclass(slots=True)
class PaperRecord:
    paper_id: str
    version: str
    title: str
    authors: list[str]
    summary: str
    categories: list[str]
    published_at: str | None
    updated_at: str | None
    abs_url: str
    pdf_url: str
    source: str
    repo_candidates: list[str] = field(default_factory=list)
    repo_extraction_status: str = "pending"
    repo_extraction_source: str | None = None
    topic_score: float = 0.0
    first_seen_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PaperRecord":
        return cls(**data)


@dataclass(slots=True)
class RepoRecord:
    repo: str
    paper_id: str
    first_seen_at: str
    current_stars: int = 0
    current_forks: int = 0
    current_open_issues: int = 0
    current_watchers: int = 0
    language: str | None = None
    license: str | None = None
    archived: bool = False
    disabled: bool = False
    default_branch: str | None = None
    last_pushed_at: str | None = None
    tier: str = "A"
    score: float = 0.0
    status: str = "active"
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RepoRecord":
        return cls(**data)


@dataclass(slots=True)
class RepoSnapshot:
    repo: str
    captured_at: str
    stars: int
    forks: int
    open_issues: int
    watchers: int
    last_pushed_at: str | None
    release_count: int = 0
    readme_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RepoSnapshot":
        return cls(**data)
