#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ReMe Long-term Memory Implementation
Uses global singleton ChromaVectorStore, distinguishes different users via workspace_id
"""
# flake8: noqa: E501
# pylint: disable=C0301

import logging
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.config import Settings
from flowllm.embedding_model import OpenAICompatibleEmbeddingModel
from flowllm.schema.vector_node import VectorNode
from flowllm.storage.vector_store import ChromaVectorStore

from backend.config.path_config import get_logs_and_memory_dir

from .base import LongTermMemory

logger = logging.getLogger(__name__)

# Maximum character length per memory (text-embedding-v4 limit is approximately 8192 tokens, roughly 8000 characters)
MAX_CONTENT_LENGTH = 8000


class ReMeMemory(LongTermMemory):
    """
    ReMe long-term memory implementation

    Design philosophy:
    - Globally share a single ChromaVectorStore instance (avoid Chroma conflicts)
    - Use workspace_id = f"{base_dir}_{user_id}" to distinguish different configurations and users
    - All data stored in a unified root directory
    """

    # Global singleton: only one ChromaVectorStore per process
    _global_vector_store: Optional[ChromaVectorStore] = None
    _global_embedding_model: Optional[OpenAICompatibleEmbeddingModel] = None
    _global_store_dir: Optional[str] = None

    def __init__(self, base_dir: str):
        """
        Initialize ReMe memory

        Args:
            base_dir: Base directory (config_name), will be used as prefix for workspace_id
        """
        self.base_dir = base_dir

        # Use globally unified storage directory
        if ReMeMemory._global_store_dir is None:
            ReMeMemory._global_store_dir = str(
                get_logs_and_memory_dir()
                / base_dir
                / "memory_data"
                / "reme_vector_store",
            )
            os.makedirs(ReMeMemory._global_store_dir, exist_ok=True)

        self.store_dir = ReMeMemory._global_store_dir

        # Initialize global embedding model (create only once)
        if ReMeMemory._global_embedding_model is None:
            embedding_model_name = os.getenv(
                "MEMORY_EMBEDDING_MODEL",
                "text-embedding-3-small",
            )
            embedding_dim = int(os.getenv("REME_EMBEDDING_DIMENSIONS", "1536"))

            logger.info(
                f"Initializing global Embedding model: {embedding_model_name} (dim={embedding_dim})",
            )
            ReMeMemory._global_embedding_model = (
                OpenAICompatibleEmbeddingModel(
                    dimensions=embedding_dim,
                    model_name=embedding_model_name,
                )
            )

        # Initialize global vector store (create only once, resolve Chroma conflicts)
        if ReMeMemory._global_vector_store is None:
            logger.info(
                f"Initializing global ChromaVectorStore: {self.store_dir}",
            )
            ReMeMemory._global_vector_store = ChromaVectorStore(
                embedding_model=ReMeMemory._global_embedding_model,
                store_dir=self.store_dir,
                batch_size=1024,
            )

            # If SQLite3 file already exists, use PersistentClient to connect directly
            # Clear collections cache to avoid using old client connections
            ReMeMemory._global_vector_store.collections.clear()
            ReMeMemory._global_vector_store._client = (
                chromadb.PersistentClient(
                    path=self.store_dir,
                    settings=Settings(anonymized_telemetry=False),
                )
            )
        # Assign vector_store first to ensure subsequent methods can access it
        self.vector_store = ReMeMemory._global_vector_store

        # Only load all existing workspaces on first creation (use flag to avoid repeated loading)
        if not hasattr(ReMeMemory, "_workspaces_loaded"):
            self._load_all_existing_workspaces()
            ReMeMemory._workspaces_loaded = True

        logger.info(f"ReMe memory initialized (base_dir={base_dir})")

    def _load_all_existing_workspaces(self):
        """Load all existing workspace memories

        If SQLite3 database exists, workspaces are already available.
        Only load from JSONL files if they exist and workspace is not in SQLite3.
        """
        # Check if SQLite3 database exists
        sqlite_file = Path(self.store_dir) / "chroma.sqlite3"
        if sqlite_file.exists():
            # SQLite3 exists, try to list all collections (workspaces)
            try:
                # pylint: disable=protected-access
                all_collections = self.vector_store._client.list_collections()
                logger.info(
                    f"Found {len(all_collections)} workspaces in SQLite3 database",
                )
                for collection in all_collections:
                    node_count = collection.count()
                    print(
                        f"✓ Workspace in SQLite3: {collection.name} ({node_count} memories)",
                    )

            except Exception as e:
                print(f"Failed to list collections from SQLite3: {e}")

        # Check if there are JSONL files that need to be imported (as backup recovery)
        jsonl_files = list(Path(self.store_dir).glob("*.jsonl"))
        if jsonl_files:
            print(
                f"Found {len(jsonl_files)} JSONL files, checking if import needed...",
            )

        for jsonl_file in jsonl_files:
            workspace_id = jsonl_file.stem
            # Only import from JSONL if workspace is not in SQLite3
            if not self.vector_store.exist_workspace(workspace_id):
                try:
                    print(f"Importing workspace from JSONL: {workspace_id}")
                    self.vector_store.load_workspace(
                        workspace_id,
                        path=self.store_dir,
                    )
                    print(f"✓ Loaded workspace from JSONL: {workspace_id}")
                except Exception as e:
                    print(f"✗ Failed to load {workspace_id} from JSONL: {e}")
            else:
                print(
                    f"✓ Workspace {workspace_id} already exists in SQLite3, skipping JSONL import",
                )

    def _get_workspace_id(self, user_id: str) -> str:
        """
        Generate complete workspace_id
        Format: {base_dir}__{user_id}
        This allows distinguishing users with different configurations in the global ChromaVectorStore
        """
        return f"{user_id}"

    def _ensure_workspace(self, user_id: str):
        """Ensure workspace exists"""
        workspace_id = self._get_workspace_id(user_id)

        if not self.vector_store.exist_workspace(workspace_id):
            # Try to load
            workspace_file = os.path.join(
                self.store_dir,
                f"{workspace_id}.jsonl",
            )
            if os.path.exists(workspace_file):
                try:
                    self.vector_store.load_workspace(
                        workspace_id,
                        path=self.store_dir,
                    )
                    return
                except Exception as e:
                    logger.warning(f"Failed to load workspace: {e}")

            # Create new workspace
            self.vector_store.create_workspace(workspace_id)

    def add(
        self,
        content: str,
        user_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Add memory

        If content exceeds MAX_CONTENT_LENGTH, it will be automatically split into multiple records and stored separately
        """
        if not content or not isinstance(content, str):
            logger.warning(
                "⚠️ [ReMeMemory] Input content is empty or not a string type, skipping",
            )
            return ""

        content = content.strip()
        if not content:
            logger.warning(
                "⚠️ [ReMeMemory] Input content is empty (contains only whitespace), skipping",
            )
            return ""

        content_len = len(content)
        logger.debug(
            f"➕ [ReMeMemory] Adding memory: user_id={user_id}, content_len={content_len}",
        )

        self._ensure_workspace(user_id)
        workspace_id = self._get_workspace_id(user_id)

        logger.debug(f"   workspace_id={workspace_id}")

        node_metadata = metadata or {}
        node_metadata["user_id"] = user_id
        node_metadata["base_dir"] = self.base_dir

        # If content exceeds maximum length, split into multiple records
        if content_len > MAX_CONTENT_LENGTH:
            logger.info(
                f"   Content length ({content_len}) exceeds limit "
                f"({MAX_CONTENT_LENGTH}), will split into multiple records",
            )

            # Split content by MAX_CONTENT_LENGTH
            chunks = []
            for i in range(0, content_len, MAX_CONTENT_LENGTH):
                chunk = content[i : i + MAX_CONTENT_LENGTH]
                chunks.append(chunk)

            logger.info(f"   Split into {len(chunks)} records")

            # Create node for each chunk
            nodes = []
            first_node_id = None
            for idx, chunk in enumerate(chunks):
                node_id = str(uuid.uuid4())
                if idx == 0:
                    first_node_id = node_id

                # Record in metadata that this is part of a split record
                chunk_metadata = node_metadata.copy()
                chunk_metadata["chunk_index"] = idx
                chunk_metadata["total_chunks"] = len(chunks)
                chunk_metadata["is_chunked"] = True

                node = VectorNode(
                    unique_id=node_id,
                    workspace_id=workspace_id,
                    content=chunk,
                    metadata=chunk_metadata,
                )
                nodes.append(node)

            # Batch insert all nodes
            self.vector_store.insert(nodes, workspace_id)
            # self.vector_store.dump_workspace(workspace_id, path=self.store_dir)

            logger.debug(
                f"   ✅ Memory added (split into {len(chunks)} records), first node_id={first_node_id}",
            )
            logger.debug(
                f"   Save path: {self.store_dir}/{workspace_id}.jsonl",
            )

            return first_node_id
        else:
            # Content length is normal, store directly
            node_id = str(uuid.uuid4())

            node = VectorNode(
                unique_id=node_id,
                workspace_id=workspace_id,
                content=content,
                metadata=node_metadata,
            )

            self.vector_store.insert([node], workspace_id)
            # self.vector_store.dump_workspace(workspace_id, path=self.store_dir)

            logger.debug(f"   ✅ Memory added, node_id={node_id}")
            logger.debug(
                f"   Save path: {self.store_dir}/{workspace_id}.jsonl",
            )

            return node_id

    def search(
        self,
        query: str,
        user_id: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Search memory"""
        if not query or not isinstance(query, str):
            logger.warning(
                "⚠️ [ReMeMemory] Search query is empty or not a string type, returning empty list",
            )
            return []

        query = query.strip()
        if not query:
            logger.warning(
                "⚠️ [ReMeMemory] Search query is empty (contains only whitespace), returning empty list",
            )
            return []

        # If query text exceeds maximum length, truncate
        if len(query) > MAX_CONTENT_LENGTH:
            logger.warning(
                f"⚠️ [ReMeMemory] Search query length ({len(query)}) exceeds limit ({MAX_CONTENT_LENGTH}), will truncate",
            )
            query = query[:MAX_CONTENT_LENGTH]

        logger.debug(
            f"🔍 [ReMeMemory] Searching memory: user_id={user_id}, query={query[:100]}...",
        )

        self._ensure_workspace(user_id)
        workspace_id = self._get_workspace_id(user_id)

        logger.debug(f"   workspace_id={workspace_id}")
        logger.debug(
            f"   workspace exists: {self.vector_store.exist_workspace(workspace_id)}",
        )

        if not self.vector_store.exist_workspace(workspace_id):
            logger.warning(
                "   ⚠️ Workspace does not exist, returning empty list",
            )
            return []

        # Check number of nodes in workspace
        try:
            all_nodes = list(
                self.vector_store.iter_workspace_nodes(workspace_id),
            )
            logger.debug(f"   Workspace contains {len(all_nodes)} nodes")
        except Exception as e:
            logger.debug(f"   Unable to count nodes: {e}")

        nodes = self.vector_store.search(query, workspace_id, top_k=top_k)

        logger.debug(f"   Search results: {len(nodes)} records")

        return [
            {
                "id": node.unique_id,
                "content": node.content,
                "metadata": node.metadata,
            }
            for node in nodes
        ]

    def update(self, memory_id: str, content: str, user_id: str) -> bool:
        """Update memory

        If content exceeds MAX_CONTENT_LENGTH, it will be automatically split into multiple records and stored separately
        Note: Update will delete old records. If old records are split, need to manually delete all related records
        """
        if not content or not isinstance(content, str):
            logger.warning(
                "⚠️ [ReMeMemory] Update content is empty or not a string type, skipping",
            )
            return False

        content = content.strip()
        if not content:
            logger.warning(
                "⚠️ [ReMeMemory] Update content is empty (contains only whitespace), skipping",
            )
            return False

        try:
            self._ensure_workspace(user_id)
            workspace_id = self._get_workspace_id(user_id)

            # Delete old node
            self.vector_store.delete([memory_id], workspace_id)

            # If content exceeds maximum length, split into multiple records
            content_len = len(content)
            if content_len > MAX_CONTENT_LENGTH:
                logger.info(
                    f"   Update content length ({content_len}) exceeds limit ({MAX_CONTENT_LENGTH}), will split into multiple records",
                )

                # Split content by MAX_CONTENT_LENGTH
                chunks = []
                for i in range(0, content_len, MAX_CONTENT_LENGTH):
                    chunk = content[i : i + MAX_CONTENT_LENGTH]
                    chunks.append(chunk)

                logger.info(f"   Split into {len(chunks)} records")

                # Create node for each chunk (first one uses original memory_id, others create new IDs)
                nodes = []
                for idx, chunk in enumerate(chunks):
                    node_id = memory_id if idx == 0 else str(uuid.uuid4())

                    chunk_metadata = {
                        "user_id": user_id,
                        "base_dir": self.base_dir,
                        "chunk_index": idx,
                        "total_chunks": len(chunks),
                        "is_chunked": True,
                    }

                    node = VectorNode(
                        unique_id=node_id,
                        workspace_id=workspace_id,
                        content=chunk,
                        metadata=chunk_metadata,
                    )
                    nodes.append(node)

                # Batch insert all nodes
                self.vector_store.insert(nodes, workspace_id)
            else:
                # Content length is normal, update directly
                node = VectorNode(
                    unique_id=memory_id,
                    workspace_id=workspace_id,
                    content=content,
                    metadata={"user_id": user_id, "base_dir": self.base_dir},
                )

                self.vector_store.insert([node], workspace_id)

            # self.vector_store.dump_workspace(workspace_id, path=self.store_dir)

            return True
        except Exception as e:
            logger.error(f"Failed to update memory: {e}")
            return False

    def delete(self, memory_id: str, user_id: str) -> bool:
        """Delete memory"""
        try:
            self._ensure_workspace(user_id)
            workspace_id = self._get_workspace_id(user_id)
            self.vector_store.delete([memory_id], workspace_id)
            # self.vector_store.dump_workspace(workspace_id, path=self.store_dir)
            return True
        except Exception as e:
            logger.error(f"Failed to delete memory: {e}")
            return False

    def get_all(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all memories"""
        self._ensure_workspace(user_id)
        workspace_id = self._get_workspace_id(user_id)

        if not self.vector_store.exist_workspace(workspace_id):
            return []

        nodes = list(self.vector_store.iter_workspace_nodes(workspace_id))

        return [
            {
                "id": node.unique_id,
                "content": node.content,
                "metadata": node.metadata,
            }
            for node in nodes
        ]

    def delete_all(self, user_id: str) -> bool:
        """Delete all memories"""
        try:
            workspace_id = self._get_workspace_id(user_id)

            if not self.vector_store.exist_workspace(workspace_id):
                logger.info(
                    f"Workspace {workspace_id} does not exist, no need to clear",
                )
                return True

            # Get all node IDs and delete
            nodes = list(self.vector_store.iter_workspace_nodes(workspace_id))
            node_ids = [node.unique_id for node in nodes]

            if node_ids:
                self.vector_store.delete(node_ids, workspace_id)
                # self.vector_store.dump_workspace(workspace_id, path=self.store_dir)
                logger.info(
                    f"Cleared {len(node_ids)} memories for user {user_id} (workspace {workspace_id})",
                )

            return True
        except Exception as e:
            logger.error(f"Failed to clear memories: {e}")
            return False

    @classmethod
    def reset_global_store(cls):
        """Reset global vector store (mainly for testing)"""
        cls._global_vector_store = None
        cls._global_embedding_model = None
        cls._global_store_dir = None
        logger.info("Global ChromaVectorStore has been reset")
