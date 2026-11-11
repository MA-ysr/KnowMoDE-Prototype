"""Paths and environment for the artefact. The implementation root is the parent of this package's
project folder (implementation/), so every path below is stable regardless of the cwd."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

IMPL_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(IMPL_ROOT / ".env")


@dataclass(frozen=True)
class Paths:
    root: Path = IMPL_ROOT
    models: Path = IMPL_ROOT / "models" / os.environ.get("XAIKG_USECASE", "diabetes-readmission")
    mde_home: Path = IMPL_ROOT / "xaikg-mde"
    jar: Path = IMPL_ROOT / "xaikg-mde" / "target" / "xaikg-mde.jar"
    metamodels: Path = IMPL_ROOT / "xaikg-mde" / "metamodels"
    generated: Path = IMPL_ROOT / "generated"
    prompts: Path = IMPL_ROOT / "generated" / "prompts"
    datasets: Path = IMPL_ROOT / "datasets"
    tabular: Path = IMPL_ROOT / "datasets" / "tabular"
    corpus: Path = IMPL_ROOT / "datasets" / "corpus"
    gold: Path = IMPL_ROOT / "datasets" / "gold"
    manifests: Path = IMPL_ROOT / "datasets" / "manifests"
    raw: Path = IMPL_ROOT / "datasets" / "raw"           # rawextraction.xmi files (LLM output as models)
    llm_cache: Path = IMPL_ROOT / "datasets" / "cache" / "llm"
    results: Path = IMPL_ROOT / "results"


PATHS = Paths()


def env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"{name} is not set; add it to {IMPL_ROOT / '.env'}")
    return value
