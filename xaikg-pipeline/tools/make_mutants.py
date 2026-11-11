"""E2 mutation set: inject one design fault per mutant into the M1 models and record which
constraint must catch it (paper, Phase 2; experiment E2, see docs/experiments.md, section E2).

Each mutant is a full copy of models/diabetes-readmission/ with exactly one textual edit, written to
models/mutants/<id>/ together with expected.json (the constraint family/name expected to fire).
Run `xaikg-mde check -m models/mutants/<id>` on each; run_mutants.py automates this.
"""
import json
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "models" / "diabetes-readmission"
OUT = ROOT / "models" / "mutants"

# id, family, expected constraint, file, (old, new) textual replacement, description
MUTANTS = [
    ("M01_concept_without_property", "C1", "C1_ConceptHasProperty", "kg-schema.xmi",
     ('<properties name="name" dataType="STRING" isRequired="true" isExplainable="true" description="Class name in lowercase plural, e.g. \'sulfonylureas\'"/>', ''),
     "DrugClass loses its only property"),
    ("M02_negative_cardinality", "C1", "C1_CardinalitiesValid", "kg-schema.xmi",
     ('id="APPLIES_TO" name="APPLIES_TO" source="Recommendation" target="Condition"\n      minCardinality="1"', 'id="APPLIES_TO" name="APPLIES_TO" source="Recommendation" target="Condition"\n      minCardinality="-3"'),
     "APPLIES_TO gets minCardinality -3"),
    ("M03_empty_query_template", "C1", "C1_PatternHasTemplate", "kg-schema.xmi",
     ('<queryPatterns name="guideline_rules" parameters="active limit"', '<queryPatterns name="guideline_rules" parameters=""'),
     "guideline_rules loses its Cypher template (parameters cleared and template emptied)"),
    ("M04_pattern_writes_graph", "C1", "C1_PatternReadsOnly", "kg-schema.xmi",
     ('MATCH (f)-[r:REDUCES_RISK_OF]->(o:ClinicalOutcome {_key: $outcome})\nWHERE f._modifiable = true', 'MATCH (f)-[r:REDUCES_RISK_OF]->(o:ClinicalOutcome {_key: $outcome})\nSET o.touched = true\nWITH f, r, o\nWHERE f._modifiable = true'),
     "protective_factors template mutates the graph"),
    ("M05_prompt_targets_undeclared_concept", "C2", "C2_PromptConceptsDeclaredInTargetSchema", "extraction-pipeline.xmi",
     ('targetConcepts="kg-schema.xmi#Drug kg-schema.xmi#DrugClass kg-schema.xmi#Condition"', 'targetConcepts="kg-schema.xmi#Drug kg-schema.xmi#DrugClass kg-schema.xmi#Condition kg-schema.xmi#Procedure"'),
     "drug_label task targets a concept that does not exist (dangling reference)"),
    ("M06_prompt_relation_without_endpoint", "C2", "C2_PromptRelationEndpointsAreTargeted", "extraction-pipeline.xmi",
     ('targetConcepts="kg-schema.xmi#Drug kg-schema.xmi#DrugClass kg-schema.xmi#Condition"', 'targetConcepts="kg-schema.xmi#Drug kg-schema.xmi#Condition"'),
     "drug_label task drops DrugClass but still targets BELONGS_TO_CLASS"),
    ("M07_concept_extracted_by_no_task", "C2", "C2_EveryConceptTargetedBySomeTask", "extraction-pipeline.xmi",
     ('targetConcepts="kg-schema.xmi#Drug kg-schema.xmi#DrugClass kg-schema.xmi#Condition"', 'targetConcepts="kg-schema.xmi#Drug kg-schema.xmi#Condition"'),
     "the only task that extracts DrugClass stops targeting it (with BELONGS_TO_CLASS and the few-shot items that use them): no task extracts DrugClass any more",
     [(' kg-schema.xmi#BELONGS_TO_CLASS">', '">'),
      (', {"type": "DrugClass", "id": "biguanides", "mention": "biguanide", "span": {"start": 347, "end": 356}, "properties": {"name": "biguanides"}, "confidence": 0.9}', ''),
      (', {"type": "BELONGS_TO_CLASS", "source": {"type": "Drug", "id": "metformin"}, "target": {"type": "DrugClass", "id": "biguanides"}, "evidence": "Metformin is a biguanide.", "span": {"start": 332, "end": 357}, "confidence": 0.95}', ''),
      (', {"type": "DrugClass", "id": "sulfonylureas", "mention": "sulfonylurea", "span": {"start": 15, "end": 27}, "properties": {"name": "sulfonylureas"}, "confidence": 0.92}', ''),
      ('{"type": "BELONGS_TO_CLASS", "source": {"type": "Drug", "id": "glipizide"}, "target": {"type": "DrugClass", "id": "sulfonylureas"}, "evidence": "Glipizide is a sulfonylurea indicated to improve glycemic control in adults with type 2 diabetes mellitus.", "span": {"start": 0, "end": 106}, "confidence": 0.95}, ', '')]),
    ("M08_threshold_out_of_range", "C3", "C3_ThresholdInRange", "validation-policy.xmi",
     ('confidenceThreshold="0.7"', 'confidenceThreshold="1.5"'),
     "confidence threshold 1.5"),
    ("M09_overlap_not_smaller_than_chunk", "C3", "C3_OverlapSmallerThanChunk", "extraction-pipeline.xmi",
     ('<chunkingStrategy chunkSize="3000" overlap="200" splitter="SENTENCE"/>', '<chunkingStrategy chunkSize="3000" overlap="3000" splitter="SENTENCE"/>'),
     "literature task overlap equals chunk size"),
    ("M10_rule_without_expression", "C3", "C3_RuleHasExpression", "validation-policy.xmi",
     ('<oclExpression>self.confidence >= config.confidenceThreshold</oclExpression>\n  </rules>\n\n  <rules name="entity_provenance_complete"', '<oclExpression></oclExpression>\n  </rules>\n\n  <rules name="entity_provenance_complete"'),
     "entity_confidence_above_threshold loses its expression"),
    ("M11_no_provenance_rule", "C3", "C3_HasProvenanceRule", "validation-policy.xmi",
     ('ruleType="PROVENANCE_CHECK" scope="ENTITY" severity="ERROR"', 'ruleType="PROVENANCE_CHECK" scope="ENTITY" severity="WARNING"'),
     "the provenance rule is downgraded to WARNING (R7 no longer guaranteed)"),
    ("M12_uncovered_audience", "C4", "C4_AudienceCovered", "explainability.xmi",
     ('audiences="quality_officer auditor" template="tpl_guideline_rules"', 'audiences="quality_officer" template="tpl_guideline_rules"'),
     "auditor is removed from GuidelineCompliance; AttributionReport still serves auditor, so ALSO remove it there",
     ('audiences="clinician auditor" template="tpl_attribution_report"', 'audiences="clinician" template="tpl_attribution_report"')),
    ("M13_low_audience_gets_feature_attribution", "C4", "C4_LowAudienceNoFeatureAttribution", "explainability.xmi",
     ('audiences="clinician auditor" template="tpl_attribution_report"', 'audiences="clinician auditor patient" template="tpl_attribution_report"'),
     "patient (LOW) is added to the FEATURE_ATTRIBUTION type"),
    ("M14_low_audience_only_technical", "C4", "C4_LowAudienceGetsAccessibleExplanation", "explainability.xmi",
     ('audiences="patient" template="tpl_plain_contrast"', 'audiences="clinician" template="tpl_plain_contrast"'),
     "patient loses the contrastive type; keeps only ModifiableFactors... so ALSO remove patient there",
     ('audiences="patient clinician quality_officer" template="tpl_modifiable_factors"', 'audiences="clinician quality_officer" template="tpl_modifiable_factors"')),
    ("M15_decision_class_misses_audience", "C4", "C4_DecisionClassCoversEveryAudience", "decision-bindings.xmi",
     ('explanationTypes="explainability.xmi#PlainLanguageContrast explainability.xmi#CausalEvidence explainability.xmi#GuidelineCompliance explainability.xmi#AttributionReport"/>', 'explanationTypes="explainability.xmi#CausalEvidence explainability.xmi#GuidelineCompliance explainability.xmi#AttributionReport"/>'),
     "LowReadmissionRisk no longer offers anything to the patient"),
    ("M16_explanation_uses_undeclared_pattern", "C5", "C5_PatternsDeclaredInTargetSchema", "explainability.xmi",
     ('queryPatterns="kg-schema.xmi#guideline_rules"', 'queryPatterns="kg-schema.xmi#nonexistent_pattern"'),
     "GuidelineCompliance references a query pattern that is not in the schema (dangling)"),
    ("M17_binding_feature_not_in_model", "C5", "C5_BindingFeatureExistsInModel", "decision-bindings.xmi",
     ('<featureBindings featureName="miglitol"', '<featureBindings featureName="miglitoll"'),
     "a feature binding refers to a feature the model does not have"),
    ("M18_binding_without_resolution", "C5", "C5_BindingHasResolution", "decision-bindings.xmi",
     ('entityName="prior emergency visits" activeWhen="value >= 1"', 'activeWhen="value >= 1"'),
     "number_emergency binding loses its entityName"),
    ("M19_configs_disagree_on_schema", "C5", "C5_AllConfigsShareOneSchema", "validation-policy.xmi",
     ('<targetSchema href="kg-schema.xmi#DiabetesReadmissionKG"/>', '<targetSchema href="alt-schema.xmi#AlternativeKG"/>'),
     "validation policy points to a different schema file", None, "alt-schema"),
    ("M20_missing_trace_pattern", "C5", "C5_FullProvenanceAudienceHasTracePattern", "explainability.xmi",
     ('  <traceQueryPattern href="kg-schema.xmi#provenance_trace"/>\n', ''),
     "auditor requires full provenance but no trace pattern is bound"),
    ("M21_counterfactual_pattern_not_actionable", "C4", "C4_CounterfactualPatternsActionable", "explainability.xmi",
     ('queryPatterns="kg-schema.xmi#counterfactual_recommendations kg-schema.xmi#protective_factors"',
      'queryPatterns="kg-schema.xmi#counterfactual_recommendations kg-schema.xmi#protective_factors kg-schema.xmi#causal_context"'),
     "ModifiableFactors (COUNTERFACTUAL) also runs causal_context, which may return non-modifiable risk factors"),
    ("M22_actionable_pattern_without_modifiability", "C1", "C1_ActionablePatternFiltersModifiable", "kg-schema.xmi",
     ('<queryPatterns name="causal_context" parameters="factors outcome limit"',
      '<queryPatterns name="causal_context" parameters="factors outcome limit" actionableOnly="true"'),
     "causal_context is declared actionableOnly without filtering on the modifiability property"),
]

