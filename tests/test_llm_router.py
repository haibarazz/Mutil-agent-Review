import os
import tempfile
import unittest
from pathlib import Path
from typing import Any

from src.infra.llm_router import LLMRouter, load_llm_router_config


class _RecordingClient:
    def __init__(self, calls: list[dict[str, Any]], provider: str) -> None:
        self.calls = calls
        self.provider = provider

    def complete_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        prompt_name: str | None = None,
        model: str | None = None,
        temperature: float = 0.2,
        top_p: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        self.calls.append({
            "kind": "text",
            "provider": self.provider,
            "model": model,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
        })
        return "ok"

    def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        prompt_name: str | None = None,
        model: str | None = None,
        temperature: float = 0.2,
        top_p: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        self.calls.append({
            "kind": "json",
            "provider": self.provider,
            "model": model,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
        })
        return {"ok": True}


class LLMRouterTests(unittest.TestCase):
    def test_loads_model_registry_and_routes_by_prompt_model_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "llm.yaml"
            config_path.write_text(
                """
default_model: prompt-default
providers:
  fake_provider:
    type: openai_compatible
    base_url_env: TEST_FAKE_BASE_URL
    api_key_env: TEST_FAKE_API_KEY
models:
  prompt-default:
    provider: fake_provider
    provider_model_id: provider-default
  prompt-model:
    provider: fake_provider
    provider_model_id: provider-model
prompts:
  reviewer2:
    temperature: 0.6
    top_p: 0.95
    max_tokens: 4000
""",
                encoding="utf-8",
            )
            os.environ["TEST_FAKE_BASE_URL"] = "https://example.test/v1"
            os.environ["TEST_FAKE_API_KEY"] = "secret"
            calls: list[dict[str, Any]] = []
            config = load_llm_router_config(config_path)

            router = LLMRouter(
                config=config,
                timeout_sec=3,
                client_factory=lambda provider, base_url, api_key, timeout: _RecordingClient(
                    calls,
                    provider.name,
                ),
            )
            result = router.complete_json(
                system_prompt="system",
                user_prompt="user",
                prompt_name="reviewer2",
                model="prompt-model",
                temperature=0.1,
            )

        self.assertEqual({"ok": True}, result)
        self.assertEqual(
            [{
                "kind": "json",
                "provider": "fake_provider",
                "model": "provider-model",
                "temperature": 0.6,
                "top_p": 0.95,
                "max_tokens": 4000,
            }],
            calls,
        )

    def test_unknown_model_fails_fast(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "llm.yaml"
            config_path.write_text(
                """
default_model: prompt-default
providers:
  fake_provider:
    type: openai_compatible
    base_url_env: TEST_FAKE_BASE_URL
    api_key_env: TEST_FAKE_API_KEY
models:
  prompt-default:
    provider: fake_provider
    provider_model_id: provider-default
""",
                encoding="utf-8",
            )
            config = load_llm_router_config(config_path)
            router = LLMRouter(
                config=config,
                timeout_sec=3,
                client_factory=lambda provider, base_url, api_key, timeout: _RecordingClient([], provider.name),
            )

            with self.assertRaisesRegex(RuntimeError, "not registered"):
                router.complete_text(system_prompt="system", user_prompt="user", model="missing-model")


if __name__ == "__main__":
    unittest.main()
