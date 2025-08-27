#!/usr/bin/env python3
"""
测试交易执行功能
验证Portfolio Manager的决策能够正确转换为portfolio更新
"""

import sys
import os
sys.path.append('/root/wuyue.wy/Project/IA')

from src.utils.trade_executor import TradeExecutor, execute_trading_decisions
import json
from datetime import datetime


def test_basic_trade_execution():
    """测试基本交易执行功能"""
    print("🧪 测试基本交易执行功能")
    print("=" * 50)
    
    # 创建测试portfolio
    test_portfolio = {
        "cash": 100000.0,
        "margin_requirement": 0.1,
        "margin_used": 0.0,
        "positions": {
            "AAPL": {
                "long": 0,
                "short": 0,
                "long_cost_basis": 0.0,
                "short_cost_basis": 0.0,
                "short_margin_used": 0.0,
            },
            "MSFT": {
                "long": 0,
                "short": 0,
                "long_cost_basis": 0.0,
                "short_cost_basis": 0.0,
                "short_margin_used": 0.0,
            }
        },
        "realized_gains": {
            "AAPL": {"long": 0.0, "short": 0.0},
            "MSFT": {"long": 0.0, "short": 0.0}
        }
    }
    
    # 模拟PM决策
    pm_decisions = {
        "AAPL": {
            "action": "buy",
            "quantity": 100,
            "confidence": 85.0,
            "reasoning": "强劲的季度业绩和创新产品线支持买入"
        },
        "MSFT": {
            "action": "buy", 
            "quantity": 50,
            "confidence": 78.0,
            "reasoning": "云计算业务增长稳定，AI布局领先"
        }
    }
    
    # 当前价格
    current_prices = {
        "AAPL": 150.0,
        "MSFT": 300.0
    }
    
    print("📊 初始Portfolio状态:")
    print(f"  💰 现金: ${test_portfolio['cash']:,.2f}")
    print(f"  📈 AAPL持仓: {test_portfolio['positions']['AAPL']['long']}股")
    print(f"  📈 MSFT持仓: {test_portfolio['positions']['MSFT']['long']}股")
    
    print("\n💼 PM决策:")
    for ticker, decision in pm_decisions.items():
        print(f"  {ticker}: {decision['action']} {decision['quantity']}股 @ ${current_prices[ticker]}")
    
    # 执行交易
    updated_portfolio, execution_report = execute_trading_decisions(
        portfolio=test_portfolio,
        pm_decisions=pm_decisions,
        current_prices=current_prices
    )
    
    print("\n📊 交易执行后Portfolio状态:")
    print(f"  💰 现金: ${updated_portfolio['cash']:,.2f}")
    print(f"  📈 AAPL持仓: {updated_portfolio['positions']['AAPL']['long']}股 @ ${updated_portfolio['positions']['AAPL']['long_cost_basis']:.2f}")
    print(f"  📈 MSFT持仓: {updated_portfolio['positions']['MSFT']['long']}股 @ ${updated_portfolio['positions']['MSFT']['long_cost_basis']:.2f}")
    
    # 验证结果
    expected_cash = 100000.0 - (100 * 150.0) - (50 * 300.0)  # 100k - 15k - 15k = 70k
    actual_cash = updated_portfolio['cash']
    
    print(f"\n✅ 验证结果:")
    print(f"  预期现金: ${expected_cash:,.2f}")
    print(f"  实际现金: ${actual_cash:,.2f}")
    print(f"  现金匹配: {'✅' if abs(expected_cash - actual_cash) < 0.01 else '❌'}")
    
    aapl_shares = updated_portfolio['positions']['AAPL']['long']
    msft_shares = updated_portfolio['positions']['MSFT']['long']
    print(f"  AAPL股份: {aapl_shares} (预期: 100) {'✅' if aapl_shares == 100 else '❌'}")
    print(f"  MSFT股份: {msft_shares} (预期: 50) {'✅' if msft_shares == 50 else '❌'}")
    
    return updated_portfolio, execution_report


