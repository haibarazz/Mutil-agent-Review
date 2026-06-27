from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import yaml

from src.core.errors import ConfigurationError, ErrorContext, ProviderFatalError, ProviderTransientError, ReviewAgentError
from src.infra.llm import OpenAICompatibleLLMClient
from src.infra.llm_diagnostics import record_llm_event
from src.ports import JsonValidator, LLMClient


@dataclass(frozen=True)
class LLMProviderRoute:
    """单个供应商的连接信息；真实密钥从 .env 读取。"""

    name: str
    type: str
    base_url_env: str
    api_key_env: str


@dataclass(frozen=True)
class LLMModelRoute:
    """一个稳定模型 ID 到真实供应商模型名的映射。"""

    model_id: str
    provider: str
    provider_model_id: str
    max_attempts: int
    retry_backoff_sec: float
    fallback_models: tuple[str, ...]


@dataclass(frozen=True)
class LLMNodeRoute:
    """节点级调用策略：节点决定主模型、重试次数和降级链。"""

    node_id: str
    primary_model: str
    max_attempts: int
    fallback_models: tuple[str, ...]


@dataclass(frozen=True)
class LLMRouterConfig:
    """LLMRouter 使用的完整模型注册表。"""

    default_model: str
    providers: dict[str, LLMProviderRoute]
    models: dict[str, LLMModelRoute]
    nodes: dict[str, LLMNodeRoute]
    prompt_options: dict[str, dict[str, Any]]


