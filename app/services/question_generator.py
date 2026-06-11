import json
from pathlib import Path

from app.config import get_settings
from app.schemas.resume_structured import JDStructured, QuestionPack, ResumeStructured
from app.services.llm import structured_completion

PROMPT_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"


def generate_question_pack(
    job_text: str,
    job_structured: JDStructured | None,
    resume: ResumeStructured,
) -> QuestionPack:
    settings = get_settings()
    system = (PROMPT_DIR / "question_generate.txt").read_text(encoding="utf-8")
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
                f"Job Description:\n{job_text[:8000]}\n\n"
                f"Structured JD:\n{jd_json}\n\n"
                f"Structured Resume:\n{resume.model_dump_json(ensure_ascii=False)}"
            ),
        },
    ]
    pack = structured_completion(
        messages, QuestionPack, model=settings.qwen_model, retries=2
    )
    if len(pack.items) < 10:
        pack = _pad_questions(pack, job_structured, resume)
    return pack


def _pad_questions(
    pack: QuestionPack,
    job_structured: JDStructured | None,
    resume: ResumeStructured,
) -> QuestionPack:
    from app.schemas.resume_structured import InterviewQuestion

    items = list(pack.items)
    skills = (job_structured.required_skills if job_structured else []) or resume.skills[:5]
    idx = 0
    while len(items) < 10 and idx < len(skills):
        skill = skills[idx]
        items.append(
            InterviewQuestion(
                question=f"请介绍你在 {skill} 方面的实践经验，并举例说明。",
                competency=skill,
                difficulty="medium",
                rubric="优秀：有具体项目与量化结果；一般：有使用经验但细节不足；不足：无法给出实例",
                category="technical",
            )
        )
        idx += 1
    while len(items) < 10:
        items.append(
            InterviewQuestion(
                question="请描述一次你在压力下解决复杂问题的经历。",
                competency="problem solving",
                difficulty="medium",
                rubric="优秀：STAR 结构清晰；一般：有案例但缺结果；不足：泛泛而谈",
                category="behavioral",
            )
        )
    return QuestionPack(items=items[:12])
