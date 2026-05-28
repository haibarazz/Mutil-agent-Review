from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict


def merge_dict(left: dict[str, Any] | None, right: dict[str, Any] | None) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    if left:
        merged.update(left)
    if right:
        merged.update(right)
    return merged

# 这个是我们langgraph最核心的状态states类


class GlobalState(TypedDict, total=False):
    # ========== 输入参数 ==========
    run_id: str                   # 当前审稿运行的唯一标识符
    paper_path: str               # 用户上传的论文文件路径 (PDF/MD)
    review_mode: str              # 审稿模式: FULL_REVIEW(完整) / QUICK_REVIEW(快速)
    venue_domain: str             # 领域: CS(计算机) / IS(信息系统)
    venue_collection: str         # 期刊集合: CCFA/CCFB/CCFC/FT50/UTD24
    venue_code: str               # 具体期刊代码: AAAI/IJCAI/NeurIPS 等
    journal_name: str             # 期刊名称 (可选)
    journal_requirements_path: str # 期刊要求文档路径 (可选)

    # ========== 解析与校验 ==========
    parsed_paper: Any             # 解析后的论文对象 (ParsedPaper 类型)
    paper_content: str            # 论文纯文本内容
    parse_error: str              # 解析错误信息 (空字符串表示成功)
    content_check: dict[str, Any] # 内容检查结果 (判断是否为有效论文)
    intent: str                   # 论文意图分类: VALID_PAPER / NOT_PAPER 等
    intent_detail: str            # 意图详细说明

    # ========== 期刊与期刊要求 ==========
    venue_profile: Any             # 目标期刊的配置信息 (VenueProfile)
    journal_requirements: str     # 期刊投稿要求原文
    journal_requirements_result: dict[str, Any] # 期刊要求收集结果

    # ========== 领域分析与编辑筛选 ==========
    field_analysis: dict[str, Any] # 领域分析结果
    field_info: dict[str, Any]     # 领域详细信息
    reviewer_config: dict[str, Any] # 审稿人配置
    se_result: dict[str, Any]      # 高级编辑(SE)审查结果
    se_decision: str               # SE 决定: PASS / DESK_REJECT
    ae_result: dict[str, Any]      # 副编辑(AE)审查结果
    ae_decision: str               # AE 决定: PASS / DESK_REJECT / SEND_FOR_REVIEW

    # ========== 并行审稿聚合 ==========
    # 使用 Annotated + add 操作符，允许多个审稿人的报告并行追加
    reviewer_reports: Annotated[list[Any], add]

    # ========== 最终输出 ==========
    ae_final: dict[str, Any]       # AE 最终综合报告
    final_decision: str            # 最终决定: ACCEPT / MINOR_REVISION / MAJOR_REVISION / REJECT / DESK_REJECT
    decision_letter: str           # 最终决定的正式通知信

    # ========== 阶段输出 (用于追踪每个节点的中间结果) ==========
    # 使用 Annotated + merge_dict 操作符合并各阶段输出
    stage_outputs: Annotated[dict[str, Any], merge_dict]


# 图输入: 启动审稿流程的初始输入参数
class GraphInput(TypedDict, total=False):
    paper_path: str               # 用户上传的论文文件路径 (PDF/MD)
    review_mode: str              # 审稿模式: FULL_REVIEW / QUICK_REVIEW
    venue_domain: str             # 领域: CS / IS
    venue_collection: str         # 期刊集合: CCFA/CCFB/CCFC/FT50/UTD24
    venue_code: str               # 具体期刊代码
    journal_name: str             # 期刊名称 (可选)
    journal_requirements_path: str # 期刊要求文档路径 (可选)


# 图输出: 审稿流程结束时的最终输出
class GraphOutput(TypedDict, total=False):
    run_id: str                   # 当前审稿运行的唯一标识符
    final_decision: str           # 最终决定: ACCEPT/MINOR_REVISION/MAJOR_REVISION/REJECT/DESK_REJECT
    decision_letter: str          # 最终决定的正式通知信
    reviewer_reports: list[Any]   # 审稿人报告列表 (ReviewerReport[])
    stage_outputs: dict[str, Any] # 各阶段中间结果的字典
