import json
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate

from src.graph.state import AgentState, show_agent_reasoning
from pydantic import BaseModel, Field
from typing_extensions import Literal
from src.utils.progress import progress
from src.utils.llm import call_llm


class PortfolioDecision(BaseModel):
    action: Literal["long", "short", "hold"]
    confidence: float = Field(description="Confidence in the decision, between 0.0 and 100.0")
    reasoning: str = Field(description="Reasoning for the decision")


class PortfolioManagerOutput(BaseModel):
    decisions: dict[str, PortfolioDecision] = Field(description="Dictionary of ticker to trading decisions")


##### Portfolio Management Agent #####
def portfolio_management_agent(state: AgentState, agent_id: str = "portfolio_manager"):
    """基于分析师信号做出最终投资方向决策"""

    # Get analyst signals
    analyst_signals = state["data"]["analyst_signals"]
    tickers = state["data"]["tickers"]
    
    # Debug: Print available analyst signals
    print(f"投资组合管理器收到的分析师信号键: {list(analyst_signals.keys())}")
    for agent_key, signals in analyst_signals.items():
        if isinstance(signals, dict):
            #format_second_round_result_for_state 因为第二轮结果经过这个函数有一个特定的格式
            if "ticker_signals" in signals:
                print(f"  {agent_key}: 第二轮格式，包含 {len(signals['ticker_signals'])} 个ticker信号")
            else:
                ticker_keys = [k for k in signals.keys() if k in tickers]
                print(f"  {agent_key}: 第一轮格式，包含ticker: {ticker_keys}")
        else:
            print(f"  警告: {agent_key}: 未知格式 - {type(signals)}")

    # Collect signals for every ticker
    signals_by_ticker = {}
    current_prices = {}

    for ticker in tickers:
        progress.update_status(agent_id, ticker, "收集分析师信号")

        # Get signals for the ticker from all analysts
        ticker_signals = {}
        for agent, signals in analyst_signals.items():
            # Handle different agent types and signal formats:
            # 1. Risk management agent: {ticker: {risk_level, risk_score, risk_assessment, ...}}
            # 2. First round format: {ticker: {signal, confidence, reasoning}}
            # 3. Second round format: {ticker_signals: [{ticker, signal, confidence, reasoning}]}
            
            if agent.startswith("risk_management_agent"):
                # Risk management agent - extract risk information
                if ticker in signals:
                    risk_info = signals[ticker]
                    ticker_signals[agent] = {
                        "type": "risk_assessment",
                        "risk_level": risk_info.get("risk_level", "unknown"),
                        "risk_score": risk_info.get("risk_score", 50),
                        "risk_assessment": risk_info.get("risk_assessment", "")
                    }
                    current_prices[ticker] = risk_info.get("current_price", 0)
                    print(f"  从 {agent} 获取 {ticker} 的风险评估: {risk_info.get('risk_level', 'unknown')} (评分: {risk_info.get('risk_score', 50)})")
            elif ticker in signals:
                # First round format - analyst signals
                if "signal" in signals[ticker] and "confidence" in signals[ticker]:
                    ticker_signals[agent] = {
                        "type": "investment_signal", 
                        "signal": signals[ticker]["signal"], 
                        "confidence": signals[ticker]["confidence"]
                    }
                    print(f"  从 {agent} 获取 {ticker} 的投资信号: {signals[ticker]['signal']}")
            elif "ticker_signals" in signals:
                # Second round format - search through ticker_signals list
                for ts in signals["ticker_signals"]:
                    # Handle case where ts might be a string instead of dict
                    if isinstance(ts, str):
                        print(f"  警告: 跳过字符串格式的信号: {ts[:100]}...")
                        continue
                    elif isinstance(ts, dict) and ts.get("ticker") == ticker:
                        ticker_signals[agent] = {
                            "type": "investment_signal",
                            "signal": ts["signal"], 
                            "confidence": ts["confidence"]
                        }
                        print(f"  从 {agent} 获取 {ticker} 的投资信号: {ts['signal']}")
                        break
        
        print(f"{ticker} 收集到的信号数量: {len(ticker_signals)}")
        signals_by_ticker[ticker] = ticker_signals
    state["data"]["current_prices"] = current_prices
    progress.update_status(agent_id, None, "生成投资方向决策")

    # Generate the trading decision
    result = generate_trading_decision(
        tickers=tickers,
        signals_by_ticker=signals_by_ticker,
        agent_id=agent_id,
        state=state,
    )

    # Create the portfolio management message
    message = HumanMessage(
        content=json.dumps({ticker: decision.model_dump() for ticker, decision in result.decisions.items()}),
        name=agent_id,
    )

    # Print the decision if the flag is set
    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning({ticker: decision.model_dump() for ticker, decision in result.decisions.items()}, "Portfolio Manager")

    progress.update_status(agent_id, None, "Done")

    return {
        "messages": state["messages"] + [message],
        "data": state["data"],
    }


