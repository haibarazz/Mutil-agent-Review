# ACM SIGKDD Conference on Knowledge Discovery and Data Mining (SIGKDD)

> CCF-A 智能体 venue 画像版，更新日期：2026-05-25。资料来源为 CCF 第七版《中国计算机学会推荐国际学术会议和期刊目录》正式版、CCF 官方目录入口和结构化整理源。此文件用于“用户选择 CS/CCF-A venue 后，智能体判断主题 fit、贡献类型和写作方向”。

## 基本识别

- 简写：SIGKDD
- 全名：ACM SIGKDD Conference on Knowledge Discovery and Data Mining
- 文件名：SIGKDD_CCFA.md
- 类型：会议
- 榜单归属：CCF-A
- CCF 专业领域：数据库/数据挖掘/内容检索 / Database / Data Mining / Content Retrieval
- 出版方 / 主办方：ACM
- CCF 官方目录入口：https://www.ccf.org.cn/Academic_Evaluation/By_category/

## 一句话定位

SIGKDD 是 CCF 推荐目录中 **数据库/数据挖掘/内容检索** 领域的 A 类会议。数据库、数据挖掘和内容检索方向的顶级 venue，适合数据管理、数据系统、数据挖掘、信息检索和 Web 数据研究。

## 官方目录定位：适合什么主题

CCF 第七版目录把该 venue 归入 **数据库/数据挖掘/内容检索**，并标记为 **A 类**。对智能体来说，最重要的 fit 判断是：论文是否真正推进该 CCF 专业领域的核心问题，而不是只借用该领域作为应用背景。

该领域通常覆盖：

- 数据库系统与查询处理
- 事务、索引、存储与数据管理
- 数据挖掘、机器学习与大规模数据分析
- 信息检索、搜索与推荐
- Web、图数据、知识图谱和数据质量
- 数据系统评测与真实工作负载

## CCF-A 投稿/选刊判断要点

- A 类表示 CCF 推荐目录中该专业领域的最高推荐等级之一，但 CCF 官方也说明目录是推荐建议，不建议简单作为学术评价依据。
- 主题必须与该 venue 所在 CCF 专业领域高度一致。
- 贡献需要达到顶级 CS venue 的标准：问题重要、方法扎实、实验/理论/系统评估充分、对领域有可迁移价值。
- 如果是系统或工程类论文，应有真实系统、明确工作负载、可复现实验和与强基线对比。
- 如果是理论类论文，应有清晰模型、定理、证明和相对已有结果的实质推进。
- 如果是 AI/数据类论文，应有强基线、消融、误差分析、数据/任务合理性和泛化讨论。
- CCF 官方说明中，会议论文指 Full paper 或 Regular paper；Short paper、Demo paper、Technical Brief、Summary、Findings 以及 Workshop 等不计入目录考虑范围。

## 对主题 fit 的判断规则

适合 SIGKDD 的论文通常满足：

- 研究问题属于 **数据库/数据挖掘/内容检索** 的核心问题。
- 论文贡献与 ACM SIGKDD Conference on Knowledge Discovery and Data Mining 的全名和领域传统一致。
- 方法、理论、系统或实验设计能够支撑 CCF-A 级别贡献。
- 结果不仅在单一数据集或场景有效，还能形成可迁移的领域 insight。
- 写作能清楚回答“为什么这个问题重要、为什么现在解决、为什么该 venue 的读者会关心”。

不适合 SIGKDD 的情况：

- 只是把现成技术应用到一个数据集或案例，缺少方法/系统/理论贡献。
- 主题属于相邻领域，但没有解释为什么适合 **数据库/数据挖掘/内容检索**。
- 只有性能数字，没有机制解释、消融、误差分析或系统洞察。
- 论文贡献主要是产品实现、工程堆叠或业务报告，而不是可发表研究。

## 官方要求抓取（官方源，2026-05-25）

官方来源：

