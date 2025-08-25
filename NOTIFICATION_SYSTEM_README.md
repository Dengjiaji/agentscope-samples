# AI投资分析系统 - 通知机制

这个系统为你的四个核心分析师（基本面、情绪、技术、估值）增加了智能通知机制，让agents能够自主决策是否与其他agents分享重要信息。

## 🏗️ 架构设计

### 核心组件

1. **NotificationSystem** - 全局通知管理器
2. **NotificationMemory** - 每个agent的通知记忆
3. **智能决策机制** - 使用LLM判断是否发送通知
4. **主程序集成** - 完整的分析流程

### 工作流程

```
[Agent分析] → [获取结果] → [LLM决策] → [发送通知?] → [其他Agent接收] → [更新记忆]
```

## 📁 文件结构

```
IA/
├── src/
│   └── communication/
│       ├── __init__.py
│       └── notification_system.py     # 核心通知系统
├── main_with_notifications.py         # 主程序
├── test_notification_system.py        # 测试脚本
└── NOTIFICATION_SYSTEM_README.md      # 本文档
```

## 🚀 快速开始

### 1. 环境准备

确保你已经设置了环境变量：
```bash
# .env 文件
FINANCIAL_DATASETS_API_KEY=your_key_here
OPENAI_API_KEY=your_openai_key_here
MODEL_NAME=gpt-3.5-turbo
```

### 2. 运行测试

先测试通知系统是否正常工作：
```bash
cd /root/wuyue.wy/Project/IA
python test_notification_system.py
```

### 3. 运行主程序

```bash
# 直接运行（默认并行模式）
python main_with_notifications.py

# 使用串行模式
python main_with_notifications.py --sequential

# 交互式模式
python main_with_notifications.py --interactive

# 并行性能测试
python test_parallel_performance.py
```

## ⚡ 并行执行机制

### 🚀 性能提升

系统现在支持**并行执行**四个分析师，相比串行执行可以显著提升性能：

- **串行执行**: 分析师按顺序执行，总时间 = 所有分析师时间之和
- **并行执行**: 分析师同时执行，总时间 ≈ 最慢分析师的时间

### 🔧 技术实现

```python
# 并行执行（默认）
results = engine.run_full_analysis(tickers, start_date, end_date, parallel=True)

# 串行执行
results = engine.run_full_analysis(tickers, start_date, end_date, parallel=False)
```

### 🛡️ 线程安全保护

- **状态隔离**: 每个分析师使用独立的状态副本，避免并发冲突
- **通知同步**: 使用线程锁保护通知系统的全局状态
- **错误处理**: 单个分析师失败不影响其他分析师

### 📊 性能测试

```bash
# 运行性能对比测试
python test_parallel_performance.py

# 快速功能验证
python test_parallel_performance.py --simple

# 完整性能对比
python test_parallel_performance.py --full
```

## 🔧 通知机制详解

### 通知数据结构

```python
@dataclass
class Notification:
    id: str                    # 唯一标识
    sender_agent: str          # 发送者
    timestamp: datetime        # 时间戳
    content: str              # 通知内容
    urgency: str              # 紧急程度: low/medium/high/critical
    category: str             # 类别: market_alert/risk_warning/opportunity/policy_update/general
```

### 智能决策机制

每个agent分析完成后，系统会：

1. **收集上下文** - 分析结果 + 历史通知记忆
2. **LLM判断** - 调用大模型判断是否需要通知
3. **执行决策** - 如果需要，则广播给所有其他agents
4. **更新记忆** - 所有相关agents的记忆都会更新

### 决策prompt示例

```
你是一个fundamentals_analyst，刚刚完成了分析并得到以下结果：

分析结果：
{analysis_result}

你最近收到的通知：
{recent_notifications}

请判断是否需要向其他分析师发送通知...
```

## 📊 使用示例

### 基本使用

```python
from main_with_notifications import InvestmentAnalysisEngine

# 创建分析引擎
engine = InvestmentAnalysisEngine()

# 运行分析
results = engine.run_full_analysis(
    tickers=["AAPL", "MSFT"],
    start_date="2024-01-01", 
    end_date="2024-03-01"
)

# 查看结果
engine.print_session_summary(results)
```

### 手动通知测试

