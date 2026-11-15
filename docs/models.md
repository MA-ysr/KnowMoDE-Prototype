# The case-study models

The case study explains **30-day readmission risk for patients with diabetes** to four audiences (paper, Section 5.1). Its five models are in [`models/diabetes-readmission/`](../models/diabetes-readmission/); each conforms to one package of the [XAI-KG metamodel](metamodel.md) and is written by one role.

| Model | File | Written by | Root class | Content |
|---|---|---|---|---|
| **KG Schema** | [`kg-schema.xmi`](../models/diabetes-readmission/kg-schema.xmi) | domain experts | `KGSchemaDefinition` | 7 concepts, 15 relations, 16 properties, 67 canonical entities (31 modifiable) with 509 aliases, 8 read-only query patterns |
| **LLM Pipeline** | [`extraction-pipeline.xmi`](../models/diabetes-readmission/extraction-pipeline.xmi) | AI engineers | `LLMPipelineConfig` | 4 extraction tasks, each with its source collection, LLM, sampling parameters, chunking strategy and prompt template (8 few-shot examples in total) |
| **Validation Policy** | [`validation-policy.xmi`](../models/diabetes-readmission/validation-policy.xmi) | compliance officers | `ValidationConfig` | 12 validation rules with OCL-style expressions, confidence threshold 0.7 |
| **Explainability** | [`explainability.xmi`](../models/diabetes-readmission/explainability.xmi) | compliance officers | `ExplainabilityConfig` | 4 audiences with presentation budgets, 5 explanation types with their templates, the trace pattern for full provenance |
| **Decision Binding** | [`decision-bindings.xmi`](../models/diabetes-readmission/decision-bindings.xmi) | AI engineers | `DecisionBindingConfig` | the predictor (`AIModelSpec`, 33 features, SHAP), 2 decision classes, 33 feature bindings |

## KG Schema

| Concept | Represents | Canonical entities (modifiable) | Relations (as source) |
|---|---|---|---|
| Drug | medication, by generic name | 16 (16) | `TREATS`, `MAY_CAUSE`, `CONTRAINDICATED_IN` a Condition; `INTERACTS_WITH` a Drug; `BELONGS_TO_CLASS` |
| DrugClass | pharmacological class | – | – |
| Condition | disease or clinical state, ICD-9 range | 14 | `INCREASES_RISK_OF` an outcome |
| LabTest | test with abnormal level  | 6 | `INDICATES` a Condition |
| RiskFactor | patient or care-process characteristic | 28 (15) | `INCREASES_RISK_OF`, `REDUCES_RISK_OF` an outcome |
| ClinicalOutcome | outcome with time window | 3 | – |
| Recommendation | guideline statement, issuer, strength | – | `APPLIES_TO` a Condition; `RECOMMENDS` a LabTest, Drug or RiskFactor |

The 31 modifiable entities are the 16 medications and 15 care-process factors such as polypharmacy or transitional care. Modifiability is **declared** by domain experts, not extracted. The query patterns `counterfactual_recommendations` and `protective_factors` are marked `actionableOnly`, so they may only return modifiable entities (checked by `C1_ActionablePatternFiltersModifiable`).

## LLM Pipeline

| Extraction task | Source collection | Chunking (size / overlap / splitter) |
|---|---|---|
| `drug_label_extraction` | `corpus/openfda` | 4000 / 300 / paragraph |
| `patient_education_extraction` | `corpus/medlineplus` | 4000 / 300 / paragraph |
| `literature_extraction` | `corpus/pubmed`, `corpus/papers` | 3000 / 200 / sentence |
| `guideline_extraction` | `corpus/pubmed/guidelines` | 3000 / 200 / sentence |

All tasks use temperature 0.1 and Gemini models; the documents are described in [datasets.md](datasets.md).

**Chunking.** A document is sent to the LLM in pieces (*chunks*). The *splitter* is the unit that is never cut: whole paragraphs (`PARAGRAPH`) or whole sentences (`SENTENCE`). The chunker packs consecutive units into a chunk as long as the chunk stays within *size* characters; the next chunk then starts by repeating the last units of the previous one, up to *overlap* characters, so that a fact stated across a chunk boundary appears complete in at least one chunk. Example: a drug label of about 10,000 characters, with size 4,000, overlap 300 and paragraph splitting, gives three or four chunks of at most 4,000 characters each, and each new chunk starts with the last paragraph(s) of the previous one when they total 300 characters or less. The repeated text is also why a few relations are extracted twice and later merged. Implementation: [`chunking.py`](../xaikg-pipeline/xaikg/llm/chunking.py).

## Validation Policy

| Rule | Type | Scope | Severity |
|---|---|---|---|
| `entity_type_in_schema` | schema conformance | entity | blocking |
| `entity_has_id_and_mention` | schema conformance | entity | blocking |
| `required_properties_present` | schema conformance | entity | blocking |
| `declared_properties_only` | schema conformance | entity | warning |
| `mention_grounded_in_source` | grounding | entity | blocking |
| `entity_confidence_above_threshold` | confidence | entity | blocking |
| `entity_provenance_complete` | provenance | entity | blocking |
| `relation_type_and_endpoints_in_schema` | schema conformance | relation | blocking |
| `relation_endpoints_accepted` | schema conformance | relation | blocking |
| `relation_evidence_grounded_in_source` | grounding | relation | blocking |
| `relation_confidence_above_threshold` | confidence | relation | blocking |
| `max_cardinality_respected` | cardinality | relation | warning |

T2a compiles each rule into one constraint of the generated validator ([transformations.md](transformations.md)).

## Explainability (the explanation contract)

| Audience | Budget | Explanation types served |
|---|---|---|
| patient | 3 facts, 120 words, plain language | PlainLanguageContrast, ModifiableFactors |
| clinician | 10 facts, codes allowed | CausalEvidence, ModifiableFactors, AttributionReport |
| quality officer | 6 facts, codes allowed | CausalEvidence, ModifiableFactors, GuidelineCompliance |
| auditor | full provenance (up to 50 facts) | GuidelineCompliance, AttributionReport |

| Explanation type | Category |
|---|---|
| PlainLanguageContrast | contrastive |
| CausalEvidence | causal |
| ModifiableFactors | counterfactual (actionable patterns only) |
| GuidelineCompliance | rule-based |
| AttributionReport | feature attribution |

## Decision Binding

The predictor is a gradient-boosting classifier explained with SHAP . Two decision classes, `HighReadmissionRisk` and `LowReadmissionRisk` (threshold 0.5), grant explanation types: the high-risk class grants all five, the low-risk class four (no counterfactual advice), which is why E5 counts 58 counterfactual explanations per audience, one per high-risk encounter. The 33 features are bound to 14 medications, 14 utilization, care-process or demographic factors, three diagnosis codes mapped to condition groups through ICD-9 ranges, and two laboratory levels.

## Mutants (experiment E2)

[`models/mutants/`](../models/mutants/) holds 22 copies of the five models, each with one injected design fault, generated by [`make_mutants.py`](../xaikg-pipeline/tools/make_mutants.py). They are used in experiment [E2](experiments.md#e2--fault-detection-by-mutation-analysis).
