from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


SUMMARY_SCHEMA = "review_usage_summary_v1"


def load_pricing_config(path: Path) -> dict[str, Any]:
    """加载本地价格表；价格只用于估算，不代表供应商账单。"""
    if not path.exists():
        return {"currency": "USD", "models": {}}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("LLM pricing config must be a YAML mapping")
    models = data.get("models") or {}
    if not isinstance(models, dict):
        raise ValueError("LLM pricing config models must be a mapping")
    return {"currency": str(data.get("currency") or "USD"), "models": models}


def build_usage_summary(
    run_id: str,
    events: list[dict[str, Any]],
    *,
    pricing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pricing = pricing or {"currency": "USD", "models": {}}
    done_events = [event for event in events if event.get("event") == "done"]
    start_count = sum(1 for event in events if event.get("event") == "start")
    error_events = [event for event in events if event.get("event") == "error"]
    fallback_count = sum(1 for event in events if event.get("event") == "fallback")

    summary = _empty_summary(run_id, str(pricing.get("currency") or "USD"))
    summary["total_calls"] = start_count or len(done_events) + len(error_events)
    summary["successful_calls"] = len(done_events)
    summary["error_calls"] = len(error_events)
    summary["fallback_count"] = fallback_count
    summary["retry_error_count"] = sum(1 for event in error_events if _truthy(event.get("retryable")))

    for event in done_events:
        usage = _usage_from_event(event)
        if usage is None:
            summary["missing_usage_count"] += 1
            continue

        cost, pricing_source = estimate_call_cost(event, pricing)
        if pricing_source == "":
            summary["missing_pricing_count"] += 1
        call = _call_summary(event, usage, cost, pricing_source)
        summary["calls"].append(call)
        _add_usage(summary, usage, cost, _elapsed_ms(event))
        _add_group(summary["by_provider"], str(event.get("provider") or "unknown"), usage, cost, _elapsed_ms(event))
        _add_group(
            summary["by_model"],
            str(event.get("model") or event.get("provider_model") or "unknown"),
            usage,
            cost,
            _elapsed_ms(event),
            provider=str(event.get("provider") or ""),
        )
        _add_prompt_group(
            summary["by_prompt"],
            str(event.get("prompt") or "unknown"),
            usage,
            cost,
            _elapsed_ms(event),
            model=str(event.get("model") or event.get("provider_model") or ""),
        )
        _maybe_set_slowest_call(summary, event)

    summary["known_usage"] = bool(done_events) and summary["missing_usage_count"] == 0
    summary["estimated_cost_usd"] = _money(summary["estimated_cost_usd"])
    for section in ("by_provider", "by_model", "by_prompt"):
        for item in summary[section].values():
            item["estimated_cost_usd"] = _money(item["estimated_cost_usd"])
            if "models" in item:
                item["models"] = sorted(item["models"])
    for call in summary["calls"]:
        call["estimated_cost_usd"] = _money(call["estimated_cost_usd"])
    return summary


def estimate_call_cost(event: dict[str, Any], pricing: dict[str, Any]) -> tuple[float, str]:
    usage = _usage_from_event(event)
    if usage is None:
        return 0.0, ""
    model_id = str(event.get("model") or event.get("provider_model") or "")
    models = pricing.get("models") if isinstance(pricing.get("models"), dict) else {}
    model_pricing = models.get(model_id) if isinstance(models, dict) else None
    if not isinstance(model_pricing, dict):
        return 0.0, ""
    input_price = _float_or_none(model_pricing.get("input_per_1m"))
    output_price = _float_or_none(model_pricing.get("output_per_1m"))
    if input_price is None or output_price is None:
        return 0.0, ""
    cost = (usage["input_tokens"] / 1_000_000 * input_price) + (usage["output_tokens"] / 1_000_000 * output_price)
    return cost, f"configs/llm_pricing.yaml:{model_id}"


def _empty_summary(run_id: str, currency: str) -> dict[str, Any]:
    return {
        "schema": SUMMARY_SCHEMA,
        "run_id": run_id,
        "currency": currency,
        "known_usage": False,
        "total_calls": 0,
        "successful_calls": 0,
        "error_calls": 0,
        "fallback_count": 0,
        "retry_error_count": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "estimated_cost_usd": 0.0,
        "elapsed_ms": 0,
        "by_provider": {},
        "by_model": {},
        "by_prompt": {},
        "slowest_call": {},
        "missing_usage_count": 0,
        "missing_pricing_count": 0,
        "calls": [],
    }


def _usage_from_event(event: dict[str, Any]) -> dict[str, int] | None:
    input_tokens = _int_or_none(event.get("input_tokens"))
    output_tokens = _int_or_none(event.get("output_tokens"))
    total_tokens = _int_or_none(event.get("total_tokens"))
    if input_tokens is None and output_tokens is None and total_tokens is None:
        return None
    input_tokens = input_tokens or 0
    output_tokens = output_tokens or 0
    total_tokens = total_tokens if total_tokens is not None else input_tokens + output_tokens
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


def _call_summary(
    event: dict[str, Any],
    usage: dict[str, int],
    cost: float,
    pricing_source: str,
) -> dict[str, Any]:
    return {
        "prompt": str(event.get("prompt") or ""),
        "provider": str(event.get("provider") or ""),
        "model": str(event.get("model") or ""),
        "provider_model": str(event.get("provider_model") or ""),
        "attempt": _int_or_none(event.get("attempt")),
        "elapsed_ms": _elapsed_ms(event),
        **usage,
        "estimated_cost_usd": cost,
        "pricing_source": pricing_source,
    }


def _add_usage(target: dict[str, Any], usage: dict[str, int], cost: float, elapsed_ms: int) -> None:
    target["input_tokens"] += usage["input_tokens"]
    target["output_tokens"] += usage["output_tokens"]
    target["total_tokens"] += usage["total_tokens"]
    target["estimated_cost_usd"] += cost
    target["elapsed_ms"] += elapsed_ms


def _add_group(
    groups: dict[str, dict[str, Any]],
    key: str,
    usage: dict[str, int],
    cost: float,
    elapsed_ms: int,
    *,
    provider: str = "",
) -> None:
    item = groups.setdefault(
        key,
        {
            "calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "estimated_cost_usd": 0.0,
            "elapsed_ms": 0,
        },
    )
    if provider:
        item["provider"] = provider
    item["calls"] += 1
    _add_usage(item, usage, cost, elapsed_ms)


def _add_prompt_group(
    groups: dict[str, dict[str, Any]],
    key: str,
    usage: dict[str, int],
    cost: float,
    elapsed_ms: int,
    *,
    model: str,
) -> None:
    item = groups.setdefault(
        key,
        {
            "calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "estimated_cost_usd": 0.0,
            "elapsed_ms": 0,
            "models": set(),
        },
    )
    item["calls"] += 1
    if model:
        item["models"].add(model)
    _add_usage(item, usage, cost, elapsed_ms)


def _maybe_set_slowest_call(summary: dict[str, Any], event: dict[str, Any]) -> None:
    elapsed_ms = _elapsed_ms(event)
    current_elapsed = int(summary.get("slowest_call", {}).get("elapsed_ms") or -1)
    if elapsed_ms <= current_elapsed:
        return
    summary["slowest_call"] = {
        "prompt": str(event.get("prompt") or ""),
        "provider": str(event.get("provider") or ""),
        "model": str(event.get("model") or ""),
        "provider_model": str(event.get("provider_model") or ""),
        "elapsed_ms": elapsed_ms,
    }


def _elapsed_ms(event: dict[str, Any]) -> int:
    return max(0, _int_or_none(event.get("elapsed_ms")) or 0)


def _int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _money(value: float) -> float:
    return round(float(value), 8)
