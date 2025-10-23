#!/usr/bin/env python3
"""
Mem0 记忆框架适配器
将现有的 Mem0Integration 适配到统一的记忆接口
"""

import os
import sqlite3
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
        
        # 加载已有的用户记忆
        self._loaded_users = self._load_existing_users()
    
    def _load_existing_users(self) -> List[str]:
        """
        从 SQLite 数据库中查询已有的用户ID
        
        Returns:
            已有用户ID列表
        """
        loaded_users = []
        
        # 获取数据库路径
        history_db_path = self.mem0_integration.config.get("history_db_path")
        
        if not history_db_path or not os.path.exists(history_db_path):
            self.logger.info("未找到已有的记忆数据库")
            return loaded_users
        
        try:
            # 连接数据库
            conn = sqlite3.connect(history_db_path)
            cursor = conn.cursor()
            
            # 查询所有唯一的 user_id
            # Mem0 的数据库结构中有 memories 表和 history 表
            cursor.execute("""
                SELECT DISTINCT user_id 
                FROM memories 
                WHERE user_id IS NOT NULL AND user_id != ''
                ORDER BY user_id
            """)
            
            rows = cursor.fetchall()
            loaded_users = [row[0] for row in rows]
            
            conn.close()
            
            if loaded_users:
                self.logger.info(f"✅ 从数据库中发现 {len(loaded_users)} 个已有用户记忆")
            else:
                self.logger.info("数据库为空，未找到已有用户记忆")
                
        except sqlite3.Error as e:
            self.logger.warning(f"查询数据库失败: {e}")
        except Exception as e:
            self.logger.warning(f"加载已有用户失败: {e}")
        
        return loaded_users
    
    def get_loaded_workspaces(self) -> List[str]:
        """
        获取已加载的用户列表（workspace）
        
        Returns:
            用户ID列表
        """
        return getattr(self, '_loaded_users', [])
    
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

