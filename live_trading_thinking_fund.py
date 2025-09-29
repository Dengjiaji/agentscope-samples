#!/usr/bin/env python3
"""
Live交易思考基金 - 时间Sandbox系统
模拟真实交易日的时间流程：交易前分析 + 交易后复盘

时间点设计：
- 交易日：交易前 + 交易后
- 非交易日：仅交易后

使用方法:
# 运行指定日期的完整模拟
python live_trading_thinking_fund.py --date 2025-01-15 --tickers AAPL,MSFT

# 使用环境变量配置
python live_trading_thinking_fund.py --date 2025-01-15

# 强制运行
python live_trading_thinking_fund.py --date 2025-01-15 --force-run
"""
import pdb
import os
import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入现有的live trading system
from live_trading_system import LiveTradingSystem
from src.config.env_config import LiveTradingConfig

# 尝试导入美国交易日历包
try:
    import pandas_market_calendars as mcal
    US_TRADING_CALENDAR_AVAILABLE = True
except ImportError:
    try:
        import exchange_calendars as xcals
        US_TRADING_CALENDAR_AVAILABLE = True
    except ImportError:
        US_TRADING_CALENDAR_AVAILABLE = False


class LiveTradingThinkingFund:
    """Live交易思考基金 - 时间Sandbox系统"""
    
    def __init__(self, base_dir: str = None):
        """初始化思考基金系统"""
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).parent
        self.sandbox_dir = self.base_dir / "sandbox_logs"
        self.sandbox_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化Live交易系统
        self.live_system = LiveTradingSystem(base_dir=base_dir)
        
        # 时间点定义
        self.PRE_MARKET = "pre_market"    # 交易前
        self.POST_MARKET = "post_market"  # 交易后
        
    def is_trading_day(self, date: str) -> bool:
        """检查是否为交易日"""
        return self.live_system.is_trading_day(date)
    
    def validate_date_format(self, date_str: str) -> bool:
        """验证日期格式"""
        return self.live_system.validate_date_format(date_str)
    
    def should_run_sandbox_analysis(self, date: str, time_point: str, force_run: bool = False) -> bool:
        """判断是否应该运行sandbox分析（独立于live_system的检查逻辑）"""
        if force_run:
            return True
        
        # 检查sandbox日志中是否已有成功的记录
        existing_data = self._load_sandbox_log(date, time_point)
        if existing_data and existing_data.get('status') == 'success':
            return False
        
        return True
    
    def _run_sandbox_analysis(self, tickers: List[str], target_date: str, max_comm_cycles: int = 2) -> Dict[str, Any]:
        """运行sandbox专用的分析（绕过live_system的状态管理）"""
        print(f"\n开始Sandbox策略分析 - {target_date}")
        print(f"监控标的: {', '.join(tickers)}")
        
        try:
            # 1. 运行策略分析（直接调用核心分析方法，绕过should_run_today检查）
            analysis_result = self.live_system.run_single_day_analysis(tickers, target_date, max_comm_cycles)
       
            
            live_env = {
                'pm_signals': {},
                'ana_signals':{}, 
                'real_returns': {}
            }           
            pm_signals = analysis_result['signals']
            live_env['pm_signals'] = pm_signals
            
            # 初始化ana_signals字典
            live_env['ana_signals'] = {}
            for agent in ['sentiment_analyst', 'technical_analyst', 'fundamentals_analyst', 'valuation_analyst']:
                live_env['ana_signals'][agent] = {}
                for ticker in tickers:
                    # 尝试从分析结果中提取分析师信号
                    agent_results = analysis_result.get('raw_results', {}).get('results', {}).get('final_analyst_results', {})
                    live_env['ana_signals'][agent][ticker] = agent_results[agent]['analysis_result'][ticker]['signal']
                    
            self.live_system.save_daily_signals(target_date, pm_signals)

            print(f"已保存 {len(pm_signals)} 个股票的交易信号")

            # 3. 计算当日收益
            target_date = str(target_date)
            daily_returns = self.live_system.calculate_daily_returns(target_date, pm_signals)
            for ticker in tickers:
                # 使用daily_return而不是real_return
                live_env['real_returns'][ticker] = daily_returns[ticker]['real_return']
            # 4. 更新个股收益
            individual_data = self.live_system.update_individual_returns(target_date, daily_returns)
            
            # 5. 清理过期数据
            self.live_system.clean_old_data()
            
            # 注意：这里我们不调用 update_last_run_date，避免影响live_system的状态
            
            print(f"{target_date} Sandbox分析完成")
            
            # 显示各股票表现
            for ticker, data in daily_returns.items():
                daily_ret = data['daily_return'] * 100
                cum_ret = (individual_data[ticker][target_date]['cumulative_return'] - 1) * 100
                signal = data['signal']
                action = data['action']
                confidence = data['confidence']
                print(f"{ticker}: 日收益 {daily_ret:.2f}%, 累计收益 {cum_ret:.2f}%, "
                      f"信号 {signal}({action}, {confidence}%)")
            
            return {
                'status': 'success',
                'date': target_date,
                'signals': pm_signals,
                'individual_returns': daily_returns,
                'individual_cumulative': individual_data,
                'live_env': live_env
            }
            
        except Exception as e:
            print(f"Sandbox分析失败: {str(e)}")
            return {'status': 'failed', 'reason': str(e)}
    
    def run_pre_market_analysis(self, date: str, tickers: List[str], 
                               max_comm_cycles: int = 2, force_run: bool = False) -> Dict[str, Any]:
        """运行交易前分析（复用live_trading_system的逻辑）"""
        print(f"\n===== 交易前分析 ({date}) =====")
        print(f"时间点: {self.PRE_MARKET}")
        print(f"分析标的: {', '.join(tickers)}")
        
        try:
            # 使用sandbox专用的检查逻辑
            # if not self.should_run_sandbox_analysis(date, self.PRE_MARKET, force_run):
            #     print(f"📋 {date} 交易前分析已存在，跳过重复运行（使用 --force-run 强制重新运行）")
            #     existing_data = self._load_sandbox_log(date, self.PRE_MARKET)
            #     return existing_data
            
            # 运行sandbox专用的分析（绕过live_system的状态检查）
            result = self._run_sandbox_analysis(tickers, date, max_comm_cycles)
            
            # 记录到sandbox日志
            self._log_sandbox_activity(date, self.PRE_MARKET, {
                'status': result['status'],
                'tickers': tickers,
                'timestamp': datetime.now().isoformat(),
                'details': result
            })
            
            return result
            
        except Exception as e:
            error_result = {
                'status': 'failed',
                'reason': f'交易前分析失败: {str(e)}',
                'timestamp': datetime.now().isoformat()
            }
            
            self._log_sandbox_activity(date, self.PRE_MARKET, error_result)
            return error_result
    
    def run_post_market_review(self, date: str, tickers: List[str], live_env: Dict[str, Any]) -> Dict[str, Any]:
        """运行交易后复盘"""
        print(f"\n===== 交易后复盘 ({date}) =====")
        print(f"时间点: {self.POST_MARKET}")
        print(f"复盘标的: {', '.join(tickers)}")
        if live_env != 'Not trading day':
        
            # 交易后复盘逻辑
            result = self._perform_post_market_review(date, tickers,live_env)
            
            # 记录到sandbox日志
            self._log_sandbox_activity(date, self.POST_MARKET, result)
            
            return result
         
    
    def _perform_post_market_review(self, date: str, tickers: List[str],live_env: Dict[str, Any]) -> Dict[str, Any]:
        """执行交易后复盘分析"""
    
        # 有交易前数据，进行对比分析
        print("基于交易前分析进行复盘...")
        
        pm_signals = live_env['pm_signals']
        ana_signals = live_env['ana_signals']
        real_returns = live_env['real_returns']
        
        print(f"\n交易前信号回顾:")
        for ticker in tickers:
            if ticker in pm_signals:
                signal_info = pm_signals[ticker]
                print(f"   {ticker}: {signal_info.get('signal', 'N/A')} "
                      f"({signal_info.get('action', 'N/A')}, "
                      f"置信度: {signal_info.get('confidence', 'N/A')}%)")
            else:
                print(f"   {ticker}: 无信号数据")
        
        print(f"\n实际收益表现:")
        for ticker in tickers:
            if ticker in real_returns:
                daily_ret = real_returns[ticker] * 100
                print(f"   {ticker}: {daily_ret:.2f}% "
                      f"(信号: {pm_signals.get(ticker, {}).get('signal', 'N/A')})")
            else:
                print(f"   {ticker}: 无收益数据")
        
        print(f"\n分析师信号对比:")
        for agent, agent_signals in ana_signals.items():
            print(f"  {agent}:")
            for ticker in tickers:
                signal = agent_signals.get(ticker, 'N/A')
                print(f"    {ticker}: {signal}")
        
        # 生成复盘报告
        review_summary = self._generate_review_summary(pm_signals, real_returns, tickers)
        
        return {
            'status': 'success',
            'type': 'full_review',
            'review_summary': review_summary,
            'pre_market_signals': pm_signals,
            'analyst_signals': ana_signals,
            'actual_returns': real_returns,
            'timestamp': datetime.now().isoformat()
        } 
    
    def _generate_review_summary(self, signals: Dict, returns: Dict, tickers: List[str]) -> Dict[str, Any]:
        """生成复盘总结"""
        summary = {
            'total_tickers': len(tickers),
            'successful_signals': 0,
            'failed_signals': 0,
            'neutral_signals': 0,
            'average_return': 0.0,
            'best_performer': None,
            'worst_performer': None,
            'signal_accuracy': 0.0
        }
        
        valid_returns = []
        signal_performance = []
        
        for ticker in tickers:
            if ticker in signals and ticker in returns:
                signal = signals[ticker].get('signal', 'neutral')
                actual_return = returns[ticker].get('daily_return', 0)
                valid_returns.append(actual_return)
                
                # 判断信号准确性
                if signal == 'bullish' and actual_return > 0:
                    summary['successful_signals'] += 1
                    signal_performance.append(1)
                elif signal == 'bearish' and actual_return < 0:
                    summary['successful_signals'] += 1
                    signal_performance.append(1)
                elif signal == 'neutral':
                    summary['neutral_signals'] += 1
                    signal_performance.append(0.5)
                else:
                    summary['failed_signals'] += 1
                    signal_performance.append(0)
        
        if valid_returns:
            summary['average_return'] = sum(valid_returns) / len(valid_returns)
            
            # 找出表现最好和最差的股票
            ticker_returns = [(ticker, returns[ticker].get('daily_return', 0)) 
                             for ticker in tickers if ticker in returns]
            
            if ticker_returns:
                ticker_returns.sort(key=lambda x: x[1], reverse=True)
                summary['best_performer'] = {
                    'ticker': ticker_returns[0][0],
                    'return': ticker_returns[0][1]
                }
                summary['worst_performer'] = {
                    'ticker': ticker_returns[-1][0],
                    'return': ticker_returns[-1][1]
                }
        
        if signal_performance:
            summary['signal_accuracy'] = sum(signal_performance) / len(signal_performance)
        
        return summary
    
    def _show_post_market_placeholder(self, date: str, tickers: List[str]):
        """显示交易后占位符信息"""
        print(f"交易后总结 - {date}")
        print("━" * 50)
        print(f"监控标的: {', '.join(tickers)}")
        print(f"复盘时间: {datetime.now().strftime('%H:%M:%S')}")
        print(f"市场状态: 交易日结束")
        print(f"复盘内容: 等待明日交易前分析...")
        print("━" * 50)
        print("下一步: 等待下一个交易日的交易前分析")
    
    def run_full_day_simulation(self, date: str, tickers: List[str], 
                               max_comm_cycles: int = 2, force_run: bool = False) -> Dict[str, Any]:
        """运行完整的一天模拟（交易前 + 交易后）"""
        print(f"\n===== 开始 {date} 完整交易日模拟 =====")
        
        results = {
            'date': date,
            'is_trading_day': self.is_trading_day(date),
            'pre_market': None,
            'post_market': None,
            'summary': {}
        }
        
        if results['is_trading_day']:
            print(f"{date} 是交易日，将执行：交易前分析 + 交易后复盘")
            
            # 1. 交易前分析
            results['pre_market'] = self.run_pre_market_analysis(
                date, tickers, max_comm_cycles, force_run
            )
            
            print(f"\n等待交易后时间点...")
            print(f"(实际使用中，这里会等待真实的市场收盘)")
            
            # 2. 交易后复盘
            # 安全地获取live_env，如果pre_market失败则为None
            live_env = results['pre_market'].get('live_env') if results['pre_market'] else None
            results['post_market'] = self.run_post_market_review(date, tickers, live_env)
            
        else:
            print(f"{date} 非交易日，仅执行：交易后总结")
            
            # 非交易日只执行交易后
            results['post_market'] = self.run_post_market_review(date, tickers,'Not trading day')
        
        # 生成日总结
        results['summary'] = self._generate_day_summary(results)
        
        print(f"\n{date} 完整模拟结束")
        self._print_day_summary(results['summary'])
        
        return results
    
    def _generate_day_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """生成日总结"""
        summary = {
            'date': results['date'],
            'is_trading_day': results['is_trading_day'],
            'activities_completed': [],
            'overall_status': 'success'
        }
        
        if results['pre_market']:
            summary['activities_completed'].append('交易前分析')
            if results['pre_market']['status'] != 'success':
                summary['overall_status'] = 'partial_success'
        
        if results['post_market']:
            summary['activities_completed'].append('交易后复盘')
            if results['post_market']['status'] != 'success':
                summary['overall_status'] = 'partial_success'
        
        return summary
    
    def _print_day_summary(self, summary: Dict[str, Any]):
        """打印日总结"""
        print(f"\n===== {summary['date']} 日总结 =====")
        print(f"交易日状态: {'是' if summary['is_trading_day'] else '否'}")
        print(f"完成活动: {', '.join(summary['activities_completed'])}")
        print(f"总体状态: {summary['overall_status']}")
        print("=" * 40)
    
    def _log_sandbox_activity(self, date: str, time_point: str, data: Dict[str, Any]):
        """记录sandbox活动日志"""
        log_file = self.sandbox_dir / f"sandbox_day_{date.replace('-', '_')}.json"
        
        # 加载现有日志
        if log_file.exists():
            import json
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    log_data = json.load(f)
            except:
                log_data = {}
        else:
            log_data = {}
        
        # 添加新活动
        log_data[time_point] = data
        log_data['last_updated'] = datetime.now().isoformat()
        
        # 保存日志
        import json
        try:
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            print(f"保存sandbox日志失败: {e}")
    
    def _load_sandbox_log(self, date: str, time_point: str) -> Dict[str, Any]:
        """加载sandbox活动日志"""
        log_file = self.sandbox_dir / f"sandbox_day_{date.replace('-', '_')}.json"
        
        if not log_file.exists():
            return {}
        
        import json
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                log_data = json.load(f)
            return log_data.get(time_point, {})
        except Exception as e:
            print(f"加载sandbox日志失败: {e}")
            return {}


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="Live交易思考基金 - 时间Sandbox系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 运行指定日期的完整模拟
  python live_trading_thinking_fund.py --date 2025-01-15 --tickers AAPL,MSFT
  
  # 使用环境变量中的股票配置
  python live_trading_thinking_fund.py --date 2025-01-15
  
  # 强制运行（忽略各种检查）
  python live_trading_thinking_fund.py --date 2025-01-15 --force-run
  
  # 自定义沟通轮数
  python live_trading_thinking_fund.py --date 2025-01-15 --max-comm-cycles 3
        """
    )
    
    # 必需参数
    parser.add_argument(
        '--date',
        type=str,
        required=True,
        help='指定模拟日期 (YYYY-MM-DD格式)'
    )
    
    # 可选参数
    parser.add_argument(
        '--tickers',
        type=str,
        help='股票代码列表，用逗号分隔 (可选，使用环境变量配置)'
    )
    
    parser.add_argument(
        '--max-comm-cycles',
        type=int,
        default=2,
        help='最大沟通轮数 (默认: 2)'
    )
    
    parser.add_argument(
        '--force-run',
        action='store_true',
        help='强制运行，忽略各种检查'
    )
    
    parser.add_argument(
        '--base-dir',
        type=str,
        help='基础目录'
    )
    
    args = parser.parse_args()
    
    try:
        # 加载配置
        config = LiveTradingConfig()
        config.override_with_args(args)
        
        # 验证日期格式
        thinking_fund = LiveTradingThinkingFund(base_dir=args.base_dir)
        
        if not thinking_fund.validate_date_format(args.date):
            print(f"错误: 日期格式无效: {args.date} (需要 YYYY-MM-DD)")
            sys.exit(1)
        
        # 检查日期不能是未来
        target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
        today = datetime.now().date()
        
        if target_date > today:
            print(f"错误: 不能模拟未来日期: {args.date}")
            sys.exit(1)
        
        # 确定股票代码
        if args.tickers:
            tickers = [ticker.strip().upper() for ticker in args.tickers.split(",") if ticker.strip()]
        elif config.tickers:
            tickers = config.tickers
        else:
            print("错误: 请通过 --tickers 参数或环境变量 TICKERS 提供股票代码")
            sys.exit(1)
        
        if not tickers:
            print("错误: 请提供至少一个有效的股票代码")
            sys.exit(1)
        
        print(f"时间Sandbox模拟设置:")
        print(f"   目标日期: {args.date}")
        print(f"   模拟标的: {', '.join(tickers)}")
        print(f"   沟通轮数: {args.max_comm_cycles}")
        print(f"   强制运行: {'是' if args.force_run else '否'}")
        
        # 运行完整日模拟
        results = thinking_fund.run_full_day_simulation(
            date=args.date,
            tickers=tickers,
            max_comm_cycles=args.max_comm_cycles,
            force_run=args.force_run
        )
        
        print(f"\n{args.date} 时间Sandbox模拟完成!")
        
    except KeyboardInterrupt:
        print("\n用户中断模拟")
        sys.exit(1)
    except Exception as e:
        print(f"\n模拟过程中出现错误: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
