#!/usr/bin/env python3
"""
记忆框架桥接器
提供统一的接口，自动根据当前框架返回正确的记忆管理器
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class MemoryManagerBridge:
    """
    记忆管理器桥接器
    根据当前使用的框架，自动路由到 Mem0 或 ReMe 的记忆管理器
    """
    
    def __init__(self):
        self._framework = None
        self._mem0_manager = None
        self._reme_adapter = None
        self._reme_notification_system = None  # 缓存 ReMe 通知系统实例（单例）
    
    def _get_current_framework(self) -> str:
        """获取当前使用的框架"""
        if self._framework is None:
            from src.memory.memory_factory import get_current_framework_name
            self._framework = get_current_framework_name()
            
            # 如果工厂还没初始化，从环境变量读取
            if self._framework is None:
                from src.memory.memory_factory import get_memory_framework
                self._framework = get_memory_framework()
        
        return self._framework
    
    def _get_mem0_manager(self):
        """获取 Mem0 管理器"""
        if self._mem0_manager is None:
            from src.memory.unified_memory import get_unified_memory_manager
            self._mem0_manager = get_unified_memory_manager()
        return self._mem0_manager
    
    def _get_reme_adapter(self):
        """获取 ReMe 适配器"""
        if self._reme_adapter is None:
            from src.memory.memory_factory import get_memory_instance
            self._reme_adapter = get_memory_instance()
        return self._reme_adapter
    
    def _get_active_manager(self):
        """获取当前激活的管理器"""
        framework = self._get_current_framework()
        
        if framework == 'reme':
            logger.debug("使用 ReMe 适配器")
            return self._get_reme_adapter()
        else:
            logger.debug("使用 Mem0 管理器")
            return self._get_mem0_manager()
    
    # 代理所有方法到实际的管理器
    def register_analyst(self, analyst_id: str, analyst_name: str = None):
        """注册分析师"""
        framework = self._get_current_framework()
        
        if framework == 'reme':
            # ✅ ReMe 也需要注册到通知系统（虽然 workspace 会自动创建）
            logger.info(f"ReMe框架自动管理分析师workspace: {analyst_id}")
            # 注册到通知系统，以便广播通知时能遍历所有 agents
            self.notification_system.register_agent(analyst_id, analyst_name)
            return
        else:
            manager = self._get_mem0_manager()
            return manager.register_analyst(analyst_id, analyst_name)
    
    def start_analysis_session(self, analyst_id: str, session_type: str, tickers: list, context: dict = None):
        """开始分析会话"""
        framework = self._get_current_framework()
        
        if framework == 'reme':
            # ReMe 使用简化的记忆存储
            adapter = self._get_reme_adapter()
            session_info = {
                "session_type": session_type,
                "tickers": tickers,
                "context": context or {}
            }
            adapter.add(
                messages=f"开始{session_type}会话，标的: {','.join(tickers)}",
                user_id=analyst_id,
                metadata=session_info
            )
            # 返回一个假的session_id（兼容性）
            import uuid
            return str(uuid.uuid4())
        else:
            manager = self._get_mem0_manager()
            return manager.start_analysis_session(analyst_id, session_type, tickers, context)
    
    def add_analysis_message(self, analyst_id: str, session_id: str, role: str, content: str, metadata: dict = None):
        """添加分析消息"""
        framework = self._get_current_framework()
        
        if framework == 'reme':
            adapter = self._get_reme_adapter()
            adapter.add(
                messages=[{"role": role, "content": content}],
                user_id=analyst_id,
                metadata=metadata or {}
            )
        else:
            manager = self._get_mem0_manager()
            manager.add_analysis_message(analyst_id, session_id, role, content, metadata)
    
    def complete_analysis_session(self, analyst_id: str, session_id: str, final_result: dict):
        """完成分析会话"""
        framework = self._get_current_framework()
        
        if framework == 'reme':
            adapter = self._get_reme_adapter()
            adapter.add(
                messages=f"完成分析会话，结果: {str(final_result)[:200]}",
                user_id=analyst_id,
                metadata={"session_id": session_id, "final_result": final_result}
            )
        else:
            manager = self._get_mem0_manager()
            manager.complete_analysis_session(analyst_id, session_id, final_result)
    
    def get_analyst_memory(self, analyst_id: str):
        """获取分析师记忆对象"""
        framework = self._get_current_framework()
        
        if framework == 'reme':
            # ReMe 返回一个简化的记忆对象
            from src.memory.reme_memory_adapter import ReMeAnalystMemory
            return ReMeAnalystMemory(analyst_id, self._get_reme_adapter())
        else:
            manager = self._get_mem0_manager()
            return manager.get_analyst_memory(analyst_id)
    
    def get_relevant_memories(self, analyst_id: str, query: str, limit: int = 10):
        """获取相关记忆"""
        framework = self._get_current_framework()
        
        if framework == 'reme':
            adapter = self._get_reme_adapter()
            results = adapter.search(query=query, user_id=analyst_id, top_k=limit)
            return results.get('results', [])
        else:
            manager = self._get_mem0_manager()
            return manager.get_relevant_memories(analyst_id, query, limit)
    
    @property
    def notification_system(self):
        """获取通知系统（单例模式）"""
        framework = self._get_current_framework()
        
        if framework == 'reme':
            # ✅ 使用缓存的实例，避免每次都创建新实例（导致 _registered_agents 丢失）
            if self._reme_notification_system is None:
                from src.memory.reme_memory_adapter import ReMeNotificationSystem
                self._reme_notification_system = ReMeNotificationSystem(self._get_reme_adapter())
                logger.info("创建 ReMeNotificationSystem 单例实例")
            return self._reme_notification_system
        else:
            manager = self._get_mem0_manager()
            return manager.notification_system
    
    def broadcast_notification(self, sender_agent: str, content: str, urgency: str = "medium", 
                             category: str = "general", backtest_date: str = None):
        """
        广播通知
        
        ✅ 对齐修改：ReMe 和 Mem0 都使用相同的 user_id，通过 metadata.type 区分
        """
        framework = self._get_current_framework()
        
        if framework == 'reme':
            # ✅ 使用 ReMeNotificationSystem，它已经对齐了 Mem0 的设计
            # 注意：使用 notification_system 属性（@property），而不是方法
            notification_system = self.notification_system
            return notification_system.broadcast_notification(
                sender_agent=sender_agent,
                content=content,
                urgency=urgency,
                category=category,
                backtest_date=backtest_date
            )
        else:
            manager = self._get_mem0_manager()
            return manager.broadcast_notification(sender_agent, content, urgency, category, backtest_date)
    
    # 添加其他必要的方法...
    def __getattr__(self, name):
        """代理其他方法到实际的管理器"""
        framework = self._get_current_framework()
        
        if framework == 'reme':
            logger.warning(f"ReMe框架不支持方法: {name}，使用Mem0兼容模式")
            # 对于不支持的方法，降级到 Mem0
            manager = self._get_mem0_manager()
        else:
            manager = self._get_mem0_manager()
        
        return getattr(manager, name)


# 创建全局桥接器实例
_memory_bridge = None

def get_memory_bridge() -> MemoryManagerBridge:
    """获取全局记忆管理器桥接器"""
    global _memory_bridge
    if _memory_bridge is None:
        _memory_bridge = MemoryManagerBridge()
    return _memory_bridge

