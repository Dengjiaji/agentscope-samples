#!/usr/bin/env python3
"""
Live交易思考基金 - 时间Sandbox系统
模拟真实交易日的时间流程：交易前分析 + 交易后复盘

时间点设计：
- 交易日：交易前 + 交易后
- 非交易日：仅交易后

使用方法:
# 运行指定日期的完整模拟
python live_trading_thinking_fund.py --date 2025-01-15 --tickers AAPL,MSFT

# 使用环境变量配置
python live_trading_thinking_fund.py --date 2025-01-15

# 强制运行
python live_trading_thinking_fund.py --date 2025-01-15 --force-run
"""

import pdb
import os
import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any
from collections import defaultdict
from dotenv import load_dotenv

# 额外引入：支持价格合成/节流
import time
import random

from src.servers.streamer import ConsoleStreamer
from src.dashboard.team_dashboard_generator import TeamDashboardGenerator

load_dotenv()
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from src.config.env_config import LiveThinkingFundConfig
from src.config.env_config import LiveTradingConfig
from src.memory.memory_factory import initialize_memory_system, get_memory_instance
# from src.memory.unified_memory import unified_memory_manager
MEMORY_AVAILABLE = True
from src.utils.llm import call_llm
from src.llm.models import get_model
from langchain_core.messages import HumanMessage
LLM_AVAILABLE = True
MEMORY_TOOLS_AVAILABLE = True

import json
import re
import pandas_market_calendars as mcal
US_TRADING_CALENDAR_AVAILABLE = True
from src.config.path_config import get_directory_config


