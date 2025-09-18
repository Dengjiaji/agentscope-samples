#!/usr/bin/env python3
"""
Agent Notification System
Implement notification mechanism between agents, including notification tools and memory management
"""

import json
import math
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import re
try:
    import numpy as _np  # For type cleaning, optional
except Exception:
    _np = None
try:
    import pandas as _pd  # For type cleaning, optional
except Exception:
    _pd = None
import logging
import re
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


def _make_json_safe(obj: Any) -> Any:
    """将对象递归转换为可JSON序列化的原生类型。
    - numpy整/浮/布尔 -> int/float/bool
    - pandas/NumPy NaN/NaT -> None
    - datetime -> isoformat 字符串
    - dict/list/tuple 递归处理
    其他不可序列化对象 -> str(obj)
    """
    # None与基础类型
    if obj is None or isinstance(obj, (str, int, float, bool)):
        # 处理float中的nan/inf
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
        return obj

    # datetime
    if isinstance(obj, datetime):
        return obj.isoformat()

    # numpy 标量
    if _np is not None:
        if isinstance(obj, (_np.integer,)):
            return int(obj)
        if isinstance(obj, (_np.floating,)):
            val = float(obj)
            return None if math.isnan(val) or math.isinf(val) else val
        if isinstance(obj, (_np.bool_,)):
            return bool(obj)
        if obj is _np.nan:
            return None

    # pandas 标量
    if _pd is not None:
        try:
            if _pd.isna(obj):
                return None
        except Exception:
            pass

    # 容器类型
    if isinstance(obj, dict):
        return {str(_make_json_safe(k)): _make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_make_json_safe(v) for v in obj]

    # 兜底：尝试获取__dict__
    if hasattr(obj, "__dict__"):
        try:
            return _make_json_safe(vars(obj))
        except Exception:
            pass

    # 最后兜底：转字符串
    try:
        return str(obj)
    except Exception:
        return None

