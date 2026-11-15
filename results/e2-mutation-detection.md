# E2 - Design-time detection of injected model faults

22/22 mutants blocked before any transformation; 22/22 caught by the expected constraint (or as an unresolved reference at load time). Mean check time 1.63 s.

| Mutant | Family | Fault | Blocked | Caught by |
|---|---|---|---|---|
| M01_concept_without_property | C1 | DrugClass loses its only property | yes | C1_ConceptHasProperty |
| M02_negative_cardinality | C1 | APPLIES_TO gets minCardinality -3 | yes | C1_CardinalitiesValid |
| M03_empty_query_template | C1 | guideline_rules loses its Cypher template (parameters cleared and template emptied) | yes | C1_PatternHasTemplate |
| M04_pattern_writes_graph | C1 | protective_factors template mutates the graph | yes | C1_PatternReadsOnly |
| M05_prompt_targets_undeclared_concept | C2 | drug_label task targets a concept that does not exist (dangling reference) | yes | unresolved reference (load time) |
| M06_prompt_relation_without_endpoint | C2 | drug_label task drops DrugClass but still targets BELONGS_TO_CLASS | yes | C2_PromptRelationEndpointsAreTargeted |
| M07_concept_extracted_by_no_task | C2 | the only task that extracts DrugClass stops targeting it (with BELONGS_TO_CLASS and the few-shot items that use them): no task extracts DrugClass any more | yes | C2_EveryConceptTargetedBySomeTask |
| M08_threshold_out_of_range | C3 | confidence threshold 1.5 | yes | C3_ThresholdInRange |
| M09_overlap_not_smaller_than_chunk | C3 | literature task overlap equals chunk size | yes | C3_OverlapSmallerThanChunk |
| M10_rule_without_expression | C3 | entity_confidence_above_threshold loses its expression | yes | C3_RuleHasExpression |
| M11_no_provenance_rule | C3 | the provenance rule is downgraded to WARNING (R7 no longer guaranteed) | yes | C3_HasProvenanceRule |
| M12_uncovered_audience | C4 | auditor removed from GuidelineCompliance and AttributionReport, its only two explanation types | yes | C4_AudienceCovered |
| M13_low_audience_gets_feature_attribution | C4 | patient (LOW) is added to the FEATURE_ATTRIBUTION type | yes | C4_LowAudienceNoFeatureAttribution |
| M14_low_audience_only_technical | C4 | patient removed from PlainLanguageContrast and ModifiableFactors, so it receives no plain-language explanation | yes | C4_LowAudienceGetsAccessibleExplanation |
| M15_decision_class_misses_audience | C4 | LowReadmissionRisk no longer offers anything to the patient | yes | C4_DecisionClassCoversEveryAudience |
| M16_explanation_uses_undeclared_pattern | C5 | GuidelineCompliance references a query pattern that is not in the schema (dangling) | yes | unresolved reference (load time) |
| M17_binding_feature_not_in_model | C5 | a feature binding refers to a feature the model does not have | yes | C5_BindingFeatureExistsInModel |
| M18_binding_without_resolution | C5 | number_emergency binding loses its entityName | yes | C5_BindingHasResolution |
| M19_configs_disagree_on_schema | C5 | validation policy points to a different schema file | yes | C5_AllConfigsShareOneSchema |
| M20_missing_trace_pattern | C5 | auditor requires full provenance but no trace pattern is bound | yes | C5_FullProvenanceAudienceHasTracePattern |
| M21_counterfactual_pattern_not_actionable | C4 | ModifiableFactors (COUNTERFACTUAL) also runs causal_context, which may return non-modifiable risk factors | yes | C4_CounterfactualPatternsActionable |
| M22_actionable_pattern_without_modifiability | C1 | causal_context is declared actionableOnly without filtering on the modifiability property | yes | C1_ActionablePatternFiltersModifiable |
