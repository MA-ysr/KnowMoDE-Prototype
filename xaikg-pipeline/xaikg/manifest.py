"""Provenance manifests for every input file (R7 starts at acquisition time).

One JSON manifest per dataset folder: for each file, the source URI, licence, retrieval time and
SHA-256. Manifests are committed; the data files are not. The SourceDocument nodes created by T5
carry the same fields, so a fact in the graph can be traced to a byte-identical input.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class Manifest:
    """A manifest is a dict keyed by relative file path (relative to the dataset folder)."""

    def __init__(self, path: Path, dataset_dir: Path):
        self.path = path
        self.dataset_dir = dataset_dir
        self.entries: dict[str, dict] = {}
        # searches already run against a source (query -> parameters and result ids), so that a
        # re-run reuses their pinned results instead of a search engine's current ranking
        self.searches: dict[str, dict] = {}
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            self.entries = data.get("files", {})
            self.searches = data.get("searches", {})

    def has(self, rel: str) -> bool:
        entry = self.entries.get(rel)
        if not entry:
            return False
        f = self.dataset_dir / rel
        return f.exists() and sha256_file(f) == entry["sha256"]

    def record(self, rel: str, *, uri: str, licence: str, collection: str, title: str | None = None, **extra) -> dict:
        f = self.dataset_dir / rel
        entry = {"uri": uri, "licence": licence, "collection": collection, "title": title,
                 "retrievedAt": now_iso(), "sha256": sha256_file(f), "bytes": f.stat().st_size, **extra}
        self.entries[rel] = entry
        return entry

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"dataset": self.dataset_dir.name, "updatedAt": now_iso(), "fileCount": len(self.entries),
                   "files": dict(sorted(self.entries.items()))}
        if self.searches:
            payload["searches"] = dict(sorted(self.searches.items()))
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def document_ids(self) -> list[str]:
        return sorted(self.entries)

    def collections_of(self, rel: str) -> set[str]:
        """Collections a file belongs to: its `collection` (where it was first retrieved) plus any further
        collection whose search also returned it (`alsoIn`)."""
        e = self.entries.get(rel, {})
        return {c for c in [e.get("collection"), *e.get("alsoIn", [])] if c}


def load_manifest(manifests_dir: Path, name: str, dataset_dir: Path) -> Manifest:
    return Manifest(manifests_dir / f"{name}.manifest.json", dataset_dir)
