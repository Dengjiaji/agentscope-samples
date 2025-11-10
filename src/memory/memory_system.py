import os
from typing import Dict, Any

# from live_trading_thinking_fund import LLM_AVAILABLE, MEMORY_TOOLS_AVAILABLE
from src.llm.models import get_model


MEMORY_AVAILABLE = True
LLM_AVAILABLE = True
MEMORY_TOOLS_AVAILABLE = True


class LLMMemoryDecisionSystem:
    """基于LLM的记忆管理决策系统"""

    def __init__(self):
        self.memory_tools = []

        if LLM_AVAILABLE and MEMORY_TOOLS_AVAILABLE:
            model_name = os.getenv('MEMORY_LLM_MODEL', 'gpt-4o-mini')
            model_provider_str = os.getenv('MEMORY_LLM_PROVIDER', 'OPENAI')
            from src.llm.models import ModelProvider

            # 转换为ModelProvider枚举
            if hasattr(ModelProvider, model_provider_str):
                model_provider = getattr(ModelProvider, model_provider_str)
            else:
                print(f"未知的模型提供商: {model_provider_str}，使用默认OPENAI")
                model_provider = ModelProvider.OPENAI

            api_keys = {}
            if model_provider == ModelProvider.OPENAI:
                api_keys['OPENAI_API_KEY'] = os.getenv('OPENAI_API_KEY')
            elif model_provider == ModelProvider.ANTHROPIC:
                api_keys['ANTHROPIC_API_KEY'] = os.getenv('ANTHROPIC_API_KEY')

            # 获取记忆管理工具
            from src.tools.memory_tools import get_memory_tools
            self.memory_tools = get_memory_tools()
            # 使用 AgentScope 模型
            self.llm = get_model(model_name, model_provider, api_keys)
            # 注意：AgentScope 不使用 bind_tools，而是通过 function calling 或直接调用
            # 这里保持引用以便后续迁移
            self.llm_with_tools = self.llm
            self.llm_available = True
            print(f"LLM记忆决策系统已启用（{model_provider_str}: {model_name}）")
            print(f"已加载 {len(self.memory_tools)} 个记忆管理工具")

    def generate_memory_decision_prompt(self, performance_data: Dict[str, Any], date: str) -> str:
        """生成LLM记忆决策的prompt"""

        prompt = f"""你是一个专业的Portfolio Manager，负责管理分析师团队的记忆系统。基于{date}的交易复盘结果，请分析分析师的表现并决定是否需要使用记忆管理工具。

# 复盘数据分析

## 分析师信号 vs 实际结果对比

### Portfolio Manager最终决策:
"""

        pm_signals = performance_data.get('pm_signals', {})
        actual_returns = performance_data.get('actual_returns', {})
        analyst_signals = performance_data.get('analyst_signals', {})
        tickers = performance_data.get('tickers', [])

        # 添加PM信号和实际结果
        for ticker in tickers:
            pm_signal = pm_signals.get(ticker, {})
            actual_return = actual_returns.get(ticker, 0)

            prompt += f"\n{ticker}:"
            prompt += f"\n  PM决策: {pm_signal.get('signal', 'N/A')} (置信度: {pm_signal.get('confidence', 'N/A')}%)"
            prompt += f"\n  实际收益: {actual_return:.2%}"

        prompt += "\n\n### 各分析师的预测表现:"

        # 添加分析师表现
        for analyst, signals in analyst_signals.items():
            prompt += f"\n\n**{analyst}:**"
            total_count = 0
            for ticker in tickers:
                if ticker in signals and ticker in actual_returns:
                    analyst_signal = signals[ticker]
                    actual_return = actual_returns[ticker]
                    total_count += 1

                    prompt += f"\n  {ticker}: 预测 {analyst_signal}, 实际 {actual_return:.2%}"

        prompt += f"""

# 记忆管理决策指导

请分析各分析师的表现，并决定是否需要执行记忆管理操作：

- **表现极差** (多个严重错误)：使用search_and_delete_analyst_memory删除严重错误记忆
- **表现不佳** (一个或者多个微小错误)：使用search_and_update_analyst_memory更新错误记忆
- **表现优秀或正常**：无需操作，直接说明分析结果即可

可用的记忆管理工具：
1. **search_and_update_analyst_memory**: 修正更新分析师的相关记忆内容
2. **search_and_delete_analyst_memory**: 删除分析师的相关记忆内容

请先分析各分析师的表现，然后如果需要记忆操作，直接调用相应的工具。如果不需要任何操作，请说明你的分析结果。
"""

        return prompt

    def make_llm_memory_decision_with_tools(self, performance_data: Dict[str, Any], date: str) -> Dict[str, Any]:
        """使用LLM进行记忆管理决策"""

        if not getattr(self, "llm_available", False):
            print("⚠️ LLM不可用，跳过记忆管理")
            return {'status': 'skipped', 'reason': 'LLM不可用'}

        try:
            # 生成prompt
            prompt = self.generate_memory_decision_prompt(performance_data, date)

            print(f"\n🤖 正在请求LLM进行记忆管理决策...")
            print(f"📝 Prompt长度: {len(prompt)} 字符")

            # 调用 LLM（使用 AgentScope 格式）
            messages = [{"role": "user", "content": prompt}]
            response = self.llm(messages)

            # 将响应转换为兼容格式
            class ResponseWrapper:
                def __init__(self, content):
                    self.content = content
                    self.tool_calls = None  # AgentScope 目前不支持自动 tool calling

            response = ResponseWrapper(response.get("content", ""))

            print(f"📥 LLM响应类型: {type(response)}")

            # 检查是否有工具调用
            tool_calls = []
            if hasattr(response, 'tool_calls') and response.tool_calls:
                tool_calls = response.tool_calls
                print(f"🛠️ LLM决定执行 {len(tool_calls)} 个工具调用")

                # 执行工具调用
                execution_results = []
                for tool_call in tool_calls:
                    tool_name = tool_call['name']
                    tool_args = tool_call['args']

                    print(f"  📞 调用工具: {tool_name}")
                    print(f"     参数: {tool_args}")

                    # 直接调用对应的工具函数
                    tool_function = next(
                        (tool for tool in self.memory_tools if tool.name == tool_name),
                        None
                    )

                    if tool_function:
                        result = tool_function.invoke(tool_args)
                        execution_results.append({
                            'tool_name': tool_name,
                            'args': tool_args,
                            'result': result
                        })
                    else:
                        print(f"    ❌ 未找到工具: {tool_name}")
                        execution_results.append({
                            'tool_name': tool_name,
                            'args': tool_args,
                            'result': {'status': 'failed', 'error': f'Tool not found: {tool_name}'}
                        })

                return {
                    'status': 'success',
                    'mode': 'operations_executed',
                    'operations_count': len(tool_calls),
                    'execution_results': execution_results,
                    'llm_reasoning': response.content,
                    'date': date
                }
            else:
                # 没有工具调用，LLM可能认为不需要操作
                reasoning = response.content if hasattr(response, 'content') else str(response)
                print(f"💭 LLM分析: {reasoning}")

                return {
                    'status': 'success',
                    'mode': 'no_action',
                    'reasoning': reasoning,
                    'date': date
                }

        except Exception as e:
            print(f"❌ LLM记忆管理决策失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                'status': 'failed',
                'error': str(e),
                'date': date
            }
