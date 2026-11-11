"""E5, substantive coverage: what the delivered explanations actually contain.

The structural coverage matrix of E5 (exported by T6) shows that every audience is served by an
explanation type. This script measures, on the explanation log, whether those explanations carry
content: it reads the records produced by the current service version (the records whose model
fingerprints equal the sourceModels of generated/service/generation-manifest.json) and reports
  1. explanations in total, with facts and without facts, per audience and explanation type;
  2. the share of non-empty explanations of every RULE_BASED explanation type;
  3. the number of distinct texts per audience of every COUNTERFACTUAL explanation type;
  4. the number of COUNTERFACTUAL explanations with a fact about a non-modifiable entity (the
     entities a fact advises on are its `actionKeys`; their modifiability is read from the graph);
  5. the number of factor rows of FEATURE_ATTRIBUTION reports shown as "none" although the report
     of another audience for the same decision (same probability and factors) lists facts for the
     factor, and the number of rows shown as "none" although facts were available to the report.
Explanation types are selected by their category in the generated contract, never by name.
Needs the loaded graph for item 4.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict

from ..config import PATHS
from ..explain.store import DEFAULT_LOG

SERVICE = PATHS.generated / "service"


def _current_records() -> tuple[list[dict], dict]:
    fingerprints = json.loads((SERVICE / "generation-manifest.json").read_text(encoding="utf-8"))["sourceModels"]
    records = []
    with DEFAULT_LOG.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                if r.get("service_models") == fingerprints:
                    records.append(r)
    return records, fingerprints


def _report_rows(text: str) -> dict[str, str]:
    """Factor (KG entity) -> grounded-evidence cell of a rendered attribution report table."""
    rows = {}
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 5 and cells[0] not in ("Feature", "---"):
            rows[cells[3]] = cells[4]
    return rows


def run() -> dict:
    contract = json.loads((SERVICE / "contract.json").read_text(encoding="utf-8"))
    category = {t["name"]: t["category"] for t in contract["explanationTypes"]}
    records, fingerprints = _current_records()

    # 1. totals per audience and explanation type
    table: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for r in records:
        c = table[(r["audience"], r["explanation_type"])]
        c["total"] += 1
        c["withFacts" if r["facts"] else "withoutFacts"] += 1
    per_pair = [{"audience": a, "explanationType": t, "category": category.get(t), **dict(c)}
                for (a, t), c in sorted(table.items())]
    for row in per_pair:
        row.setdefault("withFacts", 0)
        row.setdefault("withoutFacts", 0)

    # 2. rule-based explanations: share with at least one fact, and per active condition
    rule_types = [t for t, c in category.items() if c == "RULE_BASED"]
    rule = {}
    for t in rule_types:
        rs = [r for r in records if r["explanation_type"] == t]
        non_empty = sum(1 for r in rs if r["facts"])
        rule[t] = {"explanations": len(rs), "nonEmpty": non_empty,
                   "share": round(non_empty / len(rs), 3) if rs else None,
                   "withActiveCondition": sum(1 for r in rs if any(a.get("concept") == "Condition" for a in r.get("active", [])))}

    # 3. counterfactual explanations: distinct texts per audience
    cf_types = [t for t, c in category.items() if c == "COUNTERFACTUAL"]
    distinct = {}
    for t in cf_types:
        by_aud = defaultdict(list)
        for r in records:
            if r["explanation_type"] == t:
                by_aud[r["audience"]].append(r)
        distinct[t] = {a: {"explanations": len(rs), "distinctTexts": len({r["text"] for r in rs}),
                           "distinctFactSets": len({tuple(r["fact_ids"]) for r in rs}),
                           "distinctDecisions": len({(r["probability"], json.dumps(r["factors"], sort_keys=True)) for r in rs})}
                       for a, rs in sorted(by_aud.items())}

    # 4. counterfactual facts about non-modifiable entities (modifiability read from the graph)
    keys = sorted({k for r in records if category.get(r["explanation_type"]) == "COUNTERFACTUAL"
                   for f in r["facts"] for k in (f.get("actionKeys") or [])})
    modifiable: dict[str, bool] = {}
    if keys:
        from ..kg.neo4j_client import query
        for row in query("UNWIND $keys AS k OPTIONAL MATCH (n {_key: k}) RETURN k AS key, coalesce(n._modifiable, false) AS m", keys=keys):
            modifiable[row["key"]] = bool(modifiable.get(row["key"]) or row["m"])
    nonmod_expl = 0
    nonmod_facts = 0
    facts_without_action = 0
    for r in records:
        if category.get(r["explanation_type"]) != "COUNTERFACTUAL":
            continue
        bad = 0
        for f in r["facts"]:
            ks = f.get("actionKeys") or []
            if not ks:
                facts_without_action += 1
            bad += sum(1 for k in ks if not modifiable.get(k, False))
        nonmod_facts += bad
        nonmod_expl += bool(bad)

    # 5. "none" in attribution reports while facts exist
    attr_types = [t for t, c in category.items() if c == "FEATURE_ATTRIBUTION"]
    none_vs_other = 0
    none_vs_available = 0
    rows_total = 0
    paired_decisions = 0
    for t in attr_types:
        groups = defaultdict(list)
        for r in records:
            if r["explanation_type"] == t:
                groups[(round(r["probability"], 6), json.dumps(r["factors"], sort_keys=True))].append(r)
        for rs in groups.values():
            parsed = {r["audience"]: _report_rows(r["text"]) for r in rs}
            if len(parsed) > 1:
                paired_decisions += 1
            for r in rs:
                rows = parsed[r["audience"]]
                for entity, cell in rows.items():
                    rows_total += 1
                    if cell != "none":
                        continue
                    if r.get("available_facts", {}).get(entity, 0) > 0:
                        none_vs_available += 1
                    if any(o != r["audience"] and other.get(entity, "none") != "none" for o, other in parsed.items()):
                        none_vs_other += 1

    out = {"serviceModels": fingerprints, "records": len(records),
           "perAudienceAndType": per_pair,
           "ruleBased": rule,
           "counterfactualDistinctTexts": distinct,
           "counterfactualNonModifiable": {"explanationsWithNonModifiableFact": nonmod_expl, "nonModifiableEntityMentions": nonmod_facts,
                                           "factsWithoutActionEntity": facts_without_action, "entitiesChecked": len(keys)},
           "attributionNoneWhileFactsExist": {"pairedDecisions": paired_decisions, "factorRows": rows_total,
                                              "noneWhileAnotherAudienceListsFacts": none_vs_other,
                                              "noneWhileFactsAvailable": none_vs_available}}
    PATHS.results.mkdir(exist_ok=True)
    (PATHS.results / "e5-substantive-coverage.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")

    md = ["# E5 - Substantive coverage of the delivered explanations", "",
          f"{len(records)} explanations of the current service version (explanation log records whose model fingerprints "
          "equal the generation manifest of the service).", "",
          "## Explanations per audience and explanation type", "",
          "| Audience | Explanation type | Category | Total | With facts | Without facts |", "|---|---|---|---|---|---|"]
    md += [f"| {r['audience']} | {r['explanationType']} | {r['category']} | {r['total']} | {r['withFacts']} | {r['withoutFacts']} |"
           for r in per_pair]
    md += ["", "## Rule-based explanations", ""]
    for t, v in rule.items():
        md.append(f"- {t}: {v['nonEmpty']}/{v['explanations']} non-empty (share {v['share']}); "
                  f"{v['withActiveCondition']} of them concern an encounter with at least one active condition.")
    md += ["", "## Counterfactual explanations", ""]
    for t, per_aud in distinct.items():
        for a, v in per_aud.items():
            md.append(f"- {t}, {a}: {v['distinctTexts']} distinct texts for {v['explanations']} explanations "
                      f"({v['distinctDecisions']} distinct decisions, {v['distinctFactSets']} distinct fact sets).")
    nm = out["counterfactualNonModifiable"]
    md.append(f"- Explanations with a fact about a non-modifiable entity: {nm['explanationsWithNonModifiableFact']} "
              f"({nm['entitiesChecked']} advised entities checked against the graph; facts without an advised entity: {nm['factsWithoutActionEntity']}).")
    a = out["attributionNoneWhileFactsExist"]
    md += ["", "## Attribution reports", "",
           f"- {a['pairedDecisions']} decisions with reports for more than one audience; {a['factorRows']} factor rows in total.",
           f"- Rows reported as \"none\" although another audience's report for the same decision lists facts: {a['noneWhileAnotherAudienceListsFacts']}.",
           f"- Rows reported as \"none\" although facts were available to the report: {a['noneWhileFactsAvailable']}.", ""]
    (PATHS.results / "e5-substantive-coverage.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return out