def test_insufficient_funds():
    """测试资金不足的情况"""
    print("\n🧪 测试资金不足情况")
    print("=" * 50)
    
    # 创建资金较少的portfolio
    test_portfolio = {
        "cash": 10000.0,  # 只有1万现金
        "margin_requirement": 0.1,
        "margin_used": 0.0,
        "positions": {
            "AAPL": {
                "long": 0,
                "short": 0,
                "long_cost_basis": 0.0,
                "short_cost_basis": 0.0,
                "short_margin_used": 0.0,
            }
        },
        "realized_gains": {
            "AAPL": {"long": 0.0, "short": 0.0}
        }
    }
    
    # 尝试购买价值超过现金的股票
    pm_decisions = {
        "AAPL": {
            "action": "buy",
            "quantity": 100,  # 100股 × $150 = $15,000 > $10,000现金
            "confidence": 85.0,
            "reasoning": "强劲业绩支持买入，但资金有限"
        }
    }
    
    current_prices = {"AAPL": 150.0}
    
    print("📊 初始状态:")
    print(f"  💰 现金: ${test_portfolio['cash']:,.2f}")
    print(f"  💼 尝试购买: {pm_decisions['AAPL']['quantity']}股 AAPL @ ${current_prices['AAPL']}")
    print(f"  💸 所需资金: ${pm_decisions['AAPL']['quantity'] * current_prices['AAPL']:,.2f}")
    
    # 执行交易
    updated_portfolio, execution_report = execute_trading_decisions(
        portfolio=test_portfolio,
        pm_decisions=pm_decisions,
        current_prices=current_prices
    )
    
    # 计算实际可购买的股数
    max_affordable = int(10000.0 / current_prices['AAPL'])  # 使用原始现金计算
    actual_cost = max_affordable * current_prices['AAPL']
    
    print(f"\n📊 交易执行后状态:")
    print(f"  💰 剩余现金: ${updated_portfolio['cash']:,.2f}")
    print(f"  📈 实际购买: {updated_portfolio['positions']['AAPL']['long']}股")
    print(f"  💡 最大可购买: {max_affordable}股")
    print(f"  💸 实际花费: ${actual_cost:,.2f}")
    
    # 验证部分执行逻辑
    executed_shares = updated_portfolio['positions']['AAPL']['long']
    remaining_cash = updated_portfolio['cash']
    
    print(f"\n✅ 验证结果:")
    print(f"  部分执行: {'✅' if executed_shares == max_affordable else '❌'}")
    print(f"  现金余额: {'✅' if abs(remaining_cash - (10000 - actual_cost)) < 0.01 else '❌'}")
    
    return updated_portfolio, execution_report


def test_sell_positions():
    """测试卖出持仓"""
    print("\n🧪 测试卖出持仓")
    print("=" * 50)
    
    # 创建有持仓的portfolio
    test_portfolio = {
        "cash": 50000.0,
        "margin_requirement": 0.1,
        "margin_used": 0.0,
        "positions": {
            "AAPL": {
                "long": 200,  # 持有200股
                "short": 0,
                "long_cost_basis": 140.0,  # 平均成本$140
                "short_cost_basis": 0.0,
                "short_margin_used": 0.0,
            }
        },
        "realized_gains": {
            "AAPL": {"long": 0.0, "short": 0.0}
        }
    }
    
    # 卖出决策
    pm_decisions = {
        "AAPL": {
            "action": "sell",
            "quantity": 100,  # 卖出100股
            "confidence": 70.0,
            "reasoning": "获利了结，当前价格已达到目标价位"
        }
    }
    
    current_prices = {"AAPL": 160.0}  # 当前价格$160，高于成本价$140
    
    print("📊 初始状态:")
    print(f"  💰 现金: ${test_portfolio['cash']:,.2f}")
    print(f"  📈 AAPL持仓: {test_portfolio['positions']['AAPL']['long']}股 @ ${test_portfolio['positions']['AAPL']['long_cost_basis']}")
    print(f"  💼 计划卖出: {pm_decisions['AAPL']['quantity']}股 @ ${current_prices['AAPL']}")
    
    # 计算预期收益
    expected_gain = (current_prices['AAPL'] - test_portfolio['positions']['AAPL']['long_cost_basis']) * pm_decisions['AAPL']['quantity']
    expected_proceeds = pm_decisions['AAPL']['quantity'] * current_prices['AAPL']
    
    print(f"  💰 预期收益: ${expected_gain:,.2f}")
    print(f"  💸 预期收入: ${expected_proceeds:,.2f}")
    
    # 执行交易
    updated_portfolio, execution_report = execute_trading_decisions(
        portfolio=test_portfolio,
        pm_decisions=pm_decisions,
        current_prices=current_prices
    )
    
    print(f"\n📊 交易执行后状态:")
    print(f"  💰 现金: ${updated_portfolio['cash']:,.2f}")
    print(f"  📈 剩余AAPL持仓: {updated_portfolio['positions']['AAPL']['long']}股")
    print(f"  💰 已实现收益: ${updated_portfolio['realized_gains']['AAPL']['long']:,.2f}")
    
    # 验证结果
    expected_final_cash = 50000.0 + expected_proceeds
    actual_final_cash = updated_portfolio['cash']
    actual_realized_gain = updated_portfolio['realized_gains']['AAPL']['long']
    remaining_shares = updated_portfolio['positions']['AAPL']['long']
    
    print(f"\n✅ 验证结果:")
    print(f"  现金增加: {'✅' if abs(actual_final_cash - expected_final_cash) < 0.01 else '❌'}")
    print(f"  已实现收益: {'✅' if abs(actual_realized_gain - expected_gain) < 0.01 else '❌'}")
    print(f"  剩余持仓: {'✅' if remaining_shares == 100 else '❌'}")
    
    return updated_portfolio, execution_report


