"""E1: schema evolution propagates to every derived artefact with zero manual edits (R2).

Three evolution scenarios are applied as edits to the M1 models (never to generated files), the
chain is regenerated (check + T1 + T3 + T4 + T6 + T2a) and the generated artefacts are diffed
against the baseline. We record which artefacts changed, how many model edits were needed, and
whether the constraint layer caught the incomplete edit (e.g. renaming a relation without updating
the few-shot examples).
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JAR = ROOT / "xaikg-mde" / "target" / "xaikg-mde.jar"
MODELS = ROOT / "models" / "diabetes-readmission"
RESULTS = ROOT / "results"


def run(cmd: list[str]) -> dict:
    p = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return {**json.loads(p.stdout), "_exit": p.returncode}
    except json.JSONDecodeError:
        return {"status": "failure", "error": p.stdout[-500:] + p.stderr[-500:], "_exit": p.returncode}


def generate(models: Path, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    rep = run(["java", "-jar", str(JAR), "generate", "--mde-home", str(ROOT / "xaikg-mde"), "-m", str(models), "-o", str(out)])
    if rep.get("status") == "ok":
        # T2a (validator compilation) on an empty raw set is part of the derived artefacts too
        raw = out / "_empty_raw"
        raw.mkdir(exist_ok=True)
        (raw / "empty.xmi").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<raw:RawExtractionResult xmi:version="2.0" '
                                       'xmlns:xmi="http://www.omg.org/XMI" xmlns:raw="http://www.xaikg.org/1.0/raw" '
                                       'sourceDocument="none" sourceText="" llmModel="none" promptId="none" promptHash="none" '
                                       'extractionTimestamp="none"/>\n')
        run(["java", "-jar", str(JAR), "t2", "--mde-home", str(ROOT / "xaikg-mde"), "-m", str(models), "--raw", str(raw),
             "-o", str(out / "validated")])
    return rep


def fingerprints(out: Path) -> dict[str, str]:
    fps = {}
    for p in sorted(out.rglob("*")):
        if p.is_file() and p.suffix in (".txt", ".json", ".cypher", ".xmi", ".py", ".j2", ".evl") and "_empty_raw" not in str(p):
            text = p.read_text(encoding="utf-8", errors="replace")
            # ignore timestamps and hashes of inputs: we want semantic changes only
            text = re.sub(r"(generated-at|generatedAt|validatedAt|input: [^\n]*sha256=)[^\n]*", "", text)
            text = re.sub(r'"(promptId|promptHash|sha256|generatedAt|policyVersion|validationPolicyVersion)"\s*:\s*"[^"]*"', "", text)
            text = re.sub(r"sha256=[0-9a-f]+", "", text)
            text = re.sub(r"[0-9a-f]{64}", "", text)          # model fingerprints embedded in side-cars/manifests
            text = re.sub(r"@[0-9a-f]{12}", "", text)         # prompt ids (task@hash)
            fps[str(p.relative_to(out))] = hashlib.sha256(text.encode()).hexdigest()
    return fps


def edit(models: Path, file: str, replacements: list[tuple[str, str]]) -> int:
    p = models / file
    text = p.read_text(encoding="utf-8")
    n = 0
    for old, new in replacements:
        if old not in text:
            raise SystemExit(f"anchor not found in {file}: {old[:80]}")
        text = text.replace(old, new)
        n += 1
    p.write_text(text, encoding="utf-8")
    return n


SCENARIOS = {
    "S1_add_concept_and_relation": {
        "description": "Add concept Procedure (name, cptCode) and relation UNDERGOES (Condition -> Procedure); target both in the literature task.",
        "edits": [
            ("kg-schema.xmi", [(
                "  <!-- ============================ Relations ============================ -->",
                '  <concepts name="Procedure" uri="http://www.xaikg.org/usecases/diabetes-readmission#Procedure"\n'
                '      description="A medical or surgical procedure performed during care, e.g. dialysis, coronary bypass.">\n'
                '    <properties name="name" dataType="STRING" isRequired="true" isExplainable="true" description="Procedure name in lowercase"/>\n'
                '    <properties name="cptCode" dataType="STRING" isRequired="false" isExplainable="false" description="CPT or ICD-9 procedure code if stated"/>\n'
                '  </concepts>\n\n'
                "  <!-- ============================ Relations ============================ -->")],
            ),
            ("kg-schema.xmi", [(
                '  <relations id="INDICATES" name="INDICATES"',
                '  <relations id="UNDERGOES" name="UNDERGOES" source="Condition" target="Procedure"\n'
                '      minCardinality="0" maxCardinality="-1"\n'
                '      semantics="patients with the condition undergo the procedure"/>\n'
                '  <relations id="INDICATES" name="INDICATES"')]),
            ("extraction-pipeline.xmi", [
                ('targetConcepts="kg-schema.xmi#RiskFactor kg-schema.xmi#Condition kg-schema.xmi#LabTest kg-schema.xmi#ClinicalOutcome kg-schema.xmi#Drug"',
                 'targetConcepts="kg-schema.xmi#RiskFactor kg-schema.xmi#Condition kg-schema.xmi#LabTest kg-schema.xmi#ClinicalOutcome kg-schema.xmi#Drug kg-schema.xmi#Procedure"'),
                ('kg-schema.xmi#INDICATES kg-schema.xmi#MAY_CAUSE">', 'kg-schema.xmi#INDICATES kg-schema.xmi#MAY_CAUSE kg-schema.xmi#UNDERGOES">')]),
        ],
    },
    "S2_rename_relation": {
        "description": "Rename relation MAY_CAUSE to HAS_ADVERSE_EFFECT (name attribute); few-shot examples updated in the same model.",
        "partial_first": [("kg-schema.xmi", [('name="MAY_CAUSE"', 'name="HAS_ADVERSE_EFFECT"')])],
        "edits": [
            ("kg-schema.xmi", [('name="MAY_CAUSE"', 'name="HAS_ADVERSE_EFFECT"')]),
            ("extraction-pipeline.xmi", [('"type": "MAY_CAUSE"', '"type": "HAS_ADVERSE_EFFECT"')]),
        ],
    },
    "S3_mark_property_explainable": {
        "description": "Mark Condition.icd9Range as explainable.",
        "edits": [("kg-schema.xmi", [(
            '<properties name="icd9Range" dataType="STRING" isRequired="false" isExplainable="false"',
            '<properties name="icd9Range" dataType="STRING" isRequired="false" isExplainable="true"')])],
    },
}


def main() -> None:
    work = Path(tempfile.mkdtemp(prefix="xaikg-e1-"))
    base_out = work / "baseline"
    base_rep = generate(MODELS, base_out)
    assert base_rep.get("status") == "ok", base_rep
    base_fp = fingerprints(base_out)
    results = {"baselineArtefacts": len(base_fp), "scenarios": {}}
    for sid, sc in SCENARIOS.items():
        models = work / sid / "models"
        shutil.copytree(MODELS, models)
        caught = None
        if sc.get("partial_first"):
            # apply the incomplete edit first: does the constraint layer catch it?
            for file, reps in sc["partial_first"]:
                edit(models, file, reps)
            rep = run(["java", "-jar", str(JAR), "check", "--mde-home", str(ROOT / "xaikg-mde"), "-m", str(models)])
            caught = {"blocked": rep.get("_exit") != 0,
                      "constraints": sorted({v["constraint"] for v in rep.get("violations", []) if not v["critique"]})}
            shutil.rmtree(models)
            shutil.copytree(MODELS, models)
        n_edits = sum(edit(models, file, reps) for file, reps in sc["edits"])
        out = work / sid / "generated"
        rep = generate(models, out)
        fp = fingerprints(out)
        changed = sorted(k for k in fp if base_fp.get(k) != fp[k])
        added = sorted(k for k in fp if k not in base_fp)
        results["scenarios"][sid] = {
            "description": sc["description"], "modelEdits": n_edits, "manualEditsToGeneratedArtefacts": 0,
            "checkPassed": rep.get("status") == "ok", "warnings": rep.get("check", {}).get("summary", {}).get("warnings"),
            "artefactsChanged": changed, "artefactsAdded": added, "changedCount": len(changed) + len(added),
            "incompleteEditCaughtByConstraints": caught,
        }
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "e1-schema-evolution.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    md = ["# E1 - Schema evolution propagates through the chain (R2)", "",
          f"Baseline: {results['baselineArtefacts']} generated artefacts (prompts, side-cars, graph schema, DDL, validator, service files).", "",
          "| Scenario | Model edits | Manual edits to generated artefacts | Check | Artefacts changed/added | Incomplete edit caught |", "|---|---|---|---|---|---|"]
    for sid, r in results["scenarios"].items():
        caught = "-" if r["incompleteEditCaughtByConstraints"] is None else \
            ("yes: " + ", ".join(r["incompleteEditCaughtByConstraints"]["constraints"]) if r["incompleteEditCaughtByConstraints"]["blocked"] else "NO")
        md.append(f"| {sid}: {r['description']} | {r['modelEdits']} | {r['manualEditsToGeneratedArtefacts']} | {'ok' if r['checkPassed'] else 'FAILED'} | "
                  f"{r['changedCount']}: {', '.join(r['artefactsChanged'] + r['artefactsAdded'])} | {caught} |")
    (RESULTS / "e1-schema-evolution.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({k: {"edits": v["modelEdits"], "changed": v["changedCount"], "check": v["checkPassed"],
                          "caught": v["incompleteEditCaughtByConstraints"]} for k, v in results["scenarios"].items()}, indent=1))
    shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
