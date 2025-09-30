#!/usr/bin/env python3
"""
LLM记忆管理系统测试
用于测试live_trading_thinking_fund.py中的LLM记忆管理功能

使用方法:
python test_llm_memory_system.py

功能:
1. 创建虚拟的交易表现数据
2. 测试LLM记忆管理决策系统
3. 展示完整的记忆操作流程
"""

import os
import sys
import json
from datetime import datetime
from collections import defaultdict
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

def create_test_data():
    """创建测试用的live_env数据"""
    
    print("📊 创建测试数据...")
    
    # 模拟真实交易场景的数据
    live_env = {
        'pm_signals': {
            'AAPL': {'signal': 'bullish', 'action': 'long', 'confidence': 85},
            'MSFT': {'signal': 'neutral', 'action': 'hold', 'confidence': 50},
            'GOOGL': {'signal': 'bearish', 'action': 'short', 'confidence': 75},
            'TSLA': {'signal': 'bullish', 'action': 'long', 'confidence': 70},
            'NVDA': {'signal': 'neutral', 'action': 'hold', 'confidence': 55}
        },
        'ana_signals': defaultdict(lambda: defaultdict(str)),
        'real_returns': {
            'AAPL': 0.048,   # 4.8% 收益，PM看多正确
            'MSFT': -0.012,  # -1.2% 损失，PM中性还算合理
            'GOOGL': 0.035,  # 3.5% 收益，PM看空错误
            'TSLA': -0.062,  # -6.2% 损失，PM看多错误
            'NVDA': 0.018    # 1.8% 收益，PM中性还算合理
        }
    }
    
    # 情绪分析师：优秀表现 (100% 准确率)
    live_env['ana_signals']['sentiment_analyst']['AAPL'] = 'bullish'   # ✅ 正确
    live_env['ana_signals']['sentiment_analyst']['MSFT'] = 'bearish'   # ✅ 正确  
    live_env['ana_signals']['sentiment_analyst']['GOOGL'] = 'bullish'  # ✅ 正确
    live_env['ana_signals']['sentiment_analyst']['TSLA'] = 'bearish'   # ✅ 正确
    live_env['ana_signals']['sentiment_analyst']['NVDA'] = 'bullish'   # ✅ 正确
    
    # 技术分析师：良好表现 (80% 准确率)
    live_env['ana_signals']['technical_analyst']['AAPL'] = 'bullish'   # ✅ 正确
    live_env['ana_signals']['technical_analyst']['MSFT'] = 'neutral'   # ✅ 正确
    live_env['ana_signals']['technical_analyst']['GOOGL'] = 'bullish'  # ✅ 正确
    live_env['ana_signals']['technical_analyst']['TSLA'] = 'bullish'   # ❌ 错误
    live_env['ana_signals']['technical_analyst']['NVDA'] = 'bullish'   # ✅ 正确
    
    # 基本面分析师：一般表现 (40% 准确率)
    live_env['ana_signals']['fundamentals_analyst']['AAPL'] = 'neutral'  # ❌ 保守错失机会
    live_env['ana_signals']['fundamentals_analyst']['MSFT'] = 'bullish'  # ❌ 错误
    live_env['ana_signals']['fundamentals_analyst']['GOOGL'] = 'bullish' # ✅ 正确
    live_env['ana_signals']['fundamentals_analyst']['TSLA'] = 'neutral'  # ❌ 未识别风险
    live_env['ana_signals']['fundamentals_analyst']['NVDA'] = 'bullish'  # ✅ 正确
    
    # 估值分析师：极差表现 (0% 准确率)
    live_env['ana_signals']['valuation_analyst']['AAPL'] = 'bearish'   # ❌ 严重错误
    live_env['ana_signals']['valuation_analyst']['MSFT'] = 'bullish'   # ❌ 错误
    live_env['ana_signals']['valuation_analyst']['GOOGL'] = 'bearish'  # ❌ 错误
    live_env['ana_signals']['valuation_analyst']['TSLA'] = 'bullish'   # ❌ 严重错误
    live_env['ana_signals']['valuation_analyst']['NVDA'] = 'bearish'   # ❌ 错误
    
    print("✅ 测试数据创建完成")
    return live_env

