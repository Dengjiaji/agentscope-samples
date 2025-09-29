# 导入项目的memory模块
try:
    from src.memory.mem0_core import mem0_integration
    from src.memory.unified_memory import unified_memory_manager
    from mem0 import Memory
    MEM0_AVAILABLE = True
    print("成功导入项目Memory模块")
except ImportError as e:
    print(f"无法导入项目Memory模块: {e}")
    MEM0_AVAILABLE = False
import pdb
class MemoryDataViewer:
    """Memory数据查看器"""
    
    def __init__(self):
        """初始化查看器"""
        
        # 初始化Memory实例
        self.memory_instance = None
        if MEM0_AVAILABLE:
            try:
                self.memory_instance = mem0_integration.get_memory_instance("shared_analysts")
                print(f"Memory实例状态: 已连接到项目实例")
            except Exception as e:
                print(f"Memory实例状态: 连接失败 - {e}")
        else:
            print(f"Memory实例状态: 不可用")
        
        print("="*60)
    def get_all_memories(self, user_id: str):
        """获取用户的所有记忆"""
        if not self.memory_instance:
            print("Memory实例不可用")
            return None
        
        print(f"\n获取所有记忆 - 用户: {user_id}")
        
        try:
            memories = self.memory_instance.get_all(user_id=user_id)
            print(f"找到 {len(memories)} 条记忆")
            
            return memories
        except Exception as e:
            print(f"获取记忆失败: {str(e)}")
            return None
    
    def search_memories(self, query: str, user_id: str, limit: int = 5):
        """搜索记忆"""
        if not self.memory_instance:
            print("Memory实例不可用")
            return None
        
        print(f"\n搜索记忆")
        print(f"查询: {query}")
        print(f"用户ID: {user_id}")
        print(f"限制: {limit}")
        
        try:
            results = self.memory_instance.search(
                query=query, 
                user_id=user_id,
                limit=limit
            )
            print(f"找到 {len(results)} 条相关记忆")
            
            for i, memory in enumerate(results, 1):
                score = memory.get('score', 0)
                print(f"\n结果 {i} (相关性: {score:.3f}):")
                print(f"  ID: {memory.get('id', 'N/A')}")
                print(f"  内容: {memory.get('memory', 'N/A')}")
                print(f"  创建时间: {memory.get('created_at', 'N/A')}")
                if memory.get('metadata'):
                    print(f"  元数据: {json.dumps(memory['metadata'], ensure_ascii=False)}")
            
            return results
        except Exception as e:
            print(f"搜索记忆失败: {str(e)}")
            return None
    
    def get_memory_by_id(self, memory_id: str):
        """根据ID获取特定记忆"""
        if not self.memory_instance:
            print("Memory实例不可用")
            return None
        
        print(f"\n获取记忆 - ID: {memory_id}")
        
        try:
            memory = self.memory_instance.get(memory_id=memory_id)
            if memory:
                print(f"记忆详情:")
                print(f"  ID: {memory.get('id', 'N/A')}")
                print(f"  内容: {memory.get('memory', 'N/A')}")
                print(f"  创建时间: {memory.get('created_at', 'N/A')}")
                print(f"  更新时间: {memory.get('updated_at', 'N/A')}")
                if memory.get('metadata'):
                    print(f"  元数据: {json.dumps(memory['metadata'], indent=2, ensure_ascii=False)}")
            else:
                print("未找到指定的记忆")
            
            return memory
        except Exception as e:
            print(f"获取记忆失败: {str(e)}")
            return None
    
    def update_memory(self, memory_id: str, data: str):
        """更新记忆"""
        if not self.memory_instance:
            print("Memory实例不可用")
            return None
        
        print(f"\n更新记忆 - ID: {memory_id}")
        print(f"新内容: {data}")
        
        try:
            result = self.memory_instance.update(memory_id=memory_id, data=data)
            print(f"记忆更新成功!")
            print(f"返回结果: {json.dumps(result, indent=2, ensure_ascii=False)}")
            return result
        except Exception as e:
            print(f"记忆更新失败: {str(e)}")
            return None
    
    def delete_memory(self, memory_id: str):
        """删除记忆"""
        if not self.memory_instance:
            print("Memory实例不可用")
            return None
        
        print(f"\n删除记忆 - ID: {memory_id}")
        
        try:
            result = self.memory_instance.delete(memory_id=memory_id)
            print(f"记忆删除成功!")
            return result
        except Exception as e:
            print(f"记忆删除失败: {str(e)}")
            return None
    
    def delete_all_memories(self, user_id: str):
        """删除用户的所有记忆"""
        if not self.memory_instance:
            print("Memory实例不可用")
            return None
        
        print(f"\n删除所有记忆 - 用户: {user_id}")
        print("警告: 这将删除该用户的所有记忆!")
        
        try:
            result = self.memory_instance.delete_all(user_id=user_id)
            print(f"所有记忆删除成功!")
            return result
        except Exception as e:
            print(f"删除所有记忆失败: {str(e)}")
            return None
    
    def memory_history(self, memory_id: str):
        """获取记忆历史"""
        if not self.memory_instance:
            print("Memory实例不可用")
            return None
        
        print(f"\n记忆历史 - ID: {memory_id}")
        
        try:
            history = self.memory_instance.history(memory_id=memory_id)
            print(f"找到 {len(history)} 条历史记录")
            
            for i, record in enumerate(history, 1):
                print(f"\n历史记录 {i}:")
                print(f"  ID: {record.get('id', 'N/A')}")
                print(f"  内容: {record.get('memory', 'N/A')}")
                print(f"  时间: {record.get('created_at', 'N/A')}")
                if record.get('metadata'):
                    print(f"  元数据: {json.dumps(record['metadata'], ensure_ascii=False)}")
            
            return history
        except Exception as e:
            print(f"获取记忆历史失败: {str(e)}")
            return None
    
    def run_memory_demo(self):
        """运行记忆演示"""
        if not self.memory_instance:
            print("Memory实例不可用，无法运行演示")
            return
        
        print(f"\n=== 记忆系统演示 ===")
        
        # 1. 添加示例记忆
        demo_messages = [
            {"role": "user", "content": "我今天计划看电影。有什么推荐吗？"},
            {"role": "assistant", "content": "推荐惊悚片怎么样？通常很吸引人。"},
            {"role": "user", "content": "我不太喜欢惊悚片，但我喜欢科幻电影。"},
            {"role": "assistant", "content": "明白了！我会避免推荐惊悚片，今后推荐科幻电影。"}
        ]
        
        demo_metadata = {"category": "movie_recommendations", "demo": True}
        
        print("1. 添加演示记忆...")
        result = self.add_memory_experiment(
            user_id="alice_demo", 
            messages=demo_messages, 
            metadata=demo_metadata
        )
        
        if result:
            # 2. 获取所有记忆
            print("\n2. 获取所有记忆...")
            all_memories = self.get_all_memories("alice_demo")
            
            # 3. 搜索记忆
            print("\n3. 搜索相关记忆...")
            search_results = self.search_memories("电影偏好", "alice_demo")
            
            # 4. 如果有记忆ID，展示更多功能
            if all_memories and len(all_memories) > 0:
                memory_id = all_memories[0].get('id')
                if memory_id:
                    print(f"\n4. 获取特定记忆 (ID: {memory_id})...")
                    specific_memory = self.get_memory_by_id(memory_id)
                    
                    print(f"\n5. 获取记忆历史...")
                    history = self.memory_history(memory_id)
        
        print(f"\n演示完成!")


# memory_data_dir = "/Users/wy/Downloads/Project/IA/memory_data"
# viewer = MemoryDataViewer()


memo = mem0_integration.get_memory_instance("shared_analysts")
pdb.set_trace()
