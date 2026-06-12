"""Async screening batch — mirrors home.js upload-and-screen path."""
from __future__ import annotations

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


def poll_batch(batch_id: str, timeout_sec: int = 300) -> dict:
    deadline = time.time() + timeout_sec
    last: dict = {}
    while time.time() < deadline:
        r = requests.get(f"{BASE}/api/screen/batch/{batch_id}", timeout=30)
        if r.status_code != 200:
            fail(f"batch status {r.status_code}: {r.text[:300]}")
        last = r.json()
        if last.get("status") == "completed":
            return last
        time.sleep(1)
    fail(f"batch poll timeout, last={last}")


def main() -> None:
    try:
        requests.get(f"{BASE}/health", timeout=10).raise_for_status()
        ok("health")
    except Exception as exc:
        fail(f"server not running: {exc}")

    with (SAMPLES / "job_description.txt").open("rb") as f:
        job = requests.post(f"{BASE}/api/jobs", files={"file": f}, timeout=60).json()
    job_id = job["id"]
    ok(f"job_id={job_id}")

    files = [
        ("files", ("resume_good.txt", (SAMPLES / "resume_good.txt").read_bytes(), "text/plain")),
        ("files", ("resume_poor.txt", (SAMPLES / "resume_poor.txt").read_bytes(), "text/plain")),
    ]
    up = requests.post(f"{BASE}/api/resumes?job_id={job_id}", files=files, timeout=60)
    if up.status_code != 200:
        fail(f"upload resumes {up.status_code}")
    ok(f"uploaded {up.json().get('count', 0)} resumes")

    resume_list = requests.get(f"{BASE}/api/jobs/{job_id}/resumes", timeout=30).json()
    resume_ids = [r["resume_id"] for r in resume_list.get("resumes", [])]
    if len(resume_ids) < 2:
        fail(f"expected >=2 resumes, got {resume_ids}")

    print("[....] async screen batch...")
    t0 = time.time()
    r = requests.post(
        f"{BASE}/api/screen/{job_id}",
        json={"resume_ids": resume_ids, "async": True},
        timeout=30,
    )
    if r.status_code != 200:
        fail(f"async screen start {r.status_code}: {r.text[:300]}")
    body = r.json()
    batch_id = body.get("batch_id")
    if not batch_id:
        fail(f"no batch_id: {body}")
    ok(f"batch started id={batch_id[:8]}... total={body.get('total')}")

    status = poll_batch(batch_id)
    if status.get("completed", 0) < len(resume_ids):
        fail(f"batch incomplete: {status}")
    if status.get("failed", 0) > 0:
        print(f"[WARN] {status.get('failed')} resume(s) failed in batch")
    ok(f"batch completed in {time.time() - t0:.1f}s")

    results = requests.get(f"{BASE}/api/screen/{job_id}/results", timeout=30).json()
    items = results.get("results") or []
    if len(items) < 2:
        fail(f"expected screening results, got {len(items)}")
    screened = [i for i in items if i.get("final_score") is not None]
    if len(screened) < 1:
        fail("no scored results after batch")
    ok(f"screening results count={len(items)} scored={len(screened)}")

    print("\nAsync screen batch test passed.")


if __name__ == "__main__":
    main()
