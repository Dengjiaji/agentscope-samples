#!/usr/bin/env python3
"""
Mem0 记忆框架适配器
将现有的 Mem0Integration 适配到统一的记忆接口
"""

import os
import logging
from typing import Dict, List, Any, Optional

from src.memory.memory_interface import MemoryInterface
from src.memory.mem0_core import Mem0Integration, initialize_mem0_integration


class Mem0Adapter(MemoryInterface):
    """Mem0框架适配器"""
    
    def __init__(self, base_dir: str):
        """
        初始化Mem0适配器
        
        Args:
            base_dir: 基础目录 (config_name)
        """
        self.base_dir = base_dir
        
        # 初始化Mem0Integration（同时更新全局实例）
        self.mem0_integration = initialize_mem0_integration(base_dir)
        
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Mem0适配器已初始化 (base_dir: {base_dir})")
    
    def get_memory_instance(self, user_id: str):
        """获取底层的Mem0 Memory实例"""
        return self.mem0_integration.get_memory_instance(user_id)
    
    def add(self, messages: str | List[Dict[str, Any]], user_id: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """添加记忆"""
        memory = self.get_memory_instance(user_id)
        
        # Mem0的add方法
        result = memory.add(
            messages=messages,
            user_id=user_id,
            metadata=metadata
        )
        
        self.logger.info(f"添加记忆: user={user_id}")
        
        return result
            
        
    
    def search(self, query: str, user_id: str, top_k: int = 5, **kwargs) -> Dict[str, Any]:
        """搜索记忆"""
        memory = self.get_memory_instance(user_id)
        # Mem0的search方法
        result = memory.search(
            query=query,
            user_id=user_id,
            limit=top_k
        )
        
        self.logger.info(f"搜索记忆: user={user_id}, query='{query[:50]}...'")

        return result
            
    
    
    def update(self, memory_id: str, data: str | Dict[str, Any]) -> Dict[str, Any]:
        """更新记忆"""
        memory = self.get_memory_instance("shared_analysts")
        
        # Mem0的update方法
        result = memory.update(
            memory_id=memory_id,
            data=data
        )
        
        self.logger.info(f"更新记忆: id={memory_id}")
        
        return result
        
       
    
    def delete(self, memory_id: str) -> Dict[str, Any]:
        """删除记忆"""
        memory = self.get_memory_instance("shared_analysts")
        
        # Mem0的delete方法
        result = memory.delete(memory_id=memory_id)
        
        self.logger.info(f"删除记忆: id={memory_id}")
        
        return result
            
       
    
    def get_all(self, user_id: str, **kwargs) -> Dict[str, Any]:
        """获取所有记忆"""
        memory = self.get_memory_instance(user_id)
        
        # Mem0的get_all方法
        result = memory.get_all(user_id=user_id)
        
        self.logger.info(f"获取所有记忆: user={user_id}")
        
        return result
            
       
    
    def reset(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """重置记忆"""
        if user_id:
            memory = self.get_memory_instance(user_id)
            result = memory.reset(user_id=user_id)
            
            self.logger.info(f"重置记忆: user={user_id}")
        else:
            # 重置所有用户（Mem0可能不直接支持，需要遍历）
            self.logger.warning("Mem0重置所有用户需要手动处理")
            result = {
                'status': 'partial_support',
                'message': '请指定user_id进行重置'
            }
        
        return result
            
       
    
    def get_framework_name(self) -> str:
        """获取框架名称"""
        return "mem0"
    
    # 提供对底层Mem0Integration的访问（保持向后兼容）
    @property
    def integration(self) -> Mem0Integration:
        """获取底层的Mem0Integration实例"""
        return self.mem0_integration

