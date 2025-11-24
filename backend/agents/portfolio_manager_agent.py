"""
Portfolio Manager Agent - Portfolio Management Agent
Provides unified portfolio management interface (based on AgentScope)
"""
from typing import Dict, Any, Optional, Literal, List
import json
import pdb
import os
from pathlib import Path
from datetime import datetime, timedelta
from agentscope.agent import AgentBase
from agentscope.message import Msg

from ..graph.state import AgentState
from ..utils.progress import progress
from pydantic import BaseModel, Field
from .prompt_loader import PromptLoader
from typing_extensions import Literal as LiteralType
from ..utils.tool_call import tool_call
from ..memory.manager import get_memory


class PortfolioDecision(BaseModel):
    """Investment decision model"""
    action: LiteralType["long", "short", "hold"]
    quantity: Optional[int] = Field(default=0, description="Number of shares to trade (used in portfolio mode)")
    confidence: float = Field(description="Decision confidence, between 0.0 and 100.0")
    reasoning: str = Field(description="Decision reasoning")


class PortfolioManagerOutput(BaseModel):
    """Portfolio management output"""
    decisions: dict[str, PortfolioDecision] = Field(description="Mapping from ticker to trading decision")


class PortfolioManagerAgent(AgentBase):
    """Portfolio Management Agent (based on AgentScope)"""
    
    def __init__(self, 
                 agent_id: str = "portfolio_manager",
                 mode: Literal["direction", "portfolio"] = "direction",
                 config: Optional[Dict[str, Any]] = None):
        """
        Initialize Portfolio Management Agent
        
        Args:
            agent_id: Agent ID
            mode: Mode
                - "direction": Only decision direction (long/short/hold), does not include specific quantity
                - "portfolio": Includes specific quantity decisions, considers current positions
            config: Configuration dictionary
        
        Examples:
            >>> # Direction decision mode
            >>> agent = PortfolioManagerAgent(mode="direction")
            >>> 
            >>> # Portfolio mode (includes quantity)
            >>> agent = PortfolioManagerAgent(mode="portfolio")
        """
        # Initialize AgentBase (does not accept parameters)
        super().__init__()
        
        # Set name attribute
        self.name = agent_id
        self.agent_id = agent_id  # Keep agent_id attribute for compatibility with existing code
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
        
        # Debug info
        print(f"Portfolio manager received analyst signal keys: {list(analyst_signals.keys())}")
        
        # Collect signals for each ticker
        signals_by_ticker = {}
        current_prices = {}
        
        for ticker in tickers:
            progress.update_status(self.agent_id, ticker, "Collecting analyst signals")
            
            ticker_signals = self._collect_signals_for_ticker(
                ticker, analyst_signals, current_prices
            )
            signals_by_ticker[ticker] = ticker_signals
            
            print(f"{ticker} collected signal count: {len(ticker_signals)}")
        
        state["data"]["current_prices"] = current_prices
        progress.update_status(self.agent_id, None, "Generating investment decisions")
        
        # Generate decisions based on mode
        if self.mode == "direction":
            result = self._generate_direction_decision(
                tickers, signals_by_ticker, state
            )
        else:  # portfolio mode
            result = self._generate_portfolio_decision(
                tickers, signals_by_ticker, state
            )
        # Create message (using AgentScope Msg format)
        message = Msg(
            name=self.name,
            content=json.dumps({
                ticker: decision.model_dump() 
                for ticker, decision in result.decisions.items()
            }),
            role="assistant",
            metadata={"mode": self.mode}
        )

        
        progress.update_status(self.agent_id, None, "Done")
        
        return {
            "messages": [message.to_dict()],  # Convert to dict
            "data": state["data"],
        }
    
    def _collect_signals_for_ticker(self, ticker: str, 
                                   analyst_signals: Dict[str, Any],
                                   current_prices: Dict[str, float]) -> Dict[str, Dict]:
        """
        Collect all analyst signals for a single ticker
        
        Args:
            ticker: Stock ticker
            analyst_signals: Signals from all analysts
            current_prices: Current price dictionary (for storage)
        
        Returns:
            Signal dictionary for this ticker
        """
        ticker_signals = {}
        
        for agent, signals in analyst_signals.items():
            if agent.startswith("risk_manager"):
                # Risk management agent - extract risk information
                if ticker in signals:
                    risk_info = signals[ticker]
                    ticker_signals[agent] = {
                        "type": "risk_assessment",
                        "risk_info": {i: risk_info[i] for i in risk_info if i != "reasoning"}
                    }
                    current_prices[ticker] = risk_info.get("current_price", 0)
            elif ticker in signals:
                # First round format - analyst signals
                if "signal" in signals[ticker] and "confidence" in signals[ticker]:
                    ticker_signals[agent] = {
                        "type": "investment_signal", 
                        "signal": signals[ticker]["signal"], 
                        "confidence": signals[ticker]["confidence"]
                    }
            elif "ticker_signals" in signals:
                # Second round format - search ticker_signals list
                for ts in signals["ticker_signals"]:
                    if isinstance(ts, dict) and ts.get("ticker") == ticker:
                        ticker_signals[agent] = {
                            "type": "investment_signal",
                            "signal": ts["signal"], 
                            "confidence": ts["confidence"]
                        }
                        break
        
        return ticker_signals
    
    def _generate_direction_decision(self, tickers: list[str],
                                    signals_by_ticker: dict[str, dict],
                                    state: AgentState) -> PortfolioManagerOutput:
        """Generate direction decision (does not include quantity)"""
        progress.update_status(self.agent_id, None, "Retrieving historical decision experiences")
        relevant_memories = self._recall_relevant_memories(tickers, signals_by_ticker, state)
        

        # Get analyst weight information
        analyst_weights_info = self._format_analyst_weights(state)
        
        formatted_memories = self._format_memories_for_prompt(relevant_memories)
        
        # Generate prompt
        prompt_data = {
            "signals_by_ticker": json.dumps(signals_by_ticker, indent=2),
            "analyst_weights_info": analyst_weights_info,
            "analyst_weights_separator": "\n" if analyst_weights_info else "",
            "relevant_past_experiences": formatted_memories,  # ⭐ Inject historical experience
        }

        # Load prompt
        try:
            system_prompt = self.prompt_loader.load_prompt("direction_decision_system", variables=prompt_data)
            human_prompt = self.prompt_loader.load_prompt("direction_decision_human", variables=prompt_data)
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": human_prompt}
            ]
        except FileNotFoundError:
            raise "Failed to load prompts. please check prompt file path for : direction_decision_human"

        # Create default factory
        def create_default_output():
            return PortfolioManagerOutput(
                decisions={
                    ticker: PortfolioDecision(
                        action="hold", 
                        confidence=0.0, 
                        reasoning="Default decision: hold"
                    ) for ticker in tickers
                }
            )
        
        progress.update_status(self.agent_id, None, "Generating decisions based on signals and historical experience")
        
        return tool_call(
            messages=messages,
            pydantic_model=PortfolioManagerOutput,
            agent_name=self.agent_id,
            state=state,
            default_factory=create_default_output,
        )
    
    def _generate_portfolio_decision(self, tickers: list[str],
                                    signals_by_ticker: dict[str, dict],
                                    state: AgentState) -> PortfolioManagerOutput:
        """Generate Portfolio decision (includes quantity)"""
        progress.update_status(self.agent_id, None, "Retrieving historical decision experiences")
        relevant_memories = self._recall_relevant_memories(tickers, signals_by_ticker, state)
        
        portfolio = state["data"]["portfolio"]
        current_prices = state["data"]["current_prices"]
        
        # Calculate maximum shares for each ticker
        for ticker in tickers:
            # Get position limit from risk manager
            risk_manager_id = self._get_risk_manager_id()
            risk_data = state["data"]["analyst_signals"].get(risk_manager_id, {}).get(ticker, {})
            
            remaining_limit = risk_data.get("remaining_position_limit", 0)
            price = current_prices.get(ticker, 0)
            
            

        # Get analyst weights
        formatted_memories = self._format_memories_for_prompt(relevant_memories)
        
        # Format analyst performance stats
        analyst_performance_info = self._format_analyst_performance(state)
        
        # Get recent memory (win rates and last 3 trading days signals)
        recent_memory = self._get_recent_memory(state)
        
        # Generate prompt
        prompt_data = {
            "signals_by_ticker": json.dumps(signals_by_ticker, indent=2, ensure_ascii=False),
            "current_prices": json.dumps(current_prices, indent=2),
            "portfolio_cash": f"{portfolio.get('cash', 0):.2f}",
            "portfolio_positions": json.dumps(portfolio.get("positions", {}), indent=2),
            "margin_requirement": f"{portfolio.get('margin_requirement', 0):.2f}",
            "total_margin_used": f"{portfolio.get('margin_used', 0):.2f}",
            "analyst_performance_info": analyst_performance_info,
            "analyst_performance_separator": "\n" if analyst_performance_info else "",
            "relevant_past_experiences": formatted_memories,  # Inject historical experience
            "recent_memory": recent_memory,
            "recent_memory_separator": "\n" if recent_memory else "",
        }


        # Load prompt
        system_prompt = self.prompt_loader.load_prompt(agent_type=self.agent_type, prompt_name="portfolio_decision_system", variables=prompt_data)
        human_prompt = self.prompt_loader.load_prompt(agent_type=self.agent_type, prompt_name="portfolio_decision_human", variables=prompt_data)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": human_prompt}
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
                        reasoning="Default decision: hold"
                    ) for ticker in tickers
                }
            )
        
        progress.update_status(self.agent_id, None, "Generating decisions based on signals and historical experience")
                # 保存到文件	        
        save_dir = "/Users/wy/Downloads/Project/IA_space/reviews/pm_decisions/"	
        os.makedirs(save_dir, exist_ok=True)	
        filename = f"pm_decision_system_prompt_{state['metadata']['trading_date']}.txt"	
        filepath = os.path.join(save_dir, filename)	
        with open(filepath, 'w', encoding='utf-8') as f:	
            f.write(system_prompt)	
        filename = f"pm_decision_human_prompt_{state['metadata']['trading_date']}.txt"	
        filepath = os.path.join(save_dir, filename)	
        with open(filepath, 'w', encoding='utf-8') as f:	
            f.write(human_prompt)	
        print(f"✅ Decision saved to: {filepath}")
        # pdb.set_trace()
        return tool_call(
            messages=messages,
            pydantic_model=PortfolioManagerOutput,
            agent_name=self.agent_id,
            state=state,
            default_factory=create_default_output,
        )
    
    def _get_risk_manager_id(self) -> str:
        """Get corresponding risk manager ID"""
        if self.agent_id.startswith("portfolio_manager_portfolio_"):
            suffix = self.agent_id.split('_')[-1]
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
        
        info = "Analyst performance weights (based on recent investment signal accuracy):\n"
        sorted_weights = sorted(analyst_weights.items(), key=lambda x: x[1], reverse=True)
        
        for analyst_id, weight in sorted_weights:
            new_hire_info = ""
            if okr_state and okr_state.get("new_hires", {}).get(analyst_id):
                new_hire_info = " (Newly hired analyst)"
            
            bar_length = int(weight * 20)
            bar = "█" * bar_length + "░" * (20 - bar_length)
            
            info += f"  {analyst_id}: {weight:.3f} {bar}{new_hire_info}\n"
        
        info += "\n💡 Suggestion: Consider the importance of different analyst recommendations based on weight levels."
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
            key=lambda x: x[1].get('win_rate', 0) if x[1].get('win_rate') is not None else 0,
            reverse=True
        )
        
        for analyst_id, stats in sorted_analysts:
            win_rate = stats.get('win_rate')
            total_predictions = stats.get('total_predictions', 0)
            correct_predictions = stats.get('correct_predictions', 0)
            
            if win_rate is not None:
                win_rate_pct = win_rate * 100
                bar_length = int(win_rate * 20)
                bar = "█" * bar_length + "░" * (20 - bar_length)
                
                # Get bull/bear breakdown
                bull_info = stats.get('bull', {})
                bear_info = stats.get('bear', {})
                bull_count = bull_info.get('count', 0)
                bull_win = bull_info.get('win', 0)
                bear_count = bear_info.get('count', 0)
                bear_win = bear_info.get('win', 0)
                
                info += f"\n  {analyst_id}:\n"
                info += f"    Win Rate: {win_rate_pct:.1f}% {bar} ({correct_predictions}/{total_predictions} correct)\n"
                info += f"    Bullish: {bull_win}/{bull_count} correct | Bearish: {bear_win}/{bear_count} correct\n"
            else:
                info += f"\n  {analyst_id}: No historical data yet\n"
        
        return info
    
    def _recall_relevant_memories(
        self, 
        tickers: List[str], 
        signals_by_ticker: Dict[str, Dict],
        state: AgentState,
        top_k: int = 3
    ) -> Dict[str, List[str]]:
        """
        Step 1: Retrieve relevant historical decision experiences from memory system (code layer)
        
        Retrieve relevant historical memories for each ticker to help PM make better decisions
        
        Args:
            tickers: Stock ticker list
            signals_by_ticker: Analyst signals grouped by ticker
            state: Current state
            top_k: Number of memories to return per ticker
            
        Returns:
            Dictionary, key is ticker, value is list of relevant memories
            Example: {
                'AAPL': [
                    "2024-01-15: Made long decision under similar signal combination, but resulted in 5% loss...",
                    "2024-01-20: Need to be more cautious when technical indicators conflict with fundamentals..."
                ]
            }
        """
        memories_by_ticker = {}
        
        try:
            # Get base_dir (from config or use default)
            base_dir = self.config.get('base_dir', 'default')
            
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
                        user_id=memory_user_id,  # Uniformly use "portfolio_manager"
                        top_k=top_k
                    )
                    
                    # Format memories as readable strings
                    memory_strings = []
                    for mem in relevant_memories:
                        if isinstance(mem, dict):
                            # New API returns {'id': ..., 'content': ..., 'metadata': ...}
                            memory_content = mem.get('content', str(mem))
                            memory_strings.append(memory_content)
                        else:
                            memory_strings.append(str(mem))
                    
                    memories_by_ticker[ticker] = memory_strings
                    
                    if memory_strings:
                        print(f"✅ {ticker}: Retrieved {len(memory_strings)} relevant historical experiences")
                    
                except Exception as e:
                    print(f"⚠️ {ticker}: Memory retrieval failed - {e}")
                    memories_by_ticker[ticker] = []
            
        except Exception as e:
            print(f"⚠️ Memory system unavailable - {e}")
            # If memory system is unavailable, return empty dictionary
            for ticker in tickers:
                memories_by_ticker[ticker] = []
        
        return memories_by_ticker
    
    def _generate_memory_query(self, ticker: str, ticker_signals: Dict[str, Dict]) -> str:
        """
        Generate memory search query
        
        Generate targeted search query based on current signal combination to find historical decisions under similar circumstances
        
        Args:
            ticker: Stock ticker
            ticker_signals: Analyst signals for this ticker
            
        Returns:
            Search query string
        """
        # Extract signal directions and confidence
        signal_directions = []
        high_confidence_signals = []
        
        for agent_id, signal_data in ticker_signals.items():
            if signal_data.get("type") == "investment_signal":
                direction = signal_data.get("signal", "")
                confidence = signal_data.get("confidence", 0)
                
                signal_directions.append(direction)
                
                if confidence > 70:
                    high_confidence_signals.append(f"{agent_id}:{direction}")
        
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
        
        # Add high confidence signal information
        if high_confidence_signals:
            query_parts.append(f"high confidence analysts: {', '.join(high_confidence_signals[:2])}")
        
        query = " ".join(query_parts)
        return query
    
    def _format_memories_for_prompt(self, memories_by_ticker: Dict[str, List[str]]) -> str:
        """
        ⭐ Helper method for Step 2: Format memories as prompt-ready text
        
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
            
            formatted_lines.append(f"\n**{ticker} Relevant Historical Experience:**")
            for i, memory in enumerate(memories, 1):
                formatted_lines.append(f"  {i}. {memory}")
        
        if not formatted_lines:
            return "No relevant historical experience available."
        
        return "\n".join(formatted_lines)
    
    def _get_recent_memory(self, state: AgentState) -> str:
        """
        Get recent memory: latest win rates and last 3 trading days' signals for analysts and PM
        
        Returns:
            Formatted string with recent memory information
        """
        recent_memory_parts = []
        
        # Try to get dashboard data from config
        dashboard_dir = self.config.get('dashboard_dir')
        
        if not dashboard_dir:
            # Try to get sandbox_dir from config
            sandbox_dir = self.config.get('sandbox_dir')
            if sandbox_dir:
                dashboard_dir = Path(sandbox_dir) / "team_dashboard"
            else:
                # Try to get from config_name
                config_name = self.config.get('config_name', 'default')
                if config_name and config_name != 'default':
                    # Compute path from config_name
                    from ..config.path_config import get_directory_config
                    base_dir = Path(get_directory_config(config_name))
                    dashboard_dir = base_dir / "sandbox_logs" / "team_dashboard"
                else:
                    # No valid configuration found
                    print(f"⚠️ Dashboard directory not configured, skipping recent memory")
                    return ""
        
        dashboard_dir = Path(dashboard_dir)
        leaderboard_file = dashboard_dir / "leaderboard.json"
        summary_file = dashboard_dir / "summary.json"
        internal_state_file = dashboard_dir / "_internal_state.json"
        
        # Load leaderboard data (contains agent performance and signals)
        agent_performance_data = {}
        if leaderboard_file.exists():
            try:
                with open(leaderboard_file, 'r', encoding='utf-8') as f:
                    leaderboard = json.load(f)
                    for agent in leaderboard:
                        agent_id = agent.get('agentId', '')
                        agent_performance_data[agent_id] = {
                            'winRate': agent.get('winRate'),
                            'signals': agent.get('signals', [])
                        }
            except Exception as e:
                print(f"⚠️ Failed to load leaderboard data: {e}")
        
        # Load internal state for detailed portfolio and trade information
        internal_state = {}
        if internal_state_file.exists():
            try:
                with open(internal_state_file, 'r', encoding='utf-8') as f:
                    internal_state = json.load(f)
            except Exception as e:
                print(f"⚠️ Failed to load internal state: {e}")
        
        # Load summary data (contains benchmark returns)
        benchmark_returns = {}
        equity_history = []
        if summary_file.exists():
            try:
                with open(summary_file, 'r', encoding='utf-8') as f:
                    summary = json.load(f)
                    # Calculate returns from equity history
                    equity = summary.get('equity', [])
                    baseline = summary.get('baseline', [])
                    baseline_vw = summary.get('baseline_vw', [])
                    momentum = summary.get('momentum', [])
                    
                    initial_value = 100000.0  # Default initial cash
                    if equity and len(equity) > 0:
                        initial_value = equity[0].get('v', 100000.0) if isinstance(equity[0], dict) else equity[0]
                        equity_history = equity
                    
                        # Calculate current returns (from initial value)
                        if equity and len(equity) > 0:
                            current_equity = equity[-1].get('v', initial_value) if isinstance(equity[-1], dict) else equity[-1]
                            portfolio_return = ((current_equity - initial_value) / initial_value) * 100
                            benchmark_returns['portfolio'] = portfolio_return
                            
                            # Calculate last 3 single-day returns for portfolio
                            recent_daily_returns = []
                            if len(equity) >= 2:
                                # Calculate daily returns for the last 3 trading days
                                for i in range(max(1, len(equity) - 3), len(equity)):
                                    prev_equity = equity[i-1].get('v', initial_value) if isinstance(equity[i-1], dict) else equity[i-1]
                                    curr_equity = equity[i].get('v', initial_value) if isinstance(equity[i], dict) else equity[i]
                                    if prev_equity > 0:
                                        daily_return = ((curr_equity - prev_equity) / prev_equity) * 100
                                        recent_daily_returns.append(daily_return)
                            benchmark_returns['portfolio_recent_daily_returns'] = recent_daily_returns
                    
                    if baseline and len(baseline) > 0:
                        current_baseline = baseline[-1].get('v', initial_value) if isinstance(baseline[-1], dict) else baseline[-1]
                        baseline_return = ((current_baseline - initial_value) / initial_value) * 100
                        benchmark_returns['baseline'] = baseline_return
                        
                        # Calculate last 3 single-day returns for baseline
                        baseline_daily_returns = []
                        if len(baseline) >= 2:
                            for i in range(max(1, len(baseline) - 3), len(baseline)):
                                prev_baseline = baseline[i-1].get('v', initial_value) if isinstance(baseline[i-1], dict) else baseline[i-1]
                                curr_baseline = baseline[i].get('v', initial_value) if isinstance(baseline[i], dict) else baseline[i]
                                if prev_baseline > 0:
                                    daily_return = ((curr_baseline - prev_baseline) / prev_baseline) * 100
                                    baseline_daily_returns.append(daily_return)
                        benchmark_returns['baseline_recent_daily_returns'] = baseline_daily_returns
                    
                    if baseline_vw and len(baseline_vw) > 0:
                        current_baseline_vw = baseline_vw[-1].get('v', initial_value) if isinstance(baseline_vw[-1], dict) else baseline_vw[-1]
                        baseline_vw_return = ((current_baseline_vw - initial_value) / initial_value) * 100
                        benchmark_returns['baseline_vw'] = baseline_vw_return
                        
                        # Calculate last 3 single-day returns for baseline_vw
                        baseline_vw_daily_returns = []
                        if len(baseline_vw) >= 2:
                            for i in range(max(1, len(baseline_vw) - 3), len(baseline_vw)):
                                prev_baseline_vw = baseline_vw[i-1].get('v', initial_value) if isinstance(baseline_vw[i-1], dict) else baseline_vw[i-1]
                                curr_baseline_vw = baseline_vw[i].get('v', initial_value) if isinstance(baseline_vw[i], dict) else baseline_vw[i]
                                if prev_baseline_vw > 0:
                                    daily_return = ((curr_baseline_vw - prev_baseline_vw) / prev_baseline_vw) * 100
                                    baseline_vw_daily_returns.append(daily_return)
                        benchmark_returns['baseline_vw_recent_daily_returns'] = baseline_vw_daily_returns
                    
                    if momentum and len(momentum) > 0:
                        current_momentum = momentum[-1].get('v', initial_value) if isinstance(momentum[-1], dict) else momentum[-1]
                        momentum_return = ((current_momentum - initial_value) / initial_value) * 100
                        benchmark_returns['momentum'] = momentum_return
                        
                        # Calculate last 3 single-day returns for momentum
                        momentum_daily_returns = []
                        if len(momentum) >= 2:
                            for i in range(max(1, len(momentum) - 3), len(momentum)):
                                prev_momentum = momentum[i-1].get('v', initial_value) if isinstance(momentum[i-1], dict) else momentum[i-1]
                                curr_momentum = momentum[i].get('v', initial_value) if isinstance(momentum[i], dict) else momentum[i]
                                if prev_momentum > 0:
                                    daily_return = ((curr_momentum - prev_momentum) / prev_momentum) * 100
                                    momentum_daily_returns.append(daily_return)
                        benchmark_returns['momentum_recent_daily_returns'] = momentum_daily_returns
            except Exception as e:
                print(f"⚠️ Failed to load summary data: {e}")
           
        # Format recent memory
        recent_memory_parts.append("## Recent Memory")
        recent_memory_parts.append("")
        
        # Get unique trading dates from signals (last 3 trading days)
        all_dates = set()
        for agent_data in agent_performance_data.values():
            signals = agent_data.get('signals', [])
            for signal in signals:
                date = signal.get('date', '')
                if date:
                    all_dates.add(date)
        
        # Sort dates and get last 3
        sorted_dates = sorted(all_dates, reverse=True)[:3]
        
        # Format analyst and PM win rates and recent signals
        for agent_id, agent_data in agent_performance_data.items():
            win_rate = agent_data.get('winRate')
            signals = agent_data.get('signals', [])
            
            # Filter signals for last 3 trading days
            recent_signals = [s for s in signals if s.get('date', '') in sorted_dates]
            recent_signals.sort(key=lambda x: (x.get('date', ''), x.get('ticker', '')), reverse=True)
            
            if win_rate is not None or recent_signals:
                agent_name = agent_id.replace('_', ' ').title()
                recent_memory_parts.append(f"### {agent_name}")
                
                if win_rate is not None:
                    recent_memory_parts.append(f"- Latest Win Rate: {win_rate*100:.2f}%")
                
                if recent_signals:
                    # Special handling for Portfolio Manager signals
                    if agent_id == 'portfolio_manager':
                        recent_memory_parts.append(f"- Last 3 Trading Days Decisions:")
                        recent_memory_parts.extend(
                            self._format_pm_signals_with_trades(recent_signals, sorted_dates, internal_state)
                        )
                    else:
                        recent_memory_parts.append(f"- Last 3 Trading Days Signals:")
                        
                        # Group by date
                        signals_by_date = {}
                        for signal in recent_signals:
                            date = signal.get('date', '')
                            if date not in signals_by_date:
                                signals_by_date[date] = []
                            signals_by_date[date].append(signal)
                        
                        for date in sorted(sorted_dates, reverse=True):
                            if date in signals_by_date:
                                recent_memory_parts.append(f"  **{date}:**")
                                for signal in signals_by_date[date]:
                                    ticker = signal.get('ticker', '')
                                    signal_value = signal.get('signal', '')
                                    real_return = signal.get('real_return', 'N/A')
                                    is_correct = signal.get('is_correct', 'unknown')
                                    
                                    correct_marker = ""
                                    if is_correct == True:
                                        correct_marker = " ✓"
                                    elif is_correct == False:
                                        correct_marker = " ✗"
                                    elif is_correct == 'unknown':
                                        correct_marker = " ?"
                                    
                                    recent_memory_parts.append(
                                        f"    - {ticker}: {signal_value} (Real Return: {real_return}){correct_marker}"
                                    )
                
                recent_memory_parts.append("")
        
        # Add benchmark returns section at the end
        if benchmark_returns:
            recent_memory_parts.append("### Benchmark Performance")
            
            # Current cumulative returns
            if 'baseline' in benchmark_returns:
                recent_memory_parts.append(f"- Buy & Hold (Equal Weight): {benchmark_returns['baseline']:+.2f}%")
            if 'baseline_vw' in benchmark_returns:
                recent_memory_parts.append(f"- Buy & Hold (Value Weighted): {benchmark_returns['baseline_vw']:+.2f}%")
            if 'momentum' in benchmark_returns:
                recent_memory_parts.append(f"- Momentum Strategy: {benchmark_returns['momentum']:+.2f}%")
            if 'portfolio' in benchmark_returns:
                portfolio_return = benchmark_returns['portfolio']
                recent_memory_parts.append(f"- Portfolio (EvoTraders): {portfolio_return:+.2f}%")
                # Calculate excess return vs baseline_vw
                if 'baseline_vw' in benchmark_returns:
                    excess_return = portfolio_return - benchmark_returns['baseline_vw']
                    recent_memory_parts.append(f"- Excess Return vs VW: {excess_return:+.2f}%")
            
            # Last 3 trading days strategy returns change log
            recent_memory_parts.append("")
            recent_memory_parts.append("**Last 3 Trading Days Stategy Returns Change Log:**")
            
            if benchmark_returns.get('portfolio_recent_daily_returns'):
                daily_returns = benchmark_returns['portfolio_recent_daily_returns']
                if daily_returns:
                    returns_str = ", ".join([f"{r:+.2f}%" for r in daily_returns])
                    recent_memory_parts.append(f"- Portfolio (EvoTraders): {returns_str}")
            
            if benchmark_returns.get('baseline_recent_daily_returns'):
                daily_returns = benchmark_returns['baseline_recent_daily_returns']
                if daily_returns:
                    returns_str = ", ".join([f"{r:+.2f}%" for r in daily_returns])
                    recent_memory_parts.append(f"- Buy & Hold (Equal Weight): {returns_str}")
            
            if benchmark_returns.get('baseline_vw_recent_daily_returns'):
                daily_returns = benchmark_returns['baseline_vw_recent_daily_returns']
                if daily_returns:
                    returns_str = ", ".join([f"{r:+.2f}%" for r in daily_returns])
                    recent_memory_parts.append(f"- Buy & Hold (Value Weighted): {returns_str}")
            
            if benchmark_returns.get('momentum_recent_daily_returns'):
                daily_returns = benchmark_returns['momentum_recent_daily_returns']
                if daily_returns:
                    returns_str = ", ".join([f"{r:+.2f}%" for r in daily_returns])
                    recent_memory_parts.append(f"- Momentum Strategy: {returns_str}")
            
            recent_memory_parts.append("")
        
        if len(recent_memory_parts) == 2:  # Only header and empty line
            return ""
        
        return "\n".join(recent_memory_parts)
    
    def _format_pm_signals_with_trades(self, recent_signals: List[Dict], sorted_dates: List[str], 
                                       internal_state: Dict) -> List[str]:
        """
        Format PM signals with detailed trade information showing:
        pre_position → action (quantity) → final_position + stock_return
        
        Simplified approach: use daily trades and equity history directly
        
        Args:
            recent_signals: List of PM signals for recent days
            sorted_dates: Sorted list of recent trading dates
            internal_state: Internal state from dashboard with trade history
            
        Returns:
            List of formatted lines
        """
        from datetime import datetime
        
        formatted_lines = []
        
        # Get data from internal state
        all_trades = internal_state.get('all_trades', [])
        equity_history = internal_state.get('equity_history', [])
        daily_position_history = internal_state.get('daily_position_history', {})  # ✨ Optimized: pre-computed snapshots
        
        # Build trades index by (date, ticker)
        trades_by_date_ticker = {}
        for trade in all_trades:
            # Use trading_date if available (handles timezone offset correctly)
            # Fallback to extracting from timestamp for backward compatibility
            trade_date = trade.get('trading_date')
            if not trade_date:
                ts = trade.get('ts') or trade.get('timestamp', 0)
                if ts:
                    trade_date = datetime.fromtimestamp(ts / 1000).strftime('%Y-%m-%d')
            
            if trade_date:
                ticker = trade.get('ticker', '')
                key = (trade_date, ticker)
                if key not in trades_by_date_ticker:
                    trades_by_date_ticker[key] = []
                trades_by_date_ticker[key].append(trade)
        
        # Build equity history by date for daily return calculation
        equity_by_date = {}
        for point in equity_history:
            if 't' in point and 'v' in point:
                date_str = datetime.fromtimestamp(point['t'] / 1000).strftime('%Y-%m-%d')
                equity_by_date[date_str] = point['v']
        
        # Build position tracker
        # ✨ Optimization: Use pre-computed daily_position_history if available
        position_tracker = {}  # {(date, ticker): opening_position}
        
        if daily_position_history:
            # Fast path: Use pre-computed daily position snapshots (O(1) lookup)
            dates_list = sorted(daily_position_history.keys())
            
            for i, date in enumerate(dates_list):
                closing_positions = daily_position_history[date]
                
                # Get all tickers seen up to this date
                all_tickers_seen = set()
                for d in dates_list[:i+1]:
                    all_tickers_seen.update(daily_position_history[d].keys())
                
                for ticker in all_tickers_seen:
                    if i == 0:
                        # First day: opening = 0
                        position_tracker[(date, ticker)] = 0
                    else:
                        # Opening = previous day's closing
                        prev_date = dates_list[i-1]
                        prev_closing = daily_position_history.get(prev_date, {}).get(ticker, 0)
                        position_tracker[(date, ticker)] = prev_closing
        else:
            # Fallback: Rebuild from all_trades (slower, O(n) where n = number of trades)
            sorted_trades = sorted(all_trades, key=lambda x: x.get('ts') or x.get('timestamp', 0))
            
            daily_positions = {}
            current_positions = {}
            
            for trade in sorted_trades:
                # Use trading_date if available (handles timezone offset correctly)
                # Fallback to extracting from timestamp for backward compatibility
                trade_date = trade.get('trading_date')
                if not trade_date:
                    ts = trade.get('ts') or trade.get('timestamp', 0)
                    if not ts:
                        continue
                    trade_date = datetime.fromtimestamp(ts / 1000).strftime('%Y-%m-%d')
                
                ticker = trade.get('ticker', '')
                qty = trade.get('qty', 0)
                side = trade.get('side', '')
                
                if ticker not in current_positions:
                    current_positions[ticker] = 0
                
                if side == 'LONG':
                    current_positions[ticker] += qty
                elif side == 'SHORT':
                    current_positions[ticker] -= qty
                
                if trade_date not in daily_positions:
                    daily_positions[trade_date] = {}
                daily_positions[trade_date][ticker] = current_positions[ticker]
            
            dates_list = sorted(daily_positions.keys())
            for i, date in enumerate(dates_list):
                all_tickers_seen = set()
                for d in dates_list[:i+1]:
                    all_tickers_seen.update(daily_positions[d].keys())
                
                for ticker in all_tickers_seen:
                    if i == 0:
                        position_tracker[(date, ticker)] = 0
                    else:
                        prev_date = dates_list[i-1]
                        prev_closing = daily_positions.get(prev_date, {}).get(ticker, 0)
                        position_tracker[(date, ticker)] = prev_closing
        
        # Group signals by date
        signals_by_date = {}
        for signal in recent_signals:
            date = signal.get('date', '')
            if date not in signals_by_date:
                signals_by_date[date] = []
            signals_by_date[date].append(signal)
        
        # Process each date
        dates_list = sorted(equity_by_date.keys())
        for date in sorted(sorted_dates, reverse=True):
            if date not in signals_by_date:
                continue
            
            formatted_lines.append(f"  **{date}:**")
            
            # Calculate portfolio daily return
            portfolio_daily_return = None
            if date in equity_by_date:
                try:
                    date_idx = dates_list.index(date)
                    if date_idx > 0:
                        prev_equity = equity_by_date[dates_list[date_idx - 1]]
                        curr_equity = equity_by_date[date]
                        if prev_equity > 0:
                            portfolio_daily_return = ((curr_equity - prev_equity) / prev_equity) * 100
                except (ValueError, IndexError):
                    pass
            
            # Process each ticker's signal
            for signal in signals_by_date[date]:
                ticker = signal.get('ticker', '')
                real_return = signal.get('real_return', 'N/A')
                is_correct = signal.get('is_correct', 'unknown')
                
                # Get trades for this ticker on this date
                ticker_trades = trades_by_date_ticker.get((date, ticker), [])
                
                # Get pre-position (position before first trade of the day)
                pre_position = position_tracker.get((date, ticker), 0)
                
                # Calculate action from trades
                action_qty = 0
                for trade in ticker_trades:
                    qty = trade.get('qty', 0)
                    side = trade.get('side', '')
                    if side == 'LONG':
                        action_qty += qty
                    elif side == 'SHORT':
                        action_qty -= qty
                
                # Calculate final position
                final_position = pre_position + action_qty
                
                # Format display
                def format_position(pos):
                    if pos > 0:
                        return f"{pos} long"
                    elif pos < 0:
                        return f"{abs(pos)} short"
                    else:
                        return "0"
                
                # Format action
                if action_qty > 0:
                    action_desc = f"long {action_qty}"
                elif action_qty < 0:
                    action_desc = f"short {abs(action_qty)}"
                else:
                    action_desc = "hold"
                
                # Correct marker
                correct_marker = ""
                if is_correct == True:
                    correct_marker = " ✓"
                elif is_correct == False:
                    correct_marker = " ✗"
                elif is_correct == 'unknown':
                    correct_marker = " ?"
                
                formatted_lines.append(
                    f"    - {ticker}: [{format_position(pre_position)}] → [{action_desc}] → "
                    f"[{format_position(final_position)}] (Stock Return: {real_return}){correct_marker}"
                )
            
            # Add portfolio daily return
            if portfolio_daily_return is not None:
                formatted_lines.append(f"    Portfolio Daily Return: {portfolio_daily_return:+.2f}%")
            
            formatted_lines.append("")
        
        return formatted_lines
  
  