@dataclass(frozen=True)
class LLMCallRoute:
    """一次调用链中的路由项；fallback 使用时只尝试一次。"""

    model: LLMModelRoute
    max_attempts: int


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
    node_items = data.get("nodes") or {}
    prompt_items = data.get("prompts") or {}
    if not isinstance(provider_items, dict) or not isinstance(model_items, dict):
        raise ValueError("LLM router config must contain providers and models mappings")
    if not isinstance(node_items, dict):
        raise ValueError("LLM router config nodes must be a mapping")
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
    nodes = {
        node_id: _node_route(node_id, raw)
        for node_id, raw in node_items.items()
    }

    default_model = str(data.get("default_model") or "")
    if not default_model:
        raise ValueError("LLM router config must define default_model")
    if default_model not in models:
        raise ValueError(f"default_model is not registered in models: {default_model}")

    missing_providers = sorted({route.provider for route in models.values()} - set(providers))
    if missing_providers:
        raise ValueError(f"LLM model routes reference unknown providers: {', '.join(missing_providers)}")
    missing_node_models = _missing_node_models(nodes, models)
    if missing_node_models:
        raise ValueError(f"LLM node routes reference unknown models: {', '.join(missing_node_models)}")

    prompt_options: dict[str, dict[str, Any]] = {}
    for name, raw in prompt_items.items():
        if not isinstance(raw, dict):
            raise ValueError(f"prompt options must be a mapping: {name}")
        prompt_options[str(name)] = dict(raw)

    return LLMRouterConfig(
        default_model=default_model,
        providers=providers,
        models=models,
        nodes=nodes,
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
        return self._complete_with_fallback(
            kind="text",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            prompt_name=prompt_name,
            model=model,
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
        validator: JsonValidator | None = None,
    ) -> dict[str, Any]:
        temperature, top_p, max_tokens = self._apply_prompt_options(
            prompt_name,
            temperature,
            top_p,
            max_tokens,
        )
        return self._complete_with_fallback(
            kind="json",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            prompt_name=prompt_name,
            model=model,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            validator=validator,
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

    def _complete_with_fallback(
        self,
        *,
        kind: str,
        system_prompt: str,
        user_prompt: str,
        prompt_name: str | None,
        model: str | None,
        temperature: float,
        top_p: float | None,
        max_tokens: int | None,
        validator: JsonValidator | None = None,
    ) -> Any:
        errors: list[ReviewAgentError] = []
        routes, requested_model_id = self._routes_for(model=model, prompt_name=prompt_name)
        last_route_error: ReviewAgentError | None = None
        for route_index, call_route in enumerate(routes):
            route = call_route.model
            is_fallback = route_index > 0
            if is_fallback:
                previous_route = routes[route_index - 1].model
                _log_llm_event(
                    "fallback",
                    prompt=_display_prompt(prompt_name),
                    from_model=previous_route.model_id,
                    to_model=route.model_id,
                    reason=last_route_error.__class__.__name__ if last_route_error else "",
                )
            for attempt in range(1, call_route.max_attempts + 1):
                started = time.perf_counter()
                provider_model_id = ""
                try:
                    client, provider_model_id = self._resolve(route.model_id)
                    _log_llm_event(
                        "start",
                        kind=kind,
                        prompt=_display_prompt(prompt_name),
                        requested_model=requested_model_id,
                        model=route.model_id,
                        provider=route.provider,
                        provider_model=provider_model_id,
                        attempt=attempt,
                        max_attempts=call_route.max_attempts,
                        fallback=str(is_fallback).lower(),
                        temperature=temperature,
                        top_p=top_p,
                        max_tokens=max_tokens,
                        system_chars=len(system_prompt),
                        user_chars=len(user_prompt),
                    )
                    if kind == "text":
                        result = client.complete_text(
                            system_prompt=system_prompt,
                            user_prompt=user_prompt,
                            prompt_name=prompt_name,
                            model=provider_model_id,
                            temperature=temperature,
                            top_p=top_p,
                            max_tokens=max_tokens,
                        )
                    else:
                        result = client.complete_json(
                            system_prompt=system_prompt,
                            user_prompt=user_prompt,
                            prompt_name=prompt_name,
                            model=provider_model_id,
                            temperature=temperature,
                            top_p=top_p,
                            max_tokens=max_tokens,
                        )
                        result = self._apply_validator(
                            result,
                            validator,
                            route=route,
                            attempt=attempt,
                            prompt_name=prompt_name,
                        )
                    _log_llm_event(
                        "done",
                        kind=kind,
                        prompt=_display_prompt(prompt_name),
                        model=route.model_id,
                        provider=route.provider,
                        provider_model=provider_model_id,
                        attempt=attempt,
                        elapsed_ms=_elapsed_ms(started),
                    )
                    return result
                except Exception as exc:
                    elapsed_ms = _elapsed_ms(started)
                    error = self._classify_call_error(exc, route, attempt, prompt_name)
                    errors.append(error)
                    last_route_error = error
                    next_action = self._next_action(
                        error=error,
                        attempt=attempt,
                        max_attempts=call_route.max_attempts,
                        route_index=route_index,
                        route_count=len(routes),
                    )
                    _log_llm_event(
                        "error",
                        kind=kind,
                        prompt=_display_prompt(prompt_name),
                        requested_model=requested_model_id,
                        model=route.model_id,
                        provider=route.provider,
                        provider_model=provider_model_id,
                        attempt=attempt,
                        max_attempts=call_route.max_attempts,
                        fallback=str(is_fallback).lower(),
                        elapsed_ms=elapsed_ms,
                        error_type=error.__class__.__name__,
                        error_message=error.message,
                        retryable=str(error.retryable).lower(),
                        next_action=next_action,
                    )
                    # 配置错误不是供应商波动，继续 retry/fallback 只会掩盖真实问题。
                    if isinstance(error, ConfigurationError):
                        raise error
                    if not error.retryable:
                        break
                    if attempt < call_route.max_attempts and route.retry_backoff_sec > 0:
                        time.sleep(route.retry_backoff_sec)
        raise self._exhausted_error(errors, requested_model_id)

    def _next_action(
        self,
        *,
        error: ReviewAgentError,
        attempt: int,
        max_attempts: int,
        route_index: int,
        route_count: int,
    ) -> str:
        if isinstance(error, ConfigurationError):
            return "raise_configuration_error"
        if error.retryable and attempt < max_attempts:
            return "retry_same_model"
        if route_index + 1 < route_count:
            return "fallback_model"
        return "exhausted"

    def _routes_for(self, *, model: str | None, prompt_name: str | None) -> tuple[list[LLMCallRoute], str]:
        if prompt_name and prompt_name in self.config.nodes:
            node = self.config.nodes[prompt_name]
            return (
                self._routes_from_model_ids(
                    primary_model=node.primary_model,
                    primary_max_attempts=node.max_attempts,
                    fallback_models=node.fallback_models,
                ),
                prompt_name,
            )

        model_id = model or self.config.default_model
        if model_id not in self.config.models:
            raise ConfigurationError(f"LLM model is not registered in configs/llm.yaml: {model_id}")
        model_route = self.config.models[model_id]
        return (
            self._routes_from_model_ids(
                primary_model=model_id,
                primary_max_attempts=model_route.max_attempts,
                fallback_models=model_route.fallback_models,
            ),
            model_id,
        )

    def _routes_from_model_ids(
        self,
        *,
        primary_model: str,
        primary_max_attempts: int,
        fallback_models: tuple[str, ...],
    ) -> list[LLMCallRoute]:
        routes: list[LLMCallRoute] = []
        seen: set[str] = set()
        for index, item in enumerate((primary_model, *fallback_models)):
            if item in seen:
                continue
            if item not in self.config.models:
                raise ConfigurationError(f"LLM fallback model is not registered in configs/llm.yaml: {item}")
            route = self.config.models[item]
            # 作为主模型时允许“同模型重试一次”；作为降级/兜底模型时只试一次。
            max_attempts = max(1, primary_max_attempts) if index == 0 else 1
            routes.append(LLMCallRoute(model=route, max_attempts=max_attempts))
            seen.add(item)
        return routes

    def _apply_validator(
        self,
        result: dict[str, Any],
        validator: JsonValidator | None,
        *,
        route: LLMModelRoute,
        attempt: int,
        prompt_name: str | None,
    ) -> dict[str, Any]:
        if validator is None:
            return result
        return validator(
            result,
            context=ErrorContext(
                prompt_name=prompt_name or "",
                provider=route.provider,
                model=route.model_id,
                attempt=attempt,
            ),
        )

    def _resolve(self, model: str | None) -> tuple[LLMClient, str]:
        model_id = model or self.config.default_model
        if model_id not in self.config.models:
            raise ConfigurationError(f"LLM model is not registered in configs/llm.yaml: {model_id}")

        model_route = self.config.models[model_id]
        provider = self.config.providers[model_route.provider]
        return self._client_for(provider), model_route.provider_model_id

    def _client_for(self, provider: LLMProviderRoute) -> LLMClient:
        if provider.name in self._clients:
            return self._clients[provider.name]

        base_url = os.getenv(provider.base_url_env, "")
        api_key = os.getenv(provider.api_key_env, "")
        if not base_url or not api_key:
            raise ConfigurationError(
                f"Missing LLM provider env for {provider.name}: "
                f"{provider.base_url_env} and {provider.api_key_env}",
                context=ErrorContext(provider=provider.name),
            )

        client = self.client_factory(provider, base_url, api_key, self.timeout_sec)
        self._clients[provider.name] = client
        return client

    def _classify_call_error(
        self,
        exc: Exception,
        route: LLMModelRoute,
        attempt: int,
        prompt_name: str | None,
    ) -> ReviewAgentError:
        if isinstance(exc, ReviewAgentError):
            return _with_call_context(exc, route, attempt, prompt_name)
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        context = ErrorContext(
            prompt_name=prompt_name or "",
            provider=route.provider,
            model=route.model_id,
            attempt=attempt,
        )
        if status_code in {401, 403, 404}:
            return ProviderFatalError(str(exc), context=context)
        if status_code == 429 or (isinstance(status_code, int) and status_code >= 500):
            return ProviderTransientError(str(exc), context=context)
        name = exc.__class__.__name__.lower()
        message = str(exc).lower()
        if "timeout" in name or "timeout" in message or "connect" in name or "network" in message:
            return ProviderTransientError(str(exc), context=context)
        return ProviderTransientError(str(exc), context=context)

    def _exhausted_error(self, errors: list[ReviewAgentError], model_id: str) -> ReviewAgentError:
        message = f"LLM route exhausted for {model_id}"
        if errors:
            message = f"{message}: {errors[-1].message}"
        error_cls = errors[-1].__class__ if errors else ProviderTransientError
        # route exhausted 是“结果”，真实错误类型应该跟随最后一次失败原因，方便 batch 统计定位。
        return error_cls(
            message,
            context=ErrorContext(
                model=model_id,
                details={"errors": [error.to_dict() for error in errors]},
            ),
        )


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
    max_attempts = max(1, int(raw.get("max_attempts", 1)))
    retry_backoff_sec = float(raw.get("retry_backoff_sec", 0))
    fallback_models = raw.get("fallback_models") or ()
    if not provider:
        raise ValueError(f"model route must define provider: {model_id}")
    if not isinstance(fallback_models, (list, tuple)):
        raise ValueError(f"fallback_models must be a list: {model_id}")
    return LLMModelRoute(
        model_id=model_id,
        provider=provider,
        provider_model_id=provider_model_id,
        max_attempts=max_attempts,
        retry_backoff_sec=retry_backoff_sec,
        fallback_models=tuple(str(item) for item in fallback_models),
    )


def _node_route(node_id: str, raw: Any) -> LLMNodeRoute:
    if not isinstance(raw, dict):
        raise ValueError(f"node route must be a mapping: {node_id}")
    primary_model = str(raw.get("primary_model") or "")
    max_attempts = max(1, int(raw.get("max_attempts", 1)))
    fallback_models = raw.get("fallback_models") or ()
    if not primary_model:
        raise ValueError(f"node route must define primary_model: {node_id}")
    if not isinstance(fallback_models, (list, tuple)):
        raise ValueError(f"fallback_models must be a list: {node_id}")
    return LLMNodeRoute(
        node_id=node_id,
        primary_model=primary_model,
        max_attempts=max_attempts,
        fallback_models=tuple(str(item) for item in fallback_models),
    )


def _missing_node_models(nodes: dict[str, LLMNodeRoute], models: dict[str, LLMModelRoute]) -> list[str]:
    referenced: set[str] = set()
    for node in nodes.values():
        referenced.add(node.primary_model)
        referenced.update(node.fallback_models)
    return sorted(referenced - set(models))


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


def _llm_verbose_enabled() -> bool:
    value = os.getenv("REVIEW_LLM_VERBOSE", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _log_llm_event(event: str, **fields: object) -> None:
    record_llm_event(event, dict(fields))
    if not _llm_verbose_enabled():
        return
    # 终端 verbose 只打印结构化摘要；错误消息可能很长，完整短摘要留给 llm_calls.jsonl。
    hidden_verbose_fields = {"error_message"}
    parts = [
        f"{key}={_format_log_value(value)}"
        for key, value in fields.items()
        if key not in hidden_verbose_fields and value not in ("", None)
    ]
    print(f"[llm-router:{event}] {' '.join(parts)}")


def _format_log_value(value: object) -> str:
    text = str(value).replace("\n", " ").strip()
    return text if text else "-"


def _display_prompt(prompt_name: str | None) -> str:
    # 只打印 prompt 名和长度，不打印 prompt 正文，避免把论文全文刷到终端。
    return prompt_name or "-"


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _with_call_context(
    error: ReviewAgentError,
    route: LLMModelRoute,
    attempt: int,
    prompt_name: str | None,
) -> ReviewAgentError:
    """给底层错误补上本次调用的 prompt/model/provider，方便 diagnostics 定位。"""
    context = error.context
    enriched_context = ErrorContext(
        node=context.node,
        prompt_name=context.prompt_name or prompt_name or "",
        provider=context.provider or route.provider,
        model=context.model or route.model_id,
        attempt=context.attempt or attempt,
        elapsed_ms=context.elapsed_ms,
        details=context.details,
    )
    return error.__class__(error.message, context=enriched_context)
