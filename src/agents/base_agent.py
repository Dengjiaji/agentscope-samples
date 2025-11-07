"""
Base Agent - 所有 Agent 的基类
提供统一的接口和通用功能，兼容 AgentScope 框架
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from pathlib import Path

from ..graph.state import AgentState, AgentScopeMessage, create_message
from ..llm.agentscope_models import AgentScopeModelWrapper, ModelProvider


class BaseAgent(ABC):
    """
    Agent 基类
    
    兼容 AgentScope 框架的设计模式：
    - 使用 AgentScope 消息格式
    - 支持模型配置
    - 支持工具/服务函数注册
    """
    
    def __init__(
        self, 
        agent_id: str, 
        agent_type: str, 
        config: Optional[Dict[str, Any]] = None,
        model_config: Optional[Dict[str, Any]] = None
    ):
        """
        初始化 Base Agent
        
        Args:
            agent_id: Agent 的唯一标识符
            agent_type: Agent 类型（analyst, portfolio_manager, risk_manager等）
            config: 配置字典
            model_config: 模型配置字典，包含 model_name, model_provider, api_keys 等
        
        Examples:
            >>> class MyAgent(BaseAgent):
            ...     def __init__(self):
            ...         super().__init__(
            ...             "my_agent", 
            ...             "custom",
            ...             model_config={"model_name": "gpt-4o-mini", "model_provider": "OPENAI"}
            ...         )
            ...     
            ...     def execute(self, state):
            ...         return {"status": "success"}
        """
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.config = config or {}
        self.model_config = model_config or {}
        
        # 初始化模型（如果提供了配置）
        self._model = None
        if model_config:
            self._init_model(model_config)
        
        # 消息历史（AgentScope 风格）
        self.messages: List[AgentScopeMessage] = []
        
        # 工具/服务函数注册表
        self.tools: Dict[str, Any] = {}
        
        # Prompt loader
        self._prompt_loader = None
    
    def _init_model(self, model_config: Dict[str, Any]):
        """
        初始化 LLM 模型
        
        Args:
            model_config: 模型配置字典
        """
        model_name = model_config.get("model_name", "gpt-4o-mini")
        model_provider = model_config.get("model_provider", "OPENAI")
        api_keys = model_config.get("api_keys", {})
        
        self._model = AgentScopeModelWrapper(
            model_name=model_name,
            model_provider=model_provider,
            api_keys=api_keys
        )
    
    @property
    def model(self) -> Optional[AgentScopeModelWrapper]:
        """获取模型实例"""
        return self._model
    
    def register_tool(self, tool_name: str, tool_func: Any):
        """
        注册工具/服务函数
        
        Args:
            tool_name: 工具名称
            tool_func: 工具函数
        """
        self.tools[tool_name] = tool_func
    
    def call_tool(self, tool_name: str, **kwargs) -> Any:
        """
        调用已注册的工具
        
        Args:
            tool_name: 工具名称
            **kwargs: 工具参数
        
        Returns:
            工具执行结果
        """
        if tool_name not in self.tools:
            raise ValueError(f"Tool '{tool_name}' not registered")
        
        return self.tools[tool_name](**kwargs)
    
    def add_message(self, content: str, role: str = "assistant", metadata: Optional[Dict[str, Any]] = None):
        """
        添加消息到历史记录
        
        Args:
            content: 消息内容
            role: 角色
            metadata: 元数据
        """
        message = create_message(
            name=self.agent_id,
            content=content,
            role=role,
            metadata=metadata
        )
        self.messages.append(message)
    
    @property
    def prompt_loader(self):
        """获取 PromptLoader"""
        if self._prompt_loader is None:
            from .prompt_loader import PromptLoader
            self._prompt_loader = PromptLoader()
        return self._prompt_loader
    
    def load_prompt(self, prompt_name: str, variables: Optional[Dict[str, Any]] = None) -> str:
        """
        加载 Prompt 文件
        
        Args:
            prompt_name: Prompt 文件名（不含扩展名）
            variables: 用于渲染的变量字典
        
        Returns:
            渲染后的 prompt 字符串
        
        Examples:
            >>> agent = MyAgent()
            >>> prompt = agent.load_prompt("my_prompt", {"ticker": "AAPL"})
        """
        return self.prompt_loader.load_prompt(self.agent_type, prompt_name, variables)
    
    def load_config(self, config_name: str) -> Dict[str, Any]:
        """
        加载 YAML 配置文件
        
        Args:
            config_name: 配置文件名（不含扩展名）
        
        Returns:
            配置字典
        
        Examples:
            >>> agent = MyAgent()
            >>> config = agent.load_config("my_config")
        """
        return self.prompt_loader.load_yaml_config(self.agent_type, config_name)
    
    @abstractmethod
    def execute(self, state: AgentState) -> Dict[str, Any]:
        """
        执行 Agent 的主要逻辑
        
        Args:
            state: AgentState 对象（包含 messages, data, metadata）
        
        Returns:
            更新后的状态字典，包含 "messages" 和 "data" 键
        
        Examples:
            >>> def execute(self, state):
            ...     # 执行分析逻辑
            ...     result = self.analyze(state)
            ...     
            ...     # 创建 AgentScope 格式消息
            ...     message = create_message(
            ...         name=self.agent_id,
            ...         content=json.dumps(result),
            ...         role="assistant",
            ...         metadata={"timestamp": datetime.now().isoformat()}
            ...     )
            ...     
            ...     return {
            ...         "messages": [message],  # 会自动合并到 state["messages"]
            ...         "data": {"updated_field": "value"}
            ...     }
        """
        pass
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(agent_id='{self.agent_id}', agent_type='{self.agent_type}')>"

