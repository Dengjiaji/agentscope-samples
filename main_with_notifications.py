#!/usr/bin/env python3
"""
主程序 - 带通知机制的多Agent投资分析系统
集成了四个核心分析师和通知系统
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

# 添加项目路径
sys.path.append('/root/wuyue.wy/Project/IA')

# 加载环境变量
load_dotenv('/root/wuyue.wy/Project/IA/.env')

from src.graph.state import AgentState
from langchain_core.messages import HumanMessage

# 导入所有四个核心分析师
from src.agents.fundamentals import fundamentals_analyst_agent
from src.agents.sentiment import sentiment_analyst_agent
from src.agents.technicals import technical_analyst_agent
from src.agents.valuation import valuation_analyst_agent

# 导入通知系统
from src.communication.notification_system import (
    notification_system, 
    should_send_notification,
    format_notifications_for_context
)

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('investment_analysis.log'),
        logging.StreamHandler()
    ]
)


class InvestmentAnalysisEngine:
    """投资分析引擎 - 协调所有分析师和通知系统"""
    
    def __init__(self):
        # 添加线程锁用于并行执行时的同步
        self._notification_lock = threading.Lock()
        self.core_analysts = {
            'fundamentals_analyst': {
                'name': '基本面分析师',
                'agent_func': fundamentals_analyst_agent,
                'description': '专注于财务数据和公司基本面分析'
            },
            'sentiment_analyst': {
                'name': '情绪分析师', 
                'agent_func': sentiment_analyst_agent,
                'description': '分析市场情绪和新闻舆论'
            },
            'technical_analyst': {
                'name': '技术分析师',
                'agent_func': technical_analyst_agent, 
                'description': '专注于技术指标和图表分析'
            },
            'valuation_analyst': {
                'name': '估值分析师',
                'agent_func': valuation_analyst_agent,
                'description': '专注于公司估值和价值评估'
            }
        }
        
        # 注册所有分析师到通知系统
        for agent_id in self.core_analysts.keys():
            notification_system.register_agent(agent_id)
        
        logging.info("投资分析引擎初始化完成")
    
    def create_base_state(self, tickers: List[str], start_date: str, end_date: str) -> AgentState:
        """创建基础的AgentState"""
        # 检查环境变量
        api_key = os.getenv('FINANCIAL_DATASETS_API_KEY')
        openai_key = os.getenv('OPENAI_API_KEY')
        model_name = os.getenv('MODEL_NAME', 'gpt-3.5-turbo')
        
        if not api_key or not openai_key:
            raise ValueError("缺少必要的API密钥，请检查环境变量设置")
        
        state = AgentState(
            messages=[HumanMessage(content="Investment analysis session")],
            data={
                "tickers": tickers,
                "start_date": start_date,
                "end_date": end_date,
                "analyst_signals": {},
                "api_keys": {
                    'FINANCIAL_DATASETS_API_KEY': api_key,
                    'OPENAI_API_KEY': openai_key,
                }
            },
            metadata={
                "show_reasoning": True,
                "model_name": model_name,
                "model_provider": "OpenAI"
            }
        )
        
        return state
    
    def run_analyst_with_notifications(self, agent_id: str, agent_info: Dict, 
                                     state: AgentState) -> Dict[str, Any]:
        """运行单个分析师并处理通知逻辑"""
        agent_name = agent_info['name']
        agent_func = agent_info['agent_func']
        
        print(f"\n🔄 开始执行 {agent_name} 分析...")
        
        try:
            # 获取agent的通知记忆
            agent_memory = notification_system.get_agent_memory(agent_id)
            
            # 将之前收到的通知添加到状态中，作为上下文
            notifications_context = format_notifications_for_context(agent_memory)
            
            # 可以将通知上下文添加到消息中
            context_message = HumanMessage(
                content=f"上下文信息：{notifications_context}\n\n请基于这些信息和最新数据进行分析。"
            )
            state["messages"].append(context_message)
            
            # 执行分析师函数
            result = agent_func(state, agent_id=agent_id)
            
            # 获取分析结果
            analysis_result = state['data']['analyst_signals'].get(agent_id, {})
            
            if analysis_result:
                print(f"✅ {agent_name} 分析完成")
                print(f"📊 分析结果: {json.dumps(analysis_result, ensure_ascii=False, indent=2)}")
                
                # 判断是否需要发送通知
                notification_decision = should_send_notification(
                    agent_id=agent_id,
                    analysis_result=analysis_result,
                    agent_memory=agent_memory,
                    state=state
                )
                
                # 处理通知决策（使用线程锁保护）
                if notification_decision.get("should_notify", False):
                    print(f"📢 {agent_name} 决定发送通知...")
                    
                    # 使用线程锁保护通知系统的全局状态
                    with self._notification_lock:
                        notification_id = notification_system.broadcast_notification(
                            sender_agent=agent_id,
                            content=notification_decision["content"],
                            urgency=notification_decision.get("urgency", "medium"),
                            category=notification_decision.get("category", "general")
                        )
                    
                    print(f"✅ 通知已发送 (ID: {notification_id})")
                    print(f"📝 通知内容: {notification_decision['content']}")
                else:
                    print(f"ℹ️ {agent_name} 决定不发送通知")
                    if "reason" in notification_decision:
                        print(f"📝 原因: {notification_decision['reason']}")
                
                return {
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "analysis_result": analysis_result,
                    "notification_sent": notification_decision.get("should_notify", False),
                    "notification_decision": notification_decision,
                    "status": "success"
                }
            else:
                print(f"⚠️ {agent_name} 未返回分析结果")
                return {
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "status": "no_result"
                }
                
        except Exception as e:
            print(f"❌ {agent_name} 执行失败: {str(e)}")
            print("完整错误信息:")
            traceback.print_exc()
            return {
                "agent_id": agent_id,
                "agent_name": agent_name,
                "error": str(e),
                "status": "error"
            }
    
    def run_full_analysis(self, tickers: List[str], start_date: str, end_date: str, 
                         parallel: bool = True) -> Dict[str, Any]:
        """运行完整的分析流程"""
        print("🚀 开始投资分析会话")
        print("=" * 60)
        print(f"📈 分析股票: {', '.join(tickers)}")
        print(f"📅 时间范围: {start_date} 至 {end_date}")
        print(f"🔄 执行模式: {'并行' if parallel else '串行'}")
        print("=" * 60)
        
        # 创建基础状态
        state = self.create_base_state(tickers, start_date, end_date)
        
        if parallel:
            # 并行执行所有分析师
            analyst_results = self.run_analysts_parallel(state)
        else:
            # 串行执行所有分析师（原有逻辑）
            analyst_results = self.run_analysts_sequential(state)
        
        # 生成最终报告
        final_report = self.generate_final_report(analyst_results, state)
        
        return {
            "analyst_results": analyst_results,
            "final_report": final_report,
            "analysis_timestamp": datetime.now().isoformat(),
            "tickers": tickers,
            "date_range": {"start": start_date, "end": end_date}
        }
    
    def run_analysts_sequential(self, state: AgentState) -> Dict[str, Any]:
        """串行执行所有分析师（原有逻辑）"""
        analyst_results = {}
        
        # 按顺序执行所有分析师
        for agent_id, agent_info in self.core_analysts.items():
            result = self.run_analyst_with_notifications(agent_id, agent_info, state)
            analyst_results[agent_id] = result
            
            # 在分析师之间添加短暂延迟，让通知传播
            print("\n" + "-" * 40)
        
        return analyst_results
    
    def run_analysts_parallel(self, state: AgentState) -> Dict[str, Any]:
        """并行执行所有分析师"""
        print("🚀 启动并行分析...")
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
                    
                    print(f"✅ {agent_name} 完成 ({completed_count}/4)")
                    
                    # 合并分析结果到主状态
                    if result.get("status") == "success" and "analysis_result" in result:
                        state["data"]["analyst_signals"][agent_id] = result["analysis_result"]
                    
                except Exception as e:
                    print(f"❌ {agent_name} 执行出错: {str(e)}")
                    analyst_results[agent_id] = {
                        "agent_id": agent_id,
                        "agent_name": agent_name,
                        "error": str(e),
                        "status": "error"
                    }
        
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()
        print(f"\n⏱️ 并行执行完成，总耗时: {execution_time:.2f} 秒")
        print("=" * 40)
        
        return analyst_results
    
    def run_analyst_with_notifications_safe(self, agent_id: str, agent_info: Dict, 
                                          state: AgentState) -> Dict[str, Any]:
        """线程安全的分析师执行函数"""
        try:
            return self.run_analyst_with_notifications(agent_id, agent_info, state)
        except Exception as e:
            # 确保异常不会导致整个并行执行失败
            logging.error(f"Error in {agent_id}: {str(e)}")
            return {
                "agent_id": agent_id,
                "agent_name": agent_info['name'],
                "error": str(e),
                "status": "error"
            }
    
    def generate_final_report(self, analyst_results: Dict[str, Any], 
                            state: AgentState) -> Dict[str, Any]:
        """生成最终分析报告"""
        print("\n📋 生成最终分析报告...")
        
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
        notification_summary = self.generate_notification_summary()
        
        report = {
            "summary": {
                "total_analysts": len(analyst_results),
                "successful_analyses": len(successful_analyses),
                "failed_analyses": len(failed_analyses),
                "notifications_sent": total_notifications_sent
            },
            "analyst_signals": all_signals,
            "notification_activity": notification_summary,
            "errors": [{"agent": r["agent_id"], "error": r["error"]} 
                      for r in failed_analyses]
        }
        
        print("✅ 最终报告生成完成")
        return report
    
    def generate_notification_summary(self) -> Dict[str, Any]:
        """生成通知活动摘要"""
        summary = {
            "total_notifications": len(notification_system.global_notifications),
            "notifications_by_agent": {},
            "recent_notifications": []
        }
        
        # 按发送者统计通知
        for notification in notification_system.global_notifications:
            sender = notification.sender_agent
            if sender not in summary["notifications_by_agent"]:
                summary["notifications_by_agent"][sender] = 0
            summary["notifications_by_agent"][sender] += 1
        
        # 获取最近的通知
        recent_cutoff = datetime.now() - timedelta(hours=1)
        recent_notifications = [
            {
                "sender": n.sender_agent,
                "content": n.content,
                "urgency": n.urgency,
                "category": n.category,
                "timestamp": n.timestamp.strftime("%H:%M:%S")
            }
            for n in notification_system.global_notifications
            if n.timestamp >= recent_cutoff
        ]
        summary["recent_notifications"] = recent_notifications
        
        return summary
    
    def print_session_summary(self, results: Dict[str, Any]):
        """打印会话摘要"""
        print("\n" + "=" * 60)
        print("📊 投资分析会话摘要")
        print("=" * 60)
        
        report = results["final_report"]
        summary = report["summary"]
        
        print(f"📈 分析股票: {', '.join(results['tickers'])}")
        print(f"⏰ 分析时间: {results['analysis_timestamp']}")
        print(f"✅ 成功分析: {summary['successful_analyses']}/{summary['total_analysts']}")
        print(f"📢 发送通知: {summary['notifications_sent']} 条")
        
        if summary["failed_analyses"] > 0:
            print(f"❌ 失败分析: {summary['failed_analyses']}")
        
        # 打印通知活动
        notification_activity = report["notification_activity"]
        if notification_activity["total_notifications"] > 0:
            print(f"\n📬 通知活动:")
            for agent, count in notification_activity["notifications_by_agent"].items():
                agent_name = self.core_analysts.get(agent, {}).get('name', agent)
                print(f"  - {agent_name}: {count} 条通知")
        
        print("=" * 60)


def main():
    """主函数"""
    # 创建分析引擎
    engine = InvestmentAnalysisEngine()
    
    # 配置分析参数
    tickers = ["AAPL", "MSFT"]  # 可以修改要分析的股票
    start_date = "2024-01-01"
    end_date = "2024-03-01"
    parallel = True  # 默认使用并行模式
    
    # 检查命令行参数
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            if arg == "--sequential":
                parallel = False
                print("📝 使用串行模式")
            elif arg == "--parallel":
                parallel = True
                print("📝 使用并行模式")
    
    try:
        # 运行完整分析
        results = engine.run_full_analysis(tickers, start_date, end_date, parallel=parallel)
        
        # 打印摘要
        engine.print_session_summary(results)
        
        # 保存结果到文件
        output_file = f"analysis_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"\n💾 详细结果已保存到: {output_file}")
        
    except Exception as e:
        print(f"❌ 主程序执行失败: {str(e)}")
        traceback.print_exc()


def interactive_mode():
    """交互式模式"""
    print("\n🎮 投资分析系统 - 交互式模式")
    print("=" * 50)
    
    engine = InvestmentAnalysisEngine()
    
    while True:
        try:
            print("\n请选择操作:")
            print("  1 - 运行完整分析")
            print("  2 - 查看通知历史")
            print("  3 - 查看agent记忆") 
            print("  q - 退出")
            print("-" * 30)
            
            choice = input("请输入选择: ").strip().lower()
            
            if choice == 'q':
                print("👋 退出系统")
                break
            elif choice == '1':
                # 获取用户输入
                tickers_input = input("请输入股票代码(用逗号分隔，如AAPL,MSFT): ").strip()
                tickers = [t.strip().upper() for t in tickers_input.split(',') if t.strip()]
                
                if not tickers:
                    print("❌ 请输入有效的股票代码")
                    continue
                
                start_date = input("请输入开始日期(YYYY-MM-DD): ").strip()
                end_date = input("请输入结束日期(YYYY-MM-DD): ").strip()
                
                # 选择执行模式
                mode_input = input("选择执行模式 (p-并行/s-串行，默认并行): ").strip().lower()
                parallel = mode_input != 's'
                
                # 运行分析
                results = engine.run_full_analysis(tickers, start_date, end_date, parallel=parallel)
                engine.print_session_summary(results)
                
            elif choice == '2':
                # 查看通知历史
                print("\n📬 全局通知历史:")
                for notification in notification_system.global_notifications[-10:]:  # 最近10条
                    print(f"  {notification.timestamp.strftime('%H:%M:%S')} - "
                          f"{notification.sender_agent}: {notification.content}")
                
            elif choice == '3':
                # 查看agent记忆
                agent_id = input("请输入agent ID (fundamentals_analyst/sentiment_analyst/technical_analyst/valuation_analyst): ").strip()
                memory = notification_system.get_agent_memory(agent_id)
                if memory:
                    print(f"\n🧠 {agent_id} 的通知记忆:")
                    for notification in memory.notifications[-5:]:  # 最近5条
                        print(f"  收到: {notification.timestamp.strftime('%H:%M:%S')} - "
                              f"{notification.sender_agent}: {notification.content}")
                else:
                    print(f"❌ 未找到agent: {agent_id}")
            else:
                print("无效选择，请重试")
                
        except KeyboardInterrupt:
            print("\n👋 退出系统")
            break
        except Exception as e:
            print(f"执行错误: {str(e)}")


if __name__ == "__main__":
    # 检查命令行参数
    if len(sys.argv) > 1 and "--interactive" in sys.argv:
        interactive_mode()
    else:
        main()
