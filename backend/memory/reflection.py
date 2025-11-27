#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Memory Reflection System - Unified Memory Reflection System
Supports two modes:
- central_review: Unified LLM processes all agent memories
- individual_review: Each agent independently processes its own memories
"""
# flake8: noqa: E501
# pylint: disable=C0301
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.agents.prompt_loader import PromptLoader
from backend.config.constants import ROLE_TO_AGENT
from backend.config.path_config import get_logs_and_memory_dir
from backend.llm.models import ModelProvider, get_model

logger = logging.getLogger(__name__)


class MemoryOperationLogger:
    """Memory operation logger"""

    def __init__(self, base_dir: str):
        self.log_dir = (
            get_logs_and_memory_dir() / base_dir / "memory_operations"
        )
        self.log_dir.mkdir(parents=True, exist_ok=True)

        today = datetime.now().strftime("%Y%m%d")
        self.log_file = self.log_dir / f"memory_ops_{today}.jsonl"

    def log_operation(
        self,
        agent_id: str,
        operation_type: str,
        tool_name: str,
        args: Dict[str, Any],
        result: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ):
        """Log memory operation"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "agent_id": agent_id,
            "operation_type": operation_type,
            "tool_name": tool_name,
            "args": args,
            "result": result,
            "context": context or {},
        }

        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Failed to log: {e}")


