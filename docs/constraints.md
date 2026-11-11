# Constraint layer (Phase 2)

*Paper: Section 4.3 (Phase 2: Verifying the Models). Code: [`xaikg-mde/constraints/xaikg.evl`](../xaikg-mde/constraints/xaikg.evl).*

Before any artifact is generated, the constraint layer evaluates the five case-study models **together**, as one resource set, with invariants written in the style of OCL in the Epsilon Validation Language (EVL). The layer has **113 invariants** grouped into five families. **100 are blocking** (`constraint`): if one is violated, the command reports it and exits with code 2, and nothing is generated until the models are fixed. **13 are critiques** (`critique`): they only warn the modeler about questionable choices, such as a high sampling temperature, without stopping generation.

```bash
make check                      # or: java -jar xaikg-mde/target/xaikg-mde.jar check --mde-home xaikg-mde -m models/diabetes-readmission
```

The command prints one JSON report listing every violation (the invariant, its message and whether it is a critique). `make generate` runs the same check first and refuses to run any transformation if a blocking invariant fails. Two kinds of fault are caught even earlier, when the models are loaded: for example a reference to an element that does not exist  makes loading fail (see E2 in [experiments.md](experiments.md#e2--fault-detection-by-mutation-analysis)).

## The five families

| Family | Purpose | Blocking | Critiques |
|---|---|---|---|
| **C1** Structural well-formedness | Every model element is complete and consistent on its own: names, unique identifiers, cardinalities, relations between declared concepts, read-only query patterns, actionable patterns that filter on modifiability. | 25 | 4 |
| **C2** Schema–prompt consistency | The LLM Pipeline model agrees with the KG Schema: every targeted concept and relation exists, relation endpoints are targeted too, every concept is extracted by some task, and few-shot examples mention only targeted types. | 16 | 2 |
| **C3** Validation soundness | The Validation Policy is usable and complete: thresholds in range, every rule has an expression, chunk overlap smaller than chunk size, and conformance, grounding and provenance rules are present and blocking. | 17 | 2 |
| **C4** Audience coverage | The explanation contract serves every audience appropriately: every audience is served, lay audiences receive an accessible, plain-language explanation and no feature-attribution report, counterfactual explanations use only actionable patterns, every decision class covers every audience. | 22 | 4 |
| **C5** Cross-model traceability | The five models fit together: they share one schema, bound features exist in the AI model and resolve to graph entities, audiences that require full provenance have a trace pattern. | 20 | 1 |
| **Total** | | **100** | **13** |

## All invariants

Kind: **B** = blocking constraint, *c* = critique. 

*Context* is the model alias and the metaclass the invariant is evaluated on (aliases: `Schema`, `Pipeline`, `Policy`, `Explainability`, `Decision`, one per model).

In the message, `…` stands for a value inserted from the model element.

### C1 — Structural well-formedness

| # | Invariant | Kind | Context | Message when violated | Line |
|---|---|---|---|---|---|
| 1 | `C1_SchemaHasName` | **B** | `Schema!KGSchemaDefinition` | The KG schema has no name | 18 |
| 2 | `C1_SchemaHasConcepts` | **B** | `Schema!KGSchemaDefinition` | Schema ‘…’ declares no concept | 23 |
| 3 | `C1_UniqueConceptNames` | **B** | `Schema!KGSchemaDefinition` | Schema ‘…’ has duplicate concept names | 28 |
| 4 | `C1_UniqueRelationIds` | **B** | `Schema!KGSchemaDefinition` | Schema ‘…’ has duplicate relation ids | 33 |
| 5 | `C1_UniqueQueryPatternNames` | **B** | `Schema!KGSchemaDefinition` | Schema ‘…’ has duplicate query pattern names | 38 |
| 6 | `C1_SameNameRelationsHaveDistinctEndpoints` | **B** | `Schema!KGSchemaDefinition` | Schema ‘…’: two relations share the same name and the same endpoints | 43 |
| 7 | `C1_ConceptHasName` | **B** | `Schema!KGConcept` | Concept name ‘…’ must be UpperCamelCase (it becomes a node label) | 53 |
| 8 | `C1_ConceptHasProperty` | **B** | `Schema!KGConcept` | Concept ‘…’ declares no property | 58 |
| 9 | `C1_ConceptHasIdentifyingProperty` | **B** | `Schema!KGConcept` | Concept ‘…’ has no required property; the first required property identifies its instances in the graph | 63 |
| 10 | `C1_UniquePropertyNames` | **B** | `Schema!KGConcept` | Concept ‘…’ has duplicate property names | 68 |
| 11 | `C1_ConceptHasExplainableProperty` | *c* | `Schema!KGConcept` | Concept ‘…’ exposes no explainable property; it can never surface in an explanation | 73 |
| 12 | `C1_ConceptHasDescription` | *c* | `Schema!KGConcept` | Concept ‘…’ has no description (descriptions are emitted into the LLM prompt) | 78 |
| 13 | `C1_CanonicalEntityHasName` | **B** | `Schema!CanonicalEntity` | A canonical entity of concept ‘…’ has no name | 86 |
| 14 | `C1_CanonicalEntityNamesUniqueInConcept` | **B** | `Schema!CanonicalEntity` | Concept ‘…’ declares the canonical entity ‘…’ twice | 91 |
| 15 | `C1_CanonicalEntityAliasesDistinct` | **B** | `Schema!CanonicalEntity` | Canonical entity ‘…’ repeats an alias or lists its own name as alias | 96 |
| 16 | `C1_CanonicalEntityAliasesNotShared` | **B** | `Schema!CanonicalEntity` | Canonical entity ‘…’ shares an alias with another canonical entity of the same concept (ambiguous normalisation) | 111 |
| 17 | `C1_PropertyHasName` | **B** | `Schema!KGProperty` | Property of concept ‘…’ has an invalid name ‘…’ (lowerCamelCase expected) | 119 |
| 18 | `C1_RelationHasId` | **B** | `Schema!KGRelation` | Relation ‘…’ has no id | 127 |
| 19 | `C1_RelationHasName` | **B** | `Schema!KGRelation` | Relation ‘…’ name must be UPPER_SNAKE_CASE (it becomes a relationship type) | 132 |
| 20 | `C1_RelationHasEndpoints` | **B** | `Schema!KGRelation` | Relation ‘…’ must have both a source and a target concept | 137 |
| 21 | `C1_RelationEndpointsDeclaredInSchema` | **B** | `Schema!KGRelation` | Relation ‘…’ references a concept outside its schema | 142 |
| 22 | `C1_CardinalitiesValid` | **B** | `Schema!KGRelation` | Relation ‘…’ has invalid cardinalities [ … .. … ] | 148 |
| 23 | `C1_RelationHasSemantics` | *c* | `Schema!KGRelation` | Relation ‘…’ has no semantics text (emitted into the LLM prompt) | 153 |
| 24 | `C1_PatternHasName` | **B** | `Schema!KGQueryPattern` | Query pattern name ‘…’ must be lower_snake_case | 161 |
| 25 | `C1_PatternHasTemplate` | **B** | `Schema!KGQueryPattern` | Query pattern ‘…’ has an empty Cypher template | 166 |
| 26 | `C1_PatternDeclaresItsParameters` | **B** | `Schema!KGQueryPattern` | Query pattern ‘…’ declares a parameter that the template never uses | 171 |
| 27 | `C1_PatternReadsOnly` | **B** | `Schema!KGQueryPattern` | Query pattern ‘…’ must be read-only (explanations never modify the graph) | 178 |
| 28 | `C1_ActionablePatternFiltersModifiable` | **B** | `Schema!KGQueryPattern` | Query pattern ‘…’ is declared actionableOnly but its Cypher template never references the modifiability property _modifiable | 184 |
| 29 | `C1_PatternUsedByAnExplanation` | *c* | `Schema!KGQueryPattern` | Query pattern ‘…’ is used neither by an explanation type nor as the trace pattern | 192 |

### C2 — Schema–prompt consistency

| # | Invariant | Kind | Context | Message when violated | Line |
|---|---|---|---|---|---|
| 1 | `C2_PipelineHasTargetSchema` | **B** | `Pipeline!LLMPipelineConfig` | Pipeline ‘…’ does not reference a target KG schema | 204 |
| 2 | `C2_PipelineHasTasks` | **B** | `Pipeline!LLMPipelineConfig` | Pipeline ‘…’ declares no extraction task | 209 |
| 3 | `C2_UniqueTaskNames` | **B** | `Pipeline!LLMPipelineConfig` | Pipeline ‘…’ has duplicate task names | 214 |
| 4 | `C2_EveryConceptTargetedBySomeTask` | **B** | `Pipeline!LLMPipelineConfig` | Pipeline ‘…’: concepts extracted by no task (they would stay empty in the KG): … , | 219 |
| 5 | `C2_EveryRelationTargetedBySomeTask` | *c* | `Pipeline!LLMPipelineConfig` | Pipeline ‘…’: relations extracted by no task: … , | 226 |
| 6 | `C2_TaskHasName` | **B** | `Pipeline!ExtractionTask` | Extraction task name ‘…’ must be lower_snake_case (used in file names) | 236 |
| 7 | `C2_TaskHasPromptTemplate` | **B** | `Pipeline!ExtractionTask` | Task ‘…’ has no prompt template | 241 |
| 8 | `C2_TaskHasChunkingStrategy` | **B** | `Pipeline!ExtractionTask` | Task ‘…’ has no chunking strategy | 246 |
| 9 | `C2_TaskHasLlmModel` | **B** | `Pipeline!ExtractionTask` | Task ‘…’ must name its LLM as provider/model (e.g. gemini/gemini-2.5-flash) | 251 |
| 10 | `C2_TaskHasSourceCollection` | **B** | `Pipeline!ExtractionTask` | Task ‘…’ does not say which document collection it processes | 256 |
| 11 | `C2_PromptHasSystemInstruction` | **B** | `Pipeline!PromptTemplate` | Prompt template of task ‘…’ has no system instruction | 264 |
| 12 | `C2_PromptTargetsAtLeastOneConcept` | **B** | `Pipeline!PromptTemplate` | Prompt template of task ‘…’ targets no KG concept | 269 |
| 13 | `C2_PromptConceptsDeclaredInTargetSchema` | **B** | `Pipeline!PromptTemplate` | Prompt template of task ‘…’ targets a concept that is not in the pipeline's target schema | 274 |
| 14 | `C2_PromptRelationsDeclaredInTargetSchema` | **B** | `Pipeline!PromptTemplate` | Prompt template of task ‘…’ targets a relation that is not in the pipeline's target schema | 280 |
| 15 | `C2_PromptRelationEndpointsAreTargeted` | **B** | `Pipeline!PromptTemplate` | Prompt template of task ‘…’ targets a relation whose source or target concept it does not target | 286 |
| 16 | `C2_PromptHasFewShotExample` | *c* | `Pipeline!PromptTemplate` | Prompt template of task ‘…’ has no few-shot example | 292 |
| 17 | `C2_FewShotExamplesComplete` | **B** | `Pipeline!PromptTemplate` | Prompt template of task ‘…’ has an incomplete few-shot example | 297 |
| 18 | `C2_FewShotOutputsMentionOnlyTargetedTypes` | **B** | `Pipeline!PromptTemplate` | A few-shot example of task ‘…’ uses an entity or relation type the prompt does not target | 302 |

### C3 — Validation soundness

| # | Invariant | Kind | Context | Message when violated | Line |
|---|---|---|---|---|---|
| 1 | `C3_ThresholdInRange` | **B** | `Policy!ValidationConfig` | Validation policy ‘…’: confidence threshold … is not in [0,1] | 317 |
| 2 | `C3_PolicyHasTargetSchema` | **B** | `Policy!ValidationConfig` | Validation policy ‘…’ does not reference a target KG schema | 322 |
| 3 | `C3_PolicyHasRules` | **B** | `Policy!ValidationConfig` | Validation policy ‘…’ declares no rule | 327 |
| 4 | `C3_UniqueRuleNames` | **B** | `Policy!ValidationConfig` | Validation policy ‘…’ has duplicate rule names | 332 |
| 5 | `C3_HasSchemaConformanceRules` | **B** | `Policy!ValidationConfig` | Validation policy ‘…’ needs a SCHEMA_CONFORMANCE rule for entities and one for relations (R3) | 337 |
| 6 | `C3_HasHallucinationOrConfidenceRule` | **B** | `Policy!ValidationConfig` | Validation policy ‘…’ has no hallucination or confidence rule (R4) | 343 |
| 7 | `C3_HasProvenanceRule` | **B** | `Policy!ValidationConfig` | Validation policy ‘…’ has no blocking PROVENANCE_CHECK rule (R7: provenance by construction) | 348 |
| 8 | `C3_RuleHasName` | **B** | `Policy!ValidationRule` | Validation rule name ‘…’ must be lower_snake_case (it becomes a constraint name) | 356 |
| 9 | `C3_RuleHasExpression` | **B** | `Policy!ValidationRule` | Validation rule ‘…’ has no expression | 361 |
| 10 | `C3_RuleExpressionIsNotTrivial` | **B** | `Policy!ValidationRule` | Validation rule ‘…’ has a trivial expression | 366 |
| 11 | `C3_RuleHasMessage` | **B** | `Policy!ValidationRule` | Validation rule ‘…’ has no error message | 372 |
| 12 | `C3_RuleExpressionUsesSelf` | **B** | `Policy!ValidationRule` | Validation rule ‘…’ never refers to the checked element (self) | 377 |
| 13 | `C3_ChunkSizePositive` | **B** | `Pipeline!ChunkingStrategy` | Task ‘…’: chunk size must be positive | 386 |
| 14 | `C3_OverlapNonNegative` | **B** | `Pipeline!ChunkingStrategy` | Task ‘…’: chunk overlap must be >= 0 | 391 |
| 15 | `C3_OverlapSmallerThanChunk` | **B** | `Pipeline!ChunkingStrategy` | Task ‘…’: chunk overlap ( … ) must be smaller than chunk size ( … ) | 396 |
| 16 | `C3_ChunkFitsPromptBudget` | *c* | `Pipeline!ChunkingStrategy` | Task ‘…’: chunks above 8000 characters degrade extraction recall | 401 |
| 17 | `C3_TemperatureInRange` | **B** | `Pipeline!ExtractionTask` | Task ‘…’: temperature … is not in [0,1] | 409 |
| 18 | `C3_LowTemperatureForExtraction` | *c* | `Pipeline!ExtractionTask` | Task ‘…’: temperature … is high for extraction (<= 0.3 recommended) | 414 |
| 19 | `C3_MaxTokensPositive` | **B** | `Pipeline!ExtractionTask` | Task ‘…’: maxTokens must be positive | 419 |

### C4 — Audience coverage

| # | Invariant | Kind | Context | Message when violated | Line |
|---|---|---|---|---|---|
| 1 | `C4_CanonicalEntityHasPlainLabel` | *c* | `Schema!CanonicalEntity` | Canonical entity ‘…’ of concept ‘…’ has no plainLabel; plain-language audiences would see its clinical name | 102 |
| 2 | `C4_HasAudiences` | **B** | `Explainability!ExplainabilityConfig` | Explainability config ‘…’ declares no audience | 430 |
| 3 | `C4_HasExplanationTypes` | **B** | `Explainability!ExplainabilityConfig` | Explainability config ‘…’ declares no explanation type | 435 |
| 4 | `C4_UniqueAudienceRoles` | **B** | `Explainability!ExplainabilityConfig` | Explainability config ‘…’ has duplicate audience roles | 440 |
| 5 | `C4_UniqueExplanationTypeNames` | **B** | `Explainability!ExplainabilityConfig` | Explainability config ‘…’ has duplicate explanation type names | 445 |
| 6 | `C4_UniqueTemplateNames` | **B** | `Explainability!ExplainabilityConfig` | Explainability config ‘…’ has duplicate template names | 450 |
| 7 | `C4_RetrievalLimitCoversBudgets` | *c* | `Explainability!ExplainabilityConfig` | Explainability config ‘…’: retrievalLimit … is smaller than the presentation budget of an audience; budgets cannot be filled and omitted facts are under-counted | 455 |
| 8 | `C4_AudienceHasRole` | **B** | `Explainability!Audience` | Audience role ‘…’ must be lower_snake_case (used in endpoint paths) | 463 |
| 9 | `C4_AudienceCovered` | **B** | `Explainability!Audience` | Audience ‘…’ is served by no explanation type (R6) | 468 |
| 10 | `C4_LowAudienceGetsAccessibleExplanation` | **B** | `Explainability!Audience` | Low-proficiency audience ‘…’ gets no contrastive, example-based or counterfactual explanation (C4) | 473 |
| 11 | `C4_LowAudienceNoFeatureAttribution` | **B** | `Explainability!Audience` | Low-proficiency audience ‘…’ must not receive feature-attribution explanations (C4) | 481 |
| 12 | `C4_AudienceHasBudget` | **B** | `Explainability!Audience` | Audience ‘…’ has no valid presentation budget (maxFacts must be > 0) | 487 |
| 13 | `C4_LowAudiencePlainLanguage` | **B** | `Explainability!Audience` | Low-proficiency audience ‘…’ must have a plain-language budget without codes | 492 |
| 14 | `C4_LowAudienceSmallBudget` | *c* | `Explainability!Audience` | Low-proficiency audience ‘…’ has a budget above 5 facts | 498 |
| 15 | `C4_TypeHasName` | **B** | `Explainability!ExplanationType` | Explanation type name ‘…’ must be UpperCamelCase | 507 |
| 16 | `C4_TypeHasAudience` | **B** | `Explainability!ExplanationType` | Explanation type ‘…’ serves no audience | 512 |
| 17 | `C4_TypeHasQueryPattern` | **B** | `Explainability!ExplanationType` | Explanation type ‘…’ executes no query pattern (no evidence path) | 517 |
| 18 | `C4_TypeHasTemplate` | **B** | `Explainability!ExplanationType` | Explanation type ‘…’ has no rendering template | 522 |
| 19 | `C4_TypeAudiencesDeclaredHere` | **B** | `Explainability!ExplanationType` | Explanation type ‘…’ references an audience outside its configuration | 527 |
| 20 | `C4_CounterfactualPatternsActionable` | **B** | `Explainability!ExplanationType` | Counterfactual explanation type ‘…’ uses query patterns that are not declared actionableOnly: … , | 532 |
| 21 | `C4_FeatureAttributionNeedsAttributionMethod` | **B** | `Explainability!ExplanationType` | Explanation type ‘…’ is FEATURE_ATTRIBUTION but the AI model declares no attribution method | 539 |
| 22 | `C4_TemplateHasBody` | **B** | `Explainability!ExplanationTemplate` | Explanation template ‘…’ is empty | 548 |
| 23 | `C4_TemplateRendersFacts` | **B** | `Explainability!ExplanationTemplate` | Explanation template ‘…’ never renders the KG facts (variable 'facts') | 553 |
| 24 | `C4_TemplateUsed` | *c* | `Explainability!ExplanationTemplate` | Explanation template ‘…’ is not used by any explanation type | 558 |
| 25 | `C4_DecisionClassHasExplanationTypes` | **B** | `Decision!DecisionClass` | Decision class ‘…’ is bound to no explanation type (R5: explicit explanation contract) | 582 |
| 26 | `C4_DecisionClassCoversEveryAudience` | **B** | `Decision!DecisionClass` | Decision class ‘…’ leaves at least one audience without an explanation (R6) | 587 |

### C5 — Cross-model traceability

| # | Invariant | Kind | Context | Message when violated | Line |
|---|---|---|---|---|---|
| 1 | `C5_DecisionClassNamesItsOutcome` | **B** | `Decision!DecisionClass` | Decision class ‘…’ does not name the outcome it predicts (needed to bind $outcome in query patterns) | 566 |
| 2 | `C5_PredictedOutcomeIsCanonical` | **B** | `Decision!DecisionClass` | Decision class ‘…’ predicts ‘…’, which is not a canonical entity of any concept | 571 |
| 3 | `C5_DecisionClassThresholdInRange` | **B** | `Decision!DecisionClass` | Decision class ‘…’ has a threshold outside (0,1) | 577 |
| 4 | `C5_HasTargetSchema` | **B** | `Explainability!ExplainabilityConfig` | Explainability config ‘…’ does not reference a target KG schema | 598 |
| 5 | `C5_FullProvenanceAudienceHasTracePattern` | **B** | `Explainability!ExplainabilityConfig` | Explainability config ‘…’ has an audience requiring full provenance but no trace query pattern declared in the target schema | 603 |
| 6 | `C5_TracePatternTakesFactIds` | **B** | `Explainability!ExplainabilityConfig` | Trace query pattern ‘…’ must accept the $factIds parameter used by the /trace endpoint | 610 |
| 7 | `C5_PatternsDeclaredInTargetSchema` | **B** | `Explainability!ExplanationType` | Explanation type ‘…’ uses a query pattern that is not declared in the target KG schema (C5) | 619 |
| 8 | `C5_TemplateDeclaredHere` | **B** | `Explainability!ExplanationType` | Explanation type ‘…’ uses a template outside its configuration | 625 |
| 9 | `C5_HasTargetSchema` | **B** | `Decision!DecisionBindingConfig` | Decision bindings ‘…’ do not reference a target KG schema | 634 |
| 10 | `C5_HasAiModel` | **B** | `Decision!DecisionBindingConfig` | Decision bindings ‘…’ declare no AI model | 639 |
| 11 | `C5_HasDecisionClass` | **B** | `Decision!DecisionBindingConfig` | Decision bindings ‘…’ declare no decision class | 644 |
| 12 | `C5_UniqueFeatureBindings` | **B** | `Decision!DecisionBindingConfig` | Decision bindings ‘…’ bind the same feature twice | 649 |
| 13 | `C5_AllConfigsShareOneSchema` | **B** | `Decision!DecisionBindingConfig` | Not all M1 models reference the same KG schema (R1 single source of truth) | 654 |
| 14 | `C5_DecisionTypesDeclaredInExplainability` | **B** | `Decision!DecisionBindingConfig` | Decision bindings ‘…’ reference an explanation type outside the linked explainability configuration | 663 |
| 15 | `C5_ModelHasFeatures` | **B** | `Decision!AIModelSpec` | AI model ‘…’ lists no feature; nothing can be grounded | 671 |
| 16 | `C5_ModelHasVersion` | **B** | `Decision!AIModelSpec` | AI model ‘…’ has no version (needed in every provenance record) | 676 |
| 17 | `C5_AllFeaturesBound` | *c* | `Decision!AIModelSpec` | AI model ‘…’: some features have no KG binding and cannot be grounded in explanations | 681 |
| 18 | `C5_BoundEntityIsCanonical` | **B** | `Decision!FeatureBinding` | Feature binding ‘…’ points to ‘…’, which is not a canonical entity of concept ‘…’ | 689 |
| 19 | `C5_BindingFeatureExistsInModel` | **B** | `Decision!FeatureBinding` | Feature binding ‘…’ refers to a feature the AI model does not use | 697 |
| 20 | `C5_BindingConceptDeclaredInSchema` | **B** | `Decision!FeatureBinding` | Feature binding ‘…’ points to a concept that is not in the target KG schema | 702 |
| 21 | `C5_BindingHasResolution` | **B** | `Decision!FeatureBinding` | Feature binding ‘…’ has no resolution (entityName for ENTITY/RISK_FACTOR, JSON valueMap for LAB_LEVEL/ICD9_GROUP) | 708 |

## Relation to the paper

- Section 4.3 of the paper states that most invariants are blocking and the others are critiques; the tables above give the exact split (100 blocking, 13 critiques). The paper relates the families to the problems they address: C2 to schema–prompt drift (P1), and C1, C4 and C5 to implicit explanation contracts (P3).
- Invariant **C2_FewShotOutputsMentionOnlyTargetedTypes** is the one that caught the deliberately incomplete renaming in **E1** (schema–prompt drift, problem P1).
- **E2** injects 22 faults, three to five per family, and checks that each is caught by the intended invariant ([experiments.md](experiments.md#e2--fault-detection-by-mutation-analysis)).
