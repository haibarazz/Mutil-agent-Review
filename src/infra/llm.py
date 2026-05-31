from __future__ import annotations

import json
import re
from typing import Any

from src.core.errors import ErrorContext, ModelOutputParseError
from src.ports import JsonValidator


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
        validator: JsonValidator | None = None,
    ) -> dict[str, Any]:
        role = prompt_name or self._infer_role(system_prompt) or self._infer_role(user_prompt) or "reviewer"
        wants_zh = "自然语言字段必须使用中文" in user_prompt
        if role == "se_check":
            role = "se"
        if role == "content_check":
            return _apply_validator(
                {"is_paper": True, "reason": "Mock check found manuscript-like academic structure."},
                validator,
                context=ErrorContext(prompt_name=prompt_name or role, model=model or "mock"),
            )
        if role == "field_analyst":
            return _apply_validator({
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
            }, validator, context=ErrorContext(prompt_name=prompt_name or role, model=model or "mock"))
        if role == "se":
            return _apply_validator({
                "decision": "PASS",
                "summary": "Mock SE screening passes the manuscript to AE screening.",
                "strengths": ["The manuscript has recognizable academic structure."],
                "concerns": ["Provider-backed desk-screening behavior needs integration coverage."],
                "quality_score": 72,
                "desk_reject_types": [],
                "rejection_letter": "",
            }, validator, context=ErrorContext(prompt_name=prompt_name or role, model=model or "mock"))
        if role == "ae_check":
            return _apply_validator({
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
            }, validator, context=ErrorContext(prompt_name=prompt_name or role, model=model or "mock"))
        if role == "ae_final":
            decision_letter = "Mock AE final decision: major revision required before acceptance."
            checklist = ["Rerun with provider-backed LLM responses."]
            if wants_zh:
                decision_letter = "尊敬的作者：当前稿件需要大修后再考虑接收。请优先验证真实模型输出、补强证据链，并确保最终审稿报告能够稳定展示结构化意见。"
                checklist = ["使用真实 LLM 响应重新跑完整流程。"]
            return _apply_validator({
                "final_decision": "MAJOR_REVISION",
                "decision_letter": decision_letter,
                "revision_checklist": checklist,
                "consensus_disagreement": {"consensus": ["框架路径已经跑通。"] if wants_zh else ["Framework path is complete."], "disagreement": []},
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
            }, validator, context=ErrorContext(prompt_name=prompt_name or role, model=model or "mock"))
        return _apply_validator(
            self._mock_reviewer_result(role),
            validator,
            context=ErrorContext(prompt_name=prompt_name or role, model=model or "mock"),
        )

    def _mock_reviewer_result(self, role: str) -> dict[str, Any]:
        major_comments = [
            {
                "title": "Provider-backed node behavior is not yet validated",
                "comment": "The local smoke path validates graph wiring, but does not prove that real model outputs satisfy the structured review contract.",
                "evidence": "framework bootstrap",
                "severity": "major",
                "suggested_fix": "Run the same workflow with a provider-backed LLM and inspect reviewer JSON artifacts.",
            },
            {
                "title": "Evidence grounding needs stronger artifact checks",
                "comment": "The review currently relies on generated citations, so the workflow should verify that cited sections exist in parsed paper artifacts.",
                "evidence": "parsed_paper.json and reviewer_reports.json",
                "severity": "major",
                "suggested_fix": "Add an artifact-level check that each comment evidence string points to paper text or a documented missing-evidence claim.",
            },
            {
                "title": "The review schema needs downstream rendering coverage",
                "comment": "Structured major and minor comments are useful only if final reports display them consistently for authors.",
                "evidence": "final_report.md renderer path",
                "severity": "major",
                "suggested_fix": "Render major comments, minor comments, author questions, and scores in the final report.",
            },
        ]
        minor_comments = [
            {
                "title": "Reviewer confidence should be explicit",
                "comment": "The report should distinguish low-confidence criticism from high-confidence rejection reasons.",
                "evidence": "scores.confidence",
                "severity": "minor",
                "suggested_fix": "Show confidence next to rating and recommendation.",
            },
            {
                "title": "Questions for authors should be separated",
                "comment": "Questions are easier to answer in rebuttal when they are not mixed into weaknesses.",
                "evidence": "questions_for_authors",
                "severity": "minor",
                "suggested_fix": "Render a dedicated Questions for Authors section.",
            },
        ]
        weaknesses = [
            f"[{item['evidence']}] {item['title']}: {item['comment']}"
            for item in [*major_comments, *minor_comments]
        ]
        return {
            "summary": f"Mock {role} assessment generated from local framework.",
            "overall_assessment": "The manuscript can be reviewed end to end, but the structured review contract still needs provider-backed validation.",
            "strengths": [
                "The framework parsed the manuscript and preserved a review artifact path.",
                "The graph now produces enough structured fields for OpenReview-style rendering.",
            ],
            "major_comments": major_comments,
            "minor_comments": minor_comments,
            "questions_for_authors": [
                "Can the authors provide evidence that every generated critique is grounded in the manuscript text?",
                "Can the authors clarify how they would respond if real reviewers disagree on contribution versus presentation?",
            ],
            "scores": {
                "soundness": "2 fair",
                "presentation": "3 good",
                "contribution": "2 fair",
                "rating": 5,
                "confidence": 4,
                "recommendation": "borderline",
            },
            "ethics_and_limitations": "No ethics issue is simulated; this mock review is limited to framework validation.",
            "weaknesses": weaknesses,
            "rating": 5,
            "rating_justification": "The framework path works, but provider-backed review quality is not yet validated.",
            "recommendation": "MAJOR_REVISION",
            "evidence_citations": ["framework bootstrap", "final_report.md renderer path"],
            "strategic_advice": {
                "priority_fixes": ["Validate every reviewer node with provider-backed structured outputs."],
                "revision_plan": ["Keep the JSON schema stable before improving report styling."],
                "rebuttal_strategy": "Treat this mock output as architecture validation, not as a substantive paper review.",
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
        if "field" in lowered or "领域" in text:
            return "reviewer2"
        if "cross" in lowered or "跨学科" in text:
            return "reviewer3"
        if "method" in lowered or "方法" in text:
            return "reviewer1"
        if "devil" in lowered or "反方" in text:
            return "devils_advocate"
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
        validator: JsonValidator | None = None,
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
        try:
            parsed = extract_json_object(content)
        except (json.JSONDecodeError, ValueError):
            parsed = self._repair_json_response(
                invalid_content=str(content),
                model=model,
                max_tokens=max_tokens,
            )
        return _apply_validator(
            parsed,
            validator,
            context=ErrorContext(prompt_name=prompt_name or "", model=model or self.default_model),
        )

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

    def _repair_json_response(
        self,
        *,
        invalid_content: str,
        model: str | None,
        max_tokens: int | None,
    ) -> dict[str, Any]:
        # 真实模型偶尔会少逗号或包裹解释；失败时用同一路模型做一次纯 JSON 修复。
        repair_payload = self._chat_completion(
            system_prompt=(
                "You repair invalid JSON. Return only one valid JSON object. "
                "Do not add markdown, comments, or explanations."
            ),
            user_prompt=(
                "Fix this invalid JSON-like response into strict JSON. "
                "Preserve all fields and text as much as possible.\n\n"
                f"{invalid_content}"
            ),
            model=model,
            temperature=0,
            top_p=None,
            max_tokens=max_tokens,
            json_mode=True,
        )
        repaired_content = repair_payload["choices"][0]["message"]["content"]
        try:
            return extract_json_object(repaired_content)
        except (json.JSONDecodeError, ValueError) as repair_error:
            raise ModelOutputParseError(
                "LLM response JSON parse failed, and one repair attempt also failed"
            ) from repair_error


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
    parsed = _loads_json_object(cleaned)
    if not isinstance(parsed, dict):
        raise ValueError("LLM response JSON must be an object")
    return parsed


def _loads_json_object(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # LLM JSON 常见问题是少逗号/少引号；本地修复比再次调用模型更稳定、更便宜。
        from json_repair import loads as repair_json_loads

        return repair_json_loads(text)


def _apply_validator(
    value: dict[str, Any],
    validator: JsonValidator | None,
    *,
    context: ErrorContext,
) -> dict[str, Any]:
    if validator is None:
        return value
    return validator(value, context=context)
