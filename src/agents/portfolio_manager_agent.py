"""
Portfolio Manager Agent - 投资组合管理 Agent
提供统一的投资组合管理接口
"""
from typing import Dict, Any, Optional, Literal
import json
import pdb

from .base_agent import BaseAgent
from ..graph.state import AgentState, show_agent_reasoning, create_message
from ..utils.progress import progress
from ..agents.agentscope_prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from typing_extensions import Literal as LiteralType
from ..utils.llm import call_llm


class PortfolioDecision(BaseModel):
    """投资决策模型"""
    action: LiteralType["long", "short", "hold"]
    quantity: Optional[int] = Field(default=0, description="交易股数（portfolio模式使用）")
    confidence: float = Field(description="决策置信度，0.0到100.0之间")
    reasoning: str = Field(description="决策理由")


class PortfolioManagerOutput(BaseModel):
    """投资组合管理输出"""
    decisions: dict[str, PortfolioDecision] = Field(description="ticker到交易决策的映射")


class PortfolioManagerAgent(BaseAgent):
    """投资组合管理 Agent"""
    
    def __init__(self, 
                 agent_id: str = "portfolio_manager",
                 mode: Literal["direction", "portfolio"] = "direction",
                 config: Optional[Dict[str, Any]] = None):
        """
        初始化投资组合管理 Agent
        
        Args:
            agent_id: Agent ID
            mode: 模式
                - "direction": 仅决策方向（long/short/hold），不包含具体数量
                - "portfolio": 包含具体数量决策，考虑当前持仓
            config: 配置字典
        
        Examples:
            >>> # 方向决策模式
            >>> agent = PortfolioManagerAgent(mode="direction")
            >>> 
            >>> # Portfolio 模式（包含数量）
            >>> agent = PortfolioManagerAgent(mode="portfolio")
        """
        super().__init__(agent_id, "portfolio_manager", config)
        self.mode = mode
    
    def execute(self, state: AgentState) -> Dict[str, Any]:
        """
        执行投资组合管理逻辑
        
        Args:
            state: AgentState
        
        Returns:
            更新后的状态字典
        """
        analyst_signals = state["data"]["analyst_signals"]
        tickers = state["data"]["tickers"]
        
        # Debug信息
        print(f"投资组合管理器收到的分析师信号键: {list(analyst_signals.keys())}")
        
        # 收集每个ticker的信号
        signals_by_ticker = {}
        current_prices = {}
        
        for ticker in tickers:
            progress.update_status(self.agent_id, ticker, "收集分析师信号")
            
            ticker_signals = self._collect_signals_for_ticker(
                ticker, analyst_signals, current_prices
            )
            signals_by_ticker[ticker] = ticker_signals
            
            print(f"{ticker} 收集到的信号数量: {len(ticker_signals)}")
        
        state["data"]["current_prices"] = current_prices
        progress.update_status(self.agent_id, None, "生成投资决策")
        
        # 根据模式生成决策
        if self.mode == "direction":
            result = self._generate_direction_decision(
                tickers, signals_by_ticker, state
            )
        else:  # portfolio mode
            result = self._generate_portfolio_decision(
                tickers, signals_by_ticker, state
            )
        # 创建消息（使用 AgentScope 格式）
        message = create_message(
            name=self.agent_id,
            content=json.dumps({
                ticker: decision.model_dump() 
                for ticker, decision in result.decisions.items()
            }),
            role="assistant",
            metadata={"mode": self.mode}
        )
        
        # 显示推理过程
        if state["metadata"]["show_reasoning"]:
            mode_name = "Portfolio Manager (Direction)" if self.mode == "direction" else "Portfolio Manager (Portfolio)"
            show_agent_reasoning({
                ticker: decision.model_dump() 
                for ticker, decision in result.decisions.items()
            }, mode_name)
        
        progress.update_status(self.agent_id, None, "Done")
        
        return {
            "messages": state["messages"] + [message],
            "data": state["data"],
        }
    
    def _collect_signals_for_ticker(self, ticker: str, 
                                   analyst_signals: Dict[str, Any],
                                   current_prices: Dict[str, float]) -> Dict[str, Dict]:
        """
        收集单个ticker的所有分析师信号
        
        Args:
            ticker: 股票代码
            analyst_signals: 所有分析师的信号
            current_prices: 当前价格字典（用于存储）
        
        Returns:
            该ticker的信号字典
        """
        ticker_signals = {}
        
        for agent, signals in analyst_signals.items():
            if agent.startswith("risk_management_agent"):
                # 风险管理agent - 提取风险信息
                if ticker in signals:
                    risk_info = signals[ticker]
                    ticker_signals[agent] = {
                        "type": "risk_assessment",
                        "risk_level": risk_info.get("risk_level", "unknown"),
                        "risk_score": risk_info.get("risk_score", 50),
                        "risk_assessment": risk_info.get("risk_assessment", "")
                    }
                    current_prices[ticker] = risk_info.get("current_price", 0)
            elif ticker in signals:
                # 第一轮格式 - 分析师信号
                if "signal" in signals[ticker] and "confidence" in signals[ticker]:
                    ticker_signals[agent] = {
                        "type": "investment_signal", 
                        "signal": signals[ticker]["signal"], 
                        "confidence": signals[ticker]["confidence"]
                    }
            elif "ticker_signals" in signals:
                # 第二轮格式 - 搜索ticker_signals列表
                for ts in signals["ticker_signals"]:
                    if isinstance(ts, dict) and ts.get("ticker") == ticker:
                        ticker_signals[agent] = {
                            "type": "investment_signal",
                            "signal": ts["signal"], 
                            "confidence": ts["confidence"]
                        }
                        break
        
        return ticker_signals
    
    def _generate_direction_decision(self, tickers: list[str],
                                    signals_by_ticker: dict[str, dict],
                                    state: AgentState) -> PortfolioManagerOutput:
        """生成方向决策（不包含数量）"""
        # 加载 prompt
        try:
            system_prompt = self.load_prompt("direction_decision_system", {})
            human_prompt = self.load_prompt("direction_decision_human", {})
            template = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", human_prompt)
            ])
        except FileNotFoundError:
            # 使用硬编码模板
            template = self._create_hardcoded_direction_template()
        
        # 获取分析师权重信息
        analyst_weights_info = self._format_analyst_weights(state)
        
        # 生成prompt
        prompt_data = {
            "signals_by_ticker": json.dumps(signals_by_ticker, indent=2),
            "analyst_weights_info": analyst_weights_info,
            "analyst_weights_separator": "\n" if analyst_weights_info else "",
        }
        
        prompt = template.invoke(prompt_data)
        
        # 创建默认工厂
        def create_default_output():
            return PortfolioManagerOutput(
                decisions={
                    ticker: PortfolioDecision(
                        action="hold", 
                        confidence=0.0, 
                        reasoning="默认决策: hold"
                    ) for ticker in tickers
                }
            )
        
        return call_llm(
            prompt=prompt,
            pydantic_model=PortfolioManagerOutput,
            agent_name=self.agent_id,
            state=state,
            default_factory=create_default_output,
        )
    
    def _generate_portfolio_decision(self, tickers: list[str],
                                    signals_by_ticker: dict[str, dict],
                                    state: AgentState) -> PortfolioManagerOutput:
        """生成Portfolio决策（包含数量）"""
        portfolio = state["data"]["portfolio"]
        current_prices = state["data"]["current_prices"]
        
        # 计算每个ticker的最大股数
        max_shares = {}
        for ticker in tickers:
            # 从risk manager获取仓位限制
            risk_manager_id = self._get_risk_manager_id()
            risk_data = state["data"]["analyst_signals"].get(risk_manager_id, {}).get(ticker, {})
            
            remaining_limit = risk_data.get("remaining_position_limit", 0)
            price = current_prices.get(ticker, 0)
            
            if price > 0:
                max_shares[ticker] = int(remaining_limit / price)
            else:
                max_shares[ticker] = 0
        
        # 加载 prompt
        system_prompt = self.load_prompt("portfolio_decision_system", {})
        human_prompt = self.load_prompt("portfolio_decision_human", {})
        template = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", human_prompt)
        ])
    
        
        # 获取分析师权重
        analyst_weights_info = self._format_analyst_weights(state)
        
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
        
        # 创建默认工厂
        def create_default_output():
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
        # pdb.set_trace()
        return call_llm(
            prompt=prompt,
            pydantic_model=PortfolioManagerOutput,
            agent_name=self.agent_id,
            state=state,
            default_factory=create_default_output,
        )
    
    def _get_risk_manager_id(self) -> str:
        """获取对应的风险管理器ID"""
        if self.agent_id.startswith("portfolio_manager_portfolio_"):
            suffix = self.agent_id.split('_')[-1]
            return f"risk_management_agent_portfolio_{suffix}"
        elif self.mode == "portfolio":
            return "risk_management_agent_portfolio"
        else:
            return "risk_management_agent"
    
    def _format_analyst_weights(self, state: AgentState) -> str:
        """格式化分析师权重信息"""
        analyst_weights = state.get("data", {}).get("analyst_weights", {})
        okr_state = state.get("data", {}).get("okr_state", {})
        
        if not analyst_weights:
            return ""
        
        info = "分析师表现权重（基于最近的投资信号准确性）:\n"
        sorted_weights = sorted(analyst_weights.items(), key=lambda x: x[1], reverse=True)
        
        for analyst_id, weight in sorted_weights:
            new_hire_info = ""
            if okr_state and okr_state.get("new_hires", {}).get(analyst_id):
                new_hire_info = " (新入职分析师)"
            
            bar_length = int(weight * 20)
            bar = "█" * bar_length + "░" * (20 - bar_length)
            
            info += f"  {analyst_id}: {weight:.3f} {bar}{new_hire_info}\n"
        
        info += "\n💡 建议: 根据权重级别考虑不同分析师建议的重要性。"
        return info
    
    def _create_hardcoded_direction_template(self) -> ChatPromptTemplate:
        """创建硬编码的方向决策模板"""
        # 简化版，实际应该从 portfolio_manager.py 复制
        return ChatPromptTemplate.from_messages([
            ("system", "You are a portfolio manager making direction decisions."),
            ("human", "Signals: {signals_by_ticker}\n{analyst_weights_info}")
        ])
    
    def _create_hardcoded_portfolio_template(self) -> ChatPromptTemplate:
        """创建硬编码的portfolio决策模板"""
        # 简化版，实际应该从 portfolio_manager_portfolio.py 复制
        return ChatPromptTemplate.from_messages([
            ("system", "You are a portfolio manager making quantity decisions."),
            ("human", "Signals: {signals_by_ticker}\nPrices: {current_prices}")
        ])

