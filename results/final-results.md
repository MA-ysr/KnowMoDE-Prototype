# Final results

All figures are produced by the scripted experiments of this artifact from the five M1 models of the diabetes readmission use case, the 438-document corpus, the LLM response cache and the loaded knowledge graph. Detailed outputs: `e0-context.md`, `e2-mutation-detection.md`, `e4-e6-explanations.md`, `e5-substantive-coverage.md` (and their `.json` versions), `explanations/explanations.jsonl` and `../generated/validated/rejection-report.json`. The design-time check evaluates 113 invariants of C1-C5 on the five models: 0 errors, 0 critiques.

## E0 - Corpus, extraction, validation and knowledge graph

| Aspect | Value |
|---|---|
| Corpus documents | 438 extracted: 12 openFDA drug labels, 58 MedlinePlus health topics, 362 PubMed abstracts (305 on readmission risk factors, 57 practice guidelines, consensus statements and standards of care on inpatient diabetes management and hospital discharge; 5 abstracts belong to both collections), 1 full-text paper |
| Extraction tasks | 4 (drug labels, patient education, literature, guidelines), one schema-aware prompt each |
| LLM usage | 634 calls for 635 chunks (1 chunk without a response), 2,227,893 input and 593,734 output tokens, cost 0 (free tier) |
| Items extracted | 3,558 entities and 1,512 relations; 99.7 % of the spans reported by the LLM were re-located by exact search |
| Validation (T2) | 3,539 entities and 1,231 relations accepted, 300 items rejected (acceptance 0.941) |
| Knowledge graph | 1,720 nodes and 6,216 relationships |
| `Recommendation` nodes | 71 |
| `APPLIES_TO` edges | 49 (diabetes 18, hyperglycemia 6, other conditions 25) |
| Entities declared modifiable in the vocabulary | 29 present in the graph (15 drugs and drug classes, 14 care processes and treatment factors) |
| Predictor | HistGradientBoosting, AUROC 0.6466, AUPRC 0.1702, 69,973 patients (52,479 train, 17,494 test), SHAP additivity error below 1e-14 |

Rejections by first failing validation rule:

| Rule | Rejected items |
|---|---|
| relation_type_and_endpoints_in_schema | 137 |
| relation_evidence_grounded_in_source | 107 |
| relation_endpoints_accepted | 35 |
| mention_grounded_in_source | 19 |
| relation_confidence_above_threshold | 2 |
| Total | 300 |

Graph nodes by label: Condition 564, RiskFactor 330, ClinicalOutcome 185, Drug 136, Recommendation 71, LabTest 36, DrugClass 24, SourceDocument 369, ExtractionRun 5.

## E2 - Design-time fault detection

22 mutants of the valid models, each injecting one modelling fault: 22 blocked before any transformation, 22 by the intended invariant (2 of them as unresolved cross-model references at load time). Mean check time 1.6 s. The two invariants of the counterfactual contract each have a mutant:

| Mutant | Fault | Caught by |
|---|---|---|
| M21 | the counterfactual explanation type also runs a pattern not declared actionable | C4_CounterfactualPatternsActionable |
| M22 | a pattern is declared actionable without filtering on the modifiability property | C1_ActionablePatternFiltersModifiable |

## E4 - Traceability

200 held-out encounters (58 predicted at high risk, 142 at low risk), every explanation type the contract grants to the predicted class, for every audience of the type.

| Measure | Value |
|---|---|
| Explanations delivered | 1,574 |
| Explanations with at least one fact | 1,353 |
| Complete provenance chains (fact, source document and span, extraction run, validation policy) | 1,353 of 1,353 |
| Mean facts traced per explanation | 10.43 |

## E5 - Coverage

### Structural coverage (generated contract)

| Audience | PlainLanguageContrast | CausalEvidence | ModifiableFactors | GuidelineCompliance | AttributionReport |
|---|---|---|---|---|---|
| patient | yes | - | yes | - | - |
| clinician | - | yes | yes | - | yes |
| quality_officer | - | yes | yes | yes | - |
| auditor | - | - | - | yes | yes |

11 endpoints (10 explanation endpoints and the trace endpoint), no uncovered audience.

### Substantive coverage (explanation log of the service version)

