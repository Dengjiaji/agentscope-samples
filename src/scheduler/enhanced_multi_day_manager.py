"""
增强型多日管理器 - 整合跨日状态管理和Pre/Post分阶段逻辑

这个类结合了：
1. MultiDayManager 的跨日状态管理能力
2. LiveTradingThinkingFund 的 Pre-Market 和 Post-Market 分阶段逻辑
3. 完整的记忆管理和仪表盘集成

"""

import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from collections import defaultdict

from src.scheduler.multi_day_manager import MultiDayManager
from src.dashboard.team_dashboard_generator import TeamDashboardGenerator
from src.tools.data_tools import get_prices

# 尝试导入记忆系统
try:
    from src.memory.llm_memory_decision_system import LLMMemoryDecisionSystem
    MEMORY_SYSTEM_AVAILABLE = True
except ImportError:
    MEMORY_SYSTEM_AVAILABLE = False
    logging.warning("LLM记忆系统不可用")

logger = logging.getLogger(__name__)


class EnhancedMultiDayManager(MultiDayManager):
    """
    增强型多日管理器
    
    特性：
    - 继承 MultiDayManager 的状态管理能力
    - 添加 Pre-Market 和 Post-Market 分阶段逻辑
    - 集成 LLM 记忆系统
    - 集成团队仪表盘
    - 支持 Portfolio 模式的跨日持仓传递
    """
    
    def __init__(
        self,
        tickers: List[str],
        start_date: str,
        end_date: str,
        mode: str = "portfolio",
        initial_cash: float = 100000.0,
        margin_requirement: float = 0.0,
        base_output_dir: str = "./analysis_results_logs",
        state_dir: str = "./live_trading/state",
        dashboard_dir: Optional[str] = None,
        max_communication_cycles: int = 2,
        enable_communications: bool = True,
        enable_notifications: bool = True,
        streamer = None,
        **kwargs
    ):
        """
        初始化增强型多日管理器
        
        Args:
            tickers: 股票代码列表
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            mode: 运行模式 ("signal" 或 "portfolio")
            initial_cash: 初始现金（Portfolio模式）
            margin_requirement: 保证金要求（Portfolio模式）
            base_output_dir: 输出目录
            state_dir: 状态保存目录
            dashboard_dir: 仪表盘目录
            max_communication_cycles: 最大通信轮数
            enable_communications: 是否启用通信机制
            enable_notifications: 是否启用通知机制
            streamer: 事件广播器（用于前端推送）
        """
        # 调用父类初始化
        super().__init__(
            tickers=tickers,
            start_date=start_date,
            end_date=end_date,
            base_output_dir=base_output_dir,
            max_communication_cycles=max_communication_cycles,
            prefetch_data=kwargs.get('prefetch_data', False),
            okr_enabled=kwargs.get('okr_enabled', False)
        )
        
        # Portfolio 模式参数
        self.mode = mode
        self.initial_cash = initial_cash
        self.margin_requirement = margin_requirement
        
        # 通信和通知配置
        self.enable_communications = enable_communications
        self.enable_notifications = enable_notifications
        
        # 状态管理目录
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        
        # 当前 Portfolio 状态（核心：跨日传递）
        self.current_portfolio: Optional[Dict[str, Any]] = None
        
        # 事件广播器（用于实时推送到前端）
        self.streamer = streamer
        
        # 初始化 LLM 记忆系统
        if MEMORY_SYSTEM_AVAILABLE:
            try:
                self.llm_memory_system = LLMMemoryDecisionSystem()
                logger.info("✅ LLM记忆管理系统已启用")
            except Exception as e:
                logger.warning(f"⚠️ LLM记忆系统初始化失败: {e}")
                self.llm_memory_system = None
        else:
            self.llm_memory_system = None
            logger.info("⚠️ LLM记忆管理系统未启用")
        
        # 初始化团队仪表盘
        if dashboard_dir is None:
            dashboard_dir = self.state_dir / "team_dashboard"
        self.dashboard_dir = Path(dashboard_dir)
        self.dashboard_dir.mkdir(parents=True, exist_ok=True)
        
        self.dashboard_generator = TeamDashboardGenerator(
            dashboard_dir=self.dashboard_dir,
            initial_cash=initial_cash
        )
        
        # 初始化空仪表盘（如果不存在）
        if not (self.dashboard_dir / "summary.json").exists():
            self.dashboard_generator.initialize_empty_dashboard()
            logger.info(f"✅ 团队仪表盘已初始化: {self.dashboard_dir}")
        
        logger.info(f"✅ EnhancedMultiDayManager 初始化完成")
        logger.info(f"   模式: {mode.upper()}")
        logger.info(f"   初始现金: ${initial_cash:,.2f}")
        logger.info(f"   保证金要求: {margin_requirement * 100:.1f}%")
    
    def set_streamer(self, streamer):
        """设置事件广播器（用于前端实时推送）"""
        self.streamer = streamer
        logger.info("✅ 事件广播器已设置")
    
    # ==================== 主接口 ====================
    
    def run_multi_day_with_phases(
        self,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        运行多日策略（带Pre/Post阶段）
        
        这是对外的主接口，整合了：
        - 跨日状态管理
        - Pre-Market 分析
        - Post-Market 复盘
        - 记忆管理
        - 仪表盘更新
        
        Args:
            progress_callback: 进度回调函数
            
        Returns:
            多日分析汇总结果
        """
        logger.info("🚀 开始多日策略分析（带Pre/Post阶段）")
        logger.info(f"   时间范围: {self.start_date} → {self.end_date}")
        logger.info(f"   分析标的: {', '.join(self.tickers)}")
        
        # 生成交易日序列
        trading_dates = self.get_us_trading_dates(self.start_date, self.end_date)
        
        if len(trading_dates) == 0:
            raise ValueError(f"指定日期范围内无交易日: {self.start_date} 到 {self.end_date}")
        
        logger.info(f"📅 共 {len(trading_dates)} 个交易日待分析")
        
        # 初始化统计
        total_days = len(trading_dates)
        successful_days = 0
        failed_days = 0
        self.daily_results = []
        
        # 尝试恢复最新的 Portfolio 状态
        if self.mode == "portfolio":
            self.current_portfolio = self.get_latest_portfolio()
            if self.current_portfolio:
                logger.info(f"✅ 已恢复Portfolio状态: 现金=${self.current_portfolio.get('cash', 0):,.2f}")
        
        # 逐日执行
        for idx, current_date in enumerate(trading_dates):
            current_date_str = current_date.strftime("%Y-%m-%d")
            
            logger.info(f"\n{'='*60}")
            logger.info(f"第 {idx+1}/{total_days} 日: {current_date_str}")
            logger.info(f"{'='*60}")
            
            # 发送进度更新
            if progress_callback:
                progress_callback({
                    "type": "day_start",
                    "current_date": current_date_str,
                    "progress": idx / total_days,
                    "day_number": idx + 1,
                    "total_days": total_days
                })
            
            try:
                # 运行单日完整流程（Pre + Post）
                day_result = self.run_single_day_with_phases(
                    date=current_date_str,
                    tickers=self.tickers,
                    is_first_day=(idx == 0)
                )
                
                # 记录成功
                successful_days += 1
                self.daily_results.append({
                    "date": current_date_str,
                    "status": "success",
                    "result": day_result
                })
                
                logger.info(f"✅ {current_date_str} 分析完成")
                
                # 发送单日结果
                if progress_callback:
                    progress_callback({
                        "type": "day_complete",
                        "date": current_date_str,
                        "status": "success",
                        "result": day_result
                    })
                
            except Exception as e:
                logger.error(f"❌ {current_date_str} 分析失败: {e}", exc_info=True)
                
                failed_days += 1
                self.daily_results.append({
                    "date": current_date_str,
                    "status": "failed",
                    "error": str(e)
                })
                
                # 发送错误通知
                if progress_callback:
                    progress_callback({
                        "type": "day_error",
                        "date": current_date_str,
                        "error": str(e)
                    })
        
        # 生成汇总报告
        summary = self._generate_multi_day_summary(
            total_days=total_days,
            successful_days=successful_days,
            failed_days=failed_days
        )
        
        logger.info(f"\n{'='*60}")
        logger.info("✅ 多日策略分析完成")
        logger.info(f"   总交易日: {total_days}")
        logger.info(f"   成功: {successful_days}")
        logger.info(f"   失败: {failed_days}")
        logger.info(f"{'='*60}")
        
        return summary
    
    def run_single_day_with_phases(
        self,
        date: str,
        tickers: List[str],
        is_first_day: bool = False
    ) -> Dict[str, Any]:
        """
        运行单日完整流程（Pre-Market + Post-Market）
        
        Args:
            date: 交易日期 (YYYY-MM-DD)
            tickers: 股票代码列表
            is_first_day: 是否为第一天（需要初始化Portfolio）
            
        Returns:
            单日完整结果
        """
        result = {
            'date': date,
            'is_trading_day': True,  # 已经通过交易日筛选
            'pre_market': None,
            'post_market': None
        }
        
        # ========== 阶段1: Pre-Market 分析 ==========
        logger.info(f"🌅 开始 Pre-Market 分析...")
        
        pre_market_result = self.run_pre_market_phase(
            date=date,
            tickers=tickers,
            is_first_day=is_first_day
        )
        
        result['pre_market'] = pre_market_result
        
        # ========== 阶段2: Post-Market 复盘 ==========
        logger.info(f"🌆 开始 Post-Market 复盘...")
        
        post_market_result = self.run_post_market_phase(
            date=date,
            tickers=tickers,
            pre_market_result=pre_market_result
        )
        
        result['post_market'] = post_market_result
        
        return result
    
    # ==================== Pre-Market 阶段 ====================
    
    def run_pre_market_phase(
        self,
        date: str,
        tickers: List[str],
        is_first_day: bool = False
    ) -> Dict[str, Any]:
        """
        Pre-Market 阶段：交易前分析和决策
        
        流程：
        1. 准备分析状态（包含历史Portfolio）
        2. 运行完整分析引擎（4个阶段）
        3. 执行Portfolio交易
        4. 提取信号和收益率
        5. 更新仪表盘
        6. 保存Portfolio状态
        
        Args:
            date: 交易日期
            tickers: 股票代码列表
            is_first_day: 是否为第一天
            
        Returns:
            Pre-Market 分析结果
        """
        self._log("system", f"===== 交易前分析 ({date}) =====")
        self._log("system", f"时间点: Pre-Market (09:30前)")
        self._log("system", f"分析标的: {', '.join(tickers)}")
        
        # 1. 准备分析状态
        lookback_start = (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")
        daily_state = self.engine.create_base_state(tickers, lookback_start, date)
        
        # 设置元数据
        daily_state["metadata"]["communication_enabled"] = self.enable_communications
        daily_state["metadata"]["notifications_enabled"] = self.enable_notifications
        daily_state["metadata"]["max_communication_cycles"] = self.max_communication_cycles
        daily_state["metadata"]["mode"] = self.mode
        daily_state["metadata"]["trading_date"] = date
        
        # 2. 注入或初始化 Portfolio 状态 ⭐⭐⭐
        if self.mode == "portfolio":
            if is_first_day or self.current_portfolio is None:
                # 第一天：初始化Portfolio
                self.current_portfolio = {
                    "cash": self.initial_cash,
                    "positions": {},
                    "margin_requirement": self.margin_requirement,
                    "margin_used": 0.0
                }
                logger.info(f"💰 初始化Portfolio: 现金=${self.initial_cash:,.2f}")
            else:
                # 非第一天：使用前一天的状态
                logger.info(f"💼 使用前一天Portfolio: 现金=${self.current_portfolio.get('cash', 0):,.2f}, "
                          f"持仓数={len(self.current_portfolio.get('positions', {}))}")
            
            # 注入到分析状态
            if "data" not in daily_state:
                daily_state["data"] = {}
            daily_state["data"]["portfolio"] = self.current_portfolio
            
            # 设置Portfolio参数
            daily_state["metadata"]["initial_cash"] = self.initial_cash
            daily_state["metadata"]["margin_requirement"] = self.margin_requirement
        
        # 3. 运行完整分析引擎
        self._log("system", "开始运行完整分析引擎...")
        
        analysis_result = self.engine.run_full_analysis_with_communications(
            tickers=tickers,
            start_date=lookback_start,
            end_date=date,
            enable_communications=self.enable_communications,
            enable_notifications=self.enable_notifications,
            mode=self.mode,
            state=daily_state
        )
        
        # 4. 提取PM信号
        pm_signals = self._extract_pm_signals(analysis_result)
        
        # 5. 获取当日真实收益率
        real_returns = self._get_real_returns(tickers, date)
        
        # 6. 提取分析师信号
        ana_signals = self._extract_analyst_signals(analysis_result, tickers)
        
        # 7. Portfolio模式：提取执行报告并更新状态
        portfolio_summary = {}
        updated_portfolio = None
        
        if self.mode == "portfolio":
            try:
                pm_results = analysis_result.get('portfolio_management_results', {})
                
                # 尝试从 final_execution_report 获取（优先）
                if 'final_execution_report' in pm_results:
                    execution_report = pm_results['final_execution_report']
                else:
                    # 回退到 execution_report
                    execution_report = pm_results.get('execution_report', {})
                
                portfolio_summary = execution_report.get('portfolio_summary', {})
                updated_portfolio = execution_report.get('updated_portfolio', {})
                
                # 更新内部状态（传递到下一天）⭐⭐⭐
                if updated_portfolio:
                    self.current_portfolio = updated_portfolio
                    logger.info(f"💼 Portfolio状态已更新: 现金=${updated_portfolio.get('cash', 0):,.2f}")
                    
                    # 保存到磁盘
                    self.save_portfolio_state(date, updated_portfolio)
                
            except Exception as e:
                logger.error(f"⚠️ 提取Portfolio信息失败: {e}", exc_info=True)
        
        # 8. 构建 live_env
        live_env = {
            'pm_signals': pm_signals,
            'ana_signals': ana_signals,
            'real_returns': real_returns,
            'portfolio_summary': portfolio_summary,
            'updated_portfolio': updated_portfolio
        }
        
        # 9. 更新团队仪表盘
        try:
            dashboard_stats = self.dashboard_generator.update_from_day_result(
                date=date,
                pre_market_result={
                    'status': 'success',
                    'signals': pm_signals,
                    'live_env': live_env
                },
                mode=self.mode
            )
            self._log("system", 
                     f"📊 团队仪表盘已更新: 新增{dashboard_stats.get('trades_added', 0)}笔交易, "
                     f"更新{dashboard_stats.get('agents_updated', 0)}个Agent")
        except Exception as e:
            logger.error(f"⚠️ 团队仪表盘更新失败: {e}", exc_info=True)
        
        # 10. 返回结果
        return {
            'status': 'success',
            'date': date,
            'signals': pm_signals,
            'live_env': live_env,
            'raw_results': analysis_result
        }
    
    # ==================== Post-Market 阶段 ====================
    
    def run_post_market_phase(
        self,
        date: str,
        tickers: List[str],
        pre_market_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Post-Market 阶段：交易后复盘和记忆管理
        
        支持两种模式：
        - central_review: PM统一评估所有分析师（旧模式）
        - individual_review: 每个Agent自主复盘（新模式，默认）
        
        流程：
        1. 提取Pre-Market结果
        2. 显示复盘信息
        3. 根据模式执行记忆管理
        4. 返回结果
        
        Args:
            date: 交易日期
            tickers: 股票代码列表
            pre_market_result: Pre-Market阶段的结果
            
        Returns:
            Post-Market 复盘结果
        """
        self._log("system", f"===== 交易后复盘 ({date}) =====")
        self._log("system", f"时间点: Post-Market (16:00后)")
        self._log("system", f"复盘标的: {', '.join(tickers)}")
        
        # 1. 提取Pre-Market数据
        live_env = pre_market_result.get('live_env', {})
        pm_signals = live_env.get('pm_signals', {})
        ana_signals = live_env.get('ana_signals', {})
        real_returns = live_env.get('real_returns', {})
        portfolio_summary = live_env.get('portfolio_summary', {})
        
        # 2. 显示复盘信息
        self._display_post_market_review(
            date=date,
            tickers=tickers,
            pm_signals=pm_signals,
            ana_signals=ana_signals,
            real_returns=real_returns,
            portfolio_summary=portfolio_summary
        )
        
        # 3. 获取复盘模式
        review_mode = os.getenv('MEMORY_REVIEW_MODE', 'individual_review').lower()
        
        if review_mode == 'individual_review':
            # 新模式：每个Agent自主复盘
            result = self._run_individual_review(
                date=date,
                tickers=tickers,
                pm_signals=pm_signals,
                ana_signals=ana_signals,
                real_returns=real_returns,
                portfolio_summary=portfolio_summary
            )
        else:
            # 旧模式：PM统一评估
            result = self._run_central_review(
                date=date,
                tickers=tickers,
                pm_signals=pm_signals,
                ana_signals=ana_signals,
                real_returns=real_returns
            )
        
        return result
    
    # ==================== 辅助方法 ====================
    
    def _extract_pm_signals(self, analysis_result: Dict[str, Any]) -> Dict[str, Dict]:
        """从分析结果中提取PM信号"""
        try:
            pm_results = analysis_result.get('portfolio_management_results', {})
            pm_decisions = pm_results.get('pm_decisions', {})
            
            # 解析信号
            signals = {}
            decisions = pm_decisions.get('decisions', {})
            
            for ticker, decision_data in decisions.items():
                if isinstance(decision_data, dict):
                    signals[ticker] = {
                        'signal': decision_data.get('action', 'hold').upper(),
                        'action': decision_data.get('action', 'hold'),
                        'quantity': decision_data.get('quantity', 0),
                        'confidence': decision_data.get('confidence', 0),
                        'reasoning': decision_data.get('reasoning', '')
                    }
            
            return signals
        except Exception as e:
            logger.error(f"⚠️ 提取PM信号失败: {e}")
            return {}
    
    def _extract_analyst_signals(
        self,
        analysis_result: Dict[str, Any],
        tickers: List[str]
    ) -> Dict[str, Dict[str, str]]:
        """提取分析师信号"""
        ana_signals = defaultdict(lambda: defaultdict(str))
        
        try:
            analyst_results = analysis_result.get('final_analyst_results', {})
            
            for agent in ['sentiment_analyst', 'technical_analyst', 'fundamentals_analyst', 'valuation_analyst']:
                for ticker in tickers:
                    agent_data = analyst_results.get(agent, {}).get(ticker, {})
                    signal = agent_data.get('signal', 'N/A')
                    ana_signals[agent][ticker] = signal
        except Exception as e:
            logger.error(f"⚠️ 提取分析师信号失败: {e}")
        
        return dict(ana_signals)
    
    def _get_real_returns(self, tickers: List[str], date: str) -> Dict[str, float]:
        """获取当日真实收益率"""
        real_returns = {}
        
        try:
            for ticker in tickers:
                prices = get_prices(ticker, date, date)
                if prices and len(prices) > 0:
                    daily_return = prices[0].get('daily_return', 0.0)
                    real_returns[ticker] = daily_return
                else:
                    real_returns[ticker] = 0.0
        except Exception as e:
            logger.error(f"⚠️ 获取真实收益率失败: {e}")
            for ticker in tickers:
                real_returns[ticker] = 0.0
        
        return real_returns
    
    def _display_post_market_review(
        self,
        date: str,
        tickers: List[str],
        pm_signals: Dict,
        ana_signals: Dict,
        real_returns: Dict,
        portfolio_summary: Dict
    ):
        """显示复盘信息"""
        # 1. PM信号回顾
        pm_lines = ["基于交易前分析进行复盘...", "Portfolio Manager信号回顾:"]
        
        if self.mode == "portfolio":
            for ticker in tickers:
                if ticker in pm_signals:
                    sig = pm_signals[ticker]
                    action = sig.get('action', 'N/A')
                    quantity = sig.get('quantity', 0)
                    confidence = sig.get('confidence', 'N/A')
                    signal = sig.get('signal', 'N/A')
                    
                    if quantity > 0:
                        pm_lines.append(f"  {ticker}: {signal} ({action} {quantity}股, 置信度: {confidence}%)")
                    else:
                        pm_lines.append(f"  {ticker}: {signal} ({action}, 置信度: {confidence}%)")
                else:
                    pm_lines.append(f"  {ticker}: 无信号数据")
        else:
            for ticker in tickers:
                if ticker in pm_signals:
                    sig = pm_signals[ticker]
                    pm_lines.append(
                        f"  {ticker}: {sig.get('signal', 'N/A')} "
                        f"({sig.get('action', 'N/A')}, 置信度: {sig.get('confidence', 'N/A')}%)"
                    )
                else:
                    pm_lines.append(f"  {ticker}: 无信号数据")
        
        # 2. 实际收益表现
        returns_lines = ["实际收益表现:"]
        
        for ticker in tickers:
            if ticker in real_returns:
                daily_ret = real_returns[ticker] * 100
                sig = pm_signals.get(ticker, {})
                signal = sig.get('signal', 'N/A')
                returns_lines.append(f"  {ticker}: {daily_ret:.2f}% (信号: {signal})")
            else:
                returns_lines.append(f"  {ticker}: 无收益数据")
        
        # Portfolio总结
        if self.mode == "portfolio" and portfolio_summary:
            total_value = portfolio_summary.get('total_value', 0)
            cash = portfolio_summary.get('cash', 0)
            returns_lines.append(f"\nPortfolio总价值: ${total_value:,.2f} (现金: ${cash:,.2f})")
        
        # 3. 分析师信号对比
        analyst_lines = ["Analyst信号对比:"]
        for agent, agent_signals in ana_signals.items():
            analyst_lines.append(f"\n{agent}:")
            for ticker in tickers:
                signal = agent_signals.get(ticker, 'N/A')
                analyst_lines.append(f"  {ticker}: {signal}")
        
        # 输出
        self._log("agent", "\n".join(pm_lines) + "\n" + "\n".join(returns_lines) + 
                 "\n" + "\n".join(analyst_lines), role_key="portfolio_manager")
    
    def _process_memory_decision(self, llm_decision: Dict[str, Any]) -> Optional[List]:
        """处理LLM记忆决策结果"""
        if llm_decision.get('status') != 'success':
            self._log("system", f"⚠️ LLM决策失败: {llm_decision.get('error', 'Unknown')}")
            return None
        
        mode = llm_decision.get('mode')
        
        if mode == 'operations_executed':
            execution_results = llm_decision.get('execution_results', [])
            successful = sum(1 for r in execution_results if r['result']['status'] == 'success')
            total = len(execution_results)
            
            memory_lines = [
                "使用 LLM tool_call 进行智能记忆管理",
                f"执行了 {llm_decision.get('operations_count', 0)} 个记忆操作",
                f"执行统计：成功 {successful}/{total}",
                "\n工具调用详情:"
            ]
            
            for i, exec_result in enumerate(execution_results, 1):
                tool_name = exec_result['tool_name']
                args = exec_result['args']
                result = exec_result['result']
                
                memory_lines.append(f"\n{i}. 工具: {tool_name}")
                memory_lines.append(f"   分析师: {args.get('analyst_id', 'N/A')}")
                
                agent_id = args.get('analyst_id', 'N/A')
                
                if result['status'] == 'success':
                    memory_lines.append(f"   状态: ✅ 成功")
                    if 'affected_count' in result:
                        memory_lines.append(f"   影响记忆数: {result['affected_count']}")
                else:
                    memory_lines.append(f"   状态: ❌ 失败 - {result.get('error', 'Unknown')}")
                
                # 显示详细操作信息
                if tool_name == 'search_and_update_analyst_memory':
                    agent_mem_lines = [
                        '[memory management]: search and update memory',
                        f"search query: {args.get('query', 'N/A')}",
                        f"new content: {args.get('new_content', 'N/A')}",
                        f"reason: {args.get('reason', 'N/A')}"
                    ]
                    self._log("agent", "\n".join(agent_mem_lines), role_key=agent_id)
                
                elif tool_name == 'search_and_delete_analyst_memory':
                    agent_mem_lines = [
                        '[memory management]: search and delete memory',
                        f"search query: {args.get('query', 'N/A')}",
                        f"reason: {args.get('reason', 'N/A')}"
                    ]
                    self._log("agent", "\n".join(agent_mem_lines), role_key=agent_id)
            
            self._log("agent", "\n".join(memory_lines), role_key="portfolio_manager")
            return execution_results
        
        elif mode == 'no_action':
            no_action_lines = [
                "使用 LLM tool_call 进行智能记忆管理",
                "LLM 认为无需记忆操作",
                f"理由: {llm_decision.get('reasoning', 'N/A')}"
            ]
            self._log("agent", "\n".join(no_action_lines), role_key="portfolio_manager")
            return None
        
        else:
            self._log("system", f"⚠️ 未知的LLM决策模式: {mode}")
            return None
    
    def _log(self, event_type: str, content: str, **kwargs):
        """统一的日志输出方法"""
        # 输出到控制台
        logger.info(content)
        
        # 如果有streamer，广播到前端
        if self.streamer:
            try:
                self.streamer.print(event_type, content, **kwargs)
            except Exception as e:
                logger.error(f"⚠️ 广播消息失败: {e}")
    
    def _generate_multi_day_summary(
        self,
        total_days: int,
        successful_days: int,
        failed_days: int
    ) -> Dict[str, Any]:
        """生成多日汇总报告"""
        return {
            'session_id': self.session_id,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'tickers': self.tickers,
            'mode': self.mode,
            'total_days': total_days,
            'successful_days': successful_days,
            'failed_days': failed_days,
            'daily_results': self.daily_results,
            'final_portfolio': self.current_portfolio
        }
    
    # ==================== 状态持久化 ====================
    
    def save_portfolio_state(self, date: str, portfolio: Dict[str, Any]):
        """保存Portfolio状态到磁盘"""
        try:
            state_file = self.state_dir / f"portfolio_{date}.json"
            with open(state_file, 'w') as f:
                json.dump({
                    'date': date,
                    'timestamp': datetime.now().isoformat(),
                    'portfolio': portfolio
                }, f, indent=2)
            logger.debug(f"💾 Portfolio状态已保存: {state_file}")
        except Exception as e:
            logger.error(f"⚠️ 保存Portfolio状态失败: {e}")
    
    def load_portfolio_state(self, date: str) -> Optional[Dict[str, Any]]:
        """加载指定日期的Portfolio状态"""
        try:
            state_file = self.state_dir / f"portfolio_{date}.json"
            if state_file.exists():
                with open(state_file, 'r') as f:
                    data = json.load(f)
                return data.get('portfolio')
        except Exception as e:
            logger.error(f"⚠️ 加载Portfolio状态失败: {e}")
        return None
    
    def get_latest_portfolio(self) -> Optional[Dict[str, Any]]:
        """获取最新的Portfolio状态（从磁盘）"""
        try:
            portfolio_files = sorted(self.state_dir.glob("portfolio_*.json"))
            if portfolio_files:
                latest_file = portfolio_files[-1]
                with open(latest_file, 'r') as f:
                    data = json.load(f)
                logger.info(f"📂 已加载最新Portfolio状态: {latest_file.name}")
                return data.get('portfolio')
        except Exception as e:
            logger.error(f"⚠️ 获取最新Portfolio状态失败: {e}")
        return None
    
    # ==================== 复盘模式实现 ====================
    
    def _run_individual_review(
        self,
        date: str,
        tickers: List[str],
        pm_signals: Dict[str, Any],
        ana_signals: Dict[str, Dict[str, Any]],
        real_returns: Dict[str, float],
        portfolio_summary: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Individual Review模式：每个Agent自主复盘
        
        流程：
        1. 各分析师独立复盘
        2. PM自我复盘
        3. 生成总结报告
        """
        import os
        
        self._log("system", "\n===== Individual Review 模式 =====")
        self._log("system", "各Agent独立进行自我复盘")
        
        reflection_results = {}
        
        # 检查是否启用自主记忆管理
        enable_individual_review = os.getenv('ENABLE_INDIVIDUAL_REVIEW', 'true').lower() == 'true'
        
        if not enable_individual_review:
            self._log("system", "⚠️ Individual Review已禁用（ENABLE_INDIVIDUAL_REVIEW=false）")
            return {
                'status': 'skipped',
                'mode': 'individual_review',
                'date': date,
                'reason': 'Individual Review disabled'
            }
        
        try:
            from src.memory.agent_self_reflection import create_reflection_system
            
            # ========== 1. 各分析师自我复盘 ==========
            self._log("system", "\n--- 分析师自我复盘 ---")
            
            analysts = ['technical_analyst', 'fundamentals_analyst', 
                       'sentiment_analyst', 'valuation_analyst']
            
            for analyst_id in analysts:
                try:
                    # 提取该分析师的信号
                    my_signals = {}
                    for ticker in tickers:
                        if analyst_id in ana_signals and ticker in ana_signals[analyst_id]:
                            signal_value = ana_signals[analyst_id][ticker]
                            my_signals[ticker] = {
                                'signal': signal_value if isinstance(signal_value, str) else 'N/A',
                                'confidence': 'N/A',
                                'reasoning': ''
                            }
                    
                    # 创建复盘系统（传递streamer）
                    reflection_system = create_reflection_system(analyst_id, self.base_dir, streamer=self.streamer)
                    
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
                    logger.error(f"⚠️ {analyst_id} 自我复盘失败: {e}", exc_info=True)
                    reflection_results[analyst_id] = {
                        'status': 'failed',
                        'error': str(e)
                    }
            
            # ========== 2. PM自我复盘 ==========
            self._log("system", "\n--- Portfolio Manager 自我复盘 ---")
            
            try:
                pm_reflection_system = create_reflection_system('portfolio_manager', self.base_dir, streamer=self.streamer)
                
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
                logger.error(f"⚠️ Portfolio Manager 自我复盘失败: {e}", exc_info=True)
                reflection_results['portfolio_manager'] = {
                    'status': 'failed',
                    'error': str(e)
                }
            
            # ========== 3. 生成总结报告 ==========
            summary = self._generate_individual_review_summary(
                reflection_results=reflection_results,
                portfolio_summary=portfolio_summary
            )
            
            self._log("system", f"\n📊 Individual Review 总结:")
            self._log("system", summary)
            
            return {
                'status': 'success',
                'mode': 'individual_review',
                'date': date,
                'reflection_results': reflection_results,
                'summary': summary
            }
            
        except Exception as e:
            logger.error(f"❌ Individual Review 执行失败: {e}", exc_info=True)
            return {
                'status': 'failed',
                'mode': 'individual_review',
                'date': date,
                'error': str(e)
            }
    
    def _run_central_review(
        self,
        date: str,
        tickers: List[str],
        pm_signals: Dict[str, Any],
        ana_signals: Dict[str, Dict[str, Any]],
        real_returns: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Central Review模式：PM统一评估所有分析师（旧模式）
        
        流程：
        1. PM评估所有分析师表现
        2. PM决定记忆操作
        3. 执行记忆操作
        """
        self._log("system", "\n===== Central Review 模式 =====")
        self._log("system", "PM统一评估所有分析师")
        
        memory_operations = None
        
        if self.llm_memory_system:
            try:
                self._log("system", "===== Portfolio Manager 记忆管理决策 =====")
                
                performance_data = {
                    'pm_signals': pm_signals,
                    'actual_returns': real_returns,
                    'analyst_signals': ana_signals,
                    'tickers': tickers
                }
                
                # 使用LLM进行记忆管理决策
                llm_decision = self.llm_memory_system.make_llm_memory_decision_with_tools(
                    performance_data, date
                )
                
                # 处理LLM决策结果
                memory_operations = self._process_memory_decision(llm_decision)
                
            except Exception as e:
                logger.error(f"⚠️ 记忆管理失败: {e}", exc_info=True)
        else:
            self._log("system", "⚠️ LLM记忆管理系统未启用")
        
        return {
            'status': 'success',
            'mode': 'central_review',
            'date': date,
            'review_completed': True,
            'memory_operations': memory_operations
        }
    
    def _generate_individual_review_summary(
        self,
        reflection_results: Dict[str, Dict[str, Any]],
        portfolio_summary: Dict[str, Any]
    ) -> str:
        """
        生成Individual Review总结
        
        Args:
            reflection_results: 所有Agent的复盘结果
            portfolio_summary: Portfolio总结
        
        Returns:
            总结文本
        """
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
        
        # Portfolio表现
        if portfolio_summary:
            pnl = portfolio_summary.get('pnl_percent', 0)
            summary_lines.append(f"\nPortfolio表现: {pnl:+.2f}%")
        
        # 各Agent状态
        summary_lines.append("\n各Agent复盘状态:")
        for agent_id, result in reflection_results.items():
            status = result.get('status', 'unknown')
            ops_count = result.get('operations_count', 0)
            status_emoji = "✅" if status == 'success' else "❌"
            summary_lines.append(f"  {status_emoji} {agent_id}: {status} ({ops_count} 次操作)")
        
        return "\n".join(summary_lines)

