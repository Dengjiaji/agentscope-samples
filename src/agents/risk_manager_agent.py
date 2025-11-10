"""
Risk Manager Agent - 风险管理 Agent
提供统一的风险评估和仓位管理接口（基于AgentScope）
"""
from typing import Dict, Any, Optional, Literal
import json
import numpy as np
import pandas as pd

from agentscope.agent import AgentBase
from agentscope.message import Msg
from .prompt_loader import PromptLoader

from ..graph.state import AgentState
from ..utils.progress import progress
from ..utils.api_key import get_api_key_from_state
from ..tools.data_tools import get_prices, prices_to_df, get_last_tradeday
import pdb

class RiskManagerAgent(AgentBase):
    """风险管理 Agent（基于AgentScope）"""
    
    def __init__(self, 
                 agent_id: str = "risk_manager",
                 mode: Literal["basic", "portfolio"] = "basic",
                 config: Optional[Dict[str, Any]] = None):
        """
        初始化风险管理 Agent
        
        Args:
            agent_id: Agent ID
            mode: 模式
                - "basic": 基础风险评估（提供风险等级和评分）
                - "portfolio": Portfolio模式（计算仓位限制和最大股数）
            config: 配置字典
        
        Examples:
            >>> # 基础风险评估
            >>> agent = RiskManagerAgent(mode="basic")
            >>> 
            >>> # Portfolio 仓位管理
            >>> agent = RiskManagerAgent(mode="portfolio")
        """
        # 初始化AgentBase（不接受参数）
        super().__init__()
        
        # 设置name属性
        self.name = agent_id
        self.agent_id = agent_id  # 保留agent_id属性以兼容现有代码
        self.agent_type = "risk_manager"
        
        self.mode = mode
        self.config = config or {}
        
        # Prompt loader
        self.prompt_loader = PromptLoader()
        
        # 加载配置
        if mode == "basic":
            self.risk_config = self._load_or_default_risk_config()
        else:
            self.position_config = self._load_or_default_position_config()
    
    def _load_or_default_risk_config(self) -> Dict[str, Any]:
        """加载风险等级配置"""
        try:
            return self.prompt_loader.load_yaml_config(self.agent_type, "risk_levels")
        except FileNotFoundError:
            # 返回默认配置
            return self._get_default_risk_config()
    
    def _load_or_default_position_config(self) -> Dict[str, Any]:
        """加载仓位限制配置"""
        try:
            return self.prompt_loader.load_yaml_config(self.agent_type, "position_limits")
        except FileNotFoundError:
            return self._get_default_position_config()
    
    def execute(self, state: AgentState) -> Dict[str, Any]:
        """
        执行风险管理逻辑
        
        Args:
            state: AgentState
        
        Returns:
            更新后的状态字典
        """
        data = state["data"]
        tickers = data["tickers"]
        api_key = get_api_key_from_state(state, "FINNHUB_API_KEY")
        
        # 计算波动率
        volatility_data = {}
        current_prices = {}
        
        for ticker in tickers:
            progress.update_status(self.agent_id, ticker, "获取价格数据并计算波动率")
            
            # ⭐ 策略：
            # 1. 波动率计算：使用历史数据（截止到 T-1 日），避免使用不完整数据
            # 2. 当前价格：使用 T 日开盘价，反映当日开盘时的实际价格水平
            
            # 获取截止到 T-1 日的历史数据用于波动率计算
            adjusted_end_date = get_last_tradeday(data["end_date"])
            historical_prices = get_prices(
                ticker=ticker,
                start_date=data["start_date"],
                end_date=adjusted_end_date,
                api_key=api_key,
            )
            
            if not historical_prices:
                progress.update_status(self.agent_id, ticker, "警告: 未找到历史价格数据")
                volatility_data[ticker] = self._get_default_volatility()
                current_prices[ticker] = 0.0
                continue
            
            prices_df = prices_to_df(historical_prices)
            
            if prices_df.empty or len(prices_df) < 1:
                volatility_data[ticker] = self._get_default_volatility()
                current_prices[ticker] = 0.0
                continue
            
            # 计算波动率（基于 T-1 日及之前的历史数据）
            vol_metrics = self._calculate_volatility_metrics(prices_df)
            volatility_data[ticker] = vol_metrics
            
            # ⭐ 获取 T 日的开盘价作为当前价格
            try:
                today_prices = get_prices(
                    ticker=ticker,
                    start_date=data["end_date"],
                    end_date=data["end_date"],
                    api_key=api_key,
                )
                
                if today_prices and len(today_prices) > 0:
                    # 使用 T 日的开盘价
                    today_df = prices_to_df(today_prices)
                    if not today_df.empty and "open" in today_df.columns:
                        current_price = float(today_df["open"].iloc[0])
                        current_prices[ticker] = current_price
                        price_type = "开盘"
                    else:
                        # 如果没有开盘价，使用 T-1 日收盘价作为备选
                        current_price = float(prices_df["close"].iloc[-1])
                        current_prices[ticker] = current_price
                        price_type = "T-1收盘"
                else:
                    # 如果获取不到 T 日数据，使用 T-1 日收盘价
                    current_price = float(prices_df["close"].iloc[-1])
                    current_prices[ticker] = current_price
                    price_type = "T-1收盘(备用)"
                    
                progress.update_status(
                    self.agent_id, 
                    ticker, 
                    f"价格: ${current_price:.2f}({price_type}), 年化波动率: {vol_metrics['annualized_volatility']:.1%}"
                )
            except Exception as e:
                # 异常情况使用 T-1 日收盘价
                current_price = float(prices_df["close"].iloc[-1])
                current_prices[ticker] = current_price
                progress.update_status(
                    self.agent_id, 
                    ticker, 
                    f"价格: ${current_price:.2f}(T-1收盘/异常), 年化波动率: {vol_metrics['annualized_volatility']:.1%}"
                )
        
        # 根据模式生成风险分析
        if self.mode == "basic":
            risk_analysis = self._generate_basic_risk_analysis(
                tickers, volatility_data, current_prices
            )
        else:  # portfolio mode
            risk_analysis = self._generate_portfolio_risk_analysis(
                tickers, volatility_data, current_prices, state
            )
        
        # 创建消息（使用 AgentScope Msg 格式）
        message = Msg(
            name=self.name,
            content=json.dumps(risk_analysis),
            role="assistant",
            metadata={}
        )

        # 更新状态
        state["data"]["analyst_signals"][self.agent_id] = risk_analysis
        
        progress.update_status(self.agent_id, None, "完成")
        
        return {
            "messages": [message.to_dict()],  # 转换为dict
            "data": data,
        }
    
    def _generate_basic_risk_analysis(self, tickers: list[str],
                                     volatility_data: Dict[str, Dict],
                                     current_prices: Dict[str, float]) -> Dict[str, Dict]:
        """生成基础风险评估"""
        risk_analysis = {}
        
        for ticker in tickers:
            vol_data = volatility_data.get(ticker, {})
            if not vol_data:
                risk_analysis[ticker] = {
                    "risk_level": "unknown",
                    "risk_score": 0,
                    "current_price": float(current_prices.get(ticker, 0.0)),
                    "volatility_info": {},
                    "risk_assessment": "缺少波动率数据，无法进行风险分析"
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
                f"风险等级: {risk_level.upper()}, 风险评分: {risk_score}"
            )
        
        return risk_analysis
    
    def _generate_portfolio_risk_analysis(self, tickers: list[str],
                                         volatility_data: Dict[str, Dict],
                                         current_prices: Dict[str, float],
                                         state: AgentState) -> Dict[str, Dict]:
        """生成Portfolio风险分析（包含仓位限制）"""
        portfolio = state["data"]["portfolio"]
        risk_analysis = {}
        
        # 计算投资组合总价值
        total_value = portfolio.get("cash", 0.0)
        for ticker, position in portfolio.get("positions", {}).items():
            if ticker in current_prices:
                total_value += position.get("long", 0) * current_prices[ticker]
                total_value -= position.get("short", 0) * current_prices[ticker]
        
        progress.update_status(self.agent_id, None, f"投资组合总价值: {total_value:.2f}")
        
        for ticker in tickers:
            vol_data = volatility_data.get(ticker, {})
            price = current_prices.get(ticker, 0)
            
            if price <= 0 or not vol_data:
                risk_analysis[ticker] = {
                    "remaining_position_limit": 0.0,
                    "current_price": 0.0,
                    "max_shares": 0,
                    "reasoning": {"error": "缺少价格或波动率数据"}
                }
                continue
            
            # 计算波动率调整后的仓位限制
            annualized_vol = vol_data.get("annualized_volatility", 0.25)
            vol_adjusted_limit = self._calculate_volatility_adjusted_limit(annualized_vol)
            
            position_limit = total_value * vol_adjusted_limit
            
            # 计算当前持仓
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
        """计算波动率指标"""
        if len(prices_df) < 2:
            return self._get_default_volatility()
        
        daily_returns = prices_df["close"].pct_change().dropna()
        
        if len(daily_returns) < 2:
            return self._get_default_volatility()
        
        recent_returns = daily_returns.tail(min(lookback_days, len(daily_returns)))
        daily_vol = recent_returns.std()
        annualized_vol = daily_vol * np.sqrt(252)
        
        # 计算百分位
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
        """计算风险评估"""
        # 基于波动率的风险等级
        if annualized_vol < 0.15:
            risk_level = "low"
            base_score = 25
            if vol_percentile < 30:
                risk_score = base_score - 10
                assessment = f"低风险股票，年化波动率{annualized_vol:.1%}，当前处于历史低波动率水平"
            else:
                risk_score = base_score
                assessment = f"低风险股票，年化波动率{annualized_vol:.1%}，价格波动相对温和"
        elif annualized_vol < 0.30:
            risk_level = "medium"
            base_score = 50
            if vol_percentile > 70:
                risk_score = base_score + 15
                assessment = f"中等风险股票，年化波动率{annualized_vol:.1%}，当前波动率上升"
            else:
                risk_score = base_score
                assessment = f"中等风险股票，年化波动率{annualized_vol:.1%}，波动处于正常水平"
        elif annualized_vol < 0.50:
            risk_level = "high"
            base_score = 75
            assessment = f"高风险股票，年化波动率{annualized_vol:.1%}，价格波动较大"
        else:
            risk_level = "very_high"
            base_score = 90
            assessment = f"极高风险股票，年化波动率{annualized_vol:.1%}，价格波动极大"
        
        # 数据质量调整
        if data_points < 10:
            assessment += f"（注意：仅基于{data_points}个数据点）"
            base_score = min(base_score + 10, 100)
        
        return risk_level, max(0, min(100, base_score)), assessment

    def _calculate_volatility_adjusted_limit(self, annualized_volatility: float) -> float:
        """计算波动率调整后的仓位限制百分比"""
        base_limit = 0.35  # 35%基准
        
        if annualized_volatility < 0.15:
            vol_multiplier = 1.3  # 最多45.5% (35% * 1.3)
        elif annualized_volatility < 0.30:
            vol_multiplier = 1.1 - (annualized_volatility - 0.15) * 0.8
        elif annualized_volatility < 0.50:
            vol_multiplier = 0.8 - (annualized_volatility - 0.30) * 0.6
        else:
            vol_multiplier = 0.4  # 最多14% (35% * 0.4)
        
        vol_multiplier = max(0.4, min(1.3, vol_multiplier))
        return base_limit * vol_multiplier

    def _get_default_volatility(self) -> Dict[str, float]:
        """获取默认波动率"""
        return {
            "daily_volatility": 0.05,
            "annualized_volatility": 0.05 * np.sqrt(252),
            "volatility_percentile": 100,
            "data_points": 0
        }
    
    def _get_default_risk_config(self) -> Dict[str, Any]:
        """获取默认风险配置"""
        return {
            "volatility_thresholds": {
                "low": {"max_volatility": 0.15},
                "medium": {"min_volatility": 0.15, "max_volatility": 0.30},
                "high": {"min_volatility": 0.30, "max_volatility": 0.50},
                "very_high": {"min_volatility": 0.50}
            }
        }
    
    def _get_default_position_config(self) -> Dict[str, Any]:
        """获取默认仓位配置"""
        return {
            "base_position_limit": 0.20,
            "volatility_adjustments": {
                "low_volatility": {"max_volatility": 0.15, "multiplier": 1.25},
                "very_high_volatility": {"min_volatility": 0.50, "multiplier": 0.50}
            }
        }

