#!/usr/bin/env python3
"""
Mem0 Long-term Memory Implementation
直接使用mem0，无adapter层
"""

import os
import logging
from typing import Dict, List, Any, Optional
from mem0 import Memory

from .base import LongTermMemory
from src.config.path_config import get_logs_and_memory_dir


logger = logging.getLogger(__name__)


class Mem0Memory(LongTermMemory):
    """Mem0长期记忆实现"""
    
    def __init__(self, base_dir: str):
        """
        初始化Mem0记忆
        
        Args:
            base_dir: 存储基础目录（config_name）
        """
        self.base_dir = str(get_logs_and_memory_dir() / base_dir)
        
        # Mem0配置
        config = {
            "history_db_path": os.path.join(self.base_dir, "memory_data", "history.db"),
            "vector_store": {
                "provider": "chroma",
                "config": {
                    "collection_name": "memories",
                    "path": os.path.join(self.base_dir, "memory_data", "chroma_db")
                }
            },
            "llm": {
                "provider": "openai",
                "config": {
                    "model": os.getenv("MEMORY_LLM_MODEL", "gpt-4o-mini"),
                    "temperature": 0.1,
                    "api_key": os.getenv("OPENAI_API_KEY"),
                    "openai_base_url": os.getenv("OPENAI_BASE_URL"),
                }
            },
            "embedder": {
                "provider": "openai",
                "config": {
                    "model": os.getenv("MEMORY_EMBEDDING_MODEL", "text-embedding-3-small"),
                    "api_key": os.getenv("OPENAI_API_KEY"),
                    "openai_base_url": os.getenv("OPENAI_BASE_URL"),
                }
            }
        }
        
        # 确保目录存在
        os.makedirs(os.path.dirname(config["history_db_path"]), exist_ok=True)
        os.makedirs(config["vector_store"]["config"]["path"], exist_ok=True)
        
        # 创建共享Memory实例
        self.memory = Memory.from_config(config)
        logger.info(f"Mem0记忆已初始化: {self.base_dir}")
    
    def add(self, content: str, user_id: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """添加记忆"""
        logger.debug(f"➕ [Mem0Memory] 添加记忆: user_id={user_id}, content_len={len(content)}")
        
        result = self.memory.add(
            messages=[{"role": "user", "content": content}],
            user_id=user_id,
            metadata=metadata or {}
        )
        
        logger.debug(f"   add结果: {result}")
        
        # 提取memory_id
        if result and 'results' in result and len(result['results']) > 0:
            memory_id = result['results'][0].get('id', '')
            logger.debug(f"   ✅ 记忆已添加，memory_id={memory_id}")
            return memory_id
        
        logger.warning(f"   ⚠️ 添加记忆失败或未返回ID")
        return ''
    
    def search(self, query: str, user_id: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """搜索记忆"""
        logger.debug(f"🔍 [Mem0Memory] 搜索记忆: user_id={user_id}, query={query[:100]}...")
        
        results = self.memory.search(query=query, user_id=user_id, limit=top_k)
        
        logger.debug(f"   原始结果类型: {type(results)}")
        logger.debug(f"   原始结果长度: {len(results) if isinstance(results, list) else 'N/A'}")
        
        # 标准化返回格式
        if isinstance(results, list):
            formatted = [{'id': r.get('id'), 'content': r.get('memory'), 'metadata': r.get('metadata', {})} 
                    for r in results]
            logger.debug(f"   格式化后结果: {len(formatted)} 条")
            return formatted
        
        logger.warning(f"   ⚠️ 结果格式异常，返回空列表")
        return []
    
    def update(self, memory_id: str, content: str, user_id: str) -> bool:
        """更新记忆"""
        try:
            self.memory.update(memory_id=memory_id, data=content)
            return True
        except Exception as e:
            logger.error(f"更新记忆失败: {e}")
            return False
    
    def delete(self, memory_id: str, user_id: str) -> bool:
        """删除记忆"""
        try:
            self.memory.delete(memory_id=memory_id)
            return True
        except Exception as e:
            logger.error(f"删除记忆失败: {e}")
            return False
    
    def get_all(self, user_id: str) -> List[Dict[str, Any]]:
        """获取所有记忆"""
        results = self.memory.get_all(user_id=user_id)
        
        if isinstance(results, list):
            return [{'id': r.get('id'), 'content': r.get('memory'), 'metadata': r.get('metadata', {})} 
                    for r in results]
        return []
    
    def delete_all(self, user_id: str) -> bool:
        """删除所有记忆"""
        try:
            self.memory.delete_all(user_id=user_id)
            logger.info(f"已清空用户 {user_id} 的所有记忆")
            return True
        except Exception as e:
            logger.error(f"清空记忆失败: {e}")
            return False

