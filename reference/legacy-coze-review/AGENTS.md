## 项目概述
- **名称**: 多智能体论文审稿系统
- **功能**: 模拟真实期刊审稿流程，支持快速审稿/完整审稿，集成LLM内容审查、期刊画像注入(CCF-A/UTD24/FT50)、领域分析、并行审稿人、反方辩护人等能力
- **期刊画像**: 支持118个预设期刊/会议(CCF-A x94 + UTD24/FT50 x24)，自动读取画像文件注入SE/AE/审稿人/DA/AE终审提示词
- **手动输入**: 未选择预设期刊时，journal_name作为手动输入的期刊要求，同样注入提示词
- **审稿格式**: Part1[The Review Report] + Part2[Strategic Advice] 双板块输出
- **输入枚举**: review_mode/venue_category/venue_code 使用 Literal 类型生成前端下拉选项(147个预设代码)

### 节点清单
| 节点名 | 文件位置 | 类型 | 功能描述 | 分支逻辑 | 配置文件 |
|-------|---------|------|---------|---------|---------|
| doc_parse | `nodes/doc_parse_node.py` | task | 解析上传论文文件为纯文本 | 成功/失败 | - |
| content_check | `nodes/content_check_node.py` | agent | LLM内容审查，判断上传内容是否为学术论文 | VALID_PAPER/NOT_PAPER | `config/content_check_llm_cfg.json` |
| invalid_file_node | `nodes/invalid_file_node.py` | task | 非论文内容提示用户重新上传 | - | - |
| parse_fail_output | `nodes/parse_fail_output_node.py` | task | 解析失败时输出错误提示 | - | - |
| journal_req_collector | `nodes/journal_req_collector_node.py` | agent | 三路径收集期刊要求(上传/搜索+抓取/默认)，根据venue_code加载期刊画像文件(CCFA/UTD_FT50) | - | `config/journal_req_collector_llm_cfg.json` |
| field_analyst | `nodes/field_analyst_node.py` | agent | 论文领域分析+动态审稿人配置 | - | `config/field_analyst_llm_cfg.json` |
| se_check | `nodes/se_check_node.py` | agent | SE主编初审(反谦逊评分0-100+7类桌拒分类) | PASS/DESK_REJECT | `config/se_check_llm_cfg.json` |
| ae_check | `nodes/ae_check_node.py` | agent | AE责任编辑筛选(论文专属rubric+7类桌拒分类) | SEND_FOR_REVIEW/DESK_REJECT | `config/ae_check_llm_cfg.json` |
| review_dispatch | `nodes/review_dispatch_node.py` | task | 虚拟分发节点，透传数据给4路并行审稿人 | - | - |
| reviewer1 | `nodes/reviewer1_node.py` | agent | 审稿人1-方法论专家(Part1+Part2格式) | - | `config/reviewer1_llm_cfg.json` |
| reviewer2 | `nodes/reviewer2_node.py` | agent | 审稿人2-领域专家(论文搜索+Part1+Part2格式) | - | `config/reviewer2_llm_cfg.json` |
| reviewer3 | `nodes/reviewer3_node.py` | agent | 审稿人3-跨学科专家(Part1+Part2格式) | - | `config/reviewer3_llm_cfg.json` |
| devils_advocate | `nodes/devils_advocate_node.py` | agent | 反方辩护人(CRITICAL铁律+Part1+Part2格式) | - | `config/devils_advocate_llm_cfg.json` |
| ae_final | `nodes/ae_final_node.py` | agent | AE终审(共识分歧+R&R矩阵+改稿路线图) | - | `config/ae_final_llm_cfg.json` |
| desk_reject_output | `nodes/desk_reject_output_node.py` | task | 格式化桌拒通知(SE/AE桌拒+7类桌拒分类+改进建议) | - | - |

**类型说明**: task(任务节点) / agent(大模型) / condition(条件分支，定义在graph.py中)

### 审稿输出格式（Part1+Part2）
**审稿人1/2/3** 统一输出：
- Part1 [The Review Report]: summary / strengths / weaknesses / rating(1-10) / rating_justification
- Part2 [Strategic Advice]: problem_roots / salvageability(可修/难修) / action_guide

**反方辩护人(DA)** 输出：
- Part1: summary / strongest_counter_argument / strengths_conceded / weaknesses / rating / rating_justification
- Part2: strategic_advice(attack_surface/rebuttal_weaknesses/action_guide) / cherry_picking_evidence / confirmation_bias / logic_chain_issues / ignored_alternatives

**AE终审** 输出：
- final_decision / decision_letter / consensus_disagreement / rr_traceability_matrix / revision_roadmap(must_fix/should_fix/nice_to_fix/rebuttal_strategy)

### 条件分支函数
| 函数名 | 位置 | 判断逻辑 | 分支映射 |
|-------|------|---------|---------|
| route_after_content_check | graph.py | content_check的intent字段 | VALID_PAPER→journal_req_collector, NOT_PAPER→invalid_file_node |
| check_parse_result | graph.py | parse_error字段 | 有值→parse_fail_output, 空→content_check |
| route_after_field_analyst | graph.py | review_mode字段 | QUICK_REVIEW→review_dispatch(跳过SE/AE直接外审), FULL_REVIEW→se_check |
| route_after_se | graph.py | se_decision | DESK_REJECT→desk_reject_output, PASS→ae_check |
| should_ae_send_review | graph.py | ae_decision字段 | SEND_FOR_REVIEW→review_dispatch, DESK_REJECT→desk_reject_output |