def test_short_positions():
    """测试做空操作"""
    print("\n🧪 测试做空操作")
    print("=" * 50)
    
    # 创建有现金的portfolio
    test_portfolio = {
        "cash": 100000.0,
        "margin_requirement": 0.2,  # 20%保证金要求
        "margin_used": 0.0,
        "positions": {
            "TSLA": {
                "long": 0,
                "short": 0,
                "long_cost_basis": 0.0,
                "short_cost_basis": 0.0,
                "short_margin_used": 0.0,
            }
        },
        "realized_gains": {
            "TSLA": {"long": 0.0, "short": 0.0}
        }
    }
    
    # 做空决策
    pm_decisions = {
        "TSLA": {
            "action": "short",
            "quantity": 100,  # 做空100股
            "confidence": 75.0,
            "reasoning": "估值过高，技术指标显示下跌趋势"
        }
    }
    
    current_prices = {"TSLA": 200.0}
    
    print("📊 初始状态:")
    print(f"  💰 现金: ${test_portfolio['cash']:,.2f}")
    print(f"  📉 计划做空: {pm_decisions['TSLA']['quantity']}股 TSLA @ ${current_prices['TSLA']}")
    print(f"  🔒 保证金要求: {test_portfolio['margin_requirement']*100}%")
    
    # 计算保证金需求
    proceeds = pm_decisions['TSLA']['quantity'] * current_prices['TSLA']  # $20,000
    margin_required = proceeds * test_portfolio['margin_requirement']  # $4,000
    net_cash_impact = proceeds - margin_required  # $16,000增加
    
    print(f"  💸 做空收入: ${proceeds:,.2f}")
    print(f"  🔒 所需保证金: ${margin_required:,.2f}")
    print(f"  💰 净现金增加: ${net_cash_impact:,.2f}")
    
    # 执行交易
    updated_portfolio, execution_report = execute_trading_decisions(
        portfolio=test_portfolio,
        pm_decisions=pm_decisions,
        current_prices=current_prices
    )
    
    print(f"\n📊 交易执行后状态:")
    print(f"  💰 现金: ${updated_portfolio['cash']:,.2f}")
    print(f"  📉 TSLA空头持仓: {updated_portfolio['positions']['TSLA']['short']}股 @ ${updated_portfolio['positions']['TSLA']['short_cost_basis']}")
    print(f"  🔒 已使用保证金: ${updated_portfolio['margin_used']:,.2f}")
    
    # 验证结果
    expected_final_cash = 100000.0 + net_cash_impact
    actual_final_cash = updated_portfolio['cash']
    short_shares = updated_portfolio['positions']['TSLA']['short']
    margin_used = updated_portfolio['margin_used']
    
    print(f"\n✅ 验证结果:")
    print(f"  现金变化: {'✅' if abs(actual_final_cash - expected_final_cash) < 0.01 else '❌'}")
    print(f"  空头建立: {'✅' if short_shares == 100 else '❌'}")
    print(f"  保证金占用: {'✅' if abs(margin_used - margin_required) < 0.01 else '❌'}")
    
    return updated_portfolio, execution_report


def run_all_tests():
    """运行所有测试"""
    print("🚀 开始交易执行功能测试")
    print("=" * 60)
    
    try:
        # 测试1: 基本买入
        test_basic_trade_execution()
        
        # 测试2: 资金不足
        test_insufficient_funds()
        
        # 测试3: 卖出持仓
        test_sell_positions()
        
        # 测试4: 做空操作
        test_short_positions()
        
        print("\n🎉 所有测试完成！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 测试过程中出现错误: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_all_tests()