def generate_trading_decision(
    tickers: list[str],
    signals_by_ticker: dict[str, dict],
    agent_id: str,
    state: AgentState,
) -> PortfolioManagerOutput:
    """基于分析师信号生成投资方向决策"""
    # Create the prompt template
    template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """你是一个投资组合管理者，需要基于多个分析师的信号做出最终的投资方向决策。

              重要说明：
              - 你的任务是为每只股票决定投资方向：long（看多）、short（看空）或hold（观望）
              - 不需要考虑具体的投资数量，只需要决定方向
              - 每个决策都是基于单位资产（比如1股）进行的
              - 需要综合考虑所有分析师的意见，包括他们的置信度

              可用的投资方向：
              - "long": 看多该股票，预期价格上涨
              - "short": 看空该股票，预期价格下跌  
              - "hold": 观望，不进行操作

              输入信息：
              - signals_by_ticker: 每只股票对应的分析师信号字典
              - analyst_weights: 基于绩效的分析师权重（如果可用）
              - 风险管理器提供风险评估信息（risk_level, risk_score等），不包含投资建议
              """,
            ),
            (
                "human",
                """基于团队的分析，为每只股票做出投资方向决策。

              各股票的分析师信号：
              {signals_by_ticker}

              {analyst_weights_info}{analyst_weights_separator}

              决策规则：
              - 综合考虑所有分析师的信号和置信度
              - 权重高的分析师意见应该获得更多考虑
              - 当分析师意见分歧较大时，选择hold观望
              - 当多数分析师意见一致且置信度高时，跟随主流意见
              - 风险管理器的风险评估信息应该作为重要参考，高风险股票需要更谨慎的决策

              请严格按照以下JSON格式输出：
              {{
                "decisions": {{
                  "TICKER1": {{
                    "action": "long/short/hold",
                    "confidence": 0到100之间的浮点数,
                    "reasoning": "详细说明你的决策理由，包括如何综合各分析师意见"
                  }},
                  "TICKER2": {{
                    ...
                  }},
                  ...
                }}
              }}
              """,
            ),
        ]
    )

    # 获取分析师权重信息
    analyst_weights = state.get("data", {}).get("analyst_weights", {})
    okr_state = state.get("data", {}).get("okr_state", {})
    # 格式化分析师权重信息
    analyst_weights_info = ""
    if analyst_weights:
        analyst_weights_info = "分析师绩效权重 (基于最近投资信号准确性):\n"
        # 按权重排序
        sorted_weights = sorted(analyst_weights.items(), key=lambda x: x[1], reverse=True)
        for analyst_id, weight in sorted_weights:
            # 检查是否是新员工
            new_hire_info = ""
            if okr_state and okr_state.get("new_hires", {}).get(analyst_id):
                new_hire_info = " (新入职分析师)"
            
            # 权重条形图
            bar_length = int(weight * 20)  # 最大20个字符
            bar = "█" * bar_length + "░" * (20 - bar_length)
            
            analyst_weights_info += f"  {analyst_id}: {weight:.3f} {bar}{new_hire_info}\n"
        
        analyst_weights_info += "\n💡 建议根据权重高低来考虑不同分析师建议的重要性。权重高的分析师建议应获得更多关注。"
    print('******************************',analyst_weights_info,'******************************')
    # Generate the prompt
    prompt_data = {
        "signals_by_ticker": json.dumps(signals_by_ticker, indent=2),
        "analyst_weights_info": analyst_weights_info,
        "analyst_weights_separator": "\n" if analyst_weights_info else "",
    }
    
    prompt = template.invoke(prompt_data)

    # Create default factory for PortfolioManagerOutput
    def create_default_portfolio_output():
        return PortfolioManagerOutput(decisions={ticker: PortfolioDecision(action="hold", confidence=0.0, reasoning="Default decision: hold") for ticker in tickers})

    return call_llm(
        prompt=prompt,
        pydantic_model=PortfolioManagerOutput,
        agent_name=agent_id,
        state=state,
        default_factory=create_default_portfolio_output,
    )
