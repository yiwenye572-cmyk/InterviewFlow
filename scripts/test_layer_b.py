"""B-layer focused API smoke test (LangGraph interview + score calibration)."""
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


def run_interview_round(session_id: int, answer: str) -> dict:
    r = requests.post(
        f"{BASE}/api/interview/{session_id}/message",
        json={"content": answer},
        timeout=180,
    )
    if r.status_code != 200:
        fail(f"message {r.status_code}: {r.text[:500]}")
    body = r.json()
    consume_sse(session_id)
    return body


def main() -> None:
    try:
        requests.get(f"{BASE}/health", timeout=10).raise_for_status()
        ok("health")
    except Exception as exc:
        fail(f"health / server not running: {exc}")

    templates = requests.get(f"{BASE}/api/jobs/templates", timeout=10).json()
    if not templates.get("templates"):
        print("[WARN] no job templates loaded")
    else:
        ok(f"job templates count={len(templates['templates'])}")

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

    print("[....] start interview...")
    r = requests.post(
        f"{BASE}/api/interview/start",
        json={"job_id": job_id, "resume_id": resume_id, "persona": "tech_lead"},
        timeout=120,
    )
    if r.status_code != 200:
        fail(f"start {r.status_code}: {r.text[:500]}")
    session_id = r.json()["session_id"]
    ok(f"session_id={session_id}")

    opening = consume_sse(session_id)
    if len(opening) < 20:
        fail(f"opening too short: {opening!r}")
    ok(f"opening ({len(opening)} chars)")

    body = run_interview_round(
        session_id,
        "您好，我有4年后端经验，熟悉 FastAPI、LangGraph，参与过 AI 招聘助手项目。",
    )
    if body.get("pending_action") not in ("stream_followup", "stream_question", "stream_closing"):
        fail(f"unexpected pending: {body.get('pending_action')}")
    ok(f"round1 pending={body['pending_action']}")

    live = body.get("live_assessment") or requests.get(
        f"{BASE}/api/interview/{session_id}/live", timeout=10
    ).json()
    ok(f"live fit={live.get('provisional_job_fit')} comm={live.get('provisional_communication')}")

    print("[....] vague answers (score calibration)...")
    body = run_interview_round(session_id, "还行吧，一般。")
    comm1 = (body.get("live_assessment") or {}).get("provisional_communication", 100)
    if comm1 > 45:
        fail(f"vague answer comm too high: {comm1}")
    ok(f"vague answer comm={comm1} (<=45)")

    body = run_interview_round(session_id, "差不多就这样。")
    if body.get("pending_action") != "stream_question":
        fail(f"after 2 followups should force stream_question, got {body.get('pending_action')}")
    ok(f"2nd vague forced new topic pending=stream_question")

    body = run_interview_round(session_id, "嗯，还可以。")
    ok(f"3rd answer on new topic pending={body.get('pending_action')}")

    status = requests.get(f"{BASE}/api/interview/{session_id}/status", timeout=10).json()
    if status.get("round_count", 0) >= 3 and status.get("phase") == "opening":
        print("[WARN] phase still opening after 3 rounds")
    else:
        ok(f"phase={status.get('phase')} streak={status.get('followup_streak')}")

    if status.get("competency_status"):
        ok(f"competency_status keys={len(status['competency_status'])}")

    print("[....] hr_friendly persona smoke...")
    r = requests.post(
        f"{BASE}/api/interview/start",
        json={"job_id": job_id, "resume_id": resume_id, "persona": "hr_friendly"},
        timeout=120,
    )
    hr_session = r.json()["session_id"]
    hr_opening = consume_sse(hr_session)
    if len(hr_opening) < 15:
        fail("hr opening too short")
    ok(f"hr_friendly opening ({len(hr_opening)} chars)")

    hr_status = requests.get(f"{BASE}/api/interview/{hr_session}/status", timeout=10).json()
    if not hr_status.get("interview_config", {}).get("enable_encouragement"):
        fail("hr_friendly default enable_encouragement should be True")
    ok("hr_friendly default enable_encouragement=True")

    print("[....] tech_lead encouragement default...")
    r = requests.post(
        f"{BASE}/api/interview/start",
        json={"job_id": job_id, "resume_id": resume_id, "persona": "tech_lead"},
        timeout=120,
    )
    tech_session = r.json()["session_id"]
    consume_sse(tech_session)
    tech_status = requests.get(f"{BASE}/api/interview/{tech_session}/status", timeout=10).json()
    if tech_status.get("interview_config", {}).get("enable_encouragement"):
        fail("tech_lead default enable_encouragement should be False")
    ok("tech_lead default enable_encouragement=False")

    print("[....] encouragement on hesitant/stuck answer (hr)...")
    body = run_interview_round(hr_session, "嗯…")
    if body.get("pending_action") != "stream_encouragement":
        fail(f"hr short answer should trigger stream_encouragement, got {body.get('pending_action')}")
    comm_after_enc = (body.get("live_assessment") or {}).get("provisional_communication", 100)
    ok(f"hr stuck answer → stream_encouragement comm={comm_after_enc}")

    print("[....] tech_lead skips encouragement...")
    body = run_interview_round(tech_session, "嗯…")
    if body.get("pending_action") == "stream_encouragement":
        fail("tech_lead should not stream_encouragement when disabled")
    ok(f"tech short answer pending={body.get('pending_action')} (not encouragement)")

    print("[....] followup_type in evaluations_log...")
    r = requests.post(
        f"{BASE}/api/interview/start",
        json={"job_id": job_id, "resume_id": resume_id, "persona": "tech_lead"},
        timeout=120,
    )
    eval_session = r.json()["session_id"]
    consume_sse(eval_session)
    run_interview_round(
        eval_session,
        "我有4年后端经验，主导过 FastAPI 微服务拆分，接口 P99 从 800ms 降到 120ms。",
    )
    r = requests.post(f"{BASE}/api/interview/{eval_session}/end", json={"async": False}, timeout=300)
    evals = r.json().get("evaluations_log") or []
    if not evals:
        fail("evaluations_log empty after round")
    if not evals[0].get("followup_type"):
        fail("followup_type missing from evaluation")
    if not evals[0].get("candidate_state"):
        fail("candidate_state missing from evaluation")
    ok(f"followup_type={evals[0]['followup_type']} candidate_state={evals[0]['candidate_state']}")

    print("[....] standardized mode fixed question order...")
    r = requests.post(
        f"{BASE}/api/interview/start",
        json={
            "job_id": job_id,
            "resume_id": resume_id,
            "persona": "tech_lead",
            "config": {
                "interview_mode": "standardized",
                "persona": "tech_lead",
                "max_followup_streak": 0,
                "enable_encouragement": False,
                "standardized_question_limit": 3,
            },
        },
        timeout=120,
    )
    if r.status_code != 200:
        fail(f"standardized start {r.status_code}: {r.text[:500]}")
    std_session = r.json()["session_id"]
    if r.json().get("interview_mode") != "standardized":
        fail(f"start response interview_mode={r.json().get('interview_mode')}")
    consume_sse(std_session)
    std_status = requests.get(f"{BASE}/api/interview/{std_session}/status", timeout=10).json()
    if std_status.get("question_index", -1) != 0:
        fail(f"question_index should start at 0, got {std_status.get('question_index')}")
    ok("standardized session started question_index=0")

    answers = [
        "第一题：我用 FastAPI 做过 REST API，配合 Pydantic 做校验，部署在 K8s 上。",
        "第二题：数据库用过 PostgreSQL 与 Redis，做过读写分离与缓存穿透治理。",
        "第三题：团队协作采用 Git Flow，Code Review 与 CI 流水线保证质量。",
    ]
    last_idx = 0
    for ans in answers:
        run_interview_round(std_session, ans)
        st = requests.get(f"{BASE}/api/interview/{std_session}/status", timeout=10).json()
        idx = st.get("question_index", 0)
        if idx <= last_idx:
            fail(f"question_index should increase, was {last_idx} now {idx}")
        last_idx = idx
        ok(f"standardized round question_index={idx}")
    if last_idx < 1:
        fail("standardized mode did not advance question_index")
    ok(f"standardized mode advanced to question_index={last_idx}")

    print("[....] end + report...")
    t0 = time.time()
    r = requests.post(f"{BASE}/api/interview/{session_id}/end", json={"async": False}, timeout=300)
    if r.status_code != 200:
        fail(f"end {r.status_code}: {r.text[:500]}")
    data = r.json()
    report = data.get("report")
    if not report or "job_fit_score" not in report:
        fail(f"invalid report: {r.text[:300]}")
    if not report.get("dimension_scores"):
        print("[WARN] dimension_scores empty in report")
    if not report.get("hiring_decision_rationale"):
        print("[WARN] hiring_decision_rationale empty")
    ok(
        f"report fit={report['job_fit_score']} dims={list(report.get('dimension_scores', {}).keys())} "
        f"evals={len(data.get('evaluations_log') or [])} ({time.time() - t0:.1f}s)"
    )

    print("\n=== B-layer polish tests passed ===")


if __name__ == "__main__":
    main()
