#!/usr/bin/env python3
"""
Mem0集成测试脚本
测试IA项目中的Mem0记忆系统功能
"""

import os
import sys
from datetime import datetime
from typing import Dict, Any

# 添加项目路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from src.memory import unified_memory_manager
from src.communication.analyst_memory_mem0 import memory_manager_mem0_adapter


def test_basic_memory_operations():
    """测试基本记忆操作"""
    print("🧪 测试基本记忆操作...")
    
    analyst_id = "test_fundamentals_analyst"
    analyst_name = "测试基本面分析师"
    
    try:
        # 注册分析师
        unified_memory_manager.register_analyst(analyst_id, analyst_name)
        memory = unified_memory_manager.get_analyst_memory(analyst_id)
        
        if not memory:
            print("❌ 无法获取分析师记忆")
            return False
        
        # 测试分析会话
        session_id = memory.start_analysis_session("first_round", ["AAPL", "MSFT"])
        memory.add_analysis_message(session_id, "system", "开始分析AAPL和MSFT的基本面")
        memory.add_analysis_message(session_id, "assistant", "AAPL财务状况良好，营收增长稳定")
        memory.add_analysis_message(session_id, "assistant", "MSFT云业务表现强劲，未来前景看好")
        
        final_result = {
            "ticker_signals": [
                {"ticker": "AAPL", "signal": "bullish", "confidence": 85, "reasoning": "财务稳健"},
                {"ticker": "MSFT", "signal": "bullish", "confidence": 90, "reasoning": "云业务强劲"}
            ]
        }
        memory.complete_analysis_session(session_id, final_result)
        
        print("✅ 分析会话测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 基本记忆操作测试失败: {str(e)}")
        return False


def test_communication_memory():
    """测试通信记忆"""
    print("🧪 测试通信记忆...")
    
    try:
        analyst_id = "test_technical_analyst"
        analyst_name = "测试技术分析师"
        
        unified_memory_manager.register_analyst(analyst_id, analyst_name)
        memory = unified_memory_manager.get_analyst_memory(analyst_id)
        
        # 测试通信会话
        comm_id = memory.start_communication("private_chat", [analyst_id, "portfolio_manager"], "讨论AAPL技术指标")
        memory.add_communication_message(comm_id, "portfolio_manager", "你对AAPL的技术面有什么看法？")
        memory.add_communication_message(comm_id, analyst_id, "从技术指标看，AAPL正在突破重要阻力位")
        
        # 测试信号调整
        original_signal = {"ticker": "AAPL", "signal": "neutral", "confidence": 60}
        adjusted_signal = {"ticker": "AAPL", "signal": "bullish", "confidence": 75}
        memory.record_signal_adjustment(comm_id, original_signal, adjusted_signal, "基于技术突破调整")
        
        memory.complete_communication(comm_id)
        
        print("✅ 通信记忆测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 通信记忆测试失败: {str(e)}")
        return False


def test_memory_search():
    """测试记忆搜索"""
    print("🧪 测试记忆搜索...")
    
    try:
        analyst_id = "test_fundamentals_analyst"
        memory = unified_memory_manager.get_analyst_memory(analyst_id)
        
        if not memory:
            print("❌ 无法获取分析师记忆")
            return False
        
        # 搜索相关记忆
        memories = memory.get_relevant_memories("AAPL分析", limit=5)
        print(f"🔍 找到 {len(memories)} 条相关记忆")
        
        for i, mem in enumerate(memories[:3], 1):
            memory_text = mem.get('memory', '')[:100]
            print(f"   {i}. {memory_text}...")
        
        # 测试上下文获取
        context = memory.get_full_context_for_communication(["AAPL"])
        print(f"📋 上下文长度: {len(context)} 字符")
        
        print("✅ 记忆搜索测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 记忆搜索测试失败: {str(e)}")
        return False


