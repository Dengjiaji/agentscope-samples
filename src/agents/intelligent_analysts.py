"""
智能分析师代理函数
使用LLM进行工具选择的新一代分析师
"""

import asyncio
from langchain_core.messages import HumanMessage
from src.graph.state import AgentState, show_agent_reasoning
from src.utils.api_key import get_api_key_from_state
from src.utils.progress import progress
from src.llm.models import get_model, ModelProvider
import json
from typing import Dict, Any

from src.agents.intelligent_analyst_base import (
    IntelligentFundamentalAnalyst,
    IntelligentTechnicalAnalyst,
    IntelligentSentimentAnalyst,
    IntelligentValuationAnalyst,
    IntelligentComprehensiveAnalyst
)


def intelligent_fundamentals_analyst_agent(state: AgentState, agent_id: str = "fundamentals_analyst_agent"):
    """智能基本面分析师代理函数"""
    return _run_intelligent_analyst(state, agent_id, IntelligentFundamentalAnalyst())


def intelligent_technical_analyst_agent(state: AgentState, agent_id: str = "technical_analyst_agent"):
    """智能技术分析师代理函数"""
    return _run_intelligent_analyst(state, agent_id, IntelligentTechnicalAnalyst())


def intelligent_sentiment_analyst_agent(state: AgentState, agent_id: str = "sentiment_analyst_agent"):
    """智能情绪分析师代理函数"""
    return _run_intelligent_analyst(state, agent_id, IntelligentSentimentAnalyst())


def intelligent_valuation_analyst_agent(state: AgentState, agent_id: str = "valuation_analyst_agent"):
    """智能估值分析师代理函数"""
    return _run_intelligent_analyst(state, agent_id, IntelligentValuationAnalyst())


def intelligent_comprehensive_analyst_agent(state: AgentState, agent_id: str = "comprehensive_analyst_agent"):
    """智能综合分析师代理函数"""
    return _run_intelligent_analyst(state, agent_id, IntelligentComprehensiveAnalyst())


def _run_intelligent_analyst(state: AgentState, agent_id: str, analyst_instance) -> Dict[str, Any]:
    """运行智能分析师的通用函数"""
    
    data = state["data"]
    start_date = data.get("start_date")
    end_date = data["end_date"]
    tickers = data["tickers"]
    api_key = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")
    
    # 简化的API密钥获取验证
    # print(f"API密钥状态: {'有效' if api_key else '无效'}")  # 已禁用
    
    # 如果仍然无效，尝试环境变量作为后备
    if not api_key:
        import os
        api_key = os.getenv("FINANCIAL_DATASETS_API_KEY")
        if api_key:
            # print(f"使用环境变量API密钥")  # 已禁用
            pass  # 添加pass语句以避免缩进错误
        else:
            print(f"错误: 无法获取FINANCIAL_DATASETS_API_KEY，工具执行将失败")
    
    # 获取LLM
    llm = None
    try:
        llm = get_model(
            model_name=state["metadata"]['model_name'],
            model_provider=state['metadata']['model_provider'],
            api_keys=state['data']['api_keys']
        )
    except Exception as e:
        print(f"警告: 无法获取LLM模型，将使用默认工具选择: {e}")
    
    # 执行分析
    analysis_results = {}
    
    for ticker in tickers:
        progress.update_status(agent_id, ticker, f"开始{analyst_instance.analyst_persona}智能分析")
        
        # 生成市场条件
        market_conditions = _generate_market_conditions_from_state(state, ticker)
        
        # 设置分析目标
        analysis_objective = f"作为专业{analyst_instance.analyst_persona}，对股票{ticker}进行全面深入的投资分析"
        
        
        
        # 在当前线程中创建新的事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # print(f"{analyst_instance.analyst_persona} 创建新的事件循环进行异步分析")  # 已禁用
        result = loop.run_until_complete(
            analyst_instance.analyze_with_llm_tool_selection(
                ticker, end_date, api_key, start_date, llm, analysis_objective
            )
        )
        
        
        # 清理事件循环
        loop.close()
        asyncio.set_event_loop(None)
                    
                
            
        
        
        analysis_results[ticker] = result
            
        progress.update_status(agent_id, ticker, "完成",
                                analysis=json.dumps(result, indent=2, default=str))

    # 创建消息
    message = HumanMessage(
        content=json.dumps(analysis_results, default=str),
        name=agent_id,
    )
    
    # 显示推理过程
    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(analysis_results, f"{analyst_instance.analyst_persona} (LLM智能选择)")
    
    # 更新状态
    state["data"]["analyst_signals"][agent_id] = analysis_results
    
    progress.update_status(agent_id, None, f"所有{analyst_instance.analyst_persona}分析完成")
    
    return {
        "messages": [message],
        "data": data,
    }