def display_test_data(live_env, tickers):
    """显示测试数据详情"""
    
    print(f"\n📈 Portfolio Manager 信号 vs 实际收益:")
    print("-" * 60)
    for ticker in tickers:
        pm_signal = live_env['pm_signals'][ticker]
        actual_return = live_env['real_returns'][ticker]
        
        # 判断PM准确性
        pm_correct = False
        if pm_signal['signal'] == 'bullish' and actual_return > 0.01:
            pm_correct = True
        elif pm_signal['signal'] == 'bearish' and actual_return < -0.01:
            pm_correct = True
        elif pm_signal['signal'] == 'neutral' and abs(actual_return) <= 0.015:
            pm_correct = True
        
        status = "✅ 正确" if pm_correct else "❌ 错误"
        print(f"{ticker:6}: PM预测 {pm_signal['signal']:7} (置信度:{pm_signal['confidence']:2}%) → 实际 {actual_return:6.2%} {status}")
    
    print(f"\n🔍 各分析师预测表现:")
    print("-" * 60)
    
    # 计算并显示每个分析师的表现
    for analyst in live_env['ana_signals']:
        print(f"\n{analyst}:")
        correct = 0
        total = 0
        
        for ticker in tickers:
            signal = live_env['ana_signals'][analyst][ticker]
            actual = live_env['real_returns'][ticker]
            total += 1
            
            # 判断准确性
            is_correct = False
            if signal == 'bullish' and actual > 0.01:
                is_correct = True
            elif signal == 'bearish' and actual < -0.01:
                is_correct = True
            elif signal == 'neutral' and abs(actual) <= 0.015:
                is_correct = True
            
            if is_correct:
                correct += 1
            
            status = "✅" if is_correct else "❌"
            print(f"  {ticker:6}: 预测 {signal:7} → 实际 {actual:6.2%} {status}")
        
        accuracy = (correct / total * 100) if total > 0 else 0
        
        # 根据准确率显示评级
        if accuracy >= 80:
            grade = "🏆 优秀"
        elif accuracy >= 60:
            grade = "👍 良好"
        elif accuracy >= 40:
            grade = "😐 一般"
        elif accuracy >= 20:
            grade = "👎 不佳"
        else:
            grade = "💥 极差"
            
        print(f"  >> 准确率: {accuracy:5.1f}% ({correct}/{total}) {grade}")

