# src/servers/live_server.py
"""
在线模式服务器 - Live Trading System
功能：
1. 直接运行今天的实时交易决策分析
2. 高频获取实时价格，更新净值曲线、持仓盈亏等
3. 支持Mock模式用于非交易时段测试
"""
import asyncio
import json
import logging
import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime, timedelta, time as datetime_time
from typing import Set, Dict, Any, Optional, Tuple, List
from dotenv import load_dotenv
import pdb
BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))
from src.config.path_config import get_logs_and_memory_dir

import websockets
from websockets.server import WebSocketServerProtocol
from websockets.exceptions import ConnectionClosedError

from src.memory import get_memory
from src.servers.streamer import BroadcastStreamer
from src.servers.polling_price_manager import PollingPriceManager
from src.servers.mock_price_manager import MockPriceManager
from src.servers.state_manager import StateManager
from live_trading_fund import LiveTradingFund
from src.config.env_config import LiveThinkingFundConfig
from src.tools.data_tools import get_prices
from src.utils.virtual_clock import VirtualClock, init_virtual_clock, get_virtual_clock


import pandas_market_calendars as mcal
_NYSE_CALENDAR = mcal.get_calendar('NYSE')


load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class LiveTradingServer:
    """在线交易服务器"""
    
    def __init__(self, config: LiveThinkingFundConfig, mock_mode: bool = False, pause_before_trade: bool = False, time_accelerator: float = 1.0, virtual_start_time: Optional[datetime] = None):
        self.config = config
        self.mock_mode = mock_mode
        self.pause_before_trade = pause_before_trade
        self.time_accelerator = time_accelerator  # 时间加速器，用于调试（1.0=正常，60.0=1分钟当1小时）
        self.virtual_start_time = virtual_start_time  # 虚拟起始时间（用于Mock模式回测）
        self.connected_clients: Set[WebSocketServerProtocol] = set()
        self.lock = asyncio.Lock()
        self.loop = None
        
        # 初始化虚拟时钟（Mock模式下启用）
        if mock_mode and time_accelerator != 1.0:
            init_virtual_clock(
                start_time=virtual_start_time,
                time_accelerator=time_accelerator,
                enabled=True
            )
            logger.info(f"🕐 虚拟时钟已启用: 加速 {time_accelerator}x, 起始时间: {virtual_start_time or '当前时间'}")
        else:
            init_virtual_clock(enabled=False)
        
        self.vclock = get_virtual_clock()
        
        # Dashboard 文件路径
        self.dashboard_dir = get_logs_and_memory_dir() / config.config_name / "sandbox_logs" / "team_dashboard"
        self.dashboard_files = {
            'summary': self.dashboard_dir / 'summary.json',
            'holdings': self.dashboard_dir / 'holdings.json',
            'stats': self.dashboard_dir / 'stats.json',
            'trades': self.dashboard_dir / 'trades.json',
            'leaderboard': self.dashboard_dir / 'leaderboard.json'
        }
        self.dashboard_file_mtimes = {}
        logger.info(f"✅ Dashboard 文件目录: {self.dashboard_dir}")
        
        self.internal_state_file = self.dashboard_dir / '_internal_state.json'
        self.internal_state = self._load_internal_state()
        self.latest_prices: Dict[str, float] = {}
        
        # 使用StateManager管理状态
        self.state_manager = StateManager(
            config_name=config.config_name,
            base_dir=BASE_DIR,
            max_history=200
        )
        
        # 初始化portfolio状态
        self.state_manager.update('portfolio', {
            'total_value': config.initial_cash,
            'cash': config.initial_cash,
            'pnl_percent': 0,
            'equity': [],
            'baseline': [],
            'baseline_vw': [],
            'momentum': [],
            'strategies': []
        })
        
        # 初始化价格管理器
        if mock_mode:
            logger.info("🎭 使用Mock价格管理器（测试模式）")
            self.price_manager = MockPriceManager(poll_interval=5, volatility=0.5)
        else:
            api_key = os.getenv('FINNHUB_API_KEY', '')
            if not api_key:
                logger.error("❌ 未找到 FINNHUB_API_KEY，无法使用实时价格功能")
                logger.info("   请在 .env 文件中设置 FINNHUB_API_KEY")
                logger.info("   获取免费 API Key: https://finnhub.io/register")
                raise ValueError("缺少 FINNHUB_API_KEY")
            
            # 使用高频轮询（10秒一次）
            logger.info("📊 使用Finnhub实时价格（高频轮询: 10秒）")
            self.price_manager = PollingPriceManager(api_key, poll_interval=10)
        
        # 添加价格更新回调
        self.price_manager.add_price_callback(self._on_price_update)
        
        # 记录初始资金（用于计算收益率）
        self.initial_cash = config.initial_cash
        
        # 初始化记忆系统
        memory_instance = get_memory(config.config_name)
        logger.info(f"✅ 记忆系统已初始化")
        
        # 记忆系统初始化完成（不需要预注册分析师）
        logger.info("✅ 记忆系统准备就绪")
        
        # 初始化交易系统
        self.thinking_fund = None
        
        # 在线模式状态
        self.current_phase = "backtest"  # backtest, live_analysis, live_monitoring
        self.is_today = False
        self.market_is_open = False
        self.last_trading_date = None  # 记录上次执行交易的日期
        self.last_executed_date = None  # 记录上次实际执行交易的美国日期（用于判断是否跨天）
        self.trading_executed_today = False  # 标记今天是否已执行交易
        self.analysis_executed_today = False  # 标记今天是否已执行盘前分析
        
        # 保存每天的信号和结果，用于第二天更新 agent perf
        self.daily_signals = {}  # {date: {'ana_signals': ..., 'pm_signals': ...}}
    
    def _on_price_update(self, price_data: Dict[str, Any]):
        """价格更新回调 - 直接更新 holdings.json 和 stats.json 文件"""
        symbol = price_data['symbol']
        price = price_data['price']
        open_price = price_data.get('open', price)
        
        # 计算相对开盘价的return
        ret = ((price - open_price) / open_price) * 100 if open_price > 0 else 0
        
        # 更新当前状态（用于价格板显示）
        realtime_prices = self.state_manager.get('realtime_prices', {})
        realtime_prices[symbol] = {
            'price': price,
            'open': open_price,
            'ret': ret,
            'timestamp': price_data.get('timestamp'),
            'volume': price_data.get('volume')
        }
        self.state_manager.update('realtime_prices', realtime_prices)
        self.latest_prices[symbol] = price
        self._cache_internal_price(symbol, price)
        
        # 广播价格更新（用于价格板实时显示）
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.broadcast({
                    'type': 'price_update',
                    'symbol': symbol,
                    'price': price,
                    'open': open_price,
                    'ret': ret,
                    'timestamp': price_data.get('timestamp'),
                    'realtime_prices': realtime_prices
                }),
                self.loop
            )
        
        # 更新 holdings.json 和 stats.json 文件
        try:
            self._update_dashboard_files_with_price(symbol, price)
        except Exception as e:
            logger.error(f"更新 Dashboard 文件失败 ({symbol}): {e}")
    
    def _get_current_time_for_data(self) -> datetime:
        """
        获取用于数据记录的当前时间
        Mock模式下使用virtual time，否则使用真实时间
        """
        if self.mock_mode and self.vclock.enabled:
            return self.vclock.now()
        else:
            return datetime.now()
    
    def _get_current_timestamp_ms_for_data(self) -> int:
        """
        获取用于数据记录的时间戳（毫秒）
        Mock模式下使用virtual time，否则使用真实时间
        """
        current_time = self._get_current_time_for_data()
        return int(current_time.timestamp() * 1000)
    
    def _update_dashboard_files_with_price(self, symbol: str, price: float):
        """更新 holdings.json、stats.json 和 summary.json 文件中的价格和相关计算"""
        holdings_file = self.dashboard_files.get('holdings')
        stats_file = self.dashboard_files.get('stats')
        summary_file = self.dashboard_files.get('summary')
        
        if not holdings_file or not holdings_file.exists():
            logger.warning(f"holdings.json 文件不存在，跳过更新")
            return
        
        if not stats_file or not stats_file.exists():
            logger.warning(f"stats.json 文件不存在，跳过更新")
            return
        
        # 读取 holdings.json
        try:
            with open(holdings_file, 'r', encoding='utf-8') as f:
                holdings = json.load(f)
        except Exception as e:
            logger.error(f"读取 holdings.json 失败: {e}")
            return
        
        # 读取 stats.json
        try:
            with open(stats_file, 'r', encoding='utf-8') as f:
                stats = json.load(f)
        except Exception as e:
            logger.error(f"读取 stats.json 失败: {e}")
            return
        
        # 读取 summary.json（如果存在）
        summary = None
        if summary_file and summary_file.exists():
            try:
                with open(summary_file, 'r', encoding='utf-8') as f:
                    summary = json.load(f)
            except Exception as e:
                logger.error(f"读取 summary.json 失败: {e}")
        
        # 更新 holdings 中的价格
        updated = False
        total_value = 0.0
        cash = 0.0
        
        for holding in holdings:
            ticker = holding.get('ticker')
            quantity = holding.get('quantity', 0)
            
            if ticker == 'CASH':
                cash = holding.get('marketValue', 0)
                total_value += cash
            elif ticker == symbol:
                # 更新当前价格
                holding['currentPrice'] = round(price, 2)
                market_value = quantity * price
                holding['marketValue'] = round(market_value, 2)
                total_value += market_value
                updated = True
            else:
                # 累加其他持仓的市值
                total_value += holding.get('marketValue', 0)
        
        # 重新计算权重
        if total_value > 0:
            for holding in holdings:
                market_value = holding.get('marketValue', 0)
                weight = market_value / total_value
                holding['weight'] = round(weight, 4)
        
        # 如果有更新，保存 holdings.json
        if updated:
            try:
                with open(holdings_file, 'w', encoding='utf-8') as f:
                    json.dump(holdings, f, indent=2, ensure_ascii=False)
                logger.debug(f"✅ 已更新 holdings.json: {symbol} = ${price:.2f}")
            except Exception as e:
                logger.error(f"保存 holdings.json 失败: {e}")
                return
        
        # 更新 stats.json
        total_return = ((total_value - self.initial_cash) / self.initial_cash * 100) if self.initial_cash > 0 else 0.0
        
        # 更新 tickerWeights
        ticker_weights = {}
        for holding in holdings:
            ticker = holding.get('ticker')
            if ticker != 'CASH':
                ticker_weights[ticker] = holding.get('weight', 0)
        
        stats['totalAssetValue'] = round(total_value, 2)
        stats['totalReturn'] = round(total_return, 2)
        stats['cashPosition'] = round(cash, 2)
        stats['tickerWeights'] = ticker_weights
        
        # 保存 stats.json
        try:
            with open(stats_file, 'w', encoding='utf-8') as f:
                json.dump(stats, f, indent=2, ensure_ascii=False)
            if updated:
                logger.debug(f"✅ 已更新 stats.json: 总资产=${total_value:.2f}, 收益率={total_return:.2f}%")
        except Exception as e:
            logger.error(f"保存 stats.json 失败: {e}")
        
        summary_changed = False
        current_time = None
        
        if summary:
            try:
                # 使用virtual time（mock模式下）或真实时间
                current_time = self._get_current_timestamp_ms_for_data()
                
                if updated:
                    summary['balance'] = round(total_value, 2)
                    summary['totalAssetValue'] = round(total_value, 2)
                    summary['pnlPct'] = round(total_return, 2)
                    summary['totalReturn'] = round(total_return, 2)
                    summary['cashPosition'] = round(cash, 2)
                    summary['tickerWeights'] = ticker_weights
                    
                    equity_list = summary.get('equity', [])
                    equity_list.append({
                        't': current_time,
                        'v': round(total_value, 2)
                    })
                    if len(equity_list) > 1000:
                        equity_list = equity_list[-1000:]
                    summary['equity'] = equity_list
                    summary_changed = True
                
                if self._update_benchmark_curves(summary, current_time):
                    summary_changed = True
                
                if summary_changed:
                    with open(summary_file, 'w', encoding='utf-8') as f:
                        json.dump(summary, f, indent=2, ensure_ascii=False)
                    self._save_internal_state()
            except Exception as e:
                logger.error(f"更新 summary.json 失败: {e}")
    
    def _load_internal_state(self) -> Dict[str, Any]:
        """
        读取并标准化团队仪表盘内部状态，确保关键字段存在
        """
        default_state = {
            'baseline_state': {'initialized': False, 'initial_allocation': {}},
            'baseline_vw_state': {'initialized': False, 'initial_allocation': {}},
            'momentum_state': {'positions': {}, 'cash': 0.0, 'initialized': False},
            'baseline_history': [],
            'baseline_vw_history': [],
            'momentum_history': [],
            'price_history': {},
        }
        
        if not self.dashboard_dir.exists():
            self.dashboard_dir.mkdir(parents=True, exist_ok=True)
        
        if not self.internal_state_file.exists():
            return default_state
        
        try:
            with open(self.internal_state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            logger.warning(f"⚠️ 无法读取内部状态文件，使用默认值: {e}")
            return default_state
        
        for key, value in default_state.items():
            data.setdefault(key, value)
        return data
    
    def _save_internal_state(self):
        """
        将更新后的内部状态写回磁盘
        """
        if not self.internal_state:
            return
        try:
            with open(self.internal_state_file, 'w', encoding='utf-8') as f:
                json.dump(self.internal_state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存内部状态失败: {e}")
    
    def _cache_internal_price(self, symbol: str, price: float):
        """
        将最新价格写入内部状态的 price_history，便于基准估值
        """
        if not self.internal_state:
            return
        price_history = self.internal_state.setdefault('price_history', {})
        ticker_history = price_history.setdefault(symbol, {})
        # 使用virtual time（mock模式下）或真实时间
        current_time = self._get_current_time_for_data()
        today = current_time.strftime("%Y-%m-%d")
        ticker_history[today] = price
    
    def _get_price_for_benchmark(self, ticker: str, fallback: Optional[float] = None) -> Optional[float]:
        """
        获取用于基准估值的最新价格
        """
        if ticker in self.latest_prices:
            return self.latest_prices[ticker]
        
        price_history = self.internal_state.get('price_history', {})
        ticker_history = price_history.get(ticker, {})
        if ticker_history:
            # 取最近日期的数据
            latest_date = sorted(ticker_history.keys())[-1]
            return ticker_history[latest_date]
        
        return fallback
    
    def _append_curve_point(self, history: List[Dict[str, Any]], timestamp_ms: int, value: float) -> List[Dict[str, Any]]:
        """
        追加曲线节点并保持长度限制
        """
        history.append({'t': timestamp_ms, 'v': round(value, 2)})
        if len(history) > 1000:
            del history[:len(history) - 1000]
        return history
    
    def _update_benchmark_curves(self, summary: Dict[str, Any], timestamp_ms: int) -> bool:
        """
        根据最新价格更新基准/策略曲线
        """
        if not self.internal_state:
            return False
        
        changed = False
        
        baseline_state = self.internal_state.get('baseline_state', {})
        if baseline_state.get('initialized') and baseline_state.get('initial_allocation'):
            total_value = 0.0
            missing_price = False
            for ticker, alloc in baseline_state['initial_allocation'].items():
                price = self._get_price_for_benchmark(ticker, alloc.get('buy_price'))
                if price is None:
                    missing_price = True
                    break
                total_value += alloc.get('qty', 0) * price
            if not missing_price:
                history = self._append_curve_point(self.internal_state.setdefault('baseline_history', []), timestamp_ms, total_value)
                summary['baseline'] = history
                changed = True
        
        baseline_vw_state = self.internal_state.get('baseline_vw_state', {})
        if baseline_vw_state.get('initialized') and baseline_vw_state.get('initial_allocation'):
            total_value = 0.0
            missing_price = False
            for ticker, alloc in baseline_vw_state['initial_allocation'].items():
                price = self._get_price_for_benchmark(ticker, alloc.get('buy_price'))
                if price is None:
                    missing_price = True
                    break
                total_value += alloc.get('qty', 0) * price
            if not missing_price:
                history = self._append_curve_point(self.internal_state.setdefault('baseline_vw_history', []), timestamp_ms, total_value)
                summary['baseline_vw'] = history
                changed = True
        
        momentum_state = self.internal_state.get('momentum_state', {})
        if momentum_state.get('initialized'):
            total_value = momentum_state.get('cash', 0.0)
            missing_price = False
            for ticker, pos in momentum_state.get('positions', {}).items():
                price = self._get_price_for_benchmark(ticker, pos.get('buy_price'))
                if price is None:
                    missing_price = True
                    break
                total_value += pos.get('qty', 0) * price
            if not missing_price:
                history = self._append_curve_point(self.internal_state.setdefault('momentum_history', []), timestamp_ms, total_value)
                summary['momentum'] = history
                changed = True
        
        return changed
    
    async def broadcast(self, message: Dict[str, Any]):
        """广播消息给所有连接的客户端"""
        self.state_manager.add_feed_message(message)
        
        if not self.connected_clients:
            return
        
        message_json = json.dumps(message, ensure_ascii=False, default=str)
        
        tasks = []
        async with self.lock:
            for client in self.connected_clients.copy():
                tasks.append(self._send_to_client(client, message_json))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _send_to_client(self, client: WebSocketServerProtocol, message: str):
        """发送消息给单个客户端"""
        try:
            await client.send(message)
        except websockets.ConnectionClosed:
            async with self.lock:
                self.connected_clients.discard(client)
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
    
    def _load_dashboard_file(self, file_type: str) -> Any:
        """读取 Dashboard JSON 文件"""
        file_path = self.dashboard_files.get(file_type)
        if not file_path or not file_path.exists():
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"读取 Dashboard 文件失败 ({file_type}): {e}")
            return None
    
    def _check_dashboard_files_updated(self) -> Dict[str, bool]:
        """检查哪些 Dashboard 文件被更新了"""
        updated = {}
        
        for file_type, file_path in self.dashboard_files.items():
            if not file_path.exists():
                updated[file_type] = False
                continue
            
            try:
                current_mtime = file_path.stat().st_mtime
                last_mtime = self.dashboard_file_mtimes.get(file_type, 0)
                
                if current_mtime > last_mtime:
                    updated[file_type] = True
                    self.dashboard_file_mtimes[file_type] = current_mtime
                else:
                    updated[file_type] = False
            except Exception as e:
                logger.error(f"检查文件更新失败 ({file_type}): {e}")
                updated[file_type] = False
        
        return updated
    
    async def _broadcast_dashboard_from_files(self):
        """从文件读取 Dashboard 数据并广播"""
        updated_files = self._check_dashboard_files_updated()
        # 使用virtual time（mock模式下）或真实时间
        current_time = self._get_current_time_for_data()
        timestamp = current_time.isoformat()
        
        for file_type, is_updated in updated_files.items():
            if not is_updated:
                continue
            
            data = self._load_dashboard_file(file_type)
            if data is None:
                continue
            
            if file_type == 'summary':
                await self.broadcast({
                    'type': 'team_summary',
                    'balance': data.get('balance'),
                    'pnlPct': data.get('pnlPct'),
                    'equity': data.get('equity', []),
                    'baseline': data.get('baseline', []),
                    'baseline_vw': data.get('baseline_vw', []),
                    'momentum': data.get('momentum', []),
                    'timestamp': timestamp
                })
                logger.info(f"✅ 广播 team_summary (从文件)")
                
            elif file_type == 'holdings':
                self.state_manager.update('holdings', data)
                await self.broadcast({
                    'type': 'team_holdings',
                    'data': data,
                    'timestamp': timestamp
                })
                logger.info(f"✅ 广播 team_holdings: {len(data)} 个持仓 (从文件)")
                
            elif file_type == 'stats':
                self.state_manager.update('stats', data)
                await self.broadcast({
                    'type': 'team_stats',
                    'data': data,
                    'timestamp': timestamp
                })
                logger.info(f"✅ 广播 team_stats (从文件)")
                
            elif file_type == 'trades':
                self.state_manager.update('trades', data)
                await self.broadcast({
                    'type': 'team_trades',
                    'mode': 'full',
                    'data': data,
                    'timestamp': timestamp
                })
                logger.info(f"✅ 广播 team_trades: {len(data)} 笔交易 (从文件)")
                
            elif file_type == 'leaderboard':
                self.state_manager.update('leaderboard', data)
                await self.broadcast({
                    'type': 'team_leaderboard',
                    'data': data,
                    'timestamp': timestamp
                })
                logger.info(f"✅ 广播 team_leaderboard: {len(data)} 个 Agent (从文件)")
    
    def _is_trading_day(self, date_str: str = None) -> bool:
        """
        检查指定日期是否为交易日
        
        Args:
            date_str: 日期字符串 (YYYY-MM-DD)，默认为今天
        
        Returns:
            是否为交易日
        """
        if not _NYSE_CALENDAR:
            # 如果没有日历，简单判断（周一到周五）
            target_date = datetime.strptime(date_str, "%Y-%m-%d") if date_str else datetime.now()
            return target_date.weekday() < 5  # 0-4 是周一到周五
        
        try:
            target_date = date_str if date_str else datetime.now().strftime("%Y-%m-%d")
            schedule = _NYSE_CALENDAR.schedule(start_date=target_date, end_date=target_date)
            return not schedule.empty
        except Exception as e:
            logger.warning(f"检查交易日失败: {e}")
            # 默认认为是交易日
            return True
    
    def _is_trading_hours(self) -> bool:
        """
        检查当前是否为交易时段（美东时间9:30-16:00）
        
        Returns:
            是否在交易时段
        """
        if not _NYSE_CALENDAR:
            # 如果没有日历，简单判断
            now = datetime.now()
            # 注意：这里假设本地时间接近美东时间，实际应该转换时区
            # 简化处理：周一到周五的9:30-16:00
            if now.weekday() >= 5:  # 周末
                return False
            return datetime_time(9, 30) <= now.time() <= datetime_time(16, 0)
        
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            schedule = _NYSE_CALENDAR.schedule(start_date=today, end_date=today)
            
            if schedule.empty:
                return False  # 非交易日
            
            market_open = schedule.iloc[0]['market_open'].to_pydatetime()
            market_close = schedule.iloc[0]['market_close'].to_pydatetime()
            now = datetime.now(tz=market_open.tzinfo)
            
            return market_open <= now <= market_close
        except Exception as e:
            logger.warning(f"检查交易时段失败: {e}")
            return False
    
    def _get_market_close_time(self) -> Optional[datetime]:
        """
        获取今天的收盘时间
        
        Returns:
            收盘时间（datetime对象），如果不是交易日返回None
        """
        if not _NYSE_CALENDAR:
            # 简化处理：假设收盘时间为16:00
            now = datetime.now()
            if now.weekday() >= 5:
                return None
            return datetime.combine(now.date(), datetime_time(16, 0))
        
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            schedule = _NYSE_CALENDAR.schedule(start_date=today, end_date=today)
            
            if schedule.empty:
                return None
            
            market_close = schedule.iloc[0]['market_close'].to_pydatetime()
            return market_close
        except Exception as e:
            logger.warning(f"获取收盘时间失败: {e}")
            return None
    
    def _get_current_time_beijing(self) -> datetime:
        """获取当前北京时间（用于美股交易时间判断）"""
        from datetime import timezone
        # 使用虚拟时钟（如果启用）
        utc_now = self.vclock.now(timezone.utc)
        beijing_tz = timezone(timedelta(hours=8))
        return utc_now.astimezone(beijing_tz)
    
    def _is_market_open_time_beijing(self) -> bool:
        """
        检查当前北京时间是否在美股交易时段
        美股交易时间：北京时间 22:30 - 次日 05:00（夏令时）或 23:30 - 次日 06:00（冬令时）
        简化处理：使用 22:30 - 次日 05:00
        """
        now_beijing = self._get_current_time_beijing()
        current_time = now_beijing.time()
        
        # 22:30 之后（今天晚上开盘）
        if current_time >= datetime_time(22, 30):
            return True
        # 05:00 之前（昨天晚上开盘，今天凌晨还在交易）
        if current_time < datetime_time(5, 0):
            return True
        
        return False
    
    def _get_next_market_open_time_beijing(self) -> datetime:
        """
        获取下一次开盘时间（北京时间）
        返回：下一次开盘的 datetime 对象（22:30）
        """
        now_beijing = self._get_current_time_beijing()
        current_time = now_beijing.time()
        
        # 如果当前时间在 05:00 之后，22:30 之前，今天晚上开盘
        if datetime_time(5, 0) <= current_time < datetime_time(22, 30):
            open_time = now_beijing.replace(hour=22, minute=30, second=0, microsecond=0)
            return open_time
        
        # 如果当前时间在 22:30 之后，明天晚上开盘
        if current_time >= datetime_time(22, 30):
            next_day = now_beijing + timedelta(days=1)
            open_time = next_day.replace(hour=22, minute=30, second=0, microsecond=0)
            return open_time
        
        # 如果当前时间在 05:00 之前，今天晚上开盘
        open_time = now_beijing.replace(hour=22, minute=30, second=0, microsecond=0)
        return open_time
    
    def _get_market_status(self) -> Dict[str, Any]:
        """
        获取当前市场状态信息
        
        Returns:
            包含市场状态的字典
        """
        now_beijing = self._get_current_time_beijing()
        current_date_str = now_beijing.strftime("%Y-%m-%d")
        
        # 检查是否为交易日（使用美国日期判断）
        us_date = (now_beijing - timedelta(hours=12)).strftime("%Y-%m-%d")
        is_trading_day = self._is_trading_day(us_date)
        
        if not is_trading_day:
            return {
                'status': 'closed',
                'status_text': 'US Market Closed',
                'is_trading_day': False,
                'is_market_open': False,
                'current_time': now_beijing.isoformat(),
                'current_time_str': now_beijing.strftime('%Y-%m-%d %H:%M:%S')
            }
        
        # 交易日：检查是否在交易时段
        is_market_open = self._is_market_open_time_beijing()
        
        if is_market_open:
            return {
                'status': 'open',
                'status_text': 'US Market Open',
                'is_trading_day': True,
                'is_market_open': True,
                'current_time': now_beijing.isoformat(),
                'current_time_str': now_beijing.strftime('%Y-%m-%d %H:%M:%S'),
                'trading_date': us_date
            }
        else:
            return {
                'status': 'closed',
                'status_text': 'US Market Closed',
                'is_trading_day': True,
                'is_market_open': False,
                'current_time': now_beijing.isoformat(),
                'current_time_str': now_beijing.strftime('%Y-%m-%d %H:%M:%S'),
                'trading_date': us_date
            }
    
    def _get_next_trade_execution_time_beijing(self) -> datetime:
        """
        获取下一次交易执行时间（北京时间）
        返回：收盘后5分钟，即次日 05:05
        """
        now_beijing = self._get_current_time_beijing()
        current_time = now_beijing.time()
        
        # 如果当前时间在 05:05 之前，今天凌晨 05:05 执行
        if current_time < datetime_time(5, 5):
            execution_time = now_beijing.replace(hour=5, minute=5, second=0, microsecond=0)
            return execution_time
        
        # 否则，明天凌晨 05:05 执行
        next_day = now_beijing + timedelta(days=1)
        execution_time = next_day.replace(hour=5, minute=5, second=0, microsecond=0)
        return execution_time
    
    def _should_execute_trading_now(self) -> bool:
        """
        判断当前是否应该执行交易
        条件：收盘后（北京时间 05:05 - 21:00）
        """
        now_beijing = self._get_current_time_beijing()
        current_time = now_beijing.time()
        
        # 在 05:05 - 10:00 之间执行交易（5小时窗口，适应时间加速）
        return datetime_time(5, 5) <= current_time < datetime_time(21, 55)
    
    async def handle_client(self, websocket: WebSocketServerProtocol):
        """处理客户端连接"""
        try:
            async with self.lock:
                self.connected_clients.add(websocket)
            
            logger.info(f"✅ 新客户端连接 (总连接数: {len(self.connected_clients)})")
            
            initial_state = self.state_manager.get_full_state()
            
            # 从文件加载 Dashboard 数据
            try:
                summary_data = self._load_dashboard_file('summary')
                holdings_data = self._load_dashboard_file('holdings')
                stats_data = self._load_dashboard_file('stats')
                trades_data = self._load_dashboard_file('trades')
                leaderboard_data = self._load_dashboard_file('leaderboard')
                
                initial_state['dashboard'] = {
                    'summary': summary_data,
                    'holdings': holdings_data,
                    'stats': stats_data,
                    'trades': trades_data,
                    'leaderboard': leaderboard_data
                }
                
                if summary_data and 'portfolio' in initial_state:
                    initial_state['portfolio'].update({
                        'total_value': summary_data.get('balance'),
                        'pnl_percent': summary_data.get('pnlPct'),
                        'equity': summary_data.get('equity', []),
                        'baseline': summary_data.get('baseline', []),
                        'baseline_vw': summary_data.get('baseline_vw', []),
                        'momentum': summary_data.get('momentum', [])
                    })
                
                if holdings_data:
                    initial_state['holdings'] = holdings_data
                if stats_data:
                    initial_state['stats'] = stats_data
                if trades_data:
                    initial_state['trades'] = trades_data
                if leaderboard_data:
                    initial_state['leaderboard'] = leaderboard_data
                
                logger.info(f"✅ 从文件加载 Dashboard 数据成功")
            except Exception as e:
                logger.error(f"⚠️ 从文件加载 Dashboard 数据失败: {e}")
            
            # 添加服务器模式和市场状态信息
            initial_state['server_mode'] = 'live'
            initial_state['market_status'] = self._get_market_status()
            
            # 发送完整状态
            await websocket.send(json.dumps({
                'type': 'initial_state',
                'state': initial_state
            }, ensure_ascii=False, default=str))
            
            # 保持连接
            try:
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        msg_type = data.get('type', 'unknown')
                        
                        if msg_type == 'ping':
                            await websocket.send(json.dumps({
                                'type': 'pong',
                                'timestamp': datetime.now().isoformat()
                            }, ensure_ascii=False, default=str))
                        
                        elif msg_type == 'get_state':
                            await websocket.send(json.dumps({
                                'type': 'state_response',
                                'state': self.state_manager.get_full_state()
                            }, ensure_ascii=False, default=str))
                            
                    except json.JSONDecodeError:
                        logger.warning("收到非JSON消息")
                    except Exception as e:
                        logger.error(f"处理消息异常: {e}")
            except websockets.ConnectionClosed:
                pass
            
        except Exception as e:
            logger.error(f"连接处理异常: {e}")
        finally:
            async with self.lock:
                self.connected_clients.discard(websocket)
            logger.info(f"客户端断开 (剩余连接: {len(self.connected_clients)})")
    
    async def run_live_trading_simulation(self):
        """运行在线交易模拟"""
        logger.info("🚀 开始在线交易模式")
        
        loop = asyncio.get_event_loop()
        
        # ========== 立即启动价格管理器 ==========
        logger.info("===== [实时价格] 启动价格监控 =====")
        
        # 订阅实时价格（如果使用Mock模式，可能需要传入基准价格）
        if self.mock_mode:
            # Mock模式：使用当前portfolio的持仓价格作为基准
            base_prices = {}
            holdings = self.state_manager.get('holdings', [])
            for holding in holdings:
                ticker = holding.get('ticker')
                avg_price = holding.get('avg', 100.0)  # 默认100
                base_prices[ticker] = avg_price
            
            # 如果没有历史持仓，使用默认基准价格
            if not base_prices:
                for ticker in self.config.tickers:
                    base_prices[ticker] = 100.0
            
            self.price_manager.subscribe(self.config.tickers, base_prices=base_prices)
            logger.info(f"🎭 Mock模式: 已订阅 {len(self.config.tickers)} 个股票，使用虚拟价格")
        else:
            self.price_manager.subscribe(self.config.tickers)
            logger.info(f"📊 实时模式: 已订阅 {len(self.config.tickers)} 个股票，使用Finnhub API")
        
        self.price_manager.start()
        logger.info(f"✅ 价格管理器已启动，实时更新频率: {'每5秒 (Mock)' if self.mock_mode else '每10秒 (Finnhub)'}")
        
        await self.broadcast({
            'type': 'system',
            'content': f'✅ 股票价格板已启动，开始实时更新 ({len(self.config.tickers)} 个股票)'
        })
        
        # 创建广播streamer
        broadcast_streamer = BroadcastStreamer(
            broadcast_callback=self.broadcast,
            event_loop=loop,
            console_output=True
        )
        
        # 初始化交易系统
        self.thinking_fund = LiveTradingFund(
            config_name=self.config.config_name,
            streamer=broadcast_streamer,
            mode=self.config.mode,
            initial_cash=self.config.initial_cash,
            margin_requirement=self.config.margin_requirement,
            pause_before_trade=self.pause_before_trade
        )
        
        # 确定"今天"的美国交易日期
        # Mock模式且指定了虚拟起始时间：使用虚拟时间
        # 否则：使用真实的当前时间
        if self.mock_mode and self.virtual_start_time:
            reference_time = self.virtual_start_time
        else:
            reference_time = datetime.now()
        
        # 转换为美国交易日期（北京时间 - 12小时）
        today_us = (reference_time - timedelta(hours=12)).strftime("%Y-%m-%d")
        logger.info(f"📅 当前北京时间: {reference_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"📅 对应美国交易日: {today_us}")
        
        # ========== 直接进入今天在线模式 ==========
        logger.info(f"📅 直接进入今天在线模式: {today_us}")
        
        self.state_manager.update('status', 'live_analysis')
        self.state_manager.update('trading_days_total', 1)
        self.state_manager.update('trading_days_completed', 0)
        
        await self.broadcast({
            'type': 'system',
            'content': f'系统启动 - 直接进入今天在线模式 (美国交易日: {today_us})'
        })
        
        # ========== 今天的在线模式 ==========
        logger.info(f"===== [在线模式] 美国交易日 {today_us} =====")
        self.current_phase = "live_analysis"
        self.is_today = True
        
        self.state_manager.update('status', 'live_analysis')
        self.state_manager.update('current_date', today_us)
        
        # 根据暂停模式发送不同的消息
        if self.pause_before_trade:
            await self.broadcast({
                'type': 'system',
                'content': f'⏸️ 进入今天在线模式 - 美国交易日 {today_us}，正在进行交易决策分析（暂停模式：不执行交易）...'
            })
        else:
            await self.broadcast({
                'type': 'system',
                'content': f'进入今天在线模式 - 美国交易日 {today_us}，正在进行交易决策分析...'
            })
        
        # 第一天启动：立即运行盘前分析（func1）
        await self._run_pre_market_analysis(today_us)
        
        # ========== 进入持续监控和自动交易循环 ==========
        logger.info("===== [持续监控] 进入连续运行模式 =====")
        await self._continuous_trading_loop()
    
    async def _run_pre_market_analysis(self, date: str):
        """运行盘前分析（func1）：调用 strategy.run_single_day 生成信号"""
        
        logger.info(f"===== [盘前分析] {date} =====")
        
        await self.broadcast({
            'type': 'system',
            'content': f'📊 开始盘前分析 ({date})...'
        })
        
        result = await asyncio.to_thread(
            self.thinking_fund.run_pre_market_analysis_only,
            date=date,
            tickers=self.config.tickers,
            max_comm_cycles=self.config.max_comm_cycles,
            force_run=True,
            enable_communications=not self.config.disable_communications,
            enable_notifications=not self.config.disable_notifications
        )
        
        if not isinstance(result, dict):
            logger.error(f"❌ 分析返回类型错误: 期望dict，实际{type(result).__name__}")
            logger.error(f"   返回值: {result}")
            await self.broadcast({
                'type': 'system',
                'content': f'❌ 盘前分析失败: 返回类型错误'
            })
            return
        
        if result.get('status') != 'success':
            logger.warning(f"⚠️ 盘前分析未成功: {result.get('reason', 'unknown')}")
            await self.broadcast({
                'type': 'system',
                'content': f"⚠️ 盘前分析跳过: {result.get('reason', 'unknown')}"
            })
            return
        
        pre_market = result.get('pre_market', {})
        live_env = pre_market.get('live_env', {})
        
        pm_signals = live_env.get('pm_signals', {})
        ana_signals = live_env.get('ana_signals', {})
        
        # 保存信号供第二天使用
        self.daily_signals[date] = {
            'ana_signals': ana_signals,
            'pm_signals': pm_signals,
            'pre_market_result': result
        }
        
        self.state_manager.update('latest_signals', pm_signals)
        
        await self.broadcast({
            'type': 'system',
            'content': f'✅ 盘前分析完成 ({date})，生成 {len(pm_signals)} 个股票信号'
        })
        logger.info(f"✅ 盘前分析完成: {date}，生成 {len(pm_signals)} 个信号")
        
        # 设置标记（避免短时间内重复运行）
        self.analysis_executed_today = True
    
    async def _run_trade_execution_with_prev_update(self, date: str):
        """执行交易并更新前一天的 agent perf（func2）"""
        
        logger.info(f"===== [交易执行] {date} =====")
        
        await self.broadcast({
            'type': 'system',
            'content': f'💼 开始交易执行 ({date})...'
        })
        
        # 获取当天的信号
        current_day_data = self.daily_signals.get(date)
        
        # 获取前一个交易日
        prev_date = self.last_trading_date
        prev_signals = self.daily_signals.get(prev_date) if prev_date else None
        
        result = await asyncio.to_thread(
            self.thinking_fund.run_trade_execution_and_update_prev_perf,
            date=date,
            tickers=self.config.tickers,
            pre_market_result=current_day_data.get('pre_market_result') if current_day_data else None,
            prev_date=prev_date,
            prev_signals=prev_signals
        )
        
        if result.get('prev_day_updated'):
            await self.broadcast({
                'type': 'system',
                'content': f'✅ 已更新前一交易日 ({prev_date}) 的 agent 表现'
            })
            logger.info(f"✅ 已更新前一交易日的 agent perf: {prev_date}")
        
        if result.get('status') == 'success':
            await self.broadcast({
                'type': 'system',
                'content': f'✅ 交易执行完成 ({date})'
            })
            logger.info(f"✅ 交易执行完成: {date}")
            
            # 广播交易完成事件
            await self.broadcast({
                'type': 'trade_execution_complete',
                'date': date,
                'timestamp': datetime.now().isoformat()
            })
        
        self.state_manager.save()
        logger.info(f"💾 交易数据已保存: {date}")
    
    def _should_run_pre_market_analysis(self) -> bool:
        """判断当前是否应该运行盘前分析（22:30:00 之后）"""
        now_beijing = self._get_current_time_beijing()
        current_time = now_beijing.time()
        
        # 在 22:30:00 - 22:40:00 之间运行盘前分析（10分钟窗口，适应时间加速）
        return datetime_time(22, 30, 0) <= current_time < datetime_time(23, 30, 0)
    
    async def _continuous_trading_loop(self):
        """
        连续交易循环 - 核心逻辑
        1. 每天 22:30-22:40（10分钟窗口）运行盘前分析（func1）
        2. 每天 05:05-10:00（5小时窗口）执行交易并更新前一天的 agent perf（func2）
        3. 在交易时段（22:30-05:00）启动价格监控
        4. 在非交易时段（10:00-22:30）只维持页面时间更新
        5. 使用标记避免窗口内重复执行
        """
        logger.info("🔄 启动连续交易循环")
        
        while True:
            now_beijing = self._get_current_time_beijing()
            
            # 检查是否为交易日（使用美国日期判断）
            us_date = (now_beijing - timedelta(hours=12)).strftime("%Y-%m-%d")  # 粗略转换为美国日期
            is_trading_day = self._is_trading_day(us_date)
            
            if not is_trading_day:
                # 非交易日：只维持页面更新
                await self._handle_non_trading_day(now_beijing)
                await self.vclock.sleep(60)  # 每分钟检查一次（虚拟时间）
                continue
            
            # 交易日逻辑
            is_market_open = self._is_market_open_time_beijing()
            should_run_analysis = self._should_run_pre_market_analysis()
            should_execute_trade = self._should_execute_trading_now()
            
            # 调试日志
            if should_run_analysis:
                logger.debug(f"🔍 检测到盘前分析时间窗口 | analysis_executed_today={self.analysis_executed_today} | us_date={us_date}")
            if should_execute_trade:
                logger.debug(f"🔍 检测到交易执行时间窗口 | trading_executed_today={self.trading_executed_today} | us_date={us_date}")
            
            if should_run_analysis and not self.analysis_executed_today:
                # 开盘后运行盘前分析（22:30:00-22:40:00，10分钟窗口）
                logger.info(f"🎯 触发盘前分析 (func1) | us_date={us_date} | 北京时间={now_beijing.strftime('%H:%M:%S')}")
                await self._run_pre_market_analysis(us_date)
                await self.vclock.sleep(30)  # 等待30秒（虚拟时间）
                
            elif is_market_open:
                # 市场开盘时段（22:30-05:00）：实时价格监控
                await self._handle_market_open_period(now_beijing, us_date)
                await self.vclock.sleep(60)  # 每分钟检查一次（虚拟时间）
                
            elif should_execute_trade and not self.trading_executed_today:
                # 收盘后执行交易时间（05:05-10:00，5小时窗口）
                logger.info(f"🎯 触发交易执行 (func2) | us_date={us_date} | 北京时间={now_beijing.strftime('%H:%M:%S')}")
                await self._run_trade_execution_with_prev_update(us_date)
                self.trading_executed_today = True
                self.last_trading_date = us_date
                self.last_executed_date = us_date  # 记录实际执行日期
                await self.vclock.sleep(300)  # 执行后等待5分钟（虚拟时间）
                
            else:
                # 非交易时段（10:00-22:30）：只维持页面更新
                await self._handle_off_market_period(now_beijing)
                
                # 如果接近开盘时间，缩短等待
                next_open = self._get_next_market_open_time_beijing()
                time_to_open = (next_open - now_beijing).total_seconds()
                
                if time_to_open < 600:  # 距离开盘不到10分钟
                    await self.vclock.sleep(30)  # 虚拟时间30秒
                else:
                    await self.vclock.sleep(300)  # 虚拟时间5分钟
            
            # 检查美国交易日变更，重置标记
            # 在 10:00-22:29 之间检查是否需要重置标记（确保在交易执行窗口结束后，下次分析前）
            # ✅ 只有当日期真正变化时才重置，避免同一天内重复执行
            current_time = now_beijing.time()
            if datetime_time(10, 0) <= current_time < datetime_time(22, 29):
                # 检查日期是否真的变了
                if self.last_executed_date and us_date != self.last_executed_date:
                    if self.trading_executed_today or self.analysis_executed_today:
                        logger.info(f"📅 检测到交易日变更 ({self.last_executed_date} → {us_date})，重置每日标记")
                        logger.info(f"   北京时间={now_beijing.strftime('%H:%M:%S')}")
                        logger.info(f"   重置前: trading_executed={self.trading_executed_today}, analysis_executed={self.analysis_executed_today}")
                        self.trading_executed_today = False
                        self.analysis_executed_today = False
                        logger.info(f"   重置后: trading_executed={self.trading_executed_today}, analysis_executed={self.analysis_executed_today}")
    
    async def _handle_non_trading_day(self, now_beijing: datetime):
        """处理非交易日：只维持页面时间更新，不获取价格"""
        current_phase = self.state_manager.get('status')
        
        if current_phase != 'non_trading_day':
            self.current_phase = "non_trading_day"
            self.state_manager.update('status', 'non_trading_day')
            
            # 停止价格管理器
            if self.price_manager and not self.mock_mode:
                logger.info("🛑 非交易日，停止价格获取")
                self.price_manager.stop()
            
            await self.broadcast({
                'type': 'system',
                'content': f'📅 今天是非交易日 ({now_beijing.strftime("%Y-%m-%d")}），只维持页面更新'
            })
            logger.info(f"📅 非交易日: {now_beijing.strftime('%Y-%m-%d')}")
        
        # 广播时间更新
        next_open = self._get_next_market_open_time_beijing()
        hours_to_open = (next_open - now_beijing).total_seconds() / 3600
        
        logger.info(f"⏰ 当前时间: {now_beijing.strftime('%Y-%m-%d %H:%M:%S')} | 状态: 非交易日 | 距离开盘: {hours_to_open:.1f}小时")
        
        market_status = self._get_market_status()
        await self.broadcast({
            'type': 'time_update',
            'beijing_time': now_beijing.isoformat(),
            'beijing_time_str': now_beijing.strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'non_trading_day',
            'next_open': next_open.isoformat(),
            'hours_to_open': round(hours_to_open, 1),
            'market_status': market_status
        })
        
        # 单独广播市场状态更新
        await self.broadcast({
            'type': 'market_status_update',
            'market_status': market_status
        })
    
    async def _handle_market_open_period(self, now_beijing: datetime, trading_date: str):
        """处理市场开盘时段：实时价格监控"""
        current_phase = self.state_manager.get('status')
        
        if current_phase != 'market_open':
            self.current_phase = "market_open"
            self.state_manager.update('status', 'market_open')
            self.state_manager.update('current_trading_date', trading_date)
            
            # 确保价格管理器运行
            if self.price_manager and not self.mock_mode:
                if not hasattr(self.price_manager, 'running') or not self.price_manager.running:
                    logger.info("🚀 市场开盘，启动价格获取")
                    self.price_manager.start()
            
            await self.broadcast({
                'type': 'system',
                'content': f'📊 市场开盘 (交易日: {trading_date})，实时价格监控中...'
            })
            logger.info(f"📊 市场开盘时段: {now_beijing.strftime('%H:%M:%S')}")
        
        # 计算距离收盘和交易执行的时间
        next_trade_time = self._get_next_trade_execution_time_beijing()
        hours_to_trade = (next_trade_time - now_beijing).total_seconds() / 3600
        
        logger.info(f"⏰ 当前时间: {now_beijing.strftime('%Y-%m-%d %H:%M:%S')} | 状态: 市场开盘 | 距离交易执行: {hours_to_trade:.1f}小时")
        
        # 广播时间和状态更新
        market_status = self._get_market_status()
        await self.broadcast({
            'type': 'time_update',
            'beijing_time': now_beijing.isoformat(),
            'beijing_time_str': now_beijing.strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'market_open',
            'trading_date': trading_date,
            'next_trade_time': next_trade_time.isoformat(),
            'hours_to_trade': round(hours_to_trade, 1),
            'market_status': market_status
        })
        
        # 单独广播市场状态更新
        await self.broadcast({
            'type': 'market_status_update',
            'market_status': market_status
        })
    
    async def _handle_off_market_period(self, now_beijing: datetime):
        """处理非交易时段：只维持页面更新"""
        current_phase = self.state_manager.get('status')
        
        if current_phase not in ['off_market', 'trade_execution']:
            self.current_phase = "off_market"
            self.state_manager.update('status', 'off_market')
            
            # 停止价格管理器
            if self.price_manager and not self.mock_mode:
                if hasattr(self.price_manager, 'running') and self.price_manager.running:
                    logger.info("🛑 非交易时段，停止价格获取")
                    self.price_manager.stop()
            
            next_open = self._get_next_market_open_time_beijing()
            hours_to_open = (next_open - now_beijing).total_seconds() / 3600
            
            await self.broadcast({
                'type': 'system',
                'content': f'⏸️ 非交易时段，距离下次开盘约 {hours_to_open:.1f} 小时'
            })
            logger.info(f"⏸️ 非交易时段: {now_beijing.strftime('%H:%M:%S')}")
        
        # 广播时间更新
        next_open = self._get_next_market_open_time_beijing()
        hours_to_open = (next_open - now_beijing).total_seconds() / 3600
        
        logger.info(f"⏰ 当前时间: {now_beijing.strftime('%Y-%m-%d %H:%M:%S')} | 状态: 非交易时段 | 距离开盘: {hours_to_open:.1f}小时")
        
        market_status = self._get_market_status()
        await self.broadcast({
            'type': 'time_update',
            'beijing_time': now_beijing.isoformat(),
            'beijing_time_str': now_beijing.strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'off_market',
            'next_open': next_open.isoformat(),
            'hours_to_open': round(hours_to_open, 1),
            'market_status': market_status
        })
        
        # 单独广播市场状态更新
        await self.broadcast({
            'type': 'market_status_update',
            'market_status': market_status
        })
    
    async def _run_data_updater(self):
        """执行数据更新任务"""
        logger.info("🔄 [定时任务] 开始执行历史数据更新...")
        
        # 广播更新开始
        await self.broadcast({
            'type': 'system',
            'content': '🔄 正在自动更新历史数据...'
        })
        
        # 执行数据更新（在子进程中运行，避免阻塞）
        process = await asyncio.create_subprocess_exec(
            sys.executable, '-m', 'src.data.ret_data_updater',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(BASE_DIR)
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            logger.info("✅ [定时任务] 历史数据更新完成")
            await self.broadcast({
                'type': 'system',
                'content': '✅ 历史数据更新完成'
            })
        else:
            error_msg = stderr.decode('utf-8', errors='ignore') if stderr else "未知错误"
            logger.warning(f"⚠️ [定时任务] 历史数据更新失败: {error_msg[:200]}")
            await self.broadcast({
                'type': 'system',
                'content': f'⚠️ 历史数据更新失败（可能是周末/假期），将使用现有数据'
            })
    
    async def _daily_data_updater_scheduler(self):
        """每天 05:10 执行数据更新的调度器"""
        logger.info("📅 数据更新调度器已启动（每天 05:10 执行）")
        
        try:
            while True:
                # 获取当前时间
                now = datetime.now()
                
                # 计算下次执行时间（今天或明天的 05:10）
                target_time = datetime_time(5, 10)  # 05:10
                
                if now.time() < target_time:
                    # 今天还没到 05:10，今天执行
                    next_run = datetime.combine(now.date(), target_time)
                else:
                    # 今天已经过了 05:10，明天执行
                    next_run = datetime.combine(now.date() + timedelta(days=1), target_time)
                
                # 计算等待时间（秒）
                wait_seconds = (next_run - now).total_seconds()
                
                logger.info(f"⏰ 下次数据更新时间: {next_run.strftime('%Y-%m-%d %H:%M:%S')} (等待 {wait_seconds/3600:.2f} 小时)")
                
                # 等待到执行时间
                await asyncio.sleep(wait_seconds)
                
                # 执行数据更新
                await self._run_data_updater()
        except asyncio.CancelledError:
            logger.info("📅 数据更新调度器已停止")
            raise
    
    async def _periodic_state_saver(self):
        """定期保存状态（每5分钟）"""
        while True:
            await asyncio.sleep(300)
            self.state_manager.save()
    
    async def _periodic_dashboard_monitor(self):
        """定期监控 Dashboard 文件变化并广播（每5秒）"""
        logger.info("🔍 Dashboard 文件监控已启动（每5秒检查一次）")
        
        while True:
            try:
                await asyncio.sleep(5)
                await self._broadcast_dashboard_from_files()
                
                # 定期更新市场状态（每30秒）
                if hasattr(self, '_last_market_status_update'):
                    if (datetime.now() - self._last_market_status_update).total_seconds() >= 60:
                        market_status = self._get_market_status()
                        await self.broadcast({
                            'type': 'market_status_update',
                            'market_status': market_status
                        })
                        self._last_market_status_update = datetime.now()
                else:
                    self._last_market_status_update = datetime.now()
            except Exception as e:
                logger.error(f"❌ Dashboard 文件监控异常: {e}")
    
    async def start(self, host: str = "0.0.0.0", port: int = 8765):
        """启动服务器"""
        self.loop = asyncio.get_event_loop()
        
        # 加载已保存的状态
        self.state_manager.load()
        
        # 启动WebSocket服务器
        async with websockets.serve(
            self.handle_client,
            host,
            port,
            ping_interval=None,
            ping_timeout=None
        ):
            logger.info(f"🌐 WebSocket服务器已启动: ws://{host}:{port}")
            
            # 启动定期保存任务
            saver_task = asyncio.create_task(self._periodic_state_saver())
            dashboard_monitor_task = asyncio.create_task(self._periodic_dashboard_monitor())
            
            # 启动数据更新调度器（仅在非Mock模式下）
            data_updater_task = None
            if not self.mock_mode:
                data_updater_task = asyncio.create_task(self._daily_data_updater_scheduler())
            
            # 启动在线交易模拟
            simulation_task = asyncio.create_task(self.run_live_trading_simulation())
            
            try:
                await simulation_task
            except KeyboardInterrupt:
                logger.info("收到中断信号，正在关闭...")
            finally:
                self.state_manager.save()
                logger.info("✅ 最终状态已保存")
                
                saver_task.cancel()
                dashboard_monitor_task.cancel()
                if data_updater_task:
                    data_updater_task.cancel()
                
                if self.price_manager:
                    self.price_manager.stop()


async def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='在线交易系统服务器')
    parser.add_argument('--mock', action='store_true', help='使用Mock模式（虚拟价格测试）')
    parser.add_argument('--config-name', default='live_mode', help='配置名称（默认: live_mode）')
    parser.add_argument('--host', default='0.0.0.0', help='监听地址（默认: 0.0.0.0）')
    parser.add_argument('--port', type=int, default=8765, help='监听端口（默认: 8765')
    parser.add_argument('--pause-before-trade', action='store_true', dest='pause_before_trade_cli', help='暂停模式：完成分析但不执行交易，仅更新价格')
    parser.add_argument('--time-accelerator', type=float, default=1.0, help='时间加速器（用于调试，1.0=正常，60.0=1分钟当1小时）')
    parser.add_argument('--virtual-start-time', type=str, default=None, help='虚拟起始时间（格式: "2024-11-12 22:25:00"，仅Mock模式有效）')
    args = parser.parse_args()
    
    # 加载配置
    config = LiveThinkingFundConfig()
    config.config_name = args.config_name
    
    # 确定暂停模式：命令行参数优先，否则使用环境变量配置
    # 优先级：命令行 > 环境变量 > 默认值(False)
    if args.pause_before_trade_cli:
        # 命令行明确指定了 --pause-before-trade
        pause_before_trade = True
        pause_source = "命令行参数"
    else:
        # 使用配置对象中的值（来自环境变量或默认值）
        pause_before_trade = getattr(config, 'pause_before_trade', False)
        if pause_before_trade:
            pause_source = "环境变量"
        else:
            pause_source = "默认值"
    
    # 打印配置
    logger.info("📊 在线交易服务器配置:")
    logger.info(f"   配置名称: {config.config_name}")
    logger.info(f"   运行模式: {'🎭 MOCK（虚拟价格）' if args.mock else '🚀 LIVE（实时价格）'}")
    logger.info(f"   监控股票: {config.tickers}")
    if config.mode == "portfolio":
        logger.info(f"   初始现金: ${config.initial_cash:,.2f}")
        logger.info(f"   保证金要求: {config.margin_requirement * 100:.1f}%")
    if pause_before_trade:
        logger.info(f"   交易执行: ⏸️ 暂停模式（仅分析，不执行交易）[来源: {pause_source}]")
    else:
        logger.info(f"   交易执行: ▶️ 正常模式（分析后执行交易）")
    if args.time_accelerator != 1.0:
        logger.info(f"   ⚡ 时间加速: {args.time_accelerator}x（调试模式）")
    
    # 解析虚拟起始时间
    virtual_start_time = None
    if args.virtual_start_time and args.mock:
        from datetime import timezone
        virtual_start_time = datetime.strptime(args.virtual_start_time, "%Y-%m-%d %H:%M:%S")
        virtual_start_time = virtual_start_time.replace(tzinfo=timezone(timedelta(hours=8)))  # 北京时间
        logger.info(f"   🕐 虚拟起始时间: {virtual_start_time.strftime('%Y-%m-%d %H:%M:%S')} (北京时间)")
    
    # 创建并启动服务器
    server = LiveTradingServer(
        config, 
        mock_mode=args.mock, 
        pause_before_trade=pause_before_trade,
        time_accelerator=args.time_accelerator,
        virtual_start_time=virtual_start_time
    )
    await server.start(host=args.host, port=args.port)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Bye!")

