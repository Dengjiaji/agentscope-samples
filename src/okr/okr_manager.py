#!/usr/bin/env python3
"""
OKR Manager - Implements analyst reputation scoring and elimination mechanism
Reviews every 5 trading days, performs OKR evaluation and personnel adjustments every 30 trading days
"""

import json
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path

from src.tools.data_tools import get_price_data
from src.memory import reset_analyst_memory

class OKRManager:
    """OKR Manager - Handles analyst performance evaluation and elimination mechanism"""
    
    def __init__(self, analyst_ids: List[str], base_dir: str = "live_mode"):
        """
        Initialize OKR manager
        
        Args:
            analyst_ids: Analyst ID list
            base_dir: Memory system base directory
        """
        self.analyst_ids = analyst_ids.copy()
        self.base_dir = base_dir
        
        # Initialize weights (equal distribution)
        equal_weight = 1.0 / len(analyst_ids) if analyst_ids else 0.0
        self.current_weights = {aid: equal_weight for aid in analyst_ids}
        
        # Historical data
        self.weight_history = []  # Weight history snapshots
        self.signal_history = []  # Investment signal history
        self.performance_history = []  # Performance history
        
        # New hire tracking
        self.new_hires = {}  # {analyst_id: hire_date}
        
        # Configuration parameters
        self.review_interval = 5  # Review every 5 trading days
        self.okr_interval = 30   # Perform OKR evaluation every 30 trading days
        
        print(f"OKR manager initialized, managing {len(analyst_ids)} analysts")
    
    def record_daily_signals(self, date: str, analyst_signals: Dict[str, Any]) -> None:
        """
        Record daily analyst signals
        
        Args:
            date: Date string (YYYY-MM-DD)
            analyst_signals: Analyst signals dictionary
        """
        for analyst_id in self.analyst_ids:
            # Prefer round 2 signals, otherwise use round 1 signals
            round2_key = f"{analyst_id}_round2"
            signals_data = None
            
            if round2_key in analyst_signals:
                signals_data = analyst_signals[round2_key]
                round_type = "round2"
            elif analyst_id in analyst_signals:
                signals_data = analyst_signals[analyst_id]
                round_type = "round1"
            else:
                continue
            
            # Parse signal data
            ticker_signals = []
            if isinstance(signals_data, dict):
                if "ticker_signals" in signals_data:
                    # Standard format
                    ticker_signals = signals_data.get("ticker_signals", [])
                else:
                    # Old format: {ticker: {signal: ...}}
                    for ticker, signal_data in signals_data.items():
                        if isinstance(signal_data, dict) and "signal" in signal_data:
                            ticker_signals.append({
                                "ticker": ticker,
                                "signal": signal_data.get("signal"),
                                "confidence": signal_data.get("confidence", 50),
                                "reasoning": signal_data.get("reasoning", "")
                            })
            
            # Record each stock signal
            for ticker_signal in ticker_signals:
                if isinstance(ticker_signal, dict) and ticker_signal.get("ticker"):
                    self.signal_history.append({
                        "date": date,
                        "analyst_id": analyst_id,
                        "ticker": ticker_signal.get("ticker"),
                        "signal": ticker_signal.get("signal"),
                        "confidence": ticker_signal.get("confidence", 50),
                        "reasoning": ticker_signal.get("reasoning", ""),
                        "round_type": round_type,
                        "score": None  # Will be filled during scoring
                    })
    
    def score_signals_for_period(self, end_date: str, days_back: int = 5) -> None:
        """
        Score signals for specified period
        
        Args:
            end_date: End date
            days_back: Days to look back
        """
        end_dt = pd.to_datetime(end_date)
        start_dt = end_dt - pd.Timedelta(days=days_back + 10)  # Add extra days to ensure coverage
        
        # Find signals that need scoring
        signals_to_score = []
        for signal_record in self.signal_history:
            if (signal_record["score"] is None and 
                signal_record["date"] <= end_date and
                pd.to_datetime(signal_record["date"]) >= start_dt):
                signals_to_score.append(signal_record)
        
        print(f"Scoring {len(signals_to_score)} signals...")
        
        # Calculate score for each signal
        for signal_record in signals_to_score:
            score = self._calculate_signal_score(
                signal_record["ticker"], 
                signal_record["date"], 
                signal_record["signal"]
            )
            signal_record["score"] = score
            
            if score is not None:
                signal_emoji = {1: "✅", 0: "➖", -1: "❌"}
                emoji = signal_emoji.get(score, "❓")
                print(f"  {emoji} {signal_record['analyst_id']}: {signal_record['ticker']} "
                      f"({signal_record['signal']}) = {score} points")
    
    def _calculate_signal_score(self, ticker: str, signal_date: str, signal: str) -> Optional[int]:
        """
        Calculate score for a single signal
        
        Args:
            ticker: Stock ticker
            signal_date: Signal date
            signal: Signal type (bullish/bearish/neutral)
            
        Returns:
            Score: +1 (correct), 0 (neutral), -1 (incorrect), None (cannot score)
        """
        try:
            # Get price data
            start_dt = pd.to_datetime(signal_date)
            end_dt = start_dt + pd.Timedelta(days=7)  # Look forward 7 days to find next trading day
            
            df = get_price_data(ticker, start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d"))
            if df is None or df.empty:
                return None
            
            df = df.sort_index()
            dates = df.index.strftime("%Y-%m-%d").tolist()
            
            if signal_date not in dates:
                return None
            
            # Find signal date index
            signal_idx = dates.index(signal_date)
            if signal_idx + 1 >= len(dates):
                return None  # No next trading day data
            
            # Calculate price change direction
            today_close = float(df.iloc[signal_idx]["close"])
            next_close = float(df.iloc[signal_idx + 1]["close"])
            
            # Determine actual price direction
            if next_close > today_close:
                actual_direction = "bullish"
            elif next_close < today_close:
                actual_direction = "bearish"
            else:
                actual_direction = "neutral"
            
            # Calculate score
            signal_lower = (signal or "").lower()
            if signal_lower == "neutral" or actual_direction == "neutral":
                return 0
            elif signal_lower == actual_direction:
                return 1
            else:
                return -1
                
        except Exception as e:
            print(f"Warning: Failed to calculate signal score {ticker} {signal_date}: {e}")
            return None
    
    def update_weights_5day_review(self, current_date: str) -> Dict[str, float]:
        """
        Update weights based on performance in the last 5 trading days
        
        Args:
            current_date: Current date
            
        Returns:
            Updated weights dictionary
        """
        print(f"\n📊 Executing 5-day performance review ({current_date})")
        
        # First score recent signals
        self.score_signals_for_period(current_date, days_back=7)
        
        # Get scoring data for last 5 trading days
        end_dt = pd.to_datetime(current_date)
        start_dt = end_dt - pd.Timedelta(days=10)  # Add extra days to ensure coverage
        
        analyst_scores = {}
        analyst_counts = {}
        
        for analyst_id in self.analyst_ids:
            scores = []
            for signal_record in self.signal_history:
                if (signal_record["analyst_id"] == analyst_id and
                    signal_record["score"] is not None and
                    pd.to_datetime(signal_record["date"]) >= start_dt and
                    signal_record["date"] <= current_date):
                    scores.append(signal_record["score"])
            
            if scores:
                analyst_scores[analyst_id] = sum(scores) / len(scores)  # Average score
                analyst_counts[analyst_id] = len(scores)
            else:
                analyst_scores[analyst_id] = 0.0
                analyst_counts[analyst_id] = 0
        
        # Calculate new weights (map [-1,1] range to [0,2], then normalize)
        shifted_scores = {}
        for analyst_id in self.analyst_ids:
            shifted_scores[analyst_id] = analyst_scores[analyst_id] + 1.0
        
        total_shifted = sum(shifted_scores.values())
        if total_shifted > 1e-8:
            new_weights = {aid: shifted_scores[aid] / total_shifted for aid in self.analyst_ids}
        else:
            # If all scores are -1, distribute weights equally
            equal_weight = 1.0 / len(self.analyst_ids)
            new_weights = {aid: equal_weight for aid in self.analyst_ids}
        
        # Update weights
        self.current_weights = new_weights
        
        # Record weight history
        self.weight_history.append({
            "date": current_date,
            "weights": new_weights.copy(),
            "scores": analyst_scores.copy(),
            "counts": analyst_counts.copy(),
            "type": "5day_review"
        })
        
        # Print results
        print("📈 Analyst weight update results:")
        for analyst_id in self.analyst_ids:
            score = analyst_scores[analyst_id]
            weight = new_weights[analyst_id]
            count = analyst_counts[analyst_id]
            print(f"  {analyst_id}: Average score {score:.2f} ({count} signals) → Weight {weight:.3f}")
        
        return new_weights
    
    def perform_30day_okr_evaluation(self, current_date: str) -> Optional[str]:
        """
        Perform 30-day OKR evaluation, eliminate worst performing analyst
        
        Args:
            current_date: Current date
            
        Returns:
            Eliminated analyst ID, or None if no elimination
        """
        print(f"\n🎯 Executing 30-day OKR evaluation ({current_date})")
        
        # Need at least 4 weight snapshots to perform evaluation
        review_snapshots = [h for h in self.weight_history if h["type"] == "5day_review"]
        if len(review_snapshots) < 4:
            print(f"Insufficient weight snapshots ({len(review_snapshots)}/4), skipping OKR evaluation")
            return None
        
        # Calculate average of last 4 weights
        last_4_snapshots = review_snapshots[-4:]
        avg_weights = {}
        
        for analyst_id in self.analyst_ids:
            weights = []
            for snapshot in last_4_snapshots:
                if analyst_id in snapshot["weights"]:
                    weights.append(snapshot["weights"][analyst_id])
            
            if weights:
                avg_weights[analyst_id] = sum(weights) / len(weights)
            else:
                avg_weights[analyst_id] = 0.0
        
        # Find analyst with lowest average weight
        worst_analyst = min(self.analyst_ids, key=lambda x: avg_weights.get(x, 0.0))
        worst_weight = avg_weights[worst_analyst]
        
        print("📊 Last 4 weeks average weights:")
        for analyst_id in sorted(self.analyst_ids, key=lambda x: avg_weights.get(x, 0.0), reverse=True):
            weight = avg_weights[analyst_id]
            status = " (will be eliminated)" if analyst_id == worst_analyst else ""
            print(f"  {analyst_id}: {weight:.3f}{status}")
        
        # Execute elimination and reset
        try:
            # Reset analyst memory
            reset_analyst_memory(worst_analyst, self.base_dir)
            
            # Record new hire
            self.new_hires[worst_analyst] = current_date
            
            # Reset analyst's weight to average
            equal_weight = 1.0 / len(self.analyst_ids)
            self.current_weights[worst_analyst] = equal_weight
            
            print(f"🔄 Eliminated and reset analyst: {worst_analyst}")
            print(f"📝 Marked as new hire, hire date: {current_date}")
            
            # Record OKR evaluation history
            self.performance_history.append({
                "date": current_date,
                "type": "30day_okr_evaluation",
                "eliminated_analyst": worst_analyst,
                "elimination_reason": f"Lowest 30-day average weight ({worst_weight:.3f})",
                "avg_weights": avg_weights.copy(),
                "snapshots_used": len(last_4_snapshots)
            })
            
            return worst_analyst
            
        except Exception as e:
            print(f"❌ Error eliminating analyst: {e}")
            return None
    
    def get_analyst_weights_for_prompt(self) -> Dict[str, float]:
        """
        Get analyst weight information for prompts
        
        Returns:
            Current weights dictionary
        """
        return self.current_weights.copy()
    
    def format_weights_for_prompt(self) -> str:
        """
        Format weight information for portfolio manager prompts
        
        Returns:
            Formatted weight information string
        """
        if not self.current_weights:
            return "All analysts have equal weights."
        
        lines = ["📊 Analyst Weight Distribution (based on recent performance):"]
        
        # Sort by weight
        sorted_analysts = sorted(self.current_weights.items(), key=lambda x: x[1], reverse=True)
        
        for analyst_id, weight in sorted_analysts:
            # Check if new hire
            new_hire_info = ""
            if analyst_id in self.new_hires:
                days_since_hire = (pd.to_datetime(datetime.now().date()) - 
                                 pd.to_datetime(self.new_hires[analyst_id])).days
                if days_since_hire <= 30:
                    new_hire_info = f" (New hire, {days_since_hire} days)"
            
            # Weight bar chart
            bar_length = int(weight * 20)  # Max 20 characters
            bar = "█" * bar_length + "░" * (20 - bar_length)
            
            lines.append(f"  {analyst_id}: {weight:.3f} {bar}{new_hire_info}")
        
        lines.append("")
        lines.append("💡 Analysts with higher weights should be given more consideration.")
        
        return "\n".join(lines)
    
    def get_okr_summary(self) -> Dict[str, Any]:
        """
        Get OKR system operation summary
        
        Returns:
            OKR summary information
        """
        # Count signals
        total_signals = len(self.signal_history)
        scored_signals = len([s for s in self.signal_history if s["score"] is not None])
        
        # Statistics for each analyst
        analyst_stats = {}
        for analyst_id in self.analyst_ids:
            analyst_signals = [s for s in self.signal_history if s["analyst_id"] == analyst_id and s["score"] is not None]
            if analyst_signals:
                scores = [s["score"] for s in analyst_signals]
                analyst_stats[analyst_id] = {
                    "total_signals": len(analyst_signals),
                    "avg_score": sum(scores) / len(scores),
                    "correct_signals": len([s for s in scores if s == 1]),
                    "neutral_signals": len([s for s in scores if s == 0]),
                    "wrong_signals": len([s for s in scores if s == -1]),
                    "current_weight": self.current_weights.get(analyst_id, 0.0),
                    "is_new_hire": analyst_id in self.new_hires
                }
            else:
                analyst_stats[analyst_id] = {
                    "total_signals": 0,
                    "avg_score": 0.0,
                    "correct_signals": 0,
                    "neutral_signals": 0,
                    "wrong_signals": 0,
                    "current_weight": self.current_weights.get(analyst_id, 0.0),
                    "is_new_hire": analyst_id in self.new_hires
                }
        
        return {
            "total_analysts": len(self.analyst_ids),
            "total_signals": total_signals,
            "scored_signals": scored_signals,
            "weight_updates": len([h for h in self.weight_history if h["type"] == "5day_review"]),
            "okr_evaluations": len(self.performance_history),
            "new_hires": len(self.new_hires),
            "analyst_stats": analyst_stats,
            "current_weights": self.current_weights.copy()
        }
    
    def export_okr_data(self) -> Dict[str, Any]:
        """
        Export complete OKR data
        
        Returns:
            Complete OKR data dictionary
        """
        return {
            "analyst_ids": self.analyst_ids.copy(),
            "current_weights": self.current_weights.copy(),
            "weight_history": self.weight_history.copy(),
            "signal_history": self.signal_history.copy(),
            "performance_history": self.performance_history.copy(),
            "new_hires": self.new_hires.copy(),
            "config": {
                "review_interval": self.review_interval,
                "okr_interval": self.okr_interval,
                "base_dir": self.base_dir
            },
            "export_timestamp": datetime.now().isoformat()
        }
    
    def import_okr_data(self, data: Dict[str, Any]) -> None:
        """
        Import OKR data (for state recovery)
        
        Args:
            data: Data exported from export_okr_data
        """
        self.analyst_ids = data.get("analyst_ids", [])
        self.current_weights = data.get("current_weights", {})
        self.weight_history = data.get("weight_history", [])
        self.signal_history = data.get("signal_history", [])
        self.performance_history = data.get("performance_history", [])
        self.new_hires = data.get("new_hires", {})
        
        # Import configuration
        config = data.get("config", {})
        self.review_interval = config.get("review_interval", 5)
        self.okr_interval = config.get("okr_interval", 30)
        self.base_dir = config.get("base_dir", "live_mode")
        
        print(f"OKR data import completed: {len(self.analyst_ids)} analysts, "
              f"{len(self.signal_history)} signal records")
