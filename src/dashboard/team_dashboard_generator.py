#!/usr/bin/env python3
"""
团队仪表盘数据生成器
为前端提供5个主要数据接口：summary, holdings, stats, trades, leaderboard
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
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
            'all_trades': [],  # 所有交易历史
            'agent_performance': {},  # agent_id -> {signals: [], bull_count: 0, bull_win: 0, ...}
            'portfolio_state': {  # 当前持仓状态
                'cash': self.initial_cash,
                'positions': {}  # ticker -> {qty, avg_cost}
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
            df['Date'] = pd.to_datetime(df['Date'])
            
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
        if pre_market_result.get('status') != 'success':
            print(f"⚠️ {date} 交易前分析未成功，跳过仪表盘更新")
            return {'status': 'skipped', 'reason': 'pre_market not successful'}
        
        # 加载内部状态
        state = self._load_internal_state()
        
        # 提取数据
        pm_signals = pre_market_result.get('signals', {})
        live_env = pre_market_result.get('live_env', {})
        real_returns = live_env.get('real_returns', {})
        ana_signals = live_env.get('ana_signals', {})
        
        # 时间戳（使用交易日的时间戳）
        date_obj = datetime.strptime(date, "%Y-%m-%d")
        timestamp_ms = int(date_obj.timestamp() * 1000)
        
        update_stats = {
            'date': date,
            'mode': mode,
            'trades_added': 0,
            'agents_updated': 0
        }
        
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
        
        # 5. 更新权益曲线
        self._update_equity_curve(date, timestamp_ms, state)
        
        # 5. 保存内部状态
        state['last_update_date'] = date
        self._save_internal_state(state)
        
        # 6. 生成所有前端数据文件
        self._generate_summary(state)
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
                real_return = real_returns.get(ticker, 0)
                
                # 计算该笔交易的P&L
                pnl = 0.0
                if action in ['buy', 'cover']:
                    # 买入类操作，P&L基于当日收益
                    pnl = quantity * price * real_return
                elif action in ['sell', 'short']:
                    # 卖出类操作
                    if action == 'sell':
                        # 卖出：基于成本差
                        cost_basis = portfolio_state.get('positions', {}).get(ticker, {}).get('avg_cost', price)
                        pnl = quantity * (price - cost_basis)
                    else:
                        # 空头建仓：P&L为负的收益
                        pnl = -quantity * price * real_return
                
                # 映射action到side
                side_map = {
                    'buy': 'BUY',
                    'sell': 'SELL',
                    'short': 'SHORT',
                    'cover': 'COVER'
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
            
            if action == 'hold':
                continue
            
            # 获取当前价格
            price = self._get_ticker_price(ticker, date, signal_info, portfolio_state, real_returns)
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
            
            # 计算P&L
            pnl = quantity * price * real_returns.get(ticker, 0)
            
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
                    'bear_count': 0,
                    'bear_win': 0,
                    'neutral_count': 0,
                    'logs': []
                }
            
            agent_perf = state['agent_performance'][agent_id]
            
            for ticker, signal in signals.items():
                if not signal or signal == 'N/A':
                    continue
                
                real_return = real_returns.get(ticker, 0)
                
                # 判断信号类型和正确性
                signal_lower = signal.lower()
                is_bull = 'bull' in signal_lower
                is_bear = 'bear' in signal_lower
                is_neutral = 'neutral' in signal_lower or signal_lower == 'hold'
                
                # 判断是否正确（简化：涨跌与信号一致）
                is_correct = False
                if is_bull and real_return > 0:
                    is_correct = True
                    agent_perf['bull_count'] += 1
                    agent_perf['bull_win'] += 1
                elif is_bull and real_return <= 0:
                    agent_perf['bull_count'] += 1
                elif is_bear and real_return < 0:
                    is_correct = True
                    agent_perf['bear_count'] += 1
                    agent_perf['bear_win'] += 1
                elif is_bear and real_return >= 0:
                    agent_perf['bear_count'] += 1
                elif is_neutral:
                    agent_perf['neutral_count'] += 1
                    # neutral不计入胜率
                
                # 记录信号
                signal_record = {
                    'date': date,
                    'ticker': ticker,
                    'signal': signal,
                    'real_return': real_return,
                    'is_correct': is_correct
                }
                agent_perf['signals'].append(signal_record)
                
                # 更新日志（保留最近50条）
                log_entry = f"{'Bull' if is_bull else 'Bear' if is_bear else 'Neutral'} on {ticker} {'✓' if is_correct else '✗' if not is_neutral else ''}"
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
                'bear_count': 0,
                'bear_win': 0,
                'neutral_count': 0,
                'logs': []
            }
        
        pm_perf = state['agent_performance'][agent_id]
        
        for ticker, signal_info in pm_signals.items():
            signal = signal_info.get('signal', 'neutral')
            real_return = real_returns.get(ticker, 0)
            
            signal_lower = signal.lower()
            is_bull = 'bull' in signal_lower
            is_bear = 'bear' in signal_lower
            is_neutral = 'neutral' in signal_lower or signal_lower == 'hold'
            
            is_correct = False
            if is_bull and real_return > 0:
                is_correct = True
                pm_perf['bull_count'] += 1
                pm_perf['bull_win'] += 1
            elif is_bull and real_return <= 0:
                pm_perf['bull_count'] += 1
            elif is_bear and real_return < 0:
                is_correct = True
                pm_perf['bear_count'] += 1
                pm_perf['bear_win'] += 1
            elif is_bear and real_return >= 0:
                pm_perf['bear_count'] += 1
            elif is_neutral:
                pm_perf['neutral_count'] += 1
            
            signal_record = {
                'date': date,
                'ticker': ticker,
                'signal': signal,
                'real_return': real_return,
                'is_correct': is_correct
            }
            pm_perf['signals'].append(signal_record)
            
            log_entry = f"{'Bull' if is_bull else 'Bear' if is_bear else 'Neutral'} on {ticker} {'✓' if is_correct else '✗' if not is_neutral else ''}"
            pm_perf['logs'].insert(0, log_entry)
            pm_perf['logs'] = pm_perf['logs'][:50]
    
    def _update_equity_curve(self, date: str, timestamp_ms: int, state: Dict):
        """更新权益曲线（使用真实价格）"""
        portfolio_state = state['portfolio_state']
        
        # 计算当前总价值：现金 + 持仓市值（使用真实价格）
        cash = portfolio_state['cash']
        positions_value = 0.0
        
        for ticker, pos in portfolio_state['positions'].items():
            # 使用当日真实价格
            current_price = self._get_current_price(ticker, date, state)
            positions_value += pos['qty'] * current_price
        
        total_value = cash + positions_value
        
        # 归一化为百分比（相对初始资金）
        normalized_value = (total_value / self.initial_cash) * 100
        
        # 添加到权益曲线
        equity_point = {
            't': timestamp_ms,
            'v': round(normalized_value, 2)
        }
        state['equity_history'].append(equity_point)
        
        # 记录总价值历史
        state['total_value_history'].append({
            'date': date,
            'total_value': total_value
        })
    
    def _generate_summary(self, state: Dict):
        """生成账户概览数据（使用真实价格）"""
        portfolio_state = state['portfolio_state']
        last_date = state.get('last_update_date')
        
        # 计算当前余额：现金 + 持仓市值（使用最新价格）
        cash = portfolio_state['cash']
        positions_value = 0.0
        
        for ticker, pos in portfolio_state['positions'].items():
            # 使用最新的真实价格
            current_price = self._get_current_price(ticker, last_date, state) if last_date else self.DEFAULT_BASE_PRICE
            positions_value += pos['qty'] * current_price
        
        balance = cash + positions_value
        
        # 计算总收益率
        pnl_pct = ((balance - self.initial_cash) / self.initial_cash) * 100
        
        summary = {
            'pnlPct': round(pnl_pct, 2),
            'balance': round(balance, 2),
            'equity': state.get('equity_history', [])
        }
        
        self._save_json(self.summary_file, summary)
    
    def _generate_holdings(self, state: Dict):
        """生成持仓信息（通过累积trades的pnl计算P&L）"""
        portfolio_state = state['portfolio_state']
        positions = portfolio_state['positions']
        last_date = state.get('last_update_date')
        all_trades = state.get('all_trades', [])
        
        # 按ticker累积所有交易的pnl
        ticker_pnl = {}
        for trade in all_trades:
            ticker = trade['ticker']
            pnl = trade.get('pnl', 0)
            if ticker not in ticker_pnl:
                ticker_pnl[ticker] = 0
            ticker_pnl[ticker] += pnl
        
        # 计算总价值用于计算权重（使用真实价格）
        total_value = portfolio_state['cash']
        for ticker, pos in positions.items():
            current_price = self._get_current_price(ticker, last_date, state) if last_date else self.DEFAULT_BASE_PRICE
            total_value += pos['qty'] * current_price
        
        holdings = []
        for ticker, pos in positions.items():
            qty = pos['qty']
            avg_cost = pos['avg_cost']
            
            # 使用真实的当前价格
            current_price = self._get_current_price(ticker, last_date, state) if last_date else self.DEFAULT_BASE_PRICE
            
            # 使用累积的交易pnl作为P&L
            pl = ticker_pnl.get(ticker, 0)
            
            # 计算权重
            position_value = abs(qty) * current_price
            weight = position_value / total_value if total_value > 0 else 0
            
            holdings.append({
                'ticker': ticker,
                'qty': qty,
                'avg': round(avg_cost, 2),
                'pl': round(pl, 2),
                'weight': round(weight, 2)
            })
        
        # 按权重排序
        holdings.sort(key=lambda x: abs(x['weight']), reverse=True)
        
        self._save_json(self.holdings_file, holdings)
    
    def _generate_stats(self, state: Dict):
        """生成统计数据（Portfolio Manager表现）"""
        pm_perf = state.get('agent_performance', {}).get('portfolio_manager', {})
        
        bull_count = pm_perf.get('bull_count', 0)
        bull_win = pm_perf.get('bull_win', 0)
        bear_count = pm_perf.get('bear_count', 0)
        bear_win = pm_perf.get('bear_win', 0)
        
        total_count = bull_count + bear_count
        total_win = bull_win + bear_win
        
        win_rate = total_win / total_count if total_count > 0 else 0
        hit_rate = win_rate  # 简化：命中率=胜率
        
        stats = {
            'winRate': round(win_rate, 2),
            'hitRate': round(hit_rate, 2),
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
        
        # 限制数量（例如最近100笔）
        trades = sorted_trades[:100]
        
        self._save_json(self.trades_file, trades)
    
    def _generate_leaderboard(self, state: Dict):
        """生成AI Agent排行榜"""
        agent_performance = state.get('agent_performance', {})
        
        leaderboard = []
        
        for agent_id, perf in agent_performance.items():
            # 计算胜率
            bull_count = perf.get('bull_count', 0)
            bull_win = perf.get('bull_win', 0)
            bear_count = perf.get('bear_count', 0)
            bear_win = perf.get('bear_win', 0)
            
            total_count = bull_count + bear_count
            total_win = bull_win + bear_win
            win_rate = total_win / total_count if total_count > 0 else 0
            
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
                'winRate': round(win_rate, 2),
                'bull': {
                    'n': bull_count,
                    'win': bull_win
                },
                'bear': {
                    'n': bear_count,
                    'win': bear_win
                },
                'logs': perf.get('logs', [])[:10]  # 前10条日志
            })
        
        # 按胜率排序
        leaderboard.sort(key=lambda x: x['winRate'], reverse=True)
        
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
            'winRate': 0.0,
            'hitRate': 0.0,
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

