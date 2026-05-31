import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any
from unittest.mock import patch

from src.core.errors import (
    ConfigurationError,
    ErrorContext,
    ModelOutputValidationError,
    ProviderFatalError,
    ProviderTransientError,
)
from src.infra.llm_router import LLMRouter, load_llm_router_config
from src.infra.llm_diagnostics import llm_diagnostics_run, start_llm_call_collection, stop_llm_call_collection


class _RecordingClient:
    def __init__(
        self,
        calls: list[dict[str, Any]],
        provider: str,
        failures: dict[tuple[str, str], list[Exception]] | None = None,
    ) -> None:
        self.calls = calls
        self.provider = provider
        self.failures = failures or {}

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
        self._maybe_fail("text", str(model))
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
        self._maybe_fail("json", str(model))
        return {"ok": True}

    def _maybe_fail(self, kind: str, model: str) -> None:
        failures = self.failures.get((kind, model), [])
        if failures:
            raise failures.pop(0)


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

            with self.assertRaisesRegex(ConfigurationError, "not registered"):
                router.complete_text(system_prompt="system", user_prompt="user", model="missing-model")

    def test_unknown_fallback_model_raises_configuration_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "llm.yaml"
            config_path.write_text(
                """
default_model: primary
providers:
  fake_provider:
    type: openai_compatible
    base_url_env: TEST_FAKE_BASE_URL
    api_key_env: TEST_FAKE_API_KEY
models:
  primary:
    provider: fake_provider
    provider_model_id: provider-primary
    fallback_models:
      - missing-fallback
""",
                encoding="utf-8",
            )
            config = load_llm_router_config(config_path)
            router = LLMRouter(
                config=config,
                timeout_sec=3,
                client_factory=lambda provider, base_url, api_key, timeout: _RecordingClient([], provider.name),
            )

            with self.assertRaisesRegex(ConfigurationError, "fallback model is not registered"):
                router.complete_text(system_prompt="system", user_prompt="user", model="primary")

    def test_missing_provider_env_raises_configuration_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "llm.yaml"
            config_path.write_text(
                """
default_model: prompt-default
providers:
  fake_provider:
    type: openai_compatible
    base_url_env: TEST_MISSING_BASE_URL
    api_key_env: TEST_MISSING_API_KEY
models:
  prompt-default:
    provider: fake_provider
    provider_model_id: provider-default
""",
                encoding="utf-8",
            )
            os.environ.pop("TEST_MISSING_BASE_URL", None)
            os.environ.pop("TEST_MISSING_API_KEY", None)
            config = load_llm_router_config(config_path)
            router = LLMRouter(
                config=config,
                timeout_sec=3,
                client_factory=lambda provider, base_url, api_key, timeout: _RecordingClient([], provider.name),
            )

            with self.assertRaisesRegex(ConfigurationError, "Missing LLM provider env") as caught:
                router.complete_text(system_prompt="system", user_prompt="user")

        self.assertEqual("fake_provider", caught.exception.context.provider)
        self.assertEqual("prompt-default", caught.exception.context.model)
        self.assertEqual(1, caught.exception.context.attempt)

    def test_missing_provider_env_records_llm_error_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "llm.yaml"
            config_path.write_text(
                """
default_model: prompt-default
providers:
  fake_provider:
    type: openai_compatible
    base_url_env: TEST_DIAG_MISSING_BASE_URL
    api_key_env: TEST_DIAG_MISSING_API_KEY
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
            collector = start_llm_call_collection("missing-env-test")

            try:
                with patch.dict(
                    os.environ,
                    {
                        "TEST_DIAG_MISSING_BASE_URL": "",
                        "TEST_DIAG_MISSING_API_KEY": "",
                    },
                ), llm_diagnostics_run("missing-env-test"):
                    with self.assertRaises(ConfigurationError):
                        router.complete_text(
                            system_prompt="system secret",
                            user_prompt="SECRET PAPER BODY",
                            prompt_name="content_check",
                        )
            finally:
                collector = stop_llm_call_collection("missing-env-test")

        self.assertEqual(1, len(collector.events))
        event = collector.events[0]
        self.assertEqual("error", event["event"])
        self.assertEqual("text", event["kind"])
        self.assertEqual("content_check", event["prompt"])
        self.assertEqual("prompt-default", event["requested_model"])
        self.assertEqual("prompt-default", event["model"])
        self.assertEqual("fake_provider", event["provider"])
        self.assertEqual(1, event["attempt"])
        self.assertEqual("ConfigurationError", event["error_type"])
        self.assertEqual("false", event["retryable"])
        self.assertNotIn("system secret", str(event))
        self.assertNotIn("SECRET PAPER BODY", str(event))

    def test_retries_primary_model_then_falls_back(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "llm.yaml"
            config_path.write_text(
                """
default_model: primary
providers:
  fake_provider:
    type: openai_compatible
    base_url_env: TEST_FAKE_BASE_URL
    api_key_env: TEST_FAKE_API_KEY
models:
  primary:
    provider: fake_provider
    provider_model_id: provider-primary
    max_attempts: 2
    fallback_models:
      - fallback
  fallback:
    provider: fake_provider
    provider_model_id: provider-fallback
    max_attempts: 3
""",
                encoding="utf-8",
            )
            os.environ["TEST_FAKE_BASE_URL"] = "https://example.test/v1"
            os.environ["TEST_FAKE_API_KEY"] = "secret"
            calls: list[dict[str, Any]] = []
            failures = {
                ("json", "provider-primary"): [
                    ProviderTransientError("temporary one"),
                    ProviderTransientError("temporary two"),
                ]
            }
            config = load_llm_router_config(config_path)
            router = LLMRouter(
                config=config,
                timeout_sec=3,
                client_factory=lambda provider, base_url, api_key, timeout: _RecordingClient(
                    calls,
                    provider.name,
                    failures,
                ),
            )

            result = router.complete_json(system_prompt="system", user_prompt="user", model="primary")

        self.assertEqual({"ok": True}, result)
        self.assertEqual(
            ["provider-primary", "provider-primary", "provider-fallback"],
            [call["model"] for call in calls],
        )

    def test_fatal_provider_error_skips_primary_retry_and_uses_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "llm.yaml"
            config_path.write_text(
                """
default_model: primary
providers:
  fake_provider:
    type: openai_compatible
    base_url_env: TEST_FAKE_BASE_URL
    api_key_env: TEST_FAKE_API_KEY
models:
  primary:
    provider: fake_provider
    provider_model_id: provider-primary
    max_attempts: 2
    fallback_models:
      - fallback
  fallback:
    provider: fake_provider
    provider_model_id: provider-fallback
    max_attempts: 1
""",
                encoding="utf-8",
            )
            os.environ["TEST_FAKE_BASE_URL"] = "https://example.test/v1"
            os.environ["TEST_FAKE_API_KEY"] = "secret"
            calls: list[dict[str, Any]] = []
            failures = {("text", "provider-primary"): [ProviderFatalError("invalid key")]}
            config = load_llm_router_config(config_path)
            router = LLMRouter(
                config=config,
                timeout_sec=3,
                client_factory=lambda provider, base_url, api_key, timeout: _RecordingClient(
                    calls,
                    provider.name,
                    failures,
                ),
            )

            result = router.complete_text(system_prompt="system", user_prompt="user", model="primary")

        self.assertEqual("ok", result)
        self.assertEqual(["provider-primary", "provider-fallback"], [call["model"] for call in calls])

    def test_validation_error_retries_primary_then_falls_back(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "llm.yaml"
            config_path.write_text(
                """
default_model: primary
providers:
  fake_provider:
    type: openai_compatible
    base_url_env: TEST_FAKE_BASE_URL
    api_key_env: TEST_FAKE_API_KEY
models:
  primary:
    provider: fake_provider
    provider_model_id: provider-primary
    max_attempts: 2
    fallback_models:
      - fallback
  fallback:
    provider: fake_provider
    provider_model_id: provider-fallback
    max_attempts: 1
""",
                encoding="utf-8",
            )
            os.environ["TEST_FAKE_BASE_URL"] = "https://example.test/v1"
            os.environ["TEST_FAKE_API_KEY"] = "secret"
            calls: list[dict[str, Any]] = []
            validation_contexts: list[dict[str, Any]] = []

            def validator(value: dict[str, Any], *, context: ErrorContext) -> dict[str, Any]:
                validation_contexts.append(context.to_dict())
                if context.model == "primary":
                    raise ModelOutputValidationError("schema failed", context=context)
                return value

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
                prompt_name="reviewer1",
                model="primary",
                validator=validator,
            )

        self.assertEqual({"ok": True}, result)
        self.assertEqual(
            ["provider-primary", "provider-primary", "provider-fallback"],
            [call["model"] for call in calls],
        )
        self.assertEqual(
            ["primary", "primary", "fallback"],
            [item["model"] for item in validation_contexts],
        )

    def test_router_verbose_off_by_default(self) -> None:
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
            output = io.StringIO()

            with patch.dict(
                os.environ,
                {
                    "TEST_FAKE_BASE_URL": "https://example.test/v1",
                    "TEST_FAKE_API_KEY": "secret",
                    "REVIEW_LLM_VERBOSE": "",
                },
            ), redirect_stdout(output):
                router.complete_text(system_prompt="system", user_prompt="user")

        self.assertEqual("", output.getvalue())

    def test_router_verbose_logs_safe_attempt_summary(self) -> None:
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
""",
                encoding="utf-8",
            )
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
            output = io.StringIO()

            with patch.dict(
                os.environ,
                {
                    "TEST_FAKE_BASE_URL": "https://example.test/v1",
                    "TEST_FAKE_API_KEY": "secret",
                    "REVIEW_LLM_VERBOSE": "true",
                },
            ), redirect_stdout(output):
                router.complete_json(
                    system_prompt="system secret",
                    user_prompt="SECRET PAPER BODY",
                    prompt_name="reviewer1",
                    model="prompt-model",
                )

        logs = output.getvalue()
        self.assertIn("[llm-router:start]", logs)
        self.assertIn("kind=json", logs)
        self.assertIn("prompt=reviewer1", logs)
        self.assertIn("model=prompt-model", logs)
        self.assertIn("provider=fake_provider", logs)
        self.assertIn("provider_model=provider-model", logs)
        self.assertIn("attempt=1", logs)
        self.assertIn("system_chars=13", logs)
        self.assertIn("user_chars=17", logs)
        self.assertIn("[llm-router:done]", logs)
        self.assertNotIn("system secret", logs)
        self.assertNotIn("SECRET PAPER BODY", logs)
        self.assertNotIn("secret", logs)

    def test_router_verbose_logs_error_and_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "llm.yaml"
            config_path.write_text(
                """
default_model: primary
providers:
  fake_provider:
    type: openai_compatible
    base_url_env: TEST_FAKE_BASE_URL
    api_key_env: TEST_FAKE_API_KEY
models:
  primary:
    provider: fake_provider
    provider_model_id: provider-primary
    max_attempts: 1
    fallback_models:
      - fallback
  fallback:
    provider: fake_provider
    provider_model_id: provider-fallback
    max_attempts: 1
""",
                encoding="utf-8",
            )
            calls: list[dict[str, Any]] = []
            failures = {("json", "provider-primary"): [ProviderTransientError("temporary provider issue")]}
            config = load_llm_router_config(config_path)
            router = LLMRouter(
                config=config,
                timeout_sec=3,
                client_factory=lambda provider, base_url, api_key, timeout: _RecordingClient(
                    calls,
                    provider.name,
                    failures,
                ),
            )
            output = io.StringIO()

            with patch.dict(
                os.environ,
                {
                    "TEST_FAKE_BASE_URL": "https://example.test/v1",
                    "TEST_FAKE_API_KEY": "secret",
                    "REVIEW_LLM_VERBOSE": "true",
                },
            ), redirect_stdout(output):
                router.complete_json(system_prompt="system", user_prompt="user", prompt_name="reviewer2", model="primary")

        logs = output.getvalue()
        self.assertIn("[llm-router:error]", logs)
        self.assertIn("error_type=ProviderTransientError", logs)
        self.assertIn("retryable=true", logs)
        self.assertIn("[llm-router:fallback]", logs)
        self.assertIn("from_model=primary", logs)
        self.assertIn("to_model=fallback", logs)
        self.assertIn("fallback=true", logs)
        self.assertIn("model=fallback", logs)
        self.assertIn("provider_model=provider-fallback", logs)
        self.assertNotIn("temporary provider issue", logs)


if __name__ == "__main__":
    unittest.main()
