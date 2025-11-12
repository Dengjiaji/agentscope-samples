"""
虚拟时钟 - 用于 live脚本 debug 时间模拟和加速调试

功能：
1. 可以设置任意起始时间
2. 支持时间加速（例如60倍速）
3. 全局单例，整个系统使用统一的虚拟时间
4. 可以暂停/恢复/重置
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional
import threading


class VirtualClock:
    """虚拟时钟 - 支持时间模拟和加速"""
    
    def __init__(self, 
                 start_time: Optional[datetime] = None,
                 time_accelerator: float = 1.0,
                 enabled: bool = False):
        """
        初始化虚拟时钟
        
        Args:
            start_time: 起始时间（默认为当前时间）
            time_accelerator: 时间加速倍数（1.0=正常，60.0=60倍速）
            enabled: 是否启用虚拟时钟（False时使用真实系统时间）
        """
        self.enabled = enabled
        self.time_accelerator = time_accelerator
        
        # 真实时间的起点
        self.real_start_time = datetime.now(timezone.utc)
        
        # 虚拟时间的起点
        if start_time:
            if start_time.tzinfo is None:
                # 如果没有时区信息，假设是UTC
                self.virtual_start_time = start_time.replace(tzinfo=timezone.utc)
            else:
                self.virtual_start_time = start_time
        else:
            self.virtual_start_time = self.real_start_time
        
        # 暂停状态
        self.paused = False
        self.pause_real_time = None
        self.pause_virtual_time = None
        
        # 线程锁
        self.lock = threading.Lock()
    
    def now(self, tz: Optional[timezone] = None) -> datetime:
        """
        获取当前时间
        
        Args:
            tz: 目标时区（默认UTC）
        
        Returns:
            当前时间（虚拟时间或真实时间）
        """
        if not self.enabled:
            # 未启用虚拟时钟，返回真实时间
            return datetime.now(tz or timezone.utc)
        
        with self.lock:
            if self.paused:
                # 暂停状态，返回暂停时的虚拟时间
                current_time = self.pause_virtual_time
            else:
                # 计算虚拟时间
                real_elapsed = datetime.now(timezone.utc) - self.real_start_time
                virtual_elapsed = real_elapsed * self.time_accelerator
                current_time = self.virtual_start_time + virtual_elapsed
            
            # 转换时区
            if tz:
                return current_time.astimezone(tz)
            return current_time
    
    def set_time(self, new_time: datetime):
        """
        设置虚拟时间（跳转到指定时间）
        
        Args:
            new_time: 新的虚拟时间
        """
        if not self.enabled:
            raise RuntimeError("虚拟时钟未启用，无法设置时间")
        
        with self.lock:
            if new_time.tzinfo is None:
                new_time = new_time.replace(tzinfo=timezone.utc)
            
            self.real_start_time = datetime.now(timezone.utc)
            self.virtual_start_time = new_time
            
            if self.paused:
                self.pause_real_time = self.real_start_time
                self.pause_virtual_time = new_time
    
    def pause(self):
        """暂停虚拟时钟"""
        if not self.enabled:
            return
        
        with self.lock:
            if not self.paused:
                self.paused = True
                self.pause_real_time = datetime.now(timezone.utc)
                
                # 计算暂停时的虚拟时间
                real_elapsed = self.pause_real_time - self.real_start_time
                virtual_elapsed = real_elapsed * self.time_accelerator
                self.pause_virtual_time = self.virtual_start_time + virtual_elapsed
    
    def resume(self):
        """恢复虚拟时钟"""
        if not self.enabled:
            return
        
        with self.lock:
            if self.paused:
                # 重新设置起点，使虚拟时间从暂停点继续
                self.real_start_time = datetime.now(timezone.utc)
                self.virtual_start_time = self.pause_virtual_time
                self.paused = False
    
    def set_accelerator(self, accelerator: float):
        """
        设置时间加速倍数
        
        Args:
            accelerator: 新的加速倍数
        """
        if not self.enabled:
            return
        
        with self.lock:
            # 先计算当前虚拟时间
            current_virtual = self.now()
            
            # 更新加速倍数
            self.time_accelerator = accelerator
            
            # 重新设置起点
            self.real_start_time = datetime.now(timezone.utc)
            self.virtual_start_time = current_virtual
    
    async def sleep(self, seconds: float):
        """
        异步睡眠（考虑时间加速）
        
        Args:
            seconds: 虚拟时间的秒数
        """
        if not self.enabled:
            await asyncio.sleep(seconds)
        else:
            # 根据加速倍数调整实际睡眠时间
            real_seconds = seconds / self.time_accelerator
            await asyncio.sleep(real_seconds)
    
    def get_info(self) -> dict:
        """获取虚拟时钟信息"""
        return {
            'enabled': self.enabled,
            'time_accelerator': self.time_accelerator,
            'current_time': self.now().isoformat(),
            'paused': self.paused,
            'real_start_time': self.real_start_time.isoformat(),
            'virtual_start_time': self.virtual_start_time.isoformat()
        }


# 全局虚拟时钟实例
_global_clock: Optional[VirtualClock] = None


def init_virtual_clock(start_time: Optional[datetime] = None,
                       time_accelerator: float = 1.0,
                       enabled: bool = False) -> VirtualClock:
    """
    初始化全局虚拟时钟
    
    Args:
        start_time: 起始时间（默认为当前时间）
        time_accelerator: 时间加速倍数
        enabled: 是否启用虚拟时钟
    
    Returns:
        虚拟时钟实例
    """
    global _global_clock
    _global_clock = VirtualClock(
        start_time=start_time,
        time_accelerator=time_accelerator,
        enabled=enabled
    )
    return _global_clock


def get_virtual_clock() -> VirtualClock:
    """
    获取全局虚拟时钟实例
    
    Returns:
        虚拟时钟实例
    """
    global _global_clock
    if _global_clock is None:
        # 如果未初始化，创建一个默认的（未启用）
        _global_clock = VirtualClock(enabled=False)
    return _global_clock


def virtual_now(tz: Optional[timezone] = None) -> datetime:
    """
    获取当前虚拟时间（便捷函数）
    
    Args:
        tz: 目标时区
    
    Returns:
        当前时间
    """
    return get_virtual_clock().now(tz)


async def virtual_sleep(seconds: float):
    """
    虚拟睡眠（便捷函数）
    
    Args:
        seconds: 虚拟时间的秒数
    """
    await get_virtual_clock().sleep(seconds)

