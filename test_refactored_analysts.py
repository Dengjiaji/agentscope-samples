#!/usr/bin/env python3
"""
测试重构后的分析师系统
验证工具化架构的功能
"""

import sys
import os
from datetime import datetime, timedelta

# 添加项目路径
sys.path.append('/home/wuyue23/Project/IA')

from src.graph.state import AgentState
from src.agents.fundamentals_refactored import fundamentals_analyst_agent_refactored
from src.agents.technicals_refactored import technical_analyst_agent_refactored
from src.agents.sentiment_refactored import sentiment_analyst_agent_refactored
from src.agents.valuation_refactored import valuation_analyst_agent_refactored
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
            "session_id": f"test_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        }
    }
    
    return state


def test_fundamental_analyst():
    """测试基本面分析师"""
    print("🔧 测试基本面分析师 (工具化版本)")
    print("=" * 60)
    
    try:
        state = create_test_state()
        result = fundamentals_analyst_agent_refactored(state)
        
        # 检查结果结构
        analyst_signals = state["data"]["analyst_signals"]
        if "fundamentals_analyst_agent" in analyst_signals:
            signal_data = analyst_signals["fundamentals_analyst_agent"]
            
            print(f"✅ 基本面分析师测试成功")
            print(f"📊 分析结果:")
            for ticker, analysis in signal_data.items():
                print(f"  {ticker}: {analysis.get('signal', 'unknown')} (置信度: {analysis.get('confidence', 0)}%)")
                
                # 检查工具分析结构
                tool_analysis = analysis.get('tool_analysis', {})
                if tool_analysis:
                    print(f"    工具使用: {tool_analysis.get('tools_used', 0)}个")
                    print(f"    成功工具: {tool_analysis.get('successful_tools', 0)}个")
                    print(f"    失败工具: {tool_analysis.get('failed_tools', 0)}个")
            
            return True
        else:
            print("❌ 基本面分析师测试失败: 没有生成分析信号")
            return False
            
    except Exception as e:
        print(f"❌ 基本面分析师测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_technical_analyst():
    """测试技术分析师"""
    print("\n🔧 测试技术分析师 (工具化版本)")
    print("=" * 60)
    
    try:
        state = create_test_state()
        result = technical_analyst_agent_refactored(state)
        
        analyst_signals = state["data"]["analyst_signals"]
        if "technical_analyst_agent" in analyst_signals:
            signal_data = analyst_signals["technical_analyst_agent"]
            
            print(f"✅ 技术分析师测试成功")
            print(f"📊 分析结果:")
            for ticker, analysis in signal_data.items():
                print(f"  {ticker}: {analysis.get('signal', 'unknown')} (置信度: {analysis.get('confidence', 0)}%)")
                
                tool_analysis = analysis.get('tool_analysis', {})
                if tool_analysis:
                    print(f"    工具使用: {tool_analysis.get('tools_used', 0)}个")
                    print(f"    成功工具: {tool_analysis.get('successful_tools', 0)}个")
                    print(f"    失败工具: {tool_analysis.get('failed_tools', 0)}个")
            
            return True
        else:
            print("❌ 技术分析师测试失败: 没有生成分析信号")
            return False
            
    except Exception as e:
        print(f"❌ 技术分析师测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_sentiment_analyst():
    """测试情绪分析师"""
    print("\n🔧 测试情绪分析师 (工具化版本)")
    print("=" * 60)
    
    try:
        state = create_test_state()
        result = sentiment_analyst_agent_refactored(state)
        
        analyst_signals = state["data"]["analyst_signals"]
        if "sentiment_analyst_agent" in analyst_signals:
            signal_data = analyst_signals["sentiment_analyst_agent"]
            
            print(f"✅ 情绪分析师测试成功")
            print(f"📊 分析结果:")
            for ticker, analysis in signal_data.items():
                print(f"  {ticker}: {analysis.get('signal', 'unknown')} (置信度: {analysis.get('confidence', 0)}%)")
                
                tool_analysis = analysis.get('tool_analysis', {})
                if tool_analysis:
                    print(f"    工具使用: {tool_analysis.get('tools_used', 0)}个")
                    print(f"    成功工具: {tool_analysis.get('successful_tools', 0)}个")
                    print(f"    失败工具: {tool_analysis.get('failed_tools', 0)}个")
            
            return True
        else:
            print("❌ 情绪分析师测试失败: 没有生成分析信号")
            return False
            
    except Exception as e:
        print(f"❌ 情绪分析师测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_valuation_analyst():
    """测试估值分析师"""
    print("\n🔧 测试估值分析师 (工具化版本)")
    print("=" * 60)
    
    try:
        state = create_test_state()
        result = valuation_analyst_agent_refactored(state)
        
        analyst_signals = state["data"]["analyst_signals"]
        if "valuation_analyst_agent" in analyst_signals:
            signal_data = analyst_signals["valuation_analyst_agent"]
            
            print(f"✅ 估值分析师测试成功")
            print(f"📊 分析结果:")
            for ticker, analysis in signal_data.items():
                print(f"  {ticker}: {analysis.get('signal', 'unknown')} (置信度: {analysis.get('confidence', 0)}%)")
                
                tool_analysis = analysis.get('tool_analysis', {})
                if tool_analysis:
                    print(f"    工具使用: {tool_analysis.get('tools_used', 0)}个")
                    print(f"    成功工具: {tool_analysis.get('successful_tools', 0)}个")
                    print(f"    失败工具: {tool_analysis.get('failed_tools', 0)}个")
                
                # 显示估值摘要
                valuation_summary = analysis.get('valuation_summary', {})
                if valuation_summary and 'average_value_gap' in valuation_summary:
                    print(f"    平均价值差距: {valuation_summary['average_value_gap']:.1f}%")
                    print(f"    估值共识: {valuation_summary.get('valuation_consensus', 'unknown')}")
            
            return True
        else:
            print("❌ 估值分析师测试失败: 没有生成分析信号")
            return False
            
    except Exception as e:
        print(f"❌ 估值分析师测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_individual_tools():
    """测试单个工具"""
    print("\n🔧 测试单个分析工具")
    print("=" * 60)
    
    try:
        from src.tools.analysis_tools_unified import analyze_profitability, dcf_valuation_analysis
        
        api_key = os.getenv("FINANCIAL_DATASETS_API_KEY")
        end_date = datetime.now().strftime("%Y-%m-%d")
        
        # 测试盈利能力分析工具
        result1 = analyze_profitability.invoke({
            "ticker": "AAPL",
            "end_date": end_date,
            "api_key": api_key
        })
        
        print(f"✅ 盈利能力分析工具测试:")
        print(f"  信号: {result1.get('signal', 'unknown')}")
        print(f"  置信度: {result1.get('confidence', 0)}%")
        print(f"  推理: {result1.get('reasoning', 'N/A')}")
        
        # 测试DCF估值工具
        result2 = dcf_valuation_analysis.invoke({
            "ticker": "AAPL",
            "end_date": end_date,
            "api_key": api_key
        })
        
        print(f"\n✅ DCF估值分析工具测试:")
        print(f"  信号: {result2.get('signal', 'unknown')}")
        print(f"  置信度: {result2.get('confidence', 0)}%")
        print(f"  推理: {result2.get('reasoning', 'N/A')}")
        
        return True
        
    except Exception as e:
        print(f"❌ 工具测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("🚀 开始测试重构后的分析师系统")
    print("=" * 80)
    
    # 检查API密钥
    api_key = os.getenv("FINANCIAL_DATASETS_API_KEY")
    if not api_key:
        print("❌ 错误: 未找到 FINANCIAL_DATASETS_API_KEY 环境变量")
        print("请确保在 .env 文件中设置了正确的API密钥")
        return
    
    test_results = []
    
    # 测试单个工具
    test_results.append(("单个工具测试", test_individual_tools()))
    
    # 测试各个分析师
    test_results.append(("基本面分析师", test_fundamental_analyst()))
    test_results.append(("技术分析师", test_technical_analyst()))
    test_results.append(("情绪分析师", test_sentiment_analyst()))
    test_results.append(("估值分析师", test_valuation_analyst()))
    
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
        print("🎉 所有测试通过! 重构后的系统工作正常")
    else:
        print("⚠️ 部分测试失败，请检查错误信息并修复")
    
    print("\n💡 使用建议:")
    print("1. 如果测试通过，可以在主程序中替换原有的分析师")
    print("2. 新的工具化架构支持更灵活的分析逻辑")
    print("3. 可以根据需要添加新的分析工具")
    print("4. LLM推理功能提供更详细的分析解释")


if __name__ == "__main__":
    main()
