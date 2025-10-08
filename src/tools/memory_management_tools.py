#!/usr/bin/env python3
"""
记忆管理工具集
为Portfolio Manager提供LangChain tool形式的记忆操作功能
"""

import json
import os
from typing import Dict, List, Any, Optional, Annotated
from langchain_core.tools import tool
from pydantic import Field

# 导入记忆模块
try:
    from src.memory.mem0_core import mem0_integration
    from src.memory.unified_memory import unified_memory_manager
    MEMORY_AVAILABLE = True
except ImportError as e:
    print(f"警告: 无法导入记忆模块: {e}")
    MEMORY_AVAILABLE = False


# 全局记忆实例
_memory_instance = None

def _get_memory_instance():
    """获取记忆实例的单例"""
    global _memory_instance
    if _memory_instance is None and MEMORY_AVAILABLE:
        _memory_instance = mem0_integration.get_memory_instance("shared_analysts")
    return _memory_instance


# ===================== 记忆管理工具 - LangChain装饰器模式 =====================

@tool
def search_and_update_analyst_memory(
    query: Annotated[str, Field(description="搜索查询内容，用于找到需要更新的记忆。例如：'苹果股票分析'、'技术指标预测'等")],
    memory_id: Annotated[str, Field(description="要更新的记忆ID，如果不知道具体ID可以填写'auto'让系统自动搜索")],
    analyst_id: Annotated[str, Field(description="分析师ID，可选值：sentiment_analyst、technical_analyst、fundamentals_analyst、valuation_analyst")],
    new_content: Annotated[str, Field(description="新的记忆内容，用来替换错误的记忆。应该是正确的分析方法或经验总结")],
    reason: Annotated[str, Field(description="更新原因，解释为什么要更新这个记忆，例如：'预测错误需要修正'、'分析方法有误'等")]
) -> Dict[str, Any]:
    """
    搜索并更新分析师的错误记忆内容
    
    这个工具用于修正分析师的错误记忆，通过搜索找到相关记忆并更新为正确内容。
    适用于分析师表现不佳但错误不算严重的情况。
    
    Args:
        query: 搜索查询内容，用于找到需要更新的记忆
        memory_id: 要更新的记忆ID（可填写'auto'自动搜索）
        analyst_id: 分析师ID（sentiment_analyst/technical_analyst/fundamentals_analyst/valuation_analyst）
        new_content: 新的记忆内容，用来替换错误的记忆
        reason: 更新原因，说明为什么要更新这个记忆
        
    Returns:
        包含更新结果的字典，包含status、更新详情等信息
    """
    memory_instance = _get_memory_instance()
    if not memory_instance:
        return {
            'status': 'failed',
            'error': 'Memory system not available',
            'tool_name': 'search_and_update_analyst_memory'
        }
        
    try:
        results = memory_instance.search(
            query=query,
            user_id=analyst_id
        )
        memory_id = results['results'][0]['id']
        result = memory_instance.update(
            memory_id=memory_id,
            data=new_content
        )
        
        return {
            'status': 'success',
            'tool_name': 'search_and_update_analyst_memory',
            'memory_id': memory_id,
            'analyst_id': analyst_id,
            'reason': reason,
            'updated_content': new_content,
            'result': result
        }
        
    except Exception as e:
        return {
            'status': 'failed',
            'tool_name': 'search_and_update_analyst_memory',
            'memory_id': memory_id,
            'analyst_id': analyst_id,
            'error': str(e)
        }


