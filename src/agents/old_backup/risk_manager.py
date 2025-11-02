from langchain_core.messages import HumanMessage
from src.graph.state import AgentState, show_agent_reasoning
from src.utils.progress import progress
from src.tools.api import get_prices, prices_to_df
import json
import numpy as np
import pandas as pd
from src.utils.api_key import get_api_key_from_state


# 只提供风险评估信息，包括：
# risk_level: 风险等级 ("low", "medium", "high", "very_high")
# risk_score: 风险评分 (0-100)
# volatility_info: 波动率详细信息
# risk_assessment: 风险评估描述
# 不再提供: 投资方向建议，专注于纯粹的风险分析

##### Risk Management Agent #####
def risk_management_agent(state: AgentState, agent_id: str = "risk_management_agent"):
    """基于波动率风险因子分析，为每只股票提供风险评估信息"""
    data = state["data"]
    tickers = data["tickers"]
    api_key = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")
    
    # 初始化风险分析结果 - 只提供风险评估信息
    risk_analysis = {}
    volatility_data = {}  # 存储波动率指标
    current_prices = {}  # 存储当前价格

    # 获取股票的价格和波动率数据
    for ticker in tickers:
        progress.update_status(agent_id, ticker, "获取价格数据并计算波动率")
        
        prices = get_prices(
            ticker=ticker,
            start_date=data["start_date"],
            end_date=data["end_date"],
            api_key=api_key,
        )

        if not prices:
            progress.update_status(agent_id, ticker, "警告: 未找到价格数据")
            current_prices[ticker] = 0.0  # 无价格数据时设为0
            volatility_data[ticker] = {
                "daily_volatility": 0.05,  # 默认日波动率5%
                "annualized_volatility": 0.05 * np.sqrt(252),
                "volatility_percentile": 100,  # 假设高风险
                "data_points": 0
            }
            continue

        prices_df = prices_to_df(prices)
        
        if not prices_df.empty and len(prices_df) >= 1:
            # 获取最新价格（最后一个交易日的收盘价）
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
            current_prices[ticker] = 0.0  # 价格数据不足时设为0
            volatility_data[ticker] = {
                "daily_volatility": 0.05,
                "annualized_volatility": 0.05 * np.sqrt(252),
                "volatility_percentile": 100,
                "data_points": len(prices_df) if not prices_df.empty else 0
            }

    # 为每只股票生成风险评估信息
    for ticker in tickers:
        progress.update_status(agent_id, ticker, "生成风险评估信息")
        
        vol_data = volatility_data.get(ticker, {})
        if not vol_data:
            progress.update_status(agent_id, ticker, "失败: 无有效波动率数据")
            risk_analysis[ticker] = {
                "risk_level": "unknown",
                "risk_score": 0,
                "current_price": float(current_prices.get(ticker, 0.0)),  # 当前股价
                "volatility_info": {},
                "risk_assessment": "缺少波动率数据，无法进行风险分析"
            }
            continue
            
        annualized_vol = vol_data.get("annualized_volatility", 0.25)
        vol_percentile = vol_data.get("volatility_percentile", 50)
        daily_vol = vol_data.get("daily_volatility", 0.025)
        data_points = vol_data.get("data_points", 0)
        
        # 生成风险评估信息（不包含投资方向建议）
        risk_level, risk_score, assessment = generate_risk_assessment(
            ticker, annualized_vol, vol_percentile, daily_vol, data_points
        )
        
        risk_analysis[ticker] = {
            "risk_level": risk_level,  # "low", "medium", "high", "very_high"
            "risk_score": risk_score,  # 0-100的风险评分
            "current_price": float(current_prices.get(ticker, 0.0)),  # 当前股价
            "volatility_info": {
                "annualized_volatility": annualized_vol,
                "daily_volatility": daily_vol,
                "volatility_percentile": vol_percentile,
                "data_points": data_points
            },
            "risk_assessment": assessment
        }
        
        progress.update_status(
            agent_id, 
            ticker, 
            f"风险等级: {risk_level.upper()}, 风险评分: {risk_score}"
        )

    progress.update_status(agent_id, None, "完成")

    message = HumanMessage(
        content=json.dumps(risk_analysis),
        name=agent_id,
    )

    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(risk_analysis, "风险管理评估分析")

    # 将信号添加到analyst_signals列表
    state["data"]["analyst_signals"][agent_id] = risk_analysis

    return {
        "messages": state["messages"] + [message],
        "data": data,
    }


