"""论文审稿系统状态定义 - v3.2 简化入口：文件校验+审稿模式选择"""
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from utils.file.file import File
from graphs.venue_codes import CCFA_CODES, UTD_FT50_CODES


# ===== 全局状态 =====
class GlobalState(BaseModel):
    """全局状态定义"""
    # 入口字段
    paper_file: Optional[File] = Field(default=None, description="上传的论文文件(只支持PDF/Word/Tex)")
    review_mode: str = Field(default="FULL_REVIEW", description="审稿模式: FULL_REVIEW(完整审稿) 或 QUICK_REVIEW(快速审稿)")
    journal_name: str = Field(default="", description="目标期刊名称(如Nature/ICML/ACL)")
    venue_code: Optional[str] = Field(default=None, description="预设期刊/会议代码")
    venue_profile_text: str = Field(default="", description="期刊/会议画像文本(注入SE/AE/审稿人提示词)")
    journal_requirements_file: Optional[File] = Field(default=None, description="用户上传的期刊要求文档")
    submission_type: str = Field(default="Research Article", description="投稿类型")

    # 文件校验结果
    intent: str = Field(default="", description="校验结果: VALID_PAPER(合法论文) 或 INVALID_FILE(非论文文件)")
    intent_detail: str = Field(default="", description="校验详情说明")

    # 论文解析
    paper_content: str = Field(default="", description="论文全文内容(解析后)")
    parse_error: str = Field(default="", description="文档解析错误信息(空表示成功)")

    # 期刊要求
    journal_requirements: str = Field(default="", description="结构化的期刊投稿要求")

    # 领域分析结果 (ARS Phase 0)
    field_info: Dict[str, Any] = Field(default={}, description="论文领域分析结果")
    reviewer_config: Dict[str, Any] = Field(default={}, description="动态审稿人配置卡")

    # SE初审结果 (反谦逊评分 + 桌拒分类)
    se_decision: str = Field(default="", description="SE决定: PASS 或 DESK_REJECT")
    se_summary: str = Field(default="", description="SE对论文的简要概括")
    se_concerns: List[str] = Field(default=[], description="SE关注的问题列表")
    se_rejection_letter: str = Field(default="", description="SE桌拒信")
    se_quality_score: int = Field(default=0, description="SE评估的总体质量分(0-100)")
    se_desk_reject_types: List[str] = Field(default=[], description="SE桌拒类型列表(如DR-1/DR-2等，PASS时为空)")

    # AE筛选结果 (论文专属评分标准 + 桌拒分类)
    ae_decision: str = Field(default="", description="AE决定: SEND_FOR_REVIEW 或 DESK_REJECT")
    ae_assessment: str = Field(default="", description="AE学术评估意见")
    review_focus_points: List[str] = Field(default=[], description="AE给审稿人的关注点")
    ae_rejection_letter: str = Field(default="", description="AE桌拒信")
    paper_rubric: Dict[str, Any] = Field(default={}, description="论文专属评分标准(ReviewGrounder)")
    ae_desk_reject_types: List[str] = Field(default=[], description="AE桌拒类型列表(如DR-1/DR-2等，通过时为空)")

    # 审稿人意见 (0-100评分 + 引用具体段落)
    review1_result: Dict[str, Any] = Field(default={}, description="审稿人1的评审结果(方法论)")
    review2_result: Dict[str, Any] = Field(default={}, description="审稿人2的评审结果(理论)")
    review3_result: Dict[str, Any] = Field(default={}, description="审稿人3的评审结果(写作)")

    # Devil's Advocate (ARS)
    da_result: Dict[str, Any] = Field(default={}, description="反方辩护人评审结果")

    # 最终决定 (共识分歧 + R&R矩阵 + 改稿路线图)
    final_decision: str = Field(default="", description="最终决定: ACCEPT/MINOR_REVISION/MAJOR_REVISION/REJECT")
    decision_letter: str = Field(default="", description="最终决定信")
    revision_checklist: List[str] = Field(default=[], description="修改要求清单")
    consensus_disagreement: Dict[str, Any] = Field(default={}, description="审稿人共识与分歧分析")
    rr_traceability_matrix: List[Dict[str, Any]] = Field(default=[], description="R&R返修追溯矩阵")
    revision_roadmap: Dict[str, Any] = Field(default={}, description="改稿路线图(must_fix/should_fix/nice_to_fix/rebuttal_strategy)")

    # 格式化输出
    formatted_output: str = Field(default="", description="格式化的可读输出内容")


