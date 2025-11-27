# -*- coding: utf-8 -*-
# backend/servers/server.py
"""
Continuously running WebSocket server
- Continuously runs trading system from specified date
- Integrates real-time price data
- Broadcasts status to all connected clients
"""
# flake8: noqa: E501
# pylint: disable=C0301
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Set

import websockets
from dotenv import load_dotenv
from websockets.exceptions import ConnectionClosedError
from websockets.server import WebSocketServerProtocol

from backend.config.env_config import LiveThinkingFundConfig
from backend.config.path_config import get_logs_and_memory_dir
from backend.pipelines.live_trading_fund import LiveTradingFund
from backend.servers.mock import MockSimulator
from backend.servers.polling_price_manager import PollingPriceManager
from backend.servers.state_manager import StateManager
from backend.servers.streamer import BroadcastStreamer
from backend.utils.progress import progress

BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))


load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


class Server:
    """Continuously running trading system server"""

    def __init__(self, config: LiveThinkingFundConfig):
        self.config = config
        self.connected_clients: Set[WebSocketServerProtocol] = set()
        self.lock = asyncio.Lock()
        self.loop = None  # Event loop reference, set in start method

        # ========== Solution B: Dashboard file paths ⭐⭐⭐ ==========
        self.dashboard_dir = (
            get_logs_and_memory_dir()
            / config.config_name
            / "sandbox_logs"
            / "team_dashboard"
        )
        self.dashboard_files = {
            "summary": self.dashboard_dir / "summary.json",
            "holdings": self.dashboard_dir / "holdings.json",
            "stats": self.dashboard_dir / "stats.json",
            "trades": self.dashboard_dir / "trades.json",
            "leaderboard": self.dashboard_dir / "leaderboard.json",
        }
        # Record file modification times for change detection
        self.dashboard_file_mtimes = {}
        logger.info(f"✅ Dashboard file directory: {self.dashboard_dir}")

        # Use StateManager to manage state
        self.state_manager = StateManager(
            config_name=config.config_name,
            base_dir=BASE_DIR,
            max_history=200,
        )

        # Initialize portfolio state
        self.state_manager.update(
            "portfolio",
            {
                "total_value": config.initial_cash,
                "cash": config.initial_cash,
                "pnl_percent": 0,
                "equity": [],
                "baseline": [],
                "baseline_vw": [],
                "momentum": [],
                "strategies": [],
            },
        )

        # ⭐ add lock: disable real-time price update
        enable_realtime_price = False

        if enable_realtime_price:
            api_key = os.getenv("FINNHUB_API_KEY", "")
            if not api_key:
                logger.warning(
                    "⚠️ FINNHUB_API_KEY not found, real-time price feature will be unavailable",
                )
                logger.info("   Please set FINNHUB_API_KEY in .env file")
                logger.info("   Get free API Key: https://finnhub.io/register")
                self.price_manager = None
            else:
                # Use polling price manager (updates every 60 seconds)
                self.price_manager = PollingPriceManager(
                    api_key,
                    poll_interval=60,
                )

                # Add price update callback
                self.price_manager.add_price_callback(self._on_price_update)

                logger.info(
                    "✅ Price polling manager initialized (interval: 60 seconds)",
                )
        else:
            self.price_manager = None

        # Record initial cash (for calculating returns)
        self.initial_cash = config.initial_cash

        # Initialize memory system
        # console_streamer = ConsoleStreamer()
        # memory_instance = get_memory(config.config_name)
        logger.info("✅ Memory system initialized")

        # Memory system initialization complete (no need to pre-register analysts)
        logger.info("✅ Memory system ready")

        # Initialize trading system (but don't pass streamer, will create at runtime)
        self.thinking_fund = None

        # Initialize dashboard files if they don't exist (including leaderboard with model info)
        self._ensure_dashboard_initialized()

    def _ensure_dashboard_initialized(self):
        """
        Ensure dashboard files are initialized and model info is up-to-date
        This runs at server startup to immediately show correct model cards in frontend
        """
        from backend.dashboard.team_dashboard import TeamDashboardGenerator

        # Create dashboard generator
        dashboard_generator = TeamDashboardGenerator(
            dashboard_dir=self.dashboard_dir,
            initial_cash=self.initial_cash,
        )

        # Check if leaderboard file exists
        if not self.dashboard_files["leaderboard"].exists():
            logger.info(
                "📊 Initializing dashboard files with agent model configuration...",
            )

            # Initialize all dashboard files with default values
            dashboard_generator.initialize_empty_dashboard(state={})
            logger.info(
                "✅ Dashboard initialized with agent model configuration",
            )
        else:
            # Update model information in existing leaderboard
            # This ensures frontend always shows latest model config from environment variables
            logger.info(
                "📊 Updating agent model information from environment variables...",
            )
            dashboard_generator.update_leaderboard_model_info()
            logger.info("✅ Agent model information updated")

    def _on_price_update(self, price_data: Dict[str, Any]):
        """Price update callback - directly updates holdings.json and stats.json files"""
        symbol = price_data["symbol"]
        price = price_data["price"]
        open_price = price_data.get("open", price)

        # Calculate return relative to open price
        ret = (
            ((price - open_price) / open_price) * 100 if open_price > 0 else 0
        )

        # Update current state (for price board display)
        realtime_prices = self.state_manager.get("realtime_prices", {})
        realtime_prices[symbol] = {
            "price": price,
            "open": open_price,
            "ret": ret,
            "timestamp": price_data.get("timestamp"),
            "volume": price_data.get("volume"),
        }
        self.state_manager.update("realtime_prices", realtime_prices)

        # Broadcast price update (for real-time price board display)
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.broadcast(
                    {
                        "type": "price_update",
                        "symbol": symbol,
                        "price": price,
                        "open": open_price,
                        "ret": ret,
                        "timestamp": price_data.get("timestamp"),
                        "realtime_prices": realtime_prices,
                    },
                ),
                self.loop,
            )

        # # Update holdings.json and stats.json files
        # try:
        #     self._update_dashboard_files_with_price(symbol, price)
        # except Exception as e:
        #     logger.error(f"Failed to update Dashboard files ({symbol}): {e}")

    def _update_dashboard_files_with_price(self, symbol: str, price: float):
        """Update prices and related calculations in holdings.json, stats.json and summary.json files"""

        # Load all dashboard files
        holdings, stats, _summary = self._load_dashboard_files()
        if holdings is None or stats is None:
            return

        # Update holdings and calculate totals
        updated, total_value, cash = self._update_holdings_data(
            holdings,
            symbol,
            price,
        )

        if not updated:
            return

        # Recalculate weights
        self._recalculate_holdings_weights(holdings, total_value)

        # Save updated holdings
        self._save_dashboard_file(
            "holdings",
            holdings,
            f"Updated holdings.json: {symbol} = ${price:.2f}",
        )

        # Update and save stats
        self._update_and_save_stats(stats, holdings, total_value, cash)

    def _load_dashboard_files(self):
        """Load holdings, stats, and summary files"""
        holdings_file = self.dashboard_files.get("holdings")
        stats_file = self.dashboard_files.get("stats")
        summary_file = self.dashboard_files.get("summary")

        # Validate files exist
        if not self._validate_file_exists(holdings_file, "holdings.json"):
            return None, None, None
        if not self._validate_file_exists(stats_file, "stats.json"):
            return None, None, None

        # Load files
        holdings = self._load_json_file(holdings_file, "holdings.json")
        stats = self._load_json_file(stats_file, "stats.json")
        summary = None

        if summary_file and summary_file.exists():
            summary = self._load_json_file(summary_file, "summary.json")

        return holdings, stats, summary

    def _validate_file_exists(self, file_path, file_name: str) -> bool:
        """Check if file exists and log warning if not"""
        if not file_path or not file_path.exists():
            logger.warning(f"{file_name} file does not exist, skipping update")
            return False
        return True

    def _load_json_file(self, file_path, file_name: str):
        """Load JSON file with error handling"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read {file_name}: {e}")
            return None

    def _update_holdings_data(
        self,
        holdings: list,
        symbol: str,
        price: float,
    ) -> tuple:
        """Update holdings data with new price and return (updated, total_value, cash)"""
        updated = False
        total_value = 0.0
        cash = 0.0

        for holding in holdings:
            ticker = holding.get("ticker")
            quantity = holding.get("quantity", 0)

            if ticker == "CASH":
                cash = holding.get("marketValue", 0)
                total_value += cash
            elif ticker == symbol:
                # Update target symbol
                holding["currentPrice"] = round(price, 2)
                market_value = quantity * price
                holding["marketValue"] = round(market_value, 2)
                total_value += market_value
                updated = True
            else:
                # Accumulate other holdings
                total_value += holding.get("marketValue", 0)

        return updated, total_value, cash

    def _recalculate_holdings_weights(
        self,
        holdings: list,
        total_value: float,
    ):
        """Recalculate weight for each holding"""
        if total_value <= 0:
            return

        for holding in holdings:
            market_value = holding.get("marketValue", 0)
            weight = market_value / total_value
            holding["weight"] = round(weight, 4)

    def _save_dashboard_file(
        self,
        file_key: str,
        data,
        success_message: str = None,
    ):
        """Save data to dashboard file"""
        file_path = self.dashboard_files.get(file_key)
        if not file_path:
            return False

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            if success_message:
                logger.debug(f"✅ {success_message}")
            return True
        except Exception as e:
            logger.error(f"Failed to save {file_key}.json: {e}")
            return False

    def _update_and_save_stats(
        self,
        stats: dict,
        holdings: list,
        total_value: float,
        cash: float,
    ):
        """Update stats data and save to file"""
        total_return = (
            ((total_value - self.initial_cash) / self.initial_cash * 100)
            if self.initial_cash > 0
            else 0.0
        )

        # Build ticker weights
        ticker_weights = {
            holding.get("ticker"): holding.get("weight", 0)
            for holding in holdings
            if holding.get("ticker") != "CASH"
        }

        # Update stats
        stats.update(
            {
                "totalAssetValue": round(total_value, 2),
                "totalReturn": round(total_return, 2),
                "cashPosition": round(cash, 2),
                "tickerWeights": ticker_weights,
            },
        )

        # Save stats file
        self._save_dashboard_file(
            "stats",
            stats,
            f"Updated stats.json: Total assets=${total_value:.2f}, Return={total_return:.2f}%",
        )

    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast message to all connected clients"""
        # Save to history (handled by StateManager)
        self.state_manager.add_feed_message(message)

        if not self.connected_clients:
            return

        message_json = json.dumps(message, ensure_ascii=False, default=str)

        # Concurrently send to all clients
        tasks = []
        async with self.lock:
            for client in self.connected_clients.copy():
                tasks.append(self._send_to_client(client, message_json))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_to_client(
        self,
        client: WebSocketServerProtocol,
        message: str,
    ):
        """Send message to single client"""
        try:
            await client.send(message)
        except websockets.ConnectionClosed:
            # Connection closed, remove from list
            async with self.lock:
                self.connected_clients.discard(client)
        except Exception as e:
            logger.error(f"Failed to send message: {e}")

    def _load_dashboard_file(self, file_type: str) -> Any:
        """
        Read Dashboard JSON file

        Args:
            file_type: File type ('summary', 'holdings', 'stats', 'trades', 'leaderboard')

        Returns:
            File content (dict or list), returns None if file doesn't exist or read fails
        """
        file_path = self.dashboard_files.get(file_type)
        if not file_path or not file_path.exists():
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read Dashboard file ({file_type}): {e}")
            return None

    def _check_dashboard_files_updated(self) -> Dict[str, bool]:
        """
        Check which Dashboard files have been updated

        Returns:
            Dictionary, key is file type, value is whether updated (True/False)
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
                logger.error(f"Failed to check file update ({file_type}): {e}")
                updated[file_type] = False

        return updated

    async def _broadcast_dashboard_from_files(self):
        """
        Read Dashboard data from files and broadcast
        Only broadcast updated files
        """
        updated_files = self._check_dashboard_files_updated()
        timestamp = datetime.now().isoformat()

        # Only broadcast files that have been updated
        for file_type, is_updated in updated_files.items():
            if not is_updated:
                continue

            data = self._load_dashboard_file(file_type)
            if data is None:
                continue

            # Build message based on file type
            if file_type == "summary":
                await self.broadcast(
                    {
                        "type": "team_summary",
                        "balance": data.get("balance"),
                        "pnlPct": data.get("pnlPct"),
                        "equity": data.get("equity", []),
                        "baseline": data.get(
                            "baseline",
                            [],
                        ),  # ⭐ Equal-weight baseline
                        "baseline_vw": data.get(
                            "baseline_vw",
                            [],
                        ),  # ⭐ Value-weighted baseline
                        "momentum": data.get(
                            "momentum",
                            [],
                        ),  # ⭐ Momentum strategy
                        "timestamp": timestamp,
                    },
                )
                logger.info("✅ Broadcast team_summary (from file)")

            elif file_type == "holdings":
                self.state_manager.update("holdings", data)
                await self.broadcast(
                    {
                        "type": "team_holdings",
                        "data": data,
                        "timestamp": timestamp,
                    },
                )
                logger.info(
                    f"✅ Broadcast team_holdings: {len(data)} holdings (from file)",
                )

            elif file_type == "stats":
                self.state_manager.update("stats", data)
                await self.broadcast(
                    {
                        "type": "team_stats",
                        "data": data,
                        "timestamp": timestamp,
                    },
                )
                logger.info("✅ Broadcast team_stats (from file)")

            elif file_type == "trades":
                self.state_manager.update("trades", data)
                await self.broadcast(
                    {
                        "type": "team_trades",
                        "mode": "full",
                        "data": data,
                        "timestamp": timestamp,
                    },
                )
                logger.info(
                    f"✅ Broadcast team_trades: {len(data)} trades (from file)",
                )

            elif file_type == "leaderboard":
                self.state_manager.update("leaderboard", data)
                await self.broadcast(
                    {
                        "type": "team_leaderboard",
                        "data": data,
                        "timestamp": timestamp,
                    },
                )
                logger.info(
                    f"✅ Broadcast team_leaderboard: {len(data)} Agents (from file)",
                )

    async def handle_client(self, websocket: WebSocketServerProtocol):
        """Handle client connection"""
        try:
            await self._register_client(websocket)
            initial_state = await self._prepare_initial_state()
            await self._send_initial_state(websocket, initial_state)
            await self._handle_client_messages(websocket)
        except (ConnectionClosedError, websockets.ConnectionClosed) as e:
            self._log_connection_closed(e)
        except Exception as e:
            logger.error(f"Connection handling error: {e}")
        finally:
            await self._unregister_client(websocket)

    async def _register_client(self, websocket: WebSocketServerProtocol):
        """Register a new client connection"""
        async with self.lock:
            self.connected_clients.add(websocket)
        logger.info(
            f"✅ New client connected (total connections: {len(self.connected_clients)})",
        )

    async def _unregister_client(self, websocket: WebSocketServerProtocol):
        """Unregister a client connection"""
        async with self.lock:
            self.connected_clients.discard(websocket)
        logger.info(
            f"Client disconnected (remaining connections: {len(self.connected_clients)})",
        )

    async def _prepare_initial_state(self) -> dict:
        """Prepare initial state for new client"""
        initial_state = self.state_manager.get_full_state()

        # Load dashboard data
        self._load_dashboard_data(initial_state)

        # Load historical equity data
        self._load_historical_equity(initial_state)

        # Set server mode
        self._set_server_mode(initial_state)

        return initial_state

    def _load_dashboard_data(self, initial_state: dict):
        """Load dashboard data from files"""
        try:
            dashboard_files = {
                "summary": self._load_dashboard_file("summary"),
                "holdings": self._load_dashboard_file("holdings"),
                "stats": self._load_dashboard_file("stats"),
                "trades": self._load_dashboard_file("trades"),
                "leaderboard": self._load_dashboard_file("leaderboard"),
            }

            initial_state["dashboard"] = dashboard_files

            # Update portfolio with summary data
            self._update_portfolio_from_summary(
                initial_state,
                dashboard_files["summary"],
            )

            # Update other state sections
            self._update_state_sections(initial_state, dashboard_files)

            logger.info("✅ Successfully loaded Dashboard data from files")

        except Exception as e:
            logger.error(f"⚠️ Failed to load Dashboard data from files: {e}")
            initial_state["dashboard"] = {
                "summary": None,
                "holdings": [],
                "stats": None,
                "trades": [],
                "leaderboard": [],
            }

    def _update_portfolio_from_summary(
        self,
        initial_state: dict,
        summary_data: dict,
    ):
        """Update portfolio section with summary data"""
        if not summary_data or "portfolio" not in initial_state:
            return

        initial_state["portfolio"].update(
            {
                "total_value": summary_data.get("balance"),
                "pnl_percent": summary_data.get("pnlPct"),
                "equity": summary_data.get("equity", []),
                "baseline": summary_data.get("baseline", []),
                "baseline_vw": summary_data.get("baseline_vw", []),
                "momentum": summary_data.get("momentum", []),
            },
        )

    def _update_state_sections(
        self,
        initial_state: dict,
        dashboard_files: dict,
    ):
        """Update various state sections with dashboard data"""
        section_mapping = {
            "holdings": "holdings",
            "stats": "stats",
            "trades": "trades",
            "leaderboard": "leaderboard",
        }

        for key, section in section_mapping.items():
            if dashboard_files[key]:
                initial_state[section] = dashboard_files[key]

    def _load_historical_equity(self, initial_state: dict):
        """Load and merge historical equity data"""
        historical_data = self.state_manager.load_historical_equity()

        if not historical_data or "portfolio" not in initial_state:
            return

        initial_portfolio = dict(initial_state["portfolio"])
        current_equity = initial_portfolio.get("equity", [])
        historical_equity = historical_data.get("equity", [])

        # Merge if historical data is more complete
        if not current_equity or len(current_equity) < len(historical_equity):
            initial_portfolio["equity"] = historical_equity + current_equity

            if "baseline" in historical_data:
                initial_portfolio["baseline"] = historical_data["baseline"]
            if "strategies" in historical_data:
                initial_portfolio["strategies"] = historical_data["strategies"]

            initial_state["portfolio"] = initial_portfolio

    def _set_server_mode(self, initial_state: dict):
        """Set server mode and market status"""
        initial_state["server_mode"] = "backtest"
        initial_state["market_status"] = {
            "status": "backtest",
            "status_text": "Backtest Mode",
        }

    async def _send_initial_state(
        self,
        websocket: WebSocketServerProtocol,
        state: dict,
    ):
        """Send initial state to client"""
        message = json.dumps(
            {
                "type": "initial_state",
                "state": state,
            },
            ensure_ascii=False,
            default=str,
        )
        await websocket.send(message)

    async def _handle_client_messages(
        self,
        websocket: WebSocketServerProtocol,
    ):
        """Handle incoming messages from client"""
        async for message in websocket:
            try:
                data = json.loads(message)
                await self._process_message(websocket, data)
            except json.JSONDecodeError:
                logger.warning("Received non-JSON message")
            except Exception as e:
                logger.error(f"Error processing message: {e}")

    async def _process_message(
        self,
        websocket: WebSocketServerProtocol,
        data: dict,
    ):
        """Process a single client message"""
        msg_type = data.get("type", "unknown")

        handlers = {
            "ping": self._handle_ping,
            "get_state": self._handle_get_state,
        }

        handler = handlers.get(msg_type)
        if handler:
            await handler(websocket, data)

    async def _handle_ping(
        self,
        websocket: WebSocketServerProtocol,
        _data: dict,
    ):
        """Handle ping message"""
        response = json.dumps(
            {
                "type": "pong",
                "timestamp": datetime.now().isoformat(),
            },
            ensure_ascii=False,
            default=str,
        )
        await websocket.send(response)

    async def _handle_get_state(
        self,
        websocket: WebSocketServerProtocol,
        _data: dict,
    ):
        """Handle get_state message"""
        response = json.dumps(
            {
                "type": "state_response",
                "state": self.state_manager.get_full_state(),
            },
            ensure_ascii=False,
            default=str,
        )
        await websocket.send(response)

    def _log_connection_closed(self, error: Exception):
        """Log connection closed events"""
        if isinstance(error, ConnectionClosedError):
            logger.debug(
                "WebSocket connection closed abnormally "
                "(may be browser refresh or network issue)",
            )
        elif isinstance(error, websockets.ConnectionClosed):
            logger.debug("Client disconnected normally")

    async def run_continuous_simulation(self):
        """Continuously run trading simulation"""
        logger.info("🚀 Starting continuous running mode")

        # Get current event loop
        loop = asyncio.get_event_loop()

        # Register progress handler to capture agent status updates
        def progress_handler(
            _agent_name: str,
            ticker,
            status: str,
            analysis,
            _timestamp,
        ):
            """Capture agent progress updates and broadcast to frontend"""
            if loop.is_running():
                content = status
                if ticker:
                    content = f"[{ticker}] {status}"
                if analysis:
                    content = f"{content}: {analysis}"

        # Register handler
        progress.register_handler(progress_handler)

        try:
            # Initialize components
            await self._initialize_trading_system(loop)

            # Generate and validate trading days
            trading_days = self._prepare_trading_days()

            # Setup initial state
            self._setup_initial_state(trading_days)
            await self._broadcast_system_start(trading_days)

            # Run simulation for each trading day
            await self._run_trading_days(trading_days)

            # Finalize
            await self._finalize_simulation()

        finally:
            # Cleanup: unregister progress handler
            progress.unregister_handler(progress_handler)

    async def _initialize_trading_system(self, loop):
        """Initialize trading system components"""
        # Create broadcast streamer
        broadcast_streamer = BroadcastStreamer(
            broadcast_callback=self.broadcast,
            event_loop=loop,
            console_output=True,
        )

        # Initialize trading system
        self.thinking_fund = LiveTradingFund(
            config_name=self.config.config_name,
            streamer=broadcast_streamer,
            mode=self.config.mode,
            initial_cash=self.config.initial_cash,
            margin_requirement=self.config.margin_requirement,
        )

        # Subscribe to real-time prices
        if self.price_manager:
            self.price_manager.subscribe(self.config.tickers)
            self.price_manager.start()
            logger.info(
                f"✅ Subscribed to real-time prices: {self.config.tickers}",
            )

    def _prepare_trading_days(self):
        """Generate and validate trading days"""
        start_date = self.config.start_date
        end_date = self.config.end_date

        logger.info(f"📅 Using date range: {start_date} -> {end_date}")

        trading_days = self.thinking_fund.generate_trading_dates(
            start_date,
            end_date,
        )
        logger.info(f"📅 Planning to run {len(trading_days)} trading days")

        return trading_days

    def _setup_initial_state(self, trading_days):
        """Setup initial state before simulation"""
        self.state_manager.update("status", "running")
        self.state_manager.update("trading_days_total", len(trading_days))
        self.state_manager.update("trading_days_completed", 0)

    async def _broadcast_system_start(self, trading_days):
        """Broadcast system start message"""
        await self.broadcast(
            {
                "type": "system",
                "content": f"System started - Planning to run {len(trading_days)} trading days",
            },
        )

    async def _run_trading_days(self, trading_days):
        """Run simulation for each trading day"""
        for idx, date in enumerate(trading_days, 1):
            await self._run_single_day(date, idx, len(trading_days))
            await asyncio.sleep(1)  # Brief delay

    async def _run_single_day(self, date, idx, total_days):
        """Run simulation for a single trading day"""
        logger.info(f"===== [{idx}/{total_days}] {date} =====")

        # Update state
        self.state_manager.update("current_date", date)
        self.state_manager.update("trading_days_completed", idx)
        self.state_manager.start_new_day()

        await self.broadcast(
            {
                "type": "day_start",
                "date": date,
                "progress": idx / total_days,
            },
        )

        # Run day simulation
        result = await self._execute_day_simulation(date)

        # Process results
        await self._process_day_results(date, result)

        # Save state
        self.state_manager.end_current_day()
        self.state_manager.save()

    async def _execute_day_simulation(self, date):
        """Execute the actual day simulation"""
        result = await asyncio.to_thread(
            self.thinking_fund.run_full_day_simulation,
            date=date,
            tickers=self.config.tickers,
            max_comm_cycles=self.config.max_comm_cycles,
            enable_communications=not self.config.disable_communications,
            enable_notifications=not self.config.disable_notifications,
        )

        # Ensure result is dict type
        if not isinstance(result, dict):
            logger.warning(
                f"⚠️ Unexpected result type: {type(result)}, value: {result}",
            )
            return {}

        return result

    async def _process_day_results(self, date, result):
        """Process and broadcast day results"""
        portfolio_summary = self._update_state_from_result(result)

        await self.broadcast(
            {
                "type": "day_complete",
                "date": date,
                "result": {"portfolio_summary": portfolio_summary},
                "timestamp": datetime.now().isoformat(),
            },
        )

    def _update_state_from_result(self, result):
        """Update state manager from simulation result"""
        portfolio_summary = None

        if not result.get("pre_market"):
            return portfolio_summary

        # Update signals
        signals = result["pre_market"]["live_env"].get("pm_signals", {})
        self.state_manager.update("latest_signals", signals)

        # Update portfolio if in portfolio mode
        if self.config.mode == "portfolio":
            portfolio_summary = self._update_portfolio_state(
                result["pre_market"],
            )

        return portfolio_summary

    def _update_portfolio_state(self, pre_market_data):
        """Update portfolio state from pre-market data"""
        live_env = pre_market_data.get("live_env", {})
        portfolio_summary = live_env.get("portfolio_summary", {})
        updated_portfolio = live_env.get("updated_portfolio", {})

        if not (portfolio_summary and updated_portfolio):
            return None

        # Update portfolio summary
        portfolio = self.state_manager.get("portfolio", {})
        portfolio.update(
            {
                "total_value": portfolio_summary.get("total_value"),
                "cash": portfolio_summary.get("cash"),
                "pnl_percent": portfolio_summary.get("pnl_percent", 0),
            },
        )
        self.state_manager.update("portfolio", portfolio)

        # Update holdings
        holdings_list = self._build_holdings_list(updated_portfolio)
        self.state_manager.update("holdings", holdings_list)

        return portfolio_summary

    def _build_holdings_list(self, updated_portfolio):
        """Build holdings list from portfolio positions"""
        realtime_prices = self.state_manager.get("realtime_prices", {})
        holdings_list = []

        positions = updated_portfolio.get("positions", {})
        for symbol, position_data in positions.items():
            if not isinstance(position_data, dict):
                continue

            holding = self._create_holding_entry(
                symbol,
                position_data,
                realtime_prices,
            )
            if holding:
                holdings_list.append(holding)

        return holdings_list

    def _create_holding_entry(self, symbol, position_data, realtime_prices):
        """Create a single holding entry"""
        long_qty = position_data.get("long", 0)
        short_qty = position_data.get("short", 0)
        net_qty = long_qty - short_qty

        if net_qty == 0:
            return None

        long_cost = position_data.get("long_cost_basis", 0)
        short_cost = position_data.get("short_cost_basis", 0)
        avg_price = long_cost if net_qty > 0 else short_cost
        current_price = realtime_prices.get(symbol, {}).get("price", avg_price)

        return {
            "ticker": symbol,
            "qty": net_qty,
            "avg": avg_price,
            "currentPrice": current_price,
            "pl": (current_price - avg_price) * net_qty,
            "weight": 0,
        }

    async def _finalize_simulation(self):
        """Finalize simulation after all days complete"""
        logger.info("✅ All trading days completed")
        self.state_manager.update("status", "completed")

        await self.broadcast(
            {
                "type": "system",
                "content": "All trading days completed",
            },
        )

    async def _periodic_state_saver(self):
        """Periodically save state (every 5 minutes)"""
        while True:
            await asyncio.sleep(300)  # 5 minutes
            self.state_manager.save()

    async def _periodic_dashboard_monitor(self):
        """
        Periodically monitor Dashboard file changes and broadcast (every 5 seconds)
        Core of Solution B: Implement data broadcast through file monitoring
        """
        logger.info(
            "🔍 Dashboard file monitor started (checks every 5 seconds)",
        )

        while True:
            try:
                await asyncio.sleep(5)  # Check every 5 seconds
                await self._broadcast_dashboard_from_files()
            except Exception as e:
                logger.error(f"❌ Dashboard file monitor error: {e}")

    async def start(
        self,
        host: str = "0.0.0.0",
        port: int = 8766,
        mock: bool = False,
    ):
        """Start server

        Args:
            host: Listen address
            port: Listen port
            mock: Whether to use mock mode (for testing frontend)
        """
        # Save event loop reference
        self.loop = asyncio.get_event_loop()

        # Load saved state (if exists)
        if not mock:
            self.state_manager.load()

        # Start WebSocket server (disable auto ping, client manages heartbeat)
        async with websockets.serve(
            self.handle_client,
            host,
            port,
            ping_interval=None,
            ping_timeout=None,
        ):
            logger.info(f"🌐 WebSocket server started: ws://{host}:{port}")

            # Start periodic save task
            saver_task = asyncio.create_task(self._periodic_state_saver())

            dashboard_monitor_task = None
            if not mock:
                dashboard_monitor_task = asyncio.create_task(
                    self._periodic_dashboard_monitor(),
                )

            # Choose run mode
            if mock:
                logger.info("🎭 Using Mock mode")
                mock_simulator = MockSimulator(
                    state_manager=self.state_manager,
                    broadcast_callback=self.broadcast,
                    initial_cash=self.config.initial_cash,
                )
                simulation_task = asyncio.create_task(mock_simulator.run())
            else:
                logger.info("🚀 Using real trading mode")
                simulation_task = asyncio.create_task(
                    self.run_continuous_simulation(),
                )

            # Keep running
            try:
                await simulation_task
                # Keep server running after simulation completes (continue broadcasting real-time prices)
                await asyncio.Future()  # Run forever
            except KeyboardInterrupt:
                logger.info("Received interrupt signal, shutting down...")
            finally:
                # Final save state once
                self.state_manager.save()
                logger.info("✅ Final state saved")

                # Cancel periodic save task
                saver_task.cancel()

                if dashboard_monitor_task:
                    dashboard_monitor_task.cancel()
                    logger.info("✅ Dashboard monitor task cancelled")

                if self.price_manager:
                    self.price_manager.stop()


async def main():
    """Main function"""
    import argparse

    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Continuously running trading system server",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use Mock mode (test frontend)",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Listen address (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8766,
        help="Listen port (default: 8766)",
    )
    parser.add_argument(
        "--config-name",
        default="backtest",
        help="Config name (default: backtest)",
    )
    parser.add_argument(
        "--start-date",
        help="Start date for backtest (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end-date",
        help="End date for backtest (YYYY-MM-DD)",
    )
    args = parser.parse_args()

    # Load config
    config = LiveThinkingFundConfig()
    config.config_name = args.config_name

    # Override config with command line arguments
    config.override_with_args(args)

    # Print config
    logger.info("📊 Server configuration:")
    logger.info(f"   Config name: {config.config_name}")
    logger.info(
        f"   Run mode: {'🎭 MOCK' if args.mock else config.mode.upper()}",
    )
    logger.info(f"   Monitored stocks: {config.tickers}")
    logger.info(f"   Start date: {config.start_date}")
    logger.info(f"   End date: {config.end_date}")
    if config.mode == "portfolio":
        logger.info(f"   Initial cash: ${config.initial_cash:,.2f}")
        logger.info(
            f"   Margin requirement: {config.margin_requirement * 100:.1f}%",
        )

    # Create and start server
    server = Server(config)
    await server.start(host=args.host, port=args.port, mock=args.mock)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Bye!")
