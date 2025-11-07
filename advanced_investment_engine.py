#!/usr/bin/env python3
"""
主程序 - 带高级通信机制的多Agent投资分析系统
包含通知、私聊、开会等完整的agent交流功能
"""

import sys
import os
import json
import traceback
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any
from dotenv import load_dotenv
import asyncio
import concurrent.futures
from copy import deepcopy
import threading
import pdb
# 添加项目路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)
from src.utils.mem0_env_loader import ensure_mem0_env_loaded
ensure_mem0_env_loaded()

from src.graph.state import AgentState, create_message

# 导入所有四个核心分析师 - 使用新架构
from src.utils.analysts import (
    intelligent_fundamentals_analyst_agent,
    intelligent_technical_analyst_agent,
    intelligent_sentiment_analyst_agent,
    intelligent_valuation_analyst_agent
)

# 导入通知系统
# 使用基于 Mem0 的通知系统与工具
from src.communication.notification_system_mem0 import (
    mem0_notification_system as notification_system,
    should_send_notification)

# 导入第二轮LLM分析系统
from src.agents.second_round_llm_analyst import (
    run_second_round_llm_analysis,
    format_second_round_result_for_state,
    ANALYST_PERSONAS
)

# 导入风险管理和投资组合管理 - 使用新架构
from src.agents.risk_manager_agent import RiskManagerAgent
from src.agents.portfolio_manager_agent import PortfolioManagerAgent

# 创建兼容的包装函数
def risk_management_agent(state, agent_id="risk_manager"):
    """风险管理 - 使用新架构"""
    agent = RiskManagerAgent(agent_id=agent_id, mode="basic")
    return agent.execute(state)

def portfolio_management_agent(state, agent_id="portfolio_manager"):
    """投资组合管理 - 使用新架构"""
    agent = PortfolioManagerAgent(agent_id=agent_id, mode="direction")
    return agent.execute(state)

# 导入交易执行器
from src.utils.trade_executor import execute_trading_decisions

# 导入新的通信系统
from src.communication.chat_tools import (
    communication_manager,
    CommunicationDecision
)
from src.memory import unified_memory_manager as memory_manager

# 导入日志配置
from src.utils.logging_config import setup_logging

# 设置安静模式日志（禁用HTTP请求等详细输出）
setup_logging(
    level=logging.WARNING,
    log_file='investment_analysis_communications.log',
    quiet_mode=True
)


