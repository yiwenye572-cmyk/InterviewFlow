import json
from pathlib import Path

from app.config import get_settings
from app.schemas.resume_structured import (
    FollowupPack,
    JDStructured,
    ResumeStructured,
)
from app.services.llm import structured_completion

PROMPT_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"


def generate_followup_pack(
    job_structured: JDStructured | None,
    resume: ResumeStructured,
    gaps: list[str],
) -> FollowupPack:
    settings = get_settings()
    system = (PROMPT_DIR / "followup_probe.txt").read_text(encoding="utf-8")
    ambiguities = resume.ambiguities or ["No explicit ambiguities recorded."]
    gap_list = gaps[:5] if gaps else ["General fit verification"]
    jd_json = (
        job_structured.model_dump_json(ensure_ascii=False)
        if job_structured
        else "{}"
    )
    messages = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": (
                f"JD Structured:\n{jd_json}\n\n"
                f"Resume ambiguities:\n{json.dumps(ambiguities, ensure_ascii=False)}\n\n"
                f"Identified gaps:\n{json.dumps(gap_list, ensure_ascii=False)}\n\n"
                f"Candidate: {resume.name}, {resume.years_experience} years"
            ),
        },
    ]
    try:
        pack = structured_completion(
            messages, FollowupPack, model=settings.qwen_model_fast, retries=1
        )
        if len(pack.items) < 3:
            pack = _fallback_followups(resume, gaps)
        return pack
    except Exception:
        return _fallback_followups(resume, gaps)


def _fallback_followups(resume: ResumeStructured, gaps: list[str]) -> FollowupPack:
    from app.schemas.resume_structured import FollowupQuestion

    items = []
    for amb in (resume.ambiguities or [])[:3]:
        items.append(
            FollowupQuestion(
                question=f"请详细说明简历中提到的：{amb}",
                target_ambiguity=amb,
                probe_intent="澄清模糊经历",
                difficulty="medium",
            )
        )
    for gap in gaps[:2]:
        items.append(
            FollowupQuestion(
                question=f"针对岗位要求「{gap}」，请分享你的相关经验。",
                target_ambiguity=gap,
                probe_intent="验证能力差距",
                difficulty="medium",
            )
        )
    if not items:
        items.append(
            FollowupQuestion(
                question="请介绍与你目标岗位最相关的一个项目及你的具体贡献。",
                target_ambiguity="general",
                probe_intent="验证项目深度",
                difficulty="easy",
            )
        )
    return FollowupPack(items=items[:5])
