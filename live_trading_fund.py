#!/usr/bin/env python3
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
import pdb
import os
import sys
import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import defaultdict
from dotenv import load_dotenv

from src.config.constants import ANALYST_TYPES
from src.memory import MemoryReflectionSystem, get_memory
from src.servers.streamer import ConsoleStreamer
from src.dashboard.team_dashboard import TeamDashboardGenerator

load_dotenv()
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
current_dir = os.path.dirname(os.path.abspath(__file__))

# Import refactored modules
from investment_engine import InvestmentEngine
from multi_day_strategy import MultiDayStrategy

from src.config.env_config import LiveThinkingFundConfig


class LiveTradingFund:
    """Live Trading Thinking Fund - Sandbox time simulation system"""

    def __init__(
        self,
        config_name: str,
        streamer=None,
        mode: str = "portfolio",
        initial_cash: float = 100000.0,
        margin_requirement: float = 0.0,
        pause_before_trade: bool = False
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
        from src.config.path_config import get_directory_config
        
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
        engine = InvestmentEngine(streamer=self.streamer, pause_before_trade=pause_before_trade)
        
        # Initialize multi-day strategy manager
        self.strategy = MultiDayStrategy(
            engine=engine,
            config_name=config_name,
            mode=mode,
            initial_cash=initial_cash,
            margin_requirement=margin_requirement,
            prefetch_data=True
        )

        # Initialize memory management system
        try:
            self.memory_reflection = MemoryReflectionSystem(base_dir=config_name, streamer=self.streamer)
            print("Memory reflection system enabled")
        except Exception as e:
            self.memory_reflection = None
            print(f"Memory reflection system not enabled: {e}")

        # Time point definitions
        self.PRE_MARKET = "pre_market"    # Pre-market
        self.POST_MARKET = "post_market"  # Post-market
        
        # Portfolio mode parameters
        self.mode = mode
        self.initial_cash = initial_cash
        self.margin_requirement = margin_requirement
        
        # Initialize team dashboard generator
        dashboard_dir = self.sandbox_dir / "team_dashboard"
        self.dashboard_generator = TeamDashboardGenerator(
            dashboard_dir=dashboard_dir,
            initial_cash=initial_cash
        )
        # Initialize empty dashboard (if not exists)
        if not (dashboard_dir / "summary.json").exists():
            self.dashboard_generator.initialize_empty_dashboard()

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

    def should_run_sandbox_analysis(self, date: str, time_point: str, force_run: bool = False) -> bool:
        """Determine whether to run sandbox analysis (independent of live_system check logic)"""
        if force_run:
            return True

        # Check if sandbox log has successful record
        existing_data = self._load_sandbox_log(date, time_point)
        if existing_data and existing_data.get('status') == 'success':
            return False

        return True

    def run_pre_market_analysis(
        self,
        date: str,
        tickers: List[str],
        max_comm_cycles: int = 2,
        force_run: bool = False,
        enable_communications: bool = False,
        enable_notifications: bool = False,
        skip_real_returns: bool = False
    ) -> Dict[str, Any]:
        """Run pre-market analysis
        
        Args:
            skip_real_returns: 如果为 True，则不计算 real_returns（用于 live 模式盘前分析）
        """
        self.streamer.print("system", 
            f"===== Pre-Market Analysis ({date}) =====\n"
            f"Time point: {self.PRE_MARKET}\n"
            f"Analysis targets: {', '.join(tickers)}")

        # Run single day analysis (inject portfolio state)
        result = self.strategy.run_single_day(
            tickers=tickers,
            date=date,
            enable_communications=enable_communications,
            enable_notifications=enable_notifications,
            max_comm_cycles=max_comm_cycles
        )

        # Use defaultdict to simplify initialization
        live_env = {
            'pm_signals': {},
            'ana_signals': defaultdict(lambda: defaultdict(str)),  # Automatically create nested dict, default value is empty string
            'real_returns': defaultdict(float)  # Auto-create, default value is 0.0
        }

        # Extract PM signals
        pm_results = result.get('portfolio_management_results', {})
        final_decisions = pm_results.get('final_decisions', {})
        live_env['pm_signals'] = final_decisions

        # Extract analyst signals
        print("[system]", "===== Analyst Signal Details =====")
        
        analyst_results = result.get('final_analyst_results', {})

        for agent_id in ANALYST_TYPES.keys():
            if agent_id not in analyst_results:
                continue
                
            analyst_result = analyst_results[agent_id].get('analysis_result', {})
            
            # Format: {ticker_signals: [{ticker, signal, confidence, ...}]}
            signals = []
            if 'ticker_signals' in analyst_result:
                for item in analyst_result['ticker_signals']:
                    ticker = item['ticker']
                    live_env['ana_signals'][agent_id][ticker] = item
                    signals.append(f"{ticker}: {item['signal']} (confidence:{item.get('confidence', 'N/A')}%)")
            else:
                # Fallback format: {ticker: {signal, confidence, ...}}
                for ticker in tickers:
                    if ticker in analyst_result and 'signal' in analyst_result[ticker]:
                        live_env['ana_signals'][agent_id][ticker] = analyst_result[ticker]
                        confidence = analyst_result[ticker].get('confidence', 'N/A')
                        signals.append(f"{ticker}: {analyst_result[ticker]['signal']} (confidence:{confidence}%)")
            
            if signals:
                self.streamer.print("agent", "\n".join(signals), role_key=agent_id)

        # Calculate daily returns (跳过如果是 live 模式盘前分析)
        if not skip_real_returns:
            for ticker in tickers:
                if ticker in final_decisions:
                    action = final_decisions[ticker].get('action', 'hold')
                    daily_return, real_return, close_price = self.strategy._calculate_stock_daily_return_from_signal(
                        ticker, date, action
                    )
                    live_env['real_returns'][ticker] = daily_return
        else:
            # Live 模式：real_returns 设为 None（表示未知）
            for ticker in tickers:
                if ticker in final_decisions:
                    live_env['real_returns'][ticker] = None

        print("[system]", f"{date} Sandbox analysis completed")

        # Display stock performance
        for ticker in tickers:
            if ticker in final_decisions:
                signal_info = final_decisions[ticker]
                signal = signal_info.get('signal', 'N/A')
                action = signal_info.get('action', 'N/A')
                confidence = signal_info.get('confidence', 0)
                reasoning = signal_info.get('reasoning', 0)
                # pdb.set_trace()
                if skip_real_returns:
                    # Live 模式：不显示 daily return（还未知）
                    if self.mode == "signal":
                        self.streamer.print("agent", 
                            f"{ticker}: Final signal {signal}(confidence {confidence}%) \n{reasoning}",
                            role_key='portfolio_manager'
                        )
                    elif self.mode == "portfolio":
                        quantity = signal_info.get('quantity', 0)
                        self.streamer.print("agent", 
                            f"{ticker}: Final signal {action}({quantity} shares, confidence {confidence}%) \n{reasoning}",
                            role_key='portfolio_manager'
                        )
                else:
                    # 回测模式：显示 daily return
                    daily_ret = live_env['real_returns'].get(ticker, 0) * 100
                    if self.mode == "signal":
                        self.streamer.print("agent", 
                            f"{ticker}: Final signal {signal}(confidence {confidence}%, daily return {daily_ret:.2f}%) \n{reasoning}",
                            role_key='portfolio_manager'
                        )
                    elif self.mode == "portfolio":
                        quantity = signal_info.get('quantity', 0)
                        self.streamer.print("agent", 
                            f"{ticker}: Final signal {action}({quantity} shares, confidence {confidence}%, stock daily return {daily_ret:.2f}%) \n{reasoning}",
                            role_key='portfolio_manager'
                        )

        # Portfolio mode: Add portfolio info
        if self.mode == "portfolio":
            live_env['portfolio_summary'] = pm_results.get('portfolio_summary', {})
            live_env['updated_portfolio'] = result.get('updated_portfolio', {})

        # Record to sandbox log
        self._log_sandbox_activity(date, self.PRE_MARKET, {
            'status': 'success',
            'tickers': tickers,
            'timestamp': datetime.now().isoformat(),
            'details': result
        })
        
        # Update team dashboard data
        dashboard_update_stats = self.dashboard_generator.update_from_day_result(
            date=date,
            pre_market_result={'live_env': live_env, 'raw_results': result},
            mode=self.mode
        )
        self.streamer.print("system", 
            f"Team dashboard updated: {dashboard_update_stats.get('trades_added', 0)} trades added, "
            f"{dashboard_update_stats.get('agents_updated', 0)} agents updated")
       

        return {
            'status': 'success',
            'date': date,
            'live_env': live_env
        }

    def run_post_market_review(self, date: str, tickers: List[str], live_env: Dict[str, Any]) -> Dict[str, Any]:
        """Run post-market review"""
        self.streamer.print("system", 
            f"===== Post-Market Review ({date}) =====\n"
            f"Time point: {self.POST_MARKET}\n"
            f"Review targets: {', '.join(tickers)}")

        if live_env != 'Not trading day':
            # Post-market review logic
            result = self._perform_post_market_review(date, tickers, live_env)

            # Record to sandbox log
            self._log_sandbox_activity(date, self.POST_MARKET, result)

            return result
        else:
            return {'status': 'skipped', 'reason': 'Not trading day'}

    def _perform_post_market_review(self, date: str, tickers: List[str], live_env: Dict[str, Any]) -> Dict[str, Any]:
        """Execute post-market review analysis"""

        pm_signals = live_env['pm_signals']
        ana_signals = live_env['ana_signals']
        real_returns = live_env['real_returns']

        # 1. Portfolio Manager signal review (display different info based on mode)
        pm_review_lines = ["Reviewing based on pre-market analysis...", "Portfolio Manager signal review:"]
        
        if self.mode == "portfolio":
            # Portfolio mode: Display detailed operation info
            for ticker in tickers:
                if ticker in pm_signals:
                    signal_info = pm_signals[ticker]
                    action = signal_info.get('action', 'N/A')
                    quantity = signal_info.get('quantity', 0)
                    confidence = signal_info.get('confidence', 'N/A')
                    reasoning = signal_info.get('reasoning', '')
                    
                    # Display operation and quantity
                    if quantity > 0:
                        pm_review_lines.append(
                            f"  {ticker}: {action} ({quantity} shares, confidence: {confidence}%)"
                        )
                    else:
                        pm_review_lines.append(
                            f"  {ticker}: {action} ( confidence: {confidence}%)"
                        )
                    
                    # Add decision reasoning
                    if reasoning:
                        pm_review_lines.append(f"    💭 Reasoning: {reasoning}")
                else:
                    pm_review_lines.append(f"  {ticker}: No signal data")
        else:
            # Signal mode: Display traditional signal info
            for ticker in tickers:
                if ticker in pm_signals:
                    signal_info = pm_signals[ticker]
                    reasoning = signal_info.get('reasoning', '')
                    pm_review_lines.append(
                        f"  {ticker}: {signal_info['signal']} (confidence: {signal_info.get('confidence', 'N/A')}%)"
                    )
                    # Add decision reasoning
                    if reasoning:
                        pm_review_lines.append(f"    💭 Reasoning: {reasoning}")
                else:
                    pm_review_lines.append(f"  {ticker}: No signal data")

        # 2. Actual return performance (Portfolio mode adds value change info)
        returns_lines = ["Actual return performance:"]
        
        if self.mode == "portfolio":
            # Portfolio mode: Display value changes
            for ticker in tickers:
                if ticker in real_returns:
                    daily_ret = real_returns[ticker] * 100
                    signal_info = pm_signals.get(ticker, {})
                    action = signal_info.get('action', 'N/A')
                    quantity = signal_info.get('quantity', 0)
                    
                    # Calculate value change (simplified calculation, should actually be based on positions)
                    if quantity > 0 and action in ['long', 'short']:
                        returns_lines.append(f"  {ticker}: {daily_ret:.2f}% (operation: {action} {quantity} shares)")
                    elif quantity == 0 and action in ['hold']:
                        returns_lines.append(f"  {ticker}: {daily_ret:.2f}% (operation: {action})")
                    else:
                        returns_lines.append(f"  {ticker}: {daily_ret:.2f}% (signal: {signal_info.get('signal', 'N/A')})")
                else:
                    returns_lines.append(f"  {ticker}: No return data")
            
            # Display portfolio total value change (need to get from portfolio state)
            portfolio_info = live_env.get('portfolio_summary', {})
            if portfolio_info:
                total_value = portfolio_info.get('total_value', 0)
                cash = portfolio_info.get('cash', 0)
                returns_lines.append(f"\nPortfolio total value: ${total_value:,.2f} (cash: ${cash:,.2f})")
        else:
            # Signal mode: Display traditional return info
            for ticker in tickers:
                if ticker in real_returns:
                    daily_ret = real_returns[ticker] * 100
                    returns_lines.append(f"  {ticker}: {daily_ret:.2f}% (signal: {pm_signals.get(ticker, {}).get('signal', 'N/A')})")
                else:
                    returns_lines.append(f"  {ticker}: No return data")

        # 3. Analyst signal comparison (merge into one output)
        analyst_lines = ["Analyst signal comparison:"]
        for agent, agent_signals in ana_signals.items():
            analyst_lines.append(f"\n{agent}:")
            for ticker in tickers:
                signal_data = agent_signals.get(ticker, {})
                signal = signal_data.get('signal', 'N/A') if isinstance(signal_data, dict) else 'N/A'
                analyst_lines.append(f"  {ticker}: {signal}")
        
        self.streamer.print("agent", 
            "\n".join(pm_review_lines) + "\n" + "\n".join(returns_lines) + "\n" + "\n".join(analyst_lines),
            role_key="portfolio_manager")

        # Get review mode
        review_mode = os.getenv('MEMORY_REVIEW_MODE', 'individual_review').lower()
        
        if review_mode == 'individual_review':
            # New mode: Individual Review
            return self._run_individual_review_mode(date, tickers, pm_signals, ana_signals, real_returns, live_env)
        else:
            # Old mode: Central Review
            return self._run_central_review_mode(date, tickers, pm_signals, ana_signals, real_returns)
    
    def _perform_memory_review(
        self,
        date: str,
        tickers: List[str],
        live_env: Dict[str, Any]
    ):
        """执行记忆复盘（独立函数，用于延迟复盘）
        
        这个函数会在第二天被调用，当我们有了 real_returns 之后
        """
        pm_signals = live_env.get('pm_signals', {})
        ana_signals = live_env.get('ana_signals', {})
        real_returns = live_env.get('real_returns', {})
        
        # 显示复盘信息
        self.streamer.print("agent", 
            f"===== Post-Market Review ({date}) =====\n"
            f"Reviewing previous day's performance with actual returns",
            role_key="portfolio_manager")
        
        # 1. Portfolio Manager 信号回顾
        pm_review_lines = ["Portfolio Manager signal review:"]
        for ticker in tickers:
            if ticker in pm_signals:
                signal_info = pm_signals[ticker]
                if self.mode == "portfolio":
                    action = signal_info.get('action', 'N/A')
                    quantity = signal_info.get('quantity', 0)
                    pm_review_lines.append(f"  {ticker}: {action} ({quantity} shares)")
                else:
                    pm_review_lines.append(f"  {ticker}: {signal_info.get('signal', 'N/A')}")
        
        # 2. 实际收益回顾
        returns_lines = ["Actual returns:"]
        for ticker in tickers:
            if ticker in real_returns:
                daily_ret = real_returns[ticker] * 100
                returns_lines.append(f"  {ticker}: {daily_ret:.2f}%")
        
        # 3. 分析师信号对比
        analyst_lines = ["Analyst signal comparison:"]
        for agent, agent_signals in ana_signals.items():
            analyst_lines.append(f"\n{agent}:")
            for ticker in tickers:
                signal_data = agent_signals.get(ticker, {})
                signal = signal_data.get('signal', 'N/A') if isinstance(signal_data, dict) else 'N/A'
                analyst_lines.append(f"  {ticker}: {signal}")
        
        self.streamer.print("agent", 
            "\n".join(pm_review_lines) + "\n" + "\n".join(returns_lines) + "\n" + "\n".join(analyst_lines),
            role_key="portfolio_manager")
        
        # 执行记忆复盘
        review_mode = os.getenv('MEMORY_REVIEW_MODE', 'individual_review').lower()
        
        if review_mode == 'individual_review':
            result = self._run_individual_review_mode(date, tickers, pm_signals, ana_signals, real_returns, live_env)
        else:
            result = self._run_central_review_mode(date, tickers, pm_signals, ana_signals, real_returns)
        
        self.streamer.print("system", f"✅ Memory review completed for {date}")
        return result
    
    def _run_central_review_mode(
        self,
        date: str,
        tickers: List[str],
        pm_signals: Dict,
        ana_signals: Dict,
        real_returns: Dict
    ) -> Dict[str, Any]:
        """Central Review mode: Unified LLM manages memory"""
        self.streamer.print("system", "===== Central Review Memory Management =====")

        try:
            if self.memory_reflection:
                reflection_data = {
                    'pm_signals': pm_signals,
                    'actual_returns': real_returns,
                    'analyst_signals': ana_signals,
                    'tickers': tickers
                }

                # Use unified review system (central_review mode)
                llm_decision = self.memory_reflection.perform_reflection(
                    date=date, 
                    reflection_data=reflection_data, 
                    mode="central_review"
                )

                # Display LLM decision result
                if llm_decision['status'] == 'success':
                    if llm_decision['mode'] == 'operations_executed':
                        # Count execution results
                        successful = sum(1 for result in llm_decision['execution_results']
                                         if result['result']['status'] == 'success')
                        total = len(llm_decision['execution_results'])

                        # Build detailed tool call info
                        memory_lines = [
                            "Using LLM tool_call for intelligent memory management",
                            f"Executed {llm_decision['operations_count']} memory operations",
                            f"Execution statistics: Success {successful}/{total}",
                            "\nTool call details:"
                        ]

                        for i, exec_result in enumerate(llm_decision['execution_results'], 1):
                            tool_name = exec_result['tool_name']
                            args = exec_result['args']
                            result = exec_result['result']

                            # Tool call basic info
                            memory_lines.append(f"\n{i}. Tool: {tool_name}")
                            memory_lines.append(f"   Analyst: {args.get('analyst_id', 'N/A')}")
                            
                            agent_id = args.get('analyst_id', 'N/A')
                            memory_lines.append(f"   Memory tool parameters: {args}") 
                            
                            # Display execution result
                            if result['status'] == 'success':
                                memory_lines.append(f"\tStatus: Success")
                                if 'affected_count' in result:
                                    memory_lines.append(f"   Affected memory count: {result['affected_count']}")
                            else:
                                memory_lines.append(f"\tStatus: Failed - {result.get('error', 'Unknown')}")

                            if tool_name == 'search_and_update_analyst_memory':
                                agent_mem_lines = []
                                agent_mem_lines.append('[memory management]: search and update memory')
                                agent_mem_lines.append(f"search memory query: {args.get('query', 'N/A')}")
                                
                                # Add memory ID and queried original content
                                if result.get('memory_id'):
                                    agent_mem_lines.append(f"memory ID: {result['memory_id']}")
                                if result.get('original_content'):
                                    original = result['original_content']
                                    # Limit length to avoid being too long
                                    display_original = original[:200] + '...' if len(original) > 200 else original
                                    agent_mem_lines.append(f"original memory: {display_original}")
                                
                                agent_mem_lines.append(f"new memory content: {args.get('new_content', 'N/A')}")
                                agent_mem_lines.append(f"reason: {args.get('reason', 'N/A')}")
                                self.streamer.print("agent", "\n".join(agent_mem_lines), role_key=agent_id)
                            elif tool_name == 'search_and_delete_analyst_memory':
                                agent_mem_lines = []
                                agent_mem_lines.append('[memory management]: search and delete memory')
                                agent_mem_lines.append(f"search memory query: {args.get('query', 'N/A')}")
                                
                                # Add memory ID and deleted content
                                if result.get('memory_id'):
                                    agent_mem_lines.append(f"memory ID: {result['memory_id']}")
                                if result.get('deleted_content'):
                                    deleted = result['deleted_content']
                                    # Limit length to avoid being too long
                                    display_deleted = deleted[:200] + '...' if len(deleted) > 200 else deleted
                                    agent_mem_lines.append(f"deleted memory: {display_deleted}")
                                
                                agent_mem_lines.append(f"reason: {args.get('reason', 'N/A')}")
                                self.streamer.print("agent", "\n".join(agent_mem_lines), role_key=agent_id)

                        self.streamer.print("agent", "\n".join(memory_lines), role_key="portfolio_manager")
                        execution_results = llm_decision['execution_results']

                    elif llm_decision['mode'] == 'no_action':
                        no_action_lines = [
                            "Using LLM tool_call for intelligent memory management",
                            "LLM determined no memory operations needed",
                            f"Reasoning: {llm_decision['reasoning']}"
                        ]
                        self.streamer.print("agent", "\n".join(no_action_lines), role_key="portfolio_manager")
                        execution_results = None
                    else:
                        self.streamer.print("system", f"Unknown LLM decision mode: {llm_decision['mode']}")
                        execution_results = None

                elif llm_decision['status'] == 'skipped':
                    self.streamer.print("system", f"Memory management skipped: {llm_decision['reason']}")
                    execution_results = None
                else:
                    self.streamer.print("system", f"LLM decision failed: {llm_decision.get('error', 'Unknown error')}")
                    execution_results = None
            else:
                self.streamer.print("system", "LLM memory management system not enabled, skipping memory operations")
                llm_decision = None
                execution_results = None

        except Exception as e:
            self.streamer.print("system", f"Memory management process error: {str(e)}")
            import traceback
            traceback.print_exc()

        return {
            'status': 'success',
            'type': 'full_review',
            'pre_market_signals': pm_signals,
            'analyst_signals': ana_signals,
            'actual_returns': real_returns,
            'llm_memory_decision': llm_decision if 'llm_decision' in locals() else None,
            'memory_tool_calls_results': execution_results,
            'timestamp': datetime.now().isoformat()
        }
    
    def _run_individual_review_mode(
        self,
        date: str,
        tickers: List[str],
        pm_signals: Dict,
        ana_signals: Dict,
        real_returns: Dict,
        live_env: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Individual Review mode: Each Agent self-reviews independently (new mode)"""
        print("===== Individual Review Mode =====")
        print("Each Agent conducts independent self-review")
        
        reflection_results = {}
        portfolio_summary = live_env.get('portfolio_summary', {})
        
        # Check if enabled
        enable_individual_review = os.getenv('ENABLE_INDIVIDUAL_REVIEW', 'true').lower() == 'true'
        
        if not enable_individual_review:
            self.streamer.print("system", "⚠️ Individual Review disabled (ENABLE_INDIVIDUAL_REVIEW=false)")
            return {
                'status': 'skipped',
                'mode': 'individual_review',
                'date': date,
                'reason': 'Individual Review disabled'
            }
        
        try:
            self.streamer.print("system", "\n--- Individual Review Mode ---")
            
            # Prepare data for all agents
            agents_data = {}
            
            # ========== 1. Each analyst data ==========
            for analyst_id in ANALYST_TYPES.keys():
                my_signals = {}
                for ticker in tickers:
                    if analyst_id in ana_signals and ticker in ana_signals[analyst_id]:
                        signal_data = ana_signals[analyst_id][ticker]
                        signal_value = signal_data.get('signal', 'N/A') if isinstance(signal_data, dict) else 'N/A'
                        reasoning_text = signal_data.get('reasoning', '') or signal_data.get('tool_analysis', '') if isinstance(signal_data, dict) else ''
                        
                        my_signals[ticker] = {
                            'signal': signal_value,
                            'confidence': signal_data.get('confidence', 0) if isinstance(signal_data, dict) else 0,
                            'reasoning': reasoning_text
                        }
                
                agents_data[analyst_id] = {
                    'agent_id': analyst_id,
                    'my_signals': my_signals,
                    'actual_returns': real_returns,
                    'pm_decisions': pm_signals
                }
            
            # ========== 2. PM data ==========
            agents_data['portfolio_manager'] = {
                'agent_id': 'portfolio_manager',
                'my_decisions': pm_signals,
                'analyst_signals': ana_signals,
                'actual_returns': real_returns,
                'portfolio_summary': portfolio_summary
            }
            
            # ========== 3. Execute unified review ==========
            if self.memory_reflection:
                result = self.memory_reflection.perform_reflection(
                    date=date,
                    reflection_data={'agents_data': agents_data},
                    mode="individual_review"
                )
                
                reflection_results = {
                    agent_result['agent_id']: agent_result 
                    for agent_result in result.get('agents_results', [])
                }
            
            # ========== 4. Generate summary report ==========
            summary = self._generate_individual_review_summary(
                reflection_results=reflection_results,
                portfolio_summary=portfolio_summary
            )
            
            print("system", f"\n📊 Individual Review Summary:")
            self.streamer.print("system", summary)
            
            return {
                'status': 'success',
                'mode': 'individual_review',
                'date': date,
                'reflection_results': reflection_results,
                'summary': summary,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"❌ Individual Review execution failed: {e}")
            import traceback
            traceback.print_exc()
            return {
                'status': 'failed',
                'mode': 'individual_review',
                'date': date,
                'error': str(e)
            }
    
    def _generate_individual_review_summary(
        self,
        reflection_results: Dict[str, Dict[str, Any]],
        portfolio_summary: Dict[str, Any]
    ) -> str:
        """Generate Individual Review summary"""
        summary_lines = []
        
        # Count memory operations
        total_agents = len(reflection_results)
        successful_agents = sum(1 for r in reflection_results.values() if r.get('status') == 'success')
        total_operations = 0
        operations_by_type = {'update': 0, 'delete': 0}
        
        for agent_id, result in reflection_results.items():
            if result.get('status') == 'success':
                ops_count = len(result['memory_operations'])
                total_operations += ops_count
                
                for op in result.get('memory_operations', []):
                    tool_name = op.get('tool_name', '')
                    if 'update' in tool_name:
                        operations_by_type['update'] += 1
                    elif 'delete' in tool_name:
                        operations_by_type['delete'] += 1
        
        summary_lines.append(f"Today {total_agents} Agents completed self-review")
        summary_lines.append(f"Success: {successful_agents}, Failed: {total_agents - successful_agents}")
        summary_lines.append(f"Memory operations executed: {total_operations} times")
        
        if operations_by_type['update'] > 0:
            summary_lines.append(f"  - Update memory: {operations_by_type['update']} times")
        if operations_by_type['delete'] > 0:
            summary_lines.append(f"  - Delete memory: {operations_by_type['delete']} times")
    
        
        # Each Agent status
        summary_lines.append("\nEach Agent review status:")
        for agent_id, result in reflection_results.items():
            status = result.get('status', 'unknown')
            ops_count = len(result['memory_operations'])
            status_emoji = "✅" if status == 'success' else "❌"
            summary_lines.append(f"  {status_emoji} {agent_id}: {status} ({ops_count} operations)")
        # pdb.set_trace()
        return "\n".join(summary_lines)

    def generate_trading_dates(self, start_date: str, end_date: str) -> List[str]:
        """Generate trading date list (use batch query to optimize performance)"""
        if not self.validate_date_format(start_date) or not self.validate_date_format(end_date):
            raise ValueError("Date format should be YYYY-MM-DD")
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        if start_dt > end_dt:
            raise ValueError("Start date cannot be later than end date")

        print(f"⏳ Generating trading date list ({start_date} -> {end_date})...")
        
        # Use batch query (get all trading days at once)
        return self.strategy.get_trading_dates(start_date, end_date)

    def run_multi_day_simulation(
        self,
        start_date: str,
        end_date: str,
        tickers: List[str],
        max_comm_cycles: int = 2,
        force_run: bool = False,
        enable_communications: bool = False,
        enable_notifications: bool = False
    ) -> Dict[str, Any]:
        """Run multi-day sandbox simulation"""
        trading_days = self.generate_trading_dates(start_date, end_date)
        if not trading_days:
            self.streamer.print("system", "No trading days in selected range")
            return {
                'status': 'skipped',
                'reason': 'No trading days',
                'start_date': start_date,
                'end_date': end_date,
                'daily_results': {}
            }

        self.streamer.print("system", 
            f"===== Multi-Day Sandbox Simulation {start_date} ~ {end_date} =====")
        self.streamer.print("system", 
            f"Covering trading days: {len(trading_days)} days -> {', '.join(trading_days[:5])}{'...' if len(trading_days) > 5 else ''}")

        daily_results: Dict[str, Dict[str, Any]] = {}
        success_days: List[str] = []
        failed_days: List[str] = []

        for idx, date in enumerate(trading_days, start=1):
            self.streamer.print("system", f"--- [{idx}/{len(trading_days)}] {date} ---")
            day_result = self.run_full_day_simulation(
                date=date,
                tickers=tickers,
                max_comm_cycles=max_comm_cycles,
                force_run=force_run,
                enable_communications=enable_communications,
                enable_notifications=enable_notifications
            )
            daily_results[date] = day_result

            day_status = day_result.get('summary', {}).get('overall_status', 'failed')
            if day_status == 'success':
                success_days.append(date)
            else:
                failed_days.append(date)

        summary = self._build_multi_day_summary(
            start_date=start_date,
            end_date=end_date,
            trading_days=trading_days,
            success_days=success_days,
            failed_days=failed_days
        )
        self._print_multi_day_summary(summary)

        return {
            'status': 'completed',
            'start_date': start_date,
            'end_date': end_date,
            'trading_days': trading_days,
            'success_days': success_days,
            'failed_days': failed_days,
            'summary': summary,
            'daily_results': daily_results
        }

    def _build_multi_day_summary(
        self,
        start_date: str,
        end_date: str,
        trading_days: List[str],
        success_days: List[str],
        failed_days: List[str]
    ) -> Dict[str, Any]:
        total = len(trading_days)
        success = len(success_days)
        fail = len(failed_days)
        success_rate = success / total * 100 if total else 0.0

        return {
            'start_date': start_date,
            'end_date': end_date,
            'total_days': total,
            'success_days': success,
            'failed_days': fail,
            'success_rate_pct': round(success_rate, 2),
            'first_trading_day': trading_days[0] if trading_days else None,
            'last_trading_day': trading_days[-1] if trading_days else None,
            'failed_day_list': failed_days
        }

    def _print_multi_day_summary(self, summary: Dict[str, Any]) -> None:
        self.streamer.print("system", 
            "===== Multi-Day Simulation Summary ====="
            f"\nRange: {summary['start_date']} ~ {summary['end_date']}"
            f"\nTrading days: {summary['total_days']}"
            f"\nSuccess days: {summary['success_days']}"
            f"\nFailed days: {summary['failed_days']}"
            f"\nSuccess rate: {summary['success_rate_pct']:.2f}%")

        if summary['failed_day_list']:
            self.streamer.print("system", f"Failed dates: {', '.join(summary['failed_day_list'])}")
        self.streamer.print("system", "=" * 40)

    def run_pre_market_analysis_only(
        self,
        date: str,
        tickers: List[str],
        max_comm_cycles: int = 2,
        force_run: bool = False,
        enable_communications: bool = False,
        enable_notifications: bool = False
    ) -> Dict[str, Any]:
        """运行盘前分析（只运行 strategy.run_single_day，不执行交易）"""
        
        is_trading_day = self.is_trading_day(date)
        
        if not is_trading_day:
            print("[system]", f"{date} is not a trading day, skip pre-market analysis")
            return {
                'status': 'skipped',
                'date': date,
                'is_trading_day': False,
                'reason': 'Not trading day'
            }
        
        print("[system]", f"{date} is a trading day, executing pre-market analysis")
        
        # Display current portfolio state
        if self.mode == "portfolio" and self.strategy.portfolio_state:
            positions_count = len([p for p in self.strategy.portfolio_state.get('positions', {}).values() 
                                  if p.get('long', 0) > 0 or p.get('short', 0) > 0])
            self.streamer.print("system", 
                f"Current portfolio: Cash ${self.strategy.portfolio_state['cash']:,.2f}, "
                f"Positions {positions_count}")
        
        # Run pre-market analysis (不计算 real_returns，因为还没收盘)
        pre_market_result = self.run_pre_market_analysis(
            date, tickers, max_comm_cycles, force_run, enable_communications, enable_notifications,
            skip_real_returns=True  # Live 模式：跳过 real_returns 计算
        )
        
        return {
            'status': 'success',
            'date': date,
            'is_trading_day': True,
            'pre_market': pre_market_result
        }
    
    def run_trade_execution_and_update_prev_perf(
        self,
        date: str,
        tickers: List[str],
        pre_market_result: Optional[Dict[str, Any]] = None,
        prev_date: Optional[str] = None,
        prev_signals: Optional[Dict[str, Any]] = None,
        skip_real_returns: bool = False
    ) -> Dict[str, Any]:
        """执行交易并更新前一天的 agent performance
        
        Args:
            date: 当前交易日
            tickers: 股票列表
            pre_market_result: 当天的盘前分析结果（包含信号）
            prev_date: 前一个交易日
            prev_signals: 前一天的信号（ana_signals 和 pm_signals）
        """
        
        is_trading_day = self.is_trading_day(date)
        
        if not is_trading_day:
            print("[system]", f"{date} is not a trading day, skip trade execution")
            return {
                'status': 'skipped',
                'date': date,
                'is_trading_day': False,
                'reason': 'Not trading day'
            }
        
        print("[system]", f"{date} trade execution started")
        
        # 1. 更新前一天的 agent performance（如果提供了）
        if prev_date and prev_signals:
            self._update_previous_day_performance(prev_date, tickers, prev_signals)
        
        # 2. 执行当天的交易（如果有盘前分析结果）
        # 注意：Live 模式下，这里只执行交易操作，不进行记忆复盘
        # 因为当天还没有 real_returns（需要等到收盘后才有收盘价）
        post_market_result = None
        if pre_market_result and pre_market_result.get('status') == 'success':
            live_env = pre_market_result['pre_market'].get('live_env')
            if live_env:
                print("[system]", "Executing trades based on pre-market analysis...")
                
                # 在 Live 模式下，只执行交易，不做记忆复盘
                # 记忆复盘会在明天执行（在 _update_previous_day_performance 中）
                post_market_result = self._execute_trades_only(date, tickers, live_env)
        
        return {
            'status': 'success',
            'date': date,
            'is_trading_day': True,
            'post_market': post_market_result,
            'prev_day_updated': prev_date is not None
        }
    
    def _execute_trades_only(
        self,
        date: str,
        tickers: List[str],
        live_env: Dict[str, Any]
    ) -> Dict[str, Any]:
        """仅执行交易操作，不进行记忆复盘（用于 Live 模式）
        
        注意：在 Live 模式下，交易决策已经在盘前分析阶段通过 strategy.run_single_day 完成
        这里主要是记录日志和更新 dashboard
        """
        pm_signals = live_env.get('pm_signals', {})
        
        self.streamer.print("system", 
            f"===== Trade Execution ({date}) =====\n"
            f"Executing trades based on pre-market signals")
        
        # 显示交易信号
        trade_lines = ["Executing trades:"]
        for ticker in tickers:
            if ticker in pm_signals:
                signal_info = pm_signals[ticker]
                if self.mode == "portfolio":
                    action = signal_info.get('action', 'N/A')
                    quantity = signal_info.get('quantity', 0)
                    trade_lines.append(f"  {ticker}: {action} ({quantity} shares)")
                else:
                    trade_lines.append(f"  {ticker}: {signal_info.get('signal', 'N/A')}")
        
        self.streamer.print("agent", "\n".join(trade_lines), role_key="portfolio_manager")
        
        # 记录到 sandbox log
        log_data = {
            'status': 'success',
            'type': 'trade_execution_only',
            'pm_signals': pm_signals,
            'note': 'Memory review will be performed next day'
        }
        self._log_sandbox_activity(date, self.POST_MARKET, log_data)
        
        self.streamer.print("system", 
            "✅ Trades executed. Memory review scheduled for next trading day.")
        
        return {
            'status': 'success',
            'type': 'trade_execution_only',
            'date': date,
            'note': 'Memory review will be performed next day when real_returns available'
        }
    
    def _update_previous_day_performance(
        self,
        prev_date: str,
        tickers: List[str],
        prev_signals: Dict[str, Any]
    ):
        """更新前一天的 agent performance 并执行记忆复盘（现在可以获取 real_returns 了）"""
        
        print("[system]", f"Updating agent performance and memory review for previous trading day: {prev_date}")
        
        ana_signals = prev_signals.get('ana_signals', {})
        pm_signals = prev_signals.get('pm_signals', {})
        prev_pre_market_result = prev_signals.get('pre_market_result', {})
        
        # 计算前一天的 real_returns（现在可以获取到收盘价了）
        real_returns = {}
        for ticker in tickers:
            if ticker in pm_signals:
                action = pm_signals[ticker]['action']
                daily_return, real_return, close_price = self.strategy._calculate_stock_daily_return_from_signal(
                    ticker, prev_date, action
                )

                real_returns[ticker] = real_return

        self.streamer.print("system", real_returns)

        # 1. 更新 dashboard 中的 agent performance
        update_stats = {
            'agents_updated': 0,
            'signals_updated': 0
        }
        
        dashboard_state = self.dashboard_generator._load_internal_state()
        self.dashboard_generator._update_agent_performance(
            date=prev_date,
            ana_signals=ana_signals,
            pm_signals=pm_signals,
            real_returns=real_returns,
            state=dashboard_state,
            update_stats=update_stats
        )
        self.dashboard_generator._update_pm_performance(
            date=prev_date,
            pm_signals=pm_signals,
            real_returns=real_returns,
            state=dashboard_state,
            update_stats=update_stats
        )
        self.dashboard_generator._save_internal_state(dashboard_state)
        
        # ⭐ 关键修复：生成前端需要的 dashboard 文件
        # - stats.json: 包含 Portfolio Manager 的 win_rate 等统计数据
        # - leaderboard.json: 包含所有 Agent 的排行榜数据
        self.dashboard_generator._generate_stats(dashboard_state)
        self.dashboard_generator._generate_leaderboard(dashboard_state)
        
        self.streamer.print("system", 
            f"Previous day performance updated: {update_stats['agents_updated']} agents evaluated, dashboard files refreshed")
        
        # 2. 执行前一天的记忆复盘（现在有了 real_returns，可以准确评估表现）
        self.streamer.print("system", 
            f"===== Memory Review for {prev_date} (Delayed) =====\n")
        
        # 构建 live_env（包含 real_returns）
        live_env = {
            'pm_signals': pm_signals,
            'ana_signals': ana_signals,
            'real_returns': real_returns,
            'portfolio_summary': prev_pre_market_result.get('live_env', {}).get('portfolio_summary', {})
        }
        
        # 执行记忆复盘
        self._perform_memory_review(prev_date, tickers, live_env)
    
    def run_full_day_simulation(
        self,
        date: str,
        tickers: List[str],
        max_comm_cycles: int = 2,
        force_run: bool = False,
        enable_communications: bool = False,
        enable_notifications: bool = False
    ) -> Dict[str, Any]:
        """Run complete day simulation (pre-market + post-market) - 向后兼容的完整版本"""

        results = {
            'date': date,
            'is_trading_day': self.is_trading_day(date),
            'pre_market': None,
            'post_market': None,
            'summary': {},
            'portfolio_state': None
        }

        if results['is_trading_day']:
            print("[system]", f"{date} is a trading day, will execute pre-market analysis + post-market review")
            
            # Display current portfolio state
            if self.mode == "portfolio" and self.strategy.portfolio_state:
                positions_count = len([p for p in self.strategy.portfolio_state.get('positions', {}).values() 
                                      if p.get('long', 0) > 0 or p.get('short', 0) > 0])
                self.streamer.print("system", 
                    f"Current portfolio: Cash ${self.strategy.portfolio_state['cash']:,.2f}, "
                    f"Positions {positions_count}")

            # 1. Pre-market analysis
            results['pre_market'] = self.run_pre_market_analysis(
                date, tickers, max_comm_cycles, force_run, enable_communications, enable_notifications
            )

            print("[system]", "Waiting for post-market time point...\n(Simulating waiting for actual market close)")

            # 2. Post-market review
            live_env = results['pre_market'].get('live_env') if results['pre_market'] else None
            results['post_market'] = self.run_post_market_review(date, tickers, live_env)

        else:
            print("[system]", f"{date} is not a trading day, only executing post-market review")

            # Non-trading day only executes post-market
            results['post_market'] = self.run_post_market_review(date, tickers, 'Not trading day')

        # Generate day summary
        results['summary'] = self._generate_day_summary(results)
        
        # Return portfolio state
        if self.mode == "portfolio":
            results['portfolio_state'] = self.strategy.portfolio_state

        self._print_day_summary(results['summary'])

        return results

    def _generate_day_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        summary = {
            'date': results['date'],
            'is_trading_day': results['is_trading_day'],
            'activities_completed': [],
            'overall_status': 'success'
        }

        if results['pre_market']:
            summary['activities_completed'].append('Pre-market analysis')
            if results['pre_market']['status'] != 'success':
                summary['overall_status'] = 'partial_failure'

        if results['post_market']:
            summary['activities_completed'].append('Post-market review')
            if results['post_market']['status'] != 'success':
                summary['overall_status'] = 'failed'

        return summary

    def _print_day_summary(self, summary: Dict[str, Any]):
        """Print day summary"""
        self.streamer.print("system", 
            f"{summary['date']} complete simulation ended\n"
            f"===== {summary['date']} Day Summary =====\n"
            f"\tTrading day status: {'Yes' if summary['is_trading_day'] else 'No'}\n"
            f"\tActivities completed: {', '.join(summary['activities_completed'])}\n"
            f"\tOverall status: {summary['overall_status']}\n"
            f"============================")

    def _log_sandbox_activity(self, date: str, time_point: str, data: Dict[str, Any]):
        """Record sandbox activity log"""
        log_file = self.sandbox_dir / f"sandbox_day_{date.replace('-', '_')}.json"

        # Load existing log
        if log_file.exists():
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    log_data = json.load(f)
            except Exception:
                log_data = {}
        else:
            log_data = {}

        # Add new activity
        log_data[time_point] = data
        log_data['last_updated'] = datetime.now().isoformat()

        # Save log
        try:
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            self.streamer.print("system", f"Failed to save sandbox log: {e}")

    def _load_sandbox_log(self, date: str, time_point: str) -> Dict[str, Any]:
        """Load sandbox activity log"""
        log_file = self.sandbox_dir / f"sandbox_day_{date.replace('-', '_')}.json"

        if not log_file.exists():
            return {}

        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                log_data = json.load(f)
            return log_data.get(time_point, {})
        except Exception as e:
            self.streamer.print("system", f"Failed to load sandbox log: {e}")
            return {}


def main():
    """Main function"""
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
        """
    )

    # Required parameters
    parser.add_argument(
        '--date',
        type=str,
        help='Specify single simulation date (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--start-date',
        type=str,
        help='Multi-day simulation start date (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--end-date',
        type=str,
        help='Multi-day simulation end date (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--config_name',
        type=str,
        required=True,
        help='Configuration data storage directory name'
    )
    # Optional parameters
    parser.add_argument(
        '--tickers',
        type=str,
        help='Stock symbol list, comma separated (optional, use environment variable configuration)'
    )

    parser.add_argument(
        '--max-comm-cycles',
        type=int,
        help='Maximum communication rounds (default: 2)'
    )

    parser.add_argument(
        '--force-run',
        action='store_true',
        help='Force run, rerun even if already run on this trading day'
    )

    parser.add_argument(
        '--base-dir',
        type=str,
        help='Base directory'
    )
    
    # Portfolio mode parameters
    parser.add_argument(
        '--mode',
        type=str,
        choices=["signal", "portfolio"],
        help='Running mode: signal (signal mode) or portfolio (portfolio mode). Default read from .env'
    )
    
    parser.add_argument(
        '--initial-cash',
        type=float,
        help='Portfolio mode initial cash (default: 100000.0)'
    )
    
    parser.add_argument(
        '--margin-requirement',
        type=float,
        help='Portfolio mode margin requirement, 0.0 means disable shorting, 0.5 means 50%% margin (default: 0.0)'
    )

    args = parser.parse_args()

    try:
        # Load configuration
        config = LiveThinkingFundConfig()
        config.override_with_args(args)
        
        # Create ConsoleStreamer for initialization phase
        console_streamer = ConsoleStreamer()
        
        # Initialize memory system (automatically select framework based on environment variable)
        memory_instance = get_memory(base_dir=config.config_name)
        print(f"✅ Memory system initialized")
        
        # Initialize thinking fund system, pass mode and portfolio parameters
        thinking_fund = LiveTradingFund(
            config_name=config.config_name, 
            streamer=console_streamer,
            mode=config.mode,  # Pass running mode
            initial_cash=config.initial_cash,  # Portfolio mode initial cash
            margin_requirement=config.margin_requirement  # Portfolio mode margin requirement
        )
        
        tickers = args.tickers.split(",") if args.tickers else config.tickers
        from pprint import pprint
        print(f"\n📊 Live Trading Thinking Fund Configuration:")
        print(f"   Running mode: {config.mode.upper()}")
        if config.mode == "portfolio":
            print(f"   Initial cash: ${config.initial_cash:,.2f}")
            print(f"   Margin requirement: {config.margin_requirement * 100:.1f}%")
        pprint(config.__dict__)

        if args.start_date or args.end_date:
            if not args.start_date or not args.end_date:
                print("Error: Multi-day mode requires both --start-date and --end-date")
                sys.exit(1)
            results = thinking_fund.run_multi_day_simulation(
                start_date=args.start_date,
                end_date=args.end_date,
                tickers=tickers,
                max_comm_cycles=config.max_comm_cycles,
                force_run=args.force_run,
                enable_communications=not config.disable_communications,
                enable_notifications=not config.disable_notifications
            )
            print(f"\nMulti-day sandbox simulation completed: {results['summary']['success_days']} / {results['summary']['total_days']} success")
        else:
            if not args.date:
                print("Error: Please provide --date or --start-date/--end-date")
                sys.exit(1)
            if not thinking_fund.validate_date_format(args.date):
                print(f"Error: Invalid date format: {args.date} (need YYYY-MM-DD)")
                sys.exit(1)

            results = thinking_fund.run_full_day_simulation(
                date=args.date,
                tickers=tickers,
                max_comm_cycles=args.max_comm_cycles,
                force_run=args.force_run
            )
            print(f"\n{args.date} sandbox time simulation completed!")

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

