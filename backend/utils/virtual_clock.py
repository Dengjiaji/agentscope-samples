# -*- coding: utf-8 -*-
"""
Virtual Clock - For live script debug time simulation and accelerated debugging

Features:
1. Can set arbitrary start time
2. Supports time acceleration (e.g., 60x speed)
3. Global singleton, entire system uses unified virtual time
4. Can pause/resume/reset
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional
import threading


class VirtualClock:
    """Virtual clock - supports time simulation and acceleration"""

    def __init__(
        self,
        start_time: Optional[datetime] = None,
        time_accelerator: float = 1.0,
        enabled: bool = False,
    ):
        """
        Initialize virtual clock

        Args:
            start_time: Start time (defaults to current time)
            time_accelerator: Time acceleration multiplier (1.0=normal, 60.0=60x speed)
            enabled: Whether to enable virtual clock (False uses real system time)
        """
        self.enabled = enabled
        self.time_accelerator = time_accelerator

        # Real time starting point
        self.real_start_time = datetime.now(timezone.utc)

        # Virtual time starting point
        if start_time:
            if start_time.tzinfo is None:
                # If no timezone info, assume UTC
                self.virtual_start_time = start_time.replace(
                    tzinfo=timezone.utc,
                )
            else:
                self.virtual_start_time = start_time
        else:
            self.virtual_start_time = self.real_start_time

        # Pause state
        self.paused = False
        self.pause_real_time = None
        self.pause_virtual_time = None

        # Thread lock
        self.lock = threading.Lock()

    def now(self, tz: Optional[timezone] = None) -> datetime:
        """
        Get current time

        Args:
            tz: Target timezone (default UTC)

        Returns:
            Current time (virtual time or real time)
        """
        if not self.enabled:
            # Virtual clock not enabled, return real time
            return datetime.now(tz or timezone.utc)

        with self.lock:
            if self.paused:
                # Paused state, return virtual time at pause
                current_time = self.pause_virtual_time
            else:
                # Calculate virtual time
                real_elapsed = (
                    datetime.now(timezone.utc) - self.real_start_time
                )
                virtual_elapsed = real_elapsed * self.time_accelerator
                current_time = self.virtual_start_time + virtual_elapsed

            # Convert timezone
            if tz:
                return current_time.astimezone(tz)
            return current_time

    def set_time(self, new_time: datetime):
        """
        Set virtual time (jump to specified time)

        Args:
            new_time: New virtual time
        """
        if not self.enabled:
            raise RuntimeError("Virtual clock not enabled, cannot set time")

        with self.lock:
            if new_time.tzinfo is None:
                new_time = new_time.replace(tzinfo=timezone.utc)

            self.real_start_time = datetime.now(timezone.utc)
            self.virtual_start_time = new_time

            if self.paused:
                self.pause_real_time = self.real_start_time
                self.pause_virtual_time = new_time

    def pause(self):
        """Pause virtual clock"""
        if not self.enabled:
            return

        with self.lock:
            if not self.paused:
                self.paused = True
                self.pause_real_time = datetime.now(timezone.utc)

                # Calculate virtual time at pause
                real_elapsed = self.pause_real_time - self.real_start_time
                virtual_elapsed = real_elapsed * self.time_accelerator
                self.pause_virtual_time = (
                    self.virtual_start_time + virtual_elapsed
                )

    def resume(self):
        """Resume virtual clock"""
        if not self.enabled:
            return

        with self.lock:
            if self.paused:
                # Reset starting point so virtual time continues from pause point
                self.real_start_time = datetime.now(timezone.utc)
                self.virtual_start_time = self.pause_virtual_time
                self.paused = False

    def set_accelerator(self, accelerator: float):
        """
        Set time acceleration multiplier

        Args:
            accelerator: New acceleration multiplier
        """
        if not self.enabled:
            return

        with self.lock:
            # First calculate current virtual time
            current_virtual = self.now()

            # Update acceleration multiplier
            self.time_accelerator = accelerator

            # Reset starting point
            self.real_start_time = datetime.now(timezone.utc)
            self.virtual_start_time = current_virtual

    async def sleep(self, seconds: float):
        """
        Async sleep (considering time acceleration)

        Args:
            seconds: Number of seconds in virtual time
        """
        if not self.enabled:
            await asyncio.sleep(seconds)
        else:
            # Adjust actual sleep time based on acceleration multiplier
            real_seconds = seconds / self.time_accelerator
            await asyncio.sleep(real_seconds)

    def fast_forward(self, minutes: float = 30):
        """
        Fast forward virtual time (jump forward)

        Args:
            minutes: Number of minutes to fast forward (default 30 minutes)
        """
        if not self.enabled:
            raise RuntimeError(
                "Virtual clock not enabled, cannot fast forward time",
            )

        with self.lock:
            # Get current virtual time
            if self.paused:
                current_virtual = self.pause_virtual_time
            else:
                real_elapsed = (
                    datetime.now(timezone.utc) - self.real_start_time
                )
                virtual_elapsed = real_elapsed * self.time_accelerator
                current_virtual = self.virtual_start_time + virtual_elapsed

            # Fast forward specified minutes
            new_virtual_time = current_virtual + timedelta(minutes=minutes)

            # Update virtual time starting point
            self.real_start_time = datetime.now(timezone.utc)
            self.virtual_start_time = new_virtual_time

            # If paused, also update paused virtual time
            if self.paused:
                self.pause_virtual_time = new_virtual_time
                self.pause_real_time = self.real_start_time

    def get_info(self) -> dict:
        """Get virtual clock information"""
        return {
            "enabled": self.enabled,
            "time_accelerator": self.time_accelerator,
            "current_time": self.now().isoformat(),
            "paused": self.paused,
            "real_start_time": self.real_start_time.isoformat(),
            "virtual_start_time": self.virtual_start_time.isoformat(),
        }


# Global virtual clock instance
_global_clock: Optional[VirtualClock] = None


def init_virtual_clock(
    start_time: Optional[datetime] = None,
    time_accelerator: float = 1.0,
    enabled: bool = False,
) -> VirtualClock:
    """
    Initialize global virtual clock

    Args:
        start_time: Start time (defaults to current time)
        time_accelerator: Time acceleration multiplier
        enabled: Whether to enable virtual clock

    Returns:
        Virtual clock instance
    """
    global _global_clock
    _global_clock = VirtualClock(
        start_time=start_time,
        time_accelerator=time_accelerator,
        enabled=enabled,
    )
    return _global_clock


def get_virtual_clock() -> VirtualClock:
    """
    Get global virtual clock instance

    Returns:
        Virtual clock instance
    """
    global _global_clock
    if _global_clock is None:
        # If not initialized, create a default one (disabled)
        _global_clock = VirtualClock(enabled=False)
    return _global_clock


def virtual_now(tz: Optional[timezone] = None) -> datetime:
    """
    Get current virtual time (convenience function)

    Args:
        tz: Target timezone

    Returns:
        Current time
    """
    return get_virtual_clock().now(tz)


async def virtual_sleep(seconds: float):
    """
    Virtual sleep (convenience function)

    Args:
        seconds: Number of seconds in virtual time
    """
    await get_virtual_clock().sleep(seconds)
