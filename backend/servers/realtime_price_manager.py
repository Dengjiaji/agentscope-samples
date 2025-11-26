# -*- coding: utf-8 -*-
# backend/servers/realtime_price_manager.py
"""
Real-time Price Data Manager - Finnhub REST API Integration
Uses scheduled polling to fetch minute-level OHLCV data, simulates real-time price updates
"""
# flake8: noqa: E501
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Callable, Dict, Optional, Set

logger = logging.getLogger(__name__)


class RealtimePriceManager:
    """Real-time price manager - Uses Finnhub REST API to fetch minute-level OHLCV data"""

    def __init__(self, api_key: str, poll_interval: int = 60):
        """
        Initialize price manager

        Args:
            api_key: Finnhub API Key
            poll_interval: Polling interval (seconds), default 60 seconds
        """
        self.api_key = api_key
        self.subscribed_symbols: Set[str] = set()
        self.latest_prices: Dict[str, float] = {}
        self.latest_ohlcv: Dict[str, Dict] = {}  # Store complete OHLCV data
        self.price_callbacks: list[Callable] = []
        self.running = False
        self.thread = None
        self.poll_interval = poll_interval

        # Initialize Finnhub client
        try:
            import finnhub

            self.finnhub_client = finnhub.Client(api_key=self.api_key)
            logger.info("✅ Finnhub client initialized successfully")
        except ImportError:
            logger.error(
                "❌ finnhub-python not installed, please run: pip install finnhub-python",
            )
            raise
        except Exception as e:
            logger.error(f"❌ Finnhub client initialization failed: {e}")
            raise

    def subscribe(self, symbols: list[str]):
        """Subscribe to stock symbols"""
        for symbol in symbols:
            if symbol not in self.subscribed_symbols:
                self.subscribed_symbols.add(symbol)
                logger.info(f"✅ Subscribed to price updates: {symbol}")

                # If already running, immediately fetch price once
                if self.running:
                    self._fetch_price_for_symbol(symbol)

    def unsubscribe(self, symbols: list[str]):
        """Unsubscribe from stock symbols"""
        for symbol in symbols:
            if symbol in self.subscribed_symbols:
                self.subscribed_symbols.remove(symbol)
                logger.info(f"🔕 Unsubscribed: {symbol}")

                # Clean up data
                self.latest_prices.pop(symbol, None)
                self.latest_ohlcv.pop(symbol, None)

    def add_price_callback(self, callback: Callable):
        """Add price update callback function"""
        self.price_callbacks.append(callback)
        logger.debug(
            f"Added price callback, total {len(self.price_callbacks)} callbacks",
        )

    def _fetch_price_for_symbol(self, symbol: str):
        """Fetch latest price for a single stock"""
        try:
            # Get current time and 10 minutes ago time range (ensure data availability)
            end_time = datetime.now()
            start_time = end_time - timedelta(minutes=10)

            start_timestamp = int(start_time.timestamp())
            end_timestamp = int(end_time.timestamp())

            # Call Finnhub API to get minute-level OHLCV data
            data = self.finnhub_client.stock_candles(
                symbol,
                "1",  # 1-minute candlestick
                start_timestamp,
                end_timestamp,
            )

            # Check returned data
            if data and data.get("s") == "ok":
                # Ensure data exists
                if data.get("c") and len(data["c"]) > 0:
                    # Get latest candlestick
                    latest_price = data["c"][-1]  # Latest close price
                    latest_open = data["o"][-1]
                    latest_high = data["h"][-1]
                    latest_low = data["l"][-1]
                    latest_volume = data["v"][-1] if data.get("v") else 0
                    latest_timestamp = (
                        data["t"][-1] * 1000
                    )  # Convert to milliseconds

                    # Update price cache
                    self.latest_prices[symbol] = latest_price

                    # Store complete OHLCV
                    self.latest_ohlcv[symbol] = {
                        "open": latest_open,
                        "high": latest_high,
                        "low": latest_low,
                        "close": latest_price,
                        "volume": latest_volume,
                        "timestamp": latest_timestamp,
                    }

                    # Trigger all callbacks
                    for callback in self.price_callbacks:
                        try:
                            callback(
                                {
                                    "symbol": symbol,
                                    "price": latest_price,
                                    "volume": latest_volume,
                                    "timestamp": latest_timestamp,
                                    "ohlcv": self.latest_ohlcv[symbol],
                                },
                            )
                        except Exception as e:
                            logger.error(
                                f"Price callback error ({symbol}): {e}",
                            )

                    logger.info(
                        f"💹 {symbol}: ${latest_price:.2f} (Vol: {latest_volume:,.0f})",
                    )
                    return True
                else:
                    logger.warning(f"⚠️ {symbol}: API returned empty data")
                    return False
            elif data and data.get("s") == "no_data":
                logger.warning(
                    f"⚠️ {symbol}: No available data (market may be closed or symbol invalid)",
                )
                return False
            else:
                logger.warning(
                    f"⚠️ {symbol}: API returned abnormal status: "
                    f"{data.get('s') if data else 'None'}",
                )
                return False

        except Exception as e:
            logger.error(f"❌ Failed to fetch {symbol} price: {e}")
            return False

    def _fetch_latest_prices(self):
        """Fetch latest prices for all subscribed stocks"""
        if not self.subscribed_symbols:
            logger.debug("No subscribed stocks, skipping price fetch")
            return

        logger.info(
            f"📊 Starting to fetch prices for {len(self.subscribed_symbols)} stocks...",
        )

        success_count = 0
        for symbol in list(self.subscribed_symbols):
            if self._fetch_price_for_symbol(symbol):
                success_count += 1

            # Avoid API rate limiting, slight delay between requests
            time.sleep(0.1)

        logger.info(
            f"✅ Price update completed: {success_count}/{len(self.subscribed_symbols)} successful",
        )

    def start(self):
        """Start price polling (in separate thread)"""
        if self.running:
            logger.warning("Real-time price manager already running")
            return

        if not self.subscribed_symbols:
            logger.warning(
                "⚠️ No stocks subscribed, price manager will not fetch data",
            )

        self.running = True

        def poll_prices():
            logger.info(
                f"🚀 Price polling thread started (interval: {self.poll_interval}s)",
            )

            # Immediately fetch prices once
            try:
                self._fetch_latest_prices()
            except Exception as e:
                logger.error(f"Initial price fetch failed: {e}")

            # Scheduled polling
            while self.running:
                try:
                    time.sleep(self.poll_interval)

                    if (
                        self.running
                    ):  # Check again, avoid being stopped during sleep
                        self._fetch_latest_prices()

                except Exception as e:
                    logger.error(f"Price polling error: {e}")
                    if self.running:
                        time.sleep(5)  # Brief wait after error before retry

        self.thread = threading.Thread(target=poll_prices, daemon=True)
        self.thread.start()
        logger.info("🚀 Real-time price manager started (OHLCV polling mode)")

    def stop(self):
        """Stop price polling"""
        if not self.running:
            logger.warning("Real-time price manager not running")
            return

        logger.info("🛑 Stopping real-time price manager...")
        self.running = False

        # Wait for thread to end (max 2 seconds)
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)

        logger.info("🛑 Real-time price manager stopped")

    def get_latest_price(self, symbol: str) -> Optional[float]:
        """Get latest price"""
        return self.latest_prices.get(symbol)

    def get_all_latest_prices(self) -> Dict[str, float]:
        """Get all latest prices"""
        return self.latest_prices.copy()

    def get_ohlcv(self, symbol: str) -> Optional[Dict]:
        """Get complete OHLCV data"""
        return self.latest_ohlcv.get(symbol)

    def get_all_ohlcv(self) -> Dict[str, Dict]:
        """Get OHLCV data for all stocks"""
        return self.latest_ohlcv.copy()


