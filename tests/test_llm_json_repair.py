from __future__ import annotations

import unittest
from typing import Any

from src.core.errors import ModelOutputParseError
from src.infra.llm import OpenAICompatibleLLMClient, extract_json_object
from src.infra.llm_diagnostics import llm_diagnostics_run, start_llm_call_collection, stop_llm_call_collection


class RepairingClient(OpenAICompatibleLLMClient):
    def __init__(self) -> None:
        super().__init__(
            base_url="https://example.invalid",
            api_key="test",
            default_model="test-model",
            timeout_sec=1,
        )
        self.calls = 0

    def _chat_completion(self, **kwargs: Any) -> dict[str, Any]:
        self.calls += 1
        content = '{"summary": "ok" "rating": 6}'
        return {"choices": [{"message": {"content": content}}]}


class BrokenRepairClient(OpenAICompatibleLLMClient):
    def __init__(self) -> None:
        super().__init__(
            base_url="https://example.invalid",
            api_key="test",
            default_model="test-model",
            timeout_sec=1,
        )

    def _chat_completion(self, **kwargs: Any) -> dict[str, Any]:
        return {"choices": [{"message": {"content": "not json at all"}}]}


class UsageClient(OpenAICompatibleLLMClient):
    def __init__(self) -> None:
        super().__init__(
            base_url="https://example.invalid",
            api_key="test",
            default_model="test-model",
            timeout_sec=1,
        )

    def _chat_completion(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "choices": [{"message": {"content": '{"ok": true}'}}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 3, "total_tokens": 15},
        }


class LLMJsonRepairTest(unittest.TestCase):
    def test_extract_json_object_repairs_missing_comma_locally(self) -> None:
        result = extract_json_object('{"summary": "ok" "rating": 6}')

        self.assertEqual(result, {"summary": "ok", "rating": 6})

    def test_complete_json_uses_local_repair_before_model_retry(self) -> None:
        client = RepairingClient()

        result = client.complete_json(system_prompt="system", user_prompt="user")

        self.assertEqual(result, {"summary": "ok", "rating": 6})
        self.assertEqual(client.calls, 1)

    def test_complete_json_raises_parse_error_when_repair_fails(self) -> None:
        client = BrokenRepairClient()

        with self.assertRaises(ModelOutputParseError):
            client.complete_json(system_prompt="system", user_prompt="user")

    def test_complete_json_records_parse_error_raw_output(self) -> None:
        client = BrokenRepairClient()

        start_llm_call_collection("parse-error")
        try:
            with llm_diagnostics_run("parse-error"):
                with self.assertRaises(ModelOutputParseError) as caught:
                    client.complete_json(system_prompt="system", user_prompt="user", prompt_name="reviewer2")
        finally:
            collector = stop_llm_call_collection("parse-error")

        self.assertEqual(1, len(collector.model_output_errors))
        output_error = collector.model_output_errors[0]
        self.assertEqual("parse_error", output_error["kind"])
        self.assertEqual("model_output_errors/parse_error_001.json", output_error["path"])
        self.assertEqual("not json at all", output_error["payload"]["raw_output"])
        self.assertEqual("not json at all", output_error["payload"]["repair_output"])
        self.assertEqual(
            "model_output_errors/parse_error_001.json",
            caught.exception.context.details["model_output_error_ref"],
        )

    def test_complete_json_exposes_openai_compatible_usage(self) -> None:
        client = UsageClient()

        result = client.complete_json(system_prompt="system", user_prompt="user")

        self.assertEqual({"ok": True}, result)
        self.assertEqual(
            {"input_tokens": 12, "output_tokens": 3, "total_tokens": 15},
            client.last_usage,
        )
