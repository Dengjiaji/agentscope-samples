"""
交易执行引擎 - 将Portfolio Manager的决策转换为实际的portfolio更新
参考ai-hedge-fund项目的交易执行逻辑
"""

from typing import Dict, Any, List, Tuple
import json
from datetime import datetime


class TradeExecutor:
    """交易执行引擎，负责执行Portfolio Manager的交易决策"""
    
    def __init__(self, portfolio: Dict[str, Any]):
        """
        初始化交易执行引擎
        
        Args:
            portfolio: 当前投资组合状态
        """
        self.portfolio = portfolio
        self.trade_log = []  # 记录所有交易历史
    
    def execute_portfolio_decisions(
        self, 
        decisions: Dict[str, Dict[str, Any]], 
        current_prices: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        执行Portfolio Manager的所有交易决策
        
        Args:
            decisions: PM的交易决策 {ticker: {action, quantity, confidence, reasoning}}
            current_prices: 当前价格 {ticker: price}
            
        Returns:
            执行结果报告
        """
        execution_report = {
            "executed_trades": {},
            "failed_trades": {},
            "portfolio_changes": {},
            "cash_before": self.portfolio.get("cash", 0),
            "cash_after": 0,
            "total_portfolio_value": 0,
            "execution_timestamp": datetime.now().isoformat()
        }
        
        print("\n💼 开始执行交易决策...")
        
        # 逐个执行每个ticker的决策
        for ticker, decision in decisions.items():
            action = decision.get("action", "hold")
            quantity = decision.get("quantity", 0)
            reasoning = decision.get("reasoning", "")
            
            if action == "hold" or quantity == 0:
                print(f"   📊 {ticker}: 持有 - {reasoning}")
                execution_report["executed_trades"][ticker] = {
                    "action": "hold", 
                    "quantity": 0, 
                    "executed_quantity": 0,
                    "price": current_prices.get(ticker, 0)
                }
                continue
            
            current_price = current_prices.get(ticker, 0)
            if current_price <= 0:
                print(f"   ❌ {ticker}: 价格数据不可用，跳过交易")
                execution_report["failed_trades"][ticker] = {
                    "reason": "价格数据不可用",
                    "action": action,
                    "quantity": quantity
                }
                continue
            
            # 执行具体交易
            executed_quantity = self._execute_single_trade(
                ticker, action, quantity, current_price
            )
            
            # 记录执行结果
            if executed_quantity > 0:
                execution_report["executed_trades"][ticker] = {
                    "action": action,
                    "quantity": quantity,
                    "executed_quantity": executed_quantity,
                    "price": current_price,
                    "reasoning": reasoning
                }
                print(f"   ✅ {ticker}: {action} {executed_quantity}股 @ ${current_price:.2f} - {reasoning}")
            else:
                execution_report["failed_trades"][ticker] = {
                    "reason": "资金不足或持仓不足",
                    "action": action,
                    "quantity": quantity,
                    "price": current_price
                }
                print(f"   ⚠️ {ticker}: {action}失败 - 资金或持仓不足")
        
        # 更新执行报告
        execution_report["cash_after"] = self.portfolio.get("cash", 0)
        execution_report["total_portfolio_value"] = self._calculate_portfolio_value(current_prices)
        execution_report["portfolio_changes"] = self._get_portfolio_changes()
        
        cash_change = execution_report["cash_after"] - execution_report["cash_before"]
        print(f"\n💰 现金变化: ${cash_change:+,.2f} (余额: ${execution_report['cash_after']:,.2f})")
        print(f"📈 投资组合总价值: ${execution_report['total_portfolio_value']:,.2f}")
        
        return execution_report
    
    def _execute_single_trade(
        self, 
        ticker: str, 
        action: str, 
        quantity: int, 
        current_price: float
    ) -> int:
        """
        执行单个交易
        
        Args:
            ticker: 股票代码
            action: 交易动作 (buy, sell, short, cover)
            quantity: 交易数量
            current_price: 当前价格
            
        Returns:
            实际执行的数量
        """
        if quantity <= 0:
            return 0
        
        quantity = int(quantity)  # 强制整数股份
        
        # 确保ticker在positions中存在
        if ticker not in self.portfolio["positions"]:
            self.portfolio["positions"][ticker] = {
                "long": 0,
                "short": 0,
                "long_cost_basis": 0.0,
                "short_cost_basis": 0.0,
                "short_margin_used": 0.0
            }
        
        position = self.portfolio["positions"][ticker]
        
        if action == "buy":
            return self._execute_buy(ticker, quantity, current_price, position)
        elif action == "sell":
            return self._execute_sell(ticker, quantity, current_price, position)
        elif action == "short":
            return self._execute_short(ticker, quantity, current_price, position)
        elif action == "cover":
            return self._execute_cover(ticker, quantity, current_price, position)
        
        return 0
    
    def _execute_buy(
        self, 
        ticker: str, 
        quantity: int, 
        current_price: float, 
        position: Dict[str, Any]
    ) -> int:
        """执行买入交易"""
        cost = quantity * current_price
        
        if cost <= self.portfolio["cash"]:
            # 计算加权平均成本基础
            old_shares = position["long"]
            old_cost_basis = position["long_cost_basis"]
            new_shares = quantity
            total_shares = old_shares + new_shares
            
            if total_shares > 0:
                total_old_cost = old_cost_basis * old_shares
                total_new_cost = cost
                position["long_cost_basis"] = (total_old_cost + total_new_cost) / total_shares
            
            position["long"] += quantity
            self.portfolio["cash"] -= cost
            
            # 记录交易日志
            self._log_trade(ticker, "buy", quantity, current_price, cost)
            
            return quantity
        else:
            # 资金不足时计算最大可购买数量
            max_quantity = int(self.portfolio["cash"] / current_price)
            if max_quantity > 0:
                cost = max_quantity * current_price
                old_shares = position["long"]
                old_cost_basis = position["long_cost_basis"]
                total_shares = old_shares + max_quantity
                
                if total_shares > 0:
                    total_old_cost = old_cost_basis * old_shares
                    total_new_cost = cost
                    position["long_cost_basis"] = (total_old_cost + total_new_cost) / total_shares
                
                position["long"] += max_quantity
                self.portfolio["cash"] -= cost
                
                # 记录交易日志
                self._log_trade(ticker, "buy", max_quantity, current_price, cost)
                
                return max_quantity
            return 0
    
    def _execute_sell(
        self, 
        ticker: str, 
        quantity: int, 
        current_price: float, 
        position: Dict[str, Any]
    ) -> int:
        """执行卖出交易"""
        # 只能卖出持有的股份
        quantity = min(quantity, position["long"])
        if quantity > 0:
            # 计算已实现盈亏
            avg_cost_per_share = position["long_cost_basis"] if position["long"] > 0 else 0
            realized_gain = (current_price - avg_cost_per_share) * quantity
            
            # 确保realized_gains结构存在
            if ticker not in self.portfolio["realized_gains"]:
                self.portfolio["realized_gains"][ticker] = {"long": 0.0, "short": 0.0}
            
            self.portfolio["realized_gains"][ticker]["long"] += realized_gain
            
            position["long"] -= quantity
            proceeds = quantity * current_price
            self.portfolio["cash"] += proceeds
            
            if position["long"] == 0:
                position["long_cost_basis"] = 0.0
            
            # 记录交易日志
            self._log_trade(ticker, "sell", quantity, current_price, proceeds, realized_gain)
            
            return quantity
        return 0
    
    def _execute_short(
        self, 
        ticker: str, 
        quantity: int, 
        current_price: float, 
        position: Dict[str, Any]
    ) -> int:
        """执行做空交易"""
        proceeds = current_price * quantity
        margin_required = proceeds * self.portfolio["margin_requirement"]
        
        if margin_required <= self.portfolio["cash"]:
            # 计算加权平均做空成本基础
            old_short_shares = position["short"]
            old_cost_basis = position["short_cost_basis"]
            new_shares = quantity
            total_shares = old_short_shares + new_shares
            
            if total_shares > 0:
                total_old_cost = old_cost_basis * old_short_shares
                total_new_cost = current_price * new_shares
                position["short_cost_basis"] = (total_old_cost + total_new_cost) / total_shares
            
            position["short"] += quantity
            position["short_margin_used"] += margin_required
            self.portfolio["margin_used"] += margin_required
            
            # 增加现金（获得做空收益），然后扣除保证金
            self.portfolio["cash"] += proceeds
            self.portfolio["cash"] -= margin_required
            
            # 记录交易日志
            self._log_trade(ticker, "short", quantity, current_price, proceeds - margin_required)
            
            return quantity
        else:
            # 保证金不足时计算最大可做空数量
            margin_ratio = self.portfolio["margin_requirement"]
            if margin_ratio > 0:
                max_quantity = int(self.portfolio["cash"] / (current_price * margin_ratio))
            else:
                max_quantity = 0
            
            if max_quantity > 0:
                proceeds = current_price * max_quantity
                margin_required = proceeds * margin_ratio
                
                old_short_shares = position["short"]
                old_cost_basis = position["short_cost_basis"]
                total_shares = old_short_shares + max_quantity
                
                if total_shares > 0:
                    total_old_cost = old_cost_basis * old_short_shares
                    total_new_cost = current_price * max_quantity
                    position["short_cost_basis"] = (total_old_cost + total_new_cost) / total_shares
                
                position["short"] += max_quantity
                position["short_margin_used"] += margin_required
                self.portfolio["margin_used"] += margin_required
                
                self.portfolio["cash"] += proceeds
                self.portfolio["cash"] -= margin_required
                
                # 记录交易日志
                self._log_trade(ticker, "short", max_quantity, current_price, proceeds - margin_required)
                
                return max_quantity
            return 0
    
    def _execute_cover(
        self, 
        ticker: str, 
        quantity: int, 
        current_price: float, 
        position: Dict[str, Any]
    ) -> int:
        """执行平仓交易"""
        # 只能平仓持有的空头股份
        quantity = min(quantity, position["short"])
        if quantity > 0:
            cover_cost = quantity * current_price
            avg_short_price = position["short_cost_basis"] if position["short"] > 0 else 0
            realized_gain = (avg_short_price - current_price) * quantity
            
            # 计算需要释放的保证金比例
            if position["short"] > 0:
                portion = quantity / position["short"]
            else:
                portion = 1.0
            
            margin_to_release = portion * position["short_margin_used"]
            
            position["short"] -= quantity
            position["short_margin_used"] -= margin_to_release
            self.portfolio["margin_used"] -= margin_to_release
            
            # 支付平仓成本，但获得释放的保证金
            self.portfolio["cash"] += margin_to_release
            self.portfolio["cash"] -= cover_cost
            
            # 确保realized_gains结构存在
            if ticker not in self.portfolio["realized_gains"]:
                self.portfolio["realized_gains"][ticker] = {"long": 0.0, "short": 0.0}
            
            self.portfolio["realized_gains"][ticker]["short"] += realized_gain
            
            if position["short"] == 0:
                position["short_cost_basis"] = 0.0
                position["short_margin_used"] = 0.0
            
            # 记录交易日志
            self._log_trade(ticker, "cover", quantity, current_price, margin_to_release - cover_cost, realized_gain)
            
            return quantity
        return 0
    
    def _log_trade(
        self, 
        ticker: str, 
        action: str, 
        quantity: int, 
        price: float, 
        cash_impact: float, 
        realized_gain: float = 0.0
    ):
        """记录交易日志"""
        trade_record = {
            "timestamp": datetime.now().isoformat(),
            "ticker": ticker,
            "action": action,
            "quantity": quantity,
            "price": price,
            "cash_impact": cash_impact,
            "realized_gain": realized_gain
        }
        self.trade_log.append(trade_record)
    
    def _calculate_portfolio_value(self, current_prices: Dict[str, float]) -> float:
        """计算投资组合总价值"""
        total_value = self.portfolio["cash"]
        
        for ticker, position in self.portfolio["positions"].items():
            price = current_prices.get(ticker, 0)
            
            # 多头持仓价值
            long_value = position["long"] * price
            total_value += long_value
            
            # 空头持仓未实现盈亏 = 空头股数 * (空头成本 - 当前价格)
            if position["short"] > 0:
                short_unrealized_pnl = position["short"] * (position["short_cost_basis"] - price)
                total_value += short_unrealized_pnl
        
        return total_value
    
    def _get_portfolio_changes(self) -> Dict[str, Any]:
        """获取投资组合变化摘要"""
        changes = {
            "positions_updated": [],
            "new_positions": [],
            "closed_positions": []
        }
        
        for ticker, position in self.portfolio["positions"].items():
            if position["long"] > 0 or position["short"] > 0:
                changes["positions_updated"].append({
                    "ticker": ticker,
                    "long_shares": position["long"],
                    "short_shares": position["short"],
                    "long_cost_basis": position["long_cost_basis"],
                    "short_cost_basis": position["short_cost_basis"]
                })
        
        return changes
    
    def get_trade_summary(self) -> Dict[str, Any]:
        """获取交易摘要"""
        return {
            "total_trades": len(self.trade_log),
            "trade_log": self.trade_log,
            "current_portfolio": self.portfolio
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
    portfolio: Dict[str, Any],
    pm_decisions: Dict[str, Any], 
    current_prices: Dict[str, float]
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    执行交易决策的便捷函数
    
    Args:
        portfolio: 当前投资组合
        pm_decisions: PM的交易决策
        current_prices: 当前价格
        
    Returns:
        (更新后的portfolio, 执行报告)
    """
    # 解析PM决策
    decisions = parse_pm_decisions(pm_decisions)
    
    # 创建交易执行器
    executor = TradeExecutor(portfolio)
    
    # 执行交易
    execution_report = executor.execute_portfolio_decisions(decisions, current_prices)
    
    return portfolio, execution_report
