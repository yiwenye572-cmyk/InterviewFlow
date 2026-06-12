"""Run audit test matrix and print summary."""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = ROOT / ".venv" / "Scripts" / "python.exe"
SCRIPTS = [
    "test_layer_a.py",
    "test_screen_batch.py",
    "test_p0.py",
    "test_layer_b.py",
    "test_report_async.py",
    "test_candidate_feedback.py",
    "smoke_test.py",
    "test_audit_edge.py",
]


def main() -> None:
    results: list[tuple[str, str, float]] = []
    for name in SCRIPTS:
        path = ROOT / "scripts" / name
        print(f"\n{'='*60}\n>>> {name}\n{'='*60}")
        t0 = time.time()
        proc = subprocess.run([str(PY), str(path)], cwd=str(ROOT))
        elapsed = time.time() - t0
        status = "PASS" if proc.returncode == 0 else "FAIL"
        results.append((name, status, elapsed))
        if proc.returncode != 0:
            print(f"\n[ABORT] {name} failed — stopping suite")
            break

    print(f"\n{'='*60}\nAUDIT MATRIX\n{'='*60}")
    for name, status, elapsed in results:
        print(f"  {status:4}  {elapsed:6.1f}s  {name}")
    failed = [r for r in results if r[1] == "FAIL"]
    if failed:
        sys.exit(1)
    if len(results) < len(SCRIPTS):
        sys.exit(1)
    print("\nAll audit scripts passed.")


if __name__ == "__main__":
    main()
