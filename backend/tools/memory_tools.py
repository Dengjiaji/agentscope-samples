#!/usr/bin/env python3
"""
Memory Management Toolkit
Provides memory operation functionality in AgentScope Toolkit format for Portfolio Manager
"""

import json
import os
from typing import Dict, List, Any, Optional, Annotated
from pydantic import Field
from agentscope.tool import Toolkit


from backend.memory import get_memory



# Global base_dir cache
_cached_base_dir = None

def _set_base_dir(base_dir: str):
    """Set base_dir for creating memory instance"""
    global _cached_base_dir
    _cached_base_dir = base_dir


# Global streamer reference (for broadcasting memory operations)
_global_streamer = None

def set_memory_tools_streamer(streamer):
    """Set global streamer for broadcasting memory operations"""
    global _global_streamer
    _global_streamer = streamer

def _get_memory_instance():
    """Get memory instance"""
    global _cached_base_dir
    if not _cached_base_dir:
        return None
    return get_memory(_cached_base_dir)

def _broadcast_memory_operation(operation_type: str, content: str, agent_id: str):
    """Broadcast memory operation to frontend"""
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
            print(f"⚠️ Failed to broadcast memory operation: {e}")


# ===================== Memory Management Tools - AgentScope Tool Functions =====================

def search_and_update_analyst_memory(
    query: Annotated[str, Field(description="Search query content, used to find memories that need updating. Examples: 'Apple stock analysis', 'technical indicator predictions', etc.")],
    memory_id: Annotated[str, Field(description="Memory ID to update, if you don't know the specific ID, you can fill in 'auto' to let the system search automatically")],
    analyst_id: Annotated[str, Field(description="Analyst ID, possible values: sentiment_analyst, technical_analyst, fundamentals_analyst, valuation_analyst")],
    new_content: Annotated[str, Field(description="New memory content to replace incorrect memory. Should be correct analysis methods or experience summaries")],
    reason: Annotated[str, Field(description="Update reason, explaining why this memory needs to be updated, e.g., 'prediction error needs correction', 'analysis method is incorrect', etc.")]
) -> Dict[str, Any]:
    """
    Search and update analyst's incorrect memory content
    
    This tool is used to correct analyst's incorrect memories by searching for related memories and updating them with correct content.
    Suitable for cases where analyst performance is poor but errors are not severe.
    
    Args:
        query: Search query content, used to find memories that need updating
        memory_id: Memory ID to update (can fill 'auto' for automatic search)
        analyst_id: Analyst ID (sentiment_analyst/technical_analyst/fundamentals_analyst/valuation_analyst)
        new_content: New memory content to replace incorrect memory
        reason: Update reason, explaining why this memory needs to be updated
        
    Returns:
        Dictionary containing update results, including status, update details, etc.
    """
    memory_instance = _get_memory_instance()
    if not memory_instance:
        return {
            'status': 'failed',
            'error': 'Memory system not available',
            'tool_name': 'search_and_update_analyst_memory'
        }
        
    try:
        # Broadcast search operation
        _broadcast_memory_operation(
            operation_type="search",
            content=f"Searching memory: {query}",
            agent_id=analyst_id
        )
        
        # Search memory
        search_results = memory_instance.search(
            query=query,
            user_id=analyst_id,
            top_k=1
        )
        
        if not search_results:
            _broadcast_memory_operation(
                operation_type="search_failed",
                content=f"No related memory found: {query}",
                agent_id=analyst_id
            )
            return {
                'status': 'failed',
                'tool_name': 'search_and_update_analyst_memory',
                'error': f'No related memory found: {query}'
            }
        
        # Get found memory
        found_memory = search_results[0]
        memory_id = found_memory['id']
        original_content = found_memory.get('content', '')
        
        # 🔍 Print debug info: show found memory
        print(f"\n{'='*60}")
        print(f"🔍 Memory Update Debug Info")
        print(f"{'='*60}")
        print(f"📌 Analyst: {analyst_id}")
        print(f"🔎 Search Query: {query}")
        print(f"🆔 Memory ID: {memory_id}")
        print(f"\n📖 Original Memory Content:")
        print(f"{'-'*60}")
        print(f"{original_content[:500]}{'...' if len(original_content) > 500 else ''}")
        print(f"{'-'*60}")
        print(f"\n✏️  New Memory Content:")
        print(f"{'-'*60}")
        print(f"{new_content[:500]}{'...' if len(new_content) > 500 else ''}")
        print(f"{'-'*60}")
        print(f"\n💡 Update Reason: {reason}")
        print(f"{'='*60}\n")
        
        # Update memory (using unified API)
        result = memory_instance.update(
            memory_id=memory_id,
            content=new_content,
            user_id=analyst_id
        )
        
        # ✅ Print update success info
        print(f"✅ Memory update successful!")
        print(f"   Memory ID: {memory_id}")
        print(f"   Analyst: {analyst_id}\n")
        
        # Broadcast update operation
        update_msg = f"Update memory: {reason[:80]}..." if len(reason) > 80 else f"Update memory: {reason}"
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
            'original_content': original_content,  # Add original content
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


