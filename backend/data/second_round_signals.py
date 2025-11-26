#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Data models for second-round analysis
Used for LLM-based investment signal generation
"""

from pydantic import BaseModel, Field
from typing import Literal, Dict, Any, List
from datetime import datetime


class TickerSignal(BaseModel):
    """Investment signal for a single stock"""

    ticker: str = Field(..., description="Stock ticker symbol")
    signal: Literal["bullish", "bearish", "neutral"] = Field(
        ...,
        description="Investment signal",
    )
    confidence: int = Field(
        ...,
        ge=0,
        le=100,
        description="Confidence level (0-100)",
    )
    reasoning: str = Field(..., description="Reasoning for the judgment")


class SecondRoundAnalysis(BaseModel):
    """Second round analysis results"""

    analyst_id: str = Field(..., description="Analyst ID")
    analyst_name: str = Field(..., description="Analyst name")
    ticker_signals: List[TickerSignal] = Field(
        ...,
        description="Investment signals for each stock",
    )
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Analysis timestamp",
    )


class AnalystPersona(BaseModel):
    """Analyst persona configuration"""

    name: str = Field(..., description="Analyst name")
    specialty: str = Field(..., description="Professional specialty")
    analysis_focus: List[str] = Field(..., description="Analysis focus areas")
    decision_style: str = Field(..., description="Decision making style")
    risk_preference: str = Field(..., description="Risk preference")
