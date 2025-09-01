#!/usr/bin/env python3
"""
通信工具 - 私聊和开会功能的实现
"""

import json
import uuid
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage

from src.llm.models import get_model
from src.utils.api_key import get_api_key_from_state
from .analyst_memory import memory_manager


class PrivateChatMessage(BaseModel):
    """私聊消息模型"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sender: str = Field(..., description="发送者ID")
    receiver: str = Field(..., description="接收者ID")
    content: str = Field(..., description="消息内容")
    timestamp: datetime = Field(default_factory=datetime.now)
    message_type: str = Field(default="chat", description="消息类型")


class MeetingMessage(BaseModel):
    """会议消息模型"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    speaker: str = Field(..., description="发言者ID")
    content: str = Field(..., description="发言内容")
    timestamp: datetime = Field(default_factory=datetime.now)
    round: int = Field(..., description="发言轮次")


class SignalAdjustment(BaseModel):
    """信号调整模型"""
    ticker: str = Field(..., description="股票代码")
    original_signal: str = Field(..., description="原始信号")
    adjusted_signal: str = Field(..., description="调整后信号")
    original_confidence: int = Field(..., description="原始信心度")
    adjusted_confidence: int = Field(..., description="调整后信心度")
    adjustment_reasoning: str = Field(..., description="调整原因")


class CommunicationDecision(BaseModel):
    """交流决策模型"""
    should_communicate: bool = Field(..., description="是否需要交流")
    communication_type: str = Field(..., description="交流类型: private_chat 或 meeting")
    target_analysts: List[str] = Field(default_factory=list, description="目标分析师列表")
    discussion_topic: str = Field(..., description="讨论话题")
    reasoning: str = Field(..., description="选择交流的原因")


class PrivateChatSystem:
    """私聊系统"""
    
    def __init__(self):
        self.chat_histories: Dict[str, List[PrivateChatMessage]] = {}
    
    def start_private_chat(self, manager_id: str, analyst_id: str, 
                          initial_message: str) -> str:
        """开始私聊对话"""
        chat_key = f"{manager_id}_{analyst_id}"
        
        if chat_key not in self.chat_histories:
            self.chat_histories[chat_key] = []
        
        # 添加管理者的初始消息
        message = PrivateChatMessage(
            sender=manager_id,
            receiver=analyst_id,
            content=initial_message
        )
        
        self.chat_histories[chat_key].append(message)
        return message.id
    
    def send_message(self, sender: str, receiver: str, content: str) -> str:
        """发送消息"""
        chat_key = f"{sender}_{receiver}" if sender < receiver else f"{receiver}_{sender}"
        
        if chat_key not in self.chat_histories:
            self.chat_histories[chat_key] = []
        
        message = PrivateChatMessage(
            sender=sender,
            receiver=receiver,
            content=content
        )
        
        self.chat_histories[chat_key].append(message)
        return message.id
    
    def get_chat_history(self, participant1: str, participant2: str) -> List[PrivateChatMessage]:
        """获取聊天历史"""
        chat_key = f"{participant1}_{participant2}" if participant1 < participant2 else f"{participant2}_{participant1}"
        return self.chat_histories.get(chat_key, [])


class MeetingSystem:
    """会议系统"""
    
    def __init__(self):
        self.meetings: Dict[str, Dict[str, Any]] = {}
    
    def create_meeting(self, meeting_id: str, host: str, participants: List[str], 
                      topic: str) -> str:
        """创建会议"""
        self.meetings[meeting_id] = {
            "id": meeting_id,
            "host": host,
            "participants": participants,
            "topic": topic,
            "messages": [],
            "current_round": 1,
            "status": "active",
            "created_at": datetime.now()
        }
        return meeting_id
    
    def add_message(self, meeting_id: str, speaker: str, content: str) -> str:
        """添加会议发言"""
        if meeting_id not in self.meetings:
            raise ValueError(f"会议 {meeting_id} 不存在")
        
        meeting = self.meetings[meeting_id]
        message = MeetingMessage(
            speaker=speaker,
            content=content,
            round=meeting["current_round"]
        )
        
        meeting["messages"].append(message)
        return message.id
    
    def next_round(self, meeting_id: str):
        """进入下一轮发言"""
        if meeting_id in self.meetings:
            self.meetings[meeting_id]["current_round"] += 1
    
    def end_meeting(self, meeting_id: str):
        """结束会议"""
        if meeting_id in self.meetings:
            self.meetings[meeting_id]["status"] = "ended"
    
    def get_meeting_transcript(self, meeting_id: str) -> List[MeetingMessage]:
        """获取会议记录"""
        if meeting_id not in self.meetings:
            return []
        return self.meetings[meeting_id]["messages"]


