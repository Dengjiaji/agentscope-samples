# src/servers/mock_price_manager.py
"""
Mock价格管理器 - 用于非交易时段测试
生成虚拟的实时价格数据，模拟真实市场波动

配置说明：
- 可通过环境变量配置：
  MOCK_POLL_INTERVAL: 价格更新间隔（秒），默认5
  MOCK_VOLATILITY: 价格波动率（百分比），默认0.5
  
使用场景：
- 非交易时段调试程序
- 开发和测试前端实时数据显示
- 演示系统功能
"""
import os
import time
import random
import logging
import threading
from typing import Dict, List, Callable, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class MockPriceManager:
    """Mock价格管理器 - 生成虚拟价格用于测试"""
    
    def __init__(self, poll_interval: int = None, volatility: float = None):
        """
        Args:
            poll_interval: 价格更新间隔（秒），默认从环境变量读取或5秒
            volatility: 价格波动率（百分比），默认从环境变量读取或0.5%
        """
        # 从环境变量读取配置（如果未指定）
        if poll_interval is None:
            poll_interval = int(os.getenv('MOCK_POLL_INTERVAL', '5'))
        if volatility is None:
            volatility = float(os.getenv('MOCK_VOLATILITY', '0.5'))
        
        self.poll_interval = poll_interval
        self.volatility = volatility
        
        self.subscribed_symbols: List[str] = []
        self.base_prices: Dict[str, float] = {}  # 基准价格
        self.open_prices: Dict[str, float] = {}  # 开盘价
        self.latest_prices: Dict[str, float] = {}
        self.price_callbacks: List[Callable] = []
        
        self.running = False
        self.thread = None
        
        # 预设的基准价格（如果订阅时未设置）
        # 这些是2024年11月的真实价格水平
        self.default_base_prices = {
            'AAPL': 237.50,
            'MSFT': 425.30,
            'GOOGL': 161.50,
            'AMZN': 218.45,
            'NVDA': 950.00,
            'META': 573.22,
            'TSLA': 342.15,
            'AMD': 168.90,
            'NFLX': 688.25,
            'INTC': 42.18,
            'COIN': 285.50,
            'PLTR': 45.80,
            'BABA': 88.30,
            'DIS': 112.50,
            'BKNG': 4850.00
        }
        
        logger.info(f"✅ MockPriceManager 初始化完成")
        logger.info(f"   更新间隔: {self.poll_interval}秒")
        logger.info(f"   波动率: {self.volatility}%")
    
    def subscribe(self, symbols: List[str], base_prices: Dict[str, float] = None):
        """
        订阅股票代码并设置基准价格
        
        Args:
            symbols: 股票代码列表
            base_prices: 基准价格字典（可选），如果未提供则使用默认价格
        """
        for symbol in symbols:
            if symbol not in self.subscribed_symbols:
                self.subscribed_symbols.append(symbol)
                
                # 设置基准价格
                if base_prices and symbol in base_prices:
                    base_price = base_prices[symbol]
                elif symbol in self.default_base_prices:
                    base_price = self.default_base_prices[symbol]
                else:
                    # 如果没有预设价格，生成随机价格
                    base_price = random.uniform(50, 500)
                
                self.base_prices[symbol] = base_price
                self.open_prices[symbol] = base_price  # 开盘价等于基准价
                self.latest_prices[symbol] = base_price
                
                logger.info(f"✅ 订阅Mock价格: {symbol} (基准价: ${base_price:.2f})")
    
    def unsubscribe(self, symbols: List[str]):
        """取消订阅"""
        for symbol in symbols:
            if symbol in self.subscribed_symbols:
                self.subscribed_symbols.remove(symbol)
                self.base_prices.pop(symbol, None)
                self.open_prices.pop(symbol, None)
                self.latest_prices.pop(symbol, None)
                logger.info(f"🔕 取消订阅: {symbol}")
    
    def add_price_callback(self, callback: Callable):
        """添加价格更新回调函数"""
        self.price_callbacks.append(callback)
    
    def _generate_price_update(self, symbol: str) -> float:
        """
        生成价格更新（基于随机游走模型）
        
        模拟真实市场特征：
        - 随机游走：小幅度波动
        - 偶尔的大波动（模拟新闻事件）
        - 价格不会偏离开盘价太远（日内波动限制）
        
        Returns:
            新价格
        """
        current_price = self.latest_prices.get(symbol, self.base_prices[symbol])
        
        # 随机游走：价格变化 = 当前价格 * 随机百分比
        change_percent = random.uniform(-self.volatility, self.volatility)
        new_price = current_price * (1 + change_percent / 100)
        
        # 添加一些趋势性（10%概率出现较大波动，模拟突发新闻）
        if random.random() < 0.1:
            trend_factor = random.uniform(-2, 2)
            new_price = new_price * (1 + trend_factor / 100)
            if abs(trend_factor) > 1:
                logger.debug(f"📰 {symbol} 出现较大波动: {trend_factor:+.2f}%")
        
        # 确保价格不会偏离开盘价太远（日内波动限制: ±10%）
        # 这更符合真实市场情况
        open_price = self.open_prices[symbol]
        max_price = open_price * 1.10
        min_price = open_price * 0.90
        new_price = max(min_price, min(max_price, new_price))
        
        return new_price
    
    def _update_prices(self):
        """更新所有订阅股票的价格"""
        timestamp = int(time.time() * 1000)
        
        for symbol in self.subscribed_symbols:
            try:
                # 生成新价格
                new_price = self._generate_price_update(symbol)
                old_price = self.latest_prices.get(symbol, new_price)
                self.latest_prices[symbol] = new_price
                
                # 计算相对开盘价的变化
                open_price = self.open_prices[symbol]
                change_from_open = ((new_price - open_price) / open_price) * 100
                
                # 触发回调
                price_data = {
                    'symbol': symbol,
                    'price': new_price,
                    'timestamp': timestamp,
                    'volume': random.randint(1000000, 10000000),  # 随机成交量
                    'open': open_price,
                    'high': max(new_price, open_price),
                    'low': min(new_price, open_price),
                    'previous_close': open_price,
                    'change_from_open': change_from_open
                }
                
                for callback in self.price_callbacks:
                    try:
                        callback(price_data)
                    except Exception as e:
                        logger.error(f"Mock价格回调错误 ({symbol}): {e}")
                
                # 记录价格变化
                change = ((new_price - old_price) / old_price) * 100
                logger.debug(f"💹 Mock {symbol}: ${new_price:.2f} ({change:+.2f}%) [开盘: {change_from_open:+.2f}%]")
                
            except Exception as e:
                logger.error(f"❌ 生成Mock价格失败 ({symbol}): {e}")
    
    def _polling_loop(self):
        """轮询循环（在独立线程中运行）"""
        logger.info(f"🚀 Mock价格生成已启动 (间隔: {self.poll_interval}秒, 波动率: {self.volatility}%)")
        
        while self.running:
            try:
                start_time = time.time()
                
                # 更新所有价格
                self._update_prices()
                
                # 等待到下一个更新周期
                elapsed = time.time() - start_time
                sleep_time = max(0, self.poll_interval - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    
            except Exception as e:
                logger.error(f"Mock轮询循环错误: {e}")
                time.sleep(5)
    
    def start(self):
        """启动Mock价格生成"""
        if self.running:
            logger.warning("Mock价格管理器已在运行")
            return
        
        if not self.subscribed_symbols:
            logger.warning("⚠️ 没有订阅任何股票")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._polling_loop, daemon=True)
        self.thread.start()
        
        logger.info(f"✅ Mock价格管理器已启动 (订阅: {', '.join(self.subscribed_symbols)})")
    
    def stop(self):
        """停止Mock价格生成"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("🛑 Mock价格管理器已停止")
    
    def get_latest_price(self, symbol: str) -> Optional[float]:
        """获取最新价格"""
        return self.latest_prices.get(symbol)
    
    def get_all_latest_prices(self) -> Dict[str, float]:
        """获取所有最新价格"""
        return self.latest_prices.copy()
    
    def get_open_price(self, symbol: str) -> Optional[float]:
        """获取开盘价"""
        return self.open_prices.get(symbol)
    
    def reset_open_prices(self):
        """重置开盘价（模拟新的交易日开始）"""
        for symbol in self.subscribed_symbols:
            # 新交易日开盘价基于昨日收盘价的小幅随机变化（±1%）
            last_close = self.latest_prices[symbol]
            gap_percent = random.uniform(-1, 1)
            new_open = last_close * (1 + gap_percent / 100)
            self.open_prices[symbol] = new_open
            self.latest_prices[symbol] = new_open
            logger.debug(f"📊 {symbol} 新开盘价: ${new_open:.2f} (跳空: {gap_percent:+.2f}%)")
        logger.info("📊 开盘价已重置（模拟新交易日）")
    
    def set_base_price(self, symbol: str, price: float):
        """
        手动设置某个股票的基准价格（用于测试特定场景）
        
        Args:
            symbol: 股票代码
            price: 新的基准价格
        """
        if symbol in self.subscribed_symbols:
            self.base_prices[symbol] = price
            self.open_prices[symbol] = price
            self.latest_prices[symbol] = price
            logger.info(f"✏️ {symbol} 基准价格已设置为: ${price:.2f}")
        else:
            logger.warning(f"⚠️ {symbol} 未订阅，无法设置价格")

