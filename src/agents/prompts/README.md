# Agent Prompts 目录说明

## 📁 目录结构

```
prompts/
├── analyst/           # 分析师 Agent Prompts
├── portfolio_manager/ # 投资组合管理 Agent Prompts  
├── risk_manager/      # 风险管理 Agent Prompts
├── reflection/        # 自我反思 Prompts
├── custom/            # 自定义 Agent Prompts
└── README.md          # 本文档
```

## 🔑 Prompt 格式说明

本项目使用 **PromptLoader** 格式管理所有 prompts。

### 变量语法

使用双大括号 `{{ variable }}` 表示变量占位符。

**示例**:
```markdown
You are a professional {{ analyst_persona }} analyzing {{ ticker }}.

Your task is to {{ task_description }}.
```

### 加载方式

```python
from src.agents.prompt_loader import get_prompt_loader

loader = get_prompt_loader()
prompt = loader.load_prompt("analyst", "tool_selection", {
    "analyst_persona": "Fundamental Analyst",
    "ticker": "AAPL",
    "task_description": "Evaluate fundamentals"
})
```

### 特点

- ✅ 自动转义 JSON 代码块中的大括号
- ✅ 简单的字符串替换，无外部依赖
- ✅ 适合包含示例 JSON 的 prompts
- ✅ 统一的变量格式

## 📝 JSON 示例处理

当 prompt 中包含 JSON 示例时，使用特殊占位符：

```markdown
Output format:

\`\`\`json
{JSON_OPEN}
  "field": "value",
  "nested": {JSON_OPEN}
    "key": "value"
  {JSON_CLOSE}
{JSON_CLOSE}
\`\`\`
```

PromptLoader 会自动将这些占位符转换为实际的大括号。

## 🗂️ Prompt 文件组织

### 按 Agent 类型分类

每个 Agent 类型都有自己的目录：

```
analyst/
├── personas.yaml          # 分析师角色定义
├── tool_selection.md      # 工具选择 prompt
├── tool_synthesis.md      # 结果综合 prompt
└── second_round_*.md      # 第二轮分析 prompts

portfolio_manager/
├── direction_decision_*.md   # 方向决策 prompts
└── portfolio_decision_*.md   # 组合决策 prompts

reflection/
├── analyst_reflection_system.md  # 分析师反思 prompt
└── pm_reflection_system.md       # PM 反思 prompt
```

### 命名规范

- 使用小写字母和下划线
- 使用 `.md` 扩展名（Markdown 格式）
- 使用 `.yaml` 扩展名（配置文件）
- 描述性的文件名，反映 prompt 的用途

## 💡 使用示例

### 示例 1: 加载简单 Prompt

**文件**: `prompts/analyst/tool_selection.md`
```markdown
You are {{ analyst_persona }}.

Analyze {{ ticker }} and select appropriate tools.
```

**使用**:
```python
from src.agents.prompt_loader import get_prompt_loader

loader = get_prompt_loader()
prompt = loader.load_prompt(
    "analyst", 
    "tool_selection",
    {
        "analyst_persona": "Technical Analyst",
        "ticker": "AAPL"
    }
)
print(prompt)
# 输出: You are Technical Analyst.\n\nAnalyze AAPL and select appropriate tools.
```

### 示例 2: 包含 JSON 示例的 Prompt

**文件**: `prompts/analyst/output_format.md`
```markdown
Return your analysis in JSON format:

\`\`\`json
{JSON_OPEN}
  "signal": "BUY|SELL|HOLD",
  "confidence": 85
{JSON_CLOSE}
\`\`\`
```

**使用**:
```python
loader = get_prompt_loader()
prompt = loader.load_prompt("analyst", "output_format")
# JSON 占位符会自动转换为 { 和 }
```

## 🎯 最佳实践

### 1. 变量命名

使用清晰、描述性的变量名：

✅ **好的命名**:
```markdown
{{ analyst_persona }}
{{ analysis_objective }}
{{ ticker_symbol }}
```

❌ **不好的命名**:
```markdown
{{ x }}
{{ temp }}
{{ var1 }}
```

### 2. Prompt 结构

保持清晰的结构：

```markdown
# 角色定义
You are {{ role }}.

# 任务说明
Your task is to {{ task }}.

# 输入数据
Input: {{ input_data }}

# 输出格式
Output format:
...
```

### 3. 可复用性

将通用的 prompt 模板化：

```markdown
# 通用分析模板
Analyst: {{ analyst_type }}
Ticker: {{ ticker }}
Date: {{ date }}

# 具体分析内容
{{ analysis_content }}
```

### 4. 文档注释

在 prompt 文件顶部添加注释说明用途：

```markdown
<!--
Purpose: 分析师工具选择 prompt
Variables:
  - analyst_persona: 分析师类型
  - ticker: 股票代码
  - market_conditions: 市场条件
-->

You are a {{ analyst_persona }}...
```

## 📚 常见问题

### Q: 如何在 prompt 中使用大括号？

**A**: 在普通文本中直接使用 `{` 和 `}` 会被识别为变量。如果需要字面量大括号（如 JSON 示例），使用 `{JSON_OPEN}` 和 `{JSON_CLOSE}` 占位符。

### Q: 可以嵌套目录吗？

**A**: 可以。PromptLoader 支持多级目录结构，例如 `prompts/analyst/advanced/deep_analysis.md`。

### Q: 如何处理多语言 prompts？

**A**: 可以创建子目录，如 `prompts/analyst/en/` 和 `prompts/analyst/zh/`，或使用文件后缀 `tool_selection_en.md` 和 `tool_selection_zh.md`。

### Q: Prompt 文件可以包含什么内容？

**A**: Prompt 文件是纯文本 Markdown 格式，可以包含：
- 普通文本
- 变量占位符 `{{ variable }}`
- Markdown 格式（标题、列表等）
- 代码块（包括 JSON 示例）
- 注释（HTML 注释格式 `<!-- ... -->`）

## 🔄 更新 Prompts

修改 prompt 文件后，无需重启程序：

1. 直接编辑 `.md` 文件
2. 保存文件
3. 下次调用 `load_prompt()` 时会自动加载最新版本

PromptLoader 每次都会重新读取文件，方便快速迭代和调试。

## 🚀 进阶用法

### 条件内容

虽然 PromptLoader 本身不支持条件逻辑，但可以在 Python 代码中构建：

```python
# 根据条件选择不同的内容
if is_detailed:
    analysis_instructions = loader.load_prompt("analyst", "detailed_analysis")
else:
    analysis_instructions = loader.load_prompt("analyst", "quick_analysis")

# 组合到最终 prompt
final_prompt = loader.load_prompt("analyst", "base_template", {
    "instructions": analysis_instructions
})
```

### 组合多个 Prompts

```python
role_prompt = loader.load_prompt("analyst", "role_definition", {...})
task_prompt = loader.load_prompt("analyst", "task_description", {...})
format_prompt = loader.load_prompt("analyst", "output_format")

combined = f"{role_prompt}\n\n{task_prompt}\n\n{format_prompt}"
```

---

**版本**: 1.0  
**最后更新**: 2025-01-05  
**维护者**: Trading Intelligence Team