# ===== 图的输入输出 =====
class GraphInput(BaseModel):
    """📄 多智能体论文审稿系统 — 请上传论文并选择审稿配置"""
    paper_file: Optional[File] = Field(
        default=None,
        description="📄 上传论文手稿（支持 PDF / Word / LaTeX）"
    )
    review_mode: str = Field(
        default="FULL_REVIEW",
        description="🔄 审稿模式：FULL_REVIEW=完整审稿（含SE+AE初审+3审稿人+DA+AE终审）| QUICK_REVIEW=快速审稿（跳过SE/AE，仅3审稿人+DA+AE终审）",
        json_schema_extra={"enum": ["FULL_REVIEW", "QUICK_REVIEW"]}
    )
    venue_category: str = Field(
        default="",
        description="🏫 期刊/会议领域分类（选择后请在venue_code中选择具体期刊）：空=不选 | CS_CCFA=计算机CCF-A（94个）| IS_UTD=信息系统UTD24 | IS_FT50=商学FT50",
        json_schema_extra={"enum": ["", "CS_CCFA", "IS_UTD", "IS_FT50"]}
    )
    venue_code: str = Field(
        default="",
        description="🎯 预设期刊/会议代码（下拉选择，如ACL/CVPR/MISQ等）。若未找到目标期刊，请在journal_name中手动输入",
        json_schema_extra={"enum": [""] + CCFA_CODES + UTD_FT50_CODES}
    )
    journal_name: str = Field(
        default="",
        description="✏️ 手动输入目标期刊名称（当venue_code中无目标期刊时使用，如 Nature / Science / ICML 等）"
    )
    journal_requirements_file: Optional[File] = Field(
        default=None,
        description="📎 可选：上传期刊投稿要求文档（PDF/Word），系统将自动提取要求"
    )


class GraphOutput(BaseModel):
    """📋 审稿结果输出"""
    formatted_output: str = Field(default="", description="📋 格式化的审稿报告（完整可读版）")
    intent: str = Field(default="", description="🔍 内容校验结果：VALID_PAPER / INVALID_FILE")
    final_decision: str = Field(default="", description="⚖️ 最终审稿决定：ACCEPT / MINOR_REVISION / MAJOR_REVISION / REJECT / DESK_REJECT")
    decision_letter: str = Field(default="", description="📨 完整决定信（含修改建议/拒稿理由）")
    se_summary: str = Field(default="", description="📝 SE对论文的概括")
    se_quality_score: int = Field(default=0, description="📊 SE质量评分(0-100, 反谦逊评分)")
    review1_result: Dict[str, Any] = Field(default={}, description="🔬 审稿人1意见（方法论专家, Part1+Part2格式）")
    review2_result: Dict[str, Any] = Field(default={}, description="🧪 审稿人2意见（领域专家, Part1+Part2格式）")
    review3_result: Dict[str, Any] = Field(default={}, description="📐 审稿人3意见（跨学科专家, Part1+Part2格式）")
    da_result: Dict[str, Any] = Field(default={}, description="😈 反方辩护人意见（Part1+Part2格式）")
    consensus_disagreement: Dict[str, Any] = Field(default={}, description="🤝 审稿人共识与分歧分析")
    rr_traceability_matrix: List[Dict[str, Any]] = Field(default=[], description="R&R返修追溯矩阵")
    revision_checklist: List[str] = Field(default=[], description="修改要求清单")
    revision_roadmap: Dict[str, Any] = Field(default={}, description="改稿路线图")


# ===== 内容审查节点 (v3.2 LLM判断是否为学术论文) =====
class ContentCheckInput(BaseModel):
    """内容审查节点输入"""
    paper_content: str = Field(default="", description="解析后的文件内容")