def robust_json_parse(text: str) -> Dict[str, Any]:
    """
    鲁棒的JSON解析函数，支持多种格式
    
    Args:
        text: 要解析的文本，可能包含markdown代码块或其他格式
        
    Returns:
        解析后的字典
        
    Raises:
        json.JSONDecodeError: 如果无法解析JSON
    """
    # 去除首尾空白字符
    text = text.strip()
    
    # 尝试直接解析（最常见的情况）
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # 尝试提取markdown代码块中的JSON
    # 匹配 ```json ... ``` 或 ``` ... ``` 格式
    json_code_block_patterns = [
        r'```json\s*\n(.*?)\n```',  # ```json ... ```
        r'```\s*\n(.*?)\n```',     # ``` ... ```
        r'```json(.*?)```',        # ```json...``` (无换行)
        r'```(.*?)```'             # ```...``` (无换行)
    ]
    
    for pattern in json_code_block_patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            json_content = match.group(1).strip()
            try:
                return json.loads(json_content)
            except json.JSONDecodeError:
                continue
    
    # 尝试查找JSON对象模式 {...}
    json_object_pattern = r'\{.*?\}'
    match = re.search(json_object_pattern, text, re.DOTALL)
    if match:
        json_content = match.group(0)
        try:
            return json.loads(json_content)
        except json.JSONDecodeError:
            pass
    
    # 尝试查找更复杂的JSON对象（支持嵌套）
    # 使用简单的大括号匹配
    start_idx = text.find('{')
    if start_idx != -1:
        brace_count = 0
        end_idx = start_idx
        for i, char in enumerate(text[start_idx:], start_idx):
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_idx = i + 1
                    break
        
        if brace_count == 0:  # 找到完整的JSON对象
            json_content = text[start_idx:end_idx]
            try:
                return json.loads(json_content)
            except json.JSONDecodeError:
                pass
    
    # 如果所有方法都失败，抛出原始错误
    raise json.JSONDecodeError("Unable to parse JSON from text", text, 0)


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
    
    return f"Notification sent, ID: {notification_id}"


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
    # Build prompt
    recent_notifications = agent_memory.get_recent_notifications(24)
    notifications_context = "\n".join([
        f"- {n.sender_agent}: {n.content} (Urgency: {n.urgency})"
        for n in recent_notifications[-5:]  # Only take the latest 5
    ])
    
    prompt = f"""
You are a {agent_id}, having just completed analysis and obtained the following results:

Analysis Results:
{json.dumps(_make_json_safe(analysis_result), ensure_ascii=False, indent=2)}

Notifications you recently received:
{notifications_context}

Please determine whether you need to send notifications to other analysts. Consider the following factors:
1. Importance and urgency of analysis results
2. Whether major risks or opportunities are discovered
3. Whether there is important information relevant to other analysts
4. Avoid sending duplicate or unimportant notifications

Please reply strictly in the following JSON format, do not include any additional text explanations:

If notification is needed:
{{
    "should_notify": true,
    "content": "notification content",
    "urgency": "low/medium/high/critical",
    "category": "market_alert/risk_warning/opportunity/policy_update/general"
}}

If notification is not needed:
{{
    "should_notify": false,
    "reason": "reason for not sending notification"
}}

Important: Reply content must be in pure JSON format, do not add any explanatory text or markdown markers.
"""
    # 获取LLM模型
    # print(type(state['metadata']))
    # print(state['metadata'])
    model = get_model(model_name=state["metadata"]['model_name'],model_provider=state['metadata']['model_provider'],api_keys=state['data']['api_keys'])
    
    # 设置最大重试次数
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            # Call LLM
            response = model.invoke([HumanMessage(content=prompt)])
            
            # Debug: Print LLM's raw response
            print(f"🔍 {agent_id} LLM notification decision raw response (attempt {attempt + 1}/{max_retries}): '{response.content}'")
            
            # Use robust JSON parsing
            decision = robust_json_parse(response.content)
            print(f"✅ {agent_id} JSON parsing successful")
            return decision
            
        except json.JSONDecodeError as e:
            print(f"⚠️ {agent_id} notification decision JSON parsing failed (attempt {attempt + 1}/{max_retries}): {str(e)}")
            print(f"📝 Raw response content: '{response.content}'")
            
            if attempt < max_retries - 1:
                print(f"🔄 Retrying...")
                # Modify prompt to emphasize JSON format requirements
                prompt += f"""

Note: Please strictly reply in JSON format, do not include any additional text explanations.
The previous reply format was incorrect: {response.content}
Please regenerate the correct JSON format reply."""
            else:
                # Last attempt failed, return default decision
                print(f"❌ {agent_id} reached maximum retry count, using fallback decision")
                fallback_decision = {
                    "should_notify": False,
                    "reason": f"LLM response parsing failed, retried {max_retries} times: {str(e)}"
                }
                print(f"🔧 Using fallback decision: {fallback_decision}")
                return fallback_decision
                
        except Exception as e:
            print(f"⚠️ {agent_id} notification decision processing encountered unknown error (attempt {attempt + 1}/{max_retries}): {str(e)}")
            
            if attempt < max_retries - 1:
                print(f"🔄 Retrying...")
            else:
                # Last attempt failed, return default decision
                print(f"❌ {agent_id} reached maximum retry count, using fallback decision")
                fallback_decision = {
                    "should_notify": False,
                    "reason": f"Notification decision processing failed, retried {max_retries} times: {str(e)}"
                }
                print(f"🔧 Using fallback decision: {fallback_decision}")
                return fallback_decision
        
 

def format_notifications_for_context(agent_memory: NotificationMemory) -> str:
    """
    格式化通知为上下文字符串，用于后续分析
    """
    recent_notifications = agent_memory.get_recent_notifications(24)
    
    if not recent_notifications:
        return "No notifications received today."
    
    formatted = "Notifications received today:\n"
    for notification in recent_notifications:
        formatted += f"""
- From {notification.sender_agent} ({notification.timestamp.strftime('%H:%M')}):
  {notification.content}
  Urgency: {notification.urgency} | Category: {notification.category}
"""
    
    return formatted
