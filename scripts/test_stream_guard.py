"""Unit tests for interview stream output guard (no live LLM by default)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.services.interview.stream_guard import (
    ensure_stream_output,
    template_fallback,
    validate_stream_output,
)

GOOD_OPENING = (
    "张三你好，我是本场技术面试官。"
    "接下来我会围绕岗位与项目经验提问，请先做一个简短的自我介绍？"
)


class StreamGuardValidateTests(unittest.TestCase):
    def test_good_opening_passes(self):
        result = validate_stream_output(
            GOOD_OPENING,
            kind="opening",
            persona="tech_lead",
        )
        self.assertTrue(result.passed)
        self.assertEqual(result.guard_flags, [])

    def test_ai_leak_fails(self):
        result = validate_stream_output(
            "作为语言模型我无法回答这个问题，请问还有什么？",
            kind="followup",
            persona="tech_lead",
        )
        self.assertFalse(result.passed)
        self.assertIn("stream_guard_ai_leak", result.guard_flags)

    def test_tech_lead_persona_drift_flag(self):
        result = validate_stream_output(
            "亲爱的候选人～请先介绍一下自己好吗？",
            kind="opening",
            persona="tech_lead",
        )
        self.assertIn("stream_guard_persona_drift", result.guard_flags)
        self.assertTrue(result.passed)

    def test_too_short_fails(self):
        result = validate_stream_output(
            "你好，欢迎来参加",
            kind="opening",
            persona="tech_lead",
        )
        self.assertFalse(result.passed)
        self.assertTrue(
            "stream_guard_too_short" in result.guard_flags
            or "stream_guard_empty" in result.guard_flags
        )


class StreamGuardEnsureTests(unittest.TestCase):
    def test_template_fallback_when_rewrite_disabled(self):
        state = {"structured": {"name": "李四"}, "persona": "tech_lead"}
        with patch("app.services.interview.stream_guard.get_settings") as mock_settings:
            mock_settings.return_value.stream_guard_llm_rewrite = False
            mock_settings.return_value.stream_guard_min_chars = 10
            mock_settings.return_value.stream_guard_max_chars = 2000
            result = ensure_stream_output(
                "你好",
                kind="opening",
                persona="tech_lead",
                state=state,
            )
        self.assertTrue(result.used_template)
        self.assertIn("自我介绍", result.text)

    def test_rewrite_success(self):
        state = {"structured": {"name": "王五"}, "persona": "tech_lead"}
        fixed = (
            "王五你好，我是技术面试官。"
            "请先结合项目经历做一个自我介绍？"
        )

        def mock_rewrite(text, *, kind, persona, flags):
            return fixed

        with patch("app.services.interview.stream_guard.get_settings") as mock_settings:
            mock_settings.return_value.stream_guard_llm_rewrite = True
            mock_settings.return_value.stream_guard_min_chars = 10
            mock_settings.return_value.stream_guard_max_chars = 2000
            result = ensure_stream_output(
                "你好",
                kind="opening",
                persona="tech_lead",
                state=state,
                rewrite_fn=mock_rewrite,
            )
        self.assertTrue(result.used_rewrite)
        self.assertTrue(result.passed)
        self.assertEqual(result.text, fixed)


class StreamGuardTemplateTests(unittest.TestCase):
    def test_opening_hr_template(self):
        text = template_fallback(
            "opening",
            "hr_friendly",
            {"structured": {"name": "赵六"}},
        )
        self.assertIn("赵六", text)
        self.assertIn("介绍", text)


if __name__ == "__main__":
    unittest.main()
