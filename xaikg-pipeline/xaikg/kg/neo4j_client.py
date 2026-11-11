"""Thin Neo4j helper (official driver). Credentials from .env; never printed."""
from __future__ import annotations

import re
import time
from pathlib import Path

from neo4j import GraphDatabase

from ..config import env, require_env

_COMMENT = re.compile(r"^\s*//.*$", re.MULTILINE)


def driver():
    return GraphDatabase.driver(env("NEO4J_URI", "bolt://127.0.0.1:7687"),
                                auth=(env("NEO4J_USER", "neo4j"), require_env("NEO4J_PASSWORD")))


def split_statements(script: str) -> list[str]:
    """Splits a generated Cypher script on ';' at end of line, ignoring comments. Generated scripts
    never contain ';' inside string literals at end of line (literals are single-line)."""
    body = _COMMENT.sub("", script)
    stmts = [s.strip() for s in re.split(r";\s*\n", body + "\n")]
    return [s for s in stmts if s]


def apply_cypher_file(path: Path, database: str | None = None) -> dict:
    stmts = split_statements(path.read_text(encoding="utf-8"))
    t0 = time.perf_counter()
    counters = {"nodes_created": 0, "relationships_created": 0, "properties_set": 0, "constraints_added": 0, "indexes_added": 0}
    with driver() as d:
        with d.session(database=database or env("NEO4J_DATABASE", "neo4j")) as s:
            for stmt in stmts:
                summary = s.run(stmt).consume()
                c = summary.counters
                counters["nodes_created"] += c.nodes_created
                counters["relationships_created"] += c.relationships_created
                counters["properties_set"] += c.properties_set
                counters["constraints_added"] += c.constraints_added
                counters["indexes_added"] += c.indexes_added
    return {"file": str(path), "statements": len(stmts), "seconds": round(time.perf_counter() - t0, 1), **counters}


def query(cypher: str, **params) -> list[dict]:
    with driver() as d:
        with d.session(database=env("NEO4J_DATABASE", "neo4j")) as s:
            return [r.data() for r in s.run(cypher, **params)]


def graph_stats() -> dict:
    labels = query("MATCH (n) RETURN labels(n)[0] AS label, count(*) AS n ORDER BY label")
    rels = query("MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS n ORDER BY type")
    return {"nodes": {r["label"]: r["n"] for r in labels}, "relationships": {r["type"]: r["n"] for r in rels}}
