#!/usr/bin/env python3
"""
Mem0兼容性适配器
提供与原有AnalystMemory相同的接口，但底层使用Mem0
"""

from typing import Dict, List, Any, Optional
from datetime import datetime

from src.utils.mem0_env_loader import ensure_mem0_env_loaded
from src.memory import unified_memory_manager, Mem0AnalystMemory


class AnalystMemoryMem0Adapter:
    """
    Mem0适配器，提供与原有AnalystMemory相同的接口
    可以直接替换原有的AnalystMemory使用
    """
    
    def __init__(self, analyst_id: str, analyst_name: str):
        self.analyst_id = analyst_id
        self.analyst_name = analyst_name
        self.creation_time = datetime.now()
        
        # 确保Mem0环境变量已加载
        ensure_mem0_env_loaded()
        
        # 注册到统一记忆管理器
        unified_memory_manager.register_analyst(analyst_id, analyst_name)
        
        # 获取Mem0记忆实例
        self._mem0_memory = unified_memory_manager.get_analyst_memory(analyst_id)
        
        # 兼容性属性
        self.total_analyses = 0
        self.total_communications = 0
        self.last_active_time = datetime.now()
    
    def start_analysis_session(self, session_type: str, tickers: List[str], 
                             context: Dict[str, Any] = None) -> str:
        """开始新的分析会话（兼容原接口）"""
        if self._mem0_memory:
            session_id = self._mem0_memory.start_analysis_session(session_type, tickers, context)
            self.total_analyses += 1
            self.last_active_time = datetime.now()
            return session_id
        return ""
    
    def add_analysis_message(self, session_id: str, role: str, content: str, 
                           metadata: Dict[str, Any] = None):
        """添加分析消息到指定会话（兼容原接口）"""
        if self._mem0_memory:
            self._mem0_memory.add_analysis_message(session_id, role, content, metadata)
            self.last_active_time = datetime.now()
    
    def complete_analysis_session(self, session_id: str, final_result: Dict[str, Any]):
        """完成分析会话（兼容原接口）"""
        if self._mem0_memory:
            self._mem0_memory.complete_analysis_session(session_id, final_result)
            self.last_active_time = datetime.now()
    
    def start_communication(self, communication_type: str, participants: List[str], 
                          topic: str) -> str:
        """开始新的通信（兼容原接口）"""
        if self._mem0_memory:
            comm_id = self._mem0_memory.start_communication(communication_type, participants, topic)
            self.total_communications += 1
            self.last_active_time = datetime.now()
            return comm_id
        return ""
    
    def add_communication_message(self, communication_id: str, speaker: str, 
                                content: str, metadata: Dict[str, Any] = None):
        """添加通信消息（兼容原接口）"""
        if self._mem0_memory:
            self._mem0_memory.add_communication_message(communication_id, speaker, content, metadata)
            self.last_active_time = datetime.now()
    
    def record_signal_adjustment(self, communication_id: str, original_signal: Dict[str, Any], 
                               adjusted_signal: Dict[str, Any], reasoning: str):
        """记录信号调整（兼容原接口）"""
        if self._mem0_memory:
            self._mem0_memory.record_signal_adjustment(communication_id, original_signal, adjusted_signal, reasoning)
            self.last_active_time = datetime.now()
    
    def complete_communication(self, communication_id: str):
        """完成通信（兼容原接口）"""
        if self._mem0_memory:
            self._mem0_memory.complete_communication(communication_id)
            self.last_active_time = datetime.now()
    
    def get_full_context_for_communication(self, tickers: List[str] = None) -> str:
        """获取用于通信的完整上下文（兼容原接口）"""
        if self._mem0_memory:
            return self._mem0_memory.get_full_context_for_communication(tickers)
        
        # 降级处理
        return f"=== {self.analyst_name} 的记忆（Mem0不可用） ===\n身份: {self.analyst_id}\n总分析次数: {self.total_analyses}\n总通信次数: {self.total_communications}"
    
    # def get_analysis_summary(self) -> Dict[str, Any]:
    #     """获取分析总结（兼容原接口）"""
    #     if self._mem0_memory:
    #         summary = self._mem0_memory.get_analysis_summary()
    #         # 添加兼容性字段
    #         summary.update({
    #             "total_analyses": self.total_analyses,
    #             "total_communications": self.total_communications,
    #             "last_active": self.last_active_time.isoformat()
    #         })
    #         return summary
        
    #     # 降级处理
    #     return {
    #         "analyst_id": self.analyst_id,
    #         "analyst_name": self.analyst_name,
    #         "total_analyses": self.total_analyses,
    #         "total_communications": self.total_communications,
    #         "last_active": self.last_active_time.isoformat(),
    #         "memory_system": "mem0_unavailable"
    #     }
    
    def export_memory(self) -> Dict[str, Any]:
        """导出记忆数据（兼容原接口）"""
        if self._mem0_memory:
            return self._mem0_memory.export_memory()
        
        # 降级处理
        return {
            "analyst_id": self.analyst_id,
            "analyst_name": self.analyst_name,
            "creation_time": self.creation_time.isoformat(),
            "stats": {
                "total_analyses": self.total_analyses,
                "total_communications": self.total_communications,
                "last_active_time": self.last_active_time.isoformat()
            },
            "memory_system": "mem0_unavailable"
        }


