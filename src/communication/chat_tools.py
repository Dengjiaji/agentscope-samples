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
    
    def _get_llm_model(self, state, use_json_mode=False):
        """获取LLM模型实例"""
        try:
            # 从state中获取API密钥
            api_keys = {}
            if state and "data" in state and "api_keys" in state["data"]:
                api_keys = state["data"]["api_keys"]
            
            model_name = state.get("metadata", {}).get("model_name", "gpt-3.5-turbo")
            model_provider = state.get("metadata", {}).get("model_provider", "OpenAI")
            
            llm = get_model(model_name, model_provider, api_keys)
            
            # 如果需要JSON模式，配置结构化输出
            if use_json_mode and hasattr(llm, 'bind'):
                try:
                    llm = llm.bind(response_format={"type": "json_object"})
                except Exception:
                    # 如果不支持JSON模式，继续使用常规模式
                    pass
            
            return llm
        except Exception as e:
            print(f"❌ 获取LLM模型失败: {str(e)}")
            # 使用默认配置
            return get_model("gpt-3.5-turbo", "OpenAI", None)
    
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

必须以JSON格式返回决策，不要包含任何其他文本。"""),
            
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
        
        try:
            # 格式化分析师信号
            signals_summary = {}
            for analyst_id, signal_data in analyst_signals.items():
                if isinstance(signal_data, dict) and 'ticker_signals' in signal_data:
                    signals_summary[analyst_id] = signal_data['ticker_signals']
                else:
                    signals_summary[analyst_id] = signal_data
            
            # 调用LLM
            messages = prompt_template.format_messages(
                analyst_signals=json.dumps(signals_summary, ensure_ascii=False, indent=2)
            )
            
            # 获取LLM模型（启用JSON模式）
            llm = self._get_llm_model(state, use_json_mode=True)
            
            # 调用模型
            response = llm.invoke(messages)
            
            # 尝试解析JSON
            try:
                decision_data = json.loads(response.content)
            except json.JSONDecodeError as e:
                print(f"❌ JSON解析失败: {str(e)}")
                print(f"响应内容: {response.content}")
                # 返回默认决策
                return CommunicationDecision(
                    should_communicate=False,
                    communication_type="none",
                    target_analysts=[],
                    discussion_topic="",
                    reasoning="JSON解析失败，使用默认决策"
                )
            
            return CommunicationDecision(**decision_data)
            
        except Exception as e:
            print(f"❌ 交流决策失败: {str(e)}")
            return CommunicationDecision(
                should_communicate=False,
                communication_type="none",
                target_analysts=[],
                discussion_topic="",
                reasoning=f"决策过程出错: {str(e)}"
            )
    
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
        
        for round_num in range(max_rounds):
            print(f"\n💬 私聊第{round_num + 1}轮:")
            
            # 分析师回应
            analyst_response = self._get_analyst_chat_response(
                analyst_id, topic, conversation_history, 
                current_analyst_signal, state
            )
            
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
        
        return {
            "chat_history": conversation_history,
            "final_analyst_signal": current_analyst_signal,
            "adjustments_made": len([h for h in conversation_history if "调整" in h.get("content", "")])
        }
    
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
        
        # 管理者开场
        opening_message = f"我们来讨论{topic}。请各位分析师分享你们的观点和分析结果。"
        self.meeting_system.add_message(meeting_id, manager_id, opening_message)
        meeting_transcript.append({
            "speaker": manager_id,
            "content": opening_message,
            "round": 1
        })
        
        for round_num in range(max_rounds):
            print(f"\n🏢 会议第{round_num + 1}轮发言:")
            
            # 每个分析师发言
            for analyst_id in analyst_ids:
                analyst_response = self._get_analyst_meeting_response(
                    analyst_id, topic, meeting_transcript, 
                    current_signals.get(analyst_id, {}), 
                    current_signals, state, round_num + 1
                )
                
                self.meeting_system.add_message(
                    meeting_id, analyst_id, analyst_response["response"]
                )
                
                meeting_transcript.append({
                    "speaker": analyst_id,
                    "content": analyst_response["response"],
                    "round": round_num + 1
                })
                
                print(f"🗣️ {analyst_id}: {analyst_response['response']}")
                
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
        
        return {
            "meeting_id": meeting_id,
            "transcript": meeting_transcript,
            "final_signals": current_signals,
            "adjustments_made": len([t for t in meeting_transcript if "调整" in t.get("content", "")])
        }
    
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
            ("system", f"""你是{analyst_id}分析师。你正在与投资组合管理者进行一对一讨论。

你的完整记忆和分析历史：
{full_context}

基于你的记忆、对话历史和当前分析信号，请：
1. 回应管理者的问题或观点
2. 解释你的分析逻辑（可以引用你之前的分析过程）
3. 如果有必要，基于新信息调整你的信号、信心度或reasoning

当前话题的信号：{json.dumps(current_signal, ensure_ascii=False)}

如果需要调整信号，请在回应中明确说明调整内容和原因。

