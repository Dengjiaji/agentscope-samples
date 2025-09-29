#!/usr/bin/env python3
"""
修复记忆系统配置问题
检查和配置Mem0环境变量，确保记忆系统正常工作
"""

import os
import sys
from dotenv import load_dotenv

def check_and_create_env_file():
    """检查并创建.env文件"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(current_dir, '.env')
    
    print("🔍 检查环境变量配置...")
    
    if not os.path.exists(env_path):
        print("❌ 未找到 .env 文件")
        print("📝 创建示例 .env 文件...")
        
        env_template = """# 项目环境变量配置

# OpenAI API 配置 (必需 - 用于Mem0记忆系统)
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# 模型配置
MODEL_NAME=qwen3-max-preview
MEMORY_LLM_MODEL=qwen3-max-preview
MEMORY_EMBEDDING_MODEL=text-embedding-v4

# Financial Datasets API 配置 (必需 - 用于数据获取)
FINANCIAL_DATASETS_API_KEY=your_financial_datasets_api_key_here

# 其他配置
DEBUG=false
LOG_LEVEL=INFO
"""
        
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write(env_template)
        
        print(f"✅ 已创建 .env 文件: {env_path}")
        print("⚠️ 请编辑 .env 文件，填入正确的API密钥！")
        return False
    else:
        print(f"✅ 找到 .env 文件: {env_path}")
        return True

def validate_env_variables():
    """验证环境变量"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(current_dir, '.env')
    
    # 加载环境变量
    if os.path.exists(env_path):
        load_dotenv(env_path, override=True)
    
    print("\n🔧 验证环境变量...")
    
    required_vars = [
        ('OPENAI_API_KEY', 'OpenAI API密钥'),
        ('OPENAI_BASE_URL', 'OpenAI API地址'),
        ('FINANCIAL_DATASETS_API_KEY', 'Financial Datasets API密钥')
    ]
    
    all_valid = True
    
    for var_name, var_desc in required_vars:
        value = os.getenv(var_name)
        if not value:
            print(f"❌ 缺少 {var_name} ({var_desc})")
            all_valid = False
        elif value == f"your_{var_name.lower()}_here":
            print(f"⚠️ {var_name} 仍为示例值，请设置正确的API密钥")
            all_valid = False
        else:
            # 显示部分值用于确认
            if 'KEY' in var_name:
                display_value = f"{value[:8]}...{value[-4:]}" if len(value) > 12 else "***"
            else:
                display_value = value
            print(f"✅ {var_name}: {display_value}")
    
    return all_valid

def test_mem0_basic():
    """测试Mem0基本功能"""
    print("\n🧪 测试Mem0基本功能...")
    
    try:
        from mem0 import Memory
        
        # 使用简单配置进行测试
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
                    "model": os.getenv("MEMORY_LLM_MODEL", "qwen3-max-preview"),
                    "temperature": 0.1,
                    "api_key": os.getenv("OPENAI_API_KEY"),
                    "openai_base_url": os.getenv("OPENAI_BASE_URL"),
                }
            },
            "embedder": {
                "provider": "openai",
                "config": {
                    "model": os.getenv("MEMORY_EMBEDDING_MODEL", "text-embedding-v4"),
                    "api_key": os.getenv("OPENAI_API_KEY"),
                    "openai_base_url": os.getenv("OPENAI_BASE_URL"),
                }
            }
        }
        
        print("  🔄 创建Memory实例...")
        memory = Memory.from_config(config)
        print("  ✅ Memory实例创建成功")
        
        print("  🔄 测试记忆添加...")
        result = memory.add(
            messages=[{"role": "user", "content": "这是一个测试消息，用于验证记忆系统是否正常工作"}],
            user_id="test_user",
            infer=False
        )
        
        if result is not None:
            print(f"  ✅ 记忆添加成功: {result}")
        else:
            print("  ⚠️ 记忆添加返回None，但没有异常")
        
        print("  🔄 测试记忆搜索...")
        search_result = memory.search(
            query="测试消息",
            user_id="test_user",
            limit=1
        )
        print(f"  ✅ 记忆搜索成功，找到 {len(search_result) if isinstance(search_result, list) else 0} 条记录")
        
        # 清理测试文件
        import shutil
        if os.path.exists("./test_memory_history.db"):
            os.remove("./test_memory_history.db")
        if os.path.exists("./test_chroma_db"):
            shutil.rmtree("./test_chroma_db")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Mem0测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def fix_unified_memory_debug():
    """修复unified_memory.py中的调试代码"""
    print("\n🔧 检查unified_memory.py调试代码...")
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    unified_memory_path = os.path.join(current_dir, 'src', 'memory', 'unified_memory.py')
    
    if not os.path.exists(unified_memory_path):
        print("❌ 未找到unified_memory.py文件")
        return False
    
    # 读取文件内容
    with open(unified_memory_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查是否有pdb.set_trace()
    if 'pdb.set_trace()' in content:
        print("⚠️ 发现调试代码 pdb.set_trace()，建议移除")
        
        # 询问是否移除
        response = input("是否移除调试代码? (y/n): ").strip().lower()
        if response == 'y':
            content = content.replace('\n            pdb.set_trace()', '')
            with open(unified_memory_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print("✅ 已移除调试代码")
        else:
            print("⚠️ 保留调试代码，运行时会暂停")
    else:
        print("✅ 未发现调试代码")
    
    return True

def main():
    """主函数"""
    print("🔧 记忆系统配置修复工具")
    print("=" * 50)
    
    # 1. 检查并创建.env文件
    env_exists = check_and_create_env_file()
    
    # 2. 验证环境变量
    if env_exists:
        env_valid = validate_env_variables()
        
        if env_valid:
            # 3. 测试Mem0功能
            mem0_working = test_mem0_basic()
            
            if mem0_working:
                print("\n🎉 记忆系统配置正常！")
            else:
                print("\n❌ 记忆系统测试失败，请检查API密钥是否正确")
        else:
            print("\n⚠️ 请先正确配置环境变量")
    
    # 4. 检查调试代码
    fix_unified_memory_debug()
    
    print("\n" + "=" * 50)
    print("🔍 问题诊断总结:")
    print("1. 记忆系统返回None的主要原因是缺少OPENAI_API_KEY环境变量")
    print("2. Mem0需要有效的OpenAI API密钥才能进行记忆推理和向量化")
    print("3. 请确保.env文件中的API密钥正确设置")
    print("4. 如果问题仍然存在，请检查API密钥是否有权限访问指定的模型")

if __name__ == "__main__":
    main()
