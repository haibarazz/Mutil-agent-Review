from __future__ import annotations

import json
import re
from typing import Any


class MockLLMClient:
    """Deterministic LLM adapter for local smoke tests and API-free demos."""

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
        return (
            "## 通用学术期刊审稿标准\n\n"
            "1. 原创性与问题重要性需要清晰。\n"
            "2. 方法、实验、对照和消融需要足够严谨。\n"
            "3. 写作应完整呈现研究动机、方法、结果、局限和伦理风险。\n"
            "4. 该文本由 mock LLM 生成，用于本地框架 smoke 测试。"
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
        role = self._infer_role(system_prompt) or self._infer_role(user_prompt) or "reviewer"
        if role == "content_check":
            return {"is_paper": True, "reason": "Mock check found manuscript-like academic structure."}
        if role == "field_analyst":
            return {
                "field_info": {
                    "primary_discipline": "Computer Science",
                    "secondary_discipline": "Artificial Intelligence",
                    "research_paradigm": "empirical",
                    "methodology_type": "computational experiment",
                    "target_venue_tier": "top-tier",
                    "paper_maturity": "submission_ready",
                },
                "reviewer_config": {
                    "reviewer_1": {
                        "persona": "Methodology reviewer",
                        "expertise": "experimental design and reproducibility",
                        "focus": "baselines, ablations, statistical support",
                        "review_style": "evidence-first",
                    },
                    "reviewer_2": {
                        "persona": "Field reviewer",
                        "expertise": "contribution and related work",
                        "focus": "novelty and positioning",
                        "review_style": "community-impact oriented",
                    },
                    "reviewer_3": {
                        "persona": "Cross-disciplinary reviewer",
                        "expertise": "presentation and broader impact",
                        "focus": "clarity, assumptions, and transferability",
                        "review_style": "reader-focused",
                    },
                    "devils_advocate": {
                        "persona": "Adversarial reviewer",
                        "expertise": "logical stress testing",
                        "focus": "strongest counterargument",
                        "attack_strategy": "identify unsupported central claims",
                    },
                },
            }
        if role == "se":
            return {
                "decision": "PASS",
                "summary": "Mock SE screening passes the manuscript to AE screening.",
                "strengths": ["The manuscript has recognizable academic structure."],
                "concerns": ["Provider-backed desk-screening behavior needs integration coverage."],
                "quality_score": 72,
                "desk_reject_types": [],
                "rejection_letter": "",
            }
        if role == "ae_check":
            return {
                "decision": "SEND_FOR_REVIEW",
                "ae_assessment": "Mock AE assessment sends the manuscript for external review.",
                "review_focus_points": [
                    "Check whether the claimed contribution is novel.",
                    "Check whether baselines and ablations support the main claims.",
                ],
                "paper_rubric": {
                    "dimensions": [
                        {
                            "name": "Contribution clarity",
                            "description": "Whether claims are specific and evidence-backed.",
                            "high_score_criteria": "Clear claim with strong evidence.",
                            "low_score_criteria": "Vague or unsupported claim.",
                        }
                    ]
                },
                "desk_reject_types": [],
                "rejection_letter": "",
            }
        if role == "ae_final":
            return {
                "final_decision": "MAJOR_REVISION",
                "decision_letter": "Mock AE final decision: major revision required before acceptance.",
                "revision_checklist": ["Rerun with provider-backed LLM responses."],
                "consensus_disagreement": {"consensus": ["Framework path is complete."], "disagreement": []},
                "rr_traceability_matrix": [
                    {
                        "concern": "Provider-backed reasoning not validated",
                        "source": "mock reviewer reports",
                        "required_action": "Run the same graph with a real LLM adapter.",
                        "salvageability": "可修",
                    }
                ],
                "revision_roadmap": {
                    "must_fix": ["Validate every node with a provider-backed LLM response."],
                    "should_fix": ["Add provider-backed integration tests."],
                    "nice_to_fix": ["Add frontend event stream."],
                    "rebuttal_strategy": "Explain that the current run validates architecture, not review quality.",
                },
            }
        return {
            "summary": f"Mock {role} assessment generated from local framework.",
            "strengths": ["The framework parsed the manuscript and preserved a review artifact path."],
            "weaknesses": [
                {
                    "location": "framework bootstrap",
                    "issue": "Provider-backed reasoning still needs validation against real model responses.",
                    "severity": "medium",
                }
            ],
            "rating": 5,
            "strategic_advice": {
                "action_guide": "Use provider-backed runs to validate prompt behavior after the local graph stays stable."
            },
        }

    def _infer_role(self, text: str) -> str:
        lowered = text.lower()
        if "is_paper" in lowered or "内容审查" in text:
            return "content_check"
        if "field analyst" in lowered or "领域分析" in text:
            return "field_analyst"
        if "最终编辑决定" in text or "ae终审" in lowered or "r&r" in lowered:
            return "ae_final"
        if "associate editor" in lowered or "责任编辑" in text:
            return "ae_check"
        if "devil" in lowered or "反方" in text:
            return "devils_advocate"
        if "field" in lowered or "领域" in text:
            return "reviewer2"
        if "cross" in lowered or "跨学科" in text:
            return "reviewer3"
        if "method" in lowered or "方法" in text:
            return "reviewer1"
        if "senior editor" in lowered or "se" in lowered:
            return "se"
        if "associate editor" in lowered or "ae" in lowered:
            return "ae"
        return ""


class OpenAICompatibleLLMClient:
    """Minimal OpenAI-compatible chat completions adapter."""

    def __init__(self, *, base_url: str, api_key: str, default_model: str, timeout_sec: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.default_model = default_model
        self.timeout_sec = timeout_sec

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
        payload = self._chat_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            json_mode=False,
        )
        return str(payload["choices"][0]["message"]["content"]).strip()

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
        payload = self._chat_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            json_mode=True,
        )
        content = payload["choices"][0]["message"]["content"]
        return extract_json_object(content)

    def _chat_completion(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str | None,
        temperature: float,
        top_p: float | None,
        max_tokens: int | None,
        json_mode: bool,
    ) -> dict[str, Any]:
        try:
            import httpx
        except ImportError as exc:
            raise RuntimeError("httpx is required for openai_compatible LLM calls") from exc

        request_json: dict[str, Any] = {
            "model": model or self.default_model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if top_p is not None:
            request_json["top_p"] = top_p
        if max_tokens is not None:
            request_json["max_tokens"] = max_tokens
        if json_mode:
            request_json["response_format"] = {"type": "json_object"}
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=request_json,
            timeout=self.timeout_sec,
        )
        response.raise_for_status()
        return response.json()


def extract_json_object(text: str) -> dict[str, Any]:
    cleaned = re.sub(r"<think[^>]*>.*?</think\s*>", "", text, flags=re.DOTALL).strip()
    if "```json" in cleaned:
        cleaned = cleaned.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in cleaned:
        cleaned = cleaned.split("```", 1)[1].split("```", 1)[0].strip()
    first = cleaned.find("{")
    last = cleaned.rfind("}")
    if first != -1 and last != -1 and last > first:
        cleaned = cleaned[first : last + 1]
    parsed = json.loads(cleaned)
    if not isinstance(parsed, dict):
        raise ValueError("LLM response JSON must be an object")
    return parsed
