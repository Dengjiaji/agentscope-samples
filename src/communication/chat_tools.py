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

from src.agents.agentscope_prompts import ChatPromptTemplate
from src.llm.agentscope_models import get_model as get_agentscope_model
from src.utils.api_key import get_api_key_from_state
from src.utils.json_utils import quiet_json_dumps
from src.memory import unified_memory_manager as memory_manager
from src.memory import unified_memory_manager
import pdb
class PrivateChatMessage(BaseModel):
    """私聊消息模型"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sender: str = Field(..., description="发送者ID")
    receiver: str = Field(..., description="接收者ID")
    content: str = Field(..., description="消息内容")
    timestamp: datetime = Field(default_factory=datetime.now)
    message_type: str = Field(default="chat", description="消息类型")




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




class CommunicationManager:
    """交流管理器"""
    
    def __init__(self):
        self.private_chat_system = PrivateChatSystem()
        
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
            print("已将沟通结果写入日志文件")
        except Exception as e:
            print(f"错误: 写入沟通日志失败: {e}")
    
    def _get_llm_model(self, state, use_json_mode=False):
        """获取LLM模型实例（使用 AgentScope 模型包装器）"""
        # 从state中获取API密钥
        api_keys = {}
        if state and "metadata" in state:
            request = state.get("metadata", {}).get("request")
            if request and hasattr(request, 'api_keys'):
                api_keys = request.api_keys
        
        # 如果metadata中没有，尝试从data中获取
        if not api_keys and state and "data" in state and "api_keys" in state["data"]:
            api_keys = state["data"]["api_keys"]
        
        model_name = state.get("metadata", {}).get("model_name", "gpt-4o-mini")
        model_provider = state.get("metadata", {}).get("model_provider", "OPENAI")
        
        # 使用 AgentScope 模型包装器
        llm = get_agentscope_model(model_name, model_provider, api_keys)
        
        # 存储是否使用JSON模式的标志，供调用时使用
        llm._use_json_mode = use_json_mode
        
        return llm
    
    def decide_communication_strategy(self, manager_signals: Dict[str, Any], 
                                    analyst_signals: Dict[str, Any], 
                                    state) -> CommunicationDecision:
        """决定交流策略"""
        
        # 构建决策提示
        # TODO: 所有使用到ChatPromptTemplate的地方都改成agentscope中的formatter逻辑
        #         prompt = await self.formatter.format(
        #             msgs=[
        #                 Msg("system", self.sys_prompt, "system"),
        #                 *await self.memory.get_memory(),
        #             ],
        #         )
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", """You are a portfolio manager responsible for coordinating the analyst team.
        Based on current analysis results, you need to decide whether further communication with analysts is needed.

        There are two communication methods:
        1. private_chat: One-on-one private chat with individual analyst, suitable for in-depth discussion of specific issues
        2. meeting: Organize multiple analysts for group discussion, suitable for collective decision-making or major disagreements

        Must return decision in JSON format, do not include any other text. Please keep any text content within {max_chars} characters."""),
            
            ("human", """Analyst Signal Summary:
        {analyst_signals}

        Please decide whether communication is needed and explain the reason. If communication is needed, please specify:
        - Communication type (private_chat or meeting)
        - Target analyst list (for private_chat: only one analyst, for meeting: multiple analysts)
        - Discussion topic
        - Selection reason

        Return JSON format:
        {{
        "should_communicate": true/false,
        "communication_type": "private_chat" or "meeting",
        "target_analysts": ["analyst1"] (for private_chat) or ["analyst1", "analyst2"] (for meeting),
        "discussion_topic": "discussion topic",
        "reasoning": "selection reason"
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
            analyst_signals=quiet_json_dumps(signals_summary, ensure_ascii=False, indent=2),
            max_chars=self._get_max_chars(state)
        )
        
        # 获取LLM模型（启用JSON模式）
        llm = self._get_llm_model(state, use_json_mode=True)
        
        # 调用模型（使用 AgentScope 方式）
        response = llm(
            messages=messages,
            temperature=0.7,
            response_format={"type": "json_object"} if llm._use_json_mode else None
        )
        
        # 使用更健壮的JSON解析方法
        try:
            # 首先尝试直接解析
            decision_data = json.loads(response["content"])
            return CommunicationDecision(**decision_data)
        except json.JSONDecodeError as e:
            print(f"警告: 通信决策JSON解析失败: {str(e)}")
            print(f"响应内容: {response['content'][:200]}...")
            
            # 使用备用解析方法
            parsed_response = self._extract_and_clean_json(response["content"])
            if parsed_response:
                print("使用备用方法成功解析通信决策JSON")
                return CommunicationDecision(**parsed_response)
            else:
                print("错误: 所有通信决策JSON解析方法都失败，返回默认决策")
                # 返回默认不通信决策
                return CommunicationDecision(
                    should_communicate=False,
                    communication_type="none",
                    target_analysts=[],
                    discussion_topic="解析失败",
                    reasoning="LLM响应解析失败，默认不进行通信"
                )
    
    def conduct_private_chat(self, manager_id: str, analyst_id: str, 
                           topic: str, analyst_signal: Dict[str, Any], 
                           state, max_rounds: int = 1, streamer=None) -> Dict[str, Any]:
        """进行私聊"""
        print(f"开始私聊: {manager_id} <-> {analyst_id}")
        print(f"话题: {topic}")
        
        # 输出私聊信息到前端
        if streamer:
            streamer.print("system", f"开始私聊: {manager_id} <-> {analyst_id}\n话题: {topic}")
        
        # 在分析师记忆中记录通信开始
        analyst_memory = memory_manager.get_analyst_memory(analyst_id)
        communication_id = None
        if analyst_memory:
            # 获取 trading_date 作为 analysis_date
            analysis_date = state.get("metadata", {}).get("trading_date") or state.get("data", {}).get("end_date")
            communication_id = analyst_memory.start_communication(
                communication_type="private_chat",
                participants=[manager_id, analyst_id],
                topic=topic,
                analysis_date=analysis_date
            )
        
        # 开始私聊
        initial_message = f"Regarding {topic}, I would like to discuss your analysis results with you. Your current signal is: {quiet_json_dumps(analyst_signal, ensure_ascii=False)}"
        
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
            print(f"\n私聊第{round_num + 1}轮:")
            
            # 输出轮次到前端
            if streamer:
                streamer.print("system", f"--- 第 {round_num + 1} 轮对话 ---")
            
            # 分析师回应
            analyst_response = self._get_analyst_chat_response(
                analyst_id, topic, conversation_history, 
                current_analyst_signal, state, streamer=streamer
            )
            # # 截断分析师回应
            # if isinstance(analyst_response, dict) and "response" in analyst_response:
            #     analyst_response["response"] = self._truncate_text(analyst_response["response"], max_chars)
            # pdb.set_trace()
            conversation_history.append({
                "speaker": analyst_id,
                "content": analyst_response["response"],
                "round": round_num + 1
            })
            
            print(f"🗣️ {analyst_id}: {analyst_response['response']}")
            
            # 输出分析师回应到前端
            if streamer:
                response_text = analyst_response.get("response", "")
                # 限制输出长度
                max_display_length = 300
                if len(response_text) > max_display_length:
                    response_text = response_text[:max_display_length] + "..."
                streamer.print("agent", response_text, role_key=analyst_id)
            
            # 记录分析师回应到记忆
            # if analyst_memory and communication_id:
            #     analyst_memory.add_communication_message(
            #         communication_id, analyst_id, analyst_response['response']
            #     )
            
            # 检查是否有信号调整
            if analyst_response.get("signal_adjustment") and analyst_response.get("adjusted_signal"):
                original_signal = current_analyst_signal
                current_analyst_signal = analyst_response["adjusted_signal"]
                print(f"信号已调整: {analyst_response['signal_adjustment']}")
                adjustments_made_counter += 1
                
                # 输出信号调整到前端
                if streamer:
                    # 解析调整前后的信号
                    adjusted_signal = analyst_response.get("adjusted_signal", {})
                    
                    # 处理两种可能的信号格式
                    if isinstance(adjusted_signal, dict):
                        # 格式1: {ticker: {signal: ..., confidence: ...}}
                        if 'ticker_signals' in adjusted_signal:
                            # 格式2: {ticker_signals: [{ticker: ..., signal: ..., confidence: ...}]}
                            adjustment_details = []
                            for ticker_signal in adjusted_signal.get('ticker_signals', []):
                                ticker = ticker_signal.get('ticker', 'N/A')
                                new_signal = ticker_signal.get('signal', 'N/A')
                                new_confidence = ticker_signal.get('confidence', 'N/A')
                                
                                # 获取原始信号
                                original_ticker_signal = {}
                                if isinstance(original_signal, dict):
                                    if 'ticker_signals' in original_signal:
                                        original_ticker_signal = next(
                                            (s for s in original_signal.get('ticker_signals', []) if s.get('ticker') == ticker),
                                            {}
                                        )
                                    elif ticker in original_signal:
                                        original_ticker_signal = original_signal.get(ticker, {})
                                
                                old_signal = original_ticker_signal.get('signal', 'N/A')
                                old_confidence = original_ticker_signal.get('confidence', 'N/A')
                                
                                adjustment_details.append(
                                    f"  {ticker}: {old_signal}({old_confidence}%) → {new_signal}({new_confidence}%)"
                                )
                            
                            if adjustment_details:
                                streamer.print("agent", 
                                    f"我调整了信号:\n" + "\n".join(adjustment_details),
                                    role_key=analyst_id
                                )
                            else:
                                streamer.print("agent", "我调整了信号", role_key=analyst_id)
                        else:
                            # 简单的 ticker: {signal, confidence} 格式
                            adjustment_details = []
                            for ticker, signal_data in adjusted_signal.items():
                                if isinstance(signal_data, dict) and 'signal' in signal_data:
                                    new_signal = signal_data.get('signal', 'N/A')
                                    new_confidence = signal_data.get('confidence', 'N/A')
                                    
                                    old_signal_data = original_signal.get(ticker, {})
                                    old_signal = old_signal_data.get('signal', 'N/A')
                                    old_confidence = old_signal_data.get('confidence', 'N/A')
                                    
                                    adjustment_details.append(
                                        f"  {ticker}: {old_signal}({old_confidence}%) → {new_signal}({new_confidence}%)"
                                    )
                            
                            if adjustment_details:
                                streamer.print("agent", 
                                    f"我调整了信号:\n" + "\n".join(adjustment_details),
                                    role_key=analyst_id
                                )
                            else:
                                streamer.print("agent", "我调整了信号", role_key=analyst_id)
                    else:
                        streamer.print("agent", "我调整了信号", role_key=analyst_id)
                
                # # 记录信号调整到记忆
                # if analyst_memory and communication_id:
                #     analyst_memory.record_signal_adjustment(
                #         communication_id, 
                #         original_signal, 
                #         current_analyst_signal,
                #         f"私聊讨论{topic}后的调整"
                #     )
            
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
                
                # 输出管理者回应到前端
                if streamer:
                    max_display_length = 300
                    manager_display = manager_response if len(manager_response) <= max_display_length else manager_response[:max_display_length] + "..."
                    streamer.print("agent", manager_display, role_key=manager_id)
                
                # # 记录管理者回应到记忆
                # if analyst_memory and communication_id:
                #     analyst_memory.add_communication_message(
                #         communication_id, manager_id, manager_response
                #     )
        
        # pdb.set_trace()
        print("私聊结束")
        
        # 输出私聊结束到前端
        if streamer:
            streamer.print("system", f"私聊结束，共进行 {max_rounds} 轮对话，{adjustments_made_counter} 次信号调整")
        
        memory_format = self._convert_private_chat_to_memory_format(
            conversation_history, manager_id, analyst_id, topic, chat_id
        )

        # 将对话历史存储到分析师memory中
        if analyst_memory and communication_id:
            from src.memory.unified_memory import safe_memory_add
            
            # 将messages和metadata存储到memory
            result = safe_memory_add(
                memory_instance=analyst_memory.memory,
                messages=memory_format["messages"],
                user_id=analyst_id,
                metadata=memory_format["metadata"],
                infer=False,
                operation_name=f"私聊记录存储-{analyst_id}"
            )
            
            
            # 完成通信记录
            analyst_memory.complete_communication(communication_id)

      
        # pdb.set_trace()
        result = {
            "chat_history": conversation_history,
            "final_analyst_signal": current_analyst_signal,
            "adjustments_made": adjustments_made_counter,
        }

        return result
    
    def conduct_meeting(self, manager_id: str, analyst_ids: List[str], 
                       topic: str, analyst_signals: Dict[str, Any], 
                       state, max_rounds: int = 2, streamer=None) -> Dict[str, Any]:
        """进行会议"""
        meeting_id = str(uuid.uuid4())
        print(f"开始会议: {meeting_id}")
        print(f"话题: {topic}")
        print(f"参与者: {', '.join([manager_id] + analyst_ids)}")


        
        # 输出会议ID到前端
        if streamer:
            streamer.print("conference_start", title=topic, conferenceId=meeting_id,
                           participants=[manager_id] + analyst_ids)
        
        # 为每个分析师记录会议开始
        # 获取 trading_date 作为 analysis_date
        analysis_date = state.get("metadata", {}).get("trading_date") or state.get("data", {}).get("end_date")
        
        communication_ids = {}
        for analyst_id in analyst_ids:
            analyst_memory = memory_manager.get_analyst_memory(analyst_id)
            if analyst_memory:
                comm_id = analyst_memory.start_communication(
                    communication_type="meeting",
                    participants=[manager_id] + analyst_ids,
                    topic=topic,
                    analysis_date=analysis_date
                )
                communication_ids[analyst_id] = comm_id
        
        # 初始化会议信息（只用于日志记录）
        print(f"会议创建成功 - ID: {meeting_id}")
        
        current_signals = analyst_signals.copy()
        meeting_transcript = []
        adjustments_made_counter = 0
        
        # 管理者开场
        opening_message = f"Let's discuss {topic}. Please share your viewpoints and analysis results."
        meeting_transcript.append({
            "speaker": manager_id,
            "content": opening_message,
            "round": 1,
            "timestamp": datetime.now().isoformat()
        })
        
        # 输出开场发言到前端
        if streamer:
            streamer.print("agent", f"[开场] {opening_message}", role_key=manager_id)
        
        max_chars = self._get_max_chars(state)
        for round_num in range(max_rounds):
            print(f"\n会议第{round_num + 1}轮发言:")
            
            # 输出轮次到前端
            if streamer:
                streamer.print("system", f"--- 第 {round_num + 1} 轮发言 ---")
            
            # 调试：打印当前会议记录状态
            if round_num > 0:
                print(f"当前会议记录条数: {len(meeting_transcript)}")
                # if meeting_transcript:
                #     print(f"最后一条记录: {meeting_transcript[-1]}")
            
            # 每个分析师发言
            for analyst_id in analyst_ids:
                analyst_response = self._get_analyst_meeting_response(
                    analyst_id, topic, meeting_transcript, 
                    current_signals.get(analyst_id, {}), 
                    current_signals, state, round_num + 1, streamer=streamer
                )
                # # 截断分析师发言
                # if isinstance(analyst_response, dict) and "response" in analyst_response:
                #     analyst_response["response"] = self._truncate_text(analyst_response["response"], max_chars)
                
                meeting_transcript.append({
                    "speaker": analyst_id,
                    "content": analyst_response["response"],
                    "round": round_num + 1,
                    "timestamp": datetime.now().isoformat()
                })
                
                # print(f"{analyst_id}: {analyst_response['response']}") 
                print(f"{analyst_id}: {analyst_response}")
                
                # 输出分析师发言到前端
                if streamer:
                    response_text = analyst_response.get("response", "")
                    # 限制输出长度，避免过长
                    max_display_length = 300
                    if len(response_text) > max_display_length:
                        response_text = response_text[:max_display_length] + "..."
                    streamer.print("agent", response_text, role_key=analyst_id)

                # 记录发言到分析师记忆
                # analyst_memory = memory_manager.get_analyst_memory(analyst_id)
                # if analyst_memory and analyst_id in communication_ids:
                #     analyst_memory.add_communication_message(
                #         communication_ids[analyst_id], analyst_id, analyst_response['response']
                #     )
                
                # 检查信号调整
                if analyst_response.get("signal_adjustment") and analyst_response.get("adjusted_signal"):
                    original_signal = current_signals[analyst_id]
                    current_signals[analyst_id] = analyst_response["adjusted_signal"]
                    print(f"{analyst_id} 调整了信号")
                    adjustments_made_counter += 1
                    
                    # 输出信号调整到前端
                    if streamer:
                        # 解析调整前后的信号
                        adjusted_signal = analyst_response.get("adjusted_signal", {})
                        
                        # 处理两种可能的信号格式
                        if isinstance(adjusted_signal, dict):
                            # 格式1: {ticker: {signal: ..., confidence: ...}}
                            if 'ticker_signals' in adjusted_signal:
                                # 格式2: {ticker_signals: [{ticker: ..., signal: ..., confidence: ...}]}
                                adjustment_details = []
                                for ticker_signal in adjusted_signal.get('ticker_signals', []):
                                    ticker = ticker_signal.get('ticker', 'N/A')
                                    new_signal = ticker_signal.get('signal', 'N/A')
                                    new_confidence = ticker_signal.get('confidence', 'N/A')
                                    
                                    # 获取原始信号
                                    original_ticker_signal = {}
                                    if isinstance(original_signal, dict):
                                        if 'ticker_signals' in original_signal:
                                            original_ticker_signal = next(
                                                (s for s in original_signal.get('ticker_signals', []) if s.get('ticker') == ticker),
                                                {}
                                            )
                                        elif ticker in original_signal:
                                            original_ticker_signal = original_signal.get(ticker, {})
                                    
                                    old_signal = original_ticker_signal.get('signal', 'N/A')
                                    old_confidence = original_ticker_signal.get('confidence', 'N/A')
                                    
                                    adjustment_details.append(
                                        f"  {ticker}: {old_signal}({old_confidence}%) → {new_signal}({new_confidence}%)"
                                    )
                                
                                if adjustment_details:
                                    streamer.print("agent", 
                                        f"我调整了信号:\n" + "\n".join(adjustment_details),
                                        role_key=analyst_id
                                    )
                                else:
                                    streamer.print("agent", "我调整了信号", role_key=analyst_id)
                            else:
                                # 简单的 ticker: {signal, confidence} 格式
                                adjustment_details = []
                                for ticker, signal_data in adjusted_signal.items():
                                    if isinstance(signal_data, dict) and 'signal' in signal_data:
                                        new_signal = signal_data.get('signal', 'N/A')
                                        new_confidence = signal_data.get('confidence', 'N/A')
                                        
                                        old_signal_data = original_signal.get(ticker, {})
                                        old_signal = old_signal_data.get('signal', 'N/A')
                                        old_confidence = old_signal_data.get('confidence', 'N/A')
                                        
                                        adjustment_details.append(
                                            f"  {ticker}: {old_signal}({old_confidence}%) → {new_signal}({new_confidence}%)"
                                        )
                                
                                if adjustment_details:
                                    streamer.print("agent", 
                                        f"我调整了信号:\n" + "\n".join(adjustment_details),
                                        role_key=analyst_id
                                    )
                                else:
                                    streamer.print("agent", "我调整了信号", role_key=analyst_id)
                        else:
                            streamer.print("agent", "我调整了信号", role_key=analyst_id)
                    
                    # 记录信号调整到记忆
                    # if analyst_memory and analyst_id in communication_ids:
                    #     analyst_memory.record_signal_adjustment(
                    #         communication_ids[analyst_id],
                    #         original_signal,
                    #         analyst_response["adjusted_signal"],
                    #         f"会议讨论{topic}后的调整"
                    #     )
            
            # 进入下一轮发言（轮次管理在meeting_transcript中自动处理）
        
        # 管理者总结
        summary = self._get_manager_meeting_summary(
            manager_id, meeting_transcript, current_signals, state
        )
        summary = self._truncate_text(summary, max_chars)
        
        meeting_transcript.append({
            "speaker": manager_id,
            "content": summary,
            "round": round_num,
            "timestamp": datetime.now().isoformat()
        })
        
        print(f"会议总结: {summary}")
        
        # 输出会议总结到前端
        if streamer:
            streamer.print("system", "--- 会议总结 ---")
            # 限制总结长度
            max_summary_length = 400
            summary_display = summary if len(summary) <= max_summary_length else summary[:max_summary_length] + "..."
            streamer.print("agent", f"[总结] {summary_display}", role_key=manager_id)
        
        print("会议结束")
        streamer.print("conference_end",conference_id=meeting_id)
        memory_format = self._convert_transcript_to_memory_format(
            meeting_transcript, meeting_id, topic, max_rounds
        )

        # 完成所有分析师的通信记录
        for analyst_id in analyst_ids:
            if analyst_id in communication_ids:
                analyst_memory = memory_manager.get_analyst_memory(analyst_id)
                if analyst_memory:
                    from src.memory.unified_memory import safe_memory_add
                    
                    # 将messages和metadata存储到memory
                    result = safe_memory_add(
                        memory_instance=analyst_memory.memory,
                        messages=memory_format["messages"],
                        user_id=analyst_id,
                        metadata=memory_format["metadata"],
                        infer=False,
                        operation_name=f"会议记录存储-{analyst_id}"
                    )
                    
                    analyst_memory.complete_communication(communication_ids[analyst_id])
        # pdb.set_trace()

        result = {
            "meeting_id": meeting_id,
            "transcript": meeting_transcript,
            "final_signals": current_signals,
            "adjustments_made": adjustments_made_counter
        }
        return result
    
    def _get_analyst_chat_response(self, analyst_id: str, topic: str, 
                                 conversation_history: List[Dict], 
                                 current_signal: Dict[str, Any], 
                                 state, streamer=None) -> Dict[str, Any]:
        """获取分析师在私聊中的回应（两阶段记忆检索）"""
        
        # ========== 第一阶段：让analyst生成记忆查询query ⭐⭐⭐ ==========
        analyst_memory = memory_manager.get_analyst_memory(analyst_id)
        relevant_memories = ""
        
        if analyst_memory:
            tickers = state.get("data", {}).get("tickers", [])
            
            # 1. 生成记忆查询query
            memory_query = self._generate_memory_query_for_chat(
                analyst_id, topic, conversation_history, tickers, state
            )
            
            # 2. 使用生成的query检索相关记忆
            if memory_query:
                try:
                    # 广播memory搜索操作
                    if streamer:
                        streamer.print(
                            "memory",
                            f"搜索记忆: {memory_query[:60]}...",
                            agent_id=analyst_id,
                            operation_type="search"
                        )
                    
                    search_results = analyst_memory.memory.search(
                        query=memory_query,
                        user_id=analyst_id,
                        top_k=1  # ⭐ 修正参数名：limit -> top_k (reme框架标准参数)
                    )
                    
                    if search_results and search_results.get('results'):
                        relevant_memories = "\n".join([
                            f"- {mem.get('memory', '')}" 
                            for mem in search_results['results']
                        ])
                        print(f"✅ {analyst_id} 检索到 {len(search_results['results'])} 条相关记忆")
                        
                        # 广播搜索成功
                        if streamer:
                            streamer.print(
                                "memory",
                                f"找到 {len(search_results['results'])} 条相关记忆",
                                agent_id=analyst_id,
                                operation_type="search_success"
                            )
                        # print(relevant_memories)
                    else:
                        print(f"⚠️ {analyst_id} 未检索到相关记忆")
                        if streamer:
                            streamer.print(
                                "memory",
                                "未找到相关记忆",
                                agent_id=analyst_id,
                                operation_type="search_empty"
                            )
                except Exception as e:
                    print(f"⚠️ {analyst_id} 记忆检索失败: {e}")
                    relevant_memories = ""
                    if streamer:
                        streamer.print(
                            "memory",
                            f"记忆检索失败: {str(e)[:50]}",
                            agent_id=analyst_id,
                            operation_type="search_error"
                        )
        
        # ========== 第二阶段：基于检索到的记忆生成回应 ⭐⭐⭐ ==========
        prompt_template = ChatPromptTemplate.from_messages([
    ("system", """You are {analyst_id} analyst. You are having a one-on-one discussion with the portfolio manager.

Your relevant memories and past experiences (retrieved based on this conversation topic):
{relevant_memories}

Based on your relevant memories, conversation history and current analysis signal, please:
1. Respond to the manager's questions or viewpoints
2. Explain your analysis logic (you can reference your previous analysis process)
3. If necessary, adjust your signal, confidence level or reasoning based on new information

Current signal for the topic:
{current_signal}

If you need to adjust the signal, please clearly state the adjustment content and reason in your response.

Please must return your response in JSON format, strictly following the JSON structure below, do not include any other text:

Important: ticker_signals must be an object array, not a string array!

{{
  "response": "your response content",
  "signal_adjustment": true/false,
  "adjusted_signal": {{
    "analyst_id": "{analyst_id}",
    "analyst_name": "your analyst name",
    "ticker_signals": [
      {{"ticker": "AAPL", "signal": "bearish", "confidence": 85, "reasoning": "adjustment reason"}},
      {{"ticker": "MSFT", "signal": "neutral", "confidence": 70, "reasoning": "adjustment reason"}}
    ]
  }}
}}

Prohibited incorrect format:
{{"ticker_signals": ["ticker_signals: [...]"]}}

Must use correct format:
{{"ticker_signals": [{{"ticker": "AAPL", "signal": "bearish", "confidence": 85}}]}}

Note: Please keep the "response" field text content within {max_chars} characters."""),
    
    ("human", """Conversation topic: {topic}

Current conversation history:
{conversation_history}

Please respond to the latest conversation content based on your complete memory and analysis history.""")
])
        
        messages = prompt_template.format_messages(
            analyst_id=analyst_id,
            relevant_memories=relevant_memories if relevant_memories else "No relevant past memories found for this topic.",
            current_signal=quiet_json_dumps(current_signal, ensure_ascii=False),
            topic=topic,
            conversation_history=self._format_conversation_history(conversation_history),
            max_chars=self._get_max_chars(state)
        )
        
        # 获取LLM模型（启用JSON模式）
        llm = self._get_llm_model(state, use_json_mode=True)
        
        # 调用模型（使用 AgentScope 方式）
        response = llm(
            messages=messages,
            temperature=0.7,
            response_format={"type": "json_object"} if llm._use_json_mode else None
        )
        
        # 使用更健壮的JSON解析方法
        try:
            # 首先尝试直接解析
            return json.loads(response["content"])
        except json.JSONDecodeError as e:
            print(f"警告: 分析师聊天响应JSON解析失败: {str(e)}")
            print(f"响应内容: {response['content'][:200]}...")
            
            # 使用备用解析方法
            parsed_response = self._extract_and_clean_json(response["content"])
            if parsed_response:
                print("使用备用方法成功解析分析师聊天响应JSON")
                return parsed_response
            else:
                print("错误: 所有分析师聊天响应JSON解析方法都失败")
                # 返回默认响应
                return {
                    "response": "解析响应失败，使用默认回应",
                    "signal_adjustment": False
                }
    
    def _convert_transcript_to_memory_format(self, meeting_transcript: List[Dict], 
                                        meeting_id: str, topic: str, 
                                        total_rounds: int) -> Dict[str, Any]:
        """
        将meeting_transcript转换为适合memory系统的格式
        
        Args:
            meeting_transcript: 原始会议记录
            meeting_id: 会议ID  
            topic: 会议主题
            total_rounds: 总轮数
            
        Returns:
            转换后的格式，包含messages和metadata
        """
        messages = []
        
        # 将每个发言转换为user role的消息格式
        for entry in meeting_transcript:
            speaker = entry["speaker"]
            content = entry["content"]
            
            # 格式化内容：发言者名称 + 发言内容
            formatted_content = f"{speaker}: {content}"
            
            # 所有发言都以user角色存储，便于统一管理
            message = {
                "role": "user",
                "content": formatted_content
            }
            
            messages.append(message)
        
        # 构建metadata
        metadata = {
            "meeting_id": meeting_id,
            "topic": topic,
            "total_rounds": total_rounds,
            "total_messages": len(meeting_transcript),
            "participants": list(set([entry["speaker"] for entry in meeting_transcript])),
            "communication_type": "meeting"
        }
        
        return {
            "messages": messages,
            "metadata": metadata
        }

    def _convert_private_chat_to_memory_format(self, conversation_history: List[Dict],
                                            manager_id: str, analyst_id: str,
                                            topic: str, chat_id: str) -> Dict[str, Any]:
        """
        将私聊对话历史转换为适合memory系统的格式
        
        Args:
            conversation_history: 对话历史
            manager_id: 管理者ID
            analyst_id: 分析师ID
            topic: 对话主题
            chat_id: 对话ID
            
        Returns:
            转换后的格式，包含messages和metadata
        """
        messages = []
        
        # 添加初始消息（管理者开场）
        initial_message = f"Regarding {topic}, I would like to discuss your analysis results with you."
        messages.append({
            "role": "user",
            "content": f"{manager_id}: {initial_message}"
        })
        
        # 将每个对话转换为user role的消息格式
        for entry in conversation_history:
            speaker = entry["speaker"]
            content = entry["content"]
            
            # 格式化内容：发言者名称 + 发言内容
            formatted_content = f"{speaker}: {content}"
            
            # 所有发言都以user角色存储，便于统一管理
            message = {
                "role": "user",
                "content": formatted_content
            }
            
            messages.append(message)
        
        # 构建metadata
        metadata = {
            "chat_id": chat_id,
            "topic": topic,
            "total_rounds": len([entry for entry in conversation_history if entry["speaker"] == analyst_id]),
            "total_messages": len(conversation_history) + 1,  # +1 for initial message
            "participants": [manager_id, analyst_id],
            "communication_type": "private_chat",
            "manager_id": manager_id,
            "analyst_id": analyst_id
        }
        
        return {
            "messages": messages,
            "metadata": metadata
        }   
    def _get_manager_chat_response(self, manager_id: str, analyst_id: str,
                                 conversation_history: List[Dict],
                                 current_signal: Dict[str, Any], 
                                 state) -> str:
        """获取管理者在私聊中的回应"""
        
        prompt_template = ChatPromptTemplate.from_messages([
    ("system", """You are a portfolio manager having a one-on-one discussion with an analyst.
Based on the analyst's response, continue the conversation, ask questions or give suggestions.
Maintain a professional and constructive conversation style. Please keep your response within {max_chars} characters."""),
    
    ("human", """Conversation history:
{conversation_history}

Analyst's current signal:
{current_signal}

Please respond to the analyst's latest statement.""")
])
        
        messages = prompt_template.format_messages(
            conversation_history=self._format_conversation_history(conversation_history),
            current_signal=quiet_json_dumps(current_signal, ensure_ascii=False),
            max_chars=self._get_max_chars(state)
        )
        
        # 获取LLM模型
        llm = self._get_llm_model(state)
        
        # 调用模型（使用 AgentScope 方式）
        response = llm(messages=messages, temperature=0.7)
        return response["content"]
    
    def _get_analyst_meeting_response(self, analyst_id: str, topic: str,
                                    meeting_transcript: List[Dict],
                                    current_signal: Dict[str, Any],
                                    all_signals: Dict[str, Any],
                                    state, round_num: int, streamer=None) -> Dict[str, Any]:
        """获取分析师在会议中的发言（两阶段记忆检索）"""
        
        # ========== 第一阶段：让analyst生成记忆查询query ⭐⭐⭐ ==========
        analyst_memory = memory_manager.get_analyst_memory(analyst_id)
        relevant_memories = ""
        
        if analyst_memory:
            tickers = state.get("data", {}).get("tickers", [])
            
            # 1. 生成记忆查询query
            memory_query = self._generate_memory_query_for_meeting(
                analyst_id, topic, meeting_transcript, tickers, state
            )
            
            # 2. 使用生成的query检索相关记忆
            if memory_query:
                try:
                    # 广播memory搜索操作
                    if streamer:
                        streamer.print(
                            "memory",
                            f"搜索记忆: {memory_query[:60]}...",
                            agent_id=analyst_id,
                            operation_type="search"
                        )
                    
                    search_results = analyst_memory.memory.search(
                        query=memory_query,
                        user_id=analyst_id,
                        top_k=1  # ⭐ 修正参数名：limit -> top_k (reme框架标准参数)
                    )
                    
                    if search_results and search_results.get('results'):
                        relevant_memories = "\n".join([
                            f"- {mem.get('memory', '')}" 
                            for mem in search_results['results']
                        ])
                        print(f"✅ {analyst_id} 在会议中检索到 {len(search_results['results'])} 条相关记忆")
                        print(relevant_memories)
                        
                        # 广播搜索成功
                        if streamer:
                            streamer.print(
                                "memory",
                                f"找到 {len(search_results['results'])} 条相关记忆",
                                agent_id=analyst_id,
                                operation_type="search_success"
                            )
                    else:
                        print(f"⚠️ {analyst_id} 在会议中未检索到相关记忆")
                        if streamer:
                            streamer.print(
                                "memory",
                                "未找到相关记忆",
                                agent_id=analyst_id,
                                operation_type="search_empty"
                            )
                except Exception as e:
                    print(f"⚠️ {analyst_id} 会议记忆检索失败: {e}")
                    relevant_memories = ""
                    if streamer:
                        streamer.print(
                            "memory",
                            f"记忆检索失败: {str(e)[:50]}",
                            agent_id=analyst_id,
                            operation_type="search_error"
                        )
        
        # ========== 第二阶段：基于检索到的记忆生成发言 ⭐⭐⭐ ==========
        prompt_template = ChatPromptTemplate.from_messages([
    ("system", """You are {analyst_id} analyst participating in an investment meeting.

Your relevant memories and past experiences (retrieved based on this meeting topic):
{relevant_memories}

Your current analysis signal:
{current_signal}

Please must return your response in JSON format, strictly following the JSON structure below, do not include any other text:

Important: ticker_signals must be an object array, not a string array!

{{
  "response": "your speech content",
  "signal_adjustment": true/false,
  "adjusted_signal": {{
    "analyst_id": "{analyst_id}",
    "analyst_name": "your analyst name",
    "ticker_signals": [
      {{"ticker": "AAPL", "signal": "bearish", "confidence": 85, "reasoning": "adjustment reason"}},
      {{"ticker": "MSFT", "signal": "neutral", "confidence": 70, "reasoning": "adjustment reason"}}
    ]
  }}
}}

Prohibited incorrect format:
{{"ticker_signals": ["ticker_signals: [...]"]}}

Must use correct format:
{{"ticker_signals": [{{"ticker": "AAPL", "signal": "bearish", "confidence": 85}}]}}

Note: Please keep the "response" field text content within {max_chars} characters."""),
    
    ("human", """Meeting topic: {topic}

This is round {round_num} of speeches.

Meeting transcript (Important! Please read carefully and respond):
{meeting_transcript}

Other analysts' signals:
{other_signals}

Speech requirements:
1. If this is round 1: Share your viewpoints and analysis basis
2. If this is round 2 or more:
   - Must explicitly respond to specific viewpoints from other analysts in previous rounds
   - State whether you agree or disagree with their analysis, and give reasons
   - Consider whether to adjust your signal based on discussion content
   - Avoid repeating round 1 speech content

Please speak based on meeting transcript and discussion content, showing genuine interaction and critical thinking process.""")
])
        
        messages = prompt_template.format_messages(
            analyst_id=analyst_id,
            relevant_memories=relevant_memories if relevant_memories else "No relevant past memories found for this topic.",
            round_num=round_num,
            current_signal=quiet_json_dumps(current_signal, ensure_ascii=False),
            topic=topic,
            meeting_transcript=self._format_meeting_transcript(meeting_transcript),
            other_signals=quiet_json_dumps({k: v for k, v in all_signals.items() if k != analyst_id}, ensure_ascii=False, indent=2),
            max_chars=self._get_max_chars(state)
        )
        # pdb.set_trace()
        # 获取LLM模型（启用JSON模式）
        llm = self._get_llm_model(state, use_json_mode=True)
        
        # 调用模型（使用 AgentScope 方式）
        response = llm(
            messages=messages,
            temperature=0.7,
            response_format={"type": "json_object"} if llm._use_json_mode else None
        )
        
        # 使用更健壮的JSON解析方法
        try:
            # 首先尝试直接解析
            return json.loads(response["content"])
        except json.JSONDecodeError as e:
            print(f"警告: 分析师会议响应JSON解析失败: {str(e)}")
            print(f"响应内容: {response['content'][:200]}...")
            
            # 使用备用解析方法
            parsed_response = self._extract_and_clean_json(response["content"])
            if parsed_response:
                print("使用备用方法成功解析分析师会议响应JSON")
                return parsed_response
            else:
                print("错误: 所有分析师会议响应JSON解析方法都失败")
                # 返回默认响应
                return {
                    "response": "解析响应失败，使用默认回应",
                    "signal_adjustment": False
                }
    
    def _get_manager_meeting_summary(self, manager_id: str, 
                                   meeting_transcript: List[Dict],
                                   final_signals: Dict[str, Any], 
                                   state) -> str:
        """获取管理者的会议总结"""
        
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", """You are a portfolio manager summarizing meeting content.
        Please concisely summarize discussion points and final consensus reached. Please keep the summary within {max_chars} characters."""),
            
            ("human", """Meeting transcript:
        {meeting_transcript}

        Final signals:
        {final_signals}

        Please summarize this meeting.""")
        ])
        
        messages = prompt_template.format_messages(
            meeting_transcript=self._format_meeting_transcript(meeting_transcript),
            final_signals=quiet_json_dumps(final_signals, ensure_ascii=False, indent=2),
            max_chars=self._get_max_chars(state)
        )
        
        # 获取LLM模型
        llm = self._get_llm_model(state)
        
        # 调用模型（使用 AgentScope 方式）
        response = llm(messages=messages, temperature=0.7)
        return response["content"]
    
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
    
    def _generate_memory_query_for_chat(self, analyst_id: str, topic: str, 
                                       conversation_history: List[Dict],
                                       tickers: List[str], state) -> str:
        """
        第一阶段：让analyst根据私聊话题和上下文生成记忆查询query
        
        Args:
            analyst_id: 分析师ID
            topic: 私聊话题
            conversation_history: 对话历史
            tickers: 股票代码列表
            state: 系统状态
            
        Returns:
            记忆查询query字符串
        """
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", """You are {analyst_id} analyst. You are about to respond in a private chat with the portfolio manager.

Before responding, you need to search your past analysis experiences and memories to inform your response.

Please generate a concise search query (in Chinese or English, 1-2 sentences) to retrieve relevant memories from your past experiences.

The query should focus on:
1. The specific stocks being discussed: {tickers}
2. The conversation topic: {topic}
3. Key themes from recent conversation
4. Similar analysis scenarios or lessons learned

Return ONLY the search query text, no explanations or extra formatting."""),
            
            ("human", """Conversation topic: {topic}
Stocks: {tickers}

Recent conversation:
{conversation_history}

Generate a focused search query to retrieve relevant past memories and experiences.""")
        ])
        
        messages = prompt_template.format_messages(
            analyst_id=analyst_id,
            topic=topic,
            tickers=", ".join(tickers),
            conversation_history=self._format_conversation_history(conversation_history[-3:]) if conversation_history else "No previous conversation"
        )
        
        try:
            llm = self._get_llm_model(state)
            response = llm(messages=messages, temperature=0.7)
            query = response["content"].strip()
            print(f"📝 {analyst_id} 生成记忆查询: {query}")
            return query
        except Exception as e:
            print(f"⚠️ {analyst_id} 生成记忆查询失败: {e}")
            # 返回默认查询
            return f"{topic} {' '.join(tickers)} 分析经验"
    
    def _generate_memory_query_for_meeting(self, analyst_id: str, topic: str,
                                          meeting_transcript: List[Dict],
                                          tickers: List[str], state) -> str:
        """
        第一阶段：让analyst根据会议话题和上下文生成记忆查询query
        
        Args:
            analyst_id: 分析师ID
            topic: 会议话题
            meeting_transcript: 会议记录
            tickers: 股票代码列表
            state: 系统状态
            
        Returns:
            记忆查询query字符串
        """
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", """You are {analyst_id} analyst. You are about to speak in an investment meeting.

Before speaking, you need to search your past analysis experiences and memories to inform your contribution.

Please generate a concise search query (in Chinese or English, 1-2 sentences) to retrieve relevant memories from your past experiences.

The query should focus on:
1. The specific stocks being discussed: {tickers}
2. The meeting topic: {topic}
3. Key themes from meeting discussion so far
4. Similar analysis scenarios or lessons learned

Return ONLY the search query text, no explanations or extra formatting."""),
            
            ("human", """Meeting topic: {topic}
Stocks: {tickers}

Recent meeting discussion:
{meeting_transcript}

Generate a focused search query to retrieve relevant past memories and experiences.""")
        ])
        
        messages = prompt_template.format_messages(
            analyst_id=analyst_id,
            topic=topic,
            tickers=", ".join(tickers),
            meeting_transcript=self._format_meeting_transcript(meeting_transcript[-5:]) if meeting_transcript else "Meeting just started"
        )
        
        try:
            llm = self._get_llm_model(state)
            response = llm(messages=messages, temperature=0.7)
            query = response["content"].strip()
            print(f"📝 {analyst_id} 在会议中生成记忆查询: {query}")
            return query
        except Exception as e:
            print(f"⚠️ {analyst_id} 会议记忆查询生成失败: {e}")
            # 返回默认查询
            return f"{topic} {' '.join(tickers)} 分析经验"
    
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
