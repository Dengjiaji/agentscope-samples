#!/usr/bin/env python3
"""
分析师记忆系统 - 保存每个分析师的完整对话历史和分析过程
"""

import json
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage


class AnalysisSession(BaseModel):
    """分析会话记录"""
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_type: str = Field(..., description="会话类型：first_round, second_round, communication等")
    start_time: datetime = Field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    tickers: List[str] = Field(default_factory=list, description="分析的股票")
    context: Dict[str, Any] = Field(default_factory=dict, description="会话上下文信息")
    messages: List[Dict[str, Any]] = Field(default_factory=list, description="消息历史")
    final_result: Optional[Dict[str, Any]] = Field(None, description="最终分析结果")
    status: str = Field(default="active", description="会话状态：active, completed, failed")


class CommunicationRecord(BaseModel):
    """通信记录"""
    communication_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    communication_type: str = Field(..., description="通信类型：private_chat, meeting, notification")
    participants: List[str] = Field(..., description="参与者列表")
    topic: str = Field(..., description="讨论话题")
    start_time: datetime = Field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    messages: List[Dict[str, Any]] = Field(default_factory=list, description="通信消息")
    signal_adjustments: List[Dict[str, Any]] = Field(default_factory=list, description="信号调整记录")
    status: str = Field(default="active", description="通信状态")


