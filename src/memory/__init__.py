#!/usr/bin/env python3
"""
Memory module for IA project
基于mem0的智能记忆系统

整合后的模块结构：
- mem0_core: Mem0配置、集成和基础数据模型
- unified_memory: 完整的记忆系统实现（分析师、通信、通知）

兼容性导入：保持原有接口可用
"""

# 新的整合模块
from .mem0_core import Mem0Integration, mem0_integration
from .unified_memory import (
    Mem0AnalystMemory,
    Mem0AnalystMemoryManager,
    Mem0NotificationSystem,
    Mem0CommunicationMemory,
    Mem0MemoryManager,
    unified_memory_manager,
    mem0_memory_manager,
    mem0_notification_system,
    mem0_communication_memory
)

# 兼容性导入 - 保持原有代码可正常运行
try:
    # 如果旧文件还存在，导入它们以保持兼容性
    from .memory_manager import Mem0MemoryManager as LegacyMemoryManager
    from .analyst_memory import Mem0AnalystMemory as LegacyAnalystMemory
    from .communication_memory import Mem0CommunicationMemory as LegacyCommunicationMemory
except ImportError:
    # 如果旧文件已删除，使用新的实现
    LegacyMemoryManager = Mem0MemoryManager
    LegacyAnalystMemory = Mem0AnalystMemory
    LegacyCommunicationMemory = Mem0CommunicationMemory

__all__ = [
    # 核心组件
    'Mem0Integration',
    'mem0_integration',
    
    # 统一记忆系统
    'Mem0AnalystMemory',
    'Mem0AnalystMemoryManager', 
    'Mem0NotificationSystem',
    'Mem0CommunicationMemory',
    'Mem0MemoryManager',
    
    # 全局实例
    'unified_memory_manager',
    'mem0_memory_manager',
    'mem0_notification_system', 
    'mem0_communication_memory',
    
    # 兼容性
    'LegacyMemoryManager',
    'LegacyAnalystMemory',
    'LegacyCommunicationMemory'
]
