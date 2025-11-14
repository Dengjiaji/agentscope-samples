"""
交易执行引擎 - 支持两种模式
1. Signal模式：只记录方向信号决策
2. Portfolio模式：执行具体交易并跟踪持仓
"""

from typing import Dict, Any, List, Tuple, Optional
import json
from datetime import datetime
from copy import deepcopy


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


class PortfolioTradeExecutor:
    """Portfolio模式的交易执行器，执行具体交易并跟踪持仓"""
    
    def __init__(self, initial_portfolio: Optional[Dict[str, Any]] = None):
        """
        初始化Portfolio交易执行器
        
        Args:
            initial_portfolio: 初始投资组合状态
        """
        if initial_portfolio is None:
            self.portfolio = {
                "cash": 100000.0,
                "positions": {},
                "margin_requirement": 0.0,  # 默认0.0（禁用做空）
                "margin_used": 0.0
            }
        else:
            self.portfolio = deepcopy(initial_portfolio)
        
        self.trade_history = []  # 交易历史
        self.portfolio_history = []  # 投资组合历史
    
    def execute_trades(
        self,
        decisions: Dict[str, Dict[str, Any]],
        current_prices: Dict[str, float],
        current_date: str = None
    ) -> Dict[str, Any]:
        """
        执行交易决策并更新持仓
        
        Args:
            decisions: {ticker: {action, quantity, confidence, reasoning}}
            current_prices: {ticker: current_price}
            current_date: 当前日期
            
        Returns:
            交易执行报告
        """
        if current_date is None:
            current_date = datetime.now().strftime("%Y-%m-%d")
        
        execution_report = {
            "date": current_date,
            "timestamp": datetime.now().isoformat(),
            "executed_trades": [],
            "failed_trades": [],
            "portfolio_before": deepcopy(self.portfolio),
            "portfolio_after": None
        }
        
        print(f"\n💼 执行 {current_date} 的Portfolio交易...")
        
        # 执行每个ticker的交易
        for ticker, decision in decisions.items():
            action = decision.get("action", "hold")
            quantity = decision.get("quantity", 0)
            
            if action == "hold" or quantity == 0:
                continue
            
            price = current_prices.get(ticker, 0)
            if price <= 0:
                execution_report["failed_trades"].append({
                    "ticker": ticker,
                    "action": action,
                    "quantity": quantity,
                    "reason": "无有效价格数据"
                })
                print(f"   ❌ {ticker}: 无法执行 {action} - 无有效价格")
                continue
            
            # 执行交易
            trade_result = self._execute_single_trade(ticker, action, quantity, price, current_date)
            if trade_result["status"] == "success":
                execution_report["executed_trades"].append(trade_result)
                action_emoji = {
                    "long": "📈 看多",
                    "short": "📉 看空",
                    "hold": "➖ 观望"
                }
                emoji = action_emoji.get(action, action)
                trades_info = ", ".join(trade_result.get("trades", []))
                print(f"   ✅ {ticker}: {emoji} 目标{quantity}股 ({trades_info}) @ ${price:.2f}")
            else:
                execution_report["failed_trades"].append(trade_result)
                print(f"   ❌ {ticker}: 无法执行 {action} - {trade_result['reason']}")
        
        # 记录最终投资组合状态
        execution_report["portfolio_after"] = deepcopy(self.portfolio)
        self.portfolio_history.append({
            "date": current_date,
            "portfolio": deepcopy(self.portfolio)
        })
        
        # 计算投资组合价值
        portfolio_value = self._calculate_portfolio_value(current_prices)
        execution_report["portfolio_value"] = portfolio_value
        
        print(f"\n✅ 交易执行完成:")
        print(f"   成功: {len(execution_report['executed_trades'])} 笔")
        print(f"   失败: {len(execution_report['failed_trades'])} 笔")
        print(f"   投资组合价值: ${portfolio_value:,.2f}")
        print(f"   现金余额: ${self.portfolio['cash']:,.2f}")
        
        return execution_report
    
    def _execute_single_trade(
        self,
        ticker: str,
        action: str,
        target_quantity: int,
        price: float,
        date: str
    ) -> Dict[str, Any]:
        """
        执行单笔交易 - 增量模式
        
        Args:
            ticker: 股票代码
            action: long(加仓)/short(减仓)/hold
            target_quantity: 增量数量（long=买入股数，short=卖出股数）
            price: 当前价格
            date: 交易日期
        """
        
        # 确保持仓存在
        if ticker not in self.portfolio["positions"]:
            self.portfolio["positions"][ticker] = {
                "long": 0,
                "short": 0,
                "long_cost_basis": 0.0,
                "short_cost_basis": 0.0
            }
        
        position = self.portfolio["positions"][ticker]
        current_long = position["long"]
        current_short = position["short"]
        
        trades_executed = []  # 记录实际执行的交易步骤
        
        if action == "long":
            # 加仓：买入 target_quantity 股
            print(f"\n📈 {ticker} 加仓: 当前 {current_long}股 → 买入 {target_quantity}股 → 最终 {current_long + target_quantity}股")
            
            if target_quantity > 0:
                buy_result = self._buy_long_position(ticker, target_quantity, price, date)
                if buy_result["status"] == "failed":
                    return buy_result
                trades_executed.append(f"买入 {target_quantity}股")
            else:
                print(f"   ⏸️ quantity为0，无需交易")
            
        elif action == "short":
            # 看空：先卖出多头，如果quantity更大，剩余部分做空
            print(f"\n📉 {ticker} 看空操作 (quantity={target_quantity}股):")
            print(f"   当前状态: 多头{current_long}股, 空头{current_short}股")
            
            if target_quantity > 0:
                remaining_quantity = target_quantity
                
                # 步骤1: 如果有多头持仓，先卖出
                if current_long > 0:
                    sell_quantity = min(remaining_quantity, current_long)
                    print(f"   1️⃣ 卖出多头: {sell_quantity}股")
                    sell_result = self._sell_long_position(ticker, sell_quantity, price, date)
                    if sell_result["status"] == "failed":
                        return sell_result
                    trades_executed.append(f"卖出 {sell_quantity}股")
                    remaining_quantity -= sell_quantity
                
                # 步骤2: 如果还有剩余quantity，建立或增加空头
                if remaining_quantity > 0:
                    print(f"   2️⃣ 做空: {remaining_quantity}股")
                    short_result = self._open_short_position(ticker, remaining_quantity, price, date)
                    if short_result["status"] == "failed":
                        return short_result
                    trades_executed.append(f"做空 {remaining_quantity}股")
                
                # 显示最终结果
                final_long = self.portfolio["positions"][ticker]["long"]
                final_short = self.portfolio["positions"][ticker]["short"]
                print(f"   ✅ 最终状态: 多头{final_long}股, 空头{final_short}股")
            else:
                print(f"   ⏸️ quantity为0，无需交易")
        
        elif action == "hold":
            # 观望：不交易
            print(f"\n⏸️ {ticker} 持仓不变: {current_long}股")
        
        # 记录交易
        trade_record = {
            "status": "success",
            "ticker": ticker,
            "action": action,
            "target_quantity": target_quantity,
            "price": price,
            "trades": trades_executed,
            "date": date,
            "timestamp": datetime.now().isoformat()
        }
        
        self.trade_history.append(trade_record)
        
        return trade_record
    
    def _buy_long_position(self, ticker: str, quantity: int, price: float, date: str) -> Dict[str, Any]:
        """买入多头持仓"""
        position = self.portfolio["positions"][ticker]
        trade_value = quantity * price
        
        if self.portfolio["cash"] < trade_value:
            return {
                "status": "failed",
                "ticker": ticker,
                "action": "buy",
                "quantity": quantity,
                "price": price,
                "reason": f"现金不足 (需要: ${trade_value:.2f}, 可用: ${self.portfolio['cash']:.2f})"
            }
        
        # 更新持仓成本基础
        old_long = position["long"]
        old_cost_basis = position["long_cost_basis"]
        new_long = old_long + quantity
        
        # 🐛 调试信息
        print(f"   🔍 买入 {ticker}:")
        print(f"      旧持仓: {old_long} 股 @ ${old_cost_basis:.2f}")
        print(f"      买入: {quantity} 股 @ ${price:.2f}")
        print(f"      新持仓: {new_long} 股")
        
        if new_long > 0:
            new_cost_basis = ((old_long * old_cost_basis) + (quantity * price)) / new_long
            print(f"      新成本: ${new_cost_basis:.2f} = (({old_long} × ${old_cost_basis:.2f}) + ({quantity} × ${price:.2f})) / {new_long}")
            position["long_cost_basis"] = new_cost_basis
        position["long"] = new_long
        
        # 扣除现金
        self.portfolio["cash"] -= trade_value
        
        return {"status": "success"}
    
    def _sell_long_position(self, ticker: str, quantity: int, price: float, date: str) -> Dict[str, Any]:
        """卖出多头持仓"""
        position = self.portfolio["positions"][ticker]
        
        if position["long"] < quantity:
            return {
                "status": "failed",
                "ticker": ticker,
                "action": "sell",
                "quantity": quantity,
                "price": price,
                "reason": f"多头持仓不足 (持有: {position['long']}, 尝试卖出: {quantity})"
            }
        
        # 减少持仓
        position["long"] -= quantity
        if position["long"] == 0:
            position["long_cost_basis"] = 0.0
        
        # 增加现金
        trade_value = quantity * price
        self.portfolio["cash"] += trade_value
        
        return {"status": "success"}
    
    def _open_short_position(self, ticker: str, quantity: int, price: float, date: str) -> Dict[str, Any]:
        """开立空头持仓"""
        position = self.portfolio["positions"][ticker]
        trade_value = quantity * price
        margin_needed = trade_value * self.portfolio["margin_requirement"]
        
        if self.portfolio["cash"] < margin_needed:
            return {
                "status": "failed",
                "ticker": ticker,
                "action": "short",
                "quantity": quantity,
                "price": price,
                "reason": f"保证金不足 (需要: ${margin_needed:.2f}, 可用: ${self.portfolio['cash']:.2f})"
            }
        
        # 更新持仓成本基础
        old_short = position["short"]
        old_cost_basis = position["short_cost_basis"]
        new_short = old_short + quantity
        if new_short > 0:
            position["short_cost_basis"] = ((old_short * old_cost_basis) + (quantity * price)) / new_short
        position["short"] = new_short
        
        # 增加现金（卖空收入）和保证金使用
        self.portfolio["cash"] += trade_value - margin_needed
        self.portfolio["margin_used"] += margin_needed
        
        return {"status": "success"}
    
    def _cover_short_position(self, ticker: str, quantity: int, price: float, date: str) -> Dict[str, Any]:
        """平仓空头持仓"""
        position = self.portfolio["positions"][ticker]
        
        if position["short"] < quantity:
            return {
                "status": "failed",
                "ticker": ticker,
                "action": "cover",
                "quantity": quantity,
                "price": price,
                "reason": f"空头持仓不足 (持有: {position['short']}, 尝试平空: {quantity})"
            }
        
        # 计算释放的保证金
        trade_value = quantity * price
        margin_released = trade_value * self.portfolio["margin_requirement"]
        
        # 减少持仓
        position["short"] -= quantity
        if position["short"] == 0:
            position["short_cost_basis"] = 0.0
        
        # 扣除现金（买入平空）并释放保证金
        self.portfolio["cash"] -= trade_value
        self.portfolio["cash"] += margin_released
        self.portfolio["margin_used"] -= margin_released
        
        return {"status": "success"}
    
    def _calculate_portfolio_value(self, current_prices: Dict[str, float]) -> float:
        """计算投资组合总价值（净清算价值）"""
        total_value = self.portfolio["cash"]
        
        for ticker, position in self.portfolio["positions"].items():
            if ticker in current_prices:
                price = current_prices[ticker]
                # 加上多头持仓价值
                total_value += position["long"] * price
                # 减去空头持仓价值（负债）
                total_value -= position["short"] * price
        
        return total_value
    
    def get_portfolio_summary(self, current_prices: Dict[str, float]) -> Dict[str, Any]:
        """获取投资组合摘要"""
        portfolio_value = self._calculate_portfolio_value(current_prices)
        
        positions_summary = []
        for ticker, position in self.portfolio["positions"].items():
            if position["long"] > 0 or position["short"] > 0:
                price = current_prices.get(ticker, 0)
                long_value = position["long"] * price
                short_value = position["short"] * price
                
                positions_summary.append({
                    "ticker": ticker,
                    "long_shares": position["long"],
                    "short_shares": position["short"],
                    "long_value": long_value,
                    "short_value": short_value,
                    "long_cost_basis": position["long_cost_basis"],
                    "short_cost_basis": position["short_cost_basis"],
                    "long_pnl": long_value - (position["long"] * position["long_cost_basis"]) if position["long"] > 0 else 0,
                    "short_pnl": (position["short"] * position["short_cost_basis"]) - short_value if position["short"] > 0 else 0
                })
        
        return {
            "portfolio_value": portfolio_value,
            "cash": self.portfolio["cash"],
            "margin_used": self.portfolio["margin_used"],
            "positions": positions_summary,
            "total_trades": len(self.trade_history)
        }


def execute_trading_decisions(
    pm_decisions: Dict[str, Any], 
    current_date: str = None
) -> Dict[str, Any]:
    """
    记录方向信号决策的便捷函数（Signal模式）
    
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


def execute_portfolio_trades(
    pm_decisions: Dict[str, Any],
    current_prices: Dict[str, float],
    portfolio: Dict[str, Any],
    current_date: str = None
) -> Dict[str, Any]:
    """
    执行Portfolio模式的交易决策
    
    Args:
        pm_decisions: PM的交易决策
        current_prices: 当前价格
        portfolio: 当前投资组合状态
        current_date: 当前日期（可选）
        
    Returns:
        交易执行报告和更新后的投资组合
    """
    # 解析PM决策
    decisions = parse_pm_decisions(pm_decisions)
    
    # 创建Portfolio交易执行器
    executor = PortfolioTradeExecutor(initial_portfolio=portfolio)
    
    # 执行交易
    execution_report = executor.execute_trades(decisions, current_prices, current_date)
    
    # 添加投资组合摘要
    execution_report["portfolio_summary"] = executor.get_portfolio_summary(current_prices)
    
    # 返回更新后的投资组合
    execution_report["updated_portfolio"] = executor.portfolio
    
    return execution_report
