"""
统一的分析工具集合
包含基本面分析、技术分析、情绪分析和估值分析的所有工具
"""

from langchain_core.tools import tool
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np
import json
from datetime import datetime
from statistics import median
import math

from src.tools.api import (
    get_financial_metrics, 
    get_prices, 
    get_insider_trades, 
    get_company_news,
    prices_to_df,
    get_market_cap,
    search_line_items,
)


# ===================== 工具辅助函数 =====================

def safe_float(value, default=0.0):
    """安全转换为浮点数"""
    try:
        if pd.isna(value) or np.isnan(value):
            return default
        return float(value)
    except (ValueError, TypeError, OverflowError):
        return default


def normalize_pandas(data):
    """规范化pandas数据为可序列化格式"""
    if isinstance(data, dict):
        return {key: safe_float(value) for key, value in data.items()}
    elif hasattr(data, 'to_dict'):
        return {key: safe_float(value) for key, value in data.to_dict().items()}
    else:
        return safe_float(data)


# def combine_tool_signals_with_llm(tool_results: List[Dict[str, Any]], 
#                                  analyst_persona: str, 
#                                  ticker: str,
#                                  llm=None) -> Dict[str, Any]:
#     """
#     使用LLM综合判断多个工具的分析结果
    
#     Args:
#         tool_results: 工具结果列表
#         analyst_persona: 分析师角色
#         ticker: 股票代码
#         llm: LLM模型实例
        
#     Returns:
#         LLM综合判断后的信号结果
#     """
#     if not tool_results:
#         return {"signal": "neutral", "confidence": 0, "reasoning": "No tool results provided"}
    
#     # 过滤掉有错误的结果
#     valid_results = [result for result in tool_results if "error" not in result]
    
#     if not valid_results:
#         return {"signal": "neutral", "confidence": 0, "reasoning": "No valid tool results"}
    
    
#     # 构建LLM综合分析的prompt
#     synthesis_prompt = _build_synthesis_prompt(valid_results, analyst_persona, ticker)
    
#     # 调用LLM进行综合分析
#     from langchain_core.messages import HumanMessage
#     response = llm.invoke([HumanMessage(content=synthesis_prompt)])
    
#     # 解析LLM响应
#     result = _parse_llm_synthesis_response(response.content, valid_results)
#     return result
       

# def _build_synthesis_prompt(tool_results: List[Dict[str, Any]], 
#                            analyst_persona: str, 
#                            ticker: str) -> str:
#     """构建LLM综合分析的prompt"""
    
#     # 构建工具结果摘要
#     tool_summaries = []
#     for i, result in enumerate(tool_results, 1):
#         tool_name = result.get("tool_name", f"工具{i}")
#         signal = result.get("signal", "unknown")
#         reasoning = result.get("reasoning", "无推理信息")
#         metrics = result.get("metrics", {})
        
#         summary = f"""
# **工具{i}: {tool_name}**
# - 信号: {signal.upper()}
# - 分析推理: {reasoning}"""
        
#         # 添加关键指标
#         if metrics:
#             key_metrics = []
#             for key, value in metrics.items():
#                 if isinstance(value, (int, float)):
#                     key_metrics.append(f"{key}: {value:.2f}")
#                 else:
#                     key_metrics.append(f"{key}: {value}")
#             if key_metrics:
#                 summary += f"\n- 关键指标: {', '.join(key_metrics[:5])}"  # 只显示前5个
        
#         tool_summaries.append(summary)
    
#     tools_text = "\n".join(tool_summaries)
    
#     prompt = f"""
# 你是一位专业的{analyst_persona}，需要综合分析以下工具的结果，对股票{ticker}给出最终的投资信号和置信度。

# **分析工具结果**:
# {tools_text}

# **你的任务**:
# 1. 仔细分析每个工具的信号和推理
# 2. 考虑工具结果之间的一致性和分歧
# 3. 根据你作为{analyst_persona}的专业判断，权衡各个工具的重要性
# 4. 综合得出最终的投资信号(bullish/bearish/neutral)和置信度(0-100)

# **输出要求**（必须严格按照JSON格式）:
# ```json
# {{
#     "signal": "bullish/bearish/neutral",
#     "confidence": 85,
#     "reasoning": "详细的综合分析推理，解释为什么得出这个结论",
#     "tool_analysis": {{
#         "consistent_signals": ["一致的工具信号"],
#         "conflicting_signals": ["冲突的工具信号"], 
#         "key_factors": ["影响决策的关键因素"],
#         "risk_considerations": ["需要考虑的风险因素"]
#     }},
#     "synthesis_method": "说明你是如何综合这些工具结果的"
# }}
# ```

# 请基于你的专业经验和判断，给出最终的综合分析结果。
# """
#     return prompt


# def _parse_llm_synthesis_response(response_content: str, tool_results: List[Dict[str, Any]]) -> Dict[str, Any]:
#     """解析LLM综合分析的响应"""
#     import json
#     import re
    
#         # 尝试从    响应中提取JSON
#     json_match = re.search(r'```json\s*(.*?)\s*```', response_content, re.DOTALL)
#     if json_match:
#         json_str = json_match.group(1)
#     else:
#         # 如果没有找到```json```标记，尝试直接解析整个响应
#         json_str = response_content.strip()
    
#     result = json.loads(json_str)
    
#     # 验证必需字段
#     signal = result.get("signal", "neutral").lower()
#     if signal not in ["bullish", "bearish", "neutral"]:
#         signal = "neutral"
    
#     confidence = result.get("confidence", 50)
#     if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 100:
#         confidence = 50
    
#     return {
#         "signal": signal,
#         "confidence": int(confidence),
#         "reasoning": result.get("reasoning", "LLM综合分析结果"),
#         "tool_analysis": result.get("tool_analysis", {}),
#         "synthesis_method": result.get("synthesis_method", "LLM综合判断"),
#         "tool_count": len(tool_results),
#         "llm_enhanced": True
#     }
        


# # 保持向后兼容的旧函数名
# def combine_tool_signals(tool_results: List[Dict[str, Any]], weights: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
#     """向后兼容的函数，建议使用combine_tool_signals_with_llm"""
#     return _fallback_combine_signals([r for r in tool_results if "error" not in r])


# ===================== 基本面分析工具 =====================
@tool
def analyze_efficiency_ratios(ticker: str, end_date: str, api_key: str) -> Dict[str, Any]:
    """效率比率分析 - 分析公司资产使用效率"""
    try:
        financial_metrics = get_financial_metrics(ticker=ticker, end_date=end_date, period="ttm", limit=10, api_key=api_key)
        if not financial_metrics:
            return {"error": "No financial metrics found", "signal": "neutral", "confidence": 0}
        
        metrics = financial_metrics[0]
        
        # 效率指标
        asset_turnover = metrics.asset_turnover
        inventory_turnover = metrics.inventory_turnover
        receivables_turnover = metrics.receivables_turnover
        working_capital_turnover = metrics.working_capital_turnover
        
        score = 0
        details = []
        
        # 资产周转率
        if asset_turnover and asset_turnover > 1.0:
            score += 1
            details.append(f"资产周转率良好: {asset_turnover:.2f}")
        else:
            details.append(f"资产周转率偏低: {asset_turnover:.2f}" if asset_turnover else "资产周转率: N/A")
        
        # 存货周转率
        if inventory_turnover and inventory_turnover > 6:
            score += 1
            details.append(f"存货周转快: {inventory_turnover:.1f}次/年")
        else:
            details.append(f"存货周转慢: {inventory_turnover:.1f}次/年" if inventory_turnover else "存货周转率: N/A")
        
        # 应收账款周转率
        if receivables_turnover and receivables_turnover > 8:
            score += 1
            details.append(f"应收账款周转快: {receivables_turnover:.1f}次/年")
        else:
            details.append(f"应收账款周转慢: {receivables_turnover:.1f}次/年" if receivables_turnover else "应收账款周转率: N/A")
        
        # 营运资本周转率
        if working_capital_turnover and working_capital_turnover > 4:
            score += 1
            details.append(f"营运资本效率高: {working_capital_turnover:.1f}")
        else:
            details.append(f"营运资本效率低: {working_capital_turnover:.1f}" if working_capital_turnover else "营运资本周转率: N/A")
        
        signal = "bullish" if score >= 3 else "bearish" if score <= 1 else "neutral"
        
        return {
            "signal": signal,
            "metrics": {
                "asset_turnover": asset_turnover,
                "inventory_turnover": inventory_turnover,
                "receivables_turnover": receivables_turnover,
                "working_capital_turnover": working_capital_turnover
            },
            "details": details,
            "reasoning": f"效率分析评分: {score}/4"
        }
    except Exception as e:
        return {"error": str(e), "signal": "neutral"}

