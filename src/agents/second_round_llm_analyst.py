#!/usr/bin/env python3
"""
第二轮LLM-based分析师
基于第一轮结果、通知和Pipeline信息生成修正后的投资信号
"""

from typing import Dict, Any, List
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage

from ..graph.state import AgentState
from ..utils.llm import call_llm
from ..utils.json_utils import quiet_json_dumps
from ..models.second_round_signals import SecondRoundAnalysis, AnalystPersona, TickerSignal
from src.communication.cfg import ANALYST_PERSONAS




def create_second_round_prompt_template() -> ChatPromptTemplate:
    """Create second-round analysis prompt template"""
    template = ChatPromptTemplate.from_messages([
    ("system", """You are a professional {analyst_name} with the following characteristics:

Professional Field: {specialty}
Analysis Focus: {analysis_focus}
Decision Style: {decision_style}  
Risk Preference: {risk_preference}

Now you need to re-evaluate your investment perspective based on first-round analysis results, notifications from other analysts, and your first-round analysis Pipeline information.

Please consider the following information from your professional perspective:
1. Your own first-round analysis results
2. Notifications and viewpoints sent by other analysts
3. Overall analysis summary
4. Your first-round analysis Pipeline information

You need to provide for each stock:
- signal: "bullish" (bullish), "bearish" (bearish), "neutral" (neutral)
- confidence: integer from 0-100 (confidence level)
- reasoning: detailed judgment rationale

Please return structured analysis results in JSON format."""),        
    ("human", """=== Second Round Analysis Input ===

## Stock List for Analysis
{tickers}

## Your First Round Analysis Results  
{first_round_analysis}

## Overall Analysis Summary
{overall_summary}

## Notifications from Other Analysts
{notifications}

## Your First Round Analysis Pipeline Information
{pipeline_info}

=== Analysis Requirements ===
Please re-evaluate your investment perspective based on the above information.

From your professional perspective as {analyst_name}, please return analysis results in JSON format.

Required JSON format example:
{{
  "analyst_id": "{agent_id}",
  "analyst_name": "{analyst_name}",
  "ticker_signals": [
    {{
      "ticker": "AAPL",
      "signal": "bullish",
      "confidence": 75,
      "reasoning": "detailed judgment rationale..."
    }},
    {{
      "ticker": "MSFT", 
      "signal": "neutral",
      "confidence": 60,
      "reasoning": "detailed judgment rationale..."
    }}
  ]
}}

Please strictly return analysis results according to this JSON format.""")
])
    
    return template


def run_second_round_llm_analysis(
    agent_id: str,
    tickers: List[str], 
    first_round_analysis: Dict[str, Any],
    overall_summary: Dict[str, Any],
    notifications: List[Dict[str, Any]],
    state: AgentState
) -> SecondRoundAnalysis:
    """运行第二轮LLM分析"""
    
    # 获取分析师人格设定
    if agent_id not in ANALYST_PERSONAS:
        raise ValueError(f"Unknown analyst ID: {agent_id}")
    
    persona = ANALYST_PERSONAS[agent_id]
    
    # Create prompt template
    prompt_template = create_second_round_prompt_template()
    # 格式化分析重点为字符串
    analysis_focus_str = "\n".join([f"- {focus}" for focus in persona.analysis_focus])
    
    # 格式化通知信息
    notifications_str = ""
    if notifications:
        notifications_str = "\n".join([
            f"- {notif.get('sender', 'Unknown')}: {notif.get('content', '')}"
            for notif in notifications
        ])
    else:
        notifications_str = "No notifications from other analysts yet"
    
    # Create prompt
    prompt = prompt_template.format_messages(
        analyst_name=persona.name,
        specialty=persona.specialty,
        analysis_focus=analysis_focus_str,
        decision_style=persona.decision_style,
        risk_preference=persona.risk_preference,
        tickers=", ".join(tickers),
        first_round_analysis=quiet_json_dumps(first_round_analysis, ensure_ascii=False, indent=2),
        overall_summary=quiet_json_dumps(overall_summary, ensure_ascii=False, indent=2),
        notifications=notifications_str,
        pipeline_info = persona.pipeline_config,
        agent_id=agent_id  
    )
    # print(prompt)
    # 调用LLM
    def create_default_analysis():
        """创建默认分析结果"""
        return SecondRoundAnalysis(
            analyst_id=agent_id,
            analyst_name=persona.name,
            ticker_signals=[
                TickerSignal(
                    ticker=ticker,
                    signal="neutral", 
                    confidence=50,
                    reasoning="LLM analysis failed, maintaining neutral stance"
                ) for ticker in tickers
            ]
        )
    
    try:
        result = call_llm(
            prompt=prompt,
            pydantic_model=SecondRoundAnalysis,
            agent_name=f"{agent_id}_second_round",
            state=state,
            default_factory=create_default_analysis
        )
        
        # 确保analyst_id和analyst_name正确设置
        result.analyst_id = agent_id
        result.analyst_name = persona.name
        
        return result
        
    except Exception as e:
        print(f"❌ {persona.name} LLM analysis failed: {str(e)}")
        return create_default_analysis()


def format_second_round_result_for_state(analysis: SecondRoundAnalysis) -> Dict[str, Any]:
    """将第二轮分析结果格式化为适合存储在AgentState中的格式"""
    return {
        "analyst_id": analysis.analyst_id,
        "analyst_name": analysis.analyst_name,
        "ticker_signals": [signal.dict() for signal in analysis.ticker_signals],
        "timestamp": analysis.timestamp.isoformat(),
        "analysis_type": "second_round_llm"
    }
