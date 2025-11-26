#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Multi-Day Strategy Manager
Handles multi-day running, state persistence, performance analysis, and reporting
"""
# flake8: noqa: E501

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import exchange_calendars as xcals
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pandas_market_calendars as mcal
import seaborn as sns
from dateutil.relativedelta import relativedelta
from matplotlib import rcParams

from backend.config.path_config import get_directory_config
from backend.tools.data_tools import (
    get_company_news,
    get_financial_metrics,
    get_insider_trades,
    get_prices,
)

# Setup plotting style
rcParams["axes.unicode_minus"] = False
plt.style.use("seaborn-v0_8")
sns.set_palette("husl")


class MultiDayStrategy:
    """Multi-Day Strategy Manager - Handles multi-day running, state management, and performance analysis"""

    def __init__(
        self,
        engine,  # InvestmentEngine instance
        config_name: str = "default",
        mode: str = "signal",
        initial_cash: float = 100000.0,
        margin_requirement: float = 0.0,
        prefetch_data: bool = True,
        **kwargs,
    ):
        """
        Initialize multi-day strategy manager

        Args:
            engine: Investment engine instance
            config_name: Configuration name for memory system
            mode: Running mode ("signal" or "portfolio")
            initial_cash: Initial cash for portfolio mode
            margin_requirement: Margin requirement for portfolio mode
            prefetch_data: Whether to prefetch data
        """
        self.engine = engine
        self.config_name = config_name
        self.mode = mode
        self.initial_cash = initial_cash
        self.margin_requirement = margin_requirement
        self.prefetch_data = prefetch_data

        # Setup directories
        self.base_dir = Path(get_directory_config(config_name))
        self.data_dir = self.base_dir / "live_trading" / "data"
        self.reports_dir = self.base_dir / "live_trading" / "reports"
        self.charts_dir = self.reports_dir / "charts"
        self.state_dir = self.base_dir / "state"

        self._create_directories()

        # State tracking
        self.portfolio_state = None
        self.daily_results = []
        self.session_id = None

        # Cache NYSE calendar object (avoid repeated loading)
        self.nyse_calendar = None
        if "mcal" in globals():
            try:
                self.nyse_calendar = mcal.get_calendar("NYSE")
            except Exception as e:
                print(f"⚠️ Failed to load NYSE calendar: {e}")

        # Initialize portfolio state
        if self.mode == "portfolio":
            self._initialize_portfolio_state()

    def _create_directories(self):
        """Create necessary directory structure"""
        directories = [
            self.base_dir,
            # self.data_dir,
            # self.reports_dir,
            # self.charts_dir,
            self.state_dir,
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    def _initialize_portfolio_state(self):
        """Initialize portfolio state (prioritize loading latest state)"""
        # Try to load latest portfolio state
        latest_state = self._load_latest_portfolio_state()

        if latest_state:
            self.portfolio_state = latest_state
            positions_count = len(
                [
                    p
                    for p in latest_state.get("positions", {}).values()
                    if p.get("long", 0) > 0 or p.get("short", 0) > 0
                ],
            )
            print(
                f"✅ Loaded portfolio state from disk: Cash ${latest_state['cash']:,.2f}, "
                f"Positions {positions_count}",
            )
        else:
            # Initialize new state
            self.portfolio_state = {
                "cash": self.initial_cash,
                "positions": {},
                "margin_requirement": self.margin_requirement,
                "margin_used": 0.0,
            }
            print(
                f"✅ Initialized portfolio state: Cash ${self.initial_cash:,.2f}",
            )

    def _load_latest_portfolio_state(self) -> Optional[Dict[str, Any]]:
        """Load latest portfolio state"""
        portfolio_files = sorted(self.state_dir.glob("portfolio_*.json"))
        if portfolio_files:
            latest_file = portfolio_files[-1]
            try:
                with open(latest_file, "r") as f:
                    state = json.load(f)
                return state
            except Exception as e:
                print(
                    f"⚠️ Failed to load portfolio state ({latest_file}): {e}",
                )
        return None

    def _save_portfolio_state(self, date: str, portfolio: Dict[str, Any]):
        """Save portfolio state to disk"""
        state_file = (
            self.state_dir / f"portfolio_{date.replace('-', '_')}.json"
        )
        try:
            with open(state_file, "w") as f:
                json.dump(portfolio, f, indent=2, default=str)
        except Exception as e:
            print(f"❌ Failed to save portfolio state: {e}")

    def reset_portfolio_state(self):
        """Reset portfolio state (for new multi-day run)"""
        if self.mode == "portfolio":
            self.portfolio_state = {
                "cash": self.initial_cash,
                "positions": {},
                "margin_requirement": self.margin_requirement,
                "margin_used": 0.0,
            }
            print(f"🔄 Portfolio state reset: Cash ${self.initial_cash:,.2f}")

    def is_trading_day(self, date: str) -> bool:
        """Check if it's a trading day (using cached calendar object)"""
        if self.nyse_calendar:
            try:
                trading_dates = self.nyse_calendar.valid_days(
                    start_date=date,
                    end_date=date,
                )
                return len(trading_dates) > 0
            except Exception as e:
                print(f"⚠️ Failed to check trading day ({date}): {e}")
                return True  # Default to trading day on error

        # Fallback: use exchange_calendars
        if "xcals" in globals():
            try:
                nyse = xcals.get_calendar("XNYS")  # NYSE ISO code
                trading_dates = nyse.sessions_in_range(date, date)
                return len(trading_dates) > 0
            except Exception:
                pass

        return True  # Default to trading day

    def get_trading_dates(self, start_date: str, end_date: str) -> List[str]:
        """
        Get US stock market trading date sequence

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            List of trading dates
        """
        try:
            # Priority: use pandas_market_calendars
            if "mcal" in globals():
                nyse = mcal.get_calendar("NYSE")
                trading_dates = nyse.valid_days(
                    start_date=start_date,
                    end_date=end_date,
                )
                return [date.strftime("%Y-%m-%d") for date in trading_dates]

            # Alternative: use exchange_calendars
            elif "xcals" in globals():
                nyse = xcals.get_calendar("XNYS")  # NYSE ISO code
                trading_dates = nyse.sessions_in_range(start_date, end_date)
                return [date.strftime("%Y-%m-%d") for date in trading_dates]

        except Exception as e:
            print(
                f"⚠️ Failed to get US trading calendar, falling back to simple business days: {e}",
            )

        # Fallback to simple business day method
        date_range = pd.date_range(start_date, end_date, freq="B")
        return [date.strftime("%Y-%m-%d") for date in date_range]

    def prefetch_all_data(
        self,
        tickers: List[str],
        start_date: str,
        end_date: str,
    ):
        """Prefetch all data needed for multi-day analysis"""
        if not self.prefetch_data:
            return

        print(f"\nPrefetching data ({start_date} to {end_date})...")

        # Extend data fetch range to ensure sufficient historical data
        end_date_dt = datetime.strptime(end_date, "%Y-%m-%d")
        extended_start_dt = end_date_dt - relativedelta(years=1)
        extended_start = extended_start_dt.strftime("%Y-%m-%d")

        for ticker in tickers:
            try:
                # Prefetch price data
                get_prices(ticker, extended_start, end_date)

                # Prefetch financial metrics
                get_financial_metrics(ticker, end_date, limit=20)

                # Prefetch insider trades
                get_insider_trades(
                    ticker,
                    end_date,
                    start_date=start_date,
                    limit=1000,
                )

                # Prefetch news data
                get_company_news(
                    ticker,
                    end_date,
                    start_date=start_date,
                    limit=1000,
                )

            except Exception as e:
                print(f"Warning: Error prefetching {ticker} data: {e}")

        print("Data prefetch completed")

    def run_single_day(
        self,
        tickers: List[str],
        date: str,
        enable_communications: bool = True,
        enable_notifications: bool = True,
        max_comm_cycles: int = 2,
        analyst_stats: Optional[Dict[str, Any]] = None,
        is_live_mode: bool = False,
    ) -> Dict[str, Any]:
        """
        Run single day analysis

        Args:
            tickers: List of stock symbols
            date: Trading date
            enable_communications: Whether to enable communications
            enable_notifications: Whether to enable notifications
            max_comm_cycles: Maximum communication cycles
            analyst_stats: Historical analyst performance statistics from dashboard
            is_live_mode: Whether running in live mode (affects risk manager price selection)

        Returns:
            Single day analysis result
        """
        print(f"Starting analysis for {date} (mode: {self.mode})")

        # Display portfolio state if exists
        if self.mode == "portfolio" and self.portfolio_state:
            positions_count = len(
                [
                    p
                    for p in self.portfolio_state.get("positions", {}).values()
                    if p.get("long", 0) > 0 or p.get("short", 0) > 0
                ],
            )
            print(
                f"📌 Using existing portfolio state: Cash ${self.portfolio_state['cash']:,.2f}, "
                f"Positions {positions_count}",
            )

        # Run analysis
        result = self.engine.run_single_day_analysis(
            tickers=tickers,
            date=date,
            portfolio_state=self.portfolio_state,
            mode=self.mode,
            enable_communications=enable_communications,
            enable_notifications=enable_notifications,
            max_comm_cycles=max_comm_cycles,
            initial_cash=self.initial_cash,
            margin_requirement=self.margin_requirement,
            analyst_stats=analyst_stats,
            is_live_mode=is_live_mode,
        )

        # Update portfolio state
        if self.mode == "portfolio" and "updated_portfolio" in result:
            updated_portfolio = result["updated_portfolio"]
            if updated_portfolio:
                self.portfolio_state = updated_portfolio
                self._save_portfolio_state(date, updated_portfolio)

                # Print portfolio changes
                print(f"\n📊 Portfolio updated:")
                print(f"   Cash: ${updated_portfolio['cash']:,.2f}")
                positions_count = len(
                    [
                        p
                        for p in updated_portfolio.get(
                            "positions",
                            {},
                        ).values()
                        if p.get("long", 0) > 0 or p.get("short", 0) > 0
                    ],
                )
                print(f"   Positions: {positions_count}")
                if updated_portfolio.get("margin_used", 0) > 0:
                    print(
                        f"   Margin used: ${updated_portfolio['margin_used']:,.2f}",
                    )

        return result

    def run_multi_day(
        self,
        tickers: List[str],
        start_date: str,
        end_date: str,
        enable_communications: bool = True,
        enable_notifications: bool = True,
        max_comm_cycles: int = 2,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """
        Run multi-day strategy

        Args:
            tickers: List of stock symbols
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            enable_communications: Whether to enable communication mechanism
            enable_notifications: Whether to enable notification mechanism
            max_comm_cycles: Maximum communication cycles per day
            progress_callback: Progress callback function

        Returns:
            Multi-day analysis summary result
        """
        # Initialize session
        if self.session_id is None:
            self.session_id = (
                f"multi_day_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )

        print(
            f"Starting multi-day strategy analysis (Session ID: {self.session_id})",
        )
        print(f"Time range: {start_date} to {end_date}")
        print(f"Analysis targets: {', '.join(tickers)}")

        # Prefetch data
        if self.prefetch_data:
            self.prefetch_all_data(tickers, start_date, end_date)

        # Generate US stock market trading date sequence (considering holidays)
        trading_dates = self.get_trading_dates(start_date, end_date)

        if len(trading_dates) == 0:
            raise ValueError(
                f"No trading days in date range: {start_date} to {end_date}",
            )

        print(f"Total {len(trading_dates)} trading days to analyze")

        # Initialize summary statistics
        total_days = len(trading_dates)
        successful_days = 0
        failed_days = 0
        self.daily_results = []

        # Execute analysis day by day
        for i, current_date in enumerate(trading_dates):
            # Send progress update
            if progress_callback:
                progress_callback(
                    {
                        "type": "daily_progress",
                        "current_date": current_date,
                        "progress": (i + 1) / total_days,
                        "day_number": i + 1,
                        "total_days": total_days,
                    },
                )

            try:
                # Run single day analysis
                daily_result = self.run_single_day(
                    tickers=tickers,
                    date=current_date,
                    enable_communications=enable_communications,
                    enable_notifications=enable_notifications,
                    max_comm_cycles=max_comm_cycles,
                )

                # Record success
                successful_days += 1
                self.daily_results.append(
                    {
                        "date": current_date,
                        "status": "success",
                        "results": daily_result,
                    },
                )

                print(f"{current_date} analysis completed")

                # Send single day result
                if progress_callback:
                    progress_callback(
                        {
                            "type": "daily_result",
                            "date": current_date,
                            "status": "success",
                            "data": daily_result,
                        },
                    )

            except Exception as e:
                import traceback

                error_msg = str(e)
                full_traceback = traceback.format_exc()

                print(f"Error: {current_date} analysis failed: {error_msg}")

                failed_days += 1
                self.daily_results.append(
                    {
                        "date": current_date,
                        "status": "failed",
                        "error": error_msg,
                        "full_traceback": full_traceback,
                    },
                )

                # Send failure notification
                if progress_callback:
                    progress_callback(
                        {
                            "type": "daily_result",
                            "date": current_date,
                            "status": "failed",
                            "error": str(e),
                        },
                    )

        # Generate multi-day summary report
        summary_results = self.generate_summary_report()

        print(f"\nMulti-day strategy analysis completed!")
        print(f"Success: {successful_days} days")
        print(f"Failed: {failed_days} days")
        print(f"Success rate: {successful_days/total_days*100:.1f}%")

        return summary_results

    def generate_summary_report(self) -> Dict[str, Any]:
        """Generate multi-day summary report"""
        # Calculate summary statistics
        successful_results = [
            r for r in self.daily_results if r["status"] == "success"
        ]

        # Extract key metrics time series
        portfolio_values = []

        for daily_result in successful_results:
            date = daily_result["date"]
            results = daily_result.get("results", {})

            # Portfolio value changes
            if "portfolio_management_results" in results:
                pm_results = results["portfolio_management_results"]
                portfolio_summary = pm_results.get("portfolio_summary", {})
                if portfolio_summary:
                    portfolio_values.append(
                        {
                            "date": date,
                            "total_value": portfolio_summary.get(
                                "total_value",
                                0,
                            ),
                            "cash": portfolio_summary.get("cash", 0),
                            "positions_value": portfolio_summary.get(
                                "positions_value",
                                0,
                            ),
                        },
                    )

        # Get stock list (extract from first successful result)
        tickers = []
        for daily_result in successful_results:
            results = daily_result.get("results", {})
            portfolio_results = results.get("portfolio_management_results", {})
            if "final_decisions" in portfolio_results:
                tickers = list(portfolio_results["final_decisions"].keys())
                break

        # Generate summary result
        summary = {
            "session_id": self.session_id,
            "summary_timestamp": datetime.now().isoformat(),
            "period": {
                "start_date": (
                    self.daily_results[0]["date"]
                    if self.daily_results
                    else None
                ),
                "end_date": (
                    self.daily_results[-1]["date"]
                    if self.daily_results
                    else None
                ),
                "total_days": len(self.daily_results),
                "successful_days": len(successful_results),
                "failed_days": len(
                    [r for r in self.daily_results if r["status"] == "failed"],
                ),
            },
            "daily_results": self.daily_results,
            "time_series": {
                "portfolio_values": portfolio_values,
            },
            "performance_analysis": {
                "individual_stocks": (
                    self.calculate_individual_stock_performance(
                        successful_results,
                        tickers,
                    )
                    if tickers
                    else {}
                ),
            },
        }

        return summary

    def calculate_individual_stock_performance(
        self,
        daily_results: List[Dict[str, Any]],
        tickers: List[str],
    ) -> Dict[str, Dict[str, Any]]:
        """Calculate individual stock performance metrics (based on directional signals)"""
        stock_performance = {}

        for ticker in tickers:
            # Collect daily decisions and returns data for this stock
            daily_decisions = []
            daily_returns = []

            for daily_result in daily_results:
                if daily_result["status"] != "success":
                    continue

                results = daily_result.get("results", {})
                portfolio_results = results.get(
                    "portfolio_management_results",
                    {},
                )

                # Extract directional signal from final decisions
                final_decisions = portfolio_results.get("final_decisions", {})
                if ticker in final_decisions:
                    decision = final_decisions[ticker]
                    action = decision.get("action", "hold")
                    confidence = decision.get("confidence", 0)

                    daily_decisions.append(
                        {
                            "date": daily_result["date"],
                            "action": action,
                            "confidence": confidence,
                        },
                    )

                    # Calculate daily return based on directional signal
                    (
                        daily_return,
                        real_return,
                        close_price,
                    ) = self._calculate_stock_daily_return_from_signal(
                        ticker,
                        daily_result["date"],
                        action,
                    )
                    daily_returns.append(daily_return)

            if len(daily_returns) > 1:
                # Calculate performance metrics for this stock
                returns_series = pd.Series(daily_returns)

                # Calculate cumulative returns
                cumulative_returns = (1 + returns_series).cumprod()
                total_return = cumulative_returns.iloc[-1] - 1

                # Calculate maximum drawdown
                rolling_max = cumulative_returns.cummax()
                drawdowns = (cumulative_returns - rolling_max) / rolling_max
                max_drawdown = drawdowns.min()

                # Calculate Sharpe ratio (assume risk-free rate 4%)
                excess_returns = returns_series - 0.04 / 252
                sharpe_ratio = (
                    excess_returns.mean() / excess_returns.std() * (252**0.5)
                    if excess_returns.std() > 0
                    else 0
                )

                stock_performance[ticker] = {
                    "total_return_pct": round(total_return * 100, 4),
                    "mean_daily_return_pct": round(
                        returns_series.mean() * 100,
                        4,
                    ),
                    "annualized_return_pct": round(
                        returns_series.mean() * 252 * 100,
                        2,
                    ),
                    "volatility_pct": round(
                        returns_series.std() * (252**0.5) * 100,
                        2,
                    ),
                    "sharpe_ratio": round(sharpe_ratio, 3),
                    "max_drawdown_pct": round(max_drawdown * 100, 2),
                    "total_decisions": len(daily_decisions),
                    "long_decisions": len(
                        [d for d in daily_decisions if d["action"] == "long"],
                    ),
                    "short_decisions": len(
                        [d for d in daily_decisions if d["action"] == "short"],
                    ),
                    "hold_decisions": len(
                        [d for d in daily_decisions if d["action"] == "hold"],
                    ),
                    "avg_confidence": (
                        round(
                            sum(d["confidence"] for d in daily_decisions)
                            / len(daily_decisions),
                            2,
                        )
                        if daily_decisions
                        else 0
                    ),
                    "win_rate": round(
                        len([r for r in daily_returns if r > 0])
                        / len(daily_returns)
                        * 100,
                        2,
                    ),
                    "trading_days": len(daily_returns),
                }
            else:
                stock_performance[ticker] = {
                    "error": "Insufficient data, unable to calculate performance metrics for this stock",
                }

        return stock_performance

    def _calculate_stock_daily_return_from_signal(
        self,
        ticker: str,
        date,
        action: str,
    ) -> tuple:
        """
        Calculate single stock daily return based on directional signal

        Args:
            ticker: Stock symbol
            date: Date, can be string (YYYY-MM-DD) or datetime.date object
            action: Trading action ('long', 'short', 'hold')
        """
        # Get price data for this stock (get larger range to ensure sufficient data for return calculation)
        import datetime as dt
        from datetime import datetime

        # Handle date parameter, ensure conversion to date object
        if isinstance(date, str):
            target_date = pd.to_datetime(date).date()
        elif isinstance(date, dt.date):
            target_date = date
        elif isinstance(date, dt.datetime):
            target_date = date.date()

        # Use relative path to get data file
        current_dir = os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)),
        )
        data_path = os.path.join(
            current_dir,
            "data",
            "ret_data",
            f"{ticker}.csv",
        )

        prices_df = pd.read_csv(data_path)

        # Find return for specified date
        prices_df.index = pd.to_datetime(prices_df["time"]).dt.date

        # Find return closest to target date
        market_return = prices_df.loc[target_date, "ret"]
        price = prices_df.loc[target_date, "close"]
        # Calculate final return based on trading direction
        if action == "long":
            return (
                float(market_return),
                float(market_return),
                float(price),
            )  # Long: get market return
        elif action == "short":
            return (
                float(-market_return),
                float(market_return),
                float(price),
            )  # Short: get opposite of market return
        else:  # hold
            return 0.0, float(market_return), float(price)  # Hold: no return

    def create_individual_return_chart(
        self,
        ticker: str,
        ticker_data: Dict,
    ) -> str:
        """Create individual stock return chart"""
        try:
            dates = sorted(ticker_data.keys())
            cumulative_returns = [
                ticker_data[date]["cumulative_return"] for date in dates
            ]
            daily_returns = [
                ticker_data[date]["daily_return"] for date in dates
            ]

            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))

            # Upper chart: Cumulative return curve
            dates_dt = pd.to_datetime(dates)
            cumulative_pct = [(cr - 1) * 100 for cr in cumulative_returns]

            ax1.plot(
                dates_dt,
                cumulative_pct,
                linewidth=2,
                color="#2E86C1",
                label=f"{ticker} Cumulative Return",
            )
            ax1.axhline(y=0, color="gray", linestyle="--", alpha=0.5)
            ax1.set_title(
                f"{ticker} - Cumulative Return Chart",
                fontsize=14,
                fontweight="bold",
            )
            ax1.set_ylabel("Cumulative Return (%)", fontsize=12)
            ax1.legend()
            ax1.grid(True, alpha=0.3)

            # Add return label
            final_return = cumulative_pct[-1] if cumulative_pct else 0
            ax1.text(
                0.02,
                0.98,
                f"Total Return: {final_return:.2f}%",
                transform=ax1.transAxes,
                fontsize=12,
                bbox=dict(boxstyle="round", facecolor="lightblue", alpha=0.8),
                verticalalignment="top",
            )

            # Lower chart: Daily return
            daily_pct = [dr * 100 for dr in daily_returns]
            colors = ["green" if dr > 0 else "red" for dr in daily_returns]
            ax2.bar(dates_dt, daily_pct, color=colors, alpha=0.7, width=0.8)
            ax2.axhline(y=0, color="gray", linestyle="-", alpha=0.8)
            ax2.set_title(
                f"{ticker} - Daily Return",
                fontsize=14,
                fontweight="bold",
            )
            ax2.set_xlabel("Date", fontsize=12)
            ax2.set_ylabel("Daily Return (%)", fontsize=12)
            ax2.grid(True, alpha=0.3)

            # Format x-axis
            for ax in [ax1, ax2]:
                ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
                plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)

            plt.tight_layout()

            chart_path = (
                self.charts_dir
                / f"{ticker}_returns_{datetime.now().strftime('%Y%m%d')}.png"
            )
            plt.savefig(chart_path, dpi=300, bbox_inches="tight")
            plt.close()

            return str(chart_path)

        except Exception as e:
            raise RuntimeError(
                f"Failed to generate {ticker} return chart: {e}",
            )

    def create_stocks_comparison_chart(self, individual_data: Dict) -> str:
        """Create stock comparison chart"""
        try:
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))

            colors = plt.cm.Set1(np.linspace(0, 1, len(individual_data)))

            for i, (ticker, ticker_data) in enumerate(individual_data.items()):
                if not ticker_data:
                    continue

                dates = pd.to_datetime(sorted(ticker_data.keys()))
                cumulative = [
                    ticker_data[date.strftime("%Y-%m-%d")]["cumulative_return"]
                    for date in dates
                ]
                cumulative_pct = [(cr - 1) * 100 for cr in cumulative]

                ax1.plot(
                    dates,
                    cumulative_pct,
                    linewidth=2,
                    color=colors[i],
                    label=f"{ticker}",
                    marker="o",
                    markersize=3,
                )

            ax1.set_title(
                "Stocks Cumulative Return Comparison",
                fontsize=14,
                fontweight="bold",
            )
            ax1.set_ylabel("Cumulative Return (%)", fontsize=12)
            ax1.legend()
            ax1.grid(True, alpha=0.3)
            ax1.axhline(y=0, color="gray", linestyle="--", alpha=0.5)

            # Lower chart: Daily return comparison
            for i, (ticker, ticker_data) in enumerate(individual_data.items()):
                if not ticker_data:
                    continue

                dates = pd.to_datetime(sorted(ticker_data.keys()))
                daily_returns = [
                    ticker_data[date.strftime("%Y-%m-%d")]["daily_return"]
                    * 100
                    for date in dates
                ]

                ax2.plot(
                    dates,
                    daily_returns,
                    linewidth=1,
                    color=colors[i],
                    label=f"{ticker}",
                    alpha=0.7,
                )

            ax2.set_title(
                "Stocks Daily Return Comparison",
                fontsize=14,
                fontweight="bold",
            )
            ax2.set_xlabel("Date", fontsize=12)
            ax2.set_ylabel("Daily Return (%)", fontsize=12)
            ax2.legend()
            ax2.grid(True, alpha=0.3)
            ax2.axhline(y=0, color="gray", linestyle="--", alpha=0.5)

            # Format x-axis
            for ax in [ax1, ax2]:
                ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
                plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)

            plt.tight_layout()

            chart_path = (
                self.charts_dir
                / f"stocks_comparison_{datetime.now().strftime('%Y%m%d')}.png"
            )
            plt.savefig(chart_path, dpi=300, bbox_inches="tight")
            plt.close()

            return str(chart_path)

        except Exception as e:
            raise RuntimeError(
                f"Failed to generate stock comparison chart: {e}",
            )
