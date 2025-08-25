#!/usr/bin/env python3
"""
演示新的分析师记忆系统
"""

import sys
sys.path.append('/root/wuyue.wy/Project/IA')

from src.communication.analyst_memory import AnalystMemory

def demo_analyst_memory():
    """演示分析师记忆系统的核心功能"""
    print("🧠 演示分析师记忆系统")
    print("=" * 40)
    
    # 创建一个基本面分析师的记忆
    analyst = AnalystMemory("fundamentals_analyst", "基本面分析师")
    
    print("1️⃣ 记录第一轮分析过程...")
    # 模拟第一轮分析
    session1 = analyst.start_analysis_session(
        session_type="first_round",
        tickers=["AAPL", "MSFT"],
        context={"market": "bull_market"}
    )
    
    analyst.add_analysis_message(
        session1, "human", 
        "请分析AAPL和MSFT的基本面情况"
    )
    
    analyst.add_analysis_message(
        session1, "assistant",
        "基于财务数据分析，AAPL P/E=25，MSFT P/E=30，两者都处于合理估值区间..."
    )
    
    # 完成第一轮分析
    first_result = {
        "ticker_signals": [
            {
                "ticker": "AAPL",
                "signal": "bullish", 
                "confidence": 75,
                "reasoning": "强劲的现金流和合理估值"
            },
            {
                "ticker": "MSFT",
                "signal": "neutral",
                "confidence": 65, 
                "reasoning": "估值偏高但增长稳定"
            }
        ]
    }
    
    analyst.complete_analysis_session(session1, first_result)
    print("✅ 第一轮分析记录完成")
    
    print("\n2️⃣ 记录私聊通信...")
    # 模拟私聊
    chat_id = analyst.start_communication(
        communication_type="private_chat",
        participants=["portfolio_manager", "fundamentals_analyst"],
        topic="AAPL估值深度讨论"
    )
    
    analyst.add_communication_message(
        chat_id, "portfolio_manager",
        "你对AAPL的75%信心度是否考虑了当前的宏观环境？"
    )
    
    analyst.add_communication_message(
        chat_id, "fundamentals_analyst", 
        "是的，我已经考虑了利率环境和行业竞争，仍然认为基本面支撑当前价格"
    )
    
    # 记录信号调整
    original = first_result["ticker_signals"][0]  # AAPL信号
    adjusted = {
        "ticker": "AAPL",
        "signal": "bullish",
        "confidence": 80,  # 提高信心度
        "reasoning": "经过深度讨论，更加确信基本面支撑"
    }
    
    analyst.record_signal_adjustment(
        chat_id, original, adjusted, 
        "私聊讨论后提高对AAPL的信心度"
    )
    
    analyst.complete_communication(chat_id)
    print("✅ 私聊通信记录完成")
    
    print("\n3️⃣ 记录会议讨论...")
    # 模拟会议
    meeting_id = analyst.start_communication(
        communication_type="meeting",
        participants=["portfolio_manager", "fundamentals_analyst", "technical_analyst", "sentiment_analyst"],
        topic="科技股投资策略集体讨论"
    )
    
    analyst.add_communication_message(
        meeting_id, "portfolio_manager",
        "我们来讨论科技股的投资策略，特别是AAPL和MSFT"
    )
    
    analyst.add_communication_message(
        meeting_id, "fundamentals_analyst",
        "从基本面角度，AAPL的财务指标依然强劲，MSFT的云业务增长稳定"
    )
    
    analyst.add_communication_message(
        meeting_id, "technical_analyst", 
        "技术面显示AAPL处于上升通道，MSFT在阻力位附近"
    )
    
    analyst.complete_communication(meeting_id)
    print("✅ 会议讨论记录完成")
    
    print("\n4️⃣ 记录第二轮分析...")
    # 模拟第二轮分析
    session2 = analyst.start_analysis_session(
        session_type="second_round",
        tickers=["AAPL", "MSFT"],
        context={"based_on": "first_round + communications"}
    )
    
    analyst.add_analysis_message(
        session2, "human",
        "基于第一轮分析和团队讨论，请更新你的投资建议"
    )
    
    analyst.add_analysis_message(
        session2, "assistant",
        "综合考虑团队讨论的观点，我调整了对MSFT的看法，技术面的确认让我更加谨慎"
    )
    
    # 第二轮结果
    second_result = {
        "ticker_signals": [
            {
                "ticker": "AAPL",
                "signal": "bullish",
                "confidence": 80,  # 从私聊调整后保持
                "reasoning": "基本面强劲且得到团队认同"
            },
            {
                "ticker": "MSFT", 
                "signal": "bearish",  # 从neutral调整为bearish
                "confidence": 70,
                "reasoning": "技术面阻力让我对高估值更加担忧"
            }
        ]
    }
    
    analyst.complete_analysis_session(session2, second_result)
    print("✅ 第二轮分析记录完成")
    
    print("\n5️⃣ 生成完整记忆上下文...")
    # 展示完整的记忆上下文
    full_context = analyst.get_full_context_for_communication(["AAPL", "MSFT"])
    
    print("🧠 分析师的完整记忆:")
    print("-" * 40)
    print(full_context)
    print("-" * 40)
    
    print("\n6️⃣ 分析总结...")
    summary = analyst.get_analysis_summary()
    print(f"📊 {summary['analyst_name']} 总结:")
    print(f"  • 总分析次数: {summary['total_analyses']}")
    print(f"  • 总通信次数: {summary['total_communications']}")
    print(f"  • 信号调整次数: {summary['signal_adjustments']}")
    print(f"  • 当前持有信号: {len(summary['current_signals'])} 个")
    
    for ticker, signal in summary['current_signals'].items():
        print(f"    - {ticker}: {signal['signal']} ({signal['confidence']}%)")
    
    print(f"\n🎯 核心优势:")
    print(f"  ✅ 完整的分析历史记录")
    print(f"  ✅ 所有通信对话保存")  
    print(f"  ✅ 信号调整轨迹追踪")
    print(f"  ✅ 上下文智能生成")
    print(f"  ✅ 真实的分析师记忆")
    
    return True

if __name__ == "__main__":
    try:
        demo_analyst_memory()
        print("\n🎉 演示完成!")
    except Exception as e:
        print(f"\n❌ 演示失败: {e}")
        import traceback
        traceback.print_exc()
