# -*- coding: utf-8 -*-
"""
LLM-based intelligent tool selector
Enables analysts to intelligently select and use analysis tools through LLM
Uses AgentScope's Toolkit to manage tools
"""
import os
import json
from typing import Dict, Any, List
from agentscope.tool import Toolkit
import pdb
from .prompt_loader import PromptLoader

# Import all available analysis tools
from backend.tools.analysis_tools import (
    analyze_profitability,
    analyze_growth,
    analyze_financial_health,
    analyze_valuation_ratios,
    analyze_efficiency_ratios,
    analyze_trend_following,
    analyze_mean_reversion,
    analyze_momentum,
    analyze_volatility,
    analyze_insider_trading,
    analyze_news_sentiment,
    dcf_valuation_analysis,
    owner_earnings_valuation_analysis,
    ev_ebitda_valuation_analysis,
    residual_income_valuation_analysis,
)


class Toolselector:
    """LLM-based intelligent tool selector"""

    # Tool category mapping (for determining API key)
    TOOL_CATEGORIES = {
        "analyze_profitability": "fundamental",
        "analyze_growth": "fundamental",
        "analyze_financial_health": "fundamental",
        "analyze_valuation_ratios": "fundamental",
        "analyze_efficiency_ratios": "fundamental",
        "analyze_trend_following": "technical",
        "analyze_mean_reversion": "technical",
        "analyze_momentum": "technical",
        "analyze_volatility": "technical",
        "analyze_insider_trading": "sentiment",
        "analyze_news_sentiment": "sentiment",
        "dcf_valuation_analysis": "valuation",
        "owner_earnings_valuation_analysis": "valuation",
        "ev_ebitda_valuation_analysis": "valuation",
        "residual_income_valuation_analysis": "valuation",
    }

    # Persona name mapping
    PERSONA_KEY_MAP = {
        "Fundamental Analyst": "fundamentals_analyst",
        "Technical Analyst": "technical_analyst",
        "Sentiment Analyst": "sentiment_analyst",
        "Valuation Analyst": "valuation_analyst",
        "Comprehensive Analyst": "comprehensive_analyst",
    }

    def __init__(self):
        """Initialize tool selector"""
        self.prompt_loader = PromptLoader()
        self.toolkit = Toolkit()
        self.personas_config = self.prompt_loader.load_yaml_config(
            "analyst",
            "personas",
        )

        # Tool function mapping
        self.tool_functions = {
            "analyze_profitability": analyze_profitability,
            "analyze_growth": analyze_growth,
            "analyze_financial_health": analyze_financial_health,
            "analyze_valuation_ratios": analyze_valuation_ratios,
            "analyze_efficiency_ratios": analyze_efficiency_ratios,
            "analyze_trend_following": analyze_trend_following,
            "analyze_mean_reversion": analyze_mean_reversion,
            "analyze_momentum": analyze_momentum,
            "analyze_volatility": analyze_volatility,
            "analyze_insider_trading": analyze_insider_trading,
            "analyze_news_sentiment": analyze_news_sentiment,
            "dcf_valuation_analysis": dcf_valuation_analysis,
            "owner_earnings_valuation_analysis": owner_earnings_valuation_analysis,
            "ev_ebitda_valuation_analysis": ev_ebitda_valuation_analysis,
            "residual_income_valuation_analysis": residual_income_valuation_analysis,
        }

        # Register all tools (using native method)
        self._register_all_tools()

    def _register_all_tools(self):
        """Register all analysis tools to Toolkit"""
        tools = [
            analyze_profitability,
            analyze_growth,
            analyze_financial_health,
            analyze_valuation_ratios,
            analyze_efficiency_ratios,
            analyze_trend_following,
            analyze_mean_reversion,
            analyze_momentum,
            analyze_volatility,
            analyze_insider_trading,
            analyze_news_sentiment,
            dcf_valuation_analysis,
            owner_earnings_valuation_analysis,
            ev_ebitda_valuation_analysis,
            residual_income_valuation_analysis,
        ]

        for tool_func in tools:
            # Directly register tool function, AgentScope will automatically parse docstring
            self.toolkit.register_tool_function(tool_func)

    def get_toolkit(self) -> Toolkit:
        """Get Toolkit instance"""
        return self.toolkit

    def _get_persona_config(self, analyst_persona: str) -> Dict[str, Any]:
        """Get persona configuration"""
        persona_key = self.PERSONA_KEY_MAP.get(
            analyst_persona,
            "comprehensive_analyst",
        )
        return self.personas_config.get(persona_key, {})

    def _get_persona_description(self, analyst_persona: str) -> str:
        """Get persona description from YAML configuration"""
        return self._get_persona_config(analyst_persona).get("description", "")

    async def select_tools_with_llm(
        self,
        llm,
        analyst_persona: str,
        ticker: str,
        market_conditions: Dict[str, Any],
        analysis_objective: str = "Comprehensive investment analysis",
    ) -> Dict[str, Any]:
        """Use LLM to select analysis tools"""
        try:
            # Get persona description
            persona_description = self._get_persona_description(
                analyst_persona,
            )

            # Load prompt from file
            prompt = self.prompt_loader.load_prompt(
                "analyst",
                "tool_selection",
                {
                    "analyst_persona": analyst_persona,
                    "ticker": ticker,
                    "analysis_objective": analysis_objective,
                    "persona_description": persona_description,
                    "tools_description": self.toolkit.get_json_schemas(),
                },
            )

            # Call LLM
            messages = [{"role": "user", "content": prompt}]
            response = llm(messages=messages, temperature=0.7)
            response_text = response["content"].strip()

            # Extract JSON
            json_text = self._extract_json(response_text)
            selection_result = json.loads(json_text)

            # Validate and return
            return self._validate_selection(selection_result)

        except Exception as e:
            print(f"⚠️ LLM tool selection failed: {str(e)}")
            return []

    def _extract_json(self, text: str) -> str:
        """Extract JSON from response text"""
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            return text[start:end].strip()
        else:
            start = text.find("{")
            end = text.rfind("}") + 1
            return text[start:end]

    def _validate_selection(
        self,
        selection_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Validate tool selection result"""
        if "selected_tools" not in selection_result:
            raise ValueError("Missing selected_tools in response")

        # Filter valid tools
        valid_tools = [
            tool
            for tool in selection_result["selected_tools"]
            if tool.get("tool_name") in self.tool_functions
        ]

        return {
            "selected_tools": valid_tools,
            "analysis_strategy": selection_result.get("analysis_strategy", ""),
            "synthesis_approach": selection_result.get(
                "synthesis_approach",
                "",
            ),
            "tool_count": len(valid_tools),
        }

    def _get_api_key(self, tool_name: str) -> str:
        """Get corresponding API key based on tool name"""
        category = self.TOOL_CATEGORIES.get(tool_name)

        if category in ["fundamental", "valuation"]:
            key_name = "FINANCIAL_DATASETS_API_KEY"
        else:  # technical, sentiment
            key_name = "FINNHUB_API_KEY"

        api_key = os.getenv(key_name)

        if not api_key:
            print(f"⚠️ API key not found: {key_name} for {tool_name}")

        return api_key

    async def execute_selected_tools(
        self,
        selected_tools: List[Dict[str, Any]],
        ticker: str,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """Execute selected tools"""
        tool_results = []

        for tool_selection in selected_tools:
            tool_name = tool_selection["tool_name"]

            # Get tool function
            tool_func = self.tool_functions.get(tool_name)
            if not tool_func:
                continue

            try:
                # Prepare parameters
                tool_kwargs = {
                    "ticker": ticker,
                    "api_key": self._get_api_key(tool_name),
                    "end_date": kwargs.get("end_date"),
                }

                # Technical and sentiment analysis require start_date
                category = self.TOOL_CATEGORIES[tool_name]
                if category in ["technical", "sentiment"]:
                    tool_kwargs["start_date"] = kwargs.get("start_date")

                # Directly call tool function
                result = tool_func(**tool_kwargs)

                # Add metadata
                result["tool_name"] = tool_name
                result["selection_reason"] = tool_selection.get("reason", "")
                tool_results.append(result)

            except Exception as e:
                print(f"❌ Tool {tool_name} failed: {str(e)}")
                tool_results.append(
                    {
                        "tool_name": tool_name,
                        "error": str(e),
                        "signal": "neutral",
                        "confidence": 0,
                    },
                )

        return tool_results

    def synthesize_results_with_llm(
        self,
        tool_results: List[Dict[str, Any]],
        selection_result: Dict[str, Any],
        llm,
        ticker: str,
        analyst_persona: str,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """
        Use LLM to synthesize tool results with retry mechanism

        Args:
            tool_results: Results from executed tools
            selection_result: Tool selection decision
            llm: LLM function
            ticker: Stock ticker
            analyst_persona: Analyst persona description
            max_retries: Maximum number of retry attempts (default: 3)

        Returns:
            Synthesis result dict
        """
        import time

        # Prepare tool result summaries (once, outside retry loop)
        tool_summaries = [
            {
                "tool_name": result.get("tool_name", "unknown"),
                "selection_reason": result.get("selection_reason", ""),
                "full_result": result,  # Include full result for comprehensive analysis
            }
            for result in tool_results
            if "error" not in result
        ]

        tool_summaries_json = json.dumps(
            tool_summaries,
            indent=2,
            ensure_ascii=False,
        )

        # Load prompt (once, outside retry loop)
        prompt = self.prompt_loader.load_prompt(
            "analyst",
            "tool_synthesis",
            {
                "analyst_persona": analyst_persona,
                "ticker": ticker,
                "analysis_strategy": selection_result.get(
                    "analysis_strategy",
                    "",
                ),
                "synthesis_approach": selection_result.get(
                    "synthesis_approach",
                    "",
                ),
                "tool_summaries": tool_summaries_json,
            },
        )

        # Retry loop
        last_exception = None
        for attempt in range(max_retries):
            try:
                # Call LLM
                messages = [{"role": "user", "content": prompt}]
                response = llm(messages=messages, temperature=0.7)
                response_text = response["content"].strip()

                # Extract and parse JSON
                json_text = self._extract_json(response_text)
                synthesis_result = json.loads(json_text)

                # Success - return result
                if attempt > 0:
                    print(
                        f"✅ Synthesis succeeded on attempt {attempt + 1}/{max_retries} for {ticker}",
                    )

                return {
                    "signal": synthesis_result.get("signal", "neutral"),
                    "confidence": max(
                        0,
                        min(100, synthesis_result.get("confidence", 50)),
                    ),
                    "reasoning": synthesis_result.get("reasoning", ""),
                    "tool_impact_analysis": synthesis_result.get(
                        "tool_impact_analysis",
                        "",
                    ),
                    "synthesis_method": "llm_based",
                }

            except Exception as e:
                last_exception = e
                attempt_num = attempt + 1

                if attempt_num < max_retries:
                    # Calculate exponential backoff: 1s, 2s, 4s, ...
                    wait_time = 2**attempt
                    print(
                        f"⚠️ Synthesis attempt {attempt_num}/{max_retries} failed for {ticker}: {str(e)}",
                    )
                    print(f"   Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    # Final attempt failed
                    print(
                        f"❌ Synthesis failed after {max_retries} attempts for {ticker}: {str(e)}",
                    )

        # All retries exhausted
        return {
            "signal": "neutral",
            "confidence": 50,
            "reasoning": f"Failed to synthesize results after {max_retries} attempts",
            "tool_impact_analysis": "",
            "synthesis_method": "error",
            "error_details": str(last_exception)
            if last_exception
            else "Unknown error",
        }
