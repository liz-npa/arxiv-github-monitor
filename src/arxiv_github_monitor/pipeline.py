from __future__ import annotations

from datetime import datetime, timezone
from html import escape
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
        (output_dir / "dashboard.html").write_text(_render_dashboard_html(payload), encoding="utf-8")
        return payload


def _render_dashboard_html(payload: dict) -> str:
    repo_snapshots = payload.get("repo_latest_snapshots", {})
    paper_by_repo: dict[str, dict] = {}
    for paper in payload.get("new_papers_with_repos", []):
        for repo in paper.get("repo_candidates", []):
            paper_by_repo[repo] = paper

    cards: list[tuple[float, str]] = []
    for repo in payload.get("high_potential_repos", []):
        repo_name = repo["repo"]
        paper = paper_by_repo.get(repo_name, {})
        snapshot = repo_snapshots.get(repo_name, {})
        maintenance_score, maintenance_label = _maintenance_status(repo)
        last_pushed = repo.get("last_pushed_at") or "unknown"
        release_count = snapshot.get("release_count", 0)
        stars = repo.get("current_stars", 0)
        forks = repo.get("current_forks", 0)
        issues = repo.get("current_open_issues", 0)
        watchers = repo.get("current_watchers", 0)
        score = repo.get("score", 0.0)
        repo_url = f"https://github.com/{repo_name}"
        paper_id = paper.get("paper_id") or repo.get("paper_id", "")
        paper_title = paper.get("title") or repo.get("description") or repo_name
        abs_url = paper.get("abs_url") or (f"https://arxiv.org/abs/{paper_id}" if paper_id else "")
        pdf_url = paper.get("pdf_url") or (f"https://arxiv.org/pdf/{paper_id}.pdf" if paper_id else "")
        categories = ", ".join(paper.get("categories", [])) or "unknown"
        authors = ", ".join(paper.get("authors", [])[:6]) or "unknown"
        summary = paper.get("summary", "")
        summary = escape(summary[:320] + ("…" if len(summary) > 320 else ""))
        pdf_link = f' · <a href="{escape(pdf_url)}">PDF</a>' if pdf_url else ""
        cards.append(
            (
                maintenance_score,
                f"""
                <article class=\"card\" data-maintenance=\"{maintenance_score:.3f}\" data-stars=\"{stars}\" data-score=\"{score:.4f}\"> 
                  <div class=\"card-header\">
                    <div>
                      <div class=\"eyebrow\">arXiv {escape(paper_id)}</div>
                      <h2>{escape(paper_title)}</h2>
                    </div>
                    <div class=\"badges\">
                      <span class=\"badge badge-maintenance\">维护度: {escape(maintenance_label)}</span>
                      <span class=\"badge\">Rank score: {score:.4f}</span>
                      <span class=\"badge\">Tier {escape(str(repo.get('tier', '?')))}</span>
                    </div>
                  </div>

                  <p class=\"summary\">{summary or '暂无摘要'}</p>

                  <div class=\"meta-grid\">
                    <div><span>GitHub</span><strong><a href=\"{escape(repo_url)}\">{escape(repo_name)}</a></strong></div>
                    <div><span>arXiv</span><strong><a href=\"{escape(abs_url)}\">Abstract</a>{pdf_link}</strong></div>
                    <div><span>分类</span><strong>{escape(categories)}</strong></div>
                    <div><span>作者</span><strong>{escape(authors)}</strong></div>
                  </div>

                  <div class=\"stats\">
                    <div class=\"stat\"><span>Stars</span><strong>{stars}</strong></div>
                    <div class=\"stat\"><span>Forks</span><strong>{forks}</strong></div>
                    <div class=\"stat\"><span>Watchers</span><strong>{watchers}</strong></div>
                    <div class=\"stat\"><span>Open issues</span><strong>{issues}</strong></div>
                    <div class=\"stat\"><span>Releases</span><strong>{release_count}</strong></div>
                    <div class=\"stat\"><span>Last push</span><strong>{escape(last_pushed)}</strong></div>
                  </div>
                </article>
                """,
            )
        )

    cards_html = "\n".join(card for _, card in sorted(cards, key=lambda item: item[0], reverse=True))
    repo_count = len(payload.get("high_potential_repos", []))
    paper_count = len(payload.get("new_papers_with_repos", []))
    generated_at = escape(payload.get("generated_at", ""))
    empty_html = '<div class="empty">当前还没有带 GitHub repo 的论文卡片。先继续跑 discover / run-all 即可。</div>'
    return f"""<!DOCTYPE html>
<html lang=\"zh-CN\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>arXiv → GitHub Dashboard</title>
  <style>
    :root {{ color-scheme: dark; }}
    body {{ margin: 0; font-family: Inter, ui-sans-serif, system-ui, -apple-system, sans-serif; background: #0b1020; color: #e8ecf3; }}
    .wrap {{ max-width: 1200px; margin: 0 auto; padding: 32px 20px 80px; }}
    .hero {{ display: flex; justify-content: space-between; gap: 16px; align-items: end; margin-bottom: 24px; flex-wrap: wrap; }}
    h1 {{ margin: 0; font-size: 32px; }}
    .sub {{ color: #95a3b8; margin-top: 8px; }}
    .toolbar {{ display: flex; gap: 12px; flex-wrap: wrap; margin: 18px 0 28px; }}
    .pill {{ background: #151b31; border: 1px solid #29314d; color: #dbe6ff; border-radius: 999px; padding: 10px 14px; }}
    .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 18px; }}
    .card {{ background: linear-gradient(180deg, #121933 0%, #0f152b 100%); border: 1px solid #27304d; border-radius: 18px; padding: 18px; box-shadow: 0 12px 40px rgba(0,0,0,0.25); }}
    .card-header {{ display: flex; justify-content: space-between; gap: 16px; align-items: start; margin-bottom: 14px; }}
    .card h2 {{ margin: 4px 0 0; font-size: 20px; line-height: 1.35; }}
    .eyebrow {{ color: #7aa2ff; font-size: 12px; text-transform: uppercase; letter-spacing: .08em; }}
    .badges {{ display: flex; flex-direction: column; gap: 8px; align-items: end; }}
    .badge {{ background: #1b2547; color: #dbe6ff; border-radius: 999px; padding: 6px 10px; font-size: 12px; white-space: nowrap; }}
    .badge-maintenance {{ background: #173a31; color: #baf5df; }}
    .summary {{ color: #b8c3d9; line-height: 1.6; min-height: 72px; }}
    .meta-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin: 16px 0; }}
    .meta-grid span, .stat span {{ display: block; color: #7f8aa3; font-size: 12px; margin-bottom: 4px; }}
    .meta-grid strong, .stat strong {{ font-size: 14px; line-height: 1.4; }}
    .stats {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }}
    .stat {{ background: #0b1124; border: 1px solid #202946; border-radius: 14px; padding: 12px; }}
    a {{ color: #9bc2ff; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .empty {{ color: #95a3b8; padding: 24px; border: 1px dashed #2c3554; border-radius: 16px; }}
    @media (max-width: 700px) {{ .meta-grid, .stats {{ grid-template-columns: 1fr; }} .badges {{ align-items: start; }} }}
  </style>
</head>
<body>
  <main class=\"wrap\">
    <section class=\"hero\">
      <div>
        <h1>arXiv → GitHub 监控面板</h1>
        <div class=\"sub\">卡片按 GitHub 维护度排序，便于快速进入 paper / repo 追踪。生成时间：{generated_at}</div>
      </div>
      <div class=\"toolbar\">
        <div class=\"pill\">Papers with repo: {paper_count}</div>
        <div class=\"pill\">Tracked repos: {repo_count}</div>
      </div>
    </section>
    <section class=\"cards\">
      {cards_html or empty_html}
    </section>
  </main>
</body>
</html>
"""


def _maintenance_status(repo: dict) -> tuple[float, str]:
    if repo.get("archived"):
        return 0.0, "Archived"
    if repo.get("disabled"):
        return 0.0, "Disabled"
    last_pushed_at = repo.get("last_pushed_at")
    if not last_pushed_at:
        return 0.2, "Unknown"
    try:
        pushed = datetime.fromisoformat(str(last_pushed_at).replace("Z", "+00:00"))
    except ValueError:
        return 0.2, "Unknown"
    now = datetime.now(timezone.utc)
    days = max((now - pushed).total_seconds() / 86400, 0.0)
    if days <= 14:
        return 1.0, "Very active"
    if days <= 45:
        return 0.8, "Active"
    if days <= 120:
        return 0.5, "Cooling"
    return 0.2, "Stale"
