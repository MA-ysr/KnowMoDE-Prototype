"""PubMed abstracts via NCBI E-utilities, and open-access full texts via Europe PMC.
Abstracts are freely accessible from NLM; copyright of the abstract text may remain with the
publisher, so they are used for research extraction only and never redistributed."""
from __future__ import annotations

import time

from lxml import etree

from ..config import PATHS
from ..manifest import load_manifest, now_iso
from .http import get
from .plan import CorpusPlan
from .text import tidy

ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
EPMC_SEARCH = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
EPMC_FULLTEXT = "https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"
LICENCE_ABSTRACT = "PubMed abstract (NLM); freely accessible, publisher copyright may apply; research use only"
COLLECTION = "corpus/pubmed"


def _term(query: str, min_year: int, filter_: str | None = None) -> str:
    """The esearch term: the query, its optional filter, and the common restrictions (human studies,
    English, publication year, abstract available)."""
    return (f"({query})" + (f" AND ({filter_})" if filter_ else "")
            + f" AND humans[MeSH Terms] AND english[Language] AND {min_year}:3000[dp] AND hasabstract")


def _esearch(query: str, retmax: int, min_year: int, filter_: str | None = None) -> list[str]:
    r = get(ESEARCH, params={"db": "pubmed", "term": _term(query, min_year, filter_), "retmax": retmax,
                             "retmode": "json", "sort": "relevance"})
    return r.json()["esearchresult"]["idlist"]


def _queries(cfg: dict) -> list[dict]:
    """Queries of sources.json: a plain string, or {query, filter, max_per_query, topic}."""
    out = []
    for q in cfg["queries"]:
        q = {"query": q} if isinstance(q, str) else q
        out.append({"query": q["query"], "filter": q.get("filter"), "max": int(q.get("max_per_query", cfg["max_per_query"])),
                    "topic": q.get("topic"), "collection": q.get("collection", COLLECTION)})
    return out


def _efetch(pmids: list[str]) -> list[dict]:
    r = get(EFETCH, params={"db": "pubmed", "id": ",".join(pmids), "retmode": "xml"}, timeout=120)
    root = etree.fromstring(r.content)
    out = []
    for art in root.iter("PubmedArticle"):
        pmid = art.findtext(".//PMID")
        title = "".join(art.find(".//ArticleTitle").itertext()) if art.find(".//ArticleTitle") is not None else ""
        parts = []
        for ab in art.iter("AbstractText"):
            label = ab.get("Label")
            txt = "".join(ab.itertext()).strip()
            parts.append(f"{label}: {txt}" if label else txt)
        year = art.findtext(".//PubDate/Year") or art.findtext(".//PubDate/MedlineDate") or ""
        journal = art.findtext(".//Journal/Title") or ""
        doi = next((e.text for e in art.iter("ArticleId") if e.get("IdType") == "doi"), None)
        if parts:
            out.append({"pmid": pmid, "title": tidy(title), "abstract": tidy("\n\n".join(parts)),
                        "year": year, "journal": journal, "doi": doi})
    return out