@tool
def analyze_profitability(ticker: str, end_date: str, api_key: str) -> Dict[str, Any]:
    """
    分析公司盈利能力
    
    Args:
        ticker: 股票代码
        end_date: 结束日期
        api_key: API密钥
        
    Returns:
        包含盈利能力分析结果的字典
    """
    try:
        # 获取财务指标
        financial_metrics = get_financial_metrics(
            ticker=ticker,
            end_date=end_date,
            period="ttm",
            limit=10,
            api_key=api_key,
        )
        
        if not financial_metrics:
            return {"error": "No financial metrics found", "signal": "neutral"}
        
        metrics = financial_metrics[0]
        
        # 盈利能力指标
        return_on_equity = metrics.return_on_equity
        net_margin = metrics.net_margin
        operating_margin = metrics.operating_margin
        
        # 评估标准
        thresholds = [
            (return_on_equity, 0.15, "ROE > 15%"),  # Strong ROE above 15%
            (net_margin, 0.20, "Net Margin > 20%"),  # Healthy profit margins
            (operating_margin, 0.15, "Operating Margin > 15%"),  # Strong operating efficiency
        ]
        
        score = 0
        details = []
        for metric, threshold, description in thresholds:
            if metric is not None and metric > threshold:
                score += 1
                details.append(f"{description}: {metric:.2%}")
            else:
                details.append(f"{description}: {metric:.2%}" if metric else f"{description}: N/A")
        
        # 生成信号
        if score >= 2:
            signal = "bullish"
        elif score == 0:
            signal = "bearish"
        else:
            signal = "neutral"
            
        return {
            "signal": signal,
            "score": score,
            "max_score": len(thresholds),
            "metrics": {
                "return_on_equity": return_on_equity,
                "net_margin": net_margin,
                "operating_margin": operating_margin
            },
            "details": details,
            "reasoning": f"盈利能力评分: {score}/{len(thresholds)}"
        }
        
    except Exception as e:
        return {"error": str(e), "signal": "neutral"}


@tool
def analyze_growth(ticker: str, end_date: str, api_key: str) -> Dict[str, Any]:
    """
    分析公司成长性
    
    Args:
        ticker: 股票代码
        end_date: 结束日期
        api_key: API密钥
        
    Returns:
        包含成长性分析结果的字典
    """
    try:
        financial_metrics = get_financial_metrics(
            ticker=ticker,
            end_date=end_date,
            period="ttm", 
            limit=10,
            api_key=api_key,
        )
        
        if not financial_metrics:
            return {"error": "No financial metrics found", "signal": "neutral"}
        
        metrics = financial_metrics[0]
        
        # 成长性指标
        revenue_growth = metrics.revenue_growth
        earnings_growth = metrics.earnings_growth
        book_value_growth = metrics.book_value_growth
        
        # 评估标准
        thresholds = [
            (revenue_growth, 0.10, "Revenue Growth > 10%"),
            (earnings_growth, 0.10, "Earnings Growth > 10%"),
            (book_value_growth, 0.10, "Book Value Growth > 10%"),
        ]
        
        score = 0
        details = []
        for metric, threshold, description in thresholds:
            if metric is not None and metric > threshold:
                score += 1
                details.append(f"{description}: {metric:.2%}")
            else:
                details.append(f"{description}: {metric:.2%}" if metric else f"{description}: N/A")
        
        # 生成信号
        if score >= 2:
            signal = "bullish"
        elif score == 0:
            signal = "bearish"
        else:
            signal = "neutral"
            
        
        return {
            "signal": signal,
            "score": score,
            "max_score": len(thresholds),
            "metrics": {
                "revenue_growth": revenue_growth,
                "earnings_growth": earnings_growth,
                "book_value_growth": book_value_growth
            },
            "details": details,
            "reasoning": f"成长性评分: {score}/{len(thresholds)}"
        }
        
    except Exception as e:
        return {"error": str(e), "signal": "neutral"}


@tool  
def analyze_financial_health(ticker: str, end_date: str, api_key: str) -> Dict[str, Any]:
    """
    分析公司财务健康度
    
    Args:
        ticker: 股票代码
        end_date: 结束日期
        api_key: API密钥
        
    Returns:
        包含财务健康度分析结果的字典
    """
    try:
        financial_metrics = get_financial_metrics(
            ticker=ticker,
            end_date=end_date,
            period="ttm",
            limit=10,
            api_key=api_key,
        )
        
        if not financial_metrics:
            return {"error": "No financial metrics found", "signal": "neutral"}
        
        metrics = financial_metrics[0]
        
        # 财务健康度指标
        current_ratio = metrics.current_ratio
        debt_to_equity = metrics.debt_to_equity
        free_cash_flow_per_share = metrics.free_cash_flow_per_share
        earnings_per_share = metrics.earnings_per_share
        
        score = 0
        details = []
        
        # 流动性评估
        if current_ratio and current_ratio > 1.5:
            score += 1
            details.append(f"流动性良好: Current Ratio = {current_ratio:.2f}")
        else:
            details.append(f"流动性不足: Current Ratio = {current_ratio:.2f}" if current_ratio else "流动性不足: Current Ratio = N/A")
            
        # 债务水平评估
        if debt_to_equity and debt_to_equity < 0.5:
            score += 1
            details.append(f"债务水平保守: D/E = {debt_to_equity:.2f}")
        else:
            details.append(f"债务水平较高: D/E = {debt_to_equity:.2f}" if debt_to_equity else "债务水平较高: D/E = N/A")
            
        # 现金流评估
        if (free_cash_flow_per_share and earnings_per_share and 
            free_cash_flow_per_share > earnings_per_share * 0.8):
            score += 1
            details.append(f"现金流转换良好: FCF/EPS = {free_cash_flow_per_share/earnings_per_share:.2f}")
        else:
            details.append("现金流转换不佳")
        
        # 生成信号
        if score >= 2:
            signal = "bullish"
        elif score == 0:
            signal = "bearish"
        else:
            signal = "neutral"
            
        
        return {
            "signal": signal,
            "score": score,
            "max_score": 3,
            "metrics": {
                "current_ratio": current_ratio,
                "debt_to_equity": debt_to_equity,
                "free_cash_flow_per_share": free_cash_flow_per_share,
                "earnings_per_share": earnings_per_share
            },
            "details": details,
            "reasoning": f"财务健康度评分: {score}/3"
        }
        
    except Exception as e:
        return {"error": str(e), "signal": "neutral"}


