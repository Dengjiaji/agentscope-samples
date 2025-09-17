"""
交易执行引擎 - 简化版本，只记录方向信号决策
基于单位资产的方向信号，不涉及复杂的资金和持仓计算
"""

from typing import Dict, Any, List, Tuple
import json
from datetime import datetime


class DirectionSignalRecorder:
    """方向信号记录器，记录每日的投资方向决策"""
    
    def __init__(self):
        """初始化方向信号记录器"""
        self.signal_log = []  # 记录所有方向信号历史
    
    def record_direction_signals(
        self, 
        decisions: Dict[str, Dict[str, Any]], 
        current_date: str = None
    ) -> Dict[str, Any]:
        """
        记录Portfolio Manager的方向信号决策
        
        Args:
            decisions: PM的方向决策 {ticker: {action, confidence, reasoning}}
            current_date: 当前日期
            
        Returns:
            信号记录报告
        """
        if current_date is None:
            current_date = datetime.now().strftime("%Y-%m-%d")
            
        signal_report = {
            "recorded_signals": {},
            "date": current_date,
            "timestamp": datetime.now().isoformat(),
            "total_signals": len(decisions)
        }
        
        print(f"\n📊 记录 {current_date} 的方向信号决策...")
        
        # 记录每个ticker的方向信号
        for ticker, decision in decisions.items():
            action = decision.get("action", "hold")
            confidence = decision.get("confidence", 0)
            reasoning = decision.get("reasoning", "")
            
            # 记录信号
            signal_record = {
                "ticker": ticker,
                "action": action,
                "confidence": confidence,
                "reasoning": reasoning,
                "date": current_date,
                "timestamp": datetime.now().isoformat()
            }
            
            self.signal_log.append(signal_record)
            signal_report["recorded_signals"][ticker] = {
                "action": action,
                "confidence": confidence
            }
            
            # 显示信号
            action_emoji = {"long": "📈", "short": "📉", "hold": "➖"}
            emoji = action_emoji.get(action, "❓")
            print(f"   {emoji} {ticker}: {action.upper()} (置信度: {confidence}%) - {reasoning}")
        
        print(f"\n✅ 已记录 {len(decisions)} 个股票的方向信号")
        
        return signal_report
    
    def get_signal_summary(self) -> Dict[str, Any]:
        """获取信号记录摘要"""
        return {
            "total_signals": len(self.signal_log),
            "signal_log": self.signal_log
        }
    


def parse_pm_decisions(pm_output: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    解析Portfolio Manager的输出格式
    
    Args:
        pm_output: PM的原始输出
        
    Returns:
        标准化的决策格式
    """
    if isinstance(pm_output, dict) and "decisions" in pm_output:
        return pm_output["decisions"]
    elif isinstance(pm_output, dict):
        # 如果直接是决策字典
        return pm_output
    else:
        print(f"警告: 无法解析PM输出格式: {type(pm_output)}")
        return {}


def execute_trading_decisions(
    pm_decisions: Dict[str, Any], 
    current_date: str = None
) -> Dict[str, Any]:
    """
    记录方向信号决策的便捷函数（简化版本）
    
    Args:
        pm_decisions: PM的方向决策
        current_date: 当前日期（可选）
        
    Returns:
        信号记录报告
    """
    # 解析PM决策
    decisions = parse_pm_decisions(pm_decisions)
    
    # 创建方向信号记录器
    recorder = DirectionSignalRecorder()
    
    # 记录方向信号
    signal_report = recorder.record_direction_signals(decisions, current_date)
    
    return signal_report
