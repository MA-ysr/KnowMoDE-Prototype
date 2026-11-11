# E1 - Schema evolution propagates through the chain (R2)

Baseline: 26 generated artefacts (prompts, side-cars, graph schema, DDL, validator, service files).

| Scenario | Model edits | Manual edits to generated artefacts | Check | Artefacts changed/added | Incomplete edit caught |
|---|---|---|---|---|---|
| S1_add_concept_and_relation: Add concept Procedure (name, cptCode) and relation UNDERGOES (Condition -> Procedure); target both in the literature task. | 4 | 0 | ok | 4: graph-schema.xmi, prompts/literature_extraction.json, prompts/literature_extraction.txt, schema.cypher | - |
| S2_rename_relation: Rename relation MAY_CAUSE to HAS_ADVERSE_EFFECT (name attribute); few-shot examples updated in the same model. | 2 | 0 | ok | 8: graph-schema.xmi, prompts/drug_label_extraction.json, prompts/drug_label_extraction.txt, prompts/literature_extraction.json, prompts/literature_extraction.txt, prompts/patient_education_extraction.json, prompts/patient_education_extraction.txt, schema.cypher | yes: C2_FewShotOutputsMentionOnlyTargetedTypes |
| S3_mark_property_explainable: Mark Condition.icd9Range as explainable. | 1 | 0 | ok | 10: graph-schema.xmi, prompts/drug_label_extraction.json, prompts/drug_label_extraction.txt, prompts/guideline_extraction.json, prompts/guideline_extraction.txt, prompts/literature_extraction.json, prompts/literature_extraction.txt, prompts/patient_education_extraction.json, prompts/patient_education_extraction.txt, schema.cypher | - |
