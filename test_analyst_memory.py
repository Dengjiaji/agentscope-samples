#!/usr/bin/env python3
"""
测试分析师记忆系统
"""

import sys
import os
import json
from datetime import datetime
from dotenv import load_dotenv

# 添加项目路径
sys.path.append('/root/wuyue.wy/Project/IA')

# 加载环境变量
load_dotenv('/root/wuyue.wy/Project/IA/.env')

from src.graph.state import AgentState
from langchain_core.messages import HumanMessage
from src.communication.analyst_memory import memory_manager


def test_analyst_memory_system():
    """测试分析师记忆系统"""
    print("🧠 测试分析师记忆系统")
    print("=" * 50)
    
    # 注册几个分析师
    analysts = {
        "fundamentals_analyst": "基本面分析师",
        "technical_analyst": "技术分析师", 
        "sentiment_analyst": "情绪分析师"
    }
    
    for analyst_id, analyst_name in analysts.items():
        memory_manager.register_analyst(analyst_id, analyst_name)
    
    print(f"✅ 注册了 {len(analysts)} 个分析师")
    
    # 模拟第一轮分析
    print("\n📊 模拟第一轮分析...")
    for analyst_id in analysts.keys():
        memory = memory_manager.get_analyst_memory(analyst_id)
        if memory:
            # 开始分析会话
            session_id = memory.start_analysis_session(
                session_type="first_round",
                tickers=["AAPL", "MSFT"],
                context={"market_condition": "volatile"}
            )
            
            # 添加分析消息
            memory.add_analysis_message(
                session_id, "human", 
                "请分析AAPL和MSFT的投资机会",
                {"data_sources": ["financial_datasets", "news_api"]}
            )
            
            memory.add_analysis_message(
                session_id, "assistant",
                f"作为{analysts[analyst_id]}，我的分析结果是...",
                {"analysis_duration": "5分钟"}
            )
            
            # 完成分析并设置结果
            final_result = {
                "ticker_signals": [
                    {
                        "ticker": "AAPL",
                        "signal": "bullish",
                        "confidence": 75,
                        "reasoning": f"{analysts[analyst_id]}的专业判断"
                    },
                    {
                        "ticker": "MSFT", 
                        "signal": "neutral",
                        "confidence": 60,
                        "reasoning": "需要更多数据确认"
                    }
                ]
            }
            
            memory.complete_analysis_session(session_id, final_result)
    
    # 模拟通信过程
    print("\n💬 模拟分析师之间的通信...")
    
    # 模拟私聊
    fundamentals_memory = memory_manager.get_analyst_memory("fundamentals_analyst")
    if fundamentals_memory:
        comm_id = fundamentals_memory.start_communication(
            communication_type="private_chat",
            participants=["portfolio_manager", "fundamentals_analyst"],
            topic="AAPL估值讨论"
        )
        
        fundamentals_memory.add_communication_message(
            comm_id, "portfolio_manager", 
            "你对AAPL的75%信心度是基于什么？"
        )
        
        fundamentals_memory.add_communication_message(
            comm_id, "fundamentals_analyst",
            "基于P/E比率和现金流分析，我认为当前价格有上涨空间"
        )
        
        # 模拟信号调整
        original_signal = {
            "ticker": "AAPL",
            "signal": "bullish", 
            "confidence": 75,
            "reasoning": "基本面分析师的专业判断"
        }
        
        adjusted_signal = {
            "ticker": "AAPL",
            "signal": "bullish",
            "confidence": 85,
            "reasoning": "经过与管理者讨论，增强了信心"
        }
        
        fundamentals_memory.record_signal_adjustment(
            comm_id, original_signal, adjusted_signal,
            "私聊讨论后提高信心度"
        )
        
        fundamentals_memory.complete_communication(comm_id)
    
    # 模拟会议
    print("\n🏢 模拟分析师会议...")
    for analyst_id in ["fundamentals_analyst", "technical_analyst"]:
        memory = memory_manager.get_analyst_memory(analyst_id)
        if memory:
            meeting_id = memory.start_communication(
                communication_type="meeting",
                participants=["portfolio_manager", "fundamentals_analyst", "technical_analyst"],
                topic="AAPL和MSFT投资策略讨论"
            )
            
            memory.add_communication_message(
                meeting_id, "portfolio_manager",
                "我们来讨论AAPL和MSFT的投资策略"
            )
            
            memory.add_communication_message(
                meeting_id, analyst_id,
                f"作为{analysts[analyst_id]}，我的观点是..."
            )
            
            memory.complete_communication(meeting_id)
    
    # 模拟第二轮分析
    print("\n🔄 模拟第二轮分析...")
    for analyst_id in analysts.keys():
        memory = memory_manager.get_analyst_memory(analyst_id)
        if memory:
            session_id = memory.start_analysis_session(
                session_type="second_round",
                tickers=["AAPL", "MSFT"],
                context={"based_on": "first_round + communications"}
            )
            
            memory.add_analysis_message(
                session_id, "human",
                "基于第一轮结果和通信讨论，请更新你的分析",
                {"communication_summary": "参与了私聊和会议"}
            )
            
            memory.add_analysis_message(
                session_id, "assistant", 
                "经过讨论和反思，我更新了我的分析结果",
                {"adjustments_made": True}
            )
            
            # 第二轮结果
            second_round_result = {
                "ticker_signals": [
                    {
                        "ticker": "AAPL",
                        "signal": "bullish",
                        "confidence": 80,  # 调整后的信心度
                        "reasoning": "结合通信讨论后的最终判断"
                    }
                ]
            }
            
            memory.complete_analysis_session(session_id, second_round_result)
    
    # 展示完整的记忆上下文
    print("\n🧠 展示分析师的完整记忆...")
    print("=" * 50)
    
    for analyst_id in analysts.keys():
        memory = memory_manager.get_analyst_memory(analyst_id)
        if memory:
            print(f"\n--- {analysts[analyst_id]} ({analyst_id}) ---")
            
            # 获取完整上下文
            context = memory.get_full_context_for_communication(["AAPL", "MSFT"])
            print(context)
            
            # 获取分析总结
            summary = memory.get_analysis_summary()
            print(f"\n📊 分析总结:")
            print(f"  - 总分析次数: {summary['total_analyses']}")
            print(f"  - 总通信次数: {summary['total_communications']}")
            print(f"  - 信号调整次数: {summary['signal_adjustments']}")
            print(f"  - 当前信号数量: {len(summary['current_signals'])}")
            print(f"  - 最后活跃时间: {summary['last_active']}")
    
    # 导出所有记忆
    print("\n💾 导出所有分析师记忆...")
    all_memories = memory_manager.export_all_memories()
    
    # 保存到文件
    output_file = f"/root/wuyue.wy/Project/IA/analyst_memories_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_memories, f, ensure_ascii=False, indent=2, default=str)
        print(f"✅ 记忆已保存到: {output_file}")
    except Exception as e:
        print(f"❌ 保存失败: {e}")
    
    print("\n🎉 分析师记忆系统测试完成!")
    return True


def test_communication_with_memory():
    """测试通信时使用记忆"""
    print("\n🧪 测试通信中的记忆使用...")
    
    # 获取基本面分析师的记忆
    memory = memory_manager.get_analyst_memory("fundamentals_analyst")
    if memory:
        # 获取用于通信的完整上下文
        context = memory.get_full_context_for_communication(["AAPL"])
        
        print("📋 用于通信的完整上下文:")
        print(context[:500] + "..." if len(context) > 500 else context)
        
        return True
    return False


if __name__ == "__main__":
    try:
        success1 = test_analyst_memory_system()
        success2 = test_communication_with_memory()
        
        if success1 and success2:
            print("\n✅ 所有测试通过!")
            sys.exit(0)
        else:
            print("\n❌ 部分测试失败!")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
