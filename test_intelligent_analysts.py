#!/usr/bin/env python3
"""
测试智能分析师系统
验证基于LLM的工具选择功能
"""

import sys
import os
from datetime import datetime, timedelta

# 添加项目路径
sys.path.append('/home/wuyue23/Project/IA')

from src.graph.state import AgentState
from src.agents.intelligent_analysts import (
    intelligent_fundamentals_analyst_agent,
    intelligent_technical_analyst_agent,
    intelligent_sentiment_analyst_agent,
    intelligent_valuation_analyst_agent,
    intelligent_comprehensive_analyst_agent
)
from dotenv import load_dotenv

# 加载环境变量
load_dotenv('/home/wuyue23/Project/IA/.env')


def create_test_state():
    """创建测试状态"""
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    
    state = {
        "messages": [],
        "data": {
            "tickers": ["AAPL"],  # 使用单只股票进行测试
            "start_date": start_date,
            "end_date": end_date,
            "analyst_signals": {},
            "api_keys": {
                "FINANCIAL_DATASETS_API_KEY": os.getenv("FINANCIAL_DATASETS_API_KEY")
            }
        },
        "metadata": {
            "show_reasoning": True,
            "session_id": f"intelligent_test_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        }
    }
    
    return state


def test_intelligent_fundamental_analyst():
    """测试智能基本面分析师"""
    print("🧠 测试智能基本面分析师 (LLM工具选择)")
    print("=" * 60)
    
    try:
        state = create_test_state()
        result = intelligent_fundamentals_analyst_agent(state)
        
        # 检查结果结构
        analyst_signals = state["data"]["analyst_signals"]
        if "fundamentals_analyst_agent" in analyst_signals:
            signal_data = analyst_signals["fundamentals_analyst_agent"]
            
            print(f"✅ 智能基本面分析师测试成功")
            print(f"📊 分析结果:")
            for ticker, analysis in signal_data.items():
                print(f"  {ticker}: {analysis.get('signal', 'unknown')} (置信度: {analysis.get('confidence', 0)}%)")
                
                # 检查工具选择结构
                tool_selection = analysis.get('tool_selection', {})
                if tool_selection:
                    print(f"    选择策略: {tool_selection.get('selection_strategy', 'N/A')}")
                    print(f"    工具数量: {tool_selection.get('tool_count', 0)}个")
                    
                    # 显示选择的工具
                    selected_tools = tool_selection.get('selected_tools', [])
                    if selected_tools:
                        print(f"    选择的工具:")
                        for tool in selected_tools[:3]:  # 只显示前3个
                            print(f"      - {tool.get('tool_name', 'unknown')} (权重: {tool.get('weight', 0):.1%})")
                            if 'reason' in tool:
                                print(f"        理由: {tool['reason']}")
                
                # 检查LLM增强
                metadata = analysis.get('metadata', {})
                if metadata.get('llm_enhanced'):
                    print(f"    🧠 LLM增强: {metadata.get('selection_method', 'unknown')}")
            
            return True
        else:
            print("❌ 智能基本面分析师测试失败: 没有生成分析信号")
            return False
            
    except Exception as e:
        print(f"❌ 智能基本面分析师测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_intelligent_comprehensive_analyst():
    """测试智能综合分析师"""
    print("\n🧠 测试智能综合分析师 (LLM工具选择)")
    print("=" * 60)
    
    try:
        state = create_test_state()
        result = intelligent_comprehensive_analyst_agent(state)
        
        analyst_signals = state["data"]["analyst_signals"]
        if "comprehensive_analyst_agent" in analyst_signals:
            signal_data = analyst_signals["comprehensive_analyst_agent"]
            
            print(f"✅ 智能综合分析师测试成功")
            print(f"📊 分析结果:")
            for ticker, analysis in signal_data.items():
                print(f"  {ticker}: {analysis.get('signal', 'unknown')} (置信度: {analysis.get('confidence', 0)}%)")
                
                # 检查工具选择多样性
                tool_selection = analysis.get('tool_selection', {})
                if tool_selection:
                    selected_tools = tool_selection.get('selected_tools', [])
                    tool_categories = set()
                    for tool in selected_tools:
                        tool_name = tool.get('tool_name', '')
                        if 'fundamental' in tool_name or 'profitability' in tool_name or 'growth' in tool_name:
                            tool_categories.add('基本面')
                        elif 'technical' in tool_name or 'trend' in tool_name or 'momentum' in tool_name:
                            tool_categories.add('技术面')
                        elif 'sentiment' in tool_name or 'insider' in tool_name or 'news' in tool_name:
                            tool_categories.add('情绪面')
                        elif 'valuation' in tool_name or 'dcf' in tool_name:
                            tool_categories.add('估值面')
                    
                    print(f"    工具类别覆盖: {', '.join(tool_categories)}")
                    print(f"    选择策略: {tool_selection.get('selection_strategy', 'N/A')}")
                
                # 显示详细推理（如果有）
                reasoning = analysis.get('reasoning', {})
                if reasoning.get('detailed_analysis'):
                    detailed = reasoning['detailed_analysis']
                    print(f"    🧠 LLM详细分析: {detailed[:100]}..." if len(detailed) > 100 else f"    🧠 LLM详细分析: {detailed}")
            
            return True
        else:
            print("❌ 智能综合分析师测试失败: 没有生成分析信号")
            return False
            
    except Exception as e:
        print(f"❌ 智能综合分析师测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_tool_selection_logic():
    """测试工具选择逻辑"""
    print("\n🔧 测试LLM工具选择逻辑")
    print("=" * 60)
    
    try:
        from src.agents.llm_tool_selector import LLMToolSelector
        
        tool_selector = LLMToolSelector()
        
        # 测试工具描述生成
        print("✅ 工具选择器初始化成功")
        print(f"📊 可用工具数量: {len(tool_selector.all_available_tools)}")
        
        # 按类别统计工具
        categories = {}
        for tool_name, tool_info in tool_selector.all_available_tools.items():
            category = tool_info['category']
            if category not in categories:
                categories[category] = []
            categories[category].append(tool_name)
        
        print("📋 工具分类统计:")
        for category, tools in categories.items():
            print(f"  {category}: {len(tools)}个工具")
            for tool in tools[:2]:  # 只显示前2个
                print(f"    - {tool}")
        
        # 测试提示词生成
        market_conditions = {
            "volatility_regime": "high",
            "market_sentiment": "negative",
            "analysis_date": "2024-01-15"
        }
        
        prompt = tool_selector.get_tool_selection_prompt(
            "综合分析师", "AAPL", market_conditions, "全面投资分析"
        )
        
        print(f"\n✅ 提示词生成成功 (长度: {len(prompt)} 字符)")
        print("📝 提示词预览:")
        print(prompt[:200] + "..." if len(prompt) > 200 else prompt)
        
        return True
        
    except Exception as e:
        print(f"❌ 工具选择逻辑测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_comparison_with_original():
    """对比测试：智能分析师 vs 原始分析师"""
    print("\n⚖️ 对比测试: 智能分析师 vs 原始分析师")
    print("=" * 60)
    
    try:
        # 导入原始分析师（如果存在）
        try:
            from src.agents.fundamentals_refactored import fundamentals_analyst_agent_refactored
            original_available = True
        except ImportError:
            print("⚠️ 原始分析师不可用，跳过对比测试")
            return True
        
        state1 = create_test_state()
        state2 = create_test_state()
        
        # 运行智能分析师
        print("🧠 运行智能基本面分析师...")
        intelligent_result = intelligent_fundamentals_analyst_agent(state1)
        
        # 运行原始分析师
        print("🔧 运行原始基本面分析师...")
        original_result = fundamentals_analyst_agent_refactored(state2)
        
        # 对比结果
        intelligent_signals = state1["data"]["analyst_signals"]["fundamentals_analyst_agent"]
        original_signals = state2["data"]["analyst_signals"]["fundamentals_analyst_agent"]
        
        print("📊 对比结果:")
        for ticker in ["AAPL"]:
            if ticker in intelligent_signals and ticker in original_signals:
                intel_analysis = intelligent_signals[ticker]
                orig_analysis = original_signals[ticker]
                
                print(f"  {ticker}:")
                print(f"    智能分析师: {intel_analysis.get('signal', 'unknown')} (置信度: {intel_analysis.get('confidence', 0)}%)")
                print(f"    原始分析师: {orig_analysis.get('signal', 'unknown')} (置信度: {orig_analysis.get('confidence', 0)}%)")
                
                # 对比工具使用
                intel_tools = intel_analysis.get('tool_selection', {}).get('tool_count', 0)
                orig_tools = orig_analysis.get('tool_analysis', {}).get('tools_used', 0)
                print(f"    工具使用: 智能({intel_tools}个) vs 原始({orig_tools}个)")
                
                # 对比推理质量
                intel_reasoning = len(intel_analysis.get('reasoning', {}).get('detailed_analysis', ''))
                orig_reasoning = len(orig_analysis.get('reasoning', {}).get('summary', ''))
                print(f"    推理长度: 智能({intel_reasoning}字符) vs 原始({orig_reasoning}字符)")
        
        return True
        
    except Exception as e:
        print(f"❌ 对比测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("🚀 开始测试智能分析师系统")
    print("=" * 80)
    
    # 检查API密钥
    api_key = os.getenv("FINANCIAL_DATASETS_API_KEY")
    if not api_key:
        print("❌ 错误: 未找到 FINANCIAL_DATASETS_API_KEY 环境变量")
        print("请确保在 .env 文件中设置了正确的API密钥")
        return
    
    test_results = []
    
    # 核心功能测试
    test_results.append(("工具选择逻辑", test_tool_selection_logic()))
    test_results.append(("智能基本面分析师", test_intelligent_fundamental_analyst()))
    test_results.append(("智能综合分析师", test_intelligent_comprehensive_analyst()))
    test_results.append(("对比测试", test_comparison_with_original()))
    
    # 汇总结果
    print("\n" + "=" * 80)
    print("📊 测试结果汇总:")
    print("=" * 80)
    
    passed = 0
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n🎯 总体结果: {passed}/{total} 个测试通过")
    
    if passed == total:
        print("🎉 所有测试通过! 智能分析师系统工作正常")
        print("\n💡 智能分析师的优势:")
        print("1. 🧠 LLM智能选择最适合的工具组合")
        print("2. 🎯 根据市场条件和分析目标动态调整")
        print("3. 📝 生成更详细和专业的分析推理")
        print("4. 🔄 所有分析师都可以访问全部工具")
        print("5. ⚖️ 基于专业身份智能分配工具权重")
    else:
        print("⚠️ 部分测试失败，请检查错误信息并修复")
    
    print("\n🚀 使用建议:")
    print("1. 在主程序中导入智能分析师函数")
    print("2. 智能分析师会根据LLM可用性自动降级")
    print("3. 可以通过市场条件参数影响工具选择")
    print("4. 支持自定义分析目标和专业身份")


if __name__ == "__main__":
    main()