def test_notification_system():
    """测试通知系统"""
    print("🧪 测试通知系统...")
    
    try:
        # 发送通知
        notification_id = unified_memory_manager.broadcast_notification(
            sender_agent="test_fundamentals_analyst",
            content="发现AAPL重要财务指标异常，建议关注",
            urgency="high",
            category="risk_warning"
        )
        
        print(f"📢 发送通知: {notification_id}")
        
        # 检查通知记忆
        notification_memory = unified_memory_manager.notification_system.get_agent_memory("test_technical_analyst")
        if notification_memory:
            recent_notifications = notification_memory.get_recent_notifications(1)
            print(f"📨 收到 {len(recent_notifications)} 条最近通知")
        
        print("✅ 通知系统测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 通知系统测试失败: {str(e)}")
        return False


def test_compatibility_adapter():
    """测试兼容性适配器"""
    print("🧪 测试兼容性适配器...")
    
    try:
        # 使用适配器接口
        memory_manager_mem0_adapter.register_analyst("test_adapter_analyst", "测试适配器分析师")
        memory = memory_manager_mem0_adapter.get_analyst_memory("test_adapter_analyst")
        
        if not memory:
            print("❌ 无法通过适配器获取记忆")
            return False
        
        # 测试原有接口
        session_id = memory.start_analysis_session("compatibility_test", ["GOOGL"])
        memory.add_analysis_message(session_id, "system", "测试兼容性适配器")
        memory.complete_analysis_session(session_id, {"test": "compatibility"})
        
        # 获取分析总结
        summary = memory.get_analysis_summary()
        print(f"📊 分析总结: {summary.get('memory_system', 'unknown')}")
        
        print("✅ 兼容性适配器测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 兼容性适配器测试失败: {str(e)}")
        return False


def test_system_status():
    """测试系统状态"""
    print("🧪 测试系统状态...")
    
    try:
        status = unified_memory_manager.get_system_status()
        
        print("📊 系统状态:")
        print(f"   - 记忆系统: {status['memory_system']}")
        print(f"   - 注册分析师: {len(status['registered_analysts'])}")
        print(f"   - 通知代理: {len(status['registered_notification_agents'])}")
        print(f"   - Mem0实例: {len(status['mem0_instances'])}")
        
        # 导出测试
        export_data = unified_memory_manager.export_all_data()
        print(f"📤 导出数据大小: {len(str(export_data))} 字符")
        
        print("✅ 系统状态测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 系统状态测试失败: {str(e)}")
        return False


def cleanup_test_data():
    """清理测试数据"""
    print("🧹 清理测试数据...")
    
    try:
        # 重置测试分析师
        test_analysts = [
            "test_fundamentals_analyst",
            "test_technical_analyst", 
            "test_adapter_analyst"
        ]
        
        for analyst_id in test_analysts:
            try:
                unified_memory_manager.reset_analyst(analyst_id)
            except Exception:
                pass  # 忽略清理错误
        
        print("✅ 测试数据清理完成")
        
    except Exception as e:
        print(f"⚠️ 清理测试数据时出错: {str(e)}")


def main():
    """主测试流程"""
    print("🚀 IA项目Mem0集成测试开始")
    print("=" * 60)
    
    test_results = []
    
    # 执行各项测试
    tests = [
        ("基本记忆操作", test_basic_memory_operations),
        ("通信记忆", test_communication_memory),
        ("记忆搜索", test_memory_search),
        ("通知系统", test_notification_system),
        ("兼容性适配器", test_compatibility_adapter),
        ("系统状态", test_system_status)
    ]
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            result = test_func()
            test_results.append((test_name, result))
        except Exception as e:
            print(f"❌ 测试 {test_name} 出现异常: {str(e)}")
            test_results.append((test_name, False))
    
    # 清理测试数据
    print(f"\n{'='*20} 清理 {'='*20}")
    cleanup_test_data()
    
    # 显示测试结果
    print(f"\n{'='*20} 测试结果 {'='*20}")
    passed = 0
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n📊 总结: {passed}/{total} 项测试通过")
    
    if passed == total:
        print("🎉 所有测试通过！Mem0集成工作正常")
        return True
    else:
        print("⚠️ 部分测试失败，请检查错误信息")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
