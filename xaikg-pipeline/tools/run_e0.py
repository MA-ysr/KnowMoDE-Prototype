"""E0: the context table of the paper (corpus, KG, LLM usage, predictor, run times, and the
generated vs hand-written boundary of the artefact). Everything is measured, nothing typed.

Generated = files derived by T1-T6 (+ T2a) from the models. Hand-written framework = the MDE
runtime (Java) and the Epsilon programs (constraints, transformations), i.e. the reusable framework.
Hand-written runtime kernel = the model-independent Python package. Models = the five M1 files
of the use case (what a domain team writes). Sizes in non-blank, non-comment lines.
"""
from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"


def loc(path: Path, exts: tuple[str, ...], exclude: tuple[str, ...] = ()) -> tuple[int, int]:
    files = lines = 0
    for p in path.rglob("*"):
        if not p.is_file() or p.suffix not in exts or any(x in str(p) for x in exclude):
            continue
        files += 1
        text = p.read_text(encoding="utf-8", errors="ignore")
        if p.suffix in (".py", ".evl", ".etl", ".egl", ".egx", ".java", ".cypher"):
            text = re.sub(r"/\*.*?\*/|\[\*.*?\*\]", "", text, flags=re.DOTALL)
            text = "\n".join(l for l in text.splitlines() if l.strip() and not l.strip().startswith(("#", "//", "--")))
        lines += sum(1 for l in text.splitlines() if l.strip())
    return files, lines


def corpus_llm_usage() -> tuple[int, int, int, int, int, dict]:
    """LLM usage behind the current raw extraction models: for every chunk of every document of every
    extraction task, the cached response the extractor serves (under the configured model, or the model
    that processed the document). Returns calls, input tokens, output tokens, chunks, chunks without a
    cached response, and calls per (task, model). The run log (extraction-runs.jsonl) keeps every call
    ever made, including runs whose output was later superseded."""
    import sys
    sys.path.insert(0, str(ROOT / "xaikg-pipeline"))
    from xaikg.config import PATHS
    from xaikg.llm import extractor
    from xaikg.llm.chunking import chunk_document
    from xaikg.llm.client import LLMClient
    from xaikg.mde_bridge import prompt_registry, prompt_sidecar
    calls = tok_in = tok_out = chunks = uncached = 0
    per_model: dict[str, int] = {}
    for p in prompt_registry()["prompts"]:
        sc = prompt_sidecar(p["task"])
        prompt = (PATHS.prompts / sc["promptFile"]).read_text(encoding="utf-8")
        base = LLMClient(sc["llmModel"], temperature=sc["temperature"], max_tokens=sc["maxTokens"])
        for doc_id, path, _entry in extractor._documents(sc["sourceCollection"]):
            text = path.read_text(encoding="utf-8")
            cs = sc["chunking"]
            parts = chunk_document(text, cs["chunkSize"], cs["overlap"], cs["splitter"])
            users = [extractor._user_message(doc_id, ch, len(parts)) for ch in parts]
            client = base if extractor._fully_cached(base, prompt, users) else (
                extractor.cached_alternative(base, prompt, sc, doc_id, path) or base)
            for u in users:
                chunks += 1
                f = client.cache_dir / f"{client.cache_key(prompt, u)}.json"
                if not f.exists():
                    uncached += 1
                    continue
                usage = json.loads(f.read_text(encoding="utf-8")).get("usage", {})
                calls += 1
                tok_in += int(usage.get("input", 0) or 0)
                tok_out += int(usage.get("output", 0) or 0)
                key = f"{p['task']} ({client.provider}/{client.model})"
                per_model[key] = per_model.get(key, 0) + 1
    return calls, tok_in, tok_out, chunks, uncached, per_model


def timed(cmd: list[str], cwd: Path = ROOT) -> float:
    t0 = time.perf_counter()
    subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return round(time.perf_counter() - t0, 2)


