from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from urllib.parse import quote_plus
from urllib.error import HTTPError

from .models import PaperRecord
from .utils import fetch_text

ATOM_NS = {"a": "http://www.w3.org/2005/Atom"}
ARXIV_BASE = "https://export.arxiv.org/api/query"
RSS_TEMPLATE = "https://rss.arxiv.org/rss/{category}"


class ArxivClient:
    def __init__(self, polite_delay_seconds: float = 0.0) -> None:
        self.polite_delay_seconds = polite_delay_seconds

    def fetch_rss_entries(self, category: str, max_entries: int = 20) -> list[dict]:
        xml_text = fetch_text(RSS_TEMPLATE.format(category=category))
        root = ET.fromstring(xml_text)
        items: list[dict] = []
        for item in root.findall("./channel/item")[:max_entries]:
            link = (item.findtext("link") or "").strip()
            title = (item.findtext("title") or "").strip()
            description = (item.findtext("description") or "").strip()
            pub_date = (item.findtext("pubDate") or "").strip()
            paper_id = link.rstrip("/").split("/")[-1]
            items.append(
                {
                    "paper_id": paper_id,
                    "title": title,
                    "summary": description,
                    "published_at": pub_date,
                    "abs_url": link,
                    "source": "rss",
                    "categories": [category],
                }
            )
        if items:
            return items
        try:
            return self.fetch_latest_entries(category, max_results=max_entries)
        except HTTPError:
            return []

    def fetch_latest_entries(self, category: str, max_results: int = 20) -> list[dict]:
        if self.polite_delay_seconds:
            time.sleep(self.polite_delay_seconds)
        xml_text = fetch_text(
            f"{ARXIV_BASE}?search_query=cat:{quote_plus(category)}&sortBy=submittedDate&sortOrder=descending&max_results={int(max_results)}"
        )
        root = ET.fromstring(xml_text)
        items: list[dict] = []
        for entry in root.findall("a:entry", ATOM_NS):
            entry_id = (entry.findtext("a:id", default="", namespaces=ATOM_NS) or "").strip()
            versioned_id = entry_id.split("/abs/")[-1] if "/abs/" in entry_id else entry_id
            items.append(
                {
                    "paper_id": versioned_id,
                    "version": versioned_id[len(versioned_id.split('v')[0]):] or 'v1',
                    "title": " ".join((entry.findtext("a:title", default="", namespaces=ATOM_NS) or "").split()),
                    "summary": " ".join((entry.findtext("a:summary", default="", namespaces=ATOM_NS) or "").split()),
                    "published_at": (entry.findtext("a:published", default="", namespaces=ATOM_NS) or "").strip(),
                    "updated_at": (entry.findtext("a:updated", default="", namespaces=ATOM_NS) or "").strip(),
                    "authors": [
                        (author.findtext("a:name", default="", namespaces=ATOM_NS) or "").strip()
                        for author in entry.findall("a:author", ATOM_NS)
                    ],
                    "abs_url": f"https://arxiv.org/abs/{versioned_id}",
                    "pdf_url": f"https://arxiv.org/pdf/{versioned_id}.pdf",
                    "source": "api-search",
                    "categories": [cat.attrib.get("term", "") for cat in entry.findall("a:category", ATOM_NS) if cat.attrib.get("term")],
                }
            )
        return items

    def fetch_paper_metadata(self, paper_id: str) -> PaperRecord:
        if self.polite_delay_seconds:
            time.sleep(self.polite_delay_seconds)
        xml_text = fetch_text(f"{ARXIV_BASE}?id_list={quote_plus(paper_id)}")
        root = ET.fromstring(xml_text)
        entry = root.find("a:entry", ATOM_NS)
        if entry is None:
            raise ValueError(f"Paper not found for arXiv id: {paper_id}")
        entry_id = (entry.findtext("a:id", default="", namespaces=ATOM_NS) or "").strip()
        versioned_id = entry_id.split("/abs/")[-1] if "/abs/" in entry_id else paper_id
        base_id = versioned_id.split("v")[0]
        version = versioned_id[len(base_id):] or "v1"
        authors = [
            (author.findtext("a:name", default="", namespaces=ATOM_NS) or "").strip()
            for author in entry.findall("a:author", ATOM_NS)
        ]
        categories = [cat.attrib.get("term", "") for cat in entry.findall("a:category", ATOM_NS) if cat.attrib.get("term")]
        title = " ".join((entry.findtext("a:title", default="", namespaces=ATOM_NS) or "").split())
        summary = " ".join((entry.findtext("a:summary", default="", namespaces=ATOM_NS) or "").split())
        abs_url = f"https://arxiv.org/abs/{versioned_id}"
        pdf_url = f"https://arxiv.org/pdf/{versioned_id}.pdf"
        return PaperRecord(
            paper_id=base_id,
            version=version,
            title=title,
            authors=authors,
            summary=summary,
            categories=categories,
            published_at=(entry.findtext("a:published", default="", namespaces=ATOM_NS) or None),
            updated_at=(entry.findtext("a:updated", default="", namespaces=ATOM_NS) or None),
            abs_url=abs_url,
            pdf_url=pdf_url,
            source="api",
        )
