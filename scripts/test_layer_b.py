"""B-layer focused API smoke test (LangGraph interview agent)."""
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
    ]
    requests.post(f"{BASE}/api/resumes?job_id={job_id}", files=files, timeout=60).raise_for_status()
    ok("upload resume")

    print("[....] screening...")
    t0 = time.time()
    r = requests.post(f"{BASE}/api/screen/{job_id}", timeout=300)
    if r.status_code != 200:
        fail(f"screen {r.status_code}: {r.text[:500]}")
    ok(f"screen ({time.time() - t0:.1f}s)")

    results = requests.get(f"{BASE}/api/screen/{job_id}/results", timeout=30).json()["results"]
    resume_id = results[0]["resume_id"]
    ok(f"resume_id={resume_id}")

    print("[....] start interview (PersonaProfile + init graph)...")
    t0 = time.time()
    r = requests.post(
        f"{BASE}/api/interview/start",
        json={"job_id": job_id, "resume_id": resume_id, "persona": "tech_lead"},
        timeout=120,
    )
    if r.status_code != 200:
        fail(f"start {r.status_code}: {r.text[:500]}")
    session_id = r.json()["session_id"]
    ok(f"start session_id={session_id} ({time.time() - t0:.1f}s)")

    status = requests.get(f"{BASE}/api/interview/{session_id}/status", timeout=10).json()
    if status.get("phase") != "opening":
        fail(f"expected phase=opening, got {status}")
    if status.get("pending_action") != "stream_opening":
        fail(f"expected pending=stream_opening, got {status.get('pending_action')}")
    ok(f"status phase={status['phase']} pending={status['pending_action']}")

    print("[....] LLM opening stream...")
    t0 = time.time()
    opening = consume_sse(session_id)
    if len(opening) < 20:
        fail(f"opening too short: {opening!r}")
    ok(f"opening stream ({len(opening)} chars, {time.time() - t0:.1f}s)")

    msgs = requests.get(f"{BASE}/api/interview/{session_id}/messages", timeout=10).json()
    if len(msgs.get("messages", [])) < 1:
        fail("messages restore empty after opening")
    ok(f"messages restore count={len(msgs['messages'])}")

    status = requests.get(f"{BASE}/api/interview/{session_id}/status", timeout=10).json()
    if status.get("pending_action") != "wait_answer":
        fail(f"expected wait_answer after opening, got {status.get('pending_action')}")
    ok("pending=wait_answer after opening")

    answer = (
        "您好，我有4年后端经验，熟悉 FastAPI、LangGraph，"
        "参与过 AI 招聘助手项目，负责简历解析与多轮面试 Agent。"
    )
    print("[....] submit answer + evaluate graph...")
    t0 = time.time()
    r = requests.post(
        f"{BASE}/api/interview/{session_id}/message",
        json={"content": answer},
        timeout=180,
    )
    if r.status_code != 200:
        fail(f"message {r.status_code}: {r.text[:500]}")
    body = r.json()
    if body.get("round_count", 0) < 1:
        fail(f"round_count missing: {body}")
    if not body.get("phase"):
        fail(f"phase missing in message response: {body}")
    if body.get("pending_action") not in (
        "stream_followup", "stream_question", "stream_closing"
    ):
        fail(f"unexpected pending_action: {body.get('pending_action')}")
    ok(
        f"message round={body['round_count']} phase={body['phase']} "
        f"pending={body['pending_action']} ({time.time() - t0:.1f}s)"
    )

    live = body.get("live_assessment")
    if not live or "provisional_job_fit" not in live:
        r2 = requests.get(f"{BASE}/api/interview/{session_id}/live", timeout=10)
        if r2.status_code != 200:
            fail(f"live assessment missing: {r2.status_code} {r2.text[:200]}")
        live = r2.json()
    ok(
        f"live assessment fit={live.get('provisional_job_fit')} "
        f"comm={live.get('provisional_communication')}"
    )

    print("[....] stream next question...")
    t0 = time.time()
    next_q = consume_sse(session_id)
    if len(next_q) < 5:
        fail(f"next question too short: {next_q!r}")
    ok(f"next question ({len(next_q)} chars, {time.time() - t0:.1f}s)")

    print("[....] vague answer -> expect followup route...")
    t0 = time.time()
    r = requests.post(
        f"{BASE}/api/interview/{session_id}/message",
        json={"content": "还行吧，一般。"},
        timeout=180,
    )
    if r.status_code != 200:
        fail(f"vague message {r.status_code}: {r.text[:500]}")
    body = r.json()
    ok(f"vague answer round={body['round_count']} pending={body['pending_action']}")

    followup = consume_sse(session_id)
    if len(followup) < 5:
        fail(f"followup stream too short: {followup!r}")
    ok(f"followup/question stream ({len(followup)} chars, {time.time() - t0:.1f}s)")

    status = requests.get(f"{BASE}/api/interview/{session_id}/status", timeout=10).json()
    ok(
        f"final status phase={status.get('phase')} "
        f"competencies={len(status.get('competencies_covered', []))}/"
        f"{len(status.get('competencies_planned', []))}"
    )

    print("[....] end interview + report...")
    t0 = time.time()
    r = requests.post(f"{BASE}/api/interview/{session_id}/end", timeout=300)
    if r.status_code != 200:
        fail(f"end {r.status_code}: {r.text[:500]}")
    data = r.json()
    report = data.get("report")
    if not report or "job_fit_score" not in report:
        fail(f"invalid report: {r.text[:300]}")
    eval_log = data.get("evaluations_log") or []
    ok(
        f"report fit={report['job_fit_score']} comm={report['communication_score']} "
        f"rec={report['overall_recommendation']} evals={len(eval_log)} "
        f"({time.time() - t0:.1f}s)"
    )

    print("\n=== B-layer tests passed ===")


if __name__ == "__main__":
    main()
