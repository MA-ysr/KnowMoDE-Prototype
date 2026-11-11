"""Explanation runtime kernel used by the GENERATED router (T6).

Flow for one request (paper T6: "receive an AI decision context, execute the KGQueryPattern,
render with the audience's template"):
  1. decision context = feature values (+ optional precomputed attributions; otherwise the bundled
     model and SHAP compute them),
  2. decision class = positive class if probability >= its threshold,
  3. factors = decision bindings resolved on the top positive attributions -> KG keys ($factors);
     active = every binding active for the encounter, attributed or not -> KG keys ($active),
  4. for every query pattern of the explanation type: bind the parameters it declares
     ($factors, $active, $outcome, $contrastFactors, $limit = the configuration's retrievalLimit) and run it,
  5. the candidate facts are de-duplicated, counted per attributed factor, and the audience's
     presentation budget is spent on them with the declared allocation (ROUND_ROBIN: one fact per
     attributed factor, in attribution order, before a second one; IN_ORDER: query order); the
     selected facts and the per-factor availability are rendered with the type's template,
  6. the response carries the facts' provenance; the explanation is stored so /trace can replay the
     full chain (facts -> source document + span -> extraction run -> validation policy).
Nothing here is specific to the use case: audiences, types, patterns, templates, budgets and bindings
all come from the generated JSON/J2 files. Two column conventions of the query patterns are used:
`factId*` columns carry fact identifiers (a scalar, or a list when a row aggregates several facts),
and a `factorKey` column ties a row to the attributed factor whose evidence it is.
"""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel, Field

from ..config import PATHS
from ..kg.neo4j_client import query
from ..manifest import now_iso
from .bindings import BindingResolver, Grounded
from .store import ExplanationRecord, ExplanationStore

SERVICE_DIR = PATHS.generated / "service"


class DecisionInput(BaseModel):
    """AI decision context. `features` are the raw feature values of one encounter; `attributions`
    may be supplied (feature -> SHAP value) or are computed by the bundled model."""
    decision_id: str | None = None
    features: dict[str, Any]
    attributions: dict[str, float] | None = None
    probability: float | None = Field(default=None, ge=0, le=1)
    contrast_features: dict[str, Any] | None = None
    top_k: int = Field(default=5, ge=1, le=20)


@dataclass
class Explanation:
    id: str
    explanation_type: str
    audience: str
    decision_class: str
    probability: float
    factors: list[Grounded]
    facts: list[dict]
    text: str
    fact_ids: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=now_iso)


def _plain(text: str) -> str:
    """Plain-language filter for LOW audiences: drops codes/parentheticals, lower-cases jargon lightly."""
    s = re.sub(r"\((?:ICD|grade|conf\.?|confidence)[^)]*\)", "", str(text))
    s = re.sub(r"\s{2,}", " ", s).strip()
    return s[0].upper() + s[1:] if s else s


def fact_ids_of(row: dict) -> list[str]:
    """Fact identifiers carried by a result row: every column whose name starts with 'factId'
    (a scalar, or a list when the row aggregates several facts)."""
    ids: list[str] = []
    for k, v in row.items():
        if not k.startswith("factId") or v is None:
            continue
        for x in (v if isinstance(v, (list, tuple)) else [v]):
            if x:
                ids.append(str(x))
    return ids


def dedupe_rows(rows: list[dict]) -> list[dict]:
    """A fact is shown once: rows carrying exactly the same fact identifiers are kept only the first time."""
    seen: set[frozenset] = set()
    out = []
    for r in rows:
        ids = frozenset(fact_ids_of(r))
        if ids and ids in seen:
            continue
        if ids:
            seen.add(ids)
        out.append(r)
    return out


