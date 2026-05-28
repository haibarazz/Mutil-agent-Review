# ACM Transactions on Architecture and Code Optimization (TACO)

> CCF-A 智能体 venue 画像版，更新日期：2026-05-25。资料来源为 CCF 第七版《中国计算机学会推荐国际学术会议和期刊目录》正式版、CCF 官方目录入口和结构化整理源。此文件用于“用户选择 CS/CCF-A venue 后，智能体判断主题 fit、贡献类型和写作方向”。

## 基本识别

- 简写：TACO
- 全名：ACM Transactions on Architecture and Code Optimization
- 文件名：TACO_CCFA.md
- 类型：期刊
- 榜单归属：CCF-A
- CCF 专业领域：计算机体系结构/并行与分布计算/存储系统 / Computer Architecture / Parallel and Distributed Computing / Storage System
- 出版方 / 主办方：ACM
- CCF 官方目录入口：https://www.ccf.org.cn/Academic_Evaluation/By_category/

## 一句话定位

TACO 是 CCF 推荐目录中 **计算机体系结构/并行与分布计算/存储系统** 领域的 A 类期刊。计算机体系结构、并行与分布计算、存储系统方向的顶级 venue，适合硬件/系统/存储/HPC/云基础设施等底层计算系统研究。

## 官方目录定位：适合什么主题

CCF 第七版目录把该 venue 归入 **计算机体系结构/并行与分布计算/存储系统**，并标记为 **A 类**。对智能体来说，最重要的 fit 判断是：论文是否真正推进该 CCF 专业领域的核心问题，而不是只借用该领域作为应用背景。

该领域通常覆盖：

- 处理器与计算机体系结构
- 并行与分布式系统
- 存储系统与文件系统
- 高性能计算与云基础设施
- 编译器、运行时与系统性能优化
- 硬件/软件协同设计与系统评测

## CCF-A 投稿/选刊判断要点

- A 类表示 CCF 推荐目录中该专业领域的最高推荐等级之一，但 CCF 官方也说明目录是推荐建议，不建议简单作为学术评价依据。
- 主题必须与该 venue 所在 CCF 专业领域高度一致。
- 贡献需要达到顶级 CS venue 的标准：问题重要、方法扎实、实验/理论/系统评估充分、对领域有可迁移价值。
- 如果是系统或工程类论文，应有真实系统、明确工作负载、可复现实验和与强基线对比。
- 如果是理论类论文，应有清晰模型、定理、证明和相对已有结果的实质推进。
- 如果是 AI/数据类论文，应有强基线、消融、误差分析、数据/任务合理性和泛化讨论。

## 对主题 fit 的判断规则

适合 TACO 的论文通常满足：

- 研究问题属于 **计算机体系结构/并行与分布计算/存储系统** 的核心问题。
- 论文贡献与 ACM Transactions on Architecture and Code Optimization 的全名和领域传统一致。
- 方法、理论、系统或实验设计能够支撑 CCF-A 级别贡献。
- 结果不仅在单一数据集或场景有效，还能形成可迁移的领域 insight。
- 写作能清楚回答“为什么这个问题重要、为什么现在解决、为什么该 venue 的读者会关心”。

不适合 TACO 的情况：

- 只是把现成技术应用到一个数据集或案例，缺少方法/系统/理论贡献。
- 主题属于相邻领域，但没有解释为什么适合 **计算机体系结构/并行与分布计算/存储系统**。
- 只有性能数字，没有机制解释、消融、误差分析或系统洞察。
- 论文贡献主要是产品实现、工程堆叠或业务报告，而不是可发表研究。


## 官方要求抓取（官方源，2026-05-25）

官方来源：

- ACM TACO About: https://dl.acm.org/journal/taco/about

来源类型：官方 Aims & Scope / About / Author 页面

### 官方定位与主题范围

- TACO 官方定位为 architecture and code optimization 领域期刊，关注体系结构、编译器、代码优化和硬件/软件协同。
- 适合架构感知优化、编译技术、runtime、memory/parallelism、embedded/accelerator code generation、performance/energy optimization。

### 官方投稿与评审要求

- 论文应提供系统性方法、严谨实验、可复现 benchmark 和对架构/代码优化关系的清晰解释。
- 期刊稿件需比会议短文更完整，包含背景、方法、充分比较和局限性。

### 给智能体的硬约束

- TACO fit 要求同时接触 architecture 或 code optimization；纯算法或纯硬件设计不够。
- 建议智能体追问目标架构、编译/运行时路径和性能证据。

## 智能体提示词片段

```text
目标 venue 是 ACM Transactions on Architecture and Code Optimization (TACO)，CCF-A，类型为期刊，所属 CCF 专业领域为：计算机体系结构/并行与分布计算/存储系统 / Computer Architecture / Parallel and Distributed Computing / Storage System。

请按 CCF-A 顶级 CS venue 标准评估论文：先判断研究问题是否真正属于该专业领域，再检查贡献是否达到顶级期刊要求。重点评估问题重要性、技术/理论/系统新意、实验或证明强度、与强基线对比、可复现性、局限性和领域影响。

如果论文只是把通用方法套到一个场景，或者主题与 计算机体系结构/并行与分布计算/存储系统 关系弱，请明确指出 fit 不足，并建议如何重写为该领域核心问题。
```

## 可用于提问用户的 fit-check 问题

- 你的论文最核心的 CS 问题是什么？它为什么属于 **计算机体系结构/并行与分布计算/存储系统**？
- 你的贡献是理论、算法、系统、实证、数据集、benchmark，还是多种结合？
- 你和该 venue 近三年论文相比的新意在哪里？
- 你的 strongest baselines、ablation、scalability 或 proof obligations 是否足够？
- 如果审稿人认为这是相邻领域论文，你如何解释它适合 TACO？

## 来源

- CCF 官方目录入口：https://www.ccf.org.cn/Academic_Evaluation/By_category/
- CCF 第七版正式目录 PDF：CCF 官方页面中的“第七版中国计算机学会推荐国际学术会议和期刊目录（正式版）”
- 结构化整理源：https://ccf.atom.im/
- GitHub Gist 结构化 JSON：https://gist.github.com/ayusdixit/3dac1dcc26ece8a2ddbe3da019d671ea
