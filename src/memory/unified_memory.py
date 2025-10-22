#!/usr/bin/env python3
"""
统一记忆系统
整合分析师记忆、通信记忆、通知系统的完整实现
"""

from datetime import datetime
from typing import Dict, List, Any, Optional
import pdb
import os
from .mem0_core import (
    get_mem0_integration, 
    AnalysisSession, 
    CommunicationRecord, 
    Notification
)

# 全局调试开关
MEMORY_DEBUG = os.getenv("MEMORY_DEBUG", "false").lower() in ("true", "1", "yes")


def debug_print(message):
    """根据调试开关决定是否打印消息"""
    if MEMORY_DEBUG:
        print(message)


def safe_memory_add(memory_instance, messages, user_id, metadata, infer=False, operation_name="记忆操作", save_memory=True):
    """
    安全的记忆添加包装器，带调试信息
    
    Args:
        memory_instance: 记忆实例（可能是 Mem0Adapter 或 ReMeAdapter）
        messages: 消息内容
        user_id: 用户ID
        metadata: 元数据
        infer: 是否推断（仅 Mem0 框架使用）
        operation_name: 操作名称
        save_memory: 是否真的保存记忆到存储系统（默认True）。False时只打印调试信息，不实际保存
    """
    if not save_memory:
        debug_print(f"[调试模式] 跳过记忆保存 - {operation_name}: {messages}")
        return {"status": "skipped", "reason": "save_memory=False"}
    
    try:
        # 检查记忆实例类型，判断是否为 ReMe 框架
        framework_name = getattr(memory_instance, 'get_framework_name', lambda: 'unknown')()
        
        # 根据框架类型调用不同的 add 方法
        if framework_name == 'reme':
            # ReMe 框架不需要 infer 参数
            result = memory_instance.add(
                messages=messages,
                user_id=user_id,
                metadata=sanitize_metadata(metadata)
            )
        else:
            # Mem0 框架或其他框架使用 infer 参数
            result = memory_instance.add(
                messages=messages,
                user_id=user_id,
                metadata=sanitize_metadata(metadata),
                infer=infer
            )
        
        debug_print(f"记忆添加结果 - {operation_name}: {result}")
        return result
    except Exception as e:
        print(f"警告：{operation_name}失败: {str(e)}")
        return None


