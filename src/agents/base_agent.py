"""
Base Agent - 所有 Agent 的基类
提供统一的接口和通用功能
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pathlib import Path

from ..graph.state import AgentState


class BaseAgent(ABC):
    """Agent 基类"""
    # todo：继承 reactAgent注册
    # 直接super.__init__(),其中需要注意传入 model = {} 和 toolkit，toolkit 需要修改 LLMtoolselector进行注册，按照agentscope的逻辑
    
    def __init__(self, agent_id: str, agent_type: str, config: Optional[Dict[str, Any]] = None):
        """
        初始化 Base Agent
        
        Args:
            agent_id: Agent 的唯一标识符
            agent_type: Agent 类型（analyst, portfolio_manager, risk_manager等）
            config: 配置字典
        
        Examples:
            >>> class MyAgent(BaseAgent):
            ...     def __init__(self):
            ...         super().__init__("my_agent", "custom")
            ...     
            ...     def execute(self, state):
            ...         return {"status": "success"}
        """
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.config = config or {}

        
        # 延迟加载 prompt_loader 以避免循环导入
        self._prompt_loader = None
    
    @property
    def prompt_loader(self):
        """延迟加载 PromptLoader"""
        if self._prompt_loader is None:
            from .prompt_loader import get_prompt_loader
            self._prompt_loader = get_prompt_loader()
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
            state: AgentState 对象
        
        Returns:
            更新后的状态字典，包含 "messages" 和 "data" 键
        
        Examples:
            >>> def execute(self, state):
            ...     # 执行分析逻辑
            ...     result = self.analyze(state)
            ...     
            ...     # 创建消息
            ...     message = HumanMessage(content=json.dumps(result), name=self.agent_id)
            ...     
            ...     return {
            ...         "messages": state["messages"] + [message],
            ...         "data": state["data"]
            ...     }
        """
        pass
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(agent_id='{self.agent_id}', agent_type='{self.agent_type}')>"

