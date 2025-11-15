"""
Analyst Agent - Unified Analyst Agent implementation
Based on AgentScope AgentBase, uses Toolkit and Msg
"""
import asyncio
from typing import Dict, Any, Optional, List
import json

from agentscope.agent import AgentBase
from agentscope.message import Msg
from agentscope.tool import Toolkit

from ..graph.state import AgentState
from ..utils.progress import progress
from ..llm.models import get_model  # Use AgentScope model
from .tool_selector import Toolselector
from ..tools.data_tools import get_last_tradeday
from ..config.constants import ANALYST_TYPES
from ..utils.tool_call import tool_call
from ..data.second_round_signals import SecondRoundAnalysis, TickerSignal
from .prompt_loader import PromptLoader

_prompt_loader = PromptLoader()
_personas_config = _prompt_loader.load_yaml_config("analyst", "personas")

class AnalystAgent(AgentBase):
    """Analyst Agent - Uses LLM for intelligent tool selection and analysis (based on AgentScope)"""
    
    def __init__(self, 
                 analyst_type: str,
                 agent_id: Optional[str] = None,
                 description: Optional[str] = None, 
                 config: Optional[Dict[str, Any]] = None):
        """
        Initialize Analyst Agent
        
        Args:
            analyst_type: Analyst type (fundamental, technical, sentiment, valuation, comprehensive)
            agent_id: Agent ID (defaults to "{analyst_type}_analyst_agent")
            description: Analyst description
            config: Configuration dictionary
        """
        if analyst_type not in ANALYST_TYPES:
            raise ValueError(
                f"Unknown analyst type: {analyst_type}. "
                f"Must be one of: {list(ANALYST_TYPES.keys())}"
            )
        
        self.analyst_type_key = analyst_type
        self.analyst_persona = ANALYST_TYPES[analyst_type]["display_name"]
        
        # Set default agent_id
        if agent_id is None:
            agent_id = f"{analyst_type}_analyst_agent"
        
        # Initialize AgentBase (does not accept parameters)
        super().__init__()
        
        # Set name attribute
        self.name = agent_id
        
        self.description = description or f"{self.analyst_persona} - Uses LLM for intelligent analysis tool selection"
        self.config = config or {}
        
        # Use LLM tool selector (internally uses Toolkit)
        self.tool_selector = Toolselector()
        self.toolkit = self.tool_selector.get_toolkit()  # Get Toolkit instance
    
    def execute(self, state: AgentState) -> Dict[str, Any]:
        """
        Execute analyst logic (synchronous entry point, internally calls async)
        
        Args:
            state: AgentState
        
        Returns:
            Updated state dictionary
        """
        # Create new event loop in current thread for async analysis
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(self._execute_async(state))
            return result
        finally:
            loop.close()
            asyncio.set_event_loop(None)
    
    async def _execute_async(self, state: AgentState) -> Dict[str, Any]:
        """
        Asynchronously execute analyst logic
        
        Args:
            state: AgentState
        
        Returns:
            Updated state dictionary
        """
        data = state["data"]
        tickers = data["tickers"]
        start_date = data.get("start_date")
        end_date = data["end_date"]
        
        # Get LLM - use analyst-specific model configuration
        from ..utils.tool_call import get_agent_model_config
        
        model_name, model_provider = get_agent_model_config(state, self.name)
        llm = get_model(
            model_name=model_name,
            model_provider=model_provider,
            api_keys=state['data']['api_keys']
        )
        
        # Execute analysis
        analysis_results = {}
        
        for ticker in tickers:
            progress.update_status(
                self.name,  # Use self.name instead of self.agent_id
                ticker, 
                f"Starting {self.analyst_persona} intelligent analysis"
            )
            
            # Generate analysis objective
            analysis_objective = (
                f"As a professional {self.analyst_persona}, conduct comprehensive and in-depth investment analysis "
                f"for stock {ticker}"
            )
            
            # Asynchronously analyze ticker
            result = await self._analyze_ticker(
                ticker, end_date, state, start_date, llm, analysis_objective
            )
            analysis_results[ticker] = result
            
            progress.update_status(
                self.name, 
                ticker, 
                "Done",
                analysis=json.dumps(result, indent=2, default=str)
            )
        
        # Create message (using AgentScope Msg format)
        message = Msg(
            name=self.name,
            content=json.dumps(analysis_results, default=str),
            role="assistant",
            metadata={"analyst_type": self.analyst_type_key}
        )
        
        # Update state
        state["data"]["analyst_signals"][self.name] = analysis_results
        
        progress.update_status(
            self.name, 
            None, 
            f"All {self.analyst_persona} analysis completed"
        )
        
        return {
            "messages": [message.to_dict()],  # Convert to dict
            "data": data,
        }
    
    async def _analyze_ticker(self, ticker: str, end_date: str, state: Dict[str, Any],
                            start_date: Optional[str], llm, 
                            analysis_objective: str) -> Dict[str, Any]:
        """
        Analyze a single ticker
        
        Args:
            ticker: Stock ticker
            end_date: End date
            state: State object (contains API keys and other information)
            start_date: Start date
            llm: LLM model
            analysis_objective: Analysis objective
        
        Returns:
            Analysis result dictionary
        """
        progress.update_status(
            self.name, 
            ticker, 
            "Starting intelligent tool selection"
        )
        
        # ⭐ Adjust end_date to previous trading day
        # This ensures analysis doesn't include incomplete same-day data
        adjusted_end_date = get_last_tradeday(end_date)
        # print(f"📅 Analyst {self.name} - Original date: {end_date}, Analysis end date (previous trading day): {adjusted_end_date}")
        
        # 1. Generate market conditions
        market_conditions = {
            "analysis_date": end_date,
            "volatility_regime": "normal",
            "interest_rate": "normal", 
            "market_sentiment": "neutral"
        }
        
        # 2. Use LLM to select tools
        selection_result = await self.tool_selector.select_tools_with_llm(
            llm, self.analyst_persona, ticker, market_conditions, analysis_objective
        )
        
        progress.update_status(
            self.name, 
            ticker, 
            f"Selected {selection_result['tool_count']} tools"
        )


        # print(f"{self.name} \n\n- LLM tool selection result:\n\n {selection_result}")
        
        # 3. Execute selected tools - using AgentScope Toolkit
        tool_results = await self.tool_selector.execute_selected_tools(
            selection_result["selected_tools"],
            ticker=ticker,
            state=state,  # Pass state so tools can get required API keys themselves
            start_date=start_date,
            end_date=adjusted_end_date  # Use adjusted date
        )
        
        # 4. Use LLM to synthesize tool results
        progress.update_status(
            self.name, 
            ticker, 
            "LLM synthesizing signals"
        )


        combined_result = self.tool_selector.synthesize_results_with_llm(
            tool_results, 
            selection_result,
            llm,
            ticker,
            self.analyst_persona
        )

        # print(f"- {self.name} call output result:\n\n {combined_result}")
        
        # 5. Build final result
        analysis_result = {
            "signal": combined_result["signal"],
            "confidence": combined_result["confidence"],
            "reasoning": combined_result["reasoning"],
            "tool_impact_analysis":combined_result["tool_impact_analysis"],
            "tool_selection": {
                "analysis_strategy": selection_result["analysis_strategy"],
                "selected_tools": selection_result["selected_tools"],
                "tool_count": selection_result["tool_count"]
            },
            "tool_analysis": {
                "tools_used": len(selection_result["selected_tools"]),
                "successful_tools": len([r for r in tool_results if "error" not in r]),
                "failed_tools": len([r for r in tool_results if "error" in r]),
                "tool_results": tool_results,
                "synthesis_details": combined_result
            },
            "metadata": {
                "analyst_name": self.analyst_persona,
                "analyst_type": self.analyst_type_key,
                "analysis_date": end_date,
                "llm_enhanced": llm is not None,
                "selection_method": "LLM intelligent selection" if llm else "Default selection",
                "synthesis_method": combined_result.get("synthesis_method", "unknown"),
            }
        }
        
        progress.update_status(self.name, ticker, "Analysis completed")
        
        return analysis_result




