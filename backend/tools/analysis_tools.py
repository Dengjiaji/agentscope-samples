"""
Unified analysis tools collection
Contains all tools for fundamental analysis, technical analysis, sentiment analysis, and valuation analysis
"""

from typing import Dict, Any, List, Optional, Tuple

import pandas as pd
import numpy as np
import json
from datetime import datetime
from statistics import median
import math

from backend.tools.data_tools import (
    get_financial_metrics, 
    get_prices, 
    get_insider_trades, 
    get_company_news,
    prices_to_df,
    get_market_cap,
    search_line_items,
)

# Define a simple decorator for compatibility
def tool(func):
    """Compatibility decorator - marks function as a tool function"""
    func._is_tool = True
    return func

# ===================== Tool Helper Functions =====================

def safe_float(value, default=0.0):
    """Safely convert to float"""
    try:
        if pd.isna(value) or np.isnan(value):
            return default
        return float(value)
    except (ValueError, TypeError, OverflowError):
        return default


def normalize_pandas(data):
    """Normalize pandas data to serializable format"""
    if isinstance(data, dict):
        return {key: safe_float(value) for key, value in data.items()}
    elif hasattr(data, 'to_dict'):
        return {key: safe_float(value) for key, value in data.to_dict().items()}
    else:
        return safe_float(data)

# ===================== Fundamental Analysis Tools =====================
@tool
def analyze_efficiency_ratios(ticker: str, end_date: str, api_key: str) -> Dict[str, Any]:
    """Efficiency ratio analysis - analyze company asset utilization efficiency"""
    try:
        financial_metrics = get_financial_metrics(ticker=ticker, end_date=end_date, period="ttm", limit=10, api_key=api_key)
        if not financial_metrics:
            return {"error": "No financial metrics found"}
        
        metrics = financial_metrics[0]
        
        # Efficiency metrics
        asset_turnover = metrics.asset_turnover
        inventory_turnover = metrics.inventory_turnover
        receivables_turnover = metrics.receivables_turnover
        working_capital_turnover = metrics.working_capital_turnover
        
       
        
        return {
            "metrics": {
                "asset_turnover": asset_turnover,
                "inventory_turnover": inventory_turnover,
                "receivables_turnover": receivables_turnover,
                "working_capital_turnover": working_capital_turnover
            },
            "reasoning": f"Efficiency analysis"
        }
    except Exception as e:
        return {"error": str(e)}

@tool
def analyze_profitability(ticker: str, end_date: str, api_key: str) -> Dict[str, Any]:
    """
    Analyze company profitability
    
    Args:
        ticker: Stock ticker
        end_date: End date
        api_key: API key
        
    Returns:
        Dictionary containing profitability analysis results
    """
    try:
        # Get financial metrics
        financial_metrics = get_financial_metrics(
            ticker=ticker,
            end_date=end_date,
            period="ttm",
            limit=10,
            api_key=api_key,
        )
        
        if not financial_metrics:
            return {"error": "No financial metrics found"}
        
        metrics = financial_metrics[0]
        
        # Profitability metrics
        return_on_equity = metrics.return_on_equity
        net_margin = metrics.net_margin
        operating_margin = metrics.operating_margin

        return {
            "metrics": {
                "return_on_equity": return_on_equity,
                "net_margin": net_margin,
                "operating_margin": operating_margin
            },
            "reasoning": f"Profitability analysis"
        }
        
    except Exception as e:
        return {"error": str(e)}


@tool
def analyze_growth(ticker: str, end_date: str, api_key: str) -> Dict[str, Any]:
    """
    Analyze company growth
    
    Args:
        ticker: Stock ticker
        end_date: End date
        api_key: API key
        
    Returns:
        Dictionary containing growth analysis results
    """
    try:
        financial_metrics = get_financial_metrics(
            ticker=ticker,
            end_date=end_date,
            period="ttm", 
            limit=10,
            api_key=api_key,
        )
        
        if not financial_metrics:
            return {"error": "No financial metrics found"}
        
        metrics = financial_metrics[0]
        
        # Growth metrics
        revenue_growth = metrics.revenue_growth
        earnings_growth = metrics.earnings_growth
        book_value_growth = metrics.book_value_growth
        
        
        
        return {
            "metrics": {
                "revenue_growth": revenue_growth,
                "earnings_growth": earnings_growth,
                "book_value_growth": book_value_growth
            },
            "reasoning": f"Growth analysis"
        }
        
    except Exception as e:
        return {"error": str(e)}


