#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Memory Manager - Ultra-simple memory manager
Creates corresponding memory instance based on environment variables
"""

import logging
import os
from typing import Dict

from .base import LongTermMemory
from .mem0_memory import Mem0Memory
from .reme_memory import ReMeMemory

logger = logging.getLogger(__name__)


# Global instance cache (supports multiple base_dir)
_memory_instances: Dict[str, LongTermMemory] = {}


def get_memory(base_dir: str) -> LongTermMemory:
    """
    Get memory instance (cached by base_dir)

    Args:
        base_dir: Base directory (config_name)

    Returns:
        Memory instance
    """
    global _memory_instances

    logger.debug(f"[MemoryManager] get_memory(base_dir={base_dir})")

    # If instance for this base_dir already exists, return directly
    if base_dir in _memory_instances:
        logger.debug(
            "   Returning cached instance: "
            f"{type(_memory_instances[base_dir]).__name__}",
        )
        return _memory_instances[base_dir]

    # Get framework type from environment variable
    framework = os.getenv("MEMORY_FRAMEWORK", "mem0").lower()

    logger.info(f"   Creating new memory instance: {framework} ({base_dir})")

    if framework == "reme":
        _memory_instances[base_dir] = ReMeMemory(base_dir)
    else:
        _memory_instances[base_dir] = Mem0Memory(base_dir)

    logger.debug(
        "   ✅ Memory instance created: "
        f"{type(_memory_instances[base_dir]).__name__}",
    )

    return _memory_instances[base_dir]


def reset_memory():
    """Reset global memory instances (mainly for testing)"""
    global _memory_instances
    _memory_instances.clear()

    # If using ReMeMemory, also need to reset its global vector store
    framework = os.getenv("MEMORY_FRAMEWORK", "mem0").lower()
    if framework == "reme":
        ReMeMemory.reset_global_store()


def reset_analyst_memory(analyst_id: str, base_dir: str) -> bool:
    """
    Reset specified analyst's memory

    Args:
        analyst_id: Analyst ID
        base_dir: Base directory (config_name)

    Returns:
        Whether successful
    """
    memory = get_memory(base_dir)
    success = memory.delete_all(analyst_id)

    if success:
        logger.info(f"Reset analyst {analyst_id}'s memory")
    else:
        logger.error(f"Failed to reset analyst {analyst_id}'s memory")

    return success
