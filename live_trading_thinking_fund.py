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

import os
import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import defaultdict
from dotenv import load_dotenv

# 额外引入：支持价格合成/节流
from src.memory.memory_system import LLMMemoryDecisionSystem
from src.servers.streamer import ConsoleStreamer
from src.dashboard.team_dashboard import TeamDashboardGenerator

load_dotenv()
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from src.config.env_config import LiveThinkingFundConfig
from src.memory.memory_factory import initialize_memory_system

# from src.memory.unified_memory import unified_memory_manager
MEMORY_AVAILABLE = True
LLM_AVAILABLE = True
MEMORY_TOOLS_AVAILABLE = True

import json

US_TRADING_CALENDAR_AVAILABLE = True
from src.config.path_config import get_directory_config


class LiveTradingThinkingFund:
    """Live交易思考基金 - 时间Sandbox系统"""

    def __init__(self, base_dir: str, streamer=None, mode: str = "portfolio", initial_cash: float = 100000.0, margin_requirement: float = 0.0, pause_before_trade: bool = False):
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

        # 初始化Live交易系统（传递streamer和pause_before_trade）
        self.live_system = LiveTradingSystem(base_dir=base_dir, streamer=self.streamer, pause_before_trade=pause_before_trade)

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
        
        # ========== 新增：状态管理（学习MultiDayManager）⭐⭐⭐ ==========
        self.state_dir = self.base_dir / "state"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        
        # Portfolio状态管理（跨日传递）
        self.current_portfolio_state = None
        if self.mode == "portfolio":
            self._initialize_portfolio_state()
        
        # 初始化团队仪表盘生成器
        dashboard_dir = self.sandbox_dir / "team_dashboard"
        self.dashboard_generator = TeamDashboardGenerator(
            dashboard_dir=dashboard_dir,
            initial_cash=initial_cash
        )
        # 初始化空仪表盘（如果不存在）
        if not (dashboard_dir / "summary.json").exists():
            self.dashboard_generator.initialize_empty_dashboard()

    # ========== Portfolio状态管理方法（学习MultiDayManager）⭐⭐⭐ ==========
    
    def _initialize_portfolio_state(self):
        """初始化Portfolio状态（优先加载最新状态）"""
        # 尝试加载最新的Portfolio状态
        latest_state = self._load_latest_portfolio_state()
        
        if latest_state:
            self.current_portfolio_state = latest_state
            print(f"✅ 从磁盘加载Portfolio状态: 现金 ${latest_state['cash']:,.2f}, "
                  f"持仓数 {len([p for p in latest_state.get('positions', {}).values() if p.get('long', 0) > 0 or p.get('short', 0) > 0])}")
        else:
            # 初始化新状态
            self.current_portfolio_state = {
                "cash": self.initial_cash,
                "positions": {},
                "margin_requirement": self.margin_requirement,
                "margin_used": 0.0
            }
            print(f"✅ 初始化Portfolio状态: 现金 ${self.initial_cash:,.2f}")
    
    def _load_latest_portfolio_state(self) -> Optional[Dict[str, Any]]:
        """加载最新的Portfolio状态（类似MultiDayManager.load_previous_state）"""
        portfolio_files = sorted(self.state_dir.glob("portfolio_*.json"))
        if portfolio_files:
            latest_file = portfolio_files[-1]
            try:
                with open(latest_file, 'r') as f:
                    state = json.load(f)
                return state
            except Exception as e:
                print(f"⚠️ 加载Portfolio状态失败 ({latest_file}): {e}")
        return None
    
    def _save_portfolio_state(self, date: str, portfolio: Dict[str, Any]):
        """保存Portfolio状态到磁盘（类似MultiDayManager.save_daily_state）"""
        state_file = self.state_dir / f"portfolio_{date.replace('-', '_')}.json"
        try:
            with open(state_file, 'w') as f:
                json.dump(portfolio, f, indent=2, default=str)
            # print(f"💾 已保存Portfolio状态: {state_file.name}")
        except Exception as e:
            print(f"❌ 保存Portfolio状态失败: {e}")
    
    def reset_portfolio_state(self):
        """重置Portfolio状态（用于新的多日运行）"""
        if self.mode == "portfolio":
            self.current_portfolio_state = {
                "cash": self.initial_cash,
                "positions": {},
                "margin_requirement": self.margin_requirement,
                "margin_used": 0.0
            }
            print(f"🔄 Portfolio状态已重置: 现金 ${self.initial_cash:,.2f}")
    
    # ========== 原有方法 ==========
    
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

        # ========== 修改：注入Portfolio状态（学习MultiDayManager）⭐⭐⭐ ==========
        # 1. 运行策略分析（注入当前Portfolio状态）
        analysis_result = self.live_system.run_single_day_analysis(
            tickers, target_date, max_comm_cycles, enable_communications, enable_notifications,
            mode=self.mode,  # 传递运行模式
            initial_cash=self.initial_cash,  # Portfolio模式初始现金
            margin_requirement=self.margin_requirement,  # Portfolio模式保证金要求
            portfolio_state=self.current_portfolio_state  # ⭐ 注入当前Portfolio状态（跨日传递）
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
                
                # if agent not in agent_results:
                #     continue
                
                analyst_result = agent_results[agent].get('analysis_result', {})
                
                # 兼容两种格式：
                # 1. 第一轮格式: {ticker: {signal, confidence, ...}}
                # 2. 第二轮格式: {ticker_signals: [{ticker, signal, confidence, ...}]}
                if 'ticker_signals' in analyst_result:
                    # 第二轮格式
                    matched = next((item for item in analyst_result['ticker_signals'] if item['ticker'] == ticker), None)
                    if matched:                        
                        # pdb.set_trace()
                        live_env['ana_signals'][agent][ticker] = matched # ['signal']
                        # 输出第二轮信号
                        self.streamer.print("agent", 
                            f"{ticker} - 第二轮: {matched['signal']} (置信度: {matched.get('confidence', 'N/A')}%)",
                            role_key=agent
                        )
                elif ticker in analyst_result:
                    # 第一轮格式
                    if 'signal' in analyst_result[ticker]:
                        # pdb.set_trace()
                        live_env['ana_signals'][agent][ticker] = analyst_result[ticker] #['signal']
                        # 输出第一轮信号
                        confidence = analyst_result[ticker].get('confidence', 'N/A')
                        self.streamer.print("agent", 
                            f"{ticker} - 第一轮: {analyst_result[ticker]['signal']} (置信度: {confidence}%)",
                            role_key=agent
                        )

                self.streamer.print("agent","", role_key=agent)

                
        self.live_system.save_daily_signals(target_date, pm_signals)
        print("system", f"已保存 {len(pm_signals)} 个股票的交易信号")

        # 4. 计算当日收益
        target_date = str(target_date)
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
            # for agent in ['sentiment_analyst', 'technical_analyst', 'fundamentals_analyst', 'valuation_analyst']:
            #     sig = live_env['ana_signals'][agent].get(ticker, '')['signal']
            #     if sig:
            #         self.streamer.print("agent", f"{ticker}: {sig}",  role_key=agent)

        # ========== Portfolio模式：提取并更新状态（学习MultiDayManager）⭐⭐⭐ ==========
        if self.mode == "portfolio":
            # 从分析结果中提取Portfolio信息
            # pdb.set_trace()
            raw_results = analysis_result.get('raw_results', {})
            try:
                portfolio_summary = raw_results['results']['portfolio_management_results']['final_execution_report']['portfolio_summary']
                updated_portfolio = raw_results['results']['portfolio_management_results']['final_execution_report']['updated_portfolio']
            except:
                try:
                    portfolio_summary = raw_results['results']['portfolio_management_results']['execution_report']['portfolio_summary']
                    updated_portfolio = raw_results['results']['portfolio_management_results']['execution_report']['updated_portfolio']
                except:
                    # 暂停模式：execution_report返回的是 paused 状态，没有 portfolio_summary 和 updated_portfolio
                    execution_report = raw_results.get('results', {}).get('portfolio_management_results', {}).get('final_execution_report', {})
                    if execution_report.get('status') == 'paused':
                        print(f"\n⏸️ 暂停模式：Portfolio状态未更新（交易未执行）")
                        print(f"   当前现金: ${self.current_portfolio_state['cash']:,.2f}")
                        positions_count = len([p for p in self.current_portfolio_state.get('positions', {}).values() 
                                              if p.get('long', 0) > 0 or p.get('short', 0) > 0])
                        print(f"   当前持仓数: {positions_count}")
                        
                        # 使用当前状态作为 Portfolio 信息
                        portfolio_summary = {'status': 'paused', 'reason': 'pause_before_trade'}
                        updated_portfolio = self.current_portfolio_state  # 保持不变
                    else:
                        # 其他异常，重新抛出
                        raise
            
            # ⭐⭐⭐ 更新内部Portfolio状态（传递到下一天）⭐⭐⭐
            # 只在非暂停模式下更新
            if portfolio_summary.get('status') != 'paused':
                self.current_portfolio_state = updated_portfolio
                
                # 保存到磁盘（类似MultiDayManager.save_daily_state）
                self._save_portfolio_state(target_date, updated_portfolio)
                
                # 打印Portfolio变化
                print(f"\n📊 Portfolio更新:")
                print(f"   现金: ${updated_portfolio['cash']:,.2f}")
                positions_count = len([p for p in updated_portfolio.get('positions', {}).values() 
                                      if p.get('long', 0) > 0 or p.get('short', 0) > 0])
                print(f"   持仓数: {positions_count}")
                if updated_portfolio.get('margin_used', 0) > 0:
                    print(f"   保证金使用: ${updated_portfolio['margin_used']:,.2f}")
            
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
                    reasoning = signal_info.get('reasoning', '')
                    
                    # 显示操作和数量
                    if quantity > 0:
                        pm_review_lines.append(
                            f"  {ticker}: {signal} ({action} {quantity}股, 置信度: {confidence}%)"
                        )
                    else:
                        pm_review_lines.append(
                            f"  {ticker}: {signal} ({action}, 置信度: {confidence}%)"
                        )
                    
                    # 添加决策理由
                    if reasoning:
                        pm_review_lines.append(f"    💭 理由: {reasoning}")
                else:
                    pm_review_lines.append(f"  {ticker}: 无信号数据")
        else:
            # Signal模式：显示传统信号信息
            for ticker in tickers:
                if ticker in pm_signals:
                    signal_info = pm_signals[ticker]
                    reasoning = signal_info.get('reasoning', '')
                    pm_review_lines.append(
                        f"  {ticker}: {signal_info.get('signal', 'N/A')} ({signal_info.get('action', 'N/A')}, 置信度: {signal_info.get('confidence', 'N/A')}%)"
                    )
                    # 添加决策理由
                    if reasoning:
                        pm_review_lines.append(f"    💭 理由: {reasoning}")
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
                    if quantity > 0 and action in ['long', 'short']:
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
                signal = agent_signals.get(ticker, 'N/A')['signal']
                analyst_lines.append(f"  {ticker}: {signal}")
        
        self.streamer.print("agent", "\n".join(pm_review_lines)+"\n"+ "\n".join(returns_lines)+"\n"+"\n".join(analyst_lines), role_key="portfolio_manager")

        # ========== 获取复盘模式 ⭐⭐⭐ ==========
        review_mode = os.getenv('MEMORY_REVIEW_MODE', 'individual_review').lower()
        
        if review_mode == 'individual_review':
            # 新模式：Individual Review
            return self._run_individual_review_mode(date, tickers, pm_signals, ana_signals, real_returns, live_env)
        else:
            # 旧模式：Central Review
            return self._run_central_review_mode(date, tickers, pm_signals, ana_signals, real_returns)
    
    def _run_central_review_mode(self, date: str, tickers: List[str], pm_signals: Dict, ana_signals: Dict, real_returns: Dict) -> Dict[str, Any]:
        """Central Review模式：PM统一管理记忆（旧模式）"""
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
    
    def _run_individual_review_mode(self, date: str, tickers: List[str], pm_signals: Dict, ana_signals: Dict, real_returns: Dict, live_env: Dict[str, Any]) -> Dict[str, Any]:
        """Individual Review模式：每个Agent自主复盘（新模式）"""
        self.streamer.print("system", "\n===== Individual Review 模式 =====")
        self.streamer.print("system", "各Agent独立进行自我复盘")
        
        reflection_results = {}
        portfolio_summary = live_env.get('portfolio_summary', {})
        
        # 检查是否启用
        enable_individual_review = os.getenv('ENABLE_INDIVIDUAL_REVIEW', 'true').lower() == 'true'
        
        if not enable_individual_review:
            self.streamer.print("system", "⚠️ Individual Review已禁用（ENABLE_INDIVIDUAL_REVIEW=false）")
            return {
                'status': 'skipped',
                'mode': 'individual_review',
                'date': date,
                'reason': 'Individual Review disabled'
            }
        
        try:
            from src.memory.agent_self_reflection import create_reflection_system
            
            # ========== 1. 各分析师自我复盘 ==========
            self.streamer.print("system", "\n--- 分析师自我复盘 ---")
            
            analysts = ['technical_analyst', 'fundamentals_analyst', 
                       'sentiment_analyst', 'valuation_analyst']
            
            for analyst_id in analysts:
                try:
                    # 提取该分析师的信号
                    my_signals = {}
                    for ticker in tickers:
                        if analyst_id in ana_signals and ticker in ana_signals[analyst_id]:
                            signal_value = ana_signals[analyst_id][ticker]['signal']
                            signal_data = ana_signals[analyst_id][ticker]
                            
                            # 优先使用 reasoning，如果不存在则使用 tool_analysis
                            reasoning_text = signal_data.get('reasoning') or signal_data.get('tool_analysis', '')
                            
                            my_signals[ticker] = {
                                'signal': signal_value if isinstance(signal_value, str) else 'N/A',
                                'confidence': signal_data.get('confidence', 0),
                                'reasoning': reasoning_text
                            }
                    # pdb.set_trace()
                    # 创建复盘系统
                    reflection_system = create_reflection_system(analyst_id, self.base_dir)
                    
                    # 执行自我复盘
                    result = reflection_system.perform_self_reflection(
                        date=date,
                        reflection_data={
                            'my_signals': my_signals,
                            'actual_returns': real_returns,
                            'pm_decisions': pm_signals
                        },
                        context={
                            'market_condition': 'normal'
                        }
                    )
                    
                    reflection_results[analyst_id] = result
                    
                except Exception as e:
                    print(f"⚠️ {analyst_id} 自我复盘失败: {e}")
                    reflection_results[analyst_id] = {
                        'status': 'failed',
                        'error': str(e)
                    }
            
            # ========== 2. PM自我复盘 ==========
            self.streamer.print("system", "\n--- Portfolio Manager 自我复盘 ---")
            
            try:
                pm_reflection_system = create_reflection_system('portfolio_manager', self.base_dir)
                
                pm_result = pm_reflection_system.perform_self_reflection(
                    date=date,
                    reflection_data={
                        'pm_decisions': pm_signals,
                        'analyst_signals': ana_signals,
                        'actual_returns': real_returns,
                        'portfolio_summary': portfolio_summary
                    },
                    context={
                        'market_condition': 'normal'
                    }
                )
                
                reflection_results['portfolio_manager'] = pm_result
                
            except Exception as e:
                print(f"⚠️ Portfolio Manager 自我复盘失败: {e}")
                reflection_results['portfolio_manager'] = {
                    'status': 'failed',
                    'error': str(e)
                }
            
            # ========== 3. 生成总结报告 ==========
            summary = self._generate_individual_review_summary(
                reflection_results=reflection_results,
                portfolio_summary=portfolio_summary
            )
            
            self.streamer.print("system", f"\n📊 Individual Review 总结:")
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
            print(f"❌ Individual Review 执行失败: {e}")
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
        """生成Individual Review总结"""
        summary_lines = []
        
        # 统计记忆操作
        total_agents = len(reflection_results)
        successful_agents = sum(1 for r in reflection_results.values() if r.get('status') == 'success')
        total_operations = 0
        operations_by_type = {'update': 0, 'delete': 0}
        
        for agent_id, result in reflection_results.items():
            if result.get('status') == 'success':
                ops_count = result.get('operations_count', 0)
                total_operations += ops_count
                
                for op in result.get('memory_operations', []):
                    tool_name = op.get('tool_name', '')
                    if 'update' in tool_name:
                        operations_by_type['update'] += 1
                    elif 'delete' in tool_name:
                        operations_by_type['delete'] += 1
        
        summary_lines.append(f"今日共 {total_agents} 位Agent完成自我复盘")
        summary_lines.append(f"成功: {successful_agents}, 失败: {total_agents - successful_agents}")
        summary_lines.append(f"执行记忆操作: {total_operations} 次")
        
        if operations_by_type['update'] > 0:
            summary_lines.append(f"  - 更新记忆: {operations_by_type['update']} 次")
        if operations_by_type['delete'] > 0:
            summary_lines.append(f"  - 删除记忆: {operations_by_type['delete']} 次")
    
        
        # 各Agent状态
        summary_lines.append("\n各Agent复盘状态:")
        for agent_id, result in reflection_results.items():
            status = result.get('status', 'unknown')
            ops_count = result.get('operations_count', 0)
            status_emoji = "✅" if status == 'success' else "❌"
            summary_lines.append(f"  {status_emoji} {agent_id}: {status} ({ops_count} 次操作)")
        
        return "\n".join(summary_lines)

    def generate_trading_dates(self, start_date: str, end_date: str) -> List[str]:
        """生成交易日列表（使用批量查询优化性能）"""
        if not self.validate_date_format(start_date) or not self.validate_date_format(end_date):
            raise ValueError("日期格式应为 YYYY-MM-DD")
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        if start_dt > end_dt:
            raise ValueError("开始日期不得晚于结束日期")

        print(f"⏳ 正在生成交易日列表 ({start_date} -> {end_date})...")
        
        # ⭐ 方案2：使用批量查询（一次性获取所有交易日）
        if hasattr(self.live_system, 'nyse_calendar') and self.live_system.nyse_calendar:
            try:
                trading_dates = self.live_system.nyse_calendar.valid_days(
                    start_date=start_date, 
                    end_date=end_date
                )
                result = [date.strftime("%Y-%m-%d") for date in trading_dates]
                print(f"✅ 找到 {len(result)} 个交易日")
                return result
            except Exception as e:
                print(f"⚠️ 批量查询失败，使用逐日检查: {e}")
        
        # 备用方案：逐日检查（使用缓存的日历对象）
        trading_days: List[str] = []
        current = start_dt
        while current <= end_dt:
            date_str = current.strftime("%Y-%m-%d")
            if self.is_trading_day(date_str):
                trading_days.append(date_str)
            current += timedelta(days=1)
        
        print(f"✅ 找到 {len(trading_days)} 个交易日")
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
            'summary': {},
            'portfolio_state': None  # ⭐ 新增：返回Portfolio状态
        }

        if results['is_trading_day']:
            self.streamer.print("system", f"{date}是交易日，将执行交易前分析 + 交易后复盘")
            
            # ========== 显示当前Portfolio状态 ⭐ ==========
            if self.mode == "portfolio" and self.current_portfolio_state:
                positions_count = len([p for p in self.current_portfolio_state.get('positions', {}).values() 
                                      if p.get('long', 0) > 0 or p.get('short', 0) > 0])
                self.streamer.print("system", 
                    f"当前Portfolio: 现金 ${self.current_portfolio_state['cash']:,.2f}, "
                    f"持仓数 {positions_count}")

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
        
        # ========== 新增：返回Portfolio状态 ⭐ ==========
        if self.mode == "portfolio":
            results['portfolio_state'] = self.current_portfolio_state

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