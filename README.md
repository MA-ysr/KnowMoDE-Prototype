# KnowMoDE Prototype

Companion repository of the paper **"KnowMoDE: A Model-Driven Framework for LLM-Assisted Knowledge Graph Construction in
Explainable AI-Based Information Systems"**.

KnowMoDE treats the five concerns of a knowledge-graph-based explanation pipeline (the KG schema, the LLM pipeline, the validation
policy, the explanation contract and the bindings between AI decisions and the graph) as **five models conforming to one metamodel**.
A constraint layer rejects inconsistent models before generation, and a chain of transformations generates the graph schema, the
prompts, the validator, the loader and the explanation service. The case study explains **30-day readmission risk for patients with
diabetes** to four audiences (patient, clinician, quality officer, auditor), with a knowledge graph built by an LLM from 433 public
documents.

This repository contains the models, generated artifacts, datasets, the LLM response cache and all results. **The experiments can be re-run offline, without an LLM key.**

## Repository structure

```text
.
├── README.md                     this file
├── LICENSE, NOTICE               Apache-2.0 for the code; datasets under their own licences
├── Makefile                      the six phases and the experiments as make targets (`make help`)
├── compose.yaml                  Neo4j 5 Community (graph database), bound to 127.0.0.1
├── .env.example                  template for .env (NEO4J_PASSWORD; GEMINI_API_KEY only for live LLM runs)
├── docs/                         documentation (see the index below) and figures
├── xaikg-mde/                    ava project: metamodels, constraint layer, transformations, CLI
│   ├── metamodels/               xaikg.ecore (5 packages) + graphschema, rawextraction, validatedkg
│   ├── constraints/xaikg.evl     constraint layer C1–C5
│   ├── transformations/          T1–T6 (ETL, EGL, EGX)
│   └── src/                      Java CLI (main) and acceptance tests (test)
├── xaikg-pipeline/               Python project: runtime kernel, data acquisition, predictor, experiments
│   ├── xaikg/                    package: cli, corpus/, llm/, kg/, ml/, explain/, eval/, mde_bridge.py
│   ├── tools/                    E0, E1 and E2 runners, mutant generator
│   └── tests/                    offline tests
├── models/
│   ├── diabetes-readmission/     the five M1 models of the case study
│   └── mutants/                  22 faulty model sets (E2)
├── generated/                    every M0 artifact, as generated for the paper (do not edit)
├── datasets/                     tabular data, 433 source documents, gold standard, manifests, LLM cache, raw models
└── results/                      E0–E6 outputs, explanation log, trained predictor and model card
```

## The two projects

