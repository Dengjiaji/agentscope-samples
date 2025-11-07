import asyncio
import random
import logging
from datetime import datetime, timedelta
from typing import Callable, Dict, Any

logger = logging.getLogger(__name__)


class MockSimulator:
    """模拟数据生成器，用于测试前端"""
    
    def __init__(
        self, 
        state_manager,
        broadcast_callback: Callable,
        initial_cash: float = 100000
    ):
        self.state_manager = state_manager
        self.broadcast = broadcast_callback
        self.initial_cash = initial_cash
        
        # Mock股票列表
        self.tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META']
        
        # 初始价格
        self.prices = {
            'AAPL': 237.50,
            'MSFT': 425.30,
            'GOOGL': 161.50,
            'AMZN': 218.45,
            'NVDA': 950.00,
            'META': 573.22
        }
        
        # Mock agents
        self.agents = [
            {'id': 'alpha', 'name': 'Bob', 'role': 'Portfolio Manager'},
            {'id': 'beta', 'name': 'Carl', 'role': 'Risk Manager'},
            {'id': 'gamma', 'name': 'Alice', 'role': 'Valuation Analyst'},
            {'id': 'delta', 'name': 'David', 'role': 'Sentiment Analyst'},
            {'id': 'epsilon', 'name': 'Eve', 'role': 'Fundamentals Analyst'},
            {'id': 'zeta', 'name': 'Frank', 'role': 'Technical Analyst'}
        ]
    
    def _generate_historical_equity(self, days: int = 30) -> tuple[list, float]:
        """生成历史equity数据"""
        equity_data = []
        start_time = datetime.now() - timedelta(days=days)
        
        current_value = self.initial_cash
        for i in range(days):
            t = start_time + timedelta(days=i)
            daily_change_pct = random.uniform(-1.5, 2.0)
            current_value *= (1 + daily_change_pct / 100)
            equity_data.append({
                't': int(t.timestamp() * 1000),
                'v': current_value
            })
        
        return equity_data, current_value
    
    def _generate_leaderboard(self) -> list:
        """生成排行榜数据"""
        leaderboard = []
        for idx, agent in enumerate(self.agents, 1):
            leaderboard.append({
                'agentId': agent['id'],
                'name': agent['name'],
                'role': agent['role'],
                'rank': idx,
                'accountValue': self.initial_cash * random.uniform(0.5, 1.5),
                'returnPct': random.uniform(-50, 80),
                'totalPL': random.uniform(-5000, 8000),
                'fees': random.uniform(200, 1500),
                'winRate': random.uniform(0.2, 0.7),
                'biggestWin': random.uniform(1000, 8000),
                'biggestLoss': random.uniform(-2000, -500),
                'sharpe': random.uniform(-0.7, 0.5),
                'trades': random.randint(20, 200)
            })
        
        leaderboard.sort(key=lambda x: x['returnPct'], reverse=True)
        for idx, agent in enumerate(leaderboard, 1):
            agent['rank'] = idx
        
        return leaderboard
    
    def _generate_holdings(self) -> list:
        """生成持仓数据"""
        return [
            {
                'ticker': 'AAPL',
                'qty': 120,
                'avg': 192.30,
                'currentPrice': self.prices['AAPL'],
                'pl': (self.prices['AAPL'] - 192.30) * 120,
                'weight': 0.21
            },
            {
                'ticker': 'NVDA',
                'qty': 40,
                'avg': 980.10,
                'currentPrice': self.prices['NVDA'],
                'pl': (self.prices['NVDA'] - 980.10) * 40,
                'weight': 0.18
            },
            {
                'ticker': 'MSFT',
                'qty': 20,
                'avg': 420.20,
                'currentPrice': self.prices['MSFT'],
                'pl': (self.prices['MSFT'] - 420.20) * 20,
                'weight': 0.15
            },
            {
                'ticker': 'GOOGL',
                'qty': 80,
                'avg': 142.50,
                'currentPrice': self.prices['GOOGL'],
                'pl': (self.prices['GOOGL'] - 142.50) * 80,
                'weight': 0.12
            }
        ]
    
    def _generate_trades(self, count: int = 20) -> list:
        """生成交易记录"""
        base_time = datetime.now()
        return [
            {
                'id': f't{i}',
                'timestamp': (base_time - timedelta(hours=i)).isoformat(),
                'side': 'BUY' if i % 2 == 0 else 'SELL',
                'ticker': random.choice(self.tickers),
                'qty': random.randint(5, 50),
                'price': random.uniform(100, 1000),
                'pnl': random.uniform(-500, 1000)
            }
            for i in range(count)
        ]
    
    def _generate_stats(self) -> dict:
        """生成统计数据"""
        return {
            'winRate': 0.62,
            'hitRate': 0.58,
            'totalTrades': 44,
            'bullBear': {
                'bull': {'n': 26, 'win': 17},
                'bear': {'n': 18, 'win': 10}
            }
        }
    
    def _initialize_state(self):
        """初始化mock状态"""
        # 生成历史equity数据
        equity_data, current_value = self._generate_historical_equity()
        
        # 更新portfolio状态
        self.state_manager.update('status', 'running')
        portfolio = self.state_manager.get('portfolio', {})
        portfolio['equity'] = equity_data
        portfolio['total_value'] = current_value
        self.state_manager.update('portfolio', portfolio)
        
        # 更新其他状态
        self.state_manager.update('leaderboard', self._generate_leaderboard())
        self.state_manager.update('holdings', self._generate_holdings())
        self.state_manager.update('trades', self._generate_trades())
        self.state_manager.update('stats', self._generate_stats())
        
        return current_value
    
    def _add_historical_messages(self):
        """添加历史消息"""
        base_time = datetime.now()
        for i in range(10):
            msg_time = base_time - timedelta(minutes=10-i)
            agent = random.choice(self.agents)
            
            historical_msg = {
                'type': 'agent_message',
                'agentId': agent['id'],
                'agentName': agent['name'],
                'role': agent['role'],
                'content': f"Historical analysis: Market analysis from {i+1} updates ago",
                'timestamp': msg_time.isoformat()
            }
            self.state_manager.add_feed_message(historical_msg)
    
    async def run(self):
        """运行模拟数据推送"""
        logger.info("🎭 开始Mock模式 - 模拟数据推送")
        
        # 初始化状态
        current_value = self._initialize_state()
        
        # 添加历史消息
        self._add_historical_messages()
        
        # 发送启动消息
        await self.broadcast({
            'type': 'system',
            'content': '🎭 Mock模式启动 - 开始模拟数据推送'
        })
        
        # 持续推送更新
        iteration = 0
        while True:
            iteration += 1
            
            # 1. 每秒更新一个随机价格
            await self._update_random_price(current_value)
            
            # 2. 每10秒更新一次equity数据点
            if iteration % 10 == 0:
                current_value = await self._update_equity(current_value)
            
            # 3. 每10秒更新一次leaderboard
            if iteration % 10 == 0:
                await self._update_leaderboard()
            
            # 4. 每30秒发送一条agent消息
            if iteration % 30 == 0:
                await self._send_agent_message()
            
            # 5. 每4秒模拟一笔新交易
            if iteration % 4 == 0:
                await self._create_new_trade()
            
            await asyncio.sleep(1)
    
    async def _update_random_price(self, base_value: float):
        """更新随机价格"""
        symbol = random.choice(self.tickers)
        old_price = self.prices[symbol]
        change_pct = random.uniform(-0.5, 0.5)
        new_price = old_price * (1 + change_pct / 100)
        self.prices[symbol] = new_price
        
        # 更新holdings中的当前价格和P&L
        holdings = self.state_manager.get('holdings', [])
        for holding in holdings:
            if holding['ticker'] in self.prices:
                holding['currentPrice'] = self.prices[holding['ticker']]
                holding['pl'] = (self.prices[holding['ticker']] - holding['avg']) * holding['qty']
        self.state_manager.update('holdings', holdings)
        
        # 更新portfolio value
        portfolio = self.state_manager.get('portfolio', {})
        current_value = portfolio.get('total_value', base_value)
        new_value = current_value * (1 + change_pct / 100)
        portfolio['total_value'] = new_value
        portfolio['pnl_percent'] = ((new_value - self.initial_cash) / self.initial_cash) * 100
        self.state_manager.update('portfolio', portfolio)
        
        await self.broadcast({
            'type': 'price_update',
            'symbol': symbol,
            'price': new_price,
            'timestamp': datetime.now().isoformat(),
            'portfolio': {
                'total_value': new_value,
                'pnl_percent': portfolio['pnl_percent']
            }
        })
    
    async def _update_equity(self, current_value: float) -> float:
        """更新equity数据"""
        new_equity_point = {
            't': int(datetime.now().timestamp() * 1000),
            'v': current_value
        }
        portfolio = self.state_manager.get('portfolio', {})
        equity = portfolio.get('equity', [])
        equity.append(new_equity_point)
        
        # 保持最近50个点
        if len(equity) > 50:
            equity = equity[-50:]
        portfolio['equity'] = equity
        self.state_manager.update('portfolio', portfolio)
        
        await self.broadcast({
            'type': 'team_summary',
            'balance': current_value,
            'pnlPct': portfolio.get('pnl_percent', 0),
            'equity': equity,
            'timestamp': datetime.now().isoformat()
        })
        
        return current_value
    
    async def _update_leaderboard(self):
        """更新排行榜"""
        leaderboard = self.state_manager.get('leaderboard', [])
        
        # 随机调整leaderboard
        for agent in leaderboard:
            agent['returnPct'] += random.uniform(-2, 3)
            agent['accountValue'] = self.initial_cash * (1 + agent['returnPct'] / 100)
        
        leaderboard.sort(key=lambda x: x['returnPct'], reverse=True)
        for idx, agent in enumerate(leaderboard, 1):
            agent['rank'] = idx
        
        self.state_manager.update('leaderboard', leaderboard)
        
        await self.broadcast({
            'type': 'team_leaderboard',
            'leaderboard': leaderboard,
            'timestamp': datetime.now().isoformat()
        })
    
    async def _send_agent_message(self):
        """发送agent消息"""
        agent = random.choice(self.agents)
        messages = [
            f"Analyzing {random.choice(self.tickers)} - showing strong momentum",
            f"Risk alert: volatility increasing in {random.choice(self.tickers)}",
            f"Portfolio rebalancing recommended",
            f"Technical indicators suggest buying opportunity in {random.choice(self.tickers)}",
            f"Market sentiment turning positive"
        ]
        
        await self.broadcast({
            'type': 'agent_message',
            'agentId': agent['id'],
            'agentName': agent['name'],
            'role': agent['role'],
            'content': random.choice(messages),
            'timestamp': datetime.now().isoformat()
        })
    
    async def _create_new_trade(self):
        """创建新交易"""
        trade_ticker = random.choice(self.tickers)
        trade = {
            'id': f't-{datetime.now().timestamp()}',
            'timestamp': datetime.now().isoformat(),
            'side': random.choice(['BUY', 'SELL']),
            'ticker': trade_ticker,
            'qty': random.randint(5, 50),
            'price': self.prices[trade_ticker],
            'pnl': random.uniform(-500, 1000)
        }
        
        # 添加到trades列表开头
        trades = self.state_manager.get('trades', [])
        trades.insert(0, trade)
        
        # 保持最近50笔交易
        if len(trades) > 50:
            trades = trades[:50]
        self.state_manager.update('trades', trades)
        
        # 广播新交易
        await self.broadcast({
            'type': 'team_trades',
            'trade': trade,
            'timestamp': datetime.now().isoformat()
        })