class ContentCheckOutput(BaseModel):
    """内容审查节点输出"""
    intent: str = Field(..., description="审查结果: VALID_PAPER(学术论文) 或 NOT_PAPER(非论文内容)")
    intent_detail: str = Field(default="", description="审查详情说明")


class ContentCheckDecisionInput(BaseModel):
    """内容审查条件判断输入"""
    intent: str = Field(..., description="审查结果")


# ===== 非论文内容提示节点 =====
class InvalidFileInput(BaseModel):
    """非论文文件提示节点输入"""
    intent_detail: str = Field(default="", description="审查详情说明")


class InvalidFileOutput(BaseModel):
    """非论文文件提示节点输出"""
    formatted_output: str = Field(..., description="提示用户上传论文手稿的内容")


# ===== 期刊要求收集节点 =====
class JournalReqCollectorInput(BaseModel):
    """期刊要求收集节点输入"""
    journal_name: str = Field(default="", description="期刊名称")
    venue_code: Optional[str] = Field(default=None, description="预设期刊/会议代码")
    journal_requirements_file: Optional[File] = Field(default=None, description="用户上传的期刊要求文档")
    paper_content: str = Field(default="", description="论文全文(用于推断期刊方向)")


class JournalReqCollectorOutput(BaseModel):
    """期刊要求收集节点输出"""
    journal_requirements: str = Field(..., description="结构化的期刊投稿要求文本")
    venue_profile_text: str = Field(default="", description="期刊/会议画像文本")


# ===== 文档解析节点 =====
class DocParseInput(BaseModel):
    """文档解析节点输入"""
    paper_file: Optional[File] = Field(default=None, description="上传的论文文件")


class DocParseOutput(BaseModel):
    """文档解析节点输出"""
    paper_content: str = Field(default="", description="解析后的论文全文文本")
    parse_error: str = Field(default="", description="解析错误信息(空=成功)")


# ===== 解析结果条件判断 =====
class ParseCheckInput(BaseModel):
    """解析结果条件判断输入"""
    parse_error: str = Field(..., description="解析错误信息")


# ===== 领域分析节点 (ARS Phase 0) =====
class FieldAnalystInput(BaseModel):
    """领域分析节点输入"""
    paper_content: str = Field(..., description="论文全文")
    journal_requirements: str = Field(..., description="期刊要求")


class FieldAnalystOutput(BaseModel):
    """领域分析节点输出"""
    field_info: Dict[str, Any] = Field(..., description="论文领域分析(学科/方法/成熟度等)")
    reviewer_config: Dict[str, Any] = Field(..., description="动态审稿人配置卡(身份/专长/关注点)")


# ===== 审稿模式路由判断 =====
class ReviewModeDecisionInput(BaseModel):
    """审稿模式路由判断输入"""
    review_mode: str = Field(default="FULL_REVIEW", description="审稿模式: FULL_REVIEW 或 QUICK_REVIEW")


# ===== SE主编初审节点 (反谦逊评分) =====
class SECheckInput(BaseModel):
    """SE主编初审节点输入"""
    paper_content: str = Field(..., description="论文全文")
    journal_requirements: str = Field(..., description="期刊要求")
    venue_profile_text: str = Field(default="", description="期刊/会议画像文本")
    submission_type: str = Field(default="Research Article", description="投稿类型")
    field_info: Dict[str, Any] = Field(default={}, description="领域分析结果")


class SECheckOutput(BaseModel):
    """SE主编初审节点输出"""
    se_decision: str = Field(..., description="决定: PASS 或 DESK_REJECT")
    se_summary: str = Field(..., description="对论文的简要概括")
    se_concerns: List[str] = Field(default=[], description="主要问题列表")
    se_rejection_letter: str = Field(default="", description="桌拒信")
    se_quality_score: int = Field(default=0, description="总体质量分(0-100, 反谦逊评分)")
    se_desk_reject_types: List[str] = Field(default=[], description="桌拒类型列表(DR-1~DR-7，PASS时为空)")


# ===== SE决策条件判断 =====
class SEDecisionInput(BaseModel):
    """SE决策条件判断输入"""
    se_decision: str = Field(..., description="SE决定")


