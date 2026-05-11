from __future__ import annotations

import json
from pathlib import Path

from .arxiv_client import ArxivClient
from .config import load_config, AppConfig
from .github_client import GitHubClient
from .models import PaperRecord, RepoRecord, RepoSnapshot, to_iso, utcnow
from .repo_extractor import extract_repos_for_paper
from .scoring import assign_repo_tier, compute_repo_score, compute_topic_score
from .storage import (
    ensure_dirs,
    load_checkpoints,
    load_papers,
    load_repo_snapshots,
    load_repos,
    save_checkpoints,
    save_papers,
    save_repo_snapshots,
    save_repos,
)


class Pipeline:
    def __init__(self, root: str | Path, arxiv_client: ArxivClient | None = None, github_client: GitHubClient | None = None) -> None:
        self.config: AppConfig = load_config(root)
        ensure_dirs(self.config.root)
        self.arxiv_client = arxiv_client or ArxivClient(polite_delay_seconds=self.config.arxiv_polite_delay_seconds)
        self.github_client = github_client or GitHubClient()

    def discover_new_papers(self) -> list[PaperRecord]:
        existing = {paper.paper_id: paper for paper in load_papers(self.config.root)}
        checkpoints = load_checkpoints(self.config.root)
        discovered: list[PaperRecord] = []
        for category in self.config.categories:
            items = self.arxiv_client.fetch_rss_entries(category, max_entries=self.config.max_feed_entries_per_category)
            for item in items:
                raw_paper_id = item["paper_id"]
                paper_id = raw_paper_id.split("v")[0]
                if paper_id in existing:
                    continue
                try:
                    if item.get("source") == "api-search":
                        metadata = PaperRecord(
                            paper_id=paper_id,
                            version=item.get("version", raw_paper_id[len(paper_id):] or "v1"),
                            title=item.get("title", ""),
                            authors=item.get("authors", []),
                            summary=item.get("summary", ""),
                            categories=item.get("categories", [category]),
                            published_at=item.get("published_at"),
                            updated_at=item.get("updated_at"),
                            abs_url=item.get("abs_url", f"https://arxiv.org/abs/{raw_paper_id}"),
                            pdf_url=item.get("pdf_url", f"https://arxiv.org/pdf/{raw_paper_id}.pdf"),
                            source="api-search",
                        )
                    else:
                        metadata = self.arxiv_client.fetch_paper_metadata(raw_paper_id)
                        metadata.source = "rss+api"
                except Exception:
                    continue
                metadata.first_seen_at = to_iso(utcnow())
                metadata.topic_score = compute_topic_score(metadata, self.config.paper_topic_keywords)
                discovered.append(metadata)
                existing[paper_id] = metadata
                if len(discovered) >= self.config.max_new_papers_per_run:
                    break
            checkpoints[f"rss:{category}"] = to_iso(utcnow())
            if len(discovered) >= self.config.max_new_papers_per_run:
                break
        all_papers = sorted(existing.values(), key=lambda paper: paper.first_seen_at or paper.updated_at or "")
        save_papers(self.config.root, all_papers)
        save_checkpoints(self.config.root, checkpoints)
        return discovered

    def extract_repos(self, papers: list[PaperRecord], include_pdf_fallback: bool = False) -> list[PaperRecord]:
        all_papers = load_papers(self.config.root)
        paper_index = {paper.paper_id: paper for paper in all_papers}
        updated: list[PaperRecord] = []
        for paper in papers:
            result = extract_repos_for_paper(paper, include_pdf_fallback=include_pdf_fallback)
            paper.repo_candidates = result.repos
            paper.repo_extraction_source = result.source
            paper.repo_extraction_status = result.status
            paper_index[paper.paper_id] = paper
            updated.append(paper)
        save_papers(self.config.root, list(paper_index.values()))
        return updated

    def poll_repos(self, papers: list[PaperRecord]) -> tuple[list[RepoRecord], list[RepoSnapshot]]:
        repo_map = {repo.repo: repo for repo in load_repos(self.config.root)}
        snapshots = load_repo_snapshots(self.config.root)
        new_snapshots: list[RepoSnapshot] = []
        for paper in papers:
            for repo_name in paper.repo_candidates:
                current_first_seen = repo_map[repo_name].first_seen_at if repo_name in repo_map else (to_iso(utcnow()) or "")
                repo_record, snapshot = self.github_client.fetch_repo_metadata(repo_name, paper.paper_id, first_seen_at=current_first_seen)
                repo_record.tier = assign_repo_tier(repo_record, snapshot)
                repo_record.score = compute_repo_score(repo_record, [*snapshots, snapshot], paper.topic_score)
                repo_map[repo_name] = repo_record
                snapshots.append(snapshot)
                new_snapshots.append(snapshot)
        save_repos(self.config.root, list(repo_map.values()))
        save_repo_snapshots(self.config.root, snapshots)
        return list(repo_map.values()), new_snapshots

    def poll_existing_repos(self) -> tuple[list[RepoRecord], list[RepoSnapshot]]:
        papers = {paper.paper_id: paper for paper in load_papers(self.config.root)}
        existing_repos = load_repos(self.config.root)
        snapshots = load_repo_snapshots(self.config.root)
        repo_map = {repo.repo: repo for repo in existing_repos}
        new_snapshots: list[RepoSnapshot] = []
        for repo_name, repo_record in repo_map.items():
            paper = papers.get(repo_record.paper_id)
            topic_score = paper.topic_score if paper else 0.0
            refreshed_record, snapshot = self.github_client.fetch_repo_metadata(repo_name, repo_record.paper_id, first_seen_at=repo_record.first_seen_at)
            refreshed_record.tier = assign_repo_tier(refreshed_record, snapshot)
            refreshed_record.score = compute_repo_score(refreshed_record, [*snapshots, snapshot], topic_score)
            repo_map[repo_name] = refreshed_record
            snapshots.append(snapshot)
            new_snapshots.append(snapshot)
        save_repos(self.config.root, list(repo_map.values()))
        save_repo_snapshots(self.config.root, snapshots)
        return list(repo_map.values()), new_snapshots

    def generate_report(self) -> dict:
        papers = load_papers(self.config.root)
        repos = load_repos(self.config.root)
        snapshots = load_repo_snapshots(self.config.root)
        latest_snapshot_by_repo: dict[str, RepoSnapshot] = {}
        for snapshot in snapshots:
            latest_snapshot_by_repo[snapshot.repo] = snapshot
        new_papers = sorted(papers, key=lambda p: p.first_seen_at or "", reverse=True)[:20]
        high_potential = sorted(repos, key=lambda r: r.score, reverse=True)[:20]
        payload = {
            "new_papers_with_repos": [paper.to_dict() for paper in new_papers if paper.repo_candidates],
            "high_potential_repos": [repo.to_dict() for repo in high_potential],
            "repo_latest_snapshots": {repo: snap.to_dict() for repo, snap in latest_snapshot_by_repo.items()},
            "generated_at": to_iso(utcnow()),
        }
        output_dir = self.config.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "daily-report.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        lines = ["# Daily arXiv → GitHub Report", "", "## New papers with repos"]
        for paper in payload["new_papers_with_repos"]:
            lines.append(f"- [{paper['paper_id']}] {paper['title']}")
            lines.append(f"  - Categories: {', '.join(paper['categories'])}")
            lines.append(f"  - Repos: {', '.join(paper['repo_candidates'])}")
        lines.append("")
        lines.append("## High-potential repos")
        for repo in payload["high_potential_repos"][:10]:
            lines.append(f"- {repo['repo']} — score {repo['score']}")
        (output_dir / "daily-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        return payload