class LLMMemoryDecisionSystem:
    """基于LLM的记忆管理决策系统 - 使用LangChain tool_call"""

    def __init__(self):
        self.memory_tools = []

        if LLM_AVAILABLE and MEMORY_TOOLS_AVAILABLE:
            model_name = os.getenv('MEMORY_LLM_MODEL', 'gpt-4o-mini')
            model_provider_str = os.getenv('MEMORY_LLM_PROVIDER', 'OPENAI')
            from src.llm.models import ModelProvider

            # 转换为ModelProvider枚举
            if hasattr(ModelProvider, model_provider_str):
                model_provider = getattr(ModelProvider, model_provider_str)
            else:
                print(f"未知的模型提供商: {model_provider_str}，使用默认OPENAI")
                model_provider = ModelProvider.OPENAI

            api_keys = {}
            if model_provider == ModelProvider.OPENAI:
                api_keys['OPENAI_API_KEY'] = os.getenv('OPENAI_API_KEY')
            elif model_provider == ModelProvider.ANTHROPIC:
                api_keys['ANTHROPIC_API_KEY'] = os.getenv('ANTHROPIC_API_KEY')

            # 获取记忆管理工具
            from src.tools.memory_management_tools import get_memory_tools
            self.memory_tools = get_memory_tools()
            # 绑定工具到LLM
            self.llm = get_model(model_name, model_provider, api_keys)
            self.llm_with_tools = self.llm.bind_tools(self.memory_tools)
            self.llm_available = True
            print(f"LLM记忆决策系统已启用（{model_provider_str}: {model_name}）")
            print(f"已绑定 {len(self.memory_tools)} 个记忆管理工具")

    def generate_memory_decision_prompt(self, performance_data: Dict[str, Any], date: str) -> str:
        """生成LLM记忆决策的prompt - LangChain tool_call版本"""

        prompt = f"""你是一个专业的Portfolio Manager，负责管理分析师团队的记忆系统。基于{date}的交易复盘结果，请分析分析师的表现并决定是否需要使用记忆管理工具。

# 复盘数据分析

## 分析师信号 vs 实际结果对比

### Portfolio Manager最终决策:
"""

        pm_signals = performance_data.get('pm_signals', {})
        actual_returns = performance_data.get('actual_returns', {})
        analyst_signals = performance_data.get('analyst_signals', {})
        tickers = performance_data.get('tickers', [])

        # 添加PM信号和实际结果
        for ticker in tickers:
            pm_signal = pm_signals.get(ticker, {})
            actual_return = actual_returns.get(ticker, 0)

            prompt += f"\n{ticker}:"
            prompt += f"\n  PM决策: {pm_signal.get('signal', 'N/A')} (置信度: {pm_signal.get('confidence', 'N/A')}%)"
            prompt += f"\n  实际收益: {actual_return:.2%}"

        prompt += "\n\n### 各分析师的预测表现:"

        # 添加分析师表现
        for analyst, signals in analyst_signals.items():
            prompt += f"\n\n**{analyst}:**"
            total_count = 0
            for ticker in tickers:
                if ticker in signals and ticker in actual_returns:
                    analyst_signal = signals[ticker]
                    actual_return = actual_returns[ticker]
                    total_count += 1

                    prompt += f"\n  {ticker}: 预测 {analyst_signal}, 实际 {actual_return:.2%}"

        prompt += f"""

# 记忆管理决策指导

请分析各分析师的表现，并决定是否需要执行记忆管理操作：

- **表现极差** (多个严重错误)：使用search_and_delete_analyst_memory删除严重错误记忆
- **表现不佳** (一个或者多个微小错误)：使用search_and_update_analyst_memory更新错误记忆
- **表现优秀或正常**：无需操作，直接说明分析结果即可

可用的记忆管理工具：
1. **search_and_update_analyst_memory**: 修正更新分析师的相关记忆内容
2. **search_and_delete_analyst_memory**: 删除分析师的相关记忆内容

请先分析各分析师的表现，然后如果需要记忆操作，直接调用相应的工具。如果不需要任何操作，请说明你的分析结果。
"""

        return prompt

    def make_llm_memory_decision_with_tools(self, performance_data: Dict[str, Any], date: str) -> Dict[str, Any]:
        """使用LLM进行记忆管理决策 - LangChain tool_call版本"""

        if not getattr(self, "llm_available", False):
            print("⚠️ LLM不可用，跳过记忆管理")
            return {'status': 'skipped', 'reason': 'LLM不可用'}

        try:
            # 生成prompt
            prompt = self.generate_memory_decision_prompt(performance_data, date)

            print(f"\n🤖 正在请求LLM进行记忆管理决策...")
            print(f"📝 Prompt长度: {len(prompt)} 字符")

            # 调用绑定了工具的LLM
            messages = [HumanMessage(content=prompt)]
            response = self.llm_with_tools.invoke(messages)

            print(f"📥 LLM响应类型: {type(response)}")

            # 检查是否有工具调用
            tool_calls = []
            if hasattr(response, 'tool_calls') and response.tool_calls:
                tool_calls = response.tool_calls
                print(f"🛠️ LLM决定执行 {len(tool_calls)} 个工具调用")

                # 执行工具调用
                execution_results = []
                for tool_call in tool_calls:
                    tool_name = tool_call['name']
                    tool_args = tool_call['args']

                    print(f"  📞 调用工具: {tool_name}")
                    print(f"     参数: {tool_args}")

                    # 直接调用对应的工具函数
                    tool_function = next(
                        (tool for tool in self.memory_tools if tool.name == tool_name),
                        None
                    )

                    if tool_function:
                        result = tool_function.invoke(tool_args)
                        execution_results.append({
                            'tool_name': tool_name,
                            'args': tool_args,
                            'result': result
                        })
                    else:
                        print(f"    ❌ 未找到工具: {tool_name}")
                        execution_results.append({
                            'tool_name': tool_name,
                            'args': tool_args,
                            'result': {'status': 'failed', 'error': f'Tool not found: {tool_name}'}
                        })

                return {
                    'status': 'success',
                    'mode': 'operations_executed',
                    'operations_count': len(tool_calls),
                    'execution_results': execution_results,
                    'llm_reasoning': response.content,
                    'date': date
                }
            else:
                # 没有工具调用，LLM可能认为不需要操作
                reasoning = response.content if hasattr(response, 'content') else str(response)
                print(f"💭 LLM分析: {reasoning}")

                return {
                    'status': 'success',
                    'mode': 'no_action',
                    'reasoning': reasoning,
                    'date': date
                }

        except Exception as e:
            print(f"❌ LLM记忆管理决策失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                'status': 'failed',
                'error': str(e),
                'date': date
            }