def main() -> None:
    jar = ["java", "-jar", str(ROOT / "xaikg-mde/target/xaikg-mde.jar")]
    home = ["--mde-home", str(ROOT / "xaikg-mde")]
    models = ["-m", str(ROOT / "models/diabetes-readmission")]
    tmp = RESULTS / "tmp-e0"
    tmp.mkdir(parents=True, exist_ok=True)
    times = {
        "check (C1-C5)": timed(jar + ["check"] + home + models),
        "generate (check+T1+T3+T4+T6)": timed(jar + ["generate"] + home + models + ["-o", str(tmp / "gen")]),
        "t2 (validator generation + validation of all raw extractions)": timed(jar + ["t2"] + home + models + ["--raw", str(ROOT / "datasets/raw"), "-o", str(tmp / "validated")]),
        "t5 (loader generation)": timed(jar + ["t5"] + home + models + ["--validated", str(tmp / "validated"), "-o", str(tmp / "load.cypher")]),
    }
    subprocess.run(["rm", "-rf", str(tmp)])

    sizes = {
        "models (M1, authored per use case)": loc(ROOT / "models/diabetes-readmission", (".xmi",)),
        "metamodels (M2)": loc(ROOT / "xaikg-mde/metamodels", (".ecore",)),
        "constraints C1-C5 (EVL)": loc(ROOT / "xaikg-mde/constraints", (".evl",)),
        "transformations T1-T6 (ETL/EGL/EGX)": loc(ROOT / "xaikg-mde/transformations", (".etl", ".egl", ".egx")),
        "MDE runtime (Java, incl. tests)": loc(ROOT / "xaikg-mde/src", (".java",)),
        "Python runtime kernel (corpus, LLM, kg, ml, explain, cli)": loc(ROOT / "xaikg-pipeline/xaikg", (".py",), exclude=("/eval/",)),
        "Python evaluation scripts + tools": (lambda a, b: (a[0] + b[0], a[1] + b[1]))(loc(ROOT / "xaikg-pipeline/xaikg/eval", (".py",)), loc(ROOT / "xaikg-pipeline/tools", (".py",))),
        "generated: prompts + side-cars (T4)": loc(ROOT / "generated/prompts", (".txt", ".json")),
        "generated: graph schema + DDL (T1, T3)": (lambda a, b: (a[0] + b[0], a[1] + b[1]))(loc(ROOT / "generated", (".xmi",), exclude=("validated",)), loc(ROOT / "generated", (".cypher",), exclude=("load.cypher",))),
        "generated: validator (T2a) + loader (T5)": (lambda a, b: (a[0] + b[0], a[1] + b[1]))(loc(ROOT / "generated/validated", (".evl",)), loc(ROOT / "generated", (".cypher",), exclude=("schema.cypher",))),
        "generated: explanation service (T6)": loc(ROOT / "generated/service", (".py", ".json", ".j2")),
    }

    ctx = json.loads((RESULTS / "e0-context.json").read_text()) if (RESULTS / "e0-context.json").exists() else {}
    rej = json.loads((ROOT / "generated/validated/rejection-report.json").read_text())
    runs = [json.loads(l) for l in (RESULTS / "extraction-runs.jsonl").open() if l.strip()]
    # span repairs of the run that wrote the current raw models of each task (the latest run that processed documents)
    latest: dict[str, dict] = {}
    for r in runs:
        for task, s in r["tasks"].items():
            if s.get("documents"):
                latest[task] = s
    repaired = sum(int(s.get("spans_repaired", 0) or 0) for s in latest.values())
    items = sum(int(s.get("entities", 0) or 0) + int(s.get("relations", 0) or 0) for s in latest.values())
    calls, tok_in, tok_out, chunks, uncached, per_model = corpus_llm_usage()
    manifests = {p.stem.replace(".manifest", ""): json.load(open(p))["fileCount"] for p in (ROOT / "datasets/manifests").glob("*.json")}
    card = json.loads((RESULTS / "model/model-card.json").read_text())
    try:
        import sys
        sys.path.insert(0, str(ROOT / "xaikg-pipeline"))
        from xaikg.kg.neo4j_client import graph_stats
        graph = graph_stats()
    except Exception as e:  # database down: report without graph counts
        graph = {"error": type(e).__name__}

    out = {"corpus": manifests, "llm": {"calls": calls, "inputTokens": tok_in, "outputTokens": tok_out, "cost": "0 (free tier)",
                                         "chunks": chunks, "chunksWithoutResponse": uncached, "callsPerTaskAndModel": per_model,
                                         "spansRepaired": repaired, "itemsReturned": items,
                                         "spanRepairRate": round(repaired / items, 4) if items else None,
                                         "itemsInRawModels": rej["summary"]["rawEntities"] + rej["summary"]["rawRelations"]},
           "validation": rej["summary"], "rejectionsPerRule": {k: v["failed"] for k, v in rej["perRule"].items() if v["failed"]},
           "graph": graph, "predictor": card["metrics"], "runTimesSeconds": times,
           "sizes": {k: {"files": v[0], "lines": v[1]} for k, v in sizes.items()}}
    (RESULTS / "e0-context.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")

    gen = sum(v[1] for k, v in sizes.items() if k.startswith("generated"))
    hand_fw = sum(v[1] for k, v in sizes.items() if k.startswith(("constraints", "transformations", "MDE runtime", "metamodels")))
    hand_rt = sizes["Python runtime kernel (corpus, LLM, kg, ml, explain, cli)"][1]
    md = ["# E0 - Context of the artefact", "",
          "| Aspect | Value |", "|---|---|",
          f"| Corpus documents | {', '.join(f'{k}: {v}' for k, v in sorted(manifests.items()))} |",
          f"| LLM calls / tokens (responses the raw models are built from) | {calls} calls for {chunks} chunks ({uncached} chunk without a response), {tok_in:,} input + {tok_out:,} output tokens, cost 0 (free tier) |",
          f"| Calls per task and model | {'; '.join(f'{k}: {v}' for k, v in sorted(per_model.items()))} |",
          f"| LLM items returned (runs that wrote the raw models) | {items:,}; spans re-located by exact search: {repaired:,} ({repaired / items:.1%}) |",
          f"| Items in the raw extraction models (T2 input) | {rej['summary']['rawEntities']:,} entities + {rej['summary']['rawRelations']:,} relations |",
          f"| Validation (T2) | {rej['summary']['rawEntities']:,} entities, {rej['summary']['rawRelations']:,} relations in; {rej['summary']['validEntities']:,} / {rej['summary']['validRelations']:,} accepted; {rej['summary']['rejected']} rejected (acceptance {rej['summary']['acceptanceRate']}) |",
          f"| Graph | {graph} |",
          f"| Predictor | AUROC {card['metrics']['auroc']}, AUPRC {card['metrics']['auprc']}, positive rate {card['metrics']['positiveRate']}, {card['metrics']['patients']:,} patients |",
          "", "## Run times (s)", "", "| Step | Seconds |", "|---|---|"] + [f"| {k} | {v} |" for k, v in times.items()] + [
          "", "## Generated vs hand-written (non-blank lines)", "", "| Artefact | Files | Lines |", "|---|---|---|"] + \
         [f"| {k} | {v[0]} | {v[1]:,} |" for k, v in sizes.items()] + [
          "", f"Generated artefacts: {gen:,} lines. Reusable framework (metamodels, constraints, transformations, Java runtime): {hand_fw:,} lines. "
              f"Model-independent Python kernel: {hand_rt:,} lines. Use-case models authored by the domain team: {sizes['models (M1, authored per use case)'][1]:,} lines of XMI."]
    (RESULTS / "e0-context.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md[-4:]))
    print(json.dumps(times, indent=1))


if __name__ == "__main__":
    main()
