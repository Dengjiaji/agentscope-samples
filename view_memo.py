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


memo = mem0_integration.get_memory_instance("shared_analysts")
pdb.set_trace()


# memo.get_all(user_id='fundamentals_analyst')
# memo.get_all(user_id='technical_analyst')
# memo.get_all(user_id='sentiment_analyst')
# memo.get_all(user_id='valuation_analyst')
# memo.get_all(user_id='risk_manager')
# memo.get_all(user_id='portfolio_manager')


#memo.search(query='recent analysis for ticker apple',user_id ='fundamental_analyst') 
#memo.search(query='recent analysis for ticker apple',user_id ='fundamental_analyst')
#memo.add(messages, user_id="alice", metadata={"category": "movie_recommendations"})
#memo.update(memory_id="892db2ae-06d9-49e5-8b3e-585ef9b85b8e", data="I love India, it is my favorite country.")
#memo.delete(memory_id="892db2ae-06d9-49e5-8b3e-585ef9b85b8e")
