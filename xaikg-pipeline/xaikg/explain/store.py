"""Persistent explanation log (R8: every explanation surfaced to a user stays traceable after the
service restarts). Append-only JSON Lines file plus an index for lookup by id; the record holds
exactly what /trace needs to replay the chain: decision, grounded factors, active entities, the
query parameters, facts and fact ids, the facts available per factor before the budget, rendered
text, audience, type, model versions, and the fingerprints of the models that generated the service.

A file is used rather than Neo4j so that the knowledge graph stays read-only at explanation time
(C1_PatternReadsOnly) and the audit log can be archived independently of the database.
"""
from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ..config import PATHS
from ..manifest import now_iso

DEFAULT_LOG = PATHS.results / "explanations" / "explanations.jsonl"


@dataclass
class ExplanationRecord:
    id: str
    created_at: str
    explanation_type: str
    category: str
    audience: str
    decision_id: str
    decision_class: str
    decision_label: str
    probability: float
    model: str
    attribution_method: str
    factors: list[dict]
    facts: list[dict]
    fact_ids: list[str]
    text: str
    service_models: dict = field(default_factory=dict)
    # every binding active for the encounter (attributed or not), as bound to $active
    active: list[dict] = field(default_factory=list)
    # candidate facts available per attributed factor before the presentation budget was applied
    available_facts: dict = field(default_factory=dict)
    # parameters bound to the query patterns (so an audit can re-run them)
    query_parameters: dict = field(default_factory=dict)


class ExplanationStore:
    def __init__(self, path: Path = DEFAULT_LOG):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._offsets: dict[str, int] = {}
        self._index()

    def _index(self) -> None:
        if not self.path.exists():
            return
        with self.path.open("rb") as f:
            pos = 0
            for line in f:
                try:
                    rec = json.loads(line)
                    self._offsets[rec["id"]] = pos
                except (json.JSONDecodeError, KeyError):
                    pass
                pos += len(line)

    def append(self, rec: ExplanationRecord) -> None:
        line = json.dumps(asdict(rec), ensure_ascii=False, default=str) + "\n"
        with self._lock, self.path.open("ab") as f:
            self._offsets[rec.id] = f.tell()
            f.write(line.encode("utf-8"))

    def get(self, explanation_id: str) -> ExplanationRecord | None:
        pos = self._offsets.get(explanation_id)
        if pos is None:
            return None
        with self.path.open("rb") as f:
            f.seek(pos)
            data = json.loads(f.readline())
        return ExplanationRecord(**data)

    def __len__(self) -> int:
        return len(self._offsets)

    def ids(self) -> list[str]:
        return list(self._offsets)
