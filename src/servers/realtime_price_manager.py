# src/servers/realtime_price_manager.py
"""
实时价格数据管理器 - Finnhub WebSocket集成
负责从Finnhub获取实时股票价格并广播给订阅者
"""
import asyncio
import json
import logging
import os
from typing import Dict, Set, Callable, Optional
import websocket
import threading
from datetime import datetime

logger = logging.getLogger(__name__)


class RealtimePriceManager:
    """实时价格管理器 - 连接Finnhub获取实时交易数据"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.ws = None
        self.subscribed_symbols: Set[str] = set()
        self.latest_prices: Dict[str, float] = {}
        self.price_callbacks: list[Callable] = []
        self.running = False
        self.thread = None
        
        # Finnhub WebSocket URL
        self.ws_url = f"wss://ws.finnhub.io?token={self.api_key}"
        
    def subscribe(self, symbols: list[str]):
        """订阅股票代码"""
        for symbol in symbols:
            if symbol not in self.subscribed_symbols:
                self.subscribed_symbols.add(symbol)
                if self.ws and self.running:
                    try:
                        self.ws.send(json.dumps({"type": "subscribe", "symbol": symbol}))
                        logger.info(f"✅ 订阅实时价格: {symbol}")
                    except Exception as e:
                        logger.error(f"❌ 订阅失败 {symbol}: {e}")
    
    def unsubscribe(self, symbols: list[str]):
        """取消订阅股票代码"""
        for symbol in symbols:
            if symbol in self.subscribed_symbols:
                self.subscribed_symbols.remove(symbol)
                if self.ws and self.running:
                    try:
                        self.ws.send(json.dumps({"type": "unsubscribe", "symbol": symbol}))
                        logger.info(f"🔕 取消订阅: {symbol}")
                    except Exception as e:
                        logger.error(f"❌ 取消订阅失败 {symbol}: {e}")
    
    def add_price_callback(self, callback: Callable):
        """添加价格更新回调函数"""
        self.price_callbacks.append(callback)
    
    def _on_message(self, ws, message):
        """处理接收到的消息"""
        try:
            data = json.loads(message)
            
            if data.get("type") == "trade":
                # 处理交易数据
                for trade in data.get("data", []):
                    symbol = trade.get("s")  # symbol
                    price = trade.get("p")   # price
                    volume = trade.get("v")  # volume
                    timestamp = trade.get("t")  # timestamp
                    
                    if symbol and price:
                        # 更新最新价格
                        self.latest_prices[symbol] = price
                        
                        # 调用所有回调函数
                        for callback in self.price_callbacks:
                            try:
                                callback({
                                    "symbol": symbol,
                                    "price": price,
                                    "volume": volume,
                                    "timestamp": timestamp
                                })
                            except Exception as e:
                                logger.error(f"价格回调错误: {e}")
            
            elif data.get("type") == "ping":
                # 响应心跳
                ws.send(json.dumps({"type": "pong"}))
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析错误: {e}")
        except Exception as e:
            logger.error(f"消息处理错误: {e}")
    
    def _on_error(self, ws, error):
        """处理错误"""
        logger.error(f"WebSocket错误: {error}")
    
    def _on_close(self, ws, close_status_code, close_msg):
        """连接关闭"""
        logger.warning(f"WebSocket连接关闭: {close_status_code} - {close_msg}")
        self.running = False
    
    def _on_open(self, ws):
        """连接建立"""
        logger.info("✅ Finnhub WebSocket连接已建立")
        
        # 订阅所有已添加的股票代码
        for symbol in self.subscribed_symbols:
            try:
                ws.send(json.dumps({"type": "subscribe", "symbol": symbol}))
                logger.info(f"✅ 订阅实时价格: {symbol}")
            except Exception as e:
                logger.error(f"❌ 订阅失败 {symbol}: {e}")
    
    def start(self):
        """启动实时价格连接（在独立线程中）"""
        if self.running:
            logger.warning("实时价格管理器已在运行")
            return
        
        self.running = True
        
        def run_websocket():
            websocket.enableTrace(False)
            self.ws = websocket.WebSocketApp(
                self.ws_url,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close
            )
            self.ws.on_open = self._on_open
            self.ws.run_forever()
        
        self.thread = threading.Thread(target=run_websocket, daemon=True)
        self.thread.start()
        logger.info("🚀 实时价格管理器已启动")
    
    def stop(self):
        """停止实时价格连接"""
        self.running = False
        if self.ws:
            self.ws.close()
        logger.info("🛑 实时价格管理器已停止")
    
    def get_latest_price(self, symbol: str) -> Optional[float]:
        """获取最新价格"""
        return self.latest_prices.get(symbol)
    
    def get_all_latest_prices(self) -> Dict[str, float]:
        """获取所有最新价格"""
        return self.latest_prices.copy()


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

