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
from typing import Dict, List, Optional, Tuple, Any
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib import rcParams
import seaborn as sns
import pdb
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from advanced_investment_engine import AdvancedInvestmentAnalysisEngine
from src.scheduler.multi_day_manager import MultiDayManager
from src.config.env_config import LiveTradingConfig
from src.config.path_config import get_directory_config
import pandas_market_calendars as mcal
US_TRADING_CALENDAR_AVAILABLE = True

# 设置绘图样式
rcParams['axes.unicode_minus'] = False
plt.style.use('seaborn-v0_8')
sns.set_palette("husl")


class LiveTradingSystem:
    """Live交易策略监控系统 - 统一版本"""
    
    def __init__(self, base_dir: str = None, streamer=None):
        """初始化Live交易系统"""
        # self.base_dir = Path(base_dir) if base_dir else Path(__file__).parent
        self.base_dir = Path(get_directory_config(base_dir))
        self.live_dir = self.base_dir / "live_trading"
        self.data_dir = self.live_dir / "data"
        self.reports_dir = self.live_dir / "reports"
        self.charts_dir = self.reports_dir / "charts"
        self.config_dir = self.live_dir / "config"
        print(self.live_dir)
        # 创建必要的目录
        self._create_directories()
        
        # 数据文件路径
        self.daily_signals_file = self.data_dir / "daily_signals.json"
        self.cumulative_returns_file = self.data_dir / "cumulative_returns.json"
        self.performance_metrics_file = self.data_dir / "performance_metrics.json"
        self.config_file = self.config_dir / "live_config.json"
        
        # 保存streamer引用
        self.streamer = streamer
        
        # 初始化分析引擎（传递streamer）
        self.engine = AdvancedInvestmentAnalysisEngine(streamer=streamer)
    
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
                print(f"加载文件失败 {file_path}: {e}")
                return default or {}
        return default or {}
    
    def _save_json_file(self, file_path: Path, data: dict):
        """保存JSON文件"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            print(f"保存文件失败 {file_path}: {e}")
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
                
         
        
    
    def should_run_today(self, target_date: str = None, force_run: bool = False) -> bool:
        """判断是否今天应该运行"""
        if force_run:
            return True
            
        target_date = target_date or datetime.now().strftime("%Y-%m-%d")
        
        if not self.is_trading_day(target_date):
            print(f"{target_date} 不是交易日，跳过运行")
            return False
        
        last_run_date = self.get_last_run_date()
        if last_run_date and last_run_date >= target_date:
            print(f"{target_date} 已经运行过，跳过运行")
            return False
            
        return True
    
    
    
    # ==================== 策略分析部分 ====================
    
    def run_single_day_analysis(self, tickers: List[str], date: str, max_comm_cycles: int = 2,enable_communications:bool = False,enalbe_notifications:bool=False, mode: str = "signal", initial_cash: float = 100000.0, margin_requirement: float = 0.0, portfolio_state: Optional[Dict[str, Any]] = None) -> dict:  # ⭐ 新增参数
        """运行单日策略分析
        
        Args:
            portfolio_state: 当前Portfolio状态（如果有），用于继续多日运行 ⭐
        """
        print(f"开始分析 {date} 的策略... (模式: {mode})")
        
        # ========== 显示Portfolio状态（如果有）⭐ ==========
        if mode == "portfolio" and portfolio_state:
            positions_count = len([p for p in portfolio_state.get('positions', {}).values() 
                                  if p.get('long', 0) > 0 or p.get('short', 0) > 0])
            print(f"📌 使用现有Portfolio状态: 现金 ${portfolio_state['cash']:,.2f}, "
                  f"持仓数 {positions_count}")
        
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
        
        # ========== 如果有portfolio_state，需要预先注入到state中 ⭐⭐⭐ ==========
        # 因为run_multi_day_strategy只会在i>0时加载previous_state
        # 单日运行时i=0，所以需要手动注入
        kwargs = {
            'initial_cash': initial_cash if not portfolio_state else portfolio_state.get('cash', initial_cash),
            'margin_requirement': margin_requirement
        }
        
        # 如果有portfolio_state，将其存储为临时state供MultiDayManager使用
        if portfolio_state and mode == "portfolio":
            # 创建临时状态文件，让MultiDayManager.load_previous_state能够加载
            temp_state = {
                "portfolio": portfolio_state,
                "date": date,
                "session_id": custom_session_id
            }
            # 将temp_state保存到manager的输出目录，模拟previous_state
            import json
            from pathlib import Path
            temp_dir = Path(multi_day_manager.base_output_dir)
            temp_dir.mkdir(parents=True, exist_ok=True)
            # 使用前一天的日期命名（模拟previous state）
            from datetime import datetime as dt, timedelta
            prev_date = (dt.strptime(date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
            temp_file = temp_dir / f"{custom_session_id}_daily_{prev_date}.json"
            with open(temp_file, 'w') as f:
                json.dump(temp_state, f, indent=2, default=str)
        
        results = multi_day_manager.run_multi_day_strategy(
            tickers=tickers,
            start_date=date,
            end_date=date,
            enable_communications=enable_communications,
            enable_notifications=enalbe_notifications,
            show_reasoning=False,
            progress_callback=None,
            mode=mode,
            **kwargs
        )
        # pdb.set_trace()
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
                
    
    def _extract_signals(self, daily_result: dict) -> dict:
        """从分析结果中提取交易信号（支持signal和portfolio两种模式）"""
        signals = {}
        
        pm_results = daily_result['results'].get('portfolio_management_results', {})
        
        # 先处理final_decisions（如果有）
        if 'final_decisions' in pm_results and pm_results['final_decisions']:
            final_decisions = pm_results['final_decisions']
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
                    'reasoning': decision.get('reasoning', ''),
                    'quantity': decision.get('quantity', 0)  # 添加quantity字段，默认为0
                }
        
        # 再处理messages（Portfolio模式，补充quantity等详细信息）
        if 'messages' in pm_results and pm_results['messages']:
            for msg in reversed(pm_results['messages']):
                if hasattr(msg, 'name') and 'portfolio_manager' in str(msg.name):
                    try:
                        decisions = json.loads(msg.content)
                        for ticker, decision in decisions.items():
                            action = decision.get('action', 'hold')
                            confidence = decision.get('confidence', 0)
                            quantity = decision.get('quantity', 0)
                            
                            # 转换portfolio action到signal
                            if action == 'buy':
                                signal = 'bullish'
                            elif action in ['short', 'sell']:
                                signal = 'bearish'
                            else:  # hold, cover
                                signal = 'neutral'
                            
                            # 如果ticker已经存在，更新quantity等字段；否则创建新条目
                            if ticker in signals:
                                signals[ticker].update({
                                    'action': action,
                                    'quantity': quantity,
                                    'reasoning': decision.get('reasoning', signals[ticker].get('reasoning', ''))
                                })
                            else:
                                signals[ticker] = {
                                    'signal': signal,
                                    'confidence': confidence,
                                    'action': action,
                                    'quantity': quantity,
                                    'reasoning': decision.get('reasoning', '')
                                }
                        break
                    except (json.JSONDecodeError, KeyError, AttributeError) as e:
                        print(f"警告: 解析portfolio决策失败: {e}")
                        continue
            
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
            daily_return,real_return,close_price = multi_day_manager._calculate_stock_daily_return_from_signal(
                ticker, date, trade_action
            )
        
            returns[ticker] = {
                'daily_return': daily_return,
                'real_return': real_return,
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
            print(f"生成{ticker}收益图表失败: {e}")
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
            print(f"生成股票对比图失败: {e}")
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
                print(f"获取交易日历失败，使用简单方法: {e}")
        
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
        print(f"\n开始回填历史数据 ({start_date} 至今)")
        print(f"监控标的: {', '.join(tickers)}")
        
        # 检测缺失的日期
        missing_dates = self.get_missing_dates(tickers, start_date)
        
        if not missing_dates:
            print("所有历史数据已完整，无需回填")
            return {'status': 'completed', 'processed_dates': [], 'failed_dates': []}
        
        print(f"发现 {len(missing_dates)} 个缺失的交易日")
        print(f"缺失日期: {missing_dates[:5]}{'...' if len(missing_dates) > 5 else ''}")
        
        processed_dates = []
        failed_dates = []
        
        # 逐日处理
        for i, date in enumerate(missing_dates):
            print(f"\n处理第 {i+1}/{len(missing_dates)} 天: {date}")
            
            try:
                result = self.daily_update(
                    tickers=tickers,
                    target_date=date,
                    max_comm_cycles=max_comm_cycles,
                    force_run=True
                )
                
                if result['status'] == 'success':
                    processed_dates.append(date)
                    print(f"{date} 处理成功")
                else:
                    failed_dates.append(date)
                    print(f"{date} 处理失败: {result.get('reason', '未知错误')}")
                    
            except Exception as e:
                failed_dates.append(date)
                print(f"{date} 处理异常: {str(e)}")
        
        print(f"\n回填完成统计:")
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
        
        print(f"\n开始Live交易策略更新 - {target_date}")
        print(f"监控标的: {', '.join(tickers)}")
        
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
            print(f"已保存 {len(signals)} 个股票的交易信号")

            # 3. 计算当日收益
            target_date = str(target_date)
            daily_returns = self.calculate_daily_returns(target_date, signals)
            
            # 4. 更新个股收益
            individual_data = self.update_individual_returns(target_date, daily_returns)
            
            # 5. 清理过期数据
            self.clean_old_data()
            
            # 6. 更新运行状态
            self.update_last_run_date(target_date)
            
            print(f"{target_date} 更新完成")
            
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
                'signals': signals,
                'individual_returns': daily_returns,
                'individual_cumulative': individual_data
            }
            
        except Exception as e:
            print(f"更新失败: {str(e)}")
            return {'status': 'failed', 'reason': str(e)}
    
    def generate_report(self, tickers: List[str] = None) -> dict:
        """生成绩效报告"""
        print("开始生成绩效报告...")
        
        returns_data = self._load_json_file(self.cumulative_returns_file, {'individual': {}})
        signals_data = self._load_json_file(self.daily_signals_file, {})
        
        individual_data = returns_data.get('individual', {})
        
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
        
        print("绩效报告生成完成")
        return report
    
    def print_performance_summary(self, report: Dict):
        """打印绩效摘要"""
        if 'error' in report:
            print(f"{report['error']}")
            return
        
        print("\n" + "="*80)
        print("LIVE交易策略 - 个股绩效摘要")
        print("="*80)
        
        # 基础信息
        overview = report.get('overview', {})
        print(f"监控期间: {overview.get('start_date', 'N/A')} ~ {overview.get('end_date', 'N/A')}")
        print(f"监控股票: {', '.join(overview.get('monitored_stocks', []))}")
        print(f"股票数量: {overview.get('total_stocks', 0)} 只")
        
        # 个股详细表现
        individual_metrics = report.get('individual_metrics', {})
        if individual_metrics:
            print(f"\n个股详细表现:")
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
            
            print(f"\n统计摘要:")
            print(f"   最佳表现: {max(total_returns):.2f}% (总收益)")
            print(f"   最差表现: {min(total_returns):.2f}% (总收益)")
            print(f"   平均收益: {np.mean(total_returns):.2f}%")
            print(f"   平均胜率: {np.mean(win_rates):.1f}%")
            print(f"   平均夏普: {np.mean(sharpes):.2f}")
        
        # 图表信息
        chart_files = report.get('chart_files', [])
        if chart_files:
            print(f"\n生成图表: {len(chart_files)} 个文件")
            for chart_file in chart_files:
                chart_name = Path(chart_file).name
                print(f"   {chart_name}")
        
        print("="*80)

 


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
    backfill_parser.add_argument('--tickers', type=str, required=False, help='股票代码列表，用逗号分隔')  
    backfill_parser.add_argument('--start-date', type=str, help='回填开始日期 (格式: YYYY-MM-DD)')
    backfill_parser.add_argument('--max-comm-cycles', type=int, help='最大沟通轮数')
    backfill_parser.add_argument('--base-dir', type=str, help='基础目录')
    
    # update子命令
    update_parser = subparsers.add_parser('update', help='执行每日策略更新')
    update_parser.add_argument('--tickers', type=str, required=False, help='股票代码列表，用逗号分隔')  
    update_parser.add_argument('--date', type=str, help='指定运行日期 (YYYY-MM-DD)')
    update_parser.add_argument('--max-comm-cycles', type=int, help='最大沟通轮数')
    update_parser.add_argument('--force-run', action='store_true', help='强制运行')
    update_parser.add_argument('--base-dir', type=str, help='基础目录')
    
    # report子命令
    report_parser = subparsers.add_parser('report', help='生成绩效分析报告')
    report_parser.add_argument('--tickers', type=str, help='股票代码列表，用逗号分隔（可选）')
    report_parser.add_argument('--base-dir', type=str, help='基础目录')
    
    
    args = parser.parse_args()
    
    
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
                print("错误: 请通过 --tickers 参数或环境变量 TICKERS 提供至少一个有效的股票代码")
                print("提示: 可以运行 'python live_trading_system.py --create-env-template' 创建配置模板")
                sys.exit(1)
            
            # 验证开始日期格式
            if not system.validate_date_format(config.backfill_start_date):
                print(f"错误: 日期格式不正确，请使用 YYYY-MM-DD 格式，如: 2025-01-01")
                sys.exit(1)

            
            print(f"开始日期: {config.backfill_start_date}")
            print(f"监控股票: {', '.join(config.tickers)}")
            
            # 执行历史数据回填
            result = system.backfill_historical_data(
                tickers=config.tickers,
                start_date=config.backfill_start_date,
                max_comm_cycles=config.max_comm_cycles
            )
            
            if result['status'] == 'completed':
                print(f"\n历史数据回填完成!")
                
                # 自动生成汇总报告
                print("\n生成汇总报告...")
                report = system.generate_report(config.tickers)
                system.print_performance_summary(report)
                
                print(f"\n数据已保存，后续可使用以下命令:")
                print(f"   每日更新: python live_trading_system.py update --tickers {','.join(config.tickers)}")
                print(f"   查看报告: python live_trading_system.py report --tickers {','.join(config.tickers)}")
            else:
                print(f"\n回填失败")
                sys.exit(1)
        
        elif args.command == 'update':
            # 验证股票代码
            if not config.tickers:
                print("错误: 请通过 --tickers 参数或环境变量 TICKERS 提供至少一个有效的股票代码")
                print("提示: 可以运行 'python live_trading_system.py --create-env-template' 创建配置模板")
                sys.exit(1)
            
            # 检查是否存在历史数据，如果没有则提醒先回填
            data_start_date = system.get_data_start_date()
            check_start_date = data_start_date or "2025-01-01"  # 如果没有数据，默认从2025-01-01检查
            missing_dates = system.get_missing_dates(config.tickers, check_start_date)
            
            if len(missing_dates) > 5:  # 如果缺失超过5天，建议先回填
                print(f"检测到缺失 {len(missing_dates)} 个交易日的历史数据")
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
                print(f"\nLive更新成功完成!")
                
                # 自动生成更新后的报告
                print("\n生成最新报告...")
                report = system.generate_report(config.tickers)
                system.print_performance_summary(report)
                
            elif result['status'] == 'skipped':
                print(f"\n跳过更新: {result['reason']}")
            else:
                print(f"\n更新失败: {result['reason']}")
                sys.exit(1)
        
        elif args.command == 'report':
            # 使用配置中的股票代码（如果没有指定则为None，生成所有股票的报告）
            tickers = config.tickers if config.tickers else None
            report = system.generate_report(tickers)
            system.print_performance_summary(report)
        
        
            
    except KeyboardInterrupt:
        print("\n用户中断操作")
        sys.exit(1)
    except Exception as e:
        print(f"\n系统错误: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