必须以JSON格式返回，不要包含任何其他文本：
{{
  "response": "你的回应内容",
  "signal_adjustment": true/false,
  "adjusted_signal": {{...}} // 如果有调整的话
}}"""),
            
            ("human", f"""对话话题：{topic}

当前对话历史：
{self._format_conversation_history(conversation_history)}

请基于你的完整记忆和分析历史回应最新的对话内容。""")
        ])
        
        try:
            messages = prompt_template.format_messages()
            
            # 获取LLM模型（启用JSON模式）
            llm = self._get_llm_model(state, use_json_mode=True)
            
            # 调用模型
            response = llm.invoke(messages)
            
            # 尝试解析JSON
            try:
                return json.loads(response.content)
            except json.JSONDecodeError as e:
                print(f"❌ 分析师回应JSON解析失败: {str(e)}")
                print(f"响应内容: {response.content}")
                return {
                    "response": f"我理解你的观点，基于当前分析保持原有立场。",
                    "signal_adjustment": False
                }
            
        except Exception as e:
            print(f"❌ 获取分析师回应失败: {str(e)}")
            return {
                "response": f"抱歉，我在处理回应时遇到了问题：{str(e)}",
                "signal_adjustment": False
            }
    
    def _get_manager_chat_response(self, manager_id: str, analyst_id: str,
                                 conversation_history: List[Dict],
                                 current_signal: Dict[str, Any], 
                                 state) -> str:
        """获取管理者在私聊中的回应"""
        
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", """你是投资组合管理者，正在与分析师进行一对一讨论。
基于分析师的回应，继续对话，提出问题或给出建议。
保持专业和建设性的对话风格。"""),
            
            ("human", f"""对话历史：
{self._format_conversation_history(conversation_history)}

分析师当前信号：{json.dumps(current_signal, ensure_ascii=False)}

请回应分析师最新的发言。""")
        ])
        
        try:
            messages = prompt_template.format_messages()
            
            # 获取LLM模型
            llm = self._get_llm_model(state)
            
            # 调用模型
            response = llm.invoke(messages)
            return response.content
            
        except Exception as e:
            print(f"❌ 获取管理者回应失败: {str(e)}")
            return f"我需要更多时间思考这个问题。"
    
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
            ("system", f"""你是{analyst_id}分析师，正在参加一个投资会议。

你的完整记忆和分析历史：
{full_context}

这是第{round_num}轮发言。基于你的记忆和分析历史，请：
1. 分享你的观点和分析（可以引用你之前的分析过程和结论）
2. 回应其他与会者的观点
3. 如果听到有说服力的论据，基于新信息考虑调整你的信号
4. 保持你作为{analyst_id}的专业特色和一致性

你当前的分析信号：{json.dumps(current_signal, ensure_ascii=False)}

必须以JSON格式返回，不要包含任何其他文本：
{{
  "response": "你的发言内容",
  "signal_adjustment": true/false,
  "adjusted_signal": {{...}} // 如果有调整的话
}}"""),
            
            ("human", f"""会议话题：{topic}

会议记录：
{self._format_meeting_transcript(meeting_transcript)}

其他分析师的信号：
{json.dumps({k: v for k, v in all_signals.items() if k != analyst_id}, ensure_ascii=False, indent=2)}

请基于你的完整记忆和专业背景发言。""")
        ])
        
        try:
            messages = prompt_template.format_messages()
            
            # 获取LLM模型（启用JSON模式）
            llm = self._get_llm_model(state, use_json_mode=True)
            
            # 调用模型
            response = llm.invoke(messages)
            
            # 尝试解析JSON
            try:
                return json.loads(response.content)
            except json.JSONDecodeError as e:
                print(f"❌ 会议发言JSON解析失败: {str(e)}")
                print(f"响应内容: {response.content}")
                return {
                    "response": f"基于我的分析，我认为当前策略是合理的。",
                    "signal_adjustment": False
                }
            
        except Exception as e:
            print(f"❌ 获取分析师会议发言失败: {str(e)}")
            return {
                "response": f"我同意之前的分析观点。",
                "signal_adjustment": False
            }
    
    def _get_manager_meeting_summary(self, manager_id: str, 
                                   meeting_transcript: List[Dict],
                                   final_signals: Dict[str, Any], 
                                   state) -> str:
        """获取管理者的会议总结"""
        
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", """你是投资组合管理者，正在总结会议内容。
请简洁地总结讨论要点和最终达成的共识。"""),
            
            ("human", f"""会议记录：
{self._format_meeting_transcript(meeting_transcript)}

最终信号：
{json.dumps(final_signals, ensure_ascii=False, indent=2)}

请总结这次会议。""")
        ])
        
        try:
            messages = prompt_template.format_messages()
            
            # 获取LLM模型
            llm = self._get_llm_model(state)
            
            # 调用模型
            response = llm.invoke(messages)
            return response.content
            
        except Exception as e:
            print(f"❌ 获取会议总结失败: {str(e)}")
            return "会议讨论了投资策略，各分析师表达了观点。"
    
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


# 创建全局实例
communication_manager = CommunicationManager()
