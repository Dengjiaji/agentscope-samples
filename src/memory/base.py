#!/usr/bin/env python3
"""
Long-term Memory Base Interface
参考 AgentScope 设计，提供统一的记忆接口
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional


class LongTermMemory(ABC):
    """长期记忆抽象基类"""
    
    @abstractmethod
    def add(self, content: str, user_id: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        添加记忆
        
        Args:
            content: 记忆内容
            user_id: 用户/分析师ID
            metadata: 元数据
            
        Returns:
            记忆ID
        """
        pass
    
    @abstractmethod
    def search(self, query: str, user_id: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        搜索记忆
        
        Args:
            query: 搜索查询
            user_id: 用户/分析师ID
            top_k: 返回结果数量
            
        Returns:
            搜索结果列表
        """
        pass
    
    @abstractmethod
    def update(self, memory_id: str, content: str, user_id: str) -> bool:
        """
        更新记忆
        
        Args:
            memory_id: 记忆ID
            content: 新内容
            user_id: 用户/分析师ID
            
        Returns:
            是否成功
        """
        pass
    
    @abstractmethod
    def delete(self, memory_id: str, user_id: str) -> bool:
        """
        删除记忆
        
        Args:
            memory_id: 记忆ID
            user_id: 用户/分析师ID
            
        Returns:
            是否成功
        """
        pass
    
    @abstractmethod
    def get_all(self, user_id: str) -> List[Dict[str, Any]]:
        """
        获取用户的所有记忆
        
        Args:
            user_id: 用户/分析师ID
            
        Returns:
            记忆列表
        """
        pass
    
    @abstractmethod
    def delete_all(self, user_id: str) -> bool:
        """
        删除用户的所有记忆
        
        Args:
            user_id: 用户/分析师ID
            
        Returns:
            是否成功
        """
        pass

