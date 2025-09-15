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
    """创建第二轮分析的prompt模板"""
    template = ChatPromptTemplate.from_messages([
        ("system", """你是一位专业的{analyst_name}，具有以下特征：

专业领域：{specialty}
分析重点：{analysis_focus}
决策风格：{decision_style}  
风险偏好：{risk_preference}

现在你需要基于第一轮分析结果、其他分析师的通知以及你进行第一轮分析的Pipeline信息，重新评估你的投资观点。

请以你的专业视角，综合考虑以下信息：
1. 你自己的第一轮分析结果
2. 其他分析师发送的通知和观点
3. 整体分析摘要
4. 你进行第一轮分析的Pipeline信息

你需要为每个股票给出：
- signal: "bullish"（看涨）, "bearish"（看跌）, "neutral"（中性）
- confidence: 0-100的整数（信心度）
- reasoning: 详细的判断理由

请以JSON格式返回结构化的分析结果。"""),        
        ("human", """=== 第二轮分析输入 ===

## 分析的股票列表
{tickers}

## 你的第一轮分析结果  
{first_round_analysis}

## 整体分析摘要
{overall_summary}

## 其他分析师的通知
{notifications}

## 你进行第一轮分析的Pipeline信息
{pipeline_info}

=== 分析要求 ===
请基于以上信息，重新评估你的投资观点。

从你作为{analyst_name}的专业角度出发，请以JSON格式返回分析结果。

要求的JSON格式示例：
{{
  "analyst_id": "{agent_id}",
  "analyst_name": "{analyst_name}",
  "ticker_signals": [
    {{
      "ticker": "AAPL",
      "signal": "bullish",
      "confidence": 75,
      "reasoning": "详细的判断理由..."
    }},
    {{
      "ticker": "MSFT", 
      "signal": "neutral",
      "confidence": 60,
      "reasoning": "详细的判断理由..."
    }}
  ]
}}

请严格按照此JSON格式返回分析结果。""")
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
    
    # 创建prompt模板
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
        notifications_str = "暂无其他分析师的通知"
    
    # 创建prompt
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
                    reasoning="LLM分析失败，保持中性观点"
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
        print(f"❌ {persona.name} LLM分析失败: {str(e)}")
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
