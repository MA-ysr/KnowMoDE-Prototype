# E4-E6 - Explanations on a test sample

200 test encounters; decision classes {'LowReadmissionRisk': 142, 'HighReadmissionRisk': 58}; graph {'ClinicalOutcome': 185, 'Condition': 564, 'Drug': 136, 'DrugClass': 24, 'ExtractionRun': 5, 'LabTest': 36, 'Recommendation': 71, 'RiskFactor': 330, 'SourceDocument': 369}

E4 traceability: 1353/1353 explanations with facts have a complete provenance chain (rate 1.0); mean facts traced per explanation 10.43.
E6 grounding: 289/381 top-5 positive features are active and bound to a KG entity (rate 0.759); 242 of those have at least one validated evidence path (rate 0.837).
Budget violations: 0. Mean facts per audience: {'patient': 2.98, 'clinician': 9.12, 'quality_officer': 4.49, 'auditor': 11.74}.
Bound entities without any evidence in the KG: ['admission from the emergency room', 'diabetes medication prescribed', 'high number of laboratory procedures', 'musculoskeletal disease', 'prior emergency visits']

## Every explanation type for one high-risk encounter

### PlainLanguageContrast, audience `patient` (explanation 29c91de8-da62-4125-9b3a-84e91d16c4ac)

```
Your care team's risk tool estimates that you have a higher chance than similar patients of needing to come back to the hospital within 30 days. The main reasons, according to published medical sources:
- Heart or blood vessel disease: linked to a higher chance of returning to the hospital (source: PubMed article 34789421).
- Leaving the hospital for a nursing or rehabilitation facility: linked to a higher chance of returning to the hospital (source: PubMed article 25611424).
- Older age: linked to a higher chance of returning to the hospital (source: PubMed article 38937276).
This is not a diagnosis. Your doctor or nurse can explain what these factors mean for you and what you can do about them.
```

### CausalEvidence, audience `clinician` (explanation 98983f35-3f91-44dd-94e1-16d000d9de88)

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

### CausalEvidence, audience `quality_officer` (explanation 2354c89b-6ff7-4d86-b31d-9c5e19092e12)

```
**Prediction:** high risk of readmission within 30 days (p = 0.70)

**Attributed factors** (top 5): discharge_disposition_id = 22 (+1.110), diabetesMed = Yes (+0.067), age = [80-90) (+0.056), diag_2 = 401 (+0.015), number_outpatient = 3 (+0.010)
**Knowledge-graph evidence**
1. RiskFactor "discharge to a skilled nursing facility" INCREASES_RISK_OF hospital readmission within 30 days   evidence: pubmed/25611424.txt [chars 1234-1537], confidence 0.95, fact f_4626f0e35ae55462
2. RiskFactor "discharge to a skilled nursing facility" INCREASES_RISK_OF hospital readmission within 30 days   evidence: pubmed/29506837.txt [chars 1408-1788], confidence 0.90, fact f_8c4103233ddca0a1
3. RiskFactor "older age" INCREASES_RISK_OF hospital readmission within 30 days   evidence: pubmed/38937276.txt [chars 1332-1599], confidence 0.95, fact f_0d5eabb2c792cf9e
4. RiskFactor "older age" INCREASES_RISK_OF hospital readmission within 30 days   evidence: pubmed/28041771.txt [chars 1397-1518], confidence 0.90, fact f_3423e2cc665c5cd2
5. Condition "circulatory disease" INCREASES_RISK_OF hospital readmission within 30 days   evidence: pubmed/34789421.txt [chars 1743-2014], confidence 0.95, fact f_9ff042885462abea
6. Condition "circulatory disease" INCREASES_RISK_OF hospital readmission within 30 days   evidence: pubmed/28118530.txt [chars 1971-2120], confidence 0.90, fact f_57b67a9c7798c919
(8 further fact(s) for these factors omitted by the presentation budget.)
```

### ModifiableFactors, audience `patient` (explanation 7c0a3848-37ba-4909-a2d0-73047ba9f1d4)

