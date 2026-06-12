"""Unit tests for LLM harness (no live API calls)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pydantic import BaseModel, ValidationError

from app.services.llm.cost import estimate_cost_cny, parse_usage
from app.services.llm.errors import LLMAPIError, LLMJSONError, LLMValidationError
from app.services.llm.extract import extract_json
from app.services.llm.retry import (
    classify_error,
    get_structured_retry_action,
    run_structured_completion,
)
from app.services.llm.truncate import truncate_messages


class SampleSchema(BaseModel):
    name: str
    score: int


class ExtractJsonTests(unittest.TestCase):
    def test_strips_markdown_fence(self):
        raw = '```json\n{"name": "a", "score": 1}\n```'
        data = extract_json(raw)
        self.assertEqual(data["name"], "a")

    def test_invalid_json_raises(self):
        with self.assertRaises(LLMJSONError):
            extract_json("not json at all")


class TruncateTests(unittest.TestCase):
    def test_truncates_system_and_user(self):
        messages = [
            {"role": "system", "content": "s" * 20},
            {"role": "user", "content": "u" * 20},
        ]
        out, flags = truncate_messages(messages, max_system_chars=5, max_user_chars=5)
        self.assertTrue(flags["system"])
        self.assertTrue(flags["user"])
        self.assertIn("...[truncated]", out[0]["content"])
        self.assertIn("...[truncated]", out[1]["content"])


class RetryPolicyTests(unittest.TestCase):
    def test_json_error_first_retry_lowers_temperature(self):
        action = get_structured_retry_action(
            LLMJSONError("bad json"),
            0,
            2,
            model="qwen-turbo",
            temperature=0.2,
            timeout=30.0,
            schema_name="SampleSchema",
        )
        self.assertTrue(action.retry)
        self.assertEqual(action.temperature, 0.1)
        self.assertIsNotNone(action.append_message)

    def test_validation_error_second_retry_escalates_model(self):
        action = get_structured_retry_action(
            LLMValidationError("missing field"),
            1,
            2,
            model="qwen-turbo",
            temperature=0.2,
            timeout=30.0,
            schema_name="SampleSchema",
        )
        self.assertTrue(action.retry)
        self.assertEqual(action.model, "qwen-plus")

    def test_auth_error_not_retryable(self):
        err = LLMAPIError("denied", status_code=401)
        action = get_structured_retry_action(
            err,
            0,
            2,
            model="qwen-turbo",
            temperature=0.2,
            timeout=30.0,
            schema_name="SampleSchema",
        )
        self.assertFalse(action.retry)

    def test_classify_validation_error(self):
        try:
            SampleSchema.model_validate({"name": "x"})
        except ValidationError:
            pass
        try:
            SampleSchema.model_validate({"score": 1})
        except ValidationError as exc:
            classified = classify_error(exc)
            self.assertIsInstance(classified, LLMValidationError)


class StructuredCompletionTests(unittest.TestCase):
    def test_retries_on_invalid_json_then_succeeds(self):
        client = MagicMock()
        client.complete.side_effect = ["not-json", '{"name": "bob", "score": 90}']
        result = run_structured_completion(
            client,
            [{"role": "user", "content": "go"}],
            SampleSchema,
            retries=2,
            purpose="test",
        )
        self.assertEqual(result.name, "bob")
        self.assertEqual(client.complete.call_count, 2)


class LogStoreTests(unittest.TestCase):
    def test_append_call_log_writes_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "calls.jsonl"
            with patch("app.services.llm.log_store.get_settings") as mock_settings:
                mock_settings.return_value.llm_log_enabled = True
                mock_settings.return_value.llm_log_path = str(log_path)
                from app.services.llm.log_store import append_call_log

                append_call_log({"call_id": "abc", "success": True})
            lines = log_path.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 1)
            record = json.loads(lines[0])
            self.assertEqual(record["call_id"], "abc")
            self.assertIn("ts", record)


class CostTests(unittest.TestCase):
    def test_estimate_cost_positive(self):
        cost = estimate_cost_cny("qwen-turbo", 1000, 500)
        self.assertGreater(cost, 0)

    def test_parse_usage_fallback_estimate(self):
        usage = parse_usage(None, input_text="abcd" * 10, output_text="efgh" * 5)
        self.assertTrue(usage["estimated"])
        self.assertGreater(usage["input"], 0)


if __name__ == "__main__":
    unittest.main()
