from __future__ import annotations

from typing import Any

from src.core.models import FinalDecision, ParsedPaper, ReviewerReport, VenueProfile, to_jsonable


class ReviewArtifactRenderer:
    """把 graph 的结构化结果渲染成用户最终看到的审稿报告。"""

    def render_markdown(
        self,
        *,
        parsed_paper: ParsedPaper | None,
        venue_profile: VenueProfile | None,
        final_decision: str | FinalDecision,
        decision_letter: str,
        reviewer_reports: list[ReviewerReport],
        ae_final: dict[str, Any],
        stage_outputs: dict[str, Any],
        output_language: str = "zh",
    ) -> str:
        decision = self._decision_value(final_decision)
        title = self._paper_title(parsed_paper)
        language = self._normalize_language(output_language)
        if decision == FinalDecision.INVALID_SUBMISSION.value:
            return self._render_invalid_submission_report(
                title=title,
                decision_letter=decision_letter,
                stage_outputs=stage_outputs,
                language=language,
            )
        if decision == FinalDecision.DESK_REJECT.value:
            return self._render_desk_reject_report(
                title=title,
                venue_profile=venue_profile,
                decision_letter=decision_letter,
                stage_outputs=stage_outputs,
                language=language,
            )
        return self._render_review_report(
            title=title,
            venue_profile=venue_profile,
            decision=decision,
            decision_letter=decision_letter,
            reviewer_reports=reviewer_reports,
            ae_final=ae_final,
            stage_outputs=stage_outputs,
            language=language,
        )

    def _render_invalid_submission_report(
        self,
        *,
        title: str,
        decision_letter: str,
        stage_outputs: dict[str, Any],
        language: str,
    ) -> str:
        labels = self._labels(language)
        invalid_output = dict(stage_outputs.get("invalid_file") or {})
        message = decision_letter or str(invalid_output.get("message") or "").strip()
        if not message:
            message = labels["invalid_submission_default"]

        lines = [
            f"# {labels['invalid_submission_report']}: {title}",
            "",
            f"{labels['final_decision']}: **{FinalDecision.INVALID_SUBMISSION.value}**",
            "",
            f"## {labels['submission_status']}",
            "",
            message,
            "",
            f"## {labels['next_steps']}",
            "",
            f"- {labels['invalid_step_upload_manuscript']}",
            f"- {labels['invalid_step_check_structure']}",
            f"- {labels['invalid_step_retry']}",
            "",
        ]
        return self._join(lines)

    def _render_review_report(
        self,
        *,
        title: str,
        venue_profile: VenueProfile | None,
        decision: str,
        decision_letter: str,
        reviewer_reports: list[ReviewerReport],
        ae_final: dict[str, Any],
        stage_outputs: dict[str, Any],
        language: str,
    ) -> str:
        labels = self._labels(language)
        lines = [
            f"# {labels['review_report']}: {title}",
            "",
            f"{labels['final_decision']}: **{decision}**",
        ]
        lines.extend(self._venue_lines(venue_profile, language))
        lines.append("")

        if decision_letter:
            lines.extend([f"## {labels['decision_letter']}", "", self._decision_letter(decision_letter, language), ""])

        if ae_final:
            lines.extend(self._ae_final_lines(ae_final, language))

        if reviewer_reports:
            lines.extend([f"## {labels['reviewer_reports']}", ""])
            for report in self._sorted_reports(reviewer_reports):
                lines.extend(self._reviewer_lines(report, language))
        elif stage_outputs:
            lines.extend(self._stage_snapshot_lines(stage_outputs, language))

        return self._join(lines)

    def _render_desk_reject_report(
        self,
        *,
        title: str,
        venue_profile: VenueProfile | None,
        decision_letter: str,
        stage_outputs: dict[str, Any],
        language: str,
    ) -> str:
        labels = self._labels(language)
        se_result = dict(stage_outputs.get("se_check") or {})
        ae_result = dict(stage_outputs.get("ae_check") or {})
        concerns = self._as_list(se_result.get("se_concerns")) or self._as_list(ae_result.get("review_focus_points"))
        desk_reject_types = self._as_list(se_result.get("se_desk_reject_types")) or self._as_list(
            ae_result.get("ae_desk_reject_types")
        )
        assessment = (
            str(se_result.get("se_summary") or "").strip()
            or str(ae_result.get("ae_assessment") or "").strip()
            or labels["editorial_screening_stopped"]
        )

        lines = [
            f"# {labels['desk_reject_report']}: {title}",
            "",
            f"{labels['final_decision']}: **{FinalDecision.DESK_REJECT.value}**",
        ]
        lines.extend(self._venue_lines(venue_profile, language))
        lines.extend(
            [
                "",
                f"## {labels['decision_letter']}",
                "",
                self._decision_letter(decision_letter, language) if decision_letter else labels["desk_rejected"],
                "",
                f"## {labels['editorial_assessment']}",
                "",
                assessment,
                "",
            ]
        )

        if desk_reject_types:
            lines.extend([f"## {labels['desk_reject_reasons']}", ""])
            lines.extend(f"- {item}" for item in desk_reject_types)
            lines.append("")

        if concerns:
            lines.extend([f"## {labels['main_concerns']}", ""])
            lines.extend(f"- {item}" for item in concerns)
            lines.append("")

        lines.extend(
            [
                f"## {labels['revision_advice']}",
                "",
                f"- {labels['desk_advice_venue']}",
                f"- {labels['desk_advice_contribution']}",
                f"- {labels['desk_advice_evidence']}",
                "",
            ]
        )
        return self._join(lines)

    def _ae_final_lines(self, ae_final: dict[str, Any], language: str) -> list[str]:
        labels = self._labels(language)
        lines = [f"## {labels['ae_final']}", ""]

        revision_checklist = self._as_list(ae_final.get("revision_checklist"))
        if revision_checklist:
            lines.extend([f"### {labels['revision_checklist']}", ""])
            lines.extend(f"- {item}" for item in revision_checklist)
            lines.append("")

        consensus = self._dict(ae_final.get("consensus_disagreement"))
        if consensus:
            lines.extend(self._consensus_lines(consensus, language))

        traceability = self._as_items(ae_final.get("rr_traceability_matrix"))
        if traceability:
            lines.extend(self._traceability_lines(traceability, language))

        roadmap = self._dict(ae_final.get("revision_roadmap"))
        if roadmap:
            lines.extend(self._roadmap_lines(roadmap, language))

        return lines

    def _reviewer_lines(self, report: ReviewerReport, language: str) -> list[str]:
        labels = self._labels(language)
        lines = [
            f"### {self._reviewer_title(report, language)}",
            "",
            f"#### {labels['part1']}",
            "",
            f"##### {labels['summary']}",
            "",
            report.summary or labels["missing_summary"],
            "",
        ]

        if report.overall_assessment:
            lines.extend([f"##### {labels['overall_assessment']}", "", report.overall_assessment, ""])

        lines.extend([f"##### {labels['scores']}", "", *self._scores_lines(report, language), "", f"##### {labels['strengths']}"])
        lines.extend(f"- {item}" for item in report.strengths or [labels["missing_strengths"]])

        if report.major_comments:
            lines.extend(["", f"##### {labels['major_comments']}", ""])
            lines.extend(self._comment_lines(report.major_comments, language))
        elif report.weaknesses:
            # 兼容旧 prompt：如果还没有结构化 comments，就退回旧 weaknesses。
            lines.extend(["", f"##### {labels['major_comments']}", ""])
            lines.extend(f"{index}. [{item.location}] {item.issue}" for index, item in enumerate(report.weaknesses, 1))

        if report.minor_comments:
            lines.extend(["", f"##### {labels['minor_comments']}", ""])
            lines.extend(self._comment_lines(report.minor_comments, language))

        if report.questions_for_authors:
            lines.extend(["", f"##### {labels['questions_for_authors']}", ""])
            lines.extend(f"{index}. {item}" for index, item in enumerate(report.questions_for_authors, 1))

        if report.ethics_and_limitations:
            lines.extend(["", f"##### {labels['ethics_and_limitations']}", "", report.ethics_and_limitations])

        format_issues = self._review_format_issues(report)
        if format_issues:
            lines.extend(["", f"##### {labels['format_check']}", ""])
            lines.extend(f"- {item}" for item in format_issues)

        lines.extend(["", f"#### {labels['part2']}", ""])
        if report.strategic_advice:
            lines.extend(self._strategic_advice_lines(report.strategic_advice, language))
        else:
            lines.append(labels["missing_advice"])
        lines.append("")
        return lines

    def _comment_lines(self, comments: list[Any], language: str) -> list[str]:
        labels = self._labels(language)
        lines: list[str] = []
        for index, item in enumerate(comments, start=1):
            lines.extend(
                [
                    f"{index}. **{item.title}**",
                    f"   - {labels['comment']}: {item.comment}",
                    f"   - {labels['evidence']}: {item.evidence}",
                    f"   - {labels['severity']}: {item.severity}",
                    f"   - {labels['suggested_fix']}: {item.suggested_fix}",
                ]
            )
        return lines

    def _scores_lines(self, report: ReviewerReport, language: str) -> list[str]:
        labels = self._labels(language)
        scores = report.scores or {}
        return [
            f"- {labels['soundness']}: {scores.get('soundness', labels['not_provided'])}",
            f"- {labels['presentation']}: {scores.get('presentation', labels['not_provided'])}",
            f"- {labels['contribution']}: {scores.get('contribution', labels['not_provided'])}",
            f"- {labels['rating']}: {scores.get('rating', report.rating)}/10",
            f"- {labels['confidence']}: {scores.get('confidence', labels['not_provided'])}",
            f"- {labels['recommendation']}: {scores.get('recommendation', report.recommendation)}",
        ]

    def _review_format_issues(self, report: ReviewerReport) -> list[str]:
        issues: list[str] = []
        if len(report.major_comments) < 3:
            issues.append(f"major_comments has {len(report.major_comments)} items; expected at least 3.")
        if len(report.minor_comments) < 2:
            issues.append(f"minor_comments has {len(report.minor_comments)} items; expected at least 2.")
        if len(report.questions_for_authors) < 2:
            issues.append(
                f"questions_for_authors has {len(report.questions_for_authors)} items; expected at least 2."
            )
        if len(report.major_comments) + len(report.minor_comments) < 5:
            total = len(report.major_comments) + len(report.minor_comments)
            issues.append(f"structured comments total is {total}; expected at least 5.")
        return issues

    def _stage_snapshot_lines(self, stage_outputs: dict[str, Any], language: str) -> list[str]:
        labels = self._labels(language)
        lines = [f"## {labels['stage_outputs']}", ""]
        lines.extend(f"- {name}" for name in sorted(stage_outputs))
        lines.append("")
        return lines

    def _venue_lines(self, venue_profile: VenueProfile | None, language: str) -> list[str]:
        if not venue_profile:
            return []
        return [f"{self._labels(language)['target_venue']}: **{venue_profile.code}**"]

    def _paper_title(self, parsed_paper: ParsedPaper | None) -> str:
        if parsed_paper and parsed_paper.title:
            return parsed_paper.title
        return "Review Report"

    def _decision_value(self, final_decision: str | FinalDecision) -> str:
        if isinstance(final_decision, FinalDecision):
            return final_decision.value
        return str(final_decision or FinalDecision.REJECT.value)

    def _as_list(self, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value if str(item).strip()]
        if isinstance(value, tuple):
            return [str(item) for item in value if str(item).strip()]
        text = str(value).strip()
        return [text] if text else []

    def _as_items(self, value: Any) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        return [value]

    def _dict(self, value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    def _consensus_lines(self, data: dict[str, Any], language: str) -> list[str]:
        labels = self._labels(language)
        lines = [f"### {labels['consensus_disagreement']}", ""]

        consensus = self._as_items(data.get("consensus"))
        if consensus:
            rows = []
            for item in consensus:
                if isinstance(item, dict):
                    rows.append([
                        self._stringify(item.get("issue")),
                        self._stringify(item.get("reviewers")),
                        self._stringify(item.get("summary")),
                    ])
                else:
                    rows.append([self._stringify(item), "", ""])
            lines.extend([f"#### {labels['consensus']}", ""])
            lines.extend(self._table([labels["issue"], labels["reviewers"], labels["summary"]], rows))
            lines.append("")

        disagreement = self._as_items(data.get("disagreement"))
        if disagreement:
            rows = []
            for item in disagreement:
                if isinstance(item, dict):
                    rows.append([
                        self._stringify(item.get("issue")),
                        self._stringify(item.get("positions")),
                        self._stringify(item.get("ae_arbitration")),
                    ])
                else:
                    rows.append([self._stringify(item), "", ""])
            lines.extend([f"#### {labels['disagreement']}", ""])
            lines.extend(self._table([labels["issue"], labels["positions"], labels["ae_arbitration"]], rows))
            lines.append("")

        if "da_critical_flagged" in data:
            lines.extend([f"#### {labels['da_critical']}", ""])
            lines.append(f"- {labels['flagged']}: {self._stringify(data.get('da_critical_flagged'))}")
            if data.get("da_critical_impact"):
                lines.append(f"- {labels['impact']}: {self._stringify(data.get('da_critical_impact'))}")
            lines.append("")

        return lines

    def _traceability_lines(self, rows_data: list[Any], language: str) -> list[str]:
        labels = self._labels(language)
        rows = []
        for item in rows_data:
            if isinstance(item, dict):
                rows.append([
                    self._stringify(item.get("issue_id")),
                    self._stringify(item.get("source")),
                    self._stringify(item.get("category")),
                    self._stringify(item.get("description")),
                    self._stringify(item.get("salvageability")),
                    self._stringify(item.get("author_must_address")),
                    self._stringify(item.get("verification_criteria")),
                ])
            else:
                rows.append([self._stringify(item), "", "", "", "", "", ""])
        lines = [f"### {labels['rr_traceability']}", ""]
        lines.extend(
            self._table(
                [
                    labels["issue_id"],
                    labels["source"],
                    labels["category"],
                    labels["description"],
                    labels["salvageability"],
                    labels["must_address"],
                    labels["verification_criteria"],
                ],
                rows,
            )
        )
        lines.append("")
        return lines

    def _roadmap_lines(self, roadmap: dict[str, Any], language: str) -> list[str]:
        labels = self._labels(language)
        lines = [f"### {labels['revision_roadmap']}", ""]
        sections = [
            ("must_fix", labels["must_fix"]),
            ("should_fix", labels["should_fix"]),
            ("nice_to_fix", labels["nice_to_fix"]),
        ]
        for key, title in sections:
            items = self._as_list(roadmap.get(key))
            if items:
                lines.extend([f"#### {title}", ""])
                lines.extend(f"- {item}" for item in items)
                lines.append("")
        strategy = str(roadmap.get("rebuttal_strategy") or "").strip()
        if strategy:
            lines.extend([f"#### {labels['rebuttal_strategy']}", "", strategy, ""])
        return lines

    def _strategic_advice_lines(self, advice: dict[str, Any], language: str) -> list[str]:
        labels = self._labels(language)
        titles = {
            "problem_roots": labels["problem_roots"],
            "revision_plan": labels["revision_plan"],
            "salvageability": labels["salvageability"],
            "action_guide": labels["action_guide"],
            "rebuttal_strategy": labels["rebuttal_strategy"],
            "attack_surface": labels["attack_surface"],
            "rebuttal_weaknesses": labels["rebuttal_weaknesses"],
            "priority_fixes": labels["priority_fixes"],
        }
        lines: list[str] = []
        rendered = set()
        for key, title in titles.items():
            value = advice.get(key)
            if value:
                rendered.add(key)
                lines.extend([f"##### {title}", ""])
                lines.extend(self._generic_value_lines(value))
                lines.append("")
        for key, value in advice.items():
            if key in rendered or not value:
                continue
            lines.extend([f"##### {key.replace('_', ' ').title()}", ""])
            lines.extend(self._generic_value_lines(value))
            lines.append("")
        return lines or [labels["missing_advice"]]

    def _generic_value_lines(self, value: Any) -> list[str]:
        if isinstance(value, str):
            return [value]
        if isinstance(value, dict):
            rows = [[str(key), self._stringify(item)] for key, item in value.items()]
            return self._table(["Field", "Value"], rows)
        if isinstance(value, (list, tuple)):
            return [f"- {self._stringify(item)}" for item in value]
        return [self._stringify(value)]

    def _stringify(self, value: Any) -> str:
        value = to_jsonable(value)
        if value is None:
            return ""
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, list):
            return "; ".join(self._stringify(item) for item in value)
        if isinstance(value, dict):
            return "; ".join(f"{key}: {self._stringify(item)}" for key, item in value.items())
        return str(value)

    def _table(self, headers: list[str], rows: list[list[str]]) -> list[str]:
        safe_headers = [self._table_cell(item) for item in headers]
        lines = [
            "| " + " | ".join(safe_headers) + " |",
            "| " + " | ".join("---" for _ in safe_headers) + " |",
        ]
        for row in rows:
            padded = [*row, *([""] * (len(headers) - len(row)))]
            lines.append("| " + " | ".join(self._table_cell(item) for item in padded[: len(headers)]) + " |")
        return lines

    def _table_cell(self, value: Any) -> str:
        return self._stringify(value).replace("\n", "<br>").replace("|", "\\|")

    def _normalize_language(self, value: str) -> str:
        return "en" if str(value).lower() in {"en", "english"} else "zh"

    def _labels(self, language: str) -> dict[str, str]:
        if language == "en":
            return {
                "review_report": "Review Report",
                "desk_reject_report": "Desk Reject Report",
                "final_decision": "Final decision",
                "target_venue": "Target venue",
                "decision_letter": "Decision Letter",
                "ae_final": "AE Final Synthesis",
                "reviewer_reports": "Reviewer Reports",
                "revision_checklist": "Revision Checklist",
                "consensus_disagreement": "Consensus and Disagreement",
                "consensus": "Consensus Issues",
                "disagreement": "Disagreement Issues",
                "issue": "Issue",
                "reviewers": "Reviewers",
                "summary": "Summary",
                "positions": "Positions",
                "ae_arbitration": "AE Arbitration",
                "da_critical": "Devil's Advocate Critical Flag",
                "flagged": "Flagged",
                "impact": "Impact",
                "rr_traceability": "R&R Traceability Matrix",
                "issue_id": "Issue ID",
                "source": "Source",
                "category": "Category",
                "description": "Description",
                "salvageability": "Salvageability",
                "must_address": "Must address",
                "verification_criteria": "Verification criteria",
                "revision_roadmap": "Revision Roadmap",
                "must_fix": "Must Fix",
                "should_fix": "Should Fix",
                "nice_to_fix": "Nice to Fix",
                "rebuttal_strategy": "Rebuttal Strategy",
                "part1": "Part 1: Review Report",
                "part2": "Part 2: Strategic Advice",
                "overall_assessment": "Overall Assessment",
                "scores": "Scores",
                "strengths": "Strengths",
                "major_comments": "Major Comments",
                "minor_comments": "Minor Comments",
                "questions_for_authors": "Questions for Authors",
                "ethics_and_limitations": "Ethics and Limitations",
                "format_check": "Format Check",
                "comment": "Comment",
                "evidence": "Evidence",
                "severity": "Severity",
                "suggested_fix": "Suggested fix",
                "soundness": "Soundness",
                "presentation": "Presentation",
                "contribution": "Contribution",
                "rating": "Rating",
                "confidence": "Confidence",
                "recommendation": "Recommendation",
                "not_provided": "not provided",
                "missing_summary": "No summary was returned.",
                "missing_strengths": "No strengths were returned.",
                "missing_advice": "No strategic advice was returned.",
                "stage_outputs": "Stage Outputs",
                "editorial_assessment": "Editorial Assessment",
                "desk_reject_reasons": "Desk Reject Reasons",
                "main_concerns": "Main Concerns",
                "revision_advice": "Revision Advice",
                "invalid_submission_report": "Invalid Submission Report",
                "submission_status": "Submission Status",
                "next_steps": "Next Steps",
                "invalid_submission_default": "The uploaded content is not an academic manuscript.",
                "invalid_step_upload_manuscript": "Upload an academic manuscript instead of a general document.",
                "invalid_step_check_structure": "Check that the file contains manuscript structure such as title, abstract, introduction, methods, experiments, conclusion, or references.",
                "invalid_step_retry": "Retry the review after replacing the input file.",
                "editorial_screening_stopped": "The manuscript was stopped during editorial screening.",
                "desk_rejected": "The manuscript was desk rejected.",
                "desk_advice_venue": "Re-check the target venue fit before resubmission.",
                "desk_advice_contribution": "Make the core contribution explicit enough for an editor to identify quickly.",
                "desk_advice_evidence": "Strengthen the evidence package before sending the paper to external review.",
                "problem_roots": "Problem Roots",
                "revision_plan": "Revision Plan",
                "action_guide": "Action Guide",
                "attack_surface": "Attack Surface",
                "rebuttal_weaknesses": "Rebuttal Weaknesses",
                "priority_fixes": "Priority Fixes",
            }
        return {
            "review_report": "审稿报告",
            "desk_reject_report": "桌拒报告",
            "final_decision": "最终决定",
            "target_venue": "目标 Venue",
            "decision_letter": "决定信",
            "ae_final": "AE 终审综合意见",
            "reviewer_reports": "审稿人意见",
            "revision_checklist": "修改清单",
            "consensus_disagreement": "共识与分歧",
            "consensus": "共识问题",
            "disagreement": "分歧问题",
            "issue": "问题",
            "reviewers": "审稿人",
            "summary": "摘要",
            "positions": "立场",
            "ae_arbitration": "AE 仲裁",
            "da_critical": "反方辩护重点",
            "flagged": "是否标记",
            "impact": "影响",
            "rr_traceability": "R&R 可追踪矩阵",
            "issue_id": "问题编号",
            "source": "来源",
            "category": "类别",
            "description": "描述",
            "salvageability": "可修复性",
            "must_address": "必须回应",
            "verification_criteria": "验证标准",
            "revision_roadmap": "返修路线图",
            "must_fix": "必须修改",
            "should_fix": "建议修改",
            "nice_to_fix": "可选优化",
            "rebuttal_strategy": "Rebuttal 策略",
            "part1": "第一部分：审稿意见",
            "part2": "第二部分：策略建议",
            "overall_assessment": "总体评价",
            "scores": "评分",
            "strengths": "优点",
            "major_comments": "主要意见",
            "minor_comments": "次要意见",
            "questions_for_authors": "给作者的问题",
            "ethics_and_limitations": "伦理与限制",
            "format_check": "格式检查",
            "comment": "意见",
            "evidence": "证据",
            "severity": "严重程度",
            "suggested_fix": "建议修改",
            "soundness": "可靠性",
            "presentation": "表达",
            "contribution": "贡献",
            "rating": "总评分",
            "confidence": "置信度",
            "recommendation": "建议",
            "not_provided": "未提供",
            "missing_summary": "未返回摘要。",
            "missing_strengths": "未返回优点。",
            "missing_advice": "未返回策略性建议。",
            "stage_outputs": "阶段输出",
            "editorial_assessment": "编辑初筛意见",
            "desk_reject_reasons": "桌拒原因",
            "main_concerns": "主要问题",
            "revision_advice": "修改建议",
            "invalid_submission_report": "上传内容不是学术论文",
            "submission_status": "提交状态",
            "next_steps": "下一步",
            "invalid_submission_default": "上传内容不是学术论文。",
            "invalid_step_upload_manuscript": "请上传学术论文或论文手稿，而不是普通文档。",
            "invalid_step_check_structure": "请确认文件包含标题、摘要、引言、方法、实验、结论或参考文献等论文结构。",
            "invalid_step_retry": "替换输入文件后重新发起审稿。",
            "editorial_screening_stopped": "稿件在编辑初筛阶段被停止。",
            "desk_rejected": "稿件已被桌拒。",
            "desk_advice_venue": "重新检查目标 venue 是否匹配。",
            "desk_advice_contribution": "把核心贡献写到编辑能快速识别的程度。",
            "desk_advice_evidence": "在再次投稿前补强证据链。",
            "problem_roots": "问题根源",
            "revision_plan": "修改计划",
            "action_guide": "行动指南",
            "attack_surface": "攻击面",
            "rebuttal_weaknesses": "Rebuttal 薄弱点",
            "priority_fixes": "优先修改项",
        }

    def _reviewer_title(self, report: ReviewerReport, language: str) -> str:
        if language == "en":
            return report.role
        titles = {
            "reviewer1": "审稿人 1：方法与实验",
            "reviewer2": "审稿人 2：领域贡献与理论定位",
            "reviewer3": "审稿人 3：跨学科与表达",
            "devils_advocate": "反方辩护人",
        }
        return titles.get(report.reviewer_key, report.role)

    def _decision_letter(self, text: str, language: str) -> str:
        normalized = text.strip()
        if language != "zh":
            return normalized
        for prefix in ("Dear Author(s),", "Dear Author(s):", "Dear Authors,", "Dear Authors:"):
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix) :].lstrip()
                break
        for prefix in ("尊敬的作者：", "尊敬的作者:", "作者您好：", "作者您好:"):
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix) :].lstrip()
                break
        return f"尊敬的作者：\n\n{normalized}" if normalized else "尊敬的作者："

    def _sorted_reports(self, reports: list[ReviewerReport]) -> list[ReviewerReport]:
        order = {
            "reviewer1": 0,
            "reviewer2": 1,
            "reviewer3": 2,
            "devils_advocate": 3,
        }
        return sorted(reports, key=lambda report: order.get(report.reviewer_key, 99))

    def _join(self, lines: list[str]) -> str:
        return "\n".join(lines).strip() + "\n"
