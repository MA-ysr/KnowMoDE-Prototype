"""Bridge to the Java MDE runtime (xaikg-mde.jar). The contract: one JSON report on stdout,
exit code 0 ok / 2 model invalid / 1 failure. Python never interprets the M1 models itself."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .config import PATHS


class MdeError(RuntimeError):
    def __init__(self, command: str, report: dict, code: int):
        super().__init__(f"xaikg-mde {command} failed (exit {code}): {report.get('error', report)}")
        self.report = report
        self.code = code


def run(command: str, *args: str, check: bool = True) -> dict:
    if not PATHS.jar.exists():
        raise SystemExit(f"{PATHS.jar} not found: run `make jar` first")
    cmd = ["java", "-jar", str(PATHS.jar), command, "--mde-home", str(PATHS.mde_home), *args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    try:
        report = json.loads(proc.stdout)
    except json.JSONDecodeError:
        report = {"status": "failure", "error": (proc.stdout + proc.stderr)[-2000:]}
    if check and proc.returncode != 0:
        raise MdeError(command, report, proc.returncode)
    report["_exit"] = proc.returncode
    return report


def check(models: Path | None = None) -> dict:
    return run("check", "-m", str(models or PATHS.models), check=False)


def generate(models: Path | None = None, out: Path | None = None) -> dict:
    return run("generate", "-m", str(models or PATHS.models), "-o", str(out or PATHS.generated))


def t2(raw_dir: Path, out: Path, models: Path | None = None) -> dict:
    return run("t2", "-m", str(models or PATHS.models), "--raw", str(raw_dir), "-o", str(out))


def t5(validated: Path, out: Path, models: Path | None = None) -> dict:
    return run("t5", "-m", str(models or PATHS.models), "--validated", str(validated), "-o", str(out))


def t6(out: Path, models: Path | None = None) -> dict:
    return run("t6", "-m", str(models or PATHS.models), "-o", str(out))


def prompt_sidecar(task: str) -> dict:
    """The generated, machine-readable description of an extraction task (T4 side-car)."""
    path = PATHS.prompts / f"{task}.json"
    if not path.exists():
        raise SystemExit(f"{path} not found: run `make generate` first")
    return json.loads(path.read_text(encoding="utf-8"))


def prompt_registry() -> dict:
    path = PATHS.prompts / "prompt-registry.json"
    if not path.exists():
        raise SystemExit(f"{path} not found: run `make generate` first")
    return json.loads(path.read_text(encoding="utf-8"))
