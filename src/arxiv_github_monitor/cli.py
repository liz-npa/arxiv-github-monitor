from __future__ import annotations

import argparse
from pathlib import Path

from .pipeline import Pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="arXiv → GitHub monitor")
    parser.add_argument("command", choices=["discover", "poll", "report", "run-all"])
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--pdf-fallback", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    pipeline = Pipeline(args.root)
    if args.command == "discover":
        papers = pipeline.discover_new_papers()
        pipeline.extract_repos(papers, include_pdf_fallback=args.pdf_fallback)
        print(f"discovered={len(papers)}")
        return 0
    if args.command == "poll":
        repos, snapshots = pipeline.poll_existing_repos()
        print(f"repos={len(repos)} snapshots_added={len(snapshots)}")
        return 0
    if args.command == "report":
        payload = pipeline.generate_report()
        print(f"report_generated_at={payload['generated_at']}")
        return 0
    if args.command == "run-all":
        papers = pipeline.discover_new_papers()
        papers = pipeline.extract_repos(papers, include_pdf_fallback=args.pdf_fallback)
        papers_with_repos = [paper for paper in papers if paper.repo_candidates]
        pipeline.poll_repos(papers_with_repos)
        payload = pipeline.generate_report()
        print(f"run_all_completed generated_at={payload['generated_at']} new_papers={len(papers)} repos={len(papers_with_repos)}")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
