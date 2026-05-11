from arxiv_github_monitor.utils import extract_github_urls, normalize_github_repo


def test_extract_github_urls_finds_repo_links() -> None:
    text = "Code: https://github.com/org/repo and docs elsewhere"
    assert extract_github_urls(text) == ["https://github.com/org/repo"]


def test_normalize_github_repo_strips_suffixes() -> None:
    assert normalize_github_repo("https://github.com/Org/Repo.git?tab=readme") == "Org/Repo"
    assert normalize_github_repo("https://github.com/Org/Repo.)") == "Org/Repo"
    assert normalize_github_repo("https://example.com/nope") is None
