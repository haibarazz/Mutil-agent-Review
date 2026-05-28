# INFORMS Journal on Computing (IJOC / Journal on Computing)

> 智能体期刊画像版，更新日期：2026-05-25。资料主要来自 INFORMS 官方 Editorial Statement。此文件用于用户选择 IJOC 后，智能体判断论文是否符合计算与运筹交叉期刊的内容定位。

## 基本识别

- 简写：IJOC / Journal on Computing
- 全名：INFORMS Journal on Computing
- 榜单归属：UTD24
- 主要领域：Computing；Operations Research；Optimization；Algorithms；Simulation；Software Tools
- 出版方 / 学会：INFORMS
- 官方主页：https://pubsonline.informs.org/journal/ijoc
- 官方 Editorial Statement：https://pubsonline.informs.org/page/ijoc/editorial-statement
- 投稿指南：https://pubsonline.informs.org/page/ijoc/submission-guidelines
- IJOC Data Policy：https://pubsonline.informs.org/page/ijoc/datapolicy
- IJOC Software Policy：https://pubsonline.informs.org/page/ijoc/softwarepolicy

## 一句话定位

IJOC 关注 computing 与 operations research 的交叉，发表能扩展 OR 与计算边界的高质量论文，包括理论、方法、实验、系统、应用、survey/tutorial、软件工具和数据/软件 artifact。

## 官方内容定位：适合什么主题

IJOC 的核心标准是：论文必须同时体现 computing 贡献和 OR/management science 问题意识。它不只是算法期刊，也不只是应用期刊，而是要求研究能被后续研究者构建、复用，或被实践者使用。

官方 area 包括：

- **Artificial Intelligence & Optimization**：AI for optimization、optimization for AI、data-driven optimization、intelligent decision systems、predict-then-optimize、decision-focused learning、online learning with operational constraints、LLM 与优化/决策系统结合。
- **Computational Modeling & Applications**：有重要计算成分的 OR 模型创建、管理、解释、调试、可视化和分析；以及面向医疗、能源、交通、供应链、公共部门、金融、网络安全、可持续、体育等复杂现实问题的 computational OR。
- **Design & Analysis of Algorithms - Continuous**：连续优化算法设计、理论分析和计算评估，包括 convex/nonconvex、first/second-order、decomposition、stochastic/online、large-scale、bilevel、ML-integrated optimization。
- **Design & Analysis of Algorithms - Discrete**：离散优化 exact methods，包括 MIP/MINLP、branch-and-bound/cut/price、polyhedral combinatorics、decomposition、constraint programming、SAT、logic-based optimization。
- **Heuristic Search & Approximation Algorithms**：近似算法、启发式、metaheuristics、local search、matheuristics、性能保证或广泛计算证据。
- **Network Optimization**：网络分析、设计、规划、控制、安全、鲁棒性、韧性，以及真实大规模网络问题。
- **Quantum Computing**：量子计算与 OR 的交叉，包括量子优化、仿真、博弈、学习和 analytics；纯量子信息但无 OR 连接不适合。
- **Simulation, Stochastic Models, & Stochastic Optimization**：随机优化、随机动态规划、强化学习、随机整数规划、simulation optimization、随机系统建模。
- **Software Tools**：面向研究社群的软件和数据，要求软件/数据本身有新贡献、工程质量、可维护性和长期价值。

## 官方偏好的论文类型与贡献方式

IJOC 接受：

- 原创研究论文
- survey 和 tutorial
- 新且有用的软件工具论文
- 数据/软件 artifact 论文
- 理论、方法、实验、系统和应用研究

贡献必须能被后续研究或实践使用。对计算型论文，单纯“跑得更快”通常不够，除非能在足够广泛的问题范围中显示对 state of the art 的显著提升，并有可靠实验设计和可复现性。

## 主题 fit 判断规则

适合 IJOC 的论文通常满足：

- 研究位于 computing 和 OR 的交叉。
- 有明确 computational / computing contribution，而不是只用软件跑实验。
- 问题有 OR、management science 或决策系统意义。
- 算法/模型/系统/软件能推广、复用或被后续研究构建。
- 计算实验设计严谨，并重视结果可复现。
- 软件或数据论文必须提供可用、可维护、有长期研究价值的 artifact。

不适合的情况：

- 纯软件工程、纯 ML benchmark 或纯 CS 算法，缺少 OR/decision-making 连接。
- 只在一个窄数据集上超过 baseline，缺少方法 generality。
- 应用论文只有领域应用新颖，计算/OR 方法贡献不足。
- 软件论文像用户手册或技术规格，而不是研究贡献。
- 数据论文没有说明数据如何推进研究社群。

## 智能体提示词片段

```text
目标期刊是 INFORMS Journal on Computing。
请用计算与 OR 交叉期刊标准评估论文。论文必须扩展 computing 与 operations research 的边界，贡献可以是算法、模型、系统、实验、软件、数据、survey/tutorial 或应用，但必须能被研究者继续构建或被实践者使用。

优先检查：
1. 论文是否同时有 computing contribution 和 OR/decision-making relevance。
2. area fit 是 AI & Optimization、Algorithms、Network Optimization、Simulation/Stochastic、Computational Modeling、Quantum Computing 还是 Software Tools。
3. 方法是否有理论保证、严谨计算实验或可复现软件/数据。
4. 贡献是否具有 generality，而不只是单一 benchmark 改进。
5. 如果是软件/数据论文，artifact 是否可用、可维护、许可清楚、长期有价值。

如果论文只是通用机器学习、普通软件系统或窄应用工程，必须指出 IJOC fit 不足，并建议补强 OR/计算方法贡献。
```

## 可用于提问用户的 fit-check 问题

- 你的 computing contribution 是什么？
- 你的 OR / decision-making 问题是什么？
- 论文属于 IJOC 哪个 area？
- 结果能推广到一类问题吗？
- 计算实验是否比较了 state-of-the-art，并且可复现？
- 如果有软件/数据，是否能公开、维护并被研究社群复用？

## 来源

- INFORMS IJOC journal page：https://pubsonline.informs.org/journal/ijoc
- INFORMS IJOC Editorial Statement：https://pubsonline.informs.org/page/ijoc/editorial-statement
- INFORMS IJOC Submission Guidelines：https://pubsonline.informs.org/page/ijoc/submission-guidelines
- INFORMS IJOC Data Policy：https://pubsonline.informs.org/page/ijoc/datapolicy
- INFORMS IJOC Software Policy：https://pubsonline.informs.org/page/ijoc/softwarepolicy