@tool
def search_and_delete_analyst_memory(
    query: Annotated[str, Field(description="搜索查询内容，用于找到需要删除的记忆。例如：'错误的市场预测'、'不准确的技术分析'等")],
    memory_id: Annotated[str, Field(description="要删除的记忆ID，如果不知道具体ID可以填写'auto'让系统自动搜索")],
    analyst_id: Annotated[str, Field(description="分析师ID，可选值：sentiment_analyst、technical_analyst、fundamentals_analyst、valuation_analyst")],
    reason: Annotated[str, Field(description="删除原因，解释为什么要删除这个记忆，例如：'严重错误的预测方法'、'误导性的分析逻辑'等")]
) -> Dict[str, Any]:
    """
    搜索并删除分析师的严重错误记忆
    
    这个工具用于删除分析师的严重错误记忆，适用于分析师表现极差或有严重错误的情况。
    删除操作不可逆，请谨慎使用。
    
    Args:
        query: 搜索查询内容，用于找到需要删除的记忆
        memory_id: 要删除的记忆ID（可填写'auto'自动搜索）
        analyst_id: 分析师ID（sentiment_analyst/technical_analyst/fundamentals_analyst/valuation_analyst）
        reason: 删除原因，解释为什么要删除这个记忆
        
    Returns:
        包含删除结果的字典，包含status、删除详情等信息
    """
    memory_instance = _get_memory_instance()
    if not memory_instance:
        return {
            'status': 'failed',
            'error': 'Memory system not available',
            'tool_name': 'search_and_delete_analyst_memory'
        }
        
    try:
        results = memory_instance.search(
            query=query,
            user_id=analyst_id
        )
        memory_id = results['results'][0]['id']
        result = memory_instance.delete(memory_id=memory_id)
        
        return {
            'status': 'success',
            'tool_name': 'search_and_delete_analyst_memory',
            'memory_id': memory_id,
            'analyst_id': analyst_id,
            'deletion_reason': reason,
            'result': result
        }
        
    except Exception as e:
        return {
            'status': 'failed',
            'tool_name': 'search_and_delete_analyst_memory',
            'memory_id': memory_id,
            'analyst_id': analyst_id,
            'error': str(e)
        }


@tool
def add_reflection_memory(analyst_id: str, content: str, reason: str, date: str) -> Dict[str, Any]:
    """
    为分析师添加反思和指导记忆
    
    Args:
        analyst_id: 分析师ID
        content: 反思内容
        reason: 添加原因
        date: 相关日期
        
    Returns:
        包含添加结果的字典
    """
    memory_instance = _get_memory_instance()
    if not memory_instance:
        return {
            'status': 'failed',
            'error': 'Memory system not available',
            'tool_name': 'add_reflection_memory'
        }
        
    try:
        messages = [
            {
                "role": "user",
                "content": f"Portfolio Manager的反思和指导: {content}"
            }
        ]
        
        result = memory_instance.add(
            messages=messages,
            user_id=analyst_id,
            metadata={
                "memory_type": "pm_reflection",
                "source": "portfolio_manager_review",
                "date": date,
                "reason": reason
            }
        )
        
        return {
            'status': 'success',
            'tool_name': 'add_reflection_memory',
            'analyst_id': analyst_id,
            'reflection_content': content,
            'reason': reason,
            'date': date,
            'result': result
        }
        
    except Exception as e:
        return {
            'status': 'failed',
            'tool_name': 'add_reflection_memory',
            'analyst_id': analyst_id,
            'error': str(e)
        }


# ===================== 获取工具列表的便利函数 =====================

def get_memory_tools():
    """
    获取所有记忆管理工具的列表
    
    Returns:
        记忆管理工具的列表
    """
    return [
        search_and_update_analyst_memory,
        search_and_delete_analyst_memory,
        # add_reflection_memory
    ]


# 使用示例
if __name__ == "__main__":
    print("🛠️ 记忆管理工具集 - LangChain装饰器模式")
    print("=" * 50)
    
    # 显示可用工具
    tools = get_memory_tools()
    print(f"\n📋 可用工具 ({len(tools)}个):")
    for i, tool in enumerate(tools, 1):
        print(f"{i}. {tool.name}: {tool.description.split('Args:')[0].strip()}")
    
    print("\n✅ 记忆管理工具集初始化完成")
