#!/usr/bin/env python3
"""
Memory Reflection System - 统一的记忆复盘系统
支持两种模式：
- central_review: 统一LLM处理所有agent的记忆
- individual_review: 每个agent独立处理自己的记忆
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path

from src.llm.models import get_model, ModelProvider
from src.agents.prompt_loader import PromptLoader
from src.config.constants import ROLE_TO_AGENT
from src.config.path_config import get_logs_and_memory_dir

logger = logging.getLogger(__name__)


class MemoryOperationLogger:
    """记忆操作日志记录器"""
    
    def __init__(self, base_dir: str):
        self.log_dir = get_logs_and_memory_dir() / base_dir / "memory_operations"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        today = datetime.now().strftime("%Y%m%d")
        self.log_file = self.log_dir / f"memory_ops_{today}.jsonl"
    
    def log_operation(self, agent_id: str, operation_type: str, tool_name: str, 
                     args: Dict[str, Any], result: Dict[str, Any], 
                     context: Optional[Dict[str, Any]] = None):
        """记录记忆操作"""
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


class MemoryReflectionSystem:
    """统一的记忆复盘系统"""
    
    def __init__(self, base_dir: str = "mock", streamer=None):
        """
        初始化复盘系统
        
        Args:
            base_dir: 基础目录（config_name）
            streamer: 消息广播器
        """
        self.base_dir = base_dir
        self.streamer = streamer
        self.logger_system = MemoryOperationLogger(base_dir)
        self.prompt_loader = PromptLoader()
        
        # 初始化LLM
        model_name = os.getenv('MEMORY_LLM_MODEL', 'gpt-4o-mini')
        model_provider_str = os.getenv('MEMORY_LLM_PROVIDER', 'OPENAI')
        model_provider = getattr(ModelProvider, model_provider_str, ModelProvider.OPENAI)
        
        api_keys = {}
        if model_provider == ModelProvider.OPENAI:
            api_keys['OPENAI_API_KEY'] = os.getenv('OPENAI_API_KEY')
        elif model_provider == ModelProvider.ANTHROPIC:
            api_keys['ANTHROPIC_API_KEY'] = os.getenv('ANTHROPIC_API_KEY')
        
        # 创建记忆管理工具包和memory实例
        from src.tools.memory_tools import create_memory_toolkit, _set_base_dir, set_memory_tools_streamer
        from src.memory import get_memory
        
        _set_base_dir(base_dir)  # 设置base_dir供memory_tools使用
        self.toolkit = create_memory_toolkit()
        self.memory = get_memory(base_dir)  # 获取memory实例供直接操作
        
        # 设置streamer
        if self.streamer:
            set_memory_tools_streamer(self.streamer)
        
        self.llm = get_model(model_name, model_provider, api_keys)
        self.llm_available = True
        
        logger.info(f"记忆复盘系统已初始化（{model_provider_str}: {model_name}）")
    
    def perform_reflection(self, date: str, reflection_data: Dict[str, Any], 
                          mode: str = "individual_review") -> Dict[str, Any]:
        """
        执行记忆复盘
        
        Args:
            date: 交易日期
            reflection_data: 复盘数据
            mode: 模式 ('central_review' 或 'individual_review')
            
        Returns:
            复盘结果
        """
        if mode == "central_review":
            return self._central_review(date, reflection_data)
        else:
            return self._individual_review(date, reflection_data)
    
    def _central_review(self, date: str, reflection_data: Dict[str, Any]) -> Dict[str, Any]:
        """Central Review模式：统一LLM处理所有agent的记忆"""
        try:
            pm_signals = reflection_data.get('pm_signals', {})
            actual_returns = reflection_data.get('actual_returns', {})
            analyst_signals = reflection_data.get('analyst_signals', {})
            tickers = reflection_data.get('tickers', [])
            
            # 生成prompt
            prompt = self._build_central_review_prompt(date, tickers, pm_signals, 
                                                       analyst_signals, actual_returns)
            
            logger.info(f"🤖 Central Review模式 ({date})")
            
            # 调用LLM
            messages = [{"role": "user", "content": prompt}]
            response = self.llm(messages, temperature=0.7)
            response_content = response.get("content", "") if isinstance(response, dict) else str(response)
            
            # 解析响应
            decision_data = self._parse_json_response(response_content)
            reasoning = decision_data.get("reflection_summary", "")
            need_tool = decision_data.get("need_tool", False)
            
            # 执行工具调用
            execution_results = []
            if need_tool and "selected_tool" in decision_data:
                execution_results = self._execute_tools(decision_data["selected_tool"], 
                                                       "central_review", date)
            
            logger.info(f"📝 复盘总结: {reasoning[:200]}...")
            
            return {
                'status': 'success',
                'mode': 'central_review',
                'date': date,
                'reflection_summary': reasoning,
                'operations_count': len(execution_results),
                'execution_results': execution_results
            }
            
        except Exception as e:
            logger.error(f"❌ Central Review失败: {e}", exc_info=True)
            return {
                'status': 'failed',
                'mode': 'central_review',
                'date': date,
                'error': str(e)
            }
    
    def _individual_review(self, date: str, reflection_data: Dict[str, Any]) -> Dict[str, Any]:
        """Individual Review模式：每个agent独立处理"""
        all_results = []
        
        # 获取所有需要复盘的agents
        agents_data = reflection_data.get('agents_data', {})
        
        for agent_id, agent_data in agents_data.items():
            try:
                result = self._agent_self_reflection(agent_id, date, agent_data)
                all_results.append(result)
            except Exception as e:
                logger.error(f"❌ {agent_id} 复盘失败: {e}")
                all_results.append({
                    'status': 'failed',
                    'agent_id': agent_id,
                    'error': str(e)
                })
        
        return {
            'status': 'success',
            'mode': 'individual_review',
            'date': date,
            'agents_results': all_results,
            'total_agents': len(all_results)
        }
    
    def _agent_self_reflection(self, agent_id: str, date: str, 
                               agent_data: Dict[str, Any]) -> Dict[str, Any]:
        """单个agent的自我复盘"""
        agent_role = ROLE_TO_AGENT.get(agent_id, agent_id)
        
        # 如果是PM，先记录每日决策
        daily_record_result = None
        if agent_id == 'portfolio_manager':
            daily_record_result = self._record_pm_daily_decisions(agent_id, date, agent_data)
            if daily_record_result.get('status') == 'success':
                logger.info(f"📝 已记录 {daily_record_result.get('count', 0)} 条PM每日决策")
        
        # 生成prompt
        if agent_id == 'portfolio_manager':
            prompt = self._build_pm_reflection_prompt(agent_role, date, agent_data)
        else:
            prompt = self._build_analyst_reflection_prompt(agent_role, date, agent_data)
        
        logger.info(f"🔍 {agent_role} 自我复盘 ({date})")
        
        # 调用LLM
        messages = [{"role": "user", "content": prompt}]
        response = self.llm(messages, temperature=0.7)
        response_content = response.get("content", "") if isinstance(response, dict) else str(response)
        
        # 解析响应
        decision_data = self._parse_json_response(response_content)
        reflection_summary = decision_data.get("reflection_summary", response_content)
        need_tool = decision_data.get("need_tool", False)
        
        # 执行工具调用
        memory_operations = []
        if need_tool and "selected_tool" in decision_data:
            tool_selection = decision_data["selected_tool"]
            
            # 验证analyst_id
            if tool_selection.get('parameters', {}).get('analyst_id') == agent_id:
                memory_operations = self._execute_tools([tool_selection], agent_id, date)
            else:
                logger.warning(f"⚠️ {agent_role} 试图操作其他Agent的记忆，已阻止")
        else:
            logger.info(f"💭 {agent_role} 决定无需记忆工具操作")
        
        logger.info(f"📝 {agent_role} 复盘完成")
        
        result = {
            'status': 'success',
            'agent_id': agent_id,
            'agent_role': agent_role,
            'date': date,
            'reflection_summary': reflection_summary,
            'memory_operations': memory_operations
        }
        
        # 如果有每日决策记录结果，也包含进来
        if daily_record_result:
            result['daily_record_result'] = daily_record_result
        
        return result
    
    def _record_pm_daily_decisions(self, agent_id: str, date: str, 
                                   agent_data: Dict[str, Any]) -> Dict[str, Any]:
        """记录PM每日决策到memory"""
        try:
            pm_decisions = agent_data.get('my_decisions', {})
            actual_returns = agent_data.get('actual_returns', {})
            analyst_signals = agent_data.get('analyst_signals', {})
            
            memories_added = 0
            for ticker, decision_data in pm_decisions.items():
                pm_action = decision_data.get('action', 'N/A')
                pm_quantity = decision_data.get('quantity', 0)
                pm_confidence = decision_data.get('confidence', 'N/A')
                pm_reasoning = decision_data.get('reasoning', '')
                actual_return = actual_returns.get(ticker, 0)
                
                # 构建分析师信号汇总
                analyst_summary = []
                for analyst_id, signals in analyst_signals.items():
                    if ticker in signals:
                        signal_data = signals[ticker]
                        if isinstance(signal_data, dict):
                            signal = signal_data.get('signal', signal_data)
                            confidence = signal_data.get('confidence', 'N/A')
                            analyst_summary.append(f"{analyst_id}: {signal} (confidence: {confidence})")
                        else:
                            analyst_summary.append(f"{analyst_id}: {signal_data}")
                
                analyst_info = "; ".join(analyst_summary) if analyst_summary else "无分析师信号"
                
                # 判断决策结果
                decision_outcome = self._evaluate_decision(pm_action, actual_return)
                outcome_label = "✅ 正确" if decision_outcome else "❌ 错误"
                
                # 构建记录内容
                if not isinstance(pm_reasoning, str):
                    pm_reasoning = str(pm_reasoning) if pm_reasoning else ''
                
                content = f"""日期: {date}
