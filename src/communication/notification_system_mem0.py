#!/usr/bin/env python3
"""
基于Mem0的Agent通知系统
替换原有的notification_system，使用Mem0记忆框架
"""

import json
import math
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import re
try:
    import numpy as _np
except Exception:
    _np = None
try:
    import pandas as _pd
except Exception:
    _pd = None
import logging
from src.graph.state import AgentState, create_message
from src.llm.models import get_model

# 导入新的记忆系统（延迟导入，避免在模块加载时初始化）
# from src.memory import unified_memory_manager
from src.memory.mem0_core import Notification


def _make_json_safe(obj: Any) -> Any:
    """将对象递归转换为可JSON序列化的原生类型"""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
        return obj

    if isinstance(obj, datetime):
        return obj.isoformat()

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

    if _pd is not None:
        try:
            if _pd.isna(obj):
                return None
        except Exception:
            pass

    if isinstance(obj, dict):
        return {str(_make_json_safe(k)): _make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_make_json_safe(v) for v in obj]

    if hasattr(obj, "__dict__"):
        try:
            return _make_json_safe(vars(obj))
        except Exception:
            pass

    try:
        return str(obj)
    except Exception:
        return None


def robust_json_parse(text: str) -> Dict[str, Any]:
    """鲁棒的JSON解析函数"""
    text = text.strip()
    
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    json_code_block_patterns = [
        r'```json\s*\n(.*?)\n```',
        r'```\s*\n(.*?)\n```',
        r'```json(.*?)```',
        r'```(.*?)```'
    ]
    
    for pattern in json_code_block_patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            json_content = match.group(1).strip()
            try:
                return json.loads(json_content)
            except json.JSONDecodeError:
                continue
    
    json_object_pattern = r'\{.*?\}'
    match = re.search(json_object_pattern, text, re.DOTALL)
    if match:
        json_content = match.group(0)
        try:
            return json.loads(json_content)
        except json.JSONDecodeError:
            pass
    
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
        
        if brace_count == 0:
            json_content = text[start_idx:end_idx]
            try:
                return json.loads(json_content)
            except json.JSONDecodeError:
                pass
    
    raise json.JSONDecodeError("Unable to parse JSON from text", text, 0)


class Mem0NotificationSystem:
    """基于Mem0的通知系统"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # 使用统一记忆管理器（延迟导入）
        from src.memory import unified_memory_manager
        self.memory_manager = unified_memory_manager
    
    def register_agent(self, agent_id: str, agent_name: str = None):
        """注册agent"""
        self.memory_manager.register_analyst(agent_id, agent_name)
        self.logger.info(f"Registered agent: {agent_id}")
    
    def broadcast_notification(self, sender_agent: str, content: str, 
                             urgency: str = "medium", category: str = "general",
                             backtest_date: Optional[str] = None):
        """广播通知给所有agents（支持回测日期 backtest_date）"""
        notification_id = self.memory_manager.broadcast_notification(
            sender_agent, content, urgency, category, backtest_date
        )
        
        self.logger.info(f"Broadcasted notification from {sender_agent} to all agents")
        return notification_id
    
    def get_agent_memory(self, agent_id: str):
        """获取agent的通知记忆"""
        return self.memory_manager.notification_system.get_agent_memory(agent_id)


def send_notification(content: str, urgency: str = "medium", category: str = "general") -> str:
    """
    发送通知给所有其他agents的工具
    
    AgentScope 工具函数（不需要 @tool 装饰器）
    
    Args:
        content: 通知内容
        urgency: 紧急程度 ("low", "medium", "high", "critical")
        category: 通知类别 ("market_alert", "risk_warning", "opportunity", "policy_update", "general")
    
    Returns:
        通知ID
    """
    sender_agent = "unknown_agent"  # 实际使用时需要从context获取
    
    notification_id = mem0_notification_system.broadcast_notification(
        sender_agent=sender_agent,
        content=content,
        urgency=urgency,
        category=category
    )
    
    return f"Notification sent, ID: {notification_id}"


def should_send_notification(agent_id: str, analysis_result: Dict, 
                           agent_memory, state: AgentState) -> Dict[str, Any]:
    """
    使用LLM判断是否需要发送通知（基于Mem0记忆）
    """
    # 从Mem0获取最近的通知记忆
    # notification_memory = mem0_notification_system.get_agent_memory(agent_id)
    prompt = f"""
