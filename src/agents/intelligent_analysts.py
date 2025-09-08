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
    print(f"🔑 API密钥状态: {'✅ 有效' if api_key else '❌ 无效'}")
    
    # 如果仍然无效，尝试环境变量作为后备
    if not api_key:
        import os
        api_key = os.getenv("FINANCIAL_DATASETS_API_KEY")
        if api_key:
            print(f"🔄 使用环境变量API密钥")
        else:
            print(f"❌ 无法获取FINANCIAL_DATASETS_API_KEY，工具执行将失败")
    
    # 获取LLM
    llm = None
    try:
        llm = get_model(
            model_name=state["metadata"]['model_name'],
            model_provider=state['metadata']['model_provider'],
            api_keys=state['data']['api_keys']
        )
    except Exception as e:
        print(f"⚠️ 无法获取LLM模型，将使用默认工具选择: {e}")
    
    # 执行分析
    analysis_results = {}
    
    for ticker in tickers:
        progress.update_status(agent_id, ticker, f"开始{analyst_instance.analyst_persona}智能分析")
        
        try:
            # 生成市场条件
            market_conditions = _generate_market_conditions_from_state(state, ticker)
            
            # 设置分析目标
            analysis_objective = f"作为专业{analyst_instance.analyst_persona}，对股票{ticker}进行全面深入的投资分析"
            
            # 在多线程环境中正确处理异步调用
            if llm:
                try:
                    # 检查当前线程是否有事件循环
                    try:
                        # 尝试获取当前线程的事件循环
                        loop = asyncio.get_running_loop()
                        # 如果成功获取到运行中的事件循环，说明我们在异步上下文中
                        # 这种情况下不能使用 run_until_complete，需要使用同步版本
                        print(f"🔄 {analyst_instance.analyst_persona} 检测到运行中的事件循环，使用同步版本进行分析")
                        result = _sync_analyze_with_llm_tool_selection(
                            analyst_instance, ticker, end_date, api_key, start_date, llm, 
                            analysis_objective, market_conditions
                        )
                    except RuntimeError:
                        # 没有运行中的事件循环，我们可以创建一个新的
                        try:
                            # 在当前线程中创建新的事件循环
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            
                            print(f"🔄 {analyst_instance.analyst_persona} 创建新的事件循环进行异步分析")
                            result = loop.run_until_complete(
                                analyst_instance.analyze_with_llm_tool_selection(
                                    ticker, end_date, api_key, start_date, llm, analysis_objective
                                )
                            )
                            
                            # 显示异步分析结果
                            _display_analysis_summary(analyst_instance.analyst_persona, ticker, result)
                            
                            # 清理事件循环
                            loop.close()
                            asyncio.set_event_loop(None)
                            
                        except Exception as async_error:
                            print(f"⚠️ 异步调用失败，降级到同步版本: {async_error}")
                            result = _sync_analyze_with_llm_tool_selection(
                                analyst_instance, ticker, end_date, api_key, start_date, llm, 
                                analysis_objective, market_conditions
                            )
                except Exception as e:
                    print(f"⚠️ 事件循环处理失败，使用同步版本: {e}")
                    result = _sync_analyze_with_llm_tool_selection(
                        analyst_instance, ticker, end_date, api_key, start_date, llm, 
                        analysis_objective, market_conditions
                    )
            else:
                # 没有LLM时使用同步版本
                result = _sync_analyze_with_llm_tool_selection(
                    analyst_instance, ticker, end_date, api_key, start_date, None, 
                    analysis_objective, market_conditions
                )
            
            analysis_results[ticker] = result
            
            progress.update_status(agent_id, ticker, "完成",
                                 analysis=json.dumps(result, indent=2, default=str))
            
        except Exception as e:
            analysis_results[ticker] = {
                "signal": "neutral",
                "confidence": 0,
                "error": str(e),
                "reasoning": {"summary": f"{analyst_instance.analyst_persona}分析失败: {str(e)}"}
            }
            progress.update_status(agent_id, ticker, f"失败: {str(e)}")
    
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


