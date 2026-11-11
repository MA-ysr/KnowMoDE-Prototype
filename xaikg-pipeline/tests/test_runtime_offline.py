"""Offline checks of the explanation runtime against the GENERATED service artefacts (no Neo4j, no LLM):
the contract/coverage files are consistent with each other, bindings resolve SHAP attributions to
KG keys, templates render under every audience budget, and the generated router imports."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from xaikg.config import PATHS
from xaikg.explain.bindings import BindingResolver, is_active

SERVICE = PATHS.generated / "service"
pytestmark = pytest.mark.skipif(not (SERVICE / "contract.json").exists(), reason="run `make generate` first")


def test_contract_and_coverage_are_consistent():
    contract = json.loads((SERVICE / "contract.json").read_text())
    coverage = json.loads((SERVICE / "coverage.json").read_text())
    roles = {a["role"] for a in contract["audiences"]}
    for t in contract["explanationTypes"]:
        assert set(t["audiences"]) <= roles
        for a in t["audiences"]:
            assert coverage["matrix"][a][t["name"]] is True
    assert coverage["uncoveredAudiences"] == []
    assert coverage["totalEndpoints"] == sum(len(t["audiences"]) for t in contract["explanationTypes"]) + 1  # + /trace


def test_router_declares_one_endpoint_per_pair():
    contract = json.loads((SERVICE / "contract.json").read_text())
    router = (SERVICE / "router.py").read_text()
    for t in contract["explanationTypes"]:
        for a in t["audiences"]:
            assert f'/explain/{t["slug"]}/{a}"' in router, (t["slug"], a)
    assert '@router.get("/trace/{explanation_id}"' in router
    # the generated app refuses to bind beyond loopback
    assert 'host != "127.0.0.1"' in (SERVICE / "app.py").read_text()


def test_bindings_resolve_attributions_to_graph_keys():
    bindings = json.loads((SERVICE / "bindings.json").read_text())
    r = BindingResolver(bindings["featureBindings"])
    attributions = [
        {"feature": "number_inpatient", "value": 3, "attribution": 0.21},
        {"feature": "A1Cresult", "value": ">8", "attribution": 0.12},
        {"feature": "insulin", "value": "Up", "attribution": 0.08},
        {"feature": "diag_1", "value": "428", "attribution": 0.05},
        {"feature": "metformin", "value": "No", "attribution": 0.04},        # inactive: not prescribed
        {"feature": "num_lab_procedures", "value": 12, "attribution": 0.03},  # inactive: below threshold
        {"feature": "age", "value": "[70-80)", "attribution": -0.02},        # negative: not a risk driver
    ]
    g = r.resolve(attributions)
    keys = [x.key for x in g]
    assert keys == ["prior inpatient admissions", "hba1c > 8%", "insulin", "heart failure"]
    assert [x.concept for x in g] == ["RiskFactor", "LabTest", "Drug", "Condition"]
    assert is_active("value in ('>8', '>7', 'Norm')", "None") is False
    assert is_active("value >= 1", "0") is False and is_active("value >= 1", 2) is True
    assert is_active("value in (3, 4, 5, 22, 23, 24)", 3) is True


def test_active_bindings_cover_unattributed_features_and_raw_icd9_codes():
    bindings = json.loads((SERVICE / "bindings.json").read_text())
    r = BindingResolver(bindings["featureBindings"])
    features = {"diag_1": "428", "diag_2": "250.83", "diag_3": float("nan"), "metformin": "Steady", "insulin": "No",
                "A1Cresult": ">8", "number_inpatient": 0, "num_medications": 12}
    keys = [g.key for g in r.active(features)]
    # every active binding, attributed or not; NaN and inactive values are skipped; one entry per key
    assert {"heart failure", "diabetes", "metformin", "hba1c > 8%", "polypharmacy"} <= set(keys)
    assert "insulin" not in keys and "prior inpatient admissions" not in keys
    assert len(keys) == len(set(keys))


def test_round_robin_allocation_counts_what_the_budget_omits():
    from xaikg.explain.runtime import allocate, dedupe_rows
    rows = ([{"factorKey": "a", "factId": f"a{i}", "_pattern": "p"} for i in range(4)]
            + [{"factorKey": "b", "factId": "b0", "_pattern": "p"}]
            + [{"factId": "x0", "_pattern": "q"}, {"factId": "a0", "factorKey": "a", "_pattern": "p"}])
    rows = dedupe_rows(rows)                     # the repeated fact a0 is shown once
    chosen, available = allocate(rows, ["a", "b", "c"], 3)
    assert available == {"a": 4, "b": 1, "c": 0}
    assert [r["factId"] for r in chosen] == ["a0", "b0", "x0"]   # one per factor first, then the other rows
    chosen, _ = allocate(rows, ["a", "b", "c"], 5)
    assert [r["factId"] for r in chosen] == ["a0", "a1", "a2", "b0", "x0"]
    chosen, _ = allocate(rows, ["a", "b"], 2, "IN_ORDER")
    assert [r["factId"] for r in chosen] == ["a0", "a1"]


def test_counterfactual_items_render_on_separate_lines_and_reports_mark_omitted_facts():
    from jinja2 import Environment, FileSystemLoader
    from xaikg.explain.runtime import _plain, _source_title
    contract = json.loads((SERVICE / "contract.json").read_text())
    env = Environment(loader=FileSystemLoader(str(SERVICE / "templates")), trim_blocks=True, lstrip_blocks=True)
    env.filters["plain"], env.filters["source_title"] = _plain, _source_title
    cf = next(t for t in contract["explanationTypes"] if t["category"] == "COUNTERFACTUAL")
    facts = [{"protectiveFactor": f"factor {i}", "factorType": "RiskFactor", "outcome": "outcome", "sources": 1, "relatedTo": [],
              "sourceDocument": "pubmed/1.txt", "confidence": 0.9, "factId": f"f_{i}", "actionKeys": [f"factor {i}"]} for i in range(3)]
    for role in cf["audiences"]:
        aud = next(a for a in contract["audiences"] if a["role"] == role)
        text = env.get_template(cf["template"] + ".j2").render(decision={}, facts=facts, available_facts={},
                                                               audience={"role": role, "budget": aud["budget"]})
        items = [line for line in text.splitlines() if line.startswith("- ")]
        assert len(items) == 3, (role, text)
    fa = next(t for t in contract["explanationTypes"] if t["category"] == "FEATURE_ATTRIBUTION")
    decision = {"model": "m", "attributionMethod": "SHAP", "label": "high risk", "probability": 0.8,
                "factors": [{"feature": "f1", "value": 1, "attribution": 0.3, "entity": "e1", "key": "e1"},
                            {"feature": "f2", "value": 1, "attribution": 0.2, "entity": "e2", "key": "e2"},
                            {"feature": "f3", "value": 1, "attribution": 0.1, "entity": "e3", "key": "e3"}]}
    shown = [{"factorKey": "e1", "factId": "f_a", "sourceDocument": "pubmed/1.txt"}]
    text = env.get_template(fa["template"] + ".j2").render(decision=decision, facts=shown,
                                                           available_facts={"e1": 3, "e2": 2, "e3": 0}, audience={"budget": {}})
    assert "1 fact(s): f_a (pubmed/1.txt) + 2 omitted (budget)" in text
    assert "2 fact(s) omitted (budget)" in text
    assert "| e3 | none |" in text


def test_word_budget_keeps_items_on_their_own_lines():
    from xaikg.explain.runtime import truncate_words
    text = "Title line\n- first item has five words\n- second item also five\n- third"
    assert truncate_words(text, 50) == text
    cut = truncate_words(text, 10)             # 2 + 6 words fit; 2 words of the third line
    assert cut.splitlines() == ["Title line", "- first item has five words", "- second ..."]
    assert len(cut.replace("...", "").split()) == 10


def test_templates_render_for_every_audience_budget():
    from jinja2 import Environment, FileSystemLoader
    from xaikg.explain.runtime import _plain, _source_title
    contract = json.loads((SERVICE / "contract.json").read_text())
    env = Environment(loader=FileSystemLoader(str(SERVICE / "templates")), trim_blocks=True, lstrip_blocks=True)
    env.filters["plain"], env.filters["source_title"] = _plain, _source_title
    facts = [{"factorType": "RiskFactor", "factor": "prior inpatient admissions", "factorKey": "prior inpatient admissions", "relation": "INCREASES_RISK_OF",
              "outcome": "hospital readmission within 30 days", "factId": "f_1", "sourceDocument": "pubmed/123.txt",
              "charStart": 10, "charEnd": 80, "confidence": 0.9, "recommendation": "measure HbA1c during admission",
              "guidelineSource": "MedlinePlus", "strength": None, "condition": "diabetes", "recommends": ["HbA1c test"],
              "recommendsLabel": ["the HbA1c test"]}]
    decision = {"id": "d1", "label": "high risk", "probability": 0.81, "positive": True, "model": "readmission_gbm 0.1.0", "attributionMethod": "SHAP",
                "factors": [{"feature": "number_inpatient", "value": 3, "attribution": 0.21, "entity": "prior inpatient admissions",
                             "concept": "RiskFactor", "key": "prior inpatient admissions"}],
                "active": [{"feature": "diag_1", "value": "250", "entity": "diabetes", "concept": "Condition", "key": "diabetes"}]}
    for t in contract["explanationTypes"]:
        for role in t["audiences"]:
            aud = next(a for a in contract["audiences"] if a["role"] == role)
            text = env.get_template(t["template"] + ".j2").render(decision=decision, facts=facts, available_facts={"prior inpatient admissions": 1},
                                                                    audience={"role": role, "technicalLevel": aud["technicalLevel"], "budget": aud["budget"]})
            assert text.strip(), (t["name"], role)
            if aud["budget"]["plainLanguage"]:
                assert "f_1" not in text and "INCREASES_RISK_OF" not in text, "plain-language audience must not see codes"
