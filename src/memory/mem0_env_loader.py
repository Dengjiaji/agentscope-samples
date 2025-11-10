#!/usr/bin/env python3
"""
Mem0环境变量加载工具
统一管理Mem0相关的环境变量加载
"""

import os
from dotenv import load_dotenv
from typing import Optional


class Mem0EnvLoader:
    """Mem0环境变量加载器"""
    
    _instance = None
    _loaded = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._loaded:
            self.load_mem0_env()
            self._loaded = True
    
    def load_mem0_env(self) -> bool:
        """
        加载Mem0专用环境变量
        
        Returns:
            bool: 是否成功加载环境文件
        """
        # 如果已经加载过，直接返回
        if self._loaded:
            return True
            
        # 获取项目根目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_dir))
        mem0_env_path = os.path.join(project_root, '.env')
        
        if os.path.exists(mem0_env_path):
            load_dotenv(mem0_env_path, override=True)
            print(f"✅ 已加载Mem0环境配置: {mem0_env_path}")
            self._loaded = True
            return True
        else:
            print(f"⚠️ 未找到Mem0环境文件: {mem0_env_path}")
            print("请创建 .env 文件并配置必要的环境变量")
            return False
    
    def get_mem0_config_value(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        获取Mem0配置值
        
        Args:
            key: 环境变量键名
            default: 默认值
            
        Returns:
            str: 配置值
        """
        return os.getenv(key, default)
    
    def check_required_vars(self) -> bool:
        """
        检查必需的环境变量是否设置
        
        Returns:
            bool: 是否所有必需变量都已设置
        """
        required_vars = [
            'OPENAI_API_KEY',
            'OPENAI_BASE_URL'
        ]
        
        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            print("❌ 缺少必需的环境变量：")
            for var in missing_vars:
                print(f"   - {var}")
            print("\n请在 .mem0_env 文件中配置这些变量")
            return False
        
        return True
    
    def get_storage_paths(self) -> dict:
        """
        获取存储路径配置
        
        Returns:
            dict: 存储路径配置
        """
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_dir))
        
        memory_data_dir = os.getenv('MEMORY_DATA_DIR', os.path.join(project_root, 'memory_data'))
        
        return {
            'memory_data_dir': memory_data_dir,
            'history_db_path': os.path.join(memory_data_dir, os.getenv('MEMORY_HISTORY_DB', 'ia_memory_history.db')),
            'vector_db_path': os.path.join(memory_data_dir, os.getenv('MEMORY_VECTOR_DB', 'ia_chroma_db'))
        }


# 全局实例
mem0_env_loader = Mem0EnvLoader()


def ensure_mem0_env_loaded():
    """确保Mem0环境变量已加载"""
    return mem0_env_loader.load_mem0_env()


def get_mem0_env(key: str, default: Optional[str] = None) -> Optional[str]:
    """获取Mem0环境变量值"""
    return mem0_env_loader.get_mem0_config_value(key, default)


def check_mem0_env() -> bool:
    """检查Mem0环境变量是否完整"""
    return mem0_env_loader.check_required_vars()