def allocate(rows: list[dict], factor_keys: list[str], max_facts: int,
             allocation: str = "ROUND_ROBIN") -> tuple[list[dict], dict[str, int]]:
    """Spends a presentation budget of `max_facts` on the candidate rows of one explanation.

    A row belongs to an attributed factor when its `factorKey` column holds that factor's KG key; the
    other rows are grouped by the query pattern that returned them (`_pattern`). Returns the selected
    rows and the number of candidate rows available per factor key before the budget was applied.
    ROUND_ROBIN takes one row from every group in turn (factors in attribution order, then patterns
    in the order they were run) and presents the selection grouped the same way; IN_ORDER keeps the
    first `max_facts` rows in query order."""
    factor_keys = list(dict.fromkeys(factor_keys))
    factor_set = set(factor_keys)
    order: list[tuple[str, str]] = [("factor", k) for k in factor_keys]
    groups: dict[tuple[str, str], list[int]] = {g: [] for g in order}
    for i, r in enumerate(rows):
        fk = r.get("factorKey")
        g = ("factor", fk) if fk in factor_set else ("pattern", str(r.get("_pattern")))
        if g not in groups:
            groups[g] = []
            order.append(g)
        groups[g].append(i)
    available = {k: len(groups[("factor", k)]) for k in factor_keys}
    if allocation == "IN_ORDER":
        return rows[:max_facts], available
    chosen: list[tuple[int, int]] = []          # (group position, row index)
    depth = 0
    while len(chosen) < max_facts:
        progressed = False
        for pos, g in enumerate(order):
            if depth < len(groups[g]) and len(chosen) < max_facts:
                chosen.append((pos, groups[g][depth]))
                progressed = True
        if not progressed:
            break
        depth += 1
    chosen.sort()
    return [rows[i] for _, i in chosen], available


def truncate_words(text: str, max_words: int) -> str:
    """Cuts a rendered text to `max_words` words while keeping its line structure (list items stay on
    their own lines); the cut is marked with ' ...'."""
    if max_words <= 0 or len(text.split()) <= max_words:
        return text
    out, left = [], max_words
    for line in text.splitlines():
        words = line.split()
        if len(words) <= left:
            out.append(line)
            left -= len(words)
            continue
        prefix = line[: len(line) - len(line.lstrip())]
        out.append(prefix + " ".join(words[:left]) + " ...")
        break
    return "\n".join(out)


def _source_title(doc: str) -> str:
    """'openfda/metformin.txt' -> 'FDA label for metformin'; 'medlineplus/a1c.txt' -> 'MedlinePlus: A1c'."""
    if not doc:
        return "source unavailable"
    coll, _, name = str(doc).partition("/")
    base = name.rsplit(".", 1)[0].replace("-", " ")
    return {"openfda": f"FDA prescribing information for {base}", "medlineplus": f"MedlinePlus health topic '{base}'",
            "pubmed": f"PubMed article {base}", "papers": f"study {base}"}.get(coll, doc)