class LiveTradingThinkingFund:
    """Live交易思考基金 - 时间Sandbox系统"""

    def __init__(self, base_dir: str, streamer=None, mode: str = "signal", initial_cash: float = 100000.0, margin_requirement: float = 0.0):
        """初始化思考基金系统"""
        from live_trading_system import LiveTradingSystem

        # self.base_dir = Path(base_dir) if base_dir else Path(__file__).parent
        self.base_dir = Path(get_directory_config(base_dir))
        self.sandbox_dir = self.base_dir / "sandbox_logs"
        self.sandbox_dir.mkdir(parents=True, exist_ok=True)

        # 可选的统一事件下发器：若为 None，则仅本地打印
        if streamer:
            self.streamer = streamer
        else:
            self.streamer = ConsoleStreamer()

        # 初始化Live交易系统（传递streamer）
        self.live_system = LiveTradingSystem(base_dir=base_dir, streamer=self.streamer)

        # 初始化记忆管理系统
        if MEMORY_TOOLS_AVAILABLE:
            self.llm_memory_system = LLMMemoryDecisionSystem()
            print("LLM记忆管理系统已启用")
        else:
            self.llm_memory_system = None
            print("LLM记忆管理系统未启用")

        # 时间点定义
        self.PRE_MARKET = "pre_market"    # 交易前
        self.POST_MARKET = "post_market"  # 交易后
        
        # Portfolio模式参数
        self.mode = mode
        self.initial_cash = initial_cash
        self.margin_requirement = margin_requirement
        
        # 初始化团队仪表盘生成器
        dashboard_dir = self.sandbox_dir / "team_dashboard"
        self.dashboard_generator = TeamDashboardGenerator(
            dashboard_dir=dashboard_dir,
            initial_cash=initial_cash
        )
        # 初始化空仪表盘（如果不存在）
        if not (dashboard_dir / "summary.json").exists():
            self.dashboard_generator.initialize_empty_dashboard()

    def is_trading_day(self, date: str) -> bool:
        """检查是否为交易日"""
        return self.live_system.is_trading_day(date)

    def validate_date_format(self, date_str: str) -> bool:
        """验证日期格式"""
        return self.live_system.validate_date_format(date_str)

    def should_run_sandbox_analysis(self, date: str, time_point: str, force_run: bool = False) -> bool:
        """判断是否应该运行sandbox分析（独立于live_system的检查逻辑）"""
        if force_run:
            return True

        # 检查sandbox日志中是否已有成功的记录
        existing_data = self._load_sandbox_log(date, time_point)
        if existing_data and existing_data.get('status') == 'success':
            return False

        return True

    def _run_sandbox_analysis(self, tickers: List[str], target_date: str, max_comm_cycles: int = 2, enable_communications: bool = False, enable_notifications: bool = False) -> Dict[str, Any]:
        """运行sandbox专用的分析（绕过live_system的状态管理）"""

        # self.streamer.print("system", f"开始Sandbox策略分析 - {target_date}\n监控标的: {', '.join(tickers)}")

        # 1. 运行策略分析（直接调用核心分析方法，绕过should_run_today检查）
        analysis_result = self.live_system.run_single_day_analysis(
            tickers, target_date, max_comm_cycles, enable_communications, enable_notifications,
            mode=self.mode,  # 传递运行模式
            initial_cash=self.initial_cash,  # Portfolio模式初始现金
            margin_requirement=self.margin_requirement  # Portfolio模式保证金要求
        )

        # 使用defaultdict简化初始化
        live_env = {
            'pm_signals': {},
            'ana_signals': defaultdict(lambda: defaultdict(str)),  # 自动创建嵌套字典，默认值为空字符串
            'real_returns': defaultdict(float)  # 自动创建，默认值为0.0
        }

        # 2. 保存交易信号
        pm_signals = analysis_result['signals']
        live_env['pm_signals'] = pm_signals

        # 3. 提取分析师信号（现在不需要预先初始化）
        self.streamer.print("system", "===== 分析师信号详情 =====")
        
        for agent in ['sentiment_analyst', 'technical_analyst', 'fundamentals_analyst', 'valuation_analyst']:
            for ticker in tickers:
                agent_results = analysis_result.get('raw_results', {}).get('results', {}).get('final_analyst_results', {})
                
                if agent not in agent_results:
                    continue
                
                analyst_result = agent_results[agent].get('analysis_result', {})
                
                # 兼容两种格式：
                # 1. 第一轮格式: {ticker: {signal, confidence, ...}}
                # 2. 第二轮格式: {ticker_signals: [{ticker, signal, confidence, ...}]}
                if 'ticker_signals' in analyst_result:
                    # 第二轮格式
                    matched = next((item for item in analyst_result['ticker_signals'] if item['ticker'] == ticker), None)
                    if matched:
                        live_env['ana_signals'][agent][ticker] = matched['signal']
                        # 输出第二轮信号
                        self.streamer.print("agent", 
                            f"{ticker} - 第二轮: {matched['signal']} (置信度: {matched.get('confidence', 'N/A')}%)", 
                            role_key=agent
                        )
                elif ticker in analyst_result:
                    # 第一轮格式
                    if 'signal' in analyst_result[ticker]:
                        live_env['ana_signals'][agent][ticker] = analyst_result[ticker]['signal']
                        # 输出第一轮信号
                        confidence = analyst_result[ticker].get('confidence', 'N/A')
                        self.streamer.print("agent", 
                            f"{ticker} - 第一轮: {analyst_result[ticker]['signal']} (置信度: {confidence}%)", 
                            role_key=agent
                        )

                
        self.live_system.save_daily_signals(target_date, pm_signals)
        # self.streamer.print("system", f"已保存 {len(pm_signals)} 个股票的交易信号")

        # 4. 计算当日收益
        target_date = str(target_date)
        pdb.set_trace()
        daily_returns = self.live_system.calculate_daily_returns(target_date, pm_signals)

        for ticker in tickers:
            live_env['real_returns'][ticker] = daily_returns[ticker]['daily_return']

        # 5. 更新个股收益
        individual_data = self.live_system.update_individual_returns(target_date, daily_returns)

        self.streamer.print("system", f"已保存 {len(pm_signals)} 个股票的交易信号\n{target_date} Sandbox分析完成")

        # 显示各股票表现 + 各分析师信号
        for ticker, data in daily_returns.items():
            daily_ret = data['daily_return'] * 100
            cum_ret = (individual_data[ticker][target_date]['cumulative_return'] - 1) * 100
            signal = data['signal']
            action = data['action']
            confidence = data['confidence']
            real_ret = data['real_return'] * 100
            if self.mode == "signal":
                self.streamer.print("agent", 
                    f"{ticker}: 最终信号 {signal}({action},置信度 {confidence}% ,日收益 {daily_ret:.2f}%, 累计收益 {cum_ret:.2f}%)",
                    role_key='portfolio_manager'
                )
            elif self.mode == "portfolio":
                quantity = pm_signals[ticker]['quantity']
                self.streamer.print("agent", 
                    f"{ticker}: 最终信号 {signal}({action} {quantity}股,置信度 {confidence}% ,股票当日收益率 {real_ret:.2f}%",
                    role_key='portfolio_manager'
                )
            # 分析师逐票事件
            for agent in ['sentiment_analyst', 'technical_analyst', 'fundamentals_analyst', 'valuation_analyst']:
                sig = live_env['ana_signals'][agent].get(ticker, '')
                if sig:
                    self.streamer.print("agent", f"{ticker}: {sig}",  role_key=agent)

        # 如果是Portfolio模式，收集Portfolio相关信息
        if self.mode == "portfolio":
            # 从分析结果中提取Portfolio信息
            # pdb.set_trace()
            raw_results = analysis_result.get('raw_results', {})
            portfolio_summary = raw_results['results']['portfolio_management_results']['execution_report']['portfolio_summary']
            updated_portfolio = raw_results['results']['portfolio_management_results']['execution_report']['updated_portfolio']
            
            # 将Portfolio信息添加到live_env
            live_env['portfolio_summary'] = portfolio_summary
            live_env['updated_portfolio'] = updated_portfolio

        return {
            'status': 'success',
            'date': target_date,
            'signals': pm_signals,
            'individual_returns': daily_returns,
            'individual_cumulative': individual_data,
            'live_env': live_env
        }

    def run_pre_market_analysis(self, date: str, tickers: List[str],
                                max_comm_cycles: int = 2, force_run: bool = False,
                                enable_communications: bool = False, enable_notifications: bool = False) -> Dict[str, Any]:
        """运行交易前分析（复用live_trading_system）"""
        self.streamer.print("system", f"===== 交易前分析 ({date}) =====\n时间点: {self.PRE_MARKET}\n分析标的: {', '.join(tickers)}")

        # 使用sandbox专用的检查逻辑
        # if not self.should_run_sandbox_analysis(date, self.PRE_MARKET, force_run):
        #     print(f"📋 {date} 交易前分析已存在，跳过重复运行（使用 --force-run 强制重新运行）")
        #     existing_data = self._load_sandbox_log(date, self.PRE_MARKET)
        #     return existing_data

        # 运行sandbox专用的分析（绕过live_system的状态检查）
        result = self._run_sandbox_analysis(tickers, date, max_comm_cycles, enable_communications, enable_notifications)

        # 记录到sandbox日志
        self._log_sandbox_activity(date, self.PRE_MARKET, {
            'status': result['status'],
            'tickers': tickers,
            'timestamp': datetime.now().isoformat(),
            'details': result
        })
        
        # 更新团队仪表盘数据
        try:
            dashboard_update_stats = self.dashboard_generator.update_from_day_result(
                date=date,
                pre_market_result=result,
                mode=self.mode
            )
            self.streamer.print("system", f"团队仪表盘已更新: 新增 {dashboard_update_stats.get('trades_added', 0)} 笔交易, 更新 {dashboard_update_stats.get('agents_updated', 0)} 个Agent")
        except Exception as e:
            self.streamer.print("system", f"⚠️ 团队仪表盘更新失败: {str(e)}")
            import traceback
            traceback.print_exc()

        return result

    def run_post_market_review(self, date: str, tickers: List[str], live_env: Dict[str, Any]) -> Dict[str, Any]:
        """运行交易后复盘"""
        self.streamer.print("system", f"===== 交易后复盘 ({date}) =====\n时间点: {self.POST_MARKET} \n复盘标的: {', '.join(tickers)}")

        if live_env != 'Not trading day':
            # 交易后复盘逻辑
            result = self._perform_post_market_review(date, tickers, live_env)

            # 记录到sandbox日志
            self._log_sandbox_activity(date, self.POST_MARKET, result)

            return result

    def _perform_post_market_review(self, date: str, tickers: List[str], live_env: Dict[str, Any]) -> Dict[str, Any]:
        """执行交易后复盘分析"""

        pm_signals = live_env['pm_signals']
        ana_signals = live_env['ana_signals']
        real_returns = live_env['real_returns']

        # 1. Portfolio Manager 信号回顾（根据模式显示不同信息）
        pm_review_lines = ["基于交易前分析进行复盘...", "Portfolio Manager信号回顾:"]
        
        if self.mode == "portfolio":
            # Portfolio模式：显示详细的操作信息
            for ticker in tickers:
                if ticker in pm_signals:
                    signal_info = pm_signals[ticker]
                    action = signal_info.get('action', 'N/A')
                    quantity = signal_info.get('quantity', 0)
                    confidence = signal_info.get('confidence', 'N/A')
                    signal = signal_info.get('signal', 'N/A')
                    
                    # 显示操作和数量
                    if quantity > 0:
                        pm_review_lines.append(
                            f"  {ticker}: {signal} ({action} {quantity}股, 置信度: {confidence}%)"
                        )
                    else:
                        pm_review_lines.append(
                            f"  {ticker}: {signal} ({action}, 置信度: {confidence}%)"
                        )
                else:
                    pm_review_lines.append(f"  {ticker}: 无信号数据")
        else:
            # Signal模式：显示传统信号信息
            for ticker in tickers:
                if ticker in pm_signals:
                    signal_info = pm_signals[ticker]
                    pm_review_lines.append(
                        f"  {ticker}: {signal_info.get('signal', 'N/A')} ({signal_info.get('action', 'N/A')}, 置信度: {signal_info.get('confidence', 'N/A')}%)"
                    )
                else:
                    pm_review_lines.append(f"  {ticker}: 无信号数据")

        # 2. 实际收益表现（Portfolio模式增加价值变化信息）
        returns_lines = ["实际收益表现:"]
        
        if self.mode == "portfolio":
            # Portfolio模式：显示价值变化
            portfolio_value_change = 0.0
            for ticker in tickers:
                if ticker in real_returns:
                    daily_ret = real_returns[ticker] * 100
                    signal_info = pm_signals.get(ticker, {})
                    action = signal_info.get('action', 'N/A')
                    quantity = signal_info.get('quantity', 0)
                    
                    # 计算价值变化（简化计算，实际应该基于持仓）
                    if quantity > 0 and action in ['buy', 'sell', 'short', 'cover']:
                        # 这里需要从portfolio状态获取实际持仓来计算
                        # 暂时显示收益率
                        returns_lines.append(f"  {ticker}: {daily_ret:.2f}% (操作: {action} {quantity}股)")
                    elif quantity==0 and action in ['hold']:
                        returns_lines.append(f"  {ticker}: {daily_ret:.2f}% (操作: {action} )")
                    else:
                        returns_lines.append(f"  {ticker}: {daily_ret:.2f}% (信号: {signal_info.get('signal', 'N/A')})")
                else:
                    returns_lines.append(f"  {ticker}: 无收益数据")
            
            # 显示Portfolio总价值变化（需要从portfolio状态获取）
            portfolio_info = live_env.get('portfolio_summary', {})
            if portfolio_info:
                total_value = portfolio_info.get('total_value', 0)
                cash = portfolio_info.get('cash', 0)
                returns_lines.append(f"\nPortfolio总价值: ${total_value:,.2f} (现金: ${cash:,.2f})")
        else:
            # Signal模式：显示传统收益信息
            for ticker in tickers:
                if ticker in real_returns:
                    daily_ret = real_returns[ticker] * 100
                    returns_lines.append(f"  {ticker}: {daily_ret:.2f}% (信号: {pm_signals.get(ticker, {}).get('signal', 'N/A')})")
                else:
                    returns_lines.append(f"  {ticker}: 无收益数据")

        # 3. Analyst 信号对比（合并为一次输出）
        analyst_lines = ["Analyst信号对比:"]
        for agent, agent_signals in ana_signals.items():
            analyst_lines.append(f"\n{agent}:")
            for ticker in tickers:
                signal = agent_signals.get(ticker, 'N/A')
                analyst_lines.append(f"  {ticker}: {signal}")
        
        self.streamer.print("agent", "\n".join(pm_review_lines)+"\n"+ "\n".join(returns_lines)+"\n"+"\n".join(analyst_lines), role_key="portfolio_manager")

        self.streamer.print("system", "===== Portfolio Manager 记忆管理决策 =====")

        execution_results = None
        try:
            if self.llm_memory_system:
                performance_data = {
                    'pm_signals': pm_signals,
                    'actual_returns': real_returns,
                    'analyst_signals': ana_signals,
                    'tickers': tickers
                }

                # 使用LLM进行记忆管理决策（tool_call模式）
                llm_decision = self.llm_memory_system.make_llm_memory_decision_with_tools(
                    performance_data, date
                )

                # 显示LLM决策结果（合并输出）
                if llm_decision['status'] == 'success':
                    if llm_decision['mode'] == 'operations_executed':
                        # 统计执行结果
                        successful = sum(1 for result in llm_decision['execution_results']
                                         if result['result']['status'] == 'success')
                        total = len(llm_decision['execution_results'])

                        # 构建详细的工具调用信息
                        memory_lines = [
                            "使用 LLM tool_call 进行智能记忆管理",
                            f"执行了 {llm_decision['operations_count']} 个记忆操作",
                            f"执行统计：成功 {successful}/{total}",
                            "\n工具调用详情:"
                        ]

                        for i, exec_result in enumerate(llm_decision['execution_results'], 1):
                            tool_name = exec_result['tool_name']
                            args = exec_result['args']
                            result = exec_result['result']

                            # 工具调用基本信息
                            memory_lines.append(f"\n{i}. 工具: {tool_name}")
                            memory_lines.append(f"   分析师: {args.get('analyst_id', 'N/A')}")
                            
                            agent_id = args.get('analyst_id', 'N/A')
                            memory_lines.append(f"   memory tool 参数: {args}") 
                            
                            # 显示执行结果
                            if result['status'] == 'success':
                                memory_lines.append(f"\t状态: 成功")
                                if 'affected_count' in result:
                                    memory_lines.append(f"   影响记忆数: {result['affected_count']}")
                            else:
                                memory_lines.append(f"\t状态: 失败 - {result.get('error', 'Unknown')}")

                            if tool_name == 'search_and_update_analyst_memory':
                                agent_mem_lines = []
                                agent_mem_lines.append('[memory management]: search and update memory')
                                agent_mem_lines.append(f"search memory query: {args.get('query', 'N/A')}")
                                
                                # 添加记忆ID和查询到的原始内容
                                if result.get('memory_id'):
                                    agent_mem_lines.append(f"memory ID: {result['memory_id']}")
                                if result.get('original_content'):
                                    original = result['original_content']
                                    # 限制长度，避免过长
                                    display_original = original[:200] + '...' if len(original) > 200 else original
                                    agent_mem_lines.append(f"original memory: {display_original}")
                                
                                agent_mem_lines.append(f"new memory content: {args.get('new_content', 'N/A')}")
                                agent_mem_lines.append(f"reason: {args.get('reason', 'N/A')}")
                                self.streamer.print("agent", "\n".join(agent_mem_lines),role_key=agent_id)
                            elif tool_name == 'search_and_delete_analyst_memory':
                                agent_mem_lines = []
                                agent_mem_lines.append('[memory management]: search and delete memory')
                                agent_mem_lines.append(f"search memory query: {args.get('query', 'N/A')}")
                                
                                # 添加记忆ID和被删除的内容
                                if result.get('memory_id'):
                                    agent_mem_lines.append(f"memory ID: {result['memory_id']}")
                                if result.get('deleted_content'):
                                    deleted = result['deleted_content']
                                    # 限制长度，避免过长
                                    display_deleted = deleted[:200] + '...' if len(deleted) > 200 else deleted
                                    agent_mem_lines.append(f"deleted memory: {display_deleted}")
                                
                                agent_mem_lines.append(f"reason: {args.get('reason', 'N/A')}")
                                self.streamer.print("agent", "\n".join(agent_mem_lines),role_key=agent_id)

                        self.streamer.print("agent", "\n".join(memory_lines),role_key="portfolio_manager")
                        execution_results = llm_decision['execution_results']

                    elif llm_decision['mode'] == 'no_action':
                        no_action_lines = [
                            "使用 LLM tool_call 进行智能记忆管理",
                            "LLM 认为无需记忆操作",
                            f"理由: {llm_decision['reasoning']}"
                        ]
                        self.streamer.print("agent", "\n".join(no_action_lines),role_key="portfolio_manager")
                        execution_results = None
                    else:
                        self.streamer.print("system", f"未知的LLM决策模式: {llm_decision['mode']}")
                        execution_results = None

                elif llm_decision['status'] == 'skipped':
                    self.streamer.print("system", f"记忆管理跳过: {llm_decision['reason']}")
                    execution_results = None
                else:
                    self.streamer.print("system", f"LLM 决策失败: {llm_decision.get('error', 'Unknown error')}")
                    execution_results = None
            else:
                self.streamer.print("system", "LLM 记忆管理系统未启用，跳过记忆操作")
                llm_decision = None
                execution_results = None

        except Exception as e:
            self.streamer.print("system", f"记忆管理过程出错: {str(e)}")
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

    def generate_trading_dates(self, start_date: str, end_date: str) -> List[str]:
        if not self.validate_date_format(start_date) or not self.validate_date_format(end_date):
            raise ValueError("日期格式应为 YYYY-MM-DD")
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        if start_dt > end_dt:
            raise ValueError("开始日期不得晚于结束日期")

        trading_days: List[str] = []
        current = start_dt
        while current <= end_dt:
            date_str = current.strftime("%Y-%m-%d")
            if self.is_trading_day(date_str):
                trading_days.append(date_str)
            current += timedelta(days=1)
        return trading_days

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
        trading_days = self.generate_trading_dates(start_date, end_date)
        if not trading_days:
            self.streamer.print("system", "选定区间内无交易日")
            return {
                'status': 'skipped',
                'reason': '无交易日',
                'start_date': start_date,
                'end_date': end_date,
                'daily_results': {}
            }

        self.streamer.print("system", f"===== 多日Sandbox模拟 {start_date} ~ {end_date} =====")
        self.streamer.print("system", f"覆盖交易日: {len(trading_days)} 天 -> {', '.join(trading_days[:5])}{'...' if len(trading_days) > 5 else ''}")

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
        self.streamer.print("system", "===== 多日模拟汇总 =====")
        self.streamer.print("system", f"区间: {summary['start_date']} ~ {summary['end_date']}")
        self.streamer.print("system", f"交易日数量: {summary['total_days']}")
        self.streamer.print("system", f"成功天数: {summary['success_days']}")
        self.streamer.print("system", f"失败天数: {summary['failed_days']}")
        self.streamer.print("system", f"成功率: {summary['success_rate_pct']:.2f}%")
        if summary['failed_day_list']:
            self.streamer.print("system", f"失败日期: {', '.join(summary['failed_day_list'])}")
        self.streamer.print("system", "=" * 40)

    def run_full_day_simulation(self, date: str, tickers: List[str],
                                max_comm_cycles: int = 2, force_run: bool = False,
                                enable_communications: bool = False, enable_notifications: bool = False) -> Dict[str, Any]:
        """运行完整的一天模拟（交易前 + 交易后）"""

        results = {
            'date': date,
            'is_trading_day': self.is_trading_day(date),
            'pre_market': None,
            'post_market': None,
            'summary': {}
        }

        if results['is_trading_day']:
            self.streamer.print("system", f"{date}是交易日，将执行交易前分析 + 交易后复盘")

            # 1. 交易前分析
            results['pre_market'] = self.run_pre_market_analysis(
                date, tickers, max_comm_cycles, force_run, enable_communications, enable_notifications
            )

            self.streamer.print("system", "等待交易后时间点...\n(模拟实际使用中等待真实的市场收盘)")

            # 2. 交易后复盘
            live_env = results['pre_market'].get('live_env') if results['pre_market'] else None
            results['post_market'] = self.run_post_market_review(date, tickers, live_env)

        else:
            self.streamer.print("system", f"{date}非交易日，仅执行交易后复盘")

            # 非交易日只执行交易后
            results['post_market'] = self.run_post_market_review(date, tickers, 'Not trading day')

        # 生成日总结
        results['summary'] = self._generate_day_summary(results)

        # self.streamer.print("system", f"{date} 完整模拟结束")
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
            summary['activities_completed'].append('交易前分析')
            if results['pre_market']['status'] != 'success':
                summary['overall_status'] = 'partial_failure'

        if results['post_market']:
            summary['activities_completed'].append('交易后复盘')
            if results['post_market']['status'] != 'success':
                summary['overall_status'] = 'failed'

        return summary

    def _print_day_summary(self, summary: Dict[str, Any]):
        """打印日总结"""
        self.streamer.print("system", f"{summary['date']}完整模拟结束\n===== {summary['date']} 日总结 =====\n\t交易日状态: {'是' if summary['is_trading_day'] else '否'}\n\t完成活动: {', '.join(summary['activities_completed'])}\n\t总体状态: {summary['overall_status']}\n============================")

    def _log_sandbox_activity(self, date: str, time_point: str, data: Dict[str, Any]):
        """记录sandbox活动日志"""
        log_file = self.sandbox_dir / f"sandbox_day_{date.replace('-', '_')}.json"

        # 加载现有日志
        if log_file.exists():
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    log_data = json.load(f)
            except Exception:
                log_data = {}
        else:
            log_data = {}

        # 添加新活动
        log_data[time_point] = data
        log_data['last_updated'] = datetime.now().isoformat()

        # 保存日志
        try:
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            self.streamer.print("system", f"保存sandbox日志失败: {e}")

    def _load_sandbox_log(self, date: str, time_point: str) -> Dict[str, Any]:
        """加载sandbox活动日志"""
        log_file = self.sandbox_dir / f"sandbox_day_{date.replace('-', '_')}.json"

        if not log_file.exists():
            return {}

        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                log_data = json.load(f)
            return log_data.get(time_point, {})
        except Exception as e:
            self.streamer.print("system", f"加载sandbox日志失败: {e}")
            return {}


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="Live交易思考基金 - 时间Sandbox系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 运行指定日期的完整模拟
  python live_trading_thinking_fund.py --date 2025-01-15 --tickers AAPL,MSFT

  # 使用环境变量中的股票配置
  python live_trading_thinking_fund.py --date 2025-01-15

  # 强制运行（忽略各种检查）
  python live_trading_thinking_fund.py --date 2025-01-15 --force-run

  # 自定义沟通轮数
  python live_trading_thinking_fund.py --date 2025-01-15 --max-comm-cycles 3
        """
    )

    # 必需参数
    parser.add_argument(
        '--date',
        type=str,
        help='指定单个模拟日期 (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--start-date',
        type=str,
        help='多日模拟开始日期 (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--end-date',
        type=str,
        help='多日模拟结束日期 (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--config_name',
        type=str,
        required=True,
        help='配置的数据存储目录名称'
    )
    # 可选参数
    parser.add_argument(
        '--tickers',
        type=str,
        help='股票代码列表，用逗号分隔 (可选，使用环境变量配置)'
    )

    parser.add_argument(
        '--max-comm-cycles',
        type=int,
        help='最大沟通轮数 (默认: 2)'
    )

    parser.add_argument(
        '--force-run',
        action='store_true',
        help='强制运行，如果已经是已经运行过的交易日则重新运行'
    )

    parser.add_argument(
        '--base-dir',
        type=str,
        help='基础目录'
    )
    
    # Portfolio模式参数
    parser.add_argument(
        '--mode',
        type=str,
        choices=["signal", "portfolio"],
        help='运行模式: signal (信号模式) 或 portfolio (投资组合模式)。默认从.env读取'
    )
    
    parser.add_argument(
        '--initial-cash',
        type=float,
        help='Portfolio模式的初始现金 (默认: 100000.0)'
    )
    
    parser.add_argument(
        '--margin-requirement',
        type=float,
        help='Portfolio模式的保证金要求，0.0表示禁用做空，0.5表示50%%保证金 (默认: 0.0)'
    )

    args = parser.parse_args()

    try:
        # 加载配置
        config = LiveThinkingFundConfig()
        config.override_with_args(args)
        
        # 创建 ConsoleStreamer 用于初始化阶段
        from src.servers.streamer import ConsoleStreamer
        console_streamer = ConsoleStreamer()
        
        # 初始化记忆系统（自动根据环境变量选择框架）
        memory_instance = initialize_memory_system(base_dir=config.config_name, streamer=console_streamer)
        print(f"✅ 记忆系统已初始化: {memory_instance.get_framework_name()}")
        
        # 初始化思考基金系统，传递mode和portfolio参数
        thinking_fund = LiveTradingThinkingFund(
            base_dir=config.config_name, 
            streamer=console_streamer,
            mode=config.mode,  # 传递运行模式
            initial_cash=config.initial_cash,  # Portfolio模式初始现金
            margin_requirement=config.margin_requirement  # Portfolio模式保证金要求
        )
        
        tickers = args.tickers.split(",") if args.tickers else config.tickers
        from pprint import pprint
        print(f"\n📊 Live Trading Thinking Fund 配置:")
        print(f"   运行模式: {config.mode.upper()}")
        if config.mode == "portfolio":
            print(f"   初始现金: ${config.initial_cash:,.2f}")
            print(f"   保证金要求: {config.margin_requirement * 100:.1f}%")
        pprint(config.__dict__)

        if args.start_date or args.end_date:
            if not args.start_date or not args.end_date:
                print("错误: 多日模式需同时提供 --start-date 与 --end-date")
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
            print(f"\n多日Sandbox模拟完成: {results['summary']['success_days']} / {results['summary']['total_days']} 成功")
        else:
            if not args.date:
                print("错误: 请提供 --date 或者 --start-date/--end-date")
                sys.exit(1)
            if not thinking_fund.validate_date_format(args.date):
                print(f"错误: 日期格式无效: {args.date} (需要 YYYY-MM-DD)")
                sys.exit(1)

            results = thinking_fund.run_full_day_simulation(
                date=args.date,
                tickers=tickers,
                max_comm_cycles=args.max_comm_cycles,
                force_run=args.force_run
            )
            print(f"\n{args.date} 时间Sandbox模拟完成!")

    except KeyboardInterrupt:
        print("\n用户中断模拟")
        sys.exit(1)
    except Exception as e:
        print(f"\n模拟过程中出现错误: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()