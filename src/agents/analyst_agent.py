"""
Analyst Agent - 统一的分析师 Agent 实现
基于 AgentScope AgentBase 实现，使用Toolkit和Msg
"""
import asyncio
from typing import Dict, Any, Optional, List
import json

from agentscope.agent import AgentBase
from agentscope.message import Msg
from agentscope.tool import Toolkit

from ..graph.state import AgentState
from ..utils.progress import progress
from ..llm.models import get_model  # 使用 AgentScope 模型
from .llm_tool_selector import LLMToolSelector
from ..tools.data_tools import get_last_tradeday
from ..config.constants import ANALYST_TYPES

class AnalystAgent(AgentBase):
    """分析师 Agent - 使用 LLM 进行智能工具选择和分析（基于AgentScope）"""
    
    def __init__(self, 
                 analyst_type: str,
                 agent_id: Optional[str] = None,
                 description: Optional[str] = None, 
                 config: Optional[Dict[str, Any]] = None):
        """
        初始化分析师 Agent
        
        Args:
            analyst_type: 分析师类型 (fundamental, technical, sentiment, valuation, comprehensive)
            agent_id: Agent ID（默认为 "{analyst_type}_analyst_agent"）
            description: 分析师描述
            config: 配置字典
        """
        if analyst_type not in ANALYST_TYPES:
            raise ValueError(
                f"Unknown analyst type: {analyst_type}. "
                f"Must be one of: {list(ANALYST_TYPES.keys())}"
            )
        
        self.analyst_type_key = analyst_type
        self.analyst_persona = ANALYST_TYPES[analyst_type]["display_name"]
        
        # 设置默认 agent_id
        if agent_id is None:
            agent_id = f"{analyst_type}_analyst_agent"
        
        # 初始化AgentBase（不接受参数）
        super().__init__()
        
        # 设置name属性
        self.name = agent_id
        
        self.description = description or f"{self.analyst_persona} - 使用LLM智能选择分析工具"
        self.config = config or {}
        
        # 使用LLM工具选择器（内部使用Toolkit）
        self.tool_selector = LLMToolSelector()
        self.toolkit = self.tool_selector.get_toolkit()  # 获取Toolkit实例
    
    def execute(self, state: AgentState) -> Dict[str, Any]:
        """
        执行分析师逻辑（同步入口，内部调用异步）
        
        Args:
            state: AgentState
        
        Returns:
            更新后的状态字典
        """
        # 在当前线程中创建新的事件循环进行异步分析
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(self._execute_async(state))
            return result
        finally:
            loop.close()
            asyncio.set_event_loop(None)
    
    async def _execute_async(self, state: AgentState) -> Dict[str, Any]:
        """
        异步执行分析师逻辑
        
        Args:
            state: AgentState
        
        Returns:
            更新后的状态字典
        """
        data = state["data"]
        tickers = data["tickers"]
        start_date = data.get("start_date")
        end_date = data["end_date"]
        
        # 获取 LLM
        llm = None
        try:
            llm = get_model(
                model_name=state["metadata"]['model_name'],
                model_provider=state['metadata']['model_provider'],
                api_keys=state['data']['api_keys']
            )
        except Exception as e:
            print(f"警告: 无法获取 LLM 模型: {e}")
        
        # 执行分析
        analysis_results = {}
        
        for ticker in tickers:
            progress.update_status(
                self.name,  # 使用 self.name 而不是 self.agent_id
                ticker, 
                f"开始 {self.analyst_persona} 智能分析"
            )
            
            # 生成分析目标
            analysis_objective = (
                f"作为专业的{self.analyst_persona}，对股票 {ticker} "
                f"进行全面深入的投资分析"
            )
            
            # 异步分析ticker
            result = await self._analyze_ticker(
                ticker, end_date, state, start_date, llm, analysis_objective
            )
            analysis_results[ticker] = result
            
            progress.update_status(
                self.name, 
                ticker, 
                "完成",
                analysis=json.dumps(result, indent=2, default=str)
            )
        
        # 创建消息（使用 AgentScope Msg 格式）
        message = Msg(
            name=self.name,
            content=json.dumps(analysis_results, default=str),
            role="assistant",
            metadata={"analyst_type": self.analyst_type_key}
        )
        
        # 更新状态
        state["data"]["analyst_signals"][self.name] = analysis_results
        
        progress.update_status(
            self.name, 
            None, 
            f"所有 {self.analyst_persona} 分析完成"
        )
        
        return {
            "messages": [message.to_dict()],  # 转换为dict
            "data": data,
        }
    
    async def _analyze_ticker(self, ticker: str, end_date: str, state: Dict[str, Any],
                            start_date: Optional[str], llm, 
                            analysis_objective: str) -> Dict[str, Any]:
        """
        分析单个 ticker
        
        Args:
            ticker: 股票代码
            end_date: 结束日期
            state: State对象 (包含API keys等信息)
            start_date: 开始日期
            llm: LLM 模型
            analysis_objective: 分析目标
        
        Returns:
            分析结果字典
        """
        progress.update_status(
            self.name, 
            ticker, 
            "开始智能工具选择"
        )
        
        # ⭐ 将 end_date 调整为上一个交易日
        # 这样分析时不包含当日未收盘的数据，避免数据不完整的问题
        adjusted_end_date = get_last_tradeday(end_date)
        # print(f"📅 分析师 {self.agent_id} - 原始日期: {end_date}, 分析截止日期（上一个交易日）: {adjusted_end_date}")
        
        # 1. 生成市场条件
        market_conditions = {
            "analysis_date": end_date,
            "volatility_regime": "normal",
            "interest_rate": "normal", 
            "market_sentiment": "neutral"
        }
        
        # 2. 使用LLM选择工具
        selection_result = await self.tool_selector.select_tools_with_llm(
            llm, self.analyst_persona, ticker, market_conditions, analysis_objective
        )
        
        progress.update_status(
            self.name, 
            ticker, 
            f"已选择 {selection_result['tool_count']} 个工具"
        )


        # print(f"{self.name} \n\n-  LLM 工具选择结果:\n\n {selection_result}")
        
        # 3. 执行选定的工具 - 使用AgentScope Toolkit
        tool_results = await self.tool_selector.execute_selected_tools(
            selection_result["selected_tools"],
            ticker=ticker,
            state=state,  # 传递state,让工具自己获取需要的API key
            start_date=start_date,
            end_date=adjusted_end_date  # 使用调整后的日期
        )
        
        # 4. 使用LLM综合判断工具结果
        progress.update_status(
            self.name, 
            ticker, 
            "LLM综合分析信号"
        )


        combined_result = self.tool_selector.synthesize_results_with_llm(
            tool_results, 
            selection_result,
            llm,
            ticker,
            self.analyst_persona
        )

        print(f"{self.name} \n\n-  LLM 调用输出结果:\n\n {combined_result}")
        
        # 5. 构建最终结果
        analysis_result = {
            "signal": combined_result["signal"],
            "confidence": combined_result["confidence"],
            "reason": combined_result["reasoning"],
            "tool_selection": {
                "analysis_strategy": selection_result["analysis_strategy"],
                "selected_tools": selection_result["selected_tools"],
                "tool_count": selection_result["tool_count"]
            },
            "tool_analysis": {
                "tools_used": len(selection_result["selected_tools"]),
                "successful_tools": len([r for r in tool_results if "error" not in r]),
                "failed_tools": len([r for r in tool_results if "error" in r]),
                "tool_results": tool_results,
                "synthesis_details": combined_result
            },
            "metadata": {
                "analyst_name": self.analyst_persona,
                "analyst_type": self.analyst_type_key,
                "analysis_date": end_date,
                "llm_enhanced": llm is not None,
                "selection_method": "LLM intelligent selection" if llm else "Default selection",
                "synthesis_method": combined_result.get("synthesis_method", "unknown"),
            }
        }
        
        progress.update_status(self.name, ticker, "分析完成")
        
        return analysis_result

