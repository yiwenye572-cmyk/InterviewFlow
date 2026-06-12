"""P3: async report generation + status polling."""
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


def consume_sse(session_id: int, timeout: int = 180) -> None:
    with requests.get(
        f"{BASE}/api/interview/{session_id}/stream",
        stream=True,
        timeout=timeout,
        headers={"Accept": "text/event-stream"},
    ) as stream:
        for line in stream.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data:"):
                continue
            data = line[5:].strip()
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                pass
            if data == "[DONE]":
                break


def poll_report_status(session_id: int, timeout_sec: int = 300) -> dict:
    deadline = time.time() + timeout_sec
    last: dict = {}
    while time.time() < deadline:
        r = requests.get(
            f"{BASE}/api/interview/report/{session_id}/status", timeout=30
        )
        if r.status_code != 200:
            fail(f"status {r.status_code}: {r.text[:300]}")
        last = r.json()
        status = last.get("status")
        if status == "completed":
            return last
        if status == "failed":
            fail(f"report failed: {last.get('error')}")
        time.sleep(1)
    fail(f"poll timeout, last={last}")


def main() -> None:
    try:
        requests.get(f"{BASE}/health", timeout=10).raise_for_status()
        ok("health")
    except Exception as exc:
        fail(f"server not running: {exc}")

    with (SAMPLES / "job_description.txt").open("rb") as f:
        job = requests.post(f"{BASE}/api/jobs", files={"file": f}, timeout=60).json()
    job_id = job["id"]

    files = [
        ("files", ("resume_good.txt", (SAMPLES / "resume_good.txt").read_bytes(), "text/plain"))
    ]
    requests.post(f"{BASE}/api/resumes?job_id={job_id}", files=files, timeout=60).raise_for_status()
    requests.post(
        f"{BASE}/api/screen/{job_id}", json={"async": False}, timeout=300
    ).raise_for_status()
    resume_id = requests.get(f"{BASE}/api/screen/{job_id}/results", timeout=30).json()[
        "results"
    ][0]["resume_id"]

    r = requests.post(
        f"{BASE}/api/interview/start",
        json={"job_id": job_id, "resume_id": resume_id, "persona": "hr_friendly"},
        timeout=120,
    )
    session_id = r.json()["session_id"]
    consume_sse(session_id)
    requests.post(
        f"{BASE}/api/interview/{session_id}/message",
        json={"content": "我有4年后端经验，熟悉 FastAPI，参与过招聘系统项目。"},
        timeout=180,
    ).raise_for_status()
    consume_sse(session_id)

    print("[....] async end...")
    t0 = time.time()
    r = requests.post(
        f"{BASE}/api/interview/{session_id}/end",
        json={"async": True},
        timeout=30,
    )
    if r.status_code != 202:
        fail(f"async end expected 202, got {r.status_code}: {r.text[:300]}")
    body = r.json()
    if body.get("status") != "generating_report":
        fail(f"expected generating_report, got {body}")
    ok(f"async end 202 in {time.time() - t0:.1f}s")

    print("[....] poll status...")
    status = poll_report_status(session_id)
    if status.get("progress") != 100:
        fail(f"expected progress 100, got {status}")
    ok("poll completed")

    r = requests.get(f"{BASE}/api/interview/report/{session_id}", timeout=30)
    if r.status_code != 200:
        fail(f"report {r.status_code}")
    report = r.json().get("report")
    if not report or "job_fit_score" not in report:
        fail(f"invalid report: {r.text[:300]}")
    ok("report loaded with job_fit_score")

    print("\nAll async report checks passed.")


if __name__ == "__main__":
    main()