class CommunicationManager:
    """交流管理器"""
    
    def __init__(self):
        self.private_chat_system = PrivateChatSystem()
        self.meeting_system = MeetingSystem()
        
    def _get_max_chars(self, state) -> int:
        """获取沟通文本最大字数，默认400，可通过state.metadata.communication_max_chars覆盖"""
        try:
            return int(state.get("metadata", {}).get("communication_max_chars", 400))
        except Exception:
            return 400
    
    def _truncate_text(self, text: str, max_chars: int) -> str:
        """按字数上限截断文本（面向中文），保留前max_chars个字符"""
        if not isinstance(text, str):
            return text
        return text if len(text) <= max_chars else text[:max_chars]
    
    def _persist_communication_result(self, payload: Dict[str, Any], comm_type: str, state):
        """将沟通结果写入当前会话的输出JSON文件（从state.metadata.output_file获取）"""
        default_name = f"/root/wuyue.wy/Project/IA/analysis_results_logs/communications_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        log_path = state.get("metadata", {}).get("output_file", default_name)
        try:
            # 确保目录存在
            import os
            os.makedirs("/root/wuyue.wy/Project/IA/analysis_results_logs", exist_ok=True)
            with open(log_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
        
        if "communication_logs" not in data:
            data["communication_logs"] = {"private_chats": [], "meetings": [], "communication_decisions": []}
        
        if comm_type == "private_chat":
            data["communication_logs"].setdefault("private_chats", []).append(payload)
        elif comm_type == "meeting":
            data["communication_logs"].setdefault("meetings", []).append(payload)
        else:
            # 其他类型直接附加在communication_logs根部，带上type
            payload_with_type = {"type": comm_type, **payload}
            data["communication_logs"].setdefault("others", []).append(payload_with_type)
        
        try:
            with open(log_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print("✅ 已将沟通结果写入日志文件")
        except Exception as e:
            print(f"❌ 写入沟通日志失败: {e}")
    
    def _get_llm_model(self, state, use_json_mode=False):
        """获取LLM模型实例"""
        # 从state中获取API密钥
        api_keys = {}
        if state and "data" in state and "api_keys" in state["data"]:
            api_keys = state["data"]["api_keys"]
        
        model_name = state.get("metadata", {}).get("model_name", "gpt-3.5-turbo")
        model_provider = state.get("metadata", {}).get("model_provider", "OpenAI")
        
        llm = get_model(model_name, model_provider, api_keys)
        
        # 如果需要JSON模式，配置结构化输出
        if use_json_mode:
            # 尝试多种JSON模式绑定方式
            if hasattr(llm, 'bind'):
                llm = llm.bind(response_format={"type": "json_object"})
            elif hasattr(llm, 'with_config'):
                llm = llm.with_config({"response_format": {"type": "json_object"}})
            # print(f"✅ JSON模式已启用 for {model_name}")
        
        return llm
    
    def decide_communication_strategy(self, manager_signals: Dict[str, Any], 
                                    analyst_signals: Dict[str, Any], 
                                    state) -> CommunicationDecision:
        """决定交流策略"""
        
        # 构建决策提示
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", """你是一个投资组合管理者，负责协调分析师团队。
基于当前的分析结果，你需要决定是否需要与分析师进行进一步交流。

交流方式有两种：
1. private_chat: 与单个分析师一对一私聊，适用于需要深入讨论特定问题
2. meeting: 组织多个分析师开会讨论，适用于需要集体决策或存在重大分歧

必须以JSON格式返回决策，不要包含任何其他文本。请将任何文本内容控制在不超过{max_chars}字。"""),
            
            ("human", """分析师信号汇总:
{analyst_signals}

请决定是否需要交流，并说明原因。如果需要交流，请指定：
- 交流类型 (private_chat 或 meeting)
- 目标分析师列表
- 讨论话题
- 选择原因

返回JSON格式：
{{
  "should_communicate": true/false,
  "communication_type": "private_chat" 或 "meeting",
  "target_analysts": ["analyst1", "analyst2"],
  "discussion_topic": "讨论话题",
  "reasoning": "选择原因"
}}""")
        ])
        
        # 格式化分析师信号
        signals_summary = {}
        for analyst_id, signal_data in analyst_signals.items():
            if isinstance(signal_data, dict) and 'ticker_signals' in signal_data:
                signals_summary[analyst_id] = signal_data['ticker_signals']
            else:
                signals_summary[analyst_id] = signal_data
        
        # 调用LLM
        messages = prompt_template.format_messages(
            analyst_signals=json.dumps(signals_summary, ensure_ascii=False, indent=2),
            max_chars=self._get_max_chars(state)
        )
        
        # 获取LLM模型（启用JSON模式）
        llm = self._get_llm_model(state, use_json_mode=True)
        
        # 调用模型
        response = llm.invoke(messages)
        
        # 直接解析JSON（不捕获异常）
        decision_data = json.loads(response.content)
        return CommunicationDecision(**decision_data)
    
    def conduct_private_chat(self, manager_id: str, analyst_id: str, 
                           topic: str, analyst_signal: Dict[str, Any], 
                           state, max_rounds: int = 3) -> Dict[str, Any]:
        """进行私聊"""
        print(f"💬 开始私聊: {manager_id} <-> {analyst_id}")
        print(f"📋 话题: {topic}")
        
        # 在分析师记忆中记录通信开始
        analyst_memory = memory_manager.get_analyst_memory(analyst_id)
        communication_id = None
        if analyst_memory:
            communication_id = analyst_memory.start_communication(
                communication_type="private_chat",
                participants=[manager_id, analyst_id],
                topic=topic
            )
        
        # 开始私聊
        initial_message = f"关于{topic}，我想和你讨论一下你的分析结果。你目前的信号是：{json.dumps(analyst_signal, ensure_ascii=False)}"
        
        chat_id = self.private_chat_system.start_private_chat(
            manager_id, analyst_id, initial_message
        )
        
        # 记录初始消息到分析师记忆
        if analyst_memory and communication_id:
            analyst_memory.add_communication_message(
                communication_id, manager_id, initial_message
            )
        
        conversation_history = []
        current_analyst_signal = analyst_signal.copy()
        adjustments_made_counter = 0
        
        max_chars = self._get_max_chars(state)
        for round_num in range(max_rounds):
            print(f"\n💬 私聊第{round_num + 1}轮:")
            
            # 分析师回应
            analyst_response = self._get_analyst_chat_response(
                analyst_id, topic, conversation_history, 
                current_analyst_signal, state
            )
            # 截断分析师回应
            if isinstance(analyst_response, dict) and "response" in analyst_response:
                analyst_response["response"] = self._truncate_text(analyst_response["response"], max_chars)
            
            conversation_history.append({
                "speaker": analyst_id,
                "content": analyst_response["response"],
                "round": round_num + 1
            })
            
            print(f"🗣️ {analyst_id}: {analyst_response['response']}")
            
            # 记录分析师回应到记忆
            if analyst_memory and communication_id:
                analyst_memory.add_communication_message(
                    communication_id, analyst_id, analyst_response['response']
                )
            
            # 检查是否有信号调整
            if analyst_response.get("signal_adjustment") and analyst_response.get("adjusted_signal"):
                original_signal = current_analyst_signal
                current_analyst_signal = analyst_response["adjusted_signal"]
                print(f"📊 信号已调整: {analyst_response['signal_adjustment']}")
                adjustments_made_counter += 1
                
                # 记录信号调整到记忆
                if analyst_memory and communication_id:
                    analyst_memory.record_signal_adjustment(
                        communication_id, 
                        original_signal, 
                        current_analyst_signal,
                        f"私聊讨论{topic}后的调整"
                    )
            
            # 管理者回应（如果不是最后一轮）
            if round_num < max_rounds - 1:
                manager_response = self._get_manager_chat_response(
                    manager_id, analyst_id, conversation_history, 
                    current_analyst_signal, state
                )
                manager_response = self._truncate_text(manager_response, max_chars)
                
                conversation_history.append({
                    "speaker": manager_id,
                    "content": manager_response,
                    "round": round_num + 1
                })
                
                print(f"🗣️ {manager_id}: {manager_response}")
                
                # 记录管理者回应到记忆
                if analyst_memory and communication_id:
                    analyst_memory.add_communication_message(
                        communication_id, manager_id, manager_response
                    )
        
        print("✅ 私聊结束")
        
        # 完成通信记录
        if analyst_memory and communication_id:
            analyst_memory.complete_communication(communication_id)
        
        result = {
            "chat_history": conversation_history,
            "final_analyst_signal": current_analyst_signal,
            "adjustments_made": adjustments_made_counter
        }
        # 持久化写入日志
        payload = {
            "timestamp": datetime.now().isoformat(),
            "participants": [manager_id, analyst_id],
            "topic": topic,
            "result": result
        }
        self._persist_communication_result(payload, comm_type="private_chat", state=state)
        return result
    
    def conduct_meeting(self, manager_id: str, analyst_ids: List[str], 
                       topic: str, analyst_signals: Dict[str, Any], 
                       state, max_rounds: int = 2) -> Dict[str, Any]:
        """进行会议"""
        meeting_id = str(uuid.uuid4())
        print(f"🏢 开始会议: {meeting_id}")
        print(f"📋 话题: {topic}")
        print(f"👥 参与者: {', '.join([manager_id] + analyst_ids)}")
        
        # 为每个分析师记录会议开始
        communication_ids = {}
        for analyst_id in analyst_ids:
            analyst_memory = memory_manager.get_analyst_memory(analyst_id)
            if analyst_memory:
                comm_id = analyst_memory.start_communication(
                    communication_type="meeting",
                    participants=[manager_id] + analyst_ids,
                    topic=topic
                )
                communication_ids[analyst_id] = comm_id
        
        # 创建会议
        self.meeting_system.create_meeting(
            meeting_id, manager_id, analyst_ids, topic
        )
        
        current_signals = analyst_signals.copy()
        meeting_transcript = []
        adjustments_made_counter = 0
        
        # 管理者开场
        opening_message = f"我们来讨论{topic}。请各位分析师分享你们的观点和分析结果。"
        self.meeting_system.add_message(meeting_id, manager_id, opening_message)
        meeting_transcript.append({
            "speaker": manager_id,
            "content": opening_message,
            "round": 1
        })
        
        max_chars = self._get_max_chars(state)
        for round_num in range(max_rounds):
            print(f"\n🏢 会议第{round_num + 1}轮发言:")
            
            # 调试：打印当前会议记录状态
            if round_num > 0:
                print(f"📝 当前会议记录条数: {len(meeting_transcript)}")
                # if meeting_transcript:
                #     print(f"📝 最后一条记录: {meeting_transcript[-1]}")
            
            # 每个分析师发言
            for analyst_id in analyst_ids:
                analyst_response = self._get_analyst_meeting_response(
                    analyst_id, topic, meeting_transcript, 
                    current_signals.get(analyst_id, {}), 
                    current_signals, state, round_num + 1
                )
                # 截断分析师发言
                if isinstance(analyst_response, dict) and "response" in analyst_response:
                    analyst_response["response"] = self._truncate_text(analyst_response["response"], max_chars)
                
                self.meeting_system.add_message(
                    meeting_id, analyst_id, analyst_response["response"]
                )
                
                meeting_transcript.append({
                    "speaker": analyst_id,
                    "content": analyst_response["response"],
                    "round": round_num + 1
                })
                
                # print(f"🗣️ {analyst_id}: {analyst_response['response']}") 
                print(f"🗣️ {analyst_id}: {analyst_response}")

                # 记录发言到分析师记忆
                analyst_memory = memory_manager.get_analyst_memory(analyst_id)
                if analyst_memory and analyst_id in communication_ids:
                    analyst_memory.add_communication_message(
                        communication_ids[analyst_id], analyst_id, analyst_response['response']
                    )
                
                # 检查信号调整
                if analyst_response.get("signal_adjustment") and analyst_response.get("adjusted_signal"):
                    original_signal = current_signals[analyst_id]
                    current_signals[analyst_id] = analyst_response["adjusted_signal"]
                    print(f"📊 {analyst_id} 调整了信号")
                    adjustments_made_counter += 1
                    
                    # 记录信号调整到记忆
                    if analyst_memory and analyst_id in communication_ids:
                        analyst_memory.record_signal_adjustment(
                            communication_ids[analyst_id],
                            original_signal,
                            analyst_response["adjusted_signal"],
                            f"会议讨论{topic}后的调整"
                        )
            
            self.meeting_system.next_round(meeting_id)
        
        # 管理者总结
        summary = self._get_manager_meeting_summary(
            manager_id, meeting_transcript, current_signals, state
        )
        summary = self._truncate_text(summary, max_chars)
        
        self.meeting_system.add_message(meeting_id, manager_id, summary)
        meeting_transcript.append({
            "speaker": manager_id,
            "content": summary,
            "round": "summary"
        })
        
        print(f"📋 会议总结: {summary}")
        
        self.meeting_system.end_meeting(meeting_id)
        print("✅ 会议结束")
        
        # 完成所有分析师的通信记录
        for analyst_id in analyst_ids:
            if analyst_id in communication_ids:
                analyst_memory = memory_manager.get_analyst_memory(analyst_id)
                if analyst_memory:
                    analyst_memory.complete_communication(communication_ids[analyst_id])
        
        result = {
            "meeting_id": meeting_id,
            "transcript": meeting_transcript,
            "final_signals": current_signals,
            "adjustments_made": adjustments_made_counter
        }
        # 持久化写入日志
        payload = {
            "timestamp": datetime.now().isoformat(),
            "meeting_id": meeting_id,
            "host": manager_id,
            "participants": analyst_ids,
            "topic": topic,
            "result": result
        }
        self._persist_communication_result(payload, comm_type="meeting", state=state)
        return result
    
    def _get_analyst_chat_response(self, analyst_id: str, topic: str, 
                                 conversation_history: List[Dict], 
                                 current_signal: Dict[str, Any], 
                                 state) -> Dict[str, Any]:
        """获取分析师在私聊中的回应"""
        
        # 获取分析师的完整记忆上下文
        analyst_memory = memory_manager.get_analyst_memory(analyst_id)
        full_context = ""
        if analyst_memory:
            tickers = state.get("data", {}).get("tickers", [])
            full_context = analyst_memory.get_full_context_for_communication(tickers)
        
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", """你是{analyst_id}分析师。你正在与投资组合管理者进行一对一讨论。

你的完整记忆和分析历史：
{full_context}

基于你的记忆、对话历史和当前分析信号，请：
1. 回应管理者的问题或观点
2. 解释你的分析逻辑（可以引用你之前的分析过程）
3. 如果有必要，基于新信息调整你的信号、信心度或reasoning

当前话题的信号：
{current_signal}

如果需要调整信号，请在回应中明确说明调整内容和原因。

请必须以JSON格式返回你的回应，严格按照以下JSON结构，不要包含任何其他文本：

重要：ticker_signals必须是对象数组，不是字符串数组！

{{
  "response": "你的回应内容",
  "signal_adjustment": true/false,
  "adjusted_signal": {{
    "analyst_id": "{analyst_id}",
    "analyst_name": "你的分析师名称",
    "ticker_signals": [
      {{"ticker": "AAPL", "signal": "bearish", "confidence": 85, "reasoning": "调整原因"}},
      {{"ticker": "MSFT", "signal": "neutral", "confidence": 70, "reasoning": "调整原因"}}
    ]
  }}
}}

禁止使用这种错误格式：
{{"ticker_signals": ["ticker_signals: [...]"]}}

必须使用正确格式：
{{"ticker_signals": [{{"ticker": "AAPL", "signal": "bearish", "confidence": 85}}]}}

注意：请将上述"response"字段的文字内容控制在不超过{max_chars}字。"""),
            
            ("human", """对话话题：{topic}

当前对话历史：
{conversation_history}

请基于你的完整记忆和分析历史回应最新的对话内容。""")
        ])
        
        messages = prompt_template.format_messages(
            analyst_id=analyst_id,
            full_context=full_context,
            current_signal=json.dumps(current_signal, ensure_ascii=False),
            topic=topic,
            conversation_history=self._format_conversation_history(conversation_history),
            max_chars=self._get_max_chars(state)
        )
        
        # 获取LLM模型（启用JSON模式）
        llm = self._get_llm_model(state, use_json_mode=True)
        
        # 调用模型
        response = llm.invoke(messages)
        
        # 直接解析JSON（不捕获异常）
        return json.loads(response.content)
    
    def _get_manager_chat_response(self, manager_id: str, analyst_id: str,
                                 conversation_history: List[Dict],
                                 current_signal: Dict[str, Any], 
                                 state) -> str:
        """获取管理者在私聊中的回应"""
        
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", """你是投资组合管理者，正在与分析师进行一对一讨论。
基于分析师的回应，继续对话，提出问题或给出建议。
保持专业和建设性的对话风格。请将你的回应控制在不超过{max_chars}字。"""),
            
            ("human", """对话历史：
{conversation_history}

分析师当前信号：
{current_signal}

请回应分析师最新的发言。""")
        ])
        
        messages = prompt_template.format_messages(
            conversation_history=self._format_conversation_history(conversation_history),
            current_signal=json.dumps(current_signal, ensure_ascii=False),
            max_chars=self._get_max_chars(state)
        )
        
        # 获取LLM模型
        llm = self._get_llm_model(state)
        
        # 调用模型
        response = llm.invoke(messages)
        return response.content
    
    def _get_analyst_meeting_response(self, analyst_id: str, topic: str,
                                    meeting_transcript: List[Dict],
                                    current_signal: Dict[str, Any],
                                    all_signals: Dict[str, Any],
                                    state, round_num: int) -> Dict[str, Any]:
        """获取分析师在会议中的发言"""
        
        # 获取分析师的完整记忆上下文
        analyst_memory = memory_manager.get_analyst_memory(analyst_id)
        full_context = ""
        if analyst_memory:
            tickers = state.get("data", {}).get("tickers", [])
            full_context = analyst_memory.get_full_context_for_communication(tickers)
        
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", """你是{analyst_id}分析师，正在参加一个投资会议。

你的完整记忆和分析历史：
{full_context}

你当前的分析信号：
{current_signal}

请必须以JSON格式返回你的回应，严格按照以下JSON结构，不要包含任何其他文本：

重要：ticker_signals必须是对象数组，不是字符串数组！

{{
  "response": "你的发言内容",
  "signal_adjustment": true/false,
  "adjusted_signal": {{
    "analyst_id": "{analyst_id}",
    "analyst_name": "你的分析师名称",
    "ticker_signals": [
      {{"ticker": "AAPL", "signal": "bearish", "confidence": 85, "reasoning": "调整原因"}},
      {{"ticker": "MSFT", "signal": "neutral", "confidence": 70, "reasoning": "调整原因"}}
    ]
  }}
}}

禁止使用这种错误格式：
{{"ticker_signals": ["ticker_signals: [...]"]}}

必须使用正确格式：
{{"ticker_signals": [{{"ticker": "AAPL", "signal": "bearish", "confidence": 85}}]}}

注意：请将上述"response"字段的文字内容控制在不超过{max_chars}字。"""),
            
            ("human", """会议话题：{topic}

这是第{round_num}轮发言。

会议记录（重要！请仔细阅读并回应）：
{meeting_transcript}

其他分析师的信号：
{other_signals}

发言要求：
1. 如果这是第1轮：分享你的观点和分析依据
2. 如果这是第2轮或更多：
   - 必须明确回应前面轮次中其他分析师的具体观点
   - 说明你是否同意或不同意他们的分析，并给出理由
   - 基于讨论内容考虑是否需要调整你的信号
   - 避免重复第1轮的发言内容

请基于会议记录和讨论内容发言，展现真正的互动和思辨过程。""")
        ])
        
        messages = prompt_template.format_messages(
            analyst_id=analyst_id,
            full_context=full_context,
            round_num=round_num,
            current_signal=json.dumps(current_signal, ensure_ascii=False),
            topic=topic,
            meeting_transcript=self._format_meeting_transcript(meeting_transcript),
            other_signals=json.dumps({k: v for k, v in all_signals.items() if k != analyst_id}, ensure_ascii=False, indent=2),
            max_chars=self._get_max_chars(state)
        )
        
        # 获取LLM模型（启用JSON模式）
        llm = self._get_llm_model(state, use_json_mode=True)
        
        # 调用模型
        response = llm.invoke(messages)
        
        # 直接解析JSON（不捕获异常）
        return json.loads(response.content)
    
    def _get_manager_meeting_summary(self, manager_id: str, 
                                   meeting_transcript: List[Dict],
                                   final_signals: Dict[str, Any], 
                                   state) -> str:
        """获取管理者的会议总结"""
        
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", """你是投资组合管理者，正在总结会议内容。
请简洁地总结讨论要点和最终达成的共识。请将总结控制在不超过{max_chars}字。"""),
            
            ("human", """会议记录：
{meeting_transcript}

最终信号：
{final_signals}

请总结这次会议。""")
        ])
        
        messages = prompt_template.format_messages(
            meeting_transcript=self._format_meeting_transcript(meeting_transcript),
            final_signals=json.dumps(final_signals, ensure_ascii=False, indent=2),
            max_chars=self._get_max_chars(state)
        )
        
        # 获取LLM模型
        llm = self._get_llm_model(state)
        
        # 调用模型
        response = llm.invoke(messages)
        return response.content
    
    def _format_conversation_history(self, history: List[Dict]) -> str:
        """格式化对话历史"""
        formatted = []
        for entry in history:
            formatted.append(f"{entry['speaker']}: {entry['content']}")
        return "\n".join(formatted)
    
    def _format_meeting_transcript(self, transcript: List[Dict]) -> str:
        """格式化会议记录"""
        formatted = []
        for entry in transcript:
            round_info = f"第{entry['round']}轮" if isinstance(entry['round'], int) else entry['round']
            formatted.append(f"[{round_info}] {entry['speaker']}: {entry['content']}")
        return "\n".join(formatted)
    
    def _extract_and_clean_json(self, content: str) -> Optional[Dict[str, Any]]:
        """从响应中提取和清理JSON"""
        try:
            # 移除markdown代码块
            content = re.sub(r'```json\s*\n?', '', content)
            content = re.sub(r'\n?\s*```', '', content)
            
            # 查找JSON部分
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                
                # 移除注释
                json_str = re.sub(r'//.*', '', json_str)
                
                # 尝试解析
                return json.loads(json_str)
            
            # 如果找不到完整JSON，尝试提取关键字段
            response_match = re.search(r'"response"\s*:\s*"([^"]*)"', content)
            adjustment_match = re.search(r'"signal_adjustment"\s*:\s*(true|false)', content)
            
            if response_match:
                return {
                    "response": response_match.group(1),
                    "signal_adjustment": adjustment_match.group(1) == 'true' if adjustment_match else False
                }
                
        except Exception as e:
            print(f"JSON提取过程出错: {str(e)}")
            
        return None


# 创建全局实例
communication_manager = CommunicationManager()
