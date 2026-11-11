"""E2 runner: run `xaikg-mde check` on every mutant and report detection (paper experiment E2).

For each mutant we record whether (a) the check reported an ERROR (blocking) before any
transformation, and (b) the expected constraint is among the fired ones. Results go to
results/e2-mutation-detection.json and .md.
"""
import json
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
JAR = ROOT / "xaikg-mde" / "target" / "xaikg-mde.jar"
MUTANTS = ROOT / "models" / "mutants"
RESULTS = ROOT / "results"


def check(model_dir: pathlib.Path) -> dict:
    cmd = ["java", "-jar", str(JAR), "check", "--mde-home", str(ROOT / "xaikg-mde"), "-m", str(model_dir)]
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True)
    elapsed = time.perf_counter() - t0
    try:
        report = json.loads(proc.stdout)
    except json.JSONDecodeError:
        report = {"status": "failure", "error": proc.stdout[-500:] + proc.stderr[-500:]}
    report["_exit"] = proc.returncode
    report["_seconds"] = round(elapsed, 2)
    return report


def main() -> None:
    if not JAR.exists():
        sys.exit(f"jar not found: {JAR} (run mvn package in xaikg-mde)")
    index = json.loads((MUTANTS / "index.json").read_text())
    rows = []
    for m in index:
        report = check(MUTANTS / m["id"])
        fired = [v["constraint"] for v in report.get("violations", []) if not v["critique"]]
        unresolved = report.get("unresolvedReferences", [])
        blocked = report["_exit"] != 0
        expected_hit = m["expectedConstraint"] in fired
        # a dangling cross-file reference is caught even earlier, at load time (still before generation)
        caught_at_load = bool(unresolved) and blocked
        rows.append({**m, "blocked": blocked, "expectedConstraintFired": expected_hit,
                     "caughtAtLoad": caught_at_load, "firedConstraints": fired,
                     "unresolvedReferences": len(unresolved), "seconds": report["_seconds"]})
        status = "DETECTED" if blocked else "MISSED  "
        via = m["expectedConstraint"] if expected_hit else ("unresolved reference" if caught_at_load else ", ".join(fired) or "-")
        print(f"{status} {m['id']:<45} via {via}")
    detected = sum(r["blocked"] for r in rows)
    precise = sum(r["expectedConstraintFired"] or r["caughtAtLoad"] for r in rows)
    summary = {"mutants": len(rows), "blockedBeforeGeneration": detected, "expectedConstraintOrLoadError": precise,
               "meanSeconds": round(sum(r["seconds"] for r in rows) / len(rows), 2)}
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "e2-mutation-detection.json").write_text(json.dumps({"summary": summary, "mutants": rows}, indent=2) + "\n")
    md = ["# E2 - Design-time detection of injected model faults", "",
          f"{detected}/{len(rows)} mutants blocked before any transformation; "
          f"{precise}/{len(rows)} caught by the expected constraint (or as an unresolved reference at load time). "
          f"Mean check time {summary['meanSeconds']} s.", "",
          "| Mutant | Family | Fault | Blocked | Caught by |", "|---|---|---|---|---|"]
    for r in rows:
        via = r["expectedConstraint"] if r["expectedConstraintFired"] else ("unresolved reference (load time)" if r["caughtAtLoad"] else ", ".join(r["firedConstraints"]) or "-")
        md.append(f"| {r['id']} | {r['family']} | {r['description']} | {'yes' if r['blocked'] else 'NO'} | {via} |")
    (RESULTS / "e2-mutation-detection.md").write_text("\n".join(md) + "\n")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
