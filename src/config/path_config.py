import os
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_NAME = None
BASE_CONFIG_DIR = PROJECT_ROOT

LIVE_TRADING_DIR = None
MEMORY_DATA_DIR = None
SANDBOX_LOGS_DIR = None

def get_directory_config(config_name: str):
    global CONFIG_NAME, LIVE_TRADING_DIR, MEMORY_DATA_DIR, SANDBOX_LOGS_DIR
    CONFIG_NAME = config_name
    BASE = BASE_CONFIG_DIR / "logs_and_memory"
    BASE = BASE/config_name
    
    return BASE