def sanitize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    清理metadata，确保所有值都是mem0支持的基本数据类型
    mem0只支持: str, int, float, bool, SparseVector, None
    """
    sanitized = {}
    for key, value in metadata.items():
        if value is None:
            sanitized[key] = None
        elif isinstance(value, (str, int, float, bool)):
            sanitized[key] = value
        elif isinstance(value, list):
            # 将列表转换为逗号分隔的字符串
            sanitized[key] = ', '.join(str(item) for item in value)
        elif isinstance(value, dict):
            # 将字典转换为简化的字符串表示
            sanitized[key] = str(value)  
        else:
            # 其他类型转换为字符串
            sanitized[key] = str(value) 
    return sanitized


# ================================
# 分析师记忆系统
# ================================

class Mem0AnalystMemory:
    """基于Mem0的分析师记忆系统"""
    
    def __init__(self, analyst_id: str, analyst_name: str, save_memory: bool = True):
        self.analyst_id = analyst_id
        self.analyst_name = analyst_name
        self.creation_time = datetime.now()
        self.save_memory = save_memory  # 控制是否真的保存记忆
        

        # 获取共享的mem0实例（所有分析师共用一个实例，通过user_id区分）
        self.memory = get_mem0_integration().get_memory_instance("shared_analysts")
        
        # 本地会话管理（用于当前会话的临时存储）
        self.current_sessions: Dict[str, AnalysisSession] = {}
        self.current_communications: Dict[str, CommunicationRecord] = {}
        
        # 初始化基本信息到mem0
        self._initialize_analyst_profile()
    
    def _initialize_analyst_profile(self):
        """初始化分析师档案到mem0"""
        profile_message = f"""
        我是{self.analyst_name}（ID: {self.analyst_id}），专业的投资分析师。
        创建时间：{self.creation_time.strftime('%Y-%m-%d %H:%M:%S')}
        我的职责是进行专业的投资分析，与其他分析师协作，并根据市场情况调整投资建议。
        """
        
        safe_memory_add(
            self.memory,
            [{"role": "assistant", "content": profile_message}],
            self.analyst_id,
            {
                "type": "profile",
                "analyst_name": self.analyst_name,
                "creation_time": self.creation_time.isoformat()
            },
            infer=False,
            operation_name="分析师档案初始化",
            save_memory=self.save_memory
        )
        
    
    def start_analysis_session(self, session_type: str, tickers: List[str], 
                             context: Dict[str, Any] = None, analysis_date: str = None) -> str:
        """开始新的分析会话"""
        session = AnalysisSession(
            session_type=session_type,
            tickers=tickers,
            context=context or {}
        )
        
        self.current_sessions[session.session_id] = session
        
        # 记录到mem0
        session_start_message = f"""
        开始{session_type}分析会话
        股票代码: {', '.join(tickers)}
        会话ID: {session.session_id}
        开始时间: {session.start_time.strftime('%Y-%m-%d %H:%M:%S')}
        上下文: {context}
        """
        if analysis_date:
            session_start_message += f"\n        分析日期: {analysis_date}"
        
        messages = [
        {"role": "assistant", "content": session_start_message}
        ]   
        
        metadata = {
            "type": "session_start",
            "session_id": session.session_id,
            "session_type": session_type,
            "tickers": tickers,
            "timestamp": session.start_time.isoformat()
        }
        if analysis_date:
            metadata["analysis_date"] = analysis_date
        
        safe_memory_add(
            self.memory,
            messages,
            self.analyst_id,
            metadata,
            infer=False,
            operation_name="分析会话开始",
            save_memory=self.save_memory
        )
        
        return session.session_id
    
    def add_analysis_message(self, session_id: str, role: str, content: str, 
                           metadata: Dict[str, Any] = None):
        """添加分析消息到会话"""
        if session_id in self.current_sessions:
            message = {
                "role": role,
                "content": content,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata or {}
            }
            self.current_sessions[session_id].messages.append(message)
            
            # 记录到mem0
            safe_memory_add(
                self.memory,
                [{"role": role, "content": content}],
                self.analyst_id,
                {
                    "type": "analysis_message",
                    "session_id": session_id,
                    "timestamp": message["timestamp"],
                    **(metadata or {})
                },
                infer=False,
                operation_name="分析消息记录",
                save_memory=self.save_memory
            )
    
    def complete_analysis_session(self, session_id: str, final_result: Dict[str, Any], analysis_date: str = None):
        """完成分析会话"""
        if session_id in self.current_sessions:
            session = self.current_sessions[session_id]
            session.final_result = final_result
            session.end_time = datetime.now()
            session.status = "completed"
            
            # 从 final_result 中提取 analysis_date (如果有)
            if not analysis_date and isinstance(final_result, dict):
                analysis_date = final_result.get('metadata', {}).get('analysis_date')
            
            # 记录到mem0
            completion_message = f"""
            完成分析会话
            会话ID: {session_id}
            分析结果: {final_result}
            结束时间: {session.end_time.strftime('%Y-%m-%d %H:%M:%S')}
            总消息数: {len(session.messages)}
            """
            if analysis_date:
                completion_message += f"\n            分析日期: {analysis_date}"
            
            metadata = {
                "type": "session_complete",
                "session_id": session_id,
                "final_result": final_result,
                "timestamp": session.end_time.isoformat()
            }
            if analysis_date:
                metadata["analysis_date"] = analysis_date
            
            safe_memory_add(
                self.memory,
                [{"role": "assistant", "content": completion_message}],
                self.analyst_id,
                metadata,
                infer=False,
                operation_name="分析会话完成",
                save_memory=self.save_memory
            )
    
    def start_communication(self, communication_type: str, participants: List[str], 
                          topic: str, analysis_date: str = None) -> str:
        """开始新的通信"""
        comm = CommunicationRecord(
            communication_type=communication_type,
            participants=participants,
            topic=topic
        )
        
        self.current_communications[comm.communication_id] = comm
        
        # 记录到mem0
        comm_start_message = f"""
        开始{communication_type}通信
        参与者: {', '.join(participants)}
        话题: {topic}
        通信ID: {comm.communication_id}
        开始时间: {comm.start_time.strftime('%Y-%m-%d %H:%M:%S')}
        """
        if analysis_date:
            comm_start_message += f"\n        分析日期: {analysis_date}"
        
        metadata = {
            "type": "communication_start",
            "communication_id": comm.communication_id,
            "communication_type": communication_type,
            "participants": participants,
            "topic": topic,
            "timestamp": comm.start_time.isoformat()
        }
        if analysis_date:
            metadata["analysis_date"] = analysis_date
        
        safe_memory_add(
            self.memory,
            [{"role": "assistant", "content": comm_start_message}],
            self.analyst_id,
            metadata,
            infer=False,
            operation_name="通信开始",
            save_memory=self.save_memory
        )
        
        return comm.communication_id
    
    def add_communication_message(self, communication_id: str, speaker: str, 
                                content: str, metadata: Dict[str, Any] = None):
        """添加通信消息"""
        if communication_id in self.current_communications:
            message = {
                "speaker": speaker,
                "content": content,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata or {}
            }
            self.current_communications[communication_id].messages.append(message)
            
            # 记录到mem0
            safe_memory_add(
                self.memory,
                [{"role": "user" if speaker == self.analyst_id else "assistant", "content": f"[{speaker}]: {content}"}],
                self.analyst_id,
                {
                    "type": "communication_message",
                    "communication_id": communication_id,
                    "speaker": speaker,
                    "timestamp": message["timestamp"],
                    **(metadata or {})
                },
                infer=False,
                operation_name="通信消息记录",
                save_memory=self.save_memory
            )
    
    def record_signal_adjustment(self, communication_id: str, original_signal: Dict[str, Any], 
                               adjusted_signal: Dict[str, Any], reasoning: str):
        """记录信号调整"""
        if communication_id in self.current_communications:
            adjustment = {
                "original_signal": original_signal,
                "adjusted_signal": adjusted_signal,
                "reasoning": reasoning,
                "timestamp": datetime.now().isoformat()
            }
            self.current_communications[communication_id].signal_adjustments.append(adjustment)
            
            # 记录到mem0
            adjustment_message = f"""
            信号调整记录
            通信ID: {communication_id}
            原信号: {self._extract_signal_summary(original_signal)}
            调整后信号: {self._extract_signal_summary(adjusted_signal)}
            调整理由: {reasoning}
            调整时间: {adjustment['timestamp']}
            """
            
            safe_memory_add(
                self.memory,
                [{"role": "assistant", "content": adjustment_message}],
                self.analyst_id,
                {
                    "type": "signal_adjustment",
                    "communication_id": communication_id,
                    "original_signal": original_signal,
                    "adjusted_signal": adjusted_signal,
                    "reasoning": reasoning,
                    "timestamp": adjustment["timestamp"]
                },
                infer=False,
                operation_name="信号调整记录",
                save_memory=self.save_memory
            )
    
    def complete_communication(self, communication_id: str):
        """完成通信"""
        if communication_id in self.current_communications:
            comm = self.current_communications[communication_id]
            comm.end_time = datetime.now()
            comm.status = "completed"
            
            # 记录到mem0
            completion_message = f"""
            完成通信
            通信ID: {communication_id}
            结束时间: {comm.end_time.strftime('%Y-%m-%d %H:%M:%S')}
            总消息数: {len(comm.messages)}
            信号调整次数: {len(comm.signal_adjustments)}
            """
            
            safe_memory_add(
                self.memory,
                [{"role": "assistant", "content": completion_message}],
                self.analyst_id,
                {
                    "type": "communication_complete",
                    "communication_id": communication_id,
                    "timestamp": comm.end_time.isoformat()
                },
                infer=False,
                operation_name="通信完成",
                save_memory=self.save_memory
            )
    
    def get_relevant_memories(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """获取相关记忆"""
        try:
            memories = self.memory.search(
                query=query,
                user_id=self.analyst_id,
                limit=limit
            )
            return memories
        except Exception as e:
            print(f"警告：从mem0搜索记忆失败: {str(e)}")
            return []
    
    def get_full_context_for_communication(self, tickers: List[str] = None) -> str:
        """获取用于通信的完整上下文"""
        # 构建查询
        if tickers:
            query = f"关于{', '.join(tickers)}的分析和讨论"
        else:
            query = "最近的分析结果和讨论"
        
        # 从mem0获取相关记忆
        relevant_memories = self.get_relevant_memories(query, limit=15)
        
        context_parts = [f"=== {self.analyst_name} 的记忆上下文 ==="]
        
        if relevant_memories:
            context_parts.append("\n=== 相关记忆 ===")
            # 安全地处理 relevant_memories，确保是可迭代的列表
            memory_list = list(relevant_memories) if relevant_memories else []
            for i, memory in enumerate(memory_list[:10], 1):
                if isinstance(memory, dict):
                    memory_text = memory.get('memory', '')
                    if len(memory_text) > 200:
                        memory_text = memory_text[:200] + "..."
                    context_parts.append(f"{i}. {memory_text}")
                else:
                    # 如果memory不是字典，跳过或转换为字符串
                    context_parts.append(f"{i}. {str(memory)[:200]}")
        else:
            context_parts.append("\n=== 暂无相关记忆 ===")
        
        return "\n".join(context_parts)
    
    # def get_analysis_summary(self) -> Dict[str, Any]:
    #     """获取分析总结"""
    #     # 从mem0获取最近的记忆
    #     recent_memories = self.get_relevant_memories("分析结果", limit=5)
        
    #     return {
    #         "analyst_id": self.analyst_id,
    #         "analyst_name": self.analyst_name,
    #         "creation_time": self.creation_time.isoformat(),
    #         "recent_memories_count": len(recent_memories),
    #         "current_sessions": len(self.current_sessions),
    #         "current_communications": len(self.current_communications)
    #     }
    
    def _extract_signal_summary(self, signal: Dict[str, Any]) -> str:
        """提取信号摘要"""
        if isinstance(signal, dict):
            # 尝试提取常见的信号字段
            if 'action' in signal:
                action = signal['action']
                confidence = signal.get('confidence', 'N/A')
                return f"{action} (置信度: {confidence})"
            elif 'recommendation' in signal:
                return signal['recommendation']
            elif 'signal' in signal:
                return str(signal['signal'])
            else:
                # 返回字典的简化表示
                return str(signal)[:50] + "..." if len(str(signal)) > 50 else str(signal)
        
        return "信号格式未知"
    
    def _format_signal_adjustment(self, original: Dict[str, Any], adjusted: Dict[str, Any]) -> str:
        """格式化信号调整"""
        orig_summary = self._extract_signal_summary(original)
        adj_summary = self._extract_signal_summary(adjusted)
        return f"从 [{orig_summary}] 调整为 [{adj_summary}]"
    
    # def export_memory(self) -> Dict[str, Any]:
    #     """导出记忆数据（兼容性方法）"""
    #     # 获取所有记忆
    #     all_memories = self.get_relevant_memories("", limit=100)
        
    #     return {
    #         "analyst_id": self.analyst_id,
    #         "analyst_name": self.analyst_name,
    #         "creation_time": self.creation_time.isoformat(),
    #         "mem0_memories": all_memories,
    #         "current_sessions": [session.model_dump() for session in self.current_sessions.values()],
    #         "current_communications": [comm.model_dump() for comm in self.current_communications.values()],
    #         "export_time": datetime.now().isoformat()
    #     }


class Mem0AnalystMemoryManager:
    """基于Mem0的分析师记忆管理器"""
    
    def __init__(self, save_memory: bool = True):
        self.analysts: Dict[str, Mem0AnalystMemory] = {}
        self.save_memory = save_memory
    
    def register_analyst(self, analyst_id: str, analyst_name: str):
        """注册分析师"""
        if analyst_id not in self.analysts:
            self.analysts[analyst_id] = Mem0AnalystMemory(analyst_id, analyst_name, save_memory=self.save_memory)
            status = "（调试模式）" if not self.save_memory else "（基于Mem0）"
            print(f"注册分析师记忆{status}: {analyst_name}")
    
    def get_analyst_memory(self, analyst_id: str) -> Optional[Mem0AnalystMemory]:
        """获取分析师记忆"""
        return self.analysts.get(analyst_id)
    
    def get_all_analysts_context(self, tickers: List[str] = None) -> Dict[str, str]:
        """获取所有分析师的上下文"""
        contexts = {}
        for analyst_id, memory in self.analysts.items():
            contexts[analyst_id] = memory.get_full_context_for_communication(tickers)
        return contexts
    
    # def export_all_memories(self) -> Dict[str, Any]:
    #     """导出所有记忆"""
    #     return {
    #         "export_time": datetime.now().isoformat(),
    #         "memory_system": "mem0",
    #         "analysts": {
    #             analyst_id: memory.export_memory() 
    #             for analyst_id, memory in self.analysts.items()
    #         }
    #     }
    
    def reset_analyst_memory(self, analyst_id: str, analyst_name: str = None):
        """重置分析师记忆"""
        if analyst_id in self.analysts:
            del self.analysts[analyst_id]
            
        # 只有在真实保存模式下才重置mem0实例
        if self.save_memory:
            get_mem0_integration().reset_user_memory(analyst_id)
        
        # 如果提供了名称，重新注册
        if analyst_name:
            self.register_analyst(analyst_id, analyst_name)


# ================================
# 通信和通知记忆系统
# ================================

class Mem0NotificationMemory:
    """基于Mem0的通知记忆系统"""
    
    def __init__(self, agent_id: str, save_memory: bool = True):
        self.agent_id = agent_id
        self.save_memory = save_memory
        # 使用共享实例，通过user_id区分不同agent的通知
        self.memory = get_mem0_integration().get_memory_instance("shared_analysts")
    
    def add_received_notification(self, notification: Notification, backtest_date: Optional[str] = None):
        """记录接收到的通知"""
        if not self.save_memory:
            debug_print(f"[调试模式] 跳过通知记录 - 接收通知: {notification.content}")
            return
            
        try:
            metadata = {
                "type": "received_notification",
                "notification_id": notification.id,
                "sender": notification.sender_agent,
                "urgency": notification.urgency,
                "category": notification.category,
                "timestamp": notification.timestamp.isoformat()
            }
            if backtest_date:
                metadata["backtest_date"] = backtest_date
            
            # 构建content，包含分析日期
            content = f"收到来自{notification.sender_agent}的通知: {notification.content}"
            if backtest_date:
                content += f"\n分析日期: {backtest_date}"

            self.memory.add(
                [{"role": "assistant", "content": content}],
                user_id=self.agent_id,
                metadata=sanitize_metadata(metadata),
                infer=False
            )
        except Exception as e:
            print(f"警告：记录接收通知到mem0失败: {str(e)}")
    
    def add_sent_notification(self, notification: Notification, backtest_date: Optional[str] = None):
        """记录发送的通知"""
        if not self.save_memory:
            debug_print(f"[调试模式] 跳过通知记录 - 发送通知: {notification.content}")
            return
            
        try:
            metadata = {
                "type": "sent_notification",
                "notification_id": notification.id,
                "urgency": notification.urgency,
                "category": notification.category,
                "timestamp": notification.timestamp.isoformat()
            }
            if backtest_date:
                metadata["backtest_date"] = backtest_date
            
            # 构建content，包含分析日期
            content = f"发送通知: {notification.content}"
            if backtest_date:
                content += f"\n分析日期: {backtest_date}"

            self.memory.add(
                [{"role": "user", "content": content}],
                user_id=self.agent_id,
                metadata=sanitize_metadata(metadata),
                infer=False
            )
        except Exception as e:
            print(f"警告：记录发送通知到mem0失败: {str(e)}")
    


class Mem0NotificationSystem:
    """基于Mem0的通知系统"""
    
    def __init__(self, save_memory: bool = True):
        self.agent_memories: Dict[str, Mem0NotificationMemory] = {}
        self.save_memory = save_memory
        # 全局通知也使用共享实例
        self.global_memory = get_mem0_integration().get_memory_instance("shared_analysts")
    
    def register_agent(self, agent_id: str):
        """注册agent"""
        if agent_id not in self.agent_memories:
            self.agent_memories[agent_id] = Mem0NotificationMemory(agent_id, save_memory=self.save_memory)
            status = "（调试模式）" if not self.save_memory else ""
            print(f"注册agent到Mem0通知系统{status}: {agent_id}")
    
    def send_notification(self, sender_agent: str, target_agent: str, content: str, 
                         urgency: str = "medium", category: str = "general",
                         backtest_date: Optional[str] = None) -> str:
        """发送通知给特定agent"""
        notification = Notification(
            sender_agent=sender_agent,
            content=content,
            urgency=urgency,
            category=category
        )
        
        # 记录到发送方的记忆
        if sender_agent in self.agent_memories:
            self.agent_memories[sender_agent].add_sent_notification(notification, backtest_date)
        
        # 记录到接收方的记忆
        if target_agent in self.agent_memories:
            self.agent_memories[target_agent].add_received_notification(notification, backtest_date)
        
        return notification.id
    
    def broadcast_notification(self, sender_agent: str, content: str, 
                             urgency: str = "medium", category: str = "general",
                             backtest_date: Optional[str] = None) -> str:
        """广播通知给所有agents"""
        notification = Notification(
            sender_agent=sender_agent,
            content=content,
            urgency=urgency,
            category=category
        )
        
        # 记录到全局通知记忆
        if not self.save_memory:
            debug_print(f"[调试模式] 跳过广播通知记录: {content}")
        else:
            try:
                metadata = {
                    "type": "broadcast_notification",
                    "notification_id": notification.id,
                    "sender": sender_agent,
                    "urgency": urgency,
                    "category": category,
                    "timestamp": notification.timestamp.isoformat()
                }
                if backtest_date:
                    metadata["backtest_date"] = backtest_date

                self.global_memory.add(
                    messages=[{"role": "user", "content": f"广播通知从{sender_agent}: {content}"}],
                    user_id="global_notification_system",
                    metadata=metadata
                )
            except Exception as e:
                print(f"警告：记录广播通知到mem0失败: {str(e)}")
        
        # 发送给所有注册的agents
        for agent_id in self.agent_memories:
            # if agent_id != sender_agent:  # 不发给自己
            self.agent_memories[agent_id].add_received_notification(notification, backtest_date)
        
        return notification.id
    
    # def get_agent_notifications(self, agent_id: str, hours: int = 24,
    #                            backtest_date: Optional[str] = None) -> List[Dict[str, Any]]:
    #     """获取特定agent的通知"""
    #     if agent_id in self.agent_memories:
    #         return self.agent_memories[agent_id].get_recent_notifications(hours, backtest_date)
    #     return []
    
    def get_agent_memory(self, agent_id: str) -> Optional[Mem0NotificationMemory]:
        """获取agent的通知记忆"""
        return self.agent_memories.get(agent_id)


class Mem0CommunicationMemory:
    """基于Mem0的通信记忆系统（私聊和会议）"""
    
    def __init__(self, save_memory: bool = True):
        self.save_memory = save_memory
        # 通信记忆使用共享实例，通过user_id区分
        self.communication_memory = get_mem0_integration().get_memory_instance("shared_analysts")
    
    def record_private_chat(self, participants: List[str], topic: str, 
                          messages: List[Dict[str, Any]], result: Dict[str, Any],
                          backtest_date: Optional[str] = None):
        """记录私聊"""
        chat_summary = f"""
        私聊记录：
        参与者：{', '.join(participants)}
        话题：{topic}
        消息数量：{len(messages)}
        结果：{result.get('adjustments_made', 0)}次信号调整
        时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        if backtest_date:
            chat_summary += f"        分析日期：{backtest_date}\n"
        
        # 详细对话内容
        conversation_details = "\n".join([
            f"[{msg['speaker']}]: {msg['content'][:200]}..."
            for msg in messages[:10]  # 最多记录10条消息
        ])
        
        full_message = f"{chat_summary}\n\n对话详情：\n{conversation_details}"
        
        if not self.save_memory:
            debug_print(f"[调试模式] 跳过私聊记录: {participants} - {topic}")
            return
            
        try:
            metadata = {
                "type": "private_chat",
                "participants": ', '.join(participants),
                "topic": topic,
                "message_count": len(messages),
                "adjustments_made": result.get('adjustments_made', 0),
                "timestamp": datetime.now().isoformat()
            }
            if backtest_date:
                metadata["backtest_date"] = backtest_date

            self.communication_memory.add(
                [{"role": "assistant", "content": full_message}],
                user_id="communication_system",
                metadata=metadata,
                infer=False
            )
            print(f"记录了私聊到Mem0: {participants}")
        except Exception as e:
            print(f"警告：记录私聊到mem0失败: {str(e)}")
    
    def record_meeting(self, meeting_id: str, host: str, participants: List[str],
                      topic: str, transcript: List[Dict[str, Any]], result: Dict[str, Any],
                      backtest_date: Optional[str] = None):
        """记录会议"""
        meeting_summary = f"""
        会议记录：
        会议ID：{meeting_id}
        主持人：{host}
        参与者：{', '.join(participants)}
        话题：{topic}
        发言数：{len(transcript)}
        结果：{result.get('adjustments_made', 0)}次信号调整
        时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        if backtest_date:
            meeting_summary += f"        分析日期：{backtest_date}\n"
        
        # 详细会议记录
        meeting_details = "\n".join([
            f"[{record['speaker']}]: {record['content'][:200]}..."
            for record in transcript[:15]  # 最多记录15条发言
        ])
        
        full_message = f"{meeting_summary}\n\n会议详情：\n{meeting_details}"
        
        if not self.save_memory:
            debug_print(f"[调试模式] 跳过会议记录: {meeting_id} - {topic}")
            return
            
        try:
            metadata = {
                "type": "meeting",
                "meeting_id": meeting_id,
                "host": host,
                "participants": ', '.join(participants),
                "topic": topic,
                "transcript_count": len(transcript),
                "adjustments_made": result.get('adjustments_made', 0),
                "timestamp": datetime.now().isoformat()
            }
            if backtest_date:
                metadata["backtest_date"] = backtest_date

            self.communication_memory.add(
                messages=[{"role": "system", "content": full_message}],
                user_id="communication_system",
                metadata=metadata
            )
            print(f"记录了会议到Mem0: {meeting_id}")
        except Exception as e:
            print(f"警告：记录会议到mem0失败: {str(e)}")
    


# ================================
# 统一记忆管理器
# ================================

class Mem0MemoryManager:
    """统一的Mem0记忆管理器"""
    
    def __init__(self, save_memory: bool = True):
        self.save_memory = save_memory
        self.analyst_memory_manager = Mem0AnalystMemoryManager(save_memory=save_memory)
        self.notification_system = Mem0NotificationSystem(save_memory=save_memory)
        self.communication_memory = Mem0CommunicationMemory(save_memory=save_memory)
        
        # 预定义的分析师ID和名称映射
        self.analyst_definitions = {
            'fundamentals_analyst': '基本面分析师',
            'technical_analyst': '技术分析师',
            'sentiment_analyst': '情绪分析师',
            'valuation_analyst': '估值分析师',
            'portfolio_manager': '投资组合经理',
            'risk_manager': '风险管理师'
        }
    
    def initialize_all_analysts(self):
        """初始化所有预定义的分析师"""
        for analyst_id, analyst_name in self.analyst_definitions.items():
            self.register_analyst(analyst_id, analyst_name)
    
    def register_analyst(self, analyst_id: str, analyst_name: str = None):
        """注册分析师到所有记忆系统"""
        if analyst_name is None:
            analyst_name = self.analyst_definitions.get(analyst_id, analyst_id)
        
        # 注册到分析师记忆系统
        self.analyst_memory_manager.register_analyst(analyst_id, analyst_name)
        
        # 注册到通知系统
        self.notification_system.register_agent(analyst_id)
    
    def get_analyst_memory(self, analyst_id: str) -> Optional[Mem0AnalystMemory]:
        """获取分析师记忆"""
        return self.analyst_memory_manager.get_analyst_memory(analyst_id)
    
    def send_notification(self, sender_agent: str, target_agent: str, content: str, 
                         urgency: str = "medium", category: str = "general",
                         backtest_date: Optional[str] = None) -> str:
        """发送通知"""
        return self.notification_system.send_notification(
            sender_agent, target_agent, content, urgency, category, backtest_date
        )
    
    def broadcast_notification(self, sender_agent: str, content: str, 
                             urgency: str = "medium", category: str = "general",
                             backtest_date: Optional[str] = None) -> str:
        """广播通知（支持回测日期 backtest_date）"""
        return self.notification_system.broadcast_notification(
            sender_agent, content, urgency, category, backtest_date
        )
    

    def get_all_analysts_context(self, tickers: List[str] = None) -> Dict[str, str]:
        """获取所有分析师的上下文"""
        return self.analyst_memory_manager.get_all_analysts_context(tickers)
    
    def search_memories(self, query: str, analyst_id, limit: int = 10) -> List[Dict[str, Any]]:
        """搜索记忆"""
        if analyst_id:
            # 搜索特定分析师的记忆
            memory = self.get_analyst_memory(analyst_id)
            if memory:
                return memory.get_relevant_memories(query, limit)
            return []
    def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        registered_analysts = list(self.analyst_memory_manager.analysts.keys())
        registered_notification_agents = list(self.notification_system.agent_memories.keys())
        
        return {
            "memory_system": "Mem0",
            "registered_analysts": registered_analysts,
            "registered_notification_agents": registered_notification_agents,
            "mem0_instances": get_mem0_integration().get_all_user_ids(),
            "status_time": datetime.now().isoformat()
        }
    
    # def export_all_data(self) -> Dict[str, Any]:
    #     """导出所有数据"""
    #     return {
    #         "export_time": datetime.now().isoformat(),
    #         "system_status": self.get_system_status(),
    #         "analyst_memories": self.analyst_memory_manager.export_all_memories(),
    #         "communication_history": self.search_memories("", limit=100)
    #     }
    
    def reset_analyst(self, analyst_id: str, analyst_name: str = None):
        """重置分析师"""
        self.analyst_memory_manager.reset_analyst_memory(analyst_id, analyst_name)
        
        # 重新注册到通知系统
        if analyst_name:
            self.notification_system.register_agent(analyst_id)


# ================================
# 全局实例
# ================================

# 延迟初始化全局实例，避免在模块导入时初始化
import os
default_save_memory = not (os.getenv("MEMORY_SAVE_DISABLED", "false").lower() in ("true", "1", "yes"))

# 全局实例变量
mem0_memory_manager = None
mem0_notification_system = None
mem0_communication_memory = None
unified_memory_manager = None

def _ensure_global_instances_initialized():
    """确保全局实例已初始化（延迟初始化）"""
    global mem0_memory_manager, mem0_notification_system, mem0_communication_memory, unified_memory_manager
    
    # 检查 mem0_integration 是否可用
    from src.memory.mem0_core import mem0_integration
    if mem0_integration is None:
        # 如果使用其他框架（如ReMe），不初始化Mem0相关实例
        import warnings
        warnings.warn(
            "Mem0Integration未初始化，无法创建Mem0全局实例。"
            "这是正常的，如果您使用的是其他记忆框架（如ReMe）。",
            RuntimeWarning
        )
        return
    
    if mem0_memory_manager is None:
        mem0_memory_manager = Mem0AnalystMemoryManager(save_memory=default_save_memory)
    
    if mem0_notification_system is None:
        mem0_notification_system = Mem0NotificationSystem(save_memory=default_save_memory)
    
    if mem0_communication_memory is None:
        mem0_communication_memory = Mem0CommunicationMemory(save_memory=default_save_memory)
    
    if unified_memory_manager is None:
        unified_memory_manager = Mem0MemoryManager(save_memory=default_save_memory)

def get_mem0_memory_manager():
    """获取mem0_memory_manager实例"""
    _ensure_global_instances_initialized()
    return mem0_memory_manager

def get_mem0_notification_system():
    """获取mem0_notification_system实例"""
    _ensure_global_instances_initialized()
    return mem0_notification_system

def get_mem0_communication_memory():
    """获取mem0_communication_memory实例"""
    _ensure_global_instances_initialized()
    return mem0_communication_memory

def get_unified_memory_manager():
    """获取unified_memory_manager实例"""
    _ensure_global_instances_initialized()
    return unified_memory_manager
