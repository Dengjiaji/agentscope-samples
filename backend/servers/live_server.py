# -*- coding: utf-8 -*-
# backend/servers/live_server.py
"""
Live Mode Server - Live Trading System
Features:
1. Directly run today's real-time trading decision analysis
2. High-frequency real-time price fetching, update equity curves, position P&L, etc.
3. Support Mock mode for testing during non-trading hours
"""
# flake8: noqa: E501
# pylint: disable=C0301,W0613
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from datetime import time as datetime_time
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import pandas_market_calendars as mcal
import websockets
from dotenv import load_dotenv
from websockets.server import WebSocketServerProtocol


from backend.config.env_config import LiveThinkingFundConfig
from backend.config.path_config import get_logs_and_memory_dir
from backend.memory import get_memory
from backend.pipelines.live_trading_fund import LiveTradingFund
from backend.servers.mock_price_manager import MockPriceManager
from backend.servers.polling_price_manager import PollingPriceManager
from backend.servers.state_manager import StateManager
from backend.servers.streamer import BroadcastStreamer
from backend.utils.virtual_clock import get_virtual_clock, init_virtual_clock

BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
_NYSE_CALENDAR = mcal.get_calendar("NYSE")


load_dotenv()

logger = logging.getLogger(__name__)


class LiveTradingServer:
    """Live Trading Server"""

    def __init__(
        self,
        config: LiveThinkingFundConfig,
        mock_mode: bool = False,
        pause_before_trade: bool = False,
        time_accelerator: float = 1.0,
        virtual_start_time: Optional[datetime] = None,
    ):
        self.config = config
        self.mock_mode = mock_mode
        self.pause_before_trade = pause_before_trade
        self.time_accelerator = time_accelerator
        self.virtual_start_time = virtual_start_time
        self.connected_clients: Set[WebSocketServerProtocol] = set()
        self.lock = asyncio.Lock()
        self.loop = None

        # Initialize components
        self._setup_virtual_clock()
        self._setup_dashboard_paths()
        self._setup_state_management()
        self._setup_price_manager()
        self._setup_memory_system()
        self._initialize_trading_system()
        self._initialize_live_mode_state()

    def _setup_virtual_clock(self):
        """Initialize virtual clock for time acceleration."""
        if self.mock_mode and self.time_accelerator != 1.0:
            init_virtual_clock(
                start_time=self.virtual_start_time,
                time_accelerator=self.time_accelerator,
                enabled=True,
            )
            logger.info(
                f"🕐 Virtual clock enabled: acceleration {self.time_accelerator}x, "
                f"start time: {self.virtual_start_time or 'current time'}",
            )
        else:
            init_virtual_clock(enabled=False)

        self.vclock = get_virtual_clock()

    def _setup_dashboard_paths(self):
        """Set up dashboard file paths and load internal state."""
        self.dashboard_dir = (
            get_logs_and_memory_dir()
            / self.config.config_name
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
        self.dashboard_file_mtimes = {}
        logger.info(f"✅ Dashboard file directory: {self.dashboard_dir}")

        self.internal_state_file = self.dashboard_dir / "_internal_state.json"
        self.internal_state = self._load_internal_state()
        self.latest_prices: Dict[str, float] = {}

    def _setup_state_management(self):
        """Initialize state manager and portfolio state."""
        self.state_manager = StateManager(
            config_name=self.config.config_name,
            base_dir=BASE_DIR,
            max_history=200,
        )

        # Load equity history from internal_state if available
        equity_history = self.internal_state.get("equity_history", [])
        baseline_history = self.internal_state.get("baseline_history", [])
        baseline_vw_history = self.internal_state.get(
            "baseline_vw_history",
            [],
        )
        momentum_history = self.internal_state.get("momentum_history", [])

        self.state_manager.update(
            "portfolio",
            {
                "total_value": self.config.initial_cash,
                "cash": self.config.initial_cash,
                "pnl_percent": 0,
                "equity": equity_history,
                "baseline": baseline_history,
                "baseline_vw": baseline_vw_history,
                "momentum": momentum_history,
                "strategies": [],
            },
        )

        logger.info(
            f"📊 Loaded history: equity={len(equity_history)} points, "
            f"baseline={len(baseline_history)} points",
        )

        # Record initial cash (for calculating returns)
        self.initial_cash = self.config.initial_cash

    def _setup_price_manager(self):
        """Initialize price manager based on mode."""
        if self.mock_mode:
            logger.info("🎭 Using Mock price manager (test mode)")
            self.price_manager = MockPriceManager(
                poll_interval=5,
                volatility=0.5,
            )
        else:
            api_key = os.getenv("FINNHUB_API_KEY", "")
            if not api_key:
                logger.error(
                    "❌ FINNHUB_API_KEY not found, cannot use real-time price feature",
                )
                logger.info("   Please set FINNHUB_API_KEY in .env file")
                logger.info("   Get free API Key: https://finnhub.io/register")
                raise ValueError("Missing FINNHUB_API_KEY")

            logger.info(
                "📊 Using Finnhub real-time prices (polling interval: 30 seconds)",
            )
            self.price_manager = PollingPriceManager(api_key, poll_interval=30)

        # Add price update callback
        self.price_manager.add_price_callback(self._on_price_update)

    def _setup_memory_system(self):
        """Initialize memory system."""
        _memory_instance = get_memory(self.config.config_name)
        logger.info("✅ Memory system initialized")
        logger.info("✅ Memory system ready")

    def _initialize_trading_system(self):
        """Initialize trading system and dashboard."""
        self.thinking_fund = None
        self._ensure_dashboard_initialized()

    def _initialize_live_mode_state(self):
        """Initialize live mode state variables."""
        self.current_phase = (
            "backtest"  # backtest, live_analysis, live_monitoring
        )
        self.is_today = False
        self.market_is_open = False
        self.last_trading_date = None
        self.last_executed_date = None
        self.trading_executed_today = False
        self.analysis_executed_today = False
        self.last_pre_market_analysis_date = None
        self.daily_signals = (
            {}
        )  # {date: {'ana_signals': ..., 'pm_signals': ...}}

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
        """Price update callback - directly update holdings.json and stats.json files"""
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
        self.latest_prices[symbol] = price
        self._cache_internal_price(symbol, price)

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

        # Update holdings.json and stats.json files
        try:
            self._update_dashboard_files_with_price(symbol, price)
        except Exception as e:
            logger.error(f"Failed to update Dashboard files ({symbol}): {e}")

    def _get_current_time_for_data(self) -> datetime:
        """
        Get current time for data recording
        Use virtual time in Mock mode, otherwise use real time
        """
        if self.mock_mode and self.vclock.enabled:
            return self.vclock.now()
        else:
            return datetime.now()

    def _get_current_timestamp_ms_for_data(self) -> int:
        """
        Get timestamp for data recording (milliseconds)
        Use virtual time in Mock mode, otherwise use real time
        """
        current_time = self._get_current_time_for_data()
        return int(current_time.timestamp() * 1000)

    def _update_dashboard_files_with_price(self, symbol: str, price: float):
        """Update prices and related calculations in holdings.json, stats.json and summary.json files"""
        # Load files
        holdings, stats, summary = self._load_dashboard_files()
        if holdings is None or stats is None:
            return

        # Update holdings and calculate totals
        updated, total_value, cash = self._update_holdings_with_price(
            holdings,
            symbol,
            price,
        )

        # Update stats
        self._update_stats_file(stats, holdings, total_value, cash)

        # Update summary if exists
        if summary:
            self._update_summary_file(
                summary,
                updated,
                total_value,
                cash,
                holdings,
            )

    def _load_dashboard_files(self):
        """Load holdings, stats, and summary JSON files"""
        holdings_file = self.dashboard_files.get("holdings")
        stats_file = self.dashboard_files.get("stats")
        summary_file = self.dashboard_files.get("summary")

        if not holdings_file or not holdings_file.exists():
            logger.warning(
                "holdings.json file does not exist, skipping update",
            )
            return None, None, None

        if not stats_file or not stats_file.exists():
            logger.warning("stats.json file does not exist, skipping update")
            return None, None, None

        try:
            with open(holdings_file, "r", encoding="utf-8") as f:
                holdings = json.load(f)
            with open(stats_file, "r", encoding="utf-8") as f:
                stats = json.load(f)
        except Exception as e:
            logger.error(f"Failed to read dashboard files: {e}")
            return None, None, None

        summary = None
        if summary_file and summary_file.exists():
            try:
                with open(summary_file, "r", encoding="utf-8") as f:
                    summary = json.load(f)
            except Exception as e:
                logger.error(f"Failed to read summary.json: {e}")

        return holdings, stats, summary

    def _update_holdings_with_price(
        self,
        holdings: list,
        symbol: str,
        price: float,
    ):
        """Update holdings with new price and recalculate weights"""
        updated = False
        total_value = 0.0
        cash = 0.0

        # Update prices and calculate total value
        for holding in holdings:
            ticker = holding.get("ticker")
            quantity = holding.get("quantity", 0)

            if ticker == "CASH":
                cash = holding.get("marketValue", 0)
                total_value += cash
            elif ticker == symbol:
                holding["currentPrice"] = round(price, 2)
                market_value = quantity * price
                holding["marketValue"] = round(market_value, 2)
                total_value += market_value
                updated = True
            else:
                total_value += holding.get("marketValue", 0)

        # Recalculate weights
        if total_value > 0:
            for holding in holdings:
                market_value = holding.get("marketValue", 0)
                weight = market_value / total_value
                holding["weight"] = round(weight, 4)

        # Save if updated
        if updated:
            holdings_file = self.dashboard_files.get("holdings")
            try:
                with open(holdings_file, "w", encoding="utf-8") as f:
                    json.dump(holdings, f, indent=2, ensure_ascii=False)
                logger.debug(
                    f"✅ Updated holdings.json: {symbol} = ${price:.2f}",
                )
            except Exception as e:
                logger.error(f"Failed to save holdings.json: {e}")

        return updated, total_value, cash

    def _update_stats_file(
        self,
        stats: dict,
        holdings: list,
        total_value: float,
        cash: float,
    ):
        """Update and save stats.json"""
        total_return = (
            ((total_value - self.initial_cash) / self.initial_cash * 100)
            if self.initial_cash > 0
            else 0.0
        )

        # Update ticker weights
        ticker_weights = {
            holding.get("ticker"): holding.get("weight", 0)
            for holding in holdings
            if holding.get("ticker") != "CASH"
        }

        stats["totalAssetValue"] = round(total_value, 2)
        stats["totalReturn"] = round(total_return, 2)
        stats["cashPosition"] = round(cash, 2)
        stats["tickerWeights"] = ticker_weights

        # Save stats.json
        stats_file = self.dashboard_files.get("stats")
        try:
            with open(stats_file, "w", encoding="utf-8") as f:
                json.dump(stats, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save stats.json: {e}")

    def _update_summary_file(
        self,
        summary: dict,
        updated: bool,
        total_value: float,
        cash: float,
        holdings: list,
    ):
        """Update and save summary.json"""
        try:
            current_time = self._get_current_timestamp_ms_for_data()
            summary_changed = False

            # Update summary stats if price was updated
            if updated:
                total_return = (
                    (
                        (total_value - self.initial_cash)
                        / self.initial_cash
                        * 100
                    )
                    if self.initial_cash > 0
                    else 0.0
                )
                ticker_weights = {
                    holding.get("ticker"): holding.get("weight", 0)
                    for holding in holdings
                    if holding.get("ticker") != "CASH"
                }

                summary["balance"] = round(total_value, 2)
                summary["totalAssetValue"] = round(total_value, 2)
                summary["pnlPct"] = round(total_return, 2)
                summary["totalReturn"] = round(total_return, 2)
                summary["cashPosition"] = round(cash, 2)
                summary["tickerWeights"] = ticker_weights

            # Update equity and benchmark curves
            if self._should_add_equity_point(summary, current_time):
                self._add_equity_point(summary, total_value, current_time)
                self._update_benchmark_curves(summary, current_time)
                summary_changed = True
            elif updated:
                summary_changed = True

            # Save if changed
            if summary_changed:
                summary_file = self.dashboard_files.get("summary")
                if summary_file:
                    with open(summary_file, "w", encoding="utf-8") as f:
                        json.dump(summary, f, indent=2, ensure_ascii=False)
                    self._save_internal_state()

        except Exception as e:
            logger.error(f"Failed to update summary.json: {e}")

    def _should_add_equity_point(
        self,
        summary: dict,
        current_time: int,
    ) -> bool:
        """Check if we should add a new equity data point"""
        equity_list = summary.get("equity", [])

        if len(equity_list) == 0:
            return True

        last_timestamp = equity_list[-1].get("t", 0)
        time_diff_ms = current_time - last_timestamp
        return time_diff_ms >= 5000  # 5 seconds minimum interval

    def _add_equity_point(
        self,
        summary: dict,
        total_value: float,
        current_time: int,
    ):
        """Add a new equity point to summary"""
        equity_list = summary.get("equity", [])
        equity_list.append(
            {
                "t": current_time,
                "v": round(total_value, 2),
            },
        )
        summary["equity"] = equity_list
        self.internal_state["equity_history"] = equity_list

    def _load_internal_state(self) -> Dict[str, Any]:
        """
        Read and normalize team dashboard internal state, ensure key fields exist
        """
        default_state = {
            "baseline_state": {"initialized": False, "initial_allocation": {}},
            "baseline_vw_state": {
                "initialized": False,
                "initial_allocation": {},
            },
            "momentum_state": {
                "positions": {},
                "cash": 0.0,
                "initialized": False,
            },
            "equity_history": [],  # Portfolio equity history
            "baseline_history": [],
            "baseline_vw_history": [],
            "momentum_history": [],
            "price_history": {},
        }

        if not self.dashboard_dir.exists():
            self.dashboard_dir.mkdir(parents=True, exist_ok=True)

        if not self.internal_state_file.exists():
            return default_state

        try:
            with open(self.internal_state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.warning(
                f"⚠️ Unable to read internal state file, using default values: {e}",
            )
            return default_state

        for key, value in default_state.items():
            data.setdefault(key, value)
        return data

    def _save_internal_state(self):
        """
        Write updated internal state back to disk
        """
        if not self.internal_state:
            return
        try:
            with open(self.internal_state_file, "w", encoding="utf-8") as f:
                json.dump(self.internal_state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save internal state: {e}")

    def _cache_internal_price(self, symbol: str, price: float):
        """
        Write latest price to internal state's price_history for benchmark valuation
        """
        if not self.internal_state:
            return
        price_history = self.internal_state.setdefault("price_history", {})
        ticker_history = price_history.setdefault(symbol, {})
        # Use virtual time (in mock mode) or real time
        current_time = self._get_current_time_for_data()
        today = current_time.strftime("%Y-%m-%d")
        ticker_history[today] = price

    def _get_price_for_benchmark(
        self,
        ticker: str,
        fallback: Optional[float] = None,
    ) -> Optional[float]:
        """
        Get latest price for benchmark valuation
        """
        if ticker in self.latest_prices:
            return self.latest_prices[ticker]

        price_history = self.internal_state.get("price_history", {})
        ticker_history = price_history.get(ticker, {})
        if ticker_history:
            # Get data from latest date
            latest_date = sorted(ticker_history.keys())[-1]
            return ticker_history[latest_date]

        return fallback

    def _append_curve_point(
        self,
        history: List[Dict[str, Any]],
        timestamp_ms: int,
        value: float,
        max_points: int = None,
    ) -> List[Dict[str, Any]]:
        """
        Append curve point (no length limit by default)
        """
        history.append({"t": timestamp_ms, "v": round(value, 2)})
        if max_points is not None and len(history) > max_points:
            del history[: len(history) - max_points]
        return history

    def _calculate_cumulative_returns_for_live(
        self,
        values: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Calculate cumulative returns for live mode (current trading session only).

        For live mode, we:
        1) Identify the most recent trading session (22:30 - 05:00, next day, Asia/Shanghai).
        2) Use the last portfolio value *before* this session as the base.
        3) Return cumulative percentage returns for all points *within* this session.
        4) Always prepend a synthetic 0% point at (session_start - 1ms) so that
           all strategies can align at the same initial timestamp.

        Args:
            values: List of {t: timestamp_ms, v: value} data points

        Returns:
            List of {t: timestamp_ms, v: cumulative_return_percentage} data points
            restricted to the current trading session, with the first point being 0%.
        """
        if not values:
            return []

        # Use virtual or real time, consistent with the rest of the server
        current_time = self._get_current_time_for_data()

        current_hour = current_time.hour
        current_minute = current_time.minute

        # Trading session: 22:30 - 05:00 (next day), Asia/Shanghai equivalent
        is_in_trading_session = (
            (current_hour == 22 and current_minute >= 30)  # After 22:30
            or current_hour == 23  # All of hour 23
            or 0 <= current_hour <= 5  # Midnight to 05:00 inclusive
        )

        session_start_time = current_time.replace(
            hour=22,
            minute=30,
            second=0,
            microsecond=0,
        )
        if not is_in_trading_session or current_time < session_start_time:
            # If we are outside the trading session, use the previous day's session
            session_start_time = session_start_time - timedelta(days=1)

        session_start_timestamp = int(session_start_time.timestamp() * 1000)

        # Find base value: last value strictly before session start.
        base_value = None
        for point in reversed(values):
            if point.get("t") is None or point.get("v") is None:
                continue
            if point["t"] < session_start_timestamp:
                base_value = point["v"]
                break

        # Fallback: use the first available value as base if nothing before session
        if base_value is None:
            first_valid = next(
                (
                    p
                    for p in values
                    if p.get("t") is not None and p.get("v") is not None
                ),
                None,
            )
            if not first_valid:
                return []
            base_value = first_valid["v"]

        # Guard against division by zero
        if not base_value:
            return []

        # Collect data points that fall within the current session
        session_points: List[Dict[str, Any]] = [
            p
            for p in values
            if p
            and isinstance(p.get("t"), (int, float))
            and p["t"] >= session_start_timestamp
            and p.get("v") is not None
        ]

        if not session_points:
            # No data in the current session -> nothing to plot
            return []

        returns: List[Dict[str, Any]] = []

        # Synthetic 0% return point just before session start.
        # This ensures all strategies share the same initial timestamp.
        returns.append(
            {
                "t": session_start_timestamp - 1,
                "v": 0.0,
            },
        )

        # Then cumulative returns for all in-session points
        for point in session_points:
            cumulative_return = (point["v"] - base_value) / base_value * 100
            returns.append(
                {
                    "t": point["t"],
                    "v": round(cumulative_return, 4),
                },
            )

        return returns

    def _update_benchmark_curves(
        self,
        summary: Dict[str, Any],
        timestamp_ms: int,
    ) -> bool:
        """
        Update benchmark/strategy curves based on latest prices
        CRITICAL: This method is called synchronously with equity updates to maintain index alignment
        """
        if not self.internal_state:
            return False

        changed = False

        # Update baseline (equal weight)
        if self._update_single_benchmark(
            "baseline_state",
            "baseline_history",
            "baseline",
            summary,
            timestamp_ms,
        ):
            changed = True

        # Update baseline_vw (value weighted)
        if self._update_single_benchmark(
            "baseline_vw_state",
            "baseline_vw_history",
            "baseline_vw",
            summary,
            timestamp_ms,
        ):
            changed = True

        # Update momentum strategy
        if self._update_momentum_benchmark(summary, timestamp_ms):
            changed = True

        return changed

    def _update_single_benchmark(
        self,
        state_key: str,
        history_key: str,
        summary_key: str,
        summary: Dict[str, Any],
        timestamp_ms: int,
    ) -> bool:
        """Update a single benchmark curve."""
        state = self.internal_state.get(state_key, {})
        if not (state.get("initialized") and state.get("initial_allocation")):
            return False

        total_value = 0.0
        for ticker, alloc in state["initial_allocation"].items():
            price = self._get_price_for_benchmark(
                ticker,
                alloc.get("buy_price"),
            )
            if price is None:
                return False
            total_value += alloc.get("qty", 0) * price

        history = self._append_curve_point(
            self.internal_state.setdefault(history_key, []),
            timestamp_ms,
            total_value,
        )
        summary[summary_key] = history
        return True

    def _update_momentum_benchmark(
        self,
        summary: Dict[str, Any],
        timestamp_ms: int,
    ) -> bool:
        """Update momentum strategy curve."""
        momentum_state = self.internal_state.get("momentum_state", {})
        if not momentum_state.get("initialized"):
            return False

        total_value = momentum_state.get("cash", 0.0)
        for ticker, pos in momentum_state.get("positions", {}).items():
            price = self._get_price_for_benchmark(ticker, pos.get("buy_price"))
            if price is None:
                return False
            total_value += pos.get("qty", 0) * price

        history = self._append_curve_point(
            self.internal_state.setdefault("momentum_history", []),
            timestamp_ms,
            total_value,
        )
        summary["momentum"] = history
        return True

    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast message to all connected clients"""
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

    async def _send_to_client(
        self,
        client: WebSocketServerProtocol,
        message: str,
    ):
        """Send message to single client"""
        try:
            await client.send(message)
        except websockets.ConnectionClosed:
            async with self.lock:
                self.connected_clients.discard(client)
        except Exception as e:
            logger.error(f"Failed to send message: {e}")

    def _load_dashboard_file(self, file_type: str) -> Any:
        """Load Dashboard JSON file"""
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
        """Check which Dashboard files have been updated"""
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

    async def _broadcast_all_dashboard_files(self):
        """Broadcast all Dashboard files (regardless of update)"""
        # 使用virtual time（mock模式下）或真实时间
        current_time = self._get_current_time_for_data()
        timestamp = current_time.isoformat()

        for file_type, _ in self.dashboard_files.items():
            data = self._load_dashboard_file(file_type)
            if data is None:
                continue

            await self._broadcast_dashboard_data(file_type, data, timestamp)

    async def _broadcast_dashboard_data(
        self,
        file_type: str,
        data: Any,
        timestamp: str,
    ):
        """Broadcast single Dashboard data type"""
        if file_type == "summary":
            equity_data = data.get("equity", [])
            baseline_data = data.get("baseline", [])
            baseline_vw_data = data.get("baseline_vw", [])
            momentum_data = data.get("momentum", [])

            equity_return = self._calculate_cumulative_returns_for_live(
                equity_data,
            )
            baseline_return = self._calculate_cumulative_returns_for_live(
                baseline_data,
            )
            baseline_vw_return = self._calculate_cumulative_returns_for_live(
                baseline_vw_data,
            )
            momentum_return = self._calculate_cumulative_returns_for_live(
                momentum_data,
            )

            await self.broadcast(
                {
                    "type": "team_summary",
                    "balance": data.get("balance"),
                    "pnlPct": data.get("pnlPct"),
                    "equity": equity_data,
                    "baseline": baseline_data,
                    "baseline_vw": baseline_vw_data,
                    "momentum": momentum_data,
                    "equity_return": equity_return,
                    "baseline_return": baseline_return,
                    "baseline_vw_return": baseline_vw_return,
                    "momentum_return": momentum_return,
                    "timestamp": timestamp,
                },
            )
            logger.info("✅ Broadcast team_summary (from file)")

        elif file_type == "holdings":
            # Ensure holdings is an array
            if isinstance(data, list):
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
            if isinstance(data, dict):
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
            # Ensure trades is an array
            if isinstance(data, list):
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
            # Ensure leaderboard is an array
            if isinstance(data, list):
                self.state_manager.update("leaderboard", data)
                await self.broadcast(
                    {
                        "type": "team_leaderboard",
                        "data": data,
                        "timestamp": timestamp,
                    },
                )
                logger.info(
                    f"✅ Broadcast team_leaderboard: {len(data)} agents (from file)",
                )

    async def _broadcast_dashboard_from_files(self):
        """Read Dashboard data from files and broadcast (only broadcast updated files)"""
        updated_files = self._check_dashboard_files_updated()
        # Use virtual time (in mock mode) or real time
        current_time = self._get_current_time_for_data()
        timestamp = current_time.isoformat()

        for file_type, is_updated in updated_files.items():
            if not is_updated:
                continue

            data = self._load_dashboard_file(file_type)
            if data is None:
                continue

            await self._broadcast_dashboard_data(file_type, data, timestamp)

    def _is_trading_day(self, date_str: str = None) -> bool:
        """
        Check if specified date is a trading day

        Args:
            date_str: Date string (YYYY-MM-DD), defaults to today

        Returns:
            Whether it is a trading day
        """
        if not _NYSE_CALENDAR:
            # If no calendar, simple check (Monday to Friday)
            target_date = (
                datetime.strptime(date_str, "%Y-%m-%d")
                if date_str
                else datetime.now()
            )
            return target_date.weekday() < 5  # 0-4 is Monday to Friday

        try:
            target_date = (
                date_str if date_str else datetime.now().strftime("%Y-%m-%d")
            )
            schedule = _NYSE_CALENDAR.schedule(
                start_date=target_date,
                end_date=target_date,
            )
            return not schedule.empty
        except Exception as e:
            logger.warning(f"Failed to check trading day: {e}")
            # Default to trading day
            return True

    def _is_trading_hours(self) -> bool:
        """
        Check if current time is trading hours (US Eastern Time 9:30-16:00)

        Returns:
            Whether in trading hours
        """
        if not _NYSE_CALENDAR:
            # If no calendar, simple check
            now = datetime.now()
            # Note: Here assumes local time is close to US Eastern Time, should actually convert timezone
            # Simplified: Monday to Friday 9:30-16:00
            if now.weekday() >= 5:  # Weekend
                return False
            return datetime_time(9, 30) <= now.time() <= datetime_time(16, 0)

        try:
            today = datetime.now().strftime("%Y-%m-%d")
            schedule = _NYSE_CALENDAR.schedule(
                start_date=today,
                end_date=today,
            )

            if schedule.empty:
                return False  # Non-trading day

            market_open = schedule.iloc[0]["market_open"].to_pydatetime()
            market_close = schedule.iloc[0]["market_close"].to_pydatetime()
            now = datetime.now(tz=market_open.tzinfo)

            return market_open <= now <= market_close
        except Exception as e:
            logger.warning(f"Failed to check trading hours: {e}")
            return False

    def _get_market_close_time(self) -> Optional[datetime]:
        """
        Get today's market close time

        Returns:
            Close time (datetime object), returns None if not a trading day
        """
        if not _NYSE_CALENDAR:
            # Simplified: assume close time is 16:00
            now = datetime.now()
            if now.weekday() >= 5:
                return None
            return datetime.combine(now.date(), datetime_time(16, 0))

        try:
            today = datetime.now().strftime("%Y-%m-%d")
            schedule = _NYSE_CALENDAR.schedule(
                start_date=today,
                end_date=today,
            )

            if schedule.empty:
                return None

            market_close = schedule.iloc[0]["market_close"].to_pydatetime()
            return market_close
        except Exception as e:
            logger.warning(f"Failed to get market close time: {e}")
            return None

    def _get_current_time_beijing(self) -> datetime:
        """Get current Beijing time (for US stock trading time judgment)"""
        from datetime import timezone

        # Use virtual clock (if enabled)
        utc_now = self.vclock.now(timezone.utc)
        beijing_tz = timezone(timedelta(hours=8))
        return utc_now.astimezone(beijing_tz)

    def _is_market_open_time_beijing(self) -> bool:
        """
        Check if current Beijing time is within US stock trading hours
        US stock trading time: Beijing time 22:30 - next day 05:00 (DST) or 23:30 - next day 06:00 (standard time)
        Simplified: use 22:30 - next day 05:00
        """
        now_beijing = self._get_current_time_beijing()
        current_time = now_beijing.time()

        # After 22:30 (market opens tonight)
        if current_time >= datetime_time(22, 30):
            return True
        # Before 05:00 (market opened last night, still trading early morning)
        if current_time < datetime_time(5, 0):
            return True

        return False

    def _get_next_market_open_time_beijing(self) -> datetime:
        """
        Get next market open time (Beijing time)
        Returns: Next open datetime object (22:30)
        """
        now_beijing = self._get_current_time_beijing()
        current_time = now_beijing.time()

        # If current time is between 05:00 and 22:30, market opens tonight
        if datetime_time(5, 0) <= current_time < datetime_time(22, 30):
            open_time = now_beijing.replace(
                hour=22,
                minute=30,
                second=0,
                microsecond=0,
            )
            return open_time

        # If current time is after 22:30, market opens tomorrow night
        if current_time >= datetime_time(22, 30):
            next_day = now_beijing + timedelta(days=1)
            open_time = next_day.replace(
                hour=22,
                minute=30,
                second=0,
                microsecond=0,
            )
            return open_time

        # If current time is before 05:00, market opens tonight
        open_time = now_beijing.replace(
            hour=22,
            minute=30,
            second=0,
            microsecond=0,
        )
        return open_time

    def _get_market_status(self) -> Dict[str, Any]:
        """
        Get current market status information

        Returns:
            Dictionary containing market status
        """
        now_beijing = self._get_current_time_beijing()

        # Check if it's a trading day (using US date)
        us_date = (now_beijing - timedelta(hours=12)).strftime("%Y-%m-%d")
        is_trading_day = self._is_trading_day(us_date)

        if not is_trading_day:
            return {
                "status": "closed",
                "status_text": "US Market Closed",
                "is_trading_day": False,
                "is_market_open": False,
                "current_time": now_beijing.isoformat(),
                "current_time_str": now_beijing.strftime("%Y-%m-%d %H:%M:%S"),
            }

        # Trading day: check if in trading hours
        is_market_open = self._is_market_open_time_beijing()

        if is_market_open:
            return {
                "status": "open",
                "status_text": "US Market Open",
                "is_trading_day": True,
                "is_market_open": True,
                "current_time": now_beijing.isoformat(),
                "current_time_str": now_beijing.strftime("%Y-%m-%d %H:%M:%S"),
                "trading_date": us_date,
            }
        else:
            return {
                "status": "closed",
                "status_text": "US Market Closed",
                "is_trading_day": True,
                "is_market_open": False,
                "current_time": now_beijing.isoformat(),
                "current_time_str": now_beijing.strftime("%Y-%m-%d %H:%M:%S"),
                "trading_date": us_date,
            }

    def _get_next_trade_execution_time_beijing(self) -> datetime:
        """
        Get next trade execution time (Beijing time)
        Returns: 5 minutes after close, i.e., next day 05:05
        """
        now_beijing = self._get_current_time_beijing()
        current_time = now_beijing.time()

        # If current time is before 05:05, execute at 05:05 early morning today
        if current_time < datetime_time(5, 5):
            execution_time = now_beijing.replace(
                hour=5,
                minute=5,
                second=0,
                microsecond=0,
            )
            return execution_time

        # Otherwise, execute at 05:05 early morning tomorrow
        next_day = now_beijing + timedelta(days=1)
        execution_time = next_day.replace(
            hour=5,
            minute=5,
            second=0,
            microsecond=0,
        )
        return execution_time

    def _should_execute_trading_now(self) -> bool:
        """
        Determine if trading should be executed now
        Conditions:
        1. After close (Beijing time 05:05 - 20:00)
        2. Current US trading date equals pre-market analysis date + 1 day
        """
        now_beijing = self._get_current_time_beijing()
        current_time = now_beijing.time()

        # Condition 1: Execute trading between 05:05 - 20:00 (5-hour window, adapts to time acceleration)
        if not datetime_time(5, 5) <= current_time < datetime_time(20, 00):
            return False

        # Condition 2: Check if current US trading date equals pre-market analysis date + 1 day
        if not self.last_pre_market_analysis_date:
            # No pre-market analysis has been run yet, cannot execute trades
            logger.debug(
                "⚠️ No pre-market analysis date recorded, skipping trade execution",
            )
            return False

        # Get current Beijing trading date
        current_bj_date = now_beijing.strftime("%Y-%m-%d")

        # Calculate expected execution date (pre-market analysis date + 1 day)
        analysis_date_obj = datetime.strptime(
            self.last_pre_market_analysis_date,
            "%Y-%m-%d",
        )
        expected_execution_date = (
            analysis_date_obj + timedelta(days=1)
        ).strftime("%Y-%m-%d")

        # Check if current date matches expected execution date
        if current_bj_date != expected_execution_date:
            logger.debug(
                f"⚠️ Trade execution date mismatch: current={current_bj_date}, expected={expected_execution_date} (analysis_date={self.last_pre_market_analysis_date}+1)",
            )
            return False

        logger.debug(
            f"✅ Trade execution conditions met: time window OK, date match (analysis={self.last_pre_market_analysis_date}, execution={current_bj_date})",
        )
        return True

    async def handle_client(self, websocket: WebSocketServerProtocol):
        """Handle client connection"""
        try:
            async with self.lock:
                self.connected_clients.add(websocket)

            logger.info(
                f"✅ New client connected (total connections: {len(self.connected_clients)})",
            )

            # Send initial state
            await self._send_initial_state(websocket)

            # Keep connection and handle messages
            await self._handle_client_messages(websocket)

        except Exception as e:
            logger.error(f"Connection handling error: {e}")
        finally:
            async with self.lock:
                self.connected_clients.discard(websocket)
            logger.info(
                f"Client disconnected (remaining connections: {len(self.connected_clients)})",
            )

    async def _send_initial_state(self, websocket: WebSocketServerProtocol):
        """Send initial state to client"""
        initial_state = self.state_manager.get_full_state()

        # Load Dashboard data from files
        try:
            self._load_dashboard_data(initial_state)
            logger.info("✅ Successfully loaded Dashboard data from files")

            # Broadcast all Dashboard data immediately after connection
            await asyncio.sleep(0.1)
            await self._broadcast_all_dashboard_files()
        except Exception as e:
            logger.error(f"⚠️ Failed to load Dashboard data from files: {e}")

        # Add server metadata
        initial_state["server_mode"] = "live"
        initial_state["is_mock_mode"] = self.mock_mode
        initial_state["market_status"] = self._get_market_status()

        # Send full state
        await websocket.send(
            json.dumps(
                {
                    "type": "initial_state",
                    "state": initial_state,
                },
                ensure_ascii=False,
                default=str,
            ),
        )

    def _load_dashboard_data(self, initial_state: dict):
        """Load dashboard data from files into initial state"""
        summary_data = self._load_dashboard_file("summary")
        holdings_data = self._load_dashboard_file("holdings")
        stats_data = self._load_dashboard_file("stats")
        trades_data = self._load_dashboard_file("trades")
        leaderboard_data = self._load_dashboard_file("leaderboard")

        initial_state["dashboard"] = {
            "summary": summary_data,
            "holdings": holdings_data,
            "stats": stats_data,
            "trades": trades_data,
            "leaderboard": leaderboard_data,
        }

        # Update portfolio data
        if summary_data and "portfolio" in initial_state:
            self._update_portfolio_data(initial_state, summary_data)

        # Set holdings, stats, trades, leaderboard
        initial_state["holdings"] = (
            holdings_data if isinstance(holdings_data, list) else []
        )
        initial_state["stats"] = (
            stats_data if isinstance(stats_data, dict) else {}
        )
        initial_state["trades"] = (
            trades_data if isinstance(trades_data, list) else []
        )
        initial_state["leaderboard"] = (
            leaderboard_data if isinstance(leaderboard_data, list) else []
        )

    def _update_portfolio_data(self, initial_state: dict, summary_data: dict):
        """Update portfolio data with returns calculation"""
        equity_data = summary_data.get("equity", [])
        baseline_data = summary_data.get("baseline", [])
        baseline_vw_data = summary_data.get("baseline_vw", [])
        momentum_data = summary_data.get("momentum", [])

        initial_state["portfolio"].update(
            {
                "total_value": summary_data.get("balance"),
                "pnl_percent": summary_data.get("pnlPct"),
                "equity": equity_data,
                "baseline": baseline_data,
                "baseline_vw": baseline_vw_data,
                "momentum": momentum_data,
                "equity_return": self._calculate_cumulative_returns_for_live(
                    equity_data,
                ),
                "baseline_return": self._calculate_cumulative_returns_for_live(
                    baseline_data,
                ),
                "baseline_vw_return": self._calculate_cumulative_returns_for_live(
                    baseline_vw_data,
                ),
                "momentum_return": self._calculate_cumulative_returns_for_live(
                    momentum_data,
                ),
            },
        )

    async def _handle_client_messages(
        self,
        websocket: WebSocketServerProtocol,
    ):
        """Handle incoming client messages"""
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    msg_type = data.get("type", "unknown")

                    if msg_type == "ping":
                        await self._handle_ping(websocket)
                    elif msg_type == "get_state":
                        await self._handle_get_state(websocket)
                    elif msg_type == "fast_forward_time":
                        await self._handle_fast_forward_time(websocket, data)

                except json.JSONDecodeError:
                    logger.warning("Received non-JSON message")
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
        except websockets.ConnectionClosed:
            pass

    async def _handle_ping(self, websocket: WebSocketServerProtocol):
        """Handle ping message"""
        await websocket.send(
            json.dumps(
                {
                    "type": "pong",
                    "timestamp": datetime.now().isoformat(),
                },
                ensure_ascii=False,
                default=str,
            ),
        )

    async def _handle_get_state(self, websocket: WebSocketServerProtocol):
        """Handle get_state message"""
        await websocket.send(
            json.dumps(
                {
                    "type": "state_response",
                    "state": self.state_manager.get_full_state(),
                },
                ensure_ascii=False,
                default=str,
            ),
        )

    async def _handle_fast_forward_time(
        self,
        websocket: WebSocketServerProtocol,
        data: dict,
    ):
        """Handle fast_forward_time message"""
        if not self.mock_mode:
            await self._send_error(
                websocket,
                "Time fast forward feature is only available in Mock mode",
            )
            return

        if not self.vclock.enabled:
            await self._send_error(websocket, "Virtual clock not enabled")
            return

        minutes = data.get("minutes", 30)
        try:
            old_time = self.vclock.now()
            self.vclock.fast_forward(minutes)
            new_time = self.vclock.now()

            logger.info(
                f"⏩ Time fast forwarded: {minutes} minutes ({old_time.strftime('%H:%M:%S')} → {new_time.strftime('%H:%M:%S')})",
            )

            # Broadcast time fast forward event
            await self.broadcast(
                {
                    "type": "time_fast_forwarded",
                    "minutes": minutes,
                    "old_time": old_time.isoformat(),
                    "new_time": new_time.isoformat(),
                    "old_time_str": old_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "new_time_str": new_time.strftime("%Y-%m-%d %H:%M:%S"),
                },
            )

            await websocket.send(
                json.dumps(
                    {
                        "type": "fast_forward_success",
                        "minutes": minutes,
                        "old_time": old_time.isoformat(),
                        "new_time": new_time.isoformat(),
                        "message": f"Time fast forwarded {minutes} minutes",
                    },
                    ensure_ascii=False,
                    default=str,
                ),
            )
        except Exception as e:
            logger.error(f"Time fast forward failed: {e}")
            await self._send_error(
                websocket,
                f"Time fast forward failed: {str(e)}",
            )

    async def _send_error(
        self,
        websocket: WebSocketServerProtocol,
        message: str,
    ):
        """Send error message to client"""
        await websocket.send(
            json.dumps(
                {
                    "type": "error",
                    "message": message,
                },
                ensure_ascii=False,
                default=str,
            ),
        )

    async def run_live_trading_simulation(self):
        """Run live trading simulation"""
        logger.info("🚀 Starting live trading mode")

        loop = asyncio.get_event_loop()

        # ========== Start price manager immediately ==========
        logger.info("===== [Real-time Prices] Starting price monitoring =====")

        # Subscribe to real-time prices (if using Mock mode, may need to pass base prices)
        if self.mock_mode:
            # Mock mode: use current portfolio holding prices as base
            base_prices = {}
            holdings = self.state_manager.get("holdings", [])
            for holding in holdings:
                ticker = holding.get("ticker")
                avg_price = holding.get("avg", 100.0)  # Default 100
                base_prices[ticker] = avg_price

            # If no historical holdings, use default base prices
            if not base_prices:
                for ticker in self.config.tickers:
                    base_prices[ticker] = 100.0

            self.price_manager.subscribe(
                self.config.tickers,
                base_prices=base_prices,
            )
            logger.info(
                f"🎭 Mock mode: Subscribed to {len(self.config.tickers)} stocks, using virtual prices",
            )
        else:
            self.price_manager.subscribe(self.config.tickers)
            logger.info(
                f"📊 Real-time mode: Subscribed to {len(self.config.tickers)} stocks, using Finnhub API",
            )

        self.price_manager.start()
        logger.info(
            f"✅ Price manager started, real-time update frequency: {'Every 5 seconds (Mock)' if self.mock_mode else 'Every 10 seconds (Finnhub)'}",
        )

        await self.broadcast(
            {
                "type": "system",
                "content": f"✅ Stock price board started, beginning real-time updates ({len(self.config.tickers)} stocks)",
            },
        )

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
            pause_before_trade=self.pause_before_trade,
        )

        # Determine "today's" US trading date
        # Mock mode with specified virtual start time: use virtual time
        # Otherwise: use real current time
        if self.mock_mode and self.virtual_start_time:
            reference_time = self.virtual_start_time
        else:
            reference_time = datetime.now()

        # Convert to US trading date (Beijing time - 12 hours)
        today_us = (reference_time - timedelta(hours=12)).strftime("%Y-%m-%d")
        logger.info(
            f"📅 Current Beijing time: {reference_time.strftime('%Y-%m-%d %H:%M:%S')}",
        )
        logger.info(f"📅 Corresponding US trading day: {today_us}")

        # ========== Directly enter today's live mode ==========
        logger.info(f"📅 Directly entering today's live mode: {today_us}")

        self.state_manager.update("status", "live_analysis")
        self.state_manager.update("trading_days_total", 1)
        self.state_manager.update("trading_days_completed", 0)

        await self.broadcast(
            {
                "type": "system",
                "content": f"System started - Directly entering today's live mode (US trading day: {today_us})",
            },
        )

        # ========== Today's live mode ==========
        logger.info(f"===== [Live Mode] US trading day {today_us} =====")
        self.current_phase = "live_analysis"
        self.is_today = True

        self.state_manager.update("status", "live_analysis")
        self.state_manager.update("current_date", today_us)

        # Send different messages based on pause mode
        if self.pause_before_trade:
            await self.broadcast(
                {
                    "type": "system",
                    "content": f"⏸️ Entering today's live mode - US trading day {today_us}, running trading decision analysis (Pause mode: no trades executed)...",
                },
            )
        else:
            await self.broadcast(
                {
                    "type": "system",
                    "content": f"Entering today's live mode - US trading day {today_us}, running trading decision analysis...",
                },
            )

        # First day startup: immediately run pre-market analysis (func1)
        await self._run_pre_market_analysis(today_us)

        # ========== Enter continuous monitoring and auto-trading loop ==========
        logger.info(
            "===== [Continuous Monitoring] Entering continuous operation mode =====",
        )
        await self._continuous_trading_loop()

    async def _run_pre_market_analysis(self, date: str):
        """Run pre-market analysis (func1): call strategy.run_single_day to generate signals"""

        logger.info(f"===== [Pre-market Analysis] {date} =====")

        # Start new day
        self.state_manager.start_new_day()

        await self.broadcast(
            {
                "type": "system",
                "content": f"📊 Starting pre-market analysis ({date})...",
            },
        )

        result = await asyncio.to_thread(
            self.thinking_fund.run_pre_market_analysis_only,
            date=date,
            tickers=self.config.tickers,
            max_comm_cycles=self.config.max_comm_cycles,
            force_run=True,
            enable_communications=not self.config.disable_communications,
            enable_notifications=not self.config.disable_notifications,
        )

        if not isinstance(result, dict):
            logger.error(
                f"❌ Analysis returned wrong type: expected dict, got {type(result).__name__}",
            )
            logger.error(f"   Return value: {result}")
            await self.broadcast(
                {
                    "type": "system",
                    "content": "❌ Pre-market analysis failed: wrong return type",
                },
            )
            return

        if result.get("status") != "success":
            logger.warning(
                f"⚠️ Pre-market analysis not successful: {result.get('reason', 'unknown')}",
            )
            await self.broadcast(
                {
                    "type": "system",
                    "content": f"⚠️ Pre-market analysis skipped: {result.get('reason', 'unknown')}",
                },
            )
            return

        pre_market = result.get("pre_market", {})
        live_env = pre_market.get("live_env", {})

        pm_signals = live_env.get("pm_signals", {})
        ana_signals = live_env.get("ana_signals", {})

        # Save signals for next day use
        self.daily_signals[date] = {
            "ana_signals": ana_signals,
            "pm_signals": pm_signals,
            "pre_market_result": result,
        }

        # pdb.set_trace()

        self.state_manager.update("latest_signals", pm_signals)

        await self.broadcast(
            {
                "type": "system",
                "content": f"✅ Pre-market analysis completed ({date}), generated {len(pm_signals)} stock signals",
            },
        )
        logger.info(
            f"✅ Pre-market analysis completed: {date}, generated {len(pm_signals)} signals",
        )

        # Record pre-market analysis date (US trading date)
        self.last_pre_market_analysis_date = date
        logger.info(f"📅 Recorded pre-market analysis date: {date}")

        # Set flag (avoid repeated runs in short time)
        self.analysis_executed_today = True

    async def _run_trade_execution_with_prev_update(self, date: str):
        """Execute trades and update previous day's agent perf (func2)"""

        logger.info(f"===== [Trade Execution] {date} =====")

        await self.broadcast(
            {
                "type": "system",
                "content": f"💼 Starting trade execution ({date})...",
            },
        )

        # Get today's signals
        current_day_data = self.daily_signals.get(date)

        # Get previous trading day
        prev_date = self.last_trading_date
        prev_signals = self.daily_signals.get(prev_date) if prev_date else None

        result = await asyncio.to_thread(
            self.thinking_fund.run_trade_execution_and_update_prev_perf,
            date=date,
            tickers=self.config.tickers,
            pre_market_result=(
                current_day_data.get("pre_market_result")
                if current_day_data
                else None
            ),
            prev_date=prev_date,
            prev_signals=prev_signals,
        )

        if result.get("prev_day_updated"):
            await self.broadcast(
                {
                    "type": "system",
                    "content": f"✅ Updated previous trading day ({prev_date}) agent performance",
                },
            )

        if result.get("status") == "success":
            await self.broadcast(
                {
                    "type": "system",
                    "content": f"✅ Trade execution completed ({date})",
                },
            )
            logger.info(f"✅ Trade execution completed: {date}")

            # Broadcast trade completion event
            await self.broadcast(
                {
                    "type": "trade_execution_complete",
                    "date": date,
                    "timestamp": datetime.now().isoformat(),
                },
            )

        # End current day (save for replay)
        self.state_manager.end_current_day()

        self.state_manager.save()
        logger.info(f"💾 Trade data saved: {date}")

    def _should_run_pre_market_analysis(self) -> bool:
        """Determine if pre-market analysis should run now (after 22:30:00)"""
        now_beijing = self._get_current_time_beijing()
        current_time = now_beijing.time()

        # Run pre-market analysis between 22:30:00 - 23:30:00 (1-hour window, adapts to time acceleration)
        return (
            datetime_time(22, 30, 0) <= current_time < datetime_time(23, 30, 0)
        )

    async def _continuous_trading_loop(self):
        """
        Continuous trading loop - Core logic
        1. Run pre-market analysis every day at 22:30-23:30 (1-hour window) (func1)
        2. Execute trades and update previous day's agent perf every day at 05:05-10:00 (5-hour window) (func2)
        3. Start price monitoring during trading hours (22:30-05:00)
        4. Only maintain page time updates during non-trading hours (10:00-22:30)
        5. Use flags to avoid repeated execution within windows
        """
        logger.info("🔄 Starting continuous trading loop")

        while True:
            now_beijing = self._get_current_time_beijing()
            us_date = (now_beijing - timedelta(hours=12)).strftime("%Y-%m-%d")
            is_trading_day = self._is_trading_day(us_date)

            if not is_trading_day:
                await self._handle_non_trading_day(now_beijing)
                await self.vclock.sleep(60)
                continue

            # Trading day logic
            await self._handle_trading_day(now_beijing, us_date)

            # Reset daily flags if needed
            await self._check_and_reset_daily_flags(now_beijing, us_date)

    async def _handle_trading_day(self, now_beijing, us_date):
        """Handle trading day operations"""
        is_market_open = self._is_market_open_time_beijing()
        should_run_analysis = self._should_run_pre_market_analysis()
        should_execute_trade = self._should_execute_trading_now()

        # Debug logs
        self._log_trading_windows(
            should_run_analysis,
            should_execute_trade,
            us_date,
        )

        if should_run_analysis and not self.analysis_executed_today:
            await self._execute_pre_market_analysis(now_beijing, us_date)
        elif is_market_open:
            await self._handle_market_open_period(now_beijing, us_date)
            await self.vclock.sleep(60)
        elif should_execute_trade and not self.trading_executed_today:
            await self._execute_trading(now_beijing, us_date)
        else:
            await self._handle_off_market_with_dynamic_sleep(now_beijing)

    def _log_trading_windows(
        self,
        should_run_analysis,
        should_execute_trade,
        us_date,
    ):
        """Log trading window detection"""
        if should_run_analysis:
            print(
                f"🔍 Detected pre-market analysis time window | "
                f"analysis_executed_today={self.analysis_executed_today} | us_date={us_date}",
            )
        if should_execute_trade:
            print(
                f"🔍 Detected trade execution time window | "
                f"trading_executed_today={self.trading_executed_today} | us_date={us_date}",
            )

    async def _execute_pre_market_analysis(self, now_beijing, us_date):
        """Execute pre-market analysis"""
        print(
            f"🎯 Triggering pre-market analysis (func1) | "
            f"us_date={us_date} | Beijing time={now_beijing.strftime('%H:%M:%S')}",
        )
        await self._run_pre_market_analysis(us_date)
        await self.vclock.sleep(30)

    async def _execute_trading(self, now_beijing, us_date):
        """Execute trading operations"""
        print(
            f"🎯 Triggering trade execution (func2) | "
            f"us_date={us_date} | Beijing time={now_beijing.strftime('%H:%M:%S')}",
        )
        await self._run_trade_execution_with_prev_update(us_date)
        self.trading_executed_today = True
        self.last_trading_date = us_date
        self.last_executed_date = us_date
        await self.vclock.sleep(300)

    async def _handle_off_market_with_dynamic_sleep(self, now_beijing):
        """Handle off-market period with dynamic sleep"""
        await self._handle_off_market_period(now_beijing)

        next_open = self._get_next_market_open_time_beijing()
        time_to_open = (next_open - now_beijing).total_seconds()

        sleep_duration = 30 if time_to_open < 600 else 300
        await self.vclock.sleep(sleep_duration)

        async def _check_and_reset_daily_flags(self, now_beijing, us_date):
            """Check and reset daily flags when date changes"""
            current_time = now_beijing.time()
            if not (
                datetime_time(20, 0) <= current_time < datetime_time(22, 29)
            ):
                return

            if (
                not self.last_executed_date
                or us_date == self.last_executed_date
            ):
                return

            if self.trading_executed_today or self.analysis_executed_today:
                logger.info(
                    f"📅 Detected trading day change ({self.last_executed_date} → {us_date}), "
                    f"resetting daily flags",
                )
                logger.info(
                    f"   Beijing time={now_beijing.strftime('%H:%M:%S')}",
                )
                logger.info(
                    f"   Before reset: trading_executed={self.trading_executed_today}, "
                    f"analysis_executed={self.analysis_executed_today}",
                )
                self.trading_executed_today = False
                self.analysis_executed_today = False
                logger.info(
                    f"   After reset: trading_executed={self.trading_executed_today}, "
                    f"analysis_executed={self.analysis_executed_today}",
                )

    async def _handle_non_trading_day(self, now_beijing: datetime):
        """Handle non-trading day: only maintain page time updates, no price fetching"""
        current_phase = self.state_manager.get("status")

        if current_phase != "non_trading_day":
            self.current_phase = "non_trading_day"
            self.state_manager.update("status", "non_trading_day")

            # Stop price manager
            if self.price_manager and not self.mock_mode:
                logger.info("🛑 Non-trading day, stopping price fetching")
                self.price_manager.stop()

            await self.broadcast(
                {
                    "type": "system",
                    "content": f'📅 Today is a non-trading day ({now_beijing.strftime("%Y-%m-%d")}), only maintaining page updates',
                },
            )
            logger.info(
                f"📅 Non-trading day: {now_beijing.strftime('%Y-%m-%d')}",
            )

        # Broadcast time update
        next_open = self._get_next_market_open_time_beijing()
        hours_to_open = (next_open - now_beijing).total_seconds() / 3600

        logger.info(
            f"⏰ Current time: {now_beijing.strftime('%Y-%m-%d %H:%M:%S')} | Status: Non-trading day | Hours to open: {hours_to_open:.1f}",
        )

        market_status = self._get_market_status()
        await self.broadcast(
            {
                "type": "time_update",
                "beijing_time": now_beijing.isoformat(),
                "beijing_time_str": now_beijing.strftime("%Y-%m-%d %H:%M:%S"),
                "status": "non_trading_day",
                "next_open": next_open.isoformat(),
                "hours_to_open": round(hours_to_open, 1),
                "market_status": market_status,
                "is_mock_mode": self.mock_mode,
            },
        )

        # Broadcast market status update separately
        await self.broadcast(
            {
                "type": "market_status_update",
                "market_status": market_status,
            },
        )

    async def _handle_market_open_period(
        self,
        now_beijing: datetime,
        trading_date: str,
    ):
        """Handle market open period: real-time price monitoring"""
        current_phase = self.state_manager.get("status")

        if current_phase != "market_open":
            self.current_phase = "market_open"
            self.state_manager.update("status", "market_open")
            self.state_manager.update("current_trading_date", trading_date)

            # Ensure price manager is running
            if self.price_manager and not self.mock_mode:
                if (
                    not hasattr(self.price_manager, "running")
                    or not self.price_manager.running
                ):
                    logger.info("🚀 Market open, starting price fetching")
                    self.price_manager.start()

            await self.broadcast(
                {
                    "type": "system",
                    "content": f"📊 Market open (Trading day: {trading_date}), real-time price monitoring...",
                },
            )
            logger.info(
                f"📊 Market open period: {now_beijing.strftime('%H:%M:%S')}",
            )

        # Calculate time to close and trade execution
        next_trade_time = self._get_next_trade_execution_time_beijing()
        hours_to_trade = (next_trade_time - now_beijing).total_seconds() / 3600

        logger.info(
            f"⏰ Current time: {now_beijing.strftime('%Y-%m-%d %H:%M:%S')} | Status: Market open | Hours to trade execution: {hours_to_trade:.1f}",
        )

        # Broadcast time and status update
        market_status = self._get_market_status()
        await self.broadcast(
            {
                "type": "time_update",
                "beijing_time": now_beijing.isoformat(),
                "beijing_time_str": now_beijing.strftime("%Y-%m-%d %H:%M:%S"),
                "status": "market_open",
                "trading_date": trading_date,
                "next_trade_time": next_trade_time.isoformat(),
                "hours_to_trade": round(hours_to_trade, 1),
                "market_status": market_status,
                "is_mock_mode": self.mock_mode,
            },
        )

        # Broadcast market status update separately
        await self.broadcast(
            {
                "type": "market_status_update",
                "market_status": market_status,
            },
        )

    async def _handle_off_market_period(self, now_beijing: datetime):
        """Handle off-market period: only maintain page updates"""
        current_phase = self.state_manager.get("status")

        if current_phase not in ["off_market", "trade_execution"]:
            self.current_phase = "off_market"
            self.state_manager.update("status", "off_market")

            # Stop price manager
            if self.price_manager and not self.mock_mode:
                if (
                    hasattr(self.price_manager, "running")
                    and self.price_manager.running
                ):
                    logger.info(
                        "🛑 Off-market period, stopping price fetching",
                    )
                    self.price_manager.stop()

            next_open = self._get_next_market_open_time_beijing()
            hours_to_open = (next_open - now_beijing).total_seconds() / 3600

            await self.broadcast(
                {
                    "type": "system",
                    "content": f"⏸️ Off-market period, approximately {hours_to_open:.1f} hours until next market open",
                },
            )
            logger.info(
                f"⏸️ Off-market period: {now_beijing.strftime('%H:%M:%S')}",
            )

        # Broadcast time update
        next_open = self._get_next_market_open_time_beijing()
        hours_to_open = (next_open - now_beijing).total_seconds() / 3600

        logger.info(
            f"⏰ Current time: {now_beijing.strftime('%Y-%m-%d %H:%M:%S')} | Status: Off-market period | Hours to open: {hours_to_open:.1f}",
        )

        market_status = self._get_market_status()
        await self.broadcast(
            {
                "type": "time_update",
                "beijing_time": now_beijing.isoformat(),
                "beijing_time_str": now_beijing.strftime("%Y-%m-%d %H:%M:%S"),
                "status": "off_market",
                "next_open": next_open.isoformat(),
                "hours_to_open": round(hours_to_open, 1),
                "market_status": market_status,
                "is_mock_mode": self.mock_mode,
            },
        )

        # Broadcast market status update separately
        await self.broadcast(
            {
                "type": "market_status_update",
                "market_status": market_status,
            },
        )

    async def _run_data_updater(self):
        """Execute data update task"""
        logger.info("🔄 [Scheduled Task] Starting historical data update...")

        # Broadcast update start
        await self.broadcast(
            {
                "type": "system",
                "content": "🔄 Automatically updating historical data...",
            },
        )

        # Execute data update (run in subprocess to avoid blocking)
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "backend.data.ret_data_updater",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(BASE_DIR),
        )

        _stdout, stderr = await process.communicate()

        if process.returncode == 0:
            logger.info("✅ [Scheduled Task] Historical data update completed")
            await self.broadcast(
                {
                    "type": "system",
                    "content": "✅ Historical data update completed",
                },
            )
        else:
            error_msg = (
                stderr.decode("utf-8", errors="ignore")
                if stderr
                else "Unknown error"
            )
            logger.warning(
                f"⚠️ [Scheduled Task] Historical data update failed: {error_msg[:200]}",
            )
            await self.broadcast(
                {
                    "type": "system",
                    "content": "⚠️ Historical data update failed (may be weekend/holiday), will use existing data",
                },
            )

    async def _daily_data_updater_scheduler(self):
        """Scheduler to execute data update daily at 05:10"""
        logger.info(
            "📅 Data update scheduler started (executes daily at 05:10)",
        )

        try:
            while True:
                # Get current time
                now = datetime.now()

                # Calculate next execution time (today's or tomorrow's 05:10)
                target_time = datetime_time(5, 10)  # 05:10

                if now.time() < target_time:
                    # Today hasn't reached 05:10 yet, execute today
                    next_run = datetime.combine(now.date(), target_time)
                else:
                    # Today has passed 05:10, execute tomorrow
                    next_run = datetime.combine(
                        now.date() + timedelta(days=1),
                        target_time,
                    )

                # Calculate wait time (seconds)
                wait_seconds = (next_run - now).total_seconds()

                logger.info(
                    f"⏰ Next data update time: {next_run.strftime('%Y-%m-%d %H:%M:%S')} (waiting {wait_seconds/3600:.2f} hours)",
                )

                # Wait until execution time
                await asyncio.sleep(wait_seconds)

                # Execute data update
                await self._run_data_updater()
        except asyncio.CancelledError:
            logger.info("📅 Data update scheduler stopped")
            raise

    async def _periodic_state_saver(self):
        """Periodically save state (every 5 minutes)"""
        while True:
            await asyncio.sleep(300)
            self.state_manager.save()

    async def _periodic_dashboard_monitor(self):
        """Periodically monitor Dashboard file changes and broadcast (every 5 seconds)"""
        logger.info(
            "🔍 Dashboard file monitor started (checks every 5 seconds)",
        )
        # Broadcast all Dashboard files immediately on startup (ensure frontend receives initial data)
        try:
            await self._broadcast_all_dashboard_files()
        except Exception as e:
            logger.error(
                f"❌ Failed to broadcast Dashboard data on startup: {e}",
            )

        # Initialize before the loop
        self._last_market_status_update = datetime.now()

        while True:
            try:
                await asyncio.sleep(5)
                await self._broadcast_dashboard_from_files()

                # Periodically update market status (every 60 seconds)
                if (
                    datetime.now() - self._last_market_status_update
                ).total_seconds() >= 60:
                    market_status = self._get_market_status()
                    await self.broadcast(
                        {
                            "type": "market_status_update",
                            "market_status": market_status,
                        },
                    )
                    self._last_market_status_update = datetime.now()
            except Exception as e:
                logger.error(f"❌ Dashboard file monitor error: {e}")

    async def start(self, host: str = "0.0.0.0", port: int = 8766):
        """Start server"""
        self.loop = asyncio.get_event_loop()

        # Load saved state
        self.state_manager.load()

        # Start WebSocket server
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
            dashboard_monitor_task = asyncio.create_task(
                self._periodic_dashboard_monitor(),
            )

            # Start data update scheduler (only in non-Mock mode)
            data_updater_task = None
            if not self.mock_mode:
                data_updater_task = asyncio.create_task(
                    self._daily_data_updater_scheduler(),
                )

            # Start live trading simulation
            simulation_task = asyncio.create_task(
                self.run_live_trading_simulation(),
            )

            try:
                await simulation_task
            except KeyboardInterrupt:
                logger.info("Received interrupt signal, shutting down...")
            finally:
                self.state_manager.save()
                logger.info("✅ Final state saved")

                saver_task.cancel()
                dashboard_monitor_task.cancel()
                if data_updater_task:
                    data_updater_task.cancel()

                if self.price_manager:
                    self.price_manager.stop()


