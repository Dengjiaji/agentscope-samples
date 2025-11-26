#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mem0 Long-term Memory Implementation
Directly uses mem0, no adapter layer
"""

import os
import logging
from typing import Dict, List, Any, Optional
from mem0 import Memory

from .base import LongTermMemory
from backend.config.path_config import get_logs_and_memory_dir


logger = logging.getLogger(__name__)


class Mem0Memory(LongTermMemory):
    """Mem0 long-term memory implementation"""

    def __init__(self, base_dir: str):
        """
        Initialize Mem0 memory

        Args:
            base_dir: Storage base directory (config_name)
        """
        self.base_dir = str(get_logs_and_memory_dir() / base_dir)

        # Mem0 configuration
        config = {
            "history_db_path": os.path.join(
                self.base_dir,
                "memory_data",
                "history.db",
            ),
            "vector_store": {
                "provider": "chroma",
                "config": {
                    "collection_name": "memories",
                    "path": os.path.join(
                        self.base_dir,
                        "memory_data",
                        "chroma_db",
                    ),
                },
            },
            "llm": {
                "provider": "openai",
                "config": {
                    "model": os.getenv("MEMORY_LLM_MODEL", "gpt-4o-mini"),
                    "temperature": 0.1,
                    "api_key": os.getenv("OPENAI_API_KEY"),
                    "openai_base_url": os.getenv("OPENAI_BASE_URL"),
                },
            },
            "embedder": {
                "provider": "openai",
                "config": {
                    "model": os.getenv(
                        "MEMORY_EMBEDDING_MODEL",
                        "text-embedding-3-small",
                    ),
                    "api_key": os.getenv("OPENAI_API_KEY"),
                    "openai_base_url": os.getenv("OPENAI_BASE_URL"),
                },
            },
        }

        # Ensure directories exist
        os.makedirs(os.path.dirname(config["history_db_path"]), exist_ok=True)
        os.makedirs(config["vector_store"]["config"]["path"], exist_ok=True)

        # Create shared Memory instance
        self.memory = Memory.from_config(config)
        logger.info(f"Mem0 memory initialized: {self.base_dir}")

    def add(
        self,
        content: str,
        user_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Add memory"""
        logger.debug(
            f"➕ [Mem0Memory] Adding memory: user_id={user_id}, content_len={len(content)}",
        )

        result = self.memory.add(
            messages=[{"role": "user", "content": content}],
            user_id=user_id,
            metadata=metadata or {},
        )

        logger.debug(f"   add result: {result}")

        # Extract memory_id
        if result and "results" in result and len(result["results"]) > 0:
            memory_id = result["results"][0].get("id", "")
            logger.debug(f"   ✅ Memory added, memory_id={memory_id}")
            return memory_id

        logger.warning(f"   ⚠️ Failed to add memory or no ID returned")
        return ""

    def search(
        self,
        query: str,
        user_id: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Search memory"""
        logger.debug(
            f"🔍 [Mem0Memory] Searching memory: user_id={user_id}, query={query[:100]}...",
        )

        results = self.memory.search(query=query, user_id=user_id, limit=top_k)

        logger.debug(f"   Raw result type: {type(results)}")
        logger.debug(
            f"   Raw result length: {len(results) if isinstance(results, list) else 'N/A'}",
        )

        # Standardize return format
        if isinstance(results, list):
            formatted = [
                {
                    "id": r.get("id"),
                    "content": r.get("memory"),
                    "metadata": r.get("metadata", {}),
                }
                for r in results
            ]
            logger.debug(f"   Formatted result: {len(formatted)} records")
            return formatted

        logger.warning(f"   ⚠️ Result format abnormal, returning empty list")
        return []

    def update(self, memory_id: str, content: str, user_id: str) -> bool:
        """Update memory"""
        try:
            self.memory.update(memory_id=memory_id, data=content)
            return True
        except Exception as e:
            logger.error(f"Failed to update memory: {e}")
            return False

    def delete(self, memory_id: str, user_id: str) -> bool:
        """Delete memory"""
        try:
            self.memory.delete(memory_id=memory_id)
            return True
        except Exception as e:
            logger.error(f"Failed to delete memory: {e}")
            return False

    def get_all(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all memories"""
        results = self.memory.get_all(user_id=user_id)

        if isinstance(results, list):
            return [
                {
                    "id": r.get("id"),
                    "content": r.get("memory"),
                    "metadata": r.get("metadata", {}),
                }
                for r in results
            ]
        return []

    def delete_all(self, user_id: str) -> bool:
        """Delete all memories"""
        try:
            self.memory.delete_all(user_id=user_id)
            logger.info(f"Cleared all memories for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to clear memories: {e}")
            return False
