"""
基于LLM的智能工具选择器
让分析师通过LLM智能选择和使用分析工具
"""

from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool
from typing import Dict, Any, List, Optional
import json
import pdb
import numpy as np
from .prompt_loader import get_prompt_loader
from src.utils.api_key import get_api_key_from_state

# 导入所有可用的分析工具
from src.tools.analysis_tools_unified import (
    # 基本面工具
    analyze_profitability,
    analyze_growth,
    analyze_financial_health,
    analyze_valuation_ratios,
    analyze_efficiency_ratios,
    
    # 技术分析工具
    analyze_trend_following,
    analyze_mean_reversion,
    analyze_momentum,
    analyze_volatility,
    
    # 情绪分析工具
    analyze_insider_trading,
    analyze_news_sentiment,
    
    # 估值分析工具
    dcf_valuation_analysis,
    owner_earnings_valuation_analysis,
    ev_ebitda_valuation_analysis,
    residual_income_valuation_analysis,
    
    # # 工具组合函数
    # combine_tool_signals
)

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)
class LLMToolSelector:
    """基于LLM的智能工具选择器"""
    
    def __init__(self, use_prompt_files: bool = True):
        """
        初始化工具选择器
        
        Args:
            use_prompt_files: 是否使用外部 prompt 文件（默认 True，向后兼容）
        """
        self.use_prompt_files = use_prompt_files
        self.prompt_loader = get_prompt_loader() if use_prompt_files else None
        
        # 所有可用的分析工具
        
        self.all_available_tools = {
            # 基本面分析工具
            "analyze_profitability": {
                "tool": analyze_profitability,
                "category": "fundamental",
                "description": "Analyze company profitability, including ROE, net margin, operating margin and other indicators",
                "best_for": "Evaluate company's earning capacity and operational efficiency",
                "data_requirements": "Financial statement data"
            },
            "analyze_growth": {
                "tool": analyze_growth,
                "category": "fundamental", 
                "description": "Analyze company growth, including revenue growth, earnings growth, and net asset growth",
                "best_for": "Evaluate company's future development potential",
                "data_requirements": "Multi-period financial data"
            },
            "analyze_financial_health": {
                "tool": analyze_financial_health,
                "category": "fundamental",
                "description": "Analyze financial health, including current ratio, debt level, and cash flow conversion",
                "best_for": "Evaluate company's financial risk and stability",
                "data_requirements": "Balance sheet and cash flow statement data"
            },
            "analyze_valuation_ratios": {
                "tool": analyze_valuation_ratios,
                "category": "fundamental",
                "description": "Analyze valuation ratios, including P/E, P/B, P/S and other indicators",
                "best_for": "Evaluate whether stock price is reasonable",
                "data_requirements": "Market price and financial data"
            },
            "analyze_efficiency_ratios": {
                "tool": analyze_efficiency_ratios,
                "category": "fundamental",
                "description": "Analyze efficiency ratios, including asset turnover, inventory turnover, accounts receivable turnover, working capital turnover and other indicators",
                "best_for": "Evaluate company's asset utilization efficiency",
                "data_requirements": "Financial statement data"
            },
            # 技术分析工具
            "analyze_trend_following": {
                "tool": analyze_trend_following,
                "category": "technical",
                "description": "Trend following analysis, including moving averages, MACD and other trend indicators",
                "best_for": "Determine price trend direction and strength",
                "data_requirements": "Historical price data (recommended 50+ days)"
            },
            "analyze_mean_reversion": {
                "tool": analyze_mean_reversion,
                "category": "technical",
                "description": "Mean reversion analysis, including Bollinger Bands, RSI and other overbought/oversold indicators",
                "best_for": "Identify price deviation and reversal opportunities",
                "data_requirements": "Historical price data (recommended 20+ days)"
            },
            "analyze_momentum": {
                "tool": analyze_momentum,
                "category": "technical",
                "description": "Momentum analysis, including short, medium and long-term price momentum indicators",
                "best_for": "Evaluate momentum and sustainability of price changes",
                "data_requirements": "Historical price data (recommended 30+ days)"
            },
            "analyze_volatility": {
                "tool": analyze_volatility,
                "category": "technical",
                "description": "Volatility analysis, including price volatility across different time windows",
                "best_for": "Evaluate investment risk and market sentiment",
                "data_requirements": "Historical price data (recommended 30+ days)"
            },
            
            # 情绪分析工具
            "analyze_insider_trading": {
                "tool": analyze_insider_trading,
                "category": "sentiment",
                "description": "Insider trading analysis, statistics on insider buy/sell transactions",
                "best_for": "Understand insiders' views on company prospects",
                "data_requirements": "Insider trading disclosure data"
            },
            "analyze_news_sentiment": {
                "tool": analyze_news_sentiment,
                "category": "sentiment",
                "description": "News sentiment analysis, analyzing positive/negative sentiment in media reports",
                "best_for": "Understand market opinion and investor sentiment",
                "data_requirements": "Company-related news data"
            },
            
            # 估值分析工具
            "dcf_valuation_analysis": {
                "tool": dcf_valuation_analysis,
                "category": "valuation",
                "description": "DCF discounted cash flow valuation, intrinsic value based on future cash flow projections",
                "best_for": "Calculate company's theoretical intrinsic value",
                "data_requirements": "Cash flow data and growth rate projections"
            },
            "owner_earnings_valuation_analysis": {
                "tool": owner_earnings_valuation_analysis,
                "category": "valuation",
                "description": "Buffett-style owner earnings valuation, considering investments needed to maintain competitiveness",
                "best_for": "Conservative valuation for value investment approach",
                "data_requirements": "Net income, depreciation, capital expenditure, working capital data"
            },
            "ev_ebitda_valuation_analysis": {
                "tool": ev_ebitda_valuation_analysis,
                "category": "valuation",
                "description": "EV/EBITDA multiple valuation, relative valuation based on historical multiples",
                "best_for": "Relative valuation compared to historical levels and peers",
                "data_requirements": "Enterprise value and EBITDA historical data"
            },
            "residual_income_valuation_analysis": {
                "tool": residual_income_valuation_analysis,
                "category": "valuation",
                "description": "Residual income model valuation, value creation analysis based on excess returns",
                "best_for": "Evaluate management's value creation capability",
                "data_requirements": "Net income, book value, cost of equity data"
            }
        }
    def get_tool_selection_prompt(self, analyst_persona: str, ticker: str, 
                                 market_conditions: Dict[str, Any], 
                                 analysis_objective: str) -> str:
        """Generate LLM prompt for tool selection"""
        
        # 构建工具描述
        tools_description = []
        for tool_name, tool_info in self.all_available_tools.items():
            tools_description.append(
                f"- **{tool_name}** ({tool_info['category']}): {tool_info['description']}\n"
                f"  Best for: {tool_info['best_for']}\n"
                f"  Data requirements: {tool_info['data_requirements']}"
            )
        
        tools_text = "\n\n".join(tools_description)
        
        # 获取 persona 描述
        persona_description = self._get_analyst_persona_description(analyst_persona)
        
        # 尝试从文件加载 prompt
        if self.use_prompt_files and self.prompt_loader:
            try:
                prompt = self.prompt_loader.load_prompt(
                    "analyst",
                    "tool_selection",
                    {
                        "analyst_persona": analyst_persona,
                        "ticker": ticker,
                        "analysis_objective": analysis_objective,
                        "tools_description": tools_text,
                        "persona_description": persona_description
                    }
                )
                return prompt
            except FileNotFoundError:
                # 如果文件不存在，使用硬编码的 prompt（向后兼容）
                print(f"⚠️ Prompt file not found, using hardcoded prompt for tool_selection")
        
        # 硬编码的 prompt（向后兼容）
        prompt = f"""
You are a professional {analyst_persona}, and you need to select appropriate analysis tools for stock {ticker} to conduct investment analysis.

**Analysis Objective**: {analysis_objective}

**Available Analysis Tools**:
{tools_text}

**Your Professional Identity and Preferences**:
{persona_description}

**Task Requirements**:
1. Based on your professional background and current market environment, select 3-6 most suitable tools from the above tools
2. Briefly explain the reasons for selecting these tools
3. Explain how you will synthesize the results from these tools to form your final judgment

**Output Format** (must strictly follow JSON format):
```json
{{
    "selected_tools": [
        {{
            "tool_name": "tool name",
            "reason": "selection reason"
        }}
    ],
    "analysis_strategy": "overall analysis strategy description",
    "synthesis_approach": "method for synthesizing tool results",
}}
```

Please intelligently select the most suitable analysis tool combination for the current situation based on your professional judgment.
"""
        return prompt
    
    def _get_analyst_persona_description(self, analyst_persona: str) -> str:
        """Get analyst persona description"""
        personas = {
        "Fundamental Analyst": """
As a fundamental analyst, you focus on:
- Company financial health and profitability
- Business model sustainability and competitive advantages
- Management quality and corporate governance
- Industry position and market share
- Long-term investment value assessment
You tend to select tools that provide deep insights into company intrinsic value, preferring fundamental and valuation tools.
        """,
        "Technical Analyst": """
As a technical analyst, you focus on:
- Price trends and chart patterns
- Technical indicators and trading signals
- Market sentiment and capital flows
- Support/resistance levels and key price points
- Short to medium-term trading opportunities
You tend to select tools that capture price dynamics and market trends, preferring technical analysis tools.
        """,
        "Sentiment Analyst": """
As a sentiment analyst, you focus on:
- Market participant sentiment changes
- News opinion and media influence
- Insider trading behavior
- Investor panic and greed emotions
- Market expectations and psychological factors
You tend to select tools that reflect market sentiment and investor behavior, preferring sentiment and behavioral tools.
        """,
        "Valuation Analyst": """
As a valuation analyst, you focus on:
- Company intrinsic value calculation
- Comparison of different valuation methods
- Valuation model assumptions and sensitivity
- Relative and absolute valuation
- Investment margin of safety assessment
You tend to select tools that accurately calculate company value, preferring valuation models and fundamental tools.
        """,
        "Comprehensive Analyst": """
As a comprehensive analyst, you need to:
- Integrate multiple analytical perspectives
- Balance short-term and long-term factors
- Consider combined impact of fundamentals, technicals, and sentiment
- Provide comprehensive investment advice
- Adapt to different market environments
You will flexibly select various tools based on specific situations, pursuing comprehensiveness and accuracy in analysis.
        """
    }
        return personas.get(analyst_persona, personas["Comprehensive Analyst"])
    
    async def select_tools_with_llm(self, llm, analyst_persona: str, ticker: str,
                                   market_conditions: Dict[str, Any], 
                                   analysis_objective: str = "Comprehensive investment analysis") -> Dict[str, Any]:
        """Use LLM to select analysis tools"""
        
        # 生成提示词
        prompt = self.get_tool_selection_prompt(
            analyst_persona, ticker, market_conditions, analysis_objective
        )
        
        try:
            # 调用LLM
            messages = [HumanMessage(content=prompt)]
            response = llm.invoke(messages)
            
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
            selection_result = json.loads(json_text)
            
            # 验证和规范化结果
            return self._validate_and_normalize_selection(selection_result)
            
        except Exception as e:
            print(f"⚠️ LLM tool selection failed: {str(e)}")
            # Fallback to default selection strategy
            return self._get_default_tool_selection(analyst_persona)
    
    def _validate_and_normalize_selection(self, selection_result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and normalize tool selection results"""
        
        if "selected_tools" not in selection_result:
            raise ValueError("Missing selected_tools in response")
        
        selected_tools = selection_result["selected_tools"]
        
        # 验证工具名称
        valid_tools = []
        
        for tool_selection in selected_tools:
            tool_name = tool_selection.get("tool_name")
            
            if tool_name in self.all_available_tools:
                valid_tools.append(tool_selection)
            else:
                print(f"⚠️ Invalid tool name: {tool_name}")
        
        return {
            "selected_tools": valid_tools,
            "analysis_strategy": selection_result.get("analysis_strategy", "LLM-generated analysis strategy"),
            "synthesis_approach": selection_result.get("synthesis_approach", "Comprehensive judgment based on tool results"),
            # "market_considerations": selection_result.get("market_considerations", "Considerations based on current market environment"),
            "tool_count": len(valid_tools)
        }
    
    def _get_default_tool_selection(self, analyst_persona: str) -> Dict[str, Any]:
        """Get default tool selection (fallback strategy)"""
        
        default_selections = {
            "Fundamental Analyst": [
                {"tool_name": "analyze_profitability", "reason": "Profitability is the core of fundamental analysis"},
                {"tool_name": "analyze_growth", "reason": "Growth determines long-term investment value"},
                {"tool_name": "analyze_financial_health", "reason": "Financial health assesses investment risk"},
                {"tool_name": "analyze_valuation_ratios", "reason": "Valuation ratios determine price reasonableness"},
                {"tool_name": "analyze_efficiency_ratios", "reason": "Efficiency ratios analyze company asset utilization"}
            ],
            "Technical Analyst": [
                {"tool_name": "analyze_trend_following", "reason": "Trend is the core of technical analysis"},
                {"tool_name": "analyze_momentum", "reason": "Momentum analysis captures price momentum"},
                {"tool_name": "analyze_mean_reversion", "reason": "Mean reversion identifies reversal opportunities"},
                {"tool_name": "analyze_volatility", "reason": "Volatility assesses market risk"}
            ],
            "Sentiment Analyst": [
                {"tool_name": "analyze_news_sentiment", "reason": "News sentiment reflects market expectations"},
                {"tool_name": "analyze_insider_trading", "reason": "Insider trading shows insider confidence"}
            ],
            "Valuation Analyst": [
                {"tool_name": "dcf_valuation_analysis", "reason": "DCF is the gold standard of valuation"},
                {"tool_name": "owner_earnings_valuation_analysis", "reason": "Owner earnings is more conservative and practical"},
                {"tool_name": "ev_ebitda_valuation_analysis", "reason": "Multiple valuation provides relative perspective"},
                {"tool_name": "residual_income_valuation_analysis", "reason": "Residual income model provides supplementary analysis"}
            ]
        }
        
        selected_tools = default_selections.get(analyst_persona, default_selections["Fundamental Analyst"])
        
        return {
            "selected_tools": selected_tools,
            "analysis_strategy": f"Default {analyst_persona} analysis strategy",
            "synthesis_approach": "Comprehensive judgment based on tool results",
            # "market_considerations": "Using default tool combination",
            "tool_count": len(selected_tools)
        }
    
    def _get_api_key_for_tool(self, tool_category: str, state: dict = None) -> str:
        """
        根据工具类别获取对应的API key
        
        Args:
            tool_category: 工具类别 (fundamental, technical, sentiment, valuation)
            state: State对象 (可选)
        
        Returns:
            API key字符串
        """
        import os
        
        # 根据工具类别决定使用哪个API key
        if tool_category in ["fundamental", "valuation"]:
            # 基本面和估值工具使用 FINANCIAL_DATASETS_API_KEY
            api_key_name = "FINANCIAL_DATASETS_API_KEY"
        elif tool_category in ["technical", "sentiment"]:
            # 技术和情绪工具使用 FINNHUB_API_KEY
            api_key_name = "FINNHUB_API_KEY"
        else:
            # 默认使用 FINNHUB_API_KEY
            api_key_name = "FINNHUB_API_KEY"
        
        # 首先尝试从state获取
        if state:
            api_key = get_api_key_from_state(state, api_key_name)
            if api_key:
                return api_key
        
        # 然后尝试从环境变量获取
        api_key = os.getenv(api_key_name)
        if api_key:
            return api_key
        
        # 如果都没有,打印警告并返回None
        print(f"⚠️ 警告: 未找到 {api_key_name} (工具类别: {tool_category})")
        print(f"   请在 .env 文件中设置 {api_key_name} 或通过 state 传递")
        return None
    
    def execute_selected_tools(self, selected_tools: List[Dict[str, Any]], 
                             ticker: str, state: dict = None, **kwargs) -> List[Dict[str, Any]]:
        """
        Execute selected tools
        
        Args:
            selected_tools: 选中的工具列表
            ticker: 股票代码
            state: State对象 (可选,用于获取API keys)
            **kwargs: 其他参数 (start_date, end_date等)
        
        Returns:
            工具执行结果列表
        """
        
        tool_results = []
        
        for tool_selection in selected_tools:
            tool_name = tool_selection["tool_name"]
            
            if tool_name not in self.all_available_tools:
                continue
                
            tool = self.all_available_tools[tool_name]["tool"]
            
            try:
                # 准备工具参数 - 根据工具类型获取对应的API key
                tool_category = self.all_available_tools[tool_name]["category"]
                api_key = self._get_api_key_for_tool(tool_category, state)
                
                tool_params = {"ticker": ticker, "api_key": api_key}
                
                # 根据工具类型添加特定参数
                tool_category = self.all_available_tools[tool_name]["category"]
                if tool_category == "technical":
                    tool_params["start_date"] = kwargs.get("start_date")
                    tool_params["end_date"] = kwargs.get("end_date")
                elif tool_category in ["fundamental", "sentiment", "valuation"]:
                    tool_params["end_date"] = kwargs.get("end_date")
                    if tool_category == "sentiment":
                        tool_params["start_date"] = kwargs.get("start_date")
                
                # 执行工具
                result = tool.invoke(tool_params)
                result["tool_name"] = tool_name
                result["selection_reason"] = tool_selection.get("reason", "")
                
                tool_results.append(result)
                
            except Exception as e:
                print(f"Tool {tool_name} execution failed: {str(e)}")
                error_result = {
                    "tool_name": tool_name,
                    "error": str(e),
                    "signal": "neutral",
                    "confidence": 0,
                    "selection_reason": tool_selection.get("reason", "")
                }
                tool_results.append(error_result)
        
        return tool_results
    
    def synthesize_results_with_llm(self, tool_results: List[Dict[str, Any]], 
                                   selection_result: Dict[str, Any], 
                                   llm, ticker: str, analyst_persona: str) -> Dict[str, Any]:
        """Use LLM to synthesize tool results and generate final signal and confidence"""
        
        # 准备工具结果摘要
        tool_summaries = []
        for result in tool_results:
            if "error" not in result:
                tool_summary = {
                    "tool_name": result.get("tool_name", "unknown"),
                    "signal": result.get("signal", "neutral"),
                    "key_metrics": result.get("metrics", result.get("valuation", {})),
                    "selection_reason": result.get("selection_reason", "")
                }
                tool_summaries.append(tool_summary)
        
        tool_summaries_json = json.dumps(tool_summaries, indent=2, ensure_ascii=False, cls=NumpyEncoder)
        
        # 尝试从文件加载 prompt
        if self.use_prompt_files and self.prompt_loader:
            try:
                prompt = self.prompt_loader.load_prompt(
                    "analyst",
                    "tool_synthesis",
                    {
                        "analyst_persona": analyst_persona,
                        "ticker": ticker,
                        "analysis_strategy": selection_result.get('analysis_strategy', ''),
                        "synthesis_approach": selection_result.get('synthesis_approach', ''),
                        "tool_summaries": tool_summaries_json
                    }
                )
            except FileNotFoundError:
                print(f"⚠️ Prompt file not found, using hardcoded prompt for tool_synthesis")
                # 使用硬编码 prompt
                prompt = f"""
        As a professional {analyst_persona}, you need to synthesize the following tool analysis results and provide final investment signal and confidence level.

        Stock: {ticker}
        Analysis Strategy: {selection_result.get('analysis_strategy', '')}
        Synthesis Method: {selection_result.get('synthesis_approach', '')}

        Tool Analysis Results:
        {tool_summaries_json}

        Please provide final investment recommendation based on your professional judgment by synthesizing these tool results.

        Output Format (JSON):
        {{
            "signal": "bullish/bearish/neutral",
            "confidence": integer between 0-100,
            "reasoning": "detailed comprehensive judgment rationale, explaining how to weigh each tool result",
            "tool_impact_analysis": "analysis of each tool's impact on final judgment"
        }}
        """
        else:
            # 硬编码 prompt（向后兼容）
            prompt = f"""
        As a professional {analyst_persona}, you need to synthesize the following tool analysis results and provide final investment signal and confidence level.

        Stock: {ticker}
        Analysis Strategy: {selection_result.get('analysis_strategy', '')}
        Synthesis Method: {selection_result.get('synthesis_approach', '')}

        Tool Analysis Results:
        {tool_summaries_json}

        Please provide final investment recommendation based on your professional judgment by synthesizing these tool results.

        Output Format (JSON):
        {{
            "signal": "bullish/bearish/neutral",
            "confidence": integer between 0-100,
            "reasoning": "detailed comprehensive judgment rationale, explaining how to weigh each tool result",
            "tool_impact_analysis": "analysis of each tool's impact on final judgment"
        }}
        """
                
        from langchain_core.messages import HumanMessage
        messages = [HumanMessage(content=prompt)]
        response = llm.invoke(messages)
        
        # 解析响应
        response_text = response.content.strip()
        # 尝试提取JSON
        if "```json" in response_text:
            json_start = response_text.find("```json") + 7
            json_end = response_text.find("```", json_start)
            json_text = response_text[json_start:json_end].strip()
        else:
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            json_text = response_text[json_start:json_end]
        
        synthesis_result = json.loads(json_text)
        
        # 验证结果
        signal = synthesis_result.get("signal", "neutral")
        confidence = max(0, min(100, synthesis_result.get("confidence", 50)))
        # pdb.set_trace()
        return {
            "signal": signal,
            "confidence": confidence,
            "reasoning": synthesis_result.get("reasoning", "Comprehensive judgment based on tool results"),
            "tool_impact_analysis": synthesis_result.get("tool_impact_analysis", ""),
            "synthesis_method": "llm_based"
        }
            
    
 