async def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(description="Live trading system server")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use Mock mode (virtual price testing)",
    )
    parser.add_argument(
        "--config-name",
        default="live_mode",
        help="Config name (default: live_mode)",
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
        "--pause-before-trade",
        action="store_true",
        dest="pause_before_trade_cli",
        help="Pause mode: complete analysis but do not execute trades, only update prices",
    )
    parser.add_argument(
        "--time-accelerator",
        type=float,
        default=1.0,
        help="Time accelerator (for debugging, 1.0=normal, 60.0=1 minute as 1 hour)",
    )
    parser.add_argument(
        "--virtual-start-time",
        type=str,
        default=None,
        help='Virtual start time (format: "2024-11-12 22:25:00", Mock mode only)',
    )
    args = parser.parse_args()

    # Load config
    config = LiveThinkingFundConfig()
    config.config_name = args.config_name

    # Determine pause mode: command line argument takes priority, otherwise use environment variable config
    # Priority: command line > environment variable > default (False)
    if args.pause_before_trade_cli:
        # Command line explicitly specified --pause-before-trade
        pause_before_trade = True
        pause_source = "Command line argument"
    else:
        # Use value from config object (from environment variable or default)
        pause_before_trade = getattr(config, "pause_before_trade", False)
        if pause_before_trade:
            pause_source = "Environment variable"
        else:
            pause_source = "Default value"

    # Print config
    logger.info("📊 Live trading server configuration:")
    logger.info(f"   Config name: {config.config_name}")
    logger.info(
        f"   Run mode: {'🎭 MOCK (virtual prices)' if args.mock else '🚀 LIVE (real-time prices)'}",
    )
    logger.info(f"   Monitored stocks: {config.tickers}")
    if config.mode == "portfolio":
        logger.info(f"   Initial cash: ${config.initial_cash:,.2f}")
        logger.info(
            f"   Margin requirement: {config.margin_requirement * 100:.1f}%",
        )
    if pause_before_trade:
        logger.info(
            f"   Trade execution: ⏸️ Pause mode (analysis only, no trade execution) [Source: {pause_source}]",
        )
    else:
        logger.info(
            "   Trade execution: ▶️ Normal mode (execute trades after analysis)",
        )
    if args.time_accelerator != 1.0:
        logger.info(
            f"   ⚡ Time acceleration: {args.time_accelerator}x (debug mode)",
        )

    # Parse virtual start time
    virtual_start_time = None
    if args.virtual_start_time and args.mock:
        from datetime import timezone

        virtual_start_time = datetime.strptime(
            args.virtual_start_time,
            "%Y-%m-%d %H:%M:%S",
        )
        virtual_start_time = virtual_start_time.replace(
            tzinfo=timezone(timedelta(hours=8)),
        )  # Beijing time
        logger.info(
            f"   🕐 Virtual start time: {virtual_start_time.strftime('%Y-%m-%d %H:%M:%S')} (Beijing time)",
        )

    # Create and start server
    server = LiveTradingServer(
        config,
        mock_mode=args.mock,
        pause_before_trade=pause_before_trade,
        time_accelerator=args.time_accelerator,
        virtual_start_time=virtual_start_time,
    )
    await server.start(host=args.host, port=args.port)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Bye!")
