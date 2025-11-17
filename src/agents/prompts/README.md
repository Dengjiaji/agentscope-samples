# Agent Prompts Directory Documentation

## 📁 Directory Structure

```
prompts/
├── analyst/           # Analyst Agent Prompts
├── portfolio_manager/ # Portfolio Management Agent Prompts  
├── risk_manager/      # Risk Management Agent Prompts
├── reflection/        # Self-reflection Prompts
├── custom/            # Custom Agent Prompts
└── README.md          # This document
```

## 🔑 Prompt Format Documentation

This project uses **PromptLoader** format to manage all prompts.

### Variable Syntax

Use double curly braces `{{ variable }}` to represent variable placeholders.

**Example**:
```markdown
You are a professional {{ analyst_persona }} analyzing {{ ticker }}.

Your task is to {{ task_description }}.
```

### Loading Method

```python
from src.agents.prompt_loader import get_prompt_loader

loader = get_prompt_loader()
prompt = loader.load_prompt("analyst", "tool_selection", {
    "analyst_persona": "Fundamental Analyst",
    "ticker": "AAPL",
    "task_description": "Evaluate fundamentals"
})
```

### Features

- ✅ Automatically escape curly braces in JSON code blocks
- ✅ Simple string replacement, no external dependencies
- ✅ Suitable for prompts containing example JSON
- ✅ Unified variable format

## 📝 JSON Example Handling

When prompts contain JSON examples, use special placeholders:

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

PromptLoader will automatically convert these placeholders to actual curly braces.

## 🗂️ Prompt File Organization

### Organized by Agent Type

Each Agent type has its own directory:

```
analyst/
├── personas.yaml          # Analyst role definitions
├── tool_selection.md      # Tool selection prompt
├── tool_synthesis.md      # Result synthesis prompt
└── second_round_*.md      # Second round analysis prompts

portfolio_manager/
├── direction_decision_*.md   # Direction decision prompts
└── portfolio_decision_*.md   # Portfolio decision prompts

reflection/
├── analyst_reflection_system.md  # Analyst reflection prompt
└── pm_reflection_system.md       # PM reflection prompt
```

### Naming Conventions

- Use lowercase letters and underscores
- Use `.md` extension (Markdown format)
- Use `.yaml` extension (configuration files)
- Descriptive file names that reflect the prompt's purpose

## 💡 Usage Examples

### Example 1: Loading Simple Prompt

**File**: `prompts/analyst/tool_selection.md`
```markdown
You are {{ analyst_persona }}.

Analyze {{ ticker }} and select appropriate tools.
```

**Usage**:
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
# Output: You are Technical Analyst.\n\nAnalyze AAPL and select appropriate tools.
```

### Example 2: Prompt with JSON Example

**File**: `prompts/analyst/output_format.md`
```markdown
Return your analysis in JSON format:

\`\`\`json
{JSON_OPEN}
  "signal": "BUY|SELL|HOLD",
  "confidence": 85
{JSON_CLOSE}
\`\`\`
```

**Usage**:
```python
loader = get_prompt_loader()
prompt = loader.load_prompt("analyst", "output_format")
# JSON placeholders will be automatically converted to { and }
```

## 🎯 Best Practices

### 1. Variable Naming

Use clear, descriptive variable names:

✅ **Good naming**:
```markdown
{{ analyst_persona }}
{{ analysis_objective }}
{{ ticker_symbol }}
```

❌ **Poor naming**:
```markdown
{{ x }}
{{ temp }}
{{ var1 }}
```

### 2. Prompt Structure

Maintain clear structure:

```markdown
# Role Definition
You are {{ role }}.

# Task Description
Your task is to {{ task }}.

# Input Data
Input: {{ input_data }}

# Output Format
Output format:
...
```

### 3. Reusability

Template common prompts:

```markdown
# General Analysis Template
Analyst: {{ analyst_type }}
Ticker: {{ ticker }}
Date: {{ date }}

# Specific Analysis Content
{{ analysis_content }}
```

### 4. Documentation Comments

Add comments at the top of prompt files to explain purpose:

```markdown
<!--
Purpose: Analyst tool selection prompt
Variables:
  - analyst_persona: Analyst type
  - ticker: Stock ticker
  - market_conditions: Market conditions
-->

You are a {{ analyst_persona }}...
```

## 📚 Frequently Asked Questions

### Q: How to use curly braces in prompts?

**A**: Using `{` and `}` directly in regular text will be recognized as variables. If you need literal curly braces (such as JSON examples), use `{JSON_OPEN}` and `{JSON_CLOSE}` placeholders.

### Q: Can I nest directories?

**A**: Yes. PromptLoader supports multi-level directory structures, for example `prompts/analyst/advanced/deep_analysis.md`.

### Q: How to handle multilingual prompts?

**A**: You can create subdirectories, such as `prompts/analyst/en/` and `prompts/analyst/zh/`, or use file suffixes `tool_selection_en.md` and `tool_selection_zh.md`.

### Q: What content can prompt files contain?

**A**: Prompt files are plain text Markdown format and can contain:
- Plain text
- Variable placeholders `{{ variable }}`
- Markdown formatting (headings, lists, etc.)
- Code blocks (including JSON examples)
- Comments (HTML comment format `<!-- ... -->`)

## 🔄 Updating Prompts

After modifying prompt files, no program restart is needed:

1. Directly edit `.md` files
2. Save the file
3. The latest version will be automatically loaded on the next call to `load_prompt()`

PromptLoader re-reads files each time, making it convenient for rapid iteration and debugging.

## 🚀 Advanced Usage

### Conditional Content

Although PromptLoader itself doesn't support conditional logic, you can build it in Python code:

```python
# Select different content based on conditions
if is_detailed:
    analysis_instructions = loader.load_prompt("analyst", "detailed_analysis")
else:
    analysis_instructions = loader.load_prompt("analyst", "quick_analysis")

# Combine into final prompt
final_prompt = loader.load_prompt("analyst", "base_template", {
    "instructions": analysis_instructions
})
```

### Combining Multiple Prompts

```python
role_prompt = loader.load_prompt("analyst", "role_definition", {...})
task_prompt = loader.load_prompt("analyst", "task_description", {...})
format_prompt = loader.load_prompt("analyst", "output_format")

combined = f"{role_prompt}\n\n{task_prompt}\n\n{format_prompt}"
```

---

**Version**: 1.0  
**Last Updated**: 2025-11-15
**Maintainer**: EvoTraders Team