class AnalystMemoryManagerMem0Adapter:
    """
    Mem0适配器管理器，提供与原有AnalystMemoryManager相同的接口
    """
    
    def __init__(self):
        # 确保Mem0环境变量已加载
        ensure_mem0_env_loaded()
        
        self.analysts: Dict[str, AnalystMemoryMem0Adapter] = {}
        # 由上层（引擎或业务）决定何时注册分析师，避免重复注册
    
    def register_analyst(self, analyst_id: str, analyst_name: str):
        """注册分析师（兼容原接口）"""
        if analyst_id not in self.analysts:
            self.analysts[analyst_id] = AnalystMemoryMem0Adapter(analyst_id, analyst_name)
            print(f"注册分析师记忆（Mem0适配器）: {analyst_name}")
    
    def get_analyst_memory(self, analyst_id: str) -> Optional[AnalystMemoryMem0Adapter]:
        """获取分析师记忆（兼容原接口）"""
        return self.analysts.get(analyst_id)
    
    def get_all_analysts_context(self, tickers: List[str] = None) -> Dict[str, str]:
        """获取所有分析师的上下文（兼容原接口）"""
        contexts = {}
        for analyst_id, memory in self.analysts.items():
            contexts[analyst_id] = memory.get_full_context_for_communication(tickers)
        return contexts
    
    def export_all_memories(self) -> Dict[str, Any]:
        """导出所有记忆（兼容原接口）"""
        return {
            "export_time": datetime.now().isoformat(),
            "memory_system": "mem0_adapter",
            "analysts": {
                analyst_id: memory.export_memory() 
                for analyst_id, memory in self.analysts.items()
            }
        }
    
    def reset_analyst_memory(self, analyst_id: str, analyst_name: str = None):
        """重置指定分析师的记忆（兼容原接口）"""
        old = self.analysts.get(analyst_id)
        name = analyst_name or (old.analyst_name if old else analyst_id)
        
        # 重置底层Mem0记忆
        unified_memory_manager.reset_analyst(analyst_id, name)
        
        # 重新创建适配器实例
        self.analysts[analyst_id] = AnalystMemoryMem0Adapter(analyst_id, name)
        print(f"已重置分析师记忆（Mem0适配器）: {analyst_id} ({name})")


# 创建全局适配器管理器，可以直接替换原有的memory_manager
memory_manager_mem0_adapter = AnalystMemoryManagerMem0Adapter()