class AdvancedInvestmentAnalysisEngine:
    """高级投资分析引擎 - 包含完整的agent交流机制"""
    
    def __init__(self, streamer=None):
        # 保存streamer引用
        self.streamer = streamer
        
        # 添加线程锁用于并行执行时的同步
        self._notification_lock = threading.Lock()
        self.core_analysts = {
            'fundamentals_analyst': {
                'name': '基本面分析师',
                'agent_func': intelligent_fundamentals_analyst_agent,
                'description': '使用LLM智能选择分析工具，专注于财务数据和公司基本面分析'
            },
            'sentiment_analyst': {
                'name': '情绪分析师',
                'agent_func': intelligent_sentiment_analyst_agent,
                'description': '使用LLM智能选择分析工具，分析市场情绪和新闻舆论'
            },
            'technical_analyst': {
                'name': '技术分析师',
                'agent_func': intelligent_technical_analyst_agent, 
                'description': '使用LLM智能选择分析工具，专注于技术指标和图表分析'
            },
            'valuation_analyst': {
                'name': '估值分析师',
                'agent_func': intelligent_valuation_analyst_agent,
                'description': '使用LLM智能选择分析工具，专注于公司估值和价值评估'
            }
        }
        
        # 统一通过记忆系统注册分析师与通知（记忆管理器内部会注册通知系统）
        for agent_id, agent_info in self.core_analysts.items():
            memory_manager.register_analyst(agent_id, agent_info['name'])
        memory_manager.register_analyst("portfolio_manager", "投资组合经理")
        
        logging.info("高级投资分析引擎初始化完成")
    
    def create_base_state(self, tickers: List[str], start_date: str, end_date: str) -> AgentState:
        """创建基础的AgentState"""
        # 检查环境变量
        api_key = os.getenv('FINANCIAL_DATASETS_API_KEY')
        openai_key = os.getenv('OPENAI_API_KEY')
        model_name = os.getenv('MODEL_NAME', 'gpt-3.5-turbo')
        
        if not api_key or not openai_key:
            raise ValueError("缺少必要的API密钥，请检查环境变量设置")
        
        
        state = AgentState(
            messages=[create_message(
                name="system",
                content="Advanced investment analysis session with communications",
                role="system"
            )],
            data={
                "tickers": tickers,
                "start_date": start_date,
                "end_date": end_date,
                "analyst_signals": {},
                "communication_logs": {
                    "private_chats": [],
                    "meetings": [],
                    "communication_decisions": []
                },
                "api_keys": {
                    'FINANCIAL_DATASETS_API_KEY': api_key,
                    'OPENAI_API_KEY': openai_key,
                }
            },
            metadata={
                "show_reasoning": False,  # 默认不显示详细推理，通过参数控制
                "model_name": model_name,
                "model_provider": "OpenAI",
                "communication_enabled": True
            }
        )
        
        return state
    
    def run_analyst_with_notifications(self, agent_id: str, agent_info: Dict, 
                                     state: AgentState) -> Dict[str, Any]:
        """运行单个分析师并处理通知逻辑"""
        agent_name = agent_info['name']
        agent_func = agent_info['agent_func']
        
        print(f"\n开始执行 {agent_name} 分析...")
        
        try:
            # 获取分析师记忆并开始分析会话
            analyst_memory = memory_manager.get_analyst_memory(agent_id)
            session_id = None
            if analyst_memory:
                tickers = state.get("data", {}).get("tickers", [])
                # 获取 trading_date 作为 analysis_date
                analysis_date = state.get("metadata", {}).get("trading_date") or state.get("data", {}).get("end_date")
                session_id = analyst_memory.start_analysis_session(
                    session_type="first_round",
                    tickers=tickers,
                    context={"notifications_enabled": True},
                    analysis_date=analysis_date
                )
            
            # 获取agent的通知记忆
            agent_memory = notification_system.get_agent_memory(agent_id)
            
            # # 将之前收到的通知添加到状态中，作为上下文（Mem0版本按agent_id生成）
            # # 若为回测流程，可从state中传入 backtest_date 到通知上下文
            # backtest_date = state.get("data", {}).get("backtest_date") if isinstance(state.get("data", {}), dict) else None
            # notifications_context = format_notifications_for_context(agent_id, backtest_date=backtest_date)
            
            # # 可以将通知上下文添加到消息中
            # context_message = create_message(
            #     name=agent_id,
            #     content=f"Context information: {notifications_context}\n\nPlease analyze based on this information and latest data.",
            #     role="user"
            # )
            # state["messages"].append(context_message)
            
            # # 记录上下文消息到分析师记忆
            # if analyst_memory and session_id:
            #     notifications_included = 0
            #     try:
            #         if agent_memory:
            #             recent_list = agent_memory.get_recent_notifications(24)
            #             notifications_included = len(recent_list) if isinstance(recent_list, list) else 0
            #     except Exception:
            #         notifications_included = 0
            #     analyst_memory.add_analysis_message(
            #         session_id, "human", context_message.content,
            #         {"type": "context", "notifications_included": notifications_included}
            #     )
            
            # 执行分析师函数
            result = agent_func(state, agent_id=agent_id)
            
            # 获取分析结果
            analysis_result = state['data']['analyst_signals'].get(agent_id, {})
            
            if analysis_result:
                print(f"{agent_name} 分析完成")
                
                # 完成分析会话记录
                if analyst_memory and session_id:
                    # 获取 trading_date 作为 analysis_date
                    analysis_date = state.get("metadata", {}).get("trading_date") or state.get("data", {}).get("end_date")
                    analyst_memory.complete_analysis_session(session_id, analysis_result, analysis_date)
                
                # 判断是否需要发送通知（可选）
                notifications_enabled = state["metadata"].get("notifications_enabled", True)
                if notifications_enabled:
                    notification_decision = should_send_notification(
                        agent_id=agent_id,
                        analysis_result=analysis_result,
                        agent_memory=agent_memory,
                        state=state
                    )
                    
                    # 处理通知决策（使用线程锁保护）
                    if notification_decision.get("should_notify", False):
                        print(f"{agent_name} 决定发送通知...")

                        # 获取 trading_date 作为 backtest_date
                        backtest_date = state.get("metadata", {}).get("trading_date") or state.get("data", {}).get("end_date")
                        
                        # 使用线程锁保护通知系统的全局状态
                        with self._notification_lock:
                            notification_id = notification_system.broadcast_notification(
                                sender_agent=agent_id,
                                content=notification_decision["content"],
                                urgency=notification_decision.get("urgency", "medium"),
                                category=notification_decision.get("category", "general"),
                                backtest_date=backtest_date
                            )
                        
                        print(f"通知已发送 (ID: {notification_id})")
                        print(f"通知内容: {notification_decision['content']}")
                        if self.streamer:
                            self.streamer.print("agent", 
                                f"📢 {notification_decision['content']} [紧急度: {notification_decision.get('urgency', 'medium')}]",
                                role_key=agent_id
                            )
                    else:
                        print(f"{agent_name} 决定不发送通知")
                        if "reason" in notification_decision:
                            print(f"原因: {notification_decision['reason']}")
                        if self.streamer:
                            self.streamer.print("agent", f"{agent_name} 决定不发送通知", role_key=agent_id)
                else:
                    print(f"⚡ {agent_name} 跳过通知机制（已禁用）")
                    notification_decision = {"should_notify": False, "reason": "通知机制已禁用"}
                # pdb.set_trace()
                return {
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "analysis_result": analysis_result,
                    "notification_sent": notification_decision.get("should_notify", False),
                    "notification_decision": notification_decision,
                    "status": "success"
                }
            else:
                print(f"警告: {agent_name} 未返回分析结果")
                return {
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "status": "no_result"
                }
                
        except Exception as e:
            print(f"错误: {agent_name} 执行失败: {str(e)}")
            print("完整错误信息:")
            traceback.print_exc()
            return {
                "agent_id": agent_id,
                "agent_name": agent_name,
                "error": str(e),
                "status": "error"
            }
    
    def run_full_analysis_with_communications(self, tickers: List[str], start_date: str, end_date: str, 
                                            parallel: bool = True, enable_communications: bool = True, 
                                            enable_notifications: bool = True, state=None, mode: str = "signal") -> Dict[str, Any]:
        """运行带通信机制的完整分析流程
        
        Args:
            tickers: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            parallel: 是否并行执行
            enable_communications: 是否启用通信机制
            enable_notifications: 是否启用通知机制
            state: 预创建的状态对象（用于多日模式中的状态继承）
            mode: 运行模式 ("signal" 或 "portfolio")
        """
        # 创建或使用提供的状态
        if state is None:
            print("开始高级投资分析会话（包含通信机制）")
            print("=" * 70)
            print(f"分析股票: {', '.join(tickers)}")
            print(f"时间范围: {start_date} 至 {end_date}")
            print(f"执行模式: {'并行' if parallel else '串行'}")
            print(f"运行模式: {mode.upper()}")
            print(f"通信功能: {'启用' if enable_communications else '禁用'}")
            print(f"通知功能: {'启用' if enable_notifications else '禁用'}")

            # 创建基础状态
            state = self.create_base_state(tickers, start_date, end_date)
            state["metadata"]["communication_enabled"] = enable_communications
            state["metadata"]["notifications_enabled"] = enable_notifications
            state["metadata"]["mode"] = mode
            
            # 如果是portfolio模式，初始化投资组合
            if mode == "portfolio":
                # 从metadata或使用默认值
                initial_cash = state["metadata"].get("initial_cash", 100000.0)
                margin_requirement = state["metadata"].get("margin_requirement", 0.0)
                
                state["data"]["portfolio"] = {
                    "cash": initial_cash,
                    "positions": {},
                    "margin_requirement": margin_requirement,
                    "margin_used": 0.0
                }
            # 提前确定本次会话的输出文件路径，供通信过程落盘复用
            output_dir = os.path.join(current_dir, "analysis_results_logs")
            output_file = f"{output_dir}/communications_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            state["metadata"]["output_file"] = output_file
        else:
            # 使用提供的状态，但更新基础数据
            state["data"]["tickers"] = tickers
            state["data"]["start_date"] = start_date
            state["data"]["end_date"] = end_date
            print(f"继续多日分析: {start_date} 至 {end_date}")
        
        # 第一步：运行所有分析师（第一轮）
        if parallel:
            analyst_results = self.run_analysts_parallel(state)
        else:
            analyst_results = self.run_analysts_sequential(state)
        
        # 第二步：基于通知的第二轮分析（可选）
        notifications_enabled = state["metadata"].get("notifications_enabled", True)
        if notifications_enabled:
            print("\n开始第二轮分析（基于通知和第一轮结果）...")
            second_round_results = self.run_second_round_analysis(analyst_results, state, parallel)
        else:
            print("\n⚡ 跳过第二轮分析（通知机制已禁用）- 直接使用第一轮结果")
            second_round_results = analyst_results  # 直接使用第一轮结果
        
        # 第三步：风险管理分析
        print("\n开始风险管理分析...")
        risk_analysis_results = self.run_risk_management_analysis(state, mode)
        
        # 第四步：投资组合管理决策（包含通信机制）
        print("\n开始投资组合管理决策...")
        portfolio_management_results = self.run_portfolio_management_with_communications(
            state, enable_communications, mode
        )
        # print(portfolio_management_results.keys())
        # print(portfolio_management_results['portfolio_summary'])
        # print(portfolio_management_results['final_execution_report'])
        # print(portfolio_management_results['portfolio_summary'])
        # 生成最终报告
        final_report = self.generate_final_report(second_round_results, state)
        
        return {
            "first_round_results": analyst_results,
            "final_analyst_results": second_round_results,
            "risk_analysis_results": risk_analysis_results,
            "portfolio_management_results": portfolio_management_results,
            "communication_logs": state["data"]["communication_logs"],
            "final_report": final_report, 
            "analysis_timestamp": datetime.now().isoformat(),
            "tickers": tickers,
            "date_range": {"start": start_date, "end": end_date},
            "output_file": state["metadata"].get("output_file")
        }
    
    def run_analysts_parallel(self, state: AgentState) -> Dict[str, Any]:
        """并行执行所有分析师"""
        print("启动并行分析...")
        start_time = datetime.now()
        
        # 为每个分析师创建独立的状态副本，避免并发冲突
        analyst_states = {}
        for agent_id in self.core_analysts.keys():
            analyst_states[agent_id] = deepcopy(state)
        
        analyst_results = {}
        
        # 使用ThreadPoolExecutor进行并行执行
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            # 提交所有任务
            future_to_agent = {}
            for agent_id, agent_info in self.core_analysts.items():
                future = executor.submit(
                    self.run_analyst_with_notifications_safe,
                    agent_id, 
                    agent_info, 
                    analyst_states[agent_id]
                )
                future_to_agent[future] = agent_id
            
            # 收集结果
            completed_count = 0
            for future in concurrent.futures.as_completed(future_to_agent):
                agent_id = future_to_agent[future]
                agent_name = self.core_analysts[agent_id]['name']
                
                try:
                    result = future.result()
                    analyst_results[agent_id] = result
                    completed_count += 1
                    
                    print(f"{agent_name} 完成 ({completed_count}/4)")
                    
                    # 合并分析结果到主状态
                    if result.get("status") == "success" and "analysis_result" in result:
                        state["data"]["analyst_signals"][agent_id] = result["analysis_result"]
                    
                except Exception as e:
                    print(f"错误: {agent_name} 执行出错: {str(e)}")
                    analyst_results[agent_id] = {
                        "agent_id": agent_id,
                        "agent_name": agent_name,
                        "error": str(e),
                        "status": "error"
                    }
        
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()
        print(f"\n并行执行完成，总耗时: {execution_time:.2f} 秒")
        print("=" * 40)
        
        return analyst_results
    
    def run_analysts_sequential(self, state: AgentState) -> Dict[str, Any]:
        """串行执行所有分析师"""
        analyst_results = {}
        
        for agent_id, agent_info in self.core_analysts.items():
            result = self.run_analyst_with_notifications(agent_id, agent_info, state)
            analyst_results[agent_id] = result
            print("\n" + "-" * 40)
        
        return analyst_results
    
    def run_analyst_with_notifications_safe(self, agent_id: str, agent_info: Dict, 
                                          state: AgentState) -> Dict[str, Any]:
        """线程安全的分析师执行函数"""
        try:
            return self.run_analyst_with_notifications(agent_id, agent_info, state)
        except Exception as e:
            logging.error(f"Error in {agent_id}: {str(e)}")
            return {
                "agent_id": agent_id,
                "agent_name": agent_info['name'],
                "error": str(e),
                "status": "error"
            }
    
    def run_second_round_analysis(self, first_round_results: Dict[str, Any], 
                                state: AgentState, parallel: bool = True) -> Dict[str, Any]:
        """运行第二轮分析：基于第一轮结果和通知的修正"""
        print("准备第二轮分析数据...")
        
        # 生成第一轮的final_report
        first_round_report = self.generate_final_report(first_round_results, state)
        
        # 执行第二轮分析
        if parallel:
            second_round_results = self.run_second_round_parallel(first_round_report, state)
        else:
            second_round_results = self.run_second_round_sequential(first_round_report, state)
        
        return second_round_results
    
    def run_second_round_parallel(self, first_round_report: Dict, state: AgentState) -> Dict[str, Any]:
        """并行执行第二轮分析"""
        print("启动第二轮并行分析...")
        start_time = datetime.now()
        
        # 为每个分析师创建独立的状态副本
        analyst_states = {}
        for agent_id in self.core_analysts.keys():
            analyst_states[agent_id] = deepcopy(state)
            # 清除第一轮的分析结果，避免冲突
            analyst_states[agent_id]["data"]["analyst_signals"] = {}
        
        second_round_results = {}
        
        # 使用ThreadPoolExecutor进行并行执行
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            # 提交所有任务
            future_to_agent = {}
            for agent_id, agent_info in self.core_analysts.items():
                future = executor.submit(
                    self.run_second_round_single_analyst,
                    agent_id, 
                    agent_info, 
                    first_round_report,
                    analyst_states[agent_id]
                )
                future_to_agent[future] = agent_id
            
            # 收集结果
            completed_count = 0
            for future in concurrent.futures.as_completed(future_to_agent):
                agent_id = future_to_agent[future]
                agent_name = self.core_analysts[agent_id]['name']
                
                try:
                    result = future.result()
                    second_round_results[agent_id] = result
                    completed_count += 1
                    
                    print(f"{agent_name} 第二轮分析完成 ({completed_count}/4)")
                    
                    # 合并分析结果到主状态
                    if result.get("status") == "success" and "analysis_result" in result:
                        state["data"]["analyst_signals"][agent_id] = result["analysis_result"]
                    
                except Exception as e:
                    print(f"错误: {agent_name} 第二轮分析出错: {str(e)}")
                    second_round_results[agent_id] = {
                        "agent_id": agent_id,
                        "agent_name": agent_name,
                        "error": str(e),
                        "status": "error"
                    }
        
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()
        print(f"\n第二轮并行分析完成，总耗时: {execution_time:.2f} 秒")
        print("=" * 40)
        return second_round_results
    
    def run_second_round_sequential(self, first_round_report: Dict, state: AgentState) -> Dict[str, Any]:
        """串行执行第二轮分析"""
        second_round_results = {}
        
        for agent_id, agent_info in self.core_analysts.items():
            result = self.run_second_round_single_analyst(
                agent_id, agent_info, first_round_report, state
            )
            second_round_results[agent_id] = result
            print("\n" + "-" * 40)
        
        return second_round_results
    
    def run_second_round_single_analyst(self, agent_id: str, agent_info: Dict, 
                                      first_round_report: Dict, 
                                      state: AgentState) -> Dict[str, Any]:
        """运行单个分析师的第二轮LLM分析"""
        agent_name = agent_info['name']
        
        print(f"\n{agent_name} 开始第二轮LLM分析...")
        
        try:
            # 获取分析师记忆并开始第二轮分析会话
            analyst_memory = memory_manager.get_analyst_memory(agent_id)
            session_id = None
            # if analyst_memory:
            #     tickers = state["data"]["tickers"]
            #     session_id = analyst_memory.start_analysis_session(
            #         session_type="second_round",
            #         tickers=tickers,
            #         context={"first_round_report": first_round_report}
            #     )
            
            # 提取需要的数据
            tickers = state["data"]["tickers"]
            
            # 获取第一轮分析结果
            first_round_analysis = first_round_report.get("analyst_signals", {}).get(agent_id, {})
            
            # 获取整体摘要
            overall_summary = first_round_report.get("summary", {})
            
            # 获取通知信息
            notifications = []
            notification_activity = first_round_report.get("notification_activity", {})
            if "recent_notifications" in notification_activity:
                notifications = notification_activity["recent_notifications"]
            
            # 运行LLM分析
            llm_analysis = run_second_round_llm_analysis(
                agent_id=agent_id,
                tickers=tickers,
                first_round_analysis=first_round_analysis,
                overall_summary=overall_summary,
                notifications=notifications,
                state=state
            )
            
            # 格式化结果
            analysis_result = format_second_round_result_for_state(llm_analysis)
            
            # 存储到状态中
            state["data"]["analyst_signals"][f"{agent_id}_round2"] = analysis_result
            
            print(f"{agent_name} 第二轮LLM分析完成")
            
            # 记录第二轮分析结果到记忆
            if analyst_memory and session_id:
                analysis_summary = f"第二轮分析完成，基于第一轮结果和通知进行了调整"
                analyst_memory.add_analysis_message(
                    session_id, "assistant", analysis_summary,
                    {"llm_analysis": llm_analysis.model_dump()}
                )
                analyst_memory.complete_analysis_session(session_id, analysis_result)
            
            # 显示每个ticker的信号
            for ticker_signal in llm_analysis.ticker_signals:
                signal_emoji = {"bullish": "📈", "bearish": "📉", "neutral": "➖"}
                emoji = signal_emoji.get(ticker_signal.signal, "❓")
                print(f"  {emoji} {ticker_signal.ticker}: {ticker_signal.signal.upper()} "
                      f"(信心度: {ticker_signal.confidence}%)")
            
            return {
                "agent_id": agent_id,
                "agent_name": agent_name,
                "analysis_result": analysis_result,
                "llm_analysis": llm_analysis,
                "round": 2,
                "status": "success"
            }
            
        except Exception as e:
            print(f"错误: {agent_name} 第二轮LLM分析失败: {str(e)}")
            import traceback
            traceback.print_exc()
            
            # 创建失败结果
            fallback_result = {
                "analyst_id": agent_id,
                "analyst_name": agent_name,
                "ticker_signals": [
                    {
                        "ticker": ticker,
                        "signal": "neutral",
                        "confidence": 50,
                        "reasoning": f"由于错误无法完成分析: {str(e)}"
                    } for ticker in state["data"]["tickers"]
                ],
                "timestamp": datetime.now().isoformat(),
                "analysis_type": "second_round_llm_failed"
            }
            
            return {
                "agent_id": agent_id,
                "agent_name": agent_name,
                "analysis_result": fallback_result,
                "error": str(e),
                "round": 2,
                "status": "error"
            }
    
    def run_risk_management_analysis(self, state: AgentState, mode: str = "signal") -> Dict[str, Any]:
        """
        运行风险管理分析
        
        Args:
            state: 当前状态
            mode: 运行模式 ("signal" 或 "portfolio")
        """
        print("执行风险管理分析...")
        if self.streamer:
            self.streamer.print("system", "===== 风险管理分析 =====")
        
        try:
            # 根据模式选择相应的Risk Manager - 使用新架构
            if mode == "portfolio":
                agent_id = "risk_manager"
                # 使用新架构的 RiskManagerAgent
                risk_agent = RiskManagerAgent(agent_id=agent_id, mode="portfolio")
                risk_result = risk_agent.execute(state)
            else:
                agent_id = "risk_manager"
                risk_result = risk_management_agent(state, agent_id=agent_id)
            
            risk_analysis = state["data"]["analyst_signals"].get(agent_id, {})
            
            if risk_analysis:
                print("风险管理分析完成")
                # if self.streamer:
                #     self.streamer.print("system", "风险管理分析完成")
                
                # 显示每个ticker的风险分析
                for ticker, risk_data in risk_analysis.items():
                    # 判断是signal模式还是portfolio模式
                    if "risk_level" in risk_data:
                        # Signal模式
                        risk_level = risk_data.get("risk_level", "unknown")
                        risk_score = risk_data.get("risk_score", 0)
                        current_price = risk_data.get("current_price", 0)
                        vol_info = risk_data.get("volatility_info", {})
                        annualized_vol = vol_info.get("annualized_volatility", 0)
                        risk_assessment = risk_data.get("risk_assessment", "")
                        
                        print(f"  {ticker}:")
                        print(f"     风险等级: {risk_level.upper()}")
                        print(f"     风险评分: {risk_score}/100")
                        print(f"     年化波动率: {annualized_vol:.1%}")
                        print(f"     风险评估: {risk_assessment}")
                        
                        if self.streamer:
                            self.streamer.print("agent", 
                                f"{ticker}: \n"
                                f"  风险等级 {risk_level.upper()}\n"
                                f"  风险评分 {risk_score}/100\n"
                                f"  年化波动率 {annualized_vol:.1%}\n"
                                f"  {risk_assessment}",
                                role_key="risk_manager"
                            )
                    else:
                        # Portfolio模式
                        current_price = risk_data.get("current_price", 0)
                        max_shares = risk_data.get("max_shares", 0)
                        remaining_limit = risk_data.get("remaining_position_limit", 0)
                        vol_metrics = risk_data.get("volatility_metrics", {})
                        annualized_vol = vol_metrics.get("annualized_volatility", 0)
                        reasoning = risk_data.get("reasoning", {})
                        position_limit_pct = reasoning.get("base_position_limit_pct", 0)
                        
                        if self.streamer:
                            self.streamer.print("agent", 
                                f"{ticker}: \n"
                                f"  价格 ${current_price:.2f}\n"
                                f"  最大可买 {max_shares} 股\n"
                                f"  波动率 {annualized_vol:.1%}\n"
                                f"  仓位限制 {position_limit_pct:.1%}\n",
                                role_key="risk_manager"
                            )
                
                return {
                    "agent_id": "risk_manager",
                    "agent_name": "风险管理分析师",
                    "analysis_result": risk_analysis,
                    "status": "success"
                }
            else:
                print("警告: 风险管理分析未返回结果")
                if self.streamer:
                    self.streamer.print("system", "警告: 风险管理分析未返回结果")
                return {
                    "agent_id": "risk_management_agent",
                    "agent_name": "风险管理分析师", 
                    "status": "no_result"
                }
                
        except Exception as e:
            print(f"错误: 风险管理分析失败: {str(e)}")
            traceback.print_exc()
            return {
                "agent_id": "risk_management_agent",
                "agent_name": "风险管理分析师",
                "error": str(e),
                "status": "error"
            }
    
    def run_portfolio_management_with_communications(self, state: AgentState, 
                                                   enable_communications: bool = True,
                                                   mode: str = "signal") -> Dict[str, Any]:
        """
        运行投资组合管理（包含通信机制）
        
        Args:
            state: 当前状态
            enable_communications: 是否启用通信机制
            mode: 运行模式 ("signal" 或 "portfolio")
        """
        # print("执行投资组合管理决策...")
        
        try:
            # 根据模式选择相应的Portfolio Manager - 使用新架构
            # ⭐ 统一使用 "portfolio_manager" 作为 agent_id（无论什么模式）
            if mode == "portfolio":
                # 使用新架构的 PortfolioManagerAgent（Portfolio模式）
                pm_agent = PortfolioManagerAgent(agent_id="portfolio_manager", mode="portfolio")
                portfolio_result = pm_agent.execute(state)
            else:
                # Direction模式
                portfolio_result = portfolio_management_agent(state, agent_id="portfolio_manager")
            
            # 更新state
            if portfolio_result and "messages" in portfolio_result:
                state["messages"] = portfolio_result["messages"]
                state["data"] = portfolio_result["data"]

            # 获取初始投资决策（统一使用 "portfolio_manager"）
            initial_decisions = self._extract_portfolio_decisions(state, agent_name="portfolio_manager")
            # pdb.set_trace()
            print('initial_decisions',initial_decisions)
            if not initial_decisions:
                print("警告: 未能获取初始投资决策")
                return {
                    "agent_id": "portfolio_manager",
                    "agent_name": "投资组合管理者",
                    "error": "无法获取初始决策",
                    "status": "error"
                }
            
            print("初始投资组合决策完成")
            
            # 如果启用通信机制
            if enable_communications:
                print("\n启动高级通信机制...")
                max_cycles = 3
                try:
                    max_cycles = int(state["metadata"].get("max_communication_cycles", 3))
                except Exception:
                    max_cycles = 3
                
                final_decisions = initial_decisions
                last_decision_dump = None
                communication_results = {}
                
                for cycle in range(1, max_cycles + 1):
                    print(f"\n沟通循环 第{cycle}/{max_cycles} 轮")
                    if cycle == 1:
                        self.streamer.print("system",f"启动高级通信机制...\n===== 沟通循环 第{cycle}/{max_cycles} 轮 =====\n")
                    else:
                        self.streamer.print("system",f"===== 沟通循环 第{cycle}/{max_cycles} 轮 =====\n")
                    # 获取分析师信号（每轮刷新）
                    analyst_signals = {}
                    if cycle ==1:
                        for agent_id in self.core_analysts.keys():
                            if agent_id in state["data"]["analyst_signals"]:
                                analyst_signals[agent_id] = state["data"]["analyst_signals"][agent_id]
                    else:
                        analyst_signals = updated_signals
                    # print(analyst_signals)
                    # 决定通信策略
                    # pdb.set_trace()
                    communication_decision = communication_manager.decide_communication_strategy(
                        manager_signals=final_decisions,
                        analyst_signals=analyst_signals,
                        state=state
                    )
                    last_decision_dump = communication_decision.model_dump()
                    # 记录通信决策
                    # 确保 communication_decisions 字段存在
                    if "communication_decisions" not in state["data"]["communication_logs"]:
                        state["data"]["communication_logs"]["communication_decisions"] = []
                    
                    state["data"]["communication_logs"]["communication_decisions"].append({
                        "timestamp": datetime.now().isoformat(),
                        "decision": last_decision_dump
                    })
                    
                    if not communication_decision.should_communicate:
                        print("决定不进行额外通信")
                        print(f"原因: {communication_decision.reasoning}")
                        break
                    print(f"选择通信类型: {communication_decision.communication_type}")
                    print(f"讨论话题: {communication_decision.discussion_topic}")
                    print(f"目标分析师: {', '.join(communication_decision.target_analysts)}")
                    self.streamer.print("agent",f"选择通信类型: {communication_decision.communication_type}\n讨论话题: {communication_decision.discussion_topic}\n需参与分析师: {', '.join(communication_decision.target_analysts)}",role_key="portfolio_manager")
                    if communication_decision.communication_type == "private_chat":
                        # 进行私聊
                        communication_results = self.conduct_private_chats(
                            communication_decision, analyst_signals, state
                        )
                    elif communication_decision.communication_type == "meeting":
                        # 进行会议
                        communication_results = self.conduct_meeting(
                            communication_decision, analyst_signals, state
                        )
                    else:
                        communication_results = {}
                    # pdb.set_trace()
                    # 如果有信号调整，重新运行投资组合决策
                    if communication_results.get("signals_adjusted", False):
                        print("\n基于通信结果重新生成投资决策...")
                        self.streamer.print("agent","基于通信结果重新生成投资决策...",role_key="portfolio_manager")
                        # 更新分析师信号
                        updated_signals = communication_results.get("updated_signals", {})
                        for agent_id, updated_signal in updated_signals.items():
                            state["data"]["analyst_signals"][f"{agent_id}_post_communication_cycle{cycle}"] = updated_signal
                        
                        # # 重新运行风险管理分析（确保有最新的价格和限额数据）
                        # print("重新运行风险管理分析...")
                        # risk_analysis_results = self.run_risk_management_analysis(state)
                        
                        # 重新运行投资组合管理（根据模式选择正确的agent）- 使用新架构
                        # ⭐ 统一使用 "portfolio_manager" 作为 agent_id
                        if mode == "portfolio":
                            # 使用新架构的 PortfolioManagerAgent（Portfolio模式）
                            pm_agent = PortfolioManagerAgent(agent_id="portfolio_manager", mode="portfolio")
                            final_portfolio_result = pm_agent.execute(state)
                        else:
                            # Direction模式
                            final_portfolio_result = portfolio_management_agent(state, agent_id="portfolio_manager")
                        
                        if final_portfolio_result and "messages" in final_portfolio_result:
                            state["messages"] = final_portfolio_result["messages"]
                            state["data"] = final_portfolio_result["data"]
                        
                        # 统一使用 "portfolio_manager" 提取决策
                        new_final_decisions = self._extract_portfolio_decisions(state, agent_name="portfolio_manager")
                        if new_final_decisions:
                            final_decisions = new_final_decisions
                            print("基于通信结果的投资决策已更新")
                            self.streamer.print("agent","基于通信结果的投资决策已更新",role_key="portfolio_manager")
                        else:
                            print("警告: 决策更新失败，保留上一轮决策")
                            self.streamer.print("system","警告: 决策更新失败，保留上一轮决策")
                    else:
                        print("本轮沟通未导致信号调整，结束循环")
                        break
                    
                # 执行最终交易决策
                print("\n执行最终交易决策...")
                print('final_decisions',final_decisions)
                
                # 格式化最终决策为易读文本
                if self.streamer:
                    decision_lines = ["执行最终交易决策"]
                    for ticker, decision in final_decisions.items():
                        action = decision.get('action', 'N/A')
                        confidence = decision.get('confidence', 0)
                        reasoning = decision.get('reasoning', '')
                        
                        # 为不同的action添加emoji
                        if mode == "portfolio":
                            action_emoji = {
                                'buy': '📈 买入',
                                'sell': '📉 卖出',
                                'short': '🔻 做空',
                                'cover': '🔺 平空',
                                'hold': '⏸️ 持有'
                            }
                        else:
                            action_emoji = {
                                'long': '📈 做多',
                                'short': '📉 做空',
                                'hold': '⏸️ 持有'
                            }
                        action_display = action_emoji.get(action, action)
                        
                        decision_lines.append(f"\n【{ticker}】")
                        decision_lines.append(f"  决策: {action_display}")
                        if mode == "portfolio":
                            quantity = decision.get('quantity', 0)
                            decision_lines.append(f"  数量: {quantity}股")
                        decision_lines.append(f"  置信度: {confidence}%")
                        # 打印完整的reasoning，不截断
                        if reasoning:
                            decision_lines.append(f"  💭 理由: {reasoning}")
                    
                    agent_key = "portfolio_manager"
                    self.streamer.print("agent", "\n".join(decision_lines), role_key=agent_key)
                
                final_execution_report = self._execute_portfolio_trades(state, final_decisions, mode)
                
                # 生成简化的摘要信息
                portfolio_summary = {"status": "signal_based_analysis"}
                
                return {
                    "agent_id": "portfolio_manager",
                    "agent_name": "投资组合管理者",
                    "initial_decisions": initial_decisions,
                    "final_decisions": final_decisions,
                    "communication_decision": last_decision_dump,
                    "communication_results": communication_results,
                    "final_execution_report": final_execution_report,
                    "portfolio_summary": portfolio_summary,
                    "communications_enabled": True,
                    "status": "success"
                }
            
            else:
                # 不启用通信机制，直接执行初始决策的交易
                print("\n执行初始交易决策...")
                execution_report = self._execute_portfolio_trades(state, initial_decisions, mode)
                
                # 生成简化的摘要信息
                portfolio_summary = {"status": "signal_based_analysis"}
                
                return {
                    "agent_id": "portfolio_manager",
                    "agent_name": "投资组合管理者",
                    "final_decisions": initial_decisions,
                    "execution_report": execution_report,
                    "portfolio_summary": portfolio_summary,
                    "communications_enabled": False,
                    "status": "success"
                }
                
        except Exception as e:
            print(f"错误: 投资组合管理决策失败: {str(e)}")
            traceback.print_exc()
            return {
                "agent_id": "portfolio_manager",
                "agent_name": "投资组合管理者",
                "error": str(e),
                "status": "error"
            }
    
    def conduct_private_chats(self, communication_decision: CommunicationDecision,
                            analyst_signals: Dict[str, Any], state: AgentState) -> Dict[str, Any]:
        """进行私聊通信"""
        print("开始私聊通信...")
        if self.streamer:
            self.streamer.print("system", f"===== 私聊通信 =====\n话题: {communication_decision.discussion_topic}")
        
        chat_results = {}
        updated_signals = {}
        total_adjustments = 0
        
        for analyst_id in communication_decision.target_analysts:
            if analyst_id in analyst_signals:
                print(f"\n与 {analyst_id} 开始私聊...")
                if self.streamer:
                    self.streamer.print("system", f"portfolio_manager <-> {analyst_id} 开始私聊")
                
                chat_result = communication_manager.conduct_private_chat(
                    manager_id="portfolio_manager",
                    analyst_id=analyst_id,
                    topic=communication_decision.discussion_topic,
                    analyst_signal=analyst_signals[analyst_id],
                    state=state,
                    max_rounds=2,
                    streamer=self.streamer  # 传递 streamer
                )
                # pdb.set_trace()
                chat_results[analyst_id] = chat_result
                
                # 检查是否有信号调整
                if "final_analyst_signal" in chat_result:
                    updated_signals[analyst_id] = chat_result["final_analyst_signal"]
                    adjustments = chat_result.get("adjustments_made", 0)
                    total_adjustments += adjustments
                    
                    if self.streamer and adjustments > 0:
                        self.streamer.print("agent", 
                            f"信号已调整 {adjustments} 次",
                            role_key=analyst_id
                        )
                
                # 记录到通信日志
                state["data"]["communication_logs"]["private_chats"].append({
                    "timestamp": datetime.now().isoformat(),
                    "manager": "portfolio_manager",
                    "analyst": analyst_id,
                    "topic": communication_decision.discussion_topic,
                    "result": chat_result
                })
        
        print(f"\n私聊通信完成，共 {total_adjustments} 次信号调整")
        if self.streamer:
            self.streamer.print("system", f"私聊通信完成，共 {total_adjustments} 次信号调整")
        
        return {
            "communication_type": "private_chat",
            "chat_results": chat_results,
            "updated_signals": updated_signals,
            "signals_adjusted": total_adjustments > 0,
            "total_adjustments": total_adjustments
        }
    
    def conduct_meeting(self, communication_decision: CommunicationDecision,
                       analyst_signals: Dict[str, Any], state: AgentState) -> Dict[str, Any]:
        """进行会议通信"""
        print("开始会议通信...")
        # if self.streamer:
        #     self.streamer.print("system", f"===== 会议通信 =====\n话题: {communication_decision.discussion_topic}\n \t参与者: portfolio_manager, {', '.join(communication_decision.target_analysts)}")

        # 准备会议参与的分析师信号
        meeting_signals = {}
        for analyst_id in communication_decision.target_analysts:
            if analyst_id in analyst_signals:
                meeting_signals[analyst_id] = analyst_signals[analyst_id]
        
        meeting_result = communication_manager.conduct_meeting(
            manager_id="portfolio_manager",
            analyst_ids=communication_decision.target_analysts,
            topic=communication_decision.discussion_topic,
            analyst_signals=meeting_signals,
            state=state,
            max_rounds=2,
            streamer=self.streamer  # 传递 streamer
        )
        
        # 记录到通信日志
        state["data"]["communication_logs"]["meetings"].append({
            "timestamp": datetime.now().isoformat(),
            "meeting_id": meeting_result["meeting_id"],
            "host": "portfolio_manager",
            "participants": communication_decision.target_analysts,
            "topic": communication_decision.discussion_topic,
            "result": meeting_result
        })
        
        total_adjustments = meeting_result.get("adjustments_made", 0)
        print(f"\n会议通信完成，共 {total_adjustments} 次信号调整")
        if self.streamer:
            meeting_summary = [f"会议通信完成，共 {total_adjustments} 次信号调整"]
            if total_adjustments > 0:
                meeting_summary.append(f"信号已更新: {', '.join(meeting_result.get('final_signals', {}).keys())}")
            self.streamer.print("system", "\n".join(meeting_summary))
        
        return {
            "communication_type": "meeting",
            "meeting_result": meeting_result,
            "updated_signals": meeting_result.get("final_signals", {}),
            "signals_adjusted": total_adjustments > 0,
            "total_adjustments": total_adjustments
        }
    
    def _extract_portfolio_decisions(self, state: AgentState, agent_name: str = "portfolio_manager") -> Dict[str, Any]:
        """从状态中提取投资组合决策（AgentScope 格式）"""
        try:
            if state["messages"]:
                # 从后往前查找指定agent的消息
                for message in reversed(state["messages"]):
                    # AgentScope 格式: {"name": str, "content": str, "role": str, "metadata": dict}
                    if isinstance(message, dict):
                        message_name = message.get("name")
                        message_content = message.get("content")
                        
                        # 检查是否匹配指定的 agent
                        if message_name == agent_name and message_content:
                            try:
                                return json.loads(message_content)
                            except json.JSONDecodeError:
                                # 如果 content 不是 JSON，尝试直接返回
                                return message_content if isinstance(message_content, dict) else {}
            return {}
        except Exception as e:
            print(f"警告: 提取投资决策失败: {str(e)}")
            import traceback
            print(f"详细错误: {traceback.format_exc()}")
            return {}
    
    def _execute_portfolio_trades(self, state: AgentState, decisions: Dict[str, Any], mode: str = "signal") -> Dict[str, Any]:
        """
        执行投资组合交易决策
        
        Args:
            state: 当前状态
            decisions: PM的决策
            mode: 运行模式 ("signal" 或 "portfolio")
        """
        try:
            # 获取当前价格数据
            current_prices = state["data"].get("current_prices", {})
            if not current_prices:
                print("警告: 无法获取当前价格数据，跳过交易执行")
                return {"status": "skipped", "reason": "缺少价格数据"}
            
            # 检查是否有有效的价格数据（价格大于0）
            valid_prices = {ticker: price for ticker, price in current_prices.items() if price > 0}
            if not valid_prices:
                print("警告: 所有价格数据无效（价格为0或负数），跳过交易执行")
                print(f"价格数据: {current_prices}")
                return {"status": "skipped", "reason": "无有效价格数据"}
            
            if mode == "portfolio":
                # Portfolio模式：执行具体交易并更新持仓
                from src.utils.trade_executor import execute_portfolio_trades
                
                portfolio = state["data"].get("portfolio", {
                    "cash": 100000.0,
                    "positions": {},
                    "margin_requirement": 0.5,
                    "margin_used": 0.0
                })
                
                execution_report = execute_portfolio_trades(
                    pm_decisions=decisions,
                    current_prices=current_prices,
                    portfolio=portfolio,
                    current_date=state["data"].get("end_date")
                )
                
                # 更新state中的投资组合
                state["data"]["portfolio"] = execution_report.get("updated_portfolio", portfolio)
                
                # 添加执行报告到state
                if "execution_reports" not in state["data"]:
                    state["data"]["execution_reports"] = []
                state["data"]["execution_reports"].append(execution_report)
                
                print(f"Portfolio交易执行完成，执行了{len(execution_report.get('executed_trades', []))}笔交易")
                
            else:
                # Signal模式：只记录方向信号
                execution_report = execute_trading_decisions(
                    pm_decisions=decisions,
                    current_date=state["data"].get("end_date")
                )
                
                # 添加执行报告到state
                if "execution_reports" not in state["data"]:
                    state["data"]["execution_reports"] = []
                state["data"]["execution_reports"].append(execution_report)
                
                print(f"信号记录完成，记录了{execution_report.get('total_signals', 0)}个方向信号")
            
            return execution_report
            
        except Exception as e:
            error_msg = f"交易执行失败: {str(e)}"
            print(f"错误: {error_msg}")
            print(f"错误详情: {traceback.format_exc()}")
            return {"status": "error", "error": error_msg}
    
    def generate_final_report(self, analyst_results: Dict[str, Any], 
                            state: AgentState) -> Dict[str, Any]:
        """生成最终分析报告"""
        
        # 统计分析结果
        successful_analyses = [r for r in analyst_results.values() if r["status"] == "success"]
        failed_analyses = [r for r in analyst_results.values() if r["status"] == "error"]
        
        # 统计通知活动
        total_notifications_sent = sum(1 for r in successful_analyses if r.get("notification_sent", False))
        
        # 收集所有分析信号
        all_signals = {}
        for result in successful_analyses:
            if "analysis_result" in result:
                all_signals[result["agent_id"]] = result["analysis_result"]
        
        # 生成通知摘要
        # notification_summary = self.generate_notification_summary(analyst_results)
        
        report = {
            "summary": {
                "total_analysts": len(analyst_results),
                "successful_analyses": len(successful_analyses),
                "failed_analyses": len(failed_analyses),
                "notifications_sent": total_notifications_sent
            },
            "analyst_signals": all_signals,
            # "notification_activity": notification_summary,
            "errors": [{"agent": r["agent_id"], "error": r["error"]} 
                      for r in failed_analyses]
        }
        return report
    
    def generate_notification_summary(self, analyst_results: Dict[str, Any]) -> Dict[str, Any]:
        """生成通知活动摘要（基于analyst_results）"""
        summary: Dict[str, Any] = {
            "total_notifications": 0,
            "notifications_by_agent": {},
            "recent_notifications": []
        }

        # 直接从analyst_results中获取通知决策信息
        notifications_sent = 0
        current_time = datetime.now()
        
        print(f"📊 正在生成通知摘要，分析结果数量: {len(analyst_results)}")
        # pdb.set_trace()
        for agent_id, result in analyst_results.items():
            # 检查是否有notification_decision
            if result.get("status") == "success" and "notification_decision" in result:
                decision = result["notification_decision"]
                agent_name = result.get("agent_name", agent_id)
                
                # 统计每个agent的通知情况
                if decision.get("should_notify", False):
                    notifications_sent += 1
                    summary["notifications_by_agent"][agent_name] = 1
                    
                    # 添加到最近通知列表
                    summary["recent_notifications"].append({
                        "sender": agent_name,
                        "content": decision.get("content", "")[:200],
                        "urgency": decision.get("urgency", "medium"),
                        "category": decision.get("category", "general"),
                        "timestamp": current_time.strftime("%H:%M:%S")
                    })
                else:
                    # 即使没发送通知也记录一下（计数为0）
                    summary["notifications_by_agent"][agent_name] = 0
            else:
                print(f"   {agent_id}: 分析失败或无通知决策")

        summary["total_notifications"] = notifications_sent
        print(f"通知摘要生成完成，总通知数: {notifications_sent}")
        
        return summary
    
    def print_session_summary(self, results: Dict[str, Any]):
        """打印会话摘要"""
        print("\n" + "=" * 70)
        print("高级投资分析会话摘要（包含通信机制）")
        print("=" * 70)
        
        report = results["final_report"]
        summary = report["summary"]
        
        print(f"分析股票: {', '.join(results['tickers'])}")
        print(f"分析时间: {results['analysis_timestamp']}")
        print(f"最终成功分析: {summary['successful_analyses']}/{summary['total_analysts']}")
        print(f"发送通知: {summary['notifications_sent']} 条")
        
        # 显示两轮分析信息
        if 'first_round_results' in results:
            first_round_success = len([r for r in results['first_round_results'].values() if r.get('status') == 'success'])
            print(f"第一轮分析: {first_round_success}/{len(results['first_round_results'])} 成功")
        
        if 'final_analyst_results' in results:
            second_round_success = len([r for r in results['final_analyst_results'].values() if r.get('status') == 'success'])
            print(f"第二轮分析: {second_round_success}/{len(results['final_analyst_results'])} 成功")
        
        # 显示风险管理分析结果
        if 'risk_analysis_results' in results:
            risk_status = results['risk_analysis_results'].get('status', 'unknown')
            risk_emoji = "✅" if risk_status == "success" else "❌"
            print(f"风险管理分析: {risk_status}")
        
        # 显示投资组合管理结果 
        if 'portfolio_management_results' in results:
            portfolio_status = results['portfolio_management_results'].get('status', 'unknown')
            portfolio_emoji = "✅" if portfolio_status == "success" else "❌"
            print(f"投资组合管理: {portfolio_status}")
            
            # 显示通信机制使用情况
            portfolio_results = results['portfolio_management_results']
            communications_enabled = portfolio_results.get('communications_enabled', False)
            print(f"通信机制: {'启用' if communications_enabled else '禁用'}")
            
            if communications_enabled and 'communication_decision' in portfolio_results:
                comm_decision = portfolio_results['communication_decision']
                if comm_decision['should_communicate']:
                    comm_type = comm_decision['communication_type']
                    print(f"     使用了 {comm_type} 通信")
                    if 'communication_results' in portfolio_results:
                        comm_results = portfolio_results['communication_results']
                        adjustments = comm_results.get('total_adjustments', 0)
                        print(f"     信号调整次数: {adjustments}")
                else:
                    print(f"     决定不进行通信")
        
        # 显示通信日志摘要
        if 'communication_logs' in results:
            comm_logs = results['communication_logs']
            private_chats_count = len(comm_logs.get('private_chats', []))
            meetings_count = len(comm_logs.get('meetings', []))
            
            if private_chats_count > 0 or meetings_count > 0:
                print(f"\n通信活动:")
                if private_chats_count > 0:
                    print(f"  私聊: {private_chats_count} 次")
                if meetings_count > 0:
                    print(f"  会议: {meetings_count} 次")
        
        if summary["failed_analyses"] > 0:
            print(f"失败分析: {summary['failed_analyses']}")
        
        # 打印通知活动
        notification_activity = report["notification_activity"]
        if notification_activity["total_notifications"] > 0:
            print(f"\n通知活动:")
            for agent, count in notification_activity["notifications_by_agent"].items():
                agent_name = self.core_analysts.get(agent, {}).get('name', agent)
                print(f"  - {agent_name}: {count} 条通知")
        
        print("=" * 70)


