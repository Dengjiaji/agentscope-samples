# -*- coding: utf-8 -*-
"""
Portfolio Manager Agent - Portfolio Management Agent
Provides unified portfolio management interface (based on AgentScope)
"""
# flake8: noqa: E501

import json
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from agentscope.agent import AgentBase
from agentscope.message import Msg
from pydantic import BaseModel, Field

from ..graph.state import AgentState
from ..memory.manager import get_memory
from ..utils.progress import progress
from ..utils.tool_call import tool_call
from .prompt_loader import PromptLoader


class PortfolioDecision(BaseModel):
    """Investment decision model"""

    action: Literal["long", "short", "hold"]
    quantity: Optional[int] = Field(
        default=0,
        description="Number of shares to trade (used in portfolio mode)",
    )
    confidence: float = Field(
        description="Decision confidence, between 0.0 and 100.0",
    )
    reasoning: str = Field(description="Decision reasoning")


class PortfolioManagerOutput(BaseModel):
    """Portfolio management output"""

    decisions: dict[str, PortfolioDecision] = Field(
        description="Mapping from ticker to trading decision",
    )


class PortfolioManagerAgent(AgentBase):
    """Portfolio Management Agent (based on AgentScope)"""

    def __init__(
        self,
        agent_id: str = "portfolio_manager",
        mode: str = "portfolio",
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize Portfolio Management Agent

        Args:
            agent_id: Agent ID
            mode: Mode
                - "direction": Only decision direction (long/short/hold)
                - "portfolio": specific quantity decisions
            config: Configuration dictionary

        Examples:
            >>> # Direction decision mode
            >>> agent = PortfolioManagerAgent(mode="signal")
            >>>
            >>> # Portfolio mode (includes quantity)
            >>> agent = PortfolioManagerAgent(mode="portfolio")
        """
        # Initialize AgentBase (does not accept parameters)
        super().__init__()

        # Set name attribute
        self.name = agent_id
        self.agent_id = agent_id
        self.agent_type = "portfolio_manager"

        self.mode = mode
        self.config = config or {}

        # Prompt loader
        self.prompt_loader = PromptLoader()

    def execute(self, state: AgentState) -> Dict[str, Any]:
        """
        Execute portfolio management logic

        Args:
            state: AgentState

        Returns:
            Updated state dictionary
        """
        analyst_signals = state["data"]["analyst_signals"]
        tickers = state["data"]["tickers"]

        # Collect signals for each ticker
        signals_by_ticker = {}
        current_prices = {}

        for ticker in tickers:
            progress.update_status(
                self.agent_id,
                ticker,
                "Collecting analyst signals",
            )

            ticker_signals = self._collect_signals_for_ticker(
                ticker,
                analyst_signals,
                current_prices,
            )
            signals_by_ticker[ticker] = ticker_signals

            print(f"{ticker} collected signal count: {len(ticker_signals)}")

        state["data"]["current_prices"] = current_prices
        progress.update_status(
            self.agent_id,
            None,
            "Generating investment decisions",
        )

        # Generate decisions based on mode
        if self.mode == "direction":
            result = self._generate_direction_decision(
                tickers,
                signals_by_ticker,
                state,
            )
        else:  # portfolio mode
            result = self._generate_portfolio_decision(
                tickers,
                signals_by_ticker,
                state,
            )
        # Create message (using AgentScope Msg format)
        message = Msg(
            name=self.name,
            content=json.dumps(
                {
                    ticker: decision.model_dump()
                    for ticker, decision in result.decisions.items()
                },
            ),
            role="assistant",
            metadata={"mode": self.mode},
        )

        progress.update_status(self.agent_id, None, "Done")

        return {
            "messages": [message.to_dict()],  # Convert to dict
            "data": state["data"],
        }

    def _collect_signals_for_ticker(
        self,
        ticker: str,
        analyst_signals: Dict[str, Any],
        current_prices: Dict[str, float],
    ) -> Dict[str, Dict]:
        ticker_signals = {}

        for agent, signals in analyst_signals.items():
            if agent.startswith("risk_manager"):
                self._process_risk_manager_signal(
                    agent,
                    signals,
                    ticker,
                    ticker_signals,
                    current_prices,
                )
            elif ticker in signals:
                self._process_analyst_signal(
                    agent,
                    signals,
                    ticker,
                    ticker_signals,
                )
            elif "ticker_signals" in signals:
                self._process_ticker_signals_list(
                    agent,
                    signals,
                    ticker,
                    ticker_signals,
                )

        return ticker_signals

    def _process_risk_manager_signal(
        self,
        agent: str,
        signals: dict,
        ticker: str,
        ticker_signals: dict,
        current_prices: dict,
    ) -> None:
        if ticker in signals:
            risk_info = signals[ticker]
            ticker_signals[agent] = {
                "type": "risk_assessment",
                "risk_info": {
                    i: risk_info[i] for i in risk_info if i != "reasoning"
                },
            }
            current_prices[ticker] = risk_info.get("current_price", 0)

    def _process_analyst_signal(
        self,
        agent: str,
        signals: dict,
        ticker: str,
        ticker_signals: dict,
    ) -> None:
        if "signal" in signals[ticker] and "confidence" in signals[ticker]:
            signal_data = signals[ticker]
            ticker_signals[agent] = {
                "type": "investment_signal",
                "signal": signal_data["signal"],
                "confidence": signal_data["confidence"],
            }
            self._add_error_note_if_needed(signal_data, ticker_signals[agent])

    def _process_ticker_signals_list(
        self,
        agent: str,
        signals: dict,
        ticker: str,
        ticker_signals: dict,
    ) -> None:
        for ts in signals["ticker_signals"]:
            if isinstance(ts, dict) and ts.get("ticker") == ticker:
                ticker_signals[agent] = {
                    "type": "investment_signal",
                    "signal": ts["signal"],
                    "confidence": ts["confidence"],
                }
                self._add_error_note_if_needed(ts, ticker_signals[agent])
                break

    def _add_error_note_if_needed(
        self,
        signal_data: dict,
        target: dict,
    ) -> None:
        reasoning = signal_data.get("reasoning", "")
        if (
            "Failed to synthesize" in reasoning
            or signal_data.get("synthesis_method") == "error"
        ):
            target["error_note"] = reasoning
            if "error_details" in signal_data:
                target["error_details"] = signal_data["error_details"]

    def _generate_direction_decision(
        self,
        tickers: list[str],
        signals_by_ticker: dict[str, dict],
        state: AgentState,
    ) -> PortfolioManagerOutput:
        """Generate direction decision (does not include quantity)"""
        progress.update_status(
            self.agent_id,
            None,
            "Retrieving historical decision experiences",
        )
        relevant_memories = self._recall_relevant_memories(
            tickers,
            signals_by_ticker,
        )

        # Get analyst weight information
        analyst_weights_info = self._format_analyst_weights(state)

        formatted_memories = self._format_memories_for_prompt(
            relevant_memories,
        )

        # Generate prompt
        prompt_data = {
            "signals_by_ticker": json.dumps(signals_by_ticker, indent=2),
            "analyst_weights_info": analyst_weights_info,
            "analyst_weights_separator": "\n" if analyst_weights_info else "",
            "relevant_past_experiences": formatted_memories,
        }

        # Load prompt
        try:
            system_prompt = self.prompt_loader.load_prompt(
                self.agent_type,
                "direction_decision_system",
                variables=prompt_data,
            )
            human_prompt = self.prompt_loader.load_prompt(
                self.agent_type,
                "direction_decision_human",
                variables=prompt_data,
            )
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": human_prompt},
            ]
        except FileNotFoundError as exc:
            raise FileNotFoundError(
                "Failed to load prompts. "
                "please check prompt file path for: direction_decision_human",
            ) from exc

        # Create default factory
        def create_default_output():
            return PortfolioManagerOutput(
                decisions={
                    ticker: PortfolioDecision(
                        action="hold",
                        confidence=0.0,
                        reasoning="Default decision: hold",
                    )
                    for ticker in tickers
                },
            )

        progress.update_status(
            self.agent_id,
            None,
            "Generating decisions based on signals and historical experience",
        )

        return tool_call(
            messages=messages,
            pydantic_model=PortfolioManagerOutput,
            agent_name=self.agent_id,
            state=state,
            _default_factory=create_default_output,
        )

    def _generate_portfolio_decision(
        self,
        tickers: list[str],
        signals_by_ticker: dict[str, dict],
        state: AgentState,
    ) -> PortfolioManagerOutput:
        """Generate Portfolio decision (includes quantity)"""
        progress.update_status(
            self.agent_id,
            None,
            "Retrieving historical decision experiences",
        )
        relevant_memories = self._recall_relevant_memories(
            tickers,
            signals_by_ticker,
        )

        portfolio = state["data"]["portfolio"]
        current_prices = state["data"]["current_prices"]

        # Get analyst weights
        formatted_memories = self._format_memories_for_prompt(
            relevant_memories,
        )

        # Format analyst performance stats
        analyst_performance_info = self._format_analyst_performance(state)

        # Get recent memory (win rates and last 3 trading days signals)
        recent_memory = self._get_recent_memory()

        # Generate prompt
        prompt_data = {
            "signals_by_ticker": json.dumps(
                signals_by_ticker,
                indent=2,
                ensure_ascii=False,
            ),
            "current_prices": json.dumps(current_prices, indent=2),
            "portfolio_cash": f"{portfolio.get('cash', 0):.2f}",
            "portfolio_positions": json.dumps(
                portfolio.get("positions", {}),
                indent=2,
            ),
            "margin_requirement": f"{portfolio.get('margin_requirement', 0):.2f}",
            "total_margin_used": f"{portfolio.get('margin_used', 0):.2f}",
            "analyst_performance_info": analyst_performance_info,
            "analyst_performance_separator": (
                "\n" if analyst_performance_info else ""
            ),
            "relevant_past_experiences": formatted_memories,
            "recent_memory": recent_memory,
            "recent_memory_separator": "\n" if recent_memory else "",
        }

        # Load prompt
        system_prompt = self.prompt_loader.load_prompt(
            agent_type=self.agent_type,
            prompt_name="portfolio_decision_system",
            variables=prompt_data,
        )
        human_prompt = self.prompt_loader.load_prompt(
            agent_type=self.agent_type,
            prompt_name="portfolio_decision_human",
            variables=prompt_data,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": human_prompt},
        ]
        # pdb.set_trace()

        # Create default factory
        def create_default_output():
            return PortfolioManagerOutput(
                decisions={
                    ticker: PortfolioDecision(
                        action="hold",
                        quantity=0,
                        confidence=0.0,
                        reasoning="Default decision: hold",
                    )
                    for ticker in tickers
                },
            )

        progress.update_status(
            self.agent_id,
            None,
            "Generating decisions based on signals and historical experience",
        )

        return tool_call(
            messages=messages,
            pydantic_model=PortfolioManagerOutput,
            agent_name=self.agent_id,
            state=state,
            _default_factory=create_default_output,
        )

    def _get_risk_manager_id(self) -> str:
        """Get corresponding risk manager ID"""
        if self.agent_id.startswith("portfolio_manager_portfolio_"):
            suffix = self.agent_id.split("_")[-1]
            return f"risk_manager_{suffix}"
        elif self.mode == "portfolio":
            return "risk_manager"
        else:
            return "risk_manager"

    def _format_analyst_weights(self, state: AgentState) -> str:
        """Format analyst weight information"""
        analyst_weights = state.get("data", {}).get("analyst_weights", {})
        okr_state = state.get("data", {}).get("okr_state", {})

        if not analyst_weights:
            return ""

        info = (
            "Analyst performance weights "
            "(based on recent investment signal accuracy):\n"
        )
        sorted_weights = sorted(
            analyst_weights.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        for analyst_id, weight in sorted_weights:
            new_hire_info = ""
            if okr_state and okr_state.get("new_hires", {}).get(analyst_id):
                new_hire_info = " (Newly hired analyst)"

            progress_bar_length = int(weight * 20)
            progress_bar = "█" * progress_bar_length + "░" * (
                20 - progress_bar_length
            )

            info += (
                f"  {analyst_id}: {weight:.3f} {progress_bar}{new_hire_info}\n"
            )

        info += (
            "\n💡 Suggestion: Consider the importance of "
            "different analyst recommendations based on weight levels."
        )
        return info

    def _format_analyst_performance(self, state: AgentState) -> str:
        """Format analyst historical performance information"""
        analyst_stats = state.get("data", {}).get("analyst_stats", {})

        if not analyst_stats:
            return ""

        info = "Analyst Historical Performance (Win Rates & Track Record):\n"

        # Sort by win rate (highest first)
        sorted_analysts = sorted(
            analyst_stats.items(),
            key=lambda x: (
                x[1].get("win_rate", 0)
                if x[1].get("win_rate") is not None
                else 0
            ),
            reverse=True,
        )

        for analyst_id, stats in sorted_analysts:
            win_rate = stats.get("win_rate")
            total_predictions = stats.get("total_predictions", 0)
            correct_predictions = stats.get("correct_predictions", 0)

            if win_rate is not None:
                win_rate_pct = win_rate * 100
                performance_bar_length = int(win_rate * 20)
                performance_bar = "█" * performance_bar_length + "░" * (
                    20 - performance_bar_length
                )

                # Get bull/bear breakdown
                bull_info = stats.get("bull", {})
                bear_info = stats.get("bear", {})
                bull_count = bull_info.get("count", 0)
                bull_win = bull_info.get("win", 0)
                bear_count = bear_info.get("count", 0)
                bear_win = bear_info.get("win", 0)

                info += f"\n  {analyst_id}:\n"
                info += (
                    f"    Win Rate: {win_rate_pct:.1f}% {performance_bar} "
                    f"({correct_predictions}/{total_predictions} correct)\n"
                )
                info += (
                    f"    Bullish: {bull_win}/{bull_count} correct |"
                    f" Bearish: {bear_win}/{bear_count} correct\n"
                )
            else:
                info += f"\n  {analyst_id}: No historical data yet\n"

        return info

    def _recall_relevant_memories(
        self,
        tickers: List[str],
        signals_by_ticker: Dict[str, Dict],
        top_k: int = 1,
    ) -> Dict[str, List[str]]:
        """
        Step 1: Retrieve relevant historical decision experiences

        Retrieve relevant historical memories to help PM make better decisions

        Args:
            tickers: Stock ticker list
            signals_by_ticker: Analyst signals grouped by ticker
            state: Current state
            top_k: Number of memories to return per ticker

        Returns:
            Dictionary, key is ticker, value is list of relevant memories
            Example: {
                'AAPL': [
                    "2024-01-15: Made long decision under similar signal combination...",
                    "2024-01-20: Need to be more cautious when..."
                ]
            }
        """
        memories_by_ticker = {}

        try:
            # Get base_dir (from config or use default)
            base_dir = self.config.get("base_dir", "default")

            # Get memory instance
            memory = get_memory(base_dir)

            # ⭐ Uniformly use "portfolio_manager" as memory's user_id
            # Whether direction or portfolio mode, use the same memory space
            # This allows sharing experiences and avoids memory fragmentation
            memory_user_id = "portfolio_manager"

            # Generate search query for each ticker and retrieve memories
            for ticker in tickers:
                # Generate search query (based on current signal combination)
                ticker_signals = signals_by_ticker.get(ticker, {})
                query = self._generate_memory_query(ticker, ticker_signals)

                # Retrieve relevant memories from memory system
                try:
                    # Directly call memory.search
                    relevant_memories = memory.search(
                        query=query,
                        user_id=memory_user_id,
                        top_k=top_k,
                    )

                    # Format memories as readable strings
                    memory_strings = []
                    for mem in relevant_memories:
                        if isinstance(mem, dict):
                            # format: {'id': ..., 'content': ..., 'metadata': ...}
                            memory_content = mem.get("content", str(mem))
                            memory_strings.append(memory_content)
                        else:
                            memory_strings.append(str(mem))

                    memories_by_ticker[ticker] = memory_strings

                    if memory_strings:
                        print(
                            f"✔ {ticker}: Retrieved {len(memory_strings)} "
                            f"relevant historical experiences",
                        )

                except Exception as e:
                    print(f"⚠️ {ticker}: Memory retrieval failed - {e}")
                    memories_by_ticker[ticker] = []

        except Exception as e:
            print(f"⚠️ Memory system unavailable - {e}")
            # If memory system is unavailable, return empty dictionary
            for ticker in tickers:
                memories_by_ticker[ticker] = []

        return memories_by_ticker

    def _generate_memory_query(
        self,
        ticker: str,
        ticker_signals: Dict[str, Dict],
    ) -> str:
        """
        Generate memory search query

        Generate targeted search query based on current signal combination
        to find historical decisions under similar circumstances

        Args:
            ticker: Stock ticker
            ticker_signals: Analyst signals for this ticker

        Returns:
            Search query string
        """
        # Extract signal directions and confidence
        signal_directions = []

        for _, signal_data in ticker_signals.items():
            if signal_data.get("type") == "investment_signal":
                direction = signal_data.get("signal", "")
                # confidence = signal_data.get("confidence", 0)

                signal_directions.append(direction)

        # Build query
        query_parts = [f"{ticker} investment decision"]

        # Add main signal direction
        if signal_directions:
            bullish_count = signal_directions.count("bullish")
            bearish_count = signal_directions.count("bearish")

            if bullish_count > bearish_count:
                query_parts.append("bullish signals")
            elif bearish_count > bullish_count:
                query_parts.append("bearish signals")
            else:
                query_parts.append("signal divergence")

        query = " ".join(query_parts)
        return query

    def _format_memories_for_prompt(
        self,
        memories_by_ticker: Dict[str, List[str]],
    ) -> str:
        """
        Helper method for Step 2: Format memories as prompt-ready text

        Args:
            memories_by_ticker: Memories grouped by ticker

        Returns:
            Formatted memory text
        """
        if not memories_by_ticker or not any(memories_by_ticker.values()):
            return "No relevant historical experience available."

        formatted_lines = []

        for ticker, memories in memories_by_ticker.items():
            if not memories:
                continue

            formatted_lines.append(
                f"\n**{ticker} Relevant Historical Experience:**",
            )
            for i, memory in enumerate(memories, 1):
                formatted_lines.append(f"  {i}. {memory}")

        if not formatted_lines:
            return "No relevant historical experience available."

        return "\n".join(formatted_lines)

    def _get_recent_memory(self) -> str:  # noqa: ARG002
        """
        Get recent memory:
        - latest win rates
        - last 3 trading days signals
        for analysts and PM

        Returns:
            Formatted string with recent memory information
        """
        dashboard_dir = self._resolve_dashboard_dir()
        if not dashboard_dir:
            return ""

        # Load all data
        (
            agent_performance_data,
            internal_state,
            benchmark_returns,
        ) = self._load_dashboard_data(dashboard_dir)

        # Format output
        recent_memory_parts = ["## Recent Memory", ""]

        # Get last 3 trading dates
        sorted_dates = self._get_recent_trading_dates(
            agent_performance_data,
            3,
        )

        # Format agent data
        for agent_id, agent_data in agent_performance_data.items():
            self._format_agent_recent_data(
                agent_id,
                agent_data,
                sorted_dates,
                recent_memory_parts,
                internal_state,
            )

        # Add benchmark returns
        if benchmark_returns:
            recent_memory_parts.extend(
                self._format_benchmark_returns(benchmark_returns),
            )

        return (
            "\n".join(recent_memory_parts)
            if len(recent_memory_parts) > 2
            else ""
        )

    def _resolve_dashboard_dir(self):
        """Resolve dashboard directory from config."""
        dashboard_dir = self.config.get("dashboard_dir")

        if dashboard_dir:
            return Path(dashboard_dir)

        # Try to get sandbox_dir from config
        sandbox_dir = self.config.get("sandbox_dir")
        if sandbox_dir:
            return Path(sandbox_dir) / "team_dashboard"

        # Try to get from config_name
        config_name = self.config.get("config_name", "default")
        if config_name and config_name != "default":
            from ..config.path_config import get_directory_config

            base_dir = Path(get_directory_config(config_name))
            return base_dir / "sandbox_logs" / "team_dashboard"

        print(
            "⚠️ Dashboard directory not configured, skipping recent memory",
        )
        return None

    def _load_dashboard_data(self, dashboard_dir):
        """Load leaderboard, summary and internal state data."""
        leaderboard_file = dashboard_dir / "leaderboard.json"
        summary_file = dashboard_dir / "summary.json"
        internal_state_file = dashboard_dir / "_internal_state.json"

        agent_performance_data = self._load_leaderboard(leaderboard_file)
        internal_state = self._load_internal_state(internal_state_file)
        benchmark_returns = self._load_benchmark_returns(summary_file)

        return agent_performance_data, internal_state, benchmark_returns

    def _load_leaderboard(self, leaderboard_file):
        """Load leaderboard data."""
        agent_performance_data = {}
        if not leaderboard_file.exists():
            return agent_performance_data

        try:
            with open(leaderboard_file, "r", encoding="utf-8") as f:
                leaderboard = json.load(f)
                for agent in leaderboard:
                    agent_id = agent.get("agentId", "")
                    agent_performance_data[agent_id] = {
                        "winRate": agent.get("winRate"),
                        "signals": agent.get("signals", []),
                    }
        except Exception as e:
            print(f"⚠️ Failed to load leaderboard data: {e}")

        return agent_performance_data

    def _load_internal_state(self, internal_state_file):
        """Load internal state data."""
        internal_state = {}
        if not internal_state_file.exists():
            return internal_state

        try:
            with open(internal_state_file, "r", encoding="utf-8") as f:
                internal_state = json.load(f)
        except Exception as e:
            print(f"⚠️ Failed to load internal state: {e}")

        return internal_state

    def _load_benchmark_returns(self, summary_file):
        """Load and calculate benchmark returns from summary data."""
        benchmark_returns = {}
        if not summary_file.exists():
            return benchmark_returns

        try:
            with open(summary_file, "r", encoding="utf-8") as f:
                summary = json.load(f)
                equity = summary.get("equity", [])
                baseline = summary.get("baseline", [])
                baseline_vw = summary.get("baseline_vw", [])
                momentum = summary.get("momentum", [])

                initial_value = 100000.0
                if equity and len(equity) > 0:
                    initial_value = (
                        equity[0].get("v", 100000.0)
                        if isinstance(equity[0], dict)
                        else equity[0]
                    )

                    # Calculate returns for all benchmarks
                    self._calculate_benchmark_return(
                        equity,
                        initial_value,
                        "portfolio",
                        benchmark_returns,
                    )
                    self._calculate_benchmark_return(
                        baseline,
                        initial_value,
                        "baseline",
                        benchmark_returns,
                    )
                    self._calculate_benchmark_return(
                        baseline_vw,
                        initial_value,
                        "baseline_vw",
                        benchmark_returns,
                    )
                    self._calculate_benchmark_return(
                        momentum,
                        initial_value,
                        "momentum",
                        benchmark_returns,
                    )
        except Exception as e:
            print(f"⚠️ Failed to load summary data: {e}")

        return benchmark_returns

    def _calculate_benchmark_return(
        self,
        equity_data,
        initial_value,
        name,
        benchmark_returns,
    ):
        """Calculate cumulative and daily returns for a benchmark."""
        if not equity_data or len(equity_data) == 0:
            return

        # Calculate cumulative return
        current_value = (
            equity_data[-1].get("v", initial_value)
            if isinstance(equity_data[-1], dict)
            else equity_data[-1]
        )
        cumulative_return = (
            (current_value - initial_value) / initial_value
        ) * 100
        benchmark_returns[name] = cumulative_return

        # Calculate daily returns
        daily_returns = self._calculate_daily_returns(
            equity_data,
            initial_value,
        )
        benchmark_returns[f"{name}_recent_daily_returns"] = daily_returns

    def _calculate_daily_returns(self, equity_data, initial_value):
        """Calculate last 3 daily returns from equity data."""
        daily_returns = []
        if len(equity_data) < 2:
            return daily_returns

        for i in range(max(1, len(equity_data) - 3), len(equity_data)):
            prev_value = (
                equity_data[i - 1].get("v", initial_value)
                if isinstance(equity_data[i - 1], dict)
                else equity_data[i - 1]
            )
            curr_value = (
                equity_data[i].get("v", initial_value)
                if isinstance(equity_data[i], dict)
                else equity_data[i]
            )
            if prev_value > 0:
                daily_return = ((curr_value - prev_value) / prev_value) * 100
                daily_returns.append(daily_return)

        return daily_returns

    def _get_recent_trading_dates(self, agent_performance_data, num_days=3):
        """Get last N trading dates from agent signals."""
        all_dates = set()
        for agent_data in agent_performance_data.values():
            signals = agent_data.get("signals", [])
            for signal in signals:
                date = signal.get("date", "")
                if date:
                    all_dates.add(date)

        return sorted(all_dates, reverse=True)[:num_days]

    def _format_benchmark_returns(self, benchmark_returns):
        """Format benchmark returns section."""
        lines = ["### Benchmark Performance"]

        # Current cumulative returns
        if "baseline" in benchmark_returns:
            lines.append(
                f"- Buy & Hold (Equal Weight): "
                f"{benchmark_returns['baseline']:+.2f}%",
            )
        if "baseline_vw" in benchmark_returns:
            lines.append(
                f"- Buy & Hold (Value Weighted): "
                f"{benchmark_returns['baseline_vw']:+.2f}%",
            )
        if "momentum" in benchmark_returns:
            lines.append(
                f"- Momentum Strategy: "
                f"{benchmark_returns['momentum']:+.2f}%",
            )
        if "portfolio" in benchmark_returns:
            portfolio_return = benchmark_returns["portfolio"]
            lines.append(
                f"- Portfolio (EvoTraders): {portfolio_return:+.2f}%",
            )
            if "baseline_vw" in benchmark_returns:
                excess_return = (
                    portfolio_return - benchmark_returns["baseline_vw"]
                )
                lines.append(f"- Excess Return vs VW: {excess_return:+.2f}%")

        # Daily returns
        lines.append("")
        lines.append("**Last 3 Trading Days Stategy Returns Change Log:**")
        self._append_daily_returns(lines, benchmark_returns)
        lines.append("")

        return lines

    def _append_daily_returns(self, lines, benchmark_returns):
        """Append daily returns for all benchmarks."""
        benchmarks = [
            ("portfolio_recent_daily_returns", "Portfolio (EvoTraders)"),
            ("baseline_recent_daily_returns", "Buy & Hold (Equal Weight)"),
            (
                "baseline_vw_recent_daily_returns",
                "Buy & Hold (Value Weighted)",
            ),
            ("momentum_recent_daily_returns", "Momentum Strategy"),
        ]

        for key, label in benchmarks:
            daily_returns = benchmark_returns.get(key)
            if daily_returns:
                returns_str = ", ".join([f"{r:+.2f}%" for r in daily_returns])
                lines.append(f"- {label}: {returns_str}")

    def _format_agent_recent_data(
        self,
        agent_id: str,
        agent_data: dict,
        sorted_dates: list,
        recent_memory_parts: list,
        internal_state: dict,
    ) -> None:
        """Format recent data for a single agent"""
        win_rate = agent_data.get("winRate")
        signals = agent_data.get("signals", [])

        recent_signals = [
            s for s in signals if s.get("date", "") in sorted_dates
        ]
        recent_signals.sort(
            key=lambda x: (x.get("date", ""), x.get("ticker", "")),
            reverse=True,
        )

        if win_rate is not None or recent_signals:
            agent_name = agent_id.replace("_", " ").title()
            recent_memory_parts.append(f"### {agent_name}")

            if win_rate is not None:
                recent_memory_parts.append(
                    f"- Latest Win Rate: {win_rate*100:.2f}%",
                )

            if recent_signals:
                if agent_id == "portfolio_manager":
                    recent_memory_parts.append(
                        "- Last 3 Trading Days Decisions:",
                    )
                    recent_memory_parts.extend(
                        self._format_pm_signals_with_trades(
                            recent_signals,
                            sorted_dates,
                            internal_state,
                        ),
                    )
                else:
                    recent_memory_parts.append(
                        "- Last 3 Trading Days Signals:",
                    )
                    self._append_analyst_signals(
                        recent_signals,
                        sorted_dates,
                        recent_memory_parts,
                    )

            recent_memory_parts.append("")

    def _append_analyst_signals(
        self,
        recent_signals: list,
        sorted_dates: list,
        recent_memory_parts: list,
    ) -> None:
        """Append analyst signals to memory parts"""
        signals_by_date = {}
        for signal in recent_signals:
            date = signal.get("date", "")
            if date not in signals_by_date:
                signals_by_date[date] = []
            signals_by_date[date].append(signal)

        for date in sorted(sorted_dates, reverse=True):
            if date in signals_by_date:
                recent_memory_parts.append(f"  **{date}:**")
                for signal in signals_by_date[date]:
                    ticker = signal.get("ticker", "")
                    signal_value = signal.get("signal", "")
                    real_return = signal.get("real_return", "N/A")
                    is_correct = signal.get("is_correct", "unknown")

                    correct_marker = ""
                    if is_correct is True:
                        correct_marker = " ✓"
                    elif is_correct is False:
                        correct_marker = " ✗"
                    else:
                        correct_marker = " ?"

                    recent_memory_parts.append(
                        f"    - {ticker}: {signal_value} "
                        f"(Real Return: {real_return}){correct_marker}",
                    )

    def _format_pm_signals_with_trades(
        self,
        recent_signals: List[Dict],
        sorted_dates: List[str],
        internal_state: Dict,
    ) -> List[str]:
        """Format PM signals with detailed trade information"""

        formatted_lines = []

        # Get data from internal state
        all_trades = internal_state.get("all_trades", [])
        equity_history = internal_state.get("equity_history", [])
        daily_position_history = internal_state.get(
            "daily_position_history",
            {},
        )

        # Build indices
        trades_by_date_ticker = self._build_trades_index(all_trades)
        equity_by_date = self._build_equity_index(equity_history)
        position_tracker = self._build_position_tracker(
            daily_position_history,
            all_trades,
        )

        # Group signals by date
        signals_by_date = self._group_signals_by_date(recent_signals)

        # Process each date
        dates_list = sorted(equity_by_date.keys())
        for date in sorted(sorted_dates, reverse=True):
            if date not in signals_by_date:
                continue

            self._format_date_section(
                formatted_lines,
                date,
                signals_by_date[date],
                trades_by_date_ticker,
                position_tracker,
                equity_by_date,
                dates_list,
            )

        return formatted_lines

    # 新增辅助方法：

    def _build_trades_index(self, all_trades: List[Dict]) -> Dict:
        """Build trades index by (date, ticker)"""
        from datetime import datetime

        trades_by_date_ticker = {}
        for trade in all_trades:
            trade_date = trade.get("trading_date")
            if not trade_date:
                ts = trade.get("ts") or trade.get("timestamp", 0)
                if ts:
                    trade_date = datetime.fromtimestamp(ts / 1000).strftime(
                        "%Y-%m-%d",
                    )

            if trade_date:
                ticker = trade.get("ticker", "")
                key = (trade_date, ticker)
                if key not in trades_by_date_ticker:
                    trades_by_date_ticker[key] = []
                trades_by_date_ticker[key].append(trade)

        return trades_by_date_ticker

    def _build_equity_index(self, equity_history: List[Dict]) -> Dict:
        """Build equity history by date"""
        from datetime import datetime

        equity_by_date = {}
        for point in equity_history:
            if "t" in point and "v" in point:
                date_str = datetime.fromtimestamp(point["t"] / 1000).strftime(
                    "%Y-%m-%d",
                )
                equity_by_date[date_str] = point["v"]

        return equity_by_date

    def _build_position_tracker(
        self,
        daily_position_history: Dict,
        all_trades: List[Dict],
    ) -> Dict:
        """Build position tracker"""
        if daily_position_history:
            return self._build_position_from_history(daily_position_history)
        else:
            return self._build_position_from_trades(all_trades)

    def _build_position_from_history(
        self,
        daily_position_history: Dict,
    ) -> Dict:
        """Fast path: Use pre-computed daily position snapshots"""
        position_tracker = {}
        dates_list = sorted(daily_position_history.keys())

        for i, date in enumerate(dates_list):
            all_tickers_seen = set()
            for d in dates_list[: i + 1]:
                all_tickers_seen.update(daily_position_history[d].keys())

            for ticker in all_tickers_seen:
                if i == 0:
                    position_tracker[(date, ticker)] = 0
                else:
                    prev_date = dates_list[i - 1]
                    prev_closing = daily_position_history.get(
                        prev_date,
                        {},
                    ).get(
                        ticker,
                        0,
                    )
                    position_tracker[(date, ticker)] = prev_closing

        return position_tracker

    def _build_position_from_trades(self, all_trades: List[Dict]) -> Dict:
        """Fallback: Rebuild from all_trades"""
        from datetime import datetime

        sorted_trades = sorted(
            all_trades,
            key=lambda x: x.get("ts") or x.get("timestamp", 0),
        )

        daily_positions = {}
        current_positions = {}

        for trade in sorted_trades:
            trade_date = trade.get("trading_date")
            if not trade_date:
                ts = trade.get("ts") or trade.get("timestamp", 0)
                if not ts:
                    continue
                trade_date = datetime.fromtimestamp(ts / 1000).strftime(
                    "%Y-%m-%d",
                )

            ticker = trade.get("ticker", "")
            qty = trade.get("qty", 0)
            side = trade.get("side", "")

            if ticker not in current_positions:
                current_positions[ticker] = 0

            if side == "LONG":
                current_positions[ticker] += qty
            elif side == "SHORT":
                current_positions[ticker] -= qty

            if trade_date not in daily_positions:
                daily_positions[trade_date] = {}
            daily_positions[trade_date][ticker] = current_positions[ticker]

        # Build position tracker
        position_tracker = {}
        dates_list = sorted(daily_positions.keys())
        for i, date in enumerate(dates_list):
            all_tickers_seen = set()
            for d in dates_list[: i + 1]:
                all_tickers_seen.update(daily_positions[d].keys())

            for ticker in all_tickers_seen:
                if i == 0:
                    position_tracker[(date, ticker)] = 0
                else:
                    prev_date = dates_list[i - 1]
                    prev_closing = daily_positions.get(prev_date, {}).get(
                        ticker,
                        0,
                    )
                    position_tracker[(date, ticker)] = prev_closing

        return position_tracker

    def _group_signals_by_date(self, recent_signals: List[Dict]) -> Dict:
        """Group signals by date"""
        signals_by_date = {}
        for signal in recent_signals:
            date = signal.get("date", "")
            if date not in signals_by_date:
                signals_by_date[date] = []
            signals_by_date[date].append(signal)
        return signals_by_date

    def _format_date_section(
        self,
        formatted_lines: List[str],
        date: str,
        signals: List[Dict],
        trades_by_date_ticker: Dict,
        position_tracker: Dict,
        equity_by_date: Dict,
        dates_list: List[str],
    ):
        """Format a single date section"""
        formatted_lines.append(f"  **{date}:**")

        # Calculate portfolio daily return
        portfolio_daily_return = self._calculate_portfolio_return(
            date,
            equity_by_date,
            dates_list,
        )

        # Process each ticker's signal
        for signal in signals:
            self._format_ticker_line(
                formatted_lines,
                date,
                signal,
                trades_by_date_ticker,
                position_tracker,
            )

        # Add portfolio daily return
        if portfolio_daily_return is not None:
            formatted_lines.append(
                f" Portfolio Daily Return: {portfolio_daily_return:+.2f}%",
            )

        formatted_lines.append("")

    def _calculate_portfolio_return(
        self,
        date: str,
        equity_by_date: Dict,
        dates_list: List[str],
    ) -> Optional[float]:
        """Calculate portfolio daily return"""
        if date not in equity_by_date:
            return None

        try:
            date_idx = dates_list.index(date)
            if date_idx > 0:
                prev_equity = equity_by_date[dates_list[date_idx - 1]]
                curr_equity = equity_by_date[date]
                if prev_equity > 0:
                    return ((curr_equity - prev_equity) / prev_equity) * 100
        except (ValueError, IndexError):
            pass

        return None

    def _format_ticker_line(
        self,
        formatted_lines: List[str],
        date: str,
        signal: Dict,
        trades_by_date_ticker: Dict,
        position_tracker: Dict,
    ):
        """Format a single ticker line"""
        ticker = signal.get("ticker", "")
        real_return = signal.get("real_return", "N/A")
        is_correct = signal.get("is_correct", "unknown")

        # Get trades for this ticker on this date
        ticker_trades = trades_by_date_ticker.get((date, ticker), [])

        # Get pre-position
        pre_position = position_tracker.get((date, ticker), 0)

        # Calculate action from trades
        action_qty = sum(
            trade.get("qty", 0)
            if trade.get("side") == "LONG"
            else -trade.get("qty", 0)
            for trade in ticker_trades
        )

        # Calculate final position
        final_position = pre_position + action_qty

        # Format display
        pre_pos_str = self._format_position(pre_position)
        action_str = self._format_action(action_qty)
        final_pos_str = self._format_position(final_position)
        correct_marker = self._get_correct_marker(is_correct)

        formatted_lines.append(
            f"    - {ticker}: "
            f"[{pre_pos_str}] → [{action_str}] → "
            f"[{final_pos_str}] "
            f"(Stock Return: {real_return}){correct_marker}",
        )

    def _format_position(self, pos: int) -> str:
        """Format position display"""
        if pos > 0:
            return f"{pos} long"
        elif pos < 0:
            return f"{abs(pos)} short"
        else:
            return "0"

    def _format_action(self, action_qty: int) -> str:
        """Format action display"""
        if action_qty > 0:
            return f"long {action_qty}"
        elif action_qty < 0:
            return f"short {abs(action_qty)}"
        else:
            return "hold"

    def _get_correct_marker(self, is_correct) -> str:
        """Get correct marker"""
        if is_correct is True:
            return " ✓"
        elif is_correct is False:
            return " ✗"
        else:
            return " ?"
