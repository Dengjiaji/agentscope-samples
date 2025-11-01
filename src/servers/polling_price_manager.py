# src/servers/polling_price_manager.py
"""
基于轮询的价格管理器 - 使用 Finnhub REST API
每分钟获取一次最新价格
"""
import time
import logging
import threading
from typing import Dict, List, Callable, Optional
import finnhub

logger = logging.getLogger(__name__)


class PollingPriceManager:
    """轮询式价格管理器 - 定期从 Finnhub REST API 获取价格"""
    
    def __init__(self, api_key: str, poll_interval: int = 60):
        """
        Args:
            api_key: Finnhub API Key
            poll_interval: 轮询间隔（秒），默认60秒
        """
        self.api_key = api_key
        self.poll_interval = poll_interval
        self.finnhub_client = finnhub.Client(api_key=api_key)
        
        self.subscribed_symbols: List[str] = []
        self.latest_prices: Dict[str, float] = {}
        self.price_callbacks: List[Callable] = []
        
        self.running = False
        self.thread = None
    
    def subscribe(self, symbols: List[str]):
        """订阅股票代码"""
        for symbol in symbols:
            if symbol not in self.subscribed_symbols:
                self.subscribed_symbols.append(symbol)
                logger.info(f"✅ 订阅价格轮询: {symbol}")
    
    def unsubscribe(self, symbols: List[str]):
        """取消订阅"""
        for symbol in symbols:
            if symbol in self.subscribed_symbols:
                self.subscribed_symbols.remove(symbol)
                logger.info(f"🔕 取消订阅: {symbol}")
    
    def add_price_callback(self, callback: Callable):
        """添加价格更新回调函数"""
        self.price_callbacks.append(callback)
    
    def _fetch_prices(self):
        """获取所有订阅股票的最新价格"""
        for symbol in self.subscribed_symbols:
            try:
                # 调用 Finnhub quote API
                quote_data = self.finnhub_client.quote(symbol)
                
                # quote_data 结构:
                # {
                #   'c': current_price,      # 当前价格
                #   'h': high_price,         # 今日最高
                #   'l': low_price,          # 今日最低
                #   'o': open_price,         # 开盘价
                #   'pc': previous_close,    # 昨日收盘
                #   't': timestamp           # 时间戳
                # }
                
                current_price = quote_data.get('c')
                timestamp = quote_data.get('t', int(time.time()))
                
                if current_price and current_price > 0:
                    # 更新缓存
                    old_price = self.latest_prices.get(symbol)
                    self.latest_prices[symbol] = current_price
                    
                    # 触发回调
                    price_data = {
                        'symbol': symbol,
                        'price': current_price,
                        'timestamp': timestamp * 1000,  # 转换为毫秒
                        'volume': None,  # REST API 不提供实时成交量
                        'open': quote_data.get('o'),
                        'high': quote_data.get('h'),
                        'low': quote_data.get('l'),
                        'previous_close': quote_data.get('pc')
                    }
                    
                    for callback in self.price_callbacks:
                        try:
                            callback(price_data)
                        except Exception as e:
                            logger.error(f"价格回调错误 ({symbol}): {e}")
                    
                    # 记录价格变化
                    if old_price:
                        change = ((current_price - old_price) / old_price) * 100
                        logger.info(f"💹 {symbol}: ${current_price:.2f} ({change:+.2f}%)")
                    else:
                        logger.info(f"💹 {symbol}: ${current_price:.2f} (初始)")
                else:
                    logger.warning(f"⚠️ {symbol}: 无效价格数据 (c={current_price})")
                    
            except Exception as e:
                logger.error(f"❌ 获取 {symbol} 价格失败: {e}")
    
    def _polling_loop(self):
        """轮询循环（在独立线程中运行）"""
        logger.info(f"🚀 价格轮询已启动 (间隔: {self.poll_interval}秒)")
        
        while self.running:
            try:
                start_time = time.time()
                
                # 获取所有价格
                self._fetch_prices()
                
                # 计算耗时
                elapsed = time.time() - start_time
                logger.debug(f"⏱️ 价格更新耗时: {elapsed:.2f}秒")
                
                # 等待到下一个轮询周期
                sleep_time = max(0, self.poll_interval - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    
            except Exception as e:
                logger.error(f"轮询循环错误: {e}")
                time.sleep(5)  # 出错后等待5秒再重试
    
    def start(self):
        """启动价格轮询"""
        if self.running:
            logger.warning("价格轮询已在运行")
            return
        
        if not self.subscribed_symbols:
            logger.warning("⚠️ 没有订阅任何股票")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._polling_loop, daemon=True)
        self.thread.start()
        
        logger.info(f"✅ 价格轮询管理器已启动 (订阅: {', '.join(self.subscribed_symbols)})")
    
    def stop(self):
        """停止价格轮询"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("🛑 价格轮询管理器已停止")
    
    def get_latest_price(self, symbol: str) -> Optional[float]:
        """获取最新价格"""
        return self.latest_prices.get(symbol)
    
    def get_all_latest_prices(self) -> Dict[str, float]:
        """获取所有最新价格"""
        return self.latest_prices.copy()

