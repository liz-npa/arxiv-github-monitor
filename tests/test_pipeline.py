from pathlib import Path

from arxiv_github_monitor.models import PaperRecord, RepoRecord, RepoSnapshot, to_iso, utcnow
from arxiv_github_monitor.pipeline import Pipeline


class FakeArxivClient:
    def fetch_rss_entries(self, category: str, max_entries: int = 20):
        return [
            {
                "paper_id": "2505.12345v1",
                "title": "Agentic Benchmarks with Code",
                "summary": "Paper summary",
                "published_at": "Mon, 11 May 2026 00:00:00 GMT",
                "abs_url": "https://arxiv.org/abs/2505.12345v1",
                "source": "rss",
                "categories": [category],
            }
        ]

    def fetch_paper_metadata(self, paper_id: str) -> PaperRecord:
        return PaperRecord(
            paper_id="2505.12345",
            version="v1",
            title="Agentic Benchmarks with Code",
            authors=["Alice", "Bob"],
            summary="Code at https://github.com/example/agentic-bench",
            categories=["cs.LG", "cs.AI"],
            published_at="2026-05-11T00:00:00Z",
            updated_at="2026-05-11T01:00:00Z",
            abs_url="https://arxiv.org/abs/2505.12345v1",
            pdf_url="https://arxiv.org/pdf/2505.12345v1.pdf",
            source="api",
        )


class FakeGitHubClient:
    def fetch_repo_metadata(self, repo: str, paper_id: str, first_seen_at: str | None = None):
        record = RepoRecord(
            repo=repo,
            paper_id=paper_id,
            first_seen_at=first_seen_at or to_iso(utcnow()) or "",
            current_stars=123,
            current_forks=12,
            current_open_issues=3,
            current_watchers=20,
            language="Python",
            license="MIT",
            archived=False,
            disabled=False,
            default_branch="main",
            last_pushed_at="2026-05-11T01:30:00Z",
            description="Example repo",
        )
        snapshot = RepoSnapshot(
            repo=repo,
            captured_at=to_iso(utcnow()) or "",
            stars=123,
            forks=12,
            open_issues=3,
            watchers=20,
            last_pushed_at="2026-05-11T01:30:00Z",
            release_count=1,
            readme_hash="abc123",
        )
        return record, snapshot


def write_config(root: Path) -> None:
    (root / "config").mkdir(parents=True, exist_ok=True)
    (root / "config" / "categories.json").write_text('{"categories": ["cs.LG"]}\n', encoding="utf-8")
    (root / "config" / "settings.json").write_text(
        '{"max_feed_entries_per_category": 10, "max_new_papers_per_run": 10, '
        '"paper_topic_keywords": ["agent", "benchmark", "code"], '
        '"github_tier_a_hours": 6, "github_tier_b_hours": 24, "github_tier_c_hours": 168}\n',
        encoding="utf-8",
    )


def test_pipeline_run_all_steps(tmp_path, monkeypatch) -> None:
    write_config(tmp_path)
    pipeline = Pipeline(tmp_path, arxiv_client=FakeArxivClient(), github_client=FakeGitHubClient())
    papers = pipeline.discover_new_papers()
    monkeypatch.setattr(
        "arxiv_github_monitor.repo_extractor.fetch_text",
        lambda url: '<a href="https://github.com/example/agentic-bench">repo</a>',
    )
    papers = pipeline.extract_repos(papers)
    repos, snapshots = pipeline.poll_repos(papers)
    report = pipeline.generate_report()

    assert len(papers) == 1
    assert papers[0].repo_candidates == ["example/agentic-bench"]
    assert len(repos) == 1
    assert len(snapshots) == 1
    assert report["high_potential_repos"][0]["repo"] == "example/agentic-bench"
    assert (tmp_path / "output" / "daily-report.md").exists()
    assert (tmp_path / "state" / "papers.jsonl").exists()
