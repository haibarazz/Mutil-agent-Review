from __future__ import annotations

import json
import re
from typing import Any

from src.core.errors import ErrorContext, ModelOutputValidationError
from src.core.models import ParsedPaper, ReviewComment, ReviewerReport, VenueProfile
from src.core.models import FinalDecision, ReviewFinding
from src.core.output_schemas import (
    validate_ae_decision_output,
    validate_ae_final_output,
    validate_ae_report_output,
    validate_reviewer_output,
    validate_single_reviewer_output,
)
from src.core.prompts import PromptRepository
from src.ports import DocumentParser, JsonValidator, LLMClient, SearchClient


class ReviewNodes:
    """集中放置各个 LangGraph 节点背后的业务逻辑。

    graph.py 里的 node 函数很薄，只负责从 GlobalState 取数据、调用这里、
    再把结果写回 GlobalState。这样节点编排和具体业务实现不会混在一起。
    """

    def __init__(
        self,
        *,
        llm: LLMClient,
        search: SearchClient,
        parser: DocumentParser,
        prompts: PromptRepository,
    ) -> None:
        self.llm = llm
        self.search = search
        self.parser = parser
        self.prompts = prompts

    def content_check(self, paper: ParsedPaper, *, output_language: str = "zh") -> dict[str, Any]:
        """内容审查：判断解析出来的文本是否像一篇学术论文。"""
        non_paper_reason = self._obvious_non_paper_reason(paper.full_text, output_language=output_language)
        if non_paper_reason:
            return {
                "intent": "NOT_PAPER",
                "intent_detail": non_paper_reason,
                "raw_result": {"is_paper": False, "reason": non_paper_reason, "source": "deterministic_precheck"},
            }

        result = self._complete_json(
            "content_check",
            {"content_preview": paper.full_text[:2000]},
            output_language=output_language,
        )
        is_paper = result.get("is_paper")
        if not isinstance(is_paper, bool):
            raise ModelOutputValidationError(
                "content_check output field `is_paper` must be a boolean.",
                context=ErrorContext(
                    prompt_name="content_check",
                    details={
                        "invalid_field": "is_paper",
                        "actual_type": type(is_paper).__name__,
                        "actual_value": str(is_paper),
                    },
                ),
            )
        reason = str(result.get("reason", ""))
        return {
            "intent": "VALID_PAPER" if is_paper else "NOT_PAPER",
            "intent_detail": reason,
            "raw_result": result,
        }

    def _obvious_non_paper_reason(self, text: str, *, output_language: str = "zh") -> str:
        """只拦截非常明显的非论文；边界样本仍交给 LLM 判断，避免误杀正常论文。"""
        normalized = " ".join(str(text or "").split())
        if not normalized:
            return "上传内容为空，无法识别为论文。" if output_language != "en" else "The uploaded content is empty."

        lower = normalized.lower()
        has_academic_structure = bool(
            re.search(
                r"(?im)^\s*(?:#+\s*)?(?:abstract|introduction|methods?|experiments?|conclusion|references|摘要|引言|方法|实验|结论|参考文献)\b",
                text,
            )
        )
        junk_markers = [
            "菜谱",
            "配料",
            "食材",
            "做法",
            "番茄",
            "牛肉",
            "面条",
            "日记",
            "心情",
            "旅游攻略",
            "行程安排",
            "合同",
            "甲方",
            "乙方",
        ]
        junk_marker_count = sum(1 for marker in junk_markers if marker in lower)
        if not has_academic_structure and junk_marker_count >= 2:
            return (
                "上传内容更像菜谱、日记、合同或其他普通文档，不是学术论文。"
                if output_language != "en"
                else "The uploaded content looks like a recipe, diary, contract, or general document rather than an academic manuscript."
            )

        if not has_academic_structure and len(normalized) < 120:
            return (
                "上传内容过短，且没有摘要、引言、方法、实验或参考文献等论文特征。"
                if output_language != "en"
                else "The uploaded content is too short and lacks manuscript markers such as abstract, introduction, methods, experiments, or references."
            )

        return ""

    def field_analyst(
        self,
        paper: ParsedPaper,
        journal_requirements: str,
        *,
        output_language: str = "zh",
    ) -> dict[str, Any]:
        """领域分析：识别论文领域，并为后续审稿人生成分工配置。"""
        result = self._complete_json(
            "field_analyst",
            {"paper_content": paper.full_text, "journal_requirements": journal_requirements},
            output_language=output_language,
        )
        return {
            "field_info": result.get("field_info", {}),
            "reviewer_config": result.get("reviewer_config", {}),
            "raw_result": result,
        }

    def se_check(
        self,
        *,
        paper: ParsedPaper,
        journal_requirements: str,
        venue_profile: VenueProfile | None,
        field_info: dict[str, Any],
        output_language: str = "zh",
    ) -> dict[str, Any]:
        """SE 初筛：从主编视角判断论文是否应该直接桌拒。"""
        result = self._complete_json(
            "se_check",
            {
                "paper_content": paper.full_text,
                "journal_requirements": journal_requirements,
                "venue_profile_text": venue_profile.profile_text if venue_profile else "未提供目标期刊画像。",
                "submission_type": "Research Article",
                "field_info": field_info,
            },
            output_language=output_language,
        )
        decision = str(result.get("decision", "PASS"))
        # 这里把 LLM 的自由输出收敛成 graph.py 能稳定路由的两个枚举值。
        return {
            "se_decision": "DESK_REJECT" if decision == "DESK_REJECT" else "PASS",
            "se_summary": result.get("summary", ""),
            "se_concerns": result.get("concerns", []),
            "se_rejection_letter": result.get("rejection_letter", ""),
            "se_quality_score": int(result.get("quality_score", 50)),
            "se_desk_reject_types": result.get("desk_reject_types", []),
            "raw_result": result,
        }

    def ae_check(
        self,
        *,
        paper: ParsedPaper,
        journal_requirements: str,
        venue_profile: VenueProfile | None,
        se_result: dict[str, Any],
        field_info: dict[str, Any],
        reviewer_config: dict[str, Any],
        output_language: str = "zh",
    ) -> dict[str, Any]:
        """AE 筛选：决定是否送外审，并产出外审关注点和论文 rubric。"""
        result = self._complete_json(
            "ae_check",
            {
                "paper_content": paper.full_text,
                "journal_requirements": journal_requirements,
                "venue_profile_text": venue_profile.profile_text if venue_profile else "未提供目标期刊画像。",
                "se_summary": se_result.get("se_summary", ""),
                "se_concerns": se_result.get("se_concerns", []),
                "se_quality_score": se_result.get("se_quality_score", 0),
                "field_info": field_info,
                "reviewer_config": reviewer_config,
            },
            output_language=output_language,
        )
        decision = str(result.get("decision", "SEND_FOR_REVIEW"))
        # 这里同样把 AE 决策收敛为 graph.py 的稳定路由值。
        return {
            "ae_decision": "DESK_REJECT" if decision == "DESK_REJECT" else "SEND_FOR_REVIEW",
            "ae_assessment": result.get("ae_assessment", ""),
            "review_focus_points": result.get("review_focus_points", []),
            "ae_rejection_letter": result.get("rejection_letter", ""),
            "paper_rubric": result.get("paper_rubric", {}),
            "ae_desk_reject_types": result.get("desk_reject_types", []),
            "raw_result": result,
        }

    def reviewer(
        self,
        *,
        prompt_name: str,
        reviewer_key: str,
        role: str,
        legacy_reviewer_key: str,
        paper: ParsedPaper,
        journal_requirements: str,
        venue_profile: VenueProfile | None,
        reviewer_config: dict[str, Any],
        ae_result: dict[str, Any],
        output_language: str = "zh",
    ) -> ReviewerReport:
        """普通审稿人：Reviewer1/2/3 共用这一套调用逻辑，只换 prompt 和角色。"""
        related_papers = ""
        if prompt_name == "reviewer2":
            # Reviewer2 负责领域贡献，因此额外拿相关论文搜索结果作为参考。
            related_papers = self._related_papers_text(paper.title)

        result = self._complete_json(
            prompt_name,
            {
                "paper_content": paper.full_text,
                "journal_requirements": journal_requirements,
                "venue_profile_text": venue_profile.profile_text if venue_profile else "未提供目标期刊画像。",
                "ae_assessment": ae_result.get("ae_assessment", ""),
                "review_focus_points": ae_result.get("review_focus_points", []),
                "paper_rubric": ae_result.get("paper_rubric", {}),
                "reviewer_config": reviewer_config,
                "reviewer_key": legacy_reviewer_key,
                "reviewer_persona": self._persona(reviewer_config, legacy_reviewer_key, role),
                "related_papers": related_papers,
            },
            output_language=output_language,
        )
        return self._report_from_result(reviewer_key, role, result)

    def devils_advocate(
        self,
        *,
        paper: ParsedPaper,
        journal_requirements: str,
        venue_profile: VenueProfile | None,
        ae_result: dict[str, Any],
        output_language: str = "zh",
    ) -> ReviewerReport:
        """反方辩护人：专门从最强反对意见出发，挑战论文核心主张。"""
        result = self._complete_json(
            "devils_advocate",
            {
                "paper_content": paper.full_text,
                "journal_requirements": journal_requirements,
                "venue_profile_text": venue_profile.profile_text if venue_profile else "未提供目标期刊画像。",
                "ae_assessment": ae_result.get("ae_assessment", ""),
                "review_focus_points": ae_result.get("review_focus_points", []),
                "paper_rubric": ae_result.get("paper_rubric", {}),
            },
            output_language=output_language,
        )
        return self._report_from_result("devils_advocate", "Devil's Advocate", result)

    def single_reviewer(
        self,
        *,
        paper: ParsedPaper,
        journal_requirements: str,
        venue_profile: VenueProfile | None,
        field_info: dict[str, Any],
        output_language: str = "zh",
    ) -> dict[str, Any]:
        """单 Agent 综合审稿：一个审稿人直接给出完整意见和最终建议。"""
        result = self._complete_json(
            "single_reviewer",
            {
                "paper_content": paper.full_text,
                "journal_requirements": journal_requirements,
                "venue_profile_text": venue_profile.profile_text if venue_profile else "未提供目标期刊画像。",
                "field_info": field_info,
            },
            output_language=output_language,
        )
        report = self._report_from_result("single_reviewer", "Solo Reviewer", result)
        return {
            "report": report,
            "final_decision": self._final_decision(result.get("final_decision", "MAJOR_REVISION")).value,
            "decision_letter": str(result.get("decision_letter") or result.get("overall_assessment") or report.summary),
            "raw_result": result,
        }

    def ae_final(
        self,
        *,
        paper: ParsedPaper,
        journal_requirements: str,
        venue_profile: VenueProfile | None,
        ae_result: dict[str, Any],
        reviewer_reports: list[ReviewerReport],
        output_language: str = "zh",
    ) -> dict[str, Any]:
        """AE 终审：汇总三位审稿人和反方辩护人，生成最终编辑决定。"""
        # 转成按 reviewer_key 索引，方便 prompt 模板明确引用每一路审稿结果。
        report_by_key = {report.reviewer_key: report.raw_result for report in reviewer_reports}
        result = self._complete_json(
            "ae_final",
            {
                "paper_content": paper.full_text,
                "journal_requirements": journal_requirements,
                "venue_profile_text": venue_profile.profile_text if venue_profile else "未提供目标期刊画像。",
                "ae_assessment": ae_result.get("ae_assessment", ""),
                "review1_result": self._json(report_by_key.get("reviewer1", {})),
                "review2_result": self._json(report_by_key.get("reviewer2", {})),
                "review3_result": self._json(report_by_key.get("reviewer3", {})),
                "da_result": self._json(report_by_key.get("devils_advocate", {})),
                "paper_rubric": self._json(ae_result.get("paper_rubric", {})),
            },
            output_language=output_language,
        )
        return {
            "final_decision": self._final_decision(result.get("final_decision", "MAJOR_REVISION")).value,
            "decision_letter": result.get("decision_letter", ""),
            "revision_checklist": result.get("revision_checklist", []),
            "consensus_disagreement": result.get("consensus_disagreement", {}),
            "rr_traceability_matrix": result.get("rr_traceability_matrix", []),
            "revision_roadmap": result.get("revision_roadmap", {}),
            "raw_result": result,
        }

    def ae_decision(
        self,
        *,
        paper: ParsedPaper,
        journal_requirements: str,
        venue_profile: VenueProfile | None,
        ae_result: dict[str, Any],
        reviewer_reports: list[ReviewerReport],
        output_language: str = "zh",
    ) -> dict[str, Any]:
        """AE 裁决：只冻结最终决定和仲裁理由，不生成作者报告。"""
        result = self._complete_json(
            "ae_decision",
            self._ae_review_context(
                paper=paper,
                journal_requirements=journal_requirements,
                venue_profile=venue_profile,
                ae_result=ae_result,
                reviewer_reports=reviewer_reports,
            ),
            output_language=output_language,
        )
        return {
            "final_decision": self._final_decision(result.get("final_decision", "MAJOR_REVISION")).value,
            "decision_rationale": result.get("decision_rationale", ""),
            "consensus_disagreement": result.get("consensus_disagreement", {}),
            "critical_issues": result.get("critical_issues", []),
            "raw_result": result,
        }

    def ae_report(
        self,
        *,
        paper: ParsedPaper,
        journal_requirements: str,
        venue_profile: VenueProfile | None,
        ae_result: dict[str, Any],
        ae_decision: dict[str, Any],
        reviewer_reports: list[ReviewerReport],
        output_language: str = "zh",
    ) -> dict[str, Any]:
        """AE 报告：基于已冻结裁决整理给作者的决定信和返修路线。"""
        context = self._ae_review_context(
            paper=paper,
            journal_requirements=journal_requirements,
            venue_profile=venue_profile,
            ae_result=ae_result,
            reviewer_reports=reviewer_reports,
        )
        context.update(
            {
                "final_decision": ae_decision.get("final_decision", "MAJOR_REVISION"),
                "decision_rationale": ae_decision.get("decision_rationale", ""),
                "consensus_disagreement": self._json(ae_decision.get("consensus_disagreement", {})),
                "critical_issues": self._json(ae_decision.get("critical_issues", [])),
            }
        )
        result = self._complete_json("ae_report", context, output_language=output_language)
        return {
            "decision_letter": result.get("decision_letter", ""),
            "revision_checklist": result.get("revision_checklist", []),
            "rr_traceability_matrix": result.get("rr_traceability_matrix", []),
            "revision_roadmap": result.get("revision_roadmap", {}),
            "raw_result": result,
        }

    def _complete_json(
        self,
        prompt_name: str,
        context: dict[str, Any],
        *,
        output_language: str = "zh",
    ) -> dict[str, Any]:
        """统一的 JSON 型 LLM 调用入口：渲染 prompt，再交给 LLMRouter/Mock。"""
        context = dict(context)
        context["output_language"] = self._normalize_language(output_language)
        context["language_instruction"] = self._language_instruction(context["output_language"])
        prompt, user_prompt = self.prompts.render(prompt_name, context)
        user_prompt = f"{user_prompt}\n\n【输出语言要求】\n{context['language_instruction']}"
        return self.llm.complete_json(
            system_prompt=prompt.system_prompt,
            user_prompt=user_prompt,
            prompt_name=prompt_name,
            model=prompt.model or None,
            temperature=prompt.temperature,
            validator=self._validator_for_prompt(prompt_name),
        )

    def _validator_for_prompt(self, prompt_name: str) -> JsonValidator | None:
        if prompt_name == "single_reviewer":
            return validate_single_reviewer_output
        if prompt_name in {"reviewer1", "reviewer2", "reviewer3", "devils_advocate"}:
            return validate_reviewer_output
        if prompt_name == "ae_decision":
            return validate_ae_decision_output
        if prompt_name == "ae_report":
            return validate_ae_report_output
        if prompt_name == "ae_final":
            return validate_ae_final_output
        return None

    def _ae_review_context(
        self,
        *,
        paper: ParsedPaper,
        journal_requirements: str,
        venue_profile: VenueProfile | None,
        ae_result: dict[str, Any],
        reviewer_reports: list[ReviewerReport],
    ) -> dict[str, Any]:
        """整理 AE 终审相关 prompt 共享上下文，避免两个新节点各自拼字段。"""
        report_by_key = {report.reviewer_key: report.raw_result for report in reviewer_reports}
        return {
            "paper_content": paper.full_text,
            "journal_requirements": journal_requirements,
            "venue_profile_text": venue_profile.profile_text if venue_profile else "未提供目标期刊画像。",
            "ae_assessment": ae_result.get("ae_assessment", ""),
            "review1_result": self._json(report_by_key.get("reviewer1", {})),
            "review2_result": self._json(report_by_key.get("reviewer2", {})),
            "review3_result": self._json(report_by_key.get("reviewer3", {})),
            "da_result": self._json(report_by_key.get("devils_advocate", {})),
            "paper_rubric": self._json(ae_result.get("paper_rubric", {})),
        }

    def _normalize_language(self, value: str) -> str:
        return "en" if str(value).lower() in {"en", "english"} else "zh"

    def _language_instruction(self, output_language: str) -> str:
        if output_language == "en":
            return (
                "Use English for all natural-language values in the JSON. "
                "Keep paper titles, method names, model names, venue names, metrics, formulas, and citations in their original form. "
                "If any previous instruction conflicts with this language requirement, follow this language requirement."
            )
        return (
            "JSON 中所有自然语言字段必须使用中文。"
            "论文标题、方法名、模型名、venue 名称、指标名、公式和引用可以保留原文。"
            "如果前文提示词与本语言要求冲突，以本语言要求为准。"
        )

    def _related_papers_text(self, query: str) -> str:
        """把搜索结果压成 prompt 可读文本；当前 search 可能还是 NullSearchClient。"""
        results = self.search.search(query, limit=8)
        if not results:
            return "未搜索到相关论文。"
        lines = ["以下是通过网络搜索获取的与本论文可能相关的近期研究成果："]
        for index, item in enumerate(results, start=1):
            lines.append(f"{index}. {item.title}\n   摘要: {item.snippet}\n   链接: {item.url}")
        return "\n\n".join(lines)

    def _persona(self, reviewer_config: dict[str, Any], key: str, default: str) -> str:
        """从 field_analyst 的动态配置里提取审稿人人设。"""
        persona = reviewer_config.get(key, "")
        if isinstance(persona, str) and persona.strip():
            return persona.strip()
        if isinstance(persona, dict):
            name = persona.get("name") or persona.get("persona") or persona.get("role") or ""
            expertise = persona.get("expertise") or persona.get("focus") or ""
            return f"{name} - {expertise}".strip(" -") or default
        return default

    def _report_from_result(self, reviewer_key: str, role: str, result: dict[str, Any]) -> ReviewerReport:
        """把不同审稿 prompt 返回的 JSON 统一转换成 ReviewerReport。"""
        strengths = result.get("strengths", result.get("strengths_conceded", []))
        scores = self._dict(result.get("scores"))
        major_comments = [self._comment(item, default_severity="major") for item in self._as_list(result.get("major_comments"))]
        minor_comments = [self._comment(item, default_severity="minor") for item in self._as_list(result.get("minor_comments"))]
        weaknesses = result.get("weaknesses") or [*major_comments, *minor_comments]
        return ReviewerReport(
            reviewer_key=reviewer_key,
            role=role,
            summary=str(result.get("summary", "")),
            strengths=[str(item) for item in strengths],
            weaknesses=[self._finding(item) for item in self._as_list(weaknesses)],
            rating=self._int(result.get("rating", scores.get("rating", 5)), default=5),
            overall_assessment=str(result.get("overall_assessment", "")),
            major_comments=major_comments,
            minor_comments=minor_comments,
            questions_for_authors=[str(item) for item in self._as_list(result.get("questions_for_authors"))],
            scores=scores,
            ethics_and_limitations=str(result.get("ethics_and_limitations", "")),
            rating_justification=str(result.get("rating_justification", "")),
            recommendation=str(result.get("recommendation", scores.get("recommendation", "MAJOR_REVISION"))),
            evidence_citations=[str(item) for item in self._as_list(result.get("evidence_citations"))],
            strategic_advice=self._dict(result.get("strategic_advice")),
            raw_result=result,
        )

    def _comment(self, item: Any, *, default_severity: str) -> ReviewComment:
        """把 prompt 的结构化 comment 收敛成统一对象，兼容字符串 fallback。"""
        if isinstance(item, ReviewComment):
            return item
        if isinstance(item, dict):
            return ReviewComment(
                title=str(item.get("title", "Untitled comment")),
                comment=str(item.get("comment", item.get("issue", ""))),
                evidence=str(item.get("evidence", item.get("location", "missing evidence"))),
                severity=str(item.get("severity", default_severity)),
                suggested_fix=str(item.get("suggested_fix", item.get("fix", ""))),
            )
        text = str(item)
        return ReviewComment(
            title=text[:80] or "Untitled comment",
            comment=text,
            evidence="missing evidence",
            severity=default_severity,
            suggested_fix="请根据该问题补充具体修改方案。",
        )

    def _finding(self, item: Any) -> ReviewFinding:
        """把 weakness 条目统一成 ReviewFinding，兼容 dict 和字符串两种格式。"""
        if isinstance(item, ReviewComment):
            return ReviewFinding(
                location=item.evidence or "unknown",
                issue=f"{item.title}: {item.comment}".strip(": "),
                severity=item.severity or "medium",
            )
        if isinstance(item, dict):
            return ReviewFinding(
                location=str(item.get("location", item.get("evidence", "unknown"))),
                issue=str(item.get("issue", item.get("weakness", item.get("comment", "")))),
                severity=str(item.get("severity", "medium")),
            )
        text = str(item)
        location = "unknown"
        if text.startswith("[") and "]" in text:
            location, text = text[1:].split("]", 1)
            text = text.strip()
        return ReviewFinding(location=location, issue=text, severity="medium")

    def _final_decision(self, value: Any) -> FinalDecision:
        """把 LLM 输出的最终决策收敛到系统支持的 FinalDecision 枚举。"""
        try:
            return FinalDecision(str(value))
        except ValueError:
            return FinalDecision.MAJOR_REVISION

    def _json(self, value: Any) -> str:
        """把结构化对象转成可读 JSON 字符串，方便塞进下游 prompt。"""
        return json.dumps(value, ensure_ascii=False, indent=2)

    def _as_list(self, value: Any) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        return [value]

    def _dict(self, value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    def _int(self, value: Any, *, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default


def default_quick_review_ae_result() -> dict[str, Any]:
    """快速审稿没有真实 AE 筛选，所以给外审阶段一个默认 AE 上下文。"""
    return {
        "ae_decision": "SEND_FOR_REVIEW",
        "ae_assessment": "快速审稿模式跳过SE/AE筛选，直接进入外审。",
        "review_focus_points": ["重点检查论文贡献、方法严谨性、表达质量和可修复性。"],
        "paper_rubric": {},
        "ae_desk_reject_types": [],
    }