```
**What could lower this risk** (patient view)
- A guideline (National Institute of Diabetes and Digestive and Kidney Diseases) recommends insulin for people with diabetes. Your care team can discuss it with you (source: MedlinePlus health topic 'diabetes').
- A guideline (Endocrine Society) recommends insulin for people with diabetes. Your care team can discuss it with you (source: PubMed article 22223765).
- Support from a care-transition team after leaving the hospital: linked to a lower chance of returning to the hospital (source: PubMed article 38872270).
```

### ModifiableFactors, audience `clinician` (explanation 08492b8a-f36f-49bb-bb9e-720daad91826)

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

### ModifiableFactors, audience `quality_officer` (explanation a89eafba-6c81-48ac-803a-e9897a4adacf)

```
**What could lower this risk** (quality_officer view)
- take daily doses of insulin, either by injection or through a special pump (National Institute of Diabetes and Digestive and Kidney Diseases; applies to diabetes; concerns: insulin) [source: medlineplus/diabetes.txt, confidence 0.95, fact f_2a53dc0520e1fa49]
- implement a standardized subcutaneous insulin order set promoting scheduled basal and nutritional insulin therapy for inpatient management of diabetes (Endocrine Society; applies to diabetes; concerns: insulin) [source: pubmed/22223765.txt, confidence 0.90, fact f_1a915bc6507c5343]
- adjust insulin dosage when adding SGLT-2 inhibitors or GLP-1 receptor agonists to avoid hypoglycaemia (Hipertension y riesgo vascular; applies to diabetes; concerns: sglt2 inhibitors, glp-1 receptor agonists, insulin) [source: pubmed/39551547.txt, confidence 0.90, fact f_a421568d226051a9]
- transitional care program (RiskFactor) is associated with a lower risk of hospital readmission within 30 days (5 sources); related to this encounter's diabetes, circulatory disease, polypharmacy [source: pubmed/38872270.txt, confidence 0.98, fact f_41c3e1f387aed471]
- HbA1c measured during admission (RiskFactor) is associated with a lower risk of hospital readmission within 30 days (5 sources); related to this encounter's change of diabetes medication, diabetes [source: papers/strack2014.txt, confidence 0.95, fact f_e1a807a80031afb1]
- diabetes education (RiskFactor) is associated with a lower risk of hospital readmission within 30 days (4 sources); related to this encounter's diabetes [source: pubmed/40403266.txt, confidence 0.95, fact f_b3b2b0d1f99c45cd]
```

### GuidelineCompliance, audience `quality_officer` (explanation e8a81ba8-9ea2-41b0-9be6-8f97baca9871)

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

