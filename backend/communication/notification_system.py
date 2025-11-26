#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simplified Notification System
No longer depends on memory system, only provides basic notification broadcast functionality
"""

from datetime import datetime
from typing import List, Optional


class Notification:
    """Notification object"""

    def __init__(
        self,
        sender_agent: str,
        content: str,
        urgency: str = "medium",
        category: str = "general",
    ):
        self.id = str(datetime.now().timestamp())
        self.sender_agent = sender_agent
        self.content = content
        self.urgency = urgency
        self.category = category
        self.timestamp = datetime.now()


class AgentNotificationMemory:
    """Agent notification memory"""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.notifications: List[Notification] = []

    def add_notification(self, notification: Notification):
        """Add notification"""
        self.notifications.append(notification)

    def get_recent_notifications(self, limit: int = 10) -> List[Notification]:
        """Get recent notifications"""
        return self.notifications[-limit:]


class SimpleNotificationSystem:
    """Simplified notification system"""

    def __init__(self):
        self.agent_memories = {}
        self.global_notifications: List[Notification] = []

    def register_agent(self, agent_id: str):
        """Register agent"""
        if agent_id not in self.agent_memories:
            self.agent_memories[agent_id] = AgentNotificationMemory(agent_id)

    def get_agent_memory(
        self,
        agent_id: str,
    ) -> Optional[AgentNotificationMemory]:
        """Get agent's notification memory"""
        if agent_id not in self.agent_memories:
            self.register_agent(agent_id)
        return self.agent_memories.get(agent_id)

    def broadcast_notification(
        self,
        sender_agent: str,
        content: str,
        urgency: str = "medium",
        category: str = "general",
        backtest_date: Optional[str] = None,
    ) -> str:
        """Broadcast notification"""
        notification = Notification(sender_agent, content, urgency, category)

        # Add to global notifications
        self.global_notifications.append(notification)

        # Send to all registered agents
        for _, agent_memory in self.agent_memories.items():
            agent_memory.add_notification(notification)

        return notification.id


# Create global notification system instance
notification_system = SimpleNotificationSystem()
