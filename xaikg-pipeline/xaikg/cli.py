"""`xaikg` command line: the Python half of the paper's six-phase workflow (Section 4).

  xaikg data            download the tabular dataset (ML training)
  xaikg corpus [part]   fetch the LLM corpus (openfda | medlineplus | pubmed | papers | gold | all)
  xaikg extract         run the LLM with the GENERATED prompts -> datasets/raw/*.xmi
  xaikg validate        T2 via the jar -> generated/validated/
  xaikg load            T5 via the jar + execute against Neo4j
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from .config import PATHS

app = typer.Typer(add_completion=False, no_args_is_help=True, help=__doc__)


def _print(obj) -> None:
    typer.echo(json.dumps(obj, indent=2, ensure_ascii=False, default=str))


@app.command()
def data(force: bool = False) -> None:
    """Download the UCI 296 diabetes dataset into datasets/tabular/ (with manifest)."""
    from .corpus import dataset
    _print(dataset.fetch(force=force))


@app.command()
def corpus(part: str = typer.Argument("all"), force: bool = False) -> None:
    """Fetch the LLM corpus. The list of drugs/conditions comes from the decision-bindings model."""
    from .corpus import gold, medlineplus, openfda, pubmed
    from .corpus.plan import build_plan
    plan = build_plan()
    report: dict = {"plan": {"drugs": plan.drugs, "conditions": plan.conditions, "labs": plan.labs}}
    if part in ("openfda", "all"):
        report["openfda"] = openfda.fetch(plan, force=force)
    if part in ("medlineplus", "all"):
        report["medlineplus"] = medlineplus.fetch(plan, force=force)
    if part in ("pubmed", "all"):
        report["pubmed"] = pubmed.fetch_abstracts(plan, force=force)
    if part in ("papers", "all"):
        report["papers"] = pubmed.fetch_papers(plan, force=force)
    if part in ("gold", "all"):
        report["gold_bc5cdr"] = gold.fetch_bc5cdr(plan, force=force)
    _print(report)


@app.command()
def extract(task: Optional[str] = typer.Option(None, help="extraction task name (default: all tasks of the pipeline)"),
            limit: Optional[int] = typer.Option(None, help="max documents per task (smoke tests)"),
            model: Optional[str] = typer.Option(None, help="override provider/model, e.g. ollama/qwen2.5:14b-instruct"),
            rpm: int = typer.Option(8, help="max LLM requests per minute (free-tier friendly)"),
            force: bool = False) -> None:
    """Phase 4: call the LLM with the generated prompt of each task; write rawextraction.xmi per document."""
    from .llm.extractor import run_extraction
    _print(run_extraction(task=task, limit=limit, model_override=model, rpm=rpm, force=force))


@app.command()
def validate(out: Path = typer.Option(PATHS.generated / "validated", help="output folder")) -> None:
    """Phases 3-4: T2 (T2a generates the validator, T2b applies it applied to the raw extractions) through the jar."""
    from . import mde_bridge
    _print(mde_bridge.t2(PATHS.raw, out))


@app.command()
def load(validated: Path = typer.Option(PATHS.generated / "validated"), apply: bool = True) -> None:
    """Phase 4: T5 (loader script) through the jar, then execute it against Neo4j."""
    from . import mde_bridge
    from .kg.neo4j_client import apply_cypher_file
    report = mde_bridge.t5(validated, PATHS.generated / "load.cypher")
    if apply:
        report["neo4j"] = apply_cypher_file(PATHS.generated / "load.cypher")
    _print(report)


@app.command()
def e3(sample: int = 60, seed: int = 7, rpm: int = 10, model: Optional[str] = None) -> None:
    """Experiment E3: raw vs validated precision/recall against BC5CDR gold relations, threshold sweep."""
    from .eval.e3_hallucination import run
    r = run(sample=sample, seed=seed, rpm=rpm, model_override=model)
    _print({"raw": r["raw"], "validated": {k: {x: v[x] for x in ("precision", "recall", "f1")} for k, v in r["validated"].items()}})


def _sample_encounter(risk: str, seed: int) -> dict:
    """A real test-set encounter (UCI 296, de-identified) as a service request body."""
    from .ml.readmission import load_test_set
    test = load_test_set()
    if risk == "high":
        pool = test[(test.y_true == 1) & (test.p_readmit >= 0.5)].sort_values("p_readmit", ascending=False)
    elif risk == "low":
        pool = test[(test.y_true == 0) & (test.p_readmit < 0.3)]
    else:
        pool = test
    row = pool.sample(1, random_state=seed).iloc[0].to_dict() if seed else pool.iloc[0].to_dict()
    features = {k: (None if (isinstance(v, float) and v != v) else (int(v) if isinstance(v, float) and v.is_integer() else v))
                for k, v in row.items() if k not in ("y_true", "p_readmit")}
    return {"decision_id": f"demo-{risk}-{seed}", "features": features, "top_k": 5}


@app.command()
def sample(risk: str = typer.Option("high", help="high | low | any"), seed: int = typer.Option(0, help="0 = most confident case; >0 = random case"),
           out: Optional[Path] = typer.Option(None, help="write the JSON body to this file instead of stdout")) -> None:
    """Print a ready-to-paste request body for the explanation service (one real test encounter)."""
    body = _sample_encounter(risk, seed)
    if out:
        out.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
        typer.echo(f"wrote {out}")
    else:
        _print(body)


@app.command()
def explain(type: str = typer.Option("CausalEvidence", "--type", help="explanation type name or slug, e.g. CausalEvidence / causal_evidence"),
            audience: str = typer.Option("clinician"), risk: str = typer.Option("high"), seed: int = typer.Option(0),
            request: Optional[Path] = typer.Option(None, help="JSON request body (as produced by `xaikg sample`)"),
            trace: bool = typer.Option(True, help="also print the provenance chain")) -> None:
    """Produce one explanation in-process (no HTTP server needed; Neo4j must be up)."""
    from .explain.runtime import DecisionInput, ExplanationRuntime
    rt = ExplanationRuntime.from_generated()
    name = next((t["name"] for t in rt.contract["explanationTypes"] if type in (t["name"], t["slug"])), None)
    if name is None:
        raise SystemExit(f"unknown explanation type {type!r}; available: {[t['slug'] for t in rt.contract['explanationTypes']]}")
    if audience not in rt.audiences:
        raise SystemExit(f"unknown audience {audience!r}; available: {sorted(rt.audiences)}")
    body = json.loads(request.read_text(encoding="utf-8")) if request else _sample_encounter(risk, seed)
    result = rt.explain(name, audience, DecisionInput(**body))
    typer.echo(f"== {name} for {audience} | decision {result.get('decision_class')} p={result.get('probability')} ==\n")
    typer.echo(result.get("text") or result.get("message"))
    typer.echo("\n-- grounded factors: " + ", ".join(f"{g['feature']}={g['value']} -> {g['entity']}" for g in result.get("grounded_factors", [])))
    typer.echo(f"-- facts: {len(result.get('facts', []))} | fact ids: {result.get('fact_ids')}")
    if trace and result.get("explanation_id") and result.get("fact_ids"):
        tr = rt.trace(result["explanation_id"])
        typer.echo(f"-- trace complete: {tr['complete']} ({tr['facts_traced']} facts)")
        for c in tr["chain"][:3]:
            doc, run = c.get("document") or {}, c.get("extractionRun") or {}
            typer.echo(f"   {c['sourceType']} '{c['source']}' -[{c['relation']}]-> '{c['target']}' | {doc.get('id')} chars "
                       f"{c['provenance'].get('_prov_char_start')}-{c['provenance'].get('_prov_char_end')} | {run.get('llmModel')} | prompt {run.get('promptId')}")


@app.command()
def e4(sample: int = 200, seed: int = 11, top_k: int = 5) -> None:
    """Experiments E4 (traceability), E5 (coverage) and E6 (grounding) on a test sample (needs Neo4j + model)."""
    from .eval.e4_e6_explanations import run
    r = run(sample=sample, seed=seed, top_k=top_k)
    _print({"E4": r["E4"], "E6": {k: v for k, v in r["E6"].items() if k != "keysWithoutEvidence"}})


@app.command()
def coverage() -> None:
    """Experiment E5 (substantive coverage): content of the explanations logged by the current service version."""
    from .eval.substantive_coverage import run
    r = run()
    _print({k: r[k] for k in ("records", "ruleBased", "counterfactualNonModifiable", "attributionNoneWhileFactsExist")})


@app.command()
def train() -> None:
    """Train the readmission model (UCI 296) and store it with its test set and model card."""
    from .ml.readmission import train as _train
    _print(_train().metrics)


@app.command()
def stats() -> None:
    """Node/relationship counts of the loaded graph (E0)."""
    from .kg.neo4j_client import graph_stats
    _print(graph_stats())


@app.command()
def llm_check(model: str = "gemini/gemini-3.5-flash") -> None:
    """One tiny LLM call to verify credentials and JSON mode (no corpus text is sent)."""
    from .llm.client import LLMClient
    client = LLMClient(model, rpm=60)
    answer = client.complete_json("Reply with a JSON object {\"ok\": true, \"model\": \"<your model name>\"}.", "ping")
    _print({"model": model, "answer": answer.data, "cached": answer.cached, "latency_s": round(answer.latency, 2)})


if __name__ == "__main__":
    app()
