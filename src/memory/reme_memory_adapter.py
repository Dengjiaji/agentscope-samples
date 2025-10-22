#!/usr/bin/env python3
"""
ReMe 框架的记忆和通知系统适配器
提供与 Mem0 兼容的接口
"""

import logging
import json
from typing import Dict, List, Any, Optional
import uuid
import numpy as np


def _convert_numpy_types(obj):
    """
    递归转换对象中的numpy类型为Python原生类型
    """
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: _convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_convert_numpy_types(item) for item in obj]
    else:
        return obj


def _normalize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    标准化metadata，将不支持的类型转换为字符串
    ChromaDB只支持: str, int, float, bool (注意：实际不支持 None!)
    """
    if metadata is None:
        return {}
    
    normalized = {}
    for key, value in metadata.items():
        # ⚠️ 跳过 None 值 - ChromaDB 实际不接受 None
        if value is None:
            continue  # 不添加这个键值对
        elif isinstance(value, (str, bool)):
            # 字符串和布尔值保持不变
            normalized[key] = value
        elif isinstance(value, (int, float)):
            # Python原生数字类型保持不变
            normalized[key] = value
        elif isinstance(value, (np.integer, np.floating)):
            # numpy数字类型转换为Python原生类型
            if isinstance(value, np.integer):
                normalized[key] = int(value)
            else:
                normalized[key] = float(value)
        elif isinstance(value, (list, tuple, dict, np.ndarray)):
            # 复杂类型：先转换numpy类型，再转JSON字符串
            try:
                converted_value = _convert_numpy_types(value)
                normalized[key] = json.dumps(converted_value, ensure_ascii=False)
            except (TypeError, ValueError) as e:
                # 如果JSON序列化失败，直接转字符串
                normalized[key] = str(value)
        else:
            # 其他类型转换为字符串
            normalized[key] = str(value)
    
    return normalized


class ReMeAnalystMemory:
    """
    ReMe 框架的分析师记忆适配器
    提供与 Mem0AnalystMemory 兼容的接口
    """
    
    def __init__(self, analyst_id: str, reme_adapter):
        self.analyst_id = analyst_id
        self.analyst_name = analyst_id.replace('_', ' ').title()
        self.reme_adapter = reme_adapter
        self.logger = logging.getLogger(__name__)
        # 为兼容性提供 memory 属性（指向 reme_adapter）
        self.memory = reme_adapter
    
    def start_analysis_session(self, session_type: str, tickers: List[str], context: Dict[str, Any] = None):
        """开始分析会话"""
        session_id = str(uuid.uuid4())
        
        metadata = _normalize_metadata({
            "type": "session_start",
            "session_id": session_id,
            "session_type": session_type,
            "tickers": tickers,
            "context": context or {}
        })
        
        self.reme_adapter.add(
            messages=f"开始{session_type}会话，标的: {','.join(tickers)}",
            user_id=self.analyst_id,
            metadata=metadata
        )
        
        self.logger.info(f"ReMe: 开始分析会话 {session_id} for {self.analyst_id}")
        return session_id
    
    def add_analysis_message(self, session_id: str, role: str, content: str, metadata: Dict[str, Any] = None):
        """添加分析消息"""
        msg_metadata = {
            "type": "message",
            "session_id": session_id,
            **(metadata or {})
        }
        msg_metadata = _normalize_metadata(msg_metadata)
        
        self.reme_adapter.add(
            messages=[{"role": role, "content": content}],
            user_id=self.analyst_id,
            metadata=msg_metadata
        )
    
    def complete_analysis_session(self, session_id: str, final_result: Dict[str, Any]):
        """完成分析会话"""
        metadata = _normalize_metadata({
            "type": "session_complete",
            "session_id": session_id,
            "final_result": final_result
        })
        
        self.reme_adapter.add(
            messages=f"完成分析会话，结果: {str(final_result)[:200]}...",
            user_id=self.analyst_id,
            metadata=metadata
        )
        
        self.logger.info(f"ReMe: 完成分析会话 {session_id} for {self.analyst_id}")
    
    def get_relevant_memories(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """获取相关记忆"""
        results = self.reme_adapter.search(
            query=query,
            user_id=self.analyst_id,
            top_k=limit
        )
        return results.get('results', [])
    
    def start_communication(self, communication_type: str, participants: List[str], topic: str) -> str:
        """开始新的通信"""
        communication_id = str(uuid.uuid4())
        
        metadata = _normalize_metadata({
            "type": "communication_start",
            "communication_id": communication_id,
            "communication_type": communication_type,
            "participants": participants,
            "topic": topic
        })
        
        self.reme_adapter.add(
            messages=f"开始{communication_type}通信，话题: {topic}，参与者: {','.join(participants)}",
            user_id=self.analyst_id,
            metadata=metadata
        )
        
        self.logger.info(f"ReMe: 开始通信 {communication_id} for {self.analyst_id}")
        return communication_id
    
    def add_communication_message(self, communication_id: str, speaker: str, content: str, metadata: Dict[str, Any] = None):
        """添加通信消息"""
        msg_metadata = {
            "type": "communication_message",
            "communication_id": communication_id,
            "speaker": speaker,
            **(metadata or {})
        }
        msg_metadata = _normalize_metadata(msg_metadata)
        
        self.reme_adapter.add(
            messages=[{"role": "user" if speaker == self.analyst_id else "assistant", 
                      "content": f"[{speaker}]: {content}"}],
            user_id=self.analyst_id,
            metadata=msg_metadata
        )
    
    def complete_communication(self, communication_id: str, summary: str = None):
        """完成通信"""
        metadata = _normalize_metadata({
            "type": "communication_complete",
            "communication_id": communication_id,
            "summary": summary or "通信结束"
        })
        
        self.reme_adapter.add(
            messages=f"完成通信，总结: {summary or '无'}",
            user_id=self.analyst_id,
            metadata=metadata
        )
        
        self.logger.info(f"ReMe: 完成通信 {communication_id} for {self.analyst_id}")
    
    def record_signal_adjustment(self, communication_id: str, original_signal: Dict[str, Any], 
                                adjusted_signal: Dict[str, Any], reasoning: str):
        """记录信号调整"""
        metadata = _normalize_metadata({
            "type": "signal_adjustment",
            "communication_id": communication_id,
            "original_signal": original_signal,
            "adjusted_signal": adjusted_signal,
            "reasoning": reasoning
        })
        
        # 提取信号摘要
        orig_summary = self._extract_signal_summary(original_signal)
        adj_summary = self._extract_signal_summary(adjusted_signal)
        
        self.reme_adapter.add(
            messages=f"信号调整: {orig_summary} -> {adj_summary}, 理由: {reasoning}",
            user_id=self.analyst_id,
            metadata=metadata
        )
        
        self.logger.info(f"ReMe: 记录信号调整 for {self.analyst_id}")
    
    def get_full_context_for_communication(self, tickers: List[str] = None) -> str:
        """获取用于通信的完整上下文"""
        # 构建查询
        if tickers:
            query = f"关于{', '.join(tickers)}的分析和讨论"
        else:
            query = "最近的分析结果和讨论"
        
        # 从 ReMe 获取相关记忆
        relevant_memories = self.get_relevant_memories(query, limit=15)
        
        context_parts = [f"=== {self.analyst_name} 的记忆上下文 ==="]
        
        if relevant_memories:
            context_parts.append("\n=== 相关记忆 ===")
            for i, memory in enumerate(relevant_memories[:10], 1):
                if isinstance(memory, dict):
                    # ReMe 返回的结果格式
                    memory_text = memory.get('memory', memory.get('content', ''))
                    if len(memory_text) > 200:
                        memory_text = memory_text[:200] + "..."
                    context_parts.append(f"{i}. {memory_text}")
                else:
                    context_parts.append(f"{i}. {str(memory)[:200]}")
        else:
            context_parts.append("\n=== 暂无相关记忆 ===")
        
        return "\n".join(context_parts)
    
    def _extract_signal_summary(self, signal: Dict[str, Any]) -> str:
        """提取信号摘要"""
        if isinstance(signal, dict):
            if 'action' in signal:
                action = signal['action']
                confidence = signal.get('confidence', 'N/A')
                return f"{action} (置信度: {confidence})"
            elif 'recommendation' in signal:
                return signal['recommendation']
            elif 'signal' in signal:
                return str(signal['signal'])
            else:
                return str(signal)[:50] + "..." if len(str(signal)) > 50 else str(signal)
        
        return "信号格式未知"


class ReMeNotificationSystem:
    """
    ReMe 框架的通知系统适配器
    提供与 Mem0NotificationSystem 兼容的接口
    """
    
    def __init__(self, reme_adapter):
        self.reme_adapter = reme_adapter
        self.logger = logging.getLogger(__name__)
        self._agent_memories = {}
        self._registered_agents = set()  # 跟踪已注册的 agents
    
    def register_agent(self, agent_id: str, agent_name: str = None):
        """注册agent"""
        # 记录已注册的 agent，用于广播通知
        self._registered_agents.add(agent_id)
        self.logger.info(f"ReMe: 注册agent {agent_id} (workspace自动创建)")
    
    def get_agent_memory(self, agent_id: str):
        """获取agent的通知记忆"""
        if agent_id not in self._agent_memories:
            self._agent_memories[agent_id] = ReMeAgentNotificationMemory(
                agent_id, 
                self.reme_adapter
            )
        return self._agent_memories[agent_id]
    
    def broadcast_notification(self, sender_agent: str, content: str, 
                             urgency: str = "medium", category: str = "general",
                             backtest_date: Optional[str] = None):
        """
        广播通知给所有已注册的 agents
        
        ✅ 对齐 Mem0 设计：
        1. 使用相同的 user_id，通过 metadata.type 区分
        2. 广播到所有已注册的 agents（不只是发送者）
        """
        notification_id = str(uuid.uuid4())
        
        metadata = _normalize_metadata({
            "type": "notification",  # 通过 type 字段区分通知记忆
            "notification_id": notification_id,
            "sender": sender_agent,
            "urgency": urgency,
            "category": category,
            "backtest_date": backtest_date
        })
        
        # ✅ 重要修复：广播给所有已注册的 agents（对齐 Mem0 行为）
        # 遍历所有已注册的 agents，每个 agent 的 workspace 都保存一份通知
        agents_to_notify = self._registered_agents if self._registered_agents else {sender_agent}
        
        for agent_id in agents_to_notify:
            self.reme_adapter.add(
                messages=f"[通知] 来自{sender_agent}: {content}",
                user_id=agent_id,  # 添加到每个 agent 的 workspace
                metadata=metadata
            )
        
        self.logger.info(
            f"ReMe: 广播通知 {notification_id} from {sender_agent} "
            f"to {len(agents_to_notify)} agents"
        )
        return notification_id


class ReMeAgentNotificationMemory:
    """
    ReMe 框架的agent通知记忆
    提供与 Mem0NotificationMemory 兼容的接口
    """
    
    def __init__(self, agent_id: str, reme_adapter):
        self.agent_id = agent_id
        self.reme_adapter = reme_adapter
        self.logger = logging.getLogger(__name__)
    
    def get_recent_notifications(self, limit: int = 10, 
                                category: Optional[str] = None,
                                backtest_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取最近的通知
        
        ✅ 对齐 Mem0 设计：使用相同的 user_id，通过 metadata.type 过滤
        """
        query = f"通知 {category or ''} {backtest_date or ''}".strip()
        
        # ✅ 对齐修改：不使用 notifications_ 前缀，直接使用 agent_id
        results = self.reme_adapter.search(
            query=query,
            user_id=self.agent_id,  # 使用相同的 user_id
            top_k=limit * 2  # 增加数量以补偿过滤损失
        )
        
        # ✅ 通过 metadata.type 过滤出通知记忆
        notifications = []
        for result in results.get('results', []):
            if result.get('metadata', {}).get('type') == 'notification':
                notifications.append(result)
                if len(notifications) >= limit:
                    break  # 达到限制数量后停止
        
        return notifications
    
    def clear_notifications(self, notification_ids: Optional[List[str]] = None):
        """清除通知（ReMe 不支持，仅记录）"""
        self.logger.warning(f"ReMe: 清除通知功能未实现 (agent={self.agent_id})")
        # ReMe 不支持单独删除，可以选择不实现或标记为已读
        pass

