#!/usr/bin/env python3
"""
Live交易策略监控系统 - 统一版本
集成数据收集、增量更新、绩效分析和可视化功能

使用方法:
# 使用命令行参数
python live_trading_system.py update --tickers AAPL,MSFT
python live_trading_system.py report --tickers AAPL,MSFT

# 使用环境变量配置文件（创建 .env 文件后）
python live_trading_system.py update
python live_trading_system.py report

"""

import os
import sys
import json
import argparse
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib import rcParams
import seaborn as sns
import pdb

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from advanced_investment_engine import AdvancedInvestmentAnalysisEngine
from src.scheduler.multi_day_manager import MultiDayManager
from src.config.env_config import LiveTradingConfig

# 尝试导入美国交易日历包（与主程序保持一致）
try:
    import pandas_market_calendars as mcal
    US_TRADING_CALENDAR_AVAILABLE = True
except ImportError:
    try:
        import exchange_calendars as xcals
        US_TRADING_CALENDAR_AVAILABLE = True
    except ImportError:
        US_TRADING_CALENDAR_AVAILABLE = False

# 设置绘图样式
rcParams['axes.unicode_minus'] = False
plt.style.use('seaborn-v0_8')
sns.set_palette("husl")


class LiveTradingSystem:
    """Live交易策略监控系统 - 统一版本"""
    
    def __init__(self, base_dir: str = None):
        """初始化Live交易系统"""
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).parent
        self.live_dir = self.base_dir / "live_trading"
        self.data_dir = self.live_dir / "data"
        self.reports_dir = self.live_dir / "reports"
        self.charts_dir = self.reports_dir / "charts"
        self.config_dir = self.live_dir / "config"
        
        # 创建必要的目录
        self._create_directories()
        
        # 数据文件路径
        self.daily_signals_file = self.data_dir / "daily_signals.json"
        self.cumulative_returns_file = self.data_dir / "cumulative_returns.json"
        self.performance_metrics_file = self.data_dir / "performance_metrics.json"
        self.config_file = self.config_dir / "live_config.json"
        
        # 初始化分析引擎
        self.engine = AdvancedInvestmentAnalysisEngine()
    
    def validate_date_format(self, date_str: str) -> bool:
        """验证日期格式是否正确"""
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            return True
        except ValueError:
            return False
    
    def get_data_start_date(self) -> Optional[str]:
        """获取现有数据的最早日期"""
        daily_signals = self._load_json_file(self.daily_signals_file, {})
        if daily_signals:
            return min(daily_signals.keys())
        return None
        
    def _create_directories(self):
        """创建必要的目录结构"""
        directories = [
            self.live_dir,
            self.data_dir,
            self.reports_dir,
            self.charts_dir,
            self.config_dir
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            
    def _load_json_file(self, file_path: Path, default: dict = None) -> dict:
        """加载JSON文件"""
        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️ 加载文件失败 {file_path}: {e}")
                return default or {}
        return default or {}
    
    def _save_json_file(self, file_path: Path, data: dict):
        """保存JSON文件"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            print(f"❌ 保存文件失败 {file_path}: {e}")
            raise
    
    # ==================== 数据管理部分 ====================
    
    def get_last_run_date(self) -> Optional[str]:
        """获取上次运行日期"""
        config = self._load_json_file(self.config_file)
        return config.get('last_run_date')
    
    def update_last_run_date(self, date: str):
        """更新最后运行日期"""
        config = self._load_json_file(self.config_file)
        config['last_run_date'] = date
        config['last_update_time'] = datetime.now().isoformat()
        self._save_json_file(self.config_file, config)
    
    def is_trading_day(self, date: str) -> bool:
        """检查是否为交易日（与主程序保持一致）"""
        if US_TRADING_CALENDAR_AVAILABLE:
            try:
                # 优先尝试使用 pandas_market_calendars
                if 'mcal' in globals():
                    nyse = mcal.get_calendar('NYSE')
                    trading_dates = nyse.valid_days(start_date=date, end_date=date)
                    return len(trading_dates) > 0
                
                # 备选：使用 exchange_calendars
                elif 'xcals' in globals():
                    nyse = xcals.get_calendar('XNYS')  # NYSE的ISO代码
                    trading_dates = nyse.sessions_in_range(date, date)
                    return len(trading_dates) > 0
                    
            except Exception as e:
                print(f"⚠️ 美国交易日历检查失败，回退到简单方法: {e}")
        
        
    
    def should_run_today(self, target_date: str = None, force_run: bool = False) -> bool:
        """判断是否应该运行"""
        if force_run:
            return True
            
        target_date = target_date or datetime.now().strftime("%Y-%m-%d")
        
        if not self.is_trading_day(target_date):
            print(f"📅 {target_date} 不是交易日，跳过运行")
            return False
        
        last_run_date = self.get_last_run_date()
        if last_run_date and last_run_date >= target_date:
            print(f"✅ {target_date} 已经运行过，跳过运行")
            return False
            
        return True
    
    def clean_old_data(self, cutoff_date: str = None):
        """清理过期数据（可选，保留从2025-01-01开始的所有数据）"""
        if cutoff_date is None:
            # 默认保留从2025-01-01开始的所有数据，不清理
            return
        
        files_to_clean = [self.daily_signals_file, self.cumulative_returns_file]
        
        cleaned_count = 0
        for file_path in files_to_clean:
            if file_path.exists():
                data = self._load_json_file(file_path)
                if isinstance(data, dict):
                    if file_path == self.cumulative_returns_file and 'individual' in data:
                        for ticker in data['individual']:
                            keys_to_remove = [k for k in data['individual'][ticker].keys() if k < cutoff_date]
                            for key in keys_to_remove:
                                data['individual'][ticker].pop(key, None)
                                cleaned_count += 1
                    else:
                        keys_to_remove = [k for k in data.keys() if k < cutoff_date]
                        for key in keys_to_remove:
                            data.pop(key, None)
                            cleaned_count += 1
                    
                    if cleaned_count > 0:
                        self._save_json_file(file_path, data)
        
        if cleaned_count > 0:
            print(f"🧹 已清理 {cutoff_date} 之前的 {cleaned_count} 条历史数据")
        else:
            print("📊 保留所有历史数据，无需清理")
    
    # ==================== 策略分析部分 ====================
    
    def run_single_day_analysis(self, tickers: List[str], date: str, max_comm_cycles: int = 2) -> dict:
        """运行单日策略分析"""
        print(f"🔍 开始分析 {date} 的策略...")
        
        try:
            # 创建包含策略日期的自定义session_id
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            custom_session_id = f"live_strategy_{date}_{timestamp}"
            
            multi_day_manager = MultiDayManager(
                engine=self.engine,
                base_output_dir=str(self.reports_dir / "temp"),
                max_communication_cycles=max_comm_cycles,
                prefetch_data=True,
                okr_enabled=False,
                custom_session_id=custom_session_id
            )
            
            results = multi_day_manager.run_multi_day_strategy(
                tickers=tickers,
                start_date=date,
                end_date=date,
                enable_communications=False,
                enable_notifications=False,
                show_reasoning=False,
                progress_callback=None
            )
            
            if results and results['period']['successful_days'] > 0:
                daily_result = results['daily_results'][0]
                return {
                    'status': 'success',
                    'date': date,
                    'signals': self._extract_signals(daily_result),
                    'raw_results': daily_result
                }
            else:
                return {'status': 'failed', 'date': date, 'error': '分析失败'}
                
        except Exception as e:
            print(f"❌ {date} 分析失败: {str(e)}")
            return {'status': 'failed', 'date': date, 'error': str(e)}
    
    def _extract_signals(self, daily_result: dict) -> dict:
        """从分析结果中提取交易信号"""
        signals = {}
        
        # 优先使用最终决策
        final_decisions = daily_result['results']['portfolio_management_results']['final_decisions']
        if final_decisions:
            for ticker, decision in final_decisions.items():
                action = decision['action']
                confidence = decision['confidence']
                
                # 转换action到signal
                if action == 'long':
                    signal = 'bullish'
                elif action == 'short':
                    signal = 'bearish'
                else:
                    signal = 'neutral'
                
                signals[ticker] = {
                    'signal': signal,
                    'confidence': confidence,
                    'action': action,
                    'reasoning': decision['reasoning']
                }
            
                           
        return signals
    
    def calculate_daily_returns(self, date: str, signals: dict) -> dict:
        """计算当日收益率"""
        returns = {}
        
        # 创建包含策略日期的自定义session_id（用于收益率计算）
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        custom_session_id = f"live_returns_{date}_{timestamp}"
        
        multi_day_manager = MultiDayManager(
            engine=self.engine,
            base_output_dir=str(self.reports_dir / "temp"),
            custom_session_id=custom_session_id
        )
        
        for ticker, signal_data in signals.items():
            # 根据信号确定交易方向
            signal = signal_data['signal'] 
            action = signal_data['action']
            
            if action == 'long' or signal == 'bullish':
                trade_action = "long"
            elif action == 'short' or signal == 'bearish':
                trade_action = "short"
            else:
                trade_action = "long"  # 默认做多
            
            # 计算收益率
            daily_return = multi_day_manager._calculate_stock_daily_return_from_signal(
                ticker, date, trade_action
            )
        
            returns[ticker] = {
                'daily_return': daily_return,
                'signal': signal,
                'action': action,
                'confidence': signal_data['confidence']
            }
            

        
        return returns
    
    def update_individual_returns(self, date: str, daily_returns: dict):
        """更新个股收益数据"""
        cum_returns = self._load_json_file(self.cumulative_returns_file, {'individual': {}})
        
        for ticker, data in daily_returns.items():
            if ticker not in cum_returns['individual']:
                cum_returns['individual'][ticker] = {}
            
            # 获取历史累计收益
            ticker_dates = sorted(cum_returns['individual'][ticker].keys())
            last_cum_return = 1.0
            if ticker_dates:
                last_date = ticker_dates[-1]
                last_cum_return = cum_returns['individual'][ticker][last_date].get('cumulative_return', 1.0)
            
            # 计算新的累计收益
            daily_return = data['daily_return']
            new_cum_return = last_cum_return * (1 + daily_return)
            
            cum_returns['individual'][ticker][date] = {
                'daily_return': daily_return,
                'cumulative_return': new_cum_return,
                'signal': data['signal'],
                'action': data['action'],
                'confidence': data['confidence']
            }
        
        self._save_json_file(self.cumulative_returns_file, cum_returns)
        return cum_returns['individual']
    
    def save_daily_signals(self, date: str, signals: dict):
        """保存每日交易信号"""
        daily_signals = self._load_json_file(self.daily_signals_file)
        daily_signals[date] = signals
        self._save_json_file(self.daily_signals_file, daily_signals)
    
    # ==================== 绩效分析部分 ====================
    
    def calculate_individual_stock_metrics(self, individual_data: Dict) -> Dict:
        """计算个股绩效指标"""
        stock_metrics = {}
        
        for ticker, ticker_data in individual_data.items():
            if not ticker_data:
                continue
                
            dates = sorted(ticker_data.keys())
            returns = [ticker_data[date]['daily_return'] for date in dates]
            cumulative_values = [ticker_data[date]['cumulative_return'] for date in dates]
            
            # 基础指标
            total_return = (cumulative_values[-1] - 1) * 100 if cumulative_values else 0
            volatility = np.std(returns) * np.sqrt(252) * 100 if len(returns) > 1 else 0
            
            # 年化收益率
            trading_days = len(returns)
            if trading_days > 0 and cumulative_values:
                annualized_return = (cumulative_values[-1] ** (252 / trading_days) - 1) * 100
            else:
                annualized_return = 0
            
            # 夏普比率
            risk_free_rate = 0.02 / 252
            excess_returns = np.array(returns) - risk_free_rate
            sharpe = (np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)) if np.std(excess_returns) > 0 else 0
            
            # 最大回撤
            cumulative_max = np.maximum.accumulate(cumulative_values)
            drawdowns = (np.array(cumulative_values) - cumulative_max) / cumulative_max
            max_drawdown = np.min(drawdowns) * 100 if len(drawdowns) > 0 else 0
            
            # 胜率和盈亏比
            positive_days = np.sum(np.array(returns) > 0)
            win_rate = (positive_days / len(returns) * 100) if len(returns) > 0 else 0
            
            positive_returns = [r for r in returns if r > 0]
            negative_returns = [r for r in returns if r < 0]
            avg_win = np.mean(positive_returns) if positive_returns else 0
            avg_loss = np.mean(negative_returns) if negative_returns else 0
            profit_loss_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0
            
            # Calmar比率
            calmar_ratio = annualized_return / abs(max_drawdown) if max_drawdown != 0 else 0
            
            stock_metrics[ticker] = {
                'total_return_pct': round(total_return, 2),
                'annualized_return_pct': round(annualized_return, 2),
                'volatility_pct': round(volatility, 2),
                'sharpe_ratio': round(sharpe, 3),
                'max_drawdown_pct': round(max_drawdown, 2),
                'win_rate_pct': round(win_rate, 2),
                'profit_loss_ratio': round(profit_loss_ratio, 3),
                'calmar_ratio': round(calmar_ratio, 3),
                'trading_days': trading_days,
                'positive_days': int(positive_days),
                'negative_days': int(trading_days - positive_days),
                'avg_win_pct': round(avg_win * 100, 4),
                'avg_loss_pct': round(avg_loss * 100, 4),
                'start_date': dates[0] if dates else None,
                'end_date': dates[-1] if dates else None,
                'current_value': round(cumulative_values[-1], 4) if cumulative_values else 1.0
            }
        
        return stock_metrics
    
    # ==================== 可视化部分 ====================
    
    def create_individual_return_chart(self, ticker: str, ticker_data: Dict) -> str:
        """创建个股收益图表"""
        try:
            dates = sorted(ticker_data.keys())
            cumulative_returns = [ticker_data[date]['cumulative_return'] for date in dates]
            daily_returns = [ticker_data[date]['daily_return'] for date in dates]
            
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
            
            # 上图: 累计收益曲线
            dates_dt = pd.to_datetime(dates)
            cumulative_pct = [(cr - 1) * 100 for cr in cumulative_returns]
            
            ax1.plot(dates_dt, cumulative_pct, linewidth=2, color='#2E86C1', label=f'{ticker} Cumulative Return')
            ax1.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
            ax1.set_title(f'{ticker} - Cumulative Return Chart', fontsize=14, fontweight='bold')
            ax1.set_ylabel('Cumulative Return (%)', fontsize=12)
            ax1.legend()
            ax1.grid(True, alpha=0.3)
            
            # 添加收益标注
            final_return = cumulative_pct[-1] if cumulative_pct else 0
            ax1.text(0.02, 0.98, f'Total Return: {final_return:.2f}%', 
                    transform=ax1.transAxes, fontsize=12, 
                    bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8),
                    verticalalignment='top')
            
            # 下图: 日收益率
            daily_pct = [dr * 100 for dr in daily_returns]
            colors = ['green' if dr > 0 else 'red' for dr in daily_returns]
            ax2.bar(dates_dt, daily_pct, color=colors, alpha=0.7, width=0.8)
            ax2.axhline(y=0, color='gray', linestyle='-', alpha=0.8)
            ax2.set_title(f'{ticker} - Daily Return', fontsize=14, fontweight='bold')
            ax2.set_xlabel('Date', fontsize=12)
            ax2.set_ylabel('Daily Return (%)', fontsize=12)
            ax2.grid(True, alpha=0.3)
            
            # 格式化x轴
            for ax in [ax1, ax2]:
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
                plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
            
            plt.tight_layout()
            
            chart_path = self.charts_dir / f"{ticker}_returns_{datetime.now().strftime('%Y%m%d')}.png"
            plt.savefig(chart_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            return str(chart_path)
            
        except Exception as e:
            print(f"⚠️ 生成{ticker}收益图表失败: {e}")
            return None
    
    def create_stocks_comparison_chart(self, individual_data: Dict) -> str:
        """创建股票对比图"""
        try:
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
            
            colors = plt.cm.Set1(np.linspace(0, 1, len(individual_data)))
            
            for i, (ticker, ticker_data) in enumerate(individual_data.items()):
                if not ticker_data:
                    continue
                    
                dates = pd.to_datetime(sorted(ticker_data.keys()))
                cumulative = [ticker_data[date.strftime('%Y-%m-%d')]['cumulative_return'] for date in dates]
                cumulative_pct = [(cr - 1) * 100 for cr in cumulative]
                
                ax1.plot(dates, cumulative_pct, linewidth=2, color=colors[i], 
                        label=f'{ticker}', marker='o', markersize=3)
            
            ax1.set_title('Stocks Cumulative Return Comparison', fontsize=14, fontweight='bold')
            ax1.set_ylabel('Cumulative Return (%)', fontsize=12)
            ax1.legend()
            ax1.grid(True, alpha=0.3)
            ax1.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
            
            # 下图: 日收益率对比
            for i, (ticker, ticker_data) in enumerate(individual_data.items()):
                if not ticker_data:
                    continue
                    
                dates = pd.to_datetime(sorted(ticker_data.keys()))
                daily_returns = [ticker_data[date.strftime('%Y-%m-%d')]['daily_return'] * 100 for date in dates]
                
                ax2.plot(dates, daily_returns, linewidth=1, color=colors[i], 
                        label=f'{ticker}', alpha=0.7)
            
            ax2.set_title('Stocks Daily Return Comparison', fontsize=14, fontweight='bold')
            ax2.set_xlabel('Date', fontsize=12)
            ax2.set_ylabel('Daily Return (%)', fontsize=12)
            ax2.legend()
            ax2.grid(True, alpha=0.3)
            ax2.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
            
            # 格式化x轴
            for ax in [ax1, ax2]:
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
                plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
            
            plt.tight_layout()
            
            chart_path = self.charts_dir / f"stocks_comparison_{datetime.now().strftime('%Y%m%d')}.png"
            plt.savefig(chart_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            return str(chart_path)
            
        except Exception as e:
            print(f"⚠️ 生成股票对比图失败: {e}")
            return None
    
    # ==================== 主要功能接口 ====================
    
    def get_missing_dates(self, tickers: List[str], start_date: str = "2025-01-01") -> List[str]:
        """检测缺少哪些交易日的数据"""
        # 获取已有的数据
        daily_signals = self._load_json_file(self.daily_signals_file, {})
        
        # 获取从start_date到今天的所有交易日
        end_date = datetime.now().strftime("%Y-%m-%d")
        all_trading_dates = []
        
        if US_TRADING_CALENDAR_AVAILABLE:
            try:
                if 'mcal' in globals():
                    nyse = mcal.get_calendar('NYSE')
                    trading_dates = nyse.valid_days(start_date=start_date, end_date=end_date)
                    all_trading_dates = [date.strftime('%Y-%m-%d') for date in trading_dates]
                elif 'xcals' in globals():
                    nyse = xcals.get_calendar('XNYS')
                    trading_dates = nyse.sessions_in_range(start_date, end_date)
                    all_trading_dates = [date.strftime('%Y-%m-%d') for date in trading_dates]
            except Exception as e:
                print(f"⚠️ 获取交易日历失败，使用简单方法: {e}")
        
        # 如果无法获取交易日历，使用简单方法
        if not all_trading_dates:
            current_date = datetime.strptime(start_date, "%Y-%m-%d")
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
            
            while current_date <= end_date_obj:
                date_str = current_date.strftime("%Y-%m-%d")
                if self.is_trading_day(date_str):
                    all_trading_dates.append(date_str)
                current_date += timedelta(days=1)
        
        # 找出缺失的日期
        existing_dates = set(daily_signals.keys())
        missing_dates = [date for date in all_trading_dates if date not in existing_dates]
        
        return sorted(missing_dates)
    
    def backfill_historical_data(self, tickers: List[str], start_date: str = "2025-01-01", 
                                max_comm_cycles: int = 1) -> dict:
        """回填历史数据"""
        print(f"\n🔄 开始回填历史数据 ({start_date} 至今)")
        print(f"📊 监控标的: {', '.join(tickers)}")
        
        # 检测缺失的日期
        missing_dates = self.get_missing_dates(tickers, start_date)
        
        if not missing_dates:
            print("✅ 所有历史数据已完整，无需回填")
            return {'status': 'completed', 'processed_dates': [], 'failed_dates': []}
        
        print(f"📅 发现 {len(missing_dates)} 个缺失的交易日")
        print(f"缺失日期: {missing_dates[:5]}{'...' if len(missing_dates) > 5 else ''}")
        
        processed_dates = []
        failed_dates = []
        
        # 逐日处理
        for i, date in enumerate(missing_dates):
            print(f"\n📈 处理第 {i+1}/{len(missing_dates)} 天: {date}")
            
            try:
                result = self.daily_update(
                    tickers=tickers,
                    target_date=date,
                    max_comm_cycles=max_comm_cycles,
                    force_run=True
                )
                
                if result['status'] == 'success':
                    processed_dates.append(date)
                    print(f"✅ {date} 处理成功")
                else:
                    failed_dates.append(date)
                    print(f"❌ {date} 处理失败: {result.get('reason', '未知错误')}")
                    
            except Exception as e:
                failed_dates.append(date)
                print(f"❌ {date} 处理异常: {str(e)}")
        
        print(f"\n📊 回填完成统计:")
        print(f"   成功处理: {len(processed_dates)} 天")
        print(f"   失败处理: {len(failed_dates)} 天")
        print(f"   成功率: {len(processed_dates)/(len(processed_dates)+len(failed_dates))*100:.1f}%")
        
        return {
            'status': 'completed',
            'processed_dates': processed_dates,
            'failed_dates': failed_dates,
            'success_rate': len(processed_dates)/(len(processed_dates)+len(failed_dates))*100 if (len(processed_dates)+len(failed_dates)) > 0 else 0
        }
    
    def daily_update(self, tickers: List[str], target_date: str = None, 
                    max_comm_cycles: int = 2, force_run: bool = False) -> dict:
        """执行每日更新"""
        target_date = target_date or datetime.now().strftime("%Y-%m-%d")
        
        print(f"\n🚀 开始Live交易策略更新 - {target_date}")
        print(f"📊 监控标的: {', '.join(tickers)}")
        
        if not self.should_run_today(target_date, force_run):
            return {'status': 'skipped', 'reason': '无需运行'}
        
        try:
            # 1. 运行策略分析
            analysis_result = self.run_single_day_analysis(tickers, target_date, max_comm_cycles)
            
            if analysis_result['status'] != 'success':
                return {'status': 'failed', 'reason': '策略分析失败', 'details': analysis_result}
            
            # 2. 保存交易信号
            signals = analysis_result['signals']
            self.save_daily_signals(target_date, signals)
            print(f"✅ 已保存 {len(signals)} 个股票的交易信号")

            # 3. 计算当日收益
            target_date = str(target_date)
            daily_returns = self.calculate_daily_returns(target_date, signals)
            
            # 4. 更新个股收益
            individual_data = self.update_individual_returns(target_date, daily_returns)
            
            # 5. 清理过期数据
            self.clean_old_data()
            
            # 6. 更新运行状态
            self.update_last_run_date(target_date)
            
            print(f"✅ {target_date} 更新完成")
            
            # 显示各股票表现
            for ticker, data in daily_returns.items():
                daily_ret = data['daily_return'] * 100
                cum_ret = (individual_data[ticker][target_date]['cumulative_return'] - 1) * 100
                signal = data['signal']
                action = data['action']
                confidence = data['confidence']
                print(f"📊 {ticker}: 日收益 {daily_ret:.2f}%, 累计收益 {cum_ret:.2f}%, "
                      f"信号 {signal}({action}, {confidence}%)")
            
            return {
                'status': 'success',
                'date': target_date,
                'signals': signals,
                'individual_returns': daily_returns,
                'individual_cumulative': individual_data
            }
            
        except Exception as e:
            print(f"❌ 更新失败: {str(e)}")
            return {'status': 'failed', 'reason': str(e)}
    
    def generate_report(self, tickers: List[str] = None) -> dict:
        """生成绩效报告"""
        print("📊 开始生成绩效报告...")
        
        # 加载数据
        returns_data = self._load_json_file(self.cumulative_returns_file, {'individual': {}})
        signals_data = self._load_json_file(self.daily_signals_file, {})
        
        individual_data = returns_data.get('individual', {})
        
        # 如果指定了tickers，只分析这些股票
        if tickers:
            individual_data = {ticker: data for ticker, data in individual_data.items() 
                             if ticker in tickers}
        
        if not individual_data:
            return {'error': '没有可用的个股数据'}
        
        # 计算绩效指标
        stock_metrics = self.calculate_individual_stock_metrics(individual_data)
        
        # 生成图表
        chart_files = []
        for ticker in individual_data.keys():
            if individual_data[ticker]:
                chart_file = self.create_individual_return_chart(ticker, individual_data[ticker])
                if chart_file:
                    chart_files.append(chart_file)
        
        # 生成对比图
        comparison_chart = self.create_stocks_comparison_chart(individual_data)
        if comparison_chart:
            chart_files.append(comparison_chart)
        
        # 组合报告
        report = {
            'report_date': datetime.now().isoformat(),
            'overview': {
                'monitored_stocks': list(individual_data.keys()),
                'total_stocks': len(individual_data),
                'start_date': min([min(data.keys()) for data in individual_data.values() if data]) if individual_data else None,
                'end_date': max([max(data.keys()) for data in individual_data.values() if data]) if individual_data else None,
            },
            'individual_metrics': stock_metrics,
            'chart_files': chart_files,
        }
        
        # 保存报告
        self._save_json_file(self.performance_metrics_file, report)
        
        print("✅ 绩效报告生成完成")
        return report
    
    def print_performance_summary(self, report: Dict):
        """打印绩效摘要"""
        if 'error' in report:
            print(f"❌ {report['error']}")
            return
        
        print("\n" + "="*80)
        print("📈 LIVE交易策略 - 个股绩效摘要")
        print("="*80)
        
        # 基础信息
        overview = report.get('overview', {})
        print(f"📅 监控期间: {overview.get('start_date', 'N/A')} ~ {overview.get('end_date', 'N/A')}")
        print(f"📊 监控股票: {', '.join(overview.get('monitored_stocks', []))}")
        print(f"🔢 股票数量: {overview.get('total_stocks', 0)} 只")
        
        # 个股详细表现
        individual_metrics = report.get('individual_metrics', {})
        if individual_metrics:
            print(f"\n🏢 个股详细表现:")
            print("-" * 80)
            
            # 表头
            print(f"{'股票':<8} {'总收益%':<10} {'年化%':<10} {'胜率%':<8} {'夏普':<8} {'回撤%':<10} {'盈亏比':<8} {'交易天数':<10}")
            print("-" * 80)
            
            # 按总收益排序
            sorted_stocks = sorted(individual_metrics.items(), 
                                 key=lambda x: x[1].get('total_return_pct', 0), reverse=True)
            
            for ticker, stock_metrics in sorted_stocks:
                total_ret = stock_metrics.get('total_return_pct', 0)
                annual_ret = stock_metrics.get('annualized_return_pct', 0)
                win_rate = stock_metrics.get('win_rate_pct', 0)
                sharpe = stock_metrics.get('sharpe_ratio', 0)
                drawdown = stock_metrics.get('max_drawdown_pct', 0)
                pl_ratio = stock_metrics.get('profit_loss_ratio', 0)
                trading_days = stock_metrics.get('trading_days', 0)
                
                print(f"{ticker:<8} {total_ret:<10.2f} {annual_ret:<10.2f} {win_rate:<8.1f} "
                      f"{sharpe:<8.2f} {abs(drawdown):<10.2f} {pl_ratio:<8.2f} {trading_days:<10}")
            
            print("-" * 80)
            
            # 统计摘要
            total_returns = [m.get('total_return_pct', 0) for m in individual_metrics.values()]
            win_rates = [m.get('win_rate_pct', 0) for m in individual_metrics.values()]
            sharpes = [m.get('sharpe_ratio', 0) for m in individual_metrics.values()]
            
            print(f"\n📊 统计摘要:")
            print(f"   最佳表现: {max(total_returns):.2f}% (总收益)")
            print(f"   最差表现: {min(total_returns):.2f}% (总收益)")
            print(f"   平均收益: {np.mean(total_returns):.2f}%")
            print(f"   平均胜率: {np.mean(win_rates):.1f}%")
            print(f"   平均夏普: {np.mean(sharpes):.2f}")
        
        # 图表信息
        chart_files = report.get('chart_files', [])
        if chart_files:
            print(f"\n📈 生成图表: {len(chart_files)} 个文件")
            for chart_file in chart_files:
                chart_name = Path(chart_file).name
                print(f"   📊 {chart_name}")
        
        print("="*80)
    

    def get_recent_trading_dates(self, num_days: int = 5) -> list:
        """获取最近的交易日期（与主程序保持一致）"""
        # 使用更高效的方法：直接获取交易日历
        if US_TRADING_CALENDAR_AVAILABLE:
            try:
                end_date = datetime.now().strftime('%Y-%m-%d')
                start_date = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')  # 往前推60天确保有足够数据
                
                # 优先尝试使用 pandas_market_calendars
                if 'mcal' in globals():
                    nyse = mcal.get_calendar('NYSE')
                    trading_dates = nyse.valid_days(start_date=start_date, end_date=end_date)
                    # 转换为字符串列表并取最近的num_days天
                    dates = [date.strftime('%Y-%m-%d') for date in trading_dates]
                    return sorted(dates[-num_days:]) if len(dates) >= num_days else sorted(dates)
                
                # 备选：使用 exchange_calendars
                elif 'xcals' in globals():
                    nyse = xcals.get_calendar('XNYS')
                    trading_dates = nyse.sessions_in_range(start_date, end_date)
                    dates = [date.strftime('%Y-%m-%d') for date in trading_dates]
                    return sorted(dates[-num_days:]) if len(dates) >= num_days else sorted(dates)
                    
            except Exception as e:
                print(f"⚠️ 获取交易日历失败，回退到逐日检查: {e}")
        
        # 回退到逐日检查方法
        dates = []
        current_date = datetime.now()
        days_found = 0
        days_back = 0
        
        while days_found < num_days:
            test_date = current_date - timedelta(days=days_back)
            date_str = test_date.strftime('%Y-%m-%d')
            
            if self.is_trading_day(date_str):
                dates.append(date_str)
                days_found += 1
            
            days_back += 1
            if days_back > 60:  # 防止无限循环
                break
        
        return sorted(dates)

 


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="Live交易策略监控系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
子命令说明:
  backfill  回填历史数据 (可指定任意开始日期)
  update    执行每日策略更新
  report    生成绩效分析报告

示例用法:
  # 使用命令行参数
  python live_trading_system.py backfill --tickers AAPL,MSFT --start-date 2025-01-01
  python live_trading_system.py update --tickers AAPL,MSFT
  python live_trading_system.py report --tickers AAPL,MSFT
  
  # 使用环境变量配置文件 (创建 .env 文件)
  python live_trading_system.py backfill
  python live_trading_system.py update
  python live_trading_system.py report
  
  # 生成环境变量模板
  python live_trading_system.py --create-env-template
  
        """
    )
    
    # 全局选项
    parser.add_argument(
        "--create-env-template",
        action="store_true",
        help="创建环境变量配置模板文件并退出"
    )
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # backfill子命令
    backfill_parser = subparsers.add_parser('backfill', help='回填历史数据')
    backfill_parser.add_argument('--tickers', type=str, required=False, help='股票代码列表，用逗号分隔')  # 改为可选
    backfill_parser.add_argument('--start-date', type=str, help='回填开始日期 (格式: YYYY-MM-DD)')
    backfill_parser.add_argument('--max-comm-cycles', type=int, help='最大沟通轮数')
    backfill_parser.add_argument('--base-dir', type=str, help='基础目录')
    
    # update子命令
    update_parser = subparsers.add_parser('update', help='执行每日策略更新')
    update_parser.add_argument('--tickers', type=str, required=False, help='股票代码列表，用逗号分隔')  # 改为可选
    update_parser.add_argument('--date', type=str, help='指定运行日期 (YYYY-MM-DD)')
    update_parser.add_argument('--max-comm-cycles', type=int, help='最大沟通轮数')
    update_parser.add_argument('--force-run', action='store_true', help='强制运行')
    update_parser.add_argument('--base-dir', type=str, help='基础目录')
    
    # report子命令
    report_parser = subparsers.add_parser('report', help='生成绩效分析报告')
    report_parser.add_argument('--tickers', type=str, help='股票代码列表，用逗号分隔（可选）')
    report_parser.add_argument('--base-dir', type=str, help='基础目录')
    
    
    args = parser.parse_args()
    
    # 处理创建环境变量模板的请求
    if args.create_env_template:
        from src.config.env_config import create_env_template
        create_env_template()
        sys.exit(0)
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    try:
        # 加载环境变量配置
        config = LiveTradingConfig()
        
        # 用命令行参数覆盖环境变量配置
        config.override_with_args(args)
        
        # 初始化系统
        system = LiveTradingSystem(base_dir=config.base_dir)
        
        if args.command == 'backfill':
            # 验证股票代码
            if not config.tickers:
                print("❌ 错误: 请通过 --tickers 参数或环境变量 TICKERS 提供至少一个有效的股票代码")
                print("💡 提示: 可以运行 'python live_trading_system.py --create-env-template' 创建配置模板")
                sys.exit(1)
            
            # 验证开始日期格式
            if not system.validate_date_format(config.backfill_start_date):
                print(f"❌ 错误: 日期格式不正确，请使用 YYYY-MM-DD 格式，如: 2025-01-01")
                sys.exit(1)
            
            # 检查日期是否太早（避免过度回填）
            start_date_obj = datetime.strptime(config.backfill_start_date, "%Y-%m-%d")
            if start_date_obj < datetime(2020, 1, 1):
                print(f"⚠️ 警告: 开始日期 {config.backfill_start_date} 较早，可能需要很长时间完成回填")
                print("是否继续？[y/N] ", end="")
                response = input().strip().lower()
                if response != 'y':
                    print("已取消回填")
                    sys.exit(0)
            
            print(f"📅 开始日期: {config.backfill_start_date}")
            print(f"📊 监控股票: {', '.join(config.tickers)}")
            
            # 执行历史数据回填
            result = system.backfill_historical_data(
                tickers=config.tickers,
                start_date=config.backfill_start_date,
                max_comm_cycles=config.max_comm_cycles
            )
            
            if result['status'] == 'completed':
                print(f"\n🎉 历史数据回填完成!")
                
                # 自动生成汇总报告
                print("\n📊 生成汇总报告...")
                report = system.generate_report(config.tickers)
                system.print_performance_summary(report)
                
                print(f"\n📁 数据已保存，后续可使用以下命令:")
                print(f"   每日更新: python live_trading_system.py update --tickers {','.join(config.tickers)}")
                print(f"   查看报告: python live_trading_system.py report --tickers {','.join(config.tickers)}")
            else:
                print(f"\n❌ 回填失败")
                sys.exit(1)
        
        elif args.command == 'update':
            # 验证股票代码
            if not config.tickers:
                print("❌ 错误: 请通过 --tickers 参数或环境变量 TICKERS 提供至少一个有效的股票代码")
                print("💡 提示: 可以运行 'python live_trading_system.py --create-env-template' 创建配置模板")
                sys.exit(1)
            
            # 检查是否存在历史数据，如果没有则提醒先回填
            data_start_date = system.get_data_start_date()
            check_start_date = data_start_date or "2025-01-01"  # 如果没有数据，默认从2025-01-01检查
            missing_dates = system.get_missing_dates(config.tickers, check_start_date)
            
            if len(missing_dates) > 5:  # 如果缺失超过5天，建议先回填
                print(f"⚠️ 检测到缺失 {len(missing_dates)} 个交易日的历史数据")
                if data_start_date:
                    print(f"现有数据从 {data_start_date} 开始，建议回填缺失数据")
                    print(f"建议先运行: python live_trading_system.py backfill --tickers {','.join(config.tickers)} --start-date {check_start_date}")
                else:
                    print(f"未发现历史数据，建议先进行回填")
                    print(f"建议先运行: python live_trading_system.py backfill --tickers {','.join(config.tickers)}")
                print("是否继续执行今日更新？[y/N] ", end="")
                response = input().strip().lower()
                if response != 'y':
                    print("已取消更新")
                    sys.exit(0)
            
            # 执行更新
            result = system.daily_update(
                tickers=config.tickers,
                target_date=config.target_date,
                max_comm_cycles=config.max_comm_cycles,
                force_run=config.force_run
            )
            
            if result['status'] == 'success':
                print(f"\n🎉 Live更新成功完成!")
                
                # 自动生成更新后的报告
                print("\n📊 生成最新报告...")
                report = system.generate_report(config.tickers)
                system.print_performance_summary(report)
                
            elif result['status'] == 'skipped':
                print(f"\n⏭️ 跳过更新: {result['reason']}")
            else:
                print(f"\n❌ 更新失败: {result['reason']}")
                sys.exit(1)
        
        elif args.command == 'report':
            # 使用配置中的股票代码（如果没有指定则为None，生成所有股票的报告）
            tickers = config.tickers if config.tickers else None
            
            # 生成报告
            report = system.generate_report(tickers)
            system.print_performance_summary(report)
        
        
            
    except KeyboardInterrupt:
        print("\n⏹️ 用户中断操作")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 系统错误: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
