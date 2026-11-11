# E3 - Hallucination filtering on BC5CDR (gemini/gemini-3.1-flash-lite)

60 test abstracts, 131 gold chemical-induced-disease relations; prompt `drug_label_extraction@fc3d922aa277`; MAY_CAUSE predictions scored against gold (lenient surface match, strict direction).

| Variant | Precision | Recall | F1 | Accepted rel. | Rejections per rule |
|---|---|---|---|---|---|
| raw LLM output | 0.64 | 0.664 | 0.652 | 183 | - |
| T2 default | 0.627 | 0.641 | 0.634 | 180 | relation_evidence_grounded_in_source: 2, relation_type_and_endpoints_in_schema: 1 |
| T2 threshold_0.5 | 0.627 | 0.641 | 0.634 | 180 | relation_evidence_grounded_in_source: 2, relation_type_and_endpoints_in_schema: 1 |
| T2 threshold_0.7 | 0.627 | 0.641 | 0.634 | 180 | relation_evidence_grounded_in_source: 2, relation_type_and_endpoints_in_schema: 1 |
| T2 threshold_0.9 | 0.564 | 0.405 | 0.471 | 130 | entity_confidence_above_threshold: 3, relation_confidence_above_threshold: 50, relation_endpoints_accepted: 3, relation_evidence_grounded_in_source: 2, relation_type_and_endpoints_in_schema: 1 |
| T2 no_grounding | 0.632 | 0.656 | 0.644 | 182 | relation_evidence_grounded_in_source: 2, relation_type_and_endpoints_in_schema: 1 |

Spans repaired by exact search: 456; unparseable chunks: 0; tokens in/out: 182180/49692.
