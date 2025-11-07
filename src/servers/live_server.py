# src/servers/live_server.py
"""
在线模式服务器 - Live Trading System
功能：
1. 从当前时间点倒推n天运行历史回测
2. 到达今天后，进行实时交易决策分析
3. 高频获取实时价格，更新净值曲线、持仓盈亏等
4. 支持Mock模式用于非交易时段测试
"""
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta, time as datetime_time
from typing import Set, Dict, Any, Optional
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

import websockets
from websockets.server import WebSocketServerProtocol
from websockets.exceptions import ConnectionClosedError

from src.memory.memory_factory import initialize_memory_system
from src.servers.streamer import BroadcastStreamer
from src.servers.polling_price_manager import PollingPriceManager
from src.servers.mock_price_manager import MockPriceManager
from src.servers.realtime_price_manager import RealtimePortfolioCalculator
from src.servers.state_manager import StateManager
from live_trading_thinking_fund import LiveTradingThinkingFund
from src.config.env_config import LiveThinkingFundConfig
from src.tools.api import get_prices

# 尝试导入交易日历
try:
    import pandas_market_calendars as mcal
    _NYSE_CALENDAR = mcal.get_calendar('NYSE')
    CALENDAR_AVAILABLE = True
except ImportError:
    _NYSE_CALENDAR = None
    CALENDAR_AVAILABLE = False

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class LiveTradingServer:
    """在线交易服务器"""
    
    def __init__(self, config: LiveThinkingFundConfig, mock_mode: bool = False, lookback_days: int = 0, pause_before_trade: bool = False):
        self.config = config
        self.mock_mode = mock_mode
        self.lookback_days = lookback_days
        self.pause_before_trade = pause_before_trade
        self.connected_clients: Set[WebSocketServerProtocol] = set()
        self.lock = asyncio.Lock()
        self.loop = None
        
        # Dashboard 文件路径
        self.dashboard_dir = BASE_DIR / "logs_and_memory" / config.config_name / "sandbox_logs" / "team_dashboard"
        self.dashboard_files = {
            'summary': self.dashboard_dir / 'summary.json',
            'holdings': self.dashboard_dir / 'holdings.json',
            'stats': self.dashboard_dir / 'stats.json',
            'trades': self.dashboard_dir / 'trades.json',
            'leaderboard': self.dashboard_dir / 'leaderboard.json'
        }
        self.dashboard_file_mtimes = {}
        logger.info(f"✅ Dashboard 文件目录: {self.dashboard_dir}")
        
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
            self.portfolio_calculator = RealtimePortfolioCalculator(self.price_manager)
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
            self.portfolio_calculator = RealtimePortfolioCalculator(self.price_manager)
        
        # 添加价格更新回调
        self.price_manager.add_price_callback(self._on_price_update)
        
        # 初始化记忆系统
        from src.servers.streamer import ConsoleStreamer
        console_streamer = ConsoleStreamer()
        memory_instance = initialize_memory_system(
            base_dir=config.config_name,
            streamer=console_streamer
        )
        logger.info(f"✅ 记忆系统已初始化: {memory_instance.get_framework_name()}")
        
        # 注册分析师到记忆系统
        from src.memory.framework_bridge import get_memory_bridge
        memory_bridge = get_memory_bridge()
        
        analyst_definitions = {
            'fundamentals_analyst': '基本面分析师',
            'technical_analyst': '技术分析师',
            'sentiment_analyst': '情绪分析师',
            'valuation_analyst': '估值分析师',
            'portfolio_manager': '投资组合经理',
            'risk_manager': '风险管理师'
        }
        
        for analyst_id, analyst_name in analyst_definitions.items():
            try:
                memory_bridge.register_analyst(analyst_id, analyst_name)
            except Exception as e:
                logger.warning(f"注册 {analyst_id} 失败: {e}")
        
        logger.info("✅ 所有分析师已注册到记忆系统")
        
        # 初始化交易系统
        self.thinking_fund = None
        
        # 在线模式状态
        self.current_phase = "backtest"  # backtest, live_analysis, live_monitoring
        self.is_today = False
        self.market_is_open = False
    
    def _on_price_update(self, price_data: Dict[str, Any]):
        """价格更新回调 - 异步广播给所有客户端"""
        symbol = price_data['symbol']
        price = price_data['price']
        open_price = price_data.get('open', price)
        
        # 计算相对开盘价的return
        ret = ((price - open_price) / open_price) * 100 if open_price > 0 else 0
        
        # 更新当前状态
        realtime_prices = self.state_manager.get('realtime_prices', {})
        realtime_prices[symbol] = {
            'price': price,
            'open': open_price,
            'ret': ret,
            'timestamp': price_data.get('timestamp'),
            'volume': price_data.get('volume')
        }
        self.state_manager.update('realtime_prices', realtime_prices)
        
        # 如果有Portfolio计算器，更新净值
        if self.portfolio_calculator:
            pnl_data = self.portfolio_calculator.calculate_pnl()
            portfolio = self.state_manager.get('portfolio', {})
            portfolio.update(pnl_data)
            
            # 添加新的equity数据点
            equity_list = portfolio.get('equity', [])
            equity_list.append({
                't': price_data.get('timestamp'),
                'v': pnl_data['total_value']
            })
            # 保留最近1000个点
            if len(equity_list) > 1000:
                equity_list = equity_list[-1000:]
            portfolio['equity'] = equity_list
            
            self.state_manager.update('portfolio', portfolio)
        
        # 广播价格更新
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.broadcast({
                    'type': 'price_update',
                    'symbol': symbol,
                    'price': price,
                    'open': open_price,
                    'ret': ret,
                    'timestamp': price_data.get('timestamp'),
                    'portfolio': self.state_manager.get('portfolio', {}),
                    'realtime_prices': realtime_prices
                }),
                self.loop
            )
    
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
        timestamp = datetime.now().isoformat()
        
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
        if not CALENDAR_AVAILABLE or not _NYSE_CALENDAR:
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
        if not CALENDAR_AVAILABLE or not _NYSE_CALENDAR:
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
        if not CALENDAR_AVAILABLE or not _NYSE_CALENDAR:
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
        
        # 创建广播streamer
        broadcast_streamer = BroadcastStreamer(
            broadcast_callback=self.broadcast,
            event_loop=loop,
            console_output=True
        )
        
        # 初始化交易系统
        self.thinking_fund = LiveTradingThinkingFund(
            base_dir=self.config.config_name,
            streamer=broadcast_streamer,
            mode=self.config.mode,
            initial_cash=self.config.initial_cash,
            margin_requirement=self.config.margin_requirement,
            pause_before_trade=self.pause_before_trade
        )
        
        today = datetime.now().strftime("%Y-%m-%d")
        
        # ========== 判断是否需要回测历史 ==========
        if self.lookback_days > 0:
            # ========== 阶段1: 回测历史n天 ==========
            start_date = (datetime.now() - timedelta(days=self.lookback_days)).strftime("%Y-%m-%d")
            
            trading_days = self.thinking_fund.generate_trading_dates(start_date, today)
            
            # 区分历史日期和今天
            historical_days = [d for d in trading_days if d < today]
            
            logger.info(f"📅 阶段1: 回测历史 {len(historical_days)} 个交易日: {start_date} -> {historical_days[-1] if historical_days else 'N/A'}")
            logger.info(f"📅 阶段2: 今天在线模式: {today}")
            
            self.state_manager.update('status', 'backtest')
            self.state_manager.update('trading_days_total', len(trading_days))
            self.state_manager.update('trading_days_completed', 0)
            self.current_phase = "backtest"
            
            await self.broadcast({
                'type': 'system',
                'content': f'系统启动 - 回测 {len(historical_days)} 天，然后进入今天在线模式'
            })
            
            # 运行历史回测
            for idx, date in enumerate(historical_days, 1):
                logger.info(f"===== [回测 {idx}/{len(historical_days)}] {date} =====")
                self.state_manager.update('current_date', date)
                self.state_manager.update('trading_days_completed', idx)
                
                await self.broadcast({
                    'type': 'day_start',
                    'date': date,
                    'phase': 'backtest',
                    'progress': idx / len(trading_days)
                })
                
                try:
                    result = await asyncio.to_thread(
                        self.thinking_fund.run_full_day_simulation,
                        date=date,
                        tickers=self.config.tickers,
                        max_comm_cycles=self.config.max_comm_cycles,
                        force_run=False,
                        enable_communications=not self.config.disable_communications,
                        enable_notifications=not self.config.disable_notifications
                    )
                    
                    # 更新状态
                    if result and result.get('pre_market'):
                        signals = result['pre_market'].get('signals', {})
                        self.state_manager.update('latest_signals', signals)
                        
                        if self.config.mode == "portfolio":
                            live_env = result['pre_market'].get('live_env', {})
                            portfolio_summary = live_env.get('portfolio_summary', {})
                            updated_portfolio = live_env.get('updated_portfolio', {})
                            
                            if portfolio_summary and updated_portfolio:
                                # 更新Portfolio计算器
                                if self.portfolio_calculator:
                                    holdings = {}
                                    positions = updated_portfolio.get('positions', {})
                                    for symbol, position_data in positions.items():
                                        if isinstance(position_data, dict):
                                            long_qty = position_data.get('long', 0)
                                            short_qty = position_data.get('short', 0)
                                            net_qty = long_qty - short_qty
                                            if net_qty != 0:
                                                long_cost = position_data.get('long_cost_basis', 0)
                                                short_cost = position_data.get('short_cost_basis', 0)
                                                avg_cost = long_cost if net_qty > 0 else short_cost
                                                holdings[symbol] = {
                                                    'quantity': net_qty,
                                                    'avg_cost': avg_cost
                                                }
                                    
                                    self.portfolio_calculator.update_holdings(
                                        holdings,
                                        updated_portfolio.get('cash', 0)
                                    )
                    
                    await self.broadcast({
                        'type': 'day_complete',
                        'date': date,
                        'phase': 'backtest',
                        'timestamp': datetime.now().isoformat()
                    })
                    
                    self.state_manager.save()
                    
                except Exception as e:
                    logger.error(f"❌ {date} 运行失败: {e}")
                    await self.broadcast({
                        'type': 'day_error',
                        'date': date,
                        'error': str(e),
                        'timestamp': datetime.now().isoformat()
                    })
                
                await asyncio.sleep(0.5)
        else:
            # ========== 无需回测，直接进入今天 ==========
            logger.info(f"📅 直接进入今天在线模式: {today}（跳过历史回测）")
            
            self.state_manager.update('status', 'live_analysis')
            self.state_manager.update('trading_days_total', 1)
            self.state_manager.update('trading_days_completed', 0)
            
            await self.broadcast({
                'type': 'system',
                'content': f'系统启动 - 直接进入今天在线模式 ({today})，无历史回测'
            })
        
        # ========== 阶段2: 今天的在线模式 ==========
        logger.info(f"===== [在线模式] {today} =====")
        self.current_phase = "live_analysis"
        self.is_today = True
        
        self.state_manager.update('status', 'live_analysis')
        self.state_manager.update('current_date', today)
        
        # 根据暂停模式发送不同的消息
        if self.pause_before_trade:
            await self.broadcast({
                'type': 'system',
                'content': f'⏸️ 进入今天在线模式 - {today}，正在进行交易决策分析（暂停模式：不执行交易）...'
            })
        else:
            await self.broadcast({
                'type': 'system',
                'content': f'进入今天在线模式 - {today}，正在进行交易决策分析...'
            })
        
        # 运行今天的分析（不执行交易）
        try:
            result = await asyncio.to_thread(
                self.thinking_fund.run_full_day_simulation,
                date=today,
                tickers=self.config.tickers,
                max_comm_cycles=self.config.max_comm_cycles,
                force_run=True,
                enable_communications=not self.config.disable_communications,
                enable_notifications=not self.config.disable_notifications
            )
            
            if result and result.get('pre_market'):
                signals = result['pre_market'].get('signals', {})
                self.state_manager.update('latest_signals', signals)
                
                await self.broadcast({
                    'type': 'system',
                    'content': f'今日交易决策完成，生成 {len(signals)} 个股票信号'
                })
        except Exception as e:
            logger.error(f"❌ 今日分析失败: {e}")
        
        # ========== 阶段3: 实时价格监控 ==========
        logger.info("===== [实时监控] 启动价格更新 =====")
        self.current_phase = "live_monitoring"
        self.state_manager.update('status', 'live_monitoring')
        
        await self.broadcast({
            'type': 'system',
            'content': '开始实时价格监控，高频更新净值曲线和持仓盈亏'
        })
        
        # 订阅实时价格（如果使用Mock模式，可能需要传入基准价格）
        if self.mock_mode:
            # Mock模式：使用当前portfolio的持仓价格作为基准
            base_prices = {}
            holdings = self.state_manager.get('holdings', [])
            for holding in holdings:
                ticker = holding.get('ticker')
                avg_price = holding.get('avg', 100.0)  # 默认100
                base_prices[ticker] = avg_price
            
            self.price_manager.subscribe(self.config.tickers, base_prices=base_prices)
        else:
            self.price_manager.subscribe(self.config.tickers)
        
        self.price_manager.start()
        logger.info(f"✅ 已订阅实时价格: {self.config.tickers}")
        
        # 检查是否需要等待收盘
        if not self.mock_mode:
            self.market_is_open = self._is_trading_hours()
            is_trading_day = self._is_trading_day()
            
            if not is_trading_day:
                await self.broadcast({
                    'type': 'system',
                    'content': '今天不是交易日，只进行价格监控'
                })
                logger.info("📅 今天不是交易日，只进行价格监控")
            elif self.market_is_open:
                close_time = self._get_market_close_time()
                if close_time:
                    close_time_str = close_time.strftime("%H:%M")
                    await self.broadcast({
                        'type': 'system',
                        'content': f'市场开盘中，预计收盘时间: {close_time_str}，等待收盘后执行交易...'
                    })
                    logger.info(f"⏳ 市场开盘中（收盘时间: {close_time_str}），将等待收盘后执行交易")
                else:
                    await self.broadcast({
                        'type': 'system',
                        'content': '市场开盘中，等待收盘后执行交易...'
                    })
                    logger.info("⏳ 市场开盘中，将等待收盘...")
                
                # TODO: 添加一个后台任务，在收盘时自动执行交易
                # 这里可以添加定时检查，当市场收盘时触发交易执行
            else:
                await self.broadcast({
                    'type': 'system',
                    'content': '市场已收盘，可执行交易（当前版本仅等待，暂不自动执行）'
                })
                logger.info("✅ 市场已收盘，可执行交易")
        else:
            await self.broadcast({
                'type': 'system',
                'content': 'Mock模式运行中，使用虚拟价格进行测试'
            })
            logger.info("🎭 Mock模式运行中")
        
        # 保持运行（持续监控价格）
        logger.info("✅ 在线模式启动完成，持续监控中...")
        logger.info(f"💡 实时数据更新频率: {'每5秒 (Mock)' if self.mock_mode else '每10秒 (Finnhub Quote API)'}")
        
        await asyncio.Future()  # 永久运行
    
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
            except Exception as e:
                logger.error(f"❌ Dashboard 文件监控异常: {e}")
    
    async def start(self, host: str = "0.0.0.0", port: int = 8001):
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
                
                if self.price_manager:
                    self.price_manager.stop()