@tool  
def analyze_financial_health(ticker: str, end_date: str, api_key: str) -> Dict[str, Any]:
    """
    Analyze company financial health
    
    Args:
        ticker: Stock ticker
        end_date: End date
        api_key: API key
        
    Returns:
        Dictionary containing financial health analysis results
    """
    try:
        financial_metrics = get_financial_metrics(
            ticker=ticker,
            end_date=end_date,
            period="ttm",
            limit=10,
            api_key=api_key,
        )
        
        if not financial_metrics:
            return {"error": "No financial metrics found"}
        
        metrics = financial_metrics[0]
        
        # Financial health metrics
        current_ratio = metrics.current_ratio
        debt_to_equity = metrics.debt_to_equity
        free_cash_flow_per_share = metrics.free_cash_flow_per_share
        earnings_per_share = metrics.earnings_per_share
        
        
            
        
        return {
            "metrics": {
                "current_ratio": current_ratio,
                "debt_to_equity": debt_to_equity,
                "free_cash_flow_per_share": free_cash_flow_per_share,
                "earnings_per_share": earnings_per_share
            },
            "reasoning": f"Financial health analysis"
        }
        
    except Exception as e:
        return {"error": str(e)}


@tool
def analyze_valuation_ratios(ticker: str, end_date: str, api_key: str) -> Dict[str, Any]:
    """
    Analyze valuation ratios
    
    Args:
        ticker: Stock ticker
        end_date: End date
        api_key: API key
        
    Returns:
        Dictionary containing valuation ratio analysis results
    """
    try:
        financial_metrics = get_financial_metrics(
            ticker=ticker,
            end_date=end_date,
            period="ttm",
            limit=10,
            api_key=api_key,
        )
        
        if not financial_metrics:
            return {"error": "No financial metrics found"}
        
        metrics = financial_metrics[0]
        
        # Valuation ratio metrics
        pe_ratio = metrics.price_to_earnings_ratio
        pb_ratio = metrics.price_to_book_ratio
        ps_ratio = metrics.price_to_sales_ratio
        
        
        return {
            "metrics": {
                "pe_ratio": pe_ratio,
                "pb_ratio": pb_ratio,
                "ps_ratio": ps_ratio
            },
            "reasoning": f"Valuation ratio analysis"
        }
        
    except Exception as e:
        return {"error": str(e)}


# ===================== Technical Analysis Tools =====================

