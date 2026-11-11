# Experiments E0–E6

*Paper: Section 5 (Evaluation). Result files: [`results/`](../results/). How to re-run: [reproduce.md](reproduce.md).*

The evaluation answers three research questions with six experiments, plus E0, which gathers the context figures. Each section below gives the question, the protocol, the command, the results and the files they are stored in.

| | Research question | What is measured | Command | Key result |
|---|---|---|---|---|
| [E0](#e0--context-of-the-evaluation) | context | corpus, LLM usage, validation, graph, predictor | `make e0` | 433 documents, 634 LLM calls, AUROC 0.65 |
| [E1](#e1--schema-evolution) | RQ1 | propagation of three model changes | `make e1` | 1–4 model edits, 0 manual edits; drift caught by C2 |
| [E2](#e2--fault-detection-by-mutation-analysis) | RQ1 | detection of 22 injected model faults | `make e2` | 22/22 blocked before generation, each by the intended check |
| [E3](#e3--validation-against-a-gold-standard) | RQ2 | validation vs. an expert-annotated gold standard | `make e3` | precision 0.64 / recall 0.66 raw; validation cannot ensure truth |
| [E4](#e4--traceability-of-the-delivered-explanations) | RQ3 | traceability of the delivered explanations | `make e4` | 1,353/1,353 explanations with facts fully traceable |
| [E5](#e5--coverage-of-the-audiences) | RQ3 | coverage of the audiences | `make e4`, `make coverage` | every audience served; 184/400 guideline explanations non-empty |
| [E6](#e6--budgets-and-grounding-of-the-attributed-factors) | RQ3 | budgets and grounding of the attributed factors | `make e4` | 0 budget violations; 76% bound, 84% of these with evidence |

The construction of the knowledge graph itself, which also answers RQ2, is detailed in [kg-construction.md](kg-construction.md).

## E0 — Context of the evaluation

**Purpose.** E0 is not an experiment on a research question: it gathers the context figures of the evaluation (corpus, LLM usage, validation, graph and predictor). Several numbers of Sections 5.1 and 5.3 of the paper come from it.


**Run.** `make e0` ([`run_e0.py`](../xaikg-pipeline/tools/run_e0.py)); needs the loaded graph in Neo4j. **Results:** [`results/e0-context.md`](../results/e0-context.md), [`e0-context.json`](../results/e0-context.json).

| Aspect | Value |
|---|---|
| Corpus | 12 drug labels, 58 MedlinePlus topics, 362 PubMed abstracts, 1 full-text paper (433 documents); BC5CDR gold standard; UCI tabular data |
| LLM usage | 634 calls for 635 chunks (1 chunk without a response); 2,227,893 input and 593,734 output tokens |
| LLM output | 5,070 items; spans relocated by exact search: 5,055 (99.7%) |
| Validation (T2) | 3,558 entities and 1,512 relations in; 3,539 and 1,231 accepted; 300 rejected (acceptance 94.1%) |
| Graph | 1,346 domain entities and 1,223 domain relations, plus 369 source documents, 5 extraction runs and 4,993 provenance links ([kg-construction.md](kg-construction.md)) |
| Predictor | AUROC 0.6466, AUPRC 0.1702, positive rate 8.97%, 69,973 patients |


## E1 — Schema evolution

**Question.** Does a change to the models propagate to every generated artifact without manual intervention (R2), and does the constraint layer catch an incomplete change (P1)? Paper, Section 5.2.

**Protocol.** Three changes are applied as edits to the case-study models (never to generated files); the chain is regenerated (check, T1, T3, T4, T6, T2a) and every generated artifact is compared with the baseline generation (26 artifacts). For the renaming, the edit is first applied **incompletely** (one few-shot example still uses the old name) to see whether the constraint layer blocks generation.

**Run.** `make e1` ([`run_e1.py`](../xaikg-pipeline/tools/run_e1.py)). **Results:** [`results/e1-schema-evolution.md`](../results/e1-schema-evolution.md), [`e1-schema-evolution.json`](../results/e1-schema-evolution.json).

| Scenario | Model edits | Manual edits to generated artifacts | Artifacts regenerated | Incomplete edit caught |
|---|---|---|---|---|
| S1: add concept `Procedure` and relation `UNDERGOES` (Condition → Procedure), targeted by the literature task | 4 | 0 | 4: graph schema, DDL, literature prompt and side-car | – |
| S2: rename relation `MAY_CAUSE` to `HAS_ADVERSE_EFFECT`, few-shot examples updated in the same model | 2 | 0 | 8: graph schema, DDL, three prompts and their side-cars | **yes**, by `C2_FewShotOutputsMentionOnlyTargetedTypes` |
| S3: mark `Condition.icd9Range` as explainable | 1 | 0 | 10: graph schema, DDL, four prompts and their side-cars | – |

**Answer.** Each change took one to four model edits, and Phase 3 regenerated the affected artifacts without manual intervention. When the renaming was left incomplete in one few-shot example, invariant C2 blocked generation and caught schema–prompt drift (P1).

## E2 — Fault detection by mutation analysis

**Question.** Does the constraint layer of Phase 2 block inconsistent models before any artifact is generated (R3, R6)? Paper, Section 5.2.

**Protocol.** Mutation analysis: 22 copies of the five models, each with one injected design fault ([`models/mutants/`](../models/mutants/), generated by [`make_mutants.py`](../xaikg-pipeline/tools/make_mutants.py)). The faults were defined by the authors, three to five per constraint family (C1: 5, C2: 3, C3: 4, C4: 5, C5: 5). Each mutant is checked; it is *blocked* if generation is refused, and *caught by the intended check* if the expected invariant (or, for a dangling cross-model reference, the model loader) reports it.

**Run.** `make e2` ([`run_mutants.py`](../xaikg-pipeline/tools/run_mutants.py)). **Results:** [`results/e2-mutation-detection.md`](../results/e2-mutation-detection.md), [`e2-mutation-detection.json`](../results/e2-mutation-detection.json).

**Result.** All 22 mutants were blocked before generation, each by the intended check; two of them (M05, M16) already at load time, as dangling cross-model references.

| Mutant | Family | Mutated model | Injected fault | Blocked | Caught by |
|---|---|---|---|---|---|
| `M01_concept_without_property` | C1 | `kg-schema.xmi` | DrugClass loses its only property | yes | `C1_ConceptHasProperty` |
| `M02_negative_cardinality` | C1 | `kg-schema.xmi` | APPLIES_TO gets minCardinality -3 | yes | `C1_CardinalitiesValid` |
| `M03_empty_query_template` | C1 | `kg-schema.xmi` | guideline_rules loses its Cypher template (parameters cleared and template emptied) | yes | `C1_PatternHasTemplate` |
| `M04_pattern_writes_graph` | C1 | `kg-schema.xmi` | protective_factors template mutates the graph | yes | `C1_PatternReadsOnly` |
| `M05_prompt_targets_undeclared_concept` | C2 | `extraction-pipeline.xmi` | drug_label task targets a concept that does not exist (dangling reference) | yes | model loader (dangling cross-model reference) |
| `M06_prompt_relation_without_endpoint` | C2 | `extraction-pipeline.xmi` | drug_label task drops DrugClass but still targets BELONGS_TO_CLASS | yes | `C2_PromptRelationEndpointsAreTargeted` |
| `M07_concept_extracted_by_no_task` | C2 | `extraction-pipeline.xmi` | the only task that extracts DrugClass stops targeting it (with BELONGS_TO_CLASS and the few-shot items that use them): no task extracts DrugClass any more | yes | `C2_EveryConceptTargetedBySomeTask` |
| `M08_threshold_out_of_range` | C3 | `validation-policy.xmi` | confidence threshold 1.5 | yes | `C3_ThresholdInRange` |
| `M09_overlap_not_smaller_than_chunk` | C3 | `extraction-pipeline.xmi` | literature task overlap equals chunk size | yes | `C3_OverlapSmallerThanChunk` |
| `M10_rule_without_expression` | C3 | `validation-policy.xmi` | entity_confidence_above_threshold loses its expression | yes | `C3_RuleHasExpression` |
| `M11_no_provenance_rule` | C3 | `validation-policy.xmi` | the provenance rule is downgraded to WARNING (R7 no longer guaranteed) | yes | `C3_HasProvenanceRule` |
| `M12_uncovered_audience` | C4 | `explainability.xmi` | auditor is removed from GuidelineCompliance; AttributionReport still serves auditor, so ALSO remove it there | yes | `C4_AudienceCovered` |
| `M13_low_audience_gets_feature_attribution` | C4 | `explainability.xmi` | patient (LOW) is added to the FEATURE_ATTRIBUTION type | yes | `C4_LowAudienceNoFeatureAttribution` |
| `M14_low_audience_only_technical` | C4 | `explainability.xmi` | patient loses the contrastive type; keeps only ModifiableFactors... so ALSO remove patient there | yes | `C4_LowAudienceGetsAccessibleExplanation` |
| `M15_decision_class_misses_audience` | C4 | `decision-bindings.xmi` | LowReadmissionRisk no longer offers anything to the patient | yes | `C4_DecisionClassCoversEveryAudience` |
| `M16_explanation_uses_undeclared_pattern` | C5 | `explainability.xmi` | GuidelineCompliance references a query pattern that is not in the schema (dangling) | yes | model loader (dangling cross-model reference) |
| `M17_binding_feature_not_in_model` | C5 | `decision-bindings.xmi` | a feature binding refers to a feature the model does not have | yes | `C5_BindingFeatureExistsInModel` |
| `M18_binding_without_resolution` | C5 | `decision-bindings.xmi` | number_emergency binding loses its entityName | yes | `C5_BindingHasResolution` |
| `M19_configs_disagree_on_schema` | C5 | `validation-policy.xmi` | validation policy points to a different schema file | yes | `C5_AllConfigsShareOneSchema` |
| `M20_missing_trace_pattern` | C5 | `explainability.xmi` | auditor requires full provenance but no trace pattern is bound | yes | `C5_FullProvenanceAudienceHasTracePattern` |
| `M21_counterfactual_pattern_not_actionable` | C4 | `explainability.xmi` | ModifiableFactors (COUNTERFACTUAL) also runs causal_context, which may return non-modifiable risk factors | yes | `C4_CounterfactualPatternsActionable` |
| `M22_actionable_pattern_without_modifiability` | C1 | `kg-schema.xmi` | causal_context is declared actionableOnly without filtering on the modifiability property | yes | `C1_ActionablePatternFiltersModifiable` |

**Answer.** Consistency became a checked property instead of a matter of discipline, within the limits of the faults that the invariants can express (see the threats to validity in Section 6.2 of the paper).

## E3 — Validation against a gold standard

**Question.** What does model-driven validation guarantee for LLM-extracted knowledge, and where do these guarantees end? A **gold standard** is a public dataset in which experts annotated the correct relations; comparing the extracted relations with it measures whether they are *true*, which the validator itself cannot check. Paper, Section 5.3.

**Protocol.** The generated drug-label prompt (`drug_label_extraction@fc3d922aa277`) is applied with `gemini-3.1-flash-lite` to 60 test abstracts of the BC5CDR corpus (seed 7), which contain 131 expert-annotated chemical-induced-disease pairs; the extracted `MAY_CAUSE` relations are scored against them (lenient surface match, strict direction). **Precision** is the share of extracted relations that are correct; **recall** is the share of annotated pairs that were found. Each validation variant is obtained by editing the policy model (its confidence threshold, or the severity of its two grounding rules) and re-validating the stored output, **without new LLM calls**.

**Run.** `make e3` ([`e3_hallucination.py`](../xaikg-pipeline/xaikg/eval/e3_hallucination.py)); served from the LLM cache, no API key needed (about one minute). **Results:** [`results/e3-hallucination-filtering-gemini_gemini-3.1-flash-lite.md`](../results/e3-hallucination-filtering-gemini_gemini-3.1-flash-lite.md) and the validated models of each variant in [`results/e3/`](../results/e3/).

| Variant | Precision | Recall | F1 | Accepted relations |
|---|---|---|---|---|
| raw LLM output | 0.640 | 0.664 | 0.652 | 183 |
| default policy (threshold 0.7) | 0.627 | 0.641 | 0.634 | 180 |
| threshold 0.5 | 0.627 | 0.641 | 0.634 | 180 |
| threshold 0.9 | 0.564 | 0.405 | 0.471 | 130 |
| grounding rules downgraded to warnings | 0.632 | 0.656 | 0.644 | 182 |

**Reading the results.**

- The default policy leaves precision and recall almost unchanged.
- Downgrading the grounding rules to warnings raises recall slightly: their verbatim check had also rejected two correct relations whose quotations were not exact (86 instead of 84 true positives).
- Raising the confidence threshold from 0.7 to 0.9 lowers both values, because LLM confidence is weakly calibrated.
- The remaining errors are schema-conformant, grounded in a real sentence and confidently wrong.

**Answer.** Model-driven validation makes the extracted knowledge conformant, verifiably grounded and fully traceable, and it explains every rejection; it cannot guarantee that a fact is true. That judgment remains with domain experts, who can make it on an inspectable artifact.

## E4 — Traceability of the delivered explanations

**Question.** Can every delivered explanation be traced back to its facts, sources and model versions (R7, R8)? Paper, Section 5.4.

**Protocol.** The generated service is exercised on 200 held-out encounters (seed 11; 58 of them predicted at high risk) through every endpoint of the contract, which produces 1,574 logged explanations. For every explanation containing facts, the provenance chain of each fact is followed in the graph.

**Run.** `make e4` ([`e4_e6_explanations.py`](../xaikg-pipeline/xaikg/eval/e4_e6_explanations.py)); needs Neo4j with the loaded graph and the trained model. This command also produces the results of [E5](#e5--coverage-of-the-audiences) (structural part) and [E6](#e6--budgets-and-grounding-of-the-attributed-factors). **Results:** [`results/e4-e6-explanations.md`](../results/e4-e6-explanations.md), [`e4-e6-explanations.json`](../results/e4-e6-explanations.json), [`explanations.jsonl`](../results/explanations/explanations.jsonl).

**Result.** All **1,353** explanations that contain facts have complete provenance chains (rate 1.0; on average 10.43 facts traced per explanation): each fact leads to its source span, extraction run and policy version, and each explanation to the fingerprints of the models behind the service.

The explanations delivered for one high-risk encounter (p = 0.70) to the four audiences are reproduced in the paper (the table "One decision, four audiences"); [`results/e4-e6-explanations.md`](../results/e4-e6-explanations.md) and [`final-results.md`](../results/final-results.md) contain every explanation type for that encounter, verbatim.

## E5 — Coverage of the audiences

**Question.** Is every audience served by the explanation contract (R5, R6), and what do the delivered explanations actually contain? Paper, Section 5.4.

**Coverage at design time (structural).** The coverage matrix generated by T6 ([`generated/service/coverage.json`](../generated/service/coverage.json)) shows every audience served, and removing an audience's last explanation type is blocked at design time by `C4_AudienceCovered` (mutant M12 of [E2](#e2--fault-detection-by-mutation-analysis)).

**Coverage in substance.** It depends on the source documents. [`substantive_coverage.py`](../xaikg-pipeline/xaikg/eval/substantive_coverage.py) analyzes the 1,574 logged explanations of the current service version (records whose model fingerprints equal the service's generation manifest).

**Run.** `make coverage`. **Results:** [`results/e5-substantive-coverage.md`](../results/e5-substantive-coverage.md), [`e5-substantive-coverage.json`](../results/e5-substantive-coverage.json).

| Audience | Explanation type | Category | Explanations | With facts |
|---|---|---|---|---|
| patient | PlainLanguageContrast | contrastive | 200 | 199 |
| patient | ModifiableFactors | counterfactual | 58 | 58 |
| clinician | CausalEvidence | causal | 200 | 199 |
| clinician | ModifiableFactors | counterfactual | 58 | 58 |
| clinician | AttributionReport | feature attribution | 200 | 199 |
| quality officer | CausalEvidence | causal | 200 | 199 |
| quality officer | ModifiableFactors | counterfactual | 58 | 58 |
| quality officer | GuidelineCompliance | rule-based | 200 | 92 |
| auditor | GuidelineCompliance | rule-based | 200 | 92 |
| auditor | AttributionReport | feature attribution | 200 | 199 |

**Result.**

- The contrastive, causal and attribution explanations contain evidence for 199 of the 200 encounters.
- Every counterfactual explanation contains advice, restricted to modifiable entities: no fact concerns a non-modifiable entity.
- Guideline-compliance explanations found an applicable recommendation in **184 of 400** cases (46%), namely for every encounter whose conditions a guideline in the graph covers. For the others, mostly circulatory, respiratory or genitourinary cases, the service states that no applicable guideline was found.

**Answer.** Coverage is bounded by the knowledge in the source documents, and missing evidence is declared rather than invented.

**Note on re-running.** `make e4` appends a new run to the explanation log. Since both runs share the same service fingerprints, `make coverage` would count them together: start from an empty log when re-running E4 and E5 (see [reproduce.md](reproduce.md)).

## E6 — Budgets and grounding of the attributed factors

**Question.** Do the delivered explanations respect the presentation budget of their audience, and are the factors the predictor relies on backed by validated evidence? Paper, Section 5.4.

**Protocol.** Computed on the same 200 encounters and 1,574 explanations as [E4](#e4--traceability-of-the-delivered-explanations). For the budgets, the facts and words of every explanation are compared with the budget of its audience. For the grounding, the five strongest positive SHAP attributions of each encounter are checked: is the feature active and bound to a graph entity, and does that entity have validated evidence?

**Run.** `make e4` ([`e4_e6_explanations.py`](../xaikg-pipeline/xaikg/eval/e4_e6_explanations.py)). **Results:** [`results/e4-e6-explanations.md`](../results/e4-e6-explanations.md).

**Budgets.** No explanation exceeded its budget (0 violations). Mean facts per explanation: patient 2.98 (budget 3), clinician 9.12 (10), quality officer 4.49 (6), auditor 11.74 (full provenance, up to 50).

**Grounding of the attributed factors.**

| Measure | Value |
|---|---|
| strongest positive attributions examined (top 5 per encounter) | 381 |
| active and bound to a graph entity | 289 (75.9%) |
| … of which have validated evidence | 242 (83.7%) |

Bound entities without any evidence in the graph: *admission from the emergency room*, *diabetes medication prescribed*, *high number of laboratory procedures*, *musculoskeletal disease*, *prior emergency visits*. Such factors are reported as "none", and evidence that exists but does not fit the budget is reported as omitted, so no factor with evidence is ever presented as lacking it.
