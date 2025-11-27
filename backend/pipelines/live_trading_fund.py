#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Live Trading Fund - Sandbox time simulation system
Simulates real trading day time flow: pre-market analysis + post-market review

Time point design:
- Trading days: Pre-market + Post-market
- Non-trading days: Post-market only

Usage:
# Run complete simulation for specified date
python live_trading_fund.py --date 2025-01-15 --tickers AAPL,MSFT --config_name my_config

# Use environment variable configuration
python live_trading_fund.py --date 2025-01-15 --config_name my_config

# Force run
python live_trading_fund.py --date 2025-01-15 --force-run --config_name my_config
"""
# flake8: noqa: E501
# pylint: disable=C0301
import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from backend.config.constants import ANALYST_TYPES
from backend.config.env_config import LiveThinkingFundConfig
from backend.dashboard.team_dashboard import TeamDashboardGenerator
from backend.memory import MemoryReflectionSystem, get_memory
from backend.pipelines.investment_engine import InvestmentEngine
from backend.pipelines.multi_day_strategy import MultiDayStrategy
from backend.servers.streamer import ConsoleStreamer


# Set up path before importing backend modules
BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


load_dotenv()
current_dir = os.path.dirname(os.path.abspath(__file__))

# Import refactored modules


class LiveTradingFund:
    """Live Trading Thinking Fund - Sandbox time simulation system"""

    def __init__(
        self,
        config_name: str,
        streamer=None,
        mode: str = "portfolio",
        initial_cash: float = 100000.0,
        margin_requirement: float = 0.0,
        pause_before_trade: bool = False,
    ):
        """
        Initialize thinking fund system

        Args:
            config_name: Configuration name
            streamer: Event streamer for UI updates
            mode: Running mode ("signal" or "portfolio")
            initial_cash: Initial cash for portfolio mode
            margin_requirement: Margin requirement for portfolio mode
            pause_before_trade: Whether to pause before trade execution
        """
        from backend.config.path_config import get_directory_config

        self.config_name = config_name
        self.base_dir = Path(get_directory_config(config_name))
        self.sandbox_dir = self.base_dir / "sandbox_logs"
        self.sandbox_dir.mkdir(parents=True, exist_ok=True)

        # Optional unified event dispatcher: if None, only local print
        if streamer:
            self.streamer = streamer
        else:
            self.streamer = ConsoleStreamer()

        # Initialize investment engine
        engine = InvestmentEngine(
            streamer=self.streamer,
            pause_before_trade=pause_before_trade,
            config_name=config_name,
            sandbox_dir=str(self.sandbox_dir),
        )

        # Initialize multi-day strategy manager
        self.strategy = MultiDayStrategy(
            engine=engine,
            config_name=config_name,
            mode=mode,
            initial_cash=initial_cash,
            margin_requirement=margin_requirement,
            prefetch_data=True,
        )

        # Initialize memory management system
        try:
            self.memory_reflection = MemoryReflectionSystem(
                base_dir=config_name,
                streamer=self.streamer,
            )
            print("Memory reflection system enabled")
        except Exception as e:
            self.memory_reflection = None
            print(f"Memory reflection system not enabled: {e}")

        # Time point definitions
        self.PRE_MARKET = "pre_market"  # Pre-market
        self.POST_MARKET = "post_market"  # Post-market

        # Portfolio mode parameters
        self.mode = mode
        self.initial_cash = initial_cash
        self.margin_requirement = margin_requirement

        # Initialize team dashboard generator
        dashboard_dir = self.sandbox_dir / "team_dashboard"
        self.dashboard_generator = TeamDashboardGenerator(
            dashboard_dir=dashboard_dir,
            initial_cash=initial_cash,
        )
        # Initialize empty dashboard (if not exists)
        if not (dashboard_dir / "summary.json").exists():
            # Create a minimal state with agent model configuration from env
            from backend.config.agent_model_config import AgentModelRequest

            agent_model_request = (
                AgentModelRequest()
            )  # This loads from env vars
            initial_state = {
                "metadata": {
                    "request": agent_model_request,
                },
            }
            self.dashboard_generator.initialize_empty_dashboard(
                state=initial_state,
            )

    def is_trading_day(self, date: str) -> bool:
        """Check if it's a trading day"""
        return self.strategy.is_trading_day(date)

    def validate_date_format(self, date_str: str) -> bool:
        """Validate date format"""
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            return True
        except ValueError:
            return False

    def should_run_sandbox_analysis(
        self,
        date: str,
        time_point: str,
    ) -> bool:
        """Determine whether to run sandbox analysis (independent of live_system check logic)"""

        # Check if sandbox log has successful record
        existing_data = self._load_sandbox_log(date, time_point)
        if existing_data and existing_data.get("status") == "success":
            return False

        return True

    def run_pre_market_analysis(
        self,
        date: str,
        tickers: List[str],
        max_comm_cycles: int = 2,
        enable_communications: bool = False,
        enable_notifications: bool = False,
        skip_real_returns: bool = False,
        is_live_mode: bool = False,
    ) -> Dict[str, Any]:
        """Run pre-market analysis

        Args:
            skip_real_returns: If True, do not calculate real_returns (for live mode pre-market analysis)
            is_live_mode: Whether running in live mode (affects risk manager price selection)
        """
        self.streamer.print(
            "system",
            f"===== Pre-Market Analysis ({date}) =====\n"
            f"Time point: {self.PRE_MARKET}\n"
            f"Analysis targets: {', '.join(tickers)}",
        )

        # Get analyst performance stats
        analyst_stats = self._load_analyst_stats()

        # Run single day analysis
        result = self.strategy.run_single_day(
            tickers=tickers,
            date=date,
            enable_communications=enable_communications,
            enable_notifications=enable_notifications,
            max_comm_cycles=max_comm_cycles,
            analyst_stats=analyst_stats,
            is_live_mode=is_live_mode,
        )

        # Build live environment
        live_env = self._build_live_environment(
            result,
            tickers,
            date,
            skip_real_returns,
        )

        # Display results
        self._display_results(live_env, tickers, skip_real_returns)

        # Log sandbox activity
        self._log_sandbox_activity(
            date,
            self.PRE_MARKET,
            {
                "status": "success",
                "tickers": tickers,
                "timestamp": datetime.now().isoformat(),
                "details": result,
            },
        )

        # Update dashboard (only in backtest mode)
        if not skip_real_returns:
            self._update_dashboard(date, live_env, result)

        return {
            "status": "success",
            "date": date,
            "live_env": live_env,
        }

    def _load_analyst_stats(self) -> Optional[Dict[str, Any]]:
        """Load analyst performance statistics from dashboard"""
        if not self.dashboard_generator:
            return None

        dashboard_state = self.dashboard_generator.load_internal_state()
        agent_performance = dashboard_state.get("agent_performance", {})

        analyst_stats = {}
        for agent_id, perf in agent_performance.items():
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

            analyst_stats[agent_id] = {
                "win_rate": win_rate,
                "total_predictions": total_count,
                "correct_predictions": total_win,
                "bull": {
                    "count": bull_count,
                    "win": bull_win,
                    "unknown": bull_unknown,
                },
                "bear": {
                    "count": bear_count,
                    "win": bear_win,
                    "unknown": bear_unknown,
                },
            }

        print(
            f"✓ Loaded analyst performance stats for {len(analyst_stats)} analysts",
        )
        return analyst_stats

    def _build_live_environment(
        self,
        result: Dict[str, Any],
        tickers: List[str],
        date: str,
        skip_real_returns: bool,
    ) -> Dict[str, Any]:
        """Build live environment from analysis result"""
        ana_signals_dict: Dict[str, Dict[str, Any]] = defaultdict(dict)
        real_returns_dict: Dict[str, float] = defaultdict(float)
        daily_returns_dict: Dict[str, float] = defaultdict(float)

        live_env: Dict[str, Any] = {
            "pm_signals": {},
            "ana_signals": ana_signals_dict,
            "real_returns": real_returns_dict,
            "daily_returns": daily_returns_dict,
            "state": result.get("state"),
            "pre_portfolio_state": result.get("pre_portfolio_state"),
        }

        # Extract PM signals
        pm_results = result.get("portfolio_management_results", {})
        final_decisions = pm_results.get("final_decisions", {})
        live_env["pm_signals"] = final_decisions

        # Extract analyst signals
        self._extract_analyst_signals(result, tickers, live_env)

        # Calculate returns
        self._calculate_returns(
            tickers,
            final_decisions,
            date,
            skip_real_returns,
            live_env,
        )

        # Add portfolio info for portfolio mode
        if self.mode == "portfolio":
            self._add_portfolio_info(result, pm_results, live_env)

        return live_env

    def _extract_analyst_signals(
        self,
        result: Dict[str, Any],
        tickers: List[str],
        live_env: Dict[str, Any],
    ) -> None:
        """Extract analyst signals from result"""
        print("[system]", "===== Analyst Signal Details =====")
        analyst_results = result.get("final_analyst_results", {})

        for agent_id, _ in ANALYST_TYPES.items():
            if agent_id not in analyst_results:
                continue

            analyst_result = analyst_results[agent_id].get(
                "analysis_result",
                {},
            )
            signals = []

            # Format: {ticker_signals: [{ticker, signal, confidence, ...}]}
            if "ticker_signals" in analyst_result:
                for item in analyst_result["ticker_signals"]:
                    ticker = item["ticker"]
                    live_env["ana_signals"][agent_id][ticker] = item
                    signals.append(
                        f"{ticker}: {item['signal']} (confidence:{item.get('confidence', 'N/A')}%)",
                    )
            else:
                # Fallback format: {ticker: {signal, confidence, ...}}
                for ticker in tickers:
                    if (
                        ticker in analyst_result
                        and "signal" in analyst_result[ticker]
                    ):
                        live_env["ana_signals"][agent_id][
                            ticker
                        ] = analyst_result[ticker]
                        confidence = analyst_result[ticker].get(
                            "confidence",
                            "N/A",
                        )
                        signals.append(
                            f"{ticker}: {analyst_result[ticker]['signal']} (confidence:{confidence}%)",
                        )

            if signals:
                self.streamer.print(
                    "agent",
                    "\n".join(signals),
                    role_key=agent_id,
                )

    def _calculate_returns(
        self,
        tickers: List[str],
        final_decisions: Dict[str, Any],
        date: str,
        skip_real_returns: bool,
        live_env: Dict[str, Any],
    ) -> None:
        """Calculate daily returns for each ticker"""
        for ticker in tickers:
            if ticker not in final_decisions:
                continue

            if skip_real_returns:
                live_env["real_returns"][ticker] = None
                live_env["daily_returns"][ticker] = None
            else:
                action = final_decisions[ticker].get("action", "hold")
                (
                    daily_return,
                    real_return,
                    _close_price,
                ) = self.strategy.calculate_stock_daily_return_from_signal(
                    ticker,
                    date,
                    action,
                )
                live_env["real_returns"][ticker] = real_return
                live_env["daily_returns"][ticker] = daily_return

        if not skip_real_returns:
            print("[system]", f"{date} Sandbox analysis completed")

    def _add_portfolio_info(
        self,
        result: Dict[str, Any],
        pm_results: Dict[str, Any],
        live_env: Dict[str, Any],
    ) -> None:
        """Add portfolio information to live environment"""
        live_env["portfolio_summary"] = pm_results.get("portfolio_summary", {})
        live_env["updated_portfolio"] = result.get("updated_portfolio", {})

        # Get executed_trades from execution_report
        execution_report = pm_results.get(
            "final_execution_report",
        ) or pm_results.get("execution_report")

        if execution_report is not None:
            live_env["executed_trades"] = execution_report.get(
                "executed_trades",
                [],
            )
            live_env["failed_trades"] = execution_report.get(
                "failed_trades",
                [],
            )
        else:
            # Live mode pre-market: no trades executed yet
            live_env["executed_trades"] = []
            live_env["failed_trades"] = []

    def _display_results(
        self,
        live_env: Dict[str, Any],
        tickers: List[str],
        skip_real_returns: bool,
    ) -> None:
        """Display stock performance results"""
        final_decisions = live_env["pm_signals"]

        for ticker in tickers:
            if ticker not in final_decisions:
                continue

            signal_info = final_decisions[ticker]

            if skip_real_returns:
                self._display_signal_without_return(signal_info, ticker)
            else:
                self._display_signal_with_return(
                    signal_info,
                    ticker,
                    live_env["real_returns"],
                )

    def _display_signal_without_return(
        self,
        signal_info: Dict[str, Any],
        ticker: str,
    ) -> None:
        """Display signal without return (live mode)"""
        signal = signal_info.get("signal", "N/A")
        action = signal_info.get("action", "N/A")
        confidence = signal_info.get("confidence", 0)
        reasoning = signal_info.get("reasoning", "")

        if self.mode == "signal":
            self.streamer.print(
                "agent",
                f"{ticker}: Final signal {signal}(confidence {confidence}%) \n{reasoning}",
                role_key="portfolio_manager",
            )
        elif self.mode == "portfolio":
            quantity = signal_info.get("quantity", 0)
            shares_text = (
                "changed 0 shares"
                if action == "hold"
                else f"{quantity} shares"
            )
            self.streamer.print(
                "agent",
                f"{ticker}: Final signal {action}({shares_text}, confidence {confidence}%) \n{reasoning}",
                role_key="portfolio_manager",
            )

    def _display_signal_with_return(
        self,
        signal_info: Dict[str, Any],
        ticker: str,
        real_returns: Dict[str, float],
    ) -> None:
        """Display signal with return (backtest mode)"""
        signal = signal_info.get("signal", "N/A")
        action = signal_info.get("action", "N/A")
        confidence = signal_info.get("confidence", 0)
        reasoning = signal_info.get("reasoning", "")
        real_ret = real_returns.get(ticker, 0) * 100

        if self.mode == "signal":
            self.streamer.print(
                "agent",
                f"{ticker}: Final signal {signal}(confidence {confidence}%, stock real daily return {real_ret:.2f}%) \n{reasoning}",
                role_key="portfolio_manager",
            )
        elif self.mode == "portfolio":
            quantity = signal_info.get("quantity", 0)
            shares_text = (
                "changed 0 shares"
                if action == "hold"
                else f"{quantity} shares"
            )
            self.streamer.print(
                "agent",
                f"{ticker}: Final signal {action}({shares_text}, confidence {confidence}%, stock real daily return {real_ret:.2f}%) \n{reasoning}",
                role_key="portfolio_manager",
            )

    def _update_dashboard(
        self,
        date: str,
        live_env: Dict[str, Any],
        result: Dict[str, Any],
    ) -> None:
        """Update team dashboard with analysis results"""
        try:
            dashboard_update_stats = (
                self.dashboard_generator.update_from_day_result(
                    date=date,
                    pre_market_result={
                        "pre_market": {
                            "live_env": live_env,
                            "raw_results": result,
                        },
                    },
                    mode=self.mode,
                )
            )
            self.streamer.print(
                "system",
                f"Team dashboard updated: {dashboard_update_stats.get('trades_added', 0)} trades added, "
                f"{dashboard_update_stats.get('agents_updated', 0)} agents updated",
            )
        except Exception as e:
            self.streamer.print(
                "system",
                f"⚠️ Dashboard update failed: {e}",
            )
            import traceback

            print(f"Dashboard update error for {date}: {e}")
            traceback.print_exc()

    def run_post_market_review(
        self,
        date: str,
        tickers: List[str],
        live_env: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Run post-market review"""
        self.streamer.print(
            "system",
            f"===== Post-Market Review ({date}) =====\n"
            f"Time point: {self.POST_MARKET}\n"
            f"Review targets: {', '.join(tickers)}",
        )

        if live_env is not None:
            # Post-market review logic
            result = self._perform_post_market_review(date, tickers, live_env)

            # Record to sandbox log
            self._log_sandbox_activity(date, self.POST_MARKET, result)

            return result
        else:
            return {"status": "skipped", "reason": "Not trading day"}

    def _perform_post_market_review(
        self,
        date: str,
        tickers: List[str],
        live_env: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute post-market review analysis"""

        pm_signals = live_env["pm_signals"]
        ana_signals = live_env["ana_signals"]
        real_returns = live_env["real_returns"]
        daily_returns = live_env["daily_returns"]

        # Build and display review content
        review_content = self._build_review_content(
            tickers,
            pm_signals,
            ana_signals,
            real_returns,
            daily_returns,
            live_env,
        )
        self.streamer.print(
            "agent",
            review_content,
            role_key="portfolio_manager",
        )

        # Execute review based on mode
        review_mode = os.getenv(
            "MEMORY_REVIEW_MODE",
            "individual_review",
        ).lower()
        state = live_env.get("state")

        if review_mode == "individual_review":
            return self._run_individual_review_mode(
                date,
                tickers,
                pm_signals,
                ana_signals,
                daily_returns,
                real_returns,
                live_env,
                state,
            )
        else:
            return self._run_central_review_mode(
                date,
                tickers,
                pm_signals,
                ana_signals,
                daily_returns,
                real_returns,
                live_env,
                state,
            )

    def _build_review_content(
        self,
        tickers: List[str],
        pm_signals: Dict[str, Any],
        ana_signals: Dict[str, Any],
        real_returns: Dict[str, float],
        daily_returns: Dict[str, float],
        live_env: Dict[str, Any],
    ) -> str:
        """Build complete review content"""
        pm_review = self._build_pm_review(tickers, pm_signals)
        returns_review = self._build_returns_review(
            tickers,
            pm_signals,
            real_returns,
            daily_returns,
            live_env,
        )
        analyst_review = self._build_analyst_review(tickers, ana_signals)

        return "\n".join(
            [
                "Reviewing based on pre-market analysis...",
                pm_review,
                returns_review,
                analyst_review,
            ],
        )

    def _build_pm_review(
        self,
        tickers: List[str],
        pm_signals: Dict[str, Any],
    ) -> str:
        """Build Portfolio Manager signal review"""
        lines = ["Portfolio Manager signal review:"]

        if self.mode == "portfolio":
            lines.extend(
                self._build_pm_review_portfolio_mode(tickers, pm_signals),
            )
        else:
            lines.extend(
                self._build_pm_review_signal_mode(tickers, pm_signals),
            )

        return "\n".join(lines)

    def _build_pm_review_portfolio_mode(
        self,
        tickers: List[str],
        pm_signals: Dict[str, Any],
    ) -> List[str]:
        """Build PM review for portfolio mode"""
        lines = []

        for ticker in tickers:
            if ticker not in pm_signals:
                lines.append(f"  {ticker}: No signal data")
                continue

            signal_info = pm_signals[ticker]
            action = signal_info.get("action", "N/A")
            quantity = signal_info.get("quantity", 0)
            confidence = signal_info.get("confidence", "N/A")
            reasoning = signal_info.get("reasoning", "")

            # Display operation and quantity
            if quantity > 0:
                lines.append(
                    f"  {ticker}: {action} ({quantity} shares, confidence: {confidence}%)",
                )
            else:
                lines.append(
                    f"  {ticker}: {action} ( confidence: {confidence}%)",
                )

            # Add decision reasoning
            if reasoning:
                lines.append(f"    💭 Reasoning: {reasoning}")

        return lines

    def _build_pm_review_signal_mode(
        self,
        tickers: List[str],
        pm_signals: Dict[str, Any],
    ) -> List[str]:
        """Build PM review for signal mode"""
        lines = []

        for ticker in tickers:
            if ticker not in pm_signals:
                lines.append(f"  {ticker}: No signal data")
                continue

            signal_info = pm_signals[ticker]
            signal = signal_info["signal"]
            confidence = signal_info.get("confidence", "N/A")
            reasoning = signal_info.get("reasoning", "")

            lines.append(
                f"  {ticker}: {signal} (confidence: {confidence}%)",
            )

            # Add decision reasoning
            if reasoning:
                lines.append(f"    💭 Reasoning: {reasoning}")

        return lines

    def _build_returns_review(
        self,
        tickers: List[str],
        pm_signals: Dict[str, Any],
        real_returns: Dict[str, float],
        _daily_returns: Dict[str, float],
        live_env: Dict[str, Any],
    ) -> str:
        """Build actual return performance review"""
        lines = ["Actual return performance:"]

        if self.mode == "portfolio":
            lines.extend(
                self._build_returns_portfolio_mode(
                    tickers,
                    pm_signals,
                    real_returns,
                    live_env,
                ),
            )
        else:
            lines.extend(
                self._build_returns_signal_mode(
                    tickers,
                    pm_signals,
                    real_returns,
                ),
            )

        return "\n".join(lines)

    def _build_returns_portfolio_mode(
        self,
        tickers: List[str],
        pm_signals: Dict[str, Any],
        real_returns: Dict[str, float],
        live_env: Dict[str, Any],
    ) -> List[str]:
        """Build returns review for portfolio mode"""
        lines = []

        for ticker in tickers:
            if ticker not in real_returns:
                lines.append(f"  {ticker}: No return data")
                continue

            real_ret = real_returns[ticker] * 100
            signal_info = pm_signals.get(ticker, {})
            action = signal_info.get("action", "N/A")
            quantity = signal_info.get("quantity", 0)

            # Format return line based on action
            if quantity > 0 and action in ["long", "short"]:
                lines.append(
                    f"  {ticker}: stock real daily return {real_ret:.2f}% "
                    f"(operation: {action} {quantity} shares)",
                )
            elif quantity == 0 and action == "hold":
                lines.append(
                    f"  {ticker}: stock real daily return {real_ret:.2f}% "
                    f"(operation: {action})",
                )
            else:
                lines.append(
                    f"  {ticker}: stock real daily return {real_ret:.2f}% "
                    f"(signal: {signal_info.get('signal', 'N/A')})",
                )

        # Add portfolio summary
        portfolio_info = live_env.get("portfolio_summary", {})
        if portfolio_info:
            total_value = portfolio_info.get("total_value", 0)
            cash = portfolio_info.get("cash", 0)
            lines.append(
                f"\nPortfolio total value: ${total_value:,.2f} "
                f"(cash: ${cash:,.2f})",
            )

        return lines

    def _build_returns_signal_mode(
        self,
        tickers: List[str],
        pm_signals: Dict[str, Any],
        real_returns: Dict[str, float],
    ) -> List[str]:
        """Build returns review for signal mode"""
        lines = []

        for ticker in tickers:
            if ticker not in real_returns:
                lines.append(f"  {ticker}: No return data")
                continue

            real_ret = real_returns[ticker] * 100
            signal = pm_signals.get(ticker, {}).get("signal", "N/A")
            lines.append(
                f"  {ticker}: stock real daily return {real_ret:.2f}% "
                f"(signal: {signal})",
            )

        return lines

    def _build_analyst_review(
        self,
        tickers: List[str],
        ana_signals: Dict[str, Any],
    ) -> str:
        """Build analyst signal comparison"""
        lines = ["Analyst signal comparison:"]

        for agent, agent_signals in ana_signals.items():
            lines.append(f"\n{agent}:")
            for ticker in tickers:
                signal_data = agent_signals.get(ticker, {})
                signal = (
                    signal_data.get("signal", "N/A")
                    if isinstance(signal_data, dict)
                    else "N/A"
                )
                lines.append(f"  {ticker}: {signal}")

        return "\n".join(lines)

    def _perform_memory_review(
        self,
        date: str,
        tickers: List[str],
        live_env: Dict[str, Any],
    ):
        """Execute memory review (standalone function for delayed review)

        This function will be called the next day, after we have real_returns
        """
        pm_signals = live_env.get("pm_signals", {})
        ana_signals = live_env.get("ana_signals", {})
        daily_returns = live_env.get("daily_returns", {})
        real_returns = live_env.get("real_returns", {})

        # Display review information
        self.streamer.print(
            "agent",
            f"===== Post-Market Review ({date}) =====\n"
            f"Reviewing previous day's performance with actual returns",
            role_key="portfolio_manager",
        )

        # 1. Portfolio Manager signal review
        pm_review_lines = ["Portfolio Manager signal review:"]
        for ticker in tickers:
            if ticker in pm_signals:
                signal_info = pm_signals[ticker]
                if self.mode == "portfolio":
                    action = signal_info.get("action", "N/A")
                    quantity = signal_info.get("quantity", 0)
                    pm_review_lines.append(
                        f"  {ticker}: {action} ({quantity} shares)",
                    )
                else:
                    pm_review_lines.append(
                        f"  {ticker}: {signal_info.get('signal', 'N/A')}",
                    )

        # 2. Actual returns review
        returns_lines = ["Actual returns:"]
        for ticker in tickers:
            if ticker in real_returns:
                daily_ret = real_returns[ticker] * 100
                returns_lines.append(f"  {ticker}: {daily_ret:.2f}%")

        # 3. Analyst signal comparison
        analyst_lines = ["Analyst signal comparison:"]
        for agent, agent_signals in ana_signals.items():
            analyst_lines.append(f"\n{agent}:")
            for ticker in tickers:
                signal_data = agent_signals.get(ticker, {})
                signal = (
                    signal_data.get("signal", "N/A")
                    if isinstance(signal_data, dict)
                    else "N/A"
                )
                analyst_lines.append(f"  {ticker}: {signal}")

        self.streamer.print(
            "agent",
            "\n".join(pm_review_lines)
            + "\n"
            + "\n".join(returns_lines)
            + "\n"
            + "\n".join(analyst_lines),
            role_key="portfolio_manager",
        )

        # Execute memory review
        review_mode = os.getenv(
            "MEMORY_REVIEW_MODE",
            "individual_review",
        ).lower()
        state = live_env.get("state")

        if review_mode == "individual_review":
            result = self._run_individual_review_mode(
                date,
                tickers,
                pm_signals,
                ana_signals,
                daily_returns,
                real_returns,
                live_env,
                state,
            )
        else:
            result = self._run_central_review_mode(
                date,
                tickers,
                pm_signals,
                ana_signals,
                daily_returns,
                real_returns,
                live_env,
                state,
            )

        self.streamer.print("system", f"✅ Memory review completed for {date}")
        return result

    def _run_central_review_mode(
        self,
        date: str,
        tickers: List[str],
        pm_signals: Dict,
        ana_signals: Dict,
        daily_returns: Dict,
        real_returns: Dict,
        live_env: Dict[str, Any],
        state: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Central Review mode: Unified LLM manages memory"""
        self.streamer.print(
            "system",
            "===== Central Review Memory Management =====",
        )

        llm_decision = None
        execution_results = None

        try:
            if self.memory_reflection:
                reflection_data = self._prepare_reflection_data(
                    pm_signals,
                    ana_signals,
                    daily_returns,
                    real_returns,
                    tickers,
                    live_env,
                )

                llm_decision = self.memory_reflection.perform_reflection(
                    date=date,
                    reflection_data=reflection_data,
                    mode="central_review",
                    state=state,
                )

                execution_results = self._handle_llm_decision(llm_decision)
            else:
                self.streamer.print(
                    "system",
                    "LLM memory management system not enabled, skipping memory operations",
                )

        except Exception as e:
            self.streamer.print(
                "system",
                f"Memory management process error: {str(e)}",
            )
            import traceback

            traceback.print_exc()

        return self._build_response(
            pm_signals,
            ana_signals,
            daily_returns,
            real_returns,
            llm_decision,
            execution_results,
        )

    def _prepare_reflection_data(
        self,
        pm_signals: Dict,
        ana_signals: Dict,
        daily_returns: Dict,
        real_returns: Dict,
        tickers: List[str],
        live_env: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Prepare reflection data with analyst stats and portfolio info"""
        analyst_stats = self._extract_analyst_stats()

        return {
            "pm_signals": pm_signals,
            "actual_returns": daily_returns,
            "real_returns": real_returns,
            "analyst_signals": ana_signals,
            "tickers": tickers,
            "portfolio_summary": live_env.get("portfolio_summary", {}),
            "executed_trades": live_env.get("executed_trades", []),
            "failed_trades": live_env.get("failed_trades", []),
            "pre_portfolio_state": live_env.get("pre_portfolio_state", {}),
            "updated_portfolio": live_env.get("updated_portfolio", {}),
            "analyst_stats": analyst_stats,
            "live_env": live_env,
        }

    def _extract_analyst_stats(self) -> Dict[str, Any]:
        """Extract analyst performance stats from dashboard"""
        analyst_stats = {}

        if not self.dashboard_generator:
            return analyst_stats

        dashboard_state = self.dashboard_generator.load_internal_state()
        agent_performance = dashboard_state.get("agent_performance", {})

        for agent_id, perf in agent_performance.items():
            analyst_stats[agent_id] = self._calculate_agent_stats(perf)

        return analyst_stats

    def _calculate_agent_stats(self, perf: Dict) -> Dict[str, Any]:
        """Calculate statistics for a single agent"""
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

        return {
            "win_rate": win_rate,
            "total_predictions": total_count,
            "correct_predictions": total_win,
            "bull": {
                "count": bull_count,
                "win": bull_win,
                "unknown": bull_unknown,
            },
            "bear": {
                "count": bear_count,
                "win": bear_win,
                "unknown": bear_unknown,
            },
        }

    def _handle_llm_decision(self, llm_decision: Dict) -> Optional[list]:
        """Handle LLM decision and return execution results"""
        if llm_decision["status"] != "success":
            self._handle_failed_decision(llm_decision)
            return None

        if llm_decision["mode"] == "operations_executed":
            return self._handle_operations_executed(llm_decision)
        elif llm_decision["mode"] == "no_action":
            self._handle_no_action(llm_decision)
            return None
        else:
            self.streamer.print(
                "system",
                f"Unknown LLM decision mode: {llm_decision['mode']}",
            )
            return None

    def _handle_failed_decision(self, llm_decision: Dict) -> None:
        """Handle failed or skipped LLM decisions"""
        if llm_decision["status"] == "skipped":
            self.streamer.print(
                "system",
                f"Memory management skipped: {llm_decision['reason']}",
            )
        else:
            self.streamer.print(
                "system",
                f"LLM decision failed: {llm_decision.get('error', 'Unknown error')}",
            )

    def _handle_operations_executed(self, llm_decision: Dict) -> list:
        """Handle operations executed mode"""
        execution_results = llm_decision["execution_results"]
        successful = sum(
            1
            for result in execution_results
            if result["result"]["status"] == "success"
        )
        total = len(execution_results)

        memory_lines = [
            "Using LLM tool_call for intelligent memory management",
            f"Executed {llm_decision['operations_count']} memory operations",
            f"Execution statistics: Success {successful}/{total}",
            "\nTool call details:",
        ]

        for i, exec_result in enumerate(execution_results, 1):
            self._format_execution_result(memory_lines, i, exec_result)

        self.streamer.print(
            "agent",
            "\n".join(memory_lines),
            role_key="portfolio_manager",
        )

        return execution_results

    def _handle_no_action(self, llm_decision: Dict) -> None:
        """Handle no action mode"""
        no_action_lines = [
            "Using LLM tool_call for intelligent memory management",
            "LLM determined no memory operations needed",
            f"Reasoning: {llm_decision['reasoning']}",
        ]
        self.streamer.print(
            "agent",
            "\n".join(no_action_lines),
            role_key="portfolio_manager",
        )

    def _format_execution_result(
        self,
        memory_lines: List[str],
        index: int,
        exec_result: Dict,
    ) -> None:
        """Format a single execution result"""
        tool_name = exec_result["tool_name"]
        args = exec_result["args"]
        result = exec_result["result"]
        agent_id = args.get("analyst_id", "N/A")

        memory_lines.append(f"\n{index}. Tool: {tool_name}")
        memory_lines.append(f"   Analyst: {agent_id}")
        memory_lines.append(f"   Memory tool parameters: {args}")

        self._format_result_status(memory_lines, result)
        self._print_agent_memory_operation(tool_name, args, result, agent_id)

    def _format_result_status(
        self,
        memory_lines: List[str],
        result: Dict,
    ) -> None:
        """Format result status information"""
        if result["status"] == "success":
            memory_lines.append("\tStatus: Success")
            if "affected_count" in result:
                memory_lines.append(
                    f"   Affected memory count: {result['affected_count']}",
                )
        else:
            memory_lines.append(
                f"\tStatus: Failed - {result.get('error', 'Unknown')}",
            )

    def _print_agent_memory_operation(
        self,
        tool_name: str,
        args: Dict,
        result: Dict,
        agent_id: str,
    ) -> None:
        """Print agent-specific memory operation details"""
        if tool_name == "search_and_update_analyst_memory":
            self._print_update_operation(args, result, agent_id)
        elif tool_name == "search_and_delete_analyst_memory":
            self._print_delete_operation(args, result, agent_id)

    def _print_update_operation(
        self,
        args: Dict,
        result: Dict,
        agent_id: str,
    ) -> None:
        """Print update memory operation details"""
        agent_mem_lines = [
            "[memory management]: search and update memory",
            f"search memory query: {args.get('query', 'N/A')}",
        ]

        if result.get("memory_id"):
            agent_mem_lines.append(f"memory ID: {result['memory_id']}")

        if result.get("original_content"):
            original = result["original_content"]
            display_original = (
                original[:200] + "..." if len(original) > 200 else original
            )
            agent_mem_lines.append(f"original memory: {display_original}")

        agent_mem_lines.extend(
            [
                f"new memory content: {args.get('new_content', 'N/A')}",
                f"reason: {args.get('reason', 'N/A')}",
            ],
        )

        self.streamer.print(
            "agent",
            "\n".join(agent_mem_lines),
            role_key=agent_id,
        )

    def _print_delete_operation(
        self,
        args: Dict,
        result: Dict,
        agent_id: str,
    ) -> None:
        """Print delete memory operation details"""
        agent_mem_lines = [
            "[memory management]: search and delete memory",
            f"search memory query: {args.get('query', 'N/A')}",
        ]

        if result.get("memory_id"):
            agent_mem_lines.append(f"memory ID: {result['memory_id']}")

        if result.get("deleted_content"):
            deleted = result["deleted_content"]
            display_deleted = (
                deleted[:200] + "..." if len(deleted) > 200 else deleted
            )
            agent_mem_lines.append(f"deleted memory: {display_deleted}")

        agent_mem_lines.append(f"reason: {args.get('reason', 'N/A')}")

        self.streamer.print(
            "agent",
            "\n".join(agent_mem_lines),
            role_key=agent_id,
        )

    def _build_response(
        self,
        pm_signals: Dict,
        ana_signals: Dict,
        daily_returns: Dict,
        real_returns: Dict,
        llm_decision: Optional[Dict],
        execution_results: Optional[list],
    ) -> Dict[str, Any]:
        """Build final response dictionary"""
        return {
            "status": "success",
            "type": "full_review",
            "pre_market_signals": pm_signals,
            "analyst_signals": ana_signals,
            "actual_returns": daily_returns,
            "real_returns": real_returns,
            "llm_memory_decision": llm_decision,
            "memory_tool_calls_results": execution_results,
            "timestamp": datetime.now().isoformat(),
        }

    def _run_individual_review_mode(
        self,
        date: str,
        tickers: List[str],
        pm_signals: Dict,
        ana_signals: Dict,
        daily_returns: Dict,
        real_returns: Dict,
        live_env: Dict[str, Any],
        state: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Individual Review mode: Each Agent self-reviews independently (new mode)"""
        print("===== Individual Review Mode =====")
        print("Each Agent conducts independent self-review")

        reflection_results = {}
        portfolio_summary = live_env.get("portfolio_summary", {})

        # Check if enabled
        enable_individual_review = (
            os.getenv("ENABLE_INDIVIDUAL_REVIEW", "true").lower() == "true"
        )

        if not enable_individual_review:
            self.streamer.print(
                "system",
                "⚠️ Individual Review disabled (ENABLE_INDIVIDUAL_REVIEW=false)",
            )
            return {
                "status": "skipped",
                "mode": "individual_review",
                "date": date,
                "reason": "Individual Review disabled",
            }

        try:
            self.streamer.print("system", "\n--- Individual Review Mode ---")

            # Prepare data for all agents
            agents_data = {}

            # ========== 1. Each analyst data ==========
            for analyst_id, _ in ANALYST_TYPES.items():
                my_signals = {}
                for ticker in tickers:
                    if (
                        analyst_id in ana_signals
                        and ticker in ana_signals[analyst_id]
                    ):
                        signal_data = ana_signals[analyst_id][ticker]
                        signal_value = (
                            signal_data.get("signal", "N/A")
                            if isinstance(signal_data, dict)
                            else "N/A"
                        )
                        reasoning_text = (
                            signal_data.get("reasoning", "")
                            or signal_data.get("tool_analysis", "")
                            if isinstance(signal_data, dict)
                            else ""
                        )

                        my_signals[ticker] = {
                            "signal": signal_value,
                            "confidence": (
                                signal_data.get("confidence", 0)
                                if isinstance(signal_data, dict)
                                else 0
                            ),
                            "reasoning": reasoning_text,
                        }

                agents_data[analyst_id] = {
                    "agent_id": analyst_id,
                    "my_signals": my_signals,
                    "actual_returns": daily_returns,
                    "real_returns": real_returns,
                    "pm_decisions": pm_signals,
                }

            # ========== 2. PM data ==========
            # 获取 dashboard state 中的历史胜率数据
            dashboard_state = self.dashboard_generator.load_internal_state()
            agent_performance = dashboard_state.get("agent_performance", {})

            # 格式化为简洁的统计数据（只提取关键信息）
            analyst_stats = {}
            for agent_id, perf in agent_performance.items():
                bull_count = perf.get("bull_count", 0)
                bull_win = perf.get("bull_win", 0)
                bull_unknown = perf.get("bull_unknown", 0)
                bear_count = perf.get("bear_count", 0)
                bear_win = perf.get("bear_win", 0)
                bear_unknown = perf.get("bear_unknown", 0)

                # 计算胜率（与前端逻辑一致）
                evaluated_bull = max(bull_count - bull_unknown, 0)
                evaluated_bear = max(bear_count - bear_unknown, 0)
                total_count = bull_count + bear_count
                total_win = bull_win + bear_win
                evaluated_total = evaluated_bull + evaluated_bear
                win_rate = (
                    (total_win / evaluated_total)
                    if evaluated_total > 0
                    else None
                )

                analyst_stats[agent_id] = {
                    "win_rate": win_rate,
                    "total_predictions": total_count,
                    "correct_predictions": total_win,
                    "bull": {
                        "count": bull_count,
                        "win": bull_win,
                        "unknown": bull_unknown,
                    },
                    "bear": {
                        "count": bear_count,
                        "win": bear_win,
                        "unknown": bear_unknown,
                    },
                }

            agents_data["portfolio_manager"] = {
                "agent_id": "portfolio_manager",
                "my_decisions": pm_signals,
                "analyst_signals": ana_signals,
                "actual_returns": daily_returns,
                "real_returns": real_returns,
                "live_env": live_env,
                "analyst_stats": analyst_stats,
            }

            # pdb.set_trace()
            # ========== 3. Execute unified review ==========
            if self.memory_reflection:
                result = self.memory_reflection.perform_reflection(
                    date=date,
                    reflection_data={"agents_data": agents_data},
                    mode="individual_review",
                    state=state,
                )

                reflection_results = {
                    agent_result["agent_id"]: agent_result
                    for agent_result in result.get("agents_results", [])
                }

            # ========== 4. Generate summary report ==========
            summary = self._generate_individual_review_summary(
                reflection_results=reflection_results,
                _portfolio_summary=portfolio_summary,
            )

            print("system", "\n📊 Individual Review Summary:")
            self.streamer.print("system", summary)

            return {
                "status": "success",
                "mode": "individual_review",
                "date": date,
                "reflection_results": reflection_results,
                "summary": summary,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            print(f"❌ Individual Review execution failed: {e}")
            import traceback

            traceback.print_exc()
            return {
                "status": "failed",
                "mode": "individual_review",
                "date": date,
                "error": str(e),
            }

    def _generate_individual_review_summary(
        self,
        reflection_results: Dict[str, Dict[str, Any]],
        _portfolio_summary: Dict[str, Any],
    ) -> str:
        """Generate Individual Review summary"""
        summary_lines = []

        # Count memory operations
        total_agents = len(reflection_results)
        successful_agents = sum(
            1
            for r in reflection_results.values()
            if r.get("status") == "success"
        )
        total_operations = 0
        operations_by_type = {"update": 0, "delete": 0}

        for agent_id, result in reflection_results.items():
            if result.get("status") == "success":
                ops_count = len(result["memory_operations"])
                total_operations += ops_count

                for op in result.get("memory_operations", []):
                    tool_name = op.get("tool_name", "")
                    if "update" in tool_name:
                        operations_by_type["update"] += 1
                    elif "delete" in tool_name:
                        operations_by_type["delete"] += 1

        summary_lines.append(
            f"Today {total_agents} Agents completed self-review",
        )
        summary_lines.append(
            f"Success: {successful_agents}, Failed: {total_agents - successful_agents}",
        )
        summary_lines.append(
            f"Memory operations executed: {total_operations} times",
        )

        if operations_by_type["update"] > 0:
            summary_lines.append(
                f"  - Update memory: {operations_by_type['update']} times",
            )
        if operations_by_type["delete"] > 0:
            summary_lines.append(
                f"  - Delete memory: {operations_by_type['delete']} times",
            )

        # Each Agent status
        summary_lines.append("\nEach Agent review status:")
        for agent_id, result in reflection_results.items():
            status = result.get("status", "unknown")
            ops_count = len(result["memory_operations"])
            status_emoji = "✅" if status == "success" else "❌"
            summary_lines.append(
                f"  {status_emoji} {agent_id}: {status} ({ops_count} operations)",
            )
        # pdb.set_trace()
        return "\n".join(summary_lines)

    def generate_trading_dates(
        self,
        start_date: str,
        end_date: str,
    ) -> List[str]:
        """Generate trading date list (use batch query to optimize performance)"""
        if not self.validate_date_format(
            start_date,
        ) or not self.validate_date_format(end_date):
            raise ValueError("Date format should be YYYY-MM-DD")
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        if start_dt > end_dt:
            raise ValueError("Start date cannot be later than end date")

        print(
            f"⏳ Generating trading date list ({start_date} -> {end_date})...",
        )

        # Use batch query (get all trading days at once)
        return self.strategy.get_trading_dates(start_date, end_date)

    def run_multi_day_simulation(
        self,
        start_date: str,
        end_date: str,
        tickers: List[str],
        max_comm_cycles: int = 2,
        enable_communications: bool = False,
        enable_notifications: bool = False,
    ) -> Dict[str, Any]:
        """Run multi-day sandbox simulation"""
        trading_days = self.generate_trading_dates(start_date, end_date)
        if not trading_days:
            self.streamer.print("system", "No trading days in selected range")
            return {
                "status": "skipped",
                "reason": "No trading days",
                "start_date": start_date,
                "end_date": end_date,
                "daily_results": {},
            }

        self.streamer.print(
            "system",
            f"===== Multi-Day Sandbox Simulation {start_date} ~ {end_date} =====",
        )
        self.streamer.print(
            "system",
            f"Covering trading days: {len(trading_days)} days -> {', '.join(trading_days[:5])}{'...' if len(trading_days) > 5 else ''}",
        )

        daily_results: Dict[str, Dict[str, Any]] = {}
        success_days: List[str] = []
        failed_days: List[str] = []

        for idx, date in enumerate(trading_days, start=1):
            self.streamer.print(
                "system",
                f"--- [{idx}/{len(trading_days)}] {date} ---",
            )
            day_result = self.run_full_day_simulation(
                date=date,
                tickers=tickers,
                max_comm_cycles=max_comm_cycles,
                enable_communications=enable_communications,
                enable_notifications=enable_notifications,
            )
            daily_results[date] = day_result

            day_status = day_result.get("summary", {}).get(
                "overall_status",
                "failed",
            )
            if day_status == "success":
                success_days.append(date)
            else:
                failed_days.append(date)

        summary = self._build_multi_day_summary(
            start_date=start_date,
            end_date=end_date,
            trading_days=trading_days,
            success_days=success_days,
            failed_days=failed_days,
        )
        self._print_multi_day_summary(summary)

        return {
            "status": "completed",
            "start_date": start_date,
            "end_date": end_date,
            "trading_days": trading_days,
            "success_days": success_days,
            "failed_days": failed_days,
            "summary": summary,
            "daily_results": daily_results,
        }

    def _build_multi_day_summary(
        self,
        start_date: str,
        end_date: str,
        trading_days: List[str],
        success_days: List[str],
        failed_days: List[str],
    ) -> Dict[str, Any]:
        total = len(trading_days)
        success = len(success_days)
        fail = len(failed_days)
        success_rate = success / total * 100 if total else 0.0

        return {
            "start_date": start_date,
            "end_date": end_date,
            "total_days": total,
            "success_days": success,
            "failed_days": fail,
            "success_rate_pct": round(success_rate, 2),
            "first_trading_day": trading_days[0] if trading_days else None,
            "last_trading_day": trading_days[-1] if trading_days else None,
            "failed_day_list": failed_days,
        }

    def _print_multi_day_summary(self, summary: Dict[str, Any]) -> None:
        self.streamer.print(
            "system",
            "===== Multi-Day Simulation Summary ====="
            f"\nRange: {summary['start_date']} ~ {summary['end_date']}"
            f"\nTrading days: {summary['total_days']}"
            f"\nSuccess days: {summary['success_days']}"
            f"\nFailed days: {summary['failed_days']}"
            f"\nSuccess rate: {summary['success_rate_pct']:.2f}%",
        )

        if summary["failed_day_list"]:
            self.streamer.print(
                "system",
                f"Failed dates: {', '.join(summary['failed_day_list'])}",
            )
        self.streamer.print("system", "=" * 40)

    def run_pre_market_analysis_only(
        self,
        date: str,
        tickers: List[str],
        max_comm_cycles: int = 2,
        enable_communications: bool = False,
        enable_notifications: bool = False,
    ) -> Dict[str, Any]:
        """Run pre-market analysis (only runs strategy.run_single_day, does not execute trades)

        This method is used by live_server.py, so is_live_mode is set to True.
        """

        is_trading_day = self.is_trading_day(date)

        if not is_trading_day:
            print(
                "[system]",
                f"{date} is not a trading day, skip pre-market analysis",
            )
            return {
                "status": "skipped",
                "date": date,
                "is_trading_day": False,
                "reason": "Not trading day",
            }

        print(
            "[system]",
            f"{date} is a trading day, executing pre-market analysis",
        )

        # Display current portfolio state
        if self.mode == "portfolio" and self.strategy.portfolio_state:
            positions_count = len(
                [
                    p
                    for p in self.strategy.portfolio_state.get(
                        "positions",
                        {},
                    ).values()
                    if p.get("long", 0) > 0 or p.get("short", 0) > 0
                ],
            )
            self.streamer.print(
                "system",
                f"Current portfolio: Cash ${self.strategy.portfolio_state['cash']:,.2f}, "
                f"Positions {positions_count}",
            )

        # Run pre-market analysis (do not calculate real_returns, market hasn't closed yet)
        # ⭐ Set is_live_mode=True for live_server.py (risk manager will use T-1 day prices)
        pre_market_result = self.run_pre_market_analysis(
            date,
            tickers,
            max_comm_cycles,
            enable_communications,
            enable_notifications,
            skip_real_returns=True,  # Live mode: Skip real_returns calculation
            is_live_mode=True,  # Live mode: Risk manager uses T-1 day closing price
        )

        return {
            "status": "success",
            "date": date,
            "is_trading_day": True,
            "pre_market": pre_market_result,
        }

    def run_trade_execution_and_update_prev_perf(
        self,
        date: str,
        tickers: List[str],
        pre_market_result: Optional[Dict[str, Any]] = None,
        prev_date: Optional[str] = None,
        prev_signals: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute trades and update previous day's agent performance

        Args:
            date: Current trading day
            tickers: Stock list
            pre_market_result: Pre-market analysis result for the day (contains signals)
            prev_date: Previous trading day
            prev_signals: Previous day's signals (ana_signals and pm_signals)
        """

        is_trading_day = self.is_trading_day(date)

        if not is_trading_day:
            print(
                "[system]",
                f"{date} is not a trading day, skip trade execution",
            )
            return {
                "status": "skipped",
                "date": date,
                "is_trading_day": False,
                "reason": "Not trading day",
            }

        print("[system]", f"{date} trade execution started")

        # 1. Update previous day's agent performance (if provided)
        if prev_date and prev_signals:
            self._update_previous_day_performance(
                prev_date,
                tickers,
                prev_signals,
            )

        # 2. Execute current day's trades (if pre-market analysis result exists)
        # Note: In Live mode, only execute trades here, do not perform memory review
        # Because real_returns are not available yet (need to wait until after market close)
        post_market_result = None
        if pre_market_result and pre_market_result.get("status") == "success":
            live_env = pre_market_result["pre_market"].get("live_env")
            if live_env:
                print(
                    "[system]",
                    "Executing trades based on pre-market analysis...",
                )
                # pdb.set_trace()
                # In Live mode, only execute trades, do not perform memory review
                # Memory review will be performed tomorrow (in _update_previous_day_performance)
                post_market_result = self._execute_trades_only(
                    date,
                    tickers,
                    live_env,
                    pre_market_result,
                )

        return {
            "status": "success",
            "date": date,
            "is_trading_day": True,
            "post_market": post_market_result,
            "prev_day_updated": prev_date is not None,
        }

    def _execute_trades_only(
        self,
        date: str,
        tickers: List[str],
        live_env: Dict[str, Any],
        pre_market_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute trades only, do not perform memory review (for Live mode)

        In Live mode:
        1. First update historical data via ret_data_updater (to get today's closing prices)
        2. Then update current_prices in state from risk manager (using today's closing prices)
        3. Then execute deferred trades using today's closing prices
        """
        pm_signals = live_env.get("pm_signals", {})

        self.streamer.print(
            "system",
            f"===== Trade Execution ({date}) =====\n"
            f"Step 1: Updating historical data to get today's closing prices...",
        )

        # Step 1: Update historical data (to get today's closing prices)
        try:
            from backend.data.ret_data_updater import DataUpdater

            api_key = os.getenv("FINNHUB_API_KEY")
            if api_key:
                updater = DataUpdater(api_key=api_key)
                for ticker in tickers:
                    updater.update_ticker(ticker, force_full_update=False)
                self.streamer.print("system", "✅ Historical data updated")
            else:
                self.streamer.print(
                    "system",
                    "⚠️ FINNHUB_API_KEY not found, skipping data update",
                )
        except Exception as e:
            self.streamer.print(
                "system",
                f"⚠️ Failed to update historical data: {e}",
            )

        # Step 2: Get state and execute deferred trades
        state = live_env.get("state")
        if not state:
            self.streamer.print(
                "system",
                "⚠️ State not found in live_env, cannot execute trades",
            )
            return {
                "status": "failed",
                "type": "trade_execution_only",
                "date": date,
                "error": "State not found in live_env",
            }

        # Step 3: Execute deferred trades (this will get today's closing prices and execute trades)
        self.streamer.print(
            "system",
            "Step 2: Getting today's closing prices and executing trades...",
        )

        try:
            final_execution_report = (
                self.strategy.engine.execute_deferred_trades(
                    state=state,
                    decisions=pm_signals,
                    mode=self.mode,
                    date=date,
                )
            )

            # Update live_env with execution report
            live_env["execution_report"] = final_execution_report
            live_env["executed_trades"] = final_execution_report.get(
                "executed_trades",
                [],
            )
            live_env["failed_trades"] = final_execution_report.get(
                "failed_trades",
                [],
            )

            # Display execution results
            executed_trades = final_execution_report.get("executed_trades", [])
            failed_trades = final_execution_report.get("failed_trades", [])

            if executed_trades:
                trade_lines = ["✅ Successfully executed trades:"]
                for trade in executed_trades:
                    ticker = trade.get("ticker", "N/A")
                    action = trade.get("action", "N/A")
                    quantity = trade.get("quantity", 0)
                    price = trade.get("price", 0)
                    trade_lines.append(
                        f"  {ticker}: {action} {quantity} shares @ ${price:.2f}",
                    )
                self.streamer.print(
                    "agent",
                    "\n".join(trade_lines),
                    role_key="portfolio_manager",
                )

            if failed_trades:
                fail_lines = ["❌ Failed trades:"]
                for trade in failed_trades:
                    ticker = trade.get("ticker", "N/A")
                    reason = trade.get("reason", "Unknown")
                    fail_lines.append(f"  {ticker}: {reason}")
                self.streamer.print(
                    "agent",
                    "\n".join(fail_lines),
                    role_key="portfolio_manager",
                )

        except Exception as e:
            self.streamer.print("system", f"❌ Failed to execute trades: {e}")
            import traceback

            traceback.print_exc()
            return {
                "status": "failed",
                "type": "trade_execution_only",
                "date": date,
                "error": str(e),
            }

        # Step 4: Update dashboard
        dashboard_update_stats = (
            self.dashboard_generator.update_from_day_result(
                date=date,
                pre_market_result=pre_market_result,
                mode=self.mode,
            )
        )
        self.streamer.print(
            "system",
            f"Dashboard updated: {dashboard_update_stats.get('trades_added', 0)} trades added, "
            f"{dashboard_update_stats.get('agents_updated', 0)} agents updated",
        )

        # Record to sandbox log
        log_data = {
            "status": "success",
            "type": "trade_execution_only",
            "pm_signals": pm_signals,
            "execution_report": final_execution_report,
            "note": "Memory review will be performed next day",
        }
        self._log_sandbox_activity(date, self.POST_MARKET, log_data)

        self.streamer.print(
            "system",
            "✅ Trades executed. Memory review scheduled for next trading day.",
        )

        return {
            "status": "success",
            "type": "trade_execution_only",
            "date": date,
            "execution_report": final_execution_report,
            "note": "Memory review will be performed next day when real_returns available",
        }

    def _update_previous_day_performance(
        self,
        prev_date: str,
        tickers: List[str],
        prev_signals: Dict[str, Any],
    ):
        """Update previous day's agent performance and execute memory review (can now get real_returns)"""

        print(
            "[system]",
            f"Updating agent performance and memory review for previous trading day: {prev_date}",
        )

        ana_signals = prev_signals.get("ana_signals", {})
        pm_signals = prev_signals.get("pm_signals", {})
        prev_pre_market_result = prev_signals.get("pre_market_result", {})

        # Calculate previous day's real_returns (can now get closing prices)
        real_returns = {}
        daily_returns = {}
        for ticker in tickers:
            if ticker in pm_signals:
                action = pm_signals[ticker]["action"]
                (
                    daily_return,
                    real_return,
                    _close_price,
                ) = self.strategy.calculate_stock_daily_return_from_signal(
                    ticker,
                    prev_date,
                    action,
                )

                real_returns[ticker] = real_return
                daily_returns[ticker] = daily_return
        self.streamer.print("system", real_returns)

        # 1. Update agent performance in dashboard
        update_stats = {
            "agents_updated": 0,
            "signals_updated": 0,
        }

        dashboard_state = self.dashboard_generator.load_internal_state()

        # Note: Model configuration is now always read fresh from environment variables
        # in _get_agent_model_config(), no need to store in state

        self.dashboard_generator.update_agent_performance(
            date=prev_date,
            ana_signals=ana_signals,
            pm_signals=pm_signals,
            real_returns=real_returns,
            state=dashboard_state,
            update_stats=update_stats,
        )
        self.dashboard_generator.update_pm_performance(
            date=prev_date,
            pm_signals=pm_signals,
            real_returns=real_returns,
            state=dashboard_state,
            update_stats=update_stats,
        )
        self.dashboard_generator.save_internal_state(dashboard_state)

        # ⭐ Key fix: Generate dashboard files needed by frontend
        # - stats.json: Contains Portfolio Manager's win_rate and other statistics
        # - leaderboard.json: Contains leaderboard data for all Agents (with model info)
        self.dashboard_generator.generate_stats(dashboard_state)
        self.dashboard_generator.generate_leaderboard(dashboard_state)

        self.streamer.print(
            "system",
            f"Previous day performance updated: {update_stats['agents_updated']} agents evaluated, dashboard files refreshed",
        )

        # 2. Execute previous day's memory review (now have real_returns, can accurately evaluate performance)
        self.streamer.print(
            "system",
            f"===== Memory Review for {prev_date} (Delayed) =====\n",
        )

        # Build live_env (contains real_returns)
        live_env = {
            "pm_signals": pm_signals,
            "ana_signals": ana_signals,
            "real_returns": real_returns,
            "daily_returns": daily_returns,
            "portfolio_summary": prev_pre_market_result.get(
                "live_env",
                {},
            ).get("portfolio_summary", {}),
            "state": prev_pre_market_result.get("live_env", {}).get("state"),
        }
        # pdb.set_trace()
        # Execute memory review
        self._perform_memory_review(prev_date, tickers, live_env)

    def run_full_day_simulation(
        self,
        date: str,
        tickers: List[str],
        max_comm_cycles: int = 2,
        enable_communications: bool = False,
        enable_notifications: bool = False,
    ) -> Dict[str, Any]:
        """Run complete day simulation (pre-market + post-market) - Backward compatible full version"""

        results = {
            "date": date,
            "is_trading_day": self.is_trading_day(date),
            "pre_market": None,
            "post_market": None,
            "summary": {},
            "portfolio_state": None,
        }

        if results["is_trading_day"]:
            print(
                "[system]",
                f"{date} is a trading day, will execute pre-market analysis + post-market review",
            )

            # Display current portfolio state
            if self.mode == "portfolio" and self.strategy.portfolio_state:
                positions_count = len(
                    [
                        p
                        for p in self.strategy.portfolio_state.get(
                            "positions",
                            {},
                        ).values()
                        if p.get("long", 0) > 0 or p.get("short", 0) > 0
                    ],
                )
                self.streamer.print(
                    "system",
                    f"Current portfolio: Cash ${self.strategy.portfolio_state['cash']:,.2f}, "
                    f"Positions {positions_count}",
                )

            # 1. Pre-market analysis
            results["pre_market"] = self.run_pre_market_analysis(
                date,
                tickers,
                max_comm_cycles,
                enable_communications,
                enable_notifications,
            )

            print(
                "[system]",
                "Waiting for post-market time point...\n(Simulating waiting for actual market close)",
            )

            # 2. Post-market review
            live_env = (
                results["pre_market"].get("live_env")
                if results["pre_market"]
                else None
            )
            results["post_market"] = self.run_post_market_review(
                date,
                tickers,
                live_env,
            )

        else:
            print(
                "[system]",
                f"{date} is not a trading day, only executing post-market review",
            )

            # Non-trading day only executes post-market
            results["post_market"] = self.run_post_market_review(
                date,
                tickers,
                None,
            )

        # Generate day summary
        results["summary"] = self._generate_day_summary(results)

        # Return portfolio state
        if self.mode == "portfolio":
            results["portfolio_state"] = self.strategy.portfolio_state

        summary: Dict[str, Any] = results["summary"]
        self._print_day_summary(summary)

        return results

    def _generate_day_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        summary = {
            "date": results["date"],
            "is_trading_day": results["is_trading_day"],
            "activities_completed": [],
            "overall_status": "success",
        }

        if results["pre_market"]:
            summary["activities_completed"].append("Pre-market analysis")
            if results["pre_market"]["status"] != "success":
                summary["overall_status"] = "partial_failure"

        if results["post_market"]:
            summary["activities_completed"].append("Post-market review")
            if results["post_market"]["status"] != "success":
                summary["overall_status"] = "failed"

        return summary

    def _print_day_summary(self, summary: Dict[str, Any]):
        """Print day summary"""
        self.streamer.print(
            "system",
            f"{summary['date']} complete simulation ended\n"
            f"===== {summary['date']} Day Summary =====\n"
            f"\tTrading day status: {'Yes' if summary['is_trading_day'] else 'No'}\n"
            f"\tActivities completed: {', '.join(summary['activities_completed'])}\n"
            f"\tOverall status: {summary['overall_status']}\n"
            f"============================",
        )

    def _log_sandbox_activity(
        self,
        date: str,
        time_point: str,
        data: Dict[str, Any],
    ):
        """Record sandbox activity log"""
        log_file = (
            self.sandbox_dir / f"sandbox_day_{date.replace('-', '_')}.json"
        )

        # Load existing log
        if log_file.exists():
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    log_data = json.load(f)
            except Exception:
                log_data = {}
        else:
            log_data = {}

        # Add new activity
        log_data[time_point] = data
        log_data["last_updated"] = datetime.now().isoformat()

        # Save log
        try:
            with open(log_file, "w", encoding="utf-8") as f:
                json.dump(
                    log_data,
                    f,
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                )
        except Exception as e:
            self.streamer.print("system", f"Failed to save sandbox log: {e}")

    def _load_sandbox_log(self, date: str, time_point: str) -> Dict[str, Any]:
        """Load sandbox activity log"""
        log_file = (
            self.sandbox_dir / f"sandbox_day_{date.replace('-', '_')}.json"
        )

        if not log_file.exists():
            return {}

        try:
            with open(log_file, "r", encoding="utf-8") as f:
                log_data = json.load(f)
            return log_data.get(time_point, {})
        except Exception as e:
            self.streamer.print("system", f"Failed to load sandbox log: {e}")
            return {}


def _parse_arguments() -> argparse.Namespace:
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Live Trading Thinking Fund - Sandbox time simulation system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
  # Run complete simulation for specified date
  python live_trading_fund.py --date 2025-01-15 --tickers AAPL,MSFT --config_name my_config

  # Use environment variable stock configuration
  python live_trading_fund.py --date 2025-01-15 --config_name my_config

  # Force run (ignore various checks)
  python live_trading_fund.py --date 2025-01-15 --force-run --config_name my_config

  # Custom communication rounds
  python live_trading_fund.py --date 2025-01-15 --max-comm-cycles 3 --config_name my_config
        """,
    )

    # Required parameters
    parser.add_argument(
        "--date",
        type=str,
        help="Specify single simulation date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        help="Multi-day simulation start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        help="Multi-day simulation end date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--config_name",
        type=str,
        required=True,
        help="Configuration data storage directory name",
    )
    # Optional parameters
    parser.add_argument(
        "--tickers",
        type=str,
        help="Stock symbol list, comma separated (optional, use environment variable configuration)",
    )
    parser.add_argument(
        "--max-comm-cycles",
        type=int,
        help="Maximum communication rounds (default: 2)",
    )
    parser.add_argument(
        "--force-run",
        action="store_true",
        help="Force run, rerun even if already run on this trading day",
    )
    parser.add_argument(
        "--base-dir",
        type=str,
        help="Base directory",
    )
    # Portfolio mode parameters
    parser.add_argument(
        "--mode",
        type=str,
        choices=["signal", "portfolio"],
        help="Running mode: signal (signal mode) or portfolio (portfolio mode). Default read from .env",
    )
    parser.add_argument(
        "--initial-cash",
        type=float,
        help="Portfolio mode initial cash (default: 100000.0)",
    )
    parser.add_argument(
        "--margin-requirement",
        type=float,
        help="Portfolio mode margin requirement, 0.0 means disable shorting, 0.5 means 50%% margin (default: 0.0)",
    )

    return parser.parse_args()


def _initialize_system(config: LiveThinkingFundConfig) -> LiveTradingFund:
    """Initialize memory system and thinking fund"""
    console_streamer = ConsoleStreamer()

    # Initialize memory system
    _memory_instance = get_memory(base_dir=config.config_name)
    print("✅ Memory system initialized")

    # Initialize thinking fund system
    thinking_fund = LiveTradingFund(
        config_name=config.config_name,
        streamer=console_streamer,
        mode=config.mode,
        initial_cash=config.initial_cash,
        margin_requirement=config.margin_requirement,
    )

    return thinking_fund


def _print_configuration(config: LiveThinkingFundConfig) -> None:
    """Print system configuration"""
    from pprint import pprint

    print("\n📊 Live Trading Thinking Fund Configuration:")
    print(f"   Running mode: {config.mode.upper()}")
    if config.mode == "portfolio":
        print(f"   Initial cash: ${config.initial_cash:,.2f}")
        print(f"   Margin requirement: {config.margin_requirement * 100:.1f}%")
    pprint(config.__dict__)


def _run_simulation(
    thinking_fund: LiveTradingFund,
    args: argparse.Namespace,
    config: LiveThinkingFundConfig,
    tickers: List[str],
) -> None:
    """Run single or multi-day simulation"""
    if args.start_date or args.end_date:
        _run_multi_day_simulation(thinking_fund, args, config, tickers)
    else:
        _run_single_day_simulation(thinking_fund, args, tickers)


def _run_multi_day_simulation(
    thinking_fund: LiveTradingFund,
    args: argparse.Namespace,
    config: LiveThinkingFundConfig,
    tickers: List[str],
) -> None:
    """Run multi-day simulation"""
    if not args.start_date or not args.end_date:
        print(
            "Error: Multi-day mode requires both --start-date and --end-date",
        )
        sys.exit(1)

    results = thinking_fund.run_multi_day_simulation(
        start_date=args.start_date,
        end_date=args.end_date,
        tickers=tickers,
        max_comm_cycles=config.max_comm_cycles,
        enable_communications=not config.disable_communications,
        enable_notifications=not config.disable_notifications,
    )
    print(
        f"\nMulti-day sandbox simulation completed: "
        f"{results['summary']['success_days']} / {results['summary']['total_days']} success",
    )


def _run_single_day_simulation(
    thinking_fund: LiveTradingFund,
    args: argparse.Namespace,
    tickers: List[str],
) -> None:
    """Run single day simulation"""
    if not args.date:
        print("Error: Please provide --date or --start-date/--end-date")
        sys.exit(1)

    if not thinking_fund.validate_date_format(args.date):
        print(f"Error: Invalid date format: {args.date} (need YYYY-MM-DD)")
        sys.exit(1)

    _results = thinking_fund.run_full_day_simulation(
        date=args.date,
        tickers=tickers,
        max_comm_cycles=args.max_comm_cycles,
    )
    print(f"\n{args.date} sandbox time simulation completed!")


def main():
    """Main function"""
    try:
        args = _parse_arguments()

        # Load and override configuration
        config = LiveThinkingFundConfig()
        config.override_with_args(args)

        # Initialize system
        thinking_fund = _initialize_system(config)

        # Print configuration
        _print_configuration(config)

        # Get tickers
        tickers = args.tickers.split(",") if args.tickers else config.tickers

        # Run simulation
        _run_simulation(thinking_fund, args, config, tickers)

    except KeyboardInterrupt:
        print("\nUser interrupted simulation")
        sys.exit(1)
    except Exception as e:
        print(f"\nError during simulation: {str(e)}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
