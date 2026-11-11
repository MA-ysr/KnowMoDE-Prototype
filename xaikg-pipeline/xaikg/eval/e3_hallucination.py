"""E3: does the model-driven validation layer (T2) filter hallucinated triples?

Protocol. A sample of BC5CDR abstracts (gold chemical-induced-disease relations, MeSH-normalised)
is run through the GENERATED drug-label prompt, exactly as corpus documents are. The raw LLM output
and the T2-validated output are both scored against the gold CID relations, mapped to our schema's
MAY_CAUSE (Drug -> Condition). Matching is lenient on surface forms (case-insensitive, either side
contained in the other, or sharing the gold mention text), strict on direction and type.

Because the gold standard annotates abstracts, not FDA labels, absolute recall is bounded by what the
prompt asks for; the quantity of interest is the precision gain from raw to validated and the
per-rule rejection profile. A threshold sweep re-runs T2 with modified copies of the Validation
Policy model (a model edit, not a code edit), which is itself an R2 demonstration.
"""
from __future__ import annotations

import json
import random
import re
import shutil
import tempfile
from pathlib import Path

from .. import mde_bridge
from ..config import PATHS
from ..llm.extractor import extract_document
from ..llm.client import LLMClient
from ..llm.raw_model import RawModelWriter
from ..manifest import now_iso

GOLD = PATHS.gold / "bc5cdr" / "bc5cdr.jsonl"


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", s.lower()).strip()


def _match(pred_a: str, pred_b: str, gold_a: set[str], gold_b: set[str]) -> bool:
    pa, pb = _norm(pred_a), _norm(pred_b)

    def hit(p: str, golds: set[str]) -> bool:
        return any(p == g or (len(p) > 3 and (p in g or g in p)) for g in golds)

    return hit(pa, gold_a) and hit(pb, gold_b)


def load_gold(sample: int, seed: int, split: str = "test") -> list[dict]:
    docs = [json.loads(l) for l in GOLD.open(encoding="utf-8")]
    docs = [d for d in docs if d["split"] == split and d["relations"]]
    random.Random(seed).shuffle(docs)
    out = []
    for d in docs[:sample]:
        text = d["title"] + " " + d["abstract"]
        mesh_names: dict[str, set[str]] = {}
        for m in d["mentions"]:
            for mesh in m["mesh"].split("|"):
                mesh_names.setdefault(mesh, set()).add(_norm(m["mention"]))
        gold = []
        for r in d["relations"]:
            chem, dis = mesh_names.get(r["chemical"], set()), mesh_names.get(r["disease"], set())
            if chem and dis:
                gold.append({"chemical": chem, "disease": dis})
        out.append({"pmid": d["pmid"], "text": text, "gold": gold})
    return out


def _relations_from_vkg(vkg_dir: Path) -> dict[str, list[tuple[str, str]]]:
    """Accepted MAY_CAUSE relations per document, as (sourceKey, targetKey)."""
    from lxml import etree
    out: dict[str, list[tuple[str, str]]] = {}
    root = etree.parse(str(vkg_dir / "validated-kg.xmi")).getroot()
    # several ValidatedKG roots are serialised under an xmi:XMI wrapper; a single one is the root itself
    for vkg in root.iter():
        if not str(vkg.tag).endswith("ValidatedKG"):
            continue
        doc = vkg.get("sourceDocument")
        rels = []
        for r in vkg.findall("validRelations"):
            if r.get("type") == "MAY_CAUSE":
                rels.append((r.get("sourceKey") or "", r.get("targetKey") or ""))
        out[doc] = rels
    return out


def _score(preds: dict[str, list[tuple[str, str]]], gold_docs: list[dict]) -> dict:
    tp = fp = fn = 0
    for g in gold_docs:
        doc = f"bc5cdr/{g['pmid']}"
        pred = preds.get(doc, [])
        matched_gold: set[int] = set()
        for (a, b) in pred:
            hit = None
            for i, gr in enumerate(g["gold"]):
                if i not in matched_gold and _match(a, b, gr["chemical"], gr["disease"]):
                    hit = i
                    break
            if hit is None:
                fp += 1
            else:
                tp += 1
                matched_gold.add(hit)
        fn += len(g["gold"]) - len(matched_gold)
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": round(p, 3), "recall": round(r, 3), "f1": round(f, 3)}


def _raw_relations(raw_dir: Path) -> dict[str, list[tuple[str, str]]]:
    """MAY_CAUSE relations in the raw output (before validation), endpoint ids resolved to names when possible."""
    from lxml import etree
    out: dict[str, list[tuple[str, str]]] = {}
    for f in sorted(raw_dir.glob("*.xmi")):
        root = etree.parse(str(f)).getroot()
        names = {}
        for e in root.findall("entities"):
            name = next((p.get("value") for p in e.findall("properties") if p.get("key") == "name"), None)
            names[(e.get("type"), e.get("id"))] = name or e.get("mention") or e.get("id")
        rels = []
        for r in root.findall("relations"):
            if r.get("type") == "MAY_CAUSE":
                rels.append((names.get((r.get("sourceType"), r.get("sourceId")), r.get("sourceId")),
                             names.get((r.get("targetType"), r.get("targetId")), r.get("targetId"))))
        out[root.get("sourceDocument")] = rels
    return out


