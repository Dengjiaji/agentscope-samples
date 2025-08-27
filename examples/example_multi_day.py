#!/usr/bin/env python3
"""
多日投资策略示例脚本
展示如何使用多日管理器进行连续多日的投资分析
"""

import sys
import os
from datetime import datetime, timedelta

# 添加项目根目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from main_with_communications import AdvancedInvestmentAnalysisEngine
from src.scheduler.multi_day_manager import MultiDayManager


def simple_progress_callback(update):
    """简单的进度回调函数"""
    if update["type"] == "daily_progress":
        print(f"📈 {update['current_date']} ({update['day_number']}/{update['total_days']})")
    elif update["type"] == "daily_result":
        status_icon = "✅" if update["status"] == "success" else "❌"
        print(f"{status_icon} {update['date']} 分析完成")


def example_short_term_analysis():
    """示例：短期（5天）策略分析"""
    print("📊 示例：短期多日策略分析")
    print("=" * 50)
    
    # 设置分析参数
    tickers = ["AAPL", "MSFT"]
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    
    print(f"📈 分析标的: {', '.join(tickers)}")
    print(f"📅 时间范围: {start_date} 到 {end_date}")
    print(f"💬 沟通机制: 启用 (最多2轮/日)")
    
    try:
        # 初始化引擎和管理器
        engine = AdvancedInvestmentAnalysisEngine()
        manager = MultiDayManager(
            engine=engine,
            max_communication_cycles=2,
            prefetch_data=True
        )
        
        # 执行多日分析
        results = manager.run_multi_day_strategy(
            tickers=tickers,
            start_date=start_date,
            end_date=end_date,
            enable_communications=True,
            progress_callback=simple_progress_callback
        )
        
        # 显示结果摘要
        print("\n📊 分析结果摘要:")
        print(f"   ✅ 成功天数: {results['period']['successful_days']}")
        print(f"   ❌ 失败天数: {results['period']['failed_days']}")
        
        if "performance_analysis" in results and "error" not in results["performance_analysis"]:
            perf = results["performance_analysis"]
            print(f"   💰 总收益率: {perf['total_return_pct']}%")
            print(f"   📉 最大回撤: {perf['max_drawdown_pct']}%")
        
        print(f"\n📁 会话ID: {results['session_id']}")
        
    except Exception as e:
        print(f"❌ 分析失败: {e}")


def example_disable_communications():
    """示例：禁用沟通机制的快速分析"""
    print("\n📊 示例：禁用沟通的快速分析")
    print("=" * 50)
    
    # 设置分析参数（更短的时间范围）
    tickers = ["TSLA"]
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
    
    print(f"📈 分析标的: {', '.join(tickers)}")
    print(f"📅 时间范围: {start_date} 到 {end_date}")
    print(f"💬 沟通机制: 禁用")
    
    try:
        # 初始化引擎和管理器
        engine = AdvancedInvestmentAnalysisEngine()
        manager = MultiDayManager(
            engine=engine,
            max_communication_cycles=0,  # 不影响，因为会禁用通信
            prefetch_data=False  # 禁用预取以加快速度
        )
        
        # 执行多日分析（禁用沟通）
        start_time = datetime.now()
        results = manager.run_multi_day_strategy(
            tickers=tickers,
            start_date=start_date,
            end_date=end_date,
            enable_communications=False,  # 禁用沟通机制
            progress_callback=simple_progress_callback
        )
        execution_time = datetime.now() - start_time
        
        # 显示结果摘要
        print(f"\n📊 分析结果摘要 (耗时: {execution_time}):")
        print(f"   ✅ 成功天数: {results['period']['successful_days']}")
        print(f"   📁 会话ID: {results['session_id']}")
        
    except Exception as e:
        print(f"❌ 分析失败: {e}")


def example_custom_output_dir():
    """示例：自定义输出目录"""
    print("\n📊 示例：自定义输出目录")
    print("=" * 50)
    
    # 创建自定义输出目录
    custom_output_dir = "/tmp/my_investment_analysis"
    os.makedirs(custom_output_dir, exist_ok=True)
    
    # 设置分析参数
    tickers = ["GOOGL"]
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    
    print(f"📈 分析标的: {', '.join(tickers)}")
    print(f"📅 时间范围: {start_date} 到 {end_date}")
    print(f"📁 输出目录: {custom_output_dir}")
    
    try:
        # 初始化引擎和管理器
        engine = AdvancedInvestmentAnalysisEngine()
        manager = MultiDayManager(
            engine=engine,
            base_output_dir=custom_output_dir,  # 自定义输出目录
            max_communication_cycles=1,
            prefetch_data=True
        )
        
        # 执行多日分析
        results = manager.run_multi_day_strategy(
            tickers=tickers,
            start_date=start_date,
            end_date=end_date,
            enable_communications=True,
            progress_callback=simple_progress_callback
        )
        
        # 列出生成的文件
        print(f"\n📁 生成的文件:")
        session_files = [f for f in os.listdir(custom_output_dir) 
                        if f.startswith(results['session_id'])]
        for file in session_files:
            print(f"   📄 {file}")
        
    except Exception as e:
        print(f"❌ 分析失败: {e}")


if __name__ == "__main__":
    print("🚀 多日投资策略示例")
    print("=" * 60)
    
    # 运行示例
    try:
        example_short_term_analysis()
        
        example_disable_communications()
        
        example_custom_output_dir()
        
        print(f"\n🎉 所有示例执行完成!")
        
    except KeyboardInterrupt:
        print("\n⏹️ 用户中断")
    except Exception as e:
        print(f"\n❌ 示例执行失败: {e}")
        import traceback
        traceback.print_exc()
