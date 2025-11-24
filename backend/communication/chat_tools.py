#!/usr/bin/env python3
"""
Communication Tools - Implementation of private chat and meeting features
"""

import json
import uuid
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field

from backend.llm.models import get_model as get_agentscope_model
from backend.memory.manager import get_memory
from backend.agents.prompt_loader import PromptLoader

class PrivateChatMessage(BaseModel):
    """Private chat message model"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sender: str = Field(..., description="Sender ID")
    receiver: str = Field(..., description="Receiver ID")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(default_factory=datetime.now)
    message_type: str = Field(default="chat", description="Message type")




class SignalAdjustment(BaseModel):
    """Signal adjustment model"""
    ticker: str = Field(..., description="Stock ticker")
    original_signal: str = Field(..., description="Original signal")
    adjusted_signal: str = Field(..., description="Adjusted signal")
    original_confidence: int = Field(..., description="Original confidence")
    adjusted_confidence: int = Field(..., description="Adjusted confidence")
    adjustment_reasoning: str = Field(..., description="Adjustment reasoning")


class CommunicationDecision(BaseModel):
    """Communication decision model"""
    should_communicate: bool = Field(..., description="Whether communication is needed")
    communication_type: str = Field(..., description="Communication type: private_chat or meeting")
    target_analysts: List[str] = Field(default_factory=list, description="Target analyst list")
    discussion_topic: str = Field(..., description="Discussion topic")
    reasoning: str = Field(..., description="Reason for choosing communication")


class PrivateChatSystem:
    """Private chat system"""
    
    def __init__(self):
        self.chat_histories: Dict[str, List[PrivateChatMessage]] = {}
    
    def start_private_chat(self, manager_id: str, analyst_id: str, 
                          initial_message: str) -> str:
        """Start private chat conversation"""
        chat_key = f"{manager_id}_{analyst_id}"
        
        if chat_key not in self.chat_histories:
            self.chat_histories[chat_key] = []
        
        # Add manager's initial message
        message = PrivateChatMessage(
            sender=manager_id,
            receiver=analyst_id,
            content=initial_message
        )
        
        self.chat_histories[chat_key].append(message)
        return message.id
    
    def send_message(self, sender: str, receiver: str, content: str) -> str:
        """Send message"""
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
        """Get chat history"""
        chat_key = f"{participant1}_{participant2}" if participant1 < participant2 else f"{participant2}_{participant1}"
        return self.chat_histories.get(chat_key, [])




class CommunicationManager:
    """Communication manager"""
    
    def __init__(self):
        self.private_chat_system = PrivateChatSystem()
        self.prompt_loader = PromptLoader()
        
    def _get_max_chars(self, state) -> int:
        """Get maximum character count for communication text, default 400, can be overridden via state.metadata.communication_max_chars"""
        try:
            return int(state.get("metadata", {}).get("communication_max_chars", 400))
        except Exception:
            return 400
    
    def _truncate_text(self, text: str, max_chars: int) -> str:
        """Truncate text by character limit (for Chinese), keep first max_chars characters"""
        if not isinstance(text, str):
            return text
        return text if len(text) <= max_chars else text[:max_chars]
    
    def _persist_communication_result(self, payload: Dict[str, Any], comm_type: str, state):
        """Write communication result to current session's output JSON file (obtained from state.metadata.output_file)"""
        default_name = f"/root/wuyue.wy/Project/IA/analysis_results_logs/communications_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        log_path = state.get("metadata", {}).get("output_file", default_name)
        try:
            # Ensure directory exists
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
            # Other types directly append to communication_logs root, with type
            payload_with_type = {"type": comm_type, **payload}
            data["communication_logs"].setdefault("others", []).append(payload_with_type)
        
        try:
            with open(log_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print("Communication result written to log file")
        except Exception as e:
            print(f"Error: Failed to write communication log: {e}")
    
    def _get_llm_model(self, state, agent_id="portfolio_manager", use_json_mode=False):
        """Get LLM model instance (using AgentScope model wrapper)"""
        # Get API keys from state
        api_keys = {}
        if state and "metadata" in state:
            request = state.get("metadata", {}).get("request")
            if request and hasattr(request, 'api_keys'):
                api_keys = request.api_keys
        
        # If not in metadata, try to get from data
        if not api_keys and state and "data" in state and "api_keys" in state["data"]:
            api_keys = state["data"]["api_keys"]
        
        # Use portfolio_manager's model configuration for communication
        from backend.utils.tool_call import get_agent_model_config
        model_name, model_provider = get_agent_model_config(state, agent_id)
        
        # Use AgentScope model wrapper
        llm = get_agentscope_model(model_name, model_provider, api_keys)
        
        # Store flag for whether to use JSON mode, for use when calling
        llm._use_json_mode = use_json_mode
        
        return llm
    
    def decide_communication_strategy(self, manager_signals: Dict[str, Any], 
                                    analyst_signals: Dict[str, Any], 
                                    state) -> CommunicationDecision:
        """Decide communication strategy"""
        
        # Format analyst signals
        signals_summary = {}
        for analyst_id, signal_data in analyst_signals.items():
            if isinstance(signal_data, dict) and 'ticker_signals' in signal_data:
                signals_summary[analyst_id] = signal_data['ticker_signals']
            else:
                signals_summary[analyst_id] = signal_data
        
        # Load prompt
        prompt_data = {
            "analyst_signals": json.dumps(signals_summary, ensure_ascii=False, indent=2),
            "max_chars": self._get_max_chars(state)
        }
        
        system_prompt = self.prompt_loader.load_prompt("communication", "decide_strategy_system", variables=prompt_data)
        human_prompt = self.prompt_loader.load_prompt("communication", "decide_strategy_human", variables=prompt_data)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": human_prompt}
        ]
        
        # Get LLM model (enable JSON mode)
        llm = self._get_llm_model(state, agent_id="portfolio_manager", use_json_mode=True)
        
        # Call model (using AgentScope method)
        response = llm(
            messages=messages,
            temperature=0.7,
            response_format={"type": "json_object"} if llm._use_json_mode else None
        )
        
        # Use more robust JSON parsing method
        try:
            # First try direct parsing
            decision_data = json.loads(response["content"])
            return CommunicationDecision(**decision_data)
        except json.JSONDecodeError as e:
            print(f"Warning: Communication decision JSON parsing failed: {str(e)}")
            print(f"Response content: {response['content'][:200]}...")
            
            # Use fallback parsing method
            parsed_response = self._extract_and_clean_json(response["content"])
            if parsed_response:
                print("Successfully parsed communication decision JSON using fallback method")
                return CommunicationDecision(**parsed_response)
            else:
                print("Error: All communication decision JSON parsing methods failed, returning default decision")
                # Return default no-communication decision
                return CommunicationDecision(
                    should_communicate=False,
                    communication_type="none",
                    target_analysts=[],
                    discussion_topic="Parsing failed",
                    reasoning="LLM response parsing failed, default to no communication"
                )
    
    def conduct_private_chat(self, manager_id: str, analyst_id: str, 
                           topic: str, analyst_signal: Dict[str, Any], 
                           state, max_rounds: int = 1, streamer=None) -> Dict[str, Any]:
        """Conduct private chat"""
        print(f"Starting private chat: {manager_id} <-> {analyst_id}")
        print(f"Topic: {topic}")
        
        # Output private chat info to frontend
        if streamer:
            streamer.print("system", f"Starting private chat: {manager_id} <-> {analyst_id}\nTopic: {topic}")
        
        # Note: Communication logging functionality has been simplified, no longer records start_communication
        # If needed, can directly add memory via memory.add()
        
        # Start private chat
        initial_message = f"Regarding {topic}, I would like to discuss your analysis results with you. Your current signal is: {json.dumps(analyst_signal, ensure_ascii=False)}"
        
        chat_id = self.private_chat_system.start_private_chat(
            manager_id, analyst_id, initial_message
        )
        
        conversation_history = []
        current_analyst_signal = analyst_signal.copy()
        adjustments_made_counter = 0
        
        max_chars = self._get_max_chars(state)
        for round_num in range(max_rounds):
            print(f"\nPrivate chat round {round_num + 1}:")
            
            # Output round to frontend
            if streamer:
                streamer.print("system", f"--- Round {round_num + 1} conversation ---")
            
            # Analyst response
            analyst_response = self._get_analyst_chat_response(
                analyst_id, topic, conversation_history, 
                current_analyst_signal, state, streamer=streamer
            )
            # # Truncate analyst response
            # if isinstance(analyst_response, dict) and "response" in analyst_response:
            #     analyst_response["response"] = self._truncate_text(analyst_response["response"], max_chars)
            # pdb.set_trace()
            conversation_history.append({
                "speaker": analyst_id,
                "content": analyst_response["response"],
                "round": round_num + 1
            })
            
            print(f"🗣️ {analyst_id}: {analyst_response['response']}")
            
            # Output analyst response to frontend
            if streamer:
                response_text = analyst_response.get("response", "")
                # Limit output length
                max_display_length = 300
                if len(response_text) > max_display_length:
                    response_text = response_text[:max_display_length] + "..."
                streamer.print("agent", response_text, role_key=analyst_id)
            
            # Record analyst response to memory
            # if analyst_memory and communication_id:
            #     analyst_memory.add_communication_message(
            #         communication_id, analyst_id, analyst_response['response']
            #     )
            
            # Check for signal adjustment
            if analyst_response.get("signal_adjustment") and analyst_response.get("adjusted_signal"):
                original_signal = current_analyst_signal
                current_analyst_signal = analyst_response["adjusted_signal"]
                print(f"Signal adjusted: {analyst_response['signal_adjustment']}")
                adjustments_made_counter += 1
                print(analyst_response)
                
                # Output signal adjustment to frontend
                if streamer:
                    # Parse signals before and after adjustment
                    adjusted_signal = analyst_response.get("adjusted_signal", {})
                    
                    # Handle two possible signal formats
                    if isinstance(adjusted_signal, dict):
                        # Format 1: {ticker: {signal: ..., confidence: ...}}
                        if 'ticker_signals' in adjusted_signal:
                            # Format 2: {ticker_signals: [{ticker: ..., signal: ..., confidence: ...}]}
                            adjustment_details = []
                            for ticker_signal in adjusted_signal.get('ticker_signals', []):
                                ticker = ticker_signal.get('ticker', 'N/A')
                                new_signal = ticker_signal.get('signal', 'N/A')
                                new_confidence = ticker_signal.get('confidence', 'N/A')
                                
                                # Get original signal
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
                                    f"I adjusted the signal:\n" + "\n".join(adjustment_details),
                                    role_key=analyst_id
                                )
                            else:
                                streamer.print("agent", "I adjusted the signal", role_key=analyst_id)
                        else:
                            # Simple ticker: {signal, confidence} format
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
                                    f"I adjusted the signal:\n" + "\n".join(adjustment_details),
                                    role_key=analyst_id
                                )
                            else:
                                streamer.print("agent", "I adjusted the signal", role_key=analyst_id)
                    else:
                        streamer.print("agent", "I adjusted the signal", role_key=analyst_id)
                
                # # Record signal adjustment to memory
                # if analyst_memory and communication_id:
                #     analyst_memory.record_signal_adjustment(
                #         communication_id, 
                #         original_signal, 
                #         current_analyst_signal,
                #         f"Adjustment after private chat discussion on {topic}"
                #     )
            
            # Manager response (if not last round)
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
                
                # Output manager response to frontend
                if streamer:
                    max_display_length = 300
                    manager_display = manager_response if len(manager_response) <= max_display_length else manager_response[:max_display_length] + "..."
                    streamer.print("agent", manager_display, role_key=manager_id)
                
                # # Record manager response to memory
                # if analyst_memory and communication_id:
                #     analyst_memory.add_communication_message(
                #         communication_id, manager_id, manager_response
                #     )
        
        # pdb.set_trace()
        print("Private chat ended")
        
        # Output private chat end to frontend
        if streamer:
            streamer.print("system", f"Private chat ended, conducted {max_rounds} rounds of conversation, {adjustments_made_counter} signal adjustments")
        
        memory_format = self._convert_private_chat_to_memory_format(
            conversation_history, manager_id, analyst_id, topic, chat_id
        )

        # Store conversation history to each participant's memory
        from backend.memory import get_memory

        # Get base_dir from state (if exists)
        base_dir = state.get("metadata", {}).get("config_name", "default") if state else "default"
        
        try:
            memory = get_memory(base_dir)
            memory_content = "\n".join([msg.get("content", "") for msg in memory_format["messages"]])
            
            # Store to analyst's memory
            analyst_metadata = memory_format["metadata"].copy()
            analyst_metadata["stored_in"] = analyst_id
            memory.add(memory_content, analyst_id, analyst_metadata)
            print(f"✅ Conversation history stored to {analyst_id}'s memory")
            
            # Also store to manager's memory
            manager_metadata = memory_format["metadata"].copy()
            manager_metadata["stored_in"] = manager_id
            memory.add(memory_content, manager_id, manager_metadata)
            print(f"✅ Conversation history stored to {manager_id}'s memory")
            
        except Exception as e:
            print(f"❌ Failed to store conversation history: {e}")
            import traceback
            traceback.print_exc()


      
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
        """Conduct meeting"""
        meeting_id = str(uuid.uuid4())
        print(f"Starting meeting: {meeting_id}")
        print(f"Topic: {topic}")
        print(f"Participants: {', '.join([manager_id] + analyst_ids)}")


        # Output meeting ID to frontend
        if streamer:
            streamer.print("conference_start", title=topic, conferenceId=meeting_id,
                           participants=[manager_id] + analyst_ids)
        
        # Record meeting start for each analyst
        # Get trading_date as analysis_date
        # Note: Communication logging functionality has been simplified, no longer records start_communication
        # If needed, can directly add memory via memory.add()
        
        # Initialize meeting info (only for logging)
        print(f"Meeting created successfully - ID: {meeting_id}")
        
        current_signals = analyst_signals.copy()
        meeting_transcript = []
        adjustments_made_counter = 0
        
        # Manager opening
        opening_message = f"Let's discuss {topic}. Please share your viewpoints and analysis results."
        meeting_transcript.append({
            "speaker": manager_id,
            "content": opening_message,
            "round": 1,
            "timestamp": datetime.now().isoformat()
        })
        
        # Output opening statement to frontend
        if streamer:
            streamer.print("agent", f"[Opening] {opening_message}", role_key=manager_id)
        
        max_chars = self._get_max_chars(state)
        for round_num in range(max_rounds):
            print(f"\nMeeting round {round_num + 1} statements:")
            
            # Output round to frontend
            if streamer:
                streamer.print("system", f"--- Round {round_num + 1} statements ---")
            
            # Debug: print current meeting transcript status
            if round_num > 0:
                print(f"Current meeting transcript entries: {len(meeting_transcript)}")
                # if meeting_transcript:
                #     print(f"Last entry: {meeting_transcript[-1]}")
            
            # Each analyst speaks
            for analyst_id in analyst_ids:
                analyst_response = self._get_analyst_meeting_response(
                    analyst_id, topic, meeting_transcript, 
                    current_signals.get(analyst_id, {}), 
                    current_signals, state, round_num + 1, streamer=streamer
                )
                # # Truncate analyst statement
                # if isinstance(analyst_response, dict) and "response" in analyst_response:
                #     analyst_response["response"] = self._truncate_text(analyst_response["response"], max_chars)
                
                meeting_transcript.append({
                    "speaker": analyst_id,
                    "content": analyst_response["response"],
                    "round": round_num + 1,
                    "timestamp": datetime.now().isoformat()
                })

                # print(f"{analyst_id}: {analyst_response}")
                
                # Output analyst statement to frontend
                if streamer:
                    response_text = analyst_response.get("response", "")
                    # Limit output length to avoid too long
                    max_display_length = 300
                    if len(response_text) > max_display_length:
                        response_text = response_text[:max_display_length] + "..."
                    streamer.print("agent", response_text, role_key=analyst_id)

                # Record statement to analyst memory
                # analyst_memory = memory_manager.get_analyst_memory(analyst_id)
                # if analyst_memory and analyst_id in communication_ids:
                #     analyst_memory.add_communication_message(
                #         communication_ids[analyst_id], analyst_id, analyst_response['response']
                #     )
                
                # Check signal adjustment
                if analyst_response.get("signal_adjustment") and analyst_response.get("adjusted_signal"):
                    original_signal = current_signals[analyst_id]
                    current_signals[analyst_id] = analyst_response["adjusted_signal"]
                    print(f"{analyst_id} adjusted signal")
                    adjustments_made_counter += 1
                    
                    # Output signal adjustment to frontend
                    if streamer:
                        # Parse signals before and after adjustment
                        adjusted_signal = analyst_response.get("adjusted_signal", {})
                        
                        # Handle two possible signal formats
                        if isinstance(adjusted_signal, dict):
                            # Format 1: {ticker: {signal: ..., confidence: ...}}
                            if 'ticker_signals' in adjusted_signal:
                                # Format 2: {ticker_signals: [{ticker: ..., signal: ..., confidence: ...}]}
                                adjustment_details = []
                                for ticker_signal in adjusted_signal.get('ticker_signals', []):
                                    ticker = ticker_signal.get('ticker', 'N/A')
                                    new_signal = ticker_signal.get('signal', 'N/A')
                                    new_confidence = ticker_signal.get('confidence', 'N/A')
                                    
                                    # Get original signal
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
                                        f"I adjusted the signal:\n" + "\n".join(adjustment_details),
                                        role_key=analyst_id
                                    )
                                else:
                                    streamer.print("agent", "I adjusted the signal", role_key=analyst_id)
                            else:
                                # Simple ticker: {signal, confidence} format
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
                                        f"I adjusted the signal:\n" + "\n".join(adjustment_details),
                                        role_key=analyst_id
                                    )
                                else:
                                    streamer.print("agent", "I adjusted the signal", role_key=analyst_id)
                        else:
                            streamer.print("agent", "I adjusted the signal", role_key=analyst_id)
                    
                    # Record signal adjustment to memory
                    # if analyst_memory and analyst_id in communication_ids:
                    #     analyst_memory.record_signal_adjustment(
                    #         communication_ids[analyst_id],
                    #         original_signal,
                    #         analyst_response["adjusted_signal"],
                    #         f"Adjustment after meeting discussion on {topic}"
                    #     )
            
            # Proceed to next round (round management automatically handled in meeting_transcript)
        
        # Manager summary
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
        
        print(f"Meeting summary: {summary}")
        
        # Output meeting summary to frontend
        if streamer:
            streamer.print("system", "--- Meeting Summary ---")
            # Limit summary length
            max_summary_length = 400
            summary_display = summary if len(summary) <= max_summary_length else summary[:max_summary_length] + "..."
            streamer.print("agent", f"[Summary] {summary_display}", role_key=manager_id)
        
        print("Meeting ended")
        streamer.print("conference_end",conference_id=meeting_id)
        
        # Save meeting transcript to each participant's memory
        try:
            base_dir = state.get("metadata", {}).get("config_name", "default")
            memory = get_memory(base_dir)
            
            # Build meeting transcript content
            memory_content = f"Meeting Transcript\nTopic: {topic}\nMeeting ID: {meeting_id}\n\n" + "\n".join([
                f"[Round {entry.get('round', 'N/A')}] {entry.get('speaker', '')}: {entry.get('content', '')}" 
                for entry in meeting_transcript
            ])
            
            # Build metadata (ensure all values are basic types)
            participants_str = ",".join([manager_id] + analyst_ids)
            metadata = {
                "meeting_id": meeting_id,
                "topic": topic,
                "total_rounds": max_rounds,
                "total_messages": len(meeting_transcript),
                "participants": participants_str,  # Convert to string
                "communication_type": "meeting",
                "manager_id": manager_id
            }
            
            # Save meeting transcript for each analyst
            for analyst_id in analyst_ids:
                analyst_metadata = metadata.copy()
                analyst_metadata["stored_in"] = analyst_id
                memory.add(memory_content, analyst_id, analyst_metadata)
                print(f"✅ Meeting transcript stored to {analyst_id}'s memory")
            
            # Also save to manager's memory
            manager_metadata = metadata.copy()
            manager_metadata["stored_in"] = manager_id
            memory.add(memory_content, manager_id, manager_metadata)
            print(f"✅ Meeting transcript stored to {manager_id}'s memory")
            
        except Exception as e:
            print(f"❌ Failed to store meeting transcript: {e}")
            import traceback
            traceback.print_exc()
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
        """Get analyst's response in private chat (two-stage memory retrieval)"""
        
        # ========== Stage 1: Let analyst generate memory query ⭐⭐⭐ ==========
        relevant_memories = ""
        
        try:
            # Get base_dir (from state or use default)
            base_dir = state.get("metadata", {}).get("config_name", "default")
            print(f"\n{'='*60}")
            print(f"🔍 [chat_tools] Starting memory retrieval")
            print(f"   analyst_id: {analyst_id}")
            print(f"   base_dir: {base_dir}")
            
            memory = get_memory(base_dir)
            print(f"   memory instance: {type(memory).__name__}")
            
            tickers = state.get("data", {}).get("tickers", [])
            
            # 1. Generate memory query
            memory_query = self._generate_memory_query_for_chat(
                analyst_id, topic, conversation_history, tickers, state
            )
            print(f"   memory_query: {memory_query[:100]}..." if memory_query else "   memory_query: None")
            
            # 2. Use generated query to retrieve relevant memories
            if memory_query:
                try:
                    # Broadcast memory search operation
                    if streamer:
                        streamer.print(
                            "memory",
                            f"Searching memory: {memory_query[:60]}...",
                            agent_id=analyst_id,
                            operation_type="search"
                        )
                    
                    print(f"   Calling memory.search()...")
                    search_results = memory.search(
                        query=memory_query,
                        user_id=analyst_id,
                        top_k=1
                    )
                    print(f"   Search results count: {len(search_results) if search_results else 0}")
                    
                    # search_results is a list: [{'id': ..., 'content': ..., 'metadata': ...}, ...]
                    if search_results:
                        relevant_memories = "\n".join([
                            f"- {mem.get('content', '')}" 
                            for mem in search_results
                        ])
                        print(f"   ✅ {analyst_id} retrieved {len(search_results)} relevant memories")
                        print(f"{'='*60}\n")
                        
                        # Broadcast search success
                        if streamer:
                            streamer.print(
                                "memory",
                                f"Found {len(search_results)} relevant memories",
                                agent_id=analyst_id,
                                operation_type="search_success"
                            )
                        # print(relevant_memories)
                    else:
                        print(f"   ⚠️ {analyst_id} did not retrieve relevant memories")
                        print(f"{'='*60}\n")
                        if streamer:
                            streamer.print(
                                "memory",
                                "No relevant memories found",
                                agent_id=analyst_id,
                                operation_type="search_empty"
                            )
                except Exception as e:
                    print(f"   ❌ {analyst_id} memory retrieval failed: {e}")
                    print(f"{'='*60}\n")
                    import traceback
                    traceback.print_exc()
                    relevant_memories = ""
                    if streamer:
                        streamer.print(
                            "memory",
                            f"Memory retrieval failed: {str(e)[:50]}",
                            agent_id=analyst_id,
                            operation_type="search_error"
                        )
        except Exception as e:
            print(f"   ❌ {analyst_id} memory system error: {e}")
            print(f"{'='*60}\n")
            import traceback
            traceback.print_exc()
            relevant_memories = ""
        
        # ========== Stage 2: Generate response based on retrieved memories ⭐⭐⭐ ==========
        prompt_data = {
            "analyst_id": analyst_id,
            "relevant_memories": relevant_memories if relevant_memories else "No relevant past memories found for this topic.",
            "current_signal": json.dumps(current_signal, ensure_ascii=False),
            "topic": topic,
            "conversation_history": self._format_conversation_history(conversation_history),
            "max_chars": self._get_max_chars(state)
        }
        
        system_prompt = self.prompt_loader.load_prompt("communication", "analyst_chat_system", variables=prompt_data)
        human_prompt = self.prompt_loader.load_prompt("communication", "analyst_chat_human", variables=prompt_data)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": human_prompt}
        ]
        
        # Get LLM model (enable JSON mode)
        llm = self._get_llm_model(state, agent_id=analyst_id, use_json_mode=True)
        
        # Call model (using AgentScope method)
        response = llm(
            messages=messages,
            temperature=0.7,
            response_format={"type": "json_object"} if llm._use_json_mode else None
        )
        
        # Use more robust JSON parsing method
        try:
            # First try direct parsing
            return json.loads(response["content"])
        except json.JSONDecodeError as e:
            print(f"Warning: Analyst chat response JSON parsing failed: {str(e)}")
            print(f"Response content: {response['content'][:200]}...")
            
            # Use fallback parsing method
            parsed_response = self._extract_and_clean_json(response["content"])
            if parsed_response:
                print("Successfully parsed analyst chat response JSON using fallback method")
                return parsed_response
            else:
                print("Error: All analyst chat response JSON parsing methods failed")
                # Return default response
                return {
                    "response": "Parsing response failed, using default response",
                    "signal_adjustment": False
                }
    
    def _convert_transcript_to_memory_format(self, meeting_transcript: List[Dict], 
                                        meeting_id: str, topic: str, 
                                        total_rounds: int) -> Dict[str, Any]:
        """
        Convert meeting_transcript to format suitable for memory system
        
        Args:
            meeting_transcript: Raw meeting transcript
            meeting_id: Meeting ID  
            topic: Meeting topic
            total_rounds: Total rounds
            
        Returns:
            Converted format, containing messages and metadata
        """
        messages = []
        
        # Convert each statement to user role message format
        for entry in meeting_transcript:
            speaker = entry["speaker"]
            content = entry["content"]
            
            # Format content: speaker name + statement content
            formatted_content = f"{speaker}: {content}"
            
            # All statements stored as user role for unified management
            message = {
                "role": "user",
                "content": formatted_content
            }
            
            messages.append(message)
        
        # Build metadata
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
        Convert private chat conversation history to format suitable for memory system
        
        Args:
            conversation_history: Conversation history
            manager_id: Manager ID
            analyst_id: Analyst ID
            topic: Conversation topic
            chat_id: Chat ID
            
        Returns:
            Converted format, containing messages and metadata
        """
        messages = []
        
        # Add initial message (manager opening)
        initial_message = f"Regarding {topic}, I would like to discuss your analysis results with you."
        messages.append({
            "role": "user",
            "content": f"{manager_id}: {initial_message}"
        })
        
        # Convert each conversation to user role message format
        for entry in conversation_history:
            speaker = entry["speaker"]
            content = entry["content"]
            
            # Format content: speaker name + statement content
            formatted_content = f"{speaker}: {content}"
            
            # All statements stored as user role for unified management
            message = {
                "role": "user",
                "content": formatted_content
            }
            
            messages.append(message)
        
        # Build metadata (Note: vector database only supports str, int, float, bool, None types)
        metadata = {
            "chat_id": chat_id,
            "topic": topic,
            "total_rounds": len([entry for entry in conversation_history if entry["speaker"] == analyst_id]),
            "total_messages": len(conversation_history) + 1,  # +1 for initial message
            "participants": f"{manager_id},{analyst_id}",  # Convert to string
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
        """Get manager's response in private chat"""
        
        prompt_data = {
            "conversation_history": self._format_conversation_history(conversation_history),
            "current_signal": json.dumps(current_signal, ensure_ascii=False),
            "max_chars": self._get_max_chars(state)
        }
        
        system_prompt = self.prompt_loader.load_prompt("communication", "manager_chat_system", variables=prompt_data)
        human_prompt = self.prompt_loader.load_prompt("communication", "manager_chat_human", variables=prompt_data)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": human_prompt}
        ]
        
        # Get LLM model
        llm = self._get_llm_model(state, agent_id="portfolio_manager")
        
        # Call model (using AgentScope method)
        response = llm(messages=messages, temperature=0.7)
        return response["content"]
    
    def _get_analyst_meeting_response(self, analyst_id: str, topic: str,
                                    meeting_transcript: List[Dict],
                                    current_signal: Dict[str, Any],
                                    all_signals: Dict[str, Any],
                                    state, round_num: int, streamer=None) -> Dict[str, Any]:
        """Get analyst's statement in meeting (two-stage memory retrieval)"""
        
        # ========== Stage 1: Let analyst generate memory query ⭐⭐⭐ ==========
        relevant_memories = ""
        
        try:
            # Get base_dir (from state or use default)
            base_dir = state.get("metadata", {}).get("config_name", "default")
            memory = get_memory(base_dir)
            
            tickers = state.get("data", {}).get("tickers", [])
            
            # 1. Generate memory query
            memory_query = self._generate_memory_query_for_meeting(
                analyst_id, topic, meeting_transcript, tickers, state
            )
            
            # 2. Use generated query to retrieve relevant memories
            if memory_query:
                try:
                    # Broadcast memory search operation
                    if streamer:
                        streamer.print(
                            "memory",
                            f"Searching memory: {memory_query}...",
                            agent_id=analyst_id,
                            operation_type="search"
                        )
                    
                    search_results = memory.search(
                        query=memory_query,
                        user_id=analyst_id,
                        top_k=1
                    )
                    
                    # search_results is a list: [{'id': ..., 'content': ..., 'metadata': ...}, ...]
                    if search_results:
                        relevant_memories = "\n".join([
                            f"- {mem.get('content', '')}" 
                            for mem in search_results
                        ])
                        print(f"✅ {analyst_id} retrieved {len(search_results)} relevant memories in meeting")
                        print(relevant_memories)
                        
                        # Broadcast search success
                        if streamer:
                            streamer.print(
                                "memory",
                                f"Found {len(search_results)} relevant memories",
                                agent_id=analyst_id,
                                operation_type="search_success"
                            )
                    else:
                        print(f"⚠️ {analyst_id} did not retrieve relevant memories in meeting")
                        if streamer:
                            streamer.print(
                                "memory",
                                "No relevant memories found",
                                agent_id=analyst_id,
                                operation_type="search_empty"
                            )
                except Exception as e:
                    print(f"⚠️ {analyst_id} meeting memory retrieval failed: {e}")
                    relevant_memories = ""
                    if streamer:
                        streamer.print(
                            "memory",
                            f"Memory retrieval failed: {str(e)[:50]}",
                            agent_id=analyst_id,
                            operation_type="search_error"
                        )
        except Exception as e:
            print(f"⚠️ {analyst_id} memory system error: {e}")
            relevant_memories = ""
        
        # ========== Stage 2: Generate statement based on retrieved memories ⭐⭐⭐ ==========
        prompt_data = {
            "analyst_id": analyst_id,
            "relevant_memories": relevant_memories if relevant_memories else "No relevant past memories found for this topic.",
            "round_num": round_num,
            "current_signal": json.dumps(current_signal, ensure_ascii=False),
            "topic": topic,
            "meeting_transcript": self._format_meeting_transcript(meeting_transcript),
            "other_signals": json.dumps({k: v for k, v in all_signals.items() if k != analyst_id}, ensure_ascii=False, indent=2),
            "max_chars": self._get_max_chars(state)
        }
        
        system_prompt = self.prompt_loader.load_prompt("communication", "analyst_meeting_system", variables=prompt_data)
        human_prompt = self.prompt_loader.load_prompt("communication", "analyst_meeting_human", variables=prompt_data)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": human_prompt}
        ]
        # Get LLM model (enable JSON mode)
        llm = self._get_llm_model(state, agent_id=analyst_id, use_json_mode=True)
        
        # Call model (using AgentScope method)
        response = llm(
            messages=messages,
            temperature=0.7,
            response_format={"type": "json_object"} if llm._use_json_mode else None
        )
        
        # Use more robust JSON parsing method
        try:
            # First try direct parsing
            return json.loads(response["content"])
        except json.JSONDecodeError as e:
            print(f"Warning: Analyst meeting response JSON parsing failed: {str(e)}")
            print(f"Response content: {response['content'][:200]}...")
            
            # Use fallback parsing method
            parsed_response = self._extract_and_clean_json(response["content"])
            if parsed_response:
                print("Successfully parsed analyst meeting response JSON using fallback method")
                return parsed_response
            else:
                print("Error: All analyst meeting response JSON parsing methods failed")
                # Return default response
                return {
                    "response": "Parsing response failed, using default response",
                    "signal_adjustment": False
                }
    
    def _get_manager_meeting_summary(self, manager_id: str, 
                                   meeting_transcript: List[Dict],
                                   final_signals: Dict[str, Any], 
                                   state) -> str:
        """Get manager's meeting summary"""
        
        prompt_data = {
            "meeting_transcript": self._format_meeting_transcript(meeting_transcript),
            "final_signals": json.dumps(final_signals, ensure_ascii=False, indent=2),
            "max_chars": self._get_max_chars(state)
        }
        
        system_prompt = self.prompt_loader.load_prompt("communication", "manager_summary_system", variables=prompt_data)
        human_prompt = self.prompt_loader.load_prompt("communication", "manager_summary_human", variables=prompt_data)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": human_prompt}
        ]
        
        # Get LLM model
        llm = self._get_llm_model(state, agent_id="portfolio_manager")
        
        # Call model (using AgentScope method)
        response = llm(messages=messages, temperature=0.7)
        return response["content"]
    
    def _format_conversation_history(self, history: List[Dict]) -> str:
        """Format conversation history"""
        formatted = []
        for entry in history:
            formatted.append(f"{entry['speaker']}: {entry['content']}")
        return "\n".join(formatted)
    
    def _format_meeting_transcript(self, transcript: List[Dict]) -> str:
        """Format meeting transcript"""
        formatted = []
        for entry in transcript:
            round_info = f"Round {entry['round']}" if isinstance(entry['round'], int) else entry['round']
            formatted.append(f"[{round_info}] {entry['speaker']}: {entry['content']}")
        return "\n".join(formatted)
    
    def _generate_memory_query_for_chat(self, analyst_id: str, topic: str, 
                                       conversation_history: List[Dict],
                                       tickers: List[str], state) -> str:
        """
        Stage 1: Let analyst generate memory query based on private chat topic and context
        
        Args:
            analyst_id: Analyst ID
            topic: Private chat topic
            conversation_history: Conversation history
            tickers: Stock ticker list
            state: System state
            
        Returns:
            Memory query string
        """
        prompt_data = {
            "analyst_id": analyst_id,
            "topic": topic,
            "tickers": ", ".join(tickers),
            "conversation_history": self._format_conversation_history(conversation_history[-3:]) if conversation_history else "No previous conversation"
        }
        
        system_prompt = self.prompt_loader.load_prompt("communication", "memory_query_chat_system", variables=prompt_data)
        human_prompt = self.prompt_loader.load_prompt("communication", "memory_query_chat_human", variables=prompt_data)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": human_prompt}
        ]
        
        try:
            llm = self._get_llm_model(state, agent_id=analyst_id)
            response = llm(messages=messages, temperature=0.7)
            query = response["content"].strip()
            print(f"📝 {analyst_id} generated memory query: {query}")
            return query
        except Exception as e:
            print(f"⚠️ {analyst_id} failed to generate memory query: {e}")
            # Return default query
            return f"{topic} {' '.join(tickers)} analysis experience"
    
    def _generate_memory_query_for_meeting(self, analyst_id: str, topic: str,
                                          meeting_transcript: List[Dict],
                                          tickers: List[str], state) -> str:
        """
        Stage 1: Let analyst generate memory query based on meeting topic and context
        
        Args:
            analyst_id: Analyst ID
            topic: Meeting topic
            meeting_transcript: Meeting transcript
            tickers: Stock ticker list
            state: System state
            
        Returns:
            Memory query string
        """
        prompt_data = {
            "analyst_id": analyst_id,
            "topic": topic,
            "tickers": ", ".join(tickers),
            "meeting_transcript": self._format_meeting_transcript(meeting_transcript[-5:]) if meeting_transcript else "Meeting just started"
        }
        
        system_prompt = self.prompt_loader.load_prompt("communication", "memory_query_meeting_system", variables=prompt_data)
        human_prompt = self.prompt_loader.load_prompt("communication", "memory_query_meeting_human", variables=prompt_data)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": human_prompt}
        ]
        
        try:
            llm = self._get_llm_model(state, agent_id=analyst_id)
            response = llm(messages=messages, temperature=0.7)
            query = response["content"].strip()
            print(f"📝 {analyst_id} generated memory query in meeting: {query}")
            return query
        except Exception as e:
            print(f"⚠️ {analyst_id} failed to generate meeting memory query: {e}")
            # Return default query
            return f"{topic} {' '.join(tickers)} analysis experience"
    
    def _extract_and_clean_json(self, content: str) -> Optional[Dict[str, Any]]:
        """Extract and clean JSON from response"""
        try:
            # Remove markdown code blocks
            content = re.sub(r'```json\s*\n?', '', content)
            content = re.sub(r'\n?\s*```', '', content)
            
            # Find JSON section
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                
                # Remove comments
                json_str = re.sub(r'//.*', '', json_str)
                
                # Try parsing
                return json.loads(json_str)
            
            # If complete JSON not found, try extracting key fields
            response_match = re.search(r'"response"\s*:\s*"([^"]*)"', content)
            adjustment_match = re.search(r'"signal_adjustment"\s*:\s*(true|false)', content)
            
            if response_match:
                return {
                    "response": response_match.group(1),
                    "signal_adjustment": adjustment_match.group(1) == 'true' if adjustment_match else False
                }
                
        except Exception as e:
            print(f"Error in JSON extraction process: {str(e)}")
            
        return None


# Create global instance
communication_manager = CommunicationManager()
