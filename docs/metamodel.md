# The XAI-KG metamodel

The five concerns of a KG-based explanation pipeline are reified as five packages of one metamodel, `xaikg-mde/metamodels/xaikg.ecore`. Every case-study model of Phase 1 conforms to it (paper, Section 4.2, *Phase 1: Modeling the Pipeline*). Three auxiliary metamodels type the intermediate models of the transformations; they are documented in [transformations.md](transformations.md).

![The XAI-KG metamodel (paper, Fig. 3)](images/paper-fig3-metamodel.png)

## Packages and root classes

Each model has one root class. The roots of the four other models reference the root of the KG Schema model (`targetSchema`), and the Decision Binding root also references the Explainability root (`explainability`).

| Package (nsPrefix) | Model written by | Root class | Classes |
|---|---|---|---|
| KG Schema (`kgschema`) | domain experts | `KGSchemaDefinition` | `KGSchemaDefinition`, `KGConcept`, `CanonicalEntity`, `KGProperty`, `KGRelation`, `KGQueryPattern`; enumerations `PropertyDataType` |
| LLM Pipeline (`llmorchestration`) | AI engineers | `LLMPipelineConfig` | `LLMPipelineConfig`, `ExtractionTask`, `PromptTemplate`, `FewShotExample`, `ChunkingStrategy`; enumerations `SplitterType`, `OutputFormat` |
| Validation Policy (`validation`) | compliance officers | `ValidationConfig` | `ValidationConfig`, `ValidationRule`; enumerations `ValidationSeverity`, `ValidationRuleType`, `RuleScope` |
| Explainability (`explainability`) | compliance officers | `ExplainabilityConfig` | `ExplainabilityConfig`, `Audience`, `PresentationBudget`, `ExplanationType`, `ExplanationTemplate`; enumerations `ExplanationCategory`, `TechnicalLevel`, `TemplateFormat`, `FactAllocation` |
| Decision Binding (`decision`) | AI engineers | `DecisionBindingConfig` | `DecisionBindingConfig`, `AIModelSpec`, `DecisionClass`, `FeatureBinding`; enumerations `AttributionMethod`, `BindingKind` |

## Cross-package references

The metamodel has 11 cross-package references, all leading to the KG Schema or the Explainability package. They are typed, so they are checked when the models are loaded: an unresolved reference is reported before the constraint layer runs.

| From | Reference | To |
|---|---|---|
| `LLMPipelineConfig` (LLM Pipeline) | `targetSchema` | `KGSchemaDefinition` (KG Schema) |
| `PromptTemplate` (LLM Pipeline) | `targetConcepts` [0..*] | `KGConcept` (KG Schema) |
| `PromptTemplate` (LLM Pipeline) | `targetRelations` [0..*] | `KGRelation` (KG Schema) |
| `ValidationConfig` (Validation Policy) | `targetSchema` | `KGSchemaDefinition` (KG Schema) |
| `ExplainabilityConfig` (Explainability) | `targetSchema` | `KGSchemaDefinition` (KG Schema) |
| `ExplainabilityConfig` (Explainability) | `traceQueryPattern` | `KGQueryPattern` (KG Schema) |
| `ExplanationType` (Explainability) | `queryPatterns` [0..*] | `KGQueryPattern` (KG Schema) |
| `DecisionBindingConfig` (Decision Binding) | `targetSchema` | `KGSchemaDefinition` (KG Schema) |
| `DecisionBindingConfig` (Decision Binding) | `explainability` | `ExplainabilityConfig` (Explainability) |
| `DecisionClass` (Decision Binding) | `explanationTypes` [0..*] | `ExplanationType` (Explainability) |
| `FeatureBinding` (Decision Binding) | `concept` | `KGConcept` (KG Schema) |

## Classes by package

The tables list the attributes of each class with their types and the references with their target class. `[*]` marks a many-valued feature, and "(containment)" a containment reference.

### KG Schema

