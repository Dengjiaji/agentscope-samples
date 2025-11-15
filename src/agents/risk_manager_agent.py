"""
Risk Manager Agent - Risk Management Agent
Provides unified risk assessment and position management interface (based on AgentScope)
"""
import os
from typing import Dict, Any, Optional, Literal
import json
import numpy as np
import pandas as pd

from agentscope.agent import AgentBase
from agentscope.message import Msg
from .prompt_loader import PromptLoader

from ..graph.state import AgentState
from ..utils.progress import progress
from ..tools.data_tools import get_prices, prices_to_df, get_last_tradeday
import pdb

class RiskManagerAgent(AgentBase):
    """Risk Management Agent (based on AgentScope)"""
    
    def __init__(self, 
                 agent_id: str = "risk_manager",
                 mode: Literal["basic", "portfolio"] = "basic",
                 config: Optional[Dict[str, Any]] = None):
        """
        Initialize Risk Management Agent
        
        Args:
            agent_id: Agent ID
            mode: Mode
                - "basic": Basic risk assessment (provides risk level and score)
                - "portfolio": Portfolio mode (calculates position limits and maximum shares)
            config: Configuration dictionary
        
        Examples:
            >>> # Basic risk assessment
            >>> agent = RiskManagerAgent(mode="basic")
            >>> 
            >>> # Portfolio position management
            >>> agent = RiskManagerAgent(mode="portfolio")
        """
        # Initialize AgentBase (does not accept parameters)
        super().__init__()
        
        # Set name attribute
        self.name = agent_id
        self.agent_id = agent_id  # Keep agent_id attribute for compatibility with existing code
        self.agent_type = "risk_manager"
        
        self.mode = mode
        self.config = config or {}
        
        # Prompt loader
        self.prompt_loader = PromptLoader()
        
        # Load configuration
        if mode == "basic":
            self.risk_config = self._load_or_default_risk_config()
        else:
            self.position_config = self._load_or_default_position_config()
    
    def _load_or_default_risk_config(self) -> Dict[str, Any]:
        """Load risk level configuration"""
        try:
            return self.prompt_loader.load_yaml_config(self.agent_type, "risk_levels")
        except FileNotFoundError:
            # Return default configuration
            return self._get_default_risk_config()
    
    def _load_or_default_position_config(self) -> Dict[str, Any]:
        """Load position limit configuration"""
        try:
            return self.prompt_loader.load_yaml_config(self.agent_type, "position_limits")
        except FileNotFoundError:
            return self._get_default_position_config()
    
    def execute(self, state: AgentState) -> Dict[str, Any]:
        """
        Execute risk management logic
        
        Args:
            state: AgentState
        
        Returns:
            Updated state dictionary
        """
        data = state["data"]
        tickers = data["tickers"]
        api_key = os.getenv("FINNHUB_API_KEY")
        
        # Calculate volatility
        volatility_data = {}
        current_prices = {}
        
        for ticker in tickers:
            progress.update_status(self.agent_id, ticker, "Fetching price data and calculating volatility")
            
            # ⭐ Strategy:
            # 1. Volatility calculation: Use historical data (up to T-1 day) to avoid incomplete data
            # 2. Current price: Use T-day opening price to reflect actual price level at market open
            
            # Get historical data up to T-1 day for volatility calculation
            adjusted_end_date = get_last_tradeday(data["end_date"])
            historical_prices = get_prices(
                ticker=ticker,
                start_date=data["start_date"],
                end_date=adjusted_end_date,
                api_key=api_key,
            )
            
            if not historical_prices:
                progress.update_status(self.agent_id, ticker, "Warning: Historical price data not found")
                volatility_data[ticker] = self._get_default_volatility()
                current_prices[ticker] = 0.0
                continue
            
            prices_df = prices_to_df(historical_prices)
            
            if prices_df.empty or len(prices_df) < 1:
                volatility_data[ticker] = self._get_default_volatility()
                current_prices[ticker] = 0.0
                continue
            
            # Calculate volatility (based on historical data up to and including T-1 day)
            vol_metrics = self._calculate_volatility_metrics(prices_df)
            volatility_data[ticker] = vol_metrics
            
            # ⭐ Get T-day opening price as current price
            try:
                today_prices = get_prices(
                    ticker=ticker,
                    start_date=data["end_date"],
                    end_date=data["end_date"],
                    api_key=api_key,
                )
                
                if today_prices and len(today_prices) > 0:
                    # Use T-day opening price
                    today_df = prices_to_df(today_prices)
                    if not today_df.empty and "open" in today_df.columns:
                        current_price = float(today_df["open"].iloc[0])
                        current_prices[ticker] = current_price
                        price_type = "open"
                    else:
                        # If no opening price, use T-1 day closing price as fallback
                        current_price = float(prices_df["close"].iloc[-1])
                        current_prices[ticker] = current_price
                        price_type = "T-1 close"
                else:
                    # If T-day data unavailable, use T-1 day closing price
                    current_price = float(prices_df["close"].iloc[-1])
                    current_prices[ticker] = current_price
                    price_type = "T-1 close (fallback)"
                    
                progress.update_status(
                    self.agent_id, 
                    ticker, 
                    f"Price: ${current_price:.2f} ({price_type}), Annualized volatility: {vol_metrics['annualized_volatility']:.1%}"
                )
            except Exception as e:
                # Exception case: use T-1 day closing price
                current_price = float(prices_df["close"].iloc[-1])
                current_prices[ticker] = current_price
                progress.update_status(
                    self.agent_id, 
                    ticker, 
                    f"Price: ${current_price:.2f} (T-1 close/exception), Annualized volatility: {vol_metrics['annualized_volatility']:.1%}"
                )
        
        # Generate risk analysis based on mode
        if self.mode == "basic":
            risk_analysis = self._generate_basic_risk_analysis(
                tickers, volatility_data, current_prices
            )
        else:  # portfolio mode
            risk_analysis = self._generate_portfolio_risk_analysis(
                tickers, volatility_data, current_prices, state
            )
        
        # Create message (using AgentScope Msg format)
        message = Msg(
            name=self.name,
            content=json.dumps(risk_analysis),
            role="assistant",
            metadata={}
        )

        # Update state
        state["data"]["analyst_signals"][self.agent_id] = risk_analysis
        
        progress.update_status(self.agent_id, None, "Done")
        
        return {
            "messages": [message.to_dict()],  # Convert to dict
            "data": data,
        }
    
    def _generate_basic_risk_analysis(self, tickers: list[str],
                                     volatility_data: Dict[str, Dict],
                                     current_prices: Dict[str, float]) -> Dict[str, Dict]:
        """Generate basic risk assessment"""
        risk_analysis = {}
        
        for ticker in tickers:
            vol_data = volatility_data.get(ticker, {})
            if not vol_data:
                risk_analysis[ticker] = {
                    "risk_level": "unknown",
                    "risk_score": 0,
                    "current_price": float(current_prices.get(ticker, 0.0)),
                    "volatility_info": {},
                    "risk_assessment": "Missing volatility data, unable to perform risk analysis"
                }
                continue
            
            annualized_vol = vol_data.get("annualized_volatility", 0.25)
            vol_percentile = vol_data.get("volatility_percentile", 50)
            daily_vol = vol_data.get("daily_volatility", 0.025)
            data_points = vol_data.get("data_points", 0)
            
            risk_level, risk_score, assessment = self._calculate_risk_assessment(
                ticker, annualized_vol, vol_percentile, daily_vol, data_points
            )
            
            risk_analysis[ticker] = {
                "risk_level": risk_level,
                "risk_score": risk_score,
                "current_price": float(current_prices.get(ticker, 0.0)),
                "volatility_info": {
                    "annualized_volatility": annualized_vol,
                    "daily_volatility": daily_vol,
                    "volatility_percentile": vol_percentile,
                    "data_points": data_points
                },
                "risk_assessment": assessment
            }
            
            progress.update_status(
                self.agent_id, 
                ticker, 
                f"Risk level: {risk_level.upper()}, Risk score: {risk_score}"
            )
        
        return risk_analysis
    
    def _generate_portfolio_risk_analysis(self, tickers: list[str],
                                         volatility_data: Dict[str, Dict],
                                         current_prices: Dict[str, float],
                                         state: AgentState) -> Dict[str, Dict]:
        """Generate Portfolio risk analysis (includes position limits)"""
        portfolio = state["data"]["portfolio"]
        risk_analysis = {}
        
        # Calculate total portfolio value
        total_value = portfolio.get("cash", 0.0)
        for ticker, position in portfolio.get("positions", {}).items():
            if ticker in current_prices:
                total_value += position.get("long", 0) * current_prices[ticker]
                total_value -= position.get("short", 0) * current_prices[ticker]
        
        progress.update_status(self.agent_id, None, f"Total portfolio value: {total_value:.2f}")
        
        for ticker in tickers:
            vol_data = volatility_data.get(ticker, {})
            price = current_prices.get(ticker, 0)
            
            if price <= 0 or not vol_data:
                risk_analysis[ticker] = {
                    "remaining_position_limit": 0.0,
                    "current_price": 0.0,
                    "max_shares": 0,
                    "reasoning": {"error": "Missing price or volatility data"}
                }
                continue
            
            # Calculate volatility-adjusted position limit
            annualized_vol = vol_data.get("annualized_volatility", 0.25)
            vol_adjusted_limit = self._calculate_volatility_adjusted_limit(annualized_vol)
            
            position_limit = total_value * vol_adjusted_limit
            
            # Calculate current position
            position = portfolio.get("positions", {}).get(ticker, {})
            current_position_value = abs(
                position.get("long", 0) * price - 
                position.get("short", 0) * price
            )
            
            remaining_limit = position_limit - current_position_value
            max_position_size = min(remaining_limit, portfolio.get("cash", 0))
            max_shares = int(max_position_size / price) if price > 0 else 0
            
            risk_analysis[ticker] = {
                "remaining_position_limit": float(max_position_size),
                "current_price": float(price),
                "max_shares": int(max_shares),
                "volatility_metrics": vol_data,
                "reasoning": {
                    "portfolio_value": float(total_value),
                    "current_position_value": float(current_position_value),
                    "base_position_limit_pct": float(vol_adjusted_limit),
                    "position_limit": float(position_limit),
                    "remaining_limit": float(remaining_limit),
                    "available_cash": float(portfolio.get("cash", 0))
                }
            }
        
        return risk_analysis
    
    def _calculate_volatility_metrics(self, prices_df: pd.DataFrame, 
                                     lookback_days: int = 60) -> Dict[str, float]:
        """Calculate volatility metrics"""
        if len(prices_df) < 2:
            return self._get_default_volatility()
        
        daily_returns = prices_df["close"].pct_change().dropna()
        
        if len(daily_returns) < 2:
            return self._get_default_volatility()
        
        recent_returns = daily_returns.tail(min(lookback_days, len(daily_returns)))
        daily_vol = recent_returns.std()
        annualized_vol = daily_vol * np.sqrt(252)
        
        # Calculate percentile
        if len(daily_returns) >= 30:
            rolling_vol = daily_returns.rolling(window=30).std().dropna()
            if len(rolling_vol) > 0:
                current_vol_percentile = (rolling_vol <= daily_vol).mean() * 100
            else:
                current_vol_percentile = 50.0
        else:
            current_vol_percentile = 50.0
        
        return {
            "daily_volatility": float(daily_vol) if not np.isnan(daily_vol) else 0.025,
            "annualized_volatility": float(annualized_vol) if not np.isnan(annualized_vol) else 0.25,
            "volatility_percentile": float(current_vol_percentile) if not np.isnan(current_vol_percentile) else 50.0,
            "data_points": len(recent_returns)
        }
    
    def _calculate_risk_assessment(self, ticker: str, annualized_vol: float,
                                   vol_percentile: float, daily_vol: float,
                                   data_points: int) -> tuple:
        """Calculate risk assessment"""
        # Risk level based on volatility
        if annualized_vol < 0.15:
            risk_level = "low"
            base_score = 25
            if vol_percentile < 30:
                risk_score = base_score - 10
                assessment = f"Low risk stock, annualized volatility {annualized_vol:.1%}, currently at historically low volatility level"
            else:
                risk_score = base_score
                assessment = f"Low risk stock, annualized volatility {annualized_vol:.1%}, price volatility relatively mild"
        elif annualized_vol < 0.30:
            risk_level = "medium"
            base_score = 50
            if vol_percentile > 70:
                risk_score = base_score + 15
                assessment = f"Medium risk stock, annualized volatility {annualized_vol:.1%}, volatility currently rising"
            else:
                risk_score = base_score
                assessment = f"Medium risk stock, annualized volatility {annualized_vol:.1%}, volatility at normal level"
        elif annualized_vol < 0.50:
            risk_level = "high"
            base_score = 75
            assessment = f"High risk stock, annualized volatility {annualized_vol:.1%}, significant price volatility"
        else:
            risk_level = "very_high"
            base_score = 90
            assessment = f"Very high risk stock, annualized volatility {annualized_vol:.1%}, extreme price volatility"
        
        # Data quality adjustment
        if data_points < 10:
            assessment += f" (Note: Based on only {data_points} data points)"
            base_score = min(base_score + 10, 100)
        
        return risk_level, max(0, min(100, base_score)), assessment

    def _calculate_volatility_adjusted_limit(self, annualized_volatility: float) -> float:
        """Calculate volatility-adjusted position limit percentage"""
        base_limit = 0.35  # 35% baseline
        
        if annualized_volatility < 0.15:
            vol_multiplier = 1.3  # Maximum 45.5% (35% * 1.3)
        elif annualized_volatility < 0.30:
            vol_multiplier = 1.1 - (annualized_volatility - 0.15) * 0.8
        elif annualized_volatility < 0.50:
            vol_multiplier = 0.8 - (annualized_volatility - 0.30) * 0.6
        else:
            vol_multiplier = 0.4  # Maximum 14% (35% * 0.4)
        
        vol_multiplier = max(0.4, min(1.3, vol_multiplier))
        return base_limit * vol_multiplier

    def _get_default_volatility(self) -> Dict[str, float]:
        """Get default volatility"""
        return {
            "daily_volatility": 0.05,
            "annualized_volatility": 0.05 * np.sqrt(252),
            "volatility_percentile": 100,
            "data_points": 0
        }
    
    def _get_default_risk_config(self) -> Dict[str, Any]:
        """Get default risk configuration"""
        return {
            "volatility_thresholds": {
                "low": {"max_volatility": 0.15},
                "medium": {"min_volatility": 0.15, "max_volatility": 0.30},
                "high": {"min_volatility": 0.30, "max_volatility": 0.50},
                "very_high": {"min_volatility": 0.50}
            }
        }
    
    def _get_default_position_config(self) -> Dict[str, Any]:
        """Get default position configuration"""
        return {
            "base_position_limit": 0.20,
            "volatility_adjustments": {
                "low_volatility": {"max_volatility": 0.15, "multiplier": 1.25},
                "very_high_volatility": {"min_volatility": 0.50, "multiplier": 0.50}
            }
        }

