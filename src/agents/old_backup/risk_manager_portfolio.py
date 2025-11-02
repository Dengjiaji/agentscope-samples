"""
Portfolio模式的风险管理器
为每只股票计算基于波动率的仓位上限、允许的最大股数等信息
"""
from langchain_core.messages import HumanMessage
from src.graph.state import AgentState, show_agent_reasoning
from src.utils.progress import progress
from src.tools.api import get_prices, prices_to_df
import json
import numpy as np
import pandas as pd
from src.utils.api_key import get_api_key_from_state


def risk_management_agent_portfolio(state: AgentState, agent_id: str = "risk_management_agent_portfolio"):
    """
    Portfolio模式的风险管理 - 基于波动率控制仓位大小
    
    输出内容：
    - remaining_position_limit: 可用的仓位金额上限
    - current_price: 当前股价
    - volatility_metrics: 波动率指标
    - reasoning: 风险管理的详细推理
    """
    portfolio = state["data"]["portfolio"]
    data = state["data"]
    tickers = data["tickers"]
    api_key = get_api_key_from_state(state, "FINNHUB_API_KEY")
    
    # 初始化风险分析
    risk_analysis = {}
    current_prices = {}
    volatility_data = {}
    
    # 获取所有相关ticker的价格（包括现有持仓）
    all_tickers = set(tickers) | set(portfolio.get("positions", {}).keys())
    
    for ticker in all_tickers:
        progress.update_status(agent_id, ticker, "获取价格数据并计算波动率")
        
        prices = get_prices(
            ticker=ticker,
            start_date=data["start_date"],
            end_date=data["end_date"],
            api_key=api_key,
        )
        
        if not prices:
            progress.update_status(agent_id, ticker, "警告: 未找到价格数据")
            volatility_data[ticker] = {
                "daily_volatility": 0.05,
                "annualized_volatility": 0.05 * np.sqrt(252),
                "volatility_percentile": 100,
                "data_points": 0
            }
            continue
        
        prices_df = prices_to_df(prices)
        
        if not prices_df.empty and len(prices_df) > 1:
            current_price = prices_df["close"].iloc[-1]
            current_prices[ticker] = current_price
            
            # 计算波动率指标
            volatility_metrics = calculate_volatility_metrics(prices_df)
            volatility_data[ticker] = volatility_metrics
            
            progress.update_status(
                agent_id,
                ticker,
                f"价格: {current_price:.2f}, 年化波动率: {volatility_metrics['annualized_volatility']:.1%}"
            )
        else:
            progress.update_status(agent_id, ticker, "警告: 价格数据不足")
            current_prices[ticker] = 0
            volatility_data[ticker] = {
                "daily_volatility": 0.05,
                "annualized_volatility": 0.05 * np.sqrt(252),
                "volatility_percentile": 100,
                "data_points": len(prices_df) if not prices_df.empty else 0
            }
    
    # 计算投资组合总价值（净清算价值）
    total_portfolio_value = portfolio.get("cash", 0.0)
    
    for ticker, position in portfolio.get("positions", {}).items():
        if ticker in current_prices:
            # 加上多头持仓的市值
            total_portfolio_value += position.get("long", 0) * current_prices[ticker]
            # 减去空头持仓的市值
            total_portfolio_value -= position.get("short", 0) * current_prices[ticker]
    
    progress.update_status(agent_id, None, f"投资组合总价值: {total_portfolio_value:.2f}")
    
    # 为每只ticker计算波动率调整后的仓位限制
    for ticker in tickers:
        progress.update_status(agent_id, ticker, "计算波动率调整后的仓位限制")
        
        if ticker not in current_prices or current_prices[ticker] <= 0:
            progress.update_status(agent_id, ticker, "失败: 无有效价格数据")
            risk_analysis[ticker] = {
                "remaining_position_limit": 0.0,
                "current_price": 0.0,
                "reasoning": {
                    "error": "缺少价格数据进行风险计算"
                }
            }
            continue
        
        current_price = current_prices[ticker]
        vol_data = volatility_data.get(ticker, {})
        
        # 计算当前持仓的市值
        position = portfolio.get("positions", {}).get(ticker, {})
        long_value = position.get("long", 0) * current_price
        short_value = position.get("short", 0) * current_price
        current_position_value = abs(long_value - short_value)  # 使用绝对暴露
        
        # 计算波动率调整后的仓位限制
        vol_adjusted_limit = calculate_volatility_adjusted_limit(
            vol_data.get("annualized_volatility", 0.25)
        )
        
        position_limit = total_portfolio_value * vol_adjusted_limit
        
        # 计算剩余可用的仓位限制
        remaining_position_limit = position_limit - current_position_value
        
        # 确保不超过可用现金
        max_position_size = min(remaining_position_limit, portfolio.get("cash", 0))
        
        # 计算最大可购买股数
        max_shares = int(max_position_size / current_price) if current_price > 0 else 0
        
        risk_analysis[ticker] = {
            "remaining_position_limit": float(max_position_size),
            "current_price": float(current_price),
            "max_shares": int(max_shares),  # 添加最大可买股数
            "volatility_metrics": {
                "daily_volatility": float(vol_data.get("daily_volatility", 0.05)),
                "annualized_volatility": float(vol_data.get("annualized_volatility", 0.25)),
                "volatility_percentile": float(vol_data.get("volatility_percentile", 100)),
                "data_points": int(vol_data.get("data_points", 0))
            },
            "reasoning": {
                "portfolio_value": float(total_portfolio_value),
                "current_position_value": float(current_position_value),
                "base_position_limit_pct": float(vol_adjusted_limit),
                "position_limit": float(position_limit),
                "remaining_limit": float(remaining_position_limit),
                "available_cash": float(portfolio.get("cash", 0)),
                "risk_adjustment": f"基于波动率的限制: {vol_adjusted_limit:.1%} (相对于20%基准)"
            }
        }
        
        progress.update_status(
            agent_id,
            ticker,
            f"波动率调整限制: {vol_adjusted_limit:.1%}, 可用: ${max_position_size:.0f}"
        )
    
    progress.update_status(agent_id, None, "完成")
    
    message = HumanMessage(
        content=json.dumps(risk_analysis),
        name=agent_id,
    )
    
    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(risk_analysis, "Portfolio模式-波动率调整风险管理")
    
    # 将信号添加到analyst_signals
    state["data"]["analyst_signals"][agent_id] = risk_analysis
    
    return {
        "messages": state["messages"] + [message],
        "data": data,
    }


