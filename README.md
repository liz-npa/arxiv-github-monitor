# arXiv GitHub Monitor

This project tracks newly published arXiv papers, extracts linked GitHub repositories, and monitors those repositories for early signals of practical traction.

## Layout
- `docs/nvp-engineering-spec.md` — NVP engineering design
- `src/arxiv_github_monitor/` — implementation
- `tests/` — unit/integration-style tests with fakes
- `scripts/` — convenience entrypoints
- `state/` — local JSONL stores generated at runtime
- `output/` — generated markdown/json reports

## Commands

```bash
cd /Users/lizabethli/Documents/Projects/arxiv-github-monitor
pytest
PYTHONPATH=src python3 -m arxiv_github_monitor.cli run-all
PYTHONPATH=src python3 -m arxiv_github_monitor.cli report
make smoke
```

## Optional auth

For higher GitHub API limits, set:

```bash
export GITHUB_TOKEN=your_token_here
```

## What the current version does
- Pulls recent papers from configured arXiv RSS categories.
- Enriches paper metadata via the arXiv API.
- Extracts GitHub repos from paper summary or abstract page HTML.
- Polls GitHub repo metadata.
- Writes local state and daily reports.
