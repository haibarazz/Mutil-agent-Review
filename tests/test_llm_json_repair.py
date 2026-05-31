from __future__ import annotations

import unittest
from typing import Any

from src.core.errors import ModelOutputParseError
from src.infra.llm import OpenAICompatibleLLMClient, extract_json_object


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
