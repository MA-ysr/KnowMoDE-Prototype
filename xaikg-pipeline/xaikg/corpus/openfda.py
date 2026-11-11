"""openFDA drug labels (FDA Structured Product Labels; US Government work, public domain).
One text file per drug of the plan, built from the label sections listed in sources.json."""
from __future__ import annotations

import re
import time

from ..config import PATHS
from ..manifest import load_manifest
from .http import get
from .plan import CorpusPlan
from .text import section, strip_html

API = "https://api.fda.gov/drug/label.json"
LICENCE = "US Government work (FDA), public domain"
TITLES = {
    "boxed_warning": "Boxed warning", "indications_and_usage": "Indications and usage",
    "contraindications": "Contraindications", "warnings_and_cautions": "Warnings and precautions",
    "warnings": "Warnings", "precautions": "Precautions", "adverse_reactions": "Adverse reactions",
    "drug_interactions": "Drug interactions", "use_in_specific_populations": "Use in specific populations",
}


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def _candidates(term: str, limit: int = 10) -> list[dict]:
    r = get(API, params={"search": f'openfda.generic_name:"{term}"', "limit": limit})
    return r.json().get("results", [])


def _score(label: dict, sections: list[str]) -> int:
    present = [s for s in sections if label.get(s)]
    length = sum(len(" ".join(label.get(s, []))) for s in present)
    rx = 1 if "Rx" in " ".join(label.get("openfda", {}).get("product_type", [])).upper() or \
        "PRESCRIPTION" in " ".join(label.get("openfda", {}).get("product_type", [])).upper() else 0
    return rx * 100000 + len(present) * 10000 + min(length, 9999)


def fetch(plan: CorpusPlan, force: bool = False, sleep: float = 0.3) -> dict:
    out = PATHS.corpus / "openfda"
    out.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest(PATHS.manifests, "openfda", out)
    sections = plan.seeds["openfda"]["sections"]
    overrides = plan.seeds["openfda"]["search_overrides"]
    report = {"fetched": [], "cached": [], "missing": []}
    for drug in plan.drugs:
        rel = f"{_slug(drug)}.txt"
        if not force and manifest.has(rel):
            report["cached"].append(drug)
            continue
        best, best_term = None, None
        for term in overrides.get(drug, [drug, f"{drug} hydrochloride"]):
            try:
                cands = _candidates(term)
            except RuntimeError as e:  # 404 = no match for this term
                if "404" in str(e):
                    cands = []
                else:
                    raise
            time.sleep(sleep)
            cands = [c for c in cands if any(c.get(s) for s in sections)]
            if cands:
                cand = max(cands, key=lambda c: _score(c, sections))
                if best is None or _score(cand, sections) > _score(best, sections):
                    best, best_term = cand, term
        if best is None:
            report["missing"].append(drug)   # e.g. withdrawn drugs or dataset artefacts
            continue
        ofda = best.get("openfda", {})
        header = (f"# FDA prescribing information: {drug}\n\n"
                  f"Generic name: {', '.join(ofda.get('generic_name', [best_term]))}\n"
                  f"Brand name: {', '.join(ofda.get('brand_name', ['n/a']))}\n"
                  f"Pharmacologic class: {', '.join(ofda.get('pharm_class_epc', []) or ['n/a'])}\n"
                  f"Label set id: {best.get('set_id', 'n/a')}, effective {best.get('effective_time', 'n/a')}\n\n")
        body = "".join(section(TITLES[s], strip_html(" ".join(best[s]))) for s in sections if best.get(s))
        (out / rel).write_text(header + body, encoding="utf-8")
        manifest.record(rel, uri=f"{API}?search=openfda.generic_name:%22{best_term}%22", licence=LICENCE,
                        collection="corpus/openfda", title=f"FDA label: {drug}", setId=best.get("set_id"),
                        effectiveTime=best.get("effective_time"), matchedTerm=best_term,
                        sections=[s for s in sections if best.get(s)])
        report["fetched"].append(drug)
    manifest.save()
    return report
