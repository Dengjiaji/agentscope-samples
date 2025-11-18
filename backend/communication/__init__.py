"""
Communication module for agent interactions
Provides notification, debate, and meeting functionalities
"""

from .notification_system import notification_system
from .notification_helpers import should_send_notification

__all__ = [
    'notification_system',
    'should_send_notification',
]
