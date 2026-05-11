from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
from typing import Any


@dataclass(slots=True)
class AppConfig:
    root: Path
    categories: list[str]
    max_feed_entries_per_category: int
    max_new_papers_per_run: int
    paper_topic_keywords: list[str]
    arxiv_polite_delay_seconds: int
    github_tier_a_hours: int
    github_tier_b_hours: int
    github_tier_c_hours: int


    @property
    def state_dir(self) -> Path:
        return self.root / "state"

    @property
    def output_dir(self) -> Path:
        return self.root / "output"


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def load_config(root: str | Path) -> AppConfig:
    root_path = Path(root).expanduser().resolve()
    categories_doc = _load_json(root_path / "config" / "categories.json")
    settings_doc = _load_json(root_path / "config" / "settings.json")
    return AppConfig(
        root=root_path,
        categories=list(categories_doc["categories"]),
        max_feed_entries_per_category=int(settings_doc["max_feed_entries_per_category"]),
        max_new_papers_per_run=int(settings_doc["max_new_papers_per_run"]),
        paper_topic_keywords=list(settings_doc["paper_topic_keywords"]),
        arxiv_polite_delay_seconds=int(settings_doc.get("arxiv_polite_delay_seconds", 3)),
        github_tier_a_hours=int(settings_doc["github_tier_a_hours"]),
        github_tier_b_hours=int(settings_doc["github_tier_b_hours"]),
        github_tier_c_hours=int(settings_doc["github_tier_c_hours"]),
    )
