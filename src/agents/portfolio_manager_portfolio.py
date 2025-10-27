"""
Portfolio模式的投资组合管理器
基于分析师信号做出具体的买入/卖出决策，包括数量和操作类型
"""
import json
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate

from src.graph.state import AgentState, show_agent_reasoning
from pydantic import BaseModel, Field
from typing_extensions import Literal
from src.utils.progress import progress
from src.utils.llm import call_llm
import pdb

class PortfolioDecision(BaseModel):
    """Portfolio模式的投资决策"""
    action: Literal["buy", "sell", "short", "cover", "hold"]
    quantity: int = Field(description="交易股数")
    confidence: float = Field(description="决策置信度，0.0到100.0之间")
    reasoning: str = Field(description="决策理由")


class PortfolioManagerOutput(BaseModel):
    decisions: dict[str, PortfolioDecision] = Field(description="ticker到交易决策的映射")


def portfolio_management_agent_portfolio(state: AgentState, agent_id: str = "portfolio_manager_portfolio"):
    """
    Portfolio模式的投资组合管理 - 做出最终交易决策并生成订单
    
    输出内容:
    - action: buy/sell/short/cover/hold
    - quantity: 交易股数
    - confidence: 置信度
    - reasoning: 决策理由
    """
    
    # 获取投资组合和分析师信号
    portfolio = state["data"]["portfolio"]
    analyst_signals = state["data"]["analyst_signals"]
    tickers = state["data"]["tickers"]
    
    # 为每个ticker获取仓位限制、当前价格和信号
    position_limits = {}
    current_prices = {}
    max_shares = {}
    signals_by_ticker = {}
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
    # pdb.set_trace()
    for ticker in tickers:
        progress.update_status(agent_id, ticker, "处理分析师信号")
        
        # 获取ticker的仓位限制和当前价格
        # 查找对应的风险管理器
        if agent_id.startswith("portfolio_manager_portfolio_"):
            suffix = agent_id.split('_')[-1]
            risk_manager_id = f"risk_management_agent_portfolio_{suffix}"
        else:
            risk_manager_id = "risk_management_agent_portfolio"
        
        risk_data = analyst_signals.get(risk_manager_id, {}).get(ticker, {})
        position_limits[ticker] = risk_data.get("remaining_position_limit", 0)
        current_prices[ticker] = risk_data.get("current_price", 0)
        
        # 基于仓位限制和价格计算允许的最大股数
        if current_prices[ticker] > 0:
            max_shares[ticker] = int(position_limits[ticker] / current_prices[ticker])
        else:
            max_shares[ticker] = 0
        
        # 获取ticker的信号
        ticker_signals = {}
        print(f"Portfolio Manager 处理 {ticker} 的信号，可用分析师: {list(analyst_signals.keys())}")
        for agent, signals in analyst_signals.items():
            # 跳过所有风险管理agent（它们的信号结构不同）
            if not agent.startswith("risk_management_agent"):
                # 处理新的分析师结果格式（包含ticker_signals数组）
                if isinstance(signals, dict) and "ticker_signals" in signals:
                    # 新格式：signals包含ticker_signals数组
                    print(f"  处理 {agent} 的新格式信号")
                    for ts in signals["ticker_signals"]:
                        if isinstance(ts, dict) and ts.get("ticker") == ticker:
                            ticker_signals[agent] = {
                                "signal": ts["signal"],
                                "confidence": ts["confidence"]
                            }
                            print(f"    找到 {ticker} 信号: {ts['signal']} (置信度: {ts['confidence']})")
                            break
                # 处理旧格式：signals直接包含ticker键
                elif isinstance(signals, dict) and ticker in signals:
                    # 处理不同的信号格式
                    if isinstance(signals[ticker], dict):
                        if "signal" in signals[ticker] and "confidence" in signals[ticker]:
                            ticker_signals[agent] = {
                                "signal": signals[ticker]["signal"],
                                "confidence": signals[ticker]["confidence"]
                            }
                        # 处理第二轮格式
                        elif "ticker_signals" in signals[ticker]:
                            for ts in signals[ticker]["ticker_signals"]:
                                if isinstance(ts, dict) and ts.get("ticker") == ticker:
                                    ticker_signals[agent] = {
                                        "signal": ts["signal"],
                                        "confidence": ts["confidence"]
                                    }
                                    break
        
        print(f"  {ticker} 最终收集到的信号: {ticker_signals}")
        signals_by_ticker[ticker] = ticker_signals
    
    # 将current_prices添加到state data中，使其在整个工作流中可用
    state["data"]["current_prices"] = current_prices
    
    progress.update_status(agent_id, None, "生成交易决策")
    # pdb.set_trace()
    # 生成交易决策
    result = generate_trading_decision(
        tickers=tickers,
        signals_by_ticker=signals_by_ticker,
        current_prices=current_prices,
        max_shares=max_shares,
        portfolio=portfolio,
        agent_id=agent_id,
        state=state,
    )
    
    # 创建投资组合管理消息
    message = HumanMessage(
        content=json.dumps({ticker: decision.model_dump() for ticker, decision in result.decisions.items()}),
        name=agent_id,
    )
    
    # 如果设置了标志，打印决策
    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning({ticker: decision.model_dump() for ticker, decision in result.decisions.items()}, "Portfolio Manager (Portfolio Mode)")
    
    progress.update_status(agent_id, None, "Done")
    
    return {
        "messages": state["messages"] + [message],
        "data": state["data"],
    }


