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


def test_extract_repos_pdf_fallback_prefers_own_code_link(monkeypatch) -> None:
    paper = PaperRecord(
        paper_id="2505.99999",
        version="v1",
        title="MedExAgent",
        authors=["Alice"],
        summary="No repo in summary",
        categories=["cs.LG"],
        published_at=None,
        updated_at=None,
        abs_url="https://arxiv.org/abs/2505.99999v1",
        pdf_url="https://arxiv.org/pdf/2505.99999v1.pdf",
        source="test",
    )
    monkeypatch.setattr(repo_extractor, "fetch_text", lambda url: "")
    monkeypatch.setattr(
        repo_extractor,
        "_extract_pdf_text",
        lambda url: "Code: https://github.com/example/medexagent\n"
        "We compare against YOLOv5 [17]. URL https://github.com/ultralytics/yolov5\n"
        "References\n[17] Glenn Jocher. URL https://github.com/ultralytics/yolov5",
    )
    result = repo_extractor.extract_repos_for_paper(paper, include_pdf_fallback=True)
    assert result.status == "found"
    assert result.source == "pdf_fallback"
    assert result.repos == ["example/medexagent"]


def test_extract_repos_pdf_fallback_ignores_reference_only_links(monkeypatch) -> None:
    paper = PaperRecord(
        paper_id="2505.88888",
        version="v1",
        title="XiYOLO",
        authors=["Alice"],
        summary="No repo in summary",
        categories=["cs.LG"],
        published_at=None,
        updated_at=None,
        abs_url="https://arxiv.org/abs/2505.88888v1",
        pdf_url="https://arxiv.org/pdf/2505.88888v1.pdf",
        source="test",
    )
    monkeypatch.setattr(repo_extractor, "fetch_text", lambda url: "")
    monkeypatch.setattr(
        repo_extractor,
        "_extract_pdf_text",
        lambda url: "We compare against YOLOv5 and YOLOv8 baselines.\n"
        "[17] Glenn Jocher. YOLOv5 by Ultralytics. URL https://github.com/ultralytics/yolov5\n"
        "[18] Glenn Jocher. YOLO by Ultralytics. URL https://github.com/ultralytics/ultralytics",
    )
    result = repo_extractor.extract_repos_for_paper(paper, include_pdf_fallback=True)
    assert result.status == "not_found"
    assert result.repos == []
