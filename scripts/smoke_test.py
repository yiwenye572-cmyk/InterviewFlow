"""End-to-end smoke test using configured .env (do not print secrets)."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import requests

BASE = "http://127.0.0.1:8000"
SAMPLES = Path(__file__).resolve().parent.parent / "samples"


def ok(label: str) -> None:
    print(f"[PASS] {label}")


def fail(label: str, detail: str) -> None:
    print(f"[FAIL] {label}: {detail}")
    sys.exit(1)


def main() -> None:
    # 1. Health
    try:
        r = requests.get(f"{BASE}/health", timeout=10)
        r.raise_for_status()
        ok("health")
    except Exception as exc:
        fail("health", str(exc))

    # 2. Upload JD
    jd_path = SAMPLES / "job_description.txt"
    with jd_path.open("rb") as f:
        r = requests.post(f"{BASE}/api/jobs", files={"file": f}, timeout=60)
    if r.status_code != 200:
        fail("upload JD", f"{r.status_code} {r.text[:300]}")
    job = r.json()
    job_id = job["id"]
    ok(f"upload JD -> job_id={job_id}")

    # 3. Upload resumes
    files = [
        ("files", ("resume_good.txt", (SAMPLES / "resume_good.txt").read_bytes(), "text/plain")),
        ("files", ("resume_poor.txt", (SAMPLES / "resume_poor.txt").read_bytes(), "text/plain")),
    ]
    r = requests.post(f"{BASE}/api/resumes?job_id={job_id}", files=files, timeout=60)
    if r.status_code != 200:
        fail("upload resumes", f"{r.status_code} {r.text[:300]}")
    ok(f"upload resumes x{r.json()['count']}")

    # 4. Screening (calls Qwen + embedding — may take a while)
    print("[....] running screening (LLM + embedding, please wait)...")
    t0 = time.time()
    r = requests.post(f"{BASE}/api/screen/{job_id}", timeout=300)
    if r.status_code != 200:
        fail("screening", f"{r.status_code} {r.text[:500]}")
    ok(f"screening ({time.time() - t0:.1f}s)")

    # 5. Results
    r = requests.get(f"{BASE}/api/screen/{job_id}/results", timeout=30)
    if r.status_code != 200:
        fail("screening results", f"{r.status_code} {r.text[:300]}")
    results = r.json()["results"]
    if len(results) < 2:
        fail("screening results", "expected 2 candidates")
    results.sort(key=lambda x: x["final_score"], reverse=True)
    good, poor = results[0], results[1]
    print(f"       top: {good['candidate_name']} score={good['final_score']} recommend={good['recommend_interview']}")
    print(f"       low: {poor['candidate_name']} score={poor['final_score']} recommend={poor['recommend_interview']}")
    ok("screening results ranked")

    if not good.get("can_interview"):
        print("[WARN] top candidate not eligible for interview — continuing anyway with top resume_id")

    resume_id = good["resume_id"]

    # 6. Start interview
    print("[....] starting interview session...")
    r = requests.post(
        f"{BASE}/api/interview/start",
        json={"job_id": job_id, "resume_id": resume_id, "persona": "tech_lead"},
        timeout=60,
    )
    if r.status_code != 200:
        fail("interview start", f"{r.status_code} {r.text[:500]}")
    session_id = r.json()["session_id"]
    ok(f"interview start -> session_id={session_id}")

    # 7. SSE opening stream
    print("[....] streaming opening message...")
    chunks: list[str] = []
    with requests.get(
        f"{BASE}/api/interview/{session_id}/stream",
        stream=True,
        timeout=120,
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
            if isinstance(data, str) and data != "[DONE]":
                chunks.append(data)
    opening = "".join(chunks)
    if len(opening) < 10:
        fail("SSE opening", f"too short: {opening!r}")
    ok(f"SSE opening ({len(opening)} chars)")

    # 8. One interview round
    answer = (
        "您好，我是张三，有4年后端经验，主要使用 FastAPI 和 LangGraph 做过 AI 招聘助手项目，"
        "负责简历解析、混合匹配打分和多轮面试 Agent 编排。"
    )
    r = requests.post(
        f"{BASE}/api/interview/{session_id}/message",
        json={"content": answer},
        timeout=120,
    )
    if r.status_code != 200:
        fail("interview message", f"{r.status_code} {r.text[:500]}")
    ok(f"interview answer round={r.json()['round_count']}")

    chunks = []
    with requests.get(
        f"{BASE}/api/interview/{session_id}/stream",
        stream=True,
        timeout=180,
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
            if isinstance(data, str) and data != "[DONE]":
                chunks.append(data)
    followup = "".join(chunks)
    if len(followup) < 5:
        fail("SSE follow-up", f"too short: {followup!r}")
    ok(f"SSE follow-up ({len(followup)} chars)")

    # 9. End & report
    print("[....] generating report...")
    t0 = time.time()
    r = requests.post(f"{BASE}/api/interview/{session_id}/end", json={"async": False}, timeout=300)
    if r.status_code != 200:
        fail("end interview", f"{r.status_code} {r.text[:500]}")
    report = r.json().get("report")
    if not report or "job_fit_score" not in report:
        fail("report", f"invalid: {r.text[:300]}")
    ok(
        f"report ({time.time() - t0:.1f}s) "
        f"fit={report['job_fit_score']} comm={report['communication_score']} "
        f"rec={report['overall_recommendation']}"
    )

    print("\n=== All tests passed ===")


if __name__ == "__main__":
    main()