You are a {agent_id}, having just completed analysis and obtained the following results:

Analysis Results:
{json.dumps(_make_json_safe(analysis_result), ensure_ascii=False, indent=2)}

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
    
    model = get_model(
        model_name=state["metadata"]['model_name'],
        model_provider=state['metadata']['model_provider'],
        api_keys=state['data']['api_keys']
    )
    
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            # 使用 AgentScope 消息格式
            messages = [{"role": "user", "content": prompt}]
            response = model(messages)
            response_content = response.get("content", "")
            
            print(f"🔍 {agent_id} LLM notification decision raw response (attempt {attempt + 1}/{max_retries}): '{response_content}'")
            
            decision = robust_json_parse(response_content)
            print(f"✅ {agent_id} JSON parsing successful")
            return decision
            
        except json.JSONDecodeError as e:
            print(f"⚠️ {agent_id} notification decision JSON parsing failed (attempt {attempt + 1}/{max_retries}): {str(e)}")
            print(f"📝 Raw response content: '{response_content}'")
            
            if attempt < max_retries - 1:
                print(f"🔄 Retrying...")
                prompt += f"""

Note: Please strictly reply in JSON format, do not include any additional text explanations.
The previous reply format was incorrect: {response_content}
Please regenerate the correct JSON format reply."""
            else:
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
                print(f"❌ {agent_id} reached maximum retry count, using fallback decision")
                fallback_decision = {
                    "should_notify": False,
                    "reason": f"Notification decision processing failed, retried {max_retries} times: {str(e)}"
                }
                print(f"🔧 Using fallback decision: {fallback_decision}")
                return fallback_decision


# def format_notifications_for_context(agent_id: str, backtest_date: Optional[str] = None) -> str:
#     """
#     格式化通知为上下文字符串，用于后续分析（基于Mem0）
#     """
#     notification_memory = mem0_notification_system.get_agent_memory(agent_id)
    
#     if not notification_memory:
#         return "No notifications received today."
    
#     recent_notifications = notification_memory.get_recent_notifications(24, backtest_date=backtest_date)
    
#     if not recent_notifications:
#         return "No notifications received today."
    
#     formatted = "Notifications received today:\n"
#     for notification in recent_notifications:
#         if not isinstance(notification, dict):
#             # 搜索返回了非结构化条目，跳过
#             continue
#         metadata = notification.get('metadata', {}) or {}
#         sender = metadata.get('sender', 'unknown')
#         timestamp = metadata.get('timestamp', '')
#         urgency = metadata.get('urgency', 'unknown')
#         category = metadata.get('category', 'unknown')
#         content = (notification.get('memory', '') or '')[:200]
        
#         # 尝试解析时间戳
#         try:
#             if timestamp:
#                 dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
#                 time_str = dt.strftime('%H:%M')
#             else:
#                 time_str = '??:??'
#         except:
#             time_str = '??:??'
        
#         formatted += f"""
# - From {sender} ({time_str}):
#   {content}
#   Urgency: {urgency} | Category: {category}
# """
    
#     return formatted


# 创建全局Mem0通知系统实例（延迟初始化）
_mem0_notification_system = None

def get_mem0_notification_system():
    """获取全局Mem0通知系统实例（延迟初始化）"""
    global _mem0_notification_system
    if _mem0_notification_system is None:
        _mem0_notification_system = Mem0NotificationSystem()
    return _mem0_notification_system

# 使用模块级别的__getattr__实现延迟初始化和向后兼容
def __getattr__(name):
    if name == 'mem0_notification_system':
        return get_mem0_notification_system()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
