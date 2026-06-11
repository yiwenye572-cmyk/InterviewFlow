"""A-layer focused API smoke test."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import requests

BASE = "http://127.0.0.1:8000"
SAMPLES = Path(__file__).resolve().parent.parent / "samples"


def ok(msg: str) -> None:
    print(f"[PASS] {msg}")


def fail(msg: str) -> None:
    print(f"[FAIL] {msg}")
    sys.exit(1)


def main() -> None:
    try:
        requests.get(f"{BASE}/health", timeout=10).raise_for_status()
        ok("health")
    except Exception as exc:
        fail(f"health / server not running: {exc}")

    with (SAMPLES / "job_description.txt").open("rb") as f:
        job = requests.post(f"{BASE}/api/jobs", files={"file": f}, timeout=60).json()
    job_id = job["id"]
    ok(f"upload JD job_id={job_id}")

    files = [
        ("files", ("resume_good.txt", (SAMPLES / "resume_good.txt").read_bytes(), "text/plain")),
        ("files", ("resume_poor.txt", (SAMPLES / "resume_poor.txt").read_bytes(), "text/plain")),
    ]
    r = requests.post(f"{BASE}/api/resumes?job_id={job_id}", files=files, timeout=60)
    r.raise_for_status()
    ok("upload 2 resumes")

    print("[....] screening (JD extract + match + followups)...")
    t0 = time.time()
    r = requests.post(f"{BASE}/api/screen/{job_id}", timeout=300)
    if r.status_code != 200:
        fail(f"screen {r.status_code}: {r.text[:500]}")
    ok(f"screen ({time.time() - t0:.1f}s)")

    results = requests.get(f"{BASE}/api/screen/{job_id}/results", timeout=30).json()["results"]
    if len(results) < 2:
        fail("expected 2 screening results")
    top = max(results, key=lambda x: x["final_score"])
    low = min(results, key=lambda x: x["final_score"])
    ok(f"ranking top={top['final_score']} low={low['final_score']}")

    # A-layer fields
    for field in ("decision_summary", "dimension_scores", "followups", "parse_quality"):
        if field not in top:
            fail(f"missing field in results: {field}")
    ok("results include A-layer fields")

    if not top.get("dimension_scores"):
        print("[WARN] dimension_scores empty on top candidate")
    else:
        ok(f"dimension_scores={top['dimension_scores']}")

    followups = top.get("followups") or []
    if len(followups) < 1:
        print("[WARN] followups empty, expected 3-5")
    else:
        ok(f"followups count={len(followups)}")

    if top.get("decision_summary"):
        ok(f"decision_summary present")
    else:
        print("[WARN] decision_summary empty")

    resume_id = top["resume_id"]

    detail = requests.get(f"{BASE}/api/screen/{job_id}/detail/{resume_id}", timeout=30).json()
    if "structured" not in detail and detail.get("structured") is None:
        print("[WARN] detail.structured is null")
    else:
        ok("detail endpoint with structured data")

    structured = requests.get(f"{BASE}/api/resumes/{resume_id}/structured", timeout=30).json()
    if structured.get("structured"):
        ok("resume structured endpoint")
    else:
        print("[WARN] structured resume null")

    print("[....] lazy-load question pack...")
    t0 = time.time()
    q = requests.get(f"{BASE}/api/screen/{job_id}/questions/{resume_id}", timeout=300)
    if q.status_code != 200:
        fail(f"questions {q.status_code}: {q.text[:500]}")
    questions = q.json().get("questions") or []
    if len(questions) < 10:
        fail(f"expected >=10 questions, got {len(questions)}")
    ok(f"question pack ({time.time() - t0:.1f}s) count={len(questions)} sample={questions[0]['question'][:40]}...")

    # cached
    q2 = requests.get(f"{BASE}/api/screen/{job_id}/questions/{resume_id}", timeout=30).json()
    if not q2.get("cached"):
        print("[WARN] second question fetch not cached")
    else:
        ok("question pack cached")

    results2 = requests.get(f"{BASE}/api/screen/{job_id}/results", timeout=30).json()["results"]
    top2 = max(results2, key=lambda x: x["final_score"])
    if not top2.get("has_question_pack"):
        print("[WARN] has_question_pack not true after generation")
    else:
        ok("has_question_pack flag set")

    print("\n=== A-layer tests passed ===")


if __name__ == "__main__":
    main()