| Audience | Explanation type | Total | With facts | Without facts |
|---|---|---|---|---|
| patient | PlainLanguageContrast | 200 | 199 | 1 |
| patient | ModifiableFactors | 58 | 58 | 0 |
| clinician | CausalEvidence | 200 | 199 | 1 |
| clinician | ModifiableFactors | 58 | 58 | 0 |
| clinician | AttributionReport | 200 | 199 | 1 |
| quality_officer | CausalEvidence | 200 | 199 | 1 |
| quality_officer | ModifiableFactors | 58 | 58 | 0 |
| quality_officer | GuidelineCompliance | 200 | 92 | 108 |
| auditor | GuidelineCompliance | 200 | 92 | 108 |
| auditor | AttributionReport | 200 | 199 | 1 |

| Metric | Value |
|---|---|
| Non-empty `GuidelineCompliance` explanations | 184 of 400 (0.46) |
| `GuidelineCompliance` explanations of encounters with an active condition for which the knowledge graph holds a guideline statement | 184, all non-empty |
| `GuidelineCompliance` explanations without facts | 216, all for encounters whose active conditions have no guideline statement in the graph (mainly circulatory, respiratory and genitourinary disease, heart failure) |
| Distinct `ModifiableFactors` texts (58 high-risk decisions) | patient 8, clinician 36, quality officer 34 |
| `ModifiableFactors` explanations containing a fact about a non-modifiable entity | 0 (14 advised entities checked against the graph) |
| Factor rows of attribution reports shown as "none" while facts exist (clinician and auditor reports of the same 200 decisions paired) | 0 of 1,764 rows |

The counterfactual advice is ranked by its relation to the encounter's active entities (the entity is active, it treats or interacts with an active entity, or its evidence studies the active entities), and recommendations follow the encounter's conditions. The graph holds 10 modifiable protective factors linked to the outcome, so the 10-fact clinician budget contains most of them for every encounter; what varies between encounters is their order, the reasons given, and the guideline recommendations.

## E6 - Grounding and presentation budgets

| Measure | Value |
|---|---|
| Budget violations | 0 |
| Attributed features (top 5, positive) that are active and bound to a KG entity | 289 of 381 (0.759) |
| Of those, with at least one validated evidence path | 242 of 289 (0.837) |
| Mean facts per explanation | patient 2.98 (budget 3), clinician 9.12 (budget 10), quality officer 4.49 (budget 6), auditor 11.74 (budget 50) |
| Bound entities without evidence in the graph | admission from the emergency room, diabetes medication prescribed, high number of laboratory procedures, musculoskeletal disease, prior emergency visits |

## Example: every explanation type for one high-risk encounter

Encounter predicted at high risk of readmission within 30 days (p = 0.697); active conditions: musculoskeletal disease, circulatory disease, diabetes. Verbatim from the explanation log.

### PlainLanguageContrast, patient (explanation 29c91de8-da62-4125-9b3a-84e91d16c4ac)

```
Your care team's risk tool estimates that you have a higher chance than similar patients of needing to come back to the hospital within 30 days. The main reasons, according to published medical sources:
- Heart or blood vessel disease: linked to a higher chance of returning to the hospital (source: PubMed article 34789421).
- Leaving the hospital for a nursing or rehabilitation facility: linked to a higher chance of returning to the hospital (source: PubMed article 25611424).
- Older age: linked to a higher chance of returning to the hospital (source: PubMed article 38937276).
This is not a diagnosis. Your doctor or nurse can explain what these factors mean for you and what you can do about them.
```

### CausalEvidence, clinician (explanation 98983f35-3f91-44dd-94e1-16d000d9de88)

