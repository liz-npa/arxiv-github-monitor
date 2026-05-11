from arxiv_github_monitor.models import PaperRecord
from arxiv_github_monitor import repo_extractor


def test_extract_repos_prefers_summary(monkeypatch) -> None:
    paper = PaperRecord(
        paper_id="2505.12345",
        version="v1",
        title="Agentic Benchmarks with Code",
        authors=["Alice"],
        summary="Code: https://github.com/example/agentic-bench",
        categories=["cs.LG"],
        published_at=None,
        updated_at=None,
        abs_url="https://arxiv.org/abs/2505.12345v1",
        pdf_url="https://arxiv.org/pdf/2505.12345v1.pdf",
        source="test",
    )
    monkeypatch.setattr(repo_extractor, "fetch_text", lambda url: "")
    result = repo_extractor.extract_repos_for_paper(paper)
    assert result.status == "found"
    assert result.source == "summary"
    assert result.repos == ["example/agentic-bench"]


def test_extract_repos_falls_back_to_html(monkeypatch) -> None:
    paper = PaperRecord(
        paper_id="2505.12345",
        version="v1",
        title="Agentic Benchmarks with Code",
        authors=["Alice"],
        summary="No repo in summary",
        categories=["cs.LG"],
        published_at=None,
        updated_at=None,
        abs_url="https://arxiv.org/abs/2505.12345v1",
        pdf_url="https://arxiv.org/pdf/2505.12345v1.pdf",
        source="test",
    )
    monkeypatch.setattr(
        repo_extractor,
        "fetch_text",
        lambda url: '<a href="https://github.com/example/agentic-bench">repo</a>',
    )
    result = repo_extractor.extract_repos_for_paper(paper)
    assert result.status == "found"
    assert result.repos == ["example/agentic-bench"]
