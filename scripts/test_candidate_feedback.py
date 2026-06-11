"""P1: candidate interview experience feedback + flywheel."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import requests

BASE = "http://127.0.0.1:8000"
SAMPLES = Path(__file__).resolve().parent.parent / "samples"
ROOT = Path(__file__).resolve().parent.parent


def ok(msg: str) -> None:
    print(f"[PASS] {msg}")


def fail(msg: str) -> None:
    print(f"[FAIL] {msg}")
    sys.exit(1)


def consume_sse(session_id: int, timeout: int = 180) -> str:
    chunks: list[str] = []
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
            if isinstance(data, str) and data not in ("[DONE]",):
                chunks.append(data)
    return "".join(chunks)


def run_round(session_id: int, answer: str) -> None:
    r = requests.post(
        f"{BASE}/api/interview/{session_id}/message",
        json={"content": answer},
        timeout=180,
    )
    if r.status_code != 200:
        fail(f"message {r.status_code}: {r.text[:500]}")
    consume_sse(session_id)


def main() -> None:
    try:
        requests.get(f"{BASE}/health", timeout=10).raise_for_status()
        ok("health")
    except Exception as exc:
        fail(f"server not running: {exc}")

    with (SAMPLES / "job_description.txt").open("rb") as f:
        job = requests.post(f"{BASE}/api/jobs", files={"file": f}, timeout=60).json()
    job_id = job["id"]

    files = [("files", ("resume_good.txt", (SAMPLES / "resume_good.txt").read_bytes(), "text/plain"))]
    requests.post(f"{BASE}/api/resumes?job_id={job_id}", files=files, timeout=60).raise_for_status()
    requests.post(f"{BASE}/api/screen/{job_id}", timeout=300).raise_for_status()
    resume_id = requests.get(f"{BASE}/api/screen/{job_id}/results", timeout=30).json()["results"][0][
        "resume_id"
    ]

    r = requests.post(
        f"{BASE}/api/interview/start",
        json={"job_id": job_id, "resume_id": resume_id, "persona": "hr_friendly"},
        timeout=120,
    )
    session_id = r.json()["session_id"]
    consume_sse(session_id)
    run_round(session_id, "我有4年后端经验，熟悉 FastAPI，参与过招聘系统项目。")

    print("[....] end interview...")
    r = requests.post(f"{BASE}/api/interview/{session_id}/end", timeout=300)
    if r.status_code != 200:
        fail(f"end {r.status_code}")

    print("[....] submit candidate feedback...")
    r = requests.post(
        f"{BASE}/api/interview/{session_id}/feedback",
        json={"rating": 4, "comment": "HR 语气很好，希望追问再具体一点"},
        timeout=30,
    )
    if r.status_code != 200:
        fail(f"feedback {r.status_code}: {r.text[:300]}")
    ok("POST /feedback rating=4")

    r = requests.post(
        f"{BASE}/api/interview/{session_id}/feedback",
        json={"rating": 5, "comment": "duplicate"},
        timeout=30,
    )
    if r.status_code != 409:
        fail(f"duplicate feedback should 409, got {r.status_code}")
    ok("duplicate feedback → 409")

    r = requests.get(f"{BASE}/api/interview/report/{session_id}", timeout=10)
    fb = r.json().get("candidate_feedback")
    if not fb or fb.get("rating") != 4:
        fail(f"report missing candidate_feedback: {r.json()}")
    ok(f"GET /report candidate_feedback rating={fb['rating']}")

    print("[....] flywheel on next start...")
    r = requests.post(
        f"{BASE}/api/interview/start",
        json={"job_id": job_id, "resume_id": resume_id, "persona": "hr_friendly"},
        timeout=120,
    )
    new_session_id = r.json()["session_id"]

    sys.path.insert(0, str(ROOT))
    from app.database import SessionLocal
    from app.models.entities import InterviewSession

    db = SessionLocal()
    try:
        new_session = db.get(InterviewSession, new_session_id)
        prompt = new_session.persona_prompt or ""
        if "Prior candidate experience (flywheel)" not in prompt:
            fail(f"flywheel not in persona_prompt: {prompt[-400:]}")
        ok("flywheel injected into persona_prompt")
    finally:
        db.close()

    print("\n=== P1 candidate feedback tests passed ===")


if __name__ == "__main__":
    main()
