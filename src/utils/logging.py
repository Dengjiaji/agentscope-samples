#!/usr/bin/env python3
"""
Logging configuration module - Unified management of project logging settings
"""

import logging
import os


def setup_logging(level=logging.WARNING, log_file=None, quiet_mode=True):
    """
    Set up project logging configuration
    
    Args:
        level: Log level, default WARNING
        log_file: Log file path, if None then no file writing
        quiet_mode: Whether to enable quiet mode, disable detailed logs for HTTP requests, etc.
    """
    handlers = []
    
    # Add console handler
    handlers.append(logging.StreamHandler())
    
    # Add file handler (if specified)
    if log_file:
        # Get directory path, skip directory creation if file is in current directory
        log_dir = os.path.dirname(log_file)
        if log_dir:  # Only create directory if directory path is not empty
            os.makedirs(log_dir, exist_ok=True)
        handlers.append(logging.FileHandler(log_file))
    
    # Configure basic logging
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=handlers,
        force=True  # Force reconfiguration, override previous settings
    )
    
    # Quiet mode: disable detailed logs for third-party libraries
    if quiet_mode:
        # HTTP request related
        logging.getLogger('httpx').setLevel(logging.WARNING)
        logging.getLogger('openai').setLevel(logging.WARNING)
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('requests').setLevel(logging.WARNING)
        
        # AI/ML related
        logging.getLogger('transformers').setLevel(logging.WARNING)
        logging.getLogger('torch').setLevel(logging.WARNING)
        
        # Data processing related
        logging.getLogger('pandas').setLevel(logging.WARNING)
        logging.getLogger('numpy').setLevel(logging.WARNING)
        
        # Network related
        logging.getLogger('asyncio').setLevel(logging.WARNING)
        logging.getLogger('aiohttp').setLevel(logging.WARNING)


def enable_debug_logging():
    """Enable debug mode logging"""
    logging.getLogger().setLevel(logging.DEBUG)
    logging.info("Debug mode enabled")


def disable_all_logging():
    """Completely disable log output"""
    logging.disable(logging.CRITICAL)


def enable_verbose_logging():
    """Enable verbose log output"""
    logging.getLogger().setLevel(logging.INFO)
    # Re-enable some useful logs
    logging.getLogger('httpx').setLevel(logging.INFO)
    logging.getLogger('openai').setLevel(logging.INFO)


def enable_memory_debug():
    """Enable detailed debug logging for memory system"""
    logging.getLogger('src.memory.reme_memory').setLevel(logging.DEBUG)
    logging.getLogger('src.memory.mem0_memory').setLevel(logging.DEBUG)
    logging.getLogger('src.memory.manager').setLevel(logging.DEBUG)
    logging.getLogger('src.memory.reflection').setLevel(logging.DEBUG)
    logging.getLogger('src.tools.memory_tools').setLevel(logging.DEBUG)
    print("✅ Memory system debug logging enabled")