| | [`xaikg-mde`](xaikg-mde/): the model-driven side | [`xaikg-pipeline`](xaikg-pipeline/): the runtime kernel |
|---|---|---|
| Role | everything model-driven: metamodels (M2), constraint layer, transformations T1–T6; never calls an LLM or a database | model-independent kernel: LLM client and extractor, graph loading, predictor, explanation runtime; data acquisition; experiments |
| Language | Java 17 | Python 3.12 |
| Build / environment | Maven 3.9+: `make jar` builds the standalone `xaikg-mde/target/xaikg-mde.jar` | [uv](https://docs.astral.sh/uv/): `make venv` creates `xaikg-pipeline/.venv` |
| Main libraries | EMF (Ecore 2.39, Common 2.42), Eclipse Epsilon 2.8.0 (EOL, EVL, ETL, EGL, EGX), picocli 4.7, Jackson 2.17, JUnit 5 | pyecore 0.15, openai 1.59 (OpenAI-compatible client, used for Gemini), neo4j 5.27, pandas 2.2, scikit-learn 1.6.1, shap 0.46, FastAPI 0.115 + uvicorn, Jinja2, lxml, typer (all pinned in [`pyproject.toml`](xaikg-pipeline/pyproject.toml)) |
| Entry point | `java -jar xaikg-mde.jar {check, generate, t1, t2, t3, t4, t5, t6}`: one JSON report per command, exit code 2 if a blocking invariant fails | `xaikg {data, corpus, extract, validate, load, train, explain, e3, e4, coverage, …}` |
| Details | [xaikg-mde/README.md](xaikg-mde/README.md) | [xaikg-pipeline/README.md](xaikg-pipeline/README.md) |

External services: **Neo4j 5.26 Community** ([`compose.yaml`](compose.yaml)) stores the knowledge graph; the **Gemini API**
(models `gemini-3.5-flash-lite` and, for part of the literature task, `gemini-3.1-flash-lite`) was used for extraction and is only
needed to re-run extraction with a live LLM.

### How the projects are linked

```text
 models/diabetes-readmission/  (M1: five XMI models)
        │   xaikg-mde: check (Phase 2) → generate: T1, T3, T4, T6 (Phase 3)
        ▼
 generated/  prompts · graph schema + DDL · explanation service
        │   xaikg-pipeline: extract — the LLM runs the generated prompts → datasets/raw/ (raw models, Phase 4)
        │   xaikg-mde:      t2 — T2a generates the validator, T2b applies it → generated/validated/ (Phases 3–4)
        │   xaikg-mde:      t5 — loader generated/load.cypher, executed by xaikg-pipeline against Neo4j (Phase 4)
        ▼
 Neo4j knowledge graph ──► generated FastAPI service (its router imports xaikg.explain.runtime) ──► explanations (Phase 5)
        │
        ▼
 results/  E0–E6 outputs · explanation log with the model fingerprints of every explanation
```

The Python kernel calls the Java runtime through [`xaikg/mde_bridge.py`](xaikg-pipeline/xaikg/mde_bridge.py) (a subprocess per
command, JSON report on standard output). The only data exchanged between the two projects are files: the M1 models go in, generated
artifacts and intermediate models come out.

## Quick start

```bash
cp .env.example .env                # set NEO4J_PASSWORD; GEMINI_API_KEY can stay empty
make jar venv                       # Java 17 + Maven, Python 3.12 + uv
make check generate                 # Phases 2 and 3: constraint layer, then T1, T3, T4, T6
make neo4j-up                       # Neo4j via Docker
make reproduce                      # every phase and experiment, offline (LLM output replayed from the cache)
```

See [docs/reproduce.md](docs/reproduce.md) for the three levels of reproduction (inspect, re-run offline, re-run with a live LLM) and
the expected results of each step.

## Documentation

| Document | Content |
|---|---|
| [framework.md](docs/framework.md) | architecture (M3–M0), the six phases and where each lives in the code, fingerprints and audit trail, requirements R1–R8 |
| [metamodel.md](docs/metamodel.md) | the XAI-KG metamodel: five packages, root classes, the 11 cross-package references, all classes |
| [models.md](docs/models.md) | the five models of the case study and their content |
| [constraints.md](docs/constraints.md) | the constraint layer: five families, all 113 invariants |
| [transformations.md](docs/transformations.md) | T1–T6, the higher-order transformation T2, the three intermediate metamodels (with diagrams) |
| [runtime.md](docs/runtime.md) | the Python kernel: modules, span location, LLM cache, explanation service, explanation log |
| [datasets.md](docs/datasets.md) | every dataset: source, link, licence, acquisition (including the 12 PubMed queries) and preparation |
| [kg-construction.md](docs/kg-construction.md) | building the knowledge graph: accepted and rejected items, rejection reasons, merging, provenance |
| [experiments.md](docs/experiments.md) | experiments E0–E6: question, protocol, command, results and result files |
| [reproduce.md](docs/reproduce.md) | requirements and the three levels of reproduction |

## Licence

The code, metamodels, constraints, transformations and models are licensed under the [Apache License 2.0](LICENSE). The datasets in
[`datasets/`](datasets/) are third-party data redistributed for research reproducibility under their own licences and terms of use
([`NOTICE`](NOTICE), [docs/datasets.md](docs/datasets.md)).
