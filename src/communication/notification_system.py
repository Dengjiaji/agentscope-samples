#!/usr/bin/env python3
"""
Agent通知系统
实现agents之间的通知机制，包括通知工具和记忆管理
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from src.graph.state import AgentState
from src.llm.models import get_model


@dataclass
class Notification:
    """通知数据结构"""
    id: str
    sender_agent: str
    timestamp: datetime
    content: str
    urgency: str  # "low", "medium", "high", "critical"
    category: str  # "market_alert", "risk_warning", "opportunity", "policy_update"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "sender_agent": self.sender_agent,
            "timestamp": self.timestamp.isoformat(),
            "content": self.content,
            "urgency": self.urgency,
            "category": self.category
        }


class NotificationMemory:
    """Agent通知记忆管理"""
    
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.notifications: List[Notification] = []
        self.sent_notifications: List[Notification] = []
    
    def add_received_notification(self, notification: Notification):
        """添加收到的通知"""
        self.notifications.append(notification)
        logging.info(f"Agent {self.agent_id} received notification from {notification.sender_agent}")
    
    def add_sent_notification(self, notification: Notification):
        """添加发送的通知"""
        self.sent_notifications.append(notification)
        logging.info(f"Agent {self.agent_id} sent notification: {notification.content}")
    
    def get_recent_notifications(self, hours: int = 24) -> List[Notification]:
        """获取最近的通知"""
        cutoff_time = datetime.now().timestamp() - (hours * 3600)
        return [n for n in self.notifications 
                if n.timestamp.timestamp() > cutoff_time]
    
    def get_notifications_by_urgency(self, urgency: str) -> List[Notification]:
        """根据紧急程度获取通知"""
        return [n for n in self.notifications if n.urgency == urgency]
    
    def clear_old_notifications(self, days: int = 7):
        """清理旧通知"""
        cutoff_time = datetime.now().timestamp() - (days * 24 * 3600)
        self.notifications = [n for n in self.notifications 
                            if n.timestamp.timestamp() > cutoff_time]


class NotificationSystem:
    """全局通知系统"""
    
    def __init__(self):
        self.agent_memories: Dict[str, NotificationMemory] = {}
        self.global_notifications: List[Notification] = []
    
    def register_agent(self, agent_id: str):
        """注册agent"""
        if agent_id not in self.agent_memories:
            self.agent_memories[agent_id] = NotificationMemory(agent_id)
            logging.info(f"Registered agent: {agent_id}")
    
    def broadcast_notification(self, sender_agent: str, content: str, 
                             urgency: str = "medium", category: str = "general"):
        """广播通知给所有agents"""
        notification = Notification(
            id=f"{sender_agent}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            sender_agent=sender_agent,
            timestamp=datetime.now(),
            content=content,
            urgency=urgency,
            category=category
        )
        
        # 添加到全局通知
        self.global_notifications.append(notification)
        
        # 发送给所有其他agents
        for agent_id, memory in self.agent_memories.items():
            if agent_id != sender_agent:  # 不发送给自己
                memory.add_received_notification(notification)
        
        # 记录发送者的发送历史
        if sender_agent in self.agent_memories:
            self.agent_memories[sender_agent].add_sent_notification(notification)
        
        logging.info(f"Broadcasted notification from {sender_agent} to all agents")
        return notification.id
    
    def get_agent_memory(self, agent_id: str) -> Optional[NotificationMemory]:
        """获取agent的通知记忆"""
        return self.agent_memories.get(agent_id)


# 全局通知系统实例
notification_system = NotificationSystem()


@tool
def send_notification(content: str, urgency: str = "medium", category: str = "general") -> str:
    """
    发送通知给所有其他agents的工具
    
    Args:
        content: 通知内容
        urgency: 紧急程度 ("low", "medium", "high", "critical")
        category: 通知类别 ("market_alert", "risk_warning", "opportunity", "policy_update", "general")
    
    Returns:
        通知ID
    """
    # 这里需要从上下文获取发送者信息，暂时使用占位符
    sender_agent = "unknown_agent"  # 实际使用时需要从context获取
    
    notification_id = notification_system.broadcast_notification(
        sender_agent=sender_agent,
        content=content,
        urgency=urgency,
        category=category
    )
    
    return f"通知已发送，ID: {notification_id}"


def should_send_notification(agent_id: str, analysis_result: Dict, 
                           agent_memory: NotificationMemory, 
                           state: AgentState) -> Dict[str, Any]:
    """
    使用LLM判断是否需要发送通知
    
    Args:
        agent_id: Agent ID
        analysis_result: Agent的分析结果
        agent_memory: Agent的通知记忆
        state: Agent状态
    
    Returns:
        通知决策结果
    """
    # 构建prompt
    recent_notifications = agent_memory.get_recent_notifications(24)
    notifications_context = "\n".join([
        f"- {n.sender_agent}: {n.content} (紧急程度: {n.urgency})"
        for n in recent_notifications[-5:]  # 只取最近5条
    ])
    
    prompt = f"""
