#!/usr/bin/env python3
"""
简化的通知系统
不再依赖memory系统，只提供基本的通知广播功能
"""

from datetime import datetime
from typing import List, Optional


class Notification:
    """通知对象"""
    
    def __init__(self, sender_agent: str, content: str, urgency: str = "medium", 
                 category: str = "general"):
        self.id = str(datetime.now().timestamp())
        self.sender_agent = sender_agent
        self.content = content
        self.urgency = urgency
        self.category = category
        self.timestamp = datetime.now()


class AgentNotificationMemory:
    """Agent通知记忆）"""
    
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.notifications: List[Notification] = []
    
    def add_notification(self, notification: Notification):
        """添加通知"""
        self.notifications.append(notification)
    
    def get_recent_notifications(self, limit: int = 10) -> List[Notification]:
        """获取最近的通知"""
        return self.notifications[-limit:]


class SimpleNotificationSystem:
    """简化的通知系统"""
    
    def __init__(self):
        self.agent_memories = {}
        self.global_notifications: List[Notification] = []
    
    def register_agent(self, agent_id: str):
        """注册agent"""
        if agent_id not in self.agent_memories:
            self.agent_memories[agent_id] = AgentNotificationMemory(agent_id)
    
    def get_agent_memory(self, agent_id: str) -> Optional[AgentNotificationMemory]:
        """获取agent的通知记忆"""
        if agent_id not in self.agent_memories:
            self.register_agent(agent_id)
        return self.agent_memories.get(agent_id)
    
    def broadcast_notification(self, sender_agent: str, content: str, 
                             urgency: str = "medium", category: str = "general",
                             backtest_date: Optional[str] = None) -> str:
        """广播通知"""
        notification = Notification(sender_agent, content, urgency, category)
        
        # 添加到全局通知
        self.global_notifications.append(notification)
        
        # 发送给所有注册的agents
        for agent_id, agent_memory in self.agent_memories.items():
            agent_memory.add_notification(notification)
        
        return notification.id


# 创建全局通知系统实例
notification_system = SimpleNotificationSystem()