def test_llm_memory_system():
    """测试LLM记忆管理系统"""
    
    print("🧠 LLM记忆管理系统测试")
    print("=" * 70)
    
    try:
        # 导入LLM记忆系统
        print("📦 导入LLM记忆系统...")
        from live_trading_thinking_fund import LLMMemoryDecisionSystem
        print("✅ 成功导入LLMMemoryDecisionSystem")
        
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        print("请确保live_trading_thinking_fund.py文件存在且可导入")
        return False
    
    # 创建测试数据
    live_env = create_test_data()
    tickers = ['AAPL', 'MSFT', 'GOOGL', 'TSLA', 'NVDA']
    date = "2025-01-15"
    
    # 显示测试数据
    display_test_data(live_env, tickers)
    
    # 初始化LLM记忆系统
    print(f"\n🤖 初始化LLM记忆系统...")
    try:
        llm_system = LLMMemoryDecisionSystem()
        print(f"✅ LLM记忆系统初始化完成")
        print(f"LLM可用状态: {'是' if llm_system.llm_available else '否'}")
        
    except Exception as e:
        print(f"❌ LLM系统初始化失败: {e}")
        return False
    
    # 准备性能数据
    print(f"\n📋 准备性能数据...")
    performance_data = {
        'pm_signals': live_env['pm_signals'],
        'actual_returns': live_env['real_returns'],
        'analyst_signals': dict(live_env['ana_signals']),  # 转换defaultdict为普通dict
        'tickers': tickers
    }
    print(f"✅ 性能数据准备完成")
    
    # 执行LLM记忆管理决策
    print(f"\n🚀 执行LLM记忆管理决策...")
    print("=" * 50)
    
    try:
        decision_result = llm_system.make_llm_memory_decision_with_tools(performance_data, date)
        
        # 显示决策结果
        print(f"\n📋 LLM决策结果:")
        print(f"  状态: {decision_result['status']}")
        print(f"  日期: {decision_result.get('date', 'N/A')}")
        
        if decision_result['status'] == 'success':
            mode = decision_result.get('mode', 'unknown')
            print(f"  模式: {mode}")
            
            if mode == 'operations_executed':
                operations_count = decision_result.get('operations_count', 0)
                print(f"  执行操作数: {operations_count}")
                
                if 'execution_results' in decision_result:
                    execution_results = decision_result['execution_results']
                    
                    # 统计执行结果
                    successful = sum(1 for result in execution_results 
                                   if result['result']['status'] == 'success')
                    total = len(execution_results)
                    
                    print(f"\n📊 执行统计:")
                    print(f"  总操作数: {total}")
                    print(f"  成功: {successful}")
                    print(f"  失败: {total - successful}")
                    print(f"  成功率: {(successful/total*100):.1f}%")
                    
                    # 显示每个操作的详情
                    print(f"\n🛠️ 操作详情:")
                    for i, exec_result in enumerate(execution_results, 1):
                        tool_name = exec_result['tool_name']
                        args = exec_result['args']
                        result = exec_result['result']
                        
                        print(f"\n  {i}. {tool_name}")
                        print(f"     分析师: {args.get('analyst_id', 'N/A')}")
                        print(f"     原因: {args.get('reason', 'N/A')}")
                        
                        if result['status'] == 'success':
                            print(f"     状态: ✅ 成功")
                            if 'memory_id' in result:
                                print(f"     记忆ID: {result['memory_id']}")
                        else:
                            print(f"     状态: ❌ 失败")
                            print(f"     错误: {result.get('error', 'Unknown')}")
                        
                        # 显示记忆内容摘要
                        if 'content' in args:
                            content = args['content']
                            # 显示前100个字符
                            content_preview = content[:100] + "..." if len(content) > 100 else content
                            print(f"     内容: {content_preview}")
                
                # 显示LLM推理过程
                if 'llm_reasoning' in decision_result:
                    print(f"\n💭 LLM推理过程:")
                    reasoning = decision_result['llm_reasoning']
                    # 如果推理过程太长，分行显示
                    if len(reasoning) > 200:
                        lines = reasoning.split('\n')
                        for line in lines[:10]:  # 只显示前10行
                            print(f"     {line}")
                        if len(lines) > 10:
                            print(f"     ... (共{len(lines)}行，省略显示)")
                    else:
                        print(f"     {reasoning}")
                
            elif mode == 'no_action':
                print(f"  LLM决定: 无需执行记忆操作")
                reasoning = decision_result.get('reasoning', 'N/A')
                print(f"  理由: {reasoning}")
            
            else:
                print(f"  未知模式: {mode}")
        
        elif decision_result['status'] == 'skipped':
            reason = decision_result.get('reason', 'N/A')
            print(f"  跳过原因: {reason}")
        
        elif decision_result['status'] == 'failed':
            error = decision_result.get('error', 'N/A')
            print(f"  失败原因: {error}")
        
        else:
            print(f"  未知状态: {decision_result['status']}")
        
        print(f"\n🎉 LLM记忆管理测试完成！")
        return True
        
    except Exception as e:
        print(f"❌ LLM决策执行失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    
    print("🔬 开始LLM记忆管理系统测试")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"工作目录: {os.getcwd()}")
    
    # 显示环境变量加载状态
    print(f"\n🔧 环境变量状态:")
    env_vars_to_check = [
        "OPENAI_API_KEY", 
        "ANTHROPIC_API_KEY", 
        "MEMORY_SAVE_DISABLED",
        "MEMORY_DEBUG",
        "MEMORY_LLM_MODEL",
        "MEMORY_LLM_PROVIDER"
    ]
    
    for env_var in env_vars_to_check:
        value = os.getenv(env_var)
        if value:
            # 只显示前几个字符，保护敏感信息
            if "API_KEY" in env_var:
                display_value = value[:8] + "..." if len(value) > 8 else value
            else:
                display_value = value
            print(f"  {env_var}: ✅ {display_value}")
        else:
            print(f"  {env_var}: ❌ 未设置")
    
    # 检查.env文件是否存在
    env_file = os.path.join(os.getcwd(), '.env')
    if os.path.exists(env_file):
        print(f"  .env文件: ✅ 存在 ({env_file})")
    else:
        print(f"  .env文件: ❌ 不存在 ({env_file})")
    
    try:
        success = test_llm_memory_system()
        
        if success:
            print(f"\n✅ 测试成功完成！")
            print(f"💡 提示: 如果LLM不可用，系统会跳过记忆操作")
            print(f"💡 提示: 如果记忆工具不可用，会显示相应的警告信息")
        else:
            print(f"\n❌ 测试失败！")
            print(f"💡 请检查依赖项和配置")
        
        return 0 if success else 1
        
    except KeyboardInterrupt:
        print(f"\n\n⚠️ 用户中断测试")
        return 1
    except Exception as e:
        print(f"\n\n❌ 测试过程中发生未预期的错误: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
