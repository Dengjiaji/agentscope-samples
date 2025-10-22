#!/usr/bin/env python3
"""
ReMe 记忆框架适配器
将 ReMe (flowllm) 框架适配到统一的记忆接口
"""

import os
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path

from src.memory.memory_interface import MemoryInterface

# 尝试导入ReMe相关模块
try:
    from flowllm.storage.vector_store import ChromaVectorStore
    from flowllm.embedding_model import OpenAICompatibleEmbeddingModel
    from flowllm.schema.vector_node import VectorNode
    REME_AVAILABLE = True
except ImportError as e:
    REME_AVAILABLE = False
    print(f"⚠️ ReMe框架未安装: {e}")
    print("提示: 请安装 flowllm 包以使用ReMe框架")


class ReMeAdapter(MemoryInterface):
    """ReMe框架适配器"""
    
    def __init__(self, base_dir: str):
        """
        初始化ReMe适配器
        
        Args:
            base_dir: 基础目录 (config_name)
        """
        if not REME_AVAILABLE:
            raise ImportError("ReMe框架未安装，无法使用ReMeAdapter")
        
        self.base_dir = os.path.join("logs_and_memory", base_dir)
        self.store_dir = os.path.join(self.base_dir, "memory_data", "reme_vector_store")
        
        # 确保目录存在
        os.makedirs(self.store_dir, exist_ok=True)
        
        # 设置日志
        self._setup_logging()
        
        # 初始化embedding模型
        embedding_model_name = os.getenv("MEMORY_EMBEDDING_MODEL", "text-embedding-v4")
        embedding_dimensions = int(os.getenv("REME_EMBEDDING_DIMENSIONS", "1024"))
        
        self.embedding_model = OpenAICompatibleEmbeddingModel(
            dimensions=embedding_dimensions,
            model_name=embedding_model_name
        )
        
        # 初始化向量存储
        self.vector_store = ChromaVectorStore(
            embedding_model=self.embedding_model,
            store_dir=self.store_dir,
            batch_size=1024
        )
        
        self.logger.info(f"ReMe适配器已初始化 (存储目录: {self.store_dir})")
    
    def _setup_logging(self):
        """设置日志"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def _get_workspace_id(self, user_id: str) -> str:
        """获取workspace ID，使用user_id作为workspace_id"""
        return f"analyst_{user_id}"
    
    def _ensure_workspace_exists(self, workspace_id: str):
        """确保workspace存在"""
        if not self.vector_store.exist_workspace(workspace_id):
            self.vector_store.create_workspace(workspace_id)
            self.logger.info(f"创建workspace: {workspace_id}")
    
    def add(self, messages: str | List[Dict[str, Any]], user_id: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """添加记忆"""
        try:
            workspace_id = self._get_workspace_id(user_id)
            self._ensure_workspace_exists(workspace_id)
            
            # 处理消息格式
            if isinstance(messages, str):
                content = messages
            elif isinstance(messages, list):
                # 提取消息内容
                content = "\n".join([
                    f"{msg.get('role', 'user')}: {msg.get('content', '')}" 
                    for msg in messages
                ])
            else:
                content = str(messages)
            
            # 创建VectorNode
            import uuid
            node_id = str(uuid.uuid4())
            
            node_metadata = metadata or {}
            node_metadata['user_id'] = user_id
            
            node = VectorNode(
                unique_id=node_id,
                workspace_id=workspace_id,
                content=content,
                metadata=node_metadata
            )
            
            # 插入节点
            self.vector_store.insert([node], workspace_id)
            
            self.logger.info(f"添加记忆: user={user_id}, id={node_id}")
            
            return {
                'status': 'success',
                'results': [{'id': node_id, 'memory': content}]
            }
            
        except Exception as e:
            self.logger.error(f"添加记忆失败: {e}")
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    def search(self, query: str, user_id: str, top_k: int = 5, **kwargs) -> Dict[str, Any]:
        """搜索记忆"""
        try:
            workspace_id = self._get_workspace_id(user_id)
            
            # 检查workspace是否存在
            if not self.vector_store.exist_workspace(workspace_id):
                self.logger.warning(f"Workspace不存在: {workspace_id}")
                return {'results': []}
            
            # 搜索
            nodes = self.vector_store.search(query, workspace_id, top_k=top_k)
            
            # 转换为标准格式
            results = []
            for node in nodes:
                result = {
                    'id': node.unique_id,
                    'memory': node.content,
                    'metadata': node.metadata,
                    'score': node.metadata.get('score', 0.0)
                }
                results.append(result)
            
            self.logger.info(f"搜索记忆: user={user_id}, query='{query[:50]}...', 找到{len(results)}条")
            
            return {'results': results}
            
        except Exception as e:
            self.logger.error(f"搜索记忆失败: {e}")
            return {
                'results': [],
                'error': str(e)
            }
    
    def update(self, memory_id: str, data: str | Dict[str, Any]) -> Dict[str, Any]:
        """
        更新记忆
        注意: ReMe的ChromaVectorStore不直接支持update操作
        我们采用先删除再插入的方式
        """
        try:
            # ReMe不支持直接更新，需要通过删除+重新插入实现
            # 这里我们返回一个提示，实际使用时可能需要先search找到node，然后delete+add
            
            self.logger.warning("ReMe框架不直接支持update操作，建议使用delete+add")
            
            return {
                'status': 'not_supported',
                'message': 'ReMe框架需要使用delete+add来实现更新',
                'memory_id': memory_id
            }
            
        except Exception as e:
            self.logger.error(f"更新记忆失败: {e}")
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    def delete(self, memory_id: str) -> Dict[str, Any]:
        """
        删除记忆
        注意: 需要知道workspace_id，这里我们需要搜索所有可能的workspace
        """
        try:
            # 由于不知道具体的workspace_id，这里返回提示
            # 实际使用时，建议在metadata中记录workspace_id
            
            self.logger.warning("ReMe删除操作需要提供workspace_id")
            
            return {
                'status': 'partial_support',
                'message': 'ReMe删除需要指定workspace_id，请通过search获取完整信息后再删除',
                'memory_id': memory_id
            }
            
        except Exception as e:
            self.logger.error(f"删除记忆失败: {e}")
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    def delete_by_workspace(self, memory_id: str, workspace_id: str) -> Dict[str, Any]:
        """
        按workspace删除记忆（ReMe特定方法）
        
        Args:
            memory_id: 记忆ID
            workspace_id: workspace ID
            
        Returns:
            删除结果
        """
        try:
            self.vector_store.delete([memory_id], workspace_id)
            self.logger.info(f"删除记忆: workspace={workspace_id}, id={memory_id}")
            
            return {
                'status': 'success',
                'message': f'已删除记忆 {memory_id}'
            }
            
        except Exception as e:
            self.logger.error(f"删除记忆失败: {e}")
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    def get_all(self, user_id: str, **kwargs) -> Dict[str, Any]:
        """获取所有记忆"""
        try:
            workspace_id = self._get_workspace_id(user_id)
            
            # 检查workspace是否存在
            if not self.vector_store.exist_workspace(workspace_id):
                return {'results': []}
            
            # ReMe没有直接的get_all接口，我们通过迭代workspace节点实现
            all_nodes = []
            try:
                # 尝试使用iter_workspace_nodes（如果可用）
                for node in self.vector_store.iter_workspace_nodes(workspace_id):
                    all_nodes.append(node)
            except AttributeError:
                # 如果没有iter方法，返回空列表
                self.logger.warning("ReMe ChromaVectorStore不支持iter_workspace_nodes")
                return {'results': []}
            
            # 转换为标准格式
            results = []
            for node in all_nodes:
                result = {
                    'id': node.unique_id,
                    'memory': node.content,
                    'metadata': node.metadata
                }
                results.append(result)
            
            self.logger.info(f"获取所有记忆: user={user_id}, 共{len(results)}条")
            
            return {'results': results}
            
        except Exception as e:
            self.logger.error(f"获取所有记忆失败: {e}")
            return {
                'results': [],
                'error': str(e)
            }
    
    def reset(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """重置记忆"""
        try:
            if user_id:
                workspace_id = self._get_workspace_id(user_id)
                if self.vector_store.exist_workspace(workspace_id):
                    self.vector_store.delete_workspace(workspace_id)
                    self.logger.info(f"重置记忆: user={user_id}")
                    return {
                        'status': 'success',
                        'message': f'已重置 {user_id} 的记忆'
                    }
                else:
                    return {
                        'status': 'success',
                        'message': f'{user_id} 没有记忆需要重置'
                    }
            else:
                # 重置所有（需要知道所有workspace）
                self.logger.warning("ReMe框架重置所有记忆需要手动处理")
                return {
                    'status': 'partial_support',
                    'message': '请指定user_id进行重置'
                }
                
        except Exception as e:
            self.logger.error(f"重置记忆失败: {e}")
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    def get_framework_name(self) -> str:
        """获取框架名称"""
        return "reme"
    
    def export_workspace(self, user_id: str, export_path: Optional[str] = None) -> Dict[str, Any]:
        """
        导出workspace（ReMe特定功能）
        
        Args:
            user_id: 用户ID
            export_path: 导出路径，如果为None则使用默认路径
            
        Returns:
            导出结果
        """
        try:
            workspace_id = self._get_workspace_id(user_id)
            
            if not export_path:
                export_path = os.path.join(self.store_dir, f"{workspace_id}.jsonl")
            
            result = self.vector_store.dump_workspace(workspace_id, path=export_path)
            
            self.logger.info(f"导出workspace: {workspace_id} -> {export_path}")
            
            return {
                'status': 'success',
                'export_path': export_path,
                'result': result
            }
            
        except Exception as e:
            self.logger.error(f"导出workspace失败: {e}")
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    def import_workspace(self, user_id: str, import_path: str) -> Dict[str, Any]:
        """
        导入workspace（ReMe特定功能）
        
        Args:
            user_id: 用户ID
            import_path: 导入路径
            
        Returns:
            导入结果
        """
        try:
            workspace_id = self._get_workspace_id(user_id)
            
            result = self.vector_store.load_workspace(workspace_id, path=import_path)
            
            self.logger.info(f"导入workspace: {import_path} -> {workspace_id}")
            
            return {
                'status': 'success',
                'import_path': import_path,
                'result': result
            }
            
        except Exception as e:
            self.logger.error(f"导入workspace失败: {e}")
            return {
                'status': 'failed',
                'error': str(e)
            }

