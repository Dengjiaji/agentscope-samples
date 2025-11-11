#!/usr/bin/env python3
"""
Memory Manager - 超简单的记忆管理器
根据环境变量创建对应的记忆实例
"""

import os
import logging
from typing import Optional, Dict

from .base import LongTermMemory
from .mem0_memory import Mem0Memory
from .reme_memory import ReMeMemory


logger = logging.getLogger(__name__)


# 全局实例缓存（支持多个base_dir）
_memory_instances: Dict[str, LongTermMemory] = {}


def get_memory(base_dir: str) -> LongTermMemory:
    """
    获取记忆实例（按base_dir缓存）
    
    Args:
        base_dir: 基础目录（config_name）
        
    Returns:
        记忆实例
    """
    global _memory_instances
    
    logger.debug(f"[MemoryManager] get_memory(base_dir={base_dir})")
    
    # 如果已存在该base_dir的实例，直接返回
    if base_dir in _memory_instances:
        logger.debug(f"   返回缓存的实例: {type(_memory_instances[base_dir]).__name__}")
        return _memory_instances[base_dir]
    
    # 从环境变量获取框架类型
    framework = os.getenv('MEMORY_FRAMEWORK', 'mem0').lower()
    
    logger.info(f"   创建新记忆实例: {framework} ({base_dir})")
    
    if framework == 'reme':
        _memory_instances[base_dir] = ReMeMemory(base_dir)
    else:
        _memory_instances[base_dir] = Mem0Memory(base_dir)
    
    logger.debug(f"   ✅ 记忆实例已创建: {type(_memory_instances[base_dir]).__name__}")
    
    return _memory_instances[base_dir]


def reset_memory():
    """重置全局记忆实例（主要用于测试）"""
    global _memory_instances
    _memory_instances.clear()
    
    # 如果使用的是 ReMeMemory，还需要重置其全局向量存储
    framework = os.getenv('MEMORY_FRAMEWORK', 'mem0').lower()
    if framework == 'reme':
        ReMeMemory.reset_global_store()


def reset_analyst_memory(analyst_id: str, base_dir: str) -> bool:
    """
    重置指定分析师的记忆
    
    Args:
        analyst_id: 分析师ID
        base_dir: 基础目录（config_name）
        
    Returns:
        是否成功
    """
    memory = get_memory(base_dir)
    success = memory.delete_all(analyst_id)
    
    if success:
        logger.info(f"已重置分析师 {analyst_id} 的记忆")
    else:
        logger.error(f"重置分析师 {analyst_id} 的记忆失败")
    
    return success

