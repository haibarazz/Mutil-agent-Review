from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import yaml

from src.infra.llm import OpenAICompatibleLLMClient
from src.ports import LLMClient


@dataclass(frozen=True)
class LLMProviderRoute:
    """单个供应商的连接信息；真实密钥从 .env 读取。"""

    name: str
    type: str
    base_url_env: str
    api_key_env: str


@dataclass(frozen=True)
class LLMModelRoute:
    """一个 prompt model id 到真实供应商模型名的映射。"""

    model_id: str
    provider: str
    provider_model_id: str


@dataclass(frozen=True)
class LLMRouterConfig:
    """LLMRouter 使用的完整模型注册表。"""

    default_model: str
    providers: dict[str, LLMProviderRoute]
    models: dict[str, LLMModelRoute]
    prompt_options: dict[str, dict[str, Any]]


ClientFactory = Callable[[LLMProviderRoute, str, str, float], LLMClient]


def load_llm_router_config(path: Path) -> LLMRouterConfig:
    """从 configs/llm.yaml 加载模型注册表。"""
    if not path.exists():
        raise FileNotFoundError(f"LLM router config not found: {path}")

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("LLM router config must be a YAML mapping")

    provider_items = data.get("providers") or {}
    model_items = data.get("models") or {}
    prompt_items = data.get("prompts") or {}
    if not isinstance(provider_items, dict) or not isinstance(model_items, dict):
        raise ValueError("LLM router config must contain providers and models mappings")
    if not isinstance(prompt_items, dict):
        raise ValueError("LLM router config prompts must be a mapping")

    providers = {
        name: _provider_route(name, raw)
        for name, raw in provider_items.items()
    }
    models = {
        model_id: _model_route(model_id, raw)
        for model_id, raw in model_items.items()
    }

    default_model = str(data.get("default_model") or "")
    if not default_model:
        raise ValueError("LLM router config must define default_model")
    if default_model not in models:
        raise ValueError(f"default_model is not registered in models: {default_model}")

    missing_providers = sorted({route.provider for route in models.values()} - set(providers))
    if missing_providers:
        raise ValueError(f"LLM model routes reference unknown providers: {', '.join(missing_providers)}")

    prompt_options: dict[str, dict[str, Any]] = {}
    for name, raw in prompt_items.items():
        if not isinstance(raw, dict):
            raise ValueError(f"prompt options must be a mapping: {name}")
        prompt_options[str(name)] = dict(raw)

    return LLMRouterConfig(
        default_model=default_model,
        providers=providers,
        models=models,
        prompt_options=prompt_options,
    )


class LLMRouter:
    """按 model id 查表，把一次 LLM 调用路由到对应供应商。"""

    def __init__(
        self,
        *,
        config: LLMRouterConfig,
        timeout_sec: float,
        client_factory: ClientFactory | None = None,
    ) -> None:
        self.config = config
        self.timeout_sec = timeout_sec
        self.client_factory = client_factory or _default_client_factory
        self._clients: dict[str, LLMClient] = {}

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
        temperature, top_p, max_tokens = self._apply_prompt_options(
            prompt_name,
            temperature,
            top_p,
            max_tokens,
        )
        client, provider_model_id = self._resolve(model)
        return client.complete_text(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            prompt_name=prompt_name,
            model=provider_model_id,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
        )

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
        temperature, top_p, max_tokens = self._apply_prompt_options(
            prompt_name,
            temperature,
            top_p,
            max_tokens,
        )
        client, provider_model_id = self._resolve(model)
        return client.complete_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            prompt_name=prompt_name,
            model=provider_model_id,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
        )

    def _apply_prompt_options(
        self,
        prompt_name: str | None,
        temperature: float,
        top_p: float | None,
        max_tokens: int | None,
    ) -> tuple[float, float | None, int | None]:
        if not prompt_name:
            return temperature, top_p, max_tokens
        options = self.config.prompt_options.get(prompt_name, {})
        return (
            float(options.get("temperature", temperature)),
            _optional_float(options.get("top_p", top_p)),
            _optional_int(options.get("max_tokens", max_tokens)),
        )

    def _resolve(self, model: str | None) -> tuple[LLMClient, str]:
        model_id = model or self.config.default_model
        if model_id not in self.config.models:
            raise RuntimeError(f"LLM model is not registered in configs/llm.yaml: {model_id}")

        model_route = self.config.models[model_id]
        provider = self.config.providers[model_route.provider]
        return self._client_for(provider), model_route.provider_model_id

    def _client_for(self, provider: LLMProviderRoute) -> LLMClient:
        if provider.name in self._clients:
            return self._clients[provider.name]

        base_url = os.getenv(provider.base_url_env, "")
        api_key = os.getenv(provider.api_key_env, "")
        if not base_url or not api_key:
            raise RuntimeError(
                f"Missing LLM provider env for {provider.name}: "
                f"{provider.base_url_env} and {provider.api_key_env}"
            )

        client = self.client_factory(provider, base_url, api_key, self.timeout_sec)
        self._clients[provider.name] = client
        return client


def _provider_route(name: str, raw: Any) -> LLMProviderRoute:
    if not isinstance(raw, dict):
        raise ValueError(f"provider route must be a mapping: {name}")
    provider_type = str(raw.get("type") or "")
    if provider_type != "openai_compatible":
        raise ValueError(f"unsupported provider type for {name}: {provider_type}")
    base_url_env = str(raw.get("base_url_env") or "")
    api_key_env = str(raw.get("api_key_env") or "")
    if not base_url_env or not api_key_env:
        raise ValueError(f"provider route must define base_url_env and api_key_env: {name}")
    return LLMProviderRoute(
        name=name,
        type=provider_type,
        base_url_env=base_url_env,
        api_key_env=api_key_env,
    )


def _model_route(model_id: str, raw: Any) -> LLMModelRoute:
    if not isinstance(raw, dict):
        raise ValueError(f"model route must be a mapping: {model_id}")
    provider = str(raw.get("provider") or "")
    provider_model_id = str(raw.get("provider_model_id") or model_id)
    if not provider:
        raise ValueError(f"model route must define provider: {model_id}")
    return LLMModelRoute(
        model_id=model_id,
        provider=provider,
        provider_model_id=provider_model_id,
    )


def _default_client_factory(
    provider: LLMProviderRoute,
    base_url: str,
    api_key: str,
    timeout_sec: float,
) -> LLMClient:
    return OpenAICompatibleLLMClient(
        base_url=base_url,
        api_key=api_key,
        default_model=provider.name,
        timeout_sec=timeout_sec,
    )


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)