def calculate_volatility_metrics(prices_df: pd.DataFrame, lookback_days: int = 60) -> dict:
    """Calculate comprehensive volatility metrics from price data."""
    if len(prices_df) < 2:
        return {
            "daily_volatility": 0.05,
            "annualized_volatility": 0.05 * np.sqrt(252),
            "volatility_percentile": 100,
            "data_points": len(prices_df)
        }
    
    # Calculate daily returns
    daily_returns = prices_df["close"].pct_change().dropna()
    
    if len(daily_returns) < 2:
        return {
            "daily_volatility": 0.05,
            "annualized_volatility": 0.05 * np.sqrt(252),
            "volatility_percentile": 100,
            "data_points": len(daily_returns)
        }
    
    # Use the most recent lookback_days for volatility calculation
    recent_returns = daily_returns.tail(min(lookback_days, len(daily_returns)))
    
    # Calculate volatility metrics
    daily_vol = recent_returns.std()
    annualized_vol = daily_vol * np.sqrt(252)  # Annualize assuming 252 trading days
    
    # Calculate percentile rank of recent volatility vs historical volatility
    if len(daily_returns) >= 30:  # Need sufficient history for percentile calculation
        # Calculate 30-day rolling volatility for the full history
        rolling_vol = daily_returns.rolling(window=30).std().dropna()
        if len(rolling_vol) > 0:
            # Compare current volatility against historical rolling volatilities
            current_vol_percentile = (rolling_vol <= daily_vol).mean() * 100
        else:
            current_vol_percentile = 50  # Default to median
    else:
        current_vol_percentile = 50  # Default to median if insufficient data
    
    return {
        "daily_volatility": float(daily_vol) if not np.isnan(daily_vol) else 0.025,
        "annualized_volatility": float(annualized_vol) if not np.isnan(annualized_vol) else 0.25,
        "volatility_percentile": float(current_vol_percentile) if not np.isnan(current_vol_percentile) else 50.0,
        "data_points": len(recent_returns)
    }


def generate_risk_assessment(ticker: str, annualized_vol: float, vol_percentile: float, 
                           daily_vol: float, data_points: int) -> tuple:
    """
    基于波动率生成风险评估信息（不包含投资建议）
    
    Args:
        ticker: 股票代码
        annualized_vol: 年化波动率
        vol_percentile: 波动率百分位数
        daily_vol: 日波动率
        data_points: 数据点数量
        
    Returns:
        tuple: (risk_level, risk_score, assessment)
    """
    
    # 基于波动率的风险等级评估
    if annualized_vol < 0.15:  # 低波动率 < 15%
        risk_level = "low"
        base_score = 25
        if vol_percentile < 30:  # 当前波动率处于历史低位
            risk_score = base_score - 10  # 进一步降低风险评分
            assessment = f"低风险股票，年化波动率{annualized_vol:.1%}，当前处于历史低波动率水平，价格相对稳定"
        else:
            risk_score = base_score
            assessment = f"低风险股票，年化波动率{annualized_vol:.1%}，价格波动相对温和"
            
    elif annualized_vol < 0.30:  # 中等波动率 15-30%
        risk_level = "medium"
        base_score = 50
        if vol_percentile > 70:  # 波动率上升趋势
            risk_score = base_score + 15
            assessment = f"中等风险股票，年化波动率{annualized_vol:.1%}，当前波动率上升，风险增加"
        elif vol_percentile < 30:  # 波动率下降趋势
            risk_score = base_score - 10
            assessment = f"中等风险股票，年化波动率{annualized_vol:.1%}，当前波动率下降，风险相对降低"
        else:
            risk_score = base_score
            assessment = f"中等风险股票，年化波动率{annualized_vol:.1%}，价格波动处于正常水平"
            
    elif annualized_vol < 0.50:  # 高波动率 30-50%
        risk_level = "high"
        base_score = 75
        if vol_percentile > 80:  # 波动率极高
            risk_score = base_score + 15
            assessment = f"高风险股票，年化波动率{annualized_vol:.1%}，当前处于历史高波动率水平，价格波动剧烈"
        else:
            risk_score = base_score
            assessment = f"高风险股票，年化波动率{annualized_vol:.1%}，价格波动较大，需谨慎投资"
            
    else:  # 极高波动率 > 50%
        risk_level = "very_high"
        risk_score = 90
        assessment = f"极高风险股票，年化波动率{annualized_vol:.1%}，价格波动极大，投资风险极高"
    
    # 根据数据质量调整评估
    if data_points < 10:
        assessment += f"（注意：仅基于{data_points}个数据点，评估可靠性有限）"
        risk_score = min(risk_score + 10, 100)  # 数据不足时提高风险评分
    
    # 确保风险评分在合理范围内
    risk_score = max(0, min(100, risk_score))
    
    return risk_level, risk_score, assessment


