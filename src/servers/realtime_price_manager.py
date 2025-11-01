# src/servers/realtime_price_manager.py
"""
实时价格数据管理器 - Finnhub REST API 集成
使用定时轮询获取分钟级 OHLCV 数据，模拟实时价格更新
"""
import time
import logging
import threading
from typing import Dict, Set, Callable, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class RealtimePriceManager:
    """实时价格管理器 - 使用 Finnhub REST API 获取分钟级 OHLCV 数据"""
    
    def __init__(self, api_key: str, poll_interval: int = 60):
        """
        初始化价格管理器
        
        Args:
            api_key: Finnhub API Key
            poll_interval: 轮询间隔（秒），默认60秒
        """
        self.api_key = api_key
        self.subscribed_symbols: Set[str] = set()
        self.latest_prices: Dict[str, float] = {}
        self.latest_ohlcv: Dict[str, Dict] = {}  # 存储完整 OHLCV 数据
        self.price_callbacks: list[Callable] = []
        self.running = False
        self.thread = None
        self.poll_interval = poll_interval
        
        # 初始化 Finnhub client
        try:
            import finnhub
            self.finnhub_client = finnhub.Client(api_key=self.api_key)
            logger.info("✅ Finnhub 客户端初始化成功")
        except ImportError:
            logger.error("❌ 未安装 finnhub-python，请运行: pip install finnhub-python")
            raise
        except Exception as e:
            logger.error(f"❌ Finnhub 客户端初始化失败: {e}")
            raise
    
    def subscribe(self, symbols: list[str]):
        """订阅股票代码"""
        for symbol in symbols:
            if symbol not in self.subscribed_symbols:
                self.subscribed_symbols.add(symbol)
                logger.info(f"✅ 订阅价格更新: {symbol}")
                
                # 如果已经在运行，立即获取一次价格
                if self.running:
                    self._fetch_price_for_symbol(symbol)
    
    def unsubscribe(self, symbols: list[str]):
        """取消订阅股票代码"""
        for symbol in symbols:
            if symbol in self.subscribed_symbols:
                self.subscribed_symbols.remove(symbol)
                logger.info(f"🔕 取消订阅: {symbol}")
                
                # 清理数据
                self.latest_prices.pop(symbol, None)
                self.latest_ohlcv.pop(symbol, None)
    
    def add_price_callback(self, callback: Callable):
        """添加价格更新回调函数"""
        self.price_callbacks.append(callback)
        logger.debug(f"添加价格回调，当前共 {len(self.price_callbacks)} 个回调")
    
    def _fetch_price_for_symbol(self, symbol: str):
        """获取单个股票的最新价格"""
        try:
            # 获取当前时间和前10分钟的时间范围（确保有数据）
            end_time = datetime.now()
            start_time = end_time - timedelta(minutes=10)
            
            start_timestamp = int(start_time.timestamp())
            end_timestamp = int(end_time.timestamp())
            
            # 调用 Finnhub API 获取分钟级 OHLCV 数据
            data = self.finnhub_client.stock_candles(
                symbol, 
                '1',  # 1分钟 K线
                start_timestamp, 
                end_timestamp
            )
            
            # 检查返回数据
            if data and data.get('s') == 'ok':
                # 确保有数据
                if data.get('c') and len(data['c']) > 0:
                    # 获取最新的一根 K线
                    latest_price = data['c'][-1]  # 最新收盘价
                    latest_open = data['o'][-1]
                    latest_high = data['h'][-1]
                    latest_low = data['l'][-1]
                    latest_volume = data['v'][-1] if data.get('v') else 0
                    latest_timestamp = data['t'][-1] * 1000  # 转为毫秒
                    
                    # 更新价格缓存
                    self.latest_prices[symbol] = latest_price
                    
                    # 存储完整 OHLCV
                    self.latest_ohlcv[symbol] = {
                        'open': latest_open,
                        'high': latest_high,
                        'low': latest_low,
                        'close': latest_price,
                        'volume': latest_volume,
                        'timestamp': latest_timestamp
                    }
                    
                    # 触发所有回调
                    for callback in self.price_callbacks:
                        try:
                            callback({
                                "symbol": symbol,
                                "price": latest_price,
                                "volume": latest_volume,
                                "timestamp": latest_timestamp,
                                "ohlcv": self.latest_ohlcv[symbol]
                            })
                        except Exception as e:
                            logger.error(f"价格回调错误 ({symbol}): {e}")
                    
                    logger.info(f"💹 {symbol}: ${latest_price:.2f} (Vol: {latest_volume:,.0f})")
                    return True
                else:
                    logger.warning(f"⚠️ {symbol}: API 返回空数据")
                    return False
            elif data and data.get('s') == 'no_data':
                logger.warning(f"⚠️ {symbol}: 无可用数据（可能市场关闭或股票代码无效）")
                return False
            else:
                logger.warning(f"⚠️ {symbol}: API 返回异常状态: {data.get('s') if data else 'None'}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 获取 {symbol} 价格失败: {e}")
            return False
    
    def _fetch_latest_prices(self):
        """获取所有订阅股票的最新价格"""
        if not self.subscribed_symbols:
            logger.debug("没有订阅的股票，跳过价格获取")
            return
        
        logger.info(f"📊 开始获取 {len(self.subscribed_symbols)} 只股票的价格...")
        
        success_count = 0
        for symbol in list(self.subscribed_symbols):
            if self._fetch_price_for_symbol(symbol):
                success_count += 1
            
            # 避免 API 限流，每个请求之间稍微延迟
            time.sleep(0.1)
        
        logger.info(f"✅ 价格更新完成: {success_count}/{len(self.subscribed_symbols)} 成功")
    
    def start(self):
        """启动价格轮询（在独立线程中）"""
        if self.running:
            logger.warning("实时价格管理器已在运行")
            return
        
        if not self.subscribed_symbols:
            logger.warning("⚠️ 没有订阅任何股票，价格管理器将不会获取数据")
        
        self.running = True
        
        def poll_prices():
            logger.info(f"🚀 价格轮询线程启动（间隔: {self.poll_interval}秒）")
            
            # 立即获取一次价格
            try:
                self._fetch_latest_prices()
            except Exception as e:
                logger.error(f"初始价格获取失败: {e}")
            
            # 定时轮询
            while self.running:
                try:
                    time.sleep(self.poll_interval)
                    
                    if self.running:  # 再次检查，避免在 sleep 期间被停止
                        self._fetch_latest_prices()
                        
                except Exception as e:
                    logger.error(f"价格轮询错误: {e}")
                    if self.running:
                        time.sleep(5)  # 错误后短暂等待再重试
        
        self.thread = threading.Thread(target=poll_prices, daemon=True)
        self.thread.start()
        logger.info("🚀 实时价格管理器已启动（OHLCV 轮询模式）")
    
    def stop(self):
        """停止价格轮询"""
        if not self.running:
            logger.warning("实时价格管理器未在运行")
            return
        
        logger.info("🛑 正在停止实时价格管理器...")
        self.running = False
        
        # 等待线程结束（最多等待 2 秒）
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
        
        logger.info("🛑 实时价格管理器已停止")
    
    def get_latest_price(self, symbol: str) -> Optional[float]:
        """获取最新价格"""
        return self.latest_prices.get(symbol)
    
    def get_all_latest_prices(self) -> Dict[str, float]:
        """获取所有最新价格"""
        return self.latest_prices.copy()
    
    def get_ohlcv(self, symbol: str) -> Optional[Dict]:
        """获取完整的 OHLCV 数据"""
        return self.latest_ohlcv.get(symbol)
    
    def get_all_ohlcv(self) -> Dict[str, Dict]:
        """获取所有股票的 OHLCV 数据"""
        return self.latest_ohlcv.copy()


