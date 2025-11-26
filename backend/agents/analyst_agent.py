# -*- coding: utf-8 -*-
"""
Analyst Agent - Unified Analyst Agent implementation
Based on AgentScope AgentBase, uses Toolkit and Msg
"""
import asyncio
import json
from typing import Any, Dict, Optional

from agentscope.agent import AgentBase
from agentscope.message import Msg

from ..config.constants import ANALYST_TYPES
from ..graph.state import AgentState
from ..llm.models import get_model
from ..tools.data_tools import get_last_tradeday
from ..utils.progress import progress
from .prompt_loader import PromptLoader
from .tool_selector import Toolselector

_prompt_loader = PromptLoader()
_personas_config = _prompt_loader.load_yaml_config("analyst", "personas")


class AnalystAgent(AgentBase):
    """Analyst Agent - Uses LLM for intelligent tool selection and analysis"""

    def __init__(
        self,
        analyst_type: str,
        agent_id: Optional[str] = None,
        description: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize Analyst Agent

        Args:
            analyst_type: Analyst type
            (fundamental, technical, sentiment, valuation, comprehensive)
            agent_id: Agent ID (defaults to "{analyst_type}_analyst_agent")
            description: Analyst description
            config: Configuration dictionary
        """
        if analyst_type not in ANALYST_TYPES:
            raise ValueError(
                f"Unknown analyst type: {analyst_type}. "
                f"Must be one of: {list(ANALYST_TYPES.keys())}",
            )

        self.analyst_type_key = analyst_type
        self.analyst_persona = ANALYST_TYPES[analyst_type]["display_name"]

        # Set default agent_id
        if agent_id is None:
            agent_id = f"{analyst_type}_analyst_agent"

        # Initialize AgentBase
        super().__init__()

        # Set name attribute
        self.name = agent_id

        self.description = (
            description
            or f"{self.analyst_persona} - Uses LLM for tool selection"
        )
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
            api_keys=state["data"]["api_keys"],
        )

        # Execute analysis
        analysis_results = {}

        for ticker in tickers:
            progress.update_status(
                self.name,  # Use self.name instead of self.agent_id
                ticker,
                f"Starting {self.analyst_persona} intelligent analysis",
            )

            # Generate analysis objective
            analysis_objective = (
                f"As a professional {self.analyst_persona}, "
                f"conduct comprehensive and in-depth investment analysis "
                f"for stock {ticker}"
            )

            # Asynchronously analyze ticker
            result = await self._analyze_ticker(
                ticker,
                end_date,
                state,
                start_date,
                llm,
                analysis_objective,
            )
            analysis_results[ticker] = result

            progress.update_status(
                self.name,
                ticker,
                "Done",
                analysis=json.dumps(result, indent=2, default=str),
            )

        # Create message
        message = Msg(
            name=self.name,
            content=json.dumps(analysis_results, default=str),
            role="assistant",
            metadata={"analyst_type": self.analyst_type_key},
        )

        # Update state
        state["data"]["analyst_signals"][self.name] = analysis_results

        progress.update_status(
            self.name,
            None,
            f"All {self.analyst_persona} analysis completed",
        )

        return {
            "messages": [message.to_dict()],  # Convert to dict
            "data": data,
        }

    async def _analyze_ticker(
        self,
        ticker: str,
        end_date: str,
        state: Dict[str, Any],
        start_date: Optional[str],
        llm,
        analysis_objective: str,
    ) -> Dict[str, Any]:
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
            "Starting intelligent tool selection",
        )

        # Adjust end_date to previous trading day
        # This ensures analysis doesn't include incomplete same-day data
        adjusted_end_date = get_last_tradeday(end_date)

        # 1. Generate market conditions
        market_conditions = {
            "analysis_date": end_date,
        }

        # 2. Use LLM to select tools
        selection_result = await self.tool_selector.select_tools_with_llm(
            llm,
            self.analyst_persona,
            ticker,
            market_conditions,
            analysis_objective,
        )

        progress.update_status(
            self.name,
            ticker,
            f"Selected {selection_result['tool_count']} tools",
        )

        # 3. Execute selected tools
        tool_results = await self.tool_selector.execute_selected_tools(
            selection_result["selected_tools"],
            ticker=ticker,
            state=state,  # Pass state so tools can get required API keys
            start_date=start_date,
            end_date=adjusted_end_date,  # Use adjusted date
        )

        # 4. Use LLM to synthesize tool results
        progress.update_status(
            self.name,
            ticker,
            "LLM synthesizing signals",
        )

        combined_result = self.tool_selector.synthesize_results_with_llm(
            tool_results,
            selection_result,
            llm,
            ticker,
            self.analyst_persona,
        )

        # 5. Build final result
        analysis_result = {
            "signal": combined_result["signal"],
            "confidence": combined_result["confidence"],
            "reasoning": combined_result["reasoning"],
            "tool_impact_analysis": combined_result["tool_impact_analysis"],
            "tool_selection": {
                "analysis_strategy": selection_result["analysis_strategy"],
                "selected_tools": selection_result["selected_tools"],
                "tool_count": selection_result["tool_count"],
            },
            "tool_analysis": {
                "tools_used": len(selection_result["selected_tools"]),
                "successful_tools": len(
                    [r for r in tool_results if "error" not in r],
                ),
                "failed_tools": len([r for r in tool_results if "error" in r]),
                "tool_results": tool_results,
                "synthesis_details": combined_result,
            },
            "metadata": {
                "analyst_name": self.analyst_persona,
                "analyst_type": self.analyst_type_key,
                "analysis_date": end_date,
                "llm_enhanced": llm is not None,
                "selection_method": (
                    "LLM intelligent selection" if llm else "Default selection"
                ),
                "synthesis_method": combined_result.get(
                    "synthesis_method",
                    "unknown",
                ),
            },
        }

        progress.update_status(self.name, ticker, "Analysis completed")

        return analysis_result