# ===== AE责任编辑筛选节点 (论文专属评分标准) =====
class AECheckInput(BaseModel):
    """AE责任编辑筛选节点输入"""
    paper_content: str = Field(..., description="论文全文")
    journal_requirements: str = Field(..., description="期刊要求")
    venue_profile_text: str = Field(default="", description="期刊/会议画像文本")
    se_summary: str = Field(..., description="SE对论文的概括")
    se_concerns: List[str] = Field(default=[], description="SE关注的问题")
    se_quality_score: int = Field(default=0, description="SE质量评分(0-100)")
    field_info: Dict[str, Any] = Field(default={}, description="领域分析结果")
    reviewer_config: Dict[str, Any] = Field(default={}, description="审稿人配置卡")


class AECheckOutput(BaseModel):
    """AE责任编辑筛选节点输出"""
    ae_decision: str = Field(..., description="决定: SEND_FOR_REVIEW 或 DESK_REJECT")
    ae_assessment: str = Field(..., description="AE的学术评估意见")
    review_focus_points: List[str] = Field(default=[], description="给审稿人的重点关注问题")
    ae_rejection_letter: str = Field(default="", description="桌拒信")
    paper_rubric: Dict[str, Any] = Field(default={}, description="论文专属评分标准")
    ae_desk_reject_types: List[str] = Field(default=[], description="桌拒类型列表(DR-1~DR-7，通过时为空)")


# ===== AE决策条件判断 =====
class AEDecisionInput(BaseModel):
    """AE决策条件判断输入"""
    ae_decision: str = Field(..., description="AE决定")


# ===== 审稿分发节点 (解决并行汇聚验证) =====
class ReviewDispatchInput(BaseModel):
    """审稿分发节点输入"""
    paper_content: str = Field(default="", description="论文全文")
    journal_requirements: str = Field(default="", description="期刊要求")
    ae_assessment: str = Field(default="", description="AE评估")
    review_focus_points: List[str] = Field(default=[], description="AE关注点")
    paper_rubric: Dict[str, Any] = Field(default={}, description="评分标准")
    reviewer_config: Dict[str, Any] = Field(default={}, description="审稿人配置")


class ReviewDispatchOutput(BaseModel):
    """审稿分发节点输出"""
    paper_content: str = Field(default="", description="论文全文(透传)")
    journal_requirements: str = Field(default="", description="期刊要求(透传)")
    ae_assessment: str = Field(default="", description="AE评估(透传)")
    review_focus_points: List[str] = Field(default=[], description="AE关注点(透传)")
    paper_rubric: Dict[str, Any] = Field(default={}, description="评分标准(透传)")
    reviewer_config: Dict[str, Any] = Field(default={}, description="审稿人配置(透传)")


# ===== 审稿人节点 (0-100评分 + 引用段落 + 非重叠视角) =====
class ReviewerInput(BaseModel):
    """审稿人节点输入"""
    paper_content: str = Field(..., description="论文全文")
    journal_requirements: str = Field(..., description="期刊要求")
    venue_profile_text: str = Field(default="", description="期刊/会议画像文本")
    ae_assessment: str = Field(..., description="AE的学术评估")
    review_focus_points: List[str] = Field(default=[], description="AE关注的重点问题")
    paper_rubric: Dict[str, Any] = Field(default={}, description="论文专属评分标准")
    reviewer_config: Dict[str, Any] = Field(default={}, description="动态审稿人配置卡(含各审稿人身份)")
    reviewer_key: str = Field(default="", description="当前审稿人在reviewer_config中的key")


class Reviewer1Output(BaseModel):
    """审稿人1节点输出"""
    review1_result: Dict[str, Any] = Field(..., description="审稿人1完整意见(方法论)")


class Reviewer2Output(BaseModel):
    """审稿人2节点输出"""
    review2_result: Dict[str, Any] = Field(..., description="审稿人2完整意见(理论)")


class Reviewer3Output(BaseModel):
    """审稿人3节点输出"""
    review3_result: Dict[str, Any] = Field(..., description="审稿人3完整意见(写作)")


