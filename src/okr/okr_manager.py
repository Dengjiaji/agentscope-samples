#!/usr/bin/env python3
"""
OKR管理器 - 实现分析师声誉评分和淘汰机制
每5个交易日复盘一次，每30个交易日进行OKR评估和人员调整
"""

import json
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path

from src.tools.data_tools import get_price_data
from src.communication.analyst_memory_mem0 import memory_manager_mem0_adapter as memory_manager

class OKRManager:
    """OKR管理器 - 处理分析师绩效评估和淘汰机制"""
    
    def __init__(self, analyst_ids: List[str]):
        """
        初始化OKR管理器
        
        Args:
            analyst_ids: 分析师ID列表
        """
        self.analyst_ids = analyst_ids.copy()
        
        # 初始化权重（平均分配）
        equal_weight = 1.0 / len(analyst_ids) if analyst_ids else 0.0
        self.current_weights = {aid: equal_weight for aid in analyst_ids}
        
        # 历史数据
        self.weight_history = []  # 权重历史快照
        self.signal_history = []  # 投资信号历史
        self.performance_history = []  # 绩效历史
        
        # 新员工追踪
        self.new_hires = {}  # {analyst_id: hire_date}
        
        # 配置参数
        self.review_interval = 5  # 每5个交易日复盘一次
        self.okr_interval = 30   # 每30个交易日进行OKR评估
        
        print(f"OKR管理器初始化完成，管理 {len(analyst_ids)} 个分析师")
    
    def record_daily_signals(self, date: str, analyst_signals: Dict[str, Any]) -> None:
        """
        记录当日分析师信号
        
        Args:
            date: 日期字符串 (YYYY-MM-DD)
            analyst_signals: 分析师信号字典
        """
        for analyst_id in self.analyst_ids:
            # 优先选择第二轮信号，否则使用第一轮信号
            round2_key = f"{analyst_id}_round2"
            signals_data = None
            
            if round2_key in analyst_signals:
                signals_data = analyst_signals[round2_key]
                round_type = "round2"
            elif analyst_id in analyst_signals:
                signals_data = analyst_signals[analyst_id]
                round_type = "round1"
            else:
                continue
            
            # 解析信号数据
            ticker_signals = []
            if isinstance(signals_data, dict):
                if "ticker_signals" in signals_data:
                    # 标准格式
                    ticker_signals = signals_data.get("ticker_signals", [])
                else:
                    # 旧格式：{ticker: {signal: ...}}
                    for ticker, signal_data in signals_data.items():
                        if isinstance(signal_data, dict) and "signal" in signal_data:
                            ticker_signals.append({
                                "ticker": ticker,
                                "signal": signal_data.get("signal"),
                                "confidence": signal_data.get("confidence", 50),
                                "reasoning": signal_data.get("reasoning", "")
                            })
            
            # 记录每个股票信号
            for ticker_signal in ticker_signals:
                if isinstance(ticker_signal, dict) and ticker_signal.get("ticker"):
                    self.signal_history.append({
                        "date": date,
                        "analyst_id": analyst_id,
                        "ticker": ticker_signal.get("ticker"),
                        "signal": ticker_signal.get("signal"),
                        "confidence": ticker_signal.get("confidence", 50),
                        "reasoning": ticker_signal.get("reasoning", ""),
                        "round_type": round_type,
                        "score": None  # 将在后续评分时填入
                    })
    
    def score_signals_for_period(self, end_date: str, days_back: int = 5) -> None:
        """
        为指定期间的信号打分
        
        Args:
            end_date: 结束日期
            days_back: 回看天数
        """
        end_dt = pd.to_datetime(end_date)
        start_dt = end_dt - pd.Timedelta(days=days_back + 10)  # 多留一些天数确保覆盖
        
        # 找到需要评分的信号
        signals_to_score = []
        for signal_record in self.signal_history:
            if (signal_record["score"] is None and 
                signal_record["date"] <= end_date and
                pd.to_datetime(signal_record["date"]) >= start_dt):
                signals_to_score.append(signal_record)
        
        print(f"正在为 {len(signals_to_score)} 个信号进行评分...")
        
        # 为每个信号计算分数
        for signal_record in signals_to_score:
            score = self._calculate_signal_score(
                signal_record["ticker"], 
                signal_record["date"], 
                signal_record["signal"]
            )
            signal_record["score"] = score
            
            if score is not None:
                signal_emoji = {1: "✅", 0: "➖", -1: "❌"}
                emoji = signal_emoji.get(score, "❓")
                print(f"  {emoji} {signal_record['analyst_id']}: {signal_record['ticker']} "
                      f"({signal_record['signal']}) = {score}分")
    
    def _calculate_signal_score(self, ticker: str, signal_date: str, signal: str) -> Optional[int]:
        """
        计算单个信号的分数
        
        Args:
            ticker: 股票代码
            signal_date: 信号日期
            signal: 信号类型 (bullish/bearish/neutral)
            
        Returns:
            分数: +1 (正确), 0 (中性), -1 (错误), None (无法评分)
        """
        try:
            # 获取价格数据
            start_dt = pd.to_datetime(signal_date)
            end_dt = start_dt + pd.Timedelta(days=7)  # 向后看7天找下一个交易日
            
            df = get_price_data(ticker, start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d"))
            if df is None or df.empty:
                return None
            
            df = df.sort_index()
            dates = df.index.strftime("%Y-%m-%d").tolist()
            
            if signal_date not in dates:
                return None
            
            # 找到信号日期的索引
            signal_idx = dates.index(signal_date)
            if signal_idx + 1 >= len(dates):
                return None  # 没有下一个交易日数据
            
            # 计算价格变化方向
            today_close = float(df.iloc[signal_idx]["close"])
            next_close = float(df.iloc[signal_idx + 1]["close"])
            
            # 确定实际价格方向
            if next_close > today_close:
                actual_direction = "bullish"
            elif next_close < today_close:
                actual_direction = "bearish"
            else:
                actual_direction = "neutral"
            
            # 计算分数
            signal_lower = (signal or "").lower()
            if signal_lower == "neutral" or actual_direction == "neutral":
                return 0
            elif signal_lower == actual_direction:
                return 1
            else:
                return -1
                
        except Exception as e:
            print(f"警告: 计算信号分数失败 {ticker} {signal_date}: {e}")
            return None
    
    def update_weights_5day_review(self, current_date: str) -> Dict[str, float]:
        """
        基于最近5个交易日的表现更新权重
        
        Args:
            current_date: 当前日期
            
        Returns:
            更新后的权重字典
        """
        print(f"\n📊 执行5日绩效复盘 ({current_date})")
        
        # 先为最近的信号评分
        self.score_signals_for_period(current_date, days_back=7)
        
        # 获取最近5个交易日的评分数据
        end_dt = pd.to_datetime(current_date)
        start_dt = end_dt - pd.Timedelta(days=10)  # 多留几天确保覆盖
        
        analyst_scores = {}
        analyst_counts = {}
        
        for analyst_id in self.analyst_ids:
            scores = []
            for signal_record in self.signal_history:
                if (signal_record["analyst_id"] == analyst_id and
                    signal_record["score"] is not None and
                    pd.to_datetime(signal_record["date"]) >= start_dt and
                    signal_record["date"] <= current_date):
                    scores.append(signal_record["score"])
            
            if scores:
                analyst_scores[analyst_id] = sum(scores) / len(scores)  # 平均分
                analyst_counts[analyst_id] = len(scores)
            else:
                analyst_scores[analyst_id] = 0.0
                analyst_counts[analyst_id] = 0
        
        # 计算新权重 (将[-1,1]范围映射到[0,2]，然后归一化)
        shifted_scores = {}
        for analyst_id in self.analyst_ids:
            shifted_scores[analyst_id] = analyst_scores[analyst_id] + 1.0
        
        total_shifted = sum(shifted_scores.values())
        if total_shifted > 1e-8:
            new_weights = {aid: shifted_scores[aid] / total_shifted for aid in self.analyst_ids}
        else:
            # 如果所有分数都是-1，平均分配权重
            equal_weight = 1.0 / len(self.analyst_ids)
            new_weights = {aid: equal_weight for aid in self.analyst_ids}
        
        # 更新权重
        self.current_weights = new_weights
        
        # 记录权重历史
        self.weight_history.append({
            "date": current_date,
            "weights": new_weights.copy(),
            "scores": analyst_scores.copy(),
            "counts": analyst_counts.copy(),
            "type": "5day_review"
        })
        
        # 打印结果
        print("📈 分析师权重更新结果:")
        for analyst_id in self.analyst_ids:
            score = analyst_scores[analyst_id]
            weight = new_weights[analyst_id]
            count = analyst_counts[analyst_id]
            print(f"  {analyst_id}: 平均分 {score:.2f} ({count}个信号) → 权重 {weight:.3f}")
        
        return new_weights
    
    def perform_30day_okr_evaluation(self, current_date: str) -> Optional[str]:
        """
        执行30日OKR评估，淘汰表现最差的分析师
        
        Args:
            current_date: 当前日期
            
        Returns:
            被淘汰的分析师ID，如果没有淘汰则返回None
        """
        print(f"\n🎯 执行30日OKR评估 ({current_date})")
        
        # 需要至少4个权重快照才能进行评估
        review_snapshots = [h for h in self.weight_history if h["type"] == "5day_review"]
        if len(review_snapshots) < 4:
            print(f"权重快照不足 ({len(review_snapshots)}/4)，跳过OKR评估")
            return None
        
        # 计算最近4次权重的平均值
        last_4_snapshots = review_snapshots[-4:]
        avg_weights = {}
        
        for analyst_id in self.analyst_ids:
            weights = []
            for snapshot in last_4_snapshots:
                if analyst_id in snapshot["weights"]:
                    weights.append(snapshot["weights"][analyst_id])
            
            if weights:
                avg_weights[analyst_id] = sum(weights) / len(weights)
            else:
                avg_weights[analyst_id] = 0.0
        
        # 找到平均权重最低的分析师
        worst_analyst = min(self.analyst_ids, key=lambda x: avg_weights.get(x, 0.0))
        worst_weight = avg_weights[worst_analyst]
        
        print("📊 最近4周平均权重:")
        for analyst_id in sorted(self.analyst_ids, key=lambda x: avg_weights.get(x, 0.0), reverse=True):
            weight = avg_weights[analyst_id]
            status = " (将被淘汰)" if analyst_id == worst_analyst else ""
            print(f"  {analyst_id}: {weight:.3f}{status}")
        
        # 执行淘汰和重置
        try:
            # 重置分析师记忆
            memory_manager.reset_analyst_memory(worst_analyst)
            
            # 记录新入职
            self.new_hires[worst_analyst] = current_date
            
            # 重置该分析师的权重为平均值
            equal_weight = 1.0 / len(self.analyst_ids)
            self.current_weights[worst_analyst] = equal_weight
            
            print(f"🔄 已淘汰并重置分析师: {worst_analyst}")
            print(f"📝 标记为新入职员工，入职日期: {current_date}")
            
            # 记录OKR评估历史
            self.performance_history.append({
                "date": current_date,
                "type": "30day_okr_evaluation",
                "eliminated_analyst": worst_analyst,
                "elimination_reason": f"30日平均权重最低 ({worst_weight:.3f})",
                "avg_weights": avg_weights.copy(),
                "snapshots_used": len(last_4_snapshots)
            })
            
            return worst_analyst
            
        except Exception as e:
            print(f"❌ 淘汰分析师时出错: {e}")
            return None
    
    def get_analyst_weights_for_prompt(self) -> Dict[str, float]:
        """
        获取用于提示词的分析师权重信息
        
        Returns:
            当前权重字典
        """
        return self.current_weights.copy()
    
    def format_weights_for_prompt(self) -> str:
        """
        格式化权重信息用于基金经理提示词
        
        Returns:
            格式化的权重信息字符串
        """
        if not self.current_weights:
            return "所有分析师权重相等。"
        
        lines = ["📊 分析师权重分配 (基于最近绩效):"]
        
        # 按权重排序
        sorted_analysts = sorted(self.current_weights.items(), key=lambda x: x[1], reverse=True)
        
        for analyst_id, weight in sorted_analysts:
            # 检查是否是新员工
            new_hire_info = ""
            if analyst_id in self.new_hires:
                days_since_hire = (pd.to_datetime(datetime.now().date()) - 
                                 pd.to_datetime(self.new_hires[analyst_id])).days
                if days_since_hire <= 30:
                    new_hire_info = f" (新员工，入职{days_since_hire}天)"
            
            # 权重条形图
            bar_length = int(weight * 20)  # 最大20个字符
            bar = "█" * bar_length + "░" * (20 - bar_length)
            
            lines.append(f"  {analyst_id}: {weight:.3f} {bar}{new_hire_info}")
        
        lines.append("")
        lines.append("💡 权重越高的分析师建议应给予更多考虑。")
        
        return "\n".join(lines)
    
    def get_okr_summary(self) -> Dict[str, Any]:
        """
        获取OKR系统运行摘要
        
        Returns:
            OKR摘要信息
        """
        # 统计信号数量
        total_signals = len(self.signal_history)
        scored_signals = len([s for s in self.signal_history if s["score"] is not None])
        
        # 统计各分析师表现
        analyst_stats = {}
        for analyst_id in self.analyst_ids:
            analyst_signals = [s for s in self.signal_history if s["analyst_id"] == analyst_id and s["score"] is not None]
            if analyst_signals:
                scores = [s["score"] for s in analyst_signals]
                analyst_stats[analyst_id] = {
                    "total_signals": len(analyst_signals),
                    "avg_score": sum(scores) / len(scores),
                    "correct_signals": len([s for s in scores if s == 1]),
                    "neutral_signals": len([s for s in scores if s == 0]),
                    "wrong_signals": len([s for s in scores if s == -1]),
                    "current_weight": self.current_weights.get(analyst_id, 0.0),
                    "is_new_hire": analyst_id in self.new_hires
                }
            else:
                analyst_stats[analyst_id] = {
                    "total_signals": 0,
                    "avg_score": 0.0,
                    "correct_signals": 0,
                    "neutral_signals": 0,
                    "wrong_signals": 0,
                    "current_weight": self.current_weights.get(analyst_id, 0.0),
                    "is_new_hire": analyst_id in self.new_hires
                }
        
        return {
            "total_analysts": len(self.analyst_ids),
            "total_signals": total_signals,
            "scored_signals": scored_signals,
            "weight_updates": len([h for h in self.weight_history if h["type"] == "5day_review"]),
            "okr_evaluations": len(self.performance_history),
            "new_hires": len(self.new_hires),
            "analyst_stats": analyst_stats,
            "current_weights": self.current_weights.copy()
        }
    
    def export_okr_data(self) -> Dict[str, Any]:
        """
        导出完整的OKR数据
        
        Returns:
            完整的OKR数据字典
        """
        return {
            "analyst_ids": self.analyst_ids.copy(),
            "current_weights": self.current_weights.copy(),
            "weight_history": self.weight_history.copy(),
            "signal_history": self.signal_history.copy(),
            "performance_history": self.performance_history.copy(),
            "new_hires": self.new_hires.copy(),
            "config": {
                "review_interval": self.review_interval,
                "okr_interval": self.okr_interval
            },
            "export_timestamp": datetime.now().isoformat()
        }
    
    def import_okr_data(self, data: Dict[str, Any]) -> None:
        """
        导入OKR数据（用于恢复状态）
        
        Args:
            data: 从export_okr_data导出的数据
        """
        self.analyst_ids = data.get("analyst_ids", [])
        self.current_weights = data.get("current_weights", {})
        self.weight_history = data.get("weight_history", [])
        self.signal_history = data.get("signal_history", [])
        self.performance_history = data.get("performance_history", [])
        self.new_hires = data.get("new_hires", {})
        
        # 导入配置
        config = data.get("config", {})
        self.review_interval = config.get("review_interval", 5)
        self.okr_interval = config.get("okr_interval", 30)
        
        print(f"OKR数据导入完成: {len(self.analyst_ids)}个分析师, "
              f"{len(self.signal_history)}个信号记录")
