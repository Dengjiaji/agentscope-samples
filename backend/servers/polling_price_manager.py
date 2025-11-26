# -*- coding: utf-8 -*-
# backend/servers/polling_price_manager.py
"""
Polling-based Price Manager - Uses Finnhub REST API
Supports high-frequency real-time price fetching (default 10 seconds, recommended for online mode)
Uses Finnhub Quote API: https://finnhub.io/docs/api/quote
"""
import logging
import threading
import time
from typing import Callable, Dict, List, Optional

import finnhub

logger = logging.getLogger(__name__)


class PollingPriceManager:
    """Polling-based price manager - Regularly fetches real-time prices from Finnhub Quote API"""

    def __init__(self, api_key: str, poll_interval: int = 10):
        """
        Args:
            api_key: Finnhub API Key (Free registration: https://finnhub.io/register)
            poll_interval: Polling interval (seconds), default 10 seconds (recommended for online mode)
                          - Free account: Recommend 10-60 seconds
                          - Paid account: Can set shorter intervals
        """
        self.api_key = api_key
        self.poll_interval = poll_interval
        self.finnhub_client = finnhub.Client(api_key=api_key)

        self.subscribed_symbols: List[str] = []
        self.latest_prices: Dict[str, float] = {}
        self.open_prices: Dict[
            str,
            float,
        ] = {}  # Store open prices (for calculating return)
        self.price_callbacks: List[Callable] = []

        self.running = False
        self.thread = None

        logger.info(
            f"✅ PollingPriceManager initialized (polling interval: {poll_interval}s)",
        )

    def subscribe(self, symbols: List[str]):
        """Subscribe to stock symbols"""
        for symbol in symbols:
            if symbol not in self.subscribed_symbols:
                self.subscribed_symbols.append(symbol)
                logger.info(f"✅ Subscribed to price polling: {symbol}")

    def unsubscribe(self, symbols: List[str]):
        """Unsubscribe"""
        for symbol in symbols:
            if symbol in self.subscribed_symbols:
                self.subscribed_symbols.remove(symbol)
                logger.info(f"🔕 Unsubscribed: {symbol}")

    def add_price_callback(self, callback: Callable):
        """Add price update callback function"""
        self.price_callbacks.append(callback)

    def _fetch_prices(self):
        """
        Fetch latest prices for all subscribed stocks
        Uses Finnhub Quote API: https://finnhub.io/docs/api/quote
        """
        for symbol in self.subscribed_symbols:
            try:
                # Call Finnhub quote API
                # API documentation: https://finnhub.io/docs/api/quote
                quote_data = self.finnhub_client.quote(symbol)

                # quote_data structure:
                # {
                #   'c': current_price,      # Current price (real-time)
                #   'h': high_price,         # Today's high
                #   'l': low_price,          # Today's low
                #   'o': open_price,         # Today's open
                #   'pc': previous_close,    # Previous close
                #   't': timestamp,          # Unix timestamp
                #   'd': change,             # Price change (dollar)
                #   'dp': change_percent     # Price change percentage
                # }

                current_price = quote_data.get("c")
                open_price = quote_data.get("o")
                timestamp = quote_data.get("t", int(time.time()))

                if current_price and current_price > 0:
                    # Save open price (on first fetch)
                    if (
                        symbol not in self.open_prices
                        and open_price
                        and open_price > 0
                    ):
                        self.open_prices[symbol] = open_price
                        logger.info(
                            f"📊 {symbol} Open price: ${open_price:.2f}",
                        )

                    # Use stored open price (if available)
                    stored_open = self.open_prices.get(symbol, open_price)

                    # Calculate return relative to open price
                    ret = 0.0
                    if stored_open and stored_open > 0:
                        ret = (
                            (current_price - stored_open) / stored_open
                        ) * 100

                    # Update cache
                    old_price = self.latest_prices.get(symbol)
                    self.latest_prices[symbol] = current_price

                    # Trigger callbacks
                    price_data = {
                        "symbol": symbol,
                        "price": current_price,
                        "timestamp": timestamp
                        * 1000,  # Convert to milliseconds
                        "volume": None,  # Quote API doesn't provide real-time volume
                        "open": stored_open,
                        "high": quote_data.get("h"),
                        "low": quote_data.get("l"),
                        "previous_close": quote_data.get("pc"),
                        "ret": ret,  # Return relative to open (%)
                        "change": quote_data.get(
                            "d",
                        ),  # Change relative to previous close ($)
                        "change_percent": quote_data.get(
                            "dp",
                        ),  # Change relative to previous close (%)
                    }

                    for callback in self.price_callbacks:
                        try:
                            callback(price_data)
                        except Exception as e:
                            logger.error(
                                f"Price callback error ({symbol}): {e}",
                            )

                    # Log price change (more detailed log)
                    if old_price:
                        change = (
                            (current_price - old_price) / old_price
                        ) * 100
                        logger.info(
                            f"💹 {symbol}: ${current_price:.2f} ({change:+.2f}% from last) [Open ret: {ret:+.2f}%]",
                        )
                    else:
                        logger.info(
                            f"💹 {symbol}: ${current_price:.2f} (initial) [Open ret: {ret:+.2f}%]",
                        )
                else:
                    logger.warning(
                        f"⚠️ {symbol}: Invalid price data (c={current_price})",
                    )

            except Exception as e:
                logger.error(f"❌ Failed to fetch {symbol} price: {e}")

    def _polling_loop(self):
        """Polling loop (runs in separate thread)"""
        logger.info(
            f"🚀 Price polling started (interval: {self.poll_interval}s)",
        )

        while self.running:
            try:
                start_time = time.time()

                # Fetch all prices
                self._fetch_prices()

                # Calculate elapsed time
                elapsed = time.time() - start_time
                logger.debug(f"⏱️ Price update elapsed: {elapsed:.2f}s")

                # Wait until next polling cycle
                sleep_time = max(0, self.poll_interval - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)

            except Exception as e:
                logger.error(f"Polling loop error: {e}")
                time.sleep(5)  # Wait 5 seconds after error before retry

    def start(self):
        """Start price polling"""
        if self.running:
            logger.warning("Price polling already running")
            return

        if not self.subscribed_symbols:
            logger.warning("⚠️ No stocks subscribed")
            return

        self.running = True
        self.thread = threading.Thread(target=self._polling_loop, daemon=True)
        self.thread.start()

        logger.info(
            f"✅ Price polling manager started (subscribed: {', '.join(self.subscribed_symbols)})",
        )

    def stop(self):
        """Stop price polling"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("🛑 Price polling manager stopped")

    def get_latest_price(self, symbol: str) -> Optional[float]:
        """Get latest price"""
        return self.latest_prices.get(symbol)

    def get_all_latest_prices(self) -> Dict[str, float]:
        """Get all latest prices"""
        return self.latest_prices.copy()

    def get_open_price(self, symbol: str) -> Optional[float]:
        """Get open price"""
        return self.open_prices.get(symbol)

    def get_all_open_prices(self) -> Dict[str, float]:
        """Get all open prices"""
        return self.open_prices.copy()

    def reset_open_prices(self):
        """Reset open prices (for new trading day)"""
        self.open_prices.clear()
        logger.info("📊 Open prices reset (new trading day)")
