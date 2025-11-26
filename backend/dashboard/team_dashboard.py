#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Team Dashboard Data Generator
Provides 5 main data interfaces for frontend: summary, holdings, stats, trades, leaderboard
"""
# flake8: noqa: E501
# pylint: disable=C0301
# pylint: disable=W0613
import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import pandas_market_calendars as mcal


class TeamDashboardGenerator:
    """Team Dashboard Data Generator"""

    # Agent information configuration
    TEAM_ROLES = {"portfolio_manager", "risk_manager"}

    AGENT_CONFIG = {
        "portfolio_manager": {
            "name": "Portfolio Manager",
            "role": "Portfolio Manager",
            "avatar": "pm",
        },
        "risk_manager": {
            "name": "Risk Manager",
            "role": "Risk Manager",
            "avatar": "risk",
        },
        "sentiment_analyst": {
            "name": "Sentiment Analyst",
            "role": "Sentiment Analyst",
            "avatar": "sentiment",
        },
        "technical_analyst": {
            "name": "Technical Analyst",
            "role": "Technical Analyst",
            "avatar": "technical",
        },
        "fundamentals_analyst": {
            "name": "Fundamentals Analyst",
            "role": "Fundamentals Analyst",
            "avatar": "fundamentals",
        },
        "valuation_analyst": {
            "name": "Valuation Analyst",
            "role": "Valuation Analyst",
            "avatar": "valuation",
        },
    }

    def __init__(
        self,
        dashboard_dir: Path,
        initial_cash: float = 100000.0,
        price_data_dir: Path = None,
    ):
        """
        Initialize team dashboard generator

        Args:
            dashboard_dir: team_dashboard directory path
            initial_cash: Initial cash (for calculating returns)
            price_data_dir: Price data directory path (default: backend/data/ret_data)
        """
        self.dashboard_dir = Path(dashboard_dir)
        self.dashboard_dir.mkdir(parents=True, exist_ok=True)

        self.initial_cash = initial_cash

        # Price data directory
        if price_data_dir is None:
            # Default path: relative to project root
            project_root = Path(__file__).parent.parent.parent
            self.price_data_dir = (
                project_root / "backend" / "data" / "ret_data"
            )
        else:
            self.price_data_dir = Path(price_data_dir)

        # 5 data file paths
        self.summary_file = self.dashboard_dir / "summary.json"
        self.holdings_file = self.dashboard_dir / "holdings.json"
        self.stats_file = self.dashboard_dir / "stats.json"
        self.trades_file = self.dashboard_dir / "trades.json"
        self.leaderboard_file = self.dashboard_dir / "leaderboard.json"

        # Internal state file (stores accumulated data)
        self.state_file = self.dashboard_dir / "_internal_state.json"

        # Default base price (used when no historical price available)
        self.DEFAULT_BASE_PRICE = 100.0

        # Cache price data
        self._price_cache = {}  # ticker -> DataFrame

    def _get_next_trading_day(self, date: str) -> str:
        """
        Get the next trading day for the specified date

        Args:
            date: Date string (YYYY-MM-DD)

        Returns:
            Next trading day date string (YYYY-MM-DD)
        """
        _NYSE_CALENDAR = mcal.get_calendar("NYSE")

        if _NYSE_CALENDAR is not None:
            try:
                # Look forward 30 days from current date to get all trading days
                current_date = datetime.strptime(date, "%Y-%m-%d")
                end_search = current_date + timedelta(days=30)

                if hasattr(_NYSE_CALENDAR, "valid_days"):
                    # pandas_market_calendars
                    trading_dates = _NYSE_CALENDAR.valid_days(
                        start_date=date,
                        end_date=end_search.strftime("%Y-%m-%d"),
                    )
                else:
                    # exchange_calendars
                    trading_dates = _NYSE_CALENDAR.sessions_in_range(
                        date,
                        end_search.strftime("%Y-%m-%d"),
                    )

                # Convert to date list
                trading_dates_list = [
                    pd.Timestamp(d).strftime("%Y-%m-%d") for d in trading_dates
                ]

                # Find current date position in the list
                if date in trading_dates_list:
                    idx = trading_dates_list.index(date)
                    if idx + 1 < len(trading_dates_list):
                        return trading_dates_list[idx + 1]
                else:
                    # If current date is not a trading day, return the first trading day
                    if trading_dates_list:
                        return trading_dates_list[0]
            except Exception as e:
                print(f"⚠️ Failed to get next trading day ({date}): {e}")

        # Fallback: Simply add 1 day (ignoring weekends and holidays)
        current_date = datetime.strptime(date, "%Y-%m-%d")
        next_date = current_date + timedelta(days=1)
        return next_date.strftime("%Y-%m-%d")

    def _load_json(self, file_path: Path, default: Any = None) -> Any:
        """Load JSON file"""
        if not file_path.exists():
            return default if default is not None else {}
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load {file_path}: {e}")
            return default if default is not None else {}

    def _save_json(self, file_path: Path, data: Any):
        """Save JSON file"""
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            print(f"Failed to save {file_path}: {e}")

    def _load_internal_state(self) -> Dict[str, Any]:
        """Load internal state"""
        state = self._load_json(
            self.state_file,
            {
                "equity_history": [],  # [{t: timestamp, v: value}]
                # Buy & Hold baseline history (equal weight)
                "baseline_history": [],
                "baseline_vw_history": [],  # Buy & Hold value-weighted baseline history
                "momentum_history": [],  # Momentum strategy history
                "all_trades": [],  # All trade history
                # {date: {ticker: qty}} - Daily position snapshots for fast lookup
                "daily_position_history": {},
                "agent_performance": {},  # agent_id -> {signals: [], bull_count: 0, bull_win: 0, ...}
                "portfolio_state": {  # Current position state
                    "cash": self.initial_cash,
                    "positions": {},  # ticker -> {qty, avg_cost}
                },
                "baseline_state": {  # Buy & Hold position state (equal weight)
                    "initial_allocation": {},  # ticker -> {qty, buy_price, buy_date}
                    "initialized": False,
                },
                "baseline_vw_state": {  # Buy & Hold value-weighted position state
                    "initial_allocation": {},  # ticker -> {qty, buy_price, buy_date, weight}
                    "initialized": False,
                },
                "momentum_state": {  # Momentum strategy position state
                    "positions": {},  # ticker -> {qty, buy_price, buy_date}
                    "cash": self.initial_cash,
                    "initialized": False,
                    "last_rebalance_date": None,
                    "rebalance_period_days": 20,  # Rebalance every 20 trading days
                    "lookback_days": 20,  # Look back 20 days to calculate momentum
                    "top_n": 3,  # Hold top 3 stocks with strongest momentum
                },
                "last_update_date": None,
                "total_value_history": [],  # For calculating returns
                "price_history": {},  # ticker -> {date: price} Track daily prices
            },
        )

        # Ensure portfolio_state exists
        if "portfolio_state" not in state:
            state["portfolio_state"] = {
                "cash": self.initial_cash,
                "positions": {},
                "margin_used": 0.0,  # Initialize margin_used
            }

        # Ensure total_value_history exists
        if "total_value_history" not in state:
            state["total_value_history"] = []

        # Ensure baseline_state exists
        if "baseline_state" not in state:
            state["baseline_state"] = {
                "initial_allocation": {},
                "initialized": False,
            }

        # Ensure baseline_history exists
        if "baseline_history" not in state:
            state["baseline_history"] = []

        # Ensure momentum_state exists
        if "momentum_state" not in state:
            state["momentum_state"] = {
                "positions": {},
                "cash": self.initial_cash,
                "initialized": False,
                "last_rebalance_date": None,
                "rebalance_period_days": 20,
                "lookback_days": 20,
                "top_n": 3,
            }

        # Ensure momentum_history exists
        if "momentum_history" not in state:
            state["momentum_history"] = []

        # Ensure baseline_vw_state exists
        if "baseline_vw_state" not in state:
            state["baseline_vw_state"] = {
                "initial_allocation": {},
                "initialized": False,
            }

        # Ensure baseline_vw_history exists
        if "baseline_vw_history" not in state:
            state["baseline_vw_history"] = []

        return state

    def _save_internal_state(self, state: Dict[str, Any]):
        """Save internal state"""
        self._save_json(self.state_file, state)

    def _load_price_data(self, ticker: str) -> Optional[pd.DataFrame]:
        """
        Load stock price data

        Args:
            ticker: Stock ticker

        Returns:
            Price data DataFrame, returns None if file doesn't exist
        """
        # Check cache
        if ticker in self._price_cache:
            return self._price_cache[ticker]

        # Build CSV file path
        csv_file = self.price_data_dir / f"{ticker}.csv"

        if not csv_file.exists():
            print(f"⚠️ Price data file does not exist: {csv_file}")
            return None

        try:
            # Read CSV file
            df = pd.read_csv(csv_file)

            # Parse date column
            df["Date"] = pd.to_datetime(df["time"])

            # Extract date (without time) as index
            df["date_str"] = df["Date"].dt.strftime("%Y-%m-%d")
            df.set_index("date_str", inplace=True)

            # Cache data
            self._price_cache[ticker] = df

            return df
        except Exception as e:
            print(f"❌ Failed to load price data ({ticker}): {e}")
            return None

    def _get_price_from_csv(
        self,
        ticker: str,
        date: str,
        price_type: str = "close",
    ) -> Optional[float]:
        """
        Get price for specified date from CSV file

        Args:
            ticker: Stock ticker
            date: Date YYYY-MM-DD
            price_type: Price type ('open', 'close', 'high', 'low')

        Returns:
            Price, returns None if not found
        """
        df = self._load_price_data(ticker)

        if df is None:
            return None

        try:
            if date in df.index:
                return float(df.loc[date, price_type])
            else:
                # Date doesn't exist, might be a non-trading day
                return None
        except Exception as e:
            print(f"⚠️ Failed to get price ({ticker}, {date}): {e}")
            return None

    def update_from_day_result(
        self,
        date: str,
        pre_market_result: Dict[str, Any],
        mode: str = "signal",
    ) -> Dict[str, Any]:
        """
        Update all dashboard data based on single day result

        Args:
            date: Trading date YYYY-MM-DD
            pre_market_result: Pre-market analysis result (contains signals, live_env, etc.)
            mode: Running mode ("signal" or "portfolio")

        Returns:
            Update statistics
        """
        # if pre_market_result.get('status') != 'success':
        #     print(f"⚠️ {date} Pre-market analysis not successful, skipping dashboard update")
        #     return {'status': 'skipped', 'reason': 'pre_market not successful'}

        # Load internal state
        state = self._load_internal_state()

        # Note: Model configuration is now always read fresh from environment variables
        # in _get_agent_model_config(), no need to store in state

        # Extract data
        live_env = pre_market_result["pre_market"].get("live_env", {})
        real_returns = live_env.get("real_returns", {})
        pm_signals = live_env.get("pm_signals", {})
        ana_signals = live_env.get("ana_signals", {})
        # Timestamp (using next trading day 05:00:00 Asia/Shanghai timezone)
        # This way equity value will be displayed at 05:00 of the next trading day
        next_trading_day_str = self._get_next_trading_day(date)
        next_trading_day_obj = datetime.strptime(
            next_trading_day_str,
            "%Y-%m-%d",
        )
        # Set to 05:00:00 (Asia/Shanghai timezone 05:00)
        next_day_0500 = next_trading_day_obj.replace(
            hour=5,
            minute=0,
            second=0,
            microsecond=0,
        )
        timestamp_ms = int(next_day_0500.timestamp() * 1000)
        update_stats = {
            "date": date,
            "mode": mode,
            "trades_added": 0,
            "agents_updated": 0,
        }

        # 0. Initialize Buy & Hold and value-weighted Buy & Hold (only first time)
        available_tickers = list(pm_signals.keys())
        self._initialize_buy_and_hold(date, available_tickers, state)
        self._initialize_buy_and_hold_vw(date, available_tickers, state)
        # 1. Update trade records and positions
        if mode == "portfolio":
            self._update_portfolio_mode(
                date,
                timestamp_ms,
                pm_signals,
                real_returns,
                live_env,
                state,
                update_stats,
            )
        else:
            self._update_signal_mode(
                date,
                timestamp_ms,
                pm_signals,
                real_returns,
                state,
                update_stats,
            )

        # 2. Update price history (based on returns)
        self._update_price_history(date, real_returns, state)

        # 3. Update Agent performance
        self._update_agent_performance(
            date,
            ana_signals,
            pm_signals,
            real_returns,
            state,
            update_stats,
        )

        # 4. Update Portfolio Manager performance (pass live_env to get final positions)
        self._update_pm_performance(
            date,
            pm_signals,
            real_returns,
            state,
            update_stats,
            live_env,
            mode,
        )

        # 5. Check if closing price data exists, only update equity curve when prices are confirmed
        has_closing_prices = self._check_has_closing_prices(
            date,
            available_tickers,
        )
        curves_updated = False

        if has_closing_prices:
            # 5a. Update equity curve
            self._update_equity_curve(date, timestamp_ms, state)

            # 5b. Update Buy & Hold baseline (equal weight)
            self._update_baseline_curve(date, timestamp_ms, state)

            # 5c. Update value-weighted Buy & Hold baseline
            self._update_baseline_vw_curve(date, timestamp_ms, state)

            # 5d. Update momentum strategy curve
            self._update_momentum_curve(
                date,
                timestamp_ms,
                available_tickers,
                state,
            )

            curves_updated = True
            print(f"✅ Equity curve updated ({date})")
        else:
            print(
                f"⏸️  Skipping equity curve update ({date}) - waiting for closing price data",
            )

        # 8. Save internal state
        state["last_update_date"] = date
        state[
            "curves_updated"
        ] = curves_updated  # Record whether curves were updated
        self._save_internal_state(state)

        # 9. Generate all frontend data files
        # Note: holdings, stats, trades, leaderboard need to be updated every time (includes real-time trading signals)
        # But summary is only regenerated when curves are updated (to avoid unnecessary broadcasts)
        if curves_updated:
            self._generate_summary(state)
            print(f"✅ {date} Team dashboard equity curve updated")
        else:
            print(
                f"⏸️  {date} Skipping equity curve update - waiting for closing price data",
            )

        # Other data always updated (includes real-time trading signals and Agent performance)
        self._generate_holdings(state)
        self._generate_stats(state)
        self._generate_trades(state)
        self._generate_leaderboard(state)

        print(f"✅ {date} Team dashboard data updated")
        return update_stats

    def _update_price_history(
        self,
        date: str,
        real_returns: Dict,
        state: Dict,
    ):
        """
        Update price history (read actual prices directly from CSV files)

        Logic:
        - Read close price for corresponding date from CSV files in ret_data directory
        - If read fails, use DEFAULT_BASE_PRICE as fallback
        """
        if "price_history" not in state:
            state["price_history"] = {}

        price_history = state["price_history"]

        # Iterate through all involved tickers (from real_returns)
        for ticker in real_returns.keys():
            if ticker not in price_history:
                price_history[ticker] = {}

            # Get actual price from CSV file
            actual_price = self._get_price_from_csv(ticker, date, "close")

            # Successfully got actual price
            price_history[ticker][date] = actual_price

    def _check_has_closing_prices(self, date: str, tickers: List[str]) -> bool:
        """
        Check if all stocks have closing price data for specified date

        Args:
            date: Trading date YYYY-MM-DD
            tickers: List of stock tickers

        Returns:
            True if all stocks have closing price data, False otherwise
        """
        if not tickers:
            return False

        # Check at least half of stocks have closing prices
        valid_count = 0
        for ticker in tickers:
            price = self._get_price_from_csv(ticker, date, "close")
            if price is not None:
                valid_count += 1

        # Need at least half of stocks to have closing price data
        return valid_count >= len(tickers) / 2

    def _get_current_price(self, ticker: str, date: str, state: Dict) -> float:
        """
        Get current price of stock

        Priority:
        1. Read actual price directly from CSV file
        2. Price from price_history (if CSV read fails)
        3. Default base price
        """
        # Priority: get actual price from CSV file
        actual_price = self._get_price_from_csv(ticker, date, "close")
        if actual_price is not None:
            return actual_price

        # If CSV read fails, try to get from price_history
        price_history = state.get("price_history", {})

        if ticker in price_history and date in price_history[ticker]:
            actual_price = price_history[ticker][date]
            if actual_price is not None:
                return actual_price

        # If historical prices exist, use the latest non-None price
        if ticker in price_history and price_history[ticker]:
            dates = sorted(price_history[ticker].keys())
            # Search backwards from latest date to find first non-None price
            for date in reversed(dates):
                price = price_history[ticker][date]
                if price is not None:
                    return price

    def _get_ticker_price(
        self,
        ticker: str,
        date: str,
        signal_info: Dict,
        portfolio_state: Dict,
        real_returns: Dict,
    ) -> float:
        """
        Get stock price (try multiple sources)

        Priority:
        1. Read actual price from CSV file

        """
        # 1. Priority: get actual price from CSV file
        actual_price = self._get_price_from_csv(ticker, date, "close")
        return actual_price

    def _normalize_real_return(
        self,
        value: Any,
    ) -> Tuple[Optional[float], Any]:
        """
        Normalize real return:
        - Returns (float value for calculation or None, display value for frontend/unknown)
        """
        if value is None:
            return None, "unknown"

        # Handle string (might already be "unknown" or numeric string)
        if isinstance(value, str):
            if value.lower() == "unknown":
                return None, "unknown"
            try:
                value = float(value)
            except ValueError:
                return None, "unknown"

        if isinstance(value, (int, float)):
            # bool is also a subclass of int, convert directly
            value = float(value)
            if math.isnan(value):
                return None, "unknown"
            return value, value

        return None, "unknown"

    def _update_portfolio_mode(
        self,
        date: str,
        timestamp_ms: int,
        pm_signals: Dict,
        real_returns: Dict,
        live_env: Dict,
        state: Dict,
        update_stats: Dict,
    ):
        """Portfolio mode: Update trades and positions"""
        portfolio_state = state["portfolio_state"]

        # Get portfolio information
        portfolio_summary = live_env.get("portfolio_summary", {})
        updated_portfolio = live_env.get("updated_portfolio", {})

        # If updated_portfolio exists, use it directly
        if updated_portfolio:
            portfolio_state["cash"] = updated_portfolio.get(
                "cash",
                portfolio_state["cash"],
            )
            portfolio_state["margin_used"] = updated_portfolio.get(
                "margin_used",
                0.0,
            )  # Add margin_used
            new_positions = updated_portfolio.get("positions", {})

            # Update positions (convert to simplified format)
            for ticker, position_data in new_positions.items():
                long_qty = position_data.get("long", 0)
                short_qty = position_data.get("short", 0)
                long_cost = position_data.get("long_cost_basis", 0)
                short_cost = position_data.get("short_cost_basis", 0)

                # Merge long/short positions (simplified: net position)
                net_qty = long_qty - short_qty
                if net_qty != 0:
                    avg_cost = long_cost if net_qty > 0 else short_cost
                    portfolio_state["positions"][ticker] = {
                        "qty": net_qty,
                        "avg_cost": avg_cost,
                    }
                elif ticker in portfolio_state["positions"]:
                    # Position cleared
                    del portfolio_state["positions"][ticker]

        # Record trades (only record actually executed successful trades)
        executed_trades = live_env.get("executed_trades", [])
        # pdb.set_trace()
        for executed_trade in executed_trades:
            # pdb.set_trace()
            ticker = executed_trade["ticker"]
            action = executed_trade["action"]
            quantity = executed_trade["target_quantity"]
            price = executed_trade["price"]

            if action != "hold" and quantity > 0:
                numeric_real_return, _ = self._normalize_real_return(
                    real_returns.get(ticker),
                )

                # Calculate P&L for this trade (based on daily return, record as 0 if unknown)
                if numeric_real_return is None:
                    pnl = 0.0
                elif action == "long":
                    pnl = quantity * price * numeric_real_return
                elif action == "short":
                    pnl = -quantity * price * numeric_real_return
                else:
                    pnl = 0.0
                # Map action to side (for display)
                side_map = {
                    "long": "LONG",
                    "short": "SHORT",
                    "hold": "HOLD",
                }
                side = side_map.get(action, "HOLD")

                # Generate trade ID
                trade_count = len(
                    [
                        t
                        for t in state["all_trades"]
                        if t["ticker"] == ticker and t["ts"] == timestamp_ms
                    ],
                )
                trade_id = (
                    f"t_{date.replace('-', '')[:8]}_{ticker}_{trade_count}"
                )

                trade_record = {
                    "id": trade_id,
                    "ts": timestamp_ms,
                    "trading_date": date,  # ✨ Store trading date explicitly to avoid timezone confusion
                    "side": side,
                    "ticker": ticker,
                    "qty": quantity,
                    "price": round(price, 2),
                    "pnl": round(pnl, 2),
                }
                # pdb.set_trace()
                state["all_trades"].append(trade_record)
                update_stats["trades_added"] += 1

        # Save daily position snapshot for fast lookup (optimization for PM's _get_recent_memory)
        if "daily_position_history" not in state:
            state["daily_position_history"] = {}

        # Save current positions as end-of-day snapshot
        position_snapshot = {}
        for ticker, pos_data in portfolio_state["positions"].items():
            position_snapshot[ticker] = pos_data["qty"]
        state["daily_position_history"][date] = position_snapshot

    def _update_signal_mode(
        self,
        date: str,
        timestamp_ms: int,
        pm_signals: Dict,
        real_returns: Dict,
        state: Dict,
        update_stats: Dict,
    ):
        """Signal mode: Update signal records"""
        portfolio_state = state["portfolio_state"]

        # In Signal mode, simulate position changes (assume fixed quantity for each signal)
        DEFAULT_QUANTITY = 100  # Default trade quantity

        for ticker, signal_info in pm_signals.items():
            signal = signal_info.get("signal", "neutral")
            action = signal_info.get("action", "hold")

            # if action == 'hold':
            #     continue

            # Get current price
            price = self._get_ticker_price(
                ticker,
                date,
                signal_info,
                portfolio_state,
                real_returns,
            )
            numeric_real_return, _ = self._normalize_real_return(
                real_returns.get(ticker),
            )
            quantity = DEFAULT_QUANTITY

            # Map signal to side
            side_map = {
                "bullish": "BUY",
                "bearish": "SELL",
                "neutral": "HOLD",
            }
            side = side_map.get(signal, "HOLD")

            # Update positions
            if signal == "bullish":
                if ticker not in portfolio_state["positions"]:
                    portfolio_state["positions"][ticker] = {
                        "qty": 0,
                        "avg_cost": price,
                    }
                pos = portfolio_state["positions"][ticker]
                old_qty = pos["qty"]
                old_cost = pos["avg_cost"]
                new_qty = old_qty + quantity
                # Calculate new average cost
                if new_qty > 0:
                    new_cost = (
                        old_qty * old_cost + quantity * price
                    ) / new_qty
                    pos["qty"] = new_qty
                    pos["avg_cost"] = new_cost
            elif signal == "bearish":
                if ticker in portfolio_state["positions"]:
                    pos = portfolio_state["positions"][ticker]
                    pos["qty"] = max(0, pos["qty"] - quantity)
                    if pos["qty"] == 0:
                        del portfolio_state["positions"][ticker]

            # Calculate P&L (treat as 0 when return is unknown)
            pnl = (
                quantity
                * price
                * (
                    numeric_real_return
                    if numeric_real_return is not None
                    else 0.0
                )
            )

            # Generate trade ID
            trade_count = len(
                [
                    t
                    for t in state["all_trades"]
                    if t["ticker"] == ticker and t["ts"] == timestamp_ms
                ],
            )
            trade_id = f"t_{date.replace('-', '')}_{ticker}_{trade_count}"

            trade_record = {
                "id": trade_id,
                "ts": timestamp_ms,
                "trading_date": date,  # ✨ Store trading date explicitly to avoid timezone confusion
                "side": side,
                "ticker": ticker,
                "qty": quantity,
                "price": round(price, 2),
                "pnl": round(pnl, 2),
            }

            state["all_trades"].append(trade_record)
            update_stats["trades_added"] += 1

        # Save daily position snapshot for fast lookup (optimization for PM's _get_recent_memory)
        if "daily_position_history" not in state:
            state["daily_position_history"] = {}

        # Save current positions as end-of-day snapshot
        position_snapshot = {}
        for ticker, pos_data in portfolio_state["positions"].items():
            position_snapshot[ticker] = pos_data["qty"]
        state["daily_position_history"][date] = position_snapshot

    def _update_agent_performance(
        self,
        date: str,
        ana_signals: Dict,
        pm_signals: Dict,
        real_returns: Dict,
        state: Dict,
        update_stats: Dict,
    ):
        """Update analyst performance"""
        if "agent_performance" not in state:
            state["agent_performance"] = {}

        for agent_id, signals in ana_signals.items():
            if agent_id not in state["agent_performance"]:
                state["agent_performance"][agent_id] = {
                    "signals": [],
                    "bull_count": 0,
                    "bull_win": 0,
                    "bull_unknown": 0,
                    "bear_count": 0,
                    "bear_win": 0,
                    "bear_unknown": 0,
                    "neutral_count": 0,
                    "logs": [],
                }

            agent_perf = state["agent_performance"][agent_id]
            agent_perf.setdefault("bull_unknown", 0)
            agent_perf.setdefault("bear_unknown", 0)

            for ticker, signal_data in signals.items():
                if not signal_data or signal_data == "N/A":
                    continue

                # Extract signal value (supports dict and string formats)
                if isinstance(signal_data, dict):
                    signal = signal_data.get("signal", "N/A")
                else:
                    signal = signal_data

                if not signal or signal == "N/A":
                    continue

                (
                    numeric_real_return,
                    display_real_return,
                ) = self._normalize_real_return(real_returns.get(ticker))

                # Determine signal type and correctness (standardized format, case-insensitive)
                signal_lower = (
                    signal.lower()
                    if isinstance(signal, str)
                    else str(signal).lower()
                )
                is_bull = (
                    signal_lower in ["buy", "bullish", "long"]
                    or "bull" in signal_lower
                )
                is_bear = (
                    signal_lower in ["sell", "bearish", "short"]
                    or "bear" in signal_lower
                )
                is_neutral = (
                    signal_lower in ["hold", "neutral"]
                    or "neutral" in signal_lower
                )

                is_correct = False
                result_unknown = numeric_real_return is None

                if is_bull:
                    agent_perf["bull_count"] += 1
                    if result_unknown:
                        agent_perf["bull_unknown"] += 1
                    elif numeric_real_return > 0:
                        is_correct = True
                        agent_perf["bull_win"] += 1
                elif is_bear:
                    agent_perf["bear_count"] += 1
                    if result_unknown:
                        agent_perf["bear_unknown"] += 1
                    elif numeric_real_return < 0:
                        is_correct = True
                        agent_perf["bear_win"] += 1
                elif is_neutral:
                    agent_perf["neutral_count"] += 1
                    # neutral signals are not included in win rate statistics

                # Record signal
                signal_record = {
                    "date": date,
                    "ticker": ticker,
                    "signal": signal,
                    "real_return": display_real_return,
                    "is_correct": "unknown" if result_unknown else is_correct,
                }
                agent_perf["signals"].append(signal_record)

                # Update logs (keep last 50 entries)
                if result_unknown and not is_neutral:
                    marker = "?"
                elif is_neutral:
                    marker = ""
                else:
                    marker = "✓" if is_correct else "✗"
                log_entry = f"{'Bull' if is_bull else 'Bear' if is_bear else 'Neutral'} on {ticker} {marker}"
                agent_perf["logs"].insert(0, log_entry)
                agent_perf["logs"] = agent_perf["logs"][:50]

            update_stats["agents_updated"] += 1

    def _update_pm_performance(
        self,
        date: str,
        pm_signals: Dict,
        real_returns: Dict,
        state: Dict,
        update_stats: Dict,
        live_env: Dict = None,
        mode: str = "signal",
    ):
        """
        Update Portfolio Manager performance

        IMPORTANT: PM's correctness should be evaluated based on FINAL POSITION direction,
        not the action itself, because PM considers pre_position_state when making decisions.

        Example:
        - Pre-position: 100 long shares
        - PM action: short 30 shares → Final position: 70 long shares (still bullish)
        - If stock goes up (real_return > 0): PM is CORRECT (because final position is long)
        """
        agent_id = "portfolio_manager"

        if "agent_performance" not in state:
            state["agent_performance"] = {}

        if agent_id not in state["agent_performance"]:
            state["agent_performance"][agent_id] = {
                "signals": [],
                "bull_count": 0,
                "bull_win": 0,
                "bull_unknown": 0,
                "bear_count": 0,
                "bear_win": 0,
                "bear_unknown": 0,
                "neutral_count": 0,
                "logs": [],
            }

        pm_perf = state["agent_performance"][agent_id]
        pm_perf.setdefault("bull_unknown", 0)
        pm_perf.setdefault("bear_unknown", 0)

        # Get final positions (after trade execution) in portfolio mode
        updated_portfolio = (
            live_env.get("updated_portfolio", {}) if live_env else {}
        )
        final_positions = updated_portfolio.get("positions", {})

        for ticker, signal_info in pm_signals.items():
            # Determine signal based on FINAL POSITION (portfolio mode) or ACTION (signal mode)
            if mode == "portfolio" and ticker in final_positions:
                # Portfolio mode: Use final position direction after trade execution
                position = final_positions[ticker]
                long_qty = position.get("long", 0)
                short_qty = position.get("short", 0)

                # Determine final position direction
                if long_qty > 0:
                    signal = "bullish"  # Final position is long → bullish
                elif short_qty > 0:
                    signal = "bearish"  # Final position is short → bearish
                else:
                    signal = "neutral"  # No position → neutral
            else:
                # Signal mode or no position data: Use action as signal
                action = signal_info["action"]
                action_to_signal = {
                    "long": "bullish",
                    "short": "bearish",
                    "hold": "neutral",
                }
                signal = action_to_signal[action.lower()]

            (
                numeric_real_return,
                display_real_return,
            ) = self._normalize_real_return(real_returns.get(ticker))

            signal_lower = signal.lower()
            is_bull = "bull" in signal_lower or signal_lower == "long"
            is_bear = "bear" in signal_lower or signal_lower == "short"
            is_neutral = "neutral" in signal_lower or signal_lower == "hold"

            is_correct = False
            result_unknown = numeric_real_return is None
            if is_bull:
                pm_perf["bull_count"] += 1
                if result_unknown:
                    pm_perf["bull_unknown"] += 1
                elif numeric_real_return > 0:
                    is_correct = True
                    pm_perf["bull_win"] += 1
            elif is_bear:
                pm_perf["bear_count"] += 1
                if result_unknown:
                    pm_perf["bear_unknown"] += 1
                elif numeric_real_return < 0:
                    is_correct = True
                    pm_perf["bear_win"] += 1
            elif is_neutral:
                pm_perf["neutral_count"] += 1

            signal_record = {
                "date": date,
                "ticker": ticker,
                "signal": signal,
                "real_return": display_real_return,
                "is_correct": "unknown" if result_unknown else is_correct,
            }
            pm_perf["signals"].append(signal_record)

            if result_unknown and not is_neutral:
                marker = "?"
            elif is_neutral:
                marker = ""
            else:
                marker = "✓" if is_correct else "✗"
            log_entry = f"{'Bull' if is_bull else 'Bear' if is_bear else 'Neutral'} on {ticker} {marker}"
            pm_perf["logs"].insert(0, log_entry)
            pm_perf["logs"] = pm_perf["logs"][:50]

    def _update_equity_curve(self, date: str, timestamp_ms: int, state: Dict):
        """Update equity curve (using actual prices)"""
        portfolio_state = state["portfolio_state"]

        # If first update (history is empty), add initial point first (consistent with Baseline)
        # Initial value uses 05:00:00 of the same day, not 05:00 of next trading day
        if len(state["equity_history"]) == 0:
            date_obj = datetime.strptime(date, "%Y-%m-%d")
            # Set to 05:00:00 of the same day (Asia/Shanghai timezone)
            date_0500 = date_obj.replace(
                hour=5,
                minute=0,
                second=0,
                microsecond=0,
            )
            initial_timestamp_ms = int(date_0500.timestamp() * 1000)

            initial_point = {
                "t": initial_timestamp_ms,
                "v": round(self.initial_cash, 2),  # $100,000
            }
            state["equity_history"].append(initial_point)
            print(
                f"📊 Portfolio initial point: ${self.initial_cash:,.2f} at {date} 05:00:00",
            )

        # Calculate current total value: cash + margin_used + position market value (using actual prices)
        cash = portfolio_state["cash"]
        margin_used = portfolio_state.get(
            "margin_used",
            0.0,
        )  # Get margin_used, default to 0
        positions_value = 0.0

        for ticker, pos in portfolio_state["positions"].items():
            # Use actual price of the day
            current_price = self._get_current_price(ticker, date, state)
            positions_value += pos["qty"] * current_price

        total_value = cash + margin_used + positions_value

        # Use actual amount directly (no longer normalized to percentage)
        # normalized_value = (total_value / self.initial_cash) * 100

        # Add to equity curve
        equity_point = {
            "t": timestamp_ms,
            "v": round(total_value, 2),  # Store actual amount
        }
        state["equity_history"].append(equity_point)

        # Record total value history
        state["total_value_history"].append(
            {
                "date": date,
                "total_value": total_value,
            },
        )

    def _initialize_buy_and_hold(
        self,
        date: str,
        available_tickers: list,
        state: Dict,
    ):
        """
        Initialize Buy & Hold strategy

        At the close of the first trading day, buy stocks using closing price
        This ensures consistency with Portfolio's initial state

        Args:
            date: Trading date
            available_tickers: List of tradable stocks
            state: Internal state
        """
        baseline_state = state["baseline_state"]

        if baseline_state["initialized"]:
            return  # Already initialized

        if not available_tickers:
            print("⚠️ No tradable stocks, skipping Buy & Hold initialization")
            return

        # Calculate allocated funds per stock (equal weight)
        cash_per_ticker = self.initial_cash / len(available_tickers)

        initial_allocation = {}
        total_invested = 0.0

        for ticker in available_tickers:
            # Buy using closing price (consistent with Portfolio)
            price = self._get_price_from_csv(ticker, date, "close")

            if price is None or price <= 0:
                print(f"⚠️ {ticker} has no valid price on {date}, skipping")
                continue

            # Calculate purchasable quantity (round down)
            quantity = int(cash_per_ticker / price)

            if quantity > 0:
                initial_allocation[ticker] = {
                    "qty": quantity,
                    "buy_price": price,
                    "buy_date": date,
                }
                total_invested += quantity * price

        baseline_state["initial_allocation"] = initial_allocation
        baseline_state["initialized"] = True

        print(
            f"✅ Buy & Hold strategy initialized: {len(initial_allocation)} stocks, invested ${total_invested:,.2f}",
        )
        for ticker, info in initial_allocation.items():
            print(
                f"   {ticker}: {info['qty']} shares @ ${info['buy_price']:.2f}",
            )

    def _calculate_buy_and_hold_value(self, date: str, state: Dict) -> float:
        """
        Calculate current net value of Buy & Hold strategy

        Args:
            date: Current date
            state: Internal state

        Returns:
            Total asset value of Buy & Hold strategy
        """
        baseline_state = state["baseline_state"]

        if not baseline_state["initialized"]:
            return (
                self.initial_cash
            )  # Not initialized yet, return initial cash

        total_value = 0.0
        initial_allocation = baseline_state["initial_allocation"]

        for ticker, info in initial_allocation.items():
            # Get current price
            current_price = self._get_current_price(ticker, date, state)

            if current_price is None or current_price <= 0:
                # If unable to get price, use purchase price as fallback
                current_price = info["buy_price"]
                print(
                    f"⚠️ Unable to get price for {ticker} on {date}, using purchase price ${current_price:.2f}",
                )

            # Calculate position market value
            position_value = info["qty"] * current_price
            total_value += position_value

        return total_value

    def _update_baseline_curve(
        self,
        date: str,
        timestamp_ms: int,
        state: Dict,
    ):
        """
        Update Buy & Hold baseline curve

        Args:
            date: Trading date
            timestamp_ms: Timestamp (milliseconds)
            state: Internal state
        """
        baseline_state = state["baseline_state"]

        # If baseline just initialized and history is empty, add initial point first
        # Initial value uses 05:00:00 of the same day, not 05:00 of next trading day
        if (
            baseline_state["initialized"]
            and len(state["baseline_history"]) == 0
        ):
            date_obj = datetime.strptime(date, "%Y-%m-%d")
            # Set to 05:00:00 of the same day (Asia/Shanghai timezone)
            date_0500 = date_obj.replace(
                hour=5,
                minute=0,
                second=0,
                microsecond=0,
            )
            initial_timestamp_ms = int(date_0500.timestamp() * 1000)

            # Add initial cash as starting point (consistent with Portfolio)
            initial_point = {
                "t": initial_timestamp_ms,
                "v": round(self.initial_cash, 2),  # $100,000
            }
            state["baseline_history"].append(initial_point)
            print(
                f"📊 Buy & Hold initial point: ${self.initial_cash:,.2f} at {date} 05:00:00",
            )

        # Calculate current total value of Buy & Hold strategy
        baseline_value = self._calculate_buy_and_hold_value(date, state)

        # Use actual amount directly (no longer normalized to percentage)
        # normalized_value = (baseline_value / self.initial_cash) * 100

        # Add to baseline history
        baseline_point = {
            "t": timestamp_ms,
            "v": round(baseline_value, 2),  # Store actual amount
        }

        state["baseline_history"].append(baseline_point)

        # Calculate return percentage for log display
        return_pct = (
            (baseline_value - self.initial_cash) / self.initial_cash
        ) * 100
        print(
            f"📊 Buy & Hold baseline: ${baseline_value:,.2f} ({return_pct:+.2f}%)",
        )

    def _initialize_buy_and_hold_vw(
        self,
        date: str,
        available_tickers: list,
        state: Dict,
    ):
        """
        Initialize value-weighted Buy & Hold strategy

        Allocate initial funds according to each stock's market cap proportion

        Args:
            date: Trading date
            available_tickers: List of tradable stocks
            state: Internal state
        """
        from backend.tools.data_tools import get_market_cap

        baseline_vw_state = state["baseline_vw_state"]

        if baseline_vw_state["initialized"]:
            return  # Already initialized

        if not available_tickers:
            print(
                "⚠️ No tradable stocks, skipping value-weighted Buy & Hold initialization",
            )
            return

        # Get market cap of all stocks
        market_caps = {}
        for ticker in available_tickers:
            try:
                mcap = get_market_cap(ticker, date, api_key=None)
                if mcap and mcap > 0:
                    market_caps[ticker] = mcap
                else:
                    print(f"⚠️ {ticker} market cap data invalid, skipping")
            except Exception as e:
                print(f"⚠️ Failed to get market cap for {ticker}: {e}")

        if not market_caps:
            print(
                "⚠️ Unable to get market cap data for any stock, skipping value-weighted Buy & Hold initialization",
            )
            return

        # Calculate total market cap
        total_market_cap = sum(market_caps.values())

        # Allocate funds according to market cap proportion
        initial_allocation = {}
        total_invested = 0.0

        for ticker, mcap in market_caps.items():
            # Calculate funds allocated to this stock (by market cap proportion)
            weight = mcap / total_market_cap
            allocated_cash = self.initial_cash * weight

            # Buy using closing price
            price = self._get_price_from_csv(ticker, date, "close")

            if price is None or price <= 0:
                print(f"⚠️ {ticker} has no valid price on {date}, skipping")
                continue

            # Calculate purchasable quantity (round down)
            quantity = int(allocated_cash / price)

            if quantity > 0:
                initial_allocation[ticker] = {
                    "qty": quantity,
                    "buy_price": price,
                    "buy_date": date,
                    "weight": weight,  # Record market cap weight
                    "market_cap": mcap,
                }
                total_invested += quantity * price

        baseline_vw_state["initial_allocation"] = initial_allocation
        baseline_vw_state["initialized"] = True

        print(
            f"✅ Value-weighted Buy & Hold strategy initialized: {len(initial_allocation)} stocks, invested ${total_invested:,.2f}",
        )
        for ticker, info in initial_allocation.items():
            print(
                f"   {ticker}: {info['qty']} shares @ ${info['buy_price']:.2f} (weight: {info['weight']*100:.2f}%)",
            )

    def _calculate_buy_and_hold_vw_value(
        self,
        date: str,
        state: Dict,
    ) -> float:
        """
        Calculate current net value of value-weighted Buy & Hold strategy

        Args:
            date: Current date
            state: Internal state

        Returns:
            Total asset value of value-weighted Buy & Hold strategy
        """
        baseline_vw_state = state["baseline_vw_state"]

        if not baseline_vw_state["initialized"]:
            return (
                self.initial_cash
            )  # Not initialized yet, return initial cash

        total_value = 0.0
        initial_allocation = baseline_vw_state["initial_allocation"]

        for ticker, info in initial_allocation.items():
            # Get current price
            current_price = self._get_current_price(ticker, date, state)

            if current_price is None or current_price <= 0:
                # If unable to get price, use purchase price as fallback
                current_price = info["buy_price"]
                print(
                    f"⚠️ Unable to get price for {ticker} on {date}, using purchase price ${current_price:.2f}",
                )

            # Calculate position market value
            position_value = info["qty"] * current_price
            total_value += position_value

        return total_value

    def _update_baseline_vw_curve(
        self,
        date: str,
        timestamp_ms: int,
        state: Dict,
    ):
        """
        Update value-weighted Buy & Hold baseline curve

        Args:
            date: Trading date
            timestamp_ms: Timestamp (milliseconds)
            state: Internal state
        """
        baseline_vw_state = state["baseline_vw_state"]

        # If baseline_vw just initialized and history is empty, add initial point first
        # Initial value uses 05:00:00 of the same day, not 05:00 of next trading day
        if (
            baseline_vw_state["initialized"]
            and len(state["baseline_vw_history"]) == 0
        ):
            date_obj = datetime.strptime(date, "%Y-%m-%d")
            # Set to 05:00:00 of the same day (Asia/Shanghai timezone)
            date_0500 = date_obj.replace(
                hour=5,
                minute=0,
                second=0,
                microsecond=0,
            )
            initial_timestamp_ms = int(date_0500.timestamp() * 1000)

            # Add initial cash as starting point
            initial_point = {
                "t": initial_timestamp_ms,
                "v": round(self.initial_cash, 2),
            }
            state["baseline_vw_history"].append(initial_point)
            print(
                f"📊 Value-weighted Buy & Hold initial point: ${self.initial_cash:,.2f} at {date} 05:00:00",
            )

        # Calculate current total value of value-weighted Buy & Hold strategy
        baseline_vw_value = self._calculate_buy_and_hold_vw_value(date, state)

        # Add to baseline history
        baseline_vw_point = {
            "t": timestamp_ms,
            "v": round(baseline_vw_value, 2),
        }

        state["baseline_vw_history"].append(baseline_vw_point)

        # Calculate return percentage for log display
        return_pct = (
            (baseline_vw_value - self.initial_cash) / self.initial_cash
        ) * 100
        print(
            f"📊 Value-weighted Buy & Hold baseline: ${baseline_vw_value:,.2f} ({return_pct:+.2f}%)",
        )

    def _calculate_momentum_scores(
        self,
        date: str,
        available_tickers: list,
        lookback_days: int,
        state: Dict,
    ) -> Dict[str, float]:
        """
        Calculate momentum scores for all stocks (return over past N days)

        Args:
            date: Current date
            available_tickers: List of tradable stocks
            lookback_days: Lookback days
            state: Internal state

        Returns:
            ticker -> momentum_score (return)
        """
        momentum_scores = {}

        # Convert date to datetime
        current_date = datetime.strptime(date, "%Y-%m-%d")

        for ticker in available_tickers:
            # Get current price
            current_price = self._get_price_from_csv(ticker, date, "close")
            if current_price is None or current_price <= 0:
                continue

            # Try to get price from lookback_days days ago
            # Since there may be non-trading days, we need to search forward
            past_price = None
            for days_back in range(
                lookback_days,
                lookback_days + 10,
            ):  # Search up to 10 more days
                past_date = current_date - timedelta(days=days_back)
                past_date_str = past_date.strftime("%Y-%m-%d")
                past_price = self._get_price_from_csv(
                    ticker,
                    past_date_str,
                    "close",
                )
                if past_price is not None and past_price > 0:
                    break

            if past_price is None or past_price <= 0:
                # Unable to get historical price, skip
                continue

            # Calculate momentum score (return)
            momentum_score = (current_price - past_price) / past_price
            momentum_scores[ticker] = momentum_score

        return momentum_scores

    def _should_rebalance_momentum(self, date: str, state: Dict) -> bool:
        """
        Determine if momentum strategy needs rebalancing

        Args:
            date: Current date
            state: Internal state

        Returns:
            Whether rebalancing is needed
        """
        momentum_state = state["momentum_state"]

        # If not initialized yet, need to initialize
        if not momentum_state["initialized"]:
            return True

        last_rebalance = momentum_state.get("last_rebalance_date")
        if last_rebalance is None:
            return True

        # Calculate days since last rebalance
        current_date = datetime.strptime(date, "%Y-%m-%d")
        last_rebalance_date = datetime.strptime(last_rebalance, "%Y-%m-%d")
        days_since_rebalance = (current_date - last_rebalance_date).days

        rebalance_period = momentum_state.get("rebalance_period_days", 20)

        return days_since_rebalance >= rebalance_period

    def _rebalance_momentum_portfolio(
        self,
        date: str,
        available_tickers: list,
        state: Dict,
    ):
        """
        Rebalance momentum strategy portfolio

        Strategy logic:
        1. Calculate momentum scores for all stocks (return over past N days)
        2. Select top K stocks with strongest momentum
        3. Sell all current positions
        4. Buy newly selected stocks with equal weight

        Args:
            date: Trading date
            available_tickers: List of tradable stocks
            state: Internal state
        """
        momentum_state = state["momentum_state"]
        lookback_days = momentum_state.get("lookback_days", 20)
        top_n = momentum_state.get("top_n", 3)

        # 1. Calculate momentum scores
        momentum_scores = self._calculate_momentum_scores(
            date,
            available_tickers,
            lookback_days,
            state,
        )

        if not momentum_scores:
            print(
                f"⚠️ {date} Unable to calculate momentum scores, skipping rebalance",
            )
            return

        # 2. Select top N stocks with strongest momentum
        sorted_tickers = sorted(
            momentum_scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        top_tickers = [ticker for ticker, score in sorted_tickers[:top_n]]

        print(f"🔄 Momentum strategy rebalance ({date}):")
        print(f"   Momentum ranking:")
        for i, (ticker, score) in enumerate(sorted_tickers[:top_n], 1):
            print(f"   {i}. {ticker}: {score*100:+.2f}%")

        # 3. Sell all current positions, recover cash
        current_positions = momentum_state["positions"]
        for ticker, position in list(current_positions.items()):
            sell_price = self._get_price_from_csv(ticker, date, "close")
            if sell_price and sell_price > 0:
                sell_value = position["qty"] * sell_price
                momentum_state["cash"] += sell_value

        # Clear positions
        momentum_state["positions"] = {}

        # 4. Buy newly selected stocks with equal weight
        if top_tickers:
            cash_per_ticker = momentum_state["cash"] / len(top_tickers)
            total_invested = 0.0

            for ticker in top_tickers:
                buy_price = self._get_price_from_csv(ticker, date, "close")
                if buy_price is None or buy_price <= 0:
                    print(
                        f"⚠️ {ticker} has no valid price on {date}, skipping",
                    )
                    continue

                # Calculate purchasable quantity (round down)
                quantity = int(cash_per_ticker / buy_price)

                if quantity > 0:
                    cost = quantity * buy_price
                    momentum_state["positions"][ticker] = {
                        "qty": quantity,
                        "buy_price": buy_price,
                        "buy_date": date,
                    }
                    momentum_state["cash"] -= cost
                    total_invested += cost
                    print(
                        f"   Buy {ticker}: {quantity} shares @ ${buy_price:.2f}",
                    )

        # Update state
        momentum_state["initialized"] = True
        momentum_state["last_rebalance_date"] = date

        print(
            f"✅ Momentum strategy rebalance completed, remaining cash: ${momentum_state['cash']:,.2f}",
        )

    def _calculate_momentum_value(self, date: str, state: Dict) -> float:
        """
        Calculate current net value of momentum strategy

        Args:
            date: Current date
            state: Internal state

        Returns:
            Total asset value of momentum strategy (positions + cash)
        """
        momentum_state = state["momentum_state"]

        if not momentum_state["initialized"]:
            return self.initial_cash

        # Position market value
        positions_value = 0.0
        for ticker, position in momentum_state["positions"].items():
            current_price = self._get_current_price(ticker, date, state)
            if current_price is None or current_price <= 0:
                current_price = position["buy_price"]
            positions_value += position["qty"] * current_price

        # Total assets = position market value + cash
        total_value = positions_value + momentum_state["cash"]

        return total_value

    def _update_momentum_curve(
        self,
        date: str,
        timestamp_ms: int,
        available_tickers: list,
        state: Dict,
    ):
        """
        Update momentum strategy curve

        Args:
            date: Trading date
            timestamp_ms: Timestamp (milliseconds)
            available_tickers: List of tradable stocks
            state: Internal state
        """
        momentum_state = state["momentum_state"]

        # Determine if rebalancing is needed
        if self._should_rebalance_momentum(date, state):
            self._rebalance_momentum_portfolio(date, available_tickers, state)

        # If momentum strategy just initialized and history is empty, add initial point first
        # Initial value uses 05:00:00 of the same day, not 05:00 of next trading day
        if (
            momentum_state["initialized"]
            and len(state["momentum_history"]) == 0
        ):
            date_obj = datetime.strptime(date, "%Y-%m-%d")
            # Set to 05:00:00 of the same day (Asia/Shanghai timezone)
            date_0500 = date_obj.replace(
                hour=5,
                minute=0,
                second=0,
                microsecond=0,
            )
            initial_timestamp_ms = int(date_0500.timestamp() * 1000)

            initial_point = {
                "t": initial_timestamp_ms,
                "v": round(self.initial_cash, 2),
            }
            state["momentum_history"].append(initial_point)
            print(
                f"📊 Momentum strategy initial point: ${self.initial_cash:,.2f} at {date} 05:00:00",
            )

        # Calculate current total value of momentum strategy
        momentum_value = self._calculate_momentum_value(date, state)

        # Add to history
        momentum_point = {
            "t": timestamp_ms,
            "v": round(momentum_value, 2),
        }
        state["momentum_history"].append(momentum_point)

        # Calculate return percentage for log display
        return_pct = (
            (momentum_value - self.initial_cash) / self.initial_cash
        ) * 100
        print(
            f"📊 Momentum strategy: ${momentum_value:,.2f} ({return_pct:+.2f}%)",
        )

    def _generate_summary(self, state: Dict):
        """Generate account overview data (using actual prices)"""
        portfolio_state = state["portfolio_state"]
        last_date = state.get("last_update_date")
        all_trades = state.get("all_trades", [])
        margin_used = state["portfolio_state"].get("margin_used", 0.0)
        # Calculate current balance: cash + position market value (using latest prices)
        cash = portfolio_state["cash"]
        positions_value = 0.0
        ticker_weights = {}  # Record weight of each ticker

        for ticker, pos in portfolio_state["positions"].items():
            # Use latest actual price
            current_price = (
                self._get_current_price(ticker, last_date, state)
                if last_date
                else self.DEFAULT_BASE_PRICE
            )
            position_value = pos["qty"] * current_price
            positions_value += position_value

        balance = cash + positions_value + margin_used
        total_asset_value = balance

        # Calculate weight of each ticker
        for ticker, pos in portfolio_state["positions"].items():
            current_price = (
                self._get_current_price(ticker, last_date, state)
                if last_date
                else self.DEFAULT_BASE_PRICE
            )
            position_value = pos["qty"] * current_price
            weight = (
                (position_value / total_asset_value)
                if total_asset_value > 0
                else 0
            )
            ticker_weights[ticker] = round(weight, 4)

        # Calculate total return
        total_return = (
            (balance - self.initial_cash) / self.initial_cash
        ) * 100

        summary = {
            "totalAssetValue": round(total_asset_value, 2),
            "totalReturn": round(total_return, 2),
            "cashPosition": round(cash, 2),
            "tickerWeights": ticker_weights,
            "totalTrades": len(all_trades),  # Fix: use length of all_trades
            # Keep old fields for compatibility
            "pnlPct": round(total_return, 2),
            "balance": round(balance, 2),
            "equity": state.get("equity_history", []),
            "baseline": state.get("baseline_history", []),
            "baseline_vw": state.get(
                "baseline_vw_history",
                [],
            ),  # Value-weighted baseline
            "momentum": state.get(
                "momentum_history",
                [],
            ),  # Add momentum strategy data
        }

        self._save_json(self.summary_file, summary)

    def _generate_holdings(self, state: Dict):
        """Generate holdings information"""
        portfolio_state = state["portfolio_state"]
        positions = portfolio_state["positions"]
        cash = portfolio_state["cash"]
        last_date = state.get("last_update_date")

        print(f"\n🔍 Generating Holdings data (date: {last_date}):")

        # Calculate total value for weight calculation (using actual prices)
        # Add margin_used back because it's frozen cash
        margin_used = portfolio_state.get("margin_used", 0.0)
        total_value = cash + margin_used
        for ticker, pos in positions.items():
            current_price = (
                self._get_current_price(ticker, last_date, state)
                if last_date
                else self.DEFAULT_BASE_PRICE
            )
            total_value += pos["qty"] * current_price

        holdings = []
        # Add stock positions
        for ticker, pos in positions.items():
            qty = pos["qty"]

            # Use actual current price
            current_price = (
                self._get_current_price(ticker, last_date, state)
                if last_date
                else self.DEFAULT_BASE_PRICE
            )

            # Calculate current market value
            market_value = qty * current_price

            # Calculate weight
            weight = abs(market_value) / total_value if total_value > 0 else 0

            print(
                f"   {ticker}: qty={qty}, current_price=${current_price:.2f}, market_value=${market_value:.2f}, weight={weight:.2%}",
            )

            holdings.append(
                {
                    "ticker": ticker,
                    "quantity": qty,
                    "currentPrice": round(current_price, 2),
                    "marketValue": round(market_value, 2),
                    "weight": round(weight, 4),
                },
            )
        # Add cash as a holding item
        cash_weight = cash / total_value if total_value > 0 else 0
        holdings.append(
            {
                "ticker": "CASH",
                "quantity": 1,
                "currentPrice": round(cash, 2),
                "marketValue": round(cash, 2),
                "weight": round(cash_weight, 4),
            },
        )

        # Sort by weight
        holdings.sort(key=lambda x: abs(x["weight"]), reverse=True)

        self._save_json(self.holdings_file, holdings)

    def _generate_stats(self, state: Dict):
        """Generate statistics (Portfolio Manager performance + Overview data)"""
        pm_perf = state.get("agent_performance", {}).get(
            "portfolio_manager",
            {},
        )
        portfolio_state = state["portfolio_state"]
        margin_used = portfolio_state.get("margin_used", 0.0)
        last_date = state.get("last_update_date")
        all_trades = state.get("all_trades", [])

        bull_count = pm_perf.get("bull_count", 0)
        bull_win = pm_perf.get("bull_win", 0)
        bear_count = pm_perf.get("bear_count", 0)
        bear_win = pm_perf.get("bear_win", 0)

        total_count = bull_count + bear_count
        total_win = bull_win + bear_win

        win_rate = total_win / total_count if total_count > 0 else 0

        # Calculate Overview data (same as in summary)
        cash = portfolio_state["cash"]
        positions_value = 0.0
        ticker_weights = {}

        for ticker, pos in portfolio_state["positions"].items():
            current_price = (
                self._get_current_price(ticker, last_date, state)
                if last_date
                else self.DEFAULT_BASE_PRICE
            )
            position_value = pos["qty"] * current_price
            positions_value += position_value

        total_asset_value = cash + positions_value + margin_used

        # Calculate weight of each ticker
        for ticker, pos in portfolio_state["positions"].items():
            current_price = (
                self._get_current_price(ticker, last_date, state)
                if last_date
                else self.DEFAULT_BASE_PRICE
            )
            position_value = pos["qty"] * current_price
            weight = (
                (position_value / total_asset_value)
                if total_asset_value > 0
                else 0
            )
            ticker_weights[ticker] = round(weight, 4)

        total_return = (
            (total_asset_value - self.initial_cash) / self.initial_cash
        ) * 100

        stats = {
            # Overview data
            "totalAssetValue": round(total_asset_value, 2),
            "totalReturn": round(total_return, 2),
            "cashPosition": round(cash, 2),
            "tickerWeights": ticker_weights,
            "totalTrades": len(all_trades),
            # Performance data
            "winRate": round(win_rate, 2),
            "bullBear": {
                "bull": {
                    "n": bull_count,
                    "win": bull_win,
                },
                "bear": {
                    "n": bear_count,
                    "win": bear_win,
                },
            },
        }

        self._save_json(self.stats_file, stats)

    def _generate_trades(self, state: Dict):
        """Generate trade records"""
        all_trades = state.get("all_trades", [])

        # Sort by time descending (newest first)
        sorted_trades = sorted(all_trades, key=lambda x: x["ts"], reverse=True)

        # Limit quantity (e.g., last 100 trades) and format output
        trades = []
        for trade in sorted_trades[:100]:
            # Create new trade object, remove pnl field
            formatted_trade = {
                "id": trade.get("id"),
                "timestamp": trade.get(
                    "ts",
                ),  # Keep millisecond timestamp, frontend will format
                "side": trade.get("side"),
                "ticker": trade.get("ticker"),
                "qty": trade.get("qty"),
                "price": trade.get("price"),
            }
            trades.append(formatted_trade)

        self._save_json(self.trades_file, trades)

    def _get_agent_model_config(self, state: Dict, agent_id: str) -> tuple:
        """
        Get model configuration for a specific agent
        Always reads from environment variables to ensure latest configuration

        Args:
            state: State dictionary (not used for model config, kept for compatibility)
            agent_id: Agent ID

        Returns:
            Tuple of (model_name, model_provider)
        """
        # Always load fresh from environment variables
        from backend.config.agent_model_config import AgentModelRequest

        try:
            agent_model_request = (
                AgentModelRequest()
            )  # This loads from env vars
            (
                model_name,
                model_provider,
            ) = agent_model_request.get_agent_model_config(agent_id)

            if model_name and model_provider:
                # Convert ModelProvider enum to string if needed
                if hasattr(model_provider, "value"):
                    model_provider = model_provider.value
                return model_name, str(model_provider)
        except Exception as e:
            print(
                f"⚠️ Failed to load agent model configuration for {agent_id}: {e}",
            )

        # Fall back to default if environment variable loading fails
        return "gpt-4o-mini", "OPENAI"

    def _generate_leaderboard(self, state: Dict):
        """
        Generate AI Agent leaderboard
        Model configuration is always read fresh from environment variables
        """
        agent_performance = state.get("agent_performance", {})

        leaderboard = []
        ranking_entries = []
        team_entries = []

        for agent_id, perf in agent_performance.items():
            # Calculate win rate
            bull_count = perf.get("bull_count", 0)
            bull_win = perf.get("bull_win", 0)
            bull_unknown = perf.get("bull_unknown", 0)
            bear_count = perf.get("bear_count", 0)
            bear_win = perf.get("bear_win", 0)
            bear_unknown = perf.get("bear_unknown", 0)

            evaluated_bull = max(bull_count - bull_unknown, 0)
            evaluated_bear = max(bear_count - bear_unknown, 0)
            total_count = bull_count + bear_count
            total_win = bull_win + bear_win
            evaluated_total = evaluated_bull + evaluated_bear
            win_rate = (
                (total_win / evaluated_total) if evaluated_total > 0 else None
            )

            # Get agent configuration
            agent_config = self.AGENT_CONFIG.get(
                agent_id,
                {
                    "name": agent_id,
                    "role": agent_id,
                    "avatar": "default",
                },
            )

            # Get model configuration for this agent
            model_name, model_provider = self._get_agent_model_config(
                state,
                agent_id,
            )

            entry = {
                "agentId": agent_id,
                "name": agent_config["name"],
                "role": agent_config["role"],
                "avatar": agent_config["avatar"],
                "rank": 0,  # Fill later
                "winRate": (
                    round(win_rate, 4) if win_rate is not None else None
                ),
                "bull": {
                    "n": bull_count,
                    "win": bull_win,
                    "unknown": bull_unknown,
                },
                "bear": {
                    "n": bear_count,
                    "win": bear_win,
                    "unknown": bear_unknown,
                },
                "logs": perf.get("logs", []),  # Last 10 logs
                "signals": perf.get(
                    "signals",
                    [],
                ),  # Complete signal history (includes dates)
                "modelName": model_name,  # Agent's model name
                "modelProvider": model_provider,  # Agent's model provider
            }

            if agent_id in self.TEAM_ROLES:
                team_entries.append(entry)
            else:
                ranking_entries.append(entry)

        # Sort by win rate (only analysts participate in ranking)
        ranking_entries.sort(
            key=lambda x: (
                0 if x["winRate"] is not None else 1,  # Valid win rate first
                -(
                    x["winRate"] if x["winRate"] is not None else 0
                ),  # Win rate descending
            ),
        )

        # Fill ranks
        for i, agent in enumerate(ranking_entries, 1):
            agent["rank"] = i

        # Team roles do not participate in ranking
        for agent in team_entries:
            agent["rank"] = None

        leaderboard = ranking_entries + team_entries

        self._save_json(self.leaderboard_file, leaderboard)

    def _generate_initial_leaderboard(self, state: Dict):
        """
        Generate initial leaderboard with agent model information only
        This allows frontend to display model cards even before performance data is available

        Args:
            state: State dictionary (must contain metadata.request for agent model config)
        """
        leaderboard = []
        ranking_entries = []
        team_entries = []

        # Get all agent IDs from config
        all_agent_ids = list(self.AGENT_CONFIG.keys())

        for agent_id in all_agent_ids:
            # Get agent configuration
            agent_config = self.AGENT_CONFIG.get(
                agent_id,
                {
                    "name": agent_id,
                    "role": agent_id,
                    "avatar": "default",
                },
            )

            # Get model configuration for this agent
            model_name, model_provider = self._get_agent_model_config(
                state,
                agent_id,
            )

            # Create entry with model info but no performance data
            entry = {
                "agentId": agent_id,
                "name": agent_config["name"],
                "role": agent_config["role"],
                "avatar": agent_config["avatar"],
                "rank": None,  # No rank initially
                "winRate": None,  # No win rate initially
                "bull": {
                    "n": 0,
                    "win": 0,
                    "unknown": 0,
                },
                "bear": {
                    "n": 0,
                    "win": 0,
                    "unknown": 0,
                },
                "logs": [],
                "signals": [],
                # Agent's model name (available from env/config)
                "modelName": model_name,
                # Agent's model provider (available from env/config)
                "modelProvider": model_provider,
            }

            if agent_id in self.TEAM_ROLES:
                team_entries.append(entry)
            else:
                ranking_entries.append(entry)

        # No sorting needed initially (no win rates)
        leaderboard = ranking_entries + team_entries

        self._save_json(self.leaderboard_file, leaderboard)
        return leaderboard

    def update_leaderboard_model_info(self):
        """
        Update model information in existing leaderboard
        This allows updating model config without losing performance data
        Called at server startup to ensure latest model info is displayed
        """
        # Load existing leaderboard if it exists
        existing_leaderboard = self._load_json(self.leaderboard_file, [])

        if not existing_leaderboard:
            # If no leaderboard exists, create initial one
            print(
                "📊 No existing leaderboard found, creating initial leaderboard with model info...",
            )
            self._generate_initial_leaderboard({})
            return

        # Update model info for each agent while preserving performance data
        print("📊 Updating model information in existing leaderboard...")
        updated_count = 0

        for entry in existing_leaderboard:
            agent_id = entry.get("agentId")
            if agent_id:
                # Get latest model configuration from environment variables
                model_name, model_provider = self._get_agent_model_config(
                    {},
                    agent_id,
                )

                # Update model info (preserve all other data)
                old_model = entry.get("modelName")
                old_provider = entry.get("modelProvider")

                entry["modelName"] = model_name
                entry["modelProvider"] = model_provider

                if old_model != model_name or old_provider != model_provider:
                    updated_count += 1
                    print(
                        f"  ✅ Updated {agent_id}: {old_model or 'N/A'} → {model_name}",
                    )

        # Save updated leaderboard
        self._save_json(self.leaderboard_file, existing_leaderboard)
        print(
            f"✅ Model information updated for {updated_count} agents in leaderboard",
        )

    def initialize_empty_dashboard(self, state: Dict = None):
        """
        Initialize empty dashboard data files

        Args:
            state: Optional state dictionary (if provided, will generate initial leaderboard with model info)
        """
        # Summary
        self._save_json(
            self.summary_file,
            {
                "pnlPct": 0.0,
                "balance": self.initial_cash,
                "equity": [],
            },
        )

        # Holdings
        self._save_json(self.holdings_file, [])

        # Stats
        self._save_json(
            self.stats_file,
            {
                "totalAssetValue": self.initial_cash,
                "totalReturn": 0.0,
                "cashPosition": self.initial_cash,
                "tickerWeights": {},
                "totalTrades": 0,
                "winRate": 0.0,
                "bullBear": {
                    "bull": {"n": 0, "win": 0},
                    "bear": {"n": 0, "win": 0},
                },
            },
        )

        # Trades
        self._save_json(self.trades_file, [])

        # Leaderboard - generate initial leaderboard with model info if state is provided
        if state:
            self._generate_initial_leaderboard(state)
        else:
            # Fallback: create basic leaderboard without model info
            leaderboard = []
            for agent_id, config in self.AGENT_CONFIG.items():
                is_team_role = agent_id in self.TEAM_ROLES
                leaderboard.append(
                    {
                        "agentId": agent_id,
                        "name": config["name"],
                        "role": config["role"],
                        "avatar": config["avatar"],
                        "rank": None if is_team_role else 0,
                        "winRate": None,
                        "bull": {"n": 0, "win": 0, "unknown": 0},
                        "bear": {"n": 0, "win": 0, "unknown": 0},
                        "logs": [],
                        "signals": [],
                        "modelName": None,
                        "modelProvider": None,
                    },
                )
            self._save_json(self.leaderboard_file, leaderboard)

        print(f"✅ Team dashboard initialized: {self.dashboard_dir}")
