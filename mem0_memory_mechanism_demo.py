#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mem0 记忆机制详解演示

这个脚本详细演示了 mem0 如何处理和提取记忆：
1. 事实提取（Fact Extraction）
2. 记忆总结和压缩
3. 记忆更新机制
4. 不同类型的记忆存储
"""

import os
from mem0 import Memory
import json


def setup_environment():
    """设置环境变量"""
    os.environ["OPENAI_API_KEY"] = "sk-0JVspnhOLC"
    os.environ["OPENAI_BASE_URL"] = "https://dashscope.aliyuncs.com/compatible-mode/v1"


def create_memory_instance():
    """创建 Memory 实例"""
    config = {
        "history_db_path": "./mem0_mechanism_history.db",
        "vector_store": {
            "provider": "chroma",
            "config": {
                "collection_name": "mechanism_demo",
                "path": "./mem0_mechanism_chroma"
            }
        },
        "llm": {
            "provider": "openai",
            "config": {
                "model": "qwen3-max-preview",
                "temperature": 0.1,
                "openai_base_url": os.environ.get("OPENAI_BASE_URL"),
            }
        },
        "embedder": {
            "provider": "openai",
            "config": {
                "model": "text-embedding-v4",
                "openai_base_url": os.environ.get("OPENAI_BASE_URL"),
            }
        }
    }
    
    return Memory.from_config(config)


def demonstrate_fact_extraction():
    """演示事实提取机制"""
    print("🧠 Mem0 记忆机制详解")
    print("=" * 60)
    
    print("\n📚 什么是记忆提取？")
    print("-" * 30)
    print("Mem0 不是简单地存储原始对话，而是使用 LLM 智能提取关键事实。")
    print("这个过程叫做 'Fact Extraction'（事实提取）。")
    
    print("\n🔍 事实提取的工作原理：")
    print("1. 📝 输入：原始对话内容")
    print("2. 🤖 LLM 分析：使用专门的提示词分析对话")
    print("3. 📋 提取事实：识别关键信息和偏好")
    print("4. 💾 存储：将提取的事实存储到向量数据库")
    print("5. 🔄 更新：与现有记忆比较，决定添加、更新或删除")


def demonstrate_memory_types():
    """演示不同类型的记忆"""
    print("\n🧩 Mem0 支持的记忆类型：")
    print("-" * 30)
    
    memory_types = {
        "工作记忆": "短期会话感知，当前对话的上下文",
        "事实记忆": "长期结构化知识，如偏好、设置",
        "情景记忆": "记录特定的过去对话",
        "语义记忆": "随时间构建的一般知识"
    }
    
    for mem_type, description in memory_types.items():
        print(f"• {mem_type}: {description}")


def demonstrate_with_examples():
    """通过实际例子演示记忆处理"""
    print("\n🎯 实际例子演示")
    print("=" * 60)
    
    memory = create_memory_instance()
    
    # 示例1：复杂对话的事实提取
    print("\n📝 示例1：复杂对话 → 事实提取")
    print("-" * 40)
    
    complex_conversation = [
        {"role": "user", "content": "你好，我叫张三，我是一名在北京工作的软件工程师"},
        {"role": "assistant", "content": "你好张三！很高兴认识你。"},
        {"role": "user", "content": "我最近在学习机器学习，特别是深度学习方面的内容"},
        {"role": "assistant", "content": "机器学习是很有前景的领域！"},
        {"role": "user", "content": "我平时喜欢喝咖啡，最喜欢的是拿铁，不太喜欢美式咖啡"},
        {"role": "assistant", "content": "了解，你偏好奶咖类型的饮品。"},
        {"role": "user", "content": "对了，我每天早上9点开始工作，下午6点下班，周末喜欢去爬山"},
        {"role": "assistant", "content": "规律的工作时间和健康的爱好，很不错！"}
    ]
    
    print("原始对话内容：")
    for msg in complex_conversation:
        role_name = "用户" if msg["role"] == "user" else "助手"
        print(f"  {role_name}: {msg['content']}")
    
    print("\n🔄 正在进行事实提取...")
    try:
        result = memory.add(complex_conversation, user_id="zhang_san", infer = False)
        print("✅ 事实提取完成")
        print(result)

        if isinstance(result, dict) and "results" in result:
            extracted_facts = result["results"]
            print(f"\n📋 提取到的事实数量: {len(extracted_facts)}")
            
            for i, fact in enumerate(extracted_facts):
                if isinstance(fact, dict):
                    memory_text = fact.get("memory", fact.get("content", ""))
                    event_type = fact.get("event", "UNKNOWN")
                    print(f"  {i+1}. [{event_type}] {memory_text}")
                else:
                    print(f"  {i+1}. {fact}")
        else:
            print(f"结果格式: {result}")
            
    except Exception as e:
        print(f"❌ 事实提取失败: {e}")
    
    # 示例2：记忆查询和相关性
    print("\n🔍 示例2：记忆查询和相关性匹配")
    print("-" * 40)
    
    queries = [
        "张三的职业是什么？",
        "他有什么饮品偏好？",
        "他的工作时间安排如何？",
        "他在学习什么技术？",
        "他的休闲活动是什么？"
    ]
    
    for query in queries:
        print(f"\n🔍 查询: {query}")
        try:
            search_result = memory.search(query, user_id="zhang_san", limit=2)
            
            if search_result and search_result.get("results"):
                for result in search_result["results"]:
                    memory_text = result.get("memory", "")
                    score = result.get("score", 0)
                    print(f"   📌 记忆: {memory_text}")
                    print(f"   📊 相关性分数: {score:.3f}")
            else:
                print("   ❌ 没有找到相关记忆")
                
        except Exception as e:
            print(f"   ❌ 查询失败: {e}")


def demonstrate_memory_updates():
    """演示记忆更新机制"""
    print("\n🔄 示例3：记忆更新机制")
    print("-" * 40)
    
    memory = create_memory_instance()
    
    print("第一次添加信息：")
    first_conversation = [
        {"role": "user", "content": "我喜欢喝咖啡，特别是拿铁"},
        {"role": "assistant", "content": "好的，记住了你喜欢拿铁咖啡"}
    ]
    
    try:
        result1 = memory.add(first_conversation, user_id="update_demo")
        print("✅ 第一次记忆添加完成")
        
        print("\n第二次添加相关但更详细的信息：")
        second_conversation = [
            {"role": "user", "content": "其实我不只喜欢拿铁，我还喜欢卡布奇诺和摩卡，但不喜欢美式咖啡"},
            {"role": "assistant", "content": "了解，你喜欢奶咖系列但不喜欢美式"}
        ]
        
        result2 = memory.add(second_conversation, user_id="update_demo")
        print("✅ 第二次记忆添加完成")
        
        print("\n📋 查看最终的记忆内容：")
        all_memories = memory.get_all(user_id="update_demo")
        
        if all_memories:
            memory_list = all_memories if isinstance(all_memories, list) else all_memories.get("results", [])
            for i, mem in enumerate(memory_list):
                if isinstance(mem, dict):
                    memory_text = mem.get("memory", mem.get("content", ""))
                    print(f"   {i+1}. {memory_text}")
                else:
                    print(f"   {i+1}. {mem}")
        
        print("\n💡 注意：Mem0 会智能地合并和更新相关记忆，而不是简单地重复存储！")
        
    except Exception as e:
        print(f"❌ 记忆更新演示失败: {e}")


def explain_memory_storage():
    """解释记忆存储机制"""
    print("\n💾 记忆存储机制详解")
    print("=" * 60)
    
    print("🗃️ Mem0 使用多层存储架构：")
    print("\n1. 📝 历史数据库 (SQLite)")
    print("   • 存储完整的对话历史")
    print("   • 保持对话的时间顺序")
    print("   • 支持查询和审计")
    
    print("\n2. 🧠 向量数据库 (ChromaDB/Qdrant等)")
    print("   • 存储提取的事实和记忆")
    print("   • 使用嵌入向量进行语义搜索")
    print("   • 支持相似性匹配")
    
    print("\n3. 🔗 图数据库 (可选)")
    print("   • 存储实体关系")
    print("   • 支持复杂的关系查询")
    print("   • 构建知识图谱")
    
    print("\n🎯 记忆处理流程：")
    print("输入对话 → LLM事实提取 → 向量嵌入 → 相似性比较 → 记忆更新 → 存储")
    
    print("\n🔄 记忆操作类型：")
    operations = {
        "ADD": "添加新的记忆事实",
        "UPDATE": "更新现有记忆（更详细或更准确）",
        "DELETE": "删除矛盾或过时的记忆",
        "NONE": "无变化（信息已存在）"
    }
    
    for op, desc in operations.items():
        print(f"   • {op}: {desc}")


def main():
    """主演示函数"""
    setup_environment()
    
    # 理论解释
    demonstrate_fact_extraction()
    demonstrate_memory_types()
    explain_memory_storage()
    
    # 实际演示
    demonstrate_with_examples()
    demonstrate_memory_updates()
    
    print("\n🎉 记忆机制演示完成！")
    print("\n📝 总结要点：")
    print("1. ✅ Mem0 显示的不是原始对话，而是LLM提取的关键事实")
    print("2. ✅ 记忆会被智能压缩、合并和更新")
    print("3. ✅ 支持语义搜索，能理解查询意图")
    print("4. ✅ 使用多层存储，既保持历史又优化检索")
    print("5. ✅ 自动去重和冲突解决，避免信息冗余")


if __name__ == "__main__":
    main()