```python
from src.communication.notification_system import notification_system

# 注册agents
notification_system.register_agent("test_agent")

# 发送通知
notification_id = notification_system.broadcast_notification(
    sender_agent="fundamentals_analyst",
    content="发现重要投资机会",
    urgency="high",
    category="opportunity"
)
```

## 🎯 通知类型

| 类别 | 描述 | 示例 |
|------|------|------|
| `market_alert` | 市场重大变化 | "市场突然大幅波动" |
| `risk_warning` | 风险预警 | "检测到高风险信号" |
| `opportunity` | 投资机会 | "发现被低估的优质股票" |
| `policy_update` | 政策变化 | "央行政策调整影响" |
| `general` | 一般信息 | "常规分析更新" |

## ⚙️ 配置选项

### 紧急程度设置

- `low` - 一般信息，不紧急
- `medium` - 中等重要性（默认）
- `high` - 重要信息，需要关注
- `critical` - 紧急情况，立即处理

### 记忆管理

```python
# 获取最近24小时的通知
recent = agent_memory.get_recent_notifications(24)

# 按紧急程度筛选
critical_notifications = agent_memory.get_notifications_by_urgency("critical")

# 清理7天前的旧通知
agent_memory.clear_old_notifications(7)
```

## 🔍 调试和监控

### 查看通知历史

```python
# 全局通知
for notification in notification_system.global_notifications:
    print(f"{notification.timestamp}: {notification.sender_agent} -> {notification.content}")

# 特定agent的记忆
memory = notification_system.get_agent_memory("fundamentals_analyst")
for notification in memory.notifications:
    print(f"收到: {notification.content}")
```

### 日志文件

系统会自动生成日志文件：
- `investment_analysis.log` - 主程序日志
- 分析结果会保存为 `analysis_results_YYYYMMDD_HHMMSS.json`

## 🚀 扩展计划

当前实现的是**通知机制**，接下来可以扩展：

1. **辩论机制** - Agent间的一对一讨论
2. **会议机制** - 多Agent集体决策
3. **动态策略调整** - 基于通知历史优化策略
4. **情绪建模** - Agent的"个性"和"情绪"状态

## 🤝 贡献

这是一个模块化设计，你可以：
- 添加新的通知类型
- 改进LLM决策逻辑
- 优化记忆管理策略
- 扩展多Agent协作机制

## 📝 注意事项

1. **API限制** - 每次分析都会调用LLM，注意API配额
2. **记忆管理** - 定期清理旧通知避免内存溢出
3. **并发安全** - 当前版本未考虑并发，如需并发请添加锁机制
4. **错误处理** - LLM调用失败时会跳过通知，不影响主分析流程

## 🔄 第二轮分析机制

### 📋 **两轮分析流程**

系统现在支持完整的两轮分析机制：

1. **第一轮分析**
   - 四个agent独立分析，生成初始意见
   - 根据分析结果决定是否发送通知

2. **第二轮分析**
   - 基于第一轮的final_report进行修正
   - 每个agent收到：
     - `summary`: 第一轮分析总结
     - `analyst_signals`: 自己的第一轮结果
     - `notification_activity`: 通知活动情况
     - `pipeline_info`: 用户自定义的Pipeline信息

### 🔧 **自定义Pipeline信息**

通过修改 `pipeline_config_example.py` 添加：
- 市场观点
- 策略指导
- 外部观点
- 自定义备注

```python
pipeline_info = {
    "market_outlook": {
        "sentiment": "谨慎乐观",
        "key_events": ["美联储会议", "财报季"],
        "risk_factors": ["通胀", "地缘政治"]
    },
    "strategy_guidance": {
        "allocation_preference": "均衡配置",
        "sector_focus": ["科技", "医疗"],
        "risk_tolerance": "中等"
    }
}
```

## 🎉 总结

这个AI投资分析系统现在具备：

- 🧠 **智能判断** - 自动决定何时分享信息
- 📢 **主动通信** - 向其他agents广播重要发现
- 🔄 **两轮分析** - 基于通知和额外信息修正观点
- 🎯 **上下文感知** - 基于全面信息做出最终决策
- ⚡ **并行执行** - 支持高效的并行分析

这为构建更智能、更协作的多Agent投资决策系统奠定了基础！
