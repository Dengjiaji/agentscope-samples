"""
AgentScope 工具/服务函数包装器

提供与 AgentScope 兼容的工具调用接口
"""
from typing import Dict, Any, List, Optional, Callable
import json
from functools import wraps


class ServiceFunction:
    """
    AgentScope 服务函数包装器
    
    将现有的工具函数包装为 AgentScope 兼容的服务函数
    """
    
    def __init__(
        self,
        name: str,
        func: Callable,
        description: str,
        parameters: Dict[str, Any]
    ):
        """
        初始化服务函数
        
        Args:
            name: 函数名称
            func: 实际的函数
            description: 函数描述
            parameters: 参数 schema（JSON Schema 格式）
        """
        self.name = name
        self.func = func
        self.description = description
        self.parameters = parameters
    
    def __call__(self, **kwargs) -> Any:
        """调用服务函数"""
        return self.func(**kwargs)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式（用于 LLM 工具调用）"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }
    
    def to_openai_function_schema(self) -> Dict[str, Any]:
        """转换为 OpenAI Function Calling 格式"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }


class ServiceToolkit:
    """
    服务函数工具包
    
    管理和调用多个服务函数
    """
    
    def __init__(self):
        """初始化工具包"""
        self.functions: Dict[str, ServiceFunction] = {}
    
    def register(
        self,
        name: str,
        func: Callable,
        description: str,
        parameters: Dict[str, Any]
    ):
        """
        注册服务函数
        
        Args:
            name: 函数名称
            func: 函数实现
            description: 函数描述
            parameters: 参数 schema
        """
        service_func = ServiceFunction(name, func, description, parameters)
        self.functions[name] = service_func
    
    def call(self, name: str, **kwargs) -> Any:
        """
        调用服务函数
        
        Args:
            name: 函数名称
            **kwargs: 函数参数
        
        Returns:
            函数执行结果
        """
        if name not in self.functions:
            raise ValueError(f"Service function '{name}' not found")
        
        return self.functions[name](**kwargs)
    
    def get_function_schemas(self) -> List[Dict[str, Any]]:
        """
        获取所有函数的 schema（用于 LLM）
        
        Returns:
            函数 schema 列表
        """
        return [func.to_openai_function_schema() for func in self.functions.values()]
    
    def list_functions(self) -> List[str]:
        """列出所有已注册的函数名称"""
        return list(self.functions.keys())
    
    def get_function(self, name: str) -> Optional[ServiceFunction]:
        """获取指定名称的服务函数"""
        return self.functions.get(name)


def parse_tool_calls(response_content: str) -> List[Dict[str, Any]]:
    """
    解析 LLM 响应中的工具调用
    
    Args:
        response_content: LLM 响应内容
    
    Returns:
        工具调用列表
    """
    tool_calls = []
    
    try:
        # 尝试解析 JSON 格式的工具调用
        parsed = json.loads(response_content)
        
        if isinstance(parsed, dict):
            # 单个工具调用
            if "tool_name" in parsed and "arguments" in parsed:
                tool_calls.append({
                    "name": parsed["tool_name"],
                    "arguments": parsed["arguments"]
                })
            # 多个工具调用
            elif "tool_calls" in parsed:
                for call in parsed["tool_calls"]:
                    tool_calls.append({
                        "name": call.get("tool_name") or call.get("name"),
                        "arguments": call.get("arguments") or call.get("args", {})
                    })
        elif isinstance(parsed, list):
            # 工具调用列表
            for call in parsed:
                if isinstance(call, dict):
                    tool_calls.append({
                        "name": call.get("tool_name") or call.get("name"),
                        "arguments": call.get("arguments") or call.get("args", {})
                    })
    except json.JSONDecodeError:
        pass
    
    return tool_calls


def execute_tool_calls(
    tool_calls: List[Dict[str, Any]],
    toolkit: ServiceToolkit
) -> List[Dict[str, Any]]:
    """
    执行工具调用
    
    Args:
        tool_calls: 工具调用列表
        toolkit: 服务函数工具包
    
    Returns:
        执行结果列表
    """
    results = []
    
    for call in tool_calls:
        tool_name = call.get("name")
        arguments = call.get("arguments", {})
        
        try:
            result = toolkit.call(tool_name, **arguments)
            results.append({
                "tool_name": tool_name,
                "status": "success",
                "result": result
            })
        except Exception as e:
            results.append({
                "tool_name": tool_name,
                "status": "error",
                "error": str(e)
            })
    
    return results


def service_function(
    name: str,
    description: str,
    parameters: Optional[Dict[str, Any]] = None
):
    """
    装饰器：将函数注册为服务函数
    
    Args:
        name: 函数名称
        description: 函数描述
        parameters: 参数 schema（可选）
    
    Examples:
        >>> @service_function(
        ...     name="get_stock_price",
        ...     description="Get current stock price",
        ...     parameters={
        ...         "type": "object",
        ...         "properties": {
        ...             "ticker": {"type": "string", "description": "Stock ticker"}
        ...         },
        ...         "required": ["ticker"]
        ...     }
        ... )
        ... def get_stock_price(ticker: str) -> float:
        ...     return 150.0
    """
    def decorator(func: Callable) -> ServiceFunction:
        return ServiceFunction(
            name=name,
            func=func,
            description=description,
            parameters=parameters or {
                "type": "object",
                "properties": {},
                "required": []
            }
        )
    return decorator


# 全局工具包实例
_global_toolkit = ServiceToolkit()


def get_global_toolkit() -> ServiceToolkit:
    """获取全局工具包实例"""
    return _global_toolkit


def register_global_service(
    name: str,
    func: Callable,
    description: str,
    parameters: Dict[str, Any]
):
    """
    注册全局服务函数
    
    Args:
        name: 函数名称
        func: 函数实现
        description: 函数描述
        parameters: 参数 schema
    """
    _global_toolkit.register(name, func, description, parameters)

