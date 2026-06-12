"""Edge-case checks for project audit: DELETE job, report status poll, async end idempotency."""
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


def consume_sse(session_id: int) -> None:
    with requests.get(
        f"{BASE}/api/interview/{session_id}/stream",
        stream=True,
        timeout=120,
        headers={"Accept": "text/event-stream"},
    ) as stream:
        for line in stream.iter_lines(decode_unicode=True):
            if line and line.startswith("data:") and "[DONE]" in line:
                break


def main() -> None:
    requests.get(f"{BASE}/health", timeout=10).raise_for_status()
    ok("health")

    # DELETE job cascade
    with (SAMPLES / "job_description.txt").open("rb") as f:
        job = requests.post(f"{BASE}/api/jobs", files={"file": f}, timeout=60).json()
    job_id = job["id"]
    files = [("files", ("resume_good.txt", (SAMPLES / "resume_good.txt").read_bytes(), "text/plain"))]
    requests.post(f"{BASE}/api/resumes?job_id={job_id}", files=files, timeout=60).raise_for_status()
    r = requests.delete(f"{BASE}/api/jobs/{job_id}", timeout=30)
    if r.status_code not in (200, 204):
        fail(f"DELETE job {r.status_code}")
    r2 = requests.get(f"{BASE}/api/jobs/{job_id}/overview", timeout=10)
    if r2.status_code != 404:
        fail(f"overview after delete expected 404, got {r2.status_code}")
    ok("DELETE job cascades (overview 404)")

    # Report status poll during async generation
    with (SAMPLES / "job_description.txt").open("rb") as f:
        job = requests.post(f"{BASE}/api/jobs", files={"file": f}, timeout=60).json()
    job_id = job["id"]
    files = [("files", ("resume_good.txt", (SAMPLES / "resume_good.txt").read_bytes(), "text/plain"))]
    requests.post(f"{BASE}/api/resumes?job_id={job_id}", files=files, timeout=60).raise_for_status()
    requests.post(
        f"{BASE}/api/screen/{job_id}", json={"async": False}, timeout=300
    ).raise_for_status()
    results = requests.get(f"{BASE}/api/screen/{job_id}/results", timeout=30).json().get(
        "results"
    ) or []
    if not results:
        fail("no screening results after sync screen")
    resume_id = results[0]["resume_id"]
    session_id = requests.post(
        f"{BASE}/api/interview/start",
        json={"job_id": job_id, "resume_id": resume_id, "persona": "hr_friendly"},
        timeout=120,
    ).json()["session_id"]
    consume_sse(session_id)
    requests.post(
        f"{BASE}/api/interview/{session_id}/message",
        json={"content": "我有4年后端经验，熟悉 FastAPI。"},
        timeout=180,
    ).raise_for_status()
    consume_sse(session_id)

    r = requests.post(
        f"{BASE}/api/interview/{session_id}/end",
        json={"async": True},
        timeout=30,
    )
    if r.status_code != 202:
        fail(f"async end expected 202, got {r.status_code}")
    ok("async end 202")

    saw_generating = False
    for _ in range(120):
        st = requests.get(
            f"{BASE}/api/interview/report/{session_id}/status", timeout=30
        ).json()
        if st.get("status") == "generating_report":
            saw_generating = True
        if st.get("status") == "completed":
            break
        time.sleep(1)
    else:
        fail("report status poll timeout")
    if not saw_generating:
        print("[WARN] completed before observing generating_report (very fast LLM)")
    ok("report status poll -> completed")

    r = requests.get(f"{BASE}/api/interview/report/{session_id}", timeout=30)
    if not r.json().get("report"):
        fail("report body empty after poll")
    ok("GET report after async generation")

    # Idempotent POST /end when completed
    r = requests.post(
        f"{BASE}/api/interview/{session_id}/end",
        json={"async": True},
        timeout=30,
    )
    if r.status_code != 200:
        fail(f"completed re-end expected 200, got {r.status_code}")
    if not r.json().get("report"):
        fail("re-end should return full report")
    ok("POST /end idempotent when completed (200 + report)")

    # Active session blocks message after end
    r = requests.post(
        f"{BASE}/api/interview/{session_id}/message",
        json={"content": "extra answer"},
        timeout=30,
    )
    if r.status_code == 200:
        fail("message after end should not succeed")
    ok(f"POST /message blocked after end ({r.status_code})")

    print("\nEdge-case audit passed.")


if __name__ == "__main__":
    main()