def main():
    """主函数"""
    # 创建高级分析引擎
    engine = AdvancedInvestmentAnalysisEngine()
    
    # 配置分析参数
    tickers = ["AAPL", "MSFT"]  # 可以修改要分析的股票
    start_date = "2024-01-01"
    end_date = "2024-03-01"
    parallel = True  # 默认使用并行模式
    enable_communications = True  # 默认启用通信机制
    
    # 检查命令行参数
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            if arg == "--sequential":
                parallel = False
                print("使用串行模式")
            elif arg == "--parallel":
                parallel = True
                print("使用并行模式")
            elif arg == "--no-communications":
                enable_communications = False
                print("禁用通信机制")
            elif arg == "--communications":
                enable_communications = True
                print("启用通信机制")
    
    try:
        # 运行完整分析
        results = engine.run_full_analysis_with_communications(
            tickers, start_date, end_date, 
            parallel=parallel, 
            enable_communications=enable_communications,
            enable_notifications=True  # 默认启用通知
        )
        
        # 打印摘要
        engine.print_session_summary(results)
        
        # 保存结果到文件（排除final_report）
        results_to_save = {
            "first_round_results": results["first_round_results"],
            "final_analyst_results": results["final_analyst_results"],
            "risk_analysis_results": results["risk_analysis_results"],
            "portfolio_management_results": results["portfolio_management_results"],
            "communication_logs": results["communication_logs"],
            "analysis_timestamp": results["analysis_timestamp"],
            "tickers": results["tickers"],
            "date_range": results["date_range"]
        }
        
        # 创建目录
        output_dir = os.path.join(current_dir, "analysis_results_logs")
        os.makedirs(output_dir, exist_ok=True)
        
        # 使用会话开始时确定的输出文件，确保通信过程与最终保存一致
        output_file = results.get("output_file")
        if not output_file:
            output_file = f"{output_dir}/communications_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results_to_save, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"\n详细结果已保存到: {output_file}")
        print(f"保存内容: 完整分析流程 + 通信日志（不包含final_report汇总）")
        
    except Exception as e:
        print(f"错误: 主程序执行失败: {str(e)}")
        traceback.print_exc()


