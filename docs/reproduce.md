# Reproducing the results

There are three levels, from simply inspecting the committed results to re-running everything with a live LLM.

## Requirements

| Tool | Version | Needed for |
|---|---|---|
| Java | 17 or later | the MDE runtime (`xaikg-mde`) |
| Maven | 3.9 or later | building `xaikg-mde.jar` (`make jar`) |
| Python + [uv](https://docs.astral.sh/uv/) | 3.12 | the kernel and the experiments (`make venv`) |
| Docker (or another compose-compatible runtime) | – | Neo4j 5 Community, started by `make neo4j-up` ([`compose.yaml`](../compose.yaml)) |
| Gemini API key | – | only for level 3 |

## Level 1: inspect (nothing to install)

All models, generated artifacts, datasets, intermediate models and results of the paper are committed. Start from the [README](../README.md); each experiment page in [experiments/](experiments.md) links to its result files.

## Level 2: re-run offline (no network, no LLM key)

```bash
cp .env.example .env        # set NEO4J_PASSWORD (GEMINI_API_KEY can stay empty)
make jar venv               # build the MDE runtime, create the Python environment
make neo4j-up               # Neo4j on 127.0.0.1 only
make reproduce              # jar, generate, extract (from the cache), validate, ddl-apply, load, train, e1, e2, e3, e4, coverage, e0
```

Before re-running E4 and E5, move the committed explanation log aside (`mv results/explanations/explanations.jsonl results/explanations/paper-run.jsonl`): `make e4` appends a new run, and `make coverage` counts every logged explanation of the current service version, so the paper's run and the new one would be counted together. The new name is only an example: any name works, because E5 reads only `results/explanations/explanations.jsonl`.


What to expect:

| Step | What is re-executed | Expected result |
|---|---|---|
| `make check` / `make generate` | Phase 2 and Phase 3 | 0 errors; the generated artifacts are identical to [`generated/`](../generated/) apart from generation timestamps |
| `make extract` | Phase 4 extraction, replayed from [`datasets/cache/llm/`](../datasets/cache/llm/) | 0 LLM calls; 3,558 entities and 1,512 relations; 5,055 spans relocated |
| `make validate` | T2a and T2b | 3,539 entities and 1,231 relations accepted, 300 rejected |
| `make train` | the predictor | AUROC 0.6466 on 17,494 held-out patients |
| `make e1`, `make e2`, `make e3` | experiments E1–E3 | the results of [E1](experiments.md#e1--schema-evolution), [E2](experiments.md#e2--fault-detection-by-mutation-analysis) and [E3](experiments.md#e3--validation-against-a-gold-standard) |
| `make e4`, `make coverage`, `make e0` | experiments E4–E6 and E0 (need Neo4j) | the results of [E4](experiments.md#e4--traceability-of-the-delivered-explanations), [E5](experiments.md#e5--coverage-of-the-audiences), [E6](experiments.md#e6--budgets-and-grounding-of-the-attributed-factors) and [E0](experiments.md#e0--context-of-the-evaluation) |

To re-run extraction from scratch rather than resuming, delete `datasets/raw/` first; one raw model (`patient_education_extraction/a1c.xmi`, which contains no entity and no relation) then records the model configured in the pipeline model instead of the one recorded at the time, and every other raw model is identical apart from timestamps.

The test suites run with `make test` (Java acceptance tests and Python tests).

## Level 3: re-run with a live LLM

Set `GEMINI_API_KEY` in `.env` and run `xaikg-pipeline/.venv/bin/xaikg extract --force` (the `--model` option selects another provider or model). LLM calls are not deterministic, so a new extraction may yield a slightly different knowledge graph; every later step remains deterministic on the new raw output.

## Changing the models (Phase 6)

Edit a model in [`models/diabetes-readmission/`](../models/diabetes-readmission/) and re-run the targets listed in [framework.md](framework.md#phase-6-in-practice): a policy change only needs `make validate load`, a change to the contract or the bindings only `make generate`, and a schema change regenerates the prompts, so only the extraction tasks whose prompts changed call the LLM again.