class ExplanationRuntime:
    def __init__(self, service_dir: Path = SERVICE_DIR, store_path: Path | None = None):
        self.dir = service_dir
        self.contract = json.loads((service_dir / "contract.json").read_text(encoding="utf-8"))
        self.patterns = {p["name"]: p for p in json.loads((service_dir / "patterns.json").read_text(encoding="utf-8"))["patterns"]}
        self.bindings = json.loads((service_dir / "bindings.json").read_text(encoding="utf-8"))
        self.coverage = json.loads((service_dir / "coverage.json").read_text(encoding="utf-8"))
        self.audiences = {a["role"]: a for a in self.contract["audiences"]}
        self.types = {t["name"]: t for t in self.contract["explanationTypes"]}
        self.resolver = BindingResolver(self.bindings["featureBindings"])
        self.env = Environment(loader=FileSystemLoader(str(service_dir / "templates")), autoescape=select_autoescape([]),
                               trim_blocks=True, lstrip_blocks=True)
        self.env.filters["plain"] = _plain
        self.env.filters["source_title"] = _source_title
        self._model = None
        self.store = ExplanationStore(store_path) if store_path else ExplanationStore()
        manifest = service_dir / "generation-manifest.json"
        self.service_models = json.loads(manifest.read_text(encoding="utf-8")).get("sourceModels", {}) if manifest.exists() else {}

    @classmethod
    def from_generated(cls) -> "ExplanationRuntime":
        return cls(SERVICE_DIR)

    # ------------------------------------------------------------------ model access
    def _attributor(self):
        if self._model is None:
            from ..ml.readmission import Attributor, load_trained
            self._model = Attributor(load_trained())
        return self._model

    def decide(self, d: DecisionInput) -> tuple[dict, list[dict], float]:
        if d.attributions is not None and d.probability is not None:
            attributions = sorted(({"feature": f, "value": d.features.get(f), "attribution": v} for f, v in d.attributions.items()),
                                  key=lambda a: -abs(a["attribution"]))
            probability = d.probability
        else:
            ex = self._attributor().explain(d.features)
            attributions, probability = ex["attributions"], ex["probability"]
        classes = self.bindings["decisionClasses"]
        positive = next((c for c in classes if c["positive"] and probability >= c["threshold"]), None)
        decision = positive or next(c for c in classes if not c["positive"])
        return decision, attributions, probability

    # ------------------------------------------------------------------ explanation
    def explain(self, type_name: str, audience_role: str, d: DecisionInput) -> dict:
        et = self.types[type_name]
        aud = self.audiences[audience_role]
        decision, attributions, probability = self.decide(d)
        if type_name not in decision["explanationTypes"]:
            # the contract (R5) does not bind this type to the predicted class: say so, never improvise
            return {"explanation_id": None, "decision_class": decision["name"], "probability": round(probability, 4),
                    "message": f"Explanation type {type_name} is not part of the contract for decision class {decision['name']}",
                    "contract": decision["explanationTypes"]}
        budget = aud["budget"]
        factors = self.resolver.resolve(attributions, top_k=d.top_k)
        active = self.resolver.active(d.features)
        contrast_keys: list[str] = []
        if d.contrast_features:
            contrast = self.resolver.resolve(
                [{"feature": f, "value": v, "attribution": 1.0} for f, v in d.contrast_features.items()], top_k=None)
            contrast_keys = [g.key for g in contrast]
        params = {"factors": list(dict.fromkeys(g.key for g in factors)), "active": [g.key for g in active],
                  "outcome": (decision.get("predictedOutcome") or "").lower(),
                  "limit": int(self.contract.get("retrievalLimit") or budget["maxFacts"]),
                  "contrastFactors": contrast_keys, "factIds": []}
        candidates: list[dict] = []
        for pname in et["queryPatterns"]:
            p = self.patterns[pname]
            bound = {k: params[k] for k in p["parameters"] if k in params}
            for row in query(p["cypher"], **bound):
                row["_pattern"] = pname
                candidates.append(row)
        candidates = dedupe_rows(candidates)
        facts, available = allocate(candidates, params["factors"], int(budget["maxFacts"]), budget.get("allocation", "ROUND_ROBIN"))
        available_facts = {g.entity: available.get(g.key, 0) for g in factors}
        decision_view = {"id": d.decision_id or str(uuid.uuid4()), "label": decision["label"], "class": decision["name"],
                         "positive": bool(decision.get("positive", False)),
                         "probability": probability, "model": self.bindings["aiModel"]["name"] + " " + self.bindings["aiModel"]["version"],
                         "attributionMethod": self.bindings["aiModel"]["attributionMethod"],
                         "factors": [{"feature": g.feature, "value": g.value, "attribution": g.attribution, "entity": g.entity,
                                      "concept": g.concept, "key": g.key} for g in factors],
                         "active": [{"feature": g.feature, "value": g.value, "entity": g.entity, "concept": g.concept, "key": g.key}
                                    for g in active]}
        text = self.env.get_template(et["template"] + ".j2").render(
            decision=decision_view, facts=facts, available_facts=available_facts,
            audience={"role": aud["role"], "technicalLevel": aud["technicalLevel"], "budget": budget})
        if budget.get("maxWords"):
            text = truncate_words(text, int(budget["maxWords"]))
        fact_ids = sorted({x for f in facts for x in fact_ids_of(f)})
        exp = Explanation(str(uuid.uuid4()), type_name, audience_role, decision["name"], probability, factors, facts, text, fact_ids)
        query_parameters = {k: params[k] for k in ("factors", "active", "outcome", "contrastFactors", "limit")}
        self.store.append(ExplanationRecord(
            id=exp.id, created_at=exp.created_at, explanation_type=type_name, category=et["category"], audience=audience_role,
            decision_id=decision_view["id"], decision_class=decision["name"], decision_label=decision["label"],
            probability=round(probability, 6), model=decision_view["model"], attribution_method=decision_view["attributionMethod"],
            factors=decision_view["factors"], facts=facts, fact_ids=fact_ids, text=text, service_models=self.service_models,
            active=decision_view["active"], available_facts=available_facts, query_parameters=query_parameters))
        return {"explanation_id": exp.id, "explanation_type": type_name, "category": et["category"], "audience": audience_role,
                "decision_class": decision["name"], "decision_label": decision["label"], "probability": round(probability, 4),
                "grounded_factors": decision_view["factors"], "active_entities": decision_view["active"],
                "available_facts": available_facts, "ungrounded_top_features": [
                    a["feature"] for a in attributions[: d.top_k] if a["feature"] not in {g.feature for g in factors}],
                "text": text, "facts": facts, "fact_ids": fact_ids,
                "provenance": {"facts_with_source": sum(1 for f in facts if any(k.startswith("source") or k == "sourceDocument" for k, v in f.items() if v)),
                               "patterns": et["queryPatterns"], "trace_endpoint": f"/trace/{exp.id}" if self.contract.get("tracePattern") else None},
                "budget": budget}

    # ------------------------------------------------------------------ traceability (R8)
    def trace(self, explanation_id: str) -> dict | None:
        exp = self.store.get(explanation_id)
        if exp is None:
            return None
        chain = []
        if exp.fact_ids and self.contract.get("tracePattern"):
            p = self.patterns[self.contract["tracePattern"]]
            chain = query(p["cypher"], factIds=exp.fact_ids)
        registry_path = PATHS.prompts / "prompt-registry.json"
        registry = json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.exists() else {}
        prompts = {p["promptId"]: p for p in registry.get("prompts", [])}
        for c in chain:
            run = c.get("extractionRun") or {}
            c["prompt"] = prompts.get(run.get("promptId"))
        return {"explanation_id": exp.id, "explanation_type": exp.explanation_type, "audience": exp.audience,
                "decision_id": exp.decision_id, "decision_class": exp.decision_class, "probability": round(exp.probability, 4),
                "created_at": exp.created_at, "model": exp.model, "attribution_method": exp.attribution_method,
                "factors": exp.factors, "fact_ids": exp.fact_ids, "facts_traced": len(chain),
                "complete": bool(exp.fact_ids) and len(chain) >= len(exp.fact_ids) and all(c.get("document") and c.get("extractionRun") for c in chain),
                "chain": chain, "promptRegistryModels": registry.get("sourceModels"), "serviceModels": exp.service_models,
                "text": exp.text}

    def contract_summary(self) -> dict:
        return {"name": self.contract["name"], "targetSchema": self.contract["targetSchema"],
                "audiences": self.contract["audiences"], "explanationTypes": self.contract["explanationTypes"],
                "decisionClasses": self.bindings["decisionClasses"], "coverage": self.coverage}

    def health(self) -> dict:
        try:
            n = query("MATCH (n) RETURN count(n) AS n")[0]["n"]
            return {"status": "ok", "nodes": n, "explanations_logged": len(self.store), "log": str(self.store.path)}
        except Exception as e:  # database down: report, do not crash the service
            return {"status": "degraded", "error": type(e).__name__}
