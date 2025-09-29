#!/usr/bin/env python3
"""
测试Mem0配置是否正确
"""

import os
import sys
from dotenv import load_dotenv

# 添加项目路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

# 加载Mem0专用环境变量
mem0_env_path = os.path.join(current_dir, '.mem0_env')
if os.path.exists(mem0_env_path):
    load_dotenv(mem0_env_path, override=True)
    print(f"✅ 已加载Mem0环境配置: {mem0_env_path}")
else:
    print(f"⚠️ 未找到Mem0环境文件: {mem0_env_path}")
    print("请创建 .mem0_env 文件并配置必要的环境变量")


def test_basic_mem0():
    """测试基本的Mem0配置"""
    try:
        from mem0 import Memory
        
        # 检查必要的环境变量
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL")
        
        if not api_key:
            print("❌ 错误: 未找到OPENAI_API_KEY环境变量")
            return False
            
        print(f"🔑 API Key: {api_key[:10]}...{api_key[-4:] if len(api_key) > 14 else 'SHORT'}")
        print(f"🌐 Base URL: {base_url}")
        
        # 使用简单配置测试
        config = {
            "history_db_path": "./test_memory_history.db",
            "vector_store": {
                "provider": "chroma",
                "config": {
                    "collection_name": "test_memories",
                    "path": "./test_chroma_db"
                }
            },
            "llm": {
                "provider": "openai",
                "config": {
                    "model": "qwen3-max-preview",
                    "temperature": 0.1,
                    "api_key": api_key,
                    "openai_base_url": base_url,
                }
            },
            "embedder": {
                "provider": "openai",
                "config": {
                    "model": "text-embedding-v4",
                    "openai_base_url": base_url,
                }
            }
        }
        
        print("🧪 测试Memory.from_config()...")
        print(api_key,base_url)
        memory = Memory.from_config(config)
        print("✅ Memory实例创建成功")
        
        # 测试基本操作
        print("🧪 测试基本记忆操作...")
        memory.add(
            messages=[{"role": "user", "content": "这是一个测试消息"}],
            user_id="test_user"
        )
        print("✅ 记忆添加成功")
        
        # 测试搜索
        memories = memory.search("测试", user_id="test_user", limit=5)
        print(f"✅ 记忆搜索成功，找到 {len(memories)} 条记忆")
        
        # 清理测试文件
        import shutil
        if os.path.exists("./test_memory_history.db"):
            os.remove("./test_memory_history.db")
        if os.path.exists("./test_chroma_db"):
            shutil.rmtree("./test_chroma_db")
        
        print("🎉 Mem0配置测试通过！")
        return True
        
    except Exception as e:
        print(f"❌ Mem0配置测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_integration_import():
    """测试集成模块导入"""
    try:
        print("🧪 测试集成模块导入...")
        from src.memory import mem0_integration
        print("✅ mem0_integration 导入成功")
        
        from src.memory import unified_memory_manager
        print("✅ unified_memory_manager 导入成功")
        
        return True
        
    except Exception as e:
        print(f"❌ 集成模块导入失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 开始Mem0配置测试")
    print("=" * 50)
    
    # 检查环境变量
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️ 警告: 未设置OPENAI_API_KEY环境变量")
    
    # 测试基本配置
    basic_test = test_basic_mem0()
    
    if basic_test:
        # 测试集成导入
        integration_test = test_integration_import()
        
        if integration_test:
            print("\n🎉 所有测试通过！可以运行migrate_to_mem0.py")
        else:
            print("\n❌ 集成测试失败")
    else:
        print("\n❌ 基本配置测试失败")
