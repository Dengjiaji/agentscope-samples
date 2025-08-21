#!/usr/bin/env python3
"""
单独测试某个分析师的脚本
适合调试特定的分析师逻辑
"""

import sys
import os
import json
import traceback
from datetime import datetime, timedelta
from dotenv import load_dotenv

# 添加项目路径
sys.path.append('/Users/wy/Downloads/Project/InvestingAgents')

# 加载环境变量
load_dotenv('/Users/wy/Downloads/Project/InvestingAgents/.env')

from src.graph.state import AgentState
from langchain_core.messages import HumanMessage

# 导入所有四个分析师
from src.agents.fundamentals import fundamentals_analyst_agent
from src.agents.sentiment import sentiment_analyst_agent
from src.agents.technicals import technical_analyst_agent
from src.agents.valuation import valuation_analyst_agent


def debug_fundamentals_analyst():
    """调试基本面分析师"""
    print("🧪 调试基本面分析师 (Fundamentals)")
    print("=" * 50)
    
    # 检查环境变量
    api_key = os.getenv('FINANCIAL_DATASETS_API_KEY')
    openai_key = os.getenv('OPENAI_API_KEY')
    model_name = os.getenv('MODEL_NAME')
    print(f"FINANCIAL_DATASETS_API_KEY: {'✅ 已设置' if api_key else '❌ 未设置'}")
    print(f"OPENAI_API_KEY: {'✅ 已设置' if openai_key else '❌ 未设置'}")
    print(f"MODEL_NAME: {'✅ 已设置'+model_name if model_name else '❌ 未设置'}")
    
    # 创建测试状态
    state = AgentState(
        messages=[HumanMessage(content="Debug test")],
        data={
            "tickers": ["AAPL"],  # 可以修改为你想测试的股票
            "start_date": "2024-01-01",
            "end_date": "2024-03-01",
            "analyst_signals": {},
            "api_keys": {
                'FINANCIAL_DATASETS_API_KEY': api_key,
                'OPENAI_API_KEY': openai_key,
            }
        },
        metadata={
            "show_reasoning": True,  # 显示详细推理
            "model_name": model_name,
            "model_provider": "OpenAI"
        }
    )
    
    try:
        print("\n🔄 开始执行基本面分析...")
        
        # 执行分析师函数
        result = fundamentals_analyst_agent(state, agent_id="fundamentals_analyst_agent")
        
        print("✅ 基本面分析执行成功!")
        
        # 显示结果
        signals = state['data']['analyst_signals'].get('fundamentals_analyst_agent', {})
        if signals:
            print("\n📊 分析结果:")
            print(signals)
        
    except Exception as e:
        print(f"❌ 执行失败: {str(e)}")
        print("\n完整错误信息:")
        traceback.print_exc()
        return None


def debug_sentiment_analyst():
    """调试情绪分析师"""
    print("🧪 调试情绪分析师 (Sentiment)")
    print("=" * 50)
    
    # 检查环境变量
    api_key = os.getenv('FINANCIAL_DATASETS_API_KEY')
    openai_key = os.getenv('OPENAI_API_KEY')
    model_name = os.getenv('MODEL_NAME')
    print(f"FINANCIAL_DATASETS_API_KEY: {'✅ 已设置' if api_key else '❌ 未设置'}")
    print(f"OPENAI_API_KEY: {'✅ 已设置' if openai_key else '❌ 未设置'}")
    print(f"MODEL_NAME: {'✅ 已设置 ' + model_name if model_name else '❌ 未设置'}")
    
    # 创建测试状态
    state = AgentState(
        messages=[HumanMessage(content="Debug test")],
        data={
            "tickers": ["AAPL"],  # 可以修改为你想测试的股票
            "start_date": "2024-01-01",
            "end_date": "2024-03-01",
            "analyst_signals": {},
            "api_keys": {
                'FINANCIAL_DATASETS_API_KEY': api_key,
                'OPENAI_API_KEY': openai_key,
            }
        },
        metadata={
            "show_reasoning": True,  # 显示详细推理
            "model_name": model_name,
            "model_provider": "OpenAI"
        }
    )
    
    try:
        print("\n🔄 开始执行情绪分析...")
        
        # 执行分析师函数
        result = sentiment_analyst_agent(state, agent_id="sentiment_analyst_agent")
        
        print("✅ 情绪分析执行成功!")
        
        # 显示结果
        signals = state['data']['analyst_signals'].get('sentiment_analyst_agent', {})
        if signals:
            print("\n📊 分析结果:")
            print(signals)
        
    except Exception as e:
        print(f"❌ 执行失败: {str(e)}")
        print("\n完整错误信息:")
        traceback.print_exc()
        return None