# def _display_analysis_summary(analyst_name: str, ticker: str, analysis_result: Dict[str, Any]):
#     """统一显示分析摘要 - 适用于同步和异步版本"""
#     print(f"\n{'='*50}")
#     print(f"{analyst_name} | {ticker} 分析摘要")
#     print(f"{'='*50}")
    
#     # 工具选择信息（增加兜底策略文本）
#     if "tool_selection" in analysis_result:
#         tool_selection = analysis_result["tool_selection"]
#         analysis_strategy_text = tool_selection.get('analysis_strategy') or "基于当前市场环境与分析目标，优先采用所列工具并按权重综合信号。"
#         print(f"分析策略: {analysis_strategy_text}")
#         print(f"🌍 市场考虑: {tool_selection.get('market_considerations', 'N/A')}")
#         print(f"选择工具: {tool_selection.get('tool_count', 0)}个")
        
#         # 显示选择的工具
#         if "selected_tools" in tool_selection:
#             for tool in tool_selection["selected_tools"]:
#                 print(f"   • {tool['tool_name']:<25} {tool.get('reason', '')[:50]}")
    
#     # 工具执行结果
#     if "tool_analysis" in analysis_result:
#         tool_analysis = analysis_result["tool_analysis"]
#         successful = tool_analysis.get("successful_tools", 0)
#         failed = tool_analysis.get("failed_tools", 0)
#         if failed == 0:
#             print(f"\n执行结果: {successful}个成功")
#         else:
#             print(f"\n执行结果: {successful}个成功  {failed}个失败")
#         # 显示每个工具的结果
#         tool_results = tool_analysis.get("tool_results", [])
#         for result in tool_results:
#             if "error" not in result:
#                 signal_emoji = {"bullish": "🟢", "bearish": "🔴", "neutral": "⚪"}.get(result.get('signal'), "❓")
#                 confidence = result.get('confidence', 0)
#                 conf_bar = "█" * int(confidence / 20)
#                 print(f"   {signal_emoji} {result.get('tool_name', 'Unknown'):<20} {result.get('signal', 'unknown').upper():<8} {confidence:>3}% {conf_bar}")
#             else:
#                 error_short = result.get('error', 'Unknown')[:30] + "..." if len(result.get('error', '')) > 30 else result.get('error', 'Unknown')
#                 print(f"   失败: {result.get('tool_name', 'Unknown'):<20} {error_short}")
    
#     # 最终信号
#     final_signal = analysis_result.get('signal', 'unknown')
#     final_confidence = analysis_result.get('confidence', 0)
#     signal_emoji = {"bullish": "🟢", "bearish": "🔴", "neutral": "⚪"}.get(final_signal, "❓")
    
#     print(f"\n最终信号: {final_signal.upper()} (置信度: {final_confidence}%)")
    