def generate_trading_decision(
    tickers: list[str],
    signals_by_ticker: dict[str, dict],
    current_prices: dict[str, float],
    max_shares: dict[str, int],
    portfolio: dict,
    agent_id: str,
    state: AgentState,
) -> PortfolioManagerOutput:
    """基于LLM生成交易决策，带有重试逻辑"""
    
    # 创建prompt模板
    template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """你是一个投资组合管理者，基于多个ticker做出最终交易决策。

              重要提示: 你正在管理一个包含现有持仓的投资组合。portfolio_positions显示:
              - "long": 当前持有的多头股数
              - "short": 当前持有的空头股数
              - "long_cost_basis": 多头股票的平均买入价
              - "short_cost_basis": 空头股票的平均卖出价
              
              交易规则:
              - 对于多头持仓:
                * 只有在有可用现金时才能买入
                * 只有在当前持有该ticker的多头股票时才能卖出
                * 卖出数量必须 ≤ 当前多头持仓股数
                * 买入数量必须 ≤ 该ticker的max_shares
              
              - 对于空头持仓:
                * 只有在有可用保证金时才能做空（持仓价值 × 保证金要求）
                * 只有在当前持有该ticker的空头股票时才能平空
                * 平空数量必须 ≤ 当前空头持仓股数
                * 做空数量必须遵守保证金要求
              
              - max_shares值已经预先计算以遵守仓位限制
              - 根据信号同时考虑多头和空头机会
              - 通过多头和空头暴露维持适当的风险管理

              可用操作:
              - "buy": 开仓或增加多头持仓
              - "sell": 平仓或减少多头持仓（仅当你当前持有多头股票时）
              - "short": 开仓或增加空头持仓
              - "cover": 平仓或减少空头持仓（仅当你当前持有空头股票时）
              - "hold": 维持当前持仓不做任何变化（hold时数量应为0）

              输入信息:
              - signals_by_ticker: ticker → 信号的字典
              - max_shares: 每个ticker允许的最大股数
              - portfolio_cash: 投资组合中的当前现金
              - portfolio_positions: 当前持仓（包括多头和空头）
              - current_prices: 每个ticker的当前价格
              - margin_requirement: 空头持仓的当前保证金要求（例如0.5表示50%）
              - total_margin_used: 当前使用的总保证金
              
              - 如果分析师权重信息可用，优先考虑权重较高的分析师的建议
              """,
            ),
            (
                "human",
                """基于团队的分析，为每个ticker做出你的交易决策。

              以下是按ticker分类的信号:
              {signals_by_ticker}

              当前价格:
              {current_prices}

              允许购买的最大股数:
              {max_shares}

              投资组合现金: {portfolio_cash}
              当前持仓: {portfolio_positions}
              当前保证金要求: {margin_requirement}
              已使用总保证金: {total_margin_used}
              
              {analyst_weights_info}{analyst_weights_separator}

              重要决策规则:
              - 如果你当前持有某ticker的多头股票（long > 0），你可以:
                * HOLD: 保持当前持仓（quantity = 0）
                * SELL: 减少/平仓多头持仓（quantity = 要卖出的股数）
                * BUY: 增加多头持仓（quantity = 要额外买入的股数）
                
              - 如果你当前持有某ticker的空头股票（short > 0），你可以:
                * HOLD: 保持当前持仓（quantity = 0）
                * COVER: 减少/平仓空头持仓（quantity = 要平仓的股数）
                * SHORT: 增加空头持仓（quantity = 要额外做空的股数）
                
              - 如果你当前没有持有某ticker的股票（long = 0, short = 0），你可以:
                * HOLD: 保持观望（quantity = 0）
                * BUY: 开新的多头持仓（quantity = 要买入的股数）
                * SHORT: 开新的空头持仓（quantity = 要做空的股数）

              严格按照以下JSON结构输出:
              {{
                "decisions": {{
                  "TICKER1": {{
                    "action": "buy/sell/short/cover/hold",
                    "quantity": 整数,
                    "confidence": 0到100之间的浮点数,
                    "reasoning": "解释你的决策的字符串，考虑当前持仓"
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
        analyst_weights_info = "分析师表现权重（基于最近的投资信号准确性）:\n"
        # 按权重排序
        sorted_weights = sorted(analyst_weights.items(), key=lambda x: x[1], reverse=True)
        for analyst_id, weight in sorted_weights:
            # 检查是否是新员工
            new_hire_info = ""
            if okr_state and okr_state.get("new_hires", {}).get(analyst_id):
                new_hire_info = " (新入职分析师)"
            
            # 权重条形图
            bar_length = int(weight * 20)  # 最多20个字符
            bar = "█" * bar_length + "░" * (20 - bar_length)
            
            analyst_weights_info += f"  {analyst_id}: {weight:.3f} {bar}{new_hire_info}\n"
        
        analyst_weights_info += "\n💡 建议: 根据权重级别考虑不同分析师建议的重要性。权重较高的分析师的建议应该得到更多关注。"
    
    # 生成prompt
    prompt_data = {
        "signals_by_ticker": json.dumps(signals_by_ticker, indent=2, ensure_ascii=False),
        "current_prices": json.dumps(current_prices, indent=2),
        "max_shares": json.dumps(max_shares, indent=2),
        "portfolio_cash": f"{portfolio.get('cash', 0):.2f}",
        "portfolio_positions": json.dumps(portfolio.get("positions", {}), indent=2),
        "margin_requirement": f"{portfolio.get('margin_requirement', 0):.2f}",
        "total_margin_used": f"{portfolio.get('margin_used', 0):.2f}",
        "analyst_weights_info": analyst_weights_info,
        "analyst_weights_separator": "\n" if analyst_weights_info else "",
    }
    
    prompt = template.invoke(prompt_data)
    
    # 为PortfolioManagerOutput创建默认工厂
    def create_default_portfolio_output():
        return PortfolioManagerOutput(
            decisions={
                ticker: PortfolioDecision(
                    action="hold",
                    quantity=0,
                    confidence=0.0,
                    reasoning="默认决策: hold"
                ) for ticker in tickers
            }
        )
    
    return call_llm(
        prompt=prompt,
        pydantic_model=PortfolioManagerOutput,
        agent_name=agent_id,
        state=state,
        default_factory=create_default_portfolio_output,
    )

