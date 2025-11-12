#!/usr/bin/env python3
"""
团队仪表盘数据生成器
为前端提供5个主要数据接口：summary, holdings, stats, trades, leaderboard
"""

import json
import math
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
import os
import pdb
import pandas as pd

class TeamDashboardGenerator:
    """团队仪表盘数据生成器"""
    
    # Agent信息配置
    AGENT_CONFIG = {
        'portfolio_manager': {
            'name': 'Portfolio Manager',
            'role': 'Portfolio Manager',
            'avatar': 'pm'
        },
        'sentiment_analyst': {
            'name': 'Sentiment Analyst',
            'role': 'Sentiment Analyst',
            'avatar': 'sentiment'
        },
        'technical_analyst': {
            'name': 'Technical Analyst',
            'role': 'Technical Analyst',
            'avatar': 'technical'
        },
        'fundamentals_analyst': {
            'name': 'Fundamentals Analyst',
            'role': 'Fundamentals Analyst',
            'avatar': 'fundamentals'
        },
        'valuation_analyst': {
            'name': 'Valuation Analyst',
            'role': 'Valuation Analyst',
            'avatar': 'valuation'
        }
    }
    
    def __init__(self, dashboard_dir: Path, initial_cash: float = 100000.0, 
                 price_data_dir: Path = None):
        """
        初始化团队仪表盘生成器
        
        Args:
            dashboard_dir: team_dashboard目录路径
            initial_cash: 初始现金（用于计算收益率）
            price_data_dir: 价格数据目录路径（默认为src/data/ret_data）
        """
        self.dashboard_dir = Path(dashboard_dir)
        self.dashboard_dir.mkdir(parents=True, exist_ok=True)
        
        self.initial_cash = initial_cash
        
        # 价格数据目录
        if price_data_dir is None:
            # 默认路径：相对于项目根目录
            project_root = Path(__file__).parent.parent.parent
            self.price_data_dir = project_root / "src" / "data" / "ret_data"
        else:
            self.price_data_dir = Path(price_data_dir)
        
        # 5个数据文件路径
        self.summary_file = self.dashboard_dir / "summary.json"
        self.holdings_file = self.dashboard_dir / "holdings.json"
        self.stats_file = self.dashboard_dir / "stats.json"
        self.trades_file = self.dashboard_dir / "trades.json"
        self.leaderboard_file = self.dashboard_dir / "leaderboard.json"
        
        # 内部状态文件（存储累积数据）
        self.state_file = self.dashboard_dir / "_internal_state.json"
        
        # 默认基准价格（用于没有历史价格时）
        self.DEFAULT_BASE_PRICE = 100.0
        
        # 缓存价格数据
        self._price_cache = {}  # ticker -> DataFrame
        
    def _load_json(self, file_path: Path, default: Any = None) -> Any:
        """加载JSON文件"""
        if not file_path.exists():
            return default if default is not None else {}
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载{file_path}失败: {e}")
            return default if default is not None else {}
    
    def _save_json(self, file_path: Path, data: Any):
        """保存JSON文件"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            print(f"保存{file_path}失败: {e}")
    
    def _load_internal_state(self) -> Dict[str, Any]:
        """加载内部状态"""
        state = self._load_json(self.state_file, {
            'equity_history': [],  # [{t: timestamp, v: value}]
            'baseline_history': [],  # Buy & Hold 基准线历史 (等权重)
            'baseline_vw_history': [],  # Buy & Hold 价值加权基准线历史
            'momentum_history': [],  # 动量策略历史
            'all_trades': [],  # 所有交易历史
            'agent_performance': {},  # agent_id -> {signals: [], bull_count: 0, bull_win: 0, ...}
            'portfolio_state': {  # 当前持仓状态
                'cash': self.initial_cash,
                'positions': {}  # ticker -> {qty, avg_cost}
            },
            'baseline_state': {  # Buy & Hold 持仓状态 (等权重)
                'initial_allocation': {},  # ticker -> {qty, buy_price, buy_date}
                'initialized': False
            },
            'baseline_vw_state': {  # Buy & Hold 价值加权持仓状态
                'initial_allocation': {},  # ticker -> {qty, buy_price, buy_date, weight}
                'initialized': False
            },
            'momentum_state': {  # 动量策略持仓状态
                'positions': {},  # ticker -> {qty, buy_price, buy_date}
                'cash': self.initial_cash,
                'initialized': False,
                'last_rebalance_date': None,
                'rebalance_period_days': 20,  # 每20个交易日再平衡一次
                'lookback_days': 20,  # 回看20天计算动量
                'top_n': 3  # 持有动量最强的前3只股票
            },
            'last_update_date': None,
            'total_value_history': [],  # 用于计算收益率
            'price_history': {}  # ticker -> {date: price} 追踪每日价格
        })
        
        # 确保portfolio_state存在
        if 'portfolio_state' not in state:
            state['portfolio_state'] = {
                'cash': self.initial_cash,
                'positions': {}
            }
        
        # 确保total_value_history存在
        if 'total_value_history' not in state:
            state['total_value_history'] = []
        
        # 确保baseline_state存在
        if 'baseline_state' not in state:
            state['baseline_state'] = {
                'initial_allocation': {},
                'initialized': False
            }
        
        # 确保baseline_history存在
        if 'baseline_history' not in state:
            state['baseline_history'] = []
        
        # 确保momentum_state存在
        if 'momentum_state' not in state:
            state['momentum_state'] = {
                'positions': {},
                'cash': self.initial_cash,
                'initialized': False,
                'last_rebalance_date': None,
                'rebalance_period_days': 20,
                'lookback_days': 20,
                'top_n': 3
            }
        
        # 确保momentum_history存在
        if 'momentum_history' not in state:
            state['momentum_history'] = []
        
        # 确保baseline_vw_state存在
        if 'baseline_vw_state' not in state:
            state['baseline_vw_state'] = {
                'initial_allocation': {},
                'initialized': False
            }
        
        # 确保baseline_vw_history存在
        if 'baseline_vw_history' not in state:
            state['baseline_vw_history'] = []
        
        return state
    
    def _save_internal_state(self, state: Dict[str, Any]):
        """保存内部状态"""
        self._save_json(self.state_file, state)
    
    def _load_price_data(self, ticker: str) -> Optional[pd.DataFrame]:
        """
        加载股票价格数据
        
        Args:
            ticker: 股票代码
            
        Returns:
            价格数据DataFrame，如果文件不存在返回None
        """
        # 检查缓存
        if ticker in self._price_cache:
            return self._price_cache[ticker]
        
        # 构建CSV文件路径
        csv_file = self.price_data_dir / f"{ticker}.csv"
        
        if not csv_file.exists():
            print(f"⚠️ 价格数据文件不存在: {csv_file}")
            return None
        
        try:
            # 读取CSV文件
            df = pd.read_csv(csv_file)
            
            # 解析日期列
            df['Date'] = pd.to_datetime(df['time'])
            
            # 提取日期（不含时间）作为索引
            df['date_str'] = df['Date'].dt.strftime('%Y-%m-%d')
            df.set_index('date_str', inplace=True)
            
            # 缓存数据
            self._price_cache[ticker] = df
            
            return df
        except Exception as e:
            print(f"❌ 加载价格数据失败 ({ticker}): {e}")
            return None
    
    def _get_price_from_csv(self, ticker: str, date: str, price_type: str = 'close') -> Optional[float]:
        """
        从CSV文件获取指定日期的价格
        
        Args:
            ticker: 股票代码
            date: 日期 YYYY-MM-DD
            price_type: 价格类型 ('open', 'close', 'high', 'low')
            
        Returns:
            价格，如果不存在返回None
        """
        df = self._load_price_data(ticker)
        
        if df is None:
            return None
        
        try:
            if date in df.index:
                return float(df.loc[date, price_type])
            else:
                # 日期不存在，可能是非交易日
                return None
        except Exception as e:
            print(f"⚠️ 获取价格失败 ({ticker}, {date}): {e}")
            return None
    
    def update_from_day_result(self, date: str, pre_market_result: Dict[str, Any], 
                                mode: str = "signal") -> Dict[str, Any]:
        """
        根据单日结果更新所有仪表盘数据
        
        Args:
            date: 交易日期 YYYY-MM-DD
            pre_market_result: 交易前分析结果（包含signals, live_env等）
            mode: 运行模式 ("signal" 或 "portfolio")
            
        Returns:
            更新统计信息
        """
        # if pre_market_result.get('status') != 'success':
        #     print(f"⚠️ {date} 交易前分析未成功，跳过仪表盘更新")
        #     return {'status': 'skipped', 'reason': 'pre_market not successful'}
        
        # 加载内部状态
        state = self._load_internal_state()
        
        # 提取数据
        live_env = pre_market_result.get('live_env', {})
        real_returns = live_env.get('real_returns', {})
        pm_signals = live_env.get('pm_signals', {})
        ana_signals = live_env.get('ana_signals', {})
        pdb.set_trace()
        # 时间戳（使用交易日的时间戳）
        date_obj = datetime.strptime(date, "%Y-%m-%d")
        timestamp_ms = int(date_obj.timestamp() * 1000)
        
        update_stats = {
            'date': date,
            'mode': mode,
            'trades_added': 0,
            'agents_updated': 0
        }
        
        # 0. 初始化 Buy & Hold 和价值加权 Buy & Hold（仅第一次）
        available_tickers = list(pm_signals.keys())
        self._initialize_buy_and_hold(date, available_tickers, state)
        self._initialize_buy_and_hold_vw(date, available_tickers, state)
        
        # 1. 更新交易记录和持仓
        if mode == "portfolio":
            self._update_portfolio_mode(date, timestamp_ms, pm_signals, real_returns, 
                                       live_env, state, update_stats)
        else:
            self._update_signal_mode(date, timestamp_ms, pm_signals, real_returns, 
                                    state, update_stats)
        
        # 2. 更新价格历史（基于收益率）
        self._update_price_history(date, real_returns, state)
        
        # 3. 更新Agent表现
        self._update_agent_performance(date, ana_signals, pm_signals, real_returns, state, update_stats)
        
        # 4. 更新Portfolio Manager表现
        self._update_pm_performance(date, pm_signals, real_returns, state, update_stats)
        
        # 5. 检查是否有收盘价数据，只在有确定价格时才更新权益曲线
        has_closing_prices = self._check_has_closing_prices(date, available_tickers)
        curves_updated = False
        
        if has_closing_prices:
            # 5a. 更新权益曲线
            self._update_equity_curve(date, timestamp_ms, state)
            
            # 5b. 更新 Buy & Hold 基准线（等权重）
            self._update_baseline_curve(date, timestamp_ms, state)
            
            # 5c. 更新价值加权 Buy & Hold 基准线
            self._update_baseline_vw_curve(date, timestamp_ms, state)
            
            # 5d. 更新动量策略曲线
            self._update_momentum_curve(date, timestamp_ms, available_tickers, state)
            
            curves_updated = True
            print(f"✅ 权益曲线已更新 ({date})")
        else:
            print(f"⏸️  跳过权益曲线更新 ({date}) - 等待收盘价数据")
        
        # 8. 保存内部状态
        state['last_update_date'] = date
        state['curves_updated'] = curves_updated  # 记录曲线是否已更新
        self._save_internal_state(state)
        
        # 9. 生成所有前端数据文件
        # 注意：holdings, stats, trades, leaderboard 需要每次都更新（包含实时交易信号）
        # 但 summary 只在曲线更新时才重新生成（避免触发不必要的广播）
        if curves_updated:
            self._generate_summary(state)
            print(f"✅ {date} 团队仪表盘权益曲线已更新")
        else:
            print(f"⏸️  {date} 跳过权益曲线更新 - 等待收盘价数据")
        
        # 其他数据始终更新（包含实时交易信号和Agent表现）
        self._generate_holdings(state)
        self._generate_stats(state)
        self._generate_trades(state)
        self._generate_leaderboard(state)
        
        print(f"✅ {date} 团队仪表盘数据已更新")
        return update_stats
    
    def _update_price_history(self, date: str, real_returns: Dict, state: Dict):
        """
        更新价格历史（从CSV文件直接读取真实价格）
        
        逻辑：
        - 从ret_data目录的CSV文件读取对应日期的close价格
        - 如果读取失败，使用DEFAULT_BASE_PRICE作为后备
        """
        if 'price_history' not in state:
            state['price_history'] = {}
        
        price_history = state['price_history']
        
        # 遍历所有涉及的ticker（从real_returns获取）
        for ticker in real_returns.keys():
            if ticker not in price_history:
                price_history[ticker] = {}
            
            # 从CSV文件获取真实价格
            actual_price = self._get_price_from_csv(ticker, date, 'close')
            
            # 成功获取真实价格
            price_history[ticker][date] = actual_price
          
    def _check_has_closing_prices(self, date: str, tickers: List[str]) -> bool:
        """
        检查指定日期是否有所有股票的收盘价数据
        
        Args:
            date: 交易日期 YYYY-MM-DD
            tickers: 股票代码列表
            
        Returns:
            如果所有股票都有收盘价数据则返回True，否则返回False
        """
        if not tickers:
            return False
        
        # 检查至少一半的股票有收盘价
        valid_count = 0
        for ticker in tickers:
            price = self._get_price_from_csv(ticker, date, 'close')
            if price is not None:
                valid_count += 1
        
        # 至少需要一半的股票有收盘价数据
        return valid_count >= len(tickers) / 2
    
    def _get_current_price(self, ticker: str, date: str, state: Dict) -> float:
        """
        获取股票的当前价格
        
        优先级：
        1. 从CSV文件直接读取真实价格
        2. price_history中的价格（如果CSV读取失败）
        3. 默认基准价格
        """
        # 优先从CSV文件获取真实价格
        actual_price = self._get_price_from_csv(ticker, date, 'close')
        if actual_price is not None:
            return actual_price
        
        # 如果CSV读取失败，尝试从price_history获取
        price_history = state.get('price_history', {})
        
        if ticker in price_history and date in price_history[ticker]:
            return price_history[ticker][date]
        
        # 如果有历史价格，使用最新的
        if ticker in price_history and price_history[ticker]:
            dates = sorted(price_history[ticker].keys())
            return price_history[ticker][dates[-1]]
        
        # 默认价格
        return self.DEFAULT_BASE_PRICE
    
    def _get_ticker_price(self, ticker: str, date: str, signal_info: Dict, 
                         portfolio_state: Dict, real_returns: Dict) -> float:
        """
        获取股票价格（尝试多种来源）
        
        优先级：
        1. 从CSV文件读取真实价格
      
        """
        # 1. 优先从CSV文件获取真实价格
        actual_price = self._get_price_from_csv(ticker, date, 'close')
        return actual_price
        
    def _normalize_real_return(self, value: Any) -> Tuple[Optional[float], Any]:
        """
        标准化真实收益率：
        - 返回 (可用于计算的浮点值或None, 供前端展示的值/unknown)
        """
        if value is None:
            return None, 'unknown'
        
        # 处理字符串（可能已经是"unknown"或数字字符串）
        if isinstance(value, str):
            if value.lower() == 'unknown':
                return None, 'unknown'
            try:
                value = float(value)
            except ValueError:
                return None, 'unknown'
        
        if isinstance(value, (int, float)):
            # bool也是int的子类，直接转换
            value = float(value)
            if math.isnan(value):
                return None, 'unknown'
            return value, value
        
        return None, 'unknown'
        
       
    def _update_portfolio_mode(self, date: str, timestamp_ms: int, pm_signals: Dict, 
                                real_returns: Dict, live_env: Dict, state: Dict, 
                                update_stats: Dict):
        """Portfolio模式：更新交易和持仓"""
        portfolio_state = state['portfolio_state']
        
        # 获取portfolio信息
        portfolio_summary = live_env.get('portfolio_summary', {})
        updated_portfolio = live_env.get('updated_portfolio', {})
        
        # 如果有updated_portfolio，直接使用
        if updated_portfolio:
            portfolio_state['cash'] = updated_portfolio.get('cash', portfolio_state['cash'])
            new_positions = updated_portfolio.get('positions', {})
            
            # 更新持仓（转换为简化格式）
            for ticker, position_data in new_positions.items():
                long_qty = position_data.get('long', 0)
                short_qty = position_data.get('short', 0)
                long_cost = position_data.get('long_cost_basis', 0)
                short_cost = position_data.get('short_cost_basis', 0)
                
                # 合并多空仓位（简化处理：净持仓）
                net_qty = long_qty - short_qty
                if net_qty != 0:
                    avg_cost = long_cost if net_qty > 0 else short_cost
                    portfolio_state['positions'][ticker] = {
                        'qty': net_qty,
                        'avg_cost': avg_cost
                    }
                elif ticker in portfolio_state['positions']:
                    # 仓位清空
                    del portfolio_state['positions'][ticker]
        
        # 记录交易
        for ticker, signal_info in pm_signals.items():
            action = signal_info.get('action', 'hold')
            quantity = signal_info.get('quantity', 0)
            
            if action != 'hold' and quantity > 0:
                # 获取成交价格
                price = self._get_ticker_price(ticker, date, signal_info, portfolio_state, real_returns)
                numeric_real_return, _ = self._normalize_real_return(real_returns.get(ticker))
                
                # 计算该笔交易的P&L（基于当日收益, 未知时记为0）
                if numeric_real_return is None:
                    pnl = 0.0
                elif action == 'long':
                    pnl = quantity * price * numeric_real_return
                elif action == 'short':
                    pnl = -quantity * price * numeric_real_return
                else:
                    pnl = 0.0
                
                # 映射action到side（用于显示）
                side_map = {
                    'long': 'LONG',
                    'short': 'SHORT',
                    'hold': 'HOLD'
                }
                side = side_map.get(action, 'HOLD')
                
                # 生成交易ID
                trade_count = len([t for t in state['all_trades'] if t['ticker'] == ticker and t['ts'] == timestamp_ms])
                trade_id = f"t_{date.replace('-', '')[:8]}_{ticker}_{trade_count}"
                
                trade_record = {
                    'id': trade_id,
                    'ts': timestamp_ms,
                    'side': side,
                    'ticker': ticker,
                    'qty': quantity,
                    'price': round(price, 2),
                    'pnl': round(pnl, 2)
                }
                
                state['all_trades'].append(trade_record)
                update_stats['trades_added'] += 1
    
    def _update_signal_mode(self, date: str, timestamp_ms: int, pm_signals: Dict,
                            real_returns: Dict, state: Dict, update_stats: Dict):
        """Signal模式：更新信号记录"""
        portfolio_state = state['portfolio_state']
        
        # Signal模式下，模拟持仓变化（假设每次信号都执行固定数量）
        DEFAULT_QUANTITY = 100  # 默认交易数量
        
        for ticker, signal_info in pm_signals.items():
            signal = signal_info.get('signal', 'neutral')
            action = signal_info.get('action', 'hold')
            
            # if action == 'hold':
            #     continue
            
            # 获取当前价格
            price = self._get_ticker_price(ticker, date, signal_info, portfolio_state, real_returns)
            numeric_real_return, _ = self._normalize_real_return(real_returns.get(ticker))
            quantity = DEFAULT_QUANTITY
            
            # 映射signal到side
            side_map = {
                'bullish': 'BUY',
                'bearish': 'SELL',
                'neutral': 'HOLD'
            }
            side = side_map.get(signal, 'HOLD')
            
            # 更新持仓
            if signal == 'bullish':
                if ticker not in portfolio_state['positions']:
                    portfolio_state['positions'][ticker] = {'qty': 0, 'avg_cost': price}
                pos = portfolio_state['positions'][ticker]
                old_qty = pos['qty']
                old_cost = pos['avg_cost']
                new_qty = old_qty + quantity
                # 计算新的平均成本
                if new_qty > 0:
                    new_cost = (old_qty * old_cost + quantity * price) / new_qty
                    pos['qty'] = new_qty
                    pos['avg_cost'] = new_cost
            elif signal == 'bearish':
                if ticker in portfolio_state['positions']:
                    pos = portfolio_state['positions'][ticker]
                    pos['qty'] = max(0, pos['qty'] - quantity)
                    if pos['qty'] == 0:
                        del portfolio_state['positions'][ticker]
            
            # 计算P&L（未知收益时按0处理）
            pnl = quantity * price * (numeric_real_return if numeric_real_return is not None else 0.0)
            
            # 生成交易ID
            trade_count = len([t for t in state['all_trades'] if t['ticker'] == ticker and t['ts'] == timestamp_ms])
            trade_id = f"t_{date.replace('-', '')}_{ticker}_{trade_count}"
            
            trade_record = {
                'id': trade_id,
                'ts': timestamp_ms,
                'side': side,
                'ticker': ticker,
                'qty': quantity,
                'price': round(price, 2),
                'pnl': round(pnl, 2)
            }
            
            state['all_trades'].append(trade_record)
            update_stats['trades_added'] += 1
    
    def _update_agent_performance(self, date: str, ana_signals: Dict, pm_signals: Dict,
                                  real_returns: Dict, state: Dict, update_stats: Dict):
        """更新分析师表现"""
        if 'agent_performance' not in state:
            state['agent_performance'] = {}
        
        for agent_id, signals in ana_signals.items():
            if agent_id not in state['agent_performance']:
                state['agent_performance'][agent_id] = {
                    'signals': [],
                    'bull_count': 0,
                    'bull_win': 0,
                    'bull_unknown': 0,
                    'bear_count': 0,
                    'bear_win': 0,
                    'bear_unknown': 0,
                    'neutral_count': 0,
                    'logs': []
                }
            
            agent_perf = state['agent_performance'][agent_id]
            agent_perf.setdefault('bull_unknown', 0)
            agent_perf.setdefault('bear_unknown', 0)
            
            for ticker, signal_data in signals.items():
                if not signal_data or signal_data == 'N/A':
                    continue
                
                # 提取信号值（支持字典和字符串格式）
                if isinstance(signal_data, dict):
                    signal = signal_data.get('signal', 'N/A')
                else:
                    signal = signal_data
                
                if not signal or signal == 'N/A':
                    continue
                
                numeric_real_return, display_real_return = self._normalize_real_return(real_returns.get(ticker))
                
                # 判断信号类型和正确性（标准化格式，不区分大小写）
                signal_lower = signal.lower() if isinstance(signal, str) else str(signal).lower()
                is_bull = signal_lower in ['buy', 'bullish', 'long'] or 'bull' in signal_lower
                is_bear = signal_lower in ['sell', 'bearish', 'short'] or 'bear' in signal_lower
                is_neutral = signal_lower in ['hold', 'neutral'] or 'neutral' in signal_lower
                
                is_correct = False
                result_unknown = numeric_real_return is None
                
                if is_bull:
                    agent_perf['bull_count'] += 1
                    if result_unknown:
                        agent_perf['bull_unknown'] += 1
                    elif numeric_real_return > 0:
                        is_correct = True
                        agent_perf['bull_win'] += 1
                elif is_bear:
                    agent_perf['bear_count'] += 1
                    if result_unknown:
                        agent_perf['bear_unknown'] += 1
                    elif numeric_real_return < 0:
                        is_correct = True
                        agent_perf['bear_win'] += 1
                elif is_neutral:
                    agent_perf['neutral_count'] += 1
                    # neutral信号不纳入胜率统计
                
                # 记录信号
                signal_record = {
                    'date': date,
                    'ticker': ticker,
                    'signal': signal,
                    'real_return': display_real_return,
                    'is_correct': 'unknown' if result_unknown else is_correct
                }
                agent_perf['signals'].append(signal_record)
                
                # 更新日志（保留最近50条）
                if result_unknown and not is_neutral:
                    marker = '?'
                elif is_neutral:
                    marker = ''
                else:
                    marker = '✓' if is_correct else '✗'
                log_entry = f"{'Bull' if is_bull else 'Bear' if is_bear else 'Neutral'} on {ticker} {marker}"
                agent_perf['logs'].insert(0, log_entry)
                agent_perf['logs'] = agent_perf['logs'][:50]
            
            update_stats['agents_updated'] += 1
    
    def _update_pm_performance(self, date: str, pm_signals: Dict, real_returns: Dict,
                               state: Dict, update_stats: Dict):
        """更新Portfolio Manager表现"""
        agent_id = 'portfolio_manager'
        
        if 'agent_performance' not in state:
            state['agent_performance'] = {}
        
        if agent_id not in state['agent_performance']:
            state['agent_performance'][agent_id] = {
                'signals': [],
                'bull_count': 0,
                'bull_win': 0,
                'bull_unknown': 0,
                'bear_count': 0,
                'bear_win': 0,
                'bear_unknown': 0,
                'neutral_count': 0,
                'logs': []
            }
        
        pm_perf = state['agent_performance'][agent_id]
        pm_perf.setdefault('bull_unknown', 0)
        pm_perf.setdefault('bear_unknown', 0)
        
        for ticker, signal_info in pm_signals.items():
            signal = signal_info.get('signal', 'neutral')
            numeric_real_return, display_real_return = self._normalize_real_return(real_returns.get(ticker))
            
            signal_lower = signal.lower()
            is_bull = 'bull' in signal_lower or signal_lower == 'long'
            is_bear = 'bear' in signal_lower or signal_lower == 'short'
            is_neutral = 'neutral' in signal_lower or signal_lower == 'hold'
            
            is_correct = False
            result_unknown = numeric_real_return is None
            if is_bull:
                pm_perf['bull_count'] += 1
                if result_unknown:
                    pm_perf['bull_unknown'] += 1
                elif numeric_real_return > 0:
                    is_correct = True
                    pm_perf['bull_win'] += 1
            elif is_bear:
                pm_perf['bear_count'] += 1
                if result_unknown:
                    pm_perf['bear_unknown'] += 1
                elif numeric_real_return < 0:
                    is_correct = True
                    pm_perf['bear_win'] += 1
            elif is_neutral:
                pm_perf['neutral_count'] += 1
            
            signal_record = {
                'date': date,
                'ticker': ticker,
                'signal': signal,
                'real_return': display_real_return,
                'is_correct': 'unknown' if result_unknown else is_correct
            }
            pm_perf['signals'].append(signal_record)
            
            if result_unknown and not is_neutral:
                marker = '?'
            elif is_neutral:
                marker = ''
            else:
                marker = '✓' if is_correct else '✗'
            log_entry = f"{'Bull' if is_bull else 'Bear' if is_bear else 'Neutral'} on {ticker} {marker}"
            pm_perf['logs'].insert(0, log_entry)
            pm_perf['logs'] = pm_perf['logs'][:50]
    
    def _update_equity_curve(self, date: str, timestamp_ms: int, state: Dict):
        """更新权益曲线（使用真实价格）"""
        portfolio_state = state['portfolio_state']
        
        # 如果是第一次更新（历史记录为空），先添加初始点（和 Baseline 保持一致）
        if len(state['equity_history']) == 0:
            initial_point = {
                't': timestamp_ms,
                'v': round(self.initial_cash, 2)  # $100,000
            }
            state['equity_history'].append(initial_point)
            print(f"📊 Portfolio 初始点: ${self.initial_cash:,.2f}")
        
        # 计算当前总价值：现金 + 持仓市值（使用真实价格）
        cash = portfolio_state['cash']
        positions_value = 0.0
        
        for ticker, pos in portfolio_state['positions'].items():
            # 使用当日真实价格
            current_price = self._get_current_price(ticker, date, state)
            positions_value += pos['qty'] * current_price
        
        total_value = cash + positions_value
        
        # 直接使用实际金额（不再归一化为百分比）
        # normalized_value = (total_value / self.initial_cash) * 100
        
        # 添加到权益曲线
        equity_point = {
            't': timestamp_ms,
            'v': round(total_value, 2)  # 存储实际金额
        }
        state['equity_history'].append(equity_point)
        
        # 记录总价值历史
        state['total_value_history'].append({
            'date': date,
            'total_value': total_value
        })
    
    def _initialize_buy_and_hold(self, date: str, available_tickers: list, state: Dict):
        """
        初始化 Buy & Hold 策略
        
        在第一个交易日收盘时，使用收盘价买入股票
        这样确保和 Portfolio 的初始状态一致
        
        Args:
            date: 交易日期
            available_tickers: 可交易的股票列表
            state: 内部状态
        """
        baseline_state = state['baseline_state']
        
        if baseline_state['initialized']:
            return  # 已经初始化过了
        
        if not available_tickers:
            print("⚠️ 没有可交易的股票，跳过 Buy & Hold 初始化")
            return
        
        # 计算每只股票的分配资金（等权重）
        cash_per_ticker = self.initial_cash / len(available_tickers)
        
        initial_allocation = {}
        total_invested = 0.0
        
        for ticker in available_tickers:
            # 使用收盘价买入（和 Portfolio 保持一致）
            price = self._get_price_from_csv(ticker, date, 'close')
            
            if price is None or price <= 0:
                print(f"⚠️ {ticker} 在 {date} 没有有效价格，跳过")
                continue
            
            # 计算可购买的数量（向下取整）
            quantity = int(cash_per_ticker / price)
            
            if quantity > 0:
                initial_allocation[ticker] = {
                    'qty': quantity,
                    'buy_price': price,
                    'buy_date': date
                }
                total_invested += quantity * price
        
        baseline_state['initial_allocation'] = initial_allocation
        baseline_state['initialized'] = True
        
        print(f"✅ Buy & Hold 策略已初始化: {len(initial_allocation)} 只股票，投资 ${total_invested:,.2f}")
        for ticker, info in initial_allocation.items():
            print(f"   {ticker}: {info['qty']} 股 @ ${info['buy_price']:.2f}")
    
    def _calculate_buy_and_hold_value(self, date: str, state: Dict) -> float:
        """
        计算 Buy & Hold 策略的当前净值
        
        Args:
            date: 当前日期
            state: 内部状态
            
        Returns:
            Buy & Hold 策略的总资产价值
        """
        baseline_state = state['baseline_state']
        
        if not baseline_state['initialized']:
            return self.initial_cash  # 还未初始化，返回初始资金
        
        total_value = 0.0
        initial_allocation = baseline_state['initial_allocation']
        
        for ticker, info in initial_allocation.items():
            # 获取当前价格
            current_price = self._get_current_price(ticker, date, state)
            
            if current_price is None or current_price <= 0:
                # 如果无法获取价格，使用购买价格作为后备
                current_price = info['buy_price']
                print(f"⚠️ {ticker} 在 {date} 无法获取价格，使用买入价 ${current_price:.2f}")
            
            # 计算持仓市值
            position_value = info['qty'] * current_price
            total_value += position_value
        
        return total_value
    
    def _update_baseline_curve(self, date: str, timestamp_ms: int, state: Dict):
        """
        更新 Buy & Hold 基准线
        
        Args:
            date: 交易日期
            timestamp_ms: 时间戳（毫秒）
            state: 内部状态
        """
        baseline_state = state['baseline_state']
        
        # 如果 baseline 刚初始化，且历史记录为空，先添加初始点
        if baseline_state['initialized'] and len(state['baseline_history']) == 0:
            # 添加初始资金作为起始点（和 Portfolio 保持一致）
            initial_point = {
                't': timestamp_ms,
                'v': round(self.initial_cash, 2)  # $100,000
            }
            state['baseline_history'].append(initial_point)
            print(f"📊 Buy & Hold 初始点: ${self.initial_cash:,.2f}")
        
        # 计算 Buy & Hold 策略的当前总价值
        baseline_value = self._calculate_buy_and_hold_value(date, state)
        
        # 直接使用实际金额（不再归一化为百分比）
        # normalized_value = (baseline_value / self.initial_cash) * 100
        
        # 添加到基准线历史
        baseline_point = {
            't': timestamp_ms,
            'v': round(baseline_value, 2)  # 存储实际金额
        }
        
        state['baseline_history'].append(baseline_point)
        
        # 计算收益率用于日志显示
        return_pct = ((baseline_value - self.initial_cash) / self.initial_cash) * 100
        print(f"📊 Buy & Hold 基准: ${baseline_value:,.2f} ({return_pct:+.2f}%)")
    
    def _initialize_buy_and_hold_vw(self, date: str, available_tickers: list, state: Dict):
        """
        初始化价值加权 Buy & Hold 策略
        
        根据各股票的市值比例分配初始资金
        
        Args:
            date: 交易日期
            available_tickers: 可交易的股票列表
            state: 内部状态
        """
        from src.tools.data_tools import get_market_cap
        
        baseline_vw_state = state['baseline_vw_state']
        
        if baseline_vw_state['initialized']:
            return  # 已经初始化过了
        
        if not available_tickers:
            print("⚠️ 没有可交易的股票，跳过价值加权 Buy & Hold 初始化")
            return
        
        # 获取所有股票的市值
        market_caps = {}
        for ticker in available_tickers:
            try:
                mcap = get_market_cap(ticker, date, api_key=None)
                if mcap and mcap > 0:
                    market_caps[ticker] = mcap
                else:
                    print(f"⚠️ {ticker} 市值数据无效，跳过")
            except Exception as e:
                print(f"⚠️ 获取 {ticker} 市值失败: {e}")
        
        if not market_caps:
            print("⚠️ 无法获取任何股票的市值数据，跳过价值加权 Buy & Hold 初始化")
            return
        
        # 计算总市值
        total_market_cap = sum(market_caps.values())
        
        # 根据市值比例分配资金
        initial_allocation = {}
        total_invested = 0.0
        
        for ticker, mcap in market_caps.items():
            # 计算该股票应分配的资金（按市值比例）
            weight = mcap / total_market_cap
            allocated_cash = self.initial_cash * weight
            
            # 使用收盘价买入
            price = self._get_price_from_csv(ticker, date, 'close')
            
            if price is None or price <= 0:
                print(f"⚠️ {ticker} 在 {date} 没有有效价格，跳过")
                continue
            
            # 计算可购买的数量（向下取整）
            quantity = int(allocated_cash / price)
            
            if quantity > 0:
                initial_allocation[ticker] = {
                    'qty': quantity,
                    'buy_price': price,
                    'buy_date': date,
                    'weight': weight,  # 记录市值权重
                    'market_cap': mcap
                }
                total_invested += quantity * price
        
        baseline_vw_state['initial_allocation'] = initial_allocation
        baseline_vw_state['initialized'] = True
        
        print(f"✅ 价值加权 Buy & Hold 策略已初始化: {len(initial_allocation)} 只股票，投资 ${total_invested:,.2f}")
        for ticker, info in initial_allocation.items():
            print(f"   {ticker}: {info['qty']} 股 @ ${info['buy_price']:.2f} (权重: {info['weight']*100:.2f}%)")
    
    def _calculate_buy_and_hold_vw_value(self, date: str, state: Dict) -> float:
        """
        计算价值加权 Buy & Hold 策略的当前净值
        
        Args:
            date: 当前日期
            state: 内部状态
            
        Returns:
            价值加权 Buy & Hold 策略的总资产价值
        """
        baseline_vw_state = state['baseline_vw_state']
        
        if not baseline_vw_state['initialized']:
            return self.initial_cash  # 还未初始化，返回初始资金
        
        total_value = 0.0
        initial_allocation = baseline_vw_state['initial_allocation']
        
        for ticker, info in initial_allocation.items():
            # 获取当前价格
            current_price = self._get_current_price(ticker, date, state)
            
            if current_price is None or current_price <= 0:
                # 如果无法获取价格，使用购买价格作为后备
                current_price = info['buy_price']
                print(f"⚠️ {ticker} 在 {date} 无法获取价格，使用买入价 ${current_price:.2f}")
            
            # 计算持仓市值
            position_value = info['qty'] * current_price
            total_value += position_value
        
        return total_value
    
    def _update_baseline_vw_curve(self, date: str, timestamp_ms: int, state: Dict):
        """
        更新价值加权 Buy & Hold 基准线
        
        Args:
            date: 交易日期
            timestamp_ms: 时间戳（毫秒）
            state: 内部状态
        """
        baseline_vw_state = state['baseline_vw_state']
        
        # 如果 baseline_vw 刚初始化，且历史记录为空，先添加初始点
        if baseline_vw_state['initialized'] and len(state['baseline_vw_history']) == 0:
            # 添加初始资金作为起始点
            initial_point = {
                't': timestamp_ms,
                'v': round(self.initial_cash, 2)
            }
            state['baseline_vw_history'].append(initial_point)
            print(f"📊 价值加权 Buy & Hold 初始点: ${self.initial_cash:,.2f}")
        
        # 计算价值加权 Buy & Hold 策略的当前总价值
        baseline_vw_value = self._calculate_buy_and_hold_vw_value(date, state)
        
        # 添加到基准线历史
        baseline_vw_point = {
            't': timestamp_ms,
            'v': round(baseline_vw_value, 2)
        }
        
        state['baseline_vw_history'].append(baseline_vw_point)
        
        # 计算收益率用于日志显示
        return_pct = ((baseline_vw_value - self.initial_cash) / self.initial_cash) * 100
        print(f"📊 价值加权 Buy & Hold 基准: ${baseline_vw_value:,.2f} ({return_pct:+.2f}%)")
    
    def _calculate_momentum_scores(self, date: str, available_tickers: list, 
                                   lookback_days: int, state: Dict) -> Dict[str, float]:
        """
        计算所有股票的动量得分（过去N天的收益率）
        
        Args:
            date: 当前日期
            available_tickers: 可交易的股票列表
            lookback_days: 回看天数
            state: 内部状态
            
        Returns:
            ticker -> momentum_score (收益率)
        """
        momentum_scores = {}
        
        # 将日期转换为 datetime
        current_date = datetime.strptime(date, "%Y-%m-%d")
        
        for ticker in available_tickers:
            # 获取当前价格
            current_price = self._get_price_from_csv(ticker, date, 'close')
            if current_price is None or current_price <= 0:
                continue
            
            # 尝试获取 lookback_days 天前的价格
            # 由于可能有非交易日，我们需要向前查找
            past_price = None
            for days_back in range(lookback_days, lookback_days + 10):  # 最多多找10天
                past_date = current_date - timedelta(days=days_back)
                past_date_str = past_date.strftime("%Y-%m-%d")
                past_price = self._get_price_from_csv(ticker, past_date_str, 'close')
                if past_price is not None and past_price > 0:
                    break
            
            if past_price is None or past_price <= 0:
                # 无法获取历史价格，跳过
                continue
            
            # 计算动量得分（收益率）
            momentum_score = (current_price - past_price) / past_price
            momentum_scores[ticker] = momentum_score
        
        return momentum_scores
    
    def _should_rebalance_momentum(self, date: str, state: Dict) -> bool:
        """
        判断是否需要再平衡动量策略
        
        Args:
            date: 当前日期
            state: 内部状态
            
        Returns:
            是否需要再平衡
        """
        momentum_state = state['momentum_state']
        
        # 如果还未初始化，需要初始化
        if not momentum_state['initialized']:
            return True
        
        last_rebalance = momentum_state.get('last_rebalance_date')
        if last_rebalance is None:
            return True
        
        # 计算距离上次再平衡的天数
        current_date = datetime.strptime(date, "%Y-%m-%d")
        last_rebalance_date = datetime.strptime(last_rebalance, "%Y-%m-%d")
        days_since_rebalance = (current_date - last_rebalance_date).days
        
        rebalance_period = momentum_state.get('rebalance_period_days', 20)
        
        return days_since_rebalance >= rebalance_period
    
    def _rebalance_momentum_portfolio(self, date: str, available_tickers: list, state: Dict):
        """
        再平衡动量策略组合
        
        策略逻辑：
        1. 计算所有股票的动量得分（过去N天收益率）
        2. 选择动量最强的前K只股票
        3. 卖出所有当前持仓
        4. 等权重买入新选出的股票
        
        Args:
            date: 交易日期
            available_tickers: 可交易的股票列表
            state: 内部状态
        """
        momentum_state = state['momentum_state']
        lookback_days = momentum_state.get('lookback_days', 20)
        top_n = momentum_state.get('top_n', 3)
        
        # 1. 计算动量得分
        momentum_scores = self._calculate_momentum_scores(date, available_tickers, lookback_days, state)
        
        if not momentum_scores:
            print(f"⚠️ {date} 无法计算动量得分，跳过再平衡")
            return
        
        # 2. 选择动量最强的前N只股票
        sorted_tickers = sorted(momentum_scores.items(), key=lambda x: x[1], reverse=True)
        top_tickers = [ticker for ticker, score in sorted_tickers[:top_n]]
        
        print(f"🔄 动量策略再平衡 ({date}):")
        print(f"   动量排名:")
        for i, (ticker, score) in enumerate(sorted_tickers[:top_n], 1):
            print(f"   {i}. {ticker}: {score*100:+.2f}%")
        
        # 3. 卖出所有当前持仓，回收现金
        current_positions = momentum_state['positions']
        for ticker, position in list(current_positions.items()):
            sell_price = self._get_price_from_csv(ticker, date, 'close')
            if sell_price and sell_price > 0:
                sell_value = position['qty'] * sell_price
                momentum_state['cash'] += sell_value
        
        # 清空持仓
        momentum_state['positions'] = {}
        
        # 4. 等权重买入新选出的股票
        if top_tickers:
            cash_per_ticker = momentum_state['cash'] / len(top_tickers)
            total_invested = 0.0
            
            for ticker in top_tickers:
                buy_price = self._get_price_from_csv(ticker, date, 'close')
                if buy_price is None or buy_price <= 0:
                    print(f"⚠️ {ticker} 在 {date} 没有有效价格，跳过")
                    continue
                
                # 计算可购买的数量（向下取整）
                quantity = int(cash_per_ticker / buy_price)
                
                if quantity > 0:
                    cost = quantity * buy_price
                    momentum_state['positions'][ticker] = {
                        'qty': quantity,
                        'buy_price': buy_price,
                        'buy_date': date
                    }
                    momentum_state['cash'] -= cost
                    total_invested += cost
                    print(f"   买入 {ticker}: {quantity} 股 @ ${buy_price:.2f}")
        
        # 更新状态
        momentum_state['initialized'] = True
        momentum_state['last_rebalance_date'] = date
        
        print(f"✅ 动量策略再平衡完成，剩余现金: ${momentum_state['cash']:,.2f}")
    
    def _calculate_momentum_value(self, date: str, state: Dict) -> float:
        """
        计算动量策略的当前净值
        
        Args:
            date: 当前日期
            state: 内部状态
            
        Returns:
            动量策略的总资产价值（持仓 + 现金）
        """
        momentum_state = state['momentum_state']
        
        if not momentum_state['initialized']:
            return self.initial_cash
        
        # 持仓市值
        positions_value = 0.0
        for ticker, position in momentum_state['positions'].items():
            current_price = self._get_current_price(ticker, date, state)
            if current_price is None or current_price <= 0:
                current_price = position['buy_price']
            positions_value += position['qty'] * current_price
        
        # 总资产 = 持仓市值 + 现金
        total_value = positions_value + momentum_state['cash']
        
        return total_value
    
    def _update_momentum_curve(self, date: str, timestamp_ms: int, 
                               available_tickers: list, state: Dict):
        """
        更新动量策略曲线
        
        Args:
            date: 交易日期
            timestamp_ms: 时间戳（毫秒）
            available_tickers: 可交易的股票列表
            state: 内部状态
        """
        momentum_state = state['momentum_state']
        
        # 判断是否需要再平衡
        if self._should_rebalance_momentum(date, state):
            self._rebalance_momentum_portfolio(date, available_tickers, state)
        
        # 如果动量策略刚初始化，且历史记录为空，先添加初始点
        if momentum_state['initialized'] and len(state['momentum_history']) == 0:
            initial_point = {
                't': timestamp_ms,
                'v': round(self.initial_cash, 2)
            }
            state['momentum_history'].append(initial_point)
            print(f"📊 动量策略初始点: ${self.initial_cash:,.2f}")
        
        # 计算动量策略的当前总价值
        momentum_value = self._calculate_momentum_value(date, state)
        
        # 添加到历史
        momentum_point = {
            't': timestamp_ms,
            'v': round(momentum_value, 2)
        }
        state['momentum_history'].append(momentum_point)
        
        # 计算收益率用于日志显示
        return_pct = ((momentum_value - self.initial_cash) / self.initial_cash) * 100
        print(f"📊 动量策略: ${momentum_value:,.2f} ({return_pct:+.2f}%)")
    
    def _generate_summary(self, state: Dict):
        """生成账户概览数据（使用真实价格）"""
        portfolio_state = state['portfolio_state']
        last_date = state.get('last_update_date')
        all_trades = state.get('all_trades', [])
        
        # 计算当前余额：现金 + 持仓市值（使用最新价格）
        cash = portfolio_state['cash']
        positions_value = 0.0
        ticker_weights = {}  # 记录每个ticker的权重
        
        for ticker, pos in portfolio_state['positions'].items():
            # 使用最新的真实价格
            current_price = self._get_current_price(ticker, last_date, state) if last_date else self.DEFAULT_BASE_PRICE
            position_value = pos['qty'] * current_price
            positions_value += position_value
        
        balance = cash + positions_value
        total_asset_value = balance
        
        # 计算每个ticker的权重
        for ticker, pos in portfolio_state['positions'].items():
            current_price = self._get_current_price(ticker, last_date, state) if last_date else self.DEFAULT_BASE_PRICE
            position_value = pos['qty'] * current_price
            weight = (position_value / total_asset_value) if total_asset_value > 0 else 0
            ticker_weights[ticker] = round(weight, 4)
        
        # 计算总收益率
        total_return = ((balance - self.initial_cash) / self.initial_cash) * 100
        
        summary = {
            'totalAssetValue': round(total_asset_value, 2),
            'totalReturn': round(total_return, 2),
            'cashPosition': round(cash, 2),
            'tickerWeights': ticker_weights,
            'totalTrades': len(all_trades),  # 修复：使用all_trades的长度
            # 保留旧字段以兼容
            'pnlPct': round(total_return, 2),
            'balance': round(balance, 2),
            'equity': state.get('equity_history', []),
            'baseline': state.get('baseline_history', []),
            'baseline_vw': state.get('baseline_vw_history', []),  # 价值加权基准线
            'momentum': state.get('momentum_history', [])  # 添加动量策略数据
        }
        
        self._save_json(self.summary_file, summary)
    
    def _generate_holdings(self, state: Dict):
        """生成持仓信息"""
        portfolio_state = state['portfolio_state']
        positions = portfolio_state['positions']
        cash = portfolio_state['cash']
        last_date = state.get('last_update_date')
        
        print(f"\n🔍 生成 Holdings 数据 (日期: {last_date}):")
        
        # 计算总价值用于计算权重（使用真实价格）
        total_value = cash
        for ticker, pos in positions.items():
            current_price = self._get_current_price(ticker, last_date, state) if last_date else self.DEFAULT_BASE_PRICE
            total_value += pos['qty'] * current_price
        
        holdings = []
        # 添加股票持仓
        for ticker, pos in positions.items():
            qty = pos['qty']
            
            # 使用真实的当前价格
            current_price = self._get_current_price(ticker, last_date, state) if last_date else self.DEFAULT_BASE_PRICE
            
            # 计算当前市值
            market_value = qty * current_price
            
            # 计算权重
            weight = abs(market_value) / total_value if total_value > 0 else 0
            
            print(f"   {ticker}: 数量={qty}, 当前价=${current_price:.2f}, 市值=${market_value:.2f}, 权重={weight:.2%}")
            
            holdings.append({
                'ticker': ticker,
                'quantity': qty,
                'currentPrice': round(current_price, 2),
                'marketValue': round(market_value, 2),
                'weight': round(weight, 4)
            })
        # 添加现金作为一个持仓项
        cash_weight = cash / total_value if total_value > 0 else 0
        holdings.append({
            'ticker': 'CASH',
            'quantity': 1,
            'currentPrice': round(cash, 2),
            'marketValue': round(cash, 2),
            'weight': round(cash_weight, 4)
            })
        
        # 按权重排序
        holdings.sort(key=lambda x: abs(x['weight']), reverse=True)
        
        self._save_json(self.holdings_file, holdings)
    
    def _generate_stats(self, state: Dict):
        """生成统计数据（Portfolio Manager表现 + Overview数据）"""
        pm_perf = state.get('agent_performance', {}).get('portfolio_manager', {})
        portfolio_state = state['portfolio_state']
        last_date = state.get('last_update_date')
        all_trades = state.get('all_trades', [])
        
        bull_count = pm_perf.get('bull_count', 0)
        bull_win = pm_perf.get('bull_win', 0)
        bear_count = pm_perf.get('bear_count', 0)
        bear_win = pm_perf.get('bear_win', 0)
        
        total_count = bull_count + bear_count
        total_win = bull_win + bear_win
        
        win_rate = total_win / total_count if total_count > 0 else 0
        
        # 计算Overview数据（和summary中一样）
        cash = portfolio_state['cash']
        positions_value = 0.0
        ticker_weights = {}
        
        for ticker, pos in portfolio_state['positions'].items():
            current_price = self._get_current_price(ticker, last_date, state) if last_date else self.DEFAULT_BASE_PRICE
            position_value = pos['qty'] * current_price
            positions_value += position_value
        
        total_asset_value = cash + positions_value
        
        # 计算每个ticker的权重
        for ticker, pos in portfolio_state['positions'].items():
            current_price = self._get_current_price(ticker, last_date, state) if last_date else self.DEFAULT_BASE_PRICE
            position_value = pos['qty'] * current_price
            weight = (position_value / total_asset_value) if total_asset_value > 0 else 0
            ticker_weights[ticker] = round(weight, 4)
        
        total_return = ((total_asset_value - self.initial_cash) / self.initial_cash) * 100
        
        stats = {
            # Overview数据
            'totalAssetValue': round(total_asset_value, 2),
            'totalReturn': round(total_return, 2),
            'cashPosition': round(cash, 2),
            'tickerWeights': ticker_weights,
            'totalTrades': len(all_trades),
            # Performance数据
            'winRate': round(win_rate, 2),
            'bullBear': {
                'bull': {
                    'n': bull_count,
                    'win': bull_win
                },
                'bear': {
                    'n': bear_count,
                    'win': bear_win
                }
            }
        }
        
        self._save_json(self.stats_file, stats)
    
    def _generate_trades(self, state: Dict):
        """生成交易记录"""
        all_trades = state.get('all_trades', [])
        
        # 按时间倒序排序（最新的在前）
        sorted_trades = sorted(all_trades, key=lambda x: x['ts'], reverse=True)
        
        # 限制数量（例如最近100笔）并格式化输出
        trades = []
        for trade in sorted_trades[:100]:
            # 创建新的trade对象，去掉pnl字段
            formatted_trade = {
                'id': trade.get('id'),
                'timestamp': trade.get('ts'),  # 保持毫秒时间戳，前端会格式化
                'side': trade.get('side'),
                'ticker': trade.get('ticker'),
                'qty': trade.get('qty'),
                'price': trade.get('price')
            }
            trades.append(formatted_trade)
        
        self._save_json(self.trades_file, trades)
    
    def _generate_leaderboard(self, state: Dict):
        """生成AI Agent排行榜"""
        agent_performance = state.get('agent_performance', {})
        
        leaderboard = []
        
        for agent_id, perf in agent_performance.items():
            # 计算胜率
            bull_count = perf.get('bull_count', 0)
            bull_win = perf.get('bull_win', 0)
            bull_unknown = perf.get('bull_unknown', 0)
            bear_count = perf.get('bear_count', 0)
            bear_win = perf.get('bear_win', 0)
            bear_unknown = perf.get('bear_unknown', 0)
            
            evaluated_bull = max(bull_count - bull_unknown, 0)
            evaluated_bear = max(bear_count - bear_unknown, 0)
            total_count = bull_count + bear_count
            total_win = bull_win + bear_win
            evaluated_total = evaluated_bull + evaluated_bear
            win_rate = (total_win / evaluated_total) if evaluated_total > 0 else None
            
            # 获取agent配置
            agent_config = self.AGENT_CONFIG.get(agent_id, {
                'name': agent_id,
                'role': agent_id,
                'avatar': 'default'
            })
            
            leaderboard.append({
                'agentId': agent_id,
                'name': agent_config['name'],
                'role': agent_config['role'],
                'avatar': agent_config['avatar'],
                'rank': 0,  # 稍后填充
                'winRate': round(win_rate, 4) if win_rate is not None else None,
                'bull': {
                    'n': bull_count,
                    'win': bull_win,
                    'unknown': bull_unknown
                },
                'bear': {
                    'n': bear_count,
                    'win': bear_win,
                    'unknown': bear_unknown
                },
                'logs': perf.get('logs', []),  # 前10条日志
                'signals': perf.get('signals', [])  # 完整的信号历史记录（包含日期）
            })
        
        # 按胜率排序，胜率相同时 Portfolio Manager 排在前面
        leaderboard.sort(key=lambda x: (
            0 if x['winRate'] is not None else 1,  # 有效胜率优先
            -(x['winRate'] if x['winRate'] is not None else 0),  # 胜率降序
            0 if x['agentId'] == 'portfolio_manager' else 1  # PM优先
        ))
        
        # 填充排名
        for i, agent in enumerate(leaderboard, 1):
            agent['rank'] = i
        
        self._save_json(self.leaderboard_file, leaderboard)
    
    def initialize_empty_dashboard(self):
        """初始化空的仪表盘数据文件"""
        # Summary
        self._save_json(self.summary_file, {
            'pnlPct': 0.0,
            'balance': self.initial_cash,
            'equity': []
        })
        
        # Holdings
        self._save_json(self.holdings_file, [])
        
        # Stats
        self._save_json(self.stats_file, {
            'totalAssetValue': self.initial_cash,
            'totalReturn': 0.0,
            'cashPosition': self.initial_cash,
            'tickerWeights': {},
            'totalTrades': 0,
            'winRate': 0.0,
            'bullBear': {
                'bull': {'n': 0, 'win': 0},
                'bear': {'n': 0, 'win': 0}
            }
        })
        
        # Trades
        self._save_json(self.trades_file, [])
        
        # Leaderboard
        leaderboard = []
        for agent_id, config in self.AGENT_CONFIG.items():
            leaderboard.append({
                'agentId': agent_id,
                'name': config['name'],
                'role': config['role'],
                'avatar': config['avatar'],
                'rank': 0,
                'winRate': 0.0,
                'bull': {'n': 0, 'win': 0},
                'bear': {'n': 0, 'win': 0},
                'logs': []
            })
        self._save_json(self.leaderboard_file, leaderboard)
        
        print(f"✅ 团队仪表盘已初始化: {self.dashboard_dir}")

