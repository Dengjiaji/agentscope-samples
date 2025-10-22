#!/usr/bin/env python3
"""
记忆系统抽象接口
定义统一的记忆操作接口，支持不同记忆框架（mem0, ReMe等）
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional


class MemoryInterface(ABC):
    """记忆系统抽象基类"""
    
    @abstractmethod
    def add(self, messages: str | List[Dict[str, Any]], user_id: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        添加记忆
        
        Args:
            messages: 记忆内容，可以是字符串或消息列表
            user_id: 用户/分析师ID
            metadata: 元数据
            
        Returns:
            添加结果字典
        """
        pass
    
    @abstractmethod
    def search(self, query: str, user_id: str, top_k: int = 5, **kwargs) -> Dict[str, Any]:
        """
        搜索记忆
        
        Args:
            query: 搜索查询
            user_id: 用户/分析师ID
            top_k: 返回结果数量
            
        Returns:
            搜索结果字典，包含 'results' 列表
        """
        pass
    
    @abstractmethod
    def update(self, memory_id: str, data: str | Dict[str, Any]) -> Dict[str, Any]:
        """
        更新记忆
        
        Args:
            memory_id: 记忆ID
            data: 新的记忆内容
            
        Returns:
            更新结果字典
        """
        pass
    
    @abstractmethod
    def delete(self, memory_id: str) -> Dict[str, Any]:
        """
        删除记忆
        
        Args:
            memory_id: 记忆ID
            
        Returns:
            删除结果字典
        """
        pass
    
    @abstractmethod
    def get_all(self, user_id: str, **kwargs) -> Dict[str, Any]:
        """
        获取所有记忆
        
        Args:
            user_id: 用户/分析师ID
            
        Returns:
            所有记忆的字典
        """
        pass
    
    @abstractmethod
    def reset(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        重置记忆
        
        Args:
            user_id: 用户/分析师ID，如果为None则重置所有
            
        Returns:
            重置结果字典
        """
        pass
    
    @abstractmethod
    def get_framework_name(self) -> str:
        """
        获取框架名称
        
        Returns:
            框架名称字符串 (如 'mem0', 'reme')
        """
        pass

