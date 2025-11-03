"""
多日投资策略管理器
基于InvestingAgents项目的设计模式，实现多日循环分析和状态持续化
"""

import os
import json
import pandas as pd
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path
import pdb
# 尝试导入美国交易日历包
try:
    import pandas_market_calendars as mcal
    US_TRADING_CALENDAR_AVAILABLE = True
except ImportError:
    try:
        import exchange_calendars as xcals
        US_TRADING_CALENDAR_AVAILABLE = True
    except ImportError:
        US_TRADING_CALENDAR_AVAILABLE = False

from src.tools.api import (
    get_price_data,
    get_prices,
    get_financial_metrics,
    get_insider_trades,
    get_company_news,
)
from src.communication.analyst_memory_mem0 import memory_manager_mem0_adapter as memory_manager
from src.okr.okr_manager import OKRManager


class MultiDayManager:
    """多日投资策略管理器"""
    
    def __init__(
        self,
        engine,  # AdvancedInvestmentAnalysisEngine实例
        base_output_dir: str = "/root/wuyue.wy/Project/IA/analysis_results_logs/",
        max_communication_cycles: int = 3,
        prefetch_data: bool = True,
        okr_enabled: bool = False,
        custom_session_id: str = None,
        data_source: str = "finnhub"
    ):
        """
        初始化多日管理器
        
        Args:
            engine: 投资分析引擎实例
            base_output_dir: 基础输出目录
            max_communication_cycles: 每日最大沟通轮数
            prefetch_data: 是否预取数据
            okr_enabled: 是否启用OKR
            custom_session_id: 自定义会话ID
            data_source: 数据源 ("finnhub" 或 "financial_datasets", 默认: "finnhub")
        """
        self.engine = engine
        self.base_output_dir = base_output_dir
        self.max_communication_cycles = max_communication_cycles
        self.prefetch_data = prefetch_data
        self.okr_enabled = okr_enabled
        self.data_source = data_source
        
        # 状态追踪
        self.session_id = custom_session_id
        self.daily_results = []
        self.analyst_memory_state = None
        self.communication_logs_state = None
        self.okr_manager = None  # 将在需要时初始化
        
        # 确保输出目录存在
        os.makedirs(base_output_dir, exist_ok=True)
    
    def create_session_id(self) -> str:
        """生成会话ID"""
        return f"multi_day_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    def get_us_trading_dates(self, start_date: str, end_date: str) -> pd.DatetimeIndex:
        """
        获取美国股市交易日序列
        
        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            
        Returns:
            pd.DatetimeIndex: 交易日序列
        """
        if US_TRADING_CALENDAR_AVAILABLE:
            try:
                # 优先尝试使用 pandas_market_calendars
                if 'mcal' in globals():
                    nyse = mcal.get_calendar('NYSE')
                    trading_dates = nyse.valid_days(start_date=start_date, end_date=end_date)
                    print(f"✅ 使用NYSE交易日历 (pandas_market_calendars)")
                    return trading_dates
                
                # 备选：使用 exchange_calendars
                elif 'xcals' in globals():
                    nyse = xcals.get_calendar('XNYS')  # NYSE的ISO代码
                    trading_dates = nyse.sessions_in_range(start_date, end_date)
                    print(f"✅ 使用NYSE交易日历 (exchange_calendars)")
                    return trading_dates
                    
            except Exception as e:
                print(f"⚠️ 美国交易日历获取失败，回退到简单工作日: {e}")
        else:
            print(f"⚠️ 未安装美国交易日历包，使用简单工作日")
            print(f"   建议安装: pip install pandas_market_calendars")
        
        # 回退到原来的简单工作日方法
        return pd.date_range(start_date, end_date, freq="B")
    
    def prefetch_all_data(self, tickers: List[str], start_date: str, end_date: str):
        """预取多日分析所需的所有数据"""
        if not self.prefetch_data:
            return
            
        print(f"\n预取数据中 ({start_date} 到 {end_date})...")
        
        # 扩展数据获取范围，确保有足够的历史数据
        end_date_dt = datetime.strptime(end_date, "%Y-%m-%d")
        extended_start_dt = end_date_dt - relativedelta(years=1)
        extended_start = extended_start_dt.strftime("%Y-%m-%d")
        
        for ticker in tickers:
            try:
                # 预取价格数据
                get_prices(ticker, extended_start, end_date)
                
                # 预取财务指标
                get_financial_metrics(ticker, end_date, limit=20)
                
                # 预取内部交易数据
                get_insider_trades(ticker, end_date, start_date=start_date, limit=1000)
                
                # 预取新闻数据
                get_company_news(ticker, end_date, start_date=start_date, limit=1000)
                
            except Exception as e:
                print(f"警告: 预取 {ticker} 数据时出错: {e}")
                
        print("数据预取完成")
    
    def save_daily_state(self, date_str: str, results: Dict[str, Any], state: Dict[str, Any]):
        """保存单日状态到文件"""
        daily_file = f"{self.base_output_dir}/{self.session_id}_daily_{date_str}.json"
        
        # 确保通信日志包含所有必要字段
        comm_logs = state.get("data", {}).get("communication_logs", {})
        complete_comm_logs = {
            "decisions": comm_logs.get("decisions", []),
            "private_chats": comm_logs.get("private_chats", []),
            "meetings": comm_logs.get("meetings", []),
            "notifications": comm_logs.get("notifications", []),
            "communication_decisions": comm_logs.get("communication_decisions", [])
        }
        
        daily_state = {
            "session_id": self.session_id,
            "date": date_str,
            "timestamp": datetime.now().isoformat(),
            "results": results,
            "analyst_memory": state.get("data", {}).get("analyst_memory"),
            "communication_logs": complete_comm_logs,
            "metadata": state.get("metadata", {}),
            "okr_state": state.get("data", {}).get("okr_state"),
            "portfolio": state.get("data", {}).get("portfolio")  # 保存投资组合状态
        }
        
        try:
            with open(daily_file, 'w', encoding='utf-8') as f:
                json.dump(daily_state, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            print(f"警告: 保存日状态失败 {date_str}: {e}")
    
    def load_previous_state(self, date_str: str) -> Optional[Dict[str, Any]]:
        """加载前一日的状态"""
        # 查找最近的状态文件
        pattern = f"{self.session_id}_daily_*.json"
        daily_files = list(Path(self.base_output_dir).glob(pattern))
        
        if not daily_files:
            return None
            
        # 按日期排序，获取最新的
        daily_files.sort(key=lambda x: x.name)
        latest_file = daily_files[-1]
        
        try:
            with open(latest_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"警告: 加载前状态失败: {e}")
            return None
    
    def restore_state_to_engine(self, previous_state: Dict[str, Any], current_state: Dict[str, Any]):
        """将前一日Portfolio状态恢复到当前引擎状态"""
        if not previous_state:
            return
        
        # 只恢复投资组合状态（Portfolio模式）
        if previous_state.get("portfolio"):
            current_state["data"]["portfolio"] = previous_state["portfolio"]
            positions_count = len([p for p in previous_state["portfolio"].get("positions", {}).values() 
                                  if p.get("long", 0) > 0 or p.get("short", 0) > 0])
            print(f"✅ 已恢复Portfolio状态 - 现金: ${previous_state['portfolio'].get('cash', 0):,.2f}, 持仓数: {positions_count}")

    def _init_okr_manager(self):
        """初始化OKR管理器"""
        if self.okr_manager is None and self.okr_enabled:
            analyst_ids = list(self.engine.core_analysts.keys())
            self.okr_manager = OKRManager(analyst_ids)
            print(f"OKR管理器已初始化，管理 {len(analyst_ids)} 个分析师")

    
    def run_multi_day_strategy(
        self,
        tickers: List[str],
        start_date: str,
        end_date: str,
        enable_communications: bool = True,
        enable_notifications: bool = True,
        show_reasoning: bool = False,
        progress_callback: Optional[Callable] = None,
        mode: str = "signal",
        **kwargs
    ) -> Dict[str, Any]:
        """
        运行多日投资策略
        
        Args:
            tickers: 股票代码列表
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            enable_communications: 是否启用沟通机制
            enable_notifications: 是否启用通知机制
            show_reasoning: 是否显示详细推理过程
            progress_callback: 进度回调函数
            mode: 运行模式 ("signal" 或 "portfolio")
            **kwargs: 其他参数
            
        Returns:
            多日分析汇总结果
        """
        
        # 初始化会话
        if self.session_id is None:
            self.session_id = self.create_session_id()
        print(f"开始多日策略分析 (会话ID: {self.session_id})")
        print(f"时间范围: {start_date} 到 {end_date}")
        print(f"分析标的: {', '.join(tickers)}")
        
        # 预取数据
        if self.prefetch_data:
            self.prefetch_all_data(tickers, start_date, end_date)
        
        # 生成美国股市交易日序列（考虑节假日）
        trading_dates = self.get_us_trading_dates(start_date, end_date)
        
        if len(trading_dates) == 0:
            raise ValueError(f"指定日期范围内无交易日: {start_date} 到 {end_date}")
        
        print(f"共 {len(trading_dates)} 个交易日待分析")
        
        # 初始化汇总统计
        total_days = len(trading_dates)
        successful_days = 0
        failed_days = 0
        self.daily_results = []
        
        # 逐日执行分析
        for i, current_date in enumerate(trading_dates):
            current_date_str = current_date.strftime("%Y-%m-%d")
            # print(f"\n{'='*60}")
            # print(f"第 {i+1}/{total_days} 日分析: {current_date_str}")
            # print(f"{'='*60}")
            
            # 发送进度更新
            if progress_callback:
                progress_callback({
                    "type": "daily_progress",
                    "current_date": current_date_str,
                    "progress": (i + 1) / total_days,
                    "day_number": i + 1,
                    "total_days": total_days
                })
            
            try:
                # 设置当日分析的时间窗口（回看30天数据）
                lookback_start = (current_date - timedelta(days=30)).strftime("%Y-%m-%d")
                
                # 创建当日分析状态
                daily_state = self.engine.create_base_state(tickers, lookback_start, current_date_str)
                daily_state["metadata"]["communication_enabled"] = enable_communications
                daily_state["metadata"]["notifications_enabled"] = enable_notifications
                daily_state["metadata"]["show_reasoning"] = show_reasoning
                daily_state["metadata"]["max_communication_cycles"] = self.max_communication_cycles
                daily_state["metadata"]["session_id"] = self.session_id
                daily_state["metadata"]["mode"] = mode
                # Portfolio模式参数
                if mode == "portfolio":
                    daily_state["metadata"]["initial_cash"] = kwargs.get("initial_cash", 100000.0)
                    daily_state["metadata"]["margin_requirement"] = kwargs.get("margin_requirement", 0.0)
                daily_state["metadata"]["trading_date"] = current_date_str
                daily_state["metadata"]["day_number"] = i + 1
                
                # 设置当日输出文件
                daily_output_file = f"{self.base_output_dir}/{self.session_id}_daily_{current_date_str}.json"
                daily_state["metadata"]["output_file"] = daily_output_file
                
                # 恢复前一日状态（如果有）
                if i > 0:
                    previous_state = self.load_previous_state(current_date_str)
                    self.restore_state_to_engine(previous_state, daily_state)
                else:
                    # 第一天：尝试加载previous state（可能是多日运行的continuation）
                    previous_state = self.load_previous_state(current_date_str)
                    
                    if previous_state:
                        # 如果有previous state，恢复它（包括portfolio、analyst_memory等）
                        print(f"🔄 检测到历史状态，正在恢复...")
                        self.restore_state_to_engine(previous_state, daily_state)
                    elif mode == "portfolio":
                        # 真正的第一天：初始化新Portfolio状态
                        initial_cash = kwargs.get("initial_cash", 100000.0)
                        margin_requirement = kwargs.get("margin_requirement", 0.0)
                        
                        if "data" not in daily_state:
                            daily_state["data"] = {}
                        
                        daily_state["data"]["portfolio"] = {
                            "cash": initial_cash,
                            "positions": {},
                            "margin_requirement": margin_requirement,
                            "margin_used": 0.0
                        }
                        print(f"已初始化投资组合 (现金: ${initial_cash:,.2f}, 保证金要求: {margin_requirement*100:.1f}%)")
                
                # OKR：在运行分析前，基于过往数据更新权重，并注入到state中
                if self.okr_enabled:
                    self._init_okr_manager()
                    
                    # 每5个交易日（i基于0）更新一次权重，使其作用于下一阶段（当前日）
                    if (i % 5) == 0 and i > 0:
                        weights = self.okr_manager.update_weights_5day_review(current_date_str)
                        print(f"OKR：更新分析师权重 {weights}")
                    
                    # 每30个交易日进行一次OKR评估与记忆重置
                    if (i % 30) == 0 and i > 0:
                        eliminated_analyst = self.okr_manager.perform_30day_okr_evaluation(current_date_str)
                        if eliminated_analyst:
                            print(f"OKR评估：淘汰并重置 {eliminated_analyst}，标记为新入职分析师")
                    
                    # 注入到state供后续提示使用
                    daily_state.setdefault("data", {})["okr_state"] = self.okr_manager.export_okr_data()
                    daily_state["data"]["analyst_weights"] = self.okr_manager.get_analyst_weights_for_prompt()
                
                # 执行当日完整分析流程
                daily_results = self.engine.run_full_analysis_with_communications(
                    tickers=tickers,
                    start_date=lookback_start,
                    end_date=current_date_str,
                    enable_communications=enable_communications,
                    enable_notifications=enable_notifications,
                    mode=mode,
                    state=daily_state
                )
                
                # OKR：记录今日信号（分数在未来日补全）
                if self.okr_enabled and self.okr_manager:
                    try:
                        # 记录今日分析师信号到OKR管理器
                        analyst_signals = daily_state.get("data", {}).get("analyst_signals", {})
                        self.okr_manager.record_daily_signals(current_date_str, analyst_signals)
                        # 将最新OKR状态保存在daily_state中，便于跨日持久化
                        daily_state["data"]["okr_state"] = self.okr_manager.export_okr_data()
                    except Exception as e:
                        print(f"警告: 记录OKR信号失败: {e}")
                
                # 保存当日状态（包括投资组合）
                self.save_daily_state(current_date_str, daily_results, daily_state)
                
                # 记录成功
                successful_days += 1
                self.daily_results.append({
                    "date": current_date_str,
                    "status": "success",
                    "results": daily_results,
                    "output_file": daily_output_file
                })
                
                print(f"{current_date_str} 分析完成")
                
                # 发送单日结果
                if progress_callback:
                    progress_callback({
                        "type": "daily_result",
                        "date": current_date_str,
                        "status": "success",
                        "data": daily_results
                    })
                
            except Exception as e:
                import traceback
                error_msg = str(e)
                full_traceback = traceback.format_exc()
                
                # 检查是否是JSON序列化相关错误
                is_json_error = ("JSON" in error_msg and "serializable" in error_msg) or \
                               ("Object of type" in error_msg and "is not JSON serializable" in error_msg)
                
                if is_json_error:
                    # JSON序列化错误应该已经被我们的修复处理了，如果还出现说明有遗漏
                    print(f"警告: {current_date_str} 发现未处理的JSON序列化问题:")
                    print(f"   错误: {error_msg}")
                    print("   建议检查是否有遗漏的json.dumps调用需要替换为quiet_json_dumps")
                else:
                    # 其他真正的业务逻辑错误
                    print(f"错误: {current_date_str} 分析失败: {error_msg}")
                
                failed_days += 1
                self.daily_results.append({
                    "date": current_date_str,
                    "status": "failed",
                    "error": error_msg,
                    "full_traceback": full_traceback,
                    "output_file": None
                })
                
                # 发送失败通知
                if progress_callback:
                    progress_callback({
                        "type": "daily_result",
                        "date": current_date_str,
                        "status": "failed",
                        "error": str(e)
                    })
                
                # 严重错误时可选择停止
                # continue  # 继续下一日
        
        # 生成多日汇总报告
        summary_results = self.generate_multi_day_summary()
        
        print(f"\n多日策略分析完成!")
        print(f"成功: {successful_days} 日")
        print(f"失败: {failed_days} 日")
        print(f"成功率: {successful_days/total_days*100:.1f}%")
        
        return summary_results
    
    def generate_multi_day_summary(self) -> Dict[str, Any]:
        """生成多日汇总报告"""
        summary_file = f"{self.base_output_dir}/{self.session_id}_summary.json"
        
        # 计算汇总统计
        successful_results = [r for r in self.daily_results if r["status"] == "success"]
        
        # 提取关键指标时间序列
        portfolio_values = []
        communication_stats = []
        
        for daily_result in successful_results:
            date = daily_result["date"]
            results = daily_result.get("results", {})
            
            # 投资组合价值变化
            if "portfolio_management_results" in results:
                pm_results = results["portfolio_management_results"]
                portfolio_values.append({
                    "date": date,
                    "total_value": pm_results.get("portfolio_summary", {}).get("total_value", 0),
                    "cash": pm_results.get("portfolio_summary", {}).get("cash", 0),
                    "positions_value": pm_results.get("portfolio_summary", {}).get("positions_value", 0)
                })
            
            # 沟通统计
            if "communication_logs" in results:
                comm_logs = results["communication_logs"]
                communication_stats.append({
                    "date": date,
                    "decisions_count": len(comm_logs.get("decisions", [])),
                    "private_chats_count": len(comm_logs.get("private_chats", [])),
                    "meetings_count": len(comm_logs.get("meetings", [])),
                    "notifications_count": len(comm_logs.get("notifications", []))
                })
        
        # 获取股票列表（从第一个成功的结果中提取）
        tickers = []
        for daily_result in successful_results:
            results = daily_result.get("results", {})
            portfolio_results = results.get("portfolio_management_results", {})
            if "final_decisions" in portfolio_results:
                tickers = list(portfolio_results["final_decisions"].keys())
                break
        # pdb.set_trace()
        # 生成汇总结果
        summary = {
            "session_id": self.session_id,
            "summary_timestamp": datetime.now().isoformat(),
            "period": {
                "start_date": self.daily_results[0]["date"] if self.daily_results else None,
                "end_date": self.daily_results[-1]["date"] if self.daily_results else None,
                "total_days": len(self.daily_results),
                "successful_days": len(successful_results),
                "failed_days": len([r for r in self.daily_results if r["status"] == "failed"])
            },
            "daily_results": self.daily_results,
            "time_series": {
                "portfolio_values": portfolio_values,
                "communication_stats": communication_stats
            },
            "performance_analysis": {
                "individual_stocks": self.calculate_individual_stock_performance(successful_results, tickers) if tickers else {}
            }
        }
        
        # 保存汇总文件
        try:
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, indent=2, default=str)
            print(f"多日汇总报告已保存: {summary_file}")
        except Exception as e:
            print(f"警告: 保存汇总报告失败: {e}")
        
        return summary
    
    def calculate_performance_metrics(self, portfolio_values: List[Dict[str, Any]]) -> Dict[str, Any]:
        """计算多日绩效指标 - 基于简化的日收益率方法"""
        if len(portfolio_values) < 2:
            return {"error": "数据不足，无法计算绩效指标"}
        
        try:
            # 转换为DataFrame便于计算
            df = pd.DataFrame(portfolio_values)
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date').sort_index()
            
            # 简化计算：直接使用日收益率
            # 假设每日决策都是基于单位资产，收益率直接等于价格变化率
            df['daily_return'] = df['total_value'].pct_change()
            df['cumulative_return'] = (1 + df['daily_return']).cumprod() - 1
            
            # 基础指标
            total_return = df['cumulative_return'].iloc[-1] * 100  # 转换为百分比
            mean_daily_return = df['daily_return'].mean()
            volatility = df['daily_return'].std() * (252 ** 0.5) * 100  # 年化波动率
            
            # 年化收益率（基于日均收益率）
            annualized_return = mean_daily_return * 252 * 100
            
            # 最大回撤（基于累计收益率）
            cumulative_returns = (1 + df['daily_return']).cumprod()
            rolling_max = cumulative_returns.cummax()
            drawdown = (cumulative_returns - rolling_max) / rolling_max * 100
            max_drawdown = drawdown.min()
            
            # 夏普比率（假设无风险利率4%）
            excess_returns = df['daily_return'] - 0.04/252
            sharpe_ratio = excess_returns.mean() / excess_returns.std() * (252 ** 0.5) if excess_returns.std() > 0 else 0
            
            # 计算交易期间
            trading_days = len(df)
            trading_period_years = trading_days / 252  # 252个交易日为一年
            
            return {
                "total_return_pct": round(total_return, 2),
                "annualized_return_pct": round(annualized_return, 2),
                "annualized_volatility_pct": round(volatility, 2),
                "max_drawdown_pct": round(max_drawdown, 2),
                "sharpe_ratio": round(sharpe_ratio, 3),
                "total_trading_days": trading_days,
                "trading_period_years": round(trading_period_years, 2),
                "mean_daily_return_pct": round(mean_daily_return * 100, 4),  # 新增：日均收益率
                "start_value": df['total_value'].iloc[0],
                "end_value": df['total_value'].iloc[-1]
            }
            
        except Exception as e:
            return {"error": f"绩效计算失败: {str(e)}"}
    
    def calculate_individual_stock_performance(self, daily_results: List[Dict[str, Any]], tickers: List[str]) -> Dict[str, Dict[str, Any]]:
        """计算每只股票的单独绩效指标（基于方向信号）"""
        stock_performance = {}
        
        for ticker in tickers:
            # 收集该股票的每日决策和收益数据
            daily_decisions = []
            daily_returns = []
            
            for daily_result in daily_results:
                if daily_result["status"] != "success":
                    continue
                    
                results = daily_result.get("results", {})
                portfolio_results = results.get("portfolio_management_results", {})
                
                # 从最终决策中提取方向信号
                final_decisions = portfolio_results.get("final_decisions", {})
                if ticker in final_decisions:
                    decision = final_decisions[ticker]
                    action = decision.get("action", "hold")
                    confidence = decision.get("confidence", 0)
                    
                    daily_decisions.append({
                        "date": daily_result["date"],
                        "action": action,
                        "confidence": confidence
                    })
                    
                    # 基于方向信号计算日收益率
                    daily_return,real_return,close_price = self._calculate_stock_daily_return_from_signal(
                        ticker, daily_result["date"], action
                    )
                    daily_returns.append(daily_return)
            
            if len(daily_returns) > 1:
                # 计算该股票的绩效指标
                returns_series = pd.Series(daily_returns)
                # pdb.set_trace()
                # 计算累计收益率
                cumulative_returns = (1 + returns_series).cumprod()
                total_return = cumulative_returns.iloc[-1] - 1
                
                # 计算最大回撤
                rolling_max = cumulative_returns.cummax()
                drawdowns = (cumulative_returns - rolling_max) / rolling_max
                max_drawdown = drawdowns.min()
                
                # 计算夏普比率（假设无风险利率4%）
                excess_returns = returns_series - 0.04/252
                sharpe_ratio = excess_returns.mean() / excess_returns.std() * (252 ** 0.5) if excess_returns.std() > 0 else 0
                
                stock_performance[ticker] = {
                    "total_return_pct": round(total_return * 100, 4),
                    "mean_daily_return_pct": round(returns_series.mean() * 100, 4),
                    "annualized_return_pct": round(returns_series.mean() * 252 * 100, 2),
                    "volatility_pct": round(returns_series.std() * (252 ** 0.5) * 100, 2),
                    "sharpe_ratio": round(sharpe_ratio, 3),
                    "max_drawdown_pct": round(max_drawdown * 100, 2),
                    "total_decisions": len(daily_decisions),
                    "long_decisions": len([d for d in daily_decisions if d["action"] == "long"]),
                    "short_decisions": len([d for d in daily_decisions if d["action"] == "short"]),
                    "hold_decisions": len([d for d in daily_decisions if d["action"] == "hold"]),
                    "avg_confidence": round(sum(d["confidence"] for d in daily_decisions) / len(daily_decisions), 2) if daily_decisions else 0,
                    "win_rate": round(len([r for r in daily_returns if r > 0]) / len(daily_returns) * 100, 2),
                    "trading_days": len(daily_returns)
                }
            else:
                stock_performance[ticker] = {
                    "error": "数据不足，无法计算该股票绩效指标"
                }
        
        
        return stock_performance
    
    def _calculate_stock_daily_return_from_signal(self, ticker: str, date, action: str) -> float:
        """基于方向信号计算单只股票的日收益率
        
        Args:
            ticker: 股票代码
            date: 日期，可以是字符串 (YYYY-MM-DD) 或 datetime.date 对象
            action: 交易动作 ('long', 'short', 'hold')
        """
        # 获取该股票的价格数据（获取更大范围以确保有足够数据计算收益率）
        from datetime import datetime, timedelta
        import datetime as dt
        
        # 处理日期参数，确保转换为 date 对象
        if isinstance(date, str):
            target_date = pd.to_datetime(date).date()
        elif isinstance(date, dt.date):
            target_date = date
        elif isinstance(date, dt.datetime):
            target_date = date.date()
        
        # 使用相对路径获取数据文件
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 获取IA/src目录
        data_path = os.path.join(current_dir, 'data', 'ret_data', f'{ticker}.csv')
        
        if not os.path.exists(data_path):
            print(f"警告: 数据文件不存在 {data_path}，使用模拟收益率")
            return self._fallback_simulated_return(ticker, str(target_date), action)
            
        prices_df = pd.read_csv(data_path)
        
        if prices_df.empty:
            print(f"警告: 无法获取 {ticker} 在 {target_date} 的价格数据，使用模拟收益率")
            return self._fallback_simulated_return(ticker, str(target_date), action)
        
        # 计算日收益率
        # prices_df['ret'] = prices_df['close'].pct_change()
        
        # 查找指定日期的收益率
        prices_df.index = pd.to_datetime(prices_df['time']).dt.date
        # pdb.set_trace()
        # 找到最接近目标日期的收益率
        market_return = prices_df.loc[target_date, 'ret']
        price = prices_df.loc[target_date, 'close']
        
        # 根据交易方向计算最终收益率
        if action == "long":
            return float(market_return), float(market_return), float(price) # 做多：获得市场收益率
        elif action == "short":
            return float(-market_return) ,float(market_return),float(price) # 做空：获得市场收益率的相反收益
        else:  # hold
            return 0.0,float(market_return), float(price)# 持有：无收益
                
   
    