class MemoryReflectionSystem:
    """Unified memory reflection system"""

    def __init__(self, base_dir: str = "mock", streamer=None):
        """
        Initialize reflection system

        Args:
            base_dir: Base directory (config_name)
            streamer: Message broadcaster
        """
        self.base_dir = base_dir
        self.streamer = streamer
        self.logger_system = MemoryOperationLogger(base_dir)
        self.prompt_loader = PromptLoader()

        # Initialize LLM
        model_name = os.getenv("MEMORY_LLM_MODEL", "gpt-4o-mini")
        model_provider_str = os.getenv("MEMORY_LLM_PROVIDER", "OPENAI")
        model_provider = getattr(
            ModelProvider,
            model_provider_str,
            ModelProvider.OPENAI,
        )

        api_keys: Dict[str, str] = {}
        openai_key = os.getenv("OPENAI_API_KEY")
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if model_provider == ModelProvider.OPENAI and openai_key:
            api_keys["OPENAI_API_KEY"] = openai_key
        elif model_provider == ModelProvider.ANTHROPIC and anthropic_key:
            api_keys["ANTHROPIC_API_KEY"] = anthropic_key

        # Create memory management toolkit and memory instance
        from backend.memory import get_memory
        from backend.tools.memory_tools import (
            _set_base_dir,
            create_memory_toolkit,
            set_memory_tools_streamer,
        )

        _set_base_dir(base_dir)  # Set base_dir for memory_tools to use
        self.toolkit = create_memory_toolkit()
        self.memory = get_memory(
            base_dir,
        )  # Get memory instance for direct operations

        # Set streamer
        if self.streamer:
            set_memory_tools_streamer(self.streamer)

        self.llm = get_model(model_name, model_provider, api_keys)
        self.llm_available = True

        logger.info(
            f"Memory reflection system initialized ({model_provider_str}: {model_name})",
        )

    def _get_agent_llm(self, state: Optional[Dict], agent_id: str):
        """
        Get LLM model for a specific agent

        Args:
            state: State object (optional)
            agent_id: Agent ID

        Returns:
            LLM model instance
        """
        if state is None:
            # Fallback to default LLM
            return self.llm

        from backend.utils.tool_call import get_agent_model_config

        # Get agent-specific model configuration
        model_name, model_provider = get_agent_model_config(state, agent_id)

        # Get API keys
        api_keys = {}
        if "data" in state and "api_keys" in state["data"]:
            api_keys = state["data"]["api_keys"]
        elif "metadata" in state:
            request = state.get("metadata", {}).get("request")
            if request and hasattr(request, "api_keys"):
                api_keys = request.api_keys

        # Create and return model instance
        return get_model(model_name, model_provider, api_keys or {})

    def perform_reflection(
        self,
        date: str,
        reflection_data: Dict[str, Any],
        mode: str = "individual_review",
        state: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Perform memory reflection

        Args:
            date: Trading date
            reflection_data: Reflection data
            mode: Mode ('central_review' or 'individual_review')
            state: Optional state object for getting agent-specific model configurations

        Returns:
            Reflection result
        """
        if mode == "central_review":
            return self._central_review(date, reflection_data, state)
        else:
            return self._individual_review(date, reflection_data, state)

    def _central_review(
        self,
        date: str,
        reflection_data: Dict[str, Any],
        state: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Central Review mode: Unified LLM processes all agent memories"""
        try:
            pm_signals = reflection_data.get("pm_signals", {})
            actual_returns = reflection_data.get("actual_returns", {})
            real_returns = reflection_data.get("real_returns", {})
            analyst_signals = reflection_data.get("analyst_signals", {})
            tickers = reflection_data.get("tickers", [])

            # Extract additional data from reflection_data (added by live_trading_fund.py)
            portfolio_summary = reflection_data.get("portfolio_summary", {})
            executed_trades = reflection_data.get("executed_trades", [])
            failed_trades = reflection_data.get("failed_trades", [])
            pre_portfolio_state = reflection_data.get(
                "pre_portfolio_state",
                {},
            )
            updated_portfolio = reflection_data.get("updated_portfolio", {})
            analyst_stats = reflection_data.get("analyst_stats", {})
            live_env = reflection_data.get("live_env", {})

            # Generate prompt with enhanced data
            prompt = self._build_central_review_prompt(
                date,
                tickers,
                pm_signals,
                analyst_signals,
                actual_returns,
                real_returns,
                portfolio_summary,
                executed_trades,
                failed_trades,
                pre_portfolio_state,
                updated_portfolio,
                analyst_stats,
                live_env,
            )

            logger.info(f"🤖 Central Review mode ({date})")

            # Get LLM model - use portfolio_manager's model for central review
            llm = self._get_agent_llm(state, "portfolio_manager")

            # Call LLM
            messages = [{"role": "user", "content": prompt}]
            response = llm(messages, temperature=0.7)
            response_content = (
                response.get("content", "")
                if isinstance(response, dict)
                else str(response)
            )

            # Parse response
            decision_data = self._parse_json_response(response_content)
            reasoning = decision_data.get("reflection_summary", "")
            need_tool = decision_data.get("need_tool", False)

            # Execute tool calls
            execution_results = []
            if need_tool and "selected_tool" in decision_data:
                execution_results = self._execute_tools(
                    decision_data["selected_tool"],
                    "central_review",
                    date,
                )

            logger.info(f"📝 Reflection summary: {reasoning[:200]}...")

            return {
                "status": "success",
                "mode": "central_review",
                "date": date,
                "reflection_summary": reasoning,
                "operations_count": len(execution_results),
                "execution_results": execution_results,
            }

        except Exception as e:
            logger.error(f"❌ Central Review failed: {e}", exc_info=True)
            return {
                "status": "failed",
                "mode": "central_review",
                "date": date,
                "error": str(e),
            }

    def _individual_review(
        self,
        date: str,
        reflection_data: Dict[str, Any],
        state: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Individual Review mode: Each agent independently processes"""
        all_results = []

        # Get all agents that need reflection
        agents_data = reflection_data.get("agents_data", {})

        for agent_id, agent_data in agents_data.items():
            result = self._agent_self_reflection(
                agent_id,
                date,
                agent_data,
                state,
            )
            all_results.append(result)

        return {
            "status": "success",
            "mode": "individual_review",
            "date": date,
            "agents_results": all_results,
            "total_agents": len(all_results),
        }

    def _agent_self_reflection(
        self,
        agent_id: str,
        date: str,
        agent_data: Dict[str, Any],
        state: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Single agent's self-reflection"""
        agent_role = ROLE_TO_AGENT.get(agent_id, agent_id)

        # If PM, first record daily decisions
        daily_record_result = None
        if agent_id == "portfolio_manager":
            daily_record_result = self._record_pm_daily_decisions(
                agent_id,
                date,
                agent_data,
            )
            if daily_record_result.get("status") == "success":
                logger.info(
                    f"📝 Recorded {daily_record_result.get('count', 0)} PM daily decisions",
                )

        # Generate prompt
        if agent_id == "portfolio_manager":
            prompt = self._build_pm_reflection_prompt(
                agent_role,
                date,
                agent_data,
            )
            # pdb.set_trace()
        else:
            prompt = self._build_analyst_reflection_prompt(
                agent_role,
                date,
                agent_data,
            )

        logger.info(f"🔍 {agent_role} self-reflection ({date})")

        # Get LLM model - use this agent's specific model
        llm = self._get_agent_llm(state, agent_id)

        # Call LLM
        messages = [{"role": "user", "content": prompt}]
        response = llm(messages, temperature=0.7)
        response_content = (
            response.get("content", "")
            if isinstance(response, dict)
            else str(response)
        )

        # Parse response
        decision_data = self._parse_json_response(response_content)
        reflection_summary = decision_data.get(
            "reflection_summary",
            response_content,
        )
        need_tool = decision_data.get("need_tool", False)

        # Execute tool calls
        memory_operations = []
        if need_tool and "selected_tool" in decision_data:
            tool_selection = decision_data["selected_tool"]

            # Verify analyst_id
            if (
                tool_selection.get("parameters", {}).get("analyst_id")
                == agent_id
            ):
                memory_operations = self._execute_tools(
                    [tool_selection],
                    agent_id,
                    date,
                )
            else:
                logger.warning(
                    f"⚠️ {agent_role} attempted to operate on another Agent's memory, blocked",
                )
        else:
            logger.info(
                f"💭 {agent_role} decided no memory tool operations needed",
            )

        logger.info(f"📝 {agent_role} reflection completed")

        result = {
            "status": "success",
            "agent_id": agent_id,
            "agent_role": agent_role,
            "date": date,
            "reflection_summary": reflection_summary,
            "memory_operations": memory_operations,
        }

        # If there's a daily record result, include it
        if daily_record_result:
            result["daily_record_result"] = daily_record_result

        return result

    def _record_pm_daily_decisions(
        self,
        agent_id: str,
        date: str,
        agent_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Record PM daily decisions to memory"""
        pm_decisions = agent_data.get("my_decisions", {})
        real_returns = agent_data.get("real_returns", {})
        analyst_signals = agent_data.get("analyst_signals", {})

        memories_added = 0
        for ticker, decision_data in pm_decisions.items():
            pm_action = decision_data.get("action", "N/A")
            pm_quantity = decision_data.get("quantity", 0)
            pm_confidence = decision_data.get("confidence", "N/A")
            pm_reasoning = decision_data.get("reasoning", "")
            real_return = real_returns.get(ticker, 0)

            # Build analyst signal summary
            analyst_summary = []
            for analyst_id, signals in analyst_signals.items():
                if ticker in signals:
                    signal_data = signals[ticker]
                    if isinstance(signal_data, dict):
                        signal = signal_data.get("signal", signal_data)
                        confidence = signal_data.get("confidence", "N/A")
                        analyst_summary.append(
                            f"{analyst_id}: {signal} (confidence: {confidence})",
                        )
                    else:
                        analyst_summary.append(f"{analyst_id}: {signal_data}")

            analyst_info = (
                "; ".join(analyst_summary)
                if analyst_summary
                else "No analyst signals"
            )

            # Evaluate decision outcome
            # decision_outcome = self._evaluate_decision(pm_action, real_return)
            # outcome_label = "✅ Correct" if decision_outcome else "❌ Incorrect"

            # Build record content
            if not isinstance(pm_reasoning, str):
                pm_reasoning = str(pm_reasoning) if pm_reasoning else ""

            content = f"""Date: {date}
Stock: {ticker}
PM Decision: {pm_action} (Quantity: {pm_quantity}, Confidence: {pm_confidence}%)
Decision Reasoning: {pm_reasoning if pm_reasoning else 'N/A'}
Analyst Opinions: {analyst_info}
Stock Real Return: {real_return:+.2%}"""
            print(content)

            metadata = {
                "type": "daily_decision",
                "date": date,
                "ticker": ticker,
                "action": pm_action,
                "confidence": pm_confidence,
            }

            # Add to memory
            memory_id = self.memory.add(content, agent_id, metadata)
            if memory_id:
                memories_added += 1

        logger.info(f"  ✅ Recorded {memories_added} PM daily decisions")
        return {"status": "success", "count": memories_added}

    def _execute_tools(
        self,
        tool_selections,
        agent_id: str,
        date: str,
    ) -> List[Dict[str, Any]]:
        """Execute tool calls"""
        if not isinstance(tool_selections, list):
            tool_selections = [tool_selections]

        results = []
        for tool_selection in tool_selections:
            tool_name = tool_selection.get("tool_name")
            tool_reason = tool_selection.get("reason", "")
            tool_params = tool_selection.get("parameters", {})

            logger.info(f"🛠️ Calling tool: {tool_name}")

            try:
                if tool_name in self.toolkit.tools:
                    tool_func = self.toolkit.tools[tool_name].original_func
                    result = tool_func(**tool_params)
                else:
                    result = {
                        "status": "failed",
                        "error": f"Tool not found: {tool_name}",
                    }

                results.append(
                    {
                        "tool_name": tool_name,
                        "reason": tool_reason,
                        "args": tool_params,
                        "result": result,
                    },
                )

                # Log operation
                self.logger_system.log_operation(
                    agent_id=agent_id,
                    operation_type="reflection",
                    tool_name=tool_name,
                    args=tool_params,
                    result=result,
                    context={"date": date},
                )

                logger.info("  ✅ Tool execution completed")
            except Exception as e:
                logger.error(f"  ❌ Tool execution failed: {e}")
                results.append(
                    {
                        "tool_name": tool_name,
                        "error": str(e),
                    },
                )

        return results

    def _build_central_review_prompt(
        self,
        date: str,
        tickers: List[str],
        pm_signals: Dict,
        analyst_signals: Dict,
        _actual_returns: Dict,
        real_returns: Dict,
        portfolio_summary: Dict = None,
        executed_trades: List = None,
        failed_trades: List = None,
        pre_portfolio_state: Dict = None,
        updated_portfolio: Dict = None,
        analyst_stats: Dict = None,
        live_env: Dict = None,
    ) -> str:
        """
        Build Central Review prompt (Enhanced version with more context data)
        Uses original memory_decision.md template but with enriched information
        """
        # Extract live environment data if available
        portfolio_data = self._extract_portfolio_data(
            live_env,
            pre_portfolio_state,
            updated_portfolio,
            executed_trades,
            failed_trades,
        )

        # Build all sections
        pm_signals_section = self._build_pm_signals_section(
            tickers,
            pm_signals,
            real_returns,
        )
        analyst_signals_section = self._build_analyst_signals_section(
            tickers,
            analyst_signals,
            real_returns,
            analyst_stats,
        )
        portfolio_context = self._build_portfolio_context(
            portfolio_summary,
            portfolio_data["executed_trades"],
            portfolio_data["failed_trades"],
        )
        analyst_performance_summary = self._build_analyst_performance_summary(
            analyst_stats,
        )

        # Combine sections
        enhanced_pm_section = (
            pm_signals_section
            + portfolio_context
            + analyst_performance_summary
        )

        # Use original memory_decision template with enhanced data
        prompt = self.prompt_loader.load_prompt(
            "memory",
            "memory_decision",
            {
                "date": date,
                "pm_signals_section": enhanced_pm_section,
                "analyst_signals_section": analyst_signals_section,
            },
        )

        return prompt

    def _extract_portfolio_data(
        self,
        live_env: Dict,
        pre_portfolio_state: Dict,
        updated_portfolio: Dict,
        executed_trades: List,
        failed_trades: List,
    ) -> Dict:
        """Extract portfolio data from live_env or fallback to provided data."""
        if not live_env:
            return {
                "pre_portfolio_state": pre_portfolio_state,
                "updated_portfolio": updated_portfolio,
                "executed_trades": executed_trades or [],
                "failed_trades": failed_trades or [],
            }

        return {
            "pre_portfolio_state": live_env.get(
                "pre_portfolio_state",
                pre_portfolio_state,
            ),
            "updated_portfolio": live_env.get(
                "updated_portfolio",
                updated_portfolio,
            ),
            "executed_trades": live_env.get(
                "executed_trades",
                executed_trades or [],
            ),
            "failed_trades": live_env.get(
                "failed_trades",
                failed_trades or [],
            ),
        }

    def _build_pm_signals_section(
        self,
        tickers: List[str],
        pm_signals: Dict,
        real_returns: Dict,
    ) -> str:
        """Build PM signals section with enhanced details."""
        section = ""
        for ticker in tickers:
            if ticker in pm_signals:
                section += self._format_pm_signal(
                    ticker,
                    pm_signals[ticker],
                    real_returns,
                )
        return section

    def _format_pm_signal(
        self,
        ticker: str,
        decision_data: Dict,
        real_returns: Dict,
    ) -> str:
        """Format a single PM signal entry."""
        action = decision_data.get("action", "N/A")
        signal = decision_data.get("signal", action)
        quantity = decision_data.get("quantity", 0)
        confidence = decision_data.get("confidence", "N/A")
        reasoning = decision_data.get("reasoning", "")

        # Ensure reasoning is a string
        reasoning = (
            str(reasoning)
            if reasoning and not isinstance(reasoning, str)
            else reasoning or ""
        )

        real_return = real_returns.get(ticker, 0)

        lines = [
            f"{ticker}: PM decision {signal} ",
            f"(Action: {action}, Quantity: {quantity} shares, Confidence: {confidence}%), ",
            f"Stock real daily return: {real_return:.2%}\n",
        ]

        if reasoning:
            lines.append(f"  Reasoning: {reasoning}\n")

        return "".join(lines)

    def _build_analyst_signals_section(
        self,
        tickers: List[str],
        analyst_signals: Dict,
        real_returns: Dict,
        analyst_stats: Dict = None,
    ) -> str:
        """Build analyst signals section with enhanced details."""
        from backend.config.constants import ANALYST_TYPES

        section = ""
        for analyst_id, signals in analyst_signals.items():
            display_name = ANALYST_TYPES.get(analyst_id, {}).get(
                "display_name",
                analyst_id,
            )

            # Add analyst header with historical performance
            section += f"\n**{display_name} ({analyst_id}):**"
            section += self._format_analyst_win_rate(analyst_id, analyst_stats)
            section += "\n"

            # Add signals for each ticker
            for ticker in tickers:
                if ticker in signals:
                    section += self._format_analyst_signal(
                        ticker,
                        signals[ticker],
                        real_returns,
                    )

        return section

    def _format_analyst_win_rate(
        self,
        analyst_id: str,
        analyst_stats: Dict,
    ) -> str:
        """Format analyst historical win rate if available."""
        if not analyst_stats or analyst_id not in analyst_stats:
            return ""

        win_rate = analyst_stats[analyst_id].get("win_rate")
        if win_rate is not None:
            return f" [Historical Win Rate: {win_rate:.1%}]"
        return ""

    def _format_analyst_signal(
        self,
        ticker: str,
        analyst_signal,
        real_returns: Dict,
    ) -> str:
        """Format a single analyst signal entry."""
        if isinstance(analyst_signal, dict):
            signal = analyst_signal.get("signal", "N/A")
            confidence = analyst_signal.get("confidence", "N/A")
            signal_text = f"{ticker}: {signal} (Confidence: {confidence}%), "
        else:
            signal_text = f"{ticker}: {analyst_signal}, "

        real_return = real_returns.get(ticker, 0)
        return f"  {signal_text}Stock real daily return: {real_return:.2%}\n"

    def _build_portfolio_context(
        self,
        portfolio_summary: Dict,
        executed_trades: List,
        failed_trades: List,
    ) -> str:
        """Build portfolio context section."""
        if not (portfolio_summary or executed_trades or failed_trades):
            return ""

        context = "\n## Portfolio Performance Context\n\n"

        if portfolio_summary:
            context += self._format_portfolio_summary(portfolio_summary)

        if executed_trades:
            context += self._format_executed_trades(executed_trades)

        if failed_trades:
            context += self._format_failed_trades(failed_trades)

        return context

    def _format_portfolio_summary(self, portfolio_summary: Dict) -> str:
        """Format portfolio summary information."""
        lines = []

        total_value = portfolio_summary.get("total_value", "N/A")
        if isinstance(total_value, (int, float)):
            lines.append(f"- Total Portfolio Value: ${total_value:,.2f}\n")
        else:
            lines.append(f"- Total Portfolio Value: {total_value}\n")

        cash = portfolio_summary.get("cash", "N/A")
        if isinstance(cash, (int, float)):
            lines.append(f"- Cash Position: ${cash:,.2f}\n")
        else:
            lines.append(f"- Cash Position: {cash}\n")

        return "".join(lines)

    def _format_executed_trades(self, executed_trades: List) -> str:
        """Format executed trades information."""
        lines = [f"- Successfully Executed Trades: {len(executed_trades)}\n"]

        for trade in executed_trades[:3]:  # Show first 3 trades
            if isinstance(trade, dict):
                ticker = trade.get("ticker", "N/A")
                action = trade.get("action", "N/A")
                quantity = trade.get("quantity", 0)
                lines.append(f"  * {ticker}: {action} {quantity} shares\n")

        return "".join(lines)

    def _format_failed_trades(self, failed_trades: List) -> str:
        """Format failed trades information."""
        lines = [f"- Failed Trades: {len(failed_trades)}\n"]

        for trade in failed_trades[:3]:  # Show first 3 failed trades
            if isinstance(trade, dict):
                ticker = trade.get("ticker", "N/A")
                reason = trade.get("reason", "Unknown")
                lines.append(f"  * {ticker}: {reason}\n")

        return "".join(lines)

    def _build_analyst_performance_summary(self, analyst_stats: Dict) -> str:
        """Build analyst historical performance summary."""
        if not analyst_stats:
            return ""

        summary = "\n## Analyst Historical Performance Summary\n\n"

        # Sort by win rate (descending)
        sorted_analysts = sorted(
            analyst_stats.items(),
            key=lambda x: (
                x[1]["win_rate"] is not None,
                x[1]["win_rate"] or 0,
            ),
            reverse=True,
        )

        for analyst_id, stats in sorted_analysts:
            analyst_line = self._format_analyst_stats(analyst_id, stats)
            if analyst_line:
                summary += analyst_line

        return summary

    def _format_analyst_stats(self, analyst_id: str, stats: Dict) -> str:
        """Format a single analyst's performance stats."""
        win_rate = stats.get("win_rate")
        total = stats.get("total_predictions", 0)
        correct = stats.get("correct_predictions", 0)

        # Skip if no data
        if win_rate is None or total == 0:
            return ""

        from backend.config.constants import ANALYST_TYPES

        display_name = ANALYST_TYPES.get(analyst_id, {}).get(
            "display_name",
            analyst_id,
        )

        return f"- **{display_name}**: Win Rate {win_rate:.1%} ({correct}/{total} predictions)\n"

    def _build_analyst_reflection_prompt(
        self,
        agent_role: str,
        date: str,
        agent_data: Dict,
    ) -> str:
        """Build analyst reflection prompt"""
        my_signals = agent_data.get("my_signals", {})
        actual_returns = agent_data.get("actual_returns", {})
        real_returns = agent_data.get("real_returns", {})
        pm_decisions = agent_data.get("pm_decisions", {})

        signals_data = ""
        for ticker, signal_data in my_signals.items():
            actual_return = actual_returns.get(ticker, 0)
            signal = signal_data.get("signal", "N/A")
            confidence = signal_data.get("confidence", "N/A")
            reasoning = signal_data.get("reasoning", "")

            # Ensure reasoning is a string
            if not isinstance(reasoning, str):
                reasoning = str(reasoning) if reasoning else ""

            is_correct = self._evaluate_prediction(signal, actual_return)
            status_emoji = "✅" if is_correct else "❌"

            signals_data += f"""
{ticker}: {status_emoji}
  - Your signal: {signal} (confidence: {confidence}%)
  - Your reasoning: {reasoning[:200] if reasoning else 'N/A'}
  - Stock real daily return: {real_returns.get(ticker, 0):.2%}
  - PM decision: {pm_decisions.get(ticker, {}).get('action', 'N/A')}
"""

        return self.prompt_loader.load_prompt(
            "reflection",
            "analyst_reflection_system",
            {
                "agent_role": agent_role,
                "date": date,
                "agent_id": agent_data.get("agent_id", ""),
                "signals_data": signals_data,
                "context_data": "",
            },
        )

    def _build_pm_reflection_prompt(
        self,
        _agent_role: str,
        date: str,
        agent_data: Dict,
    ) -> str:
        """Build PM reflection prompt"""
        pm_decisions = agent_data.get("my_decisions", {})
        analyst_signals = agent_data.get("analyst_signals", {})
        real_returns = agent_data.get("real_returns", {})
        analyst_stats = agent_data.get("analyst_stats", {})

        # Build analyst historical performance data
        analyst_performance_data = self._build_analyst_performance_data(
            analyst_stats,
        )

        # Build decision data
        decisions_data = self._build_decisions_data(
            pm_decisions,
            analyst_signals,
            real_returns,
        )

        # Build portfolio data
        portfolio_data = self._build_portfolio_data(agent_data["live_env"])

        prompt = self.prompt_loader.load_prompt(
            "reflection",
            "pm_reflection_system",
            {
                "date": date,
                "portfolio_data": portfolio_data,
                "decisions_data": decisions_data,
                "analyst_performance_data": analyst_performance_data,
            },
        )

        return prompt

    def _build_analyst_performance_data(self, analyst_stats: Dict) -> str:
        """Build analyst historical performance data"""
        if not analyst_stats:
            return ""

        analyst_performance_data = ""
        sorted_analysts = sorted(
            analyst_stats.items(),
            key=lambda x: (
                x[1]["win_rate"] is not None,
                x[1]["win_rate"] or 0,
            ),
            reverse=True,
        )

        for analyst_id, stats in sorted_analysts:
            win_rate = stats.get("win_rate")
            total = stats.get("total_predictions", 0)
            correct = stats.get("correct_predictions", 0)
            bull_stats = stats.get("bull", {})
            bear_stats = stats.get("bear", {})

            # Skip if no data
            if win_rate is None or total == 0:
                continue

            # Get display name
            from backend.config.constants import ANALYST_TYPES

            display_name = ANALYST_TYPES.get(analyst_id, {}).get(
                "display_name",
                analyst_id,
            )

            analyst_performance_data += f"""
    {display_name} ({analyst_id})
    - Historical Win Rate: {win_rate:.1%} ({correct}/{total} correct)
    - Bull Signals: {bull_stats.get('win', 0)}/{bull_stats.get('count', 0)} correct
    - Bear Signals: {bear_stats.get('win', 0)}/{bear_stats.get('count', 0)} correct
    """
        return analyst_performance_data

    def _build_decisions_data(
        self,
        pm_decisions: Dict,
        analyst_signals: Dict,
        real_returns: Dict,
    ) -> str:
        """Build decision data"""
        decisions_data = ""
        for ticker, decision_data in pm_decisions.items():
            action = decision_data.get("action", "N/A")
            quantity = decision_data.get("quantity", 0)
            confidence = decision_data.get("confidence", "N/A")
            reasoning = decision_data.get("reasoning", "")

            # Ensure reasoning is a string
            if not isinstance(reasoning, str):
                reasoning = str(reasoning) if reasoning else ""

            decisions_data += f"""
    {ticker}:
    - Your decision: {action}
    - Quantity: {quantity} shares
    - Confidence: {confidence}%
    - Decision reasoning: {reasoning if reasoning else 'N/A'}
    - Stock real daily return: {real_returns.get(ticker, 0):.2%}
    """

            # Add analyst opinion comparison
            decisions_data += "  - Analyst opinions:\n"
            for analyst_id, signals in analyst_signals.items():
                if ticker in signals:
                    analyst_signal = signals[ticker]
                    if isinstance(analyst_signal, dict):
                        signal = analyst_signal.get("signal", "N/A")
                        decisions_data += f"    * {analyst_id}: {signal}, Stock real daily return: {real_returns.get(ticker, 0):.2%}\n"
                    else:
                        decisions_data += f"    * {analyst_id}: {analyst_signal}, Stock real daily return: {real_returns.get(ticker, 0):.2%}\n"

        return decisions_data

    def _build_portfolio_data(self, live_env: Dict) -> str:
        """Build portfolio data"""
        pre_portfolio_state = live_env["pre_portfolio_state"]
        updated_portfolio_state = live_env["updated_portfolio"]
        executed_trades = live_env["executed_trades"]
        failed_trades = live_env["failed_trades"]

        # Remove timestamp field from each trade
        executed_trades_filtered = [
            {k: v for k, v in trade.items() if k != "timestamp"}
            if isinstance(trade, dict)
            else trade
            for trade in executed_trades
        ]

        failed_trades_filtered = [
            {k: v for k, v in trade.items() if k != "timestamp"}
            if isinstance(trade, dict)
            else trade
            for trade in failed_trades
        ]

        return f"""
    - Pre portfolio state: {pre_portfolio_state}
    - Updated portfolio state: {updated_portfolio_state}
    - Today Executed trades: {executed_trades_filtered}
    - Today Failed trades: {failed_trades_filtered}
    """

    def _evaluate_prediction(self, signal: str, actual_return: float) -> bool:
        """Evaluate if prediction is correct"""
        threshold = 0.005
        signal_lower = (signal or "").lower()

        if (
            signal_lower in ["buy", "bullish", "long"]
            and actual_return > threshold
        ):
            return True
        elif (
            signal_lower in ["sell", "bearish", "short"]
            and actual_return < -threshold
        ):
            return True
        elif (
            signal_lower in ["hold", "neutral"]
            and abs(actual_return) <= threshold
        ):
            return True
        return False

    def _evaluate_decision(self, action: str, actual_return: float) -> bool:
        """Evaluate if decision is correct"""
        return self._evaluate_prediction(action, actual_return)

    def _parse_json_response(self, response_content: str) -> dict:
        """Parse JSON response"""
        try:
            json_start = response_content.find("{")
            json_end = response_content.rfind("}") + 1
            if json_start != -1 and json_end > json_start:
                json_str = response_content[json_start:json_end]
                return json.loads(json_str)
            return json.loads(response_content)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parsing failed: {e}")
            return {
                "reflection_summary": response_content,
                "need_tool": False,
            }


def create_reflection_system(
    base_dir: str = "mock",
    streamer=None,
) -> MemoryReflectionSystem:
    """Create memory reflection system"""
    return MemoryReflectionSystem(base_dir, streamer)
