"""
AgentScope Prompt 处理模块

提供灵活的 Prompt 模板处理功能
"""
from typing import Dict, Any, List, Optional, Union
import re


class PromptTemplate:
    """
    Prompt 模板类
    
    支持变量替换和消息格式化
    """
    
    def __init__(self, template: str, input_variables: Optional[List[str]] = None):
        """
        初始化 Prompt 模板
        
        Args:
            template: 模板字符串，使用 {variable} 或 {{variable}} 标记变量
            input_variables: 输入变量列表（可选，会自动检测）
        """
        self.template = template
        self.input_variables = input_variables or self._extract_variables(template)
    
    def _extract_variables(self, template: str) -> List[str]:
        """
        从模板中提取变量名
        
        支持 {var} 和 {{var}} 两种格式
        """
        # 匹配 {var} 格式（单大括号）
        single_brace = re.findall(r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}', template)
        # 匹配 {{var}} 格式（双大括号）
        double_brace = re.findall(r'\{\{([a-zA-Z_][a-zA-Z0-9_]*)\}\}', template)
        
        # 合并并去重
        variables = list(set(single_brace + double_brace))
        return variables
    
    def format(self, **kwargs) -> str:
        """
        格式化模板
        
        Args:
            **kwargs: 变量值
        
        Returns:
            格式化后的字符串
        """
        result = self.template
        
        # 替换变量
        for var in self.input_variables:
            value = kwargs.get(var, "")
            # 尝试双大括号格式
            result = result.replace(f"{{{{{var}}}}}", str(value))
            # 尝试单大括号格式
            result = result.replace(f"{{{var}}}", str(value))
        
        return result
    
    def format_messages(self, **kwargs) -> List[Dict[str, str]]:
        """
        格式化为消息列表
        
        Args:
            **kwargs: 变量值
        
        Returns:
            消息列表（单条消息）
        """
        content = self.format(**kwargs)
        return [{"role": "user", "content": content}]


class ChatPromptTemplate:
    """
    聊天 Prompt 模板
    
    支持多轮对话的 Prompt 构建
    """
    
    def __init__(self, messages: List[tuple]):
        """
        初始化聊天模板
        
        Args:
            messages: 消息列表，格式: [(role, template), ...]
                     role 可以是: "system", "user", "assistant", "human", "ai"
        """
        self.messages = []
        
        for role, template in messages:
            # 标准化角色名称
            normalized_role = self._normalize_role(role)
            
            # 创建模板
            if isinstance(template, str):
                prompt_template = PromptTemplate(template)
            else:
                prompt_template = template
            
            self.messages.append((normalized_role, prompt_template))
    
    def _normalize_role(self, role: str) -> str:
        """
        标准化角色名称
        
        Args:
            role: 原始角色名称
        
        Returns:
            标准化后的角色名称
        """
        role_mapping = {
            "human": "user",
            "ai": "assistant",
            "system": "system",
            "user": "user",
            "assistant": "assistant"
        }
        return role_mapping.get(role.lower(), role)
    
    def format_messages(self, **kwargs) -> List[Dict[str, str]]:
        """
        格式化为消息列表
        
        Args:
            **kwargs: 变量值
        
        Returns:
            格式化后的消息列表
        """
        formatted_messages = []
        
        for role, template in self.messages:
            content = template.format(**kwargs)
            formatted_messages.append({
                "role": role,
                "content": content
            })
        
        return formatted_messages
    
    @classmethod
    def from_messages(cls, messages: List[tuple]) -> "ChatPromptTemplate":
        """
        从消息列表创建模板
        
        Args:
            messages: 消息列表，格式: [(role, template), ...]
        
        Returns:
            ChatPromptTemplate 实例
        
        Examples:
            >>> template = ChatPromptTemplate.from_messages([
            ...     ("system", "You are a helpful assistant."),
            ...     ("user", "Tell me about {topic}")
            ... ])
            >>> messages = template.format_messages(topic="Python")
        """
        return cls(messages)
    
    @classmethod
    def from_template(cls, template: str, role: str = "user") -> "ChatPromptTemplate":
        """
        从单个模板创建
        
        Args:
            template: 模板字符串
            role: 角色（默认: user）
        
        Returns:
            ChatPromptTemplate 实例
        """
        return cls([(role, template)])
    
    def invoke(self, variables: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        执行 Prompt 模板，返回格式化后的消息列表
        
        Args:
            variables: 变量字典
        
        Returns:
            格式化后的消息列表
        """
        return self.format_messages(**variables)


def format_prompt_with_context(
    template: str,
    context: Dict[str, Any],
    escape_json: bool = True
) -> str:
    """
    使用上下文格式化 prompt
    
    Args:
        template: 模板字符串
        context: 上下文字典
        escape_json: 是否转义 JSON 代码块中的大括号
    
    Returns:
        格式化后的字符串
    """
    if escape_json:
        # 保护 JSON 代码块中的大括号
        template = _protect_json_braces(template)
    
    # 格式化模板
    prompt = PromptTemplate(template)
    result = prompt.format(**context)
    
    if escape_json:
        # 恢复 JSON 代码块中的大括号
        result = _restore_json_braces(result)
    
    return result


def _protect_json_braces(text: str) -> str:
    """
    保护 JSON 代码块中的大括号
    
    将 ```json ... ``` 中的 { } 替换为占位符
    """
    pattern = r'```json\s*(.*?)\s*```'
    
    def replace_braces(match):
        json_content = match.group(1)
        # 使用占位符替换
        json_content = json_content.replace('{', '<<<JSON_OPEN>>>')
        json_content = json_content.replace('}', '<<<JSON_CLOSE>>>')
        return f'```json\n{json_content}\n```'
    
    return re.sub(pattern, replace_braces, text, flags=re.DOTALL)


def _restore_json_braces(text: str) -> str:
    """恢复 JSON 代码块中的大括号"""
    text = text.replace('<<<JSON_OPEN>>>', '{')
    text = text.replace('<<<JSON_CLOSE>>>', '}')
    return text


def create_system_message(content: str) -> Dict[str, str]:
    """创建系统消息"""
    return {"role": "system", "content": content}


def create_user_message(content: str) -> Dict[str, str]:
    """创建用户消息"""
    return {"role": "user", "content": content}


def create_assistant_message(content: str) -> Dict[str, str]:
    """创建助手消息"""
    return {"role": "assistant", "content": content}


def messages_to_agentscope_format(
    messages: List[Dict[str, str]],
    agent_name: str = "assistant"
) -> List[Dict[str, Any]]:
    """
    将标准消息格式转换为 AgentScope 格式
    
    Args:
        messages: 标准消息列表 [{"role": str, "content": str}, ...]
        agent_name: Agent 名称
    
    Returns:
        AgentScope 格式消息列表
    """
    agentscope_messages = []
    
    for msg in messages:
        agentscope_messages.append({
            "name": agent_name,
            "content": msg["content"],
            "role": msg["role"],
            "metadata": {}
        })
    
    return agentscope_messages


def agentscope_to_standard_format(
    messages: List[Dict[str, Any]]
) -> List[Dict[str, str]]:
    """
    将 AgentScope 格式转换为标准消息格式
    
    Args:
        messages: AgentScope 格式消息列表
    
    Returns:
        标准消息列表
    """
    standard_messages = []
    
    for msg in messages:
        standard_messages.append({
            "role": msg.get("role", "assistant"),
            "content": msg.get("content", "")
        })
    
    return standard_messages