- KDD 2026 Research Track CFP: https://kdd2026.kdd.org/research-track-call-for-papers/

### 官方定位与主题范围

- 官方短摘：`knowledge discovery, data science and AI`；`innovative research`。
- KDD Research Track 官方 scope 覆盖 knowledge discovery、data science、AI，从 theoretical foundations 到面向 science、business、medicine、engineering 的 applied problems。
- 官方主题包括 Foundations of Knowledge Discovery and Data Science、Modern AI and Big Data、Trustworthy and Responsible Data Science、Systems for Data Science and Scalable AI、Data Science Applications。
- 官方欢迎 visionary papers on new and emerging topics，也欢迎 application-oriented papers that make innovative technical contributions to research。
- Survey papers 如果只是总结 current state、没有 novel intellectual contribution，则 out of scope。

### 官方投稿与评审要求

- Research track 使用 OpenReview；authors 必须有完整 OpenReview profile，缺失可 desk reject。
- Full paper 为 single PDF：8 content pages main paper，references 和 optional appendix 另计；前 8 页应 self-contained，reviewers 不需要读 appendix。
- Double-blind review；submission 需隐藏作者、机构和其他识别信息。
- 每篇 submission 需指定至少一位 qualified reviewer author；不履行 review duty 可能导致 desk rejection 或影响 rebuttal 可见性。
- Ethical Use of Data and Informed Consent：涉及人类参与者/数据时需遵守 ACM policy 和 IRB/ethics review 要求。
- Decision factors 包括 technical merit、originality、potential impact、quality of execution、quality of presentation、related work、reproducibility、ethics。
- Accepted papers 鼓励公开 code/data，并可申请 ACM Artifacts Available badge。

### 给智能体的硬约束

- KDD fit 的核心不是“用了数据”，而是对 knowledge discovery/data science/AI 的方法、系统、理论、评估、责任治理或应用研究有创新贡献。
- 对应用论文，必须检查是否有 innovative technical contribution；纯业务分析或领域报告应判为弱。
- 对数据集、平台、系统论文，应强制追问 reproducibility、artifact、伦理使用数据、informed consent、IRB 和可公开性。

## 智能体提示词片段

```text
目标 venue 是 ACM SIGKDD Conference on Knowledge Discovery and Data Mining (SIGKDD)，CCF-A，类型为会议，所属 CCF 专业领域为：数据库/数据挖掘/内容检索 / Database / Data Mining / Content Retrieval。

请按 CCF-A 顶级 CS venue 标准评估论文：先判断研究问题是否真正属于该专业领域，再检查贡献是否达到顶级会议要求。重点评估问题重要性、技术/理论/系统新意、实验或证明强度、与强基线对比、可复现性、局限性和领域影响。

如果论文只是把通用方法套到一个场景，或者主题与 数据库/数据挖掘/内容检索 关系弱，请明确指出 fit 不足，并建议如何重写为该领域核心问题。
```

## 可用于提问用户的 fit-check 问题

- 你的论文最核心的 CS 问题是什么？它为什么属于 **数据库/数据挖掘/内容检索**？
- 你的贡献是理论、算法、系统、实证、数据集、benchmark，还是多种结合？
- 你和该 venue 近三年论文相比的新意在哪里？
- 你的 strongest baselines、ablation、scalability 或 proof obligations 是否足够？
- 如果审稿人认为这是相邻领域论文，你如何解释它适合 SIGKDD？

## 来源

- CCF 官方目录入口：https://www.ccf.org.cn/Academic_Evaluation/By_category/
- CCF 第七版正式目录 PDF：CCF 官方页面中的“第七版中国计算机学会推荐国际学术会议和期刊目录（正式版）”
- 结构化整理源：https://ccf.atom.im/
- GitHub Gist 结构化 JSON：https://gist.github.com/ayusdixit/3dac1dcc26ece8a2ddbe3da019d671ea
