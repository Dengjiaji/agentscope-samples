"""
Agent Registry - Agent 注册中心
支持动态注册和创建 Agent，便于扩展和管理
"""
from typing import Dict, Type, Callable, Optional, Any
from .base_agent import BaseAgent


class AgentRegistry:
    """Agent 注册中心 - 管理所有可用的 Agent"""
    
    def __init__(self):
        """初始化注册中心"""
        self._agents: Dict[str, Type[BaseAgent]] = {}
        self._factories: Dict[str, Callable] = {}
        self._agent_metadata: Dict[str, Dict[str, Any]] = {}
    
    def register_agent(self, agent_name: str, agent_class: Type[BaseAgent],
                      metadata: Optional[Dict[str, Any]] = None):
        """
        注册 Agent 类
        
        Args:
            agent_name: Agent 名称（用于创建时引用）
            agent_class: Agent 类
            metadata: Agent 元数据（描述、分类等）
        
        Examples:
            >>> registry = AgentRegistry()
            >>> registry.register_agent("my_analyst", MyAnalystAgent, {
            ...     "category": "analyst",
            ...     "description": "My custom analyst"
            ... })
        """
        self._agents[agent_name] = agent_class
        if metadata:
            self._agent_metadata[agent_name] = metadata
        
        print(f"✅ Agent registered: {agent_name} -> {agent_class.__name__}")
    
    def register_factory(self, agent_name: str, factory_func: Callable,
                        metadata: Optional[Dict[str, Any]] = None):
        """
        注册 Agent 工厂函数
        
        Args:
            agent_name: Agent 名称
            factory_func: 工厂函数，调用时返回 Agent 实例
            metadata: Agent 元数据
        
        Examples:
            >>> def create_my_agent(**kwargs):
            ...     return MyAgent(**kwargs)
            >>> 
            >>> registry.register_factory("my_agent", create_my_agent)
        """
        self._factories[agent_name] = factory_func
        if metadata:
            self._agent_metadata[agent_name] = metadata
        
        print(f"✅ Factory registered: {agent_name}")
    
    def create_agent(self, agent_name: str, **kwargs) -> BaseAgent:
        """
        创建 Agent 实例
        
        Args:
            agent_name: Agent 名称
            **kwargs: 传递给 Agent 构造函数或工厂函数的参数
        
        Returns:
            Agent 实例
        
        Raises:
            ValueError: 如果 Agent 名称未注册
        
        Examples:
            >>> agent = registry.create_agent("technical_analyst")
            >>> agent = registry.create_agent("my_custom_agent", threshold=0.7)
        """
        if agent_name in self._factories:
            return self._factories[agent_name](**kwargs)
        elif agent_name in self._agents:
            return self._agents[agent_name](**kwargs)
        else:
            raise ValueError(
                f"Unknown agent: {agent_name}\n"
                f"Available agents: {self.list_agents()}"
            )
    
    def is_registered(self, agent_name: str) -> bool:
        """检查 Agent 是否已注册"""
        return agent_name in self._agents or agent_name in self._factories
    
    def list_agents(self) -> list[str]:
        """列出所有已注册的 Agent 名称"""
        return sorted(list(self._agents.keys()) + list(self._factories.keys()))
    
    def get_agent_info(self, agent_name: str) -> Dict[str, Any]:
        """
        获取 Agent 信息
        
        Args:
            agent_name: Agent 名称
        
        Returns:
            Agent 信息字典
        """
        if not self.is_registered(agent_name):
            raise ValueError(f"Agent not registered: {agent_name}")
        
        info = {
            "name": agent_name,
            "type": "class" if agent_name in self._agents else "factory",
        }
        
        if agent_name in self._agents:
            info["class"] = self._agents[agent_name].__name__
        
        if agent_name in self._agent_metadata:
            info.update(self._agent_metadata[agent_name])
        
        return info
    
    def list_agents_by_category(self, category: str) -> list[str]:
        """
        按类别列出 Agent
        
        Args:
            category: Agent 类别（analyst, portfolio_manager, risk_manager, custom）
        
        Returns:
            该类别的 Agent 名称列表
        """
        result = []
        for agent_name in self.list_agents():
            metadata = self._agent_metadata.get(agent_name, {})
            if metadata.get("category") == category:
                result.append(agent_name)
        return result
    
    def unregister(self, agent_name: str):
        """
        注销 Agent
        
        Args:
            agent_name: Agent 名称
        """
        if agent_name in self._agents:
            del self._agents[agent_name]
        if agent_name in self._factories:
            del self._factories[agent_name]
        if agent_name in self._agent_metadata:
            del self._agent_metadata[agent_name]
        
        print(f"✅ Agent unregistered: {agent_name}")
    
    def clear(self):
        """清空所有注册的 Agent"""
        self._agents.clear()
        self._factories.clear()
        self._agent_metadata.clear()
        print("✅ All agents cleared from registry")