def _policy_variant(threshold: float | None, disable_grounding: bool) -> Path:
    """A modified copy of the use-case models: the policy's threshold and/or grounding rules changed
    (an M1 edit; the validator is regenerated from it by T2)."""
    tmp = Path(tempfile.mkdtemp(prefix="xaikg-e3-models-"))
    shutil.copytree(PATHS.models, tmp, dirs_exist_ok=True)
    policy = tmp / "validation-policy.xmi"
    text = policy.read_text(encoding="utf-8")
    if threshold is not None:
        text = re.sub(r'confidenceThreshold="[0-9.]+"', f'confidenceThreshold="{threshold}"', text)
    if disable_grounding:
        text = text.replace('name="mention_grounded_in_source" ruleType="HALLUCINATION_CHECK" scope="ENTITY" severity="ERROR"',
                            'name="mention_grounded_in_source" ruleType="HALLUCINATION_CHECK" scope="ENTITY" severity="WARNING"')
        text = text.replace('name="relation_evidence_grounded_in_source" ruleType="HALLUCINATION_CHECK" scope="RELATION" severity="ERROR"',
                            'name="relation_evidence_grounded_in_source" ruleType="HALLUCINATION_CHECK" scope="RELATION" severity="WARNING"')
    policy.write_text(text, encoding="utf-8")
    return tmp


def run(sample: int = 60, seed: int = 7, rpm: int = 10, model_override: str | None = None,
        thresholds: tuple[float, ...] = (0.5, 0.7, 0.9)) -> dict:
    sidecar = mde_bridge.prompt_sidecar("drug_label_extraction")
    prompt = (PATHS.prompts / sidecar["promptFile"]).read_text(encoding="utf-8")
    model_spec = model_override or sidecar["llmModel"]
    if model_override:
        sidecar = {**sidecar, "llmModel": model_override}
    client = LLMClient(model_spec, rpm=rpm, temperature=sidecar["temperature"], max_tokens=sidecar["maxTokens"])
    gold_docs = load_gold(sample, seed)
    work = PATHS.results / "e3" / model_spec.replace("/", "_")
    raw_dir = work / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    writer = RawModelWriter()
    stats = {"documents": 0, "skipped_existing": 0, "chunks_ok": 0, "chunks_failed": 0, "calls": 0, "cached": 0,
             "input_tokens": 0, "output_tokens": 0, "entities": 0, "relations": 0, "spans_repaired": 0, "malformed_items": 0}
    for g in gold_docs:
        out = raw_dir / f"{g['pmid']}.xmi"
        if out.exists():
            stats["skipped_existing"] += 1
            continue
        path = work / "docs" / f"{g['pmid']}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(g["text"], encoding="utf-8")
        doc = extract_document(client, prompt, sidecar, f"bc5cdr/{g['pmid']}", path,
                               {"uri": f"https://pubmed.ncbi.nlm.nih.gov/{g['pmid']}/"}, stats)
        writer.write(doc, out)
        stats["documents"] += 1
        stats["entities"] += len(doc.entities)
        stats["relations"] += len(doc.relations)

    results: dict = {"model": model_spec, "promptId": sidecar["promptId"], "sample": len(gold_docs),
                     "goldRelations": sum(len(g["gold"]) for g in gold_docs), "extraction": stats, "ranAt": now_iso(),
                     "raw": _score(_raw_relations(raw_dir), gold_docs), "validated": {}}
    variants = [("default", None, False)] + [(f"threshold_{t}", t, False) for t in thresholds] + [("no_grounding", None, True)]
    for name, thr, nog in variants:
        models = PATHS.models if (thr is None and not nog) else _policy_variant(thr, nog)
        out = work / f"validated_{name}"
        rep = mde_bridge.t2(raw_dir, out, models=models)
        score = _score(_relations_from_vkg(out), gold_docs)
        per_rule = {k: v["failed"] for k, v in rep["perRule"].items() if v["failed"]}
        results["validated"][name] = {**score, "summary": rep["summary"], "rejectionsPerRule": per_rule}
        if models != PATHS.models:
            shutil.rmtree(models, ignore_errors=True)

    (PATHS.results / "e3").mkdir(parents=True, exist_ok=True)
    (PATHS.results / f"e3-hallucination-filtering-{model_spec.replace('/', '_')}.json").write_text(
        json.dumps(results, indent=2) + "\n", encoding="utf-8")
    md = [f"# E3 - Hallucination filtering on BC5CDR ({model_spec})", "",
          f"{results['sample']} test abstracts, {results['goldRelations']} gold chemical-induced-disease relations; "
          f"prompt `{results['promptId']}`; MAY_CAUSE predictions scored against gold (lenient surface match, strict direction).", "",
          "| Variant | Precision | Recall | F1 | Accepted rel. | Rejections per rule |", "|---|---|---|---|---|---|",
          f"| raw LLM output | {results['raw']['precision']} | {results['raw']['recall']} | {results['raw']['f1']} | {stats['relations'] or '-'} | - |"]
    for name, v in results["validated"].items():
        rules = ", ".join(f"{k}: {n}" for k, n in sorted(v["rejectionsPerRule"].items())) or "-"
        md.append(f"| T2 {name} | {v['precision']} | {v['recall']} | {v['f1']} | {v['summary']['validRelations']} | {rules} |")
    md += ["", f"Spans repaired by exact search: {stats['spans_repaired']}; unparseable chunks: {stats['chunks_failed']}; "
               f"tokens in/out: {stats['input_tokens']}/{stats['output_tokens']}."]
    (PATHS.results / f"e3-hallucination-filtering-{model_spec.replace('/', '_')}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return results