def fetch_abstracts(plan: CorpusPlan, force: bool = False, sleep: float = 0.4) -> dict:
    """All abstracts live in corpus/pubmed with one manifest. A query may name a sub-collection
    (`collection`, e.g. corpus/pubmed/guidelines) so that an extraction task can process exactly the
    abstracts retrieved for its purpose; the manifest records it per file (`collection`, `alsoIn`)."""
    out = PATHS.corpus / "pubmed"
    out.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest(PATHS.manifests, "pubmed", out)
    cfg = plan.seeds["pubmed"]
    queries = _queries(cfg)
    collection_of = {q["query"]: q["collection"] for q in queries}
    # PubMed's relevance ranking is not stable over time: a query that has already been run is never
    # run again (its PMIDs are pinned in the manifest); a query new to sources.json is run once and its
    # results are pinned in turn. --force re-runs every query (discovery mode).
    pinned = {rel[:-4]: e.get("query", "") for rel, e in manifest.entries.items() if rel.endswith(".txt")}
    already_run = set(pinned.values()) | set(manifest.searches)
    wanted: dict[str, str] = {} if force else dict(pinned)
    searched = []
    for q in queries:
        if q["query"] in already_run and not force:
            continue
        ids = _esearch(q["query"], q["max"], cfg["min_year"], q["filter"])
        for pmid in ids:
            rel = f"{pmid}.txt"
            if rel in manifest.entries and q["collection"] not in manifest.collections_of(rel):
                # already in the corpus through another collection: record the membership, no new download
                manifest.entries[rel].setdefault("alsoIn", []).append(q["collection"])
            wanted.setdefault(pmid, q["query"])
        manifest.searches[q["query"]] = {"searchedAt": now_iso(), "topic": q["topic"], "collection": q["collection"],
                                         "filter": q["filter"], "retmax": q["max"], "minYear": cfg["min_year"], "pmids": ids}
        searched.append(q["query"])
        time.sleep(sleep)
    todo = [p for p in wanted if force or not manifest.has(f"{p}.txt")]
    fetched = 0
    for i in range(0, len(todo), 50):
        for a in _efetch(todo[i:i + 50]):
            rel = f"{a['pmid']}.txt"
            text = (f"# PubMed {a['pmid']}: {a['title']}\n\n{a['journal']} ({a['year']})"
                    + (f", doi:{a['doi']}" if a["doi"] else "") + "\n\n" + a["abstract"] + "\n")
            (out / rel).write_text(text, encoding="utf-8")
            manifest.record(rel, uri=f"https://pubmed.ncbi.nlm.nih.gov/{a['pmid']}/", licence=LICENCE_ABSTRACT,
                            collection=collection_of.get(wanted[a["pmid"]], COLLECTION), title=a["title"], year=a["year"], journal=a["journal"],
                            doi=a["doi"], query=wanted[a["pmid"]])
            fetched += 1
        time.sleep(sleep)
    manifest.save()
    return {"candidates": len(wanted), "fetched": fetched, "cached": len(wanted) - len(todo), "queriesRun": len(searched)}


def fetch_papers(plan: CorpusPlan, force: bool = False) -> dict:
    out = PATHS.corpus / "papers"
    out.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest(PATHS.manifests, "papers", out)
    report = {"fetched": [], "cached": [], "missing": []}
    for paper in plan.seeds["papers"]:
        rel = f"{paper['id']}.txt"
        if not force and manifest.has(rel):
            report["cached"].append(paper["id"])
            continue
        r = get(EPMC_SEARCH, params={"query": f"DOI:{paper['doi']}", "format": "json"})
        hits = r.json().get("resultList", {}).get("result", [])
        pmcid = next((h.get("pmcid") for h in hits if h.get("pmcid")), None)
        if not pmcid:
            report["missing"].append(paper["id"])
            continue
        xml = get(EPMC_FULLTEXT.format(pmcid=pmcid), timeout=120).content
        root = etree.fromstring(xml)
        lines = [f"# {paper['title']}\n", f"doi:{paper['doi']} ({pmcid}), licence {paper['licence']}\n"]
        abstract = root.find(".//abstract")
        if abstract is not None:
            lines.append("## Abstract\n")
            lines.append(tidy(" ".join(abstract.itertext())) + "\n")
        body = root.find(".//body")
        if body is not None:
            for sec in body.iter("sec"):
                title = sec.find("title")
                if title is not None and title.text:
                    lines.append(f"## {tidy(''.join(title.itertext()))}\n")
                for p in sec.findall("p"):
                    txt = tidy(" ".join(p.itertext()))
                    if txt:
                        lines.append(txt + "\n")
        (out / rel).write_text("\n".join(lines), encoding="utf-8")
        manifest.record(rel, uri=f"https://doi.org/{paper['doi']}", licence=paper["licence"], collection="corpus/papers",
                        title=paper["title"], pmcid=pmcid)
        report["fetched"].append(paper["id"])
    manifest.save()
    return report