ALT_SCHEMA = """<?xml version="1.0" encoding="UTF-8"?>
<kgschema:KGSchemaDefinition xmi:version="2.0" xmlns:xmi="http://www.omg.org/XMI"
    xmlns:kgschema="http://www.xaikg.org/1.0/kgschema" name="AlternativeKG" nsURI="http://example.org/alt">
  <concepts name="Thing" description="placeholder"><properties name="name" isRequired="true" isExplainable="true"/></concepts>
</kgschema:KGSchemaDefinition>
"""


def apply(text: str, old: str, new: str, mutant: str, file: str) -> str:
    if old not in text:
        sys.exit(f"{mutant}: anchor text not found in {file}:\n{old}")
    return text.replace(old, new, 1)


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    index = []
    for spec in MUTANTS:
        mid, family, constraint, file, (old, new), description = spec[:6]
        extra = spec[6] if len(spec) > 6 else None
        alt = spec[7] if len(spec) > 7 else None
        target = OUT / mid
        shutil.copytree(SRC, target)
        path = target / file
        text = path.read_text(encoding="utf-8")
        text = apply(text, old, new, mid, file)
        for old_x, new_x in ([extra] if isinstance(extra, tuple) else (extra or [])):
            text = apply(text, old_x, new_x, mid, file)
        if mid == "M03_empty_query_template":
            # also empty the template body itself
            start = text.index('<queryPatterns name="guideline_rules"')
            body_start = text.index("<cypherTemplate>", start) + len("<cypherTemplate>")
            body_end = text.index("</cypherTemplate>", body_start)
            text = text[:body_start] + text[body_end:]
        path.write_text(text, encoding="utf-8")
        if alt == "alt-schema":
            (target / "alt-schema.xmi").write_text(ALT_SCHEMA, encoding="utf-8")
        expected = {"id": mid, "family": family, "expectedConstraint": constraint, "mutatedFile": file,
                    "description": description}
        (target / "expected.json").write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")
        index.append(expected)
    (OUT / "index.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(index)} mutants under {OUT}")


if __name__ == "__main__":
    main()