你是一个{agent_id}，刚刚完成了分析并得到以下结果：

分析结果：
{json.dumps(analysis_result, ensure_ascii=False, indent=2)}

你最近收到的通知：
{notifications_context}

请判断是否需要向其他分析师发送通知。考虑以下因素：
1. 分析结果的重要性和紧急性
2. 是否发现了重大风险或机会
3. 是否有与其他分析师相关的重要信息
4. 避免发送重复或不重要的通知

请严格按照以下JSON格式回复，不要包含任何额外的文字说明：

如果需要发送通知：
{{
    "should_notify": true,
    "content": "通知内容",
    "urgency": "low/medium/high/critical",
    "category": "market_alert/risk_warning/opportunity/policy_update/general"
}}

如果不需要发送通知：
{{
    "should_notify": false,
    "reason": "不发送通知的原因"
}}

重要：回复内容必须是纯JSON格式，不要添加任何解释文字或markdown标记。
"""
    
    # 获取LLM模型
    # print(type(state['metadata']))
    # print(state['metadata'])
    model = get_model(model_name=state["metadata"]['model_name'],model_provider=state['metadata']['model_provider'],api_keys=state['data']['api_keys'])
    
    # 设置最大重试次数
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            # 调用LLM
            response = model.invoke([HumanMessage(content=prompt)])
            
            # 调试：打印LLM的原始响应
            print(f"🔍 {agent_id} LLM通知决策原始响应 (尝试 {attempt + 1}/{max_retries}): '{response.content}'")
            
            # 解析响应
            decision = json.loads(response.content)
            print(f"✅ {agent_id} JSON解析成功")
            return decision
            
        except json.JSONDecodeError as e:
            print(f"⚠️ {agent_id} 通知决策JSON解析失败 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
            print(f"📝 原始响应内容: '{response.content}'")
            
            if attempt < max_retries - 1:
                print(f"🔄 正在重试...")
                # 修改prompt，强调JSON格式要求
                prompt += f"""

注意：请务必严格按照JSON格式回复，不要包含任何额外的文字说明。
上一次回复格式有误：{response.content}
请重新生成正确的JSON格式回复。"""
            else:
                # 最后一次尝试失败，返回默认决策
                print(f"❌ {agent_id} 达到最大重试次数，使用备用决策")
                fallback_decision = {
                    "should_notify": False,
                    "reason": f"LLM响应解析失败，已重试{max_retries}次: {str(e)}"
                }
                print(f"🔧 使用备用决策: {fallback_decision}")
                return fallback_decision
                
        except Exception as e:
            print(f"⚠️ {agent_id} 通知决策处理出现未知错误 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
            
            if attempt < max_retries - 1:
                print(f"🔄 正在重试...")
            else:
                # 最后一次尝试失败，返回默认决策
                print(f"❌ {agent_id} 达到最大重试次数，使用备用决策")
                fallback_decision = {
                    "should_notify": False,
                    "reason": f"通知决策处理失败，已重试{max_retries}次: {str(e)}"
                }
                print(f"🔧 使用备用决策: {fallback_decision}")
                return fallback_decision
        
 

def format_notifications_for_context(agent_memory: NotificationMemory) -> str:
    """
    格式化通知为上下文字符串，用于后续分析
    """
    recent_notifications = agent_memory.get_recent_notifications(24)
    
    if not recent_notifications:
        return "今日暂无收到通知。"
    
    formatted = "今日收到的通知：\n"
    for notification in recent_notifications:
        formatted += f"""
- 来自 {notification.sender_agent} ({notification.timestamp.strftime('%H:%M')}):
  {notification.content}
  紧急程度: {notification.urgency} | 类别: {notification.category}
"""
    
    return formatted
