"""Heuristics for resume text when LLM extraction fails or needs hints."""

from __future__ import annotations

import re

from app.schemas.resume_structured import ContactInfo, ResumeStructured


def guess_name_from_text(raw_text: str) -> str:
    text = (raw_text or "").strip()
    if not text:
        return "Unknown"

    patterns = [
        r"^#+\s*([\u4e00-\u9fa5A-Za-z·]{2,8})\s*简历",
        r"^([\u4e00-\u9fa5A-Za-z·]{2,8})\s*简历",
        r"^姓名[：:]\s*([\u4e00-\u9fa5A-Za-z·]{2,8})",
        r"^Name[：:]\s*([A-Za-z·\s]{2,40})",
    ]
    for line in text.splitlines()[:8]:
        line = line.strip()
        if not line:
            continue
        for pat in patterns:
            m = re.search(pat, line, re.IGNORECASE)
            if m:
                return m.group(1).strip()
        if 2 <= len(line) <= 8 and re.fullmatch(r"[\u4e00-\u9fa5A-Za-z·]+", line):
            return line
    return "Unknown"


def guess_contact_from_text(raw_text: str) -> ContactInfo:
    phone = ""
    email = ""
    phone_m = re.search(r"(?:电话|手机|Tel|Phone)[：:\s]*([+\d\-]{7,20})", raw_text, re.I)
    if phone_m:
        phone = phone_m.group(1).strip()
    email_m = re.search(r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", raw_text)
    if email_m:
        email = email_m.group(1).strip()
    return ContactInfo(phone=phone, email=email)


def build_partial_structured(raw_text: str) -> ResumeStructured:
    name = guess_name_from_text(raw_text)
    contact = guess_contact_from_text(raw_text)
    preview = raw_text[:500].replace("\n", " ")
    return ResumeStructured(
        name=name,
        years_experience=0.0,
        skills=[],
        education=[],
        work_history=[],
        highlights=[],
        ambiguities=["结构化抽取未完整完成，已使用文本摘要降级。"],
        summary=preview[:300],
        contact=contact,
    )


def parse_failure_summary(
    *,
    parse_quality: str,
    text_len: int,
    exc: Exception | None = None,
) -> str:
    if parse_quality == "scanned":
        return "简历为扫描件或无可提取文本，请上传可搜索的 PDF/DOCX 或 TXT。"
    if parse_quality == "low" and text_len < 100:
        return f"简历文本过短（{text_len} 字，需至少 100 字），请补充内容后重新上传。"
    if exc:
        msg = str(exc).replace("\n", " ")[:160]
        return f"结构化抽取失败（{msg}）。TXT/PDF/DOCX 均支持，请检查 DashScope Key 后重试筛选。"
    return "结构化抽取未完成，已使用文本相似度降级评估。"