class AnalystMemory:
    """分析师记忆系统"""
    
    def __init__(self, analyst_id: str, analyst_name: str):
        self.analyst_id = analyst_id
        self.analyst_name = analyst_name
        self.creation_time = datetime.now()
        
        # 核心记忆存储
        self.analysis_sessions: List[AnalysisSession] = []
        self.communication_records: List[CommunicationRecord] = []
        self.current_signals: Dict[str, Any] = {}
        self.signal_history: List[Dict[str, Any]] = []
        
        # 元数据
        self.total_analyses = 0
        self.total_communications = 0
        self.last_active_time = datetime.now()
    
    def start_analysis_session(self, session_type: str, tickers: List[str], 
                             context: Dict[str, Any] = None) -> str:
        """开始新的分析会话"""
        session = AnalysisSession(
            session_type=session_type,
            tickers=tickers,
            context=context or {}
        )
        
        self.analysis_sessions.append(session)
        self.total_analyses += 1
        self.last_active_time = datetime.now()
        
        print(f"📝 {self.analyst_name} 开始新会话: {session_type} (ID: {session.session_id[:8]}...)")
        return session.session_id
    
    def add_analysis_message(self, session_id: str, role: str, content: str, 
                           metadata: Dict[str, Any] = None):
        """添加分析消息到指定会话"""
        session = self._get_session(session_id)
        if session:
            message = {
                "timestamp": datetime.now().isoformat(),
                "role": role,  # system, human, assistant
                "content": content,
                "metadata": metadata or {}
            }
            session.messages.append(message)
            self.last_active_time = datetime.now()
    
    def complete_analysis_session(self, session_id: str, final_result: Dict[str, Any]):
        """完成分析会话"""
        session = self._get_session(session_id)
        if session:
            session.end_time = datetime.now()
            session.final_result = final_result
            session.status = "completed"
            
            # 更新当前信号
            if "ticker_signals" in final_result:
                for ticker_signal in final_result["ticker_signals"]:
                    ticker = ticker_signal.get("ticker")
                    if ticker:
                        self.current_signals[ticker] = ticker_signal
                        
                        # 添加到信号历史
                        self.signal_history.append({
                            "timestamp": datetime.now().isoformat(),
                            "session_id": session_id,
                            "session_type": session.session_type,
                            "ticker": ticker,
                            "signal": ticker_signal
                        })
            
            print(f"✅ {self.analyst_name} 完成会话: {session.session_type}")
    
    def start_communication(self, communication_type: str, participants: List[str], 
                          topic: str) -> str:
        """开始新的通信"""
        communication = CommunicationRecord(
            communication_type=communication_type,
            participants=participants,
            topic=topic
        )
        
        self.communication_records.append(communication)
        self.total_communications += 1
        self.last_active_time = datetime.now()
        
        print(f"💬 {self.analyst_name} 开始通信: {communication_type} (ID: {communication.communication_id[:8]}...)")
        return communication.communication_id
    
    def add_communication_message(self, communication_id: str, speaker: str, 
                                content: str, metadata: Dict[str, Any] = None):
        """添加通信消息"""
        communication = self._get_communication(communication_id)
        if communication:
            message = {
                "timestamp": datetime.now().isoformat(),
                "speaker": speaker,
                "content": content,
                "metadata": metadata or {}
            }
            communication.messages.append(message)
            self.last_active_time = datetime.now()
    
    def record_signal_adjustment(self, communication_id: str, original_signal: Dict[str, Any], 
                               adjusted_signal: Dict[str, Any], reasoning: str):
        """记录信号调整"""
        communication = self._get_communication(communication_id)
        if communication:
            adjustment = {
                "timestamp": datetime.now().isoformat(),
                "original_signal": original_signal,
                "adjusted_signal": adjusted_signal,
                "reasoning": reasoning
            }
            communication.signal_adjustments.append(adjustment)
            
            # 更新当前信号（兼容两种结构：单ticker 或 多ticker列表）
            printed_any = False
            # 情况1：批量结构，形如 { analyst_id, analyst_name, ticker_signals: [ {ticker, signal, ...}, ...] }
            if isinstance(adjusted_signal, dict) and isinstance(adjusted_signal.get("ticker_signals"), list):
                for ts in adjusted_signal.get("ticker_signals", []):
                    ticker_code = (ts or {}).get("ticker")
                    if not ticker_code:
                        continue
                    # 更新最新信号
                    self.current_signals[ticker_code] = ts
                    # 记录历史
                    self.signal_history.append({
                        "timestamp": datetime.now().isoformat(),
                        "communication_id": communication_id,
                        "communication_type": communication.communication_type,
                        "ticker": ticker_code,
                        "signal": ts,
                        "adjustment_reason": reasoning
                    })
                    print(f"🔄 {self.analyst_name} 调整了信号: {ticker_code}")
                    printed_any = True
            
            # 情况2：单ticker结构，形如 { ticker: "AAPL", signal: "bearish", ... }
            if not printed_any and isinstance(adjusted_signal, dict):
                ticker_code = adjusted_signal.get("ticker")
                if ticker_code:
                    self.current_signals[ticker_code] = adjusted_signal
                    self.signal_history.append({
                        "timestamp": datetime.now().isoformat(),
                        "communication_id": communication_id,
                        "communication_type": communication.communication_type,
                        "ticker": ticker_code,
                        "signal": adjusted_signal,
                        "adjustment_reason": reasoning
                    })
                    print(f"🔄 {self.analyst_name} 调整了信号: {ticker_code}")
                    printed_any = True
            
            # 情况3：无法提取ticker，做降级打印
            if not printed_any:
                print(f"🔄 {self.analyst_name} 调整了信号: unknown")
    
    def complete_communication(self, communication_id: str):
        """完成通信"""
        communication = self._get_communication(communication_id)
        if communication:
            communication.end_time = datetime.now()
            communication.status = "completed"
            print(f"✅ {self.analyst_name} 完成通信: {communication.communication_type}")
    
    def get_full_context_for_communication(self, tickers: List[str] = None) -> str:
        """获取用于通信的完整上下文"""
        context_parts = []
        
        # 基本信息
        context_parts.append(f"=== {self.analyst_name} 的完整记忆 ===")
        context_parts.append(f"身份: {self.analyst_id}")
        context_parts.append(f"总分析次数: {self.total_analyses}")
        context_parts.append(f"总通信次数: {self.total_communications}")
        
        # 当前信号状态
        if self.current_signals:
            context_parts.append("\n=== 当前信号状态 ===")
            for ticker, signal in self.current_signals.items():
                if not tickers or ticker in tickers:
                    context_parts.append(f"{ticker}: {signal.get('signal', 'unknown')} "
                                       f"(信心度: {signal.get('confidence', 0)}%)")
                    context_parts.append(f"  理由: {signal.get('reasoning', '无')}")
        
        # 最近的分析会话
        recent_sessions = self.analysis_sessions[-3:]  # 最近3次会话
        if recent_sessions:
            context_parts.append("\n=== 最近分析过程 ===")
            for session in recent_sessions:
                context_parts.append(f"\n--- {session.session_type} 会话 ---")
                context_parts.append(f"时间: {session.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
                context_parts.append(f"股票: {', '.join(session.tickers)}")
                
                # 关键消息（只显示助手的回应）
                assistant_messages = [msg for msg in session.messages if msg["role"] == "assistant"]
                for msg in assistant_messages[-2:]:  # 最近2条助手消息
                    content = msg["content"]
                    if len(content) > 200:
                        content = content[:200] + "..."
                    context_parts.append(f"  分析: {content}")
        
        # 信号变化历史
        if self.signal_history:
            context_parts.append("\n=== 信号调整历史 ===")
            recent_adjustments = self.signal_history[-5:]  # 最近5次调整
            for adj in recent_adjustments:
                if not tickers or adj["ticker"] in tickers:
                    context_parts.append(f"{adj['timestamp'][:19]}: {adj['ticker']} "
                                       f"-> {adj['signal'].get('signal', 'unknown')}")
                    if "adjustment_reason" in adj:
                        context_parts.append(f"  调整原因: {adj['adjustment_reason']}")
        
        # 最近通信记录
        recent_communications = self.communication_records[-2:]  # 最近2次通信
        if recent_communications:
            context_parts.append("\n=== 最近通信记录 ===")
            for comm in recent_communications:
                context_parts.append(f"\n--- {comm.communication_type} ---")
                context_parts.append(f"参与者: {', '.join(comm.participants)}")
                context_parts.append(f"话题: {comm.topic[:100]}...")
                
                # 自己的发言
                my_messages = [msg for msg in comm.messages if msg["speaker"] == self.analyst_id]
                for msg in my_messages[-2:]:  # 最近2条发言
                    content = msg["content"]
                    if len(content) > 150:
                        content = content[:150] + "..."
                    context_parts.append(f"  我说: {content}")
        
        return "\n".join(context_parts)
    
    def get_analysis_summary(self) -> Dict[str, Any]:
        """获取分析总结"""
        return {
            "analyst_id": self.analyst_id,
            "analyst_name": self.analyst_name,
            "total_analyses": self.total_analyses,
            "total_communications": self.total_communications,
            "current_signals": self.current_signals,
            "recent_sessions": len(self.analysis_sessions),
            "signal_adjustments": len([adj for adj in self.signal_history if "adjustment_reason" in adj]),
            "last_active": self.last_active_time.isoformat()
        }
    
    def _get_session(self, session_id: str) -> Optional[AnalysisSession]:
        """获取指定会话"""
        for session in self.analysis_sessions:
            if session.session_id == session_id:
                return session
        return None
    
    def _get_communication(self, communication_id: str) -> Optional[CommunicationRecord]:
        """获取指定通信记录"""
        for communication in self.communication_records:
            if communication.communication_id == communication_id:
                return communication
        return None
    
    def export_memory(self) -> Dict[str, Any]:
        """导出记忆数据"""
        return {
            "analyst_id": self.analyst_id,
            "analyst_name": self.analyst_name,
            "creation_time": self.creation_time.isoformat(),
            "analysis_sessions": [session.model_dump() for session in self.analysis_sessions],
            "communication_records": [comm.model_dump() for comm in self.communication_records],
            "current_signals": self.current_signals,
            "signal_history": self.signal_history,
            "stats": {
                "total_analyses": self.total_analyses,
                "total_communications": self.total_communications,
                "last_active_time": self.last_active_time.isoformat()
            }
        }


class AnalystMemoryManager:
    """分析师记忆管理器"""
    
    def __init__(self):
        self.analysts: Dict[str, AnalystMemory] = {}
    
    def register_analyst(self, analyst_id: str, analyst_name: str):
        """注册分析师"""
        if analyst_id not in self.analysts:
            self.analysts[analyst_id] = AnalystMemory(analyst_id, analyst_name)
            print(f"🧠 注册分析师记忆: {analyst_name}")
    
    def get_analyst_memory(self, analyst_id: str) -> Optional[AnalystMemory]:
        """获取分析师记忆"""
        return self.analysts.get(analyst_id)
    
    def get_all_analysts_context(self, tickers: List[str] = None) -> Dict[str, str]:
        """获取所有分析师的上下文"""
        contexts = {}
        for analyst_id, memory in self.analysts.items():
            contexts[analyst_id] = memory.get_full_context_for_communication(tickers)
        return contexts
    
    def export_all_memories(self) -> Dict[str, Any]:
        """导出所有记忆"""
        return {
            "export_time": datetime.now().isoformat(),
            "analysts": {
                analyst_id: memory.export_memory() 
                for analyst_id, memory in self.analysts.items()
            }
        }


# 创建全局记忆管理器
memory_manager = AnalystMemoryManager()
