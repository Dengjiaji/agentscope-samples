# -*- coding: utf-8 -*-
from typing_extensions import TypedDict, Dict, Any, List


# Define agent state
class AgentState(TypedDict):
    """
    Agent state definition

    Uses AgentScope message format (return format of Msg.to_dict())
    Message format: {"id": str, "name": str, "content": str, "role": str, "metadata": dict, "timestamp": str}
    """

    messages: List[Dict[str, Any]]  # List of Msg.to_dict()
    data: Dict[str, Any]
    metadata: Dict[str, Any]
