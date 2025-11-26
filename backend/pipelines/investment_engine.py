#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Investment Engine - Core investment analysis engine
Handles single-day analysis workflow: analysts → risk → portfolio manager → communications
"""

import sys
import os
import json
import traceback
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
import concurrent.futures
from copy import deepcopy
import threading
import pdb

# Add project path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from backend.graph.state import AgentState
from backend.config.constants import ANALYST_TYPES
from backend.agents.analyst_agent import AnalystAgent
from agentscope.message import Msg
from backend.config.agent_model_config import AgentModelRequest

# Import notification system
from backend.communication.notification_system import notification_system
from backend.communication import should_send_notification
from backend.utils.tool_call import tool_call
from backend.data.second_round_signals import SecondRoundAnalysis, TickerSignal
from agentscope.tool import Toolkit

# Import risk manager and portfolio manager - new architecture
from backend.agents.risk_manager_agent import RiskManagerAgent
from backend.agents.portfolio_manager_agent import PortfolioManagerAgent

# Import communication system
from backend.communication.chat_tools import (
    communication_manager,
    CommunicationDecision,
)

# Import logging configuration
from backend.utils.logger_config import setup_logging

from backend.agents.prompt_loader import PromptLoader

_prompt_loader = PromptLoader()
_personas_config = _prompt_loader.load_yaml_config("analyst", "personas")


# Setup quiet mode logging (disable HTTP request details)
setup_logging(
    level=logging.WARNING,
    log_file="../../investment_analysis_communications.log",
    quiet_mode=True,
)


class InvestmentEngine:
    """Core Investment Analysis Engine - Handles single-day complete analysis workflow"""

    def __init__(
        self,
        streamer=None,
        pause_before_trade=False,
        config_name: str = "default",
        sandbox_dir: str = None,
    ):
        """
        Initialize investment engine

        Args:
            streamer: Event streamer for UI updates
            pause_before_trade: Whether to pause before trade execution (only generate decisions, don't execute trades)
            config_name: Configuration name for directory paths
            sandbox_dir: Sandbox directory path (optional, will be computed from config_name if not provided)
        """
        self.streamer = streamer
        self.pause_before_trade = pause_before_trade
        self.config_name = config_name
        self.sandbox_dir = sandbox_dir

        # Add thread lock for parallel execution synchronization
        self._notification_lock = threading.Lock()

        # Create analyst instances
        self.core_analysts = {}
        for analyst_type, config in ANALYST_TYPES.items():
            if analyst_type == "comprehensive":
                continue  # Skip comprehensive analyst in core_analysts

            agent_id = config["agent_id"]
            self.core_analysts[agent_id] = {
                "name": config["display_name"],
                "agent": AnalystAgent(
                    analyst_type=analyst_type,
                    agent_id=agent_id,
                    description=config["description"],
                ),
                "description": config["description"],
            }

        logging.info("Investment engine initialized")

    def create_base_state(
        self,
        tickers: List[str],
        start_date: str,
        end_date: str,
        agent_model_request: Optional[AgentModelRequest] = None,
    ) -> AgentState:
        """
        Create base AgentState

        Args:
            tickers: List of stock tickers
            start_date: Start date for analysis
            end_date: End date for analysis
            agent_model_request: Optional AgentModelRequest for agent-specific model configuration
        """
        # Check environment variables
        api_key = os.getenv("FINANCIAL_DATASETS_API_KEY")
        openai_key = os.getenv("OPENAI_API_KEY")
        model_name = os.getenv("MODEL_NAME", "gpt-3.5-turbo")

        if not api_key or not openai_key:
            raise ValueError(
                "Missing required API keys, please check environment variables",
            )

        # Create agent model request if not provided (will load from env if available)
        if agent_model_request is None:
            agent_model_request = AgentModelRequest()

        state = AgentState(
            messages=[
                Msg(
                    name="system",
                    content="Advanced investment analysis session with communications",
                    role="system",
                ),
            ],
            data={
                "tickers": tickers,
                "start_date": start_date,
                "end_date": end_date,
                "analyst_signals": {},
                "communication_logs": {
                    "private_chats": [],
                    "meetings": [],
                    "communication_decisions": [],
                },
                "api_keys": {
                    "FINANCIAL_DATASETS_API_KEY": api_key,
                    "OPENAI_API_KEY": openai_key,
                },
            },
            metadata={
                "show_reasoning": False,
                "model_name": model_name,
                "model_provider": "OpenAI",
                "communication_enabled": True,
                "request": agent_model_request,  # Add agent model request
            },
        )

        return state

    def run_single_day_analysis(
        self,
        tickers: List[str],
        date: str,
        portfolio_state: Optional[Dict] = None,
        mode: str = "signal",
        enable_communications: bool = True,
        enable_notifications: bool = True,
        max_comm_cycles: int = 2,
        is_live_mode: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Run single-day complete analysis workflow

        Args:
            tickers: List of stock symbols
            date: Trading date (YYYY-MM-DD)
            portfolio_state: Current portfolio state (for portfolio mode)
            mode: Running mode ("signal" or "portfolio")
            enable_communications: Whether to enable communication mechanism
            enable_notifications: Whether to enable notification mechanism
            max_comm_cycles: Maximum communication cycles
            is_live_mode: Whether running in live mode (affects risk manager price selection)
            **kwargs: Additional parameters (initial_cash, margin_requirement, etc.)

        Returns:
            Single-day analysis result including updated portfolio state
        """
        # Calculate lookback start date (30 days)
        from datetime import datetime, timedelta

        date_obj = datetime.strptime(date, "%Y-%m-%d")
        lookback_start = (date_obj - timedelta(days=30)).strftime("%Y-%m-%d")

        # Create state
        state = self.create_base_state(tickers, lookback_start, date)
        state["metadata"]["communication_enabled"] = enable_communications
        state["metadata"]["notifications_enabled"] = enable_notifications
        state["metadata"]["max_communication_cycles"] = max_comm_cycles
        state["metadata"]["trading_date"] = date
        state["metadata"]["mode"] = mode
        state["metadata"]["is_live_mode"] = is_live_mode

        # Add analyst performance stats if available
        analyst_stats = kwargs.get("analyst_stats", None)
        if analyst_stats:
            state["data"]["analyst_stats"] = analyst_stats

        # Portfolio mode: initialize or inject portfolio state
        if mode == "portfolio":
            if portfolio_state:
                # Inject existing portfolio state
                state["data"]["portfolio"] = portfolio_state
            else:
                # Initialize new portfolio
                initial_cash = kwargs.get("initial_cash", 100000.0)
                margin_requirement = kwargs.get("margin_requirement", 0.0)

                state["data"]["portfolio"] = {
                    "cash": initial_cash,
                    "positions": {},
                    "margin_requirement": margin_requirement,
                    "margin_used": 0.0,
                }

        # Run full analysis workflow
        results = self.run_full_analysis_with_communications(
            tickers=tickers,
            start_date=lookback_start,
            end_date=date,
            parallel=True,
            enable_communications=enable_communications,
            enable_notifications=enable_notifications,
            state=state,
            mode=mode,
        )
        results["pre_portfolio_state"] = portfolio_state
        return results

    def run_full_analysis_with_communications(
        self,
        tickers: List[str],
        start_date: str,
        end_date: str,
        parallel: bool = True,
        enable_communications: bool = True,
        enable_notifications: bool = True,
        state: AgentState = None,
        mode: str = "signal",
    ) -> Dict[str, Any]:
        """
        Run complete analysis workflow with communications

        Args:
            tickers: List of stock symbols
            start_date: Start date
            end_date: End date
            parallel: Whether to run in parallel
            enable_communications: Whether to enable communication mechanism
            enable_notifications: Whether to enable notification mechanism
            state: Pre-created state object
            mode: Running mode ("signal" or "portfolio")
        """
        # Use provided state
        if state is None:
            state = self.create_base_state(tickers, start_date, end_date)
            state["metadata"]["communication_enabled"] = enable_communications
            state["metadata"]["notifications_enabled"] = enable_notifications
            state["metadata"]["mode"] = mode

        # Step 1: Run all analysts (first round)
        if parallel:
            analyst_results = self._run_analysts_parallel(state)
        else:
            analyst_results = self._run_analysts_sequential(state)

        # Step 2: Second round analysis based on notifications (optional)
        if enable_notifications:
            second_round_results = self._run_second_round_analysis(
                analyst_results,
                state,
                parallel,
            )
        else:
            second_round_results = (
                analyst_results  # Use first round results directly
            )

        # Step 3: Risk management analysis
        risk_analysis_results = self._run_risk_management_analysis(state, mode)

        # Step 4: Portfolio management decisions (including communication mechanism)
        # Check if in live mode and should defer trade execution
        is_live_mode = state.get("metadata", {}).get("is_live_mode", False)
        execute_trades = (
            not is_live_mode
        )  # In live mode, defer trade execution to after market close
        portfolio_management_results = (
            self._run_portfolio_management_with_communications(
                state,
                enable_communications,
                mode,
                execute_trades=execute_trades,
            )
        )

        # Generate final report
        final_report = self._generate_final_report(second_round_results, state)

        return {
            "first_round_results": analyst_results,
            "final_analyst_results": second_round_results,
            "risk_analysis_results": risk_analysis_results,
            "portfolio_management_results": portfolio_management_results,
            "communication_logs": state["data"]["communication_logs"],
            "final_report": final_report,
            "analysis_timestamp": datetime.now().isoformat(),
            "tickers": tickers,
            "date_range": {"start": start_date, "end": end_date},
            "updated_portfolio": state["data"].get(
                "portfolio",
            ),  # Return updated portfolio state
            "state": state,  # Return state for deferred trade execution in live mode
        }

    def _run_second_round_llm_analysis(
        self,
        agent_id: str,
        tickers: List[str],
        first_round_analysis: Dict[str, Any],
        overall_summary: Dict[str, Any],
        notifications: List[Dict[str, Any]],
        state: AgentState,
    ) -> SecondRoundAnalysis:
        """Run second round LLM analysis"""

        if agent_id not in _personas_config:
            raise ValueError(f"Unknown analyst ID: {agent_id}")

        persona = _personas_config[agent_id]

        analysis_focus_str = "\n".join(
            [f"- {focus}" for focus in persona["analysis_focus"]],
        )

        # Format notification information
        notifications_str = ""
        if notifications:
            notifications_str = "\n".join(
                [
                    f"- {notif.get('sender', 'Unknown')}: {notif.get('content', '')}"
                    for notif in notifications
                ],
            )
        else:
            notifications_str = "No notifications from other analysts yet"

        # Generate per-ticker reports
        ticker_reports = []
        for i, ticker in enumerate(tickers, 1):
            ticker_first_round = {}
            if isinstance(first_round_analysis, dict):
                if "ticker_signals" in first_round_analysis:
                    for signal in first_round_analysis["ticker_signals"]:
                        if signal.get("ticker") == ticker:
                            ticker_first_round = signal
                            break
                else:
                    ticker_first_round = first_round_analysis.get(ticker, {})
            # pdb.set_trace()
            try:
                ticker_first_round["tool_analysis"]["synthesis_details"]
            except:
                with open("../../../ticker_first_round.json", "w") as f:
                    json.dump(
                        ticker_first_round,
                        f,
                        ensure_ascii=False,
                        indent=2,
                    )

                # 保存first_round_analysis到txt文件,不一定是dict，最安全的保存方式
                with open(
                    "../../../first_round_analysis.txt",
                    "w",
                    encoding="utf-8",
                ) as f:
                    f.write(f"=== first_round_analysis ===\n\n")
                    f.write(f"Type: {type(first_round_analysis)}\n\n")
                    f.write(f"Content:\n{str(first_round_analysis)}\n\n")
                    f.write(f"Repr:\n{repr(first_round_analysis)}\n")

                # 抛出异常以便调试
                raise ValueError(
                    f"ticker_first_round structure is invalid for ticker {ticker}. Debug files saved to txt.",
                )

            ticker_report = f"""## Stock {i}: {ticker}

    ### Your First Round Analysis for {ticker}

    Analysis Result and Thought Process:
    {json.dumps(ticker_first_round['tool_analysis']['synthesis_details'], ensure_ascii=False, indent=2)}
    Analysis Tools Selection and Reasoning:
    {json.dumps(ticker_first_round['tool_selection'], ensure_ascii=False, indent=2)}

    """
            ticker_reports.append(ticker_report)

        variables = {
            "analyst_name": persona["name"],
            "specialty": persona["specialty"],
            "analysis_focus": analysis_focus_str,
            "decision_style": persona["decision_style"],
            "risk_preference": persona["risk_preference"],
            "ticker_reports": "\n".join(ticker_reports),
            "notifications": notifications_str,
            "agent_id": agent_id,
        }

        system_prompt = _prompt_loader.load_prompt(
            "analyst",
            "second_round_system",
            variables,
        )
        human_prompt = _prompt_loader.load_prompt(
            "analyst",
            "second_round_human",
            variables,
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": human_prompt},
        ]

        result = tool_call(
            messages=messages,
            pydantic_model=SecondRoundAnalysis,
            agent_name=agent_id,  # Use agent_id directly for correct model config
            state=state,
        )

        result.analyst_id = agent_id
        result.analyst_name = persona["name"]

        return result

    def _format_second_round_result_for_state(
        self,
        analysis: SecondRoundAnalysis,
    ) -> Dict[str, Any]:
        """Format second round analysis result for storage in AgentState"""
        return {
            "analyst_id": analysis.analyst_id,
            "analyst_name": analysis.analyst_name,
            "ticker_signals": [
                signal.model_dump() for signal in analysis.ticker_signals
            ],
            "timestamp": analysis.timestamp.isoformat(),
            "analysis_type": "second_round_llm",
        }

    def _run_analyst_with_notifications(
        self,
        agent_id: str,
        agent_info: Dict,
        state: AgentState,
    ) -> Dict[str, Any]:
        """Run single analyst and handle notification logic"""
        agent_name = agent_info["name"]
        agent = agent_info["agent"]

        # Get agent's notification memory
        agent_memory = notification_system.get_agent_memory(agent_id)

        # Execute analyst
        result = agent.execute(state)

        # Get analysis result
        analysis_result = state["data"]["analyst_signals"].get(agent_id, {})

        # print(f"{agent_name}: {analysis_result}")

        if analysis_result:
            # Write analysis result to agent memory

            analysis_date = state["metadata"].get("trading_date") or state[
                "data"
            ].get("end_date")
            ticker_signals = []

            for ticker, signal_data in analysis_result.items():
                if isinstance(signal_data, dict) and "signal" in signal_data:
                    ticker_signals.append(
                        f"{ticker}: {signal_data['signal']} (confidence: {signal_data.get('confidence', 'N/A')}%)",
                    )

                    # tools_details = "\n".join([f"{key}: {value}" for key, value in signal_data.get("tool_impact_analysis", {}).items()])
                    message = (
                        f"{ticker}: {signal_data['signal']} (confidence: {signal_data.get('confidence', 'N/A')}%)\n"
                        f"Analysis of {ticker}:\n"
                        f"{signal_data.get('reasoning', 'N/A')}\n"
                        # f"details_evidence_from_tools:\n{tools_details}"
                    )

                    self.streamer.print("agent", message, role_key=agent_id)
            from backend.memory import get_memory

            base_dir = (
                state.get("metadata", {}).get("config_name", "mock")
                if state
                else "mock"
            )
            memory = get_memory(base_dir=base_dir)

            # Filter analysis_result before storing in memory
            def filter_analysis_result(result: dict) -> dict:
                """Filter analysis_result: remove tool_selection and filter tool_results"""
                filtered = {}
                for ticker, ticker_data in result.items():
                    if isinstance(ticker_data, dict):
                        filtered_ticker_data = {
                            k: v
                            for k, v in ticker_data.items()
                            if k != "tool_selection"
                        }

                        # Filter tool_analysis.tool_results
                        if (
                            "tool_analysis" in filtered_ticker_data
                            and isinstance(
                                filtered_ticker_data["tool_analysis"],
                                dict,
                            )
                        ):
                            tool_analysis = filtered_ticker_data[
                                "tool_analysis"
                            ].copy()
                            if "tool_results" in tool_analysis and isinstance(
                                tool_analysis["tool_results"],
                                list,
                            ):
                                # Keep only specified fields in each tool_result
                                filtered_tool_results = []
                                for tool_result in tool_analysis[
                                    "tool_results"
                                ]:
                                    if isinstance(tool_result, dict):
                                        filtered_tool_result = {
                                            k: v
                                            for k, v in tool_result.items()
                                            if k
                                            in [
                                                "signal",
                                                "reasoning",
                                                "tool_name",
                                                "details",
                                                "selection_reason",
                                            ]
                                        }
                                        filtered_tool_results.append(
                                            filtered_tool_result,
                                        )
                                tool_analysis[
                                    "tool_results"
                                ] = filtered_tool_results
                            filtered_ticker_data[
                                "tool_analysis"
                            ] = tool_analysis

                        filtered[ticker] = filtered_ticker_data
                    else:
                        filtered[ticker] = ticker_data
                return filtered

            filtered_analysis_result = filter_analysis_result(analysis_result)

            memory.add(
                user_id=agent_id,
                content=f"[{analysis_date}] Analysis completed - {', '.join(ticker_signals) if ticker_signals else 'no signals'}"
                f"\nDetails: {filtered_analysis_result}",
                metadata={"type": "analysis_result", "date": analysis_date},
            )

            # Determine whether to send notification (optional)
            notifications_enabled = state["metadata"].get(
                "notifications_enabled",
                True,
            )
            if notifications_enabled:
                notification_decision = should_send_notification(
                    agent_id=agent_id,
                    analysis_result=analysis_result,
                    agent_memory=agent_memory,
                    state=state,
                )

                # Handle notification decision (with thread lock)
                if notification_decision.get("should_notify", False):
                    # Get trading_date as backtest_date
                    backtest_date = state.get("metadata", {}).get(
                        "trading_date",
                    ) or state.get("data", {}).get("end_date")

                    # Use thread lock to protect notification system's global state
                    with self._notification_lock:
                        notification_id = (
                            notification_system.broadcast_notification(
                                sender_agent=agent_id,
                                content=notification_decision["content"],
                                urgency=notification_decision.get(
                                    "urgency",
                                    "medium",
                                ),
                                category=notification_decision.get(
                                    "category",
                                    "general",
                                ),
                                backtest_date=backtest_date,
                            )
                        )

                    # Broadcast notification to all agents' memory
                    notification_content = f"[Notification] From {agent_id}: {notification_decision['content']}"
                    all_agent_ids = list(self.core_analysts.keys()) + [
                        "portfolio_manager",
                    ]
                    for recipient_id in all_agent_ids:
                        memory.add(
                            user_id=recipient_id,
                            content=f"[{backtest_date}] {notification_content}",
                            metadata={
                                "type": "notification",
                                "sender": agent_id,
                                "urgency": notification_decision.get(
                                    "urgency",
                                    "medium",
                                ),
                                "date": backtest_date,
                            },
                        )

                    if self.streamer:
                        self.streamer.print(
                            "agent",
                            f"📢 {notification_decision['content']} [Level of urgency: {notification_decision.get('urgency', 'medium')}]",
                            role_key=agent_id,
                        )
            else:
                notification_decision = {
                    "should_notify": False,
                    "reason": "Notification mechanism disabled",
                }

            return {
                "agent_id": agent_id,
                "agent_name": agent_name,
                "analysis_result": analysis_result,
                "notification_sent": notification_decision.get(
                    "should_notify",
                    False,
                ),
                "notification_decision": notification_decision,
                "status": "success",
            }
        else:
            return {
                "agent_id": agent_id,
                "agent_name": agent_name,
                "status": "no_result",
            }

    def _run_analysts_parallel(self, state: AgentState) -> Dict[str, Any]:
        """Execute all analysts in parallel"""
        start_time = datetime.now()

        # Create independent state copy for each analyst to avoid concurrency conflicts
        analyst_states = {}
        for agent_id in self.core_analysts.keys():
            analyst_states[agent_id] = deepcopy(state)

        analyst_results = {}

        # Use ThreadPoolExecutor for parallel execution
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            # Submit all tasks
            future_to_agent = {}
            for agent_id, agent_info in self.core_analysts.items():
                future = executor.submit(
                    self._run_analyst_with_notifications_safe,
                    agent_id,
                    agent_info,
                    analyst_states[agent_id],
                )
                future_to_agent[future] = agent_id

            # Collect results
            completed_count = 0
            for future in concurrent.futures.as_completed(future_to_agent):
                agent_id = future_to_agent[future]
                agent_name = self.core_analysts[agent_id]["name"]

                try:
                    result = future.result()
                    analyst_results[agent_id] = result
                    completed_count += 1

                    # Merge analysis results into main state
                    if (
                        result.get("status") == "success"
                        and "analysis_result" in result
                    ):
                        state["data"]["analyst_signals"][agent_id] = result[
                            "analysis_result"
                        ]

                except Exception as e:
                    analyst_results[agent_id] = {
                        "agent_id": agent_id,
                        "agent_name": agent_name,
                        "error": str(e),
                        "status": "error",
                    }

        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()

        return analyst_results

    def _run_analysts_sequential(self, state: AgentState) -> Dict[str, Any]:
        """Execute all analysts sequentially"""
        analyst_results = {}

        for agent_id, agent_info in self.core_analysts.items():
            result = self._run_analyst_with_notifications(
                agent_id,
                agent_info,
                state,
            )
            analyst_results[agent_id] = result

        return analyst_results

    def _run_analyst_with_notifications_safe(
        self,
        agent_id: str,
        agent_info: Dict,
        state: AgentState,
    ) -> Dict[str, Any]:
        """Thread-safe analyst execution function"""
        try:
            return self._run_analyst_with_notifications(
                agent_id,
                agent_info,
                state,
            )
        except Exception as e:
            logging.error(f"Error in {agent_id}: {str(e)}")
            return {
                "agent_id": agent_id,
                "agent_name": agent_info["name"],
                "error": str(e),
                "status": "error",
            }

    def _run_second_round_analysis(
        self,
        first_round_results: Dict[str, Any],
        state: AgentState,
        parallel: bool = True,
    ) -> Dict[str, Any]:
        """Run second round analysis: corrections based on first round results and notifications"""

        # Generate first round final_report
        first_round_report = self._generate_final_report(
            first_round_results,
            state,
        )

        # Execute second round analysis
        if parallel:
            second_round_results = self._run_second_round_parallel(
                first_round_report,
                state,
            )
        else:
            second_round_results = self._run_second_round_sequential(
                first_round_report,
                state,
            )

        return second_round_results

    def _run_second_round_parallel(
        self,
        first_round_report: Dict,
        state: AgentState,
    ) -> Dict[str, Any]:
        """Execute second round analysis in parallel"""
        start_time = datetime.now()

        # Create independent state copy for each analyst
        analyst_states = {}
        for agent_id in self.core_analysts.keys():
            analyst_states[agent_id] = deepcopy(state)
            # Clear first round analysis results to avoid conflicts
            analyst_states[agent_id]["data"]["analyst_signals"] = {}

        second_round_results = {}

        # Use ThreadPoolExecutor for parallel execution
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            # Submit all tasks
            future_to_agent = {}
            for agent_id, agent_info in self.core_analysts.items():
                future = executor.submit(
                    self._run_second_round_single_analyst,
                    agent_id,
                    agent_info,
                    first_round_report,
                    analyst_states[agent_id],
                )
                future_to_agent[future] = agent_id

            # Collect results
            for future in concurrent.futures.as_completed(future_to_agent):
                agent_id = future_to_agent[future]

                result = future.result()
                second_round_results[agent_id] = result

                # Merge analysis results into main state
                if (
                    result.get("status") == "success"
                    and "analysis_result" in result
                ):
                    state["data"]["analyst_signals"][agent_id] = result[
                        "analysis_result"
                    ]

        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()

        return second_round_results

    def _run_second_round_sequential(
        self,
        first_round_report: Dict,
        state: AgentState,
    ) -> Dict[str, Any]:
        """Execute second round analysis sequentially"""
        second_round_results = {}

        for agent_id, agent_info in self.core_analysts.items():
            result = self._run_second_round_single_analyst(
                agent_id,
                agent_info,
                first_round_report,
                state,
            )
            second_round_results[agent_id] = result

        return second_round_results

    def _run_second_round_single_analyst(
        self,
        agent_id: str,
        agent_info: Dict,
        first_round_report: Dict,
        state: AgentState,
    ) -> Dict[str, Any]:
        """Run single analyst's second round LLM analysis"""
        agent_name = agent_info["name"]

        # Extract required data
        tickers = state["data"]["tickers"]

        # Get first round analysis result
        first_round_analysis = first_round_report.get(
            "analyst_signals",
            {},
        ).get(agent_id, {})

        # Check if first_round_analysis is empty or incomplete, retry if needed
        max_retries = 10
        retry_count = 0

        while retry_count < max_retries:
            # Validate first_round_analysis structure
            is_valid = self._validate_first_round_analysis(
                first_round_analysis,
                tickers,
            )

            if is_valid:
                break

            # Log and retry
            retry_count += 1
            logging.warning(
                f"[{agent_id}] First round analysis is empty or incomplete (attempt {retry_count}/{max_retries}). Retrying first round analysis...",
            )

            try:
                # Retry first round analysis
                first_round_result = self._run_analyst_with_notifications(
                    agent_id,
                    agent_info,
                    state,
                )

                if (
                    first_round_result.get("status") == "success"
                    and "analysis_result" in first_round_result
                ):
                    first_round_analysis = first_round_result[
                        "analysis_result"
                    ]
                    # Update the state with the new result
                    state["data"]["analyst_signals"][
                        agent_id
                    ] = first_round_analysis
                    logging.info(
                        f"[{agent_id}] Successfully retried first round analysis",
                    )
                else:
                    logging.error(
                        f"[{agent_id}] Retry failed: {first_round_result.get('error', 'Unknown error')}",
                    )

            except Exception as e:
                logging.error(f"[{agent_id}] Exception during retry: {str(e)}")
                import traceback

                logging.debug(
                    f"Retry exception traceback:\n{traceback.format_exc()}",
                )

        # If still invalid after retries, raise an error
        if not self._validate_first_round_analysis(
            first_round_analysis,
            tickers,
        ):
            error_msg = f"[{agent_id}] First round analysis is still invalid after {max_retries} retries. Skipping second round analysis."
            logging.error(error_msg)
            raise ValueError(error_msg)

        # Get overall summary
        overall_summary = first_round_report.get("summary", {})

        # Get notification information
        notifications = []
        notification_activity = first_round_report.get(
            "notification_activity",
            {},
        )
        if "recent_notifications" in notification_activity:
            notifications = notification_activity["recent_notifications"]

        # Run LLM analysis
        llm_analysis = self._run_second_round_llm_analysis(
            agent_id=agent_id,
            tickers=tickers,
            first_round_analysis=first_round_analysis,
            overall_summary=overall_summary,
            notifications=notifications,
            state=state,
        )

        # Format result
        analysis_result = self._format_second_round_result_for_state(
            llm_analysis,
        )
        # Store in state
        state["data"]["analyst_signals"][
            f"{agent_id}_round2"
        ] = analysis_result

        return {
            "agent_id": agent_id,
            "agent_name": agent_name,
            "analysis_result": analysis_result,
            "llm_analysis": llm_analysis,
            "round": 2,
            "status": "success",
        }

    def _validate_first_round_analysis(
        self,
        first_round_analysis: Dict[str, Any],
        tickers: List[str],
    ) -> bool:
        """
        Validate if first round analysis has the required structure

        Args:
            first_round_analysis: First round analysis result to validate
            tickers: List of tickers that should be in the analysis

        Returns:
            True if valid, False otherwise
        """
        if not first_round_analysis or not isinstance(
            first_round_analysis,
            dict,
        ):
            return False

        # Check if analysis contains data for at least one ticker
        has_valid_ticker_data = False

        for ticker in tickers:
            ticker_data = first_round_analysis.get(ticker)

            if not ticker_data or not isinstance(ticker_data, dict):
                continue

            # Check for required nested structure
            if "tool_analysis" in ticker_data and isinstance(
                ticker_data["tool_analysis"],
                dict,
            ):
                tool_analysis = ticker_data["tool_analysis"]
                if (
                    "synthesis_details" in tool_analysis
                    and "tool_selection" in ticker_data
                ):
                    has_valid_ticker_data = True
                    break

        return has_valid_ticker_data

    def _run_risk_management_analysis(
        self,
        state: AgentState,
        mode: str = "signal",
    ) -> Dict[str, Any]:
        """
        Run risk management analysis

        Args:
            state: Current state
            mode: Running mode ("signal" or "portfolio")
        """
        # Select appropriate Risk Manager based on mode
        agent_id = "risk_manager"
        if mode == "portfolio":
            risk_agent = RiskManagerAgent(agent_id=agent_id, mode="portfolio")
        else:
            risk_agent = RiskManagerAgent(agent_id=agent_id, mode="basic")

        risk_result = risk_agent.execute(state)
        risk_analysis = state["data"]["analyst_signals"].get(agent_id, {})

        if risk_analysis:
            # Display risk analysis for each ticker
            for ticker, risk_data in risk_analysis.items():
                # Determine if it's signal mode or portfolio mode
                if "risk_level" in risk_data:
                    # Signal mode
                    risk_level = risk_data.get("risk_level", "unknown")
                    risk_score = risk_data.get("risk_score", 0)
                    annualized_vol = risk_data.get("volatility_info", {}).get(
                        "annualized_volatility",
                        0,
                    )
                    risk_assessment = risk_data.get("risk_assessment", "")

                    if self.streamer:
                        self.streamer.print(
                            "agent",
                            f"{ticker}: \n"
                            f"  Risk Level {risk_level.upper()}\n"
                            f"  Risk Score {risk_score}/100\n"
                            f"  Annualized Volatility {annualized_vol:.1%}\n"
                            f"  {risk_assessment}",
                            role_key="risk_manager",
                        )
                else:
                    # Portfolio mode
                    current_price = risk_data.get("current_price", 0)
                    vol_metrics = risk_data.get("volatility_metrics", {})
                    annualized_vol = vol_metrics.get(
                        "annualized_volatility",
                        0,
                    )
                    reasoning = risk_data.get("reasoning", {})
                    position_limit_pct = reasoning.get(
                        "base_position_limit_pct",
                        0,
                    )

                    if self.streamer:
                        self.streamer.print(
                            "agent",
                            f"{ticker}: \n"
                            f"  Price ${current_price:.2f}\n"
                            f"  Volatility {annualized_vol:.1%}\n"
                            f"  Position Limit {position_limit_pct:.1%}\n",
                            role_key="risk_manager",
                        )

            return {
                "agent_id": "risk_manager",
                "agent_name": "Risk Manager",
                "analysis_result": risk_analysis,
                "status": "success",
            }
        else:
            return {
                "agent_id": "risk_manager",
                "agent_name": "Risk Manager",
                "status": "no_result",
            }

    def _run_portfolio_management_with_communications(
        self,
        state: AgentState,
        enable_communications: bool = True,
        mode: str = "signal",
        execute_trades: bool = True,
    ) -> Dict[str, Any]:
        """
        Run portfolio management (including communication mechanism)

        Args:
            state: Current state
            enable_communications: Whether to enable communication mechanism
            mode: Running mode ("signal" or "portfolio")
            execute_trades: Whether to execute trades. If False, only generate decisions without execution (for live mode pre-market)
        """
        try:
            # Select appropriate Portfolio Manager based on mode
            # Prepare config with dashboard directory
            pm_config = {
                "config_name": self.config_name,
                "sandbox_dir": self.sandbox_dir,
            }
            if mode == "portfolio":
                pm_agent = PortfolioManagerAgent(
                    agent_id="portfolio_manager",
                    mode="portfolio",
                    config=pm_config,
                )
            else:
                pm_agent = PortfolioManagerAgent(
                    agent_id="portfolio_manager",
                    mode="direction",
                    config=pm_config,
                )

            portfolio_result = pm_agent.execute(state)

            # Update state
            if portfolio_result and "messages" in portfolio_result:
                state["messages"] = portfolio_result["messages"]
                state["data"] = portfolio_result["data"]

            # Get initial investment decisions
            initial_decisions = self._extract_portfolio_decisions(
                state,
                agent_name="portfolio_manager",
            )

            if not initial_decisions:
                return {
                    "agent_id": "portfolio_manager",
                    "agent_name": "Portfolio Manager",
                    "error": "Unable to get initial decisions",
                    "status": "error",
                }

            # If communications enabled
            if enable_communications:
                try:
                    max_cycles = int(
                        state["metadata"].get("max_communication_cycles", 3),
                    )
                except Exception:
                    max_cycles = 3

                final_decisions = initial_decisions
                last_decision_dump = None
                communication_results = {}

                for cycle in range(1, max_cycles + 1):
                    # Get analyst signals (refresh each round)
                    analyst_signals = {}
                    if cycle == 1:
                        for agent_id in self.core_analysts.keys():
                            if agent_id in state["data"]["analyst_signals"]:
                                analyst_signals[agent_id] = state["data"][
                                    "analyst_signals"
                                ][agent_id]
                    else:
                        analyst_signals = updated_signals

                    # Decide communication strategy
                    communication_decision = (
                        communication_manager.decide_communication_strategy(
                            manager_signals=final_decisions,
                            analyst_signals=analyst_signals,
                            state=state,
                        )
                    )
                    last_decision_dump = communication_decision.model_dump()

                    # Record communication decision
                    if (
                        "communication_decisions"
                        not in state["data"]["communication_logs"]
                    ):
                        state["data"]["communication_logs"][
                            "communication_decisions"
                        ] = []

                    state["data"]["communication_logs"][
                        "communication_decisions"
                    ].append(
                        {
                            "timestamp": datetime.now().isoformat(),
                            "decision": last_decision_dump,
                        },
                    )

                    if not communication_decision.should_communicate:
                        break

                    if self.streamer:
                        self.streamer.print(
                            "agent",
                            f"Communication type selected: {communication_decision.communication_type}\n"
                            f"Discussion topic: {communication_decision.discussion_topic}\n"
                            f"Target analysts: {', '.join(communication_decision.target_analysts)}",
                            role_key="portfolio_manager",
                        )

                    if (
                        communication_decision.communication_type
                        == "private_chat"
                    ):
                        # Conduct private chats
                        communication_results = self._conduct_private_chats(
                            communication_decision,
                            analyst_signals,
                            state,
                        )
                    elif (
                        communication_decision.communication_type == "meeting"
                    ):
                        # Conduct meeting
                        communication_results = self._conduct_meeting(
                            communication_decision,
                            analyst_signals,
                            state,
                        )
                    else:
                        communication_results = {}

                    # If signals adjusted, rerun portfolio decisions
                    if communication_results.get("signals_adjusted", False):
                        if self.streamer:
                            self.streamer.print(
                                "agent",
                                "Regenerating investment decisions based on communication results...",
                                role_key="portfolio_manager",
                            )

                        # Update analyst signals
                        updated_signals = communication_results.get(
                            "updated_signals",
                            {},
                        )
                        for (
                            agent_id,
                            updated_signal,
                        ) in updated_signals.items():
                            state["data"]["analyst_signals"][
                                f"{agent_id}_post_communication_cycle{cycle}"
                            ] = updated_signal

                        # Rerun portfolio management
                        # Prepare config with dashboard directory
                        pm_config = {
                            "config_name": self.config_name,
                            "sandbox_dir": self.sandbox_dir,
                        }
                        if mode == "portfolio":
                            pm_agent = PortfolioManagerAgent(
                                agent_id="portfolio_manager",
                                mode="portfolio",
                                config=pm_config,
                            )
                        else:
                            pm_agent = PortfolioManagerAgent(
                                agent_id="portfolio_manager",
                                mode="direction",
                                config=pm_config,
                            )

                        final_portfolio_result = pm_agent.execute(state)

                        if (
                            final_portfolio_result
                            and "messages" in final_portfolio_result
                        ):
                            state["messages"] = final_portfolio_result[
                                "messages"
                            ]
                            state["data"] = final_portfolio_result["data"]

                        new_final_decisions = (
                            self._extract_portfolio_decisions(
                                state,
                                agent_name="portfolio_manager",
                            )
                        )
                        if new_final_decisions:
                            final_decisions = new_final_decisions
                            if self.streamer:
                                self.streamer.print(
                                    "agent",
                                    "Investment decisions updated based on communication results",
                                    role_key="portfolio_manager",
                                )
                    else:
                        break

                # Execute final trading decisions (only if execute_trades=True)
                if not execute_trades:
                    # Live mode pre-market: Only generate decisions, do not execute trades yet
                    # Execution will happen after market close when we have closing prices
                    if self.streamer:
                        decision_lines = [
                            "Generated final trading decisions (will execute after market close):",
                        ]
                        for ticker, decision in final_decisions.items():
                            action = decision.get("action", "N/A")
                            confidence = decision.get("confidence", 0)
                            reasoning = decision.get("reasoning", "")

                            decision_lines.append(f"\n【{ticker}】")
                            decision_lines.append(f"  Decision: {action}")
                            if mode == "portfolio":
                                quantity = decision.get("quantity", 0)
                                decision_lines.append(
                                    f"  Quantity: {quantity} shares",
                                )
                            decision_lines.append(
                                f"  Confidence: {confidence}%",
                            )
                            if reasoning:
                                decision_lines.append(
                                    f"  💭 Reasoning: {reasoning}",
                                )

                        self.streamer.print(
                            "agent",
                            "\n".join(decision_lines),
                            role_key="portfolio_manager",
                        )

                    # Return decisions without execution
                    return {
                        "agent_id": "portfolio_manager",
                        "agent_name": "Portfolio Manager",
                        "initial_decisions": initial_decisions,
                        "final_decisions": final_decisions,
                        "communication_decision": last_decision_dump,
                        "communication_results": communication_results,
                        "final_execution_report": None,  # No execution yet
                        "portfolio_summary": {
                            "status": "signal_based_analysis",
                        },
                        "communications_enabled": True,
                        "status": "success",
                        "trades_deferred": True,  # Flag indicating trades are deferred
                    }

                # Execute final trading decisions
                if self.streamer:
                    decision_lines = ["Executing final trading decisions"]
                    for ticker, decision in final_decisions.items():
                        action = decision.get("action", "N/A")
                        confidence = decision.get("confidence", 0)
                        reasoning = decision.get("reasoning", "")

                        decision_lines.append(f"\n【{ticker}】")
                        decision_lines.append(f"  Decision: {action}")
                        if mode == "portfolio":
                            quantity = decision.get("quantity", 0)
                            decision_lines.append(
                                f"  Quantity: {quantity} shares",
                            )
                        decision_lines.append(f"  Confidence: {confidence}%")
                        if reasoning:
                            decision_lines.append(
                                f"  💭 Reasoning: {reasoning}",
                            )

                    self.streamer.print(
                        "agent",
                        "\n".join(decision_lines),
                        role_key="portfolio_manager",
                    )

                final_execution_report = self._execute_portfolio_trades(
                    state,
                    final_decisions,
                    mode,
                )

                # Generate simplified summary
                portfolio_summary = {"status": "signal_based_analysis"}

                return {
                    "agent_id": "portfolio_manager",
                    "agent_name": "Portfolio Manager",
                    "initial_decisions": initial_decisions,
                    "final_decisions": final_decisions,
                    "communication_decision": last_decision_dump,
                    "communication_results": communication_results,
                    "final_execution_report": final_execution_report,
                    "portfolio_summary": portfolio_summary,
                    "communications_enabled": True,
                    "status": "success",
                }

            else:
                # Communication mechanism disabled
                if not execute_trades:
                    # Live mode pre-market: Only generate decisions
                    return {
                        "agent_id": "portfolio_manager",
                        "agent_name": "Portfolio Manager",
                        "final_decisions": initial_decisions,
                        "execution_report": None,
                        "portfolio_summary": {
                            "status": "signal_based_analysis",
                        },
                        "communications_enabled": False,
                        "status": "success",
                        "trades_deferred": True,
                    }
                else:
                    # Execute initial decisions directly
                    execution_report = self._execute_portfolio_trades(
                        state,
                        initial_decisions,
                        mode,
                    )

                    # Generate simplified summary
                    portfolio_summary = {"status": "signal_based_analysis"}

                    return {
                        "agent_id": "portfolio_manager",
                        "agent_name": "Portfolio Manager",
                        "final_decisions": initial_decisions,
                        "execution_report": execution_report,
                        "portfolio_summary": portfolio_summary,
                        "communications_enabled": False,
                        "status": "success",
                    }

        except Exception as e:
            traceback.print_exc()
            return {
                "agent_id": "portfolio_manager",
                "agent_name": "Portfolio Manager",
                "error": str(e),
                "status": "error",
            }

    def _conduct_private_chats(
        self,
        communication_decision: CommunicationDecision,
        analyst_signals: Dict[str, Any],
        state: AgentState,
    ) -> Dict[str, Any]:
        """Conduct private chat communication"""
        if self.streamer:
            self.streamer.print(
                "system",
                f"===== Private Chat =====\nTopic: {communication_decision.discussion_topic}",
            )

        chat_results = {}
        updated_signals = {}
        total_adjustments = 0

        for analyst_id in communication_decision.target_analysts:
            if analyst_id in analyst_signals:
                if self.streamer:
                    self.streamer.print(
                        "system",
                        f"portfolio_manager <-> {analyst_id} starting private chat",
                    )

                chat_result = communication_manager.conduct_private_chat(
                    manager_id="portfolio_manager",
                    analyst_id=analyst_id,
                    topic=communication_decision.discussion_topic,
                    analyst_signal=analyst_signals[analyst_id],
                    state=state,
                    max_rounds=1,
                    streamer=self.streamer,
                )

                chat_results[analyst_id] = chat_result

                # Check if signal adjusted
                if "final_analyst_signal" in chat_result:
                    updated_signals[analyst_id] = chat_result[
                        "final_analyst_signal"
                    ]
                    adjustments = chat_result.get("adjustments_made", 0)
                    total_adjustments += adjustments

                    if self.streamer and adjustments > 0:
                        self.streamer.print(
                            "agent",
                            f"Signal adjusted {adjustments} times",
                            role_key=analyst_id,
                        )

                # Record to communication log
                state["data"]["communication_logs"]["private_chats"].append(
                    {
                        "timestamp": datetime.now().isoformat(),
                        "manager": "portfolio_manager",
                        "analyst": analyst_id,
                        "topic": communication_decision.discussion_topic,
                        "result": chat_result,
                    },
                )

        if self.streamer:
            self.streamer.print(
                "system",
                f"Private chat completed, {total_adjustments} signal adjustments in total",
            )

        return {
            "communication_type": "private_chat",
            "chat_results": chat_results,
            "updated_signals": updated_signals,
            "signals_adjusted": total_adjustments > 0,
            "total_adjustments": total_adjustments,
        }

    def _conduct_meeting(
        self,
        communication_decision: CommunicationDecision,
        analyst_signals: Dict[str, Any],
        state: AgentState,
    ) -> Dict[str, Any]:
        """Conduct meeting communication"""

        # Prepare meeting analyst signals
        meeting_signals = {}
        for analyst_id in communication_decision.target_analysts:
            if analyst_id in analyst_signals:
                meeting_signals[analyst_id] = analyst_signals[analyst_id]

        meeting_result = communication_manager.conduct_meeting(
            manager_id="portfolio_manager",
            analyst_ids=communication_decision.target_analysts,
            topic=communication_decision.discussion_topic,
            analyst_signals=meeting_signals,
            state=state,
            max_rounds=1,
            streamer=self.streamer,
        )

        # Record to communication log
        state["data"]["communication_logs"]["meetings"].append(
            {
                "timestamp": datetime.now().isoformat(),
                "meeting_id": meeting_result["meeting_id"],
                "host": "portfolio_manager",
                "participants": communication_decision.target_analysts,
                "topic": communication_decision.discussion_topic,
                "result": meeting_result,
            },
        )

        total_adjustments = meeting_result.get("adjustments_made", 0)

        if self.streamer:
            meeting_summary = [
                f"Meeting completed, {total_adjustments} signal adjustments in total",
            ]
            if total_adjustments > 0:
                meeting_summary.append(
                    f"Signals updated: {', '.join(meeting_result.get('final_signals', {}).keys())}",
                )
            self.streamer.print("system", "\n".join(meeting_summary))

        return {
            "communication_type": "meeting",
            "meeting_result": meeting_result,
            "updated_signals": meeting_result.get("final_signals", {}),
            "signals_adjusted": total_adjustments > 0,
            "total_adjustments": total_adjustments,
        }

    def _extract_portfolio_decisions(
        self,
        state: AgentState,
        agent_name: str = "portfolio_manager",
    ) -> Dict[str, Any]:
        """Extract portfolio decisions from state (AgentScope format)"""
        try:
            if state["messages"]:
                # Search from back for specified agent's message
                for message in reversed(state["messages"]):
                    # AgentScope format: {"name": str, "content": str, "role": str, "metadata": dict}
                    if isinstance(message, dict):
                        message_name = message.get("name")
                        message_content = message.get("content")

                        # Check if matches specified agent
                        if message_name == agent_name and message_content:
                            try:
                                return json.loads(message_content)
                            except json.JSONDecodeError:
                                # If content is not JSON, try to return directly
                                return (
                                    message_content
                                    if isinstance(message_content, dict)
                                    else {}
                                )
            return {}
        except Exception as e:
            import traceback

            return {}

    def execute_deferred_trades(
        self,
        state: AgentState,
        decisions: Dict[str, Any],
        mode: str = "signal",
        date: str = None,
    ) -> Dict[str, Any]:
        """
        Execute deferred trades (for live mode after market close)

        Args:
            state: Current state with decisions already generated
            decisions: PM decisions from pre-market analysis
            mode: Running mode ("signal" or "portfolio")
            date: Trading date (for updating current prices)

        Returns:
            Execution report
        """
        # Update end_date in state to current date (to get today's closing price)
        if date:
            state["data"]["end_date"] = date
            state["metadata"]["trading_date"] = date

        # Re-run risk manager to get today's closing prices
        # Set is_live_mode=False temporarily to get T-day closing price
        original_is_live_mode = state.get("metadata", {}).get(
            "is_live_mode",
            False,
        )
        state["metadata"]["is_live_mode"] = False  # Get today's closing price

        risk_analysis_results = self._run_risk_management_analysis(state, mode)

        # Extract current_prices from risk manager results
        analyst_signals = state["data"].get("analyst_signals", {})
        current_prices = {}

        # Extract current_prices from risk_manager signals (as user suggested)
        # Get tickers from decisions (since these are the ones we need to trade)
        tickers = list(decisions.keys())

        for agent, signals in analyst_signals.items():
            if agent.startswith("risk_manager"):
                # Risk management agent - extract risk information
                for ticker in tickers:
                    if ticker in signals:
                        risk_info = signals[ticker]
                        current_prices[ticker] = risk_info.get(
                            "current_price",
                            0,
                        )

        # Update state with current prices
        state["data"]["current_prices"] = current_prices

        # Restore original is_live_mode
        state["metadata"]["is_live_mode"] = original_is_live_mode

        # Now execute trades with updated prices
        if self.streamer:
            decision_lines = [
                "Executing final trading decisions (after market close):",
            ]
            for ticker, decision in decisions.items():
                action = decision.get("action", "N/A")
                confidence = decision.get("confidence", 0)
                reasoning = decision.get("reasoning", "")
                price = current_prices.get(ticker, 0)

                decision_lines.append(f"\n【{ticker}】")
                decision_lines.append(f"  Decision: {action}")
                decision_lines.append(f"  Closing Price: ${price:.2f}")
                if mode == "portfolio":
                    quantity = decision.get("quantity", 0)
                    decision_lines.append(f"  Quantity: {quantity} shares")
                decision_lines.append(f"  Confidence: {confidence}%")
                if reasoning:
                    decision_lines.append(f"  💭 Reasoning: {reasoning}")

            self.streamer.print(
                "agent",
                "\n".join(decision_lines),
                role_key="portfolio_manager",
            )

        final_execution_report = self._execute_portfolio_trades(
            state,
            decisions,
            mode,
        )

        return final_execution_report

    def _execute_portfolio_trades(
        self,
        state: AgentState,
        decisions: Dict[str, Any],
        mode: str = "signal",
    ) -> Dict[str, Any]:
        """
        Execute portfolio trading decisions

        Args:
            state: Current state
            decisions: PM decisions
            mode: Running mode ("signal" or "portfolio")
        """
        # If pause flag set, skip trade execution
        if self.pause_before_trade:
            if self.streamer:
                self.streamer.print(
                    "system",
                    "⏸️ Pause mode: Trading decisions generated but not executed. Price updates will continue.",
                )

            return {
                "status": "paused",
                "reason": "pause_before_trade=True, decisions generated but not executed",
                "decisions": decisions,
                "executed_trades": [],
                "failed_trades": [],
            }

        try:
            # Get current price data
            current_prices = state["data"].get("current_prices", {})
            if not current_prices:
                return {"status": "skipped", "reason": "Missing price data"}

            # Check for valid price data (price > 0)
            valid_prices = {
                ticker: price
                for ticker, price in current_prices.items()
                if price > 0
            }
            if not valid_prices:
                return {"status": "skipped", "reason": "No valid price data"}

            if mode == "portfolio":
                # Portfolio mode: Execute specific trades and update positions
                from backend.utils.trade_executor import (
                    execute_portfolio_trades,
                )

                portfolio = state["data"].get(
                    "portfolio",
                    {
                        "cash": 100000.0,
                        "positions": {},
                        "margin_requirement": 0.5,
                        "margin_used": 0.0,
                    },
                )

                execution_report = execute_portfolio_trades(
                    pm_decisions=decisions,
                    current_prices=current_prices,
                    portfolio=portfolio,
                    current_date=state["data"].get("end_date"),
                )

                # Update portfolio in state
                state["data"]["portfolio"] = execution_report.get(
                    "updated_portfolio",
                    portfolio,
                )

                # Add execution report to state
                if "execution_reports" not in state["data"]:
                    state["data"]["execution_reports"] = []
                state["data"]["execution_reports"].append(execution_report)

            else:
                # Signal mode: Only record directional signals
                from backend.utils.trade_executor import (
                    execute_trading_decisions,
                )

                execution_report = execute_trading_decisions(
                    pm_decisions=decisions,
                    current_date=state["data"].get("end_date"),
                )

                # Add execution report to state
                if "execution_reports" not in state["data"]:
                    state["data"]["execution_reports"] = []
                state["data"]["execution_reports"].append(execution_report)

            return execution_report

        except Exception as e:
            error_msg = f"Trade execution failed: {str(e)}"
            return {"status": "error", "error": error_msg}

    def _generate_final_report(
        self,
        analyst_results: Dict[str, Any],
        state: AgentState,
    ) -> Dict[str, Any]:
        """Generate final analysis report"""
        # pdb.set_trace()
        # Count analysis results
        successful_analyses = [
            r for r in analyst_results.values() if r["status"] == "success"
        ]
        failed_analyses = [
            r for r in analyst_results.values() if r["status"] == "error"
        ]

        # Count notification activity
        total_notifications_sent = sum(
            1 for r in successful_analyses if r.get("notification_sent", False)
        )

        # Collect all analysis signals
        all_signals = {}
        for result in successful_analyses:
            if "analysis_result" in result:
                all_signals[result["agent_id"]] = result["analysis_result"]

        report = {
            "summary": {
                "total_analysts": len(analyst_results),
                "successful_analyses": len(successful_analyses),
                "failed_analyses": len(failed_analyses),
                "notifications_sent": total_notifications_sent,
            },
            "analyst_signals": all_signals,
            "errors": [
                {"agent": r["agent_id"], "error": r["error"]}
                for r in failed_analyses
            ],
        }
        return report
