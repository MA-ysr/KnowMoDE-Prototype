# Datasets: sources, acquisition and licences

All data used in the paper is **committed** in [`datasets/`](../datasets/), so every experiment can be re-run without network access. The data were collected with the acquisition scripts of the Python project ([`xaikg-pipeline/xaikg/corpus/`](../xaikg-pipeline/xaikg/corpus/)), configured by [`datasets/corpus/sources.json`](../datasets/corpus/sources.json) and by the case-study models. Every file is recorded in a manifest ([`datasets/manifests/`](../datasets/manifests/)) with its source URI, licence and SHA-256 checksum. Document acquisition lies outside the framework (paper, Section 4.5): the corpus was assembled by the authors with these scripts.

> **Licences.** The datasets are third-party data redistributed for research reproducibility under their own licences and terms of use (table below). They are **not** covered by the Apache License of the code (see [`NOTICE`](../NOTICE)).

## Overview

| Dataset | Used for | Folder | Files | Source | Licence | Fetched by |
|---|---|---|---|---|---|---|
| Diabetes 130-US hospitals for years 1999–2008 (UCI dataset 296) | training and testing the predictor | [`datasets/tabular/`](../datasets/tabular/) | 2 | [UCI Machine Learning Repository](https://archive.ics.uci.edu/dataset/296/diabetes+130-us+hospitals+for+years+1999-2008) | CC BY 4.0 | [`dataset.py`](../xaikg-pipeline/xaikg/corpus/dataset.py) (`make data`) |
| openFDA drug labels | `drug_label_extraction` | [`datasets/corpus/openfda/`](../datasets/corpus/openfda/) | 12 | [openFDA drug label API](https://open.fda.gov/apis/drug/label/) (`https://api.fda.gov/drug/label.json`) | US Government work (FDA), public domain | [`openfda.py`](../xaikg-pipeline/xaikg/corpus/openfda.py) (`make corpus`) |
| MedlinePlus health topics | `patient_education_extraction` | [`datasets/corpus/medlineplus/`](../datasets/corpus/medlineplus/) | 58 | [MedlinePlus web service](https://medlineplus.gov/about/developers/webservices/) (`db=healthTopics`) | public domain (NLM); attribution: MedlinePlus.gov | [`medlineplus.py`](../xaikg-pipeline/xaikg/corpus/medlineplus.py) (`make corpus`) |
| PubMed abstracts | `literature_extraction` (310), `guideline_extraction` (57) | [`datasets/corpus/pubmed/`](../datasets/corpus/pubmed/) | 362 | [NCBI E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25501/) (`esearch`, `efetch`) | freely accessible (NLM); publisher copyright may apply; research use only | [`pubmed.py`](../xaikg-pipeline/xaikg/corpus/pubmed.py) (`make corpus`) |
| Full text of Strack et al. (2014), doi:[10.1155/2014/781670](https://doi.org/10.1155/2014/781670) | `literature_extraction` | [`datasets/corpus/papers/`](../datasets/corpus/papers/) | 1 | [Europe PMC](https://europepmc.org/) (searched by DOI, full-text XML) | CC BY 3.0 | [`pubmed.py`](../xaikg-pipeline/xaikg/corpus/pubmed.py) (`make corpus`) |
| BC5CDR (BioCreative V Chemical Disease Relation corpus) | gold standard of [E3](experiments.md#e3--validation-against-a-gold-standard) (never loaded into the graph) | [`datasets/gold/bc5cdr/`](../datasets/gold/bc5cdr/) | 1 (JSON lines) | [`JHnlp/BioCreative-V-CDR-Corpus`](https://github.com/JHnlp/BioCreative-V-CDR-Corpus) (`CDR_Data.zip`) | free for research use (see the corpus licence) | [`gold.py`](../xaikg-pipeline/xaikg/corpus/gold.py) (`make corpus`) |

Derived data, also committed:

| Data | Folder | Content |
|---|---|---|
| LLM response cache | [`datasets/cache/llm/`](../datasets/cache/llm/) | every LLM response, keyed by provider, model, prompt and chunk; replays extraction and E3 without an API key |
| Raw-extraction models | [`datasets/raw/`](../datasets/raw/) | 438 models, one per document and extraction task (five abstracts are processed by two tasks), each with the full source text (input of T2b) |

## The corpus: 433 distinct documents

| Collection | Distinct documents | Processed by |
|---|---|---|
| openFDA drug labels | 12 | drug-label task |
| MedlinePlus health topics | 58 | patient-education task |
| PubMed research abstracts | 310 | literature task |
| PubMed guideline abstracts | 57, five of which are also research abstracts | guideline task |
| Strack et al. (2014), full text | 1 | literature task |
| **Total** | **12 + 58 + 1 + 362 = 433** (362 = 310 + 57 − 5) | 438 document–task pairs |

## How each source was fetched

### openFDA drug labels

One label per medication bound in the decision-binding model, searched by generic name (`openfda.generic_name`). Name overrides for three searches are configured in `sources.json` (`insulin` → *insulin human*, *insulin glargine*, *insulin lispro*; the two metformin combinations → their hydrochloride names). Labels were found for 12 of the 14 bound medications (none for chlorpropamide and rosiglitazone): acarbose, glimepiride, glipizide, glipizide and metformin, glyburide, glyburide and metformin, insulin, metformin, miglitol, nateglinide, pioglitazone, repaglinide. Nine label sections are kept: `boxed_warning`, `indications_and_usage`, `contraindications`, `warnings_and_cautions`, `warnings`, `precautions`, `adverse_reactions`, `drug_interactions`, `use_in_specific_populations`.

### MedlinePlus health topics

Health-topic summaries only (`db=healthTopics`; the copyrighted drug-information pages are deliberately not fetched). Search terms: the 18 terms of `sources.json` (*diabetes, diabetes type 2, diabetes complications, diabetes medicines, A1C, blood sugar, hypoglycemia, hyperglycemia, insulin, diabetic kidney disease, diabetic heart disease, heart failure, kidney disease, high blood pressure, diabetic foot, diabetic eye problems, after a hospital stay, metformin*) plus the condition names of the case-study models, at most 3 topics per term. Result: 58 distinct topics.

### PubMed abstracts

Every query is sent to `esearch` as:

```text
(<query>) [AND (<filter>)] AND humans[MeSH Terms] AND english[Language] AND 2005:3000[dp] AND hasabstract
```

sorted by relevance, with at most 40 results per query (30 for the second guideline query). Because PubMed's relevance ranking changes over time, a query is run once and its results are **pinned** in [`pubmed.manifest.json`](../datasets/manifests/pubmed.manifest.json): later runs re-fetch exactly the same PMIDs (`--force` re-runs the searches).

**Research abstracts (literature task): 10 queries, 310 abstracts.** Each abstract is attributed to the first query that returned it.

| Query | Abstracts |
|---|---|
| `diabetes hospital readmission risk factors` | 40 |
| `HbA1c hospital readmission` | 38 |
| `heart failure diabetes readmission` | 36 |
| `inpatient hyperglycemia readmission` | 35 |
| `diabetes 30-day readmission predictors` | 33 |
| `diabetes emergency department visits readmission` | 33 |
| `chronic kidney disease diabetes readmission` | 28 |
| `diabetes readmission discharge skilled nursing facility` | 26 |
| `hypoglycemia hospital readmission insulin` | 22 |
| `diabetes polypharmacy readmission` | 19 |
| **Total** | **310** |

**Guideline abstracts (guideline task): 2 queries, 57 distinct abstracts** (40 and 18 results, one in common). Five of them were also returned by research queries, so they are processed by both tasks.

1. *Inpatient diabetes management: practice guidelines, consensus statements, standards of care* (at most 40 results):
   ```text
   (diabet*[ti] OR hyperglyc*[ti] OR hypoglyc*[ti] OR glycemic[ti] OR glycaemic[ti] OR insulin[ti]) AND (hospital*[ti] OR inpatient*[ti] OR in-patient*[ti] OR noncritical*[ti] OR non-critical*[ti] OR perioperative[ti] OR peri-operative[ti] OR surgery[ti] OR "critically ill"[ti])
   filter: guideline[pt] OR practice guideline[pt] OR consensus development conference[pt] OR consensus[ti] OR guideline*[ti] OR recommendation*[ti] OR "position statement"[ti] OR "standards of care"[ti] OR "standards of medical care"[ti]
   ```
2. *Hospital discharge and transitions of care for patients with diabetes: recommendations* (at most 30 results):
   ```text
   (diabet*[ti] OR hyperglyc*[ti] OR insulin[ti] OR glycemic[ti] OR glycaemic[ti]) AND (discharge*[ti] OR "transition of care"[ti] OR "transitions of care"[ti] OR "hospital to home"[ti] OR post-discharge[ti]) AND (hospital*[tiab] OR inpatient*[tiab])
   filter: guideline[pt] OR practice guideline[pt] OR consensus development conference[pt] OR review[pt] OR consensus[ti] OR guideline*[ti] OR recommendation*[ti] OR "position statement"[ti] OR practical[ti] OR "best practice"[ti]
   ```

### Full text of Strack et al. (2014)

The paper that introduced the UCI dataset is open access (CC BY 3.0). It is located in Europe PMC by its DOI and its full-text XML (abstract and body sections) is converted to plain text.

### BC5CDR gold standard

The gold corpus `CDR.Corpus.v010516` (500 training, 500 development and 500 test abstracts with expert-annotated, MeSH-normalized chemical-induced-disease relations) is converted to JSON lines; the system outputs shipped in the same archive are not used. E3 draws 60 test abstracts with seed 7, which contain 131 gold relations.

## The tabular data and the predictor

[`ml/readmission.py`](../xaikg-pipeline/xaikg/ml/readmission.py) prepares the UCI table as in Strack et al. (2014):

| Step | Records |
|---|---|
| encounters in the dataset | 101,766 |
| first encounter of each patient | 71,518 |
| minus encounters ending in death or hospice discharge (discharge codes 11, 13, 14, 19, 20, 21) | −1,545 |
| **patients kept** | **69,973** |
| readmitted within 30 days (`readmitted == "<30"`) | 6,277 (8.97%) |
| stratified 75/25 split (seed 42): training / test | 52,479 / 17,494 |

The predictor is scikit-learn's `HistGradientBoostingClassifier` (300 iterations, learning rate 0.05, balanced class weights, seed 42) on the 33 features declared in the decision-binding model; SHAP's `TreeExplainer` computes the attributions. Its discrimination, measured by the area under the ROC curve, is 0.6466 on the 17,494 held-out patients ([model card](../results/model/model-card.json)). The 200 encounters of [E4–E6](experiments.md#e4--traceability-of-the-delivered-explanations) are drawn from the test set with seed 11.

## Re-fetching the data

`make data` and `make corpus` re-run the acquisition (network access required; NCBI and openFDA are rate-limited politely by [`http.py`](../xaikg-pipeline/xaikg/corpus/http.py)). Pinned PubMed queries are re-fetched by PMID, and the manifests' checksums show whether a source has changed since the paper.
