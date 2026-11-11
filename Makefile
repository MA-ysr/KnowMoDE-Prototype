# KnowMoDE artefact: the six phases of the paper (Section 4) as make targets.
#   Phase 2 check | Phase 3 generate (T1, T3, T4, T6, T2a) | Phase 4 extract, validate (T2b), load (T5)
#   Phase 5 serve | Phase 6 = edit a model and re-run the targets above (see docs/framework.md).
# All datasets and the LLM response cache are committed: `make reproduce` needs no network and no LLM key
# (only Neo4j for load/serve/e4/coverage/e0). `make data corpus` re-fetch the sources (network).

USECASE   ?= diabetes-readmission
MODELS     = models/$(USECASE)
MDE        = xaikg-mde
JAR        = $(MDE)/target/xaikg-mde.jar
XAIKG      = java -jar $(JAR)
MDEHOME    = --mde-home $(MDE)
PY         = xaikg-pipeline/.venv/bin/python
CLI        = xaikg-pipeline/.venv/bin/xaikg
COMPOSE   ?= docker compose           # or: finch compose

.PHONY: help jar venv check generate ddl-apply data corpus extract validate load train serve stats mutants e1 e2 e3 e4 coverage e0 test neo4j-up neo4j-down all reproduce clean

help:
	@echo "jar          build xaikg-mde.jar (EMF + Epsilon, standalone)"
	@echo "venv         create the Python environment (uv, Python 3.12) and install xaikg"
	@echo "check        Phase 2: constraint layer C1-C5 on $(MODELS)"
	@echo "generate     Phases 2-3: check, then T1, T3 (DDL), T4 (prompts), T6 (service) -> generated/"
	@echo "ddl-apply    apply generated/schema.cypher to Neo4j"
	@echo "data         re-download the UCI 296 dataset (committed in datasets/tabular/)"
	@echo "corpus       re-fetch the corpus + gold standard (openFDA, MedlinePlus, PubMed, Strack 2014, BC5CDR; committed)"
	@echo "extract      Phase 4: LLM extraction with the generated prompts -> datasets/raw/ (served from the cache)"
	@echo "validate     Phases 3-4: T2a (policy -> generated validator), T2b (raw -> ValidatedKG) -> generated/validated/"
	@echo "load         Phase 4: T5 loader -> generated/load.cypher, executed against Neo4j"
	@echo "train        readmission model + SHAP background -> results/model/"
	@echo "serve        Phase 5: run the generated explanation service on 127.0.0.1:8000"
	@echo "e1 | e2 | e3  experiments E1 (schema evolution), E2 (mutation analysis), E3 (gold standard) -> results/"
	@echo "e4           E4-E6 on 200 test encounters (explanations appended to the log)"
	@echo "coverage     E5 substantive coverage of the explanations of the current service version"
	@echo "test         Java + Python tests"

$(JAR): $(shell find $(MDE)/src $(MDE)/metamodels $(MDE)/constraints $(MDE)/transformations -type f) $(MDE)/pom.xml
	cd $(MDE) && mvn -B -q -DskipTests package

jar: $(JAR)

venv:
	cd xaikg-pipeline && uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -e ".[dev]"

check: $(JAR)
	$(XAIKG) check $(MDEHOME) -m $(MODELS)

generate: $(JAR)
	$(XAIKG) generate $(MDEHOME) -m $(MODELS) -o generated

ddl-apply:
	$(PY) -c "from pathlib import Path; from xaikg.kg.neo4j_client import apply_cypher_file; print(apply_cypher_file(Path('generated/schema.cypher')))"

data:
	$(CLI) data

corpus:
	$(CLI) corpus all

extract: generate
	$(CLI) extract

validate: $(JAR)
	$(XAIKG) t2 $(MDEHOME) -m $(MODELS) --raw datasets/raw -o generated/validated

load: $(JAR)
	$(CLI) load

train:
	$(CLI) train

serve:
	cd generated/service && ../../$(PY) app.py

stats:
	$(CLI) stats

mutants:
	python3 xaikg-pipeline/tools/make_mutants.py

e1: $(JAR)
	$(PY) xaikg-pipeline/tools/run_e1.py

e2: $(JAR) mutants
	python3 xaikg-pipeline/tools/run_mutants.py

e3: $(JAR)
	$(CLI) e3

test: mutants $(JAR)
	cd $(MDE) && mvn -B -q test
	cd xaikg-pipeline && .venv/bin/python -m pytest -q

neo4j-up:
	$(COMPOSE) up -d

neo4j-down:
	$(COMPOSE) down

e4:
	$(CLI) e4

coverage:
	$(CLI) coverage

e0:
	$(PY) xaikg-pipeline/tools/run_e0.py

all: check generate data corpus extract validate load train

# Reviewer path: no network and no LLM key needed. The datasets are committed (verified by the manifests)
# and `extract` is served entirely from the committed LLM response cache. Neo4j must be up (make neo4j-up).
reproduce: jar generate extract validate ddl-apply load train e1 e2 e3 e4 coverage e0

clean:
	rm -rf $(MDE)/target generated/prompts generated/service generated/validated generated/graph-schema.xmi generated/schema.cypher generated/load.cypher
