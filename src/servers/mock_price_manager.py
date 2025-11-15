# src/servers/mock_price_manager.py
"""
Mock Price Manager - For testing during non-trading hours
Generates virtual real-time price data, simulates real market volatility

Configuration:
- Can be configured via environment variables:
  MOCK_POLL_INTERVAL: Price update interval (seconds), default 5
  MOCK_VOLATILITY: Price volatility (percentage), default 0.5
  
Use cases:
- Debug programs during non-trading hours
- Develop and test frontend real-time data display
- Demonstrate system functionality
"""
import os
import time
import random
import logging
import threading
from typing import Dict, List, Callable, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