def debug_technicals_analyst():
    """调试技术分析师"""
    print("🧪 调试技术分析师 (Technicals)")
    print("=" * 50)
    
    # 检查环境变量
    api_key = os.getenv('FINANCIAL_DATASETS_API_KEY')
    openai_key = os.getenv('OPENAI_API_KEY')
    model_name = os.getenv('MODEL_NAME')
    print(f"FINANCIAL_DATASETS_API_KEY: {'✅ 已设置' if api_key else '❌ 未设置'}")
    print(f"OPENAI_API_KEY: {'✅ 已设置' if openai_key else '❌ 未设置'}")
    print(f"MODEL_NAME: {'✅ 已设置 ' + model_name if model_name else '❌ 未设置'}")
    
    # 创建测试状态
    state = AgentState(
        messages=[HumanMessage(content="Debug test")],
        data={
            "tickers": ["AAPL"],  # 可以修改为你想测试的股票
            "start_date": "2024-01-01",
            "end_date": "2024-03-01",
            "analyst_signals": {},
            "api_keys": {
                'FINANCIAL_DATASETS_API_KEY': api_key,
                'OPENAI_API_KEY': openai_key,
            }
        },
        metadata={
            "show_reasoning": True,  # 显示详细推理
            "model_name": model_name,
            "model_provider": "OpenAI"
        }
    )
    
    try:
        print("\n🔄 开始执行技术分析...")
        
        # 执行分析师函数
        result = technical_analyst_agent(state, agent_id="technical_analyst_agent")
        
        print("✅ 技术分析执行成功!")
        
        # 显示结果
        signals = state['data']['analyst_signals'].get('technical_analyst_agent', {})
        if signals:
            print("\n📊 分析结果:")
            print(signals)
        
    except Exception as e:
        print(f"❌ 执行失败: {str(e)}")
        print("\n完整错误信息:")
        traceback.print_exc()
        return None


def debug_valuation_analyst():
    """调试估值分析师"""
    print("🧪 调试估值分析师 (Valuation)")
    print("=" * 50)
    
    # 检查环境变量
    api_key = os.getenv('FINANCIAL_DATASETS_API_KEY')
    openai_key = os.getenv('OPENAI_API_KEY')
    model_name = os.getenv('MODEL_NAME')
    print(f"FINANCIAL_DATASETS_API_KEY: {'✅ 已设置' if api_key else '❌ 未设置'}")
    print(f"OPENAI_API_KEY: {'✅ 已设置' if openai_key else '❌ 未设置'}")
    print(f"MODEL_NAME: {'✅ 已设置 ' + model_name if model_name else '❌ 未设置'}")
    
    # 创建测试状态
    state = AgentState(
        messages=[HumanMessage(content="Debug test")],
        data={
            "tickers": ["AAPL"],  # 可以修改为你想测试的股票
            "start_date": "2024-01-01",
            "end_date": "2024-03-01",
            "analyst_signals": {},
            "api_keys": {
                'FINANCIAL_DATASETS_API_KEY': api_key,
                'OPENAI_API_KEY': openai_key,
            }
        },
        metadata={
            "show_reasoning": True,  # 显示详细推理
            "model_name": model_name,
            "model_provider": "OpenAI"
        }
    )
    
    try:
        print("\n🔄 开始执行估值分析...")
        
        # 执行分析师函数
        result = valuation_analyst_agent(state, agent_id="valuation_analyst_agent")
        
        print("✅ 估值分析执行成功!")
        
        # 显示结果
        signals = state['data']['analyst_signals'].get('valuation_analyst_agent', {})
        if signals:
            print("\n📊 分析结果:")
            print(signals)
        
    except Exception as e:
        print(f"❌ 执行失败: {str(e)}")
        print("\n完整错误信息:")
        traceback.print_exc()
        return None


def test_all_four_analysts():
    """测试所有四个分析师"""
    print("🚀 测试所有四个分析师")
    print("=" * 60)
    
    analysts = {
        'fundamentals': debug_fundamentals_analyst,
        'sentiment': debug_sentiment_analyst,
        'technicals': debug_technicals_analyst,
        'valuation': debug_valuation_analyst,
    }
    
    results = {}
    
    for name, func in analysts.items():
        try:
            print(f"\n{'='*20} {name.upper()} {'='*20}")
            func()
            results[name] = '✅ 成功'
        except Exception as e:
            results[name] = f'❌ 失败: {str(e)}'
            print(f"❌ {name} 失败: {str(e)}")
    
    # 总结报告
    print("\n" + "="*60)
    print("📊 测试总结报告")
    print("="*60)
    for name, status in results.items():
        print(f"{name.ljust(15)}: {status}")


def interactive_debug():
    """交互式调试菜单"""
    print("\n🎮 交互式调试菜单")
    print("请选择要调试的分析师:")
    print("  1 - 基本面分析师 (Fundamentals)")
    print("  2 - 情绪分析师 (Sentiment)")
    print("  3 - 技术分析师 (Technicals)")
    print("  4 - 估值分析师 (Valuation)")
    print("  a - 测试所有分析师")
    print("  q - 退出")
    print("-" * 40)
    
    while True:
        try:
            choice = input("\n请输入选择: ").strip().lower()
            
            if choice == 'q':
                print("👋 退出调试")
                break
            elif choice == '1':
                debug_fundamentals_analyst()
            elif choice == '2':
                debug_sentiment_analyst()
            elif choice == '3':
                debug_technicals_analyst()
            elif choice == '4':
                debug_valuation_analyst()
            elif choice == 'a':
                test_all_four_analysts()
            else:
                print("无效选择，请重试")
                
        except KeyboardInterrupt:
            print("\n👋 退出调试")
            break
        except Exception as e:
            print(f"执行错误: {str(e)}")

