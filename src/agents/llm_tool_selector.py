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
# 导入所有可用的分析工具
from src.tools.analysis_tools_unified import (
    # 基本面工具
    analyze_profitability,
    analyze_growth,
    analyze_financial_health,
    analyze_valuation_ratios,
    
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
    
    # 工具组合函数
    combine_tool_signals
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
    
    def __init__(self):
        # 所有可用的分析工具
        self.all_available_tools = {
            # 基本面分析工具
            "analyze_profitability": {
                "tool": analyze_profitability,
                "category": "fundamental",
                "description": "分析公司盈利能力，包括ROE、净利率、营业利率等指标",
                "best_for": "评估公司赚钱能力和经营效率",
                "data_requirements": "财务报表数据"
            },
            "analyze_growth": {
                "tool": analyze_growth,
                "category": "fundamental", 
                "description": "分析公司成长性，包括收入增长、盈利增长、净资产增长",
                "best_for": "评估公司未来发展潜力",
                "data_requirements": "多期财务数据"
            },
            "analyze_financial_health": {
                "tool": analyze_financial_health,
                "category": "fundamental",
                "description": "分析财务健康度，包括流动比率、债务水平、现金流转换",
                "best_for": "评估公司财务风险和稳定性",
                "data_requirements": "资产负债表和现金流量表数据"
            },
            "analyze_valuation_ratios": {
                "tool": analyze_valuation_ratios,
                "category": "fundamental",
                "description": "分析估值比率，包括P/E、P/B、P/S等指标",
                "best_for": "评估股票价格是否合理",
                "data_requirements": "市场价格和财务数据"
            },
            
            # 技术分析工具
            "analyze_trend_following": {
                "tool": analyze_trend_following,
                "category": "technical",
                "description": "趋势跟踪分析，包括移动平均线、MACD等趋势指标",
                "best_for": "判断价格趋势方向和强度",
                "data_requirements": "历史价格数据（建议50天以上）"
            },
            "analyze_mean_reversion": {
                "tool": analyze_mean_reversion,
                "category": "technical",
                "description": "均值回归分析，包括布林带、RSI等超买超卖指标",
                "best_for": "识别价格偏离和反转机会",
                "data_requirements": "历史价格数据（建议20天以上）"
            },
            "analyze_momentum": {
                "tool": analyze_momentum,
                "category": "technical",
                "description": "动量分析，包括短中长期价格动量指标",
                "best_for": "评估价格变化的动能和持续性",
                "data_requirements": "历史价格数据（建议30天以上）"
            },
            "analyze_volatility": {
                "tool": analyze_volatility,
                "category": "technical",
                "description": "波动率分析，包括不同时间窗口的价格波动率",
                "best_for": "评估投资风险和市场情绪",
                "data_requirements": "历史价格数据（建议30天以上）"
            },
            
            # 情绪分析工具
            "analyze_insider_trading": {
                "tool": analyze_insider_trading,
                "category": "sentiment",
                "description": "内部交易分析，统计内部人员买卖交易情况",
                "best_for": "了解内部人员对公司前景的看法",
                "data_requirements": "内部交易披露数据"
            },
            "analyze_news_sentiment": {
                "tool": analyze_news_sentiment,
                "category": "sentiment",
                "description": "新闻情绪分析，分析媒体报道的正负面情绪",
                "best_for": "了解市场舆论和投资者情绪",
                "data_requirements": "公司相关新闻数据"
            },
            
            # 估值分析工具
            "dcf_valuation_analysis": {
                "tool": dcf_valuation_analysis,
                "category": "valuation",
                "description": "DCF折现现金流估值，基于未来现金流预测的内在价值",
                "best_for": "计算公司理论内在价值",
                "data_requirements": "现金流数据和增长率预测"
            },
            "owner_earnings_valuation_analysis": {
                "tool": owner_earnings_valuation_analysis,
                "category": "valuation",
                "description": "巴菲特式所有者收益估值，考虑维持竞争力所需投资",
                "best_for": "价值投资导向的保守估值",
                "data_requirements": "净利润、折旧、资本支出、营运资本数据"
            },
            "ev_ebitda_valuation_analysis": {
                "tool": ev_ebitda_valuation_analysis,
                "category": "valuation",
                "description": "EV/EBITDA倍数估值，基于历史倍数的相对估值",
                "best_for": "与历史水平和同行比较的相对估值",
                "data_requirements": "企业价值和EBITDA历史数据"
            },
            "residual_income_valuation_analysis": {
                "tool": residual_income_valuation_analysis,
                "category": "valuation",
                "description": "剩余收益模型估值，基于超额收益的价值创造分析",
                "best_for": "评估管理层价值创造能力",
                "data_requirements": "净利润、账面价值、股权成本数据"
            }
        }
    
    def get_tool_selection_prompt(self, analyst_persona: str, ticker: str, 
                                 market_conditions: Dict[str, Any], 
                                 analysis_objective: str) -> str:
        """生成工具选择的LLM提示词"""
        
        # 构建工具描述
        tools_description = []
        for tool_name, tool_info in self.all_available_tools.items():
            tools_description.append(
                f"- **{tool_name}** ({tool_info['category']}): {tool_info['description']}\n"
                f"  适用场景: {tool_info['best_for']}\n"
                f"  数据需求: {tool_info['data_requirements']}"
            )
        
        tools_text = "\n\n".join(tools_description)
        
        # 市场条件描述
        market_context = []
        for key, value in market_conditions.items():
            market_context.append(f"- {key}: {value}")
        market_text = "\n".join(market_context) if market_context else "- 无特殊市场条件信息"

# **当前市场环境**:
# {market_text}
        prompt = f"""
你是一位专业的{analyst_persona}，需要为股票{ticker}选择合适的分析工具进行投资分析。

**分析目标**: {analysis_objective}


**可用分析工具**:
{tools_text}

**你的专业身份和偏好**:
{self._get_analyst_persona_description(analyst_persona)}

**任务要求**:
1. 根据你的专业背景和当前市场环境，从上述工具中选择3-6个最适合的工具
2. 简要说明选择这些工具的原因
3. 说明你将如何综合这些工具的结果来形成最终判断

**输出格式**（必须严格按照JSON格式）:
```json
{{
    "selected_tools": [
        {{
            "tool_name": "工具名称",
            "reason": "选择原因"
        }}
    ],
    "analysis_strategy": "整体分析策略说明",
    "synthesis_approach": "如何综合工具结果的方法",
    "market_considerations": "市场环境考虑因素"
}}
```

请基于你的专业判断，智能选择最适合当前情况的分析工具组合。
"""
        return prompt
    
    def _get_analyst_persona_description(self, analyst_persona: str) -> str:
        """获取分析师人设描述"""
        personas = {
            "基本面分析师": """
作为基本面分析师，你专注于：
- 公司财务健康状况和盈利能力
- 业务模式的可持续性和竞争优势
- 管理层质量和公司治理
- 行业地位和市场份额
- 长期投资价值评估
你倾向于选择能深入了解公司内在价值的工具，偏好基本面和估值类工具。
            """,
            "技术分析师": """
作为技术分析师，你专注于：
- 价格走势和图表形态
- 技术指标和交易信号
- 市场情绪和资金流向
- 支撑阻力位和关键价位
- 短中期交易机会
你倾向于选择能捕捉价格动态和市场趋势的工具，偏好技术分析类工具。
            """,
            "情绪分析师": """
作为情绪分析师，你专注于：
- 市场参与者的情绪变化
- 新闻舆论和媒体影响
- 内部人员交易行为
- 投资者恐慌和贪婪情绪
- 市场预期和心理因素
你倾向于选择能反映市场情绪和投资者行为的工具，偏好情绪和行为类工具。
            """,
            "估值分析师": """
作为估值分析师，你专注于：
- 公司内在价值计算
- 不同估值方法的对比
- 估值模型的假设和敏感性
- 相对估值和绝对估值
- 投资安全边际评估
你倾向于选择能精确计算公司价值的工具，偏好估值模型和基本面工具。
            """,
            "综合分析师": """
作为综合分析师，你需要：
- 整合多个维度的分析视角
- 平衡短期和长期因素
- 考虑基本面、技术面、情绪面的综合影响
- 提供全面的投资建议
- 适应不同的市场环境
你会根据具体情况灵活选择各类工具，追求分析的全面性和准确性。
            """
        }
        return personas.get(analyst_persona, personas["综合分析师"])
    
    async def select_tools_with_llm(self, llm, analyst_persona: str, ticker: str,
                                   market_conditions: Dict[str, Any], 
                                   analysis_objective: str = "全面的投资分析") -> Dict[str, Any]:
        """使用LLM选择分析工具"""
        
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
            print(f"⚠️ LLM工具选择失败: {str(e)}")
            # 降级到默认选择策略
            return self._get_default_tool_selection(analyst_persona)
    
    def _validate_and_normalize_selection(self, selection_result: Dict[str, Any]) -> Dict[str, Any]:
        """验证和规范化工具选择结果"""
        
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
                print(f"⚠️ 无效工具名称: {tool_name}")
        
        return {
            "selected_tools": valid_tools,
            "analysis_strategy": selection_result.get("analysis_strategy", "LLM生成的分析策略"),
            "synthesis_approach": selection_result.get("synthesis_approach", "基于工具结果综合判断"),
            "market_considerations": selection_result.get("market_considerations", "基于当前市场环境的考虑"),
            "tool_count": len(valid_tools)
        }
    
    def _get_default_tool_selection(self, analyst_persona: str) -> Dict[str, Any]:
        """获取默认工具选择（降级策略）"""
        
        default_selections = {
            "基本面分析师": [
                {"tool_name": "analyze_profitability", "reason": "盈利能力是基本面分析核心"},
                {"tool_name": "analyze_growth", "reason": "成长性决定长期投资价值"},
                {"tool_name": "analyze_financial_health", "reason": "财务健康度评估投资风险"},
                {"tool_name": "analyze_valuation_ratios", "reason": "估值比率判断价格合理性"}
            ],
            "技术分析师": [
                {"tool_name": "analyze_trend_following", "reason": "趋势是技术分析的核心"},
                {"tool_name": "analyze_momentum", "reason": "动量分析捕捉价格动能"},
                {"tool_name": "analyze_mean_reversion", "reason": "均值回归识别反转机会"},
                {"tool_name": "analyze_volatility", "reason": "波动率评估市场风险"}
            ],
            "情绪分析师": [
                {"tool_name": "analyze_news_sentiment", "reason": "新闻情绪反映市场预期"},
                {"tool_name": "analyze_insider_trading", "reason": "内部交易显示内部信心"}
            ],
            "估值分析师": [
                {"tool_name": "dcf_valuation_analysis", "reason": "DCF是估值的金标准"},
                {"tool_name": "owner_earnings_valuation_analysis", "reason": "所有者收益更保守实用"},
                {"tool_name": "ev_ebitda_valuation_analysis", "reason": "倍数估值提供相对视角"},
                {"tool_name": "residual_income_valuation_analysis", "reason": "剩余收益模型补充分析"}
            ]
        }
        
        selected_tools = default_selections.get(analyst_persona, default_selections["基本面分析师"])
        
        return {
            "selected_tools": selected_tools,
            "analysis_strategy": f"默认{analyst_persona}分析策略",
            "synthesis_approach": "基于工具结果综合判断",
            "market_considerations": "使用默认工具组合",
            "tool_count": len(selected_tools)
        }
    
    def execute_selected_tools(self, selected_tools: List[Dict[str, Any]], 
                             ticker: str, api_key: str, **kwargs) -> List[Dict[str, Any]]:
        """执行选定的工具"""
        
        tool_results = []
        
        for tool_selection in selected_tools:
            tool_name = tool_selection["tool_name"]
            
            if tool_name not in self.all_available_tools:
                continue
                
            tool = self.all_available_tools[tool_name]["tool"]
            
            try:
                # 准备工具参数
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
                print(f"❌ 工具 {tool_name} 执行失败: {str(e)}")
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
        """使用LLM综合工具结果，生成最终的信号和置信度"""
        
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
        
        # 构建LLM提示
        prompt = f"""
作为专业的{analyst_persona}，你需要综合以下工具的分析结果，给出最终的投资信号和置信度。

股票: {ticker}
分析策略: {selection_result.get('analysis_strategy', '')}
综合方法: {selection_result.get('synthesis_approach', '')}

工具分析结果:
{json.dumps(tool_summaries, indent=2, ensure_ascii=False, cls=NumpyEncoder)}

请基于你的专业判断，综合这些工具结果，给出最终的投资建议。

输出格式（JSON）:
{{
    "signal": "bullish/bearish/neutral",
    "confidence": 0-100之间的整数,
    "reasoning": "详细的综合判断理由，说明如何权衡各工具结果",
    "tool_impact_analysis": "各工具对最终判断的影响分析"
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
            "reasoning": synthesis_result.get("reasoning", "基于工具结果的综合判断"),
            "tool_impact_analysis": synthesis_result.get("tool_impact_analysis", ""),
            "synthesis_method": "llm_based"
        }
            
    
 
