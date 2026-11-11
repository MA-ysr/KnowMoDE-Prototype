"""Decision-binding resolver: turns a decision context (feature values + attributions) into KG
entity keys, following the FeatureBinding elements of the decision-bindings model as exported by T6
into bindings.json. This is the bridge between the black-box model and the knowledge graph.

Binding kinds (metamodel decision::BindingKind):
  ENTITY       feature value selects a fixed entity (entityName), active when `activeWhen` holds
  RISK_FACTOR  same, for utilisation/administrative factors
  LAB_LEVEL    categorical value mapped by valueMap to an entity name
  ICD9_GROUP   ICD-9 code mapped by range table (valueMap) to an entity name; specific codes first
"""
from __future__ import annotations

import ast
import json
from dataclasses import dataclass


@dataclass(frozen=True)
class Binding:
    feature: str
    kind: str
    concept: str
    entity_name: str | None
    value_map: dict | None
    active_when: str | None


@dataclass(frozen=True)
class Grounded:
    feature: str
    value: object
    attribution: float
    concept: str
    entity: str          # human-readable entity name
    key: str             # lower-cased key used in the graph (_key)


class _SafeEval(ast.NodeVisitor):
    """Evaluates the tiny `activeWhen` condition language: comparisons, `in`, and/or/not on `value`."""
    ALLOWED = (ast.Expression, ast.BoolOp, ast.UnaryOp, ast.Compare, ast.Name, ast.Constant, ast.Tuple, ast.List,
               ast.And, ast.Or, ast.Not, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn, ast.Load)

    def generic_visit(self, node):
        if not isinstance(node, self.ALLOWED):
            raise ValueError(f"disallowed construct in activeWhen: {type(node).__name__}")
        super().generic_visit(node)


def _coerce(value):
    if isinstance(value, str):
        try:
            return float(value) if "." in value else int(value)
        except ValueError:
            return value
    return value


def is_active(condition: str | None, value) -> bool:
    if not condition:
        return value not in (None, "", "No", "missing", "?")
    tree = ast.parse(condition, mode="eval")
    _SafeEval().visit(tree)
    v = _coerce(value)
    try:
        return bool(eval(compile(tree, "<activeWhen>", "eval"), {"__builtins__": {}}, {"value": v, "None": None}))
    except TypeError:  # e.g. comparing a string value with a number
        return False


def _missing(value) -> bool:
    return value is None or (isinstance(value, float) and value != value)  # None or NaN


def _icd9_lookup(code, table: dict) -> str | None:
    if _missing(code) or code in ("", "?", "missing"):
        return None
    s = str(code)
    if s.startswith(("V", "E")):
        return None
    try:
        n = float(s)
    except ValueError:
        return None
    # specific codes take precedence over ranges
    for k, name in table.items():
        parts = [p.strip() for p in k.split(",")]
        if any("-" not in p and p and float(p) == float(int(n)) for p in parts):
            return name
    for k, name in table.items():
        for p in (q.strip() for q in k.split(",")):
            if "-" in p:
                lo, hi = p.split("-")
                if float(lo) <= n <= float(hi):
                    return name
            elif p and float(p) == float(int(n)):
                return name
    return None


class BindingResolver:
    def __init__(self, bindings: list[dict]):
        self.bindings = [Binding(b["feature"], b["kind"], b["concept"], b.get("entityName"),
                                 json.loads(b["valueMap"]) if b.get("valueMap") else None, b.get("activeWhen"))
                         for b in bindings]
        self.by_feature = {b.feature: b for b in self.bindings}

    def resolve(self, attributions: list[dict], top_k: int | None = None, positive_only: bool = True) -> list[Grounded]:
        """attributions: [{feature, value, attribution}] sorted by |attribution| desc (as produced by SHAP)."""
        out: list[Grounded] = []
        for a in attributions:
            b = self.by_feature.get(a["feature"])
            if b is None:
                continue
            if positive_only and a["attribution"] <= 0:
                continue
            if _missing(a["value"]) or not is_active(b.active_when, a["value"]):
                continue
            entity = None
            if b.kind in ("ENTITY", "RISK_FACTOR"):
                entity = b.entity_name
            elif b.kind == "LAB_LEVEL":
                entity = (b.value_map or {}).get(str(a["value"]))
            elif b.kind == "ICD9_GROUP":
                entity = _icd9_lookup(a["value"], b.value_map or {})
            if not entity:
                continue
            out.append(Grounded(a["feature"], a["value"], float(a["attribution"]), b.concept, entity, entity.lower().strip()))
            if top_k and len(out) >= top_k:
                break
        return out

    def active(self, features: dict) -> list[Grounded]:
        """Every binding that is active for the decision context, attributed or not: each feature is
        evaluated against its activeWhen condition, valueMap or ICD-9 range table. One entry per KG key,
        in the order of the bindings (the value bound to the $active query parameter)."""
        candidates = [{"feature": b.feature, "value": features.get(b.feature), "attribution": 0.0}
                      for b in self.bindings if b.feature in features]
        out: list[Grounded] = []
        seen: set[str] = set()
        for g in self.resolve(candidates, top_k=None, positive_only=False):
            if g.key not in seen:
                seen.add(g.key)
                out.append(g)
        return out