@tool
def analyze_valuation_ratios(ticker: str, end_date: str, api_key: str) -> Dict[str, Any]:
    """
    分析估值比率
    
    Args:
        ticker: 股票代码
        end_date: 结束日期
        api_key: API密钥
        
    Returns:
        包含估值比率分析结果的字典
    """
    try:
        financial_metrics = get_financial_metrics(
            ticker=ticker,
            end_date=end_date,
            period="ttm",
            limit=10,
            api_key=api_key,
        )
        
        if not financial_metrics:
            return {"error": "No financial metrics found", "signal": "neutral"}
        
        metrics = financial_metrics[0]
        
        # 估值比率指标
        pe_ratio = metrics.price_to_earnings_ratio
        pb_ratio = metrics.price_to_book_ratio
        ps_ratio = metrics.price_to_sales_ratio
        
        # 评估标准 (高估值为负面信号)
        thresholds = [
            (pe_ratio, 25, "P/E < 25"),
            (pb_ratio, 3, "P/B < 3"),
            (ps_ratio, 5, "P/S < 5"),
        ]
        
        overvalued_score = 0
        details = []
        for metric, threshold, description in thresholds:
            if metric is not None and metric > threshold:
                overvalued_score += 1
                details.append(f"估值偏高: {description.split('<')[0]}= {metric:.2f}")
            else:
                details.append(f"估值合理: {description.split('<')[0]}= {metric:.2f}" if metric else f"{description.split('<')[0]}= N/A")
        
        # 生成信号 (高估值越多越bearish)
        if overvalued_score >= 2:
            signal = "bearish"
        elif overvalued_score == 0:
            signal = "bullish"
        else:
            signal = "neutral"
            
        
        return {
            "signal": signal,
            "overvalued_score": overvalued_score,
            "max_score": len(thresholds),
            "metrics": {
                "pe_ratio": pe_ratio,
                "pb_ratio": pb_ratio,
                "ps_ratio": ps_ratio
            },
            "details": details,
            "reasoning": f"估值偏高指标数: {overvalued_score}/{len(thresholds)}"
        }
        
    except Exception as e:
        return {"error": str(e), "signal": "neutral"}


# ===================== 技术分析工具 =====================

