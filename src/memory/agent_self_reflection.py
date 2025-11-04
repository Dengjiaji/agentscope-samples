#!/usr/bin/env python3
"""
Agent自我复盘系统
每个分析师（包括PM）独立评估自己的表现并管理记忆
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
    """分析师自我复盘系统"""
    
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
            
            self.llm_available = True
            print(f"✅ {agent_role} 自我复盘系统已初始化（AgentScope Toolkit 模式）")
            print(f"   已注册工具: {', '.join(self.toolkit.list_functions())}")
            
        except Exception as e:
            logger.error(f"{agent_role} 自我复盘系统初始化失败: {e}")
            self.llm_available = False
    
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

## 记忆管理决策

根据表现决定是否需要记忆操作：

### 🔴 需要删除记忆 (使用 search_and_delete_analyst_memory)
- 连续多次严重预测错误
- 使用了根本错误的分析逻辑
- 对市场的理解存在重大偏差
- 示例: "连续3天看多但市场暴跌，说明对趋势判断有根本性错误"

### 🟡 需要更新记忆 (使用 search_and_update_analyst_memory)
- 预测方向错误但不算离谱
- 分析方法需要微调优化
- 需要补充新的经验教训
- 示例: "技术指标显示超买但未考虑基本面支撑，需要综合判断"

### 🟢 表现良好，无需操作
- 预测准确，分析逻辑正确
- 可以简单总结经验，不调用工具
- 示例: "成功预测突破，MACD金叉信号有效"

## 输出要求

请以 JSON 格式返回结果，包含以下字段：

```json
{{
  "reflection_summary": "你的复盘总结（1-2段话）",
  "memory_action": "none" | "update" | "delete",
  "memory_operation": {{
    "tool_name": "search_and_update_analyst_memory" 或 "search_and_delete_analyst_memory",
    "query": "搜索查询内容",
    "analyst_id": "{self.agent_id}",
    "memory_id": "auto",
    "new_content": "新的记忆内容（仅update需要）",
    "reason": "操作原因"
  }},
  "improvements": ["改进建议1", "改进建议2"]
}}
```

**字段说明：**
- `memory_action`: "none"(无需操作) | "update"(更新记忆) | "delete"(删除记忆)
- `memory_operation`: 仅当 memory_action 不是 "none" 时需要填写
- 只管理你自己 ({self.agent_id}) 的记忆

只返回 JSON，不要添加任何其他文字。
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
        pdb.set_trace()
        prompt += f"""

# 自我复盘指导

请按以下标准评估自己的表现：

## 评估标准
1. **决策准确性**: 投资决策是否带来正收益？
2. **信息整合**: 是否正确综合了分析师意见？
3. **风险控制**: 仓位管理是否合理？
4. **执行纪律**: 是否遵循了既定策略？

## 记忆管理决策

根据表现决定是否需要记忆操作：

### 🔴 需要删除记忆 (使用 search_and_delete_analyst_memory)
- 决策导致重大损失（如单日损失>3%）
- 使用了错误的决策框架
- 忽略了明显的风险信号
- 示例: "过度依赖单一分析师意见，导致忽视风险"

### 🟡 需要更新记忆 (使用 search_and_update_analyst_memory)
- 决策方向错误但损失可控
- 信息整合方法需要优化
- 风险控制需要加强
- 示例: "技术面和基本面冲突时，需要更谨慎"

### 🟢 表现良好，无需操作
- 决策带来正收益
- 风险控制得当
- 可以总结成功经验
- 示例: "成功识别趋势，及时调整仓位"

## 输出要求

请以 JSON 格式返回结果，包含以下字段：