def _sync_analyze_with_llm_tool_selection(analyst_instance, ticker: str, end_date: str, api_key: str,
                                        start_date: str, llm, analysis_objective: str, 
                                        market_conditions: Dict[str, Any]) -> Dict[str, Any]:
    """同步版本的LLM工具选择分析"""
    
    progress.update_status(f"{analyst_instance.analyst_persona.lower()}_agent", ticker, "开始智能工具选择")
    
    try:
        # 1. 使用LLM选择工具
        if llm:
            print(f"🤖 {analyst_instance.analyst_persona} 使用LLM智能选择工具...")
            print(f"   市场条件: {market_conditions}")
            selection_result = _sync_select_tools_with_llm(
                analyst_instance.tool_selector, llm, analyst_instance.analyst_persona, 
                ticker, market_conditions, analysis_objective
            )
            print(f"   LLM选择策略: {selection_result.get('analysis_strategy', 'N/A')}")
        else:
            print(f"⚠️ {analyst_instance.analyst_persona} 使用默认工具选择 (无LLM)")
            # 降级到默认选择
            selection_result = analyst_instance.tool_selector._get_default_tool_selection(analyst_instance.analyst_persona)
        
        progress.update_status(f"{analyst_instance.analyst_persona.lower()}_agent", ticker, 
                             f"选择了{selection_result['tool_count']}个工具")
        
        # 2. 执行选定的工具
        if not api_key:
            print(f"❌ {analyst_instance.analyst_persona} API密钥无效，工具执行将失败")
            
        tool_results = analyst_instance.tool_selector.execute_selected_tools(
            selection_result["selected_tools"],
            ticker=ticker,
            api_key=api_key,
            start_date=start_date,
            end_date=end_date
        )
        
        # 3. 组合工具结果
        
        progress.update_status(f"{analyst_instance.analyst_persona.lower()}_agent", ticker, "组合分析信号")
        combined_result = analyst_instance.tool_selector.combine_tool_results(tool_results)
        
        # 4. 生成详细推理
        detailed_reasoning = ""
        if llm:
            progress.update_status(f"{analyst_instance.analyst_persona.lower()}_agent", ticker, "生成详细推理")
            detailed_reasoning = analyst_instance.generate_detailed_reasoning_with_llm(
                ticker, tool_results, combined_result, selection_result, llm
            )
        
        # 5. 构建最终结果
        analysis_result = {
            "signal": combined_result["signal"],
            "confidence": combined_result["confidence"],
            "tool_selection": {
                "selection_strategy": selection_result["analysis_strategy"],
                "market_considerations": selection_result["market_considerations"],
                "selected_tools": selection_result["selected_tools"],
                "tool_count": selection_result["tool_count"]
            },
            "tool_analysis": {
                "tools_used": len(selection_result["selected_tools"]),
                "successful_tools": len([r for r in tool_results if "error" not in r]),
                "failed_tools": len([r for r in tool_results if "error" in r]),
                "tool_results": tool_results,
                "combination_details": combined_result
            },
            "reasoning": {
                "summary": combined_result.get("reasoning", "基于LLM智能选择的工具组合分析"),
                "detailed_analysis": detailed_reasoning,
                "tool_breakdown": {result.get("tool_name", f"tool_{i}"): {
                    "signal": result.get("signal", "unknown"),
                    "confidence": result.get("confidence", 0),
                    "weight": result.get("assigned_weight", 0),
                    "selection_reason": result.get("selection_reason", ""),
                    "key_data": result.get("metrics", result.get("valuation", {}))
                } for i, result in enumerate(tool_results) if "error" not in result}
            },
            "metadata": {
                "analyst_name": analyst_instance.analyst_persona,
                "analysis_date": end_date,
                "llm_enhanced": llm is not None,
                "selection_method": "LLM智能选择" if llm else "默认选择"
            }
        }
        
        progress.update_status(f"{analyst_instance.analyst_persona.lower()}_agent", ticker, "分析完成")
        
        # 显示同步分析结果摘要
        _display_analysis_summary(analyst_instance.analyst_persona, ticker, analysis_result)
        
        return analysis_result
        
    except Exception as e:
        progress.update_status(f"{analyst_instance.analyst_persona.lower()}_agent", ticker, f"分析失败: {str(e)}")
        return {
            "signal": "neutral",
            "confidence": 0,
            "error": str(e),
            "reasoning": {"summary": f"{analyst_instance.analyst_persona}分析失败: {str(e)}"},
            "metadata": {"analyst_name": analyst_instance.analyst_persona, "analysis_date": end_date}
        }


