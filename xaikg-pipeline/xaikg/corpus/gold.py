"""Gold standards for experiment E3 (never loaded into the KG).
BC5CDR: BioCreative V chemical-disease relation corpus (PubTator format), 1,500 PubMed abstracts
with chemical-induced disease (CID) relations, MeSH-normalised."""
from __future__ import annotations

import io
import json
import zipfile

from ..config import PATHS
from ..manifest import load_manifest
from .http import get
from .plan import CorpusPlan


def parse_pubtator(text: str) -> list[dict]:
    docs, cur = [], None
    for line in text.splitlines():
        if not line.strip():
            if cur:
                docs.append(cur)
            cur = None
            continue
        if "|t|" in line or "|a|" in line:
            pmid, kind, content = line.split("|", 2)
            if cur is None or cur["pmid"] != pmid:
                if cur:
                    docs.append(cur)
                cur = {"pmid": pmid, "title": "", "abstract": "", "mentions": [], "relations": []}
            cur["title" if kind == "t" else "abstract"] = content
            continue
        parts = line.split("\t")
        if cur is None:
            continue
        if len(parts) >= 4 and parts[1] == "CID":
            cur["relations"].append({"type": "CID", "chemical": parts[2], "disease": parts[3]})
        elif len(parts) >= 6:
            cur["mentions"].append({"start": int(parts[1]), "end": int(parts[2]), "mention": parts[3],
                                    "type": parts[4], "mesh": parts[5]})
    if cur:
        docs.append(cur)
    return docs


def fetch_bc5cdr(plan: CorpusPlan, force: bool = False) -> dict:
    out = PATHS.gold / "bc5cdr"
    out.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest(PATHS.manifests, "gold-bc5cdr", out)
    if not force and manifest.has("bc5cdr.jsonl"):
        return {"status": "cached", "documents": sum(1 for _ in (out / "bc5cdr.jsonl").open(encoding="utf-8"))}
    url = plan.seeds["gold"]["bc5cdr_zip"]
    r = get(url, timeout=300)
    docs: list[dict] = []
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        # Only the gold corpus (CDR.Corpus.v010516: 500 training, 500 development, 500 test abstracts).
        # The archive also ships the DNorm and tmChem system outputs on the test set (automatic
        # annotations without CID relations); those are not gold data and are skipped.
        members = [n for n in z.namelist() if n.endswith(".PubTator.txt") and "CDR.Corpus" in n
                   and not n.split("/")[-1].startswith("._")]
        if not members:
            raise RuntimeError(f"no PubTator files in {url}: {z.namelist()[:20]}")
        for m in sorted(members):
            split = "train" if "Training" in m else "dev" if "Development" in m else "test" if "Test" in m else "other"
            raw = z.read(m)
            try:
                content = raw.decode("utf-8")
            except UnicodeDecodeError:  # one of the corpus files is Latin-1 encoded
                content = raw.decode("latin-1")
            for d in parse_pubtator(content):
                d["split"] = split
                docs.append(d)
    with (out / "bc5cdr.jsonl").open("w", encoding="utf-8") as f:
        for d in docs:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    manifest.record("bc5cdr.jsonl", uri=url, licence=plan.seeds["gold"]["bc5cdr_licence"], collection="gold/bc5cdr",
                    title="BioCreative V CDR corpus (PubTator), parsed to JSONL", documents=len(docs),
                    relations=sum(len(d["relations"]) for d in docs))
    manifest.save()
    return {"status": "downloaded", "documents": len(docs), "relations": sum(len(d["relations"]) for d in docs)}
