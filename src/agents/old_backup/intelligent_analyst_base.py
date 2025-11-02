"""
Intelligent Analyst Base Class
LLM-based tool selection and analysis framework
"""

from langchain_core.messages import HumanMessage
from src.graph.state import AgentState, show_agent_reasoning
from src.utils.api_key import get_api_key_from_state
from src.utils.progress import progress
from src.llm.models import get_model
import json
from typing import List, Dict, Any, Optional

from src.agents.llm_tool_selector import LLMToolSelector


class IntelligentAnalystBase:
    """智能分析师基类 - 使用LLM进行工具选择"""
    
    def __init__(self, analyst_persona: str, description: str):
        self.analyst_persona = analyst_persona
        self.description = description
        self.tool_selector = LLMToolSelector()
    
    def generate_market_conditions(self, state: AgentState) -> Dict[str, Any]:
        """从状态中提取市场条件信息"""
        data = state.get("data", {})
        metadata = state.get("metadata", {})
        
        market_conditions = {
            "analysis_date": data.get("end_date", "unknown"),
            "time_period": f"{data.get('start_date', 'unknown')} to {data.get('end_date', 'unknown')}",
            "multi_ticker_analysis": len(data.get("tickers", [])) > 1,
            "session_type": "multi_day" if metadata.get("session_id", "").startswith("multi_day") else "single_day"
        }
        
        # 从之前的分析师结果中推断市场条件
        analyst_signals = data.get("analyst_signals", {})
        if analyst_signals:
            # 分析技术指标推断波动率环境
            tech_signals = analyst_signals.get("technical_analyst_agent", {})
            if tech_signals:
                for ticker_analysis in tech_signals.values():
                    if isinstance(ticker_analysis, dict) and "reasoning" in ticker_analysis:
                        reasoning = ticker_analysis["reasoning"]
                        if isinstance(reasoning, dict):
                            volatility_info = reasoning.get("tool_breakdown", {}).get("analyze_volatility", {})
                            if volatility_info and "key_metrics" in volatility_info:
                                vol_20d = volatility_info["key_metrics"].get("volatility_20d", 0)
                                if vol_20d > 30:
                                    market_conditions["volatility_regime"] = "high"
                                elif vol_20d < 15:
                                    market_conditions["volatility_regime"] = "low"
                                else:
                                    market_conditions["volatility_regime"] = "normal"
                                break
        
        # 其他市场条件的默认值
        if "volatility_regime" not in market_conditions:
            market_conditions["volatility_regime"] = "normal"
        
        market_conditions["interest_rate"] = "normal"  # 可以根据实际情况调整
        market_conditions["market_sentiment"] = "neutral"  # 可以根据情绪分析结果调整
        market_conditions["news_rich_environment"] = True
        market_conditions["insider_activity_level"] = "normal"
        
        return market_conditions
    
    def generate_detailed_reasoning_with_llm(self, ticker: str, tool_results: List[Dict[str, Any]], 
                                           combined_result: Dict[str, Any], 
                                           selection_info: Dict[str, Any], llm) -> str:
        """使用LLM生成详细的分析推理"""
        
        # 构建工具结果摘要
        tool_summary = []
        for result in tool_results:
            if "error" not in result:
                tool_name = result.get("tool_name", "unknown")
                signal = result.get("signal", "unknown")
                # confidence = result.get("confidence", 0)
                reason = result.get("selection_reason", "")
                
                # tool_summary.append(f"- **{tool_name}**: {signal} (Confidence: {confidence}%)")
                tool_summary.append(f"- **{tool_name}**: {signal}")

                if reason:
                    tool_summary.append(f"  Selection reason: {reason}")
                if 'reasoning' in result:
                    tool_summary.append(f"  Analysis result: {result['reasoning']}")
                
                # 添加关键指标
                self._add_key_metrics_to_summary(result, tool_summary)
        
        # 构建提示词
        prompt = f"""
As a professional {self.analyst_persona}, please generate a detailed professional analysis report for stock {ticker} based on the following analysis results:

**Tool Selection Strategy**: {selection_info.get('analysis_strategy', 'Not provided')}

**Tool Analysis Results**:
{chr(10).join(tool_summary)}

**Comprehensive Analysis Signal**: {combined_result['signal']} (Confidence: {combined_result['confidence']}%)

**Please Provide**:
1. Professional interpretation and integration of each analysis result
2. Deep insights based on your professional background
3. Reliability assessment of current analysis results
4. Specific investment recommendations and risk warnings
5. Key factors to watch and follow-up observation points

Please maintain the professional perspective and analytical style of {self.analyst_persona}, provide valuable investment insights, and keep within 300 words.
"""
        
        try:
            messages = [HumanMessage(content=prompt)]
            response = llm.invoke(messages)
            return response.content
        except Exception as e:
            return f"LLM reasoning generation failed: {str(e)}"
    
    def _add_key_metrics_to_summary(self, result: Dict[str, Any], tool_summary: List[str]):
        """添加关键指标到摘要中"""
        metrics = result.get('metrics', {})
        valuation = result.get('valuation', {})
        
        key_metrics = []
        
        # 基本面指标
        if 'return_on_equity' in metrics:
            key_metrics.append(f"ROE: {metrics['return_on_equity']:.2%}" if metrics['return_on_equity'] else "ROE: N/A")
        if 'revenue_growth' in metrics:
            key_metrics.append(f"Revenue Growth: {metrics['revenue_growth']:.2%}" if metrics['revenue_growth'] else "Revenue Growth: N/A")
        
        # 技术指标
        if 'current_price' in metrics:
            key_metrics.append(f"Current Price: {metrics['current_price']:.2f}")
        if 'rsi' in metrics:
            key_metrics.append(f"RSI: {metrics['rsi']:.1f}")
        if 'volatility_20d' in metrics:
            key_metrics.append(f"20-day Volatility: {metrics['volatility_20d']:.1f}%")
        
        # 情绪指标
        if 'total_trades' in metrics:
            key_metrics.append(f"Insider Trades: {metrics['total_trades']}")
        if 'positive_ratio' in metrics:
            key_metrics.append(f"Positive News Ratio: {metrics['positive_ratio']:.1f}%")
        
        # 估值指标
        if 'value_gap_pct' in valuation:
            key_metrics.append(f"Value Gap: {valuation['value_gap_pct']:.1f}%")
        if 'enterprise_value' in valuation:
            key_metrics.append(f"Enterprise Value: ${valuation['enterprise_value']:,.0f}")
        
        if key_metrics:
            tool_summary.append(f"  Key Metrics: {', '.join(key_metrics[:3])}")  # Only show first 3 key metrics
    
    async def analyze_with_llm_tool_selection(self, ticker: str, end_date: str, api_key: str,
                                            start_date: str = None, llm=None, 
                                            analysis_objective: str = None) -> Dict[str, Any]:
        """Perform analysis using LLM tool selection"""
        
        if analysis_objective is None:
            analysis_objective = f"As a professional {self.analyst_persona}, conduct comprehensive analysis of stock {ticker}"
        
        progress.update_status(f"{self.analyst_persona.lower()}_agent", ticker, "Starting intelligent tool selection")
        
        # 1. 生成市场条件（这里需要从外部传入state或其他方式获取）
        market_conditions = {
            "analysis_date": end_date,
            "volatility_regime": "normal",
            "interest_rate": "normal", 
            "market_sentiment": "neutral"
        }
        
        # 2. 使用LLM选择工具

        selection_result = await self.tool_selector.select_tools_with_llm(
            llm, self.analyst_persona, ticker, market_conditions, analysis_objective
        )
        
        progress.update_status(f"{self.analyst_persona.lower()}_agent", ticker, 
                                f"Selected {selection_result['tool_count']} tools")
        
        # 3. 执行选定的工具
        tool_results = self.tool_selector.execute_selected_tools(
            selection_result["selected_tools"],
            ticker=ticker,
            api_key=api_key,
            start_date=start_date,
            end_date=end_date
        )

        # 4. 使用LLM综合判断工具结果
        progress.update_status(f"{self.analyst_persona.lower()}_agent", ticker, "LLM synthesizing analysis signals")
        combined_result = self.tool_selector.synthesize_results_with_llm(
            tool_results, 
            selection_result,
            llm,
            ticker,
            self.analyst_persona
        )
        # Display LLM prompt merged signal results
        # print(f"{self.analyst_persona.lower()}_agent\n",combined_result)
        
        # 5. 生成详细推理 (已移除，避免重复内容)
        
        # 6. 构建最终结果
        analysis_result = {
            "signal": combined_result["signal"],
            "confidence": combined_result["confidence"],
            "tool_selection": {
                "analysis_strategy": selection_result["analysis_strategy"],
                # "market_considerations": selection_result["market_considerations"],
                "selected_tools": selection_result["selected_tools"],
                "tool_count": selection_result["tool_count"]
            },
            "tool_analysis": {
                "tools_used": len(selection_result["selected_tools"]),
                "successful_tools": len([r for r in tool_results if "error" not in r]),
                "failed_tools": len([r for r in tool_results if "error" in r]),
                "tool_results": tool_results,
                "synthesis_details": combined_result
            },
            "metadata": {
                "analyst_name": self.analyst_persona,
                "analysis_date": end_date,
                "llm_enhanced": llm is not None,
                "selection_method": "LLM intelligent selection" if llm else "Default selection",
                "synthesis_method": combined_result.get("synthesis_method", "unknown")
            }
        }
        
        progress.update_status(f"{self.analyst_persona.lower()}_agent", ticker, "Analysis completed")
        
        return analysis_result
            
     


# 具体的分析师类
class IntelligentFundamentalAnalyst(IntelligentAnalystBase):
    """智能基本面分析师"""
    def __init__(self):
        super().__init__("基本面分析师", "专注于公司财务数据和基本面分析，使用LLM智能选择分析工具")


class IntelligentTechnicalAnalyst(IntelligentAnalystBase):
    """智能技术分析师"""
    def __init__(self):
        super().__init__("技术分析师", "专注于技术指标和图表分析，使用LLM智能选择分析工具")


class IntelligentSentimentAnalyst(IntelligentAnalystBase):
    """智能情绪分析师"""
    def __init__(self):
        super().__init__("情绪分析师", "分析市场情绪和投资者行为，使用LLM智能选择分析工具")


class IntelligentValuationAnalyst(IntelligentAnalystBase):
    """智能估值分析师"""
    def __init__(self):
        super().__init__("估值分析师", "专注于公司估值和价值评估，使用LLM智能选择分析工具")


class IntelligentComprehensiveAnalyst(IntelligentAnalystBase):
    """智能综合分析师"""
    def __init__(self):
        super().__init__("综合分析师", "整合多维度分析视角，使用LLM智能选择最适合的工具组合")