class RealtimePortfolioCalculator:
    """实时Portfolio净值计算器"""
    
    def __init__(self, price_manager: RealtimePriceManager):
        self.price_manager = price_manager
        self.holdings: Dict[str, Dict] = {}  # {symbol: {quantity, avg_cost}}
        self.cash: float = 0.0
        self.initial_value: float = 0.0
        
    def update_holdings(self, holdings: Dict[str, Dict], cash: float):
        """更新持仓信息"""
        self.holdings = holdings.copy()
        self.cash = cash
        
        if self.initial_value == 0.0:
            self.initial_value = self.calculate_total_value()
    
    def calculate_total_value(self) -> float:
        """计算Portfolio总价值"""
        positions_value = 0.0
        
        for symbol, holding in self.holdings.items():
            latest_price = self.price_manager.get_latest_price(symbol)
            if latest_price:
                quantity = holding.get('quantity', 0)
                positions_value += latest_price * quantity
            else:
                # 如果没有实时价格，使用平均成本
                avg_cost = holding.get('avg_cost', 0)
                quantity = holding.get('quantity', 0)
                positions_value += avg_cost * quantity
        
        return positions_value + self.cash
    
    def calculate_pnl(self) -> Dict[str, float]:
        """计算盈亏"""
        current_value = self.calculate_total_value()
        pnl_dollar = current_value - self.initial_value
        pnl_percent = (pnl_dollar / self.initial_value * 100) if self.initial_value > 0 else 0.0
        
        return {
            'total_value': current_value,
            'initial_value': self.initial_value,
            'pnl_dollar': pnl_dollar,
            'pnl_percent': pnl_percent,
            'cash': self.cash
        }
    
    def get_position_details(self) -> list[Dict]:
        """获取各持仓详情"""
        positions = []
        
        for symbol, holding in self.holdings.items():
            quantity = holding.get('quantity', 0)
            avg_cost = holding.get('avg_cost', 0)
            latest_price = self.price_manager.get_latest_price(symbol)
            
            if latest_price:
                current_value = latest_price * quantity
                cost_basis = avg_cost * quantity
                pnl = current_value - cost_basis
                pnl_percent = (pnl / cost_basis * 100) if cost_basis > 0 else 0.0
            else:
                latest_price = avg_cost
                current_value = avg_cost * quantity
                pnl = 0.0
                pnl_percent = 0.0
            
            positions.append({
                'symbol': symbol,
                'quantity': quantity,
                'avg_cost': avg_cost,
                'current_price': latest_price,
                'current_value': current_value,
                'pnl': pnl,
                'pnl_percent': pnl_percent
            })
        
        return positions
