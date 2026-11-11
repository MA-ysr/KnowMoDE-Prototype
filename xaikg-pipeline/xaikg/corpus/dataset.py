"""UCI 296: Diabetes 130-US hospitals for years 1999-2008 (CC BY 4.0). Trains the readmission model.
Never sent to the LLM."""
from __future__ import annotations

import io
import zipfile

from ..config import PATHS
from ..manifest import load_manifest
from .http import get

UCI_ZIP = "https://archive.ics.uci.edu/static/public/296/diabetes+130-us+hospitals+for+years+1999-2008.zip"
LICENCE = "CC BY 4.0 (UCI Machine Learning Repository, dataset 296)"
FILES = {"diabetic_data.csv": "dataset_diabetes/diabetic_data.csv", "IDS_mapping.csv": "dataset_diabetes/IDS_mapping.csv"}


def fetch(force: bool = False) -> dict:
    out = PATHS.tabular
    out.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest(PATHS.manifests, "tabular", out)
    if not force and all(manifest.has(name) for name in FILES):
        return {"status": "cached", "files": list(FILES)}
    r = get(UCI_ZIP, timeout=300)
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        names = set(z.namelist())
        for target, inner in FILES.items():
            member = inner if inner in names else next((n for n in names if n.endswith("/" + target) or n == target), None)
            if member is None:
                raise RuntimeError(f"{target} not found in UCI archive: {sorted(names)[:10]}")
            (out / target).write_bytes(z.read(member))
            manifest.record(target, uri=UCI_ZIP, licence=LICENCE, collection="tabular",
                            title="Diabetes 130-US hospitals for years 1999-2008", archiveMember=member)
    manifest.save()
    rows = sum(1 for _ in (out / "diabetic_data.csv").open(encoding="utf-8")) - 1
    return {"status": "downloaded", "files": list(FILES), "encounters": rows}
