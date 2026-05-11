.PHONY: test run report smoke

test:
	PYTHONPATH=src pytest

run:
	PYTHONPATH=src python3 -m arxiv_github_monitor.cli run-all

report:
	PYTHONPATH=src python3 -m arxiv_github_monitor.cli report

smoke:
	PYTHONPATH=src python3 -c "from arxiv_github_monitor.github_client import GitHubClient; repo, snap = GitHubClient().fetch_repo_metadata('octocat/Hello-World', paper_id='smoke-test'); print(repo.repo, repo.current_stars, repo.default_branch, bool(snap.readme_hash))"