async def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='在线交易系统服务器')
    parser.add_argument('--mock', action='store_true', help='使用Mock模式（虚拟价格测试）')
    parser.add_argument('--lookback-days', type=int, default=0, help='回溯天数（默认: 0，即不回测，直接运行今天）')
    parser.add_argument('--config-name', default='live_mode', help='配置名称（默认: live_mode）')
    parser.add_argument('--host', default='0.0.0.0', help='监听地址（默认: 0.0.0.0）')
    parser.add_argument('--port', type=int, default=8001, help='监听端口（默认: 8001）')
    parser.add_argument('--pause-before-trade', action='store_true', dest='pause_before_trade_cli', help='暂停模式：完成分析但不执行交易，仅更新价格')
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
    logger.info(f"   回溯天数: {args.lookback_days}")
    logger.info(f"   监控股票: {config.tickers}")
    if config.mode == "portfolio":
        logger.info(f"   初始现金: ${config.initial_cash:,.2f}")
        logger.info(f"   保证金要求: {config.margin_requirement * 100:.1f}%")
    if pause_before_trade:
        logger.info(f"   交易执行: ⏸️ 暂停模式（仅分析，不执行交易）[来源: {pause_source}]")
    else:
        logger.info(f"   交易执行: ▶️ 正常模式（分析后执行交易）")
    
    # 创建并启动服务器
    server = LiveTradingServer(config, mock_mode=args.mock, lookback_days=args.lookback_days, pause_before_trade=pause_before_trade)
    await server.start(host=args.host, port=args.port)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Bye!")

