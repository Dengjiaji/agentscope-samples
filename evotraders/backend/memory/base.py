#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Long-term Memory Base Interface
Reference AgentScope design, provides unified memory interface
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class LongTermMemory(ABC):
    """Long-term memory abstract base class"""

    @abstractmethod
    def add(
        self,
        content: str,
        user_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Add memory

        Args:
            content: Memory content
            user_id: User/analyst ID
            metadata: Metadata

        Returns:
            Memory ID
        """

    @abstractmethod
    def search(
        self,
        query: str,
        user_id: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Search memory

        Args:
            query: Search query
            user_id: User/analyst ID
            top_k: Number of results to return

        Returns:
            Search result list
        """

    @abstractmethod
    def update(self, memory_id: str, content: str, user_id: str) -> bool:
        """
        Update memory

        Args:
            memory_id: Memory ID
            content: New content
            user_id: User/analyst ID

        Returns:
            Whether successful
        """

    @abstractmethod
    def delete(self, memory_id: str, user_id: str) -> bool:
        """
        Delete memory

        Args:
            memory_id: Memory ID
            user_id: User/analyst ID

        Returns:
            Whether successful
        """

    @abstractmethod
    def get_all(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all memories for a user

        Args:
            user_id: User/analyst ID

        Returns:
            Memory list
        """

    @abstractmethod
    def delete_all(self, user_id: str) -> bool:
        """
        Delete all memories for a user

        Args:
            user_id: User/analyst ID

        Returns:
            Whether successful
        """
