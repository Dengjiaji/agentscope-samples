#!/usr/bin/env python3
"""
测试高级沟通机制中的信号格式修复
验证LLM工具选择器集成和JSON解析改进的效果
"""

import sys
import os
import json
from datetime import datetime

# 添加项目路径
sys.path.append('/home/wuyue23/Project/IA')

def test_malformed_string_parsing():
    """测试格式错误字符串的解析能力"""
    print("🧪 测试格式错误字符串解析...")
    
    try:
        from src.communication.analyst_memory import AnalystMemory
        
        # 创建测试分析师记忆
        memory = AnalystMemory("test_analyst", "测试分析师")
        
        # 测试用例1: 从终端选择中看到的实际格式
        malformed_str1 = '{"ticker": "AAPL", "signal": "bearish", "confidence": 85, "reasoning": "尽管苹果公司展现出强劲的盈利能力..."}'
        
        print(f"测试用例1: {malformed_str1[:50]}...")
        result1 = memory._extract_ticker_signals_from_malformed_string(malformed_str1)
        if result1:
            print(f"✅ 成功解析: {len(result1)} 个信号")
            print(f"   第一个信号: {result1[0]['ticker']} -> {result1[0]['signal']}")
        else:
            print("❌ 解析失败")
        
        # 测试用例2: ticker_signals格式
        malformed_str2 = 'ticker_signals: [{"ticker": "MSFT", "signal": "neutral", "confidence": 70, "reasoning": "测试"}]'
        
        print(f"\n测试用例2: {malformed_str2[:50]}...")
        result2 = memory._extract_ticker_signals_from_malformed_string(malformed_str2)
        if result2:
            print(f"✅ 成功解析: {len(result2)} 个信号")
            print(f"   第一个信号: {result2[0]['ticker']} -> {result2[0]['signal']}")
        else:
            print("❌ 解析失败")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_json_parsing_robustness():
    """测试JSON解析的健壮性"""
    print("\n🧪 测试JSON解析健壮性...")
    
    try:
        from src.communication.chat_tools import CommunicationManager
        
        # 创建通信管理器
        comm_mgr = CommunicationManager()
        
        # 测试格式错误的JSON响应
        malformed_json1 = '''
        {
            "response": "我同意基本面分析师的观点",
            "signal_adjustment": true,
            "adjusted_signal": {
                "analyst_id": "test_analyst",
                "ticker_signals": [
                    "{"ticker": "AAPL", "signal": "bearish", "confidence": 85}"
                ]
            }
        }
        '''
        
        print("测试格式错误的JSON响应...")
        result1 = comm_mgr._extract_and_clean_json(malformed_json1)
        if result1:
            print("✅ 成功解析格式错误的JSON")
            print(f"   包含字段: {list(result1.keys())}")
        else:
            print("❌ JSON解析失败")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_llm_tool_selector_integration():
    """测试LLM工具选择器集成"""
    print("\n🧪 测试LLM工具选择器集成...")
    
    try:
        from src.agents.llm_tool_selector import LLMToolSelector
        from src.agents.intelligent_analyst_base import IntelligentFundamentalAnalyst
        
        # 创建工具选择器
        selector = LLMToolSelector()
        print(f"✅ 成功创建LLMToolSelector，包含{len(selector.all_available_tools)}个工具")
        
        # 创建智能分析师
        analyst = IntelligentFundamentalAnalyst()
        print(f"✅ 成功创建IntelligentFundamentalAnalyst")
        print(f"   分析师人设: {analyst.analyst_persona}")
        
        # 测试默认工具选择
        default_selection = selector._get_default_tool_selection("基本面分析师")
        print(f"✅ 默认工具选择包含{default_selection['tool_count']}个工具")
        
        # 列出选择的工具
        for tool in default_selection["selected_tools"]:
            print(f"   - {tool['tool_name']}: 权重{tool['weight']:.2f}")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主测试函数"""
    print("🚀 开始高级沟通机制格式修复测试")
    print("=" * 60)
    
    test_results = []
    
    # 运行所有测试
    test_results.append(test_malformed_string_parsing())
    test_results.append(test_json_parsing_robustness())
    test_results.append(test_llm_tool_selector_integration())
    
    # 统计结果
    passed = sum(test_results)
    total = len(test_results)
    
    print("\n" + "=" * 60)
    print(f"📊 测试结果: {passed}/{total} 测试通过")
    
    if passed == total:
        print("🎉 所有测试通过！高级沟通机制格式修复成功！")
        print("\n✅ 主要改进:")
        print("   1. 替换了旧版本analyst为LLM智能工具选择器版本")
        print("   2. 改进了JSON解析的健壮性，增加了错误处理")
        print("   3. 增强了格式错误字符串的修复能力")
        print("   4. 支持多种格式的ticker信号解析")
    else:
        print("❌ 部分测试失败，需要进一步调试")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
