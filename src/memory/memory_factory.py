#!/usr/bin/env python3
"""
记忆系统工厂
根据环境变量创建相应的记忆框架实例
"""

import os
import logging
from typing import Optional

from src.memory.memory_interface import MemoryInterface

# 全局记忆实例
_memory_instance: Optional[MemoryInterface] = None
_current_framework: Optional[str] = None
_current_base_dir: Optional[str] = None


def get_memory_framework() -> str:
    """
    获取当前配置的记忆框架
    
    Returns:
        框架名称: 'mem0' 或 'reme'
    """
    framework = os.getenv('MEMORY_FRAMEWORK', 'mem0').lower()
    
    if framework not in ['mem0', 'reme']:
        logging.warning(f"未知的记忆框架: {framework}，使用默认值 mem0")
        return 'mem0'
    
    return framework


def create_memory_instance(base_dir: str, framework: Optional[str] = None) -> MemoryInterface:
    """
    创建记忆实例
    
    Args:
        base_dir: 基础目录 (config_name)
        framework: 指定框架名称，如果为None则从环境变量读取
        
    Returns:
        记忆实例
        
    Raises:
        ImportError: 如果框架不可用
        ValueError: 如果框架名称无效
    """
    if framework is None:
        framework = get_memory_framework()
    
    framework = framework.lower()
    
    logger = logging.getLogger(__name__)
    logger.info(f"创建记忆实例: framework={framework}, base_dir={base_dir}")
    
    if framework == 'mem0':
        try:
            from src.memory.mem0_adapter import Mem0Adapter
            return Mem0Adapter(base_dir)
        except ImportError as e:
            logger.error(f"无法导入Mem0适配器: {e}")
            raise ImportError(f"Mem0框架不可用: {e}")
    
    elif framework == 'reme':
        try:
            # 即使使用ReMe，也需要初始化mem0_integration作为占位
            # 因为某些旧代码可能still依赖它
            from src.memory.mem0_core import initialize_mem0_integration
            initialize_mem0_integration(base_dir)
            logger.info("已初始化Mem0Integration作为占位（使用ReMe框架）")
            
            from src.memory.reme_adapter import ReMeAdapter
            return ReMeAdapter(base_dir)
        except ImportError as e:
            logger.error(f"无法导入ReMe适配器: {e}")
            raise ImportError(f"ReMe框架不可用: {e}. 请安装 flowllm 包")
    
    else:
        raise ValueError(f"不支持的记忆框架: {framework}")


def initialize_memory_system(base_dir: str, framework: Optional[str] = None, streamer=None) -> MemoryInterface:
    """
    初始化全局记忆系统
    
    Args:
        base_dir: 基础目录 (config_name)
        framework: 指定框架名称，如果为None则从环境变量读取
        streamer: 可选的streamer用于输出初始化信息
        
    Returns:
        记忆实例
    """
    global _memory_instance, _current_framework, _current_base_dir
    
    if framework is None:
        framework = get_memory_framework()
    
    # 检查是否需要重新创建实例
    if (_memory_instance is not None and 
        _current_framework == framework and 
        _current_base_dir == base_dir):
        # 已存在相同配置的实例，直接返回
        if streamer:
            streamer.print("system", f"记忆系统已存在: {framework} ({base_dir})")
        return _memory_instance
    
    # 创建新实例
    _memory_instance = create_memory_instance(base_dir, framework)
    _current_framework = framework
    _current_base_dir = base_dir
    
    logger = logging.getLogger(__name__)
    logger.info(f"全局记忆系统已初始化: {framework} ({base_dir})")
    
    # 构建并输出记忆系统初始化信息（一次性输出）
    if streamer:
        message_lines = [f"记忆系统初始化: {framework} ({base_dir})"]
        
        # 检查并添加workspace加载信息
        if hasattr(_memory_instance, 'get_loaded_workspaces'):
            loaded_workspaces = _memory_instance.get_loaded_workspaces()
            if loaded_workspaces:
                message_lines.append(f"成功加载 {len(loaded_workspaces)} 个workspace的已有记忆:")
                message_lines.extend([f"  - {ws}" for ws in loaded_workspaces])
            else:
                message_lines.append("开始新记忆（未找到已有workspace记忆）")
        
        # 一次性输出所有信息
        streamer.print("system", "\n".join(message_lines))
    
    return _memory_instance


def get_memory_instance() -> Optional[MemoryInterface]:
    """
    获取全局记忆实例
    
    Returns:
        记忆实例，如果未初始化则返回None
    """
    global _memory_instance
    
    if _memory_instance is None:
        logger = logging.getLogger(__name__)
        logger.warning("记忆系统尚未初始化，请先调用 initialize_memory_system()")
    
    return _memory_instance


def reset_memory_system():
    """重置全局记忆系统（主要用于测试）"""
    global _memory_instance, _current_framework, _current_base_dir
    
    _memory_instance = None
    _current_framework = None
    _current_base_dir = None
    
    logger = logging.getLogger(__name__)
    logger.info("全局记忆系统已重置")


def get_current_framework_name() -> Optional[str]:
    """
    获取当前使用的框架名称
    
    Returns:
        框架名称，如果未初始化则返回None
    """
    global _current_framework
    return _current_framework


# 便利函数，保持向后兼容
def initialize_mem0_integration(base_dir: str) -> MemoryInterface:
    """
    初始化记忆集成（兼容旧接口）
    
    Args:
        base_dir: 基础目录
        
    Returns:
        记忆实例
    """
    return initialize_memory_system(base_dir)


def get_mem0_integration() -> Optional[MemoryInterface]:
    """
    获取记忆集成实例（兼容旧接口）
    
    Returns:
        记忆实例
    """
    return get_memory_instance()


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 60)
    print("记忆系统工厂测试")
    print("=" * 60)
    
    # 测试获取框架名称
    framework = get_memory_framework()
    print(f"\n当前配置的框架: {framework}")
    
    # 测试环境变量
    print(f"\n环境变量 MEMORY_FRAMEWORK: {os.getenv('MEMORY_FRAMEWORK', '未设置')}")
    
    print("\n提示: 设置环境变量 MEMORY_FRAMEWORK=reme 可切换到ReMe框架")
    print("=" * 60)

