#!/usr/bin/env python3
"""
通知系统测试脚本
用于快速验证通知机制是否正常工作
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

from src.communication.notification_system import (
    notification_system,
    should_send_notification,
    format_notifications_for_context
)
from src.graph.state import AgentState
from langchain_core.messages import HumanMessage


def test_notification_system():
    """测试通知系统基本功能"""
    print("🧪 测试通知系统")
    print("=" * 50)
    
    # 注册测试agents
    test_agents = ['fundamentals_analyst', 'sentiment_analyst', 'technical_analyst', 'valuation_analyst']
    
    for agent_id in test_agents:
        notification_system.register_agent(agent_id)
        print(f"✅ 已注册 {agent_id}")
    
    print(f"\n📊 当前注册的agents: {len(notification_system.agent_memories)}")
    
    # 测试发送通知
    print("\n📢 测试发送通知...")
    
    notification_id = notification_system.broadcast_notification(
        sender_agent="fundamentals_analyst",
        content="AAPL基本面分析显示强劲增长，建议关注",
        urgency="high",
        category="opportunity"
    )
    
    print(f"✅ 通知已发送，ID: {notification_id}")
    
    # 检查其他agents是否收到通知
    print("\n📬 检查通知接收情况:")
    for agent_id in test_agents:
        if agent_id != "fundamentals_analyst":
            memory = notification_system.get_agent_memory(agent_id)
            notifications = memory.get_recent_notifications(24)
            print(f"  {agent_id}: 收到 {len(notifications)} 条通知")
            
            if notifications:
                latest = notifications[-1]
                print(f"    最新: {latest.content[:50]}...")
    
    print("\n✅ 通知系统基本功能测试完成")


def test_notification_decision():
    """测试通知决策功能"""
    print("\n🤖 测试通知决策功能")
    print("=" * 50)
    
    # 模拟分析结果
    mock_analysis_result = {
        "signals": [
            {
                "signal": "BUY",
                "strength": 0.8,
                "reasoning": "强劲的财务指标和增长预期"
            }
        ],
        "risk_assessment": "medium",
        "confidence": 0.85
    }
    
    # 创建模拟状态
    state = AgentState(
        messages=[HumanMessage(content="Test")],
        data={
            "tickers": ["AAPL"],
            "api_keys": {
                'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY')
            }
        },
        metadata={
            "model_name": os.getenv('MODEL_NAME', 'gpt-3.5-turbo'),
            "model_provider": "OpenAI"
        }
    )
    
    agent_memory = notification_system.get_agent_memory("fundamentals_analyst")
    
    try:
        print("🔄 调用LLM进行通知决策...")
        
        decision = should_send_notification(
            agent_id="fundamentals_analyst",
            analysis_result=mock_analysis_result,
            agent_memory=agent_memory,
            state=state
        )
        
        print("✅ 决策完成:")
        print(json.dumps(decision, ensure_ascii=False, indent=2))
        
        if decision.get("should_notify", False):
            print("\n📢 模拟发送通知...")
            notification_id = notification_system.broadcast_notification(
                sender_agent="fundamentals_analyst",
                content=decision["content"],
                urgency=decision.get("urgency", "medium"),
                category=decision.get("category", "general")
            )
            print(f"✅ 通知已发送，ID: {notification_id}")
        
    except Exception as e:
        print(f"❌ 通知决策测试失败: {str(e)}")
        print("这可能是因为缺少API密钥或网络问题")


def test_memory_formatting():
    """测试记忆格式化功能"""
    print("\n🧠 测试记忆格式化功能")
    print("=" * 50)
    
    # 先发送几条测试通知
    notifications = [
        ("sentiment_analyst", "市场情绪转为乐观，投资者信心增强", "medium", "market_alert"),
        ("technical_analyst", "AAPL突破关键阻力位，技术面看涨", "high", "opportunity"),
        ("valuation_analyst", "当前估值略显偏高，建议谨慎", "medium", "risk_warning")
    ]
    
    for sender, content, urgency, category in notifications:
        notification_system.broadcast_notification(sender, content, urgency, category)
        print(f"📤 发送测试通知: {sender}")
    
    # 格式化fundamentals_analyst的通知记忆
    agent_memory = notification_system.get_agent_memory("fundamentals_analyst")
    formatted_context = format_notifications_for_context(agent_memory)
    
    print(f"\n📋 格式化的通知上下文:")
    print(formatted_context)
    
    print("✅ 记忆格式化测试完成")


def main():
    """主测试函数"""
    print("🚀 通知系统完整测试")
    print("=" * 60)
    
    # 检查环境变量
    api_key = os.getenv('OPENAI_API_KEY')
    print(f"OpenAI API Key: {'✅ 已设置' if api_key else '❌ 未设置'}")
    
    if not api_key:
        print("⚠️ 警告: 未设置OpenAI API密钥，某些测试可能失败")
    
    try:
        # 运行所有测试
        test_notification_system()
        test_memory_formatting()
        
        if api_key:
            test_notification_decision()
        else:
            print("\n⏭️ 跳过通知决策测试（需要API密钥）")
        
        print(f"\n📊 测试总结:")
        print(f"  - 全局通知数量: {len(notification_system.global_notifications)}")
        print(f"  - 注册的agents: {len(notification_system.agent_memories)}")
        
        print("\n🎉 所有测试完成!")
        
    except Exception as e:
        print(f"\n❌ 测试过程中出现错误: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
