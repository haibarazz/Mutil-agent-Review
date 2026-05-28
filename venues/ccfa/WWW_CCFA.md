# International World Wide Web Conference (WWW)

> CCF-A 智能体 venue 画像版，更新日期：2026-05-25。资料来源为 CCF 第七版《中国计算机学会推荐国际学术会议和期刊目录》正式版、CCF 官方目录入口和结构化整理源。此文件用于“用户选择 CS/CCF-A venue 后，智能体判断主题 fit、贡献类型和写作方向”。

## 基本识别

- 简写：WWW
- 全名：International World Wide Web Conference
- 文件名：WWW_CCFA.md
- 类型：会议
- 榜单归属：CCF-A
- CCF 专业领域：交叉/综合/新兴 / Cross-disciplinary / Comprehensive / Emerging
- 出版方 / 主办方：ACM
- CCF 官方目录入口：https://www.ccf.org.cn/Academic_Evaluation/By_category/

## 一句话定位

WWW 是 CCF 推荐目录中 **交叉/综合/新兴** 领域的 A 类会议。交叉、综合和新兴方向的顶级 venue，适合 Web、实时系统、计算生物、跨学科计算和新兴计算问题研究。

## 官方目录定位：适合什么主题

CCF 第七版目录把该 venue 归入 **交叉/综合/新兴**，并标记为 **A 类**。对智能体来说，最重要的 fit 判断是：论文是否真正推进该 CCF 专业领域的核心问题，而不是只借用该领域作为应用背景。

该领域通常覆盖：

- Web、互联网平台和综合计算系统
- 实时系统和嵌入式系统
- 计算生物学、医学信息和生物信息学
- 跨学科计算方法
- 新兴计算技术、社会技术系统和服务科学
- 与计算机科学核心方法深度耦合的应用研究

## CCF-A 投稿/选刊判断要点

- A 类表示 CCF 推荐目录中该专业领域的最高推荐等级之一，但 CCF 官方也说明目录是推荐建议，不建议简单作为学术评价依据。
- 主题必须与该 venue 所在 CCF 专业领域高度一致。
- 贡献需要达到顶级 CS venue 的标准：问题重要、方法扎实、实验/理论/系统评估充分、对领域有可迁移价值。
- 如果是系统或工程类论文，应有真实系统、明确工作负载、可复现实验和与强基线对比。
- 如果是理论类论文，应有清晰模型、定理、证明和相对已有结果的实质推进。
- 如果是 AI/数据类论文，应有强基线、消融、误差分析、数据/任务合理性和泛化讨论。
- CCF 官方说明中，会议论文指 Full paper 或 Regular paper；Short paper、Demo paper、Technical Brief、Summary、Findings 以及 Workshop 等不计入目录考虑范围。

## 对主题 fit 的判断规则

适合 WWW 的论文通常满足：

- 研究问题属于 **交叉/综合/新兴** 的核心问题。
- 论文贡献与 International World Wide Web Conference 的全名和领域传统一致。
- 方法、理论、系统或实验设计能够支撑 CCF-A 级别贡献。
- 结果不仅在单一数据集或场景有效，还能形成可迁移的领域 insight。
- 写作能清楚回答“为什么这个问题重要、为什么现在解决、为什么该 venue 的读者会关心”。

不适合 WWW 的情况：

- 只是把现成技术应用到一个数据集或案例，缺少方法/系统/理论贡献。
- 主题属于相邻领域，但没有解释为什么适合 **交叉/综合/新兴**。
- 只有性能数字，没有机制解释、消融、误差分析或系统洞察。
- 论文贡献主要是产品实现、工程堆叠或业务报告，而不是可发表研究。

## 官方要求抓取（官方源，2026-05-25）

官方来源：

- The Web Conference 2026 Research Tracks: https://www2026.thewebconf.org/calls/research-tracks.html

### 官方定位与主题范围

- 官方短摘：`understanding the current state and the evolution of the Web`。
- The Web Conference 官方 scope 强调 Web 是 distinct scholarly field；论文应显式聚焦 Web，而不是只使用 Web artifact。
- 官方要求论文首页明确说明与 Web 和 track 的相关性；如果只是用了 Web dataset、Web API 或 social network，而没有回答 Web-related scientific research challenge，会 desk reject。
- Research tracks 包括 Economics/online markets/human computation、Graph algorithms and modeling for the Web、Responsible Web、Search and retrieval-augmented AI、Security and privacy、Semantics and knowledge、Social networks and social media、Systems and infrastructure for Web/mobile/WoT、User modeling/personalization/recommendation、Web mining and content analysis。

### 官方投稿与评审要求

- Submissions 使用 EasyChair；authors 需要更新 EasyChair profile 和 conflict information。
- 论文需为 ACM double-column format；main paper 8 pages，references 和 optional appendix 可额外加入，总页数最多 12 pages；前 8 页必须 self-contained。
- Double-blind review；作者姓名、机构、acknowledgments、自引方式等需要匿名。
- LLM 不能作为作者；作者可用 LLM rephrase text，但要对论文文本负责。
- Ethical Use of Data and Informed Consent：适用 ACM human participants / subjects policy；涉及 IRB 时应在论文中说明审批信息。
- Review decisions 会考虑 technical merit、originality、potential impact、quality of execution、presentation、related work、reproducibility、ethics。

### 给智能体的硬约束

- WWW fit 最关键的问题是“这是否解决 Web 作为技术基础设施、社会经济系统、影响机制或可访问/公平/责任治理对象的研究问题”。
- 如果论文只是用网页数据、社交网络数据或 Web API 当普通数据源，应提示它可能被官方定义为 out of scope。
- 对推荐、搜索、图、社媒、隐私、安全、知识图谱、Web mining 论文，必须把贡献锚定到 Web-specific challenge。

## 智能体提示词片段

```text
目标 venue 是 International World Wide Web Conference (WWW)，CCF-A，类型为会议，所属 CCF 专业领域为：交叉/综合/新兴 / Cross-disciplinary / Comprehensive / Emerging。

请按 CCF-A 顶级 CS venue 标准评估论文：先判断研究问题是否真正属于该专业领域，再检查贡献是否达到顶级会议要求。重点评估问题重要性、技术/理论/系统新意、实验或证明强度、与强基线对比、可复现性、局限性和领域影响。

如果论文只是把通用方法套到一个场景，或者主题与 交叉/综合/新兴 关系弱，请明确指出 fit 不足，并建议如何重写为该领域核心问题。
```

## 可用于提问用户的 fit-check 问题

- 你的论文最核心的 CS 问题是什么？它为什么属于 **交叉/综合/新兴**？
- 你的贡献是理论、算法、系统、实证、数据集、benchmark，还是多种结合？
- 你和该 venue 近三年论文相比的新意在哪里？
- 你的 strongest baselines、ablation、scalability 或 proof obligations 是否足够？
- 如果审稿人认为这是相邻领域论文，你如何解释它适合 WWW？

## 来源

- CCF 官方目录入口：https://www.ccf.org.cn/Academic_Evaluation/By_category/
- CCF 第七版正式目录 PDF：CCF 官方页面中的“第七版中国计算机学会推荐国际学术会议和期刊目录（正式版）”
- 结构化整理源：https://ccf.atom.im/
- GitHub Gist 结构化 JSON：https://gist.github.com/ayusdixit/3dac1dcc26ece8a2ddbe3da019d671ea
