"""E4 (traceability), E5 (coverage) and E6 (grounding quality) on a sample of test encounters.

For each sampled encounter the runtime produces every explanation its decision class is entitled to
(the contract), for every audience of each type. We then measure:
  E4  fraction of explanations whose every fact id traces to a complete chain
      (fact -> source document + span -> extraction run -> validation policy); chain lengths
  E5  the generated coverage matrix (audience x type) and the number of endpoints
  E6  grounding: share of top-k attributed, active features resolved to a KG entity; share of those
      with at least one validated evidence path; facts per audience vs presentation budget
Needs the loaded graph (Neo4j) and the trained model.
"""
from __future__ import annotations

import json
import random

from ..config import PATHS
from ..explain.runtime import DecisionInput, ExplanationRuntime
from ..manifest import now_iso
from ..kg.neo4j_client import graph_stats, query
from ..ml.readmission import load_test_set


def run(sample: int = 200, seed: int = 11, top_k: int = 5) -> dict:
    rt = ExplanationRuntime.from_generated()
    test = load_test_set()
    rows = test.sample(n=min(sample, len(test)), random_state=seed)
    classes = {c["name"]: c for c in rt.bindings["decisionClasses"]}
    stats = {"encounters": 0, "explanations": 0, "withFacts": 0, "traced": 0, "complete": 0, "chainLengths": [],
             "topFeatures": 0, "activeBound": 0, "withEvidence": 0, "budgetViolations": 0,
             "factsPerAudience": {}, "byClass": {}, "examples": {}}
    keys_with_evidence: dict[str, bool] = {}
    for _, r in rows.iterrows():
        features = {k: (None if (isinstance(v, float) and v != v) else v) for k, v in r.to_dict().items() if k not in ("y_true", "p_readmit")}
        decision, attributions, prob = rt.decide(DecisionInput(features=features))
        stats["encounters"] += 1
        stats["byClass"][decision["name"]] = stats["byClass"].get(decision["name"], 0) + 1
        # E6 grounding of the top-k attributed features
        top = [a for a in attributions[:top_k] if a["attribution"] > 0]
        stats["topFeatures"] += len(top)
        grounded = rt.resolver.resolve(top, top_k=None)
        stats["activeBound"] += len(grounded)
        for g in grounded:
            if g.key not in keys_with_evidence:
                hit = query("MATCH (f {_key: $k})-[r]->() WHERE type(r) <> 'EXTRACTED_FROM' AND type(r) <> 'PRODUCED_BY' RETURN count(r) AS n", k=g.key)
                keys_with_evidence[g.key] = hit[0]["n"] > 0 if hit else False
            if keys_with_evidence[g.key]:
                stats["withEvidence"] += 1
        for type_name in decision["explanationTypes"]:
            et = rt.types[type_name]
            for role in et["audiences"]:
                resp = rt.explain(type_name, role, DecisionInput(features=features, top_k=top_k))
                stats["explanations"] += 1
                budget = rt.audiences[role]["budget"]
                n_facts = len(resp.get("facts", []))
                stats["factsPerAudience"].setdefault(role, []).append(n_facts)
                if n_facts > budget["maxFacts"] or (budget["maxWords"] and len(resp["text"].split()) > budget["maxWords"] + 1):
                    stats["budgetViolations"] += 1
                if n_facts:
                    stats["withFacts"] += 1
                    tr = rt.trace(resp["explanation_id"])
                    if tr is not None:
                        stats["traced"] += 1
                        stats["chainLengths"].append(tr["facts_traced"])
                        if tr["complete"]:
                            stats["complete"] += 1
                        # examples: the first high-risk encounter whose explanations of every type have facts
                        if tr["complete"] and decision["positive"] and not stats["examples"]:
                            stats.setdefault("candidate", {})[(type_name, role)] = {
                                "type": type_name, "audience": role, "decision_class": decision["name"],
                                "explanation_id": resp["explanation_id"], "text": resp["text"]}
        cand = stats.pop("candidate", {})
        if not stats["examples"] and decision["positive"] and \
                {t for t, _ in cand} >= set(decision["explanationTypes"]) and \
                all((t, a) in cand for t in decision["explanationTypes"] for a in rt.types[t]["audiences"]):
            stats["examples"] = {f"{t}/{a}": cand[(t, a)] for t in decision["explanationTypes"] for a in rt.types[t]["audiences"]}
    out = {
        "ranAt": now_iso(), "sample": stats["encounters"], "graph": graph_stats(), "decisionClasses": stats["byClass"],
        "E4": {"explanations": stats["explanations"], "withFacts": stats["withFacts"], "traced": stats["traced"],
               "completeChains": stats["complete"],
               "completeRate": round(stats["complete"] / stats["withFacts"], 3) if stats["withFacts"] else None,
               "meanChainLength": round(sum(stats["chainLengths"]) / len(stats["chainLengths"]), 2) if stats["chainLengths"] else None},
        "E5": {"coverage": rt.coverage},
        "E6": {"topKFeatures": stats["topFeatures"], "activeAndBound": stats["activeBound"],
               "boundRate": round(stats["activeBound"] / stats["topFeatures"], 3) if stats["topFeatures"] else None,
               "withEvidencePath": stats["withEvidence"],
               "evidenceRate": round(stats["withEvidence"] / stats["activeBound"], 3) if stats["activeBound"] else None,
               "factsPerAudience": {k: round(sum(v) / len(v), 2) for k, v in stats["factsPerAudience"].items()},
               "budgetViolations": stats["budgetViolations"],
               "keysWithoutEvidence": sorted(k for k, v in keys_with_evidence.items() if not v)},
        "examples": stats["examples"],
    }
    PATHS.results.mkdir(exist_ok=True)
    (PATHS.results / "e4-e6-explanations.json").write_text(json.dumps(out, indent=2, default=str) + "\n", encoding="utf-8")
    md = ["# E4-E6 - Explanations on a test sample", "",
          f"{out['sample']} test encounters; decision classes {out['decisionClasses']}; graph {out['graph']['nodes']}", "",
          f"E4 traceability: {out['E4']['completeChains']}/{out['E4']['withFacts']} explanations with facts have a complete provenance chain "
          f"(rate {out['E4']['completeRate']}); mean facts traced per explanation {out['E4']['meanChainLength']}.",
          f"E6 grounding: {out['E6']['activeAndBound']}/{out['E6']['topKFeatures']} top-{top_k} positive features are active and bound to a KG entity "
          f"(rate {out['E6']['boundRate']}); {out['E6']['withEvidencePath']} of those have at least one validated evidence path (rate {out['E6']['evidenceRate']}).",
          f"Budget violations: {out['E6']['budgetViolations']}. Mean facts per audience: {out['E6']['factsPerAudience']}.",
          f"Bound entities without any evidence in the KG: {out['E6']['keysWithoutEvidence']}", ""]
    if out["examples"]:
        md += ["## Every explanation type for one high-risk encounter", ""]
    for key, ex in out["examples"].items():
        md += [f"### {ex['type']}, audience `{ex['audience']}` (explanation {ex['explanation_id']})", "", "```", ex["text"].strip(), "```", ""]
    (PATHS.results / "e4-e6-explanations.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return out
