# src/servers/server.py
"""
持续运行的WebSocket服务器
- 从指定日期开始持续运行交易系统
- 集成实时价格数据
- 广播状态给所有连接的客户端
"""
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Set, Dict, Any
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

import websockets
from websockets.server import WebSocketServerProtocol
from websockets.exceptions import ConnectionClosedError

from src.memory import get_memory
from src.servers.streamer import WebSocketStreamer, ConsoleStreamer, MultiStreamer, BroadcastStreamer
from src.servers.polling_price_manager import PollingPriceManager
from src.servers.state_manager import StateManager
from src.servers.mock import MockSimulator
from live_trading_thinking_fund import LiveTradingThinkingFund
from src.config.env_config import LiveThinkingFundConfig
from src.tools.data_tools import get_prices
from src.utils.progress import progress

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class Server:
    """持续运行的交易系统服务器"""
    
    def __init__(self, config: LiveThinkingFundConfig):
        self.config = config
        self.connected_clients: Set[WebSocketServerProtocol] = set()
        self.lock = asyncio.Lock()
        self.loop = None  # 事件循环引用，在start时设置
        
        # ========== 方案B：Dashboard 文件路径 ⭐⭐⭐ ==========
        self.dashboard_dir = BASE_DIR / "logs_and_memory" / config.config_name / "sandbox_logs" / "team_dashboard"
        self.dashboard_files = {
            'summary': self.dashboard_dir / 'summary.json',
            'holdings': self.dashboard_dir / 'holdings.json',
            'stats': self.dashboard_dir / 'stats.json',
            'trades': self.dashboard_dir / 'trades.json',
            'leaderboard': self.dashboard_dir / 'leaderboard.json'
        }
        # 记录文件修改时间，用于检测变化
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
        
        # 初始化实时价格管理器（使用轮询方式）
        api_key = os.getenv('FINNHUB_API_KEY', '')
        if not api_key:
            logger.warning("⚠️ 未找到 FINNHUB_API_KEY，实时价格功能将不可用")
            logger.info("   请在 .env 文件中设置 FINNHUB_API_KEY")
            logger.info("   获取免费 API Key: https://finnhub.io/register")
            self.price_manager = None
        else:
            # 使用轮询式价格管理器（每60秒更新一次）
            self.price_manager = PollingPriceManager(api_key, poll_interval=60)
            
            # 添加价格更新回调
            self.price_manager.add_price_callback(self._on_price_update)
            
            logger.info("✅ 价格轮询管理器已初始化 (间隔: 60秒)")
        
        # 记录初始资金（用于计算收益率）
        self.initial_cash = config.initial_cash
        
        # 初始化记忆系统
        console_streamer = ConsoleStreamer()
        memory_instance = get_memory(config.config_name)
        logger.info(f"✅ 记忆系统已初始化")
        
        # 记忆系统初始化完成（不需要预注册分析师）
        logger.info("✅ 记忆系统准备就绪")
        
        # 初始化交易系统（但不传入streamer，稍后在运行时创建）
        self.thinking_fund = None
    
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
        
        # 注意：不更新 summary.json 中的 equity 曲线
        # 原因：
        # 1. 对于回测模式（正常模式），净值曲线应该由回测系统（TeamDashboardGenerator）在每天结束时更新
        # 2. 实时价格更新只用于显示当前价格，不应该修改历史净值曲线
        # 3. equity 曲线的更新应该在回测过程中通过 _update_equity_curve 方法完成，而不是通过价格更新回调
        # 
        # 如果需要更新 summary.json 中的其他字段（如 balance、pnlPct）用于实时显示，
        # 可以在这里添加，但不要修改 equity 曲线
    
    async def broadcast(self, message: Dict[str, Any]):
        """广播消息给所有连接的客户端"""
        # 保存到历史记录（由StateManager处理）
        self.state_manager.add_feed_message(message)
        
        if not self.connected_clients:
            return
        
        message_json = json.dumps(message, ensure_ascii=False, default=str)
        
        # 并发发送给所有客户端
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
            # 连接已关闭，从列表中移除
            async with self.lock:
                self.connected_clients.discard(client)
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
    
    def _load_dashboard_file(self, file_type: str) -> Any:
        """
        读取 Dashboard JSON 文件
        
        Args:
            file_type: 文件类型 ('summary', 'holdings', 'stats', 'trades', 'leaderboard')
            
        Returns:
            文件内容（字典或列表），如果文件不存在或读取失败返回 None
        """
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
        """
        检查哪些 Dashboard 文件被更新了
        
        Returns:
            字典，key 为文件类型，value 为是否更新（True/False）
        """
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
        """
        从文件读取 Dashboard 数据并广播
        仅广播已更新的文件
        """
        updated_files = self._check_dashboard_files_updated()
        timestamp = datetime.now().isoformat()
        
        # 只广播有更新的文件
        for file_type, is_updated in updated_files.items():
            if not is_updated:
                continue
            
            data = self._load_dashboard_file(file_type)
            if data is None:
                continue
            
            # 根据文件类型构建消息
            if file_type == 'summary':
                await self.broadcast({
                    'type': 'team_summary',
                    'balance': data.get('balance'),
                    'pnlPct': data.get('pnlPct'),
                    'equity': data.get('equity', []),
                    'baseline': data.get('baseline', []),  # ⭐ 等权重 baseline
                    'baseline_vw': data.get('baseline_vw', []),  # ⭐ 价值加权 baseline
                    'momentum': data.get('momentum', []),  # ⭐ 动量策略
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
    
    async def handle_client(self, websocket: WebSocketServerProtocol):
        """处理客户端连接"""
        client_id = id(websocket)
        
        try:
            async with self.lock:
                self.connected_clients.add(websocket)
            
            logger.info(f"✅ 新客户端连接 (总连接数: {len(self.connected_clients)})")
            # 准备发送给新客户端的初始状态（不修改全局状态）
            initial_state = self.state_manager.get_full_state()
            
            # ========== 方案B：从文件加载 Dashboard 数据 ⭐⭐⭐ ==========
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
                
                # 将 summary 数据映射到 portfolio（供前端使用）
                if summary_data and 'portfolio' in initial_state:
                    initial_state['portfolio'].update({
                        'total_value': summary_data.get('balance'),
                        'pnl_percent': summary_data.get('pnlPct'),
                        'equity': summary_data.get('equity', []),
                        'baseline': summary_data.get('baseline', []),  # ⭐ 等权重 baseline
                        'baseline_vw': summary_data.get('baseline_vw', []),  # ⭐ 价值加权 baseline
                        'momentum': summary_data.get('momentum', [])  # ⭐ 动量策略
                    })
                
                # 更新其他数据
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
                initial_state['dashboard'] = {
                    'summary': None,
                    'holdings': [],
                    'stats': None,
                    'trades': [],
                    'leaderboard': []
                }
            
            # 加载历史equity数据并合并到portfolio（仅用于新客户端）
            historical_data = self.state_manager.load_historical_equity()
            if historical_data and 'portfolio' in initial_state:
                # 创建副本以避免修改全局状态
                initial_portfolio = dict(initial_state['portfolio'])
                
                # 只有当当前equity数据为空或少于历史数据时才合并
                current_equity = initial_portfolio.get('equity', [])
                historical_equity = historical_data.get('equity', [])
                
                if not current_equity or len(current_equity) < len(historical_equity):
                    # 合并历史数据（优先保留当前数据）
                    initial_portfolio['equity'] = historical_equity + current_equity
                    if 'baseline' in historical_data:
                        initial_portfolio['baseline'] = historical_data['baseline']
                    if 'strategies' in historical_data:
                        initial_portfolio['strategies'] = historical_data['strategies']
                
                initial_state['portfolio'] = initial_portfolio
            
            # 发送完整状态给新连接的客户端
            await websocket.send(json.dumps({
                'type': 'initial_state',
                'state': initial_state
            }, ensure_ascii=False, default=str))
            
            # 保持连接并接收消息（只读模式，不处理命令）
            try:
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        msg_type = data.get('type', 'unknown')
                        
                        # 响应心跳包
                        if msg_type == 'ping':
                            await websocket.send(json.dumps({
                                'type': 'pong',
                                'timestamp': datetime.now().isoformat()
                            }, ensure_ascii=False, default=str))
                        
                        # 可以添加一些只读查询功能
                        elif msg_type == 'get_state':
                            await websocket.send(json.dumps({
                                'type': 'state_response',
                                'state': self.state_manager.get_full_state()
                            }, ensure_ascii=False, default=str))
                            
                    except json.JSONDecodeError:
                        logger.warning("收到非JSON消息")
                    except Exception as e:
                        logger.error(f"处理消息异常: {e}")
            except websockets.ConnectionClosed as e:
                logger.debug(f"连接关闭: code={e.code}")
            except Exception as e:
                logger.error(f"连接异常: {e}")
                    
        except ConnectionClosedError as e:
            # WebSocket 握手失败或连接异常关闭
            logger.debug(f"WebSocket 连接异常关闭 (可能是浏览器刷新或网络问题)")
        except websockets.ConnectionClosed:
            # 正常断开
            logger.debug("客户端正常断开连接")
        except Exception as e:
            logger.error(f"连接处理异常: {e}")
        finally:
            # 清理：从连接池中移除
            async with self.lock:
                self.connected_clients.discard(websocket)
            logger.info(f"客户端断开 (剩余连接: {len(self.connected_clients)})")
    
    async def run_continuous_simulation(self):
        """持续运行交易模拟"""
        logger.info("🚀 开始持续运行模式")
        
        # 获取当前事件循环
        loop = asyncio.get_event_loop()
        
        # 注册progress handler来捕获agent状态更新
        def progress_handler(agent_name: str, ticker, status: str, analysis, timestamp):
            """捕获agent进度更新并广播到前端"""
            if loop.is_running():
                content = status
                if ticker:
                    content = f"[{ticker}] {status}"
                if analysis:
                    content = f"{content}: {analysis}"
                
                # asyncio.run_coroutine_threadsafe(
                #     self.broadcast({
                #         'type': 'agent_message',
                #         'agentId': agent_name,
                #         'agentName': agent_name.replace('_agent', '').replace('_', ' ').title(),
                #         'content': content,
                #         'timestamp': timestamp
                #     }),
                #     loop
                # )
        
        # 注册handler
        progress.register_handler(progress_handler)
        
        # 创建广播streamer（使用统一的BroadcastStreamer类）
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
            margin_requirement=self.config.margin_requirement
        )
        
        # 订阅实时价格
        if self.price_manager:
            self.price_manager.subscribe(self.config.tickers)
            self.price_manager.start()
            logger.info(f"✅ 已订阅实时价格: {self.config.tickers}")
        
        # 生成交易日列表
        start_date = self.config.start_date or "2025-01-07"
        end_date = self.config.end_date or datetime.now().strftime("%Y-%m-%d")
        
        trading_days = self.thinking_fund.generate_trading_dates(start_date, end_date)
        logger.info(f"📅 计划运行 {len(trading_days)} 个交易日: {start_date} -> {end_date}")
        
        self.state_manager.update('status', 'running')
        self.state_manager.update('trading_days_total', len(trading_days))
        self.state_manager.update('trading_days_completed', 0)
        
        await self.broadcast({
            'type': 'system',
            'content': f'系统启动 - 计划运行 {len(trading_days)} 个交易日'
        })
        
        # 逐日运行
        for idx, date in enumerate(trading_days, 1):
            logger.info(f"===== [{idx}/{len(trading_days)}] {date} =====")
            self.state_manager.update('current_date', date)
            self.state_manager.update('trading_days_completed', idx)
            
            await self.broadcast({
                'type': 'day_start',
                'date': date,
                'progress': idx / len(trading_days)
            })
            
            try:
                # 在独立线程中运行（避免阻塞）
                result = await asyncio.to_thread(
                    self.thinking_fund.run_full_day_simulation,
                    date=date,
                    tickers=self.config.tickers,
                    max_comm_cycles=self.config.max_comm_cycles,
                    force_run=False,
                    enable_communications=not self.config.disable_communications,
                    enable_notifications=not self.config.disable_notifications
                )
                
                # 确保result是字典类型
                if not isinstance(result, dict):
                    logger.warning(f"⚠️ Unexpected result type: {type(result)}, value: {result}")
                    result = {}
                
                # 更新当前状态和提取portfolio_summary
                portfolio_summary = None
                if result.get('pre_market'):
                    signals = result['pre_market'].get('signals', {})
                    self.state_manager.update('latest_signals', signals)
                    
                    # 更新Portfolio持仓（如果是portfolio模式）⭐ 修复bug
                    if self.config.mode == "portfolio":
                        live_env = result['pre_market'].get('live_env', {})
                        portfolio_summary = live_env.get('portfolio_summary', {})
                        updated_portfolio = live_env.get('updated_portfolio', {})
                        
                        if portfolio_summary and updated_portfolio:
                            # 注意：正常模式（回测模式）不需要portfolio_calculator
                            # portfolio数据由回测系统（TeamDashboardGenerator）更新，并写入Dashboard文件
                            # 这里只更新内存中的状态用于前端显示，不进行实时计算
                            
                            # 更新portfolio状态（从回测结果中读取）
                            portfolio = self.state_manager.get('portfolio', {})
                            portfolio.update({
                                'total_value': portfolio_summary.get('total_value'),
                                'cash': portfolio_summary.get('cash'),
                                'pnl_percent': portfolio_summary.get('pnl_percent', 0)
                            })
                            self.state_manager.update('portfolio', portfolio)
                            
                            # 更新holdings（转换为前端格式）⭐ 修复bug
                            realtime_prices = self.state_manager.get('realtime_prices', {})
                            holdings_list = []
                            positions = updated_portfolio.get('positions', {})
                            for symbol, position_data in positions.items():
                                if isinstance(position_data, dict):
                                    long_qty = position_data.get('long', 0)
                                    short_qty = position_data.get('short', 0)
                                    net_qty = long_qty - short_qty
                                    
                                    if net_qty != 0:  # 只显示有持仓的股票
                                        long_cost = position_data.get('long_cost_basis', 0)
                                        short_cost = position_data.get('short_cost_basis', 0)
                                        avg_price = long_cost if net_qty > 0 else short_cost
                                        current_price = realtime_prices.get(symbol, {}).get('price', avg_price)
                                        
                                        holdings_list.append({
                                            'ticker': symbol,
                                            'qty': net_qty,
                                            'avg': avg_price,
                                            'currentPrice': current_price,
                                            'pl': (current_price - avg_price) * net_qty,
                                            'weight': 0  # 权重需要另外计算
                                        })
                            self.state_manager.update('holdings', holdings_list)
                
                # 构建简化的result用于广播（避免发送过大的数据）
                broadcast_result = {
                    'portfolio_summary': portfolio_summary
                }
                
                await self.broadcast({
                    'type': 'day_complete',
                    'date': date,
                    'result': broadcast_result,
                    'timestamp': datetime.now().isoformat()
                })
                
                # 保存状态（每天结束后）
                self.state_manager.save()
                
            except Exception as e:
                logger.error(f"❌ {date} 运行失败: {e}")
                await self.broadcast({
                    'type': 'day_error',
                    'date': date,
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                })
            
            # 短暂延迟（避免过快）
            await asyncio.sleep(1)
        
        logger.info("✅ 所有交易日运行完成")
        self.state_manager.update('status', 'completed')
        
        await self.broadcast({
            'type': 'system',
            'content': '所有交易日运行完成'
        })
        
        # 清理：取消注册progress handler
        progress.unregister_handler(progress_handler)
    
    async def _periodic_state_saver(self):
        """定期保存状态（每5分钟）"""
        while True:
            await asyncio.sleep(300)  # 5分钟
            self.state_manager.save()
    
    async def _periodic_dashboard_monitor(self):
        """
        定期监控 Dashboard 文件变化并广播（每5秒）
        方案B的核心：通过文件监控实现数据广播
        """
        logger.info("🔍 Dashboard 文件监控已启动（每5秒检查一次）")
        
        while True:
            try:
                await asyncio.sleep(5)  # 每5秒检查一次
                await self._broadcast_dashboard_from_files()
            except Exception as e:
                logger.error(f"❌ Dashboard 文件监控异常: {e}")
    
    async def start(self, host: str = "0.0.0.0", port: int = 8001, mock: bool = False):
        """启动服务器
        
        Args:
            host: 监听地址
            port: 监听端口
            mock: 是否使用mock模式（用于测试前端）
        """
        # 保存事件循环引用
        self.loop = asyncio.get_event_loop()
        
        # 加载已保存的状态（如果存在）
        if not mock:
            self.state_manager.load()
        
        # 启动WebSocket服务器（禁用自动ping，由客户端管理心跳）
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
            
            dashboard_monitor_task = None
            if not mock:
                dashboard_monitor_task = asyncio.create_task(self._periodic_dashboard_monitor())
            
            # 选择运行模式
            if mock:
                logger.info("🎭 使用Mock模式")
                mock_simulator = MockSimulator(
                    state_manager=self.state_manager,
                    broadcast_callback=self.broadcast,
                    initial_cash=self.config.initial_cash
                )
                simulation_task = asyncio.create_task(mock_simulator.run())
            else:
                logger.info("🚀 使用真实交易模式")
                simulation_task = asyncio.create_task(self.run_continuous_simulation())
            
            # 保持运行
            try:
                await simulation_task
                # 模拟完成后保持服务器运行（继续广播实时价格）
                await asyncio.Future()  # 永久运行
            except KeyboardInterrupt:
                logger.info("收到中断信号，正在关闭...")
            finally:
                # 最终保存一次状态
                self.state_manager.save()
                logger.info("✅ 最终状态已保存")
                
                # 取消定期保存任务
                saver_task.cancel()
                
                if dashboard_monitor_task:
                    dashboard_monitor_task.cancel()
                    logger.info("✅ Dashboard 监控任务已取消")
                
                if self.price_manager:
                    self.price_manager.stop()


async def main():
    """主函数"""
    import argparse
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='持续运行的交易系统服务器')
    parser.add_argument('--mock', action='store_true', help='使用Mock模式（测试前端）')
    parser.add_argument('--host', default='0.0.0.0', help='监听地址 (默认: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=8001, help='监听端口 (默认: 8001)')
    args = parser.parse_args()
    
    # 加载配置
    config = LiveThinkingFundConfig()
    config.config_name = "mock"
    
    # 打印配置
    logger.info("📊 服务器配置:")
    logger.info(f"   配置名称: {config.config_name}")
    logger.info(f"   运行模式: {'🎭 MOCK' if args.mock else config.mode.upper()}")
    logger.info(f"   监控股票: {config.tickers}")
    if config.mode == "portfolio":
        logger.info(f"   初始现金: ${config.initial_cash:,.2f}")
        logger.info(f"   保证金要求: {config.margin_requirement * 100:.1f}%")
    
    # 创建并启动服务器
    server = Server(config)
    await server.start(host=args.host, port=args.port, mock=args.mock)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Bye!")

