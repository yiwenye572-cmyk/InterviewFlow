"""Post-extraction grounding checks for resume structured data."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from app.config import get_settings
from app.schemas.resume_structured import ResumeStructured, WorkItem

Severity = Literal["ok", "warn", "fail"]

_PLACEHOLDER_PATTERN = re.compile(
    r"^(未知|不详|某公司|某大学|待补充|n/?a|unknown|tbd)$",
    re.IGNORECASE,
)
_ORG_SUFFIXES = (
    "股份有限公司",
    "有限责任公司",
    "有限公司",
    "科技集团",
    "集团公司",
    "集团",
    "科技",
    "信息",
    "网络",
    "大学",
    "学院",
    "学校",
)
_DURATION_RANGE = re.compile(
    r"(20\d{2})[\./年\-]?\d{0,2}\s*[-–—~至到]+\s*(20\d{2}|至今|现在|present|now)",
    re.IGNORECASE,
)
_DURATION_SINGLE = re.compile(r"(20\d{2})[\./年\-]?\d{0,2}")
_INTERN_KEYWORDS = ("实习", "intern", "internship")


@dataclass
class GroundingResult:
    validation_flags: list[str] = field(default_factory=list)
    confidence: float = 1.0
    ambiguities_added: list[str] = field(default_factory=list)
    severity: Severity = "ok"
    structured: ResumeStructured | None = None


def _fullwidth_to_halfwidth(text: str) -> str:
    result: list[str] = []
    for ch in text:
        code = ord(ch)
        if code == 0x3000:
            result.append(" ")
        elif 0xFF01 <= code <= 0xFF5E:
            result.append(chr(code - 0xFEE0))
        else:
            result.append(ch)
    return "".join(result)


def _normalize(text: str) -> str:
    text = _fullwidth_to_halfwidth(text or "").lower()
    text = re.sub(r"[\s\-_·•|/,，。；;：:()（）\[\]【】]+", "", text)
    return text


def _core_org_name(name: str) -> str:
    core = (name or "").strip()
    for suffix in _ORG_SUFFIXES:
        if core.endswith(suffix) and len(core) > len(suffix):
            core = core[: -len(suffix)]
            break
    return core.strip()


def _is_placeholder(value: str) -> bool:
    cleaned = (value or "").strip()
    if not cleaned or len(cleaned) < 2:
        return True
    return bool(_PLACEHOLDER_PATTERN.match(cleaned))


def _fuzzy_contains(haystack: str, needle: str) -> bool:
    if not needle or not haystack:
        return False

    hay_norm = _normalize(haystack)
    needle_norm = _normalize(needle)
    if not needle_norm:
        return False
    if needle_norm in hay_norm:
        return True

    core = _normalize(_core_org_name(needle))
    if len(core) >= 2 and core in hay_norm:
        return True

    if re.search(r"[\u4e00-\u9fff]", needle):
        if len(needle_norm) >= 2:
            return needle_norm in hay_norm
        return False

    tokens = [t for t in re.split(r"[\s,+/]+", needle.lower()) if len(t) >= 2]
    if not tokens:
        return False
    hay_lower = haystack.lower()
    return all(token in hay_lower for token in tokens)


def _parse_implied_years(work_history: list[WorkItem]) -> float | None:
    current_year = datetime.now().year
    spans: list[tuple[int, int]] = []

    for item in work_history:
        duration = item.duration or ""
        for match in _DURATION_RANGE.finditer(duration):
            start_year = int(match.group(1))
            end_raw = match.group(2).lower()
            end_year = current_year if end_raw in ("至今", "现在", "present", "now") else int(end_raw)
            if end_year >= start_year:
                spans.append((start_year, end_year))

    if not spans:
        years: list[int] = []
        for item in work_history:
            for match in _DURATION_SINGLE.finditer(item.duration or ""):
                years.append(int(match.group(1)))
        if len(years) >= 2:
            return float(max(years) - min(years))
        return None

    covered = [False] * (current_year - min(s for s, _ in spans) + 1)
    base = min(s for s, _ in spans)
    for start, end in spans:
        for year in range(start, end + 1):
            idx = year - base
            if 0 <= idx < len(covered):
                covered[idx] = True
    return float(sum(covered))


def _count_severe_flags(flags: list[str], *, name_failed: bool, skills_ratio: float) -> int:
    severe = 0
    if name_failed:
        severe += 1
    if any(f == "validation_years_inflated" for f in flags):
        severe += 1
    if any(f == "validation_years_vs_intern" for f in flags):
        severe += 1
    if skills_ratio < 0.3:
        severe += 1
    return severe


def validate_resume_grounding(raw_text: str, structured: ResumeStructured) -> GroundingResult:
    settings = get_settings()
    flags: list[str] = []
    ambiguities: list[str] = []
    moderate_count = 0
    name_failed = False

    haystack = raw_text or ""

    name = (structured.name or "").strip()
    if not _is_placeholder(name) and len(name) >= 2:
        if not _fuzzy_contains(haystack, name):
            flags.append("validation_name_ungrounded")
            ambiguities.append(f"「姓名 {name}」: 原文中未找到对应表述，可能为模型推断")
            if settings.resume_validation_name_required:
                name_failed = True

    for item in structured.work_history:
        company = (item.company or "").strip()
        if _is_placeholder(company):
            continue
        if not _fuzzy_contains(haystack, company):
            flags.append(f"validation_company_ungrounded:{company}")
            ambiguities.append(f"「公司 {company}」: 原文中未找到对应表述，可能为模型推断")
            moderate_count += 1

    for edu in structured.education:
        school = (edu or "").strip()
        if _is_placeholder(school):
            continue
        school_key = school.split("|")[0].split(" ")[0].strip()
        if not _fuzzy_contains(haystack, school_key) and not _fuzzy_contains(haystack, school):
            flags.append(f"validation_education_ungrounded:{school_key}")
            ambiguities.append(f"「教育 {school}」: 原文中未找到对应表述，可能为模型推断")
            moderate_count += 1

    contact = structured.contact
    if contact:
        email = (contact.email or "").strip()
        phone = (contact.phone or "").strip()
        if email and email not in haystack:
            flags.append("validation_contact_ungrounded:email")
        if phone:
            phone_digits = re.sub(r"\D", "", phone)
            hay_digits = re.sub(r"\D", "", haystack)
            if phone_digits and phone_digits not in hay_digits:
                flags.append("validation_contact_ungrounded:phone")

    skills = [s.strip() for s in structured.skills if s and len(s.strip()) >= 2]
    grounded_skills = 0
    for skill in skills:
        if _fuzzy_contains(haystack, skill):
            grounded_skills += 1
        else:
            flags.append(f"validation_skill_ungrounded:{skill}")
            ambiguities.append(f"「技能 {skill}」: 原文中未找到对应表述，可能为模型推断")

    skills_ratio = 1.0 if not skills else grounded_skills / len(skills)
    if skills and skills_ratio < settings.resume_validation_skill_min_ratio:
        flags.append("validation_skills_low_ratio")
        moderate_count += 1

    implied_years = _parse_implied_years(structured.work_history)
    years = float(structured.years_experience or 0)
    if implied_years is not None and implied_years > 0 and years > implied_years + 1.5:
        flags.append("validation_years_inflated")
        ambiguities.append(
            f"「工作年限 {years} 年」: 与经历时间段估算（约 {implied_years:.1f} 年）不一致"
        )

    if years >= 5 and structured.work_history:
        internish = sum(
            1
            for item in structured.work_history
            if any(k in (item.title or "").lower() or k in (item.description or "").lower()
                   for k in _INTERN_KEYWORDS)
        )
        if internish == len(structured.work_history):
            flags.append("validation_years_vs_intern")
            ambiguities.append("「工作年限」: 经历均为实习/项目表述，与较高年限可能矛盾")

    severe_count = _count_severe_flags(flags, name_failed=name_failed, skills_ratio=skills_ratio)
    confidence = max(0.0, 1.0 - 0.15 * moderate_count - 0.25 * severe_count)

    if name_failed or severe_count >= settings.resume_validation_force_partial_severe:
        severity: Severity = "fail"
    elif flags:
        severity = "warn"
    else:
        severity = "ok"

    updated = structured.model_copy(deep=True)
    if ambiguities:
        merged = list(updated.ambiguities or [])
        for note in ambiguities:
            if note not in merged:
                merged.append(note)
        updated.ambiguities = merged

    return GroundingResult(
        validation_flags=flags,
        confidence=round(confidence, 3),
        ambiguities_added=ambiguities,
        severity=severity,
        structured=updated,
    )