#     # 信号分布（如果有的话）
#     if "tool_analysis" in analysis_result and "synthesis_details" in analysis_result["tool_analysis"]:
#         synthesis_details = analysis_result["tool_analysis"]["synthesis_details"]
#         if "signal_distribution" in synthesis_details:
#             distribution = synthesis_details["signal_distribution"]
#             total_tools = sum(distribution.values())
#             if total_tools > 0:
#                 print(f"工具信号分布:")
#                 for signal, count in distribution.items():
#                     percentage = (count / total_tools) * 100
#                     signal_emoji = {"bullish": "🟢", "bearish": "🔴", "neutral": "⚪"}.get(signal, "❓")
#                     bar = "█" * int(percentage / 5)  # 每5%一个方块
#                     print(f"   {signal_emoji} {signal}: {count}个工具 ({percentage:4.1f}%) {bar}")
        
#         # 显示综合方法
#         synthesis_method = synthesis_details.get("synthesis_method", "unknown")
#         if synthesis_method != "unknown":
#             method_desc = {
#                 "llm_based": "🤖 LLM智能综合",
#                 "fallback_majority_vote": "📊 多数投票",
#                 "fallback_no_data": "⚠️ 无数据降级"
#             }.get(synthesis_method, synthesis_method)
#             print(f"综合方法: {method_desc}")
    
#     print(f"{'='*50}\n")


def _generate_market_conditions_from_state(state: AgentState, ticker: str) -> Dict[str, Any]:
    """从状态中生成市场条件"""
    data = state.get("data", {})
    metadata = state.get("metadata", {})
    
    market_conditions = {
        "analysis_date": data.get("end_date", "unknown"),
        "time_period": f"{data.get('start_date', 'unknown')} to {data.get('end_date', 'unknown')}",
        "multi_ticker_analysis": len(data.get("tickers", [])) > 1,
        "session_type": "multi_day" if metadata.get("session_id", "").startswith("multi_day") else "single_day",
        "ticker": ticker
    }
    
    # 从之前的分析师结果中推断市场条件
    analyst_signals = data.get("analyst_signals", {})
    
    # 分析技术指标推断波动率环境
    tech_signals = analyst_signals.get("technical_analyst_agent", {})
    if tech_signals and ticker in tech_signals:
        ticker_analysis = tech_signals[ticker]
        if isinstance(ticker_analysis, dict) and "reasoning" in ticker_analysis:
            reasoning = ticker_analysis["reasoning"]
            if isinstance(reasoning, dict):
                volatility_info = reasoning.get("tool_breakdown", {}).get("analyze_volatility", {})
                if volatility_info and "key_data" in volatility_info:
                    vol_20d = volatility_info["key_data"].get("volatility_20d", 0)
                    if vol_20d > 30:
                        market_conditions["volatility_regime"] = "high"
                    elif vol_20d < 15:
                        market_conditions["volatility_regime"] = "low"
                    else:
                        market_conditions["volatility_regime"] = "normal"
    
    # 分析情绪指标推断市场情绪
    sentiment_signals = analyst_signals.get("sentiment_analyst_agent", {})
    if sentiment_signals and ticker in sentiment_signals:
        ticker_analysis = sentiment_signals[ticker]
        if isinstance(ticker_analysis, dict) and ticker_analysis.get("signal"):
            if ticker_analysis["signal"] == "bullish" and ticker_analysis.get("confidence", 0) > 70:
                market_conditions["market_sentiment"] = "positive"
            elif ticker_analysis["signal"] == "bearish" and ticker_analysis.get("confidence", 0) > 70:
                market_conditions["market_sentiment"] = "negative"
            else:
                market_conditions["market_sentiment"] = "neutral"
    
    # 设置默认值
    if "volatility_regime" not in market_conditions:
        market_conditions["volatility_regime"] = "normal"
    if "market_sentiment" not in market_conditions:
        market_conditions["market_sentiment"] = "neutral"
    
    market_conditions["interest_rate"] = "normal"  # 可以根据实际情况调整
    market_conditions["news_rich_environment"] = True
    market_conditions["insider_activity_level"] = "normal"
    
    return market_conditions
