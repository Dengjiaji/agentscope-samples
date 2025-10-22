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
        
        # 🔧 加载 ReMe 环境变量配置
        self._load_reme_env()
        
        # 初始化embedding模型
        embedding_model_name = os.getenv("MEMORY_EMBEDDING_MODEL", "text-embedding-v4")
        embedding_dimensions = int(os.getenv("REME_EMBEDDING_DIMENSIONS", "1024"))
        
        self.logger.info(f"ReMe配置: model={embedding_model_name}, dimensions={embedding_dimensions}")
        self.logger.info(f"ReMe API: base_url={os.getenv('FLOW_EMBEDDING_BASE_URL', 'Not set')}")
        
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
    
    def _load_reme_env(self):
        """
        加载 ReMe 环境变量
        ReMe 使用 FLOW_ 前缀的环境变量，需要映射到 OpenAI 兼容的环境变量
        """
        # 如果已经设置了 FLOW_ 环境变量，映射到 OpenAI 兼容的变量
        flow_embedding_api_key = os.getenv("FLOW_EMBEDDING_API_KEY")
        flow_embedding_base_url = os.getenv("FLOW_EMBEDDING_BASE_URL")
        flow_llm_api_key = os.getenv("FLOW_LLM_API_KEY")
        flow_llm_base_url = os.getenv("FLOW_LLM_BASE_URL")
        
        # 映射 FLOW_ 变量到 OPENAI_ 变量（如果 OPENAI_ 变量未设置）
        if flow_embedding_api_key and not os.getenv("OPENAI_API_KEY"):
            os.environ["OPENAI_API_KEY"] = flow_embedding_api_key
            self.logger.info("已从 FLOW_EMBEDDING_API_KEY 设置 OPENAI_API_KEY")
        
        if flow_embedding_base_url and not os.getenv("OPENAI_BASE_URL"):
            os.environ["OPENAI_BASE_URL"] = flow_embedding_base_url
            self.logger.info(f"已从 FLOW_EMBEDDING_BASE_URL 设置 OPENAI_BASE_URL: {flow_embedding_base_url}")
        
        # 检查必需的环境变量
        if not os.getenv("OPENAI_API_KEY"):
            self.logger.warning("⚠️ 未设置 OPENAI_API_KEY 或 FLOW_EMBEDDING_API_KEY")
            self.logger.warning("   ReMe 需要 API key 才能生成 embedding")
        
        if not os.getenv("OPENAI_BASE_URL"):
            self.logger.warning("⚠️ 未设置 OPENAI_BASE_URL 或 FLOW_EMBEDDING_BASE_URL")
            self.logger.warning("   将使用默认 OpenAI API: https://api.openai.com/v1")
    
    def _setup_logging(self):
        """设置日志"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def _get_workspace_id(self, user_id: str) -> str:
        """获取workspace ID，直接使用user_id作为workspace_id"""
        return user_id
    
    def _ensure_workspace_exists(self, workspace_id: str):
        """确保workspace存在"""
        if not self.vector_store.exist_workspace(workspace_id):
            self.vector_store.create_workspace(workspace_id)
            self.logger.info(f"创建workspace: {workspace_id}")
    
    def _convert_numpy_types(self, obj):
        """
        递归转换对象中的numpy类型为Python原生类型
        """
        try:
            import numpy as np
            
            if isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, dict):
                return {key: self._convert_numpy_types(value) for key, value in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [self._convert_numpy_types(item) for item in obj]
            else:
                return obj
        except ImportError:
            # 如果没有numpy，直接返回原值
            return obj
    
    def _normalize_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        标准化metadata，将不支持的类型转换为字符串
        ChromaDB只支持: str, int, float, bool (注意：实际不支持 None!)
        """
        if metadata is None:
            return {}
        
        import json
        
        # 尝试导入numpy用于类型检查
        try:
            import numpy as np
            has_numpy = True
        except ImportError:
            has_numpy = False
        
        normalized = {}
        for key, value in metadata.items():
            # ⚠️ 跳过 None 值 - ChromaDB 实际不接受 None
            if value is None:
                continue  # 不添加这个键值对
            elif isinstance(value, (str, bool)):
                # 字符串和布尔值保持不变
                normalized[key] = value
            elif isinstance(value, (int, float)):
                # Python原生数字类型保持不变
                normalized[key] = value
            elif has_numpy and isinstance(value, (np.integer, np.floating)):
                # numpy数字类型转换为Python原生类型
                if isinstance(value, np.integer):
                    normalized[key] = int(value)
                else:
                    normalized[key] = float(value)
            elif isinstance(value, (list, tuple, dict)) or (has_numpy and isinstance(value, np.ndarray)):
                # 复杂类型：先转换numpy类型，再转JSON字符串
                try:
                    converted_value = self._convert_numpy_types(value)
                    normalized[key] = json.dumps(converted_value, ensure_ascii=False)
                except (TypeError, ValueError) as e:
                    # 如果JSON序列化失败，直接转字符串
                    normalized[key] = str(value)
            else:
                # 其他类型转换为字符串
                normalized[key] = str(value)
        
        return normalized
    
    def add(self, messages: str | List[Dict[str, Any]], user_id: str, metadata: Optional[Dict[str, Any]] = None, infer: bool = False, **kwargs) -> Dict[str, Any]:
        """
        添加记忆
        
        Args:
            messages: 消息内容
            user_id: 用户ID
            metadata: 元数据
            infer: Mem0参数，ReMe中忽略
            **kwargs: 其他兼容性参数，ReMe中忽略
        """
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
        
        # 标准化metadata，确保所有值都是支持的类型
        node_metadata = self._normalize_metadata(node_metadata)
        
        node = VectorNode(
            unique_id=node_id,
            workspace_id=workspace_id,
            content=content,
            metadata=node_metadata
        )
        
        # 插入节点
        self.vector_store.insert([node], workspace_id)
        
        # 自动保存workspace
        print(f"💾 准备保存 workspace: {workspace_id}")
        print(f"   保存路径: {self.store_dir}")
        # ⚠️ 必须传入 path 参数，否则会保存到当前工作目录
        self.vector_store.dump_workspace(workspace_id, path=self.store_dir)
        
        self.logger.info(f"添加记忆: user={user_id}, id={node_id} (已保存)")
        
        return {
            'status': 'success',
            'results': [{'id': node_id, 'memory': content}]
        }
    
    def search(self, query: str, user_id: str, top_k: int = 5, **kwargs) -> Dict[str, Any]:
        """搜索记忆"""
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
    
    def update(self, memory_id: str, data: str | Dict[str, Any], workspace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        更新记忆
        通过插入相同unique_id的VectorNode来覆盖更新
        
        Args:
            memory_id: 记忆ID (unique_id)
            data: 新的记忆内容
            workspace_id: workspace ID，如果未提供则必须在 data 中指定 user_id
            
        Returns:
            更新结果
        """
        # 如果没有提供workspace_id，从data中获取user_id并生成workspace_id
        if workspace_id is None:
            if isinstance(data, dict) and 'user_id' in data:
                user_id = data['user_id']
                workspace_id = self._get_workspace_id(user_id)
            else:
                raise ValueError("必须提供 workspace_id 或在 data 中指定 user_id")
        
        # 处理数据格式
        if isinstance(data, str):
            content = data
            metadata = {}
        elif isinstance(data, dict):
            content = data.get('content', str(data))
            metadata = data.get('metadata', {})
        else:
            content = str(data)
            metadata = {}
        
        # 标准化metadata
        metadata = self._normalize_metadata(metadata)
        
        # 创建新的VectorNode，使用相同的unique_id来覆盖
        updated_node = VectorNode(
            unique_id=memory_id,  # 使用相同的ID实现覆盖
            workspace_id=workspace_id,
            content=content,
            metadata=metadata
        )
        
        # 插入节点（会覆盖同ID的旧节点）
        self.vector_store.insert([updated_node], workspace_id)
        
        # 自动保存workspace
        self.vector_store.dump_workspace(workspace_id, path=self.store_dir)
        
        self.logger.info(f"更新记忆: workspace={workspace_id}, id={memory_id} (已保存)")
        
        return {
            'status': 'success',
            'message': f'已更新记忆 {memory_id}',
            'memory_id': memory_id
        }
    
    def delete(self, memory_id: str, workspace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        删除记忆
        
        Args:
            memory_id: 记忆ID
            workspace_id: workspace ID，必须提供
            
        Returns:
            删除结果
        """
        if workspace_id is None:
            raise ValueError("必须提供 workspace_id 来删除记忆")
        
        # 执行删除
        self.vector_store.delete([memory_id], workspace_id)
        
        # 自动保存workspace
        self.vector_store.dump_workspace(workspace_id, path=self.store_dir)
        
        self.logger.info(f"删除记忆: workspace={workspace_id}, id={memory_id} (已保存)")
        
        return {
            'status': 'success',
            'message': f'已删除记忆 {memory_id}'
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
        self.vector_store.delete([memory_id], workspace_id)
        
        # 自动保存workspace
        self.vector_store.dump_workspace(workspace_id, path=self.store_dir)
        
        self.logger.info(f"删除记忆: workspace={workspace_id}, id={memory_id} (已保存)")
        
        return {
            'status': 'success',
            'message': f'已删除记忆 {memory_id}'
        }
    
    def get_all(self, user_id: str, **kwargs) -> Dict[str, Any]:
        """获取所有记忆"""
        workspace_id = self._get_workspace_id(user_id)
        
        # 检查workspace是否存在
        if not self.vector_store.exist_workspace(workspace_id):
            return {'results': []}
        
        # 使用 iter_workspace_nodes() 方法获取workspace中的所有节点
        # 这是一个生成器，需要转换为列表
        workspace_nodes = list(self.vector_store.iter_workspace_nodes(workspace_id))
        
        # 转换为标准格式
        results = []
        for node in workspace_nodes:
            result = {
                'id': node.unique_id,
                'memory': node.content,
                'metadata': node.metadata
            }
            results.append(result)
        
        self.logger.info(f"获取所有记忆: user={user_id}, 共{len(results)}条")
        
        return {'results': results}
    
    def reset(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """重置记忆"""
        if user_id:
            workspace_id = self._get_workspace_id(user_id)
            if self.vector_store.exist_workspace(workspace_id):
                self.vector_store.delete_workspace(workspace_id)
                # 注意：删除workspace后无需dump，因为workspace已不存在
                self.logger.info(f"重置记忆: user={user_id} (已删除workspace)")
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
    
    def import_workspace(self, user_id: str, import_path: str) -> Dict[str, Any]:
        """
        导入workspace（ReMe特定功能）
        
        Args:
            user_id: 用户ID
            import_path: 导入路径
            
        Returns:
            导入结果
        """
        workspace_id = self._get_workspace_id(user_id)
        
        result = self.vector_store.load_workspace(workspace_id, path=import_path)
        
        self.logger.info(f"导入workspace: {import_path} -> {workspace_id}")
        
        return {
            'status': 'success',
            'import_path': import_path,
            'result': result
        }

