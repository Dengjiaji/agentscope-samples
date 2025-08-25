#!/usr/bin/env python3
"""
独立测试通信机制 - 不依赖完整的分析系统
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
from src.communication.chat_tools import communication_manager, CommunicationDecision


def create_mock_state():
    """创建模拟的状态对象"""
    api_key = os.getenv('OPENAI_API_KEY')
    
    state = AgentState(
        messages=[HumanMessage(content="Test communication session")],
        data={
            "tickers": ["AAPL", "MSFT"],
            "analyst_signals": {},
            "api_keys": {
                'OPENAI_API_KEY': api_key,
            }
        },
        metadata={
            "model_name": "gpt-3.5-turbo",
            "model_provider": "OpenAI"
        }
    )
    
    return state


def create_mock_analyst_signals():
    """创建模拟的分析师信号"""
    return {
        "fundamentals_analyst": {
            "ticker_signals": [
                {
                    "ticker": "AAPL",
                    "signal": "bearish",
                    "confidence": 75,
                    "reasoning": "基本面数据显示增长放缓，营收预期下调"
                },
                {
                    "ticker": "MSFT",
                    "signal": "bearish", 
                    "confidence": 80,
                    "reasoning": "云服务增长不及预期，竞争加剧"
                }
            ]
        },
        "sentiment_analyst": {
            "ticker_signals": [
                {
                    "ticker": "AAPL",
                    "signal": "neutral",
                    "confidence": 60,
                    "reasoning": "市场情绪混合，缺乏明确方向"
                },
                {
                    "ticker": "MSFT",
                    "signal": "neutral",
                    "confidence": 55,
                    "reasoning": "情绪数据样本不足，难以确定趋势"
                }
            ]
        },
        "technical_analyst": {
            "ticker_signals": [
                {
                    "ticker": "AAPL",
                    "signal": "bearish",
                    "confidence": 70,
                    "reasoning": "技术指标显示超卖，但趋势依然向下"
                },
                {
                    "ticker": "MSFT",
                    "signal": "neutral",
                    "confidence": 65,
                    "reasoning": "技术面处于关键阻力位，方向不明"
                }
            ]
        },
        "valuation_analyst": {
            "ticker_signals": [
                {
                    "ticker": "AAPL",
                    "signal": "bearish",
                    "confidence": 85,
                    "reasoning": "估值过高，P/E比超出合理范围"
                },
                {
                    "ticker": "MSFT",
                    "signal": "bearish",
                    "confidence": 78,
                    "reasoning": "估值拉伸，风险回报比不佳"
                }
            ]
        }
    }


def test_communication_decision():
    """测试通信决策功能"""
    print("🧪 测试通信决策功能...")
    
    state = create_mock_state()
    analyst_signals = create_mock_analyst_signals()
    manager_signals = {"portfolio_decision": "需要进一步讨论"}
    
    try:
        decision = communication_manager.decide_communication_strategy(
            manager_signals=manager_signals,
            analyst_signals=analyst_signals,
            state=state
        )
        
        print(f"✅ 通信决策成功!")
        print(f"📞 是否需要通信: {decision.should_communicate}")
        print(f"📋 通信类型: {decision.communication_type}")
        print(f"🎯 目标分析师: {decision.target_analysts}")
        print(f"💭 原因: {decision.reasoning}")
        print(f"📝 讨论话题: {decision.discussion_topic[:100]}...")
        
        return decision
        
    except Exception as e:
        print(f"❌ 通信决策测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def test_private_chat():
    """测试私聊功能"""
    print("\n🧪 测试私聊功能...")
    
    state = create_mock_state()
    analyst_signals = create_mock_analyst_signals()
    
    # 选择一个分析师进行私聊
    analyst_id = "fundamentals_analyst"
    analyst_signal = analyst_signals[analyst_id]
    
    try:
        chat_result = communication_manager.conduct_private_chat(
            manager_id="portfolio_manager",
            analyst_id=analyst_id,
            topic="AAPL投资策略讨论",
            analyst_signal=analyst_signal,
            state=state,
            max_rounds=2  # 减少轮次以便测试
        )
        
        print(f"✅ 私聊测试成功!")
        print(f"💬 对话轮数: {len(chat_result['chat_history'])}")
        print(f"🔄 信号调整次数: {chat_result['adjustments_made']}")
        
        # 显示对话历史
        print("\n📝 对话记录:")
        for i, msg in enumerate(chat_result['chat_history'][:4]):  # 只显示前4条
            print(f"  {i+1}. {msg['speaker']}: {msg['content'][:80]}...")
        
        return chat_result
        
    except Exception as e:
        print(f"❌ 私聊测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def test_meeting():
    """测试会议功能"""
    print("\n🧪 测试会议功能...")
    
    state = create_mock_state()
    analyst_signals = create_mock_analyst_signals()
    
    # 选择部分分析师参加会议
    analyst_ids = ["fundamentals_analyst", "valuation_analyst"]
    meeting_signals = {aid: analyst_signals[aid] for aid in analyst_ids}
    
    try:
        meeting_result = communication_manager.conduct_meeting(
            manager_id="portfolio_manager",
            analyst_ids=analyst_ids,
            topic="AAPL和MSFT投资策略集体讨论",
            analyst_signals=meeting_signals,
            state=state,
            max_rounds=1  # 减少轮次以便测试
        )
        
        print(f"✅ 会议测试成功!")
        print(f"🏢 会议ID: {meeting_result['meeting_id']}")
        print(f"📝 发言数量: {len(meeting_result['transcript'])}")
        print(f"🔄 信号调整次数: {meeting_result['adjustments_made']}")
        
        # 显示会议记录
        print("\n📋 会议记录:")
        for i, msg in enumerate(meeting_result['transcript'][:5]):  # 只显示前5条
            round_info = f"第{msg['round']}轮" if isinstance(msg['round'], int) else msg['round']
            print(f"  {i+1}. [{round_info}] {msg['speaker']}: {msg['content'][:80]}...")
        
        return meeting_result
        
    except Exception as e:
        print(f"❌ 会议测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def test_json_parsing():
    """测试JSON解析功能"""
    print("\n🧪 测试JSON解析功能...")
    
    # 测试有效的JSON
    valid_json = '{"response": "我同意这个观点", "signal_adjustment": false}'
    try:
        result = json.loads(valid_json)
        print(f"✅ 有效JSON解析成功: {result}")
    except Exception as e:
        print(f"❌ 有效JSON解析失败: {e}")
    
    # 测试无效的JSON
    invalid_json = '{"response": "我同意这个观点", "signal_adjustment": false'  # 缺少闭合括号
    try:
        result = json.loads(invalid_json)
        print(f"✅ 无效JSON意外解析成功: {result}")
    except json.JSONDecodeError as e:
        print(f"✅ 无效JSON正确报错: {e}")
    except Exception as e:
        print(f"❌ 无效JSON解析异常: {e}")


def main():
    """主测试函数"""
    print("🚀 开始独立通信机制测试")
    print("=" * 50)
    
    # 检查API密钥
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ 缺少 OPENAI_API_KEY 环境变量")
        return False
    
    print(f"✅ API密钥已配置: {api_key[:10]}...")
    
    # 测试基础JSON解析
    test_json_parsing()
    
    # 测试通信决策
    decision = test_communication_decision()
    if not decision:
        print("❌ 通信决策测试失败，停止后续测试")
        return False
    
    # 根据决策结果选择测试
    if decision.should_communicate:
        if decision.communication_type == "private_chat":
            test_private_chat()
        elif decision.communication_type == "meeting":
            test_meeting()
        else:
            print("⚠️ 未知的通信类型，测试私聊和会议功能")
            test_private_chat()
            test_meeting()
    else:
        print("📝 决策建议不进行通信，但我们仍测试通信功能")
        test_private_chat()
        test_meeting()
    
    print("\n" + "=" * 50)
    print("🎉 通信机制测试完成!")
    return True


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n❌ 测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试过程中发生未预期错误: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
