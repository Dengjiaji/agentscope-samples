"""
State Manager - Manages server state persistence and history
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict, field

from backend.config.path_config import get_logs_and_memory_dir

logger = logging.getLogger(__name__)


# Large data fields that should be excluded from feed_history to reduce file size
_LARGE_DATA_FIELDS = {'equity', 'baseline', 'baseline_vw', 'momentum', 'strategies'}


@dataclass
class FeedMessage:
    """Unified Feed message format - saves original event"""
    type: str  # event type
    timestamp: float  # Unix timestamp in milliseconds
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Return original event (processed uniformly by frontend)"""
        return self.metadata
    
    @classmethod
    def from_event(cls, event: Dict[str, Any]) -> Optional['FeedMessage']:
        event_type = event.get('type', '')
        
        save_types = {
            'system', 'agent_message', 'day_start', 'day_complete', 
            'day_error', 'team_summary', 'conference_start', 'conference_end', 'memory'
        }
        
        if event_type not in save_types:
            return None
        
        # For team_summary, strip large curve data to reduce storage size
        # Curves are already stored separately in portfolio state
        if event_type == 'team_summary':
            slim_event = {k: v for k, v in event.items() if k not in _LARGE_DATA_FIELDS}
            return cls(
                type=event_type,
                timestamp=event.get('timestamp', datetime.now().timestamp() * 1000),
                metadata=slim_event
            )
        
        return cls(
            type=event_type,
            timestamp=event.get('timestamp', datetime.now().timestamp() * 1000),
            metadata=event
        )


class StateManager:
    """Server state manager - responsible for state persistence and history"""
    
    def __init__(self, config_name: str, base_dir: Path, max_history: int = 200):
        self.config_name = config_name
        self.base_dir = base_dir
        self.max_history = max_history
        
        # Initialize state
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
        
        # Feed history (using FeedMessage objects)
        self._feed_history: List[FeedMessage] = []
    
    def get_state_file_path(self) -> Path:
        """Get state file path"""
        # Unified storage to logs_and_memory/{config_name}/state/ directory (located in project parent directory)
        state_dir = get_logs_and_memory_dir() / self.config_name / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        return state_dir / f"server_state.json"  # Simplified filename
    
    def update(self, key: str, value: Any):
        """Update state"""
        self.state[key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get state"""
        return self.state.get(key, default)
    
    def add_feed_message(self, event: Dict[str, Any]) -> bool:
        """Add message to feed history"""
        message = FeedMessage.from_event(event)
        if not message:
            return False
        
        self._feed_history.insert(0, message)
        if len(self._feed_history) > self.max_history:
            self._feed_history = self._feed_history[:self.max_history]
        
        return True
    
    def get_feed_history(self) -> List[Dict[str, Any]]:
        """Get feed history (converted to frontend format)"""
        return [msg.to_dict() for msg in self._feed_history]
    
    def get_full_state(self) -> Dict[str, Any]:
        """Get full state (including feed history)"""
        return {
            **self.state,
            'feed_history': self.get_feed_history()
        }
    
    def _truncate_curves(self, data: Dict[str, Any], max_points: int = 500) -> Dict[str, Any]:
        """Truncate curve data to reduce storage size"""
        result = data.copy()
        
        # Truncate portfolio curves
        if 'portfolio' in result and isinstance(result['portfolio'], dict):
            portfolio = result['portfolio'].copy()
            for curve_key in _LARGE_DATA_FIELDS:
                if curve_key in portfolio and isinstance(portfolio[curve_key], list):
                    portfolio[curve_key] = portfolio[curve_key][-max_points:]
            result['portfolio'] = portfolio
        
        return result
    
    def save(self):
        """Save state to file"""
        try:
            state_file = self.get_state_file_path()
            
            # Prepare state to save (with truncated curves)
            state_to_save = self._truncate_curves({
                **self.state,
                'feed_history': [asdict(msg) for msg in self._feed_history[:self.max_history]],
                'trades': self.state.get('trades', [])[:100],  # Only save last 100 trades
                'last_saved': datetime.now().isoformat()
            })
            
            # Use compact JSON format (no indent) to reduce file size
            with open(state_file, 'w') as f:
                json.dump(state_to_save, f, ensure_ascii=False, separators=(',', ':'), default=str)
            
            logger.debug(f"✅ State saved to: {state_file}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to save state: {e}")
            return False
    
    def load(self) -> bool:
        """Load state from file"""
        try:
            state_file = self.get_state_file_path()
            if not state_file.exists():
                logger.info("No saved state file found")
                return False
            
            with open(state_file, 'r') as f:
                saved_state = json.load(f)
            
            # Restore feed history
            feed_history = saved_state.pop('feed_history', [])
            self._feed_history = []
            for item in feed_history:
                try:
                    msg = FeedMessage(**item)
                    self._feed_history.append(msg)
                except Exception as e:
                    logger.warning(f"Skipping invalid history message: {e}")
            
            # Restore other state
            for key in ['status', 'current_date', 'portfolio', 'holdings', 'trades', 
                       'stats', 'leaderboard', 'trading_days_total', 'trading_days_completed']:
                if key in saved_state and saved_state[key] is not None:
                    self.state[key] = saved_state[key]
            
            logger.info(f"✅ State restored from file (last saved: {saved_state.get('last_saved', 'unknown')})")
            logger.info(f"   📝 History messages: {len(self._feed_history)} records")
            logger.info(f"   💼 Holdings: {len(self.state.get('holdings', []))} items")
            logger.info(f"   📊 Trade records: {len(self.state.get('trades', []))} trades")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to load state: {e}")
            return False
    
    def load_historical_equity(self) -> Dict[str, List]:
        """Load historical equity data"""
        try:
            # Unified read from logs_and_memory/{config_name}/state/ (located in project parent directory)
            returns_file = get_logs_and_memory_dir() / self.config_name / "state" / "cumulative_returns.json"
            if not returns_file.exists():
                return {'equity': [], 'baseline': [], 'strategies': []}
            
            with open(returns_file, 'r') as f:
                data = json.load(f)
            
            # Convert to frontend format
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
            logger.warning(f"Failed to load historical equity data: {e}")
            return {'equity': [], 'baseline': [], 'strategies': []}

