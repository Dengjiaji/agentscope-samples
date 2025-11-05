#!/usr/bin/env python3
"""
Agent自我复盘系统
每个分析师（包括PM）独立评估自己的表现并管理记忆
使用类似 analyst 分析阶段的 LLM 智能工具选择机制
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path
import pdb
# 尝试导入 AgentScope 相关模块
try:
    from src.graph.state import create_message
    from src.llm.agentscope_models import get_model, ModelProvider
    from src.tools.memory_management_tools import get_memory_tools
    LANGCHAIN_AVAILABLE = True  # 保持变量名以向后兼容
except ImportError as e:
    LANGCHAIN_AVAILABLE = False
    print(f"⚠️ LangChain模块未安装: {e}")

logger = logging.getLogger(__name__)


class MemoryOperationLogger:
    """记忆操作日志记录器"""
    
    def __init__(self, base_dir: str):
        """
        初始化日志记录器
        
        Args:
            base_dir: 基础目录（config_name）
        """
        self.log_dir = Path("logs_and_memory") / base_dir / "memory_operations"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # 当前日期的日志文件
        today = datetime.now().strftime("%Y%m%d")
        self.log_file = self.log_dir / f"memory_ops_{today}.jsonl"
    
    def log_operation(
        self,
        agent_id: str,
        operation_type: str,
        tool_name: str,
        args: Dict[str, Any],
        result: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ):
        """
        记录记忆操作
        
        Args:
            agent_id: Agent ID
            operation_type: 操作类型 (self_reflection, central_review)
            tool_name: 工具名称
            args: 工具参数
            result: 执行结果
            context: 额外上下文
        """
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'agent_id': agent_id,
            'operation_type': operation_type,
            'tool_name': tool_name,
            'args': args,
            'result': result,
            'context': context or {}
        }
        
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        except Exception as e:
            logger.error(f"记录日志失败: {e}")
    
    def get_today_operations(self, agent_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取今日的记忆操作记录
        
        Args:
            agent_id: 如果指定，只返回该Agent的操作
        
        Returns:
            操作记录列表
        """
        if not self.log_file.exists():
            return []
        
        operations = []
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        if agent_id is None or entry.get('agent_id') == agent_id:
                            operations.append(entry)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"读取日志失败: {e}")
        
        return operations


