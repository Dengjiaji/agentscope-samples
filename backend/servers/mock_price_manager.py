# -*- coding: utf-8 -*-
# backend/servers/mock_price_manager.py
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
import logging
import os
import random
import threading
import time
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class MockPriceManager:
    """Mock Price Manager - Generates virtual prices for testing"""

    def __init__(self, poll_interval: int = None, volatility: float = None):
        """
        Args:
            poll_interval: Price update interval (seconds), defaults to environment variable or 5 seconds
            volatility: Price volatility (percentage), defaults to environment variable or 0.5%
        """
        # Read configuration from environment variables (if not specified)
        if poll_interval is None:
            poll_interval = int(os.getenv("MOCK_POLL_INTERVAL", "5"))
        if volatility is None:
            volatility = float(os.getenv("MOCK_VOLATILITY", "0.5"))

        self.poll_interval = poll_interval
        self.volatility = volatility

        self.subscribed_symbols: List[str] = []
        self.base_prices: Dict[str, float] = {}  # Base prices
        self.open_prices: Dict[str, float] = {}  # Open prices
        self.latest_prices: Dict[str, float] = {}
        self.price_callbacks: List[Callable] = []

        self.running = False
        self.thread = None

        # Preset base prices (if not set when subscribing)
        # These are real price levels from November 2024
        self.default_base_prices = {
            "AAPL": 237.50,
            "MSFT": 425.30,
            "GOOGL": 161.50,
            "AMZN": 218.45,
            "NVDA": 950.00,
            "META": 573.22,
            "TSLA": 342.15,
            "AMD": 168.90,
            "NFLX": 688.25,
            "INTC": 42.18,
            "COIN": 285.50,
            "PLTR": 45.80,
            "BABA": 88.30,
            "DIS": 112.50,
            "BKNG": 4850.00,
        }

        logger.info(f"✅ MockPriceManager initialized")
        logger.info(f"   Update interval: {self.poll_interval}s")
        logger.info(f"   Volatility: {self.volatility}%")

    def subscribe(
        self,
        symbols: List[str],
        base_prices: Dict[str, float] = None,
    ):
        """
        Subscribe to stock symbols and set base prices

        Args:
            symbols: List of stock symbols
            base_prices: Dictionary of base prices (optional), uses default prices if not provided
        """
        for symbol in symbols:
            if symbol not in self.subscribed_symbols:
                self.subscribed_symbols.append(symbol)

                # Set base price
                if base_prices and symbol in base_prices:
                    base_price = base_prices[symbol]
                elif symbol in self.default_base_prices:
                    base_price = self.default_base_prices[symbol]
                else:
                    # If no preset price, generate random price
                    base_price = random.uniform(50, 500)

                self.base_prices[symbol] = base_price
                self.open_prices[
                    symbol
                ] = base_price  # Open price equals base price
                self.latest_prices[symbol] = base_price

                logger.info(
                    f"✅ Subscribed to Mock price: {symbol} (Base price: ${base_price:.2f})",
                )

    def unsubscribe(self, symbols: List[str]):
        """Unsubscribe"""
        for symbol in symbols:
            if symbol in self.subscribed_symbols:
                self.subscribed_symbols.remove(symbol)
                self.base_prices.pop(symbol, None)
                self.open_prices.pop(symbol, None)
                self.latest_prices.pop(symbol, None)
                logger.info(f"🔕 Unsubscribed: {symbol}")

    def add_price_callback(self, callback: Callable):
        """Add price update callback function"""
        self.price_callbacks.append(callback)

    def _generate_price_update(self, symbol: str) -> float:
        """
        Generate price update (based on random walk model)

        Simulates real market characteristics:
        - Random walk: small fluctuations
        - Occasional large fluctuations (simulating news events)
        - Price does not deviate too far from open price (intraday fluctuation limit)

        Returns:
            New price
        """
        current_price = self.latest_prices.get(
            symbol,
            self.base_prices[symbol],
        )

        # Random walk: price change = current price * random percentage
        change_percent = random.uniform(-self.volatility, self.volatility)
        new_price = current_price * (1 + change_percent / 100)

        # Add some trend (10% probability of larger fluctuation, simulating sudden news)
        if random.random() < 0.1:
            trend_factor = random.uniform(-2, 2)
            new_price = new_price * (1 + trend_factor / 100)
            if abs(trend_factor) > 1:
                logger.debug(
                    f"📰 {symbol} large fluctuation: {trend_factor:+.2f}%",
                )

        # Ensure price does not deviate too far from open price (intraday fluctuation limit: ±10%)
        # This better matches real market conditions
        open_price = self.open_prices[symbol]
        max_price = open_price * 1.10
        min_price = open_price * 0.90
        new_price = max(min_price, min(max_price, new_price))

        return new_price

    def _update_prices(self):
        """Update prices for all subscribed stocks"""
        timestamp = int(time.time() * 1000)

        for symbol in self.subscribed_symbols:
            try:
                # Generate new price
                new_price = self._generate_price_update(symbol)
                old_price = self.latest_prices.get(symbol, new_price)
                self.latest_prices[symbol] = new_price

                # Calculate change relative to open price
                open_price = self.open_prices[symbol]
                change_from_open = (
                    (new_price - open_price) / open_price
                ) * 100

                # Trigger callback
                price_data = {
                    "symbol": symbol,
                    "price": new_price,
                    "timestamp": timestamp,
                    "volume": random.randint(
                        1000000,
                        10000000,
                    ),  # Random volume
                    "open": open_price,
                    "high": max(new_price, open_price),
                    "low": min(new_price, open_price),
                    "previous_close": open_price,
                    "change_from_open": change_from_open,
                }

                for callback in self.price_callbacks:
                    try:
                        callback(price_data)
                    except Exception as e:
                        logger.error(
                            f"Mock price callback error ({symbol}): {e}",
                        )

                # Log price change
                change = ((new_price - old_price) / old_price) * 100
                logger.debug(
                    f"💹 Mock {symbol}: ${new_price:.2f} ({change:+.2f}%) [Open: {change_from_open:+.2f}%]",
                )

            except Exception as e:
                logger.error(
                    f"❌ Failed to generate Mock price ({symbol}): {e}",
                )

    def _polling_loop(self):
        """Polling loop (runs in separate thread)"""
        logger.info(
            f"🚀 Mock price generation started (interval: {self.poll_interval}s, volatility: {self.volatility}%)",
        )

        while self.running:
            try:
                start_time = time.time()

                # Update all prices
                self._update_prices()

                # Wait until next update cycle
                elapsed = time.time() - start_time
                sleep_time = max(0, self.poll_interval - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)

            except Exception as e:
                logger.error(f"Mock polling loop error: {e}")
                time.sleep(5)

    def start(self):
        """Start Mock price generation"""
        if self.running:
            logger.warning("Mock price manager already running")
            return

        if not self.subscribed_symbols:
            logger.warning("⚠️ No stocks subscribed")
            return

        self.running = True
        self.thread = threading.Thread(target=self._polling_loop, daemon=True)
        self.thread.start()

        logger.info(
            f"✅ Mock price manager started (subscribed: {', '.join(self.subscribed_symbols)})",
        )

    def stop(self):
        """Stop Mock price generation"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("🛑 Mock price manager stopped")

    def get_latest_price(self, symbol: str) -> Optional[float]:
        """Get latest price"""
        return self.latest_prices.get(symbol)

    def get_all_latest_prices(self) -> Dict[str, float]:
        """Get all latest prices"""
        return self.latest_prices.copy()

    def get_open_price(self, symbol: str) -> Optional[float]:
        """Get open price"""
        return self.open_prices.get(symbol)

    def reset_open_prices(self):
        """Reset open prices (simulate new trading day start)"""
        for symbol in self.subscribed_symbols:
            # New trading day open price based on small random change from yesterday's close (±1%)
            last_close = self.latest_prices[symbol]
            gap_percent = random.uniform(-1, 1)
            new_open = last_close * (1 + gap_percent / 100)
            self.open_prices[symbol] = new_open
            self.latest_prices[symbol] = new_open
            logger.debug(
                f"📊 {symbol} New open price: ${new_open:.2f} (Gap: {gap_percent:+.2f}%)",
            )
        logger.info("📊 Open prices reset (simulating new trading day)")

    def set_base_price(self, symbol: str, price: float):
        """
        Manually set base price for a stock (for testing specific scenarios)

        Args:
            symbol: Stock symbol
            price: New base price
        """
        if symbol in self.subscribed_symbols:
            self.base_prices[symbol] = price
            self.open_prices[symbol] = price
            self.latest_prices[symbol] = price
            logger.info(f"✏️ {symbol} Base price set to: ${price:.2f}")
        else:
            logger.warning(f"⚠️ {symbol} not subscribed, cannot set price")
