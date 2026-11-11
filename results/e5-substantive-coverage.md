# E5 - Substantive coverage of the delivered explanations

1574 explanations of the current service version (explanation log records whose model fingerprints equal the generation manifest of the service).

## Explanations per audience and explanation type

| Audience | Explanation type | Category | Total | With facts | Without facts |
|---|---|---|---|---|---|
| auditor | AttributionReport | FEATURE_ATTRIBUTION | 200 | 199 | 1 |
| auditor | GuidelineCompliance | RULE_BASED | 200 | 92 | 108 |
| clinician | AttributionReport | FEATURE_ATTRIBUTION | 200 | 199 | 1 |
| clinician | CausalEvidence | CAUSAL | 200 | 199 | 1 |
| clinician | ModifiableFactors | COUNTERFACTUAL | 58 | 58 | 0 |
| patient | ModifiableFactors | COUNTERFACTUAL | 58 | 58 | 0 |
| patient | PlainLanguageContrast | CONTRASTIVE | 200 | 199 | 1 |
| quality_officer | CausalEvidence | CAUSAL | 200 | 199 | 1 |
| quality_officer | GuidelineCompliance | RULE_BASED | 200 | 92 | 108 |
| quality_officer | ModifiableFactors | COUNTERFACTUAL | 58 | 58 | 0 |

## Rule-based explanations

- GuidelineCompliance: 184/400 non-empty (share 0.46); 394 of them concern an encounter with at least one active condition.

## Counterfactual explanations

- ModifiableFactors, clinician: 36 distinct texts for 58 explanations (58 distinct decisions, 3 distinct fact sets).
- ModifiableFactors, patient: 8 distinct texts for 58 explanations (58 distinct decisions, 6 distinct fact sets).
- ModifiableFactors, quality_officer: 34 distinct texts for 58 explanations (58 distinct decisions, 5 distinct fact sets).
- Explanations with a fact about a non-modifiable entity: 0 (14 advised entities checked against the graph; facts without an advised entity: 0).

## Attribution reports

- 200 decisions with reports for more than one audience; 1764 factor rows in total.
- Rows reported as "none" although another audience's report for the same decision lists facts: 0.
- Rows reported as "none" although facts were available to the report: 0.

