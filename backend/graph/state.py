from typing_extensions import Annotated, Sequence, TypedDict, Dict, Any, List
import operator
import json
from agentscope.message import Msg

# Define agent state
class AgentState(TypedDict):
    """
    Agent state definition
    
    Uses AgentScope message format (return format of Msg.to_dict())
    Message format: {"id": str, "name": str, "content": str, "role": str, "metadata": dict, "timestamp": str}
    """
    messages: List[Dict[str, Any]]  # List of Msg.to_dict()
    data: [dict[str, any]]
    metadata: [dict[str, any]]
