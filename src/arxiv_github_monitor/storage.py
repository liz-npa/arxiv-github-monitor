from __future__ import annotations

from pathlib import Path
import json
from typing import Iterable, TypeVar, Callable

from .models import PaperRecord, RepoRecord, RepoSnapshot

T = TypeVar("T")


def ensure_dirs(root: Path) -> None:
    for relative in [
        "state",
        "output",
        "data/raw",
        "data/processed",
        "data/snapshots",
        "scripts",
        "config",
        "tests/fixtures",
    ]:
        (root / relative).mkdir(parents=True, exist_ok=True)


def _read_jsonl(path: Path, factory: Callable[[dict], T]) -> list[T]:
    if not path.exists():
        return []
    items: list[T] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            items.append(factory(json.loads(line)))
    return items


def _write_jsonl(path: Path, items: Iterable) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for item in items:
            fh.write(json.dumps(item.to_dict(), ensure_ascii=False) + "\n")


def load_papers(root: Path) -> list[PaperRecord]:
    return _read_jsonl(root / "state" / "papers.jsonl", PaperRecord.from_dict)


def save_papers(root: Path, papers: list[PaperRecord]) -> None:
    _write_jsonl(root / "state" / "papers.jsonl", papers)


def load_repos(root: Path) -> list[RepoRecord]:
    return _read_jsonl(root / "state" / "repos.jsonl", RepoRecord.from_dict)


def save_repos(root: Path, repos: list[RepoRecord]) -> None:
    _write_jsonl(root / "state" / "repos.jsonl", repos)


def load_repo_snapshots(root: Path) -> list[RepoSnapshot]:
    return _read_jsonl(root / "state" / "repo_snapshots.jsonl", RepoSnapshot.from_dict)


def save_repo_snapshots(root: Path, snapshots: list[RepoSnapshot]) -> None:
    _write_jsonl(root / "state" / "repo_snapshots.jsonl", snapshots)


def load_checkpoints(root: Path) -> dict:
    path = root / "state" / "checkpoints.json"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def save_checkpoints(root: Path, checkpoints: dict) -> None:
    path = root / "state" / "checkpoints.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(checkpoints, fh, ensure_ascii=False, indent=2)