class RealtimePortfolioCalculator:
    """Real-time Portfolio net value calculator"""

    def __init__(self, price_manager: RealtimePriceManager):
        self.price_manager = price_manager
        self.holdings: Dict[str, Dict] = {}  # {symbol: {quantity, avg_cost}}
        self.cash: float = 0.0
        self.initial_value: float = 0.0

    def update_holdings(self, holdings: Dict[str, Dict], cash: float):
        """Update holdings information"""
        self.holdings = holdings.copy()
        self.cash = cash

        if self.initial_value == 0.0:
            self.initial_value = self.calculate_total_value()

    def calculate_total_value(self) -> float:
        """Calculate Portfolio total value"""
        positions_value = 0.0

        for symbol, holding in self.holdings.items():
            latest_price = self.price_manager.get_latest_price(symbol)
            if latest_price:
                quantity = holding.get("quantity", 0)
                positions_value += latest_price * quantity
            else:
                # If no real-time price, use average cost
                avg_cost = holding.get("avg_cost", 0)
                quantity = holding.get("quantity", 0)
                positions_value += avg_cost * quantity

        return positions_value + self.cash

    def calculate_pnl(self) -> Dict[str, float]:
        """Calculate profit and loss"""
        current_value = self.calculate_total_value()
        pnl_dollar = current_value - self.initial_value
        pnl_percent = (
            (pnl_dollar / self.initial_value * 100)
            if self.initial_value > 0
            else 0.0
        )

        return {
            "total_value": current_value,
            "initial_value": self.initial_value,
            "pnl_dollar": pnl_dollar,
            "pnl_percent": pnl_percent,
            "cash": self.cash,
        }

    def get_position_details(self) -> list[Dict]:
        """Get details for each position"""
        positions = []

        for symbol, holding in self.holdings.items():
            quantity = holding.get("quantity", 0)
            avg_cost = holding.get("avg_cost", 0)
            latest_price = self.price_manager.get_latest_price(symbol)

            if latest_price:
                current_value = latest_price * quantity
                cost_basis = avg_cost * quantity
                pnl = current_value - cost_basis
                pnl_percent = (
                    (pnl / cost_basis * 100) if cost_basis > 0 else 0.0
                )
            else:
                latest_price = avg_cost
                current_value = avg_cost * quantity
                pnl = 0.0
                pnl_percent = 0.0

            positions.append(
                {
                    "symbol": symbol,
                    "quantity": quantity,
                    "avg_cost": avg_cost,
                    "current_price": latest_price,
                    "current_value": current_value,
                    "pnl": pnl,
                    "pnl_percent": pnl_percent,
                },
            )

        return positions