股票: {ticker}
PM决策: {pm_action} (数量: {pm_quantity}, 置信度: {pm_confidence}%)
决策理由: {pm_reasoning[:300] if pm_reasoning else 'N/A'}
分析师意见: {analyst_info}
实际收益: {actual_return:+.2%}
决策结果: {outcome_label}"""
                
                metadata = {
                    "type": "daily_decision",
                    "date": date,
                    "ticker": ticker,
                    "action": pm_action,
                    "confidence": pm_confidence,
                    "actual_return": actual_return,
                    "outcome": "correct" if decision_outcome else "incorrect"
                }
                
                # 添加到memory
                memory_id = self.memory.add(content, agent_id, metadata)
                if memory_id:
                    memories_added += 1
            
            logger.info(f"  ✅ 记录了 {memories_added} 条PM每日决策")
            return {'status': 'success', 'count': memories_added}
            
        except Exception as e:
            logger.error(f"⚠️ 记录PM决策失败: {e}")
            return {'status': 'failed', 'error': str(e)}
    
    def _execute_tools(self, tool_selections, agent_id: str, date: str) -> List[Dict[str, Any]]:
        """执行工具调用"""
        if not isinstance(tool_selections, list):
            tool_selections = [tool_selections]
        
        results = []
        for tool_selection in tool_selections:
            tool_name = tool_selection.get("tool_name")
            tool_reason = tool_selection.get("reason", "")
            tool_params = tool_selection.get("parameters", {})
            
            logger.info(f"🛠️ 调用工具: {tool_name}")
            
            try:
                if tool_name in self.toolkit.tools:
                    tool_func = self.toolkit.tools[tool_name].original_func
                    result = tool_func(**tool_params)
                else:
                    result = {'status': 'failed', 'error': f'Tool not found: {tool_name}'}
                
                results.append({
                    'tool_name': tool_name,
                    'reason': tool_reason,
                    'args': tool_params,
                    'result': result
                })
                
                # 记录日志
                self.logger_system.log_operation(
                    agent_id=agent_id,
                    operation_type='reflection',
                    tool_name=tool_name,
                    args=tool_params,
                    result=result,
                    context={'date': date}
                )
                
                logger.info(f"  ✅ 工具执行完成")
            except Exception as e:
                logger.error(f"  ❌ 工具执行失败: {e}")
                results.append({
                    'tool_name': tool_name,
                    'error': str(e)
                })
        
        return results
    
    def _build_central_review_prompt(self, date: str, tickers: List[str],
                                    pm_signals: Dict, analyst_signals: Dict, 
                                    actual_returns: Dict) -> str:
        """构建Central Review的prompt"""
        pm_signals_section = "\n".join([
            f"{ticker}: PM决策 {pm_signals.get(ticker, {}).get('signal', 'N/A')} "
            f"(置信度: {pm_signals.get(ticker, {}).get('confidence', 'N/A')}%), "
            f"实际收益: {actual_returns.get(ticker, 0):.2%}"
            for ticker in tickers
        ])
        
        analyst_signals_section = ""
        for analyst, signals in analyst_signals.items():
            analyst_signals_section += f"\n\n**{analyst}:**"
            for ticker in tickers:
                if ticker in signals:
                    analyst_signals_section += f"\n  {ticker}: {signals[ticker]}, 实际 {actual_returns.get(ticker, 0):.2%}"
        
        return self.prompt_loader.load_prompt(
            "memory",
            "memory_decision",
            {
                "date": date,
                "pm_signals_section": pm_signals_section,
                "analyst_signals_section": analyst_signals_section
            }
        )
    
    def _build_analyst_reflection_prompt(self, agent_role: str, date: str, 
                                        agent_data: Dict) -> str:
        """构建分析师reflection的prompt"""
        my_signals = agent_data.get('my_signals', {})
        actual_returns = agent_data.get('actual_returns', {})
        pm_decisions = agent_data.get('pm_decisions', {})
        
        signals_data = ""
        for ticker, signal_data in my_signals.items():
            actual_return = actual_returns.get(ticker, 0)
            signal = signal_data.get('signal', 'N/A')
            confidence = signal_data.get('confidence', 'N/A')
            reasoning = signal_data.get('reasoning', '')
            
            # 确保reasoning是字符串
            if not isinstance(reasoning, str):
                reasoning = str(reasoning) if reasoning else ''
            
            is_correct = self._evaluate_prediction(signal, actual_return)
            status_emoji = "✅" if is_correct else "❌"
            
            signals_data += f"""
{ticker}: {status_emoji}
  - 你的信号: {signal} (置信度: {confidence}%)
  - 你的理由: {reasoning[:200] if reasoning else 'N/A'}
  - 实际收益: {actual_return:.2%}
  - PM决策: {pm_decisions.get(ticker, {}).get('action', 'N/A')}
