"""T2 acceptance test (R3/R4): a raw extraction with injected faults must be filtered by the validator
GENERATED from the Validation Policy model, each rejection naming the rule that fired.

Needs the jar (make jar). Runs in a temp folder; no LLM, no network."""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from xaikg import mde_bridge
from xaikg.config import PATHS
from xaikg.llm.raw_model import RawDocumentData, RawEntityData, RawModelWriter, RawRelationData

TEXT = ("Metformin hydrochloride tablets are indicated as an adjunct to diet and exercise to improve glycemic "
        "control in adults with type 2 diabetes mellitus. Metformin is contraindicated in patients with severe "
        "renal impairment. Postmarketing cases of metformin-associated lactic acidosis have been reported.")


def span(mention: str) -> tuple[int, int]:
    i = TEXT.index(mention)
    return i, i + len(mention)


def build_doc() -> RawDocumentData:
    doc = RawDocumentData(source_document="test/metformin.txt", source_uri="test://metformin", source_sha256="0" * 64,
                          source_text=TEXT, extraction_task="drug_label_extraction", llm_model="test/model",
                          prompt_id="drug_label_extraction@test", prompt_hash="f" * 64, timestamp="2026-01-01T00:00:00Z")
    s, e = span("Metformin hydrochloride")
    doc.entities.append(RawEntityData("Drug", "metformin", "Metformin hydrochloride", 0.98, s, e, 0,
                                      {"name": "metformin", "drugClass": "biguanide"}))
    s, e = span("type 2 diabetes mellitus")
    doc.entities.append(RawEntityData("Condition", "t2dm", "type 2 diabetes mellitus", 0.97, s, e, 0,
                                      {"name": "type 2 diabetes mellitus", "category": "metabolic"}))
    s, e = span("lactic acidosis")
    doc.entities.append(RawEntityData("Condition", "lactic-acidosis", "lactic acidosis", 0.93, s, e, 0,
                                      {"name": "lactic acidosis"}))
    # --- injected faults -------------------------------------------------------------------
    # F1 unknown concept (schema conformance)
    doc.entities.append(RawEntityData("Procedure", "dialysis", "Metformin", 0.9, 0, 9, 0, {"name": "dialysis"}))
    # F2 hallucinated mention: not in the text at the reported span
    doc.entities.append(RawEntityData("Condition", "pancreatitis", "acute pancreatitis", 0.95, 10, 28, 0,
                                      {"name": "acute pancreatitis"}))
    # F3 low confidence
    s, e = span("severe renal impairment")
    doc.entities.append(RawEntityData("Condition", "renal", "severe renal impairment", 0.42, s, e, 0,
                                      {"name": "severe renal impairment"}))
    # F4 missing required property (Drug.name)
    s, e = span("diet")
    doc.entities.append(RawEntityData("Drug", "diet", "diet", 0.9, s, e, 0, {"drugClass": "lifestyle"}))
    # relations
    ev = "Metformin hydrochloride tablets are indicated as an adjunct to diet and exercise to improve glycemic control in adults with type 2 diabetes mellitus."
    s, e = span(ev)
    doc.relations.append(RawRelationData("TREATS", "Drug", "metformin", "Condition", "t2dm", 0.97, ev, s, e, 0))
    ev2 = "Postmarketing cases of metformin-associated lactic acidosis have been reported."
    s, e = span(ev2)
    doc.relations.append(RawRelationData("MAY_CAUSE", "Drug", "metformin", "Condition", "lactic-acidosis", 0.9, ev2, s, e, 0))
    # F5 relation to a rejected entity (dangling after filtering)
    doc.relations.append(RawRelationData("CONTRAINDICATED_IN", "Drug", "metformin", "Condition", "renal", 0.96, ev2, s, e, 0))
    # F6 relation type not declared between these endpoint types
    doc.relations.append(RawRelationData("TREATS", "Condition", "t2dm", "Drug", "metformin", 0.9, ev, *span(ev), 0))
    # F7 relation with fabricated evidence
    doc.relations.append(RawRelationData("MAY_CAUSE", "Drug", "metformin", "Condition", "t2dm", 0.9,
                                         "Metformin causes type 2 diabetes.", 0, 33, 0))
    return doc


@pytest.mark.skipif(not PATHS.jar.exists(), reason="xaikg-mde.jar not built")
def test_generated_validator_rejects_injected_faults():
    tmp = Path(tempfile.mkdtemp(prefix="xaikg-t2-"))
    try:
        raw_dir, out = tmp / "raw", tmp / "out"
        RawModelWriter().write(build_doc(), raw_dir / "metformin.xmi")
        report = mde_bridge.t2(raw_dir, out)
        assert report["status"] == "ok"
        s = report["summary"]
        assert (s["rawEntities"], s["rawRelations"]) == (7, 5)
        assert (s["validEntities"], s["validRelations"]) == (3, 2), s
        rejected = json.loads((out / "rejection-report.json").read_text())["rejected"]
        by_id = {r["originalId"]: r["failedRule"] for r in rejected}
        assert by_id["dialysis"] == "entity_type_in_schema"
        assert by_id["pancreatitis"] == "mention_grounded_in_source"
        assert by_id["renal"] == "entity_confidence_above_threshold"
        assert by_id["diet"] == "required_properties_present"
        assert by_id["Drug:metformin -> Condition:renal"] == "relation_endpoints_accepted"
        assert by_id["Condition:t2dm -> Drug:metformin"] == "relation_type_and_endpoints_in_schema"
        assert by_id["Drug:metformin -> Condition:t2dm"] == "relation_evidence_grounded_in_source"
        # every rejection and every accepted fact carries provenance with the full verdict list (R7)
        evl = (out / "validation.evl").read_text()
        assert evl.count("constraint ") + evl.count("critique ") == 12, "one EVL constraint per ValidationRule"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
