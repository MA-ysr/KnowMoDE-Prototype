"""MedlinePlus health topics (NIH/NLM). Health-topic summaries are public domain; the drug
information pages (AHFS) are copyrighted and deliberately NOT fetched (db=healthTopics only).
Usage rules: https://medlineplus.gov/about/using/usingcontent/"""
from __future__ import annotations

import re
import time

from lxml import etree

from ..config import PATHS
from ..manifest import load_manifest
from .http import get
from .plan import CorpusPlan
from .text import strip_html, tidy

API = "https://wsearch.nlm.nih.gov/ws/query"
LICENCE = "MedlinePlus health topic summary (NLM), public domain; attribution: MedlinePlus.gov"


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def _topics(term: str, retmax: int) -> list[dict]:
    r = get(API, params={"db": "healthTopics", "term": term, "retmax": retmax, "rettype": "all"})
    root = etree.fromstring(r.content)
    out = []
    for doc in root.iter("document"):
        fields: dict[str, list[str]] = {}
        for c in doc.iter("content"):
            fields.setdefault(c.get("name"), []).append("".join(c.itertext()))
        out.append({"url": doc.get("url"), "rank": doc.get("rank"), "title": strip_html(fields.get("title", [""])[0]),
                    "summary": strip_html(" ".join(fields.get("FullSummary", []))),
                    "alsoCalled": [strip_html(x) for x in fields.get("altTitle", [])],
                    "groups": [strip_html(x) for x in fields.get("groupName", [])]})
    return out


def fetch(plan: CorpusPlan, force: bool = False, sleep: float = 1.0) -> dict:
    out = PATHS.corpus / "medlineplus"
    out.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest(PATHS.manifests, "medlineplus", out)
    retmax = plan.seeds["medlineplus"]["max_topics_per_term"]
    report = {"fetched": [], "cached": [], "terms_without_topic": []}
    seen_urls = {e.get("uri") for e in manifest.entries.values()}
    for term in plan.medlineplus_terms():
        topics = _topics(term, retmax)
        time.sleep(sleep)
        if not topics:
            report["terms_without_topic"].append(term)
            continue
        for t in topics:
            if not t["summary"] or len(t["summary"]) < 200:
                continue
            rel = f"{_slug(t['title'])}.txt"
            if (t["url"] in seen_urls or manifest.has(rel)) and not force:
                if rel not in report["cached"]:
                    report["cached"].append(rel)
                continue
            text = (f"# MedlinePlus health topic: {t['title']}\n\n"
                    + (f"Also called: {', '.join(t['alsoCalled'])}\n\n" if t["alsoCalled"] else "")
                    + tidy(t["summary"]) + "\n")
            (out / rel).write_text(text, encoding="utf-8")
            manifest.record(rel, uri=t["url"], licence=LICENCE, collection="corpus/medlineplus",
                            title=t["title"], searchTerm=term)
            seen_urls.add(t["url"])
            report["fetched"].append(rel)
    manifest.save()
    return report