### 桌拒7类分类
| 编号 | 类型 | 英文 | 说明 |
|:---:|------|------|------|
| DR-1 | 🎯 选题范围不匹配 | Scope Mismatch | 论文主题不属于期刊关注领域 |
| DR-2 | 💡 创新性不足 | Insufficient Novelty | 研究问题陈旧、增量贡献不够 |
| DR-3 | 🔬 方法论根本缺陷 | Fundamental Methodological Flaws | 实验设计不合理、统计方法错误 |
| DR-4 | 📝 内容严重不完整 | Incomplete Manuscript | 核心章节缺失、正文过短 |
| DR-5 | ✍️ 写作/格式严重不达标 | Poor Writing/Formatting | 语言质量极差、格式不合规 |
| DR-6 | ⚠️ 学术伦理/规范问题 | Ethical/Compliance Issues | 涉嫌抄袭、缺少伦理审批 |
| DR-7 | 🏔️ 影响力不匹配期刊定位 | Insufficient Impact for Target Venue | 论文OK但对目标顶刊不够 |

## 技能使用
- `content_check`: 大语言模型 (doubao-seed-2-0-pro)
- `journal_req_collector`: 大语言模型 + 网络搜索(SearchClient) + URL内容抓取(FetchClient) + 期刊画像文件读取
- `field_analyst`: 大语言模型 (doubao-seed-2-0-pro)
- `se_check`: 大语言模型 (doubao-seed-2-0-pro)
- `ae_check`: 大语言模型 (doubao-seed-2-0-pro)
- `reviewer1`: 大语言模型 (doubao-seed-2-0-pro)
- `reviewer2`: 大语言模型 (doubao-seed-2-0-pro) + 网络搜索(SearchClient)
- `reviewer3`: 大语言模型 (doubao-seed-2-0-pro)
- `devils_advocate`: 大语言模型 (doubao-seed-2-0-pro)
- `ae_final`: 大语言模型 (doubao-seed-2-0-pro)

## 变更记录
### v4.2
- **下拉选项枚举**: GraphInput的review_mode/venue_category/venue_code改为Literal类型，前端自动渲染下拉选择框
- **期刊代码枚举**: 新增`graphs/venue_codes.py`，包含CCFA_CODES(94个)、UTD_FT50_CODES(52个)、ALL_VENUE_CODES(147个含空字符串)
- **x-component提示**: review_mode/venue_category/venue_code添加`json_schema_extra={"x-component": "select"}`提示前端使用选择器组件
- **描述优化**: GraphInput/GraphOutput字段描述添加emoji图标和详细说明，改善前端可读性

### v4.1
- **期刊画像注入**: 根据venue_code自动读取CCFA/UTD_FT50画像文件，提取内容注入SE/AE/审稿人/DA/AE终审的UP
- **输入更新**: GraphInput新增venue_code字段，保留journal_name用于手动输入期刊要求
- **画像加载**: journal_req_collector_node新增`_load_venue_profile()`函数，支持CCFA和UTD_FT50两种命名规则
- **配置文件更新**: se_check/ae_check/reviewer1/reviewer2/reviewer3/devils_advocate/ae_final共7个UP追加`{{venue_profile_text}}`注入点
- **节点代码更新**: 7个Agent节点渲染UP时传入`venue_profile_text=state.venue_profile_text`

### v4.0
- **审稿格式重构**: 所有审稿人统一为 Part1[The Review Report] + Part2[Strategic Advice] 双板块输出
- **审稿人1/2/3**: 输出字段从 scores/major_comments/minor_comments 改为 summary/strengths/weaknesses/rating(1-10)/rating_justification/strategic_advice
- **DA反方辩护人**: 输出字段简化对齐，增加 strengths_conceded/cherry_picking/confirmation_bias/logic_chain_issues
- **AE终审**: 新增 revision_roadmap(must_fix/should_fix/nice_to_fix/rebuttal_strategy) 改稿路线图
- **State更新**: Reviewer1/2/3Output、DAOutput、AEFinalOutput 字段全面更新
- **DA配置优化**: 关闭thinking模式避免JSON截断，增大max_completion_tokens到6000

### v3.2
- **重做意图识别**: 去掉LLM 4路意图识别，改为review_mode选择(FULL_REVIEW/QUICK_REVIEW)
- **新增LLM内容审查**: content_check_node用LLM判断上传内容是否为学术论文（非仅检查扩展名）
- **新增invalid_file_node**: 非论文内容提示用户重新上传
- **输入简化**: GraphInput改为paper_file + review_mode + journal_name
- **删除废弃节点**: intent_recognition, refuse_response, ask_for_paper, quick_review_output, file_check
- **修复content_check_node LLM调用**: 从错误的client.chat()改为正确的client.invoke()

### v3.1
- **快速审稿改为直接外审**: 跳过SE/AE筛选，用户一定能拿到完整审稿意见
- **默认策略**: user_query为空但paper_file已提供时默认走FULL_REVIEW
- **7类桌拒分类**: DR-1~DR-7，SE/AE桌拒时自动分类并给出改进建议
- **ask_for_paper增加missing_inputs**: 前端可程序化展示上传组件
- **JSON解析鲁棒性增强**: 所有9个Agent节点增加think标签去除+花括号提取+ValueError捕获

### v3.0
- **新增意图识别**: 4路路由(NON_REVIEW/NEED_PAPER/QUICK_REVIEW/FULL_REVIEW)
- **新增期刊要求收集**: 三路径(上传文档/联网搜索+抓取/默认通用)
- **新增桌拒输出节点**: 修复P0桌拒时输出为空
- **新增解析失败终止**: 修复P0解析失败后继续审稿
- **修复reviewer_persona断裂**: 审稿人从reviewer_config dict提取各自persona
- **新增review_dispatch分发节点**: 解决4审稿人并行汇聚验证
