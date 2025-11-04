from typing_extensions import Annotated, Sequence, TypedDict, Dict, Any, List
import operator
import json


def merge_dicts(a: dict[str, any], b: dict[str, any]) -> dict[str, any]:
    return {**a, **b}


def merge_messages(a: List[Dict[str, Any]], b: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """合并消息列表"""
    return a + b


# AgentScope Message 格式
# 参考: https://github.com/agentscope-ai/agentscope
# 消息格式: {"name": str, "content": str, "role": str, "metadata": dict}
class AgentScopeMessage(TypedDict):
    """AgentScope 消息格式"""
    name: str  # Agent 名称
    content: str  # 消息内容
    role: str  # 角色: "user", "assistant", "system"
    metadata: Dict[str, Any]  # 元数据


# Define agent state
class AgentState(TypedDict):
    """
    Agent 状态定义
    
    使用 AgentScope 消息格式，不再依赖 langchain_core.messages
    消息格式: {"name": str, "content": str, "role": str, "metadata": dict}
    """
    messages: Annotated[List[AgentScopeMessage], merge_messages]
    data: Annotated[dict[str, any], merge_dicts]
    metadata: Annotated[dict[str, any], merge_dicts]


def create_message(name: str, content: str, role: str = "assistant", metadata: Dict[str, Any] = None) -> AgentScopeMessage:
    """
    创建 AgentScope 消息
    
    Args:
        name: Agent 名称
        content: 消息内容
        role: 角色，可选值: "user", "assistant", "system"
        metadata: 元数据字典
    
    Returns:
        AgentScopeMessage 对象
    """
    return AgentScopeMessage(
        name=name,
        content=content,
        role=role,
        metadata=metadata or {}
    )


def langchain_to_agentscope_message(lc_message) -> AgentScopeMessage:
    """
    将 LangChain 消息转换为 AgentScope 消息格式
    
    用于兼容性和迁移过程
    """
    # 从 LangChain 消息中提取信息
    name = getattr(lc_message, 'name', 'unknown')
    content = lc_message.content
    
    # 映射消息类型
    role_mapping = {
        'human': 'user',
        'ai': 'assistant',
        'system': 'system',
    }
    
    lc_type = lc_message.type if hasattr(lc_message, 'type') else 'ai'
    role = role_mapping.get(lc_type, 'assistant')
    
    return create_message(name=name, content=content, role=role)


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