### GuidelineCompliance, audience `auditor` (explanation 260e8a3f-3832-4651-af68-9ea796ddef21)

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
| diabetes | People with diabetes usually have an A1C test at least twice a year. | MedlinePlus | - | A1C test | medlineplus/blood-glucose.txt (fact f_308fe933c477625e, conf. 0.90) |
| diabetes | monitor blood glucose for patients with diabetes and admission hyperglycemia | clinical practice guidelines | - | - | pubmed/40117466.txt (fact f_56c429ac46beeca9, conf. 0.90) |
| diabetes | refer patients to a diabetologist preoperatively if previously unknown diabetes or glycaemic imbalance (HbA1c <5% or >8%) is detected | Anaesthesia, critical care & pain medicine | - | HbA1c <5% or >8% | pubmed/29317312.txt (fact f_5c66fbca88d6210d, conf. 0.90) |
| diabetes | Be sure they are physically active | MedlinePlus | - | - | medlineplus/diabetes-in-children-and-teens.txt (fact f_6ba21c498884decb, conf. 0.90) |
| diabetes | refer patients to a diabetologist during hospitalisation for recognition of unknown diabetes, persisting glycaemic imbalance, or difficulty resuming chronic treatment | Anaesthesia, critical care & pain medicine | - | - | pubmed/29317312.txt (fact f_853349f7c3f57877, conf. 0.90) |
| diabetes | initiate or intensify outpatient diabetes regimen in hospitalized patients with newly diagnosed or poorly controlled type 2 diabetes | Current diabetes reports | - | - | pubmed/28573408.txt (fact f_89e0d149c1501b27, conf. 0.90) |
| diabetes | use custom therapeutic footwear in high-risk diabetic patients | Society for Vascular Surgery, American Podiatric Medical Association, and Society for Vascular Medicine | - | custom therapeutic footwear | pubmed/26804367.txt (fact f_91d8c83373bc38c1, conf. 0.90) |
| diabetes | adjust insulin dosage when adding SGLT-2 inhibitors or GLP-1 receptor agonists to avoid hypoglycaemia | Hipertension y riesgo vascular | - | sglt2 inhibitors, glp-1 receptor agonists, insulin | pubmed/39551547.txt (fact f_a421568d226051a9, conf. 0.90) |
| diabetes | use early identification of patients in need of education, implementation of a clinical pathway, and clear instructions about medications and follow-up appointments to ensure an effective diabetes discharge | Endocrine practice | - | implementation of a clinical pathway, post-discharge follow-up, diabetes education | pubmed/19364697.txt (fact f_aa4d4270e93a395c, conf. 0.90) |
| diabetes | Have them maintain a healthy weight | MedlinePlus | - | - | medlineplus/diabetes-in-children-and-teens.txt (fact f_cea847214a308145, conf. 0.90) |
| diabetes | patients should receive structured education on blood glucose monitoring, nutritional strategies, and recognition and management of hypoglycemia | The Medical clinics of North America | - | diabetes education | pubmed/42036164.txt (fact f_4a281bb4a4101648, conf. 0.88) |
| diabetes | take one of a few types of diabetes medicines if you are at high risk | National Institute of Diabetes and Digestive and Kidney Diseases | - | diabetes medicines | medlineplus/how-to-prevent-diabetes.txt (fact f_5b3b00c5c0a789c7, conf. 0.85) |
```

### AttributionReport, audience `clinician` (explanation 1093040f-26d5-4a9a-a947-8328715c0af8)

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

### AttributionReport, audience `auditor` (explanation 6319b44d-5136-443e-9740-98e3b09e4175)

```
**Feature attribution report** - model readmission_gbm 0.1.0 (SHAP), prediction high risk of readmission within 30 days p = 0.697

| Feature | Value | Attribution | KG entity | Grounded evidence |
|---|---|---|---|---|
| discharge_disposition_id | 22 | +1.1099 | discharge to a skilled nursing facility | 6 fact(s): f_4626f0e35ae55462 (pubmed/25611424.txt); f_8c4103233ddca0a1 (pubmed/29506837.txt); f_9894eddf59d98b91 (pubmed/32521438.txt); f_9affcafa9d4a4417 (pubmed/30846065.txt); f_bf6f1eb9b3a2b114 (pubmed/31542449.txt); f_f19542c3b754a95c (pubmed/26483156.txt) |
| diabetesMed | Yes | +0.0667 | diabetes medication prescribed | none |
| age | [80-90) | +0.0556 | older age | 4 fact(s): f_0d5eabb2c792cf9e (pubmed/38937276.txt); f_3423e2cc665c5cd2 (pubmed/28041771.txt); f_a9da2286445fe8b5 (pubmed/29436275.txt); f_e3b25f8d8c2a98cd (pubmed/27874940.txt) |
| diag_2 | 401 | +0.0147 | circulatory disease | 4 fact(s): f_9ff042885462abea (pubmed/34789421.txt); f_57b67a9c7798c919 (pubmed/28118530.txt); f_bbc8290417463081 (pubmed/31461001.txt); f_59fb1a0a6ae01d32 (pubmed/37535655.txt) |
| number_outpatient | 3 | +0.0103 | prior outpatient visits | none |

"none" means the knowledge graph holds no validated evidence for the factor; facts that exist but do not fit the presentation budget are reported as omitted. Nothing is invented to fill the table.
```

