# datasets/

All data of the paper, committed for offline reproducibility. Sources, links, licences, queries and preparation steps are documented in [docs/datasets.md](../docs/datasets.md).

| Folder | Content |
|---|---|
| [`tabular/`](tabular/) | UCI Diabetes 130-US hospitals (CC BY 4.0) |
| [`corpus/`](corpus/) | the 433 source documents (openFDA, MedlinePlus, PubMed, Strack et al. 2014) and the acquisition configuration [`sources.json`](corpus/sources.json) |
| [`gold/bc5cdr/`](gold/bc5cdr/) | the BC5CDR gold standard of experiment E3 |
| [`manifests/`](manifests/) | source URI, licence and SHA-256 of every file |
| [`cache/llm/`](cache/llm/) | the LLM response cache |
| [`raw/`](raw/) | the 438 raw-extraction models (LLM output, input of T2b) |

These datasets are third-party data under their own licences; they are not covered by the Apache License of the code.
