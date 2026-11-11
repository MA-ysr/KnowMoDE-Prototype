# E0 - Context of the artefact

| Aspect | Value |
|---|---|
| Corpus documents | gold-bc5cdr: 1, medlineplus: 58, openfda: 12, papers: 1, pubmed: 362, tabular: 2 |
| LLM calls / tokens (responses the raw models are built from) | 634 calls for 635 chunks (1 chunk without a response), 2,227,893 input + 593,734 output tokens, cost 0 (free tier) |
| Calls per task and model | drug_label_extraction (gemini/gemini-3.5-flash-lite): 146; guideline_extraction (gemini/gemini-3.5-flash-lite): 61; literature_extraction (gemini/gemini-3.1-flash-lite): 79; literature_extraction (gemini/gemini-3.5-flash-lite): 263; patient_education_extraction (gemini/gemini-3.5-flash-lite): 85 |
| LLM items returned (runs that wrote the raw models) | 5,070; spans re-located by exact search: 5,055 (99.7%) |
| Items in the raw extraction models (T2 input) | 3,558 entities + 1,512 relations |
| Validation (T2) | 3,558 entities, 1,512 relations in; 3,539 / 1,231 accepted; 300 rejected (acceptance 0.941) |
| Graph | {'nodes': {'ClinicalOutcome': 185, 'Condition': 564, 'Drug': 136, 'DrugClass': 24, 'ExtractionRun': 5, 'LabTest': 36, 'Recommendation': 71, 'RiskFactor': 330, 'SourceDocument': 369}, 'relationships': {'APPLIES_TO': 49, 'BELONGS_TO_CLASS': 34, 'CONTRAINDICATED_IN': 60, 'EXTRACTED_FROM': 3510, 'INCREASES_RISK_OF': 510, 'INDICATES': 11, 'INTERACTS_WITH': 127, 'MAY_CAUSE': 281, 'PRODUCED_BY': 1483, 'RECOMMENDS': 60, 'REDUCES_RISK_OF': 75, 'TREATS': 16}} |
| Predictor | AUROC 0.6466, AUPRC 0.1702, positive rate 0.0897, 69,973 patients |

## Run times (s)

| Step | Seconds |
|---|---|
| check (C1-C5) | 1.87 |
| generate (check+T1+T3+T4+T6) | 2.09 |
| t2 (validator generation + validation of all raw extractions) | 17.3 |
| t5 (loader generation) | 1.97 |

## Generated vs hand-written (non-blank lines)

| Artefact | Files | Lines |
|---|---|---|
| models (M1, authored per use case) | 5 | 1,246 |
| metamodels (M2) | 4 | 834 |
| constraints C1-C5 (EVL) | 1 | 535 |
| transformations T1-T6 (ETL/EGL/EGX) | 16 | 780 |
| MDE runtime (Java, incl. tests) | 13 | 1,213 |
| Python runtime kernel (corpus, LLM, kg, ml, explain, cli) | 27 | 1,984 |
| Python evaluation scripts + tools | 11 | 1,456 |
| generated: prompts + side-cars (T4) | 9 | 721 |
| generated: graph schema + DDL (T1, T3) | 2 | 203 |
| generated: validator (T2a) + loader (T5) | 2 | 5,685 |
| generated: explanation service (T6) | 14 | 432 |

Generated artefacts: 7,041 lines. Reusable framework (metamodels, constraints, transformations, Java runtime): 3,362 lines. Model-independent Python kernel: 1,984 lines. Use-case models authored by the domain team: 1,246 lines of XMI.
