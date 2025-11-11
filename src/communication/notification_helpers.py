#!/usr/bin/env python3
"""
通知系统辅助函数
提供通知决策等功能
"""

import json
import math
import re
from typing import Dict, Any, Optional
from datetime import datetime
import logging

try:
    import numpy as _np
except Exception:
    _np = None
try:
    import pandas as _pd
except Exception:
    _pd = None

from src.graph.state import AgentState
from src.llm.models import get_model


logger = logging.getLogger(__name__)


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


def should_send_notification(agent_id: str, analysis_result: Dict, 
                           agent_memory, state: AgentState) -> Dict[str, Any]:
    """
    使用LLM判断是否需要发送通知
    
    Args:
        agent_id: Agent ID
        analysis_result: 分析结果
        agent_memory: Agent记忆（可以为None）
        state: Agent状态
        
    Returns:
        决策字典，包含should_notify, content, urgency, category等字段
    """
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
            
            logger.debug(f"🔍 {agent_id} LLM notification decision raw response (attempt {attempt + 1}/{max_retries}): '{response_content}'")
            
            decision = robust_json_parse(response_content)
            logger.debug(f"✅ {agent_id} JSON parsing successful")
            return decision
            
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ {agent_id} notification decision JSON parsing failed (attempt {attempt + 1}/{max_retries}): {str(e)}")
            
            if attempt < max_retries - 1:
                logger.debug(f"🔄 Retrying...")
                prompt += f"""

Note: Please strictly reply in JSON format, do not include any additional text explanations.
The previous reply format was incorrect: {response_content}
Please regenerate the correct JSON format reply."""
            else:
                logger.warning(f"❌ {agent_id} reached maximum retry count, using fallback decision")
                fallback_decision = {
                    "should_notify": False,
                    "reason": f"LLM response parsing failed, retried {max_retries} times: {str(e)}"
                }
                return fallback_decision
                
        except Exception as e:
            logger.warning(f"⚠️ {agent_id} notification decision processing encountered unknown error (attempt {attempt + 1}/{max_retries}): {str(e)}")
            
            if attempt < max_retries - 1:
                logger.debug(f"🔄 Retrying...")
            else:
                logger.warning(f"❌ {agent_id} reached maximum retry count, using fallback decision")
                fallback_decision = {
                    "should_notify": False,
                    "reason": f"Notification decision processing failed, retried {max_retries} times: {str(e)}"
                }
                return fallback_decision

