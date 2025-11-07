from typing_extensions import Annotated, Sequence, TypedDict, Dict, Any, List
import operator
import json
from agentscope.message import Msg

def merge_dicts(a: dict[str, any], b: dict[str, any]) -> dict[str, any]:
    return {**a, **b}


def merge_messages(a: List[Dict[str, Any]], b: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """合并消息列表（兼容AgentScope Msg的dict格式）"""
    return a + b


# Define agent state
class AgentState(TypedDict):
    """
    Agent 状态定义
    
    使用 AgentScope 消息格式（Msg.to_dict()的返回格式）
    消息格式: {"id": str, "name": str, "content": str, "role": str, "metadata": dict, "timestamp": str}
    """
    messages: Annotated[List[Dict[str, Any]], merge_messages]  # Msg.to_dict()的列表
    data: Annotated[dict[str, any], merge_dicts]
    metadata: Annotated[dict[str, any], merge_dicts]


def create_message(name: str, content: str, role: str = "assistant", metadata: Dict[str, Any] = None) -> Msg:
    """
    创建 AgentScope 消息（使用原生Msg类）
    
    Args:
        name: Agent 名称
        content: 消息内容
        role: 角色，可选值: "user", "assistant", "system"
        metadata: 元数据字典
    
    Returns:
        Msg 对象
    """
    return Msg(
        name=name,
        content=content,
        role=role,
        metadata=metadata or {}
    )


def show_agent_reasoning(output, agent_name):
    print(f"\n{'=' * 10} {agent_name.center(28)} {'=' * 10}")

    def convert_to_serializable(obj):
        if hasattr(obj, "to_dict"):  # Handle Pandas Series/DataFrame
            return obj.to_dict()
        elif hasattr(obj, "__dict__"):  # Handle custom objects
            return obj.__dict__
        elif isinstance(obj, (int, float, bool, str)):
            return obj
        elif isinstance(obj, (list, tuple)):
            return [convert_to_serializable(item) for item in obj]
        elif isinstance(obj, dict):
            return {key: convert_to_serializable(value) for key, value in obj.items()}
        else:
            return str(obj)  # Fallback to string representation

    if isinstance(output, (dict, list)):
        # Convert the output to JSON-serializable format
        serializable_output = convert_to_serializable(output)
        print(json.dumps(serializable_output, indent=2))
    else:
        try:
            # Parse the string as JSON and pretty print it
            parsed_output = json.loads(output)
            print(json.dumps(parsed_output, indent=2))
        except json.JSONDecodeError:
            # Fallback to original string if not valid JSON
            print(output)

    print("=" * 48)
