"""
Portfolio Manager Agent - Portfolio Management Agent
Provides unified portfolio management interface (based on AgentScope)
"""
from typing import Dict, Any, Optional, Literal, List
import json
import pdb
import os
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
                        "risk_level": risk_info.get("risk_level", "unknown"),
                        "risk_score": risk_info.get("risk_score", 50),
                        "risk_assessment": risk_info.get("risk_assessment", "")
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
        progress.update_status(self.agent_id, None, "Generating decisions based on signals and historical experience")
        
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