```
**Prediction:** high risk of readmission within 30 days (p = 0.70)
**Attributed factors** (top 5): discharge_disposition_id = 22 (+1.110), diabetesMed = Yes (+0.067), age = [80-90) (+0.056), diag_2 = 401 (+0.015), number_outpatient = 3 (+0.010)
**Knowledge-graph evidence**
1. RiskFactor "discharge to a skilled nursing facility" INCREASES_RISK_OF hospital readmission within 30 days   evidence: pubmed/25611424.txt [chars 1234-1537], confidence 0.95, fact f_4626f0e35ae55462
2. RiskFactor "discharge to a skilled nursing facility" INCREASES_RISK_OF hospital readmission within 30 days   evidence: pubmed/29506837.txt [chars 1408-1788], confidence 0.90, fact f_8c4103233ddca0a1
3. RiskFactor "discharge to a skilled nursing facility" INCREASES_RISK_OF hospital readmission within 30 days   evidence: pubmed/32521438.txt [chars 852-1379], confidence 0.90, fact f_9894eddf59d98b91
4. RiskFactor "discharge to a skilled nursing facility" INCREASES_RISK_OF hospital readmission within 30 days   evidence: pubmed/30846065.txt [chars 1253-1664], confidence 0.90, fact f_9affcafa9d4a4417
5. RiskFactor "older age" INCREASES_RISK_OF hospital readmission within 30 days   evidence: pubmed/38937276.txt [chars 1332-1599], confidence 0.95, fact f_0d5eabb2c792cf9e
6. RiskFactor "older age" INCREASES_RISK_OF hospital readmission within 30 days   evidence: pubmed/28041771.txt [chars 1397-1518], confidence 0.90, fact f_3423e2cc665c5cd2
7. RiskFactor "older age" INCREASES_RISK_OF hospital readmission within 30 days   evidence: pubmed/29436275.txt [chars 1413-1661], confidence 0.90, fact f_a9da2286445fe8b5
8. Condition "circulatory disease" INCREASES_RISK_OF hospital readmission within 30 days   evidence: pubmed/34789421.txt [chars 1743-2014], confidence 0.95, fact f_9ff042885462abea
9. Condition "circulatory disease" INCREASES_RISK_OF hospital readmission within 30 days   evidence: pubmed/28118530.txt [chars 1971-2120], confidence 0.90, fact f_57b67a9c7798c919
10. Condition "circulatory disease" INCREASES_RISK_OF hospital readmission within 30 days   evidence: pubmed/31461001.txt [chars 1541-1640], confidence 0.90, fact f_bbc8290417463081
(4 further fact(s) for these factors omitted by the presentation budget.)
```

### ModifiableFactors, patient (explanation 7c0a3848-37ba-4909-a2d0-73047ba9f1d4)

```
**What could lower this risk** (patient view)
- A guideline (National Institute of Diabetes and Digestive and Kidney Diseases) recommends insulin for people with diabetes. Your care team can discuss it with you (source: MedlinePlus health topic 'diabetes').
- A guideline (Endocrine Society) recommends insulin for people with diabetes. Your care team can discuss it with you (source: PubMed article 22223765).
- Support from a care-transition team after leaving the hospital: linked to a lower chance of returning to the hospital (source: PubMed article 38872270).
```

### ModifiableFactors, clinician (explanation 08492b8a-f36f-49bb-bb9e-720daad91826)

```
**What could lower this risk** (clinician view)
- take daily doses of insulin, either by injection or through a special pump (National Institute of Diabetes and Digestive and Kidney Diseases; applies to diabetes; concerns: insulin) [source: medlineplus/diabetes.txt, confidence 0.95, fact f_2a53dc0520e1fa49]
- implement a standardized subcutaneous insulin order set promoting scheduled basal and nutritional insulin therapy for inpatient management of diabetes (Endocrine Society; applies to diabetes; concerns: insulin) [source: pubmed/22223765.txt, confidence 0.90, fact f_1a915bc6507c5343]
- adjust insulin dosage when adding SGLT-2 inhibitors or GLP-1 receptor agonists to avoid hypoglycaemia (Hipertension y riesgo vascular; applies to diabetes; concerns: sglt2 inhibitors, glp-1 receptor agonists, insulin) [source: pubmed/39551547.txt, confidence 0.90, fact f_a421568d226051a9]
- use early identification of patients in need of education, implementation of a clinical pathway, and clear instructions about medications and follow-up appointments to ensure an effective diabetes discharge (Endocrine practice; applies to diabetes; concerns: post-discharge follow-up, diabetes education) [source: pubmed/19364697.txt, confidence 0.90, fact f_aa4d4270e93a395c]
- patients should receive structured education on blood glucose monitoring, nutritional strategies, and recognition and management of hypoglycemia (The Medical clinics of North America; applies to diabetes; concerns: diabetes education) [source: pubmed/42036164.txt, confidence 0.88, fact f_4a281bb4a4101648]
- transitional care program (RiskFactor) is associated with a lower risk of hospital readmission within 30 days (5 sources); related to this encounter's diabetes, circulatory disease, polypharmacy [source: pubmed/38872270.txt, confidence 0.98, fact f_41c3e1f387aed471]
- HbA1c measured during admission (RiskFactor) is associated with a lower risk of hospital readmission within 30 days (5 sources); related to this encounter's change of diabetes medication, diabetes [source: papers/strack2014.txt, confidence 0.95, fact f_e1a807a80031afb1]
- diabetes education (RiskFactor) is associated with a lower risk of hospital readmission within 30 days (4 sources); related to this encounter's diabetes [source: pubmed/40403266.txt, confidence 0.95, fact f_b3b2b0d1f99c45cd]
- insulin continuation after discharge (RiskFactor) is associated with a lower risk of hospital readmission within 30 days (2 sources); related to this encounter's diabetes [source: pubmed/22440990.txt, confidence 0.90, fact f_96415426ccc4c1e1]
- medication reconciliation (RiskFactor) is associated with a lower risk of hospital readmission within 30 days (1 source); related to this encounter's diabetes [source: pubmed/29931547.txt, confidence 0.85, fact f_1a2dea1bb773a121]
```

