.PHONY: test run report smoke

PYTHON := python3.11

test:
	PYTHONPATH=src $(PYTHON) -m pytest

run:
	PYTHONPATH=src $(PYTHON) -m arxiv_github_monitor.cli run-all

report:
	PYTHONPATH=src $(PYTHON) -m arxiv_github_monitor.cli report

smoke:
	PYTHONPATH=src $(PYTHON) -c "from arxiv_github_monitor.github_client import GitHubClient; repo, snap = GitHubClient().fetch_repo_metadata('octocat/Hello-World', paper_id='smoke-test'); print(repo.repo, repo.current_stars, repo.default_branch, bool(snap.readme_hash))"
