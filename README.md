# EvoTraders：自我进化的多智能体交易系统

## 项目概览

EvoTraders 是一个开源的金融交易智能体框架，旨在构建能够真正自我进化的多智能体交易系统。不同于传统的预定义工作流，EvoTrader 通过三维反馈机制让智能体群体在实战中持续学习、适应与进化。

### 为什么选择EvoTrader？

传统的算法交易系统追求的是确定性与可重复性——通过精密的数学模型和严格的回测来保证策略的稳定性。但现实市场是一个动态演化的复杂系统，没有任何静态策略能够永远有效。

当我们观察一家成功的对冲基金时，看到的不是一台完美校准的机器，而是一个活跃的生态系统：

- 分析师之间激烈的观点碰撞
- 投资经理对不同信息源的动态权衡
- 风控团队与执行团队的持续博弈
- 整个组织在市场反馈中的集体学习

这种看似混乱的过程，恰恰孕育着真正的集体智能。**EvoTrader 的核心洞见是：优秀的交易系统不应被设计（design），而应被进化（evolve）**。

## 核心理念：三维反馈驱动的自我进化

在 EvoTrader 中，智能体的学习信号来自三个维度，构成完整的进化循环：

### 1. From Agents：智能通信网络

智能体之间的交互不再是简单的信息传递，而是一个动态的、有策略的协作网络。

**分析师的 Notification 机制**  
当任何分析师在研究过程中发现重大机会或风险时，可以超越自身职责范围，向整个系统广播高优先级通知。这确保了关键信息不会被埋没在常规流程中。

**投资组合经理的智能沟通策略**  
作为决策核心，投资组合经理能够：
- 智能选择与哪些分析师进行深度交流
- 决定采用 Meeting（集体共识）还是 Private Chat（深度质询）模式
- 动态调整沟通资源的分配，向更高质量的信息源倾斜

这种设计使得系统能够自动识别并放大有价值的信息，同时过滤噪声。

### 2. From Environment：市场驱动的记忆进化

智能体的学习直接与市场结果挂钩，形成闭环的经验循环。

**盘前/盘后复盘机制（Time Sandbox）**  
- **盘前（Pre-market）**：系统基于当前认知给出交易信号
- **盘后（Post-market）**：利用真实市场结果进行自主复盘

**记忆的动态更新与修正**  
投资组合经理可以：
- **Search**：检索过去的相关决策记忆
- **Update**：强化被市场验证的成功分析逻辑
- **Delete**：快速清除导致重大错误的决策模式

这种机制实现了"错误思想"的快速淘汰，避免系统重复犯错。系统支持两种可插拔的记忆框架：**mem0** 和 **ReMe**，为不同场景提供灵活的记忆管理策略。

### 3. From System：OKR治理机制

借鉴现代企业管理的 OKR（Objectives and Key Results）理念，EvoTrader 引入了系统级的治理机制：

**5日复盘机制**  
每5个交易日，系统会根据各分析师的信号质量和市场反馈，动态调整其在决策中的权重。表现优异的分析师将获得更大的话语权。

**30日OKR评估**  
每30个交易日，系统执行彻底的绩效评估：
- 统计最近四周的平均权重
- 淘汰表现最差的分析师
- 引入新的分析师（新员工有3个月的保护期）

这种"优胜劣汰"的机制确保了智能体群体的持续优化，模拟了真实对冲基金的人员管理策略。

## 系统架构

### 多角色智能体生态

EvoTrader 内置了五种专业化的分析师角色，每种角色都有独特的分析视角和工具偏好：

**1. 基本面分析师（Fundamental Analyst）**
- 关注：公司财务健康度、商业模式可持续性、管理层质量
- 偏好工具：盈利能力分析、增长分析、财务健康分析、估值比率分析

**2. 技术分析师（Technical Analyst）**
- 关注：价格趋势、技术指标、市场情绪、资金流向
- 偏好工具：趋势跟踪、动量分析、均值回归、波动率分析

**3. 情绪分析师（Sentiment Analyst）**
- 关注：市场参与者情绪、新闻舆情、内部人交易、投资者心理
- 偏好工具：新闻情绪分析、内部人交易分析

**4. 估值分析师（Valuation Analyst）**
- 关注：公司内在价值计算、估值模型对比、安全边际评估
- 偏好工具：DCF估值、所有者收益估值、EV/EBITDA估值、剩余收益估值

**5. 综合分析师（Comprehensive Analyst）**
- 整合多维度分析视角，平衡短期与长期因素
- 灵活选择工具，适应不同市场环境

**投资组合经理（Portfolio Manager）**
- 收集并整合所有分析师信号
- 执行智能沟通策略
- 做出最终投资决策
- 管理记忆系统的更新与修正

**风险管理器（Risk Manager）**
- 实时监控持仓风险
- 执行头寸限制和风险控制
- 提供多层次的风险预警

### 两种运行模式

**Signal Mode（信号模式）**  
针对每个交易标的（ticker）生成当日操作建议（买入/卖出/持有），可视为一种因子信号输出。适合作为量化系统的信号源，或与其他策略组合使用。

**Portfolio Mode（组合模式）**  
从整体视角出发，动态管理并优化整个投资组合的资产配置。系统会考虑当前持仓、资金状态、风险约束等因素，给出具体的交易数量建议。

## 技术特性

### 模块化设计

所有智能体工具都被独立封装，极大简化了新角色或新能力的扩展。只需：
1. 在 `src/tools/` 中定义新工具
2. 在 `src/agents/prompts/` 中配置角色persona
3. 系统自动完成工具注册和调用

### 实时回测与可视化

EvoTrader 提供了强大的回测和可视化系统：

**实时数据回测**  
- 支持历史数据回放和实时数据接入
- 自动处理美股交易日历和时区
- 支持日频和高频数据回测

