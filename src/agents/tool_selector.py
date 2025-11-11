"""
基于LLM的智能工具选择器
让分析师通过LLM智能选择和使用分析工具
使用AgentScope的Toolkit管理工具
"""
import os
import json
from typing import Dict, Any, List
from agentscope.tool import Toolkit

from .prompt_loader import PromptLoader

# 导入所有可用的分析工具
from src.tools.analysis_tools import (
    analyze_profitability,
    analyze_growth,
    analyze_financial_health,
    analyze_valuation_ratios,
    analyze_efficiency_ratios,
    analyze_trend_following,
    analyze_mean_reversion,
    analyze_momentum,
    analyze_volatility,
    analyze_insider_trading,
    analyze_news_sentiment,
    dcf_valuation_analysis,
    owner_earnings_valuation_analysis,
    ev_ebitda_valuation_analysis,
    residual_income_valuation_analysis,
)

class Toolselector:
    """基于LLM的智能工具选择器"""
    
    # 工具分类映射（用于确定API key）
    TOOL_CATEGORIES = {
        "analyze_profitability": "fundamental",
        "analyze_growth": "fundamental",
        "analyze_financial_health": "fundamental",
        "analyze_valuation_ratios": "fundamental",
        "analyze_efficiency_ratios": "fundamental",
        "analyze_trend_following": "technical",
        "analyze_mean_reversion": "technical",
        "analyze_momentum": "technical",
        "analyze_volatility": "technical",
        "analyze_insider_trading": "sentiment",
        "analyze_news_sentiment": "sentiment",
        "dcf_valuation_analysis": "valuation",
        "owner_earnings_valuation_analysis": "valuation",
        "ev_ebitda_valuation_analysis": "valuation",
        "residual_income_valuation_analysis": "valuation",
    }
    
    # Persona 名称映射
    PERSONA_KEY_MAP = {
        "Fundamental Analyst": "fundamentals_analyst",
        "Technical Analyst": "technical_analyst",
        "Sentiment Analyst": "sentiment_analyst",
        "Valuation Analyst": "valuation_analyst",
        "Comprehensive Analyst": "comprehensive_analyst",
    }
    
    def __init__(self):
        """初始化工具选择器"""
        self.prompt_loader = PromptLoader()
        self.toolkit = Toolkit()
        self.personas_config = self.prompt_loader.load_yaml_config("analyst", "personas")
        
        # 工具函数映射
        self.tool_functions = {
            "analyze_profitability": analyze_profitability,
            "analyze_growth": analyze_growth,
            "analyze_financial_health": analyze_financial_health,
            "analyze_valuation_ratios": analyze_valuation_ratios,
            "analyze_efficiency_ratios": analyze_efficiency_ratios,
            "analyze_trend_following": analyze_trend_following,
            "analyze_mean_reversion": analyze_mean_reversion,
            "analyze_momentum": analyze_momentum,
            "analyze_volatility": analyze_volatility,
            "analyze_insider_trading": analyze_insider_trading,
            "analyze_news_sentiment": analyze_news_sentiment,
            "dcf_valuation_analysis": dcf_valuation_analysis,
            "owner_earnings_valuation_analysis": owner_earnings_valuation_analysis,
            "ev_ebitda_valuation_analysis": ev_ebitda_valuation_analysis,
            "residual_income_valuation_analysis": residual_income_valuation_analysis,
        }
        
        # 注册所有工具（使用原生方法）
        self._register_all_tools()
    
    def _register_all_tools(self):
        """将所有分析工具注册到 Toolkit"""
        tools = [
            analyze_profitability, analyze_growth, analyze_financial_health,
            analyze_valuation_ratios, analyze_efficiency_ratios,
            analyze_trend_following, analyze_mean_reversion, analyze_momentum, analyze_volatility,
            analyze_insider_trading, analyze_news_sentiment,
            dcf_valuation_analysis, owner_earnings_valuation_analysis,
            ev_ebitda_valuation_analysis, residual_income_valuation_analysis,
        ]
        
        for tool_func in tools:
            # 直接注册工具函数，AgentScope 会自动解析 docstring
            self.toolkit.register_tool_function(tool_func)
    
    def get_toolkit(self) -> Toolkit:
        """获取Toolkit实例"""
        return self.toolkit
    
    def _get_persona_config(self, analyst_persona: str) -> Dict[str, Any]:
        """获取 persona 配置"""
        persona_key = self.PERSONA_KEY_MAP.get(analyst_persona, "comprehensive_analyst")
        return self.personas_config.get(persona_key, {})
    
    def _get_persona_description(self, analyst_persona: str) -> str:
        """从 YAML 配置获取 persona 描述"""
        return self._get_persona_config(analyst_persona).get("description", "")
    
    async def select_tools_with_llm(self, llm, analyst_persona: str, ticker: str,
                                   market_conditions: Dict[str, Any], 
                                   analysis_objective: str = "Comprehensive investment analysis") -> Dict[str, Any]:
        """使用 LLM 选择分析工具"""
        try:
            # 获取 persona 描述
            persona_description = self._get_persona_description(analyst_persona)
            
            # 从文件加载 prompt
            prompt = self.prompt_loader.load_prompt(
                "analyst",
                "tool_selection",
                {
                    "analyst_persona": analyst_persona,
                    "ticker": ticker,
                    "analysis_objective": analysis_objective,
                    "persona_description": persona_description,
                    "tools_description": self.toolkit.get_json_schemas()
                }
            )

            # 调用 LLM
            messages = [{"role": "user", "content": prompt}]
            response = llm(messages=messages, temperature=0.7)
            response_text = response["content"].strip()

            # 提取 JSON
            json_text = self._extract_json(response_text)
            selection_result = json.loads(json_text)
            
            # 验证并返回
            return self._validate_selection(selection_result)
            
        except Exception as e:
            print(f"⚠️ LLM tool selection failed: {str(e)}")
            return []
    
    def _extract_json(self, text: str) -> str:
        """从响应文本中提取 JSON"""
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            return text[start:end].strip()
        else:
            start = text.find("{")
            end = text.rfind("}") + 1
            return text[start:end]
    
    def _validate_selection(self, selection_result: Dict[str, Any]) -> Dict[str, Any]:
        """验证工具选择结果"""
        if "selected_tools" not in selection_result:
            raise ValueError("Missing selected_tools in response")
        
        # 过滤有效的工具
        valid_tools = [
            tool for tool in selection_result["selected_tools"]
            if tool.get("tool_name") in self.tool_functions
        ]
        
        return {
            "selected_tools": valid_tools,
            "analysis_strategy": selection_result.get("analysis_strategy", ""),
            "synthesis_approach": selection_result.get("synthesis_approach", ""),
            "tool_count": len(valid_tools)
        }

    
    def _get_api_key(self, tool_name: str) -> str:
        """根据工具名称获取对应的 API key"""
        category = self.TOOL_CATEGORIES.get(tool_name)
        
        if category in ["fundamental", "valuation"]:
            key_name = "FINANCIAL_DATASETS_API_KEY"
        else:  # technical, sentiment
            key_name = "FINNHUB_API_KEY"
        
        api_key = os.getenv(key_name)

        if not api_key:
            print(f"⚠️ API key not found: {key_name} for {tool_name}")
        
        return api_key
    
    async def execute_selected_tools(self, selected_tools: List[Dict[str, Any]], 
                                     ticker: str, **kwargs) -> List[Dict[str, Any]]:
        """执行选中的工具"""
        tool_results = []
        
        for tool_selection in selected_tools:
            tool_name = tool_selection["tool_name"]
            
            # 获取工具函数
            tool_func = self.tool_functions.get(tool_name)
            if not tool_func:
                continue
            
            try:
                # 准备参数
                tool_kwargs = {
                    "ticker": ticker,
                    "api_key": self._get_api_key(tool_name),
                    "end_date": kwargs.get("end_date"),
                }
                
                # 技术分析和情绪分析需要 start_date
                category = self.TOOL_CATEGORIES[tool_name]
                if category in ["technical", "sentiment"]:
                    tool_kwargs["start_date"] = kwargs.get("start_date")
                
                # 直接调用工具函数
                result = tool_func(**tool_kwargs)
                
                # 添加元信息
                result["tool_name"] = tool_name
                result["selection_reason"] = tool_selection.get("reason", "")
                tool_results.append(result)
                
            except Exception as e:
                print(f"❌ Tool {tool_name} failed: {str(e)}")
                tool_results.append({
                    "tool_name": tool_name,
                    "error": str(e),
                    "signal": "neutral",
                    "confidence": 0,
                })
        
        return tool_results
    
    def synthesize_results_with_llm(self, tool_results: List[Dict[str, Any]], 
                                   selection_result: Dict[str, Any], 
                                   llm, ticker: str, analyst_persona: str) -> Dict[str, Any]:
        """使用 LLM 综合工具结果"""
        try:
            # 准备工具结果摘要
            tool_summaries = [
                {
                    "tool_name": result.get("tool_name", "unknown"),
                    "signal": result.get("signal", "neutral"),
                    "key_metrics": result.get("metrics", result.get("valuation", {})),
                    "selection_reason": result.get("selection_reason", "")
                }
                for result in tool_results if "error" not in result
            ]
            
            tool_summaries_json = json.dumps(tool_summaries, indent=2, ensure_ascii=False)
            
            # 加载 prompt
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
            
            # 调用 LLM
            messages = [{"role": "user", "content": prompt}]
            response = llm(messages=messages, temperature=0.7)
            response_text = response["content"].strip()
            
            # 提取并解析 JSON
            json_text = self._extract_json(response_text)
            synthesis_result = json.loads(json_text)
            
            return {
                "signal": synthesis_result.get("signal", "neutral"),
                "confidence": max(0, min(100, synthesis_result.get("confidence", 50))),
                "reasoning": synthesis_result.get("reasoning", ""),
                "tool_impact_analysis": synthesis_result.get("tool_impact_analysis", ""),
                "synthesis_method": "llm_based"
            }
            
        except Exception as e:
            print(f"⚠️ Synthesis failed: {str(e)}")
            return {
                "signal": "neutral",
                "confidence": 50,
                "reasoning": "Failed to synthesize results",
                "tool_impact_analysis": "",
                "synthesis_method": "error"
            }
