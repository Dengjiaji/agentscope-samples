#!/usr/bin/env python3
"""
日志配置模块 - 统一管理项目的日志设置
"""

import logging
import os


def setup_logging(level=logging.WARNING, log_file=None, quiet_mode=True):
    """
    设置项目日志配置
    
    Args:
        level: 日志级别，默认WARNING
        log_file: 日志文件路径，如果为None则不写入文件
        quiet_mode: 是否启用安静模式，禁用HTTP请求等详细日志
    """
    handlers = []
    
    # 添加控制台处理器
    handlers.append(logging.StreamHandler())
    
    # 添加文件处理器（如果指定）
    if log_file:
        # 获取目录路径，如果文件在当前目录则跳过目录创建
        log_dir = os.path.dirname(log_file)
        if log_dir:  # 只有当目录路径不为空时才创建目录
            os.makedirs(log_dir, exist_ok=True)
        handlers.append(logging.FileHandler(log_file))
    
    # 配置基础日志
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=handlers,
        force=True  # 强制重新配置，覆盖之前的设置
    )
    
    # 安静模式：禁用第三方库的详细日志
    if quiet_mode:
        # HTTP请求相关
        logging.getLogger('httpx').setLevel(logging.WARNING)
        logging.getLogger('openai').setLevel(logging.WARNING)
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('requests').setLevel(logging.WARNING)
        
        # AI/ML相关
        logging.getLogger('transformers').setLevel(logging.WARNING)
        logging.getLogger('torch').setLevel(logging.WARNING)
        
        # 数据处理相关
        logging.getLogger('pandas').setLevel(logging.WARNING)
        logging.getLogger('numpy').setLevel(logging.WARNING)
        
        # 网络相关
        logging.getLogger('asyncio').setLevel(logging.WARNING)
        logging.getLogger('aiohttp').setLevel(logging.WARNING)


def enable_debug_logging():
    """启用调试模式日志"""
    logging.getLogger().setLevel(logging.DEBUG)
    logging.info("调试模式已启用")


def disable_all_logging():
    """完全禁用日志输出"""
    logging.disable(logging.CRITICAL)


def enable_verbose_logging():
    """启用详细日志输出"""
    logging.getLogger().setLevel(logging.INFO)
    # 重新启用一些有用的日志
    logging.getLogger('httpx').setLevel(logging.INFO)
    logging.getLogger('openai').setLevel(logging.INFO)