class AgentSelfReflectionSystem:
    """分析师自我复盘系统 - 使用 LLM 智能工具选择"""
    
    def __init__(
        self,
        agent_id: str,
        agent_role: str,
        base_dir: str = "mock",
        streamer=None
    ):
        """
        初始化自我复盘系统
        
        Args:
            agent_id: Agent ID（如 'technical_analyst' 或 'portfolio_manager'）
            agent_role: Agent角色描述（如 'Technical Analyst'）
            base_dir: 基础目录（config_name）
            streamer: 消息广播器（用于向前端发送memory操作消息）
        """
        self.agent_id = agent_id
        self.agent_role = agent_role
        self.base_dir = base_dir
        self.streamer = streamer
        
        # 初始化日志记录器
        self.logger_system = MemoryOperationLogger(base_dir)
        
        # 检查LangChain是否可用
        if not LANGCHAIN_AVAILABLE:
            logger.warning(f"{agent_role} 自我复盘系统初始化失败：LangChain不可用")
            self.llm_available = False
            return
        
        # 初始化LLM（使用与记忆管理相同的配置）
        try:
            model_name = os.getenv('MEMORY_LLM_MODEL', 'gpt-4o-mini')
            model_provider_str = os.getenv('MEMORY_LLM_PROVIDER', 'OPENAI')
            
            # 转换为ModelProvider枚举
            model_provider = getattr(ModelProvider, model_provider_str, ModelProvider.OPENAI)
            
            api_keys = {}
            if model_provider == ModelProvider.OPENAI:
                api_keys['OPENAI_API_KEY'] = os.getenv('OPENAI_API_KEY')
            elif model_provider == ModelProvider.ANTHROPIC:
                api_keys['ANTHROPIC_API_KEY'] = os.getenv('ANTHROPIC_API_KEY')
            
            # 创建记忆管理工具包（AgentScope Toolkit）
            from src.tools.memory_management_tools import create_memory_toolkit
            self.toolkit = create_memory_toolkit()
            
            # 设置memory工具的streamer
            if self.streamer:
                from src.tools.memory_management_tools import set_memory_tools_streamer
                set_memory_tools_streamer(self.streamer)
            
            # 使用 AgentScope 模型
            self.llm = get_model(model_name, model_provider, api_keys)
            
            # 构建可用工具的描述（类似 LLMToolSelector）
            self.available_memory_tools = self._build_tool_descriptions()
            
            self.llm_available = True
            print(f"✅ {agent_role} 自我复盘系统已初始化（LLM 智能工具选择模式）")
            print(f"   可用记忆工具: {', '.join(self.toolkit.list_functions())}")
            
        except Exception as e:
            logger.error(f"{agent_role} 自我复盘系统初始化失败: {e}")
            self.llm_available = False
    
    def _build_tool_descriptions(self) -> Dict[str, Dict[str, str]]:
        """构建记忆管理工具的描述信息"""
        return {
            "search_and_update_analyst_memory": {
                "name": "search_and_update_analyst_memory",
                "description": "搜索并更新分析师的记忆内容。适用于预测方向错误但不算离谱、分析方法需要微调优化的情况。",
                "when_to_use": "预测错误但不严重，需要修正分析方法或补充经验教训",
                "parameters": "query(搜索内容), memory_id(通常填'auto'), analyst_id(你的ID), new_content(新记忆), reason(更新原因)"
            },
            "search_and_delete_analyst_memory": {
                "name": "search_and_delete_analyst_memory",
                "description": "搜索并删除分析师的严重错误记忆。适用于连续严重预测错误、使用根本错误的分析逻辑的情况。",
                "when_to_use": "连续多次严重错误，分析逻辑存在根本性问题",
                "parameters": "query(搜索内容), memory_id(通常填'auto'), analyst_id(你的ID), reason(删除原因)"
            }
        }
    
    def generate_analyst_reflection_prompt(
        self,
        date: str,
        my_signals: Dict[str, Any],
        actual_returns: Dict[str, float],
        pm_decisions: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        生成分析师自我复盘的prompt
        
        Args:
            date: 交易日期
            my_signals: 我的预测信号
            actual_returns: 实际收益率
            pm_decisions: PM的最终决策
            context: 额外上下文
        """
        prompt = f"""你是一位专业的 {self.agent_role}，现在需要对 {date} 的分析表现进行自我复盘。

# 你的职责
作为 {self.agent_role}，你需要：
1. 客观评估自己的预测准确性
2. 分析预测错误的原因
3. 决定是否需要更新或删除错误的记忆
4. 总结经验教训，提升未来表现

# 今日复盘数据

## 你的预测信号
"""
        
        # 添加自己的信号
        for ticker, signal_data in my_signals.items():
            actual_return = actual_returns.get(ticker, 0)
            signal = signal_data.get('signal', 'N/A')
            confidence = signal_data.get('confidence', 'N/A')
            reasoning = signal_data.get('reasoning', '')
            
            # 判断预测是否正确
            is_correct = self._evaluate_prediction(signal, actual_return)
            status_emoji = "✅" if is_correct else "❌"
            
            prompt += f"""
{ticker}: {status_emoji}
  - 你的信号: {signal} (置信度: {confidence}%)
  - 你的理由: {reasoning[:200] if reasoning else 'N/A'}
  - 实际收益: {actual_return:.2%}
  - PM最终决策: {pm_decisions.get(ticker, {}).get('action', 'N/A')}
"""
        
        # 添加额外上下文
        if context:
            prompt += "\n## 额外上下文\n"
            if 'market_condition' in context:
                prompt += f"- 市场环境: {context['market_condition']}\n"
        
        prompt += f"""

# 自我复盘指导

请按以下标准评估自己的表现：

## 评估标准
1. **预测准确性**: 信号方向是否与实际收益一致？
2. **置信度校准**: 高置信度的预测是否更准确？
3. **分析逻辑**: 使用的分析方法是否合理？
4. **市场理解**: 是否正确理解了市场环境？

## 可用的记忆管理工具

你可以选择使用以下工具来管理你的记忆：

### 工具 1: search_and_update_analyst_memory
- **功能**: 搜索并更新记忆内容
- **适用场景**: 预测方向错误但不算离谱、分析方法需要微调优化
- **参数**:
  * query: 搜索查询内容（描述要找什么记忆）
  * memory_id: 填 "auto" 让系统自动搜索
  * analyst_id: "{self.agent_id}"
  * new_content: 新的正确记忆内容
  * reason: 更新原因

### 工具 2: search_and_delete_analyst_memory
- **功能**: 搜索并删除严重错误的记忆
- **适用场景**: 连续多次严重错误、分析逻辑存在根本性问题
- **参数**:
  * query: 搜索查询内容
  * memory_id: 填 "auto"
  * analyst_id: "{self.agent_id}"
  * reason: 删除原因

## 决策要求

请根据你的表现，决定是否需要调用记忆管理工具：

1. **表现良好** → 不需要调用工具，直接总结经验即可
2. **表现一般** → 考虑使用 `search_and_update_analyst_memory` 修正记忆
3. **表现很差** → 考虑使用 `search_and_delete_analyst_memory` 删除错误记忆

## 输出格式

请以 JSON 格式返回，包含以下字段：

```json
{{
  "reflection_summary": "你的复盘总结（1-2段话）",
  "need_tool": true/false,
  "selected_tool": {{
    "tool_name": "search_and_update_analyst_memory" 或 "search_and_delete_analyst_memory",
    "reason": "为什么选择这个工具",
    "parameters": {{
      "query": "搜索查询",
      "memory_id": "auto",
      "analyst_id": "{self.agent_id}",
      "new_content": "新内容（仅update需要）",
      "reason": "操作原因"
    }}
  }}
}}
```

**注意：**
- 如果 `need_tool` 为 false，则不需要填写 `selected_tool` 字段
- 只能操作你自己（{self.agent_id}）的记忆
- 谨慎决策是否真的需要调用工具

请基于你的专业判断，诚实地评估自己的表现并做出明智的决策。
"""
        
        return prompt
    
    def generate_pm_reflection_prompt(
        self,
        date: str,
        pm_decisions: Dict[str, Any],
        analyst_signals: Dict[str, Dict[str, Any]],
        actual_returns: Dict[str, float],
        portfolio_summary: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        生成Portfolio Manager自我复盘的prompt
        
        Args:
            date: 交易日期
            pm_decisions: PM的决策
            analyst_signals: 所有分析师的信号
            actual_returns: 实际收益率
            portfolio_summary: Portfolio总结
            context: 额外上下文
        """
        prompt = f"""你是一位专业的 Portfolio Manager，现在需要对 {date} 的投资决策进行自我复盘。

# 你的职责
作为 Portfolio Manager，你需要：
1. 评估自己的决策质量
2. 分析决策失误的原因
3. 反思是否正确综合了分析师意见
4. 决定是否需要更新决策记忆
5. 总结经验教训

# 今日复盘数据

## Portfolio 表现
"""
        
        if portfolio_summary:
            total_value = portfolio_summary.get('total_value', 0)
            pnl_percent = portfolio_summary.get('pnl_percent', 0)
            cash = portfolio_summary.get('cash', 0)
            
            prompt += f"""
- 总资产: ${total_value:,.2f}
- 收益率: {pnl_percent:+.2f}%
- 现金: ${cash:,.2f}
"""
        
        prompt += "\n## 你的投资决策 vs 实际结果\n"
        
        # 添加PM决策和实际结果
        for ticker, decision_data in pm_decisions.items():
            actual_return = actual_returns.get(ticker, 0)
            action = decision_data.get('action', 'N/A')
            quantity = decision_data.get('quantity', 0)
            confidence = decision_data.get('confidence', 'N/A')
            reasoning = decision_data.get('reasoning', '')
            
            # 判断决策是否正确
            is_correct = self._evaluate_pm_decision(action, actual_return)
            status_emoji = "✅" if is_correct else "❌"
            
            prompt += f"""
{ticker}: {status_emoji}
  - 你的决策: {action}
  - 数量: {quantity} 股
  - 置信度: {confidence}%
  - 决策理由: {reasoning[:200] if reasoning else 'N/A'}
  - 实际收益: {actual_return:.2%}
"""
            
            # 添加分析师意见对比
            prompt += "  - 分析师意见:\n"
            for analyst_id, signals in analyst_signals.items():
                if ticker in signals:
                    analyst_signal = signals[ticker]
                    prompt += f"    * {analyst_id}: {analyst_signal}\n"
        
        # 添加额外上下文
        if context:
            prompt += "\n## 额外上下文\n"
            if 'market_condition' in context:
                prompt += f"- 市场环境: {context['market_condition']}\n"
            if 'risk_metrics' in context:
                prompt += f"- 风险指标: {context['risk_metrics']}\n"
        # pdb.set_trace()
        prompt += f"""

# 自我复盘指导

请按以下标准评估自己的表现：

## 评估标准
1. **决策准确性**: 投资决策是否带来正收益？
2. **信息整合**: 是否正确综合了分析师意见？
3. **风险控制**: 仓位管理是否合理？
4. **执行纪律**: 是否遵循了既定策略？

## 可用的记忆管理工具

你可以选择使用以下工具来管理你的记忆：

### 工具 1: search_and_update_analyst_memory
- **功能**: 搜索并更新记忆内容
- **适用场景**: 决策方向错误但损失可控、信息整合方法需要优化
- **参数**:
  * query: 搜索查询内容
  * memory_id: 填 "auto"
  * analyst_id: "portfolio_manager"
  * new_content: 新的决策经验
  * reason: 更新原因

### 工具 2: search_and_delete_analyst_memory
- **功能**: 搜索并删除严重错误的记忆
- **适用场景**: 决策导致重大损失、使用错误决策框架
- **参数**:
  * query: 搜索查询内容
  * memory_id: 填 "auto"
  * analyst_id: "portfolio_manager"
  * reason: 删除原因

## 决策要求

请根据你的表现，决定是否需要调用记忆管理工具：

1. **表现良好** → 不需要调用工具，总结成功经验即可
2. **表现一般** → 考虑使用 `search_and_update_analyst_memory` 优化决策方法
3. **表现很差** → 考虑使用 `search_and_delete_analyst_memory` 删除错误决策框架

## 输出格式

请以 JSON 格式返回：

```json
{{
  "reflection_summary": "你的复盘总结",
  "need_tool": true/false,
  "selected_tool": {{
    "tool_name": "工具名称",
    "reason": "选择原因",
    "parameters": {{
      "query": "搜索查询",
      "memory_id": "auto",
      "analyst_id": "portfolio_manager",
      "new_content": "新内容（仅update需要）",
      "reason": "操作原因"
    }}
  }}
}}
```

**注意：**
- 如果 `need_tool` 为 false，则不需要 `selected_tool` 字段
- 诚实评估决策质量

请基于你作为 Portfolio Manager 的专业判断，客观评估自己的决策并做出明智的选择。
"""
        
        return prompt
    
    def _evaluate_prediction(self, signal: str, actual_return: float) -> bool:
        """
        评估分析师预测是否正确
        
        Args:
            signal: 预测信号 ('BUY'/'bullish', 'SELL'/'bearish', 'HOLD'/'neutral')
            actual_return: 实际收益率
        
        Returns:
            是否预测正确
        """
        threshold = 0.005  # 0.5%的阈值
        
        # 标准化信号格式（支持多种格式）
        signal_lower = signal.lower() if signal else ''
        
        # 判断是否为看涨信号
        is_bullish = signal_lower in ['buy', 'bullish', 'long']
        # 判断是否为看跌信号
        is_bearish = signal_lower in ['sell', 'bearish', 'short']
        # 判断是否为中性信号
        is_neutral = signal_lower in ['hold', 'neutral']
        
        if is_bullish and actual_return > threshold:
            return True
        elif is_bearish and actual_return < -threshold:
            return True
        elif is_neutral and abs(actual_return) <= threshold:
            return True
        else:
            return False
    
    def _evaluate_pm_decision(self, action: str, actual_return: float) -> bool:
        """
        评估PM决策是否正确
        
        Args:
            action: 决策动作 ('buy'/'long', 'sell'/'short', 'hold'/'neutral')
            actual_return: 实际收益率
        
        Returns:
            是否决策正确
        """
        threshold = 0.005  # 0.5%的阈值
        
        # 标准化动作格式（支持多种格式）
        action_lower = action.lower() if action else 'hold'
        
        # 判断是否为买入动作
        is_buy = action_lower in ['buy', 'long', 'bullish']
        # 判断是否为卖出动作
        is_sell = action_lower in ['sell', 'short', 'bearish']
        # 判断是否为持有动作
        is_hold = action_lower in ['hold', 'neutral']
        
        if is_buy and actual_return > threshold:
            return True
        elif is_sell and actual_return < -threshold:
            return True
        elif is_hold and abs(actual_return) <= threshold:
            return True
        else:
            return False
    
    def perform_self_reflection(
        self,
        date: str,
        reflection_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        执行自我复盘
        
        Args:
            date: 交易日期
            reflection_data: 复盘数据（根据agent类型不同而不同）
            context: 额外上下文
        
        Returns:
            复盘结果
        """
        if not self.llm_available:
            return {
                'status': 'skipped',
                'reason': 'LLM不可用',
                'agent_id': self.agent_id,
                'date': date
            }
        
        try:
            # 根据agent类型生成不同的prompt
            if self.agent_id == 'portfolio_manager':
                prompt = self.generate_pm_reflection_prompt(
                    date=date,
                    pm_decisions=reflection_data.get('pm_decisions', {}),
                    analyst_signals=reflection_data.get('analyst_signals', {}),
                    actual_returns=reflection_data.get('actual_returns', {}),
                    portfolio_summary=reflection_data.get('portfolio_summary', {}),
                    context=context
                )
            else:
                # 分析师
                prompt = self.generate_analyst_reflection_prompt(
                    date=date,
                    my_signals=reflection_data.get('my_signals', {}),
                    actual_returns=reflection_data.get('actual_returns', {}),
                    pm_decisions=reflection_data.get('pm_decisions', {}),
                    context=context
                )
            print(f"\n{'='*60}")
            print(f"🔍 {self.agent_role} 开始自我复盘 ({date})")
            print(f"{'='*60}")
            
            # 调用 LLM（使用 AgentScope 格式）
            messages = [{"role": "user", "content": prompt}]
            response = self.llm(messages=messages, temperature=0.7)
            
            # 获取响应内容
            if isinstance(response, dict):
                response_content = response.get("content", "")
            elif hasattr(response, 'content'):
                response_content = response.content
            else:
                response_content = str(response)
            
            # 解析 JSON 响应
            import json
            try:
                # 尝试提取 JSON（可能被 markdown 包裹）
                json_start = response_content.find("{")
                json_end = response_content.rfind("}") + 1
                if json_start != -1 and json_end > json_start:
                    json_str = response_content[json_start:json_end]
                    reflection_data = json.loads(json_str)
                else:
                    # 如果找不到 JSON，尝试直接解析
                    reflection_data = json.loads(response_content)
            except json.JSONDecodeError as e:
                print(f"⚠️ JSON 解析失败: {e}")
                print(f"原始响应: {response_content[:500]}...")
                # 使用默认值
                reflection_data = {
                    "reflection_summary": response_content,
                    "need_tool": False
                }
            # 提取复盘总结
            reflection_summary = reflection_data.get("reflection_summary", response_content)
            need_tool = reflection_data.get("need_tool", False)
            
            # 执行记忆工具（如果 LLM 决定需要）
            memory_operations = []
            if need_tool and "selected_tool" in reflection_data:
                tool_selection = reflection_data["selected_tool"]
                tool_name = tool_selection.get("tool_name")
                tool_reason = tool_selection.get("reason", "")
                tool_params = tool_selection.get("parameters", {})
                
                # 验证 analyst_id（确保只操作自己的记忆）
                if tool_params.get('analyst_id') != self.agent_id:
                    print(f"⚠️ 警告: {self.agent_role} 试图操作其他Agent的记忆，已阻止")
                    print(f"   期望: {self.agent_id}, 实际: {tool_params.get('analyst_id')}")
                else:
                    print(f"🛠️ {self.agent_role} 智能选择了工具: {tool_name}")
                    print(f"   选择理由: {tool_reason}")
                    
                    try:
                        # 执行工具（类似 analyst 的 execute_selected_tools）
                        result = self.toolkit.call(tool_name, **tool_params)
                        
                        memory_operations.append({
                            'tool_name': tool_name,
                            'selection_reason': tool_reason,
                            'args': tool_params,
                            'result': result
                        })
                        
                        print(f"  ✅ 工具执行完成: {result.get('status', 'unknown')}")
                        
                        # 记录到日志
                        self.logger_system.log_operation(
                            agent_id=self.agent_id,
                            operation_type='self_reflection_with_llm_selection',
                            tool_name=tool_name,
                            args=tool_params,
                            result=result,
                            context={
                                'date': date,
                                'selection_reason': tool_reason
                            }
                        )
                        
                    except Exception as e:
                        print(f"  ❌ 工具执行失败: {e}")
                        import traceback
                        traceback.print_exc()
                        
                        # 记录失败
                        memory_operations.append({
                            'tool_name': tool_name,
                            'selection_reason': tool_reason,
                            'args': tool_params,
                            'error': str(e)
                        })
            else:
                print(f"💭 {self.agent_role} 决定无需记忆工具操作")
            
            # 显示复盘总结
            print(f"\n📝 复盘总结:")
            print(reflection_summary)
            print(f"{'='*60}\n")
            
            return {
                'status': 'success',
                'agent_id': self.agent_id,
                'agent_role': self.agent_role,
                'date': date,
                'reflection_summary': reflection_summary,
                'memory_operations': memory_operations,
                'operations_count': len(memory_operations)
            }
            
        except Exception as e:
            print(f"❌ {self.agent_role} 自我复盘失败: {str(e)}")
            import traceback
            traceback.print_exc()
            
            return {
                'status': 'failed',
                'agent_id': self.agent_id,
                'agent_role': self.agent_role,
                'date': date,
                'error': str(e)
            }


def create_reflection_system(
    agent_id: str,
    base_dir: str = "mock",
    streamer=None
) -> AgentSelfReflectionSystem:
    """
    工厂函数：为指定Agent创建自我复盘系统
    
    Args:
        agent_id: Agent ID
        base_dir: 基础目录（config_name）
        streamer: 消息广播器
    
    Returns:
        自我复盘系统实例
    """
    role_mapping = {
        'technical_analyst': 'Technical Analyst',
        'fundamentals_analyst': 'Fundamentals Analyst',
        'sentiment_analyst': 'Sentiment Analyst',
        'valuation_analyst': 'Valuation Analyst',
        'portfolio_manager': 'Portfolio Manager'
    }
    
    agent_role = role_mapping.get(agent_id, agent_id)
    return AgentSelfReflectionSystem(agent_id, agent_role, base_dir, streamer=streamer)