def interactive_mode():
    """交互式模式"""
    print("\n高级投资分析系统 - 交互式模式（包含通信机制）")
    print("=" * 60)
    
    engine = AdvancedInvestmentAnalysisEngine()
    
    while True:
        try:
            print("\n请选择操作:")
            print("  1 - 运行完整分析（包含通信机制）")
            print("  2 - 运行简化分析（不含通信机制）")
            print("  3 - 查看通知历史")
            print("  4 - 查看通信日志")
            print("  q - 退出")
            print("-" * 30)
            
            choice = input("请输入选择: ").strip().lower()
            
            if choice == 'q':
                print("退出系统")
                break
            elif choice in ['1', '2']:
                enable_communications = choice == '1'
                
                # 获取用户输入
                tickers_input = input("请输入股票代码(用逗号分隔，如AAPL,MSFT): ").strip()
                tickers = [t.strip().upper() for t in tickers_input.split(',') if t.strip()]
                
                if not tickers:
                    print("错误: 请输入有效的股票代码")
                    continue
                
                start_date = input("请输入开始日期(YYYY-MM-DD): ").strip()
                end_date = input("请输入结束日期(YYYY-MM-DD): ").strip()
                
                # 选择执行模式
                mode_input = input("选择执行模式 (p-并行/s-串行，默认并行): ").strip().lower()
                parallel = mode_input != 's'
                
                # 运行分析
                results = engine.run_full_analysis_with_communications(
                    tickers, start_date, end_date, 
                    parallel=parallel,
                    enable_communications=enable_communications,
                    enable_notifications=True  # 默认启用通知
                )
                engine.print_session_summary(results)
                
            elif choice == '3':
                # 查看通知历史
                print("\n全局通知历史:")
                for notification in notification_system.global_notifications[-10:]:  # 最近10条
                    print(f"  {notification.timestamp.strftime('%H:%M:%S')} - "
                          f"{notification.sender_agent}: {notification.content}")
                
            elif choice == '4':
                # 查看通信日志
                print("\n通信日志功能尚未在交互模式中实现")
                print("请运行完整分析后查看保存的结果文件")
                
            else:
                print("无效选择，请重试")
                
        except KeyboardInterrupt:
            print("\n退出系统")
            break
        except Exception as e:
            print(f"执行错误: {str(e)}")


if __name__ == "__main__":
    # 检查命令行参数
    if len(sys.argv) > 1 and "--interactive" in sys.argv:
        interactive_mode()
    else:
        main()
