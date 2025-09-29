#!/usr/bin/env python3
"""
调试Mem0配置问题
"""

import os
import sys
from dotenv import load_dotenv

# 添加项目路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

# 加载环境变量
env_path = os.path.join(current_dir, '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)

def debug_environment():
    """调试环境变量"""
    print("🔍 环境变量调试")
    print("=" * 50)
    
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    
    print(f"API Key 存在: {'✅' if api_key else '❌'}")
    if api_key:
        print(f"API Key 长度: {len(api_key)}")
        print(f"API Key 前缀: {api_key[:10] if len(api_key) > 10 else api_key}")
        print(f"API Key 后缀: {api_key[-4:] if len(api_key) > 4 else api_key}")
    
    print(f"Base URL: {base_url}")
    
    return api_key, base_url

def test_openai_direct():
    """直接测试OpenAI API"""
    print("\n🧪 直接测试OpenAI API")
    print("=" * 50)
    
    try:
        import openai
        
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL")
        
        client = openai.OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        
        print("🔄 测试模型列表...")
        models = client.models.list()
        print("✅ OpenAI API连接成功")
        print(f"可用模型数量: {len(models.data)}")
        
        # 测试聊天完成
        print("\n🔄 测试聊天完成...")
        response = client.chat.completions.create(
            model="qwen3-max-preview",
            messages=[
                {"role": "user", "content": "Hello, this is a test message."}
            ],
            max_tokens=10
        )
        print("✅ 聊天完成测试成功")
        print(f"响应: {response.choices[0].message.content}")
        
        return True
        
    except Exception as e:
        print(f"❌ OpenAI API测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_mem0_with_debug():
    """使用调试模式测试Mem0"""
    print("\n🧪 调试模式测试Mem0")
    print("=" * 50)
    
    try:
        from mem0 import Memory
        
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL")
        
        # 使用最简单的配置
        config = {
            "history_db_path": "./debug_memory_history.db",
            "vector_store": {
                "provider": "chroma",
                "config": {
                    "collection_name": "debug_memories",
                    "path": "./debug_chroma_db"
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
        
        print("🔄 创建Memory实例...")
        memory = Memory.from_config(config)
        print("✅ Memory实例创建成功")
        
        # 检查内部配置
        print(f"\n🔍 LLM配置检查:")
        if hasattr(memory, 'llm') and hasattr(memory.llm, 'client'):
            client = memory.llm.client
            print(f"  API Key: {client.api_key[:10]}...{client.api_key[-4:] if len(client.api_key) > 14 else 'SHORT'}")
            print(f"  Base URL: {client.base_url}")
        
        print(f"\n🔍 Embedder配置检查:")
        if hasattr(memory, 'embedding_model') and hasattr(memory.embedding_model, 'client'):
            embed_client = memory.embedding_model.client
            print(f"  API Key: {embed_client.api_key[:10]}...{embed_client.api_key[-4:] if len(embed_client.api_key) > 14 else 'SHORT'}")
            print(f"  Base URL: {embed_client.base_url}")
        
        print("\n🔄 测试记忆添加...")
        result = memory.add(
            messages=[{"role": "user", "content": "这是一个调试测试消息"}],
            user_id="debug_user"
        )
        print("✅ 记忆添加成功")
        print(f"结果: {result}")
        
        # 清理文件
        import shutil
        if os.path.exists("./debug_memory_history.db"):
            os.remove("./debug_memory_history.db")
        if os.path.exists("./debug_chroma_db"):
            shutil.rmtree("./debug_chroma_db")
        
        return True
        
    except Exception as e:
        print(f"❌ Mem0调试测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_environment_variables():
    """测试环境变量设置"""
    print("\n🔧 测试环境变量设置")
    print("=" * 50)
    
    # 检查.env文件
    env_file = os.path.join(current_dir, '.env')
    if os.path.exists(env_file):
        print(f"✅ .env文件存在: {env_file}")
        with open(env_file, 'r') as f:
            lines = f.readlines()
        print(f"📄 .env文件内容行数: {len(lines)}")
        
        for line in lines:
            if line.startswith('OPENAI_API_KEY'):
                print(f"  🔑 找到API Key配置")
            elif line.startswith('OPENAI_BASE_URL'):
                print(f"  🌐 找到Base URL配置")
    else:
        print(f"❌ .env文件不存在: {env_file}")
    
    # 检查系统环境变量
    print(f"\n🌍 系统环境变量:")
    print(f"  OPENAI_API_KEY: {'设置' if os.environ.get('OPENAI_API_KEY') else '未设置'}")
    print(f"  OPENAI_BASE_URL: {'设置' if os.environ.get('OPENAI_BASE_URL') else '未设置'}")

if __name__ == "__main__":
    print("🔍 Mem0配置调试工具")
    print("=" * 60)
    
    # 1. 环境变量调试
    api_key, base_url = debug_environment()
    
    # 2. 测试环境变量设置
    test_environment_variables()
    
    # 3. 直接测试OpenAI API
    if api_key and base_url:
        openai_success = test_openai_direct()
        
        if openai_success:
            # 4. 调试模式测试Mem0
            mem0_success = test_mem0_with_debug()
            
            if mem0_success:
                print("\n🎉 所有测试通过！")
            else:
                print("\n❌ Mem0测试失败")
        else:
            print("\n❌ OpenAI API测试失败，无法继续Mem0测试")
    else:
        print("\n❌ 环境变量缺失，无法进行API测试")