def _sync_select_tools_with_llm(tool_selector, llm, analyst_persona: str, ticker: str,
                               market_conditions: Dict[str, Any], analysis_objective: str) -> Dict[str, Any]:
    """同步版本的LLM工具选择"""
    
    # 生成提示词
    prompt = tool_selector.get_tool_selection_prompt(
        analyst_persona, ticker, market_conditions, analysis_objective
    )
    
    print(f"🤖 LLM提示词长度: {len(prompt)} 字符")
    
    try:
        # 调用LLM
        messages = [HumanMessage(content=prompt)]
        print(f"🤖 正在调用LLM进行工具选择...")
        response = llm.invoke(messages)
        print(f"🤖 LLM响应长度: {len(response.content)} 字符")
        
        # 解析响应
        response_text = response.content.strip()
        
        # 尝试提取JSON部分
        if "```json" in response_text:
            json_start = response_text.find("```json") + 7
            json_end = response_text.find("```", json_start)
            json_text = response_text[json_start:json_end].strip()
        else:
            # 如果没有markdown格式，尝试找到JSON对象
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            json_text = response_text[json_start:json_end]
        
        # 解析JSON
        print(f"🤖 提取的JSON文本: {json_text[:200]}...")
        selection_result = json.loads(json_text)
        print(f"🤖 JSON解析成功，包含 {len(selection_result.get('selected_tools', []))} 个工具")
        
        # 验证和规范化结果
        normalized_result = tool_selector._validate_and_normalize_selection(selection_result)
        print(f"🤖 工具选择验证完成")
        return normalized_result
        
    except Exception as e:
        print(f"⚠️ LLM工具选择失败: {str(e)}")
        # 降级到默认选择策略
        return tool_selector._get_default_tool_selection(analyst_persona)


def _display_analysis_summary(analyst_name: str, ticker: str, analysis_result: Dict[str, Any]):
    """统一显示分析摘要 - 适用于同步和异步版本"""
    print(f"\n{'='*50}")
    print(f"📋 {analyst_name} | {ticker} 分析摘要")
    print(f"{'='*50}")
    
    # 工具选择信息
    if "tool_selection" in analysis_result:
        tool_selection = analysis_result["tool_selection"]
        print(f"🎯 分析策略: {tool_selection.get('analysis_strategy', 'N/A')}")
        print(f"🌍 市场考虑: {tool_selection.get('market_considerations', 'N/A')}")
        print(f"🔧 选择工具: {tool_selection.get('tool_count', 0)}个")
        
        # 显示选择的工具
        if "selected_tools" in tool_selection:
            for tool in tool_selection["selected_tools"]:
                weight_bar = "█" * int(tool['weight'] * 10)
                print(f"   • {tool['tool_name']:<20} 权重:{tool['weight']:.2f} {weight_bar}")
    
    # 工具执行结果
    if "tool_analysis" in analysis_result:
        tool_analysis = analysis_result["tool_analysis"]
        successful = tool_analysis.get("successful_tools", 0)
        failed = tool_analysis.get("failed_tools", 0)
        
        print(f"\n📊 执行结果: ✅{successful}个成功  ❌{failed}个失败")
        
        # 显示每个工具的结果
        tool_results = tool_analysis.get("tool_results", [])
        for result in tool_results:
            if "error" not in result:
                signal_emoji = {"bullish": "🟢", "bearish": "🔴", "neutral": "⚪"}.get(result.get('signal'), "❓")
                confidence = result.get('confidence', 0)
                conf_bar = "█" * int(confidence / 20)
                print(f"   {signal_emoji} {result.get('tool_name', 'Unknown'):<20} {result.get('signal', 'unknown').upper():<8} {confidence:>3}% {conf_bar}")
            else:
                error_short = result.get('error', 'Unknown')[:30] + "..." if len(result.get('error', '')) > 30 else result.get('error', 'Unknown')
                print(f"   ❌ {result.get('tool_name', 'Unknown'):<20} 失败: {error_short}")
    
    # 最终信号
    final_signal = analysis_result.get('signal', 'unknown')
    final_confidence = analysis_result.get('confidence', 0)
    signal_emoji = {"bullish": "🟢", "bearish": "🔴", "neutral": "⚪"}.get(final_signal, "❓")
    
    print(f"\n🎯 最终信号: {signal_emoji} {final_signal.upper()} (置信度: {final_confidence}%)")
    
    # 信号权重分解
    if "tool_analysis" in analysis_result and "combination_details" in analysis_result["tool_analysis"]:
        breakdown = analysis_result["tool_analysis"]["combination_details"].get("signal_breakdown", {})
        if breakdown:
            bullish_w = breakdown.get('bullish_weight', 0)
            bearish_w = breakdown.get('bearish_weight', 0)
            neutral_w = breakdown.get('neutral_weight', 0)
            total_w = breakdown.get('total_weight', 1)
            
            if total_w > 0:
                print(f"📈 权重分布:")
                print(f"   🟢 看涨: {(bullish_w/total_w)*100:5.1f}% {'█' * int((bullish_w/total_w)*20)}")
                print(f"   🔴 看跌: {(bearish_w/total_w)*100:5.1f}% {'█' * int((bearish_w/total_w)*20)}")
                print(f"   ⚪ 中性: {(neutral_w/total_w)*100:5.1f}% {'█' * int((neutral_w/total_w)*20)}")
    
    print(f"{'='*50}\n")


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
