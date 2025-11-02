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
    from src.memory.memory_factory import get_memory_instance
    MEMORY_AVAILABLE = True
except ImportError as e:
    print(f"警告: 无法导入记忆模块: {e}")
    MEMORY_AVAILABLE = False


# 全局streamer引用（用于广播memory操作）
_global_streamer = None

def set_memory_tools_streamer(streamer):
    """设置全局streamer用于广播memory操作"""
    global _global_streamer
    _global_streamer = streamer

def _get_memory_instance():
    """获取记忆实例（从工厂获取）"""
    if not MEMORY_AVAILABLE:
        return None
    return get_memory_instance()

def _broadcast_memory_operation(operation_type: str, content: str, agent_id: str):
    """广播memory操作到前端"""
    global _global_streamer
    if _global_streamer:
        try:
            _global_streamer.print(
                "memory",
                content,
                agent_id=agent_id,
                operation_type=operation_type
            )
        except Exception as e:
            print(f"⚠️ 广播memory操作失败: {e}")


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
        # 广播搜索操作
        _broadcast_memory_operation(
            operation_type="search",
            content=f"搜索记忆: {query}",
            agent_id=analyst_id
        )
        
        # 搜索记忆
        search_results = memory_instance.search(
            query=query,
            user_id=analyst_id,
            top_k=1
        )
        
        if not search_results.get('results'):
            _broadcast_memory_operation(
                operation_type="search_failed",
                content=f"未找到相关记忆: {query}",
                agent_id=analyst_id
            )
            return {
                'status': 'failed',
                'tool_name': 'search_and_update_analyst_memory',
                'error': f'未找到相关记忆: {query}'
            }
        
        # 获取搜索到的记忆
        found_memory = search_results['results'][0]
        memory_id = found_memory['id']
        original_content = found_memory.get('memory', '')
        
        # 🔍 打印调试信息：显示搜索到的记忆
        print(f"\n{'='*60}")
        print(f"🔍 记忆更新调试信息")
        print(f"{'='*60}")
        print(f"📌 分析师: {analyst_id}")
        print(f"🔎 搜索查询: {query}")
        print(f"🆔 记忆ID: {memory_id}")
        print(f"\n📖 原始记忆内容:")
        print(f"{'-'*60}")
        print(f"{original_content[:500]}{'...' if len(original_content) > 500 else ''}")
        print(f"{'-'*60}")
        print(f"\n✏️  新记忆内容:")
        print(f"{'-'*60}")
        print(f"{new_content[:500]}{'...' if len(new_content) > 500 else ''}")
        print(f"{'-'*60}")
        print(f"\n💡 更新原因: {reason}")
        print(f"{'='*60}\n")
        
        # 获取框架类型，以便正确传递参数
        framework_name = getattr(memory_instance, 'get_framework_name', lambda: 'unknown')()
        
        # 更新记忆
        if framework_name == 'reme':
            # ReMe 框架需要 workspace_id 参数和 metadata
            workspace_id = analyst_id  # 直接使用 analyst_id 作为 workspace_id
            result = memory_instance.update(
                memory_id=memory_id,
                data={
                    'content': new_content,
                    'metadata': {
                        'type': 'memory_update',
                        'analyst_id': analyst_id,
                        'update_reason': reason,
                        'updated_by': 'portfolio_manager'
                    }
                },
                workspace_id=workspace_id
            )
        else:
            # Mem0 框架不需要 workspace_id
            result = memory_instance.update(
                memory_id=memory_id,
                data=new_content
            )
        
        # ✅ 打印更新成功信息
        print(f"✅ 记忆更新成功!")
        print(f"   记忆ID: {memory_id}")
        print(f"   分析师: {analyst_id}\n")
        
        # 广播更新操作
        update_msg = f"更新记忆: {reason[:80]}..." if len(reason) > 80 else f"更新记忆: {reason}"
        _broadcast_memory_operation(
            operation_type="update",
            content=update_msg,
            agent_id=analyst_id
        )
        
        return {
            'status': 'success',
            'tool_name': 'search_and_update_analyst_memory',
            'memory_id': memory_id,
            'analyst_id': analyst_id,
            'reason': reason,
            'original_content': original_content,  # 添加原始内容
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
        # 广播搜索操作
        _broadcast_memory_operation(
            operation_type="search",
            content=f"搜索待删除记忆: {query}",
            agent_id=analyst_id
        )
        
        # 搜索记忆
        search_results = memory_instance.search(
            query=query,
            user_id=analyst_id,
            top_k=1
        )
        
        if not search_results.get('results'):
            _broadcast_memory_operation(
                operation_type="search_failed",
                content=f"未找到相关记忆: {query}",
                agent_id=analyst_id
            )
            return {
                'status': 'failed',
                'tool_name': 'search_and_delete_analyst_memory',
                'error': f'未找到相关记忆: {query}'
            }
        
        # 获取搜索到的记忆
        found_memory = search_results['results'][0]
        memory_id = found_memory['id']
        memory_content = found_memory.get('memory', '')
        
        # 🔍 打印调试信息：显示要删除的记忆
        print(f"\n{'='*60}")
        print(f"🗑️  记忆删除调试信息")
        print(f"{'='*60}")
        print(f"📌 分析师: {analyst_id}")
        print(f"🔎 搜索查询: {query}")
        print(f"🆔 记忆ID: {memory_id}")
        print(f"\n📖 要删除的记忆内容:")
        print(f"{'-'*60}")
        print(f"{memory_content[:500]}{'...' if len(memory_content) > 500 else ''}")
        print(f"{'-'*60}")
        print(f"\n⚠️  删除原因: {reason}")
        print(f"{'='*60}\n")
        
        # 获取框架类型，以便正确传递参数
        framework_name = getattr(memory_instance, 'get_framework_name', lambda: 'unknown')()
        
        # 删除记忆
        if framework_name == 'reme':
            # ReMe 框架需要 workspace_id 参数
            workspace_id = analyst_id  # 直接使用 analyst_id 作为 workspace_id
            result = memory_instance.delete(
                memory_id=memory_id,
                workspace_id=workspace_id
            )
        else:
            # Mem0 框架不需要 workspace_id
            result = memory_instance.delete(memory_id=memory_id)
        
        # ✅ 打印删除成功信息
        print(f"✅ 记忆删除成功!")
        print(f"   记忆ID: {memory_id}")
        print(f"   分析师: {analyst_id}\n")
        
        # 广播删除操作
        delete_msg = f"删除记忆: {reason[:80]}..." if len(reason) > 80 else f"删除记忆: {reason}"
        _broadcast_memory_operation(
            operation_type="delete",
            content=delete_msg,
            agent_id=analyst_id
        )
        
        return {
            'status': 'success',
            'tool_name': 'search_and_delete_analyst_memory',
            'memory_id': memory_id,
            'analyst_id': analyst_id,
            'deleted_content': memory_content,  # 添加被删除的内容
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
