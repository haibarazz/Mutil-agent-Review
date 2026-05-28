from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.core.models import ParsedPaper, ReviewMode, ReviewRequest, ReviewerReport, VenueProfile
from src.core.models import FinalDecision, ReviewFinding
from src.core.prompts import PromptRepository
from src.ports import DocumentParser, LLMClient, SearchClient


DEFAULT_JOURNAL_REQUIREMENTS = """## 通用学术期刊审稿标准

1. 原创性与创新性：论文应提出新的研究问题、新的方法或有意义的新发现。
2. 方法论严谨性：研究方法应合理、可重复，实验设计严谨。
3. 文献综述：应充分覆盖相关领域文献，清晰定位研究贡献。
4. 结果与分析：实验结果应充分支持结论，数据分析严谨。
5. 写作质量：论文应逻辑清晰、表达准确、结构完整。
6. 伦理合规：研究应符合学术伦理规范。
"""


class ReviewNodes:
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

    def content_check(self, paper: ParsedPaper) -> dict[str, Any]:
        result = self._complete_json("content_check", {"content_preview": paper.full_text[:2000]})
        is_paper = bool(result.get("is_paper", True))
        reason = str(result.get("reason", ""))
        return {
            "intent": "VALID_PAPER" if is_paper else "NOT_PAPER",
            "intent_detail": reason,
            "raw_result": result,
        }

    def journal_requirements(self, request: ReviewRequest, paper: ParsedPaper) -> dict[str, Any]:
        raw_text = ""
        source = "default"
        if request.journal_requirements_path:
            raw_text = self.parser.parse(Path(request.journal_requirements_path)).full_text
            source = "uploaded_file"
        elif request.journal_name:
            search_results = self.search.search(f"{request.journal_name} author guidelines submission requirements")
            raw_text = "\n\n".join(
                f"{item.title}\n{item.url}\n{item.snippet}" for item in search_results
            )
            source = "search" if raw_text else "default"

        if raw_text:
            prompt, user_prompt = self.prompts.render(
                "journal_req_collector",
                {"journal_name": request.journal_name or request.venue_code or "未指定", "raw_text": raw_text[:6000]},
            )
            requirements = self.llm.complete_text(
                system_prompt=prompt.system_prompt,
                user_prompt=user_prompt,
                prompt_name="journal_req_collector",
                model=prompt.model or None,
                temperature=prompt.temperature,
            )
        else:
            requirements = DEFAULT_JOURNAL_REQUIREMENTS

        return {"journal_requirements": requirements, "source": source}

    def field_analyst(self, paper: ParsedPaper, journal_requirements: str) -> dict[str, Any]:
        result = self._complete_json(
            "field_analyst",
            {"paper_content": paper.full_text, "journal_requirements": journal_requirements},
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
    ) -> dict[str, Any]:
        result = self._complete_json(
            "se_check",
            {
                "paper_content": paper.full_text,
                "journal_requirements": journal_requirements,
                "venue_profile_text": venue_profile.profile_text if venue_profile else "未提供目标期刊画像。",
                "submission_type": "Research Article",
                "field_info": field_info,
            },
        )
        decision = str(result.get("decision", "PASS"))
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
    ) -> dict[str, Any]:
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
        )
        decision = str(result.get("decision", "SEND_FOR_REVIEW"))
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
    ) -> ReviewerReport:
        related_papers = ""
        if prompt_name == "reviewer2":
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
        )
        return self._report_from_result(reviewer_key, role, result)

    def devils_advocate(
        self,
        *,
        paper: ParsedPaper,
        journal_requirements: str,
        venue_profile: VenueProfile | None,
        ae_result: dict[str, Any],
    ) -> ReviewerReport:
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
        )
        return self._report_from_result("devils_advocate", "Devil's Advocate", result)

    def ae_final(
        self,
        *,
        paper: ParsedPaper,
        journal_requirements: str,
        venue_profile: VenueProfile | None,
        ae_result: dict[str, Any],
        reviewer_reports: list[ReviewerReport],
    ) -> dict[str, Any]:
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

    def _complete_json(self, prompt_name: str, context: dict[str, Any]) -> dict[str, Any]:
        prompt, user_prompt = self.prompts.render(prompt_name, context)
        return self.llm.complete_json(
            system_prompt=prompt.system_prompt,
            user_prompt=user_prompt,
            prompt_name=prompt_name,
            model=prompt.model or None,
            temperature=prompt.temperature,
        )

    def _related_papers_text(self, query: str) -> str:
        results = self.search.search(query, limit=8)
        if not results:
            return "未搜索到相关论文。"
        lines = ["以下是通过网络搜索获取的与本论文可能相关的近期研究成果："]
        for index, item in enumerate(results, start=1):
            lines.append(f"{index}. {item.title}\n   摘要: {item.snippet}\n   链接: {item.url}")
        return "\n\n".join(lines)

    def _persona(self, reviewer_config: dict[str, Any], key: str, default: str) -> str:
        persona = reviewer_config.get(key, "")
        if isinstance(persona, str) and persona.strip():
            return persona.strip()
        if isinstance(persona, dict):
            name = persona.get("name") or persona.get("persona") or persona.get("role") or ""
            expertise = persona.get("expertise") or persona.get("focus") or ""
            return f"{name} - {expertise}".strip(" -") or default
        return default

    def _report_from_result(self, reviewer_key: str, role: str, result: dict[str, Any]) -> ReviewerReport:
        strengths = result.get("strengths", result.get("strengths_conceded", []))
        return ReviewerReport(
            reviewer_key=reviewer_key,
            role=role,
            summary=str(result.get("summary", "")),
            strengths=[str(item) for item in strengths],
            weaknesses=[self._finding(item) for item in result.get("weaknesses", [])],
            rating=int(result.get("rating", 5)),
            rating_justification=str(result.get("rating_justification", "")),
            recommendation=str(result.get("recommendation", "MAJOR_REVISION")),
            evidence_citations=[str(item) for item in result.get("evidence_citations", [])],
            strategic_advice=dict(result.get("strategic_advice", {})),
            raw_result=result,
        )

    def _finding(self, item: Any) -> ReviewFinding:
        if isinstance(item, dict):
            return ReviewFinding(
                location=str(item.get("location", "unknown")),
                issue=str(item.get("issue", item.get("weakness", ""))),
                severity=str(item.get("severity", "medium")),
            )
        text = str(item)
        location = "unknown"
        if text.startswith("[") and "]" in text:
            location, text = text[1:].split("]", 1)
            text = text.strip()
        return ReviewFinding(location=location, issue=text, severity="medium")

    def _final_decision(self, value: Any) -> FinalDecision:
        try:
            return FinalDecision(str(value))
        except ValueError:
            return FinalDecision.MAJOR_REVISION

    def _json(self, value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, indent=2)


def default_quick_review_ae_result() -> dict[str, Any]:
    return {
        "ae_decision": "SEND_FOR_REVIEW",
        "ae_assessment": "快速审稿模式跳过SE/AE筛选，直接进入外审。",
        "review_focus_points": ["重点检查论文贡献、方法严谨性、表达质量和可修复性。"],
        "paper_rubric": {},
        "ae_desk_reject_types": [],
    }
