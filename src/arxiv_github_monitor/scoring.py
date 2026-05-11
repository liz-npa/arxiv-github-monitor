from __future__ import annotations

from .models import PaperRecord, RepoRecord, RepoSnapshot, from_iso, utcnow


def compute_topic_score(paper: PaperRecord, keywords: list[str]) -> float:
    haystack = f"{paper.title} {paper.summary}".lower()
    if not keywords:
        return 0.0
    matches = sum(1 for keyword in keywords if keyword.lower() in haystack)
    return min(1.0, matches / max(4, len(keywords) / 3))


def assign_repo_tier(repo: RepoRecord, latest_snapshot: RepoSnapshot | None) -> str:
    now = utcnow()
    first_seen = from_iso(repo.first_seen_at)
    if first_seen and (now - first_seen).days < 7:
        return "A"
    if latest_snapshot and latest_snapshot.stars >= 50:
        return "B"
    return "C"


def compute_repo_score(repo: RepoRecord, snapshots: list[RepoSnapshot], paper_topic_score: float) -> float:
    latest = snapshots[-1] if snapshots else None
    stars = latest.stars if latest else repo.current_stars
    recent_activity = 0.0
    if repo.last_pushed_at:
        recent_activity = 1.0
    star_signal = min(1.0, stars / 200)
    docs_signal = 1.0 if snapshots and snapshots[-1].readme_hash else 0.2
    readiness = 1.0 if repo.license and repo.default_branch else 0.4
    score = (
        0.30 * paper_topic_score
        + 0.20 * readiness
        + 0.20 * recent_activity
        + 0.15 * star_signal
        + 0.10 * docs_signal
        + 0.05 * (0.0 if repo.archived else 1.0)
    )
    return round(min(1.0, score), 4)
