"""桌拒输出节点 - v3.1 增加7类桌拒分类展示"""
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context

from graphs.state import DeskRejectInput, DeskRejectOutput


# 桌拒7类分类定义
DESK_REJECT_TYPE_MAP = {
    "DR-1": {"name": "选题范围不匹配", "icon": "🎯", "en": "Scope Mismatch",
             "desc": "论文主题不属于期刊关注领域，或研究范式与期刊风格不符"},
    "DR-2": {"name": "创新性不足", "icon": "💡", "en": "Insufficient Novelty",
             "desc": "研究问题陈旧、与已有工作无明显区别、增量式贡献不够"},
    "DR-3": {"name": "方法论根本缺陷", "icon": "🔬", "en": "Fundamental Methodological Flaws",
             "desc": "实验设计不合理、缺少对照组/基线对比、统计方法错误、可复现性存疑"},
    "DR-4": {"name": "内容严重不完整", "icon": "📝", "en": "Incomplete Manuscript",
             "desc": "核心章节缺失、正文过短、缺少必要的实验/参考文献"},
    "DR-5": {"name": "写作/格式严重不达标", "icon": "✍️", "en": "Poor Writing/Formatting",
             "desc": "语言质量极差影响理解、未按投稿指南格式、图表模糊不清"},
    "DR-6": {"name": "学术伦理/规范问题", "icon": "⚠️", "en": "Ethical/Compliance Issues",
             "desc": "涉嫌抄袭/重复发表、缺少伦理审批、数据造假嫌疑"},
    "DR-7": {"name": "影响力不匹配期刊定位", "icon": "🏔️", "en": "Insufficient Impact for Target Venue",
             "desc": "工作本身没问题，但对目标顶刊来说不够突出，建议投更适合的期刊"},
}


def desk_reject_output_node(
    state: DeskRejectInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> DeskRejectOutput:
    """
    title: 桌拒通知输出
    desc: 将SE或AE的桌拒决定格式化为用户可读的通知内容，包含7类桌拒分类标签
    """
    ctx = runtime.context

    # 判断是SE桌拒还是AE桌拒
    if state.ae_decision == "DESK_REJECT" and state.ae_rejection_letter:
        reject_stage = "AE责任编辑"
        rejection_letter = state.ae_rejection_letter
        assessment = state.ae_assessment
        reject_types = state.ae_desk_reject_types
    else:
        reject_stage = "SE主编"
        rejection_letter = state.se_rejection_letter
        assessment = ""
        reject_types = state.se_desk_reject_types

    concerns_text = ""
    if state.se_concerns:
        concerns_items: list[str] = []
        for i, c in enumerate(state.se_concerns, 1):
            concerns_items.append(f"  {i}. {c}")
        concerns_text = "\n".join(concerns_items)

    # 格式化桌拒类型标签
    types_text = ""
    if reject_types:
        type_items: list[str] = []
        for dr_type in reject_types:
            type_info = DESK_REJECT_TYPE_MAP.get(dr_type, None)
            if type_info is not None:
                type_items.append(
                    f"  {type_info['icon']} **{dr_type} {type_info['name']}** ({type_info['en']})\n"
                    f"     {type_info['desc']}"
                )
            else:
                type_items.append(f"  - {dr_type}")
        types_text = "\n".join(type_items)
    else:
        types_text = "  未明确分类（请联系编辑了解详细原因）"

    # 根据桌拒类型给出建议
    suggestion_text = _generate_suggestion(reject_types)

    output = f"""# 📵 稿件被桌拒 (Desk Reject)

---

## 决定信息

- **决策阶段**: {reject_stage}
- **最终决定**: Desk Reject（不送外审）

---

## 🏷️ 桌拒类型

{types_text}

---

{f'## 📝 论文概括\n\n{state.se_summary}\n\n---\n' if state.se_summary else ''}

{f'## ⚠️ 主要问题\n\n{concerns_text}\n\n---\n' if concerns_text else ''}

{f'## 📋 {reject_stage}评估意见\n\n{assessment}\n\n---\n' if assessment else ''}

## 📨 桌拒信

{rejection_letter or '经初步审查，您的稿件不适合进入外审流程。建议根据上述意见进行修改后重新投稿。'}

---

## 💡 改进建议

{suggestion_text}

---

*桌拒意味着稿件未进入外审阶段。建议根据以上反馈修改后重新投稿，或选择更合适的期刊。*
"""

    return DeskRejectOutput(
        formatted_output=output,
        final_decision="DESK_REJECT"
    )


def _generate_suggestion(reject_types: list) -> str:
    """根据桌拒类型生成针对性建议"""
    if not reject_types:
        return "建议仔细阅读桌拒信中的反馈意见，针对性地修改论文后重新投稿或选择更合适的期刊。"

    suggestions: list[str] = []

    for dr_type in reject_types:
        if dr_type == "DR-1":
            suggestions.append(
                "🎯 **选题范围不匹配**：建议仔细阅读目标期刊的 Aims & Scope，"
                "引用该刊近年相关论文，选择更匹配的期刊重新投稿。"
            )
        elif dr_type == "DR-2":
            suggestions.append(
                "💡 **创新性不足**：建议在引言中更清晰地阐明与已有工作的区别（Need a \"However, ...\" gap statement），"
                "突出研究的独特贡献和增量价值。"
            )
        elif dr_type == "DR-3":
            suggestions.append(
                "🔬 **方法论根本缺陷**：这是最严重的问题。建议重新审视实验设计，"
                "补充对照组/基线对比，修正统计方法，确保可复现性后再投稿。"
            )
        elif dr_type == "DR-4":
            suggestions.append(
                "📝 **内容严重不完整**：建议补全所有核心章节（方法、实验、讨论、参考文献），"
                "确保论文结构完整后再投稿。"
            )
        elif dr_type == "DR-5":
            suggestions.append(
                "✍️ **写作/格式不达标**：建议请母语者润色语言，严格按照目标期刊的投稿指南调整格式，"
                "确保图表清晰（≥300dpi）。"
            )
        elif dr_type == "DR-6":
            suggestions.append(
                "⚠️ **学术伦理/规范问题**：请认真核查引用规范性，补充必要的伦理审批文件，"
                "确保数据处理合规后再投稿。"
            )
        elif dr_type == "DR-7":
            suggestions.append(
                "🏔️ **影响力不匹配**：论文本身质量合格，但对当前目标期刊来说竞争力不足。"
                "建议考虑影响力稍低但领域更匹配的期刊，或进一步提升研究的创新性和实验深度。"
            )

    return "\n\n".join(suggestions)