| Class | Attributes | References |
|---|---|---|
| `KGSchemaDefinition` | name: String, nsURI: String, description: String | concepts → KGConcept[*] (containment), relations → KGRelation[*] (containment), queryPatterns → KGQueryPattern[*] (containment) |
| `KGConcept` | name: String, description: String, uri: String | properties → KGProperty[*] (containment), canonicalEntities → CanonicalEntity[*] (containment) |
| `CanonicalEntity` | name: String, description: String, aliases: String[*], pattern: String, isModifiable: Boolean, plainLabel: String | – |
| `KGProperty` | name: String, description: String, dataType: PropertyDataType, isRequired: Boolean, isExplainable: Boolean | – |
| `KGRelation` | id: String, name: String, semantics: String, minCardinality: Int, maxCardinality: Int | source → KGConcept, target → KGConcept |
| `KGQueryPattern` | name: String, description: String, cypherTemplate: String, parameters: String[*], actionableOnly: Boolean | – |

### LLM Pipeline

| Class | Attributes | References |
|---|---|---|
| `LLMPipelineConfig` | name: String, description: String | targetSchema → KGSchemaDefinition, extractionTasks → ExtractionTask[*] (containment) |
| `ExtractionTask` | name: String, description: String, llmModel: String, temperature: Double, maxTokens: Int, sourceCollection: String | promptTemplate → PromptTemplate (containment), chunkingStrategy → ChunkingStrategy (containment) |
| `PromptTemplate` | name: String, systemInstruction: String, outputFormat: OutputFormat | targetConcepts → KGConcept[*], targetRelations → KGRelation[*], fewShotExamples → FewShotExample[*] (containment) |
| `FewShotExample` | name: String, inputText: String, expectedOutput: String | – |
| `ChunkingStrategy` | chunkSize: Int, overlap: Int, splitter: SplitterType | – |

### Validation Policy

| Class | Attributes | References |
|---|---|---|
| `ValidationConfig` | name: String, description: String, confidenceThreshold: Double | targetSchema → KGSchemaDefinition, rules → ValidationRule[*] (containment) |
| `ValidationRule` | name: String, description: String, ruleType: ValidationRuleType, scope: RuleScope, oclExpression: String, severity: ValidationSeverity, errorMessage: String | – |

### Explainability

| Class | Attributes | References |
|---|---|---|
| `ExplainabilityConfig` | name: String, description: String, retrievalLimit: Int | targetSchema → KGSchemaDefinition, traceQueryPattern → KGQueryPattern, audiences → Audience[*] (containment), explanationTypes → ExplanationType[*] (containment), templates → ExplanationTemplate[*] (containment) |
| `Audience` | role: String, technicalLevel: TechnicalLevel, informationNeeds: String, requiresFullProvenance: Boolean | presentationBudget → PresentationBudget (containment) |
| `PresentationBudget` | maxFacts: Int, maxWords: Int, allowCodes: Boolean, plainLanguage: Boolean, allocation: FactAllocation | – |
| `ExplanationType` | name: String, category: ExplanationCategory, description: String | queryPatterns → KGQueryPattern[*], audiences → Audience[*], template → ExplanationTemplate |
| `ExplanationTemplate` | name: String, format: TemplateFormat, templatePattern: String | – |

### Decision Binding

| Class | Attributes | References |
|---|---|---|
| `DecisionBindingConfig` | name: String | targetSchema → KGSchemaDefinition, explainability → ExplainabilityConfig, aiModel → AIModelSpec (containment), decisionClasses → DecisionClass[*] (containment), featureBindings → FeatureBinding[*] (containment) |
| `AIModelSpec` | name: String, version: String, taskType: String, trainingDataset: String, attributionMethod: AttributionMethod, featureNames: String[*] | – |
| `DecisionClass` | name: String, label: String, positive: Boolean, predictedOutcome: String, threshold: Double | explanationTypes → ExplanationType[*] |
| `FeatureBinding` | featureName: String, description: String, kind: BindingKind, entityName: String, valueMap: String, activeWhen: String | concept → KGConcept |