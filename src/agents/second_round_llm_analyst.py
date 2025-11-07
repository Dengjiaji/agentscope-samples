#!/usr/bin/env python3
"""
第二轮LLM-based分析师
基于第一轮结果、通知和Pipeline信息生成修正后的投资信号
"""

from typing import Dict, Any, List

from ..graph.state import AgentState, create_message
from ..utils.llm import call_llm
from ..utils.json_utils import quiet_json_dumps
from ..data.second_round_signals import SecondRoundAnalysis, AnalystPersona, TickerSignal
from src.communication.cfg import ANALYST_PERSONAS
from .prompt_loader import PromptLoader

_prompt_loader = PromptLoader()


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
    
    # 准备prompt变量
    analysis_focus_str = "\n".join([f"- {focus}" for focus in persona.analysis_focus])
    
    notifications_str = (
        "\n".join([f"- {notif.get('sender', 'Unknown')}: {notif.get('content', '')}" 
                   for notif in notifications])
        if notifications else "No notifications from other analysts yet"
    )
    
    # 生成分ticker的报告
    ticker_reports = []
    for i, ticker in enumerate(tickers, 1):
        ticker_first_round = {}
        if isinstance(first_round_analysis, dict):
            if 'ticker_signals' in first_round_analysis:
                for signal in first_round_analysis['ticker_signals']:
                    if signal.get('ticker') == ticker:
                        ticker_first_round = signal
                        break
            else:
                ticker_first_round = first_round_analysis.get(ticker, {})
        
        ticker_report = f"""## Stock {i}: {ticker}

### Your First Round Analysis for {ticker}

Analysis Result and Thought Process:
{quiet_json_dumps(ticker_first_round['tool_analysis']['synthesis_details'], ensure_ascii=False, indent=2)}
Analysis Tools Selection and Reasoning:
{quiet_json_dumps(ticker_first_round['tool_selection'], ensure_ascii=False, indent=2)}

"""
        ticker_reports.append(ticker_report)
    
    # 使用 PromptLoader 加载和渲染 prompts
    variables = {
        "analyst_name": persona.name,
        "specialty": persona.specialty,
        "analysis_focus": analysis_focus_str,
        "decision_style": persona.decision_style,
        "risk_preference": persona.risk_preference,
        "ticker_reports": "\n".join(ticker_reports),
        "notifications": notifications_str,
        "agent_id": agent_id
    }

    system_prompt = _prompt_loader.load_prompt("analyst", "second_round_system", variables)
    human_prompt = _prompt_loader.load_prompt("analyst", "second_round_human", variables)

    full_prompt = f"{system_prompt}\n\n{human_prompt}"
    
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
            prompt=full_prompt,
            pydantic_model=SecondRoundAnalysis,
            agent_name=f"{agent_id}_second_round",
            state=state,
            default_factory=create_default_analysis
        )
        
        # 确保analyst_id和analyst_name正确设置
        result.analyst_id = agent_id
        result.analyst_name = persona.name
        # pdb.set_trace()

        return result
        
    except Exception as e:
        print(f"❌ {persona.name} LLM analysis failed: {str(e)}")
        return create_default_analysis()


def format_second_round_result_for_state(analysis: SecondRoundAnalysis) -> Dict[str, Any]:
    """将第二轮分析结果格式化为适合存储在AgentState中的格式"""
    return {
        "analyst_id": analysis.analyst_id,
        "analyst_name": analysis.analyst_name,
        "ticker_signals": [signal.model_dump() for signal in analysis.ticker_signals],
        "timestamp": analysis.timestamp.isoformat(),
        "analysis_type": "second_round_llm"
    }
