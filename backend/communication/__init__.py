# -*- coding: utf-8 -*-
"""
Communication module for agent interactions
Provides notification, debate, and meeting functionalities
"""

from .notification_helpers import should_send_notification
from .notification_system import notification_system

__all__ = [
    "notification_system",
    "should_send_notification",
]
