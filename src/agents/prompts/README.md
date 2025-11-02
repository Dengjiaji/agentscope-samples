# Agent Prompts 目录说明

## 📁 目录结构

```
prompts/
├── analyst/           # 分析师 Agent Prompts
├── portfolio_manager/ # 投资组合管理 Agent Prompts  
├── risk_manager/      # 风险管理 Agent Prompts
├── custom/            # 自定义 Agent Prompts
└── README.md          # 本文档
```

## 🔑 Prompt 格式说明

本项目支持两种 Prompt 格式，根据使用场景选择：

### 格式 1: PromptLoader 格式（推荐用于新 Prompts）

**变量语法**: `{{ variable }}`

**适用场景**:
- 通过 `PromptLoader` 加载的 prompts
- 需要在加载时就填充所有变量的场景
- 包含 JSON 示例的 prompts

**示例**:
```markdown
You are a professional {{ analyst_persona }} analyzing {{ ticker }}.

Your task is to {{ task_description }}.
```

**加载方式**:
```python
from src.agents.prompt_loader import get_prompt_loader

loader = get_prompt_loader()
prompt = loader.load_prompt("analyst", "tool_selection", {
    "analyst_persona": "Fundamental Analyst",
    "ticker": "AAPL",
    "task_description": "Evaluate fundamentals"
})
```

**特点**:
- ✅ 自动转义 JSON 代码块中的大括号
- ✅ 简单的字符串替换，无外部依赖
- ✅ 适合包含示例 JSON 的 prompts

**当前使用此格式的文件**:
- `analyst/tool_selection.md`
- `analyst/tool_synthesis.md`
- `portfolio_manager/direction_decision_*.md`
- `portfolio_manager/portfolio_decision_*.md`

---

### 格式 2: LangChain 格式（用于与 LangChain 集成）

**变量语法**: `{variable}`

**适用场景**:
- 直接与 `ChatPromptTemplate.from_messages()` 一起使用
- 需要 LangChain 的高级功能（如 partial variables）
- 已有的 LangChain 代码迁移

**示例**:
```markdown
You are a professional {analyst_name} with expertise in {specialty}.

Analysis Focus: {analysis_focus}
```

**加载方式**:
```python
from langchain_core.prompts import ChatPromptTemplate
from pathlib import Path

# 直接读取文件
prompts_dir = Path(__file__).parent / "prompts" / "analyst"
with open(prompts_dir / "second_round_system.md") as f:
    system_template = f.read()

# 创建 LangChain 模板
template = ChatPromptTemplate.from_messages([
    ("system", system_template)
])

# 使用 LangChain 的 format_messages
prompt = template.format_messages(
    analyst_name="Technical Analyst",
    specialty="Chart patterns"
)
```

**特点**:
- ✅ 完全兼容 LangChain 生态
- ✅ 支持 LangChain 的高级功能
- ⚠️ 需要手动处理 JSON 示例中的大括号转义

**当前使用此格式的文件**:
- `analyst/second_round_system.md`
- `analyst/second_round_human.md`

---

## 📝 最佳实践

### 1. 选择合适的格式

**使用 PromptLoader 格式（`{{ }}`）当:**
- ✅ 创建新的 prompt 文件
- ✅ Prompt 中包含 JSON 示例
- ✅ 不需要 LangChain 的高级功能

**使用 LangChain 格式（`{ }`）当:**
- ✅ 需要与现有 LangChain 代码集成
- ✅ 需要使用 partial variables
- ✅ 需要 LangChain 的其他高级功能

### 2. JSON 示例处理

**PromptLoader 格式**: 自动处理
```markdown
Output format:
\```json
{
  "result": "value"
}
\```
```

**LangChain 格式**: 需要转义
```markdown
Output format:
\```json
{{
  "result": "value"
}}
\```
```

### 3. 文件组织

```
prompts/
└── agent_type/
    ├── prompt_name.md        # Prompt 文件
    ├── config_name.yaml      # 配置文件
    └── README.md             # 说明文档（可选）
```

## 🔧 示例

### 示例 1: 创建新的 Analyst Prompt

**文件**: `prompts/analyst/my_analysis.md`
```markdown
You are a {{ analyst_type }} analyzing {{ ticker }}.

Task: {{ task }}

Output format:
\```json
{
  "signal": "bullish/bearish/neutral",
  "confidence": 0-100
}
\```
```

**使用**:
```python
from src.agents.prompt_loader import get_prompt_loader

loader = get_prompt_loader()
prompt = loader.load_prompt("analyst", "my_analysis", {
    "analyst_type": "Growth Analyst",
    "ticker": "NVDA",
    "task": "Evaluate growth potential"
})
# JSON 大括号会自动转义
```

### 示例 2: 使用 LangChain 格式

**文件**: `prompts/analyst/langchain_prompt.md`
```markdown
You are {role} analyzing {ticker}.

Previous analysis: {previous_result}
```

**使用**:
```python
from langchain_core.prompts import ChatPromptTemplate
from pathlib import Path

prompts_dir = Path("src/agents/prompts/analyst")
with open(prompts_dir / "langchain_prompt.md") as f:
    template_str = f.read()

template = ChatPromptTemplate.from_messages([
    ("human", template_str)
])

prompt = template.format_messages(
    role="Senior Analyst",
    ticker="AAPL",
    previous_result="Bullish"
)
```

## 📚 相关文档

- [BaseAgent 文档](../base_agent.py)
- [PromptLoader 文档](../prompt_loader.py)
- [Agent 重构完成总结](../REFACTORING_COMPLETED.md)

## 🆘 常见问题

### Q: 为什么有两种格式？
**A**: 
- PromptLoader 格式（`{{ }}`）: 我们的自定义实现，简单且自动处理 JSON
- LangChain 格式（`{ }`）: 标准 LangChain 格式，用于向后兼容

### Q: 我应该使用哪种格式？
**A**: 对于新的 prompts，推荐使用 PromptLoader 格式（`{{ }}`），它更简单且自动处理 JSON 转义。

### Q: 如何转义 JSON 示例？
**A**: 
- PromptLoader 格式: 自动处理，无需手动转义
- LangChain 格式: 使用 `{{` 和 `}}` 转义

### Q: 可以混用两种格式吗？
**A**: 不推荐。每个 prompt 文件应该只使用一种格式。同一个 agent 类型的 prompts 最好使用相同格式。

---

**最后更新**: 2025-01-02  
**维护者**: AI Investment Analysis Team