# 全局注册中心实例
_global_registry: Optional[AgentRegistry] = None


def get_registry() -> AgentRegistry:
    """
    获取全局注册中心实例
    
    Returns:
        AgentRegistry 实例
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = AgentRegistry()
        _register_builtin_agents(_global_registry)
    return _global_registry


def register_agent(name: str, metadata: Optional[Dict[str, Any]] = None):
    """
    装饰器：注册 Agent 类
    
    Args:
        name: Agent 名称
        metadata: Agent 元数据
    
    Examples:
        >>> @register_agent("momentum_analyst", metadata={"category": "analyst"})
        ... class MomentumAnalyst(BaseAgent):
        ...     def execute(self, state):
        ...         pass
    """
    def decorator(cls):
        get_registry().register_agent(name, cls, metadata)
        return cls
    return decorator


def register_factory(name: str, metadata: Optional[Dict[str, Any]] = None):
    """
    装饰器：注册工厂函数
    
    Args:
        name: Agent 名称
        metadata: Agent 元数据
    
    Examples:
        >>> @register_factory("custom_analyst")
        ... def create_custom_analyst(**kwargs):
        ...     return CustomAnalyst(**kwargs)
    """
    def decorator(func):
        get_registry().register_factory(name, func, metadata)
        return func
    return decorator


def _register_builtin_agents(registry: AgentRegistry):
    """注册内置的 Agent"""
    from .analyst_agent import (
        create_fundamental_analyst,
        create_technical_analyst,
        create_sentiment_analyst,
        create_valuation_analyst,
        create_comprehensive_analyst
    )
    from .portfolio_manager_agent import PortfolioManagerAgent
    from .risk_manager_agent import RiskManagerAgent
    
    # 注册分析师
    registry.register_factory(
        "fundamental_analyst",
        create_fundamental_analyst,
        {
            "category": "analyst",
            "description": "基本面分析师 - 专注于公司财务和基本面分析"
        }
    )
    
    registry.register_factory(
        "technical_analyst",
        create_technical_analyst,
        {
            "category": "analyst",
            "description": "技术分析师 - 专注于技术指标和图表分析"
        }
    )
    
    registry.register_factory(
        "sentiment_analyst",
        create_sentiment_analyst,
        {
            "category": "analyst",
            "description": "情绪分析师 - 分析市场情绪和投资者行为"
        }
    )
    
    registry.register_factory(
        "valuation_analyst",
        create_valuation_analyst,
        {
            "category": "analyst",
            "description": "估值分析师 - 专注于公司估值和价值评估"
        }
    )
    
    registry.register_factory(
        "comprehensive_analyst",
        create_comprehensive_analyst,
        {
            "category": "analyst",
            "description": "综合分析师 - 整合多维度分析视角"
        }
    )
    
    # 注册投资组合管理器
    registry.register_agent(
        "portfolio_manager",
        PortfolioManagerAgent,
        {
            "category": "portfolio_manager",
            "description": "投资组合管理器 - 方向决策和数量管理"
        }
    )
    
    # 注册风险管理器
    registry.register_agent(
        "risk_manager",
        RiskManagerAgent,
        {
            "category": "risk_manager",
            "description": "风险管理器 - 风险评估和仓位控制"
        }
    )
    
    print("✅ Built-in agents registered")


# 便捷函数
def create_agent(agent_name: str, **kwargs) -> BaseAgent:
    """
    便捷函数：创建 Agent
    
    Args:
        agent_name: Agent 名称
        **kwargs: Agent 参数
    
    Returns:
        Agent 实例
    """
    return get_registry().create_agent(agent_name, **kwargs)


def list_available_agents() -> list[str]:
    """列出所有可用的 Agent"""
    return get_registry().list_agents()

