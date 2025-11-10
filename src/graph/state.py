from typing_extensions import Annotated, Sequence, TypedDict, Dict, Any, List
import operator
import json
from agentscope.message import Msg

# Define agent state
class AgentState(TypedDict):
    """
    Agent 状态定义
    
    使用 AgentScope 消息格式（Msg.to_dict()的返回格式）
    消息格式: {"id": str, "name": str, "content": str, "role": str, "metadata": dict, "timestamp": str}
    """
    messages: List[Dict[str, Any]]  # Msg.to_dict()的列表
    data: [dict[str, any]]
    metadata: [dict[str, any]]