@tool
def analyze_trend_following(ticker: str, start_date: str, end_date: str, api_key: str) -> Dict[str, Any]:
    """
    Trend following analysis
    
    Args:
        ticker: Stock ticker
        start_date: Start date
        end_date: End date
        api_key: API key
        
    Returns:
        Dictionary containing trend following analysis results
    """
    try:
        # Automatically extend historical data range to meet technical analysis needs
        from datetime import datetime, timedelta
        
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        # Extend to 250 days ago to ensure sufficient data for 200-day MA
        extended_start_date = (end_dt - timedelta(days=250)).strftime("%Y-%m-%d")
        
        # Get extended price data
        prices = get_prices(ticker=ticker, start_date=extended_start_date, end_date=end_date, api_key=api_key)
        
        if not prices:
            return {"error": "No price data found"}
        
        prices_df = prices_to_df(prices)
        
        # Lower minimum data requirements but provide better error messages
        if len(prices_df) < 10:
            return {
                "error": f"Insufficient data for trend analysis: only {len(prices_df)} days available, need at least 10", 
                "data_range": f"Attempted to fetch data from {extended_start_date} to {end_date}"
            }
        elif len(prices_df) < 20:
            # If data is less than 20 days but more than 10 days, downgrade but continue analysis
            print(f"Warning: Insufficient data for trend analysis, only {len(prices_df)} days available, recommend at least 20 days")
        
        # Calculate moving averages - adjust windows based on data length
        data_length = len(prices_df)
        sma_short_window = min(20, data_length // 2)
        sma_long_window = min(50, data_length - 5) if data_length > 25 else min(25, data_length - 5)
        sma_200_window = min(200, data_length - 10) if data_length > 200 else None
        
        prices_df['SMA_20'] = prices_df['close'].rolling(window=sma_short_window).mean()
        prices_df['SMA_50'] = prices_df['close'].rolling(window=sma_long_window).mean()
        if sma_200_window:
            prices_df['SMA_200'] = prices_df['close'].rolling(window=sma_200_window).mean()
        prices_df['EMA_12'] = prices_df['close'].ewm(span=min(12, data_length // 3)).mean()
        prices_df['EMA_26'] = prices_df['close'].ewm(span=min(26, data_length // 2)).mean()
        
        # MACD
        prices_df['MACD'] = prices_df['EMA_12'] - prices_df['EMA_26']
        prices_df['MACD_signal'] = prices_df['MACD'].ewm(span=9).mean()
        prices_df['MACD_histogram'] = prices_df['MACD'] - prices_df['MACD_signal']
        
        # Get latest values
        current_price = safe_float(prices_df['close'].iloc[-1])
        sma_20 = safe_float(prices_df['SMA_20'].iloc[-1])
        sma_50 = safe_float(prices_df['SMA_50'].iloc[-1])
        sma_200 = safe_float(prices_df['SMA_200'].iloc[-1]) if 'SMA_200' in prices_df.columns else None
        macd = safe_float(prices_df['MACD'].iloc[-1])
        macd_signal = safe_float(prices_df['MACD_signal'].iloc[-1])
        macd_histogram = safe_float(prices_df['MACD_histogram'].iloc[-1])
        
        
        
        # 3. Short-term trend
        recent_prices = prices_df['close'].tail(5).values
       
        long_term_trend = None
        
        distance_from_200ma_pct = None
        
        if sma_200 is not None:
            long_term_trend = "bullish" if current_price > sma_200 else "bearish"
            distance_from_200ma_pct = ((current_price - sma_200) / sma_200) * 100
       
        return {
            "metrics": {
                "current_price": current_price,
                "sma_20": sma_20,
                "sma_50": sma_50,
                "sma_200": sma_200,
                "macd": macd,
                "macd_signal": macd_signal,
                "macd_histogram": macd_histogram,
                "trend_slope": safe_float(np.polyfit(range(len(recent_prices)), recent_prices, 1)[0] if len(recent_prices) >= 5 else 0),
                "distance_from_200ma_pct": distance_from_200ma_pct
            },
            "long_term_trend": long_term_trend,
            "reasoning": f"Trend following analysis"
        }
        
    except Exception as e:
        return {"error": str(e)}


@tool
def analyze_mean_reversion(ticker: str, start_date: str, end_date: str, api_key: str) -> Dict[str, Any]:
    """
    Mean reversion analysis
    
    Args:
        ticker: Stock ticker
        start_date: Start date
        end_date: End date
        api_key: API key
        
    Returns:
        Dictionary containing mean reversion analysis results
    """
    try:
        # Automatically extend historical data range to meet technical analysis needs
        from datetime import datetime, timedelta
        
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        # Extend to 60 days ago to ensure sufficient historical data
        extended_start_date = (end_dt - timedelta(days=60)).strftime("%Y-%m-%d")
        
        prices = get_prices(ticker=ticker, start_date=extended_start_date, end_date=end_date, api_key=api_key)
        
        if not prices:
            return {"error": "No price data found"}
        
        prices_df = prices_to_df(prices)
        
        if len(prices_df) < 5:
            return {
                "error": f"Insufficient data for mean reversion analysis: only {len(prices_df)} days available, need at least 5", 
                "data_range": f"Attempted to fetch data from {extended_start_date} to {end_date}"
            }
        elif len(prices_df) < 20:
            print(f"Warning: Insufficient data for mean reversion analysis, only {len(prices_df)} days available, recommend at least 20 days")
        
        # Calculate Bollinger Bands - adjust window based on data length
        window = min(20, len(prices_df) - 2)
        prices_df['SMA'] = prices_df['close'].rolling(window=window).mean()
        prices_df['STD'] = prices_df['close'].rolling(window=window).std()
        prices_df['Upper_Band'] = prices_df['SMA'] + (2 * prices_df['STD'])
        prices_df['Lower_Band'] = prices_df['SMA'] - (2 * prices_df['STD'])
        
        # RSI calculation
        delta = prices_df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        prices_df['RSI'] = 100 - (100 / (1 + rs))
        
        # Get latest values
        current_price = safe_float(prices_df['close'].iloc[-1])
        sma = safe_float(prices_df['SMA'].iloc[-1])
        upper_band = safe_float(prices_df['Upper_Band'].iloc[-1])
        lower_band = safe_float(prices_df['Lower_Band'].iloc[-1])
        rsi = safe_float(prices_df['RSI'].iloc[-1])
        
        
        # 3. Price deviation
        price_deviation = (current_price - sma) / sma * 100
        
        return {
            "metrics": {
                "current_price": current_price,
                "sma": sma,
                "upper_band": upper_band,
                "lower_band": lower_band,
                "rsi": rsi,
                "price_deviation_pct": round(price_deviation, 2)
            },
            "reasoning": f"Mean reversion analysis"
        }
        
    except Exception as e:
        return {"error": str(e)}


@tool
def analyze_momentum(ticker: str, start_date: str, end_date: str, api_key: str) -> Dict[str, Any]:
    """
    Momentum analysis
    
    Args:
        ticker: Stock ticker
        start_date: Start date
        end_date: End date
        api_key: API key
        
    Returns:
        Dictionary containing momentum analysis results
    """
    try:
        # Automatically extend historical data range to meet technical analysis needs
        from datetime import datetime, timedelta
        
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        # Extend to 45 days ago to ensure sufficient historical data
        extended_start_date = (end_dt - timedelta(days=45)).strftime("%Y-%m-%d")
        
        prices = get_prices(ticker=ticker, start_date=extended_start_date, end_date=end_date, api_key=api_key)
        
        if not prices:
            return {"error": "No price data found"}
        
        prices_df = prices_to_df(prices)
        
        if len(prices_df) < 5:
            return {
                "error": f"Insufficient data for momentum analysis: only {len(prices_df)} days available, need at least 5", 
                "data_range": f"Attempted to fetch data from {extended_start_date} to {end_date}"
            }
        elif len(prices_df) < 20:
            print(f"Warning: Insufficient data for momentum analysis, only {len(prices_df)} days available, recommend at least 20 days")
        
        # Calculate returns
        prices_df['returns'] = prices_df['close'].pct_change()
        
        # Calculate momentum for different periods - adjust based on data length
        data_length = len(prices_df)
        short_period = min(5, data_length // 3)
        medium_period = min(10, data_length // 2)
        long_period = min(20, data_length - 2)
        
        prices_df['momentum_5'] = prices_df['close'] / prices_df['close'].shift(short_period) - 1
        prices_df['momentum_10'] = prices_df['close'] / prices_df['close'].shift(medium_period) - 1
        prices_df['momentum_20'] = prices_df['close'] / prices_df['close'].shift(long_period) - 1
        
        # Get latest values
        current_price = safe_float(prices_df['close'].iloc[-1])
        momentum_5 = safe_float(prices_df['momentum_5'].iloc[-1])
        momentum_10 = safe_float(prices_df['momentum_10'].iloc[-1])
        momentum_20 = safe_float(prices_df['momentum_20'].iloc[-1])
        
        # Calculate recent volatility
        recent_volatility = safe_float(prices_df['returns'].tail(20).std() * np.sqrt(252))
       
            
        
        return {
            "metrics": {
                "current_price": current_price,
                "momentum_5d_pct": round(momentum_5 * 100, 2),
                "momentum_10d_pct": round(momentum_10 * 100, 2),
                "momentum_20d_pct": round(momentum_20 * 100, 2),
                "recent_volatility": round(recent_volatility * 100, 2)
            },
            "reasoning": f"Momentum analysis"
        }
        
    except Exception as e:
        return {"error": str(e)}


@tool
def analyze_volatility(ticker: str, start_date: str, end_date: str, api_key: str) -> Dict[str, Any]:
    """
    Volatility analysis
    
    Args:
        ticker: Stock ticker
        start_date: Start date
        end_date: End date
        api_key: API key
        
    Returns:
        Dictionary containing volatility analysis results
    """
    try:
        # Automatically extend historical data range to meet technical analysis needs
        from datetime import datetime, timedelta
        
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        # Extend to 90 days ago to ensure sufficient historical data for volatility calculation
        extended_start_date = (end_dt - timedelta(days=90)).strftime("%Y-%m-%d")
        
        prices = get_prices(ticker=ticker, start_date=extended_start_date, end_date=end_date, api_key=api_key)
        
        if not prices:
            return {"error": "No price data found"}
        
        prices_df = prices_to_df(prices)
        
        if len(prices_df) < 5:
            return {
                "error": f"Insufficient data for volatility analysis: only {len(prices_df)} days available, need at least 5", 
                "data_range": f"Attempted to fetch data from {extended_start_date} to {end_date}"
            }
        elif len(prices_df) < 20:
            print(f"Warning: Insufficient data for volatility analysis, only {len(prices_df)} days available, recommend at least 20 days")
        
        # Calculate returns
        prices_df['returns'] = prices_df['close'].pct_change()
        
        # Calculate volatility for different windows - adjust based on data length
        data_length = len(prices_df)
        short_window = min(10, data_length // 2)
        medium_window = min(20, data_length - 2)
        long_window = min(60, data_length - 1) if data_length > 30 else medium_window
        
        prices_df['vol_10'] = prices_df['returns'].rolling(window=short_window).std() * np.sqrt(252)
        prices_df['vol_20'] = prices_df['returns'].rolling(window=medium_window).std() * np.sqrt(252)
        prices_df['vol_60'] = prices_df['returns'].rolling(window=long_window).std() * np.sqrt(252)
        
        # Get latest values
        current_vol_10 = safe_float(prices_df['vol_10'].iloc[-1])
        current_vol_20 = safe_float(prices_df['vol_20'].iloc[-1])
        current_vol_60 = safe_float(prices_df['vol_60'].iloc[-1])
        current_price = safe_float(prices_df['close'].iloc[-1])
        
        # Calculate volatility percentile
        vol_20_percentile = (prices_df['vol_20'].rank(pct=True).iloc[-1]) * 100
        
            
        
        return {
            "metrics": {
                "current_price": current_price,
                "volatility_10d": round(current_vol_10 * 100, 2),
                "volatility_20d": round(current_vol_20 * 100, 2),
                "volatility_60d": round(current_vol_60 * 100, 2),
                "volatility_percentile": round(vol_20_percentile, 1)
            },
            "reasoning": f"Volatility analysis"
        }
        
    except Exception as e:
        return {"error": str(e)}


# ===================== Sentiment Analysis Tools =====================

@tool
def analyze_insider_trading(ticker: str, end_date: str, api_key: str, start_date: Optional[str] = None) -> Dict[str, Any]:
    """
    Analyze insider trading activity
    
    Args:
        ticker: Stock ticker
        end_date: End date
        api_key: API key
        start_date: Start date (optional)
        
    Returns:
        Dictionary containing insider trading analysis results
    """
    try:
        # Get insider trading data
        insider_trades = get_insider_trades(
            ticker=ticker,
            end_date=end_date,
            start_date=start_date,
            limit=1000,
            api_key=api_key,
        )
        
        if not insider_trades:
            # When no insider trading data, return neutral signal instead of error
            return {
                "metrics": {
                    "total_trades": 0,
                    "buy_trades": 0,
                    "sell_trades": 0,
                    "total_buy_volume": 0,
                    "total_sell_volume": 0,
                    "trade_ratio": 0,
                    "volume_ratio": 0
                },
                "reasoning": "Insider trading analysis: No trading data"
            }
        
        # Analyze trading signals
        transaction_shares = pd.Series([t.transaction_shares for t in insider_trades]).dropna()
        
        if len(transaction_shares) == 0:
            return {
                "metrics": {
                    "total_trades": len(insider_trades),
                    "buy_trades": 0,
                    "sell_trades": 0,
                    "total_buy_volume": 0,
                    "total_sell_volume": 0,
                    "trade_ratio": 0,
                    "volume_ratio": 0
                },  
                "reasoning": "Insider trading analysis: Trading data invalid"
            }
        
        # Buy (positive) and sell (negative) statistics
        buy_trades = int((transaction_shares > 0).sum())
        sell_trades = int((transaction_shares < 0).sum())
        total_trades = len(transaction_shares)
        
        # Weighted by trading volume
        total_buy_volume = transaction_shares[transaction_shares > 0].sum()
        total_sell_volume = abs(transaction_shares[transaction_shares < 0].sum())
        
            
        return {
            "metrics": {
                "total_trades": total_trades,
                "buy_trades": buy_trades,
                "sell_trades": sell_trades,
                "total_buy_volume": float(total_buy_volume),
                "total_sell_volume": float(total_sell_volume),
                "trade_ratio": round(buy_trades / max(sell_trades, 1), 2),
                "volume_ratio": round(total_buy_volume / max(total_sell_volume, 1), 2)
            },
            "reasoning": f"Insider trading analysis"
        }
        
    except Exception as e:
        return {"error": str(e)}


@tool
def analyze_news_sentiment(ticker: str, end_date: str, api_key: str, start_date: Optional[str] = None) -> Dict[str, Any]:
    """
    Analyze news sentiment
    
    Returns different formats based on API used:
    - Finnhub API: Returns raw data of latest 10 news articles (title, source, date, link)
    - Financial Datasets API: Returns sentiment statistics
    
    Args:
        ticker: Stock ticker
        end_date: End date
        api_key: API key
        start_date: Start date (optional)
        
    Returns:
        Dictionary containing news sentiment analysis results
    """
    try:
        # Get company news
        company_news = get_company_news(
            ticker=ticker,
            end_date=end_date,
            start_date=start_date,
            limit=100,
            api_key=api_key
        )
        
        if not company_news:
            # When no news data, return neutral signal instead of error
            return {
                "metrics": {
                    "total_articles": 0,
                    "positive_articles": 0,
                    "negative_articles": 0,
                    "neutral_articles": 0,
                    "positive_ratio": 0,
                    "negative_ratio": 0,
                    "neutral_ratio": 0
                },
                "reasoning": "News sentiment analysis: No news data"
            }
        
        # Check if sentiment data exists (determine which API is being used)
        sentiment_data = pd.Series([n.sentiment for n in company_news]).dropna()
        
        # If no sentiment data, using Finnhub API
        # Return raw data of latest 10 news articles for LLM analysis
        if len(sentiment_data) == 0:
            # Get latest 10 news articles
            recent_news = company_news[:10]
            
            news_list = []
            for idx, news in enumerate(recent_news, 1):
                news_list.append({
                    "index": idx,
                    "title": news.title,
                    "source": news.source,
                    "date": news.date,
                    "url": news.url
                })
            
            return {
                "data_source": "finnhub",
                "total_news_count": len(company_news),
                "news_list": news_list,
                "reasoning": "News data analysis: Using Finnhub API, returning raw news data for LLM sentiment analysis"
            }
        
       
  
    except Exception as e:
        return {"error": str(e)}


# ===================== Valuation Analysis Tools =====================

@tool
def dcf_valuation_analysis(ticker: str, end_date: str, api_key: str) -> Dict[str, Any]:
    """
    Discounted Cash Flow (DCF) valuation analysis
    
    Args:
        ticker: Stock ticker
        end_date: End date
        api_key: API key
        
    Returns:
        Dictionary containing DCF valuation analysis results
    """
    try:
        # Get financial metrics
        financial_metrics = get_financial_metrics(
            ticker=ticker,
            end_date=end_date,
            period="ttm",
            limit=8,
            api_key=api_key,
        )
        
        if not financial_metrics:
            return {"error": "No financial metrics found"}
        
        most_recent = financial_metrics[0]
        
        # Get cash flow data
        line_items = search_line_items(
            ticker=ticker,
            line_items=["free_cash_flow"],
            end_date=end_date,
            period="ttm",
            limit=2,
            api_key=api_key,
        )
        
        if not line_items:
            return {"error": "No cash flow data found"}
        
        current_fcf = line_items[0].free_cash_flow
        if not current_fcf or current_fcf <= 0:
            return {"error": "Invalid free cash flow data"}
        
        # Get market cap
        market_cap = get_market_cap(ticker, end_date, api_key=api_key)
        if not market_cap:
            return {"error": "Market cap unavailable"}
        
        # DCF valuation calculation
        growth_rate = most_recent.earnings_growth or 0.05
        discount_rate = 0.10
        terminal_growth_rate = 0.03
        num_years = 5
        
        # Calculate present value of future cash flows
        pv_fcf = 0.0
        for year in range(1, num_years + 1):
            future_fcf = current_fcf * (1 + growth_rate) ** year
            pv_fcf += future_fcf / (1 + discount_rate) ** year
        
        # Calculate terminal value
        terminal_fcf = current_fcf * (1 + growth_rate) ** num_years * (1 + terminal_growth_rate)
        terminal_value = terminal_fcf / (discount_rate - terminal_growth_rate)
        pv_terminal = terminal_value / (1 + discount_rate) ** num_years
        
        # Enterprise value
        enterprise_value = pv_fcf + pv_terminal
        
        # Calculate value gap
        value_gap = (enterprise_value - market_cap) / market_cap
        
        
        return {
            "valuation": {
                "enterprise_value": enterprise_value,
                "market_cap": market_cap,
                "value_gap_pct": round(value_gap * 100, 2),
                "current_free_cash_flow": current_fcf,
                "growth_rate": growth_rate,
                "discount_rate": discount_rate
            },
            "reasoning": f"DCF valuation analysis"
        }
        
    except Exception as e:
        return {"error": str(e)}


@tool
def owner_earnings_valuation_analysis(ticker: str, end_date: str, api_key: str) -> Dict[str, Any]:
    """
    Buffett-style owner earnings valuation analysis
    
    Args:
        ticker: Stock ticker
        end_date: End date
        api_key: API key
        
    Returns:
        Dictionary containing owner earnings valuation analysis results
    """
    try:
        # Get financial metrics
        financial_metrics = get_financial_metrics(
            ticker=ticker,
            end_date=end_date,
            period="ttm",
            limit=8,
            api_key=api_key,
        )
        
        if not financial_metrics:
            return {"error": "No financial metrics found"}
        
        most_recent = financial_metrics[0]
        
        # Get detailed financial data
        line_items = search_line_items(
            ticker=ticker,
            line_items=[
                "net_income",
                "depreciation_and_amortization", 
                "capital_expenditure",
                "working_capital",
            ],
            end_date=end_date,
            period="ttm",
            limit=2,
            api_key=api_key,
        )
        
        if len(line_items) < 2:
            return {"error": "Insufficient financial data"}
        
        current, previous = line_items[0], line_items[1]
        
        # Calculate owner earnings
        net_income = current.net_income or 0
        depreciation = current.depreciation_and_amortization or 0
        capex = current.capital_expenditure or 0
        wc_change = (current.working_capital or 0) - (previous.working_capital or 0)
        
        owner_earnings = net_income + depreciation - capex - wc_change
        
        if owner_earnings <= 0:
            return {"error": "Negative owner earnings"}
        
        # Get market cap
        market_cap = get_market_cap(ticker, end_date, api_key=api_key)
        if not market_cap:
            return {"error": "Market cap unavailable"}
        
        # Valuation calculation
        growth_rate = most_recent.earnings_growth or 0.05
        required_return = 0.15
        margin_of_safety = 0.25
        num_years = 5
        
        # Calculate present value of future owner earnings
        pv_earnings = 0.0
        for year in range(1, num_years + 1):
            future_earnings = owner_earnings * (1 + growth_rate) ** year
            pv_earnings += future_earnings / (1 + required_return) ** year
        
        # Terminal value calculation
        terminal_growth = min(growth_rate, 0.03)
        terminal_earnings = owner_earnings * (1 + growth_rate) ** num_years * (1 + terminal_growth)
        terminal_value = terminal_earnings / (required_return - terminal_growth)
        pv_terminal = terminal_value / (1 + required_return) ** num_years
        
        # Intrinsic value (with margin of safety)
        intrinsic_value = (pv_earnings + pv_terminal) * (1 - margin_of_safety)
        
        # Value gap
        value_gap = (intrinsic_value - market_cap) / market_cap
        
        
        return {
            "valuation": {
                "intrinsic_value": intrinsic_value,
                "market_cap": market_cap,
                "value_gap_pct": round(value_gap * 100, 2),
                "owner_earnings": owner_earnings,
                "growth_rate": growth_rate,
                "required_return": required_return,
                "margin_of_safety": margin_of_safety,
                "net_income": net_income,
                "depreciation": depreciation,
                "capex": capex,
                "wc_change": wc_change
            },
           
            "reasoning": f"Owner earnings valuation analysis"
        }
        
    except Exception as e:
        return {"error": str(e)}


@tool  
def ev_ebitda_valuation_analysis(ticker: str, end_date: str, api_key: str) -> Dict[str, Any]:
    """
    EV/EBITDA multiple valuation analysis
    
    Args:
        ticker: Stock ticker
        end_date: End date
        api_key: API key
        
    Returns:
        Dictionary containing EV/EBITDA valuation analysis results
    """
    try:
        # Get financial metrics
        financial_metrics = get_financial_metrics(
            ticker=ticker,
            end_date=end_date,
            period="ttm",
            limit=8,
            api_key=api_key,
        )
        
        if not financial_metrics:
            return {"error": "No financial metrics found"}
        
        most_recent = financial_metrics[0]
        
        # Check required data
        if not (most_recent.enterprise_value and most_recent.enterprise_value_to_ebitda_ratio):
            return {"error": "Missing EV/EBITDA data"}
        
        if most_recent.enterprise_value_to_ebitda_ratio <= 0:
            return {"error": "Invalid EV/EBITDA ratio"}
        
        # Get market cap
        market_cap = get_market_cap(ticker, end_date, api_key=api_key)
        if not market_cap:
            return {"error": "Market cap unavailable"}
        
        # Calculate current EBITDA
        current_ebitda = most_recent.enterprise_value / most_recent.enterprise_value_to_ebitda_ratio
        
        # Calculate historical median multiple
        valid_multiples = [
            m.enterprise_value_to_ebitda_ratio 
            for m in financial_metrics 
            if m.enterprise_value_to_ebitda_ratio and m.enterprise_value_to_ebitda_ratio > 0
        ]
        
        if len(valid_multiples) < 3:
            return {"error": "Insufficient historical data"}
        
        median_multiple = median(valid_multiples)
        current_multiple = most_recent.enterprise_value_to_ebitda_ratio
        
        # Implied enterprise value based on median multiple
        implied_ev = median_multiple * current_ebitda
        
        # Calculate net debt
        net_debt = (most_recent.enterprise_value or 0) - (market_cap or 0)
        
        # Implied equity value
        implied_equity_value = max(implied_ev - net_debt, 0)
        
        # Value gap
        value_gap = (implied_equity_value - market_cap) / market_cap if market_cap > 0 else 0
        
        # Multiple comparison
        multiple_discount = (median_multiple - current_multiple) / median_multiple
        
        
        return {
            "valuation": {
                "implied_equity_value": implied_equity_value,
                "market_cap": market_cap,
                "value_gap_pct": round(value_gap * 100, 2),
                "Current EV/EBITDA": current_multiple,
                "Historical median": median_multiple,
                "multiple_discount_pct": round(multiple_discount * 100, 2),
                "current_ebitda": current_ebitda
            },
           
            "reasoning": f"EV/EBITDA valuation analysis"
        }
        
    except Exception as e:
        return {"error": str(e)}


@tool
def residual_income_valuation_analysis(ticker: str, end_date: str, api_key: str) -> Dict[str, Any]:
    """
    Residual Income Model (RIM) valuation analysis
    
    Args:
        ticker: Stock ticker
        end_date: End date
        api_key: API key
        
    Returns:
        Dictionary containing residual income valuation analysis results
    """
    try:
        # Get financial metrics
        financial_metrics = get_financial_metrics(
            ticker=ticker,
            end_date=end_date,
            period="ttm",
            limit=8,
            api_key=api_key,
        )
        
        if not financial_metrics:
            return {"error": "No financial metrics found"}
        
        most_recent = financial_metrics[0]
        
        # Get net income data
        line_items = search_line_items(
            ticker=ticker,
            line_items=["net_income"],
            end_date=end_date,
            period="ttm",
            limit=1,
            api_key=api_key,
        )
        
        if not line_items or not line_items[0].net_income:
            return {"error": "No net income data"}
        
        net_income = line_items[0].net_income
        
        # Get market cap
        market_cap = get_market_cap(ticker, end_date, api_key=api_key)
        if not market_cap:
            return {"error": "Market cap unavailable"}
        
        # Check required data
        pb_ratio = most_recent.price_to_book_ratio
        if not pb_ratio or pb_ratio <= 0:
            return {"error": "Invalid P/B ratio"}
        
        # Calculate book value
        book_value = market_cap / pb_ratio
        
        # Model parameters
        cost_of_equity = 0.10
        book_value_growth = most_recent.book_value_growth or 0.03
        terminal_growth_rate = 0.03
        num_years = 5
        margin_of_safety = 0.20
        
        # Calculate initial residual income
        initial_residual_income = net_income - cost_of_equity * book_value
        
        if initial_residual_income <= 0:
            return {"error": "Negative residual income"}
        
        # Calculate present value of future residual income
        pv_residual_income = 0.0
        for year in range(1, num_years + 1):
            future_ri = initial_residual_income * (1 + book_value_growth) ** year
            pv_residual_income += future_ri / (1 + cost_of_equity) ** year
        
        # Terminal value
        terminal_ri = initial_residual_income * (1 + book_value_growth) ** (num_years + 1)
        terminal_value = terminal_ri / (cost_of_equity - terminal_growth_rate)
        pv_terminal = terminal_value / (1 + cost_of_equity) ** num_years
        
        # Intrinsic value
        intrinsic_value = (book_value + pv_residual_income + pv_terminal) * (1 - margin_of_safety)
        
        # Value gap
        value_gap = (intrinsic_value - market_cap) / market_cap
        
        
        return {
            "valuation": {
                "intrinsic_value": intrinsic_value,
                "market_cap": market_cap,
                "value_gap_pct": round(value_gap * 100, 2),
                "book_value": book_value,
                "residual_income": initial_residual_income,
                "cost_of_equity": cost_of_equity,
                "book_value_growth": book_value_growth,
                "margin_of_safety": margin_of_safety
            },
           
            "reasoning": f"Residual income valuation analysis"
        }
        
    except Exception as e:
        return {"error": str(e)}