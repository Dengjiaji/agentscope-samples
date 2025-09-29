#!/usr/bin/env python3
"""
Mem0配置文件
用于配置IA项目的Mem0集成
"""

import os
from typing import Dict, Any
from dotenv import load_dotenv


def load_mem0_env():
    """加载Mem0专用环境变量"""
    base_dir = os.path.dirname(__file__)
    mem0_env_path = os.path.join(base_dir, '.mem0_env')
    
    if os.path.exists(mem0_env_path):
        load_dotenv(mem0_env_path, override=True)
        return True
    return False

def get_mem0_config() -> Dict[str, Any]:
    """
    获取Mem0配置
    可以通过环境变量覆盖默认设置
    """
    # 确保加载了Mem0环境变量
    load_mem0_env()
    
    base_dir = os.path.dirname(__file__)
    
    config = {
        # 历史数据库路径
        "history_db_path": os.path.join(base_dir, "memory_data", "ia_memory_history.db"),
        
        # 向量存储配置
        "vector_store": {
            "provider": "chroma",
            "config": {
                "collection_name": "ia_analyst_memories",
                "path": os.path.join(base_dir, "memory_data", "ia_chroma_db")
            }
        },
        
        # LLM配置（用于记忆处理）
        "llm": {
            "provider": "openai",
            "config": {
                "model": os.getenv("MEMORY_LLM_MODEL", "qwen3-max-preview"),
                "temperature": 0.1,
                "api_key": os.getenv("OPENAI_API_KEY"),
                "openai_base_url": os.getenv("OPENAI_BASE_URL"),
            }
        },
        
        # 嵌入模型配置
        "embedder": {
            "provider": "openai",
            "config": {
                "model": os.getenv("MEMORY_EMBEDDING_MODEL", "text-embedding-v4"),
                "openai_base_url": os.getenv("OPENAI_BASE_URL"),
            }
        }
    }
    
    return config


def get_analyst_definitions() -> Dict[str, str]:
    """获取分析师定义"""
    return {
        'fundamentals_analyst': '基本面分析师',
        'technical_analyst': '技术分析师',
        'sentiment_analyst': '情绪分析师',
        'valuation_analyst': '估值分析师',
        'portfolio_manager': '投资组合经理',
        'risk_manager': '风险管理师'
    }


# 环境变量检查
def check_environment():
    """检查必要的环境变量"""
    # 首先加载Mem0环境变量
    env_loaded = load_mem0_env()
    
    if not env_loaded:
        print("⚠️ 警告：未找到 .mem0_env 文件")
        print("请创建 .mem0_env 文件并配置必要的环境变量")
        return False
    
    required_vars = ["OPENAI_API_KEY"]
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print("⚠️ 警告：以下环境变量未设置，Mem0可能无法正常工作：")
        for var in missing_vars:
            print(f"   - {var}")
        print("\n请在 .mem0_env 文件中配置这些环境变量")
        return False
    
    return True


if __name__ == "__main__":
    # 测试配置
    print("Mem0配置测试：")
    print("=" * 50)
    
    # 检查环境
    env_ok = check_environment()
    print(f"环境检查: {'✅ 通过' if env_ok else '❌ 失败'}")
    
    # 显示配置
    config = get_mem0_config()
    print(f"\n配置信息：")
    print(f"- 历史数据库: {config['history_db_path']}")
    print(f"- 向量存储: {config['vector_store']['config']['path']}")
    print(f"- LLM模型: {config['llm']['config']['model']}")
    print(f"- 嵌入模型: {config['embedder']['config']['model']}")
    
    # 显示分析师定义
    analysts = get_analyst_definitions()
    print(f"\n分析师定义：")
    for analyst_id, name in analysts.items():
        print(f"- {analyst_id}: {name}")
