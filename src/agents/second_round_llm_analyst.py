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
from ..data.second_round_signals import SecondRoundAnalysis, AnalystPersona, TickerSignal
from src.communication.cfg import ANALYST_PERSONAS
from .prompt_loader import get_prompt_loader
import pdb



def create_second_round_prompt_template(use_prompt_files: bool = True) -> ChatPromptTemplate:
    """
    Create second-round analysis prompt template
    
    Args:
        use_prompt_files: 是否使用外部 prompt 文件（默认 True）
    """
    # 尝试从文件加载
    if use_prompt_files:
        try:
            # 直接读取文件内容（不通过 prompt_loader，因为这些是 LangChain 模板）
            import pathlib
            prompts_dir = pathlib.Path(__file__).parent / "prompts" / "analyst"
            
            with open(prompts_dir / "second_round_system.md", 'r', encoding='utf-8') as f:
                system_template = f.read()
            
            with open(prompts_dir / "second_round_human.md", 'r', encoding='utf-8') as f:
                human_template = f.read()
            
            # 创建 LangChain 模板（使用 {variable} 格式）
            template = ChatPromptTemplate.from_messages([
                ("system", system_template),
                ("human", human_template)
            ])
            return template
        except FileNotFoundError:
            print(f"⚠️ Prompt files not found for second_round, using hardcoded templates")
    
    # 硬编码模板（向后兼容）
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

{ticker_reports}

## Notifications from Other Analysts
{notifications}

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
    
    # 生成分ticker的报告格式
    ticker_reports = []
    for i, ticker in enumerate(tickers, 1):
        # 提取该ticker的第一轮分析结果
        ticker_first_round = {}
        if isinstance(first_round_analysis, dict):
            # 如果first_round_analysis包含ticker_signals列表
            if 'ticker_signals' in first_round_analysis:
                for signal in first_round_analysis['ticker_signals']:
                    if signal.get('ticker') == ticker:
                        ticker_first_round = signal
                        break
            else:
                # 如果是直接的ticker->analysis映射
                ticker_first_round = first_round_analysis.get(ticker, {})
        
        ticker_report = f"""## Stock {i}: {ticker}

### Your First Round Analysis for {ticker}

Analysis Result and Thought Process:
{quiet_json_dumps(ticker_first_round['tool_analysis']['synthesis_details'], ensure_ascii=False, indent=2)}
Analysis Tools Selection and Reasoning:
{quiet_json_dumps(ticker_first_round['tool_selection'], ensure_ascii=False, indent=2)}

"""
        ticker_reports.append(ticker_report)
    
    ticker_reports_str = "\n".join(ticker_reports)
    
    # Create prompt
    prompt = prompt_template.format_messages(
        analyst_name=persona.name,
        specialty=persona.specialty,
        analysis_focus=analysis_focus_str,
        decision_style=persona.decision_style,
        risk_preference=persona.risk_preference,
        ticker_reports=ticker_reports_str,
        notifications=notifications_str,
        agent_id=agent_id  
    )
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
