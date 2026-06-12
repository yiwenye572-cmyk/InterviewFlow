"""Unit tests for resume grounding validator (no LLM)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.schemas.resume_structured import ContactInfo, ResumeStructured, WorkItem
from app.services.resume_validator import validate_resume_grounding

SAMPLES = ROOT / "samples"


def _good_structured() -> ResumeStructured:
    return ResumeStructured(
        name="张三",
        years_experience=4.0,
        skills=[
            "Python",
            "FastAPI",
            "SQLAlchemy",
            "LangChain",
            "LangGraph",
            "Redis",
            "PostgreSQL",
            "Docker",
            "Git",
        ],
        education=["浙江大学 | 计算机科学与技术 | 本科 | 2015-2019"],
        work_history=[
            WorkItem(
                company="阿里巴巴集团",
                title="高级后端工程师",
                duration="2021.06 - 至今",
                description="FastAPI AI 招聘助手",
            ),
            WorkItem(
                company="字节跳动",
                title="Python 开发工程师",
                duration="2019.07 - 2021.05",
                description="推荐系统后端",
            ),
        ],
        highlights=["主导 AI 招聘 MVP"],
        summary="4年后端经验",
        contact=ContactInfo(phone="13800000000", email="zhangsan@example.com"),
    )


class ResumeValidatorTests(unittest.TestCase):
    def setUp(self):
        sample_path = SAMPLES / "resume_good.txt"
        if not sample_path.exists():
            self.skipTest("samples/resume_good.txt missing")
        self.good_text = sample_path.read_text(encoding="utf-8")

    def test_good_resume_ok(self):
        result = validate_resume_grounding(self.good_text, _good_structured())
        self.assertEqual(result.severity, "ok")
        self.assertGreaterEqual(result.confidence, 0.8)
        self.assertEqual(result.validation_flags, [])

    def test_fabricated_company(self):
        structured = _good_structured()
        structured.work_history = list(structured.work_history) + [
            WorkItem(company="腾讯科技", title="工程师", duration="2020-2021", description="")
        ]
        result = validate_resume_grounding(self.good_text, structured)
        self.assertTrue(
            any(f.startswith("validation_company_ungrounded:") for f in result.validation_flags)
        )

    def test_fabricated_skill(self):
        structured = _good_structured()
        structured.skills = list(structured.skills) + ["Kubernetes"]
        result = validate_resume_grounding(self.good_text, structured)
        self.assertTrue(
            any(f.startswith("validation_skill_ungrounded:") for f in result.validation_flags)
        )
        self.assertTrue(any("Kubernetes" in a for a in result.ambiguities_added))

    def test_inflated_years(self):
        structured = _good_structured()
        structured.years_experience = 8.0
        structured.work_history = [
            WorkItem(
                company="阿里巴巴集团",
                title="工程师",
                duration="2023.01 - 2024.12",
                description="",
            )
        ]
        result = validate_resume_grounding(self.good_text, structured)
        self.assertIn("validation_years_inflated", result.validation_flags)

    def test_unknown_name_skips_severe(self):
        structured = _good_structured()
        structured.name = "Unknown"
        result = validate_resume_grounding(self.good_text, structured)
        self.assertNotIn("validation_name_ungrounded", result.validation_flags)

    def test_zhejiang_university_core_match(self):
        structured = _good_structured()
        structured.education = ["浙江大学 计算机 本科"]
        result = validate_resume_grounding(self.good_text, structured)
        self.assertFalse(
            any(f.startswith("validation_education_ungrounded:") for f in result.validation_flags)
        )


if __name__ == "__main__":
    unittest.main()