**可视化Dashboard**  
- 实时展示智能体交互过程
- 多维度绩效分析（收益曲线、最大回撤、夏普比率等）
- 智能体权重演化追踪
- 支持Mock模式用于前端开发和调试

### 可扩展的记忆系统

**mem0 框架**  
适合快速原型开发，提供简洁的API和良好的文档。

**ReMe 框架**  
基于向量存储的高性能记忆系统，支持：
- 全局单例模式避免资源冲突
- workspace_id 机制实现多用户隔离
- 高效的语义检索和相似度匹配

## Quick Start

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/EvoTrader.git
cd EvoTrader
```

2. Install the package:
```bash
pip install -e .
```

3. Configure environment variables:
```bash
cp env.template .env
# Edit .env file and add your API keys
```

### CLI Usage

EvoTraders provides a simple command-line interface:

**Run Backtest Mode:**
```bash
evotraders backtest --start 2025-11-01 --end 2025-12-01
```

**Run Live Trading Mode:**
```bash
evotraders live                    # Real-time mode
evotraders live --mock             # Mock mode for testing
```

**Start Frontend Dashboard:**
```bash
evotraders frontend                # Connect to default port 8765
evotraders frontend --ws-port 8766 # Connect to custom port
```

**Get Help:**
```bash
evotraders --help
evotraders backtest --help
evotraders live --help
evotraders frontend --help
```

### Access Dashboard

After starting the backend, open your browser and visit:
```
http://localhost:5173/
```

Select a date on the right panel and click Run/Replay to observe the agent decision-making process.

## Project Structure

```
EvoTrader/
├── backend/
│   ├── agents/           # Agent implementations
│   ├── communication/    # Agent communication system
│   ├── memory/          # Memory system (mem0, ReMe)
│   ├── tools/           # Analysis tools
│   ├── servers/         # Backend servers
│   ├── okr/            # OKR governance system
│   ├── cli.py          # CLI entry point
│   └── ...
├── frontend/           # React dashboard
├── logs_and_memory/    # Logs and memory data
└── pyproject.toml      # Package configuration
```

## 核心概念深入

### 为什么需要"进化"而非"优化"？

传统量化交易强调策略的稳定性和可解释性，往往通过超参数优化（hyperparameter tuning）来寻找最佳配置。但这种方法存在固有局限：

1. **过拟合风险**：基于历史数据优化的参数在未来可能失效
2. **制度性变化**：市场微观结构、监管政策、参与者构成都在不断演化
3. **黑天鹅事件**：罕见事件无法在历史数据中充分体现

EvoTrader 采用的"进化"范式，核心在于让系统保持**持续适应能力**，而非追求某个时点的最优解。通过三维反馈机制，系统能够：
- 在市场制度变化时自动调整策略权重
- 在新型市场行为出现时快速学习
- 在罕见事件后更新风险认知

### 智能体之间的"涌现智能"

EvoTrader 的多智能体设计不仅仅是为了"分工"，更重要的是为了创造**涌现现象**（emergence）。

当不同视角的分析师同时工作时，可能会出现单个智能体无法产生的洞察：
- 技术分析师发现价格突破，但基本面分析师指出财务恶化，Portfolio Manager 可能选择观望
- 估值分析师认为严重低估，情绪分析师发现内部人增持，形成强烈的买入信号
- 多个分析师的分歧本身就是重要信号，提示市场不确定性

这种"群体智慧"的涌现，正是 EvoTrader 相比单一模型策略的本质优势。

### 记忆系统的哲学

传统机器学习中，模型的"记忆"体现为参数矩阵的权重。但这种记忆有两个问题：
1. **不可解释**：无法理解模型"记住"了什么
2. **难以修正**：无法精确删除某个错误的记忆

EvoTrader 的记忆系统采用了显式的、语义化的记忆存储：
- 每条记忆都是可读的文本片段
- 可以通过语义检索找到相关记忆
- 可以精确删除或修正错误的记忆

这使得系统的学习过程变得透明和可控，符合金融场景对可解释性的要求。

## 未来规划

### 即将实现的功能

- **更丰富的风险控制策略**：VaR、CVaR、压力测试等
- **多资产类别支持**：期货、期权、固定收益等
- **更高级的记忆检索**：时序记忆、因果推理、反事实分析
- **自动化的Prompt进化**：让Prompt本身也参与进化循环
- **分布式回测**：支持大规模并行回测和参数搜索

### 研究方向

- **智能体的元学习能力**：让系统学会"如何学习"
- **对抗性训练**：引入专门寻找策略漏洞的"红队"智能体
- **跨市场知识迁移**：在A股学到的经验能否迁移到美股？
- **人机协作模式**：人类交易员与AI智能体的最佳协作方式

## 贡献指南

我们欢迎各种形式的贡献：

- **代码贡献**：新的分析工具、智能体角色、记忆机制等
- **Bug报告**：通过Issue提交发现的问题
- **功能建议**：分享你的想法和需求
- **文档改进**：帮助完善文档和示例

请参考 `CONTRIBUTING.md`（即将添加）了解详细的贡献流程。

## 许可证

本项目采用 MIT 许可证。详见 LICENSE 文件。

## 致谢

EvoTrader 的开发受到以下研究和项目的启发：

- OpenAI的多智能体协作研究
- DeepMind在强化学习领域的工作
- 对冲基金行业的最佳实践
- 开源量化交易社区的贡献

## 联系方式

- **问题和讨论**：请使用 GitHub Issues
- **邮件**：[待添加]
- **社区交流**：[待添加]

---

**注意**：EvoTrader 是一个研究和教育项目。在实际资金交易前，请务必进行充分的测试和风险评估。历史表现不代表未来收益，投资有风险。