### GuidelineCompliance, quality officer (explanation e8a81ba8-9ea2-41b0-9be6-8f97baca9871)

```
**Guideline statements applying to this encounter** (patient conditions: musculoskeletal disease, circulatory disease, diabetes)
| Condition | Recommendation | Source | Strength | Recommends | Provenance |
|---|---|---|---|---|---|
| diabetes | have an exam every year | MedlinePlus | - | - | medlineplus/eye-care.txt (fact f_286b8b0f1f634926, conf. 0.95) |
| diabetes | take daily doses of insulin, either by injection or through a special pump | National Institute of Diabetes and Digestive and Kidney Diseases | - | insulin | medlineplus/diabetes.txt (fact f_2a53dc0520e1fa49, conf. 0.95) |
| diabetes | People with diabetes should get regular screenings for kidney disease. | MedlinePlus | - | - | medlineplus/diabetic-kidney-problems.txt (fact f_80ac2748a9651601, conf. 0.95) |
| diabetes | refer diabetic patients to a diabetologist postoperatively and after discharge if HbA1c is >8% | Anaesthesia, critical care & pain medicine | - | HbA1c > 8% | pubmed/29317312.txt (fact f_294de5298d7f833d, conf. 0.92) |
| diabetes | implement a standardized subcutaneous insulin order set promoting scheduled basal and nutritional insulin therapy for inpatient management of diabetes | Endocrine Society | - | scheduled basal and nutritional insulin therapy, insulin | pubmed/22223765.txt (fact f_1a915bc6507c5343, conf. 0.90) |
| diabetes | administer influenza vaccinations to patients with diabetes mellitus | Acta medica Indonesiana | - | - | pubmed/38561880.txt (fact f_2294d54fbddd215e, conf. 0.90) |
```

### AttributionReport, clinician (explanation 1093040f-26d5-4a9a-a947-8328715c0af8)

```
**Feature attribution report** - model readmission_gbm 0.1.0 (SHAP), prediction high risk of readmission within 30 days p = 0.697
| Feature | Value | Attribution | KG entity | Grounded evidence |
|---|---|---|---|---|
| discharge_disposition_id | 22 | +1.1099 | discharge to a skilled nursing facility | 4 fact(s): f_4626f0e35ae55462 (pubmed/25611424.txt); f_8c4103233ddca0a1 (pubmed/29506837.txt); f_9894eddf59d98b91 (pubmed/32521438.txt); f_9affcafa9d4a4417 (pubmed/30846065.txt) + 2 omitted (budget) |
| diabetesMed | Yes | +0.0667 | diabetes medication prescribed | none |
| age | [80-90) | +0.0556 | older age | 3 fact(s): f_0d5eabb2c792cf9e (pubmed/38937276.txt); f_3423e2cc665c5cd2 (pubmed/28041771.txt); f_a9da2286445fe8b5 (pubmed/29436275.txt) + 1 omitted (budget) |
| diag_2 | 401 | +0.0147 | circulatory disease | 3 fact(s): f_9ff042885462abea (pubmed/34789421.txt); f_57b67a9c7798c919 (pubmed/28118530.txt); f_bbc8290417463081 (pubmed/31461001.txt) + 1 omitted (budget) |
| number_outpatient | 3 | +0.0103 | prior outpatient visits | none |
"none" means the knowledge graph holds no validated evidence for the factor; facts that exist but do not fit the presentation budget are reported as omitted. Nothing is invented to fill the table.
```
