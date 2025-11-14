#!/usr/bin/env python3
"""
ReMe Long-term Memory Implementation
使用全局单例 ChromaVectorStore，通过 workspace_id 区分不同用户
"""

import os
import uuid
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path

from .base import LongTermMemory

from flowllm.storage.vector_store import ChromaVectorStore
from flowllm.embedding_model import OpenAICompatibleEmbeddingModel
from flowllm.schema.vector_node import VectorNode
from src.config.path_config import get_logs_and_memory_dir

logger = logging.getLogger(__name__)

# 每条记忆的最大字符长度（text-embedding-v4 限制约为 8192 tokens，约等于 8000 字符）
MAX_CONTENT_LENGTH = 8000


class ReMeMemory(LongTermMemory):
    """
    ReMe长期记忆实现
    
    设计理念：
    - 全局共享一个 ChromaVectorStore 实例（避免 Chroma 冲突）
    - 使用 workspace_id = f"{base_dir}_{user_id}" 区分不同配置和用户
    - 所有数据存储在统一的根目录下
    """
    
    # 全局单例：一个进程只有一个 ChromaVectorStore
    _global_vector_store: Optional[ChromaVectorStore] = None
    _global_embedding_model: Optional[OpenAICompatibleEmbeddingModel] = None
    _global_store_dir: Optional[str] = None
    
    def __init__(self, base_dir: str):
        """
        初始化ReMe记忆
        
        Args:
            base_dir: 基础目录（config_name），会作为 workspace_id 的前缀
        """
        self.base_dir = base_dir
        
        # 使用全局统一的存储目录
        if ReMeMemory._global_store_dir is None:
            ReMeMemory._global_store_dir = str(get_logs_and_memory_dir() / base_dir / "memory_data" / "reme_vector_store")
            os.makedirs(ReMeMemory._global_store_dir, exist_ok=True)
        
        self.store_dir = ReMeMemory._global_store_dir
        
        # 初始化全局 embedding 模型（只创建一次）
        if ReMeMemory._global_embedding_model is None:
            embedding_model_name = os.getenv("MEMORY_EMBEDDING_MODEL", "text-embedding-3-small")
            embedding_dim = int(os.getenv("REME_EMBEDDING_DIMENSIONS", "1536"))
            
            logger.info(f"初始化全局 Embedding 模型: {embedding_model_name} (dim={embedding_dim})")
            ReMeMemory._global_embedding_model = OpenAICompatibleEmbeddingModel(
                dimensions=embedding_dim,
                model_name=embedding_model_name
            )
        
        # 初始化全局向量存储（只创建一次，解决 Chroma 冲突）
        if ReMeMemory._global_vector_store is None:
            logger.info(f"初始化全局 ChromaVectorStore: {self.store_dir}")
            ReMeMemory._global_vector_store = ChromaVectorStore(
                embedding_model=ReMeMemory._global_embedding_model,
                store_dir=self.store_dir,
                batch_size=1024
            )
        
        # 先赋值 vector_store，确保后续方法可以访问
        self.vector_store = ReMeMemory._global_vector_store
        
        # 只在第一次创建时加载所有已有workspaces（使用标志位避免重复加载）
        if not hasattr(ReMeMemory, '_workspaces_loaded'):
            self._load_all_existing_workspaces()
            ReMeMemory._workspaces_loaded = True
        
        logger.info(f"ReMe记忆已初始化 (base_dir={base_dir})")
    
    def _load_all_existing_workspaces(self):
        """加载所有已有的workspace记忆"""
        jsonl_files = list(Path(self.store_dir).glob("*.jsonl"))
        
        if jsonl_files:
            logger.info(f"发现 {len(jsonl_files)} 个workspace文件，正在加载...")
            
        for jsonl_file in jsonl_files:
            workspace_id = jsonl_file.stem
            if not self.vector_store.exist_workspace(workspace_id):
                try:
                    self.vector_store.load_workspace(workspace_id, path=self.store_dir)
                    logger.debug(f"✓ 加载 workspace: {workspace_id}")
                except Exception as e:
                    logger.warning(f"✗ 加载失败 {workspace_id}: {e}")
    
    
    def _get_workspace_id(self, user_id: str) -> str:
        """
        生成完整的 workspace_id
        格式: {base_dir}__{user_id}
        这样可以在全局 ChromaVectorStore 中区分不同配置的用户
        """
        return f"{user_id}"
    
    def _ensure_workspace(self, user_id: str):
        """确保workspace存在"""
        workspace_id = self._get_workspace_id(user_id)
        
        if not self.vector_store.exist_workspace(workspace_id):
            # 尝试加载
            workspace_file = os.path.join(self.store_dir, f"{workspace_id}.jsonl")
            if os.path.exists(workspace_file):
                try:
                    self.vector_store.load_workspace(workspace_id, path=self.store_dir)
                    return
                except Exception as e:
                    logger.warning(f"加载workspace失败: {e}")
            
            # 创建新workspace
            self.vector_store.create_workspace(workspace_id)
    
    def add(self, content: str, user_id: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """添加记忆
        
        如果内容超过 MAX_CONTENT_LENGTH，会自动分割成多条记录分别存储
        """
        if not content or not isinstance(content, str):
            logger.warning(f"⚠️ [ReMeMemory] 输入内容为空或非字符串类型，跳过")
            return ""
        
        content = content.strip()
        if not content:
            logger.warning(f"⚠️ [ReMeMemory] 输入内容为空（仅包含空白字符），跳过")
            return ""
        
        content_len = len(content)
        logger.debug(f"➕ [ReMeMemory] 添加记忆: user_id={user_id}, content_len={content_len}")
        
        self._ensure_workspace(user_id)
        workspace_id = self._get_workspace_id(user_id)
        
        logger.debug(f"   workspace_id={workspace_id}")
        
        node_metadata = metadata or {}
        node_metadata['user_id'] = user_id
        node_metadata['base_dir'] = self.base_dir
        
        # 如果内容超过最大长度，分割成多条记录
        if content_len > MAX_CONTENT_LENGTH:
            logger.info(f"   内容长度 ({content_len}) 超过限制 ({MAX_CONTENT_LENGTH})，将分割成多条记录")
            
            # 按 MAX_CONTENT_LENGTH 分割内容
            chunks = []
            for i in range(0, content_len, MAX_CONTENT_LENGTH):
                chunk = content[i:i + MAX_CONTENT_LENGTH]
                chunks.append(chunk)
            
            logger.info(f"   分割成 {len(chunks)} 条记录")
            
            # 为每个片段创建节点
            nodes = []
            first_node_id = None
            for idx, chunk in enumerate(chunks):
                node_id = str(uuid.uuid4())
                if idx == 0:
                    first_node_id = node_id
                
                # 在元数据中记录这是分割记录的一部分
                chunk_metadata = node_metadata.copy()
                chunk_metadata['chunk_index'] = idx
                chunk_metadata['total_chunks'] = len(chunks)
                chunk_metadata['is_chunked'] = True
                
                node = VectorNode(
                    unique_id=node_id,
                    workspace_id=workspace_id,
                    content=chunk,
                    metadata=chunk_metadata
                )
                nodes.append(node)
            
            # 批量插入所有节点
            self.vector_store.insert(nodes, workspace_id)
            self.vector_store.dump_workspace(workspace_id, path=self.store_dir)
            
            logger.debug(f"   ✅ 记忆已添加（分割成 {len(chunks)} 条），第一条 node_id={first_node_id}")
            logger.debug(f"   保存路径: {self.store_dir}/{workspace_id}.jsonl")
            
            return first_node_id
        else:
            # 内容长度正常，直接存储
            node_id = str(uuid.uuid4())
            
            node = VectorNode(
                unique_id=node_id,
                workspace_id=workspace_id,
                content=content,
                metadata=node_metadata
            )
            
            self.vector_store.insert([node], workspace_id)
            self.vector_store.dump_workspace(workspace_id, path=self.store_dir)
            
            logger.debug(f"   ✅ 记忆已添加，node_id={node_id}")
            logger.debug(f"   保存路径: {self.store_dir}/{workspace_id}.jsonl")
            
            return node_id
    
    def search(self, query: str, user_id: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """搜索记忆"""
        if not query or not isinstance(query, str):
            logger.warning(f"⚠️ [ReMeMemory] 搜索查询为空或非字符串类型，返回空列表")
            return []
        
        query = query.strip()
        if not query:
            logger.warning(f"⚠️ [ReMeMemory] 搜索查询为空（仅包含空白字符），返回空列表")
            return []
        
        # 如果查询文本超过最大长度，截断
        if len(query) > MAX_CONTENT_LENGTH:
            logger.warning(f"⚠️ [ReMeMemory] 搜索查询长度 ({len(query)}) 超过限制 ({MAX_CONTENT_LENGTH})，将截断")
            query = query[:MAX_CONTENT_LENGTH]
        
        logger.debug(f"🔍 [ReMeMemory] 搜索记忆: user_id={user_id}, query={query[:100]}...")
        
        self._ensure_workspace(user_id)
        workspace_id = self._get_workspace_id(user_id)
        
        logger.debug(f"   workspace_id={workspace_id}")
        logger.debug(f"   workspace存在: {self.vector_store.exist_workspace(workspace_id)}")
        
        if not self.vector_store.exist_workspace(workspace_id):
            logger.warning(f"   ⚠️ workspace不存在，返回空列表")
            return []
        
        # 检查workspace中的节点数量
        try:
            all_nodes = list(self.vector_store.iter_workspace_nodes(workspace_id))
            logger.debug(f"   workspace中共有 {len(all_nodes)} 个节点")
        except Exception as e:
            logger.debug(f"   无法统计节点数量: {e}")
        
        nodes = self.vector_store.search(query, workspace_id, top_k=top_k)
        
        logger.debug(f"   搜索结果: {len(nodes)} 条")
        
        return [
            {
                'id': node.unique_id,
                'content': node.content,
                'metadata': node.metadata
            }
            for node in nodes
        ]
    
    def update(self, memory_id: str, content: str, user_id: str) -> bool:
        """更新记忆
        
        如果内容超过 MAX_CONTENT_LENGTH，会自动分割成多条记录分别存储
        注意：更新时会删除旧记录，如果旧记录是分割的，需要手动删除所有相关记录
        """
        if not content or not isinstance(content, str):
            logger.warning(f"⚠️ [ReMeMemory] 更新内容为空或非字符串类型，跳过")
            return False
        
        content = content.strip()
        if not content:
            logger.warning(f"⚠️ [ReMeMemory] 更新内容为空（仅包含空白字符），跳过")
            return False
        
        try:
            self._ensure_workspace(user_id)
            workspace_id = self._get_workspace_id(user_id)
            
            # 删除旧节点
            self.vector_store.delete([memory_id], workspace_id)
            
            # 如果内容超过最大长度，分割成多条记录
            content_len = len(content)
            if content_len > MAX_CONTENT_LENGTH:
                logger.info(f"   更新内容长度 ({content_len}) 超过限制 ({MAX_CONTENT_LENGTH})，将分割成多条记录")
                
                # 按 MAX_CONTENT_LENGTH 分割内容
                chunks = []
                for i in range(0, content_len, MAX_CONTENT_LENGTH):
                    chunk = content[i:i + MAX_CONTENT_LENGTH]
                    chunks.append(chunk)
                
                logger.info(f"   分割成 {len(chunks)} 条记录")
                
                # 为每个片段创建节点（第一条使用原 memory_id，其他创建新 ID）
                nodes = []
                for idx, chunk in enumerate(chunks):
                    node_id = memory_id if idx == 0 else str(uuid.uuid4())
                    
                    chunk_metadata = {
                        'user_id': user_id,
                        'base_dir': self.base_dir,
                        'chunk_index': idx,
                        'total_chunks': len(chunks),
                        'is_chunked': True
                    }
                    
                    node = VectorNode(
                        unique_id=node_id,
                        workspace_id=workspace_id,
                        content=chunk,
                        metadata=chunk_metadata
                    )
                    nodes.append(node)
                
                # 批量插入所有节点
                self.vector_store.insert(nodes, workspace_id)
            else:
                # 内容长度正常，直接更新
                node = VectorNode(
                    unique_id=memory_id,
                    workspace_id=workspace_id,
                    content=content,
                    metadata={'user_id': user_id, 'base_dir': self.base_dir}
                )
                
                self.vector_store.insert([node], workspace_id)
            
            self.vector_store.dump_workspace(workspace_id, path=self.store_dir)
            
            return True
        except Exception as e:
            logger.error(f"更新记忆失败: {e}")
            return False
    
    def delete(self, memory_id: str, user_id: str) -> bool:
        """删除记忆"""
        try:
            self._ensure_workspace(user_id)
            workspace_id = self._get_workspace_id(user_id)
            self.vector_store.delete([memory_id], workspace_id)
            self.vector_store.dump_workspace(workspace_id, path=self.store_dir)
            return True
        except Exception as e:
            logger.error(f"删除记忆失败: {e}")
            return False
    
    def get_all(self, user_id: str) -> List[Dict[str, Any]]:
        """获取所有记忆"""
        self._ensure_workspace(user_id)
        workspace_id = self._get_workspace_id(user_id)
        
        if not self.vector_store.exist_workspace(workspace_id):
            return []
        
        nodes = list(self.vector_store.iter_workspace_nodes(workspace_id))
        
        return [
            {
                'id': node.unique_id,
                'content': node.content,
                'metadata': node.metadata
            }
            for node in nodes
        ]
    
    def delete_all(self, user_id: str) -> bool:
        """删除所有记忆"""
        try:
            workspace_id = self._get_workspace_id(user_id)
            
            if not self.vector_store.exist_workspace(workspace_id):
                logger.info(f"workspace {workspace_id} 不存在，无需清空")
                return True
            
            # 获取所有节点ID并删除
            nodes = list(self.vector_store.iter_workspace_nodes(workspace_id))
            node_ids = [node.unique_id for node in nodes]
            
            if node_ids:
                self.vector_store.delete(node_ids, workspace_id)
                self.vector_store.dump_workspace(workspace_id, path=self.store_dir)
                logger.info(f"已清空用户 {user_id} (workspace {workspace_id}) 的 {len(node_ids)} 条记忆")
            
            return True
        except Exception as e:
            logger.error(f"清空记忆失败: {e}")
            return False
    
    @classmethod
    def reset_global_store(cls):
        """重置全局向量存储（主要用于测试）"""
        cls._global_vector_store = None
        cls._global_embedding_model = None
        cls._global_store_dir = None
        logger.info("全局 ChromaVectorStore 已重置")