"""
        
        return self.prompt_loader.load_prompt(
            "reflection",
            "analyst_reflection_system",
            {
                "agent_role": agent_role,
                "date": date,
                "agent_id": agent_data.get('agent_id', ''),
                "signals_data": signals_data,
                "context_data": ""
            }
        )
    
    def _build_pm_reflection_prompt(self, agent_role: str, date: str, 
                                   agent_data: Dict) -> str:
        """构建PM reflection的prompt"""
        pm_decisions = agent_data.get('my_decisions', {})
        analyst_signals = agent_data.get('analyst_signals', {})
        actual_returns = agent_data.get('actual_returns', {})
        portfolio_summary = agent_data.get('portfolio_summary', {})
        
        # 构建portfolio数据
        portfolio_data = ""
        if portfolio_summary:
            total_value = portfolio_summary.get('total_value', 0)
            pnl_percent = portfolio_summary.get('pnl_percent', 0)
            cash = portfolio_summary.get('cash', 0)
            
            portfolio_data = f"""
- 总资产: ${total_value:,.2f}
- 收益率: {pnl_percent:+.2f}%
- 现金: ${cash:,.2f}
"""
        
        # 构建决策数据
        decisions_data = ""
        for ticker, decision_data in pm_decisions.items():
            actual_return = actual_returns.get(ticker, 0)
            action = decision_data.get('action', 'N/A')
            quantity = decision_data.get('quantity', 0)
            confidence = decision_data.get('confidence', 'N/A')
            reasoning = decision_data.get('reasoning', '')
            
            # 确保reasoning是字符串
            if not isinstance(reasoning, str):
                reasoning = str(reasoning) if reasoning else ''
            
            is_correct = self._evaluate_decision(action, actual_return)
            status_emoji = "✅" if is_correct else "❌"
            
            decisions_data += f"""
{ticker}: {status_emoji}
  - 你的决策: {action}
  - 数量: {quantity} 股
  - 置信度: {confidence}%
  - 决策理由: {reasoning[:200] if reasoning else 'N/A'}
  - 实际收益: {actual_return:.2%}
