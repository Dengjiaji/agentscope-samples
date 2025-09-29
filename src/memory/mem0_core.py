#!/usr/bin/env python3
"""
Mem0 核心集成模块
包含 Mem0 配置、集成层和基础记忆类
"""

from email import message
import os
import json
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
from mem0 import Memory
from dotenv import load_dotenv


# ================================
# Mem0 集成配置层
# ================================

class Mem0Integration:
    """Mem0集成配置和管理"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化Mem0集成
        
        Args:
            config: 自定义配置，如果为None则使用默认配置
        """
        # 加载Mem0专用环境变量
        self._load_mem0_env()
        self.config = config or self._get_default_config()
        self._memory_instances: Dict[str, Memory] = {}
        self._setup_logging()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        # 从环境变量或默认值获取配置
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        
        return {
            "history_db_path": os.path.join(base_dir, "memory_data", "ia_memory_history.db"),
            "vector_store": {
                "provider": "chroma",
                "config": {
                    "collection_name": "ia_analyst_memories",
                    "path": os.path.join(base_dir, "memory_data", "ia_chroma_db")
                }
            },
            "llm": {
                "provider": "openai",
                "config": {
                    "model": os.getenv("MEMORY_LLM_MODEL", "qwen3-max-preview"),
                    "temperature": 0.1,
                    "api_key": os.getenv("OPENAI_API_KEY"),
                    "openai_base_url": os.getenv("OPENAI_BASE_URL"),
                }
            },
            "embedder": {
                "provider": "openai", 
                "config": {
                    "model": os.getenv("MEMORY_EMBEDDING_MODEL", "text-embedding-v4"),
                    "api_key": os.getenv("OPENAI_API_KEY"),
                    "openai_base_url": os.getenv("OPENAI_BASE_URL"),
                }
            }
        }
    
    def _load_mem0_env(self):
        """加载Mem0专用环境变量"""
        # 使用统一的mem0_env_loader来避免重复加载
        from src.utils.mem0_env_loader import ensure_mem0_env_loaded
        ensure_mem0_env_loaded()
    
    def _setup_logging(self):
        """设置日志"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def get_memory_instance(self, user_id: str) -> Memory:
        """
        获取或创建特定用户的Memory实例
        
        Args:
            user_id: 用户ID（如 'fundamentals_analyst', 'technical_analyst' 等）
            
        Returns:
            Memory实例
        """
        if not hasattr(self, '_shared_memory'):
            # 确保存储目录存在
            self._ensure_storage_directories()
            
            # 创建共享的Memory实例
            self._shared_memory = Memory.from_config(self.config)
            self.logger.info(f"Created shared memory instance")
        return self._shared_memory
            
    
    def _ensure_storage_directories(self):
        """确保存储目录存在"""
        history_db_dir = os.path.dirname(self.config.get("history_db_path", ""))
        vector_store_path = self.config.get("vector_store", {}).get("config", {}).get("path", "")
        
        for directory in [history_db_dir, vector_store_path]:
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
                self.logger.info(f"Created directory: {directory}")
    
    def get_all_user_ids(self) -> List[str]:
        """获取所有已创建的用户ID"""
        return list(self._memory_instances.keys())
    
    def reset_user_memory(self, user_id: str):
        """重置特定用户的记忆"""
        if user_id in self._memory_instances:
            del self._memory_instances[user_id]
            self.logger.info(f"Reset memory for user: {user_id}")


# ================================
# 基础数据模型
# ================================

class AnalysisSession(BaseModel):
    """分析会话记录"""
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_type: str = Field(description="会话类型")
    tickers: List[str] = Field(description="相关股票代码")
    start_time: datetime = Field(default_factory=datetime.now)
    context: Dict[str, Any] = Field(default_factory=dict)
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    final_result: Optional[Dict[str, Any]] = None
    end_time: Optional[datetime] = None
    status: str = Field(default="active", description="会话状态")


class CommunicationRecord(BaseModel):
    """通信记录"""
    communication_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    communication_type: str = Field(description="通信类型")
    participants: List[str] = Field(description="参与者")
    topic: str = Field(description="讨论话题")
    start_time: datetime = Field(default_factory=datetime.now)
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    signal_adjustments: List[Dict[str, Any]] = Field(default_factory=list)
    end_time: Optional[datetime] = None
    status: str = Field(default="active", description="通信状态")


class Notification(BaseModel):
    """通知模型"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sender_agent: str = Field(description="发送方代理ID")
    content: str = Field(description="通知内容")
    urgency: str = Field(default="medium", description="紧急程度: low, medium, high")
    category: str = Field(default="general", description="通知类别")
    timestamp: datetime = Field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "sender_agent": self.sender_agent,
            "content": self.content,
            "urgency": self.urgency,
            "category": self.category,
            "timestamp": self.timestamp.isoformat()
        }


# ================================
# 全局实例
# ================================

# 创建全局的Mem0集成实例
mem0_integration = Mem0Integration()
