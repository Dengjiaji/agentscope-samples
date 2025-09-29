#!/usr/bin/env python3
"""
多日投资策略主程序
基于InvestingAgents项目的多日策略模式，实现连续多日的投资分析

使用方法:
# 使用命令行参数
python main_multi_day.py --tickers AAPL,MSFT --start-date 2024-01-01 --end-date 2024-01-31

# 使用环境变量配置文件（创建 .env 文件后）
python main_multi_day.py
"""

import sys
import argparse
import asyncio
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import pandas as pd 
from advanced_investment_engine import AdvancedInvestmentAnalysisEngine
from src.scheduler.multi_day_manager import MultiDayManager
from src.config.env_config import MultiDayConfig


def validate_date_format(date_string: str) -> bool:
    """验证日期格式"""
    try:
        datetime.strptime(date_string, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def progress_callback(update: dict):
    """进度回调函数，打印进度信息"""
    if update["type"] == "daily_progress":
        print(f"📈 进度: {update['progress']*100:.1f}% ({update['day_number']}/{update['total_days']})")
    elif update["type"] == "daily_result":
        if update["status"] == "success":
            print(f"✅ {update['date']} 分析完成")
        else:
            print(f"❌ {update['date']} 分析失败: {update.get('error', '未知错误')}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="运行多日投资策略分析",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 使用命令行参数
  python main_multi_day.py --tickers AAPL,MSFT --start-date 2024-01-01 --end-date 2024-01-31
  
  # 使用环境变量配置文件 (创建 .env 文件)
  python main_multi_day.py
  
  # 命令行参数会覆盖环境变量设置
  python main_multi_day.py --tickers TSLA --disable-communications
  
  # 生成环境变量模板
  python main_multi_day.py --create-env-template
        """
    )
    
    # 工具选项
    parser.add_argument(
        "--create-env-template",
        action="store_true",
        help="创建环境变量配置模板文件并退出"
    )
    
    # 必需参数 (如果使用环境变量则可选)
    parser.add_argument(
        "--tickers", 
        type=str, 
        required=False,  # 改为可选，支持环境变量
        help="股票代码列表，用逗号分隔 (例如: AAPL,MSFT,GOOGL)"
    )
    
    # 日期参数
    parser.add_argument(
        "--start-date",
        type=str,
        help="开始日期 (YYYY-MM-DD格式)。默认为30天前"
    )
    parser.add_argument(
        "--end-date", 
        type=str,
        help="结束日期 (YYYY-MM-DD格式)。默认为今天"
    )
    
    # 沟通设置
    parser.add_argument(
        "--disable-communications",
        action="store_true",
        help="禁用沟通机制，仅进行基础分析"
    )
    parser.add_argument(
        "--disable-notifications",
        action="store_true",
        help="禁用分析师通知机制，跳过第二轮分析，直接使用第一轮结果"
    )
    parser.add_argument(
        "--max-comm-cycles",
        type=int,
        default=3,
        help="每日最大沟通轮数 (默认: 3)"
    )
    
    # 数据和输出设置
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./analysis_results_logs",
        help="输出目录路径 (默认: ./analysis_results_logs)"
    )
    parser.add_argument(
        "--disable-data-prefetch",
        action="store_true",
        help="禁用数据预取，可能会降低分析速度但减少初始等待时间"
    )
    
    # 调试选项
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="干运行模式，仅验证参数和设置，不执行实际分析"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="详细输出模式"
    )
    parser.add_argument(
        "--show-reasoning",
        action="store_true",
        help="显示分析师的详细推理过程（会产生大量输出）"
    )
    parser.add_argument(
        "--enable-okr",
        action="store_true",
        help="启用OKR声誉机制（每5个交易日复盘赋权、每30日淘汰/新入职）"
    )
    
    args = parser.parse_args()
    
    # 处理创建环境变量模板的请求
    if args.create_env_template:
        from src.config.env_config import create_env_template
        create_env_template()
        sys.exit(0)
    
    # 加载环境变量配置
    config = MultiDayConfig()
    
    # 用命令行参数覆盖环境变量配置
    config.override_with_args(args)
    
    # 验证股票代码
    if not config.tickers:
        print("❌ 错误: 请通过 --tickers 参数或环境变量 TICKERS 提供至少一个有效的股票代码")
        print("💡 提示: 可以运行 'python main_multi_day.py --create-env-template' 创建配置模板")
        sys.exit(1)
    
    # 验证日期格式
    if not validate_date_format(config.start_date):
        print(f"❌ 错误: 开始日期格式无效: {config.start_date} (需要 YYYY-MM-DD)")
        sys.exit(1)
    
    if not validate_date_format(config.end_date):
        print(f"❌ 错误: 结束日期格式无效: {config.end_date} (需要 YYYY-MM-DD)")
        sys.exit(1)
    
    # 验证日期逻辑
    start_date_obj = datetime.strptime(config.start_date, "%Y-%m-%d")
    end_date_obj = datetime.strptime(config.end_date, "%Y-%m-%d")
    
    if start_date_obj >= end_date_obj:
        print("❌ 错误: 开始日期必须早于结束日期")
        sys.exit(1)
    
    if end_date_obj > datetime.now():
        print("❌ 错误: 结束日期不能超过今天")
        sys.exit(1)
    
    # 计算分析天数
    total_days = (end_date_obj - start_date_obj).days + 1
   
    
    # 打印配置信息
    print("🔧 多日策略分析配置:")
    print(f"   📊 分析标的: {', '.join(config.tickers)}")
    print(f"   📅 时间范围: {config.start_date} 到 {config.end_date} ({total_days} 天)")
    print(f"   💬 沟通机制: {'禁用' if config.disable_communications else '启用'}")
    print(f"   🔔 通知机制: {'禁用' if config.disable_notifications else '启用'}")
    if not config.disable_communications:
        print(f"   🔄 沟通轮数: 最多 {config.max_comm_cycles} 轮/日")
    if config.disable_notifications:
        print("   ⚡ 快速模式: 仅第一轮分析，跳过分析师间通知")
    print(f"   📁 输出目录: {config.output_dir}")
    print(f"   📦 数据预取: {'禁用' if config.disable_data_prefetch else '启用'}")
    print(f"   🔍 详细推理: {'启用' if config.show_reasoning else '禁用'}")
    print(f"   🏁 OKR机制: {'启用' if config.enable_okr else '禁用'}")
    
    if config.dry_run:
        print("\n🧪 干运行模式 - 配置验证完成，未执行实际分析")
        return
    
    try:
        # 初始化分析引擎
        print("\n🔧 初始化投资分析引擎...")
        engine = AdvancedInvestmentAnalysisEngine()
        
        # 初始化多日管理器
        multi_day_manager = MultiDayManager(
            engine=engine,
            base_output_dir=config.output_dir,
            max_communication_cycles=config.max_comm_cycles,
            prefetch_data=not config.disable_data_prefetch,
            okr_enabled=config.enable_okr
        )
        
        # 执行多日策略分析
        print("\n🚀 开始执行多日策略分析...")
        start_time = datetime.now()
        
        results = multi_day_manager.run_multi_day_strategy(
            tickers=config.tickers,
            start_date=config.start_date,
            end_date=config.end_date,
            enable_communications=not config.disable_communications,
            enable_notifications=not config.disable_notifications,
            show_reasoning=config.show_reasoning,
            progress_callback=progress_callback if config.verbose else None
        )
        
        end_time = datetime.now()
        execution_time = end_time - start_time
        
        # 打印结果摘要
        print(f"\n📊 分析完成摘要:")
        print(f"   ⏱️ 总耗时: {execution_time}")
        print(f"   📈 成功天数: {results['period']['successful_days']}")
        print(f"   ❌ 失败天数: {results['period']['failed_days']}")
        print(f"   💡 成功率: {results['period']['successful_days']/results['period']['total_days']*100:.1f}%")
        
        # 绩效指标
        if "performance_analysis" in results and "error" not in results["performance_analysis"]:
            perf = results["performance_analysis"]['individual_stocks']
            for ticker in perf.keys():
                print('股票 performance:',ticker)
                print(pd.DataFrame(perf[ticker],index=[0]).T)
                # print(f"\n📈 绩效指标:")
                
                # print(f"   💰 年化收益率: {perf['annualized_return_pct']}%")
                # print(f"   💰 日均收益率: {perf['total_return_pct']}%")
                # print(f"   📊 年化波动率: {perf['annualized_volatility_pct']}%")
                # print(f"   📉 最大回撤: {perf['max_drawdown_pct']}%")
                # print(f"   ⚡ 夏普比率: {perf['sharpe_ratio']}")
                # print(f"   📅 交易期间: {perf['trading_period_years']} 年 ({perf['total_trading_days']} 交易日)")
                # print(f"   📊 总收益率: {perf['total_return_pct']}% ")

        
        print(f"\n📁 详细结果已保存到: {config.output_dir}")
        print(f"   📄 汇总报告: {results.get('session_id', 'unknown')}_summary.json")
        
    except KeyboardInterrupt:
        print("\n⏹️ 用户中断分析")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 分析过程中出现错误: {str(e)}")
        if config.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
