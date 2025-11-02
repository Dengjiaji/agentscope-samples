# Custom Agent Prompts

这个目录用于存放自定义 Agent 的 Prompt 文件。

## 如何创建自定义 Agent

### 方法 1：通过继承 BaseAgent

```python
from src.agents.base_agent import BaseAgent
from src.graph.state import AgentState

class MyCustomAgent(BaseAgent):
    """自定义分析 Agent"""
    
    def __init__(self):
        super().__init__(
            agent_id="my_custom_agent",
            agent_type="custom",  # 对应 prompts/custom/ 目录
            config={"threshold": 0.7}
        )
    
    def execute(self, state: AgentState):
        # 加载自定义 prompt
        my_prompt = self.load_prompt("my_analysis", {
            "ticker": "AAPL",
            "parameter": self.config["threshold"]
        })
        
        # 执行自定义逻辑
        result = self._do_analysis(state, my_prompt)
        
        # 更新状态
        state["data"]["my_results"] = result
        
        return {
            "messages": state["messages"],
            "data": state["data"]
        }
    
    def _do_analysis(self, state, prompt):
        # 实现你的分析逻辑
        pass
```

### 方法 2：使用 Agent Registry 注册

```python
from src.agents.agent_registry import register_agent
from src.agents.base_agent import BaseAgent

@register_agent("momentum_analyst")
class MomentumAnalyst(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_id="momentum_analyst",
            agent_type="custom"
        )
    
    def execute(self, state):
        # 实现逻辑
        pass

# 使用
from src.agents.agent_registry import get_registry
agent = get_registry().create_agent("momentum_analyst")
```

## Prompt 文件示例

创建 `prompts/custom/my_analysis.md`:

```markdown
You are analyzing stock {ticker} with threshold {parameter}.

Please provide:
1. Analysis result
2. Confidence score
3. Reasoning

Output in JSON format.
```

创建 `prompts/custom/config.yaml`:

```yaml
my_agent:
  name: "My Custom Agent"
  parameters:
    threshold: 0.7
    lookback_days: 30
```

## 目录结构

```
prompts/custom/
├── README.md          # 本文件
├── my_analysis.md     # 你的 prompt 文件
└── config.yaml        # 你的配置文件
```