def run_second_round_llm_analysis(
    agent_id: str,
    tickers: List[str], 
    first_round_analysis: Dict[str, Any],
    overall_summary: Dict[str, Any],
    notifications: List[Dict[str, Any]],
    state: AgentState
) -> SecondRoundAnalysis:
    """Run second round LLM analysis"""
    
    if agent_id not in _personas_config:
        raise ValueError(f"Unknown analyst ID: {agent_id}")
    
    persona = _personas_config[agent_id]
    
    analysis_focus_str = "\n".join([f"- {focus}" for focus in persona['analysis_focus']])
    
    # Format notification information
    notifications_str = ""
    if notifications:
        notifications_str = "\n".join([
            f"- {notif.get('sender', 'Unknown')}: {notif.get('content', '')}"
            for notif in notifications
        ])
    else:
        notifications_str = "No notifications from other analysts yet"
    
    # Generate per-ticker reports
    ticker_reports = []
    for i, ticker in enumerate(tickers, 1):
        ticker_first_round = {}
        if isinstance(first_round_analysis, dict):
            if 'ticker_signals' in first_round_analysis:
                for signal in first_round_analysis['ticker_signals']:
                    if signal.get('ticker') == ticker:
                        ticker_first_round = signal
                        break
            else:
                ticker_first_round = first_round_analysis.get(ticker, {})
        
        ticker_report = f"""## Stock {i}: {ticker}

### Your First Round Analysis for {ticker}

Analysis Result and Thought Process:
{json.dumps(ticker_first_round['tool_analysis']['synthesis_details'], ensure_ascii=False, indent=2)}
Analysis Tools Selection and Reasoning:
{json.dumps(ticker_first_round['tool_selection'], ensure_ascii=False, indent=2)}

"""
        ticker_reports.append(ticker_report)
    
    variables = {
        "analyst_name": persona['name'],
        "specialty": persona['specialty'],
        "analysis_focus": analysis_focus_str,
        "decision_style": persona['decision_style'],
        "risk_preference": persona['risk_preference'],
        "ticker_reports": "\n".join(ticker_reports),
        "notifications": notifications_str,
        "agent_id": agent_id
    }
    
    system_prompt = _prompt_loader.load_prompt("analyst", "second_round_system", variables)
    human_prompt = _prompt_loader.load_prompt("analyst", "second_round_human", variables)
    messages = [{"role":"system", "content":system_prompt},
        {"role":"user", "content":human_prompt}]
    
    def create_default_analysis():
        return SecondRoundAnalysis(
            analyst_id=agent_id,
            analyst_name=persona['name'],
            ticker_signals=[
                TickerSignal(
                    ticker=ticker,
                    signal="neutral", 
                    confidence=50,
                    reasoning="LLM analysis failed, maintaining neutral stance"
                ) for ticker in tickers
            ]
        )
    
    result = tool_call(
        messages=messages,
        pydantic_model=SecondRoundAnalysis,
        agent_name=agent_id,  # Use agent_id directly for correct model config
        state=state,
        default_factory=create_default_analysis
    )
    
    result.analyst_id = agent_id
    result.analyst_name = persona['name']
    
    return result


def format_second_round_result_for_state(analysis: SecondRoundAnalysis) -> Dict[str, Any]:
    """Format second round analysis result for storage in AgentState"""
    return {
        "analyst_id": analysis.analyst_id,
        "analyst_name": analysis.analyst_name,
        "ticker_signals": [signal.model_dump() for signal in analysis.ticker_signals],
        "timestamp": analysis.timestamp.isoformat(),
        "analysis_type": "second_round_llm"
    }
