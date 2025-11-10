import os
from typing import Dict, Any

from src.llm.models import get_model
from src.tools.memory_tools import create_memory_toolkit
from src.agents.prompt_loader import PromptLoader

MEMORY_AVAILABLE = True
LLM_AVAILABLE = True
MEMORY_TOOLS_AVAILABLE = True


class LLMMemoryDecisionSystem:
    """基于LLM的记忆管理决策系统"""

    def __init__(self):
        self.toolkit = None
        self.prompt_loader = PromptLoader()

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

            # 创建记忆管理工具包（AgentScope Toolkit）
            from src.tools.memory_tools import create_memory_toolkit
            self.toolkit = create_memory_toolkit()
            # 使用 AgentScope 模型
            self.llm = get_model(model_name, model_provider, api_keys)
            self.llm_with_tools = self.llm
            self.llm_available = True
            print(f"LLM记忆决策系统已启用（{model_provider_str}: {model_name}）")
            print(f"已加载 {len(self.toolkit.tools)} 个记忆管理工具")

    def generate_memory_decision_prompt(self, performance_data: Dict[str, Any], date: str) -> str:
        """生成LLM记忆决策的prompt"""
        pm_signals = performance_data.get('pm_signals', {})
        actual_returns = performance_data.get('actual_returns', {})
        analyst_signals = performance_data.get('analyst_signals', {})
        tickers = performance_data.get('tickers', [])

        pm_signals_section = self._build_pm_signals_section(tickers, pm_signals, actual_returns)
        analyst_signals_section = self._build_analyst_signals_section(analyst_signals, tickers, actual_returns)

        return self.prompt_loader.load_prompt(
            agent_type="memory",
            prompt_name="memory_decision",
            variables={
                "date": date,
                "pm_signals_section": pm_signals_section,
                "analyst_signals_section": analyst_signals_section,
            }
        )

    def _build_pm_signals_section(self, tickers, pm_signals, actual_returns) -> str:
        """构建PM信号部分"""
        lines = []
        for ticker in tickers:
            pm_signal = pm_signals.get(ticker, {})
            actual_return = actual_returns.get(ticker, 0)
            lines.append(f"\n{ticker}:")
            lines.append(f"\n  PM决策: {pm_signal.get('signal', 'N/A')} (置信度: {pm_signal.get('confidence', 'N/A')}%)")
            lines.append(f"\n  实际收益: {actual_return:.2%}")
        return "".join(lines)

    def _build_analyst_signals_section(self, analyst_signals, tickers, actual_returns) -> str:
        """构建分析师信号部分"""
        lines = []
        for analyst, signals in analyst_signals.items():
            lines.append(f"\n\n**{analyst}:**")
            for ticker in tickers:
                if ticker in signals and ticker in actual_returns:
                    analyst_signal = signals[ticker]
                    actual_return = actual_returns[ticker]
                    lines.append(f"\n  {ticker}: 预测 {analyst_signal}, 实际 {actual_return:.2%}")
        return "".join(lines)

    def _parse_json_response(self, response_content: str) -> dict:
        """解析 JSON 响应（可能带有 ```json``` 包裹）"""
        import json
        json_start = response_content.find("{")
        json_end = response_content.rfind("}") + 1
        if json_start != -1 and json_end > json_start:
            json_str = response_content[json_start:json_end]
            return json.loads(json_str)
        return json.loads(response_content)

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
            print(f"   📝 Prompt:{prompt}")
            messages = [{"role": "user", "content": prompt}]
            response = self.llm(messages)
            response["content"]

            print(f"   📥 LLM响应:{response}")

            # 解析 JSON 响应
            decision_data = self._parse_json_response(response["content"])
            reasoning = decision_data.get("reflection_summary", "")
            need_tool = decision_data.get("need_tool", False)
            
            # 执行工具调用
            execution_results = []
            if need_tool and "selected_tool" in decision_data:
                selected_tools = decision_data["selected_tool"]
                if not isinstance(selected_tools, list):
                    selected_tools = [selected_tools]
                
                print(f"🛠️ LLM决定执行 {len(selected_tools)} 个工具调用")
                
                for tool_selection in selected_tools:
                    tool_name = tool_selection.get("tool_name")
                    tool_reason = tool_selection.get("reason", "")
                    tool_params = tool_selection.get("parameters", {})
                    
                    print(f"  📞 调用工具: {tool_name}")
                    print(f"     选择理由: {tool_reason}")
                    print(f"     参数: {tool_params}")
                    
                    try:
                        if tool_name in self.toolkit.tools:
                            tool_func = self.toolkit.tools[tool_name].original_func
                            result = tool_func(**tool_params)
                        else:
                            result = {'status': 'failed', 'error': f'Tool not found: {tool_name}'}
                        
                        execution_results.append({
                            'tool_name': tool_name,
                            'selection_reason': tool_reason,
                            'args': tool_params,
                            'result': result
                        })
                        print(f"  ✅ 工具执行完成: {result.get('status', 'unknown')}")
                    except Exception as e:
                        print(f"  ❌ 工具执行失败: {e}")
                        execution_results.append({
                            'tool_name': tool_name,
                            'selection_reason': tool_reason,
                            'args': tool_params,
                            'error': str(e)
                        })
                
                return {
                    'status': 'success',
                    'mode': 'operations_executed',
                    'operations_count': len(execution_results),
                    'execution_results': execution_results,
                    'llm_reasoning': reasoning,
                    'date': date
                }
            else:
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