def calculate_volatility_metrics(prices_df: pd.DataFrame, lookback_days: int = 60) -> dict:
    """从价格数据计算综合波动率指标"""
    if len(prices_df) < 2:
        return {
            "daily_volatility": 0.05,
            "annualized_volatility": 0.05 * np.sqrt(252),
            "volatility_percentile": 100,
            "data_points": len(prices_df)
        }
    
    # 计算日收益率
    daily_returns = prices_df["close"].pct_change().dropna()
    
    if len(daily_returns) < 2:
        return {
            "daily_volatility": 0.05,
            "annualized_volatility": 0.05 * np.sqrt(252),
            "volatility_percentile": 100,
            "data_points": len(daily_returns)
        }
    
    # 使用最近的lookback_days进行波动率计算
    recent_returns = daily_returns.tail(min(lookback_days, len(daily_returns)))
    
    # 计算波动率指标
    daily_vol = recent_returns.std()
    annualized_vol = daily_vol * np.sqrt(252)  # 年化，假设252个交易日
    
    # 计算近期波动率相对于历史波动率的百分位
    if len(daily_returns) >= 30:
        # 计算完整历史的30日滚动波动率
        rolling_vol = daily_returns.rolling(window=30).std().dropna()
        if len(rolling_vol) > 0:
            # 将当前波动率与历史滚动波动率比较
            current_vol_percentile = (rolling_vol <= daily_vol).mean() * 100
        else:
            current_vol_percentile = 50
    else:
        current_vol_percentile = 50
    
    return {
        "daily_volatility": float(daily_vol) if not np.isnan(daily_vol) else 0.025,
        "annualized_volatility": float(annualized_vol) if not np.isnan(annualized_vol) else 0.25,
        "volatility_percentile": float(current_vol_percentile) if not np.isnan(current_vol_percentile) else 50.0,
        "data_points": len(recent_returns)
    }


def calculate_volatility_adjusted_limit(annualized_volatility: float) -> float:
    """
    基于波动率计算仓位限制占投资组合的百分比
    
    逻辑:
    - 低波动率 (<15%): 最多25%配置
    - 中等波动率 (15-30%): 15-20%配置
    - 高波动率 (>30%): 10-15%配置
    - 极高波动率 (>50%): 最多10%配置
    """
    base_limit = 0.20  # 20%基准
    
    if annualized_volatility < 0.15:  # 低波动率
        # 对稳定股票允许更高配置
        vol_multiplier = 1.25  # 最多25%
    elif annualized_volatility < 0.30:  # 中等波动率
        # 基于波动率微调的标准配置
        vol_multiplier = 1.0 - (annualized_volatility - 0.15) * 0.5  # 20% -> 12.5%
    elif annualized_volatility < 0.50:  # 高波动率
        # 显著降低配置
        vol_multiplier = 0.75 - (annualized_volatility - 0.30) * 0.5  # 15% -> 5%
    else:  # 极高波动率 (>50%)
        # 高风险股票的最小配置
        vol_multiplier = 0.50  # 最多10%
    
    # 应用边界确保合理限制
    vol_multiplier = max(0.25, min(1.25, vol_multiplier))  # 5%到25%范围
    
    return base_limit * vol_multiplier