```json
{{
  "reflection_summary": "你的复盘总结（2-3段话）",
  "memory_action": "none" | "update" | "delete",
  "memory_operation": {{
    "tool_name": "search_and_update_analyst_memory" 或 "search_and_delete_analyst_memory",
    "query": "搜索查询内容",
    "analyst_id": "portfolio_manager",
    "memory_id": "auto",
    "new_content": "新的记忆内容（仅update需要）",
    "reason": "操作原因"
  }},
  "improvements": ["改进建议1", "改进建议2", "改进建议3"]
}}
```

**字段说明：**
- `memory_action`: "none"(无需操作) | "update"(更新记忆) | "delete"(删除记忆)
- `memory_operation`: 仅当 memory_action 不是 "none" 时需要填写
- 诚实评估决策质量，考虑如何更好地利用分析师意见

只返回 JSON，不要添加任何其他文字。
"""
        
        return prompt
    
    def _evaluate_prediction(self, signal: str, actual_return: float) -> bool:
        """
        评估分析师预测是否正确
        
        Args:
            signal: 预测信号 ('BUY', 'SELL', 'HOLD')
            actual_return: 实际收益率
        
        Returns:
            是否预测正确
        """
        threshold = 0.005  # 0.5%的阈值
        
        if signal == 'BUY' and actual_return > threshold:
            return True
        elif signal == 'SELL' and actual_return < -threshold:
            return True
        elif signal == 'HOLD' and abs(actual_return) <= threshold:
            return True
        else:
            return False
    
    def _evaluate_pm_decision(self, action: str, actual_return: float) -> bool:
        """
        评估PM决策是否正确
        
        Args:
            action: 决策动作 ('buy', 'sell', 'hold')
            actual_return: 实际收益率
        
        Returns:
            是否决策正确
        """
        threshold = 0.005  # 0.5%的阈值
        
        action_lower = action.lower() if action else 'hold'
        
        if action_lower == 'buy' and actual_return > threshold:
            return True
        elif action_lower == 'sell' and actual_return < -threshold:
            return True
        elif action_lower == 'hold' and abs(actual_return) <= threshold:
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
            response = self.llm(messages)
            # pdb.set_trace()
            response_content = response.get("content", "")
            
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
                    "memory_action": "none",
                    "improvements": []
                }
            
            # 提取复盘总结
            reflection_summary = reflection_data.get("reflection_summary", response_content)
            memory_action = reflection_data.get("memory_action", "none")
            improvements = reflection_data.get("improvements", [])
            
            # 执行记忆操作
            memory_operations = []
            if memory_action != "none" and "memory_operation" in reflection_data:
                mem_op = reflection_data["memory_operation"]
                tool_name = mem_op.get("tool_name")
                
                # 确保只操作自己的记忆
                if mem_op.get('analyst_id') != self.agent_id:
                    print(f"⚠️ 警告: {self.agent_role} 试图操作其他Agent的记忆，已阻止")
                else:
                    print(f"🛠️ {self.agent_role} 决定执行记忆操作: {memory_action}")
                    print(f"  📞 执行: {tool_name}")
                    
                    try:
                        # 使用 toolkit 调用工具
                        result = self.toolkit.call(tool_name, **mem_op)
                        memory_operations.append({
                            'tool_name': tool_name,
                            'args': mem_op,
                            'result': result
                        })
                        print(f"  ✅ 操作完成: {result.get('status', 'unknown')}")
                        
                        # 记录到日志
                        self.logger_system.log_operation(
                            agent_id=self.agent_id,
                            operation_type='individual_review',
                            tool_name=tool_name,
                            args=mem_op,
                            result=result,
                            context={'date': date}
                        )
                    except Exception as e:
                        print(f"  ❌ 工具调用失败: {e}")
            else:
                print(f"💭 {self.agent_role} 认为无需记忆操作")
            
            # 显示复盘总结
            print(f"\n📝 复盘总结:")
            print(reflection_summary)
            
            if improvements:
                print(f"\n💡 改进建议:")
                for i, improvement in enumerate(improvements, 1):
                    print(f"  {i}. {improvement}")
            
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