"""
            
            # 添加分析师意见对比
            decisions_data += "  - 分析师意见:\n"
            for analyst_id, signals in analyst_signals.items():
                if ticker in signals:
                    analyst_signal = signals[ticker]
                    if isinstance(analyst_signal, dict):
                        signal = analyst_signal.get('signal', 'N/A')
                        decisions_data += f"    * {analyst_id}: {signal}\n"
                    else:
                        decisions_data += f"    * {analyst_id}: {analyst_signal}\n"
        
        return self.prompt_loader.load_prompt(
            "reflection",
            "pm_reflection_system",
            {
                "date": date,
                "portfolio_data": portfolio_data,
                "decisions_data": decisions_data,
                "context_data": ""
            }
        )
    
    def _evaluate_prediction(self, signal: str, actual_return: float) -> bool:
        """评估预测是否正确"""
        threshold = 0.005
        signal_lower = (signal or '').lower()
        
        if signal_lower in ['buy', 'bullish', 'long'] and actual_return > threshold:
            return True
        elif signal_lower in ['sell', 'bearish', 'short'] and actual_return < -threshold:
            return True
        elif signal_lower in ['hold', 'neutral'] and abs(actual_return) <= threshold:
            return True
        return False
    
    def _evaluate_decision(self, action: str, actual_return: float) -> bool:
        """评估决策是否正确"""
        return self._evaluate_prediction(action, actual_return)
    
    def _parse_json_response(self, response_content: str) -> dict:
        """解析JSON响应"""
        try:
            json_start = response_content.find("{")
            json_end = response_content.rfind("}") + 1
            if json_start != -1 and json_end > json_start:
                json_str = response_content[json_start:json_end]
                return json.loads(json_str)
            return json.loads(response_content)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON解析失败: {e}")
            return {
                "reflection_summary": response_content,
                "need_tool": False
            }


def create_reflection_system(base_dir: str = "mock", streamer=None) -> MemoryReflectionSystem:
    """创建记忆复盘系统"""
    return MemoryReflectionSystem(base_dir, streamer)

