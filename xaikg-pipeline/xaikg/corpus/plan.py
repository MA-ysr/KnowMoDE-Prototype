"""The corpus plan: which documents to fetch, derived from the use-case models.

Drugs = entityName of every ENTITY feature binding whose concept is Drug; conditions = values of
the ICD9_GROUP valueMaps; labs = LAB_LEVEL valueMap values. Read with plain XML parsing (these are
data values of the M1 model, not logic). Search terms with no model counterpart come from
datasets/corpus/sources.json.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from lxml import etree

from ..config import PATHS


@dataclass
class CorpusPlan:
    drugs: list[str]
    conditions: list[str]
    labs: list[str]
    seeds: dict = field(default_factory=dict)

    def medlineplus_terms(self) -> list[str]:
        terms = list(self.seeds["medlineplus"]["terms"])
        for c in self.conditions:
            if c not in terms:
                terms.append(c)
        return terms


def _bindings_root() -> etree._Element:
    return etree.parse(str(PATHS.models / "decision-bindings.xmi")).getroot()


def build_plan() -> CorpusPlan:
    root = _bindings_root()
    drugs, conditions, labs = [], [], []
    for b in root.iter("featureBindings"):
        kind = b.get("kind", "ENTITY")
        concept = (b.get("concept") or "").split("#")[-1]
        if kind == "ENTITY" and concept == "Drug" and b.get("entityName"):
            if b.get("entityName") not in drugs:
                drugs.append(b.get("entityName"))
        elif kind in ("ICD9_GROUP", "LAB_LEVEL") and b.get("valueMap"):
            for v in json.loads(b.get("valueMap")).values():
                if v and v not in (conditions if kind == "ICD9_GROUP" else labs):
                    (conditions if kind == "ICD9_GROUP" else labs).append(v)
    seeds = json.loads((PATHS.corpus / "sources.json").read_text(encoding="utf-8"))
    return CorpusPlan(drugs=drugs, conditions=conditions, labs=labs, seeds=seeds)
