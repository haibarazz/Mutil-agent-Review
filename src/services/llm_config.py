from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from src.core.prompts import PromptRepository
from src.infra.llm_router import LLMRouterConfig, load_llm_router_config
from src.infra.settings import Settings, load_settings


def build_llm_runtime_config(settings: Settings | None = None) -> dict[str, Any]:
    """生成给前端 Settings 页看的 LLM 路由摘要；只暴露配置结构，不暴露密钥和值。"""
    settings = settings or load_settings()
    payload: dict[str, Any] = {
        "status": "loaded",
        "mode": settings.llm_provider,
        "config_path": str(settings.llm_config_path),
        "default_model": "",
        "providers": [],
        "models": [],
        "nodes": [],
        "prompts": [],
        "error_type": "",
        "error_message": "",
    }
    try:
        config = load_llm_router_config(settings.llm_config_path)
    except Exception as exc:
        payload["status"] = "error"
        payload["error_type"] = exc.__class__.__name__
        payload["error_message"] = str(exc)
        return payload

    payload["default_model"] = config.default_model
    payload["providers"] = _provider_summaries(config)
    payload["models"] = _model_summaries(config)
    payload["nodes"] = _node_summaries(config)
    payload["prompts"] = _prompt_summaries(settings.prompts_dir, config)
    return payload


def _provider_summaries(config: LLMRouterConfig) -> list[dict[str, Any]]:
    return [
        {
            "name": provider.name,
            "type": provider.type,
            "base_url_env": provider.base_url_env,
            "api_key_env": provider.api_key_env,
            "base_url_configured": bool(os.getenv(provider.base_url_env, "")),
            "api_key_configured": bool(os.getenv(provider.api_key_env, "")),
        }
        for provider in sorted(config.providers.values(), key=lambda item: item.name)
    ]


def _model_summaries(config: LLMRouterConfig) -> list[dict[str, Any]]:
    return [
        {
            "model_id": model.model_id,
            "provider": model.provider,
            "provider_model_id": model.provider_model_id,
            "max_attempts": model.max_attempts,
            "fallback_models": list(model.fallback_models),
        }
        for model in sorted(config.models.values(), key=lambda item: item.model_id)
    ]


def _node_summaries(config: LLMRouterConfig) -> list[dict[str, Any]]:
    return [
        {
            "name": node.node_id,
            "primary_model": node.primary_model,
            "max_attempts": node.max_attempts,
            "fallback_models": list(node.fallback_models),
        }
        for node in sorted(config.nodes.values(), key=lambda item: item.node_id)
    ]


def _prompt_summaries(prompts_dir: Path, config: LLMRouterConfig) -> list[dict[str, Any]]:
    repository = PromptRepository(prompts_dir)
    prompts: list[dict[str, Any]] = []
    for path in sorted(prompts_dir.glob("*.md")):
        prompt = repository.load(path.stem)
        route = config.models.get(prompt.model)
        prompts.append(
            {
                "name": prompt.name,
                "model": prompt.model,
                "registered": route is not None,
                "provider": route.provider if route else "",
                "provider_model_id": route.provider_model_id if route else "",
            }
        )
    return prompts
