"""
状态管理器 - 管理服务器状态的持久化和历史记录
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict, field

logger = logging.getLogger(__name__)


@dataclass
class FeedMessage:
    """统一的Feed消息格式"""
    type: str  # 'message', 'conference', etc.
    timestamp: float  # Unix timestamp in milliseconds
    content: str
    agent: str = 'System'
    role: str = 'System'
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式（前端兼容）"""
        return {
            'id': f"{self.type}-{self.timestamp}",
            'type': 'message',
            'data': {
                'id': f"{self.type}-{self.timestamp}",
                'timestamp': self.timestamp,
                'agent': self.agent,
                'role': self.role,
                'content': self.content,
                **self.metadata
            }
        }
    
    @classmethod
    def from_event(cls, event: Dict[str, Any]) -> Optional['FeedMessage']:
        """从事件创建FeedMessage"""
        event_type = event.get('type', '')
        
        # 只保存这些类型的消息
        save_types = {
            'system', 'agent_message', 'day_start', 'day_complete', 
            'day_error', 'team_summary'
        }
        
        if event_type not in save_types:
            return None
        
        # 解析时间戳
        timestamp = event.get('timestamp')
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00')).timestamp() * 1000
            except:
                timestamp = datetime.now().timestamp() * 1000
        elif not timestamp:
            timestamp = datetime.now().timestamp() * 1000
        
        # 提取内容
        content = event.get('content', '')
        agent = event.get('agentName') or event.get('agent') or 'System'
        role = event.get('role', 'System')
        
        # 根据类型优化内容显示
        if event_type == 'day_start':
            content = f"Starting day: {event.get('date', 'Unknown')}"
        elif event_type == 'day_complete':
            content = f"Day completed: {event.get('date', 'Unknown')}"
        elif event_type == 'day_error':
            content = f"Day error: {event.get('date', 'Unknown')} - {event.get('error', 'Unknown error')}"
        elif event_type == 'team_summary':
            balance = event.get('balance', 0)
            pnl = event.get('pnlPct', 0)
            content = f"Portfolio update: ${balance:,.0f} ({'+' if pnl >= 0 else ''}{pnl:.2f}%)"
        
        # 保存额外的元数据
        metadata = {k: v for k, v in event.items() 
                   if k not in ['type', 'timestamp', 'content', 'agent', 'agentName', 'role']}
        
        return cls(
            type=event_type,
            timestamp=timestamp,
            content=content,
            agent=agent,
            role=role,
            metadata=metadata
        )


class StateManager:
    """服务器状态管理器 - 负责状态的持久化和历史记录"""
    
    def __init__(self, config_name: str, base_dir: Path, max_history: int = 200):
        self.config_name = config_name
        self.base_dir = base_dir
        self.max_history = max_history
        
        # 初始化状态
        self.state: Dict[str, Any] = {
            'status': 'initializing',
            'current_date': None,
            'portfolio': {},
            'holdings': [],
            'trades': [],
            'stats': None,
            'leaderboard': [],
            'realtime_prices': {},
            'system_started': datetime.now().isoformat()
        }
        
        # Feed历史记录（使用FeedMessage对象）
        self._feed_history: List[FeedMessage] = []
    
    def get_state_file_path(self) -> Path:
        """获取状态文件路径"""
        state_dir = self.base_dir / "live_trading" / "data"
        state_dir.mkdir(parents=True, exist_ok=True)
        return state_dir / f"server_state_{self.config_name}.json"
    
    def update(self, key: str, value: Any):
        """更新状态"""
        self.state[key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取状态"""
        return self.state.get(key, default)
    
    def add_feed_message(self, event: Dict[str, Any]) -> bool:
        """添加消息到feed历史"""
        message = FeedMessage.from_event(event)
        if not message:
            return False
        
        self._feed_history.insert(0, message)
        if len(self._feed_history) > self.max_history:
            self._feed_history = self._feed_history[:self.max_history]
        
        return True
    
    def get_feed_history(self) -> List[Dict[str, Any]]:
        """获取feed历史（转换为前端格式）"""
        return [msg.to_dict() for msg in self._feed_history]
    
    def get_full_state(self) -> Dict[str, Any]:
        """获取完整状态（包括feed历史）"""
        return {
            **self.state,
            'feed_history': self.get_feed_history()
        }
    
    def save(self):
        """保存状态到文件"""
        try:
            state_file = self.get_state_file_path()
            
            # 准备要保存的状态
            state_to_save = {
                **self.state,
                'feed_history': [asdict(msg) for msg in self._feed_history[:self.max_history]],
                'trades': self.state.get('trades', [])[:100],  # 只保存最近100笔
                'last_saved': datetime.now().isoformat()
            }
            
            with open(state_file, 'w') as f:
                json.dump(state_to_save, f, ensure_ascii=False, indent=2, default=str)
            
            logger.debug(f"✅ 状态已保存到: {state_file}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 保存状态失败: {e}")
            return False
    
    def load(self) -> bool:
        """从文件加载状态"""
        try:
            state_file = self.get_state_file_path()
            if not state_file.exists():
                logger.info("未找到已保存的状态文件")
                return False
            
            with open(state_file, 'r') as f:
                saved_state = json.load(f)
            
            # 恢复feed历史
            feed_history = saved_state.pop('feed_history', [])
            self._feed_history = []
            for item in feed_history:
                try:
                    msg = FeedMessage(**item)
                    self._feed_history.append(msg)
                except Exception as e:
                    logger.warning(f"跳过无效的历史消息: {e}")
            
            # 恢复其他状态
            for key in ['status', 'current_date', 'portfolio', 'holdings', 'trades', 
                       'stats', 'leaderboard', 'trading_days_total', 'trading_days_completed']:
                if key in saved_state and saved_state[key] is not None:
                    self.state[key] = saved_state[key]
            
            logger.info(f"✅ 已从文件恢复状态 (上次保存: {saved_state.get('last_saved', 'unknown')})")
            logger.info(f"   📝 历史消息: {len(self._feed_history)} 条")
            logger.info(f"   💼 持仓: {len(self.state.get('holdings', []))} 个")
            logger.info(f"   📊 交易记录: {len(self.state.get('trades', []))} 笔")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 加载状态失败: {e}")
            return False
    
    def load_historical_equity(self) -> Dict[str, List]:
        """加载历史equity数据"""
        try:
            returns_file = self.base_dir / "live_trading" / "data" / "cumulative_returns.json"
            if not returns_file.exists():
                return {'equity': [], 'baseline': [], 'strategies': []}
            
            with open(returns_file, 'r') as f:
                data = json.load(f)
            
            # 转换为前端格式
            equity = []
            for date_str, value in sorted(data.items()):
                try:
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                    equity.append({
                        't': int(date_obj.timestamp() * 1000),
                        'v': value
                    })
                except:
                    continue
            
            return {
                'equity': equity,
                'baseline': [],
                'strategies': []
            }
            
        except Exception as e:
            logger.warning(f"加载历史equity数据失败: {e}")
            return {'equity': [], 'baseline': [], 'strategies': []}