@tool
def analyze_trend_following(ticker: str, start_date: str, end_date: str, api_key: str) -> Dict[str, Any]:
    """
    趋势跟踪分析
    
    Args:
        ticker: 股票代码
        start_date: 开始日期
        end_date: 结束日期
        api_key: API密钥
        
    Returns:
        包含趋势跟踪分析结果的字典
    """
    try:
        # 自动扩展历史数据范围以满足技术分析需求
        from datetime import datetime, timedelta
        
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        # 扩展到90天前以确保有足够的历史数据
        extended_start_date = (end_dt - timedelta(days=90)).strftime("%Y-%m-%d")
        
        # 获取扩展的价格数据
        prices = get_prices(ticker=ticker, start_date=extended_start_date, end_date=end_date, api_key=api_key)
        
        if not prices:
            return {"error": "No price data found", "signal": "neutral"}
        
        prices_df = prices_to_df(prices)
        
        # 降低最小数据要求，但提供更好的错误信息
        if len(prices_df) < 10:
            return {
                "error": f"Insufficient data for trend analysis: only {len(prices_df)} days available, need at least 10", 
                "signal": "neutral", 
                "data_range": f"Attempted to fetch data from {extended_start_date} to {end_date}"
            }
        elif len(prices_df) < 20:
            # 如果数据不足20天但超过10天，降级处理但继续分析
            print(f"警告: 趋势分析数据不足，仅有{len(prices_df)}天数据，建议至少20天")
        
        # 计算移动平均线 - 根据数据长度调整窗口
        data_length = len(prices_df)
        sma_short_window = min(20, data_length // 2)
        sma_long_window = min(50, data_length - 5) if data_length > 25 else min(25, data_length - 5)
        
        prices_df['SMA_20'] = prices_df['close'].rolling(window=sma_short_window).mean()
        prices_df['SMA_50'] = prices_df['close'].rolling(window=sma_long_window).mean()
        prices_df['EMA_12'] = prices_df['close'].ewm(span=min(12, data_length // 3)).mean()
        prices_df['EMA_26'] = prices_df['close'].ewm(span=min(26, data_length // 2)).mean()
        
        # MACD
        prices_df['MACD'] = prices_df['EMA_12'] - prices_df['EMA_26']
        prices_df['MACD_signal'] = prices_df['MACD'].ewm(span=9).mean()
        prices_df['MACD_histogram'] = prices_df['MACD'] - prices_df['MACD_signal']
        
        # 获取最新值
        current_price = safe_float(prices_df['close'].iloc[-1])
        sma_20 = safe_float(prices_df['SMA_20'].iloc[-1])
        sma_50 = safe_float(prices_df['SMA_50'].iloc[-1])
        macd = safe_float(prices_df['MACD'].iloc[-1])
        macd_signal = safe_float(prices_df['MACD_signal'].iloc[-1])
        macd_histogram = safe_float(prices_df['MACD_histogram'].iloc[-1])
        
        # 趋势信号评分
        signals = []
        details = []
        
        # 1. 价格vs移动平均线
        if current_price > sma_20 > sma_50:
            signals.append("bullish")
            details.append(f"价格位于均线上方: {current_price:.2f} > SMA20({sma_20:.2f}) > SMA50({sma_50:.2f})")
        elif current_price < sma_20 < sma_50:
            signals.append("bearish")
            details.append(f"价格位于均线下方: {current_price:.2f} < SMA20({sma_20:.2f}) < SMA50({sma_50:.2f})")
        else:
            signals.append("neutral")
            details.append(f"价格与均线交织: {current_price:.2f}, SMA20({sma_20:.2f}), SMA50({sma_50:.2f})")
        
        # 2. MACD信号
        if macd > macd_signal and macd_histogram > 0:
            signals.append("bullish")
            details.append(f"MACD看涨: MACD({macd:.4f}) > Signal({macd_signal:.4f})")
        elif macd < macd_signal and macd_histogram < 0:
            signals.append("bearish")
            details.append(f"MACD看跌: MACD({macd:.4f}) < Signal({macd_signal:.4f})")
        else:
            signals.append("neutral")
            details.append(f"MACD中性: MACD({macd:.4f}), Signal({macd_signal:.4f})")
        
        # 3. 短期趋势
        recent_prices = prices_df['close'].tail(5).values
        if len(recent_prices) >= 5:
            trend_slope = np.polyfit(range(len(recent_prices)), recent_prices, 1)[0]
            if trend_slope > 0:
                signals.append("bullish")
                details.append(f"短期上升趋势: 斜率 {trend_slope:.4f}")
            elif trend_slope < 0:
                signals.append("bearish")
                details.append(f"短期下降趋势: 斜率 {trend_slope:.4f}")
            else:
                signals.append("neutral")
                details.append("短期趋势平稳")
        
        # 综合信号
        bullish_count = signals.count("bullish")
        bearish_count = signals.count("bearish")
        
        if bullish_count > bearish_count:
            final_signal = "bullish"
        elif bearish_count > bullish_count:
            final_signal = "bearish"
        else:
            final_signal = "neutral"
            
        
        return {
            "signal": final_signal,
            "metrics": {
                "current_price": current_price,
                "sma_20": sma_20,
                "sma_50": sma_50,
                "macd": macd,
                "macd_signal": macd_signal,
                "macd_histogram": macd_histogram,
                "trend_slope": safe_float(np.polyfit(range(len(recent_prices)), recent_prices, 1)[0] if len(recent_prices) >= 5 else 0)
            },
            "signal_breakdown": {
                "bullish_signals": bullish_count,
                "bearish_signals": bearish_count,
                "neutral_signals": signals.count("neutral")
            },
            "details": details,
            "reasoning": f"趋势跟踪分析: {bullish_count}个看涨信号, {bearish_count}个看跌信号"
        }
        
    except Exception as e:
        return {"error": str(e), "signal": "neutral"}


@tool
def analyze_mean_reversion(ticker: str, start_date: str, end_date: str, api_key: str) -> Dict[str, Any]:
    """
    均值回归分析
    
    Args:
        ticker: 股票代码
        start_date: 开始日期
        end_date: 结束日期
        api_key: API密钥
        
    Returns:
        包含均值回归分析结果的字典
    """
    try:
        # 自动扩展历史数据范围以满足技术分析需求
        from datetime import datetime, timedelta
        
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        # 扩展到60天前以确保有足够的历史数据
        extended_start_date = (end_dt - timedelta(days=60)).strftime("%Y-%m-%d")
        
        prices = get_prices(ticker=ticker, start_date=extended_start_date, end_date=end_date, api_key=api_key)
        
        if not prices:
            return {"error": "No price data found", "signal": "neutral"}
        
        prices_df = prices_to_df(prices)
        
        if len(prices_df) < 5:
            return {
                "error": f"Insufficient data for mean reversion analysis: only {len(prices_df)} days available, need at least 5", 
                "signal": "neutral", 
                "data_range": f"Attempted to fetch data from {extended_start_date} to {end_date}"
            }
        elif len(prices_df) < 20:
            print(f"警告: 均值回归分析数据不足，仅有{len(prices_df)}天数据，建议至少20天")
        
        # 计算布林带 - 根据数据长度调整窗口
        window = min(20, len(prices_df) - 2)
        prices_df['SMA'] = prices_df['close'].rolling(window=window).mean()
        prices_df['STD'] = prices_df['close'].rolling(window=window).std()
        prices_df['Upper_Band'] = prices_df['SMA'] + (2 * prices_df['STD'])
        prices_df['Lower_Band'] = prices_df['SMA'] - (2 * prices_df['STD'])
        
        # RSI计算
        delta = prices_df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        prices_df['RSI'] = 100 - (100 / (1 + rs))
        
        # 获取最新值
        current_price = safe_float(prices_df['close'].iloc[-1])
        sma = safe_float(prices_df['SMA'].iloc[-1])
        upper_band = safe_float(prices_df['Upper_Band'].iloc[-1])
        lower_band = safe_float(prices_df['Lower_Band'].iloc[-1])
        rsi = safe_float(prices_df['RSI'].iloc[-1])
        
        signals = []
        details = []
        
        # 1. 布林带信号
        if current_price <= lower_band:
            signals.append("bullish")  # 超卖，可能反弹
            details.append(f"价格触及下轨，超卖: {current_price:.2f} <= {lower_band:.2f}")
        elif current_price >= upper_band:
            signals.append("bearish")  # 超买，可能回调
            details.append(f"价格触及上轨，超买: {current_price:.2f} >= {upper_band:.2f}")
        else:
            signals.append("neutral")
            details.append(f"价格在布林带内: {lower_band:.2f} < {current_price:.2f} < {upper_band:.2f}")
        
        # 2. RSI信号
        if rsi <= 30:
            signals.append("bullish")  # 超卖
            details.append(f"RSI超卖: {rsi:.2f} <= 30")
        elif rsi >= 70:
            signals.append("bearish")  # 超买
            details.append(f"RSI超买: {rsi:.2f} >= 70")
        else:
            signals.append("neutral")
            details.append(f"RSI正常: {rsi:.2f}")
        
        # 3. 价格偏离度
        price_deviation = (current_price - sma) / sma * 100
        if price_deviation <= -5:  # 低于均线5%以上
            signals.append("bullish")
            details.append(f"价格大幅偏离均线下方: {price_deviation:.2f}%")
        elif price_deviation >= 5:  # 高于均线5%以上
            signals.append("bearish")
            details.append(f"价格大幅偏离均线上方: {price_deviation:.2f}%")
        else:
            signals.append("neutral")
            details.append(f"价格接近均线: 偏离 {price_deviation:.2f}%")
        
        # 综合信号
        bullish_count = signals.count("bullish")
        bearish_count = signals.count("bearish")
        
        if bullish_count > bearish_count:
            final_signal = "bullish"
        elif bearish_count > bullish_count:
            final_signal = "bearish"
        else:
            final_signal = "neutral"
            
        
        return {
            "signal": final_signal,
            "metrics": {
                "current_price": current_price,
                "sma": sma,
                "upper_band": upper_band,
                "lower_band": lower_band,
                "rsi": rsi,
                "price_deviation_pct": round(price_deviation, 2)
            },
            "signal_breakdown": {
                "bullish_signals": bullish_count,
                "bearish_signals": bearish_count,
                "neutral_signals": signals.count("neutral")
            },
            "details": details,
            "reasoning": f"均值回归分析: {bullish_count}个看涨信号, {bearish_count}个看跌信号"
        }
        
    except Exception as e:
        return {"error": str(e), "signal": "neutral"}


@tool
def analyze_momentum(ticker: str, start_date: str, end_date: str, api_key: str) -> Dict[str, Any]:
    """
    动量分析
    
    Args:
        ticker: 股票代码
        start_date: 开始日期
        end_date: 结束日期
        api_key: API密钥
        
    Returns:
        包含动量分析结果的字典
    """
    try:
        # 自动扩展历史数据范围以满足技术分析需求
        from datetime import datetime, timedelta
        
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        # 扩展到45天前以确保有足够的历史数据
        extended_start_date = (end_dt - timedelta(days=45)).strftime("%Y-%m-%d")
        
        prices = get_prices(ticker=ticker, start_date=extended_start_date, end_date=end_date, api_key=api_key)
        
        if not prices:
            return {"error": "No price data found", "signal": "neutral"}
        
        prices_df = prices_to_df(prices)
        
        if len(prices_df) < 5:
            return {
                "error": f"Insufficient data for momentum analysis: only {len(prices_df)} days available, need at least 5", 
                "signal": "neutral", 
                "data_range": f"Attempted to fetch data from {extended_start_date} to {end_date}"
            }
        elif len(prices_df) < 20:
            print(f"警告: 动量分析数据不足，仅有{len(prices_df)}天数据，建议至少20天")
        
        # 计算收益率
        prices_df['returns'] = prices_df['close'].pct_change()
        
        # 计算不同期间的动量 - 根据数据长度调整
        data_length = len(prices_df)
        short_period = min(5, data_length // 3)
        medium_period = min(10, data_length // 2)
        long_period = min(20, data_length - 2)
        
        prices_df['momentum_5'] = prices_df['close'] / prices_df['close'].shift(short_period) - 1
        prices_df['momentum_10'] = prices_df['close'] / prices_df['close'].shift(medium_period) - 1
        prices_df['momentum_20'] = prices_df['close'] / prices_df['close'].shift(long_period) - 1
        
        # 获取最新值
        current_price = safe_float(prices_df['close'].iloc[-1])
        momentum_5 = safe_float(prices_df['momentum_5'].iloc[-1])
        momentum_10 = safe_float(prices_df['momentum_10'].iloc[-1])
        momentum_20 = safe_float(prices_df['momentum_20'].iloc[-1])
        
        # 计算近期波动率
        recent_volatility = safe_float(prices_df['returns'].tail(20).std() * np.sqrt(252))
        
        signals = []
        details = []
        
        # 1. 短期动量(5日)
        if momentum_5 > 0.02:  # 5日涨幅超过2%
            signals.append("bullish")
            details.append(f"短期动量强劲: 5日涨幅 {momentum_5*100:.2f}%")
        elif momentum_5 < -0.02:  # 5日跌幅超过2%
            signals.append("bearish")
            details.append(f"短期动量疲弱: 5日跌幅 {momentum_5*100:.2f}%")
        else:
            signals.append("neutral")
            details.append(f"短期动量平稳: 5日变化 {momentum_5*100:.2f}%")
        
        # 2. 中期动量(10日)
        if momentum_10 > 0.05:  # 10日涨幅超过5%
            signals.append("bullish")
            details.append(f"中期动量强劲: 10日涨幅 {momentum_10*100:.2f}%")
        elif momentum_10 < -0.05:  # 10日跌幅超过5%
            signals.append("bearish")
            details.append(f"中期动量疲弱: 10日跌幅 {momentum_10*100:.2f}%")
        else:
            signals.append("neutral")
            details.append(f"中期动量平稳: 10日变化 {momentum_10*100:.2f}%")
        
        # 3. 长期动量(20日)
        if momentum_20 > 0.10:  # 20日涨幅超过10%
            signals.append("bullish")
            details.append(f"长期动量强劲: 20日涨幅 {momentum_20*100:.2f}%")
        elif momentum_20 < -0.10:  # 20日跌幅超过10%
            signals.append("bearish")
            details.append(f"长期动量疲弱: 20日跌幅 {momentum_20*100:.2f}%")
        else:
            signals.append("neutral")
            details.append(f"长期动量平稳: 20日变化 {momentum_20*100:.2f}%")
        
        # 综合信号
        bullish_count = signals.count("bullish")
        bearish_count = signals.count("bearish")
        
        if bullish_count > bearish_count:
            final_signal = "bullish"
        elif bearish_count > bullish_count:
            final_signal = "bearish"
        else:
            final_signal = "neutral"
            
        
        return {
            "signal": final_signal,
            "metrics": {
                "current_price": current_price,
                "momentum_5d_pct": round(momentum_5 * 100, 2),
                "momentum_10d_pct": round(momentum_10 * 100, 2),
                "momentum_20d_pct": round(momentum_20 * 100, 2),
                "recent_volatility": round(recent_volatility * 100, 2)
            },
            "signal_breakdown": {
                "bullish_signals": bullish_count,
                "bearish_signals": bearish_count,
                "neutral_signals": signals.count("neutral")
            },
            "details": details,
            "reasoning": f"动量分析: {bullish_count}个看涨信号, {bearish_count}个看跌信号"
        }
        
    except Exception as e:
        return {"error": str(e), "signal": "neutral"}


@tool
def analyze_volatility(ticker: str, start_date: str, end_date: str, api_key: str) -> Dict[str, Any]:
    """
    波动率分析
    
    Args:
        ticker: 股票代码
        start_date: 开始日期
        end_date: 结束日期
        api_key: API密钥
        
    Returns:
        包含波动率分析结果的字典
    """
    try:
        # 自动扩展历史数据范围以满足技术分析需求
        from datetime import datetime, timedelta
        
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        # 扩展到90天前以确保有足够的历史数据用于波动率计算
        extended_start_date = (end_dt - timedelta(days=90)).strftime("%Y-%m-%d")
        
        prices = get_prices(ticker=ticker, start_date=extended_start_date, end_date=end_date, api_key=api_key)
        
        if not prices:
            return {"error": "No price data found", "signal": "neutral"}
        
        prices_df = prices_to_df(prices)
        
        if len(prices_df) < 5:
            return {
                "error": f"Insufficient data for volatility analysis: only {len(prices_df)} days available, need at least 5", 
                "signal": "neutral", 
                "data_range": f"Attempted to fetch data from {extended_start_date} to {end_date}"
            }
        elif len(prices_df) < 20:
            print(f"警告: 波动率分析数据不足，仅有{len(prices_df)}天数据，建议至少20天")
        
        # 计算收益率
        prices_df['returns'] = prices_df['close'].pct_change()
        
        # 计算不同窗口的波动率 - 根据数据长度调整
        data_length = len(prices_df)
        short_window = min(10, data_length // 2)
        medium_window = min(20, data_length - 2)
        long_window = min(60, data_length - 1) if data_length > 30 else medium_window
        
        prices_df['vol_10'] = prices_df['returns'].rolling(window=short_window).std() * np.sqrt(252)
        prices_df['vol_20'] = prices_df['returns'].rolling(window=medium_window).std() * np.sqrt(252)
        prices_df['vol_60'] = prices_df['returns'].rolling(window=long_window).std() * np.sqrt(252)
        
        # 获取最新值
        current_vol_10 = safe_float(prices_df['vol_10'].iloc[-1])
        current_vol_20 = safe_float(prices_df['vol_20'].iloc[-1])
        current_vol_60 = safe_float(prices_df['vol_60'].iloc[-1])
        current_price = safe_float(prices_df['close'].iloc[-1])
        
        # 计算波动率百分位数
        vol_20_percentile = (prices_df['vol_20'].rank(pct=True).iloc[-1]) * 100
        
        signals = []
        details = []
        
        # 1. 波动率趋势
        if current_vol_10 > current_vol_20 > current_vol_60:
            signals.append("bearish")  # 波动率上升通常是风险信号
            details.append("波动率持续上升，风险增加")
        elif current_vol_10 < current_vol_20 < current_vol_60:
            signals.append("bullish")  # 波动率下降，风险降低
            details.append("波动率持续下降，风险降低")
        else:
            signals.append("neutral")
            details.append("波动率变化不明显")
        
        # 2. 波动率水平
        if current_vol_20 > 0.40:  # 年化波动率超过40%
            signals.append("bearish")
            details.append(f"高波动率环境: {current_vol_20*100:.1f}%")
        elif current_vol_20 < 0.15:  # 年化波动率低于15%
            signals.append("bullish")
            details.append(f"低波动率环境: {current_vol_20*100:.1f}%")
        else:
            signals.append("neutral")
            details.append(f"中等波动率: {current_vol_20*100:.1f}%")
        
        # 3. 波动率百分位数
        if vol_20_percentile > 80:
            signals.append("bearish")
            details.append(f"波动率处于高位: {vol_20_percentile:.1f}百分位")
        elif vol_20_percentile < 20:
            signals.append("bullish")
            details.append(f"波动率处于低位: {vol_20_percentile:.1f}百分位")
        else:
            signals.append("neutral")
            details.append(f"波动率正常: {vol_20_percentile:.1f}百分位")
        
        # 综合信号
        bullish_count = signals.count("bullish")
        bearish_count = signals.count("bearish")
        
        if bullish_count > bearish_count:
            final_signal = "bullish"
        elif bearish_count > bullish_count:
            final_signal = "bearish"
        else:
            final_signal = "neutral"
            
        
        return {
            "signal": final_signal,
            "metrics": {
                "current_price": current_price,
                "volatility_10d": round(current_vol_10 * 100, 2),
                "volatility_20d": round(current_vol_20 * 100, 2),
                "volatility_60d": round(current_vol_60 * 100, 2),
                "volatility_percentile": round(vol_20_percentile, 1)
            },
            "signal_breakdown": {
                "bullish_signals": bullish_count,
                "bearish_signals": bearish_count,
                "neutral_signals": signals.count("neutral")
            },
            "details": details,
            "reasoning": f"波动率分析: {bullish_count}个看涨信号, {bearish_count}个看跌信号"
        }
        
    except Exception as e:
        return {"error": str(e), "signal": "neutral"}


# ===================== 情绪分析工具 =====================

@tool
def analyze_insider_trading(ticker: str, end_date: str, api_key: str, start_date: Optional[str] = None) -> Dict[str, Any]:
    """
    分析内部交易情况
    
    Args:
        ticker: 股票代码
        end_date: 结束日期
        api_key: API密钥
        start_date: 开始日期(可选)
        
    Returns:
        包含内部交易分析结果的字典
    """
    try:
        # 获取内部交易数据
        insider_trades = get_insider_trades(
            ticker=ticker,
            end_date=end_date,
            start_date=start_date,
            limit=1000,
            api_key=api_key,
        )
        
        if not insider_trades:
            # 当没有内部交易数据时，返回中性信号而不是错误
            return {
                "signal": "neutral",
                "metrics": {
                    "total_trades": 0,
                    "buy_trades": 0,
                    "sell_trades": 0,
                    "total_buy_volume": 0,
                    "total_sell_volume": 0,
                    "trade_ratio": 0,
                    "volume_ratio": 0
                },
                "details": ["无可用的内部交易数据"],
                "reasoning": "内部交易分析: 无交易数据，返回中性信号"
            }
        
        # 分析交易信号
        transaction_shares = pd.Series([t.transaction_shares for t in insider_trades]).dropna()
        
        if len(transaction_shares) == 0:
            return {
                "signal": "neutral",
                "metrics": {
                    "total_trades": len(insider_trades),
                    "buy_trades": 0,
                    "sell_trades": 0,
                    "total_buy_volume": 0,
                    "total_sell_volume": 0,
                    "trade_ratio": 0,
                    "volume_ratio": 0
                },
                "details": [f"找到{len(insider_trades)}笔交易，但交易数据无效"],
                "reasoning": "内部交易分析: 交易数据无效，返回中性信号"
            }
        
        # 买入(正数)和卖出(负数)统计
        buy_trades = (transaction_shares > 0).sum()
        sell_trades = (transaction_shares < 0).sum()
        total_trades = len(transaction_shares)
        
        # 按交易量加权
        total_buy_volume = transaction_shares[transaction_shares > 0].sum()
        total_sell_volume = abs(transaction_shares[transaction_shares < 0].sum())
        
        # 生成信号
        if buy_trades > sell_trades and total_buy_volume > total_sell_volume:
            signal = "bullish"
        elif sell_trades > buy_trades and total_sell_volume > total_buy_volume:
            signal = "bearish"
        else:
            signal = "neutral"
            
        
        return {
            "signal": signal,
            "metrics": {
                "total_trades": total_trades,
                "buy_trades": buy_trades,
                "sell_trades": sell_trades,
                "total_buy_volume": float(total_buy_volume),
                "total_sell_volume": float(total_sell_volume),
                "trade_ratio": round(buy_trades / max(sell_trades, 1), 2),
                "volume_ratio": round(total_buy_volume / max(total_sell_volume, 1), 2)
            },
            "details": [
                f"总交易数: {total_trades}",
                f"买入交易: {buy_trades} ({buy_trades/total_trades*100:.1f}%)",
                f"卖出交易: {sell_trades} ({sell_trades/total_trades*100:.1f}%)",
                f"买入量: {total_buy_volume:,.0f}",
                f"卖出量: {total_sell_volume:,.0f}"
            ],
            "reasoning": f"内部交易分析: {'买入占优' if signal == 'bullish' else '卖出占优' if signal == 'bearish' else '中性'}"
        }
        
    except Exception as e:
        return {"error": str(e), "signal": "neutral"}


@tool
def analyze_news_sentiment(ticker: str, end_date: str, api_key: str, start_date: Optional[str] = None) -> Dict[str, Any]:
    """
    分析新闻情绪
    
    Args:
        ticker: 股票代码
        end_date: 结束日期
        api_key: API密钥
        start_date: 开始日期(可选)
        
    Returns:
        包含新闻情绪分析结果的字典
    """
    try:
        # 获取公司新闻
        company_news = get_company_news(
            ticker=ticker,
            end_date=end_date,
            start_date=start_date,
            limit=100,
            api_key=api_key
        )
        
        if not company_news:
            # 当没有新闻数据时，返回中性信号而不是错误
            return {
                "signal": "neutral", 
                "metrics": {
                    "total_articles": 0,
                    "positive_articles": 0,
                    "negative_articles": 0,
                    "neutral_articles": 0,
                    "positive_ratio": 0,
                    "negative_ratio": 0,
                    "neutral_ratio": 0
                },
                "details": ["无可用的公司新闻数据"],
                "reasoning": "新闻情绪分析: 无新闻数据，返回中性信号"
            }
        
        # 分析情绪
        sentiment_data = pd.Series([n.sentiment for n in company_news]).dropna()
        
        if len(sentiment_data) == 0:
            # 当情绪数据无效时，也返回中性信号
            return {
                "signal": "neutral", 
                "metrics": {
                    "total_articles": len(company_news),
                    "positive_articles": 0,
                    "negative_articles": 0,
                    "neutral_articles": 0,
                    "positive_ratio": 0,
                    "negative_ratio": 0,
                    "neutral_ratio": 0
                },
                "details": [f"找到{len(company_news)}篇新闻，但情绪数据无效"],
                "reasoning": "新闻情绪分析: 情绪数据无效，返回中性信号"
            }
        
        # 统计各种情绪
        positive_count = (sentiment_data == "positive").sum()
        negative_count = (sentiment_data == "negative").sum()
        neutral_count = (sentiment_data == "neutral").sum()
        total_count = len(sentiment_data)
        
        # 生成信号
        if positive_count > negative_count:
            signal = "bullish"
            dominant_count = positive_count
        elif negative_count > positive_count:
            signal = "bearish"
            dominant_count = negative_count
        else:
            signal = "neutral"
            dominant_count = max(positive_count, negative_count)
            
        
        return {
            "signal": signal,
            "metrics": {
                "total_articles": total_count,
                "positive_articles": positive_count,
                "negative_articles": negative_count,
                "neutral_articles": neutral_count,
                "positive_ratio": round(positive_count / total_count * 100, 1),
                "negative_ratio": round(negative_count / total_count * 100, 1),
                "neutral_ratio": round(neutral_count / total_count * 100, 1)
            },
            "details": [
                f"总新闻数: {total_count}",
                f"正面新闻: {positive_count} ({positive_count/total_count*100:.1f}%)",
                f"负面新闻: {negative_count} ({negative_count/total_count*100:.1f}%)",
                f"中性新闻: {neutral_count} ({neutral_count/total_count*100:.1f}%)"
            ],
            "reasoning": f"新闻情绪分析: {'正面情绪占优' if signal == 'bullish' else '负面情绪占优' if signal == 'bearish' else '情绪中性'}"
        }
        
    except Exception as e:
        return {"error": str(e), "signal": "neutral"}


# ===================== 估值分析工具 =====================

@tool
def dcf_valuation_analysis(ticker: str, end_date: str, api_key: str) -> Dict[str, Any]:
    """
    折现现金流(DCF)估值分析
    
    Args:
        ticker: 股票代码
        end_date: 结束日期
        api_key: API密钥
        
    Returns:
        包含DCF估值分析结果的字典
    """
    try:
        # 获取财务指标
        financial_metrics = get_financial_metrics(
            ticker=ticker,
            end_date=end_date,
            period="ttm",
            limit=8,
            api_key=api_key,
        )
        
        if not financial_metrics:
            return {"error": "No financial metrics found", "signal": "neutral"}
        
        most_recent = financial_metrics[0]
        
        # 获取现金流数据
        line_items = search_line_items(
            ticker=ticker,
            line_items=["free_cash_flow"],
            end_date=end_date,
            period="ttm",
            limit=2,
            api_key=api_key,
        )
        
        if not line_items:
            return {"error": "No cash flow data found", "signal": "neutral"}
        
        current_fcf = line_items[0].free_cash_flow
        if not current_fcf or current_fcf <= 0:
            return {"error": "Invalid free cash flow data", "signal": "neutral"}
        
        # 获取市值
        market_cap = get_market_cap(ticker, end_date, api_key=api_key)
        if not market_cap:
            return {"error": "Market cap unavailable", "signal": "neutral"}
        
        # DCF估值计算
        growth_rate = most_recent.earnings_growth or 0.05
        discount_rate = 0.10
        terminal_growth_rate = 0.03
        num_years = 5
        
        # 计算未来现金流现值
        pv_fcf = 0.0
        for year in range(1, num_years + 1):
            future_fcf = current_fcf * (1 + growth_rate) ** year
            pv_fcf += future_fcf / (1 + discount_rate) ** year
        
        # 计算终值
        terminal_fcf = current_fcf * (1 + growth_rate) ** num_years * (1 + terminal_growth_rate)
        terminal_value = terminal_fcf / (discount_rate - terminal_growth_rate)
        pv_terminal = terminal_value / (1 + discount_rate) ** num_years
        
        # 企业价值
        enterprise_value = pv_fcf + pv_terminal
        
        # 计算价值差距
        value_gap = (enterprise_value - market_cap) / market_cap
        
        # 生成信号
        if value_gap > 0.20:  # 低估超过20%
            signal = "bullish"
        elif value_gap < -0.20:  # 高估超过20%
            signal = "bearish"
        else:
            signal = "neutral"
        
        
        return {
            "signal": signal,
            "valuation": {
                "enterprise_value": enterprise_value,
                "market_cap": market_cap,
                "value_gap_pct": round(value_gap * 100, 2),
                "current_fcf": current_fcf,
                "growth_rate": growth_rate,
                "discount_rate": discount_rate
            },
            "details": [
                f"企业价值: ${enterprise_value:,.0f}",
                f"市值: ${market_cap:,.0f}",
                f"价值差距: {value_gap*100:.1f}%",
                f"自由现金流: ${current_fcf:,.0f}",
                f"增长率假设: {growth_rate*100:.1f}%"
            ],
            "reasoning": f"DCF估值: {'低估' if signal == 'bullish' else '高估' if signal == 'bearish' else '合理'} {abs(value_gap)*100:.1f}%"
        }
        
    except Exception as e:
        return {"error": str(e), "signal": "neutral"}


@tool
def owner_earnings_valuation_analysis(ticker: str, end_date: str, api_key: str) -> Dict[str, Any]:
    """
    巴菲特式所有者收益估值分析
    
    Args:
        ticker: 股票代码
        end_date: 结束日期
        api_key: API密钥
        
    Returns:
        包含所有者收益估值分析结果的字典
    """
    try:
        # 获取财务指标
        financial_metrics = get_financial_metrics(
            ticker=ticker,
            end_date=end_date,
            period="ttm",
            limit=8,
            api_key=api_key,
        )
        
        if not financial_metrics:
            return {"error": "No financial metrics found", "signal": "neutral"}
        
        most_recent = financial_metrics[0]
        
        # 获取详细财务数据
        line_items = search_line_items(
            ticker=ticker,
            line_items=[
                "net_income",
                "depreciation_and_amortization", 
                "capital_expenditure",
                "working_capital",
            ],
            end_date=end_date,
            period="ttm",
            limit=2,
            api_key=api_key,
        )
        
        if len(line_items) < 2:
            return {"error": "Insufficient financial data", "signal": "neutral"}
        
        current, previous = line_items[0], line_items[1]
        
        # 计算所有者收益
        net_income = current.net_income or 0
        depreciation = current.depreciation_and_amortization or 0
        capex = current.capital_expenditure or 0
        wc_change = (current.working_capital or 0) - (previous.working_capital or 0)
        
        owner_earnings = net_income + depreciation - capex - wc_change
        
        if owner_earnings <= 0:
            return {"error": "Negative owner earnings", "signal": "neutral"}
        
        # 获取市值
        market_cap = get_market_cap(ticker, end_date, api_key=api_key)
        if not market_cap:
            return {"error": "Market cap unavailable", "signal": "neutral"}
        
        # 估值计算
        growth_rate = most_recent.earnings_growth or 0.05
        required_return = 0.15
        margin_of_safety = 0.25
        num_years = 5
        
        # 计算未来所有者收益现值
        pv_earnings = 0.0
        for year in range(1, num_years + 1):
            future_earnings = owner_earnings * (1 + growth_rate) ** year
            pv_earnings += future_earnings / (1 + required_return) ** year
        
        # 终值计算
        terminal_growth = min(growth_rate, 0.03)
        terminal_earnings = owner_earnings * (1 + growth_rate) ** num_years * (1 + terminal_growth)
        terminal_value = terminal_earnings / (required_return - terminal_growth)
        pv_terminal = terminal_value / (1 + required_return) ** num_years
        
        # 内在价值（含安全边际）
        intrinsic_value = (pv_earnings + pv_terminal) * (1 - margin_of_safety)
        
        # 价值差距
        value_gap = (intrinsic_value - market_cap) / market_cap
        
        # 生成信号
        if value_gap > 0.25:  # 低估超过25%
            signal = "bullish"
        elif value_gap < -0.25:  # 高估超过25%
            signal = "bearish"
        else:
            signal = "neutral"
        
        
        return {
            "signal": signal,
            "valuation": {
                "intrinsic_value": intrinsic_value,
                "market_cap": market_cap,
                "value_gap_pct": round(value_gap * 100, 2),
                "owner_earnings": owner_earnings,
                "growth_rate": growth_rate,
                "required_return": required_return,
                "margin_of_safety": margin_of_safety
            },
            "components": {
                "net_income": net_income,
                "depreciation": depreciation,
                "capex": capex,
                "wc_change": wc_change
            },
            "details": [
                f"内在价值: ${intrinsic_value:,.0f}",
                f"市值: ${market_cap:,.0f}",
                f"价值差距: {value_gap*100:.1f}%",
                f"所有者收益: ${owner_earnings:,.0f}",
                f"安全边际: {margin_of_safety*100:.0f}%"
            ],
            "reasoning": f"所有者收益估值: {'低估' if signal == 'bullish' else '高估' if signal == 'bearish' else '合理'} {abs(value_gap)*100:.1f}%"
        }
        
    except Exception as e:
        return {"error": str(e), "signal": "neutral"}


@tool  
def ev_ebitda_valuation_analysis(ticker: str, end_date: str, api_key: str) -> Dict[str, Any]:
    """
    EV/EBITDA倍数估值分析
    
    Args:
        ticker: 股票代码
        end_date: 结束日期
        api_key: API密钥
        
    Returns:
        包含EV/EBITDA估值分析结果的字典
    """
    try:
        # 获取财务指标
        financial_metrics = get_financial_metrics(
            ticker=ticker,
            end_date=end_date,
            period="ttm",
            limit=8,
            api_key=api_key,
        )
        
        if not financial_metrics:
            return {"error": "No financial metrics found", "signal": "neutral"}
        
        most_recent = financial_metrics[0]
        
        # 检查必需数据
        if not (most_recent.enterprise_value and most_recent.enterprise_value_to_ebitda_ratio):
            return {"error": "Missing EV/EBITDA data", "signal": "neutral"}
        
        if most_recent.enterprise_value_to_ebitda_ratio <= 0:
            return {"error": "Invalid EV/EBITDA ratio", "signal": "neutral"}
        
        # 获取市值
        market_cap = get_market_cap(ticker, end_date, api_key=api_key)
        if not market_cap:
            return {"error": "Market cap unavailable", "signal": "neutral"}
        
        # 计算当前EBITDA
        current_ebitda = most_recent.enterprise_value / most_recent.enterprise_value_to_ebitda_ratio
        
        # 计算历史中位数倍数
        valid_multiples = [
            m.enterprise_value_to_ebitda_ratio 
            for m in financial_metrics 
            if m.enterprise_value_to_ebitda_ratio and m.enterprise_value_to_ebitda_ratio > 0
        ]
        
        if len(valid_multiples) < 3:
            return {"error": "Insufficient historical data", "signal": "neutral"}
        
        median_multiple = median(valid_multiples)
        current_multiple = most_recent.enterprise_value_to_ebitda_ratio
        
        # 基于中位数倍数的隐含企业价值
        implied_ev = median_multiple * current_ebitda
        
        # 计算净债务
        net_debt = (most_recent.enterprise_value or 0) - (market_cap or 0)
        
        # 隐含股权价值
        implied_equity_value = max(implied_ev - net_debt, 0)
        
        # 价值差距
        value_gap = (implied_equity_value - market_cap) / market_cap if market_cap > 0 else 0
        
        # 倍数比较
        multiple_discount = (median_multiple - current_multiple) / median_multiple
        
        # 生成信号
        if value_gap > 0.15 and multiple_discount > 0.10:  # 低估且倍数折价
            signal = "bullish"
        elif value_gap < -0.15 and multiple_discount < -0.10:  # 高估且倍数溢价
            signal = "bearish"
        else:
            signal = "neutral"
        
        
        return {
            "signal": signal,
            "valuation": {
                "implied_equity_value": implied_equity_value,
                "market_cap": market_cap,
                "value_gap_pct": round(value_gap * 100, 2),
                "current_multiple": current_multiple,
                "median_multiple": median_multiple,
                "multiple_discount_pct": round(multiple_discount * 100, 2),
                "current_ebitda": current_ebitda
            },
            "details": [
                f"隐含股权价值: ${implied_equity_value:,.0f}",
                f"市值: ${market_cap:,.0f}",
                f"价值差距: {value_gap*100:.1f}%",
                f"当前EV/EBITDA: {current_multiple:.1f}x",
                f"历史中位数: {median_multiple:.1f}x",
                f"倍数折价: {multiple_discount*100:.1f}%"
            ],
            "reasoning": f"EV/EBITDA估值: {'低估' if signal == 'bullish' else '高估' if signal == 'bearish' else '合理'}"
        }
        
    except Exception as e:
        return {"error": str(e), "signal": "neutral"}


@tool
def residual_income_valuation_analysis(ticker: str, end_date: str, api_key: str) -> Dict[str, Any]:
    """
    剩余收益模型(RIM)估值分析
    
    Args:
        ticker: 股票代码
        end_date: 结束日期
        api_key: API密钥
        
    Returns:
        包含剩余收益估值分析结果的字典
    """
    try:
        # 获取财务指标
        financial_metrics = get_financial_metrics(
            ticker=ticker,
            end_date=end_date,
            period="ttm",
            limit=8,
            api_key=api_key,
        )
        
        if not financial_metrics:
            return {"error": "No financial metrics found", "signal": "neutral"}
        
        most_recent = financial_metrics[0]
        
        # 获取净利润数据
        line_items = search_line_items(
            ticker=ticker,
            line_items=["net_income"],
            end_date=end_date,
            period="ttm",
            limit=1,
            api_key=api_key,
        )
        
        if not line_items or not line_items[0].net_income:
            return {"error": "No net income data", "signal": "neutral"}
        
        net_income = line_items[0].net_income
        
        # 获取市值
        market_cap = get_market_cap(ticker, end_date, api_key=api_key)
        if not market_cap:
            return {"error": "Market cap unavailable", "signal": "neutral"}
        
        # 检查必需数据
        pb_ratio = most_recent.price_to_book_ratio
        if not pb_ratio or pb_ratio <= 0:
            return {"error": "Invalid P/B ratio", "signal": "neutral"}
        
        # 计算账面价值
        book_value = market_cap / pb_ratio
        
        # 模型参数
        cost_of_equity = 0.10
        book_value_growth = most_recent.book_value_growth or 0.03
        terminal_growth_rate = 0.03
        num_years = 5
        margin_of_safety = 0.20
        
        # 计算初始剩余收益
        initial_residual_income = net_income - cost_of_equity * book_value
        
        if initial_residual_income <= 0:
            return {"error": "Negative residual income", "signal": "neutral"}
        
        # 计算未来剩余收益现值
        pv_residual_income = 0.0
        for year in range(1, num_years + 1):
            future_ri = initial_residual_income * (1 + book_value_growth) ** year
            pv_residual_income += future_ri / (1 + cost_of_equity) ** year
        
        # 终值
        terminal_ri = initial_residual_income * (1 + book_value_growth) ** (num_years + 1)
        terminal_value = terminal_ri / (cost_of_equity - terminal_growth_rate)
        pv_terminal = terminal_value / (1 + cost_of_equity) ** num_years
        
        # 内在价值
        intrinsic_value = (book_value + pv_residual_income + pv_terminal) * (1 - margin_of_safety)
        
        # 价值差距
        value_gap = (intrinsic_value - market_cap) / market_cap
        
        # 生成信号
        if value_gap > 0.20:  # 低估超过20%
            signal = "bullish"
        elif value_gap < -0.20:  # 高估超过20%
            signal = "bearish"
        else:
            signal = "neutral"
        
        
        return {
            "signal": signal,
            "valuation": {
                "intrinsic_value": intrinsic_value,
                "market_cap": market_cap,
                "value_gap_pct": round(value_gap * 100, 2),
                "book_value": book_value,
                "residual_income": initial_residual_income,
                "cost_of_equity": cost_of_equity,
                "book_value_growth": book_value_growth,
                "margin_of_safety": margin_of_safety
            },
            "details": [
                f"内在价值: ${intrinsic_value:,.0f}",
                f"市值: ${market_cap:,.0f}",
                f"价值差距: {value_gap*100:.1f}%",
                f"账面价值: ${book_value:,.0f}",
                f"剩余收益: ${initial_residual_income:,.0f}",
                f"安全边际: {margin_of_safety*100:.0f}%"
            ],
            "reasoning": f"剩余收益估值: {'低估' if signal == 'bullish' else '高估' if signal == 'bearish' else '合理'} {abs(value_gap)*100:.1f}%"
        }
        
    except Exception as e:
        return {"error": str(e), "signal": "neutral"}