def search_and_delete_analyst_memory(
    query: Annotated[str, Field(description="Search query content, used to find memories that need deletion. Examples: 'incorrect market predictions', 'inaccurate technical analysis', etc.")],
    memory_id: Annotated[str, Field(description="Memory ID to delete, if you don't know the specific ID, you can fill in 'auto' to let the system search automatically")],
    analyst_id: Annotated[str, Field(description="Analyst ID, possible values: sentiment_analyst, technical_analyst, fundamentals_analyst, valuation_analyst")],
    reason: Annotated[str, Field(description="Deletion reason, explaining why this memory needs to be deleted, e.g., 'severely incorrect prediction method', 'misleading analysis logic', etc.")]
) -> Dict[str, Any]:
    """
    Search and delete analyst's severely incorrect memories
    
    This tool is used to delete analyst's severely incorrect memories, suitable for cases where analyst performance is very poor or has serious errors.
    Deletion operation is irreversible, please use with caution.
    
    Args:
        query: Search query content, used to find memories that need deletion
        memory_id: Memory ID to delete (can fill 'auto' for automatic search)
        analyst_id: Analyst ID (sentiment_analyst/technical_analyst/fundamentals_analyst/valuation_analyst)
        reason: Deletion reason, explaining why this memory needs to be deleted
        
    Returns:
        Dictionary containing deletion results, including status, deletion details, etc.
    """
    memory_instance = _get_memory_instance()
    if not memory_instance:
        return {
            'status': 'failed',
            'error': 'Memory system not available',
            'tool_name': 'search_and_delete_analyst_memory'
        }
        
    try:
        # Broadcast search operation
        _broadcast_memory_operation(
            operation_type="search",
            content=f"Searching memory to delete: {query}",
            agent_id=analyst_id
        )
        
        # Search memory
        search_results = memory_instance.search(
            query=query,
            user_id=analyst_id,
            top_k=1
        )
        
        if not search_results:
            _broadcast_memory_operation(
                operation_type="search_failed",
                content=f"No related memory found: {query}",
                agent_id=analyst_id
            )
            return {
                'status': 'failed',
                'tool_name': 'search_and_delete_analyst_memory',
                'error': f'No related memory found: {query}'
            }
        
        # Get found memory
        found_memory = search_results[0]
        memory_id = found_memory['id']
        memory_content = found_memory.get('content', '')
        
        # 🔍 Print debug info: show memory to delete
        print(f"\n{'='*60}")
        print(f"🗑️  Memory Deletion Debug Info")
        print(f"{'='*60}")
        print(f"📌 Analyst: {analyst_id}")
        print(f"🔎 Search Query: {query}")
        print(f"🆔 Memory ID: {memory_id}")
        print(f"\n📖 Memory Content to Delete:")
        print(f"{'-'*60}")
        print(f"{memory_content[:500]}{'...' if len(memory_content) > 500 else ''}")
        print(f"{'-'*60}")
        print(f"\n⚠️  Deletion Reason: {reason}")
        print(f"{'='*60}\n")
        
        # Delete memory (using unified API)
        result = memory_instance.delete(
            memory_id=memory_id,
            user_id=analyst_id
        )
        
        # ✅ Print deletion success info
        print(f"✅ Memory deletion successful!")
        print(f"   Memory ID: {memory_id}")
        print(f"   Analyst: {analyst_id}\n")
        
        # Broadcast deletion operation
        delete_msg = f"Delete memory: {reason[:80]}..." if len(reason) > 80 else f"Delete memory: {reason}"
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
            'deleted_content': memory_content,  # Add deleted content
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


def add_reflection_memory(analyst_id: str, content: str, reason: str, date: str) -> Dict[str, Any]:
    """
    Add reflection and guidance memory for analyst
    
    Args:
        analyst_id: Analyst ID
        content: Reflection content
        reason: Addition reason
        date: Related date
        
    Returns:
        Dictionary containing addition results
    """
    memory_instance = _get_memory_instance()
    if not memory_instance:
        return {
            'status': 'failed',
            'error': 'Memory system not available',
            'tool_name': 'add_reflection_memory'
        }
        
    try:
        result = memory_instance.add(
            content=f"Portfolio Manager's reflection and guidance: {content}",
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


# ===================== AgentScope Toolkit Integration =====================

def create_memory_toolkit() -> Toolkit:
    """
    Create memory management toolkit (AgentScope native Toolkit)
    
    Returns:
        Toolkit instance
    """
    toolkit = Toolkit()
    
    # Register tool functions - AgentScope will automatically extract parameter info from function signatures and docstrings
    toolkit.register_tool_function(search_and_update_analyst_memory)
    toolkit.register_tool_function(search_and_delete_analyst_memory)
    
    return toolkit


# Usage example
if __name__ == "__main__":
    print("🛠️ Memory Management Toolkit - AgentScope Toolkit Mode")
    print("=" * 50)
    
    # Create and display toolkit
    toolkit = create_memory_toolkit()
    tool_names = list(toolkit.tools.keys())
    
    # print(f"\n📋 Available tools ({len(tool_names)}):")
    # for i, tool_name in enumerate(tool_names, 1):
    #     tool_info = toolkit.tools[tool_name]
        # Extract first line of function docstring as description
    desc = toolkit.get_json_schemas()
    print(f"{desc}")
    
    print("\n✅ Memory management toolkit initialization completed")
