#!/usr/bin/env python3
"""
第二轮分析的数据模型
用于LLM-based的投资信号生成
"""

from pydantic import BaseModel, Field
from typing import Literal, Dict, Any, List
from datetime import datetime


class TickerSignal(BaseModel):
    """单个股票的投资信号"""
    ticker: str = Field(..., description="股票代码")
    signal: Literal["bullish", "bearish", "neutral"] = Field(..., description="投资信号")
    confidence: int = Field(..., ge=0, le=100, description="信心度 (0-100)")
    reasoning: str = Field(..., description="做出判断的原因")


class SecondRoundAnalysis(BaseModel):
    """第二轮分析结果"""
    analyst_id: str = Field(..., description="分析师ID")
    analyst_name: str = Field(..., description="分析师名称")
    ticker_signals: List[TickerSignal] = Field(..., description="各股票的投资信号")
    timestamp: datetime = Field(default_factory=datetime.now, description="分析时间")


class AnalystPersona(BaseModel):
    """分析师人格设定"""
    name: str = Field(..., description="分析师名称")
    specialty: str = Field(..., description="专业领域")
    analysis_focus: List[str] = Field(..., description="分析重点")
    decision_style: str = Field(..., description="决策风格")
    risk_preference: str = Field(..., description="风险偏好")
    pipeline_config: str = Field(..., description="专属pipeline配置")