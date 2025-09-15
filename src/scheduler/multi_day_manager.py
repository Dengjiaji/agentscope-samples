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

from src.tools.api import (
    get_price_data,
    get_prices,
    get_financial_metrics,
    get_insider_trades,
    get_company_news,
)


class MultiDayManager:
    """多日投资策略管理器"""
    
    def __init__(
        self,
        engine,  # AdvancedInvestmentAnalysisEngine实例
        base_output_dir: str = "/root/wuyue.wy/Project/IA/analysis_results_logs/",
        max_communication_cycles: int = 3,
        prefetch_data: bool = True
    ):
        """
        初始化多日管理器
        
        Args:
            engine: 投资分析引擎实例
            base_output_dir: 基础输出目录
            max_communication_cycles: 每日最大沟通轮数
            prefetch_data: 是否预取数据
        """
        self.engine = engine
        self.base_output_dir = base_output_dir
        self.max_communication_cycles = max_communication_cycles
        self.prefetch_data = prefetch_data
        
        # 状态追踪
        self.session_id = None
        self.daily_results = []
        self.analyst_memory_state = None
        self.communication_logs_state = None
        self.portfolio_state = None
        
        # 确保输出目录存在
        os.makedirs(base_output_dir, exist_ok=True)
    
    def create_session_id(self) -> str:
        """生成会话ID"""
        return f"multi_day_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
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
            "portfolio_snapshot": state.get("data", {}).get("portfolio"),
            "metadata": state.get("metadata", {})
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
        """将前一日状态恢复到当前引擎状态"""
        if not previous_state:
            return
            
        # 恢复分析师记忆
        if previous_state.get("analyst_memory"):
            current_state["data"]["analyst_memory"] = previous_state["analyst_memory"]
        
        # 恢复沟通日志（继承历史决策上下文）
        if previous_state.get("communication_logs"):
            # 保留历史沟通记录作为上下文，确保所有必要字段都存在
            current_state["data"]["communication_logs"] = {
                "decisions": previous_state["communication_logs"].get("decisions", []),
                "private_chats": previous_state["communication_logs"].get("private_chats", []),
                "meetings": previous_state["communication_logs"].get("meetings", []),
                "notifications": previous_state["communication_logs"].get("notifications", []),
                "communication_decisions": previous_state["communication_logs"].get("communication_decisions", [])
            }
        else:
            # 如果没有历史记录，确保创建完整的通信日志结构
            if "communication_logs" not in current_state["data"]:
                current_state["data"]["communication_logs"] = {}
            
            # 确保所有必要的子字段都存在
            comm_logs = current_state["data"]["communication_logs"]
            if "decisions" not in comm_logs:
                comm_logs["decisions"] = []
            if "private_chats" not in comm_logs:
                comm_logs["private_chats"] = []
            if "meetings" not in comm_logs:
                comm_logs["meetings"] = []
            if "notifications" not in comm_logs:
                comm_logs["notifications"] = []
            if "communication_decisions" not in comm_logs:
                comm_logs["communication_decisions"] = []
        
        # 恢复投资组合状态（关键：保持仓位连续性）
        if previous_state.get("portfolio_snapshot"):
            current_state["data"]["portfolio"] = previous_state["portfolio_snapshot"]
            
        print(f"已恢复前一交易日状态")
    
    def run_multi_day_strategy(
        self,
        tickers: List[str],
        start_date: str,
        end_date: str,
        enable_communications: bool = True,
        enable_notifications: bool = True,
        show_reasoning: bool = False,
        progress_callback: Optional[Callable] = None
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
            
        Returns:
            多日分析汇总结果
        """
        
        # 初始化会话
        self.session_id = self.create_session_id()
        print(f"开始多日策略分析 (会话ID: {self.session_id})")
        print(f"时间范围: {start_date} 到 {end_date}")
        print(f"分析标的: {', '.join(tickers)}")
        
        # 预取数据
        if self.prefetch_data:
            self.prefetch_all_data(tickers, start_date, end_date)
        
        # 生成交易日序列（跳过周末）
        trading_dates = pd.date_range(start_date, end_date, freq="B")
        
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
            print(f"\n{'='*60}")
            print(f"第 {i+1}/{total_days} 日分析: {current_date_str}")
            print(f"{'='*60}")
            
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
                daily_state["metadata"]["trading_date"] = current_date_str
                daily_state["metadata"]["day_number"] = i + 1
                
                # 设置当日输出文件
                daily_output_file = f"{self.base_output_dir}/{self.session_id}_daily_{current_date_str}.json"
                daily_state["metadata"]["output_file"] = daily_output_file
                
                # 恢复前一日状态（如果有）
                if i > 0:
                    previous_state = self.load_previous_state(current_date_str)
                    self.restore_state_to_engine(previous_state, daily_state)
                
                # 执行当日完整分析流程 
                daily_results = self.engine.run_full_analysis_with_communications(
                    tickers=tickers,
                    start_date=lookback_start,
                    end_date=current_date_str,
                    enable_communications=enable_communications,
                    enable_notifications=enable_notifications,
                    state=daily_state
                )
                
                # 保存当日状态
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
            "performance_analysis": self.calculate_performance_metrics(portfolio_values)
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
        """计算多日绩效指标"""
        if len(portfolio_values) < 2:
            return {"error": "数据不足，无法计算绩效指标"}
        
        try:
            # 转换为DataFrame便于计算
            df = pd.DataFrame(portfolio_values)
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date').sort_index()
            
            # 计算收益率
            df['daily_return'] = df['total_value'].pct_change()
            df['cumulative_return'] = (df['total_value'] / df['total_value'].iloc[0] - 1) * 100
            
            # 基础指标
            total_return = df['cumulative_return'].iloc[-1]
            volatility = df['daily_return'].std() * (252 ** 0.5) * 100  # 年化波动率
            
            # 计算年化收益率（与夏普比率计算方式一致）
            # 使用日收益率的均值乘以252个交易日
            annualized_return = df['daily_return'].mean() * 252 * 100  # 转换为百分比
            
            # 最大回撤
            rolling_max = df['total_value'].cummax()
            drawdown = (df['total_value'] - rolling_max) / rolling_max * 100
            max_drawdown = drawdown.min()
            
            # 夏普比率（假设无风险利率4%）
            excess_returns = df['daily_return'] - 0.04/252
            sharpe_ratio = excess_returns.mean() / excess_returns.std() * (252 ** 0.5) if excess_returns.std() > 0 else 0
            
            # 计算交易期间年数
            trading_days = len(df)
            trading_period_years = trading_days / 252  # 252个交易日为一年
            
            return {
                "total_return_pct": round(total_return, 2),  # 保留总收益率供参考
                "annualized_return_pct": round(annualized_return, 2),  # 年化收益率（基于日均收益率）
                "annualized_volatility_pct": round(volatility, 2),
                "max_drawdown_pct": round(max_drawdown, 2),
                "sharpe_ratio": round(sharpe_ratio, 3),
                "total_trading_days": trading_days,
                "trading_period_years": round(trading_period_years, 2),  # 交易期间年数
                "start_value": df['total_value'].iloc[0],
                "end_value": df['total_value'].iloc[-1]
            }
            
        except Exception as e:
            return {"error": f"绩效计算失败: {str(e)}"}
