import os
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
# logs_and_memory 目录放在项目父目录下
LOGS_AND_MEMORY_DIR = PROJECT_ROOT.parent / "logs_and_memory"
CONFIG_NAME = None
BASE_CONFIG_DIR = PROJECT_ROOT

LIVE_TRADING_DIR = None
MEMORY_DATA_DIR = None
SANDBOX_LOGS_DIR = None

def get_logs_and_memory_dir() -> Path:
    """获取 logs_and_memory 目录路径（位于项目父目录下）"""
    return LOGS_AND_MEMORY_DIR

def get_directory_config(config_name: str):
    global CONFIG_NAME, LIVE_TRADING_DIR, MEMORY_DATA_DIR, SANDBOX_LOGS_DIR
    CONFIG_NAME = config_name
    BASE = LOGS_AND_MEMORY_DIR / config_name
    
    return BASE