# ===== Devil's Advocate节点 (ARS) =====
class DAInput(BaseModel):
    """反方辩护人节点输入"""
    paper_content: str = Field(..., description="论文全文")
    journal_requirements: str = Field(..., description="期刊要求")
    venue_profile_text: str = Field(default="", description="期刊/会议画像文本")
    ae_assessment: str = Field(..., description="AE的学术评估")
    review_focus_points: List[str] = Field(default=[], description="AE关注的重点问题")
    paper_rubric: Dict[str, Any] = Field(default={}, description="论文专属评分标准")


class DAOutput(BaseModel):
    """反方辩护人节点输出"""
    da_result: Dict[str, Any] = Field(..., description="反方辩护人完整意见")
    confirmation_bias: str = Field(default="", description="确认偏误检测")
    logic_chain_issues: List[str] = Field(default=[], description="逻辑链条问题")
    overall_score: int = Field(default=50, description="整体评分(0-100, 反方视角)")
    summary_for_editor: str = Field(default="", description="给编辑的保密意见(50字以内)")


# ===== AE终审节点 (共识分歧 + DA CRITICAL + R&R矩阵) =====
class AEFinalInput(BaseModel):
    """AE终审节点输入"""
    paper_content: str = Field(..., description="论文全文")
    journal_requirements: str = Field(..., description="期刊要求")
    venue_profile_text: str = Field(default="", description="期刊/会议画像文本")
    ae_assessment: str = Field(default="", description="AE之前的评估")
    review1_result: Dict[str, Any] = Field(default={}, description="审稿人1意见(方法论)")
    review2_result: Dict[str, Any] = Field(default={}, description="审稿人2意见(理论)")
    review3_result: Dict[str, Any] = Field(default={}, description="审稿人3意见(写作)")
    da_result: Dict[str, Any] = Field(default={}, description="反方辩护人意见")
    paper_rubric: Dict[str, Any] = Field(default={}, description="论文专属评分标准")


class AEFinalOutput(BaseModel):
    """AE终审节点输出"""
    final_decision: str = Field(..., description="最终决定: ACCEPT/MINOR_REVISION/MAJOR_REVISION/REJECT")
    decision_letter: str = Field(..., description="完整的决定信")
    revision_checklist: List[str] = Field(default=[], description="修改要求清单")
    consensus_disagreement: Dict[str, Any] = Field(default={}, description="共识与分歧分析")
    rr_traceability_matrix: List[Dict[str, Any]] = Field(default=[], description="R&R返修追溯矩阵")
    revision_roadmap: Dict[str, Any] = Field(default={}, description="改稿路线图(must_fix/should_fix/nice_to_fix/rebuttal_strategy)")


# ===== 桌拒输出节点 =====
class DeskRejectInput(BaseModel):
    """桌拒输出节点输入"""
    se_decision: str = Field(default="", description="SE决定(如有)")
    se_rejection_letter: str = Field(default="", description="SE桌拒信(如有)")
    se_summary: str = Field(default="", description="SE概括(如有)")
    se_concerns: List[str] = Field(default=[], description="SE关注问题(如有)")
    se_desk_reject_types: List[str] = Field(default=[], description="SE桌拒类型(如有)")
    ae_decision: str = Field(default="", description="AE决定(如有)")
    ae_rejection_letter: str = Field(default="", description="AE桌拒信(如有)")
    ae_assessment: str = Field(default="", description="AE评估(如有)")
    ae_desk_reject_types: List[str] = Field(default=[], description="AE桌拒类型(如有)")


class DeskRejectOutput(BaseModel):
    """桌拒输出节点输出"""
    formatted_output: str = Field(..., description="格式化的桌拒通知内容")
    final_decision: str = Field(default="DESK_REJECT", description="最终决定标记")


# ===== 解析失败输出节点 =====
class ParseFailInput(BaseModel):
    """解析失败输出节点输入"""
    parse_error: str = Field(..., description="解析错误信息")


class ParseFailOutput(BaseModel):
    """解析失败输出节点输出"""
    formatted_output: str = Field(..., description="格式化的错误提示")
