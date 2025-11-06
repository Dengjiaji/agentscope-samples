"""
Portfolio Manager Agent - 投资组合管理 Agent
提供统一的投资组合管理接口
"""
from typing import Dict, Any, Optional, Literal, List
import json
import pdb

from .base_agent import BaseAgent
from ..graph.state import AgentState, show_agent_reasoning, create_message
from ..utils.progress import progress
from ..agents.agentscope_prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from typing_extensions import Literal as LiteralType
from ..utils.llm import call_llm
from ..memory.framework_bridge import get_memory_bridge


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
            if agent.startswith("risk_manager"):
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
        progress.update_status(self.agent_id, None, "检索历史决策经验")
        relevant_memories = self._recall_relevant_memories(tickers, signals_by_ticker, state)
        
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
        
        formatted_memories = self._format_memories_for_prompt(relevant_memories)
        
        # 生成prompt
        prompt_data = {
            "signals_by_ticker": json.dumps(signals_by_ticker, indent=2),
            "analyst_weights_info": analyst_weights_info,
            "analyst_weights_separator": "\n" if analyst_weights_info else "",
            "relevant_past_experiences": formatted_memories,  # ⭐ 注入历史经验
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
        
        progress.update_status(self.agent_id, None, "基于信号和历史经验生成决策")
        
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
        progress.update_status(self.agent_id, None, "检索历史决策经验")
        relevant_memories = self._recall_relevant_memories(tickers, signals_by_ticker, state)
        
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
        
        formatted_memories = self._format_memories_for_prompt(relevant_memories)
        
        # 生成prompt
        prompt_data = {
            "signals_by_ticker": json.dumps(signals_by_ticker, indent=2, ensure_ascii=False),
            "current_prices": json.dumps(current_prices, indent=2),
            "max_shares": json.dumps(max_shares, indent=2),
            "portfolio_cash": f"{portfolio.get('cash', 0):.2f}",
            "portfolio_positions": json.dumps(portfolio.get("positions", {}), indent=2),
            "margin_requirement": f"{portfolio.get('margin_requirement', 0):.2f}",
            "total_margin_used": f"{portfolio.get('margin_used', 0):.2f}",
            # "analyst_weights_info": analyst_weights_info,
            # "analyst_weights_separator": "\n" if analyst_weights_info else "",
            "relevant_past_experiences": formatted_memories,  # 注入历史经验
        }
        
        prompt = template.invoke(prompt_data)
        # pdb.set_trace()

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
        
        progress.update_status(self.agent_id, None, "基于信号和历史经验生成决策")
        
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
            return f"risk_manager_{suffix}"
        elif self.mode == "portfolio":
            return "risk_manager"
        else:
            return "risk_manager"
    
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
    
    def _recall_relevant_memories(
        self, 
        tickers: List[str], 
        signals_by_ticker: Dict[str, Dict],
        state: AgentState,
        top_k: int = 3
    ) -> Dict[str, List[str]]:
        """
        步骤1：从memory系统检索相关的历史决策经验（代码层）
        
        为每个ticker检索相关的历史记忆，帮助PM做出更好的决策
        
        Args:
            tickers: 股票代码列表
            signals_by_ticker: 按ticker分组的分析师信号
            state: 当前状态
            top_k: 每个ticker返回的记忆数量
            
        Returns:
            字典，key为ticker，value为相关记忆列表
            例如: {
                'AAPL': [
                    "2024-01-15: 在相似信号组合下做了long决策，但结果亏损5%...",
                    "2024-01-20: 当技术指标与基本面冲突时需要更谨慎..."
                ]
            }
        """
        memories_by_ticker = {}
        
        try:
            # 获取memory bridge
            memory_bridge = get_memory_bridge()
            
            # ⭐ 统一使用 "portfolio_manager" 作为memory的user_id
            # 无论是direction还是portfolio模式，都使用同一个memory space
            # 这样可以共享经验，避免记忆分散
            # 注意：portfolio_manager 已在服务器初始化时注册，此处无需重复注册
            memory_user_id = "portfolio_manager"
            
            # 为每个ticker生成搜索query并检索记忆
            for ticker in tickers:
                # 生成搜索query（基于当前信号组合）
                ticker_signals = signals_by_ticker.get(ticker, {})
                query = self._generate_memory_query(ticker, ticker_signals)
                
                # 从memory系统检索相关记忆
                try:
                    relevant_memories = memory_bridge.get_relevant_memories(
                        analyst_id=memory_user_id,  # 统一使用 "portfolio_manager"
                        query=query,
                        limit=top_k
                    )
                    
                    # 格式化记忆为可读字符串
                    memory_strings = []
                    for mem in relevant_memories:
                        if isinstance(mem, dict):
                            memory_content = mem.get('memory', str(mem))
                            memory_strings.append(memory_content)
                        else:
                            memory_strings.append(str(mem))
                    
                    memories_by_ticker[ticker] = memory_strings
                    
                    if memory_strings:
                        print(f"✅ {ticker}: 检索到 {len(memory_strings)} 条相关历史经验")
                    
                except Exception as e:
                    print(f"⚠️ {ticker}: Memory检索失败 - {e}")
                    memories_by_ticker[ticker] = []
            
        except Exception as e:
            print(f"⚠️ Memory系统不可用 - {e}")
            # 如果memory系统不可用，返回空字典
            for ticker in tickers:
                memories_by_ticker[ticker] = []
        
        return memories_by_ticker
    
    def _generate_memory_query(self, ticker: str, ticker_signals: Dict[str, Dict]) -> str:
        """
        生成memory搜索query
        
        根据当前信号组合生成针对性的搜索query，找到类似情况下的历史决策
        
        Args:
            ticker: 股票代码
            ticker_signals: 该ticker的分析师信号
            
        Returns:
            搜索query字符串
        """
        # 提取信号方向和置信度
        signal_directions = []
        high_confidence_signals = []
        
        for agent_id, signal_data in ticker_signals.items():
            if signal_data.get("type") == "investment_signal":
                direction = signal_data.get("signal", "")
                confidence = signal_data.get("confidence", 0)
                
                signal_directions.append(direction)
                
                if confidence > 70:
                    high_confidence_signals.append(f"{agent_id}:{direction}")
        
        # 构建query
        query_parts = [f"{ticker} 投资决策"]
        
        # 添加主要信号方向
        if signal_directions:
            bullish_count = signal_directions.count("bullish")
            bearish_count = signal_directions.count("bearish")
            
            if bullish_count > bearish_count:
                query_parts.append("看多信号")
            elif bearish_count > bullish_count:
                query_parts.append("看空信号")
            else:
                query_parts.append("信号分歧")
        
        # 添加高置信度信号信息
        if high_confidence_signals:
            query_parts.append(f"高置信度分析师: {', '.join(high_confidence_signals[:2])}")
        
        query = " ".join(query_parts)
        return query
    
    def _format_memories_for_prompt(self, memories_by_ticker: Dict[str, List[str]]) -> str:
        """
        ⭐ 步骤2的辅助方法：格式化记忆为prompt可用的文本
        
        Args:
            memories_by_ticker: 按ticker分组的记忆
            
        Returns:
            格式化后的记忆文本
        """
        if not memories_by_ticker or not any(memories_by_ticker.values()):
            return "暂无相关历史经验。"
        
        formatted_lines = []
        
        for ticker, memories in memories_by_ticker.items():
            if not memories:
                continue
            
            formatted_lines.append(f"\n**{ticker} 相关历史经验:**")
            for i, memory in enumerate(memories, 1):
                formatted_lines.append(f"  {i}. {memory}")
        
        if not formatted_lines:
            return "暂无相关历史经验。"
        
        return "\n".join(formatted_lines)
    
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

