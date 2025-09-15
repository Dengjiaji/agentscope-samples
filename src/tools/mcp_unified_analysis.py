import os
import time
import math
import json
import datetime
from statistics import median
from typing import Any, Dict, List, Optional, Union

import requests
import pandas as pd
import numpy as np


# ===================== 基础与工具函数 =====================

def _make_api_request(url: str, headers: dict, method: str = "GET", json_data: Union[dict, None] = None, max_retries: int = 3) -> requests.Response:
    for attempt in range(max_retries + 1):
        if method.upper() == "POST":
            response = requests.post(url, headers=headers, json=json_data)
        else:
            response = requests.get(url, headers=headers)

        if response.status_code == 429 and attempt < max_retries:
            delay = 60 + (30 * attempt)
            print(f"Rate limited (429). Attempt {attempt + 1}/{max_retries + 1}. Waiting {delay}s before retrying...")
            time.sleep(delay)
            continue

        return response


def _get_api_headers(api_key: Optional[str]) -> dict:
    headers: dict = {}
    financial_api_key = api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY")
    if financial_api_key:
        headers["X-API-KEY"] = financial_api_key
    return headers


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return default
        return float(value)
    except (ValueError, TypeError, OverflowError):
        return default


def prices_to_df(prices: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(prices)
    if df.empty:
        return df
    df["Date"] = pd.to_datetime(df["time"]) if "time" in df.columns else pd.to_datetime(df.index)
    df.set_index("Date", inplace=True)
    numeric_cols = [c for c in ["open", "close", "high", "low", "volume"] if c in df.columns]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df.sort_index(inplace=True)
    return df



def get_prices(ticker: str, start_date: str, end_date: str, api_key: Optional[str]) -> list[dict]:
    headers = _get_api_headers(api_key)
    url = f"https://api.financialdatasets.ai/prices/?ticker={ticker}&interval=day&interval_multiplier=1&start_date={start_date}&end_date={end_date}"
    response = _make_api_request(url, headers)
    if response.status_code != 200:
        raise Exception(f"Error fetching prices: {ticker} - {response.status_code} - {response.text}")
    data = response.json() or {}
    return data.get("prices", [])


def get_financial_metrics(ticker: str, end_date: str, period: str, limit: int, api_key: Optional[str]) -> list[dict]:
    headers = _get_api_headers(api_key)
    url = f"https://api.financialdatasets.ai/financial-metrics/?ticker={ticker}&report_period_lte={end_date}&limit={limit}&period={period}"
    response = _make_api_request(url, headers)
    if response.status_code != 200:
        raise Exception(f"Error fetching financial metrics: {ticker} - {response.status_code} - {response.text}")
    data = response.json() or {}
    return data.get("financial_metrics", [])


def search_line_items(ticker: str, line_items: list[str], end_date: str, period: str, limit: int, api_key: Optional[str]) -> list[dict]:
    headers = _get_api_headers(api_key)
    url = "https://api.financialdatasets.ai/financials/search/line-items"
    body = {
        "tickers": [ticker],
        "line_items": line_items,
        "end_date": end_date,
        "period": period,
        "limit": limit,
    }
    response = _make_api_request(url, headers, method="POST", json_data=body)
    if response.status_code != 200:
        raise Exception(f"Error searching line items: {ticker} - {response.status_code} - {response.text}")
    data = response.json() or {}
    return (data.get("search_results") or [])[:limit]


def get_insider_trades(ticker: str, end_date: str, start_date: Optional[str], limit: int, api_key: Optional[str]) -> list[dict]:
    headers = _get_api_headers(api_key)
    all_trades: list[dict] = []
    current_end_date = end_date
    while True:
        url = f"https://api.financialdatasets.ai/insider-trades/?ticker={ticker}&filing_date_lte={current_end_date}&limit={limit}"
        if start_date:
            url += f"&filing_date_gte={start_date}"
        response = _make_api_request(url, headers)
        if response.status_code != 200:
            raise Exception(f"Error fetching insider trades: {ticker} - {response.status_code} - {response.text}")
        data = response.json() or {}
        trades = data.get("insider_trades", [])
        if not trades:
            break
        all_trades.extend(trades)
        if not start_date or len(trades) < limit:
            break
        current_end_date = min(t.get("filing_date", "9999-12-31T00:00:00") for t in trades).split("T")[0]
        if current_end_date <= start_date:
            break
    return all_trades


def get_company_news(ticker: str, end_date: str, start_date: Optional[str], limit: int, api_key: Optional[str]) -> list[dict]:
    headers = _get_api_headers(api_key)
    all_news: list[dict] = []
    current_end_date = end_date
    while True:
        url = f"https://api.financialdatasets.ai/news/?ticker={ticker}&end_date={current_end_date}&limit={limit}"
        if start_date:
            url += f"&start_date={start_date}"
        response = _make_api_request(url, headers)
        if response.status_code != 200:
            raise Exception(f"Error fetching company news: {ticker} - {response.status_code} - {response.text}")
        data = response.json() or {}
        news = data.get("news", [])
        if not news:
            break
        all_news.extend(news)
        if not start_date or len(news) < limit:
            break
        current_end_date = min(n.get("date", "9999-12-31T00:00:00") for n in news).split("T")[0]
        if current_end_date <= start_date:
            break
    return all_news


def get_market_cap(ticker: str, end_date: str, api_key: Optional[str]) -> Optional[float]:
    # 如果是当天，用company facts
    if end_date == datetime.datetime.now().strftime("%Y-%m-%d"):
        headers = _get_api_headers(api_key)
        url = f"https://api.financialdatasets.ai/company/facts/?ticker={ticker}"
        response = _make_api_request(url, headers)
        if response.status_code != 200:
            print(f"Error fetching company facts: {ticker} - {response.status_code}")
            return None
        data = response.json() or {}
        company_facts = data.get("company_facts") or {}
        return company_facts.get("market_cap")

    # 否则从financial metrics取最近一期
    metrics = get_financial_metrics(ticker, end_date, period="ttm", limit=1, api_key=api_key)
    if not metrics:
        return None
    return metrics[0].get("market_cap")


# ===================== 综合信号 =====================

def combine_tool_signals(tool_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not tool_results:
        return {"signal": "neutral"}
    valid_results = [r for r in tool_results if "error" not in r and "signal" in r]
    if not valid_results:
        return {"signal": "neutral"}
    
    bullish_count = sum(1 for r in valid_results if r.get("signal") == "bullish")
    bearish_count = sum(1 for r in valid_results if r.get("signal") == "bearish")
    neutral_count = sum(1 for r in valid_results if r.get("signal") == "neutral")
    
    if bullish_count > bearish_count and bullish_count > neutral_count:
        return {"signal": "bullish"}
    elif bearish_count > bullish_count and bearish_count > neutral_count:
        return {"signal": "bearish"}
    else:
        return {"signal": "neutral"}


# ===================== 子分析实现 =====================

def analyze_profitability(metrics: dict) -> Dict[str, Any]:
    roe = metrics.get("return_on_equity")
    net_margin = metrics.get("net_margin")
    op_margin = metrics.get("operating_margin")
    thresholds = [
        (roe, 0.15, "ROE > 15%"),
        (net_margin, 0.20, "Net Margin > 20%"),
        (op_margin, 0.15, "Operating Margin > 15%"),
    ]
    score = 0
    for val, th, desc in thresholds:
        if val is not None and val > th:
            score += 1
    signal = "bullish" if score >= 2 else ("bearish" if score == 0 else "neutral")
    return {"signal": signal, "metrics": {"return_on_equity": roe, "net_margin": net_margin, "operating_margin": op_margin}}


def analyze_growth(metrics: dict) -> Dict[str, Any]:
    rev = metrics.get("revenue_growth")
    earn = metrics.get("earnings_growth")
    bv = metrics.get("book_value_growth")
    thresholds = [(rev, 0.10), (earn, 0.10), (bv, 0.10)]
    score = 0
    for val, th in thresholds:
        if val is not None and val > th:
            score += 1
    signal = "bullish" if score >= 2 else ("bearish" if score == 0 else "neutral")
    return {"signal": signal, "metrics": {"revenue_growth": rev, "earnings_growth": earn, "book_value_growth": bv}}


def analyze_financial_health(metrics: dict) -> Dict[str, Any]:
    cr = metrics.get("current_ratio")
    de = metrics.get("debt_to_equity")
    fcf_ps = metrics.get("free_cash_flow_per_share")
    eps = metrics.get("earnings_per_share")
    score = 0
    if cr and cr > 1.5:
        score += 1
    if de and de < 0.5:
        score += 1
    if fcf_ps and eps and fcf_ps > eps * 0.8:
        score += 1
    signal = "bullish" if score >= 2 else ("bearish" if score == 0 else "neutral")
    return {"signal": signal, "metrics": {"current_ratio": cr, "debt_to_equity": de, "free_cash_flow_per_share": fcf_ps, "earnings_per_share": eps}}


def analyze_valuation_ratios(metrics: dict) -> Dict[str, Any]:
    pe = metrics.get("price_to_earnings_ratio")
    pb = metrics.get("price_to_book_ratio")
    ps = metrics.get("price_to_sales_ratio")
    thresholds = [(pe, 25), (pb, 3), (ps, 5)]
    over = 0
    for val, th in thresholds:
        if val is not None and val > th:
            over += 1
    signal = "bearish" if over >= 2 else ("bullish" if over == 0 else "neutral")
    return {"signal": signal, "metrics": {"pe_ratio": pe, "pb_ratio": pb, "ps_ratio": ps}}


def analyze_trend_following(prices_df: pd.DataFrame) -> Dict[str, Any]:
    if prices_df is None or len(prices_df) < 10:
        return {"error": f"Insufficient data for trend analysis: only {0 if prices_df is None else len(prices_df)} days available, need at least 10", "signal": "neutral"}
    n = len(prices_df)
    sma_short_window = min(20, n // 2)
    sma_long_window = min(50, n - 5) if n > 25 else min(25, n - 5)
    prices_df = prices_df.copy()
    prices_df["SMA_20"] = prices_df["close"].rolling(window=sma_short_window).mean()
    prices_df["SMA_50"] = prices_df["close"].rolling(window=sma_long_window).mean()
    prices_df["EMA_12"] = prices_df["close"].ewm(span=min(12, n // 3)).mean()
    prices_df["EMA_26"] = prices_df["close"].ewm(span=min(26, n // 2)).mean()
    prices_df["MACD"] = prices_df["EMA_12"] - prices_df["EMA_26"]
    prices_df["MACD_signal"] = prices_df["MACD"].ewm(span=9).mean()
    prices_df["MACD_histogram"] = prices_df["MACD"] - prices_df["MACD_signal"]
    current_price = safe_float(prices_df["close"].iloc[-1])
    sma_20 = safe_float(prices_df["SMA_20"].iloc[-1])
    sma_50 = safe_float(prices_df["SMA_50"].iloc[-1])
    macd = safe_float(prices_df["MACD"].iloc[-1])
    macd_signal = safe_float(prices_df["MACD_signal"].iloc[-1])
    macd_histogram = safe_float(prices_df["MACD_histogram"].iloc[-1])
    signals: list[str] = []
    if current_price > sma_20 > sma_50:
        signals.append("bullish")
    elif current_price < sma_20 < sma_50:
        signals.append("bearish")
    else:
        signals.append("neutral")
    if macd > macd_signal and macd_histogram > 0:
        signals.append("bullish")
    elif macd < macd_signal and macd_histogram < 0:
        signals.append("bearish")
    else:
        signals.append("neutral")
    recent_prices = prices_df["close"].tail(5).values
    if len(recent_prices) >= 5:
        trend_slope = float(np.polyfit(range(len(recent_prices)), recent_prices, 1)[0])
        if trend_slope > 0:
            signals.append("bullish")
        elif trend_slope < 0:
            signals.append("bearish")
        else:
            signals.append("neutral")
    bullish_count = signals.count("bullish"); bearish_count = signals.count("bearish")
    final_signal = "bullish" if bullish_count > bearish_count else ("bearish" if bearish_count > bullish_count else "neutral")
    return {
        "signal": final_signal,
        "metrics": {
            "current_price": current_price,
            "sma_20": sma_20,
            "sma_50": sma_50,
            "macd": macd,
            "macd_signal": macd_signal,
            "macd_histogram": macd_histogram,
        },
    }


def analyze_mean_reversion(prices_df: pd.DataFrame) -> Dict[str, Any]:
    if prices_df is None or len(prices_df) < 5:
        return {"error": f"Insufficient data for mean reversion: only {0 if prices_df is None else len(prices_df)} days available, need at least 5", "signal": "neutral"}
    window = min(20, len(prices_df) - 2)
    prices_df = prices_df.copy()
    prices_df["SMA"] = prices_df["close"].rolling(window=window).mean()
    prices_df["STD"] = prices_df["close"].rolling(window=window).std()
    prices_df["Upper_Band"] = prices_df["SMA"] + (2 * prices_df["STD"])
    prices_df["Lower_Band"] = prices_df["SMA"] - (2 * prices_df["STD"])
    delta = prices_df["close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    prices_df["RSI"] = 100 - (100 / (1 + rs))
    current_price = safe_float(prices_df["close"].iloc[-1])
    sma = safe_float(prices_df["SMA"].iloc[-1])
    upper_band = safe_float(prices_df["Upper_Band"].iloc[-1])
    lower_band = safe_float(prices_df["Lower_Band"].iloc[-1])
    rsi = safe_float(prices_df["RSI"].iloc[-1])
    signals: list[str] = []
    if current_price <= lower_band:
        signals.append("bullish")
    elif current_price >= upper_band:
        signals.append("bearish")
    else:
        signals.append("neutral")
    if rsi <= 30:
        signals.append("bullish")
    elif rsi >= 70:
        signals.append("bearish")
    else:
        signals.append("neutral")
    price_deviation = (current_price - sma) / sma * 100 if sma else 0.0
    if price_deviation <= -5:
        signals.append("bullish")
    elif price_deviation >= 5:
        signals.append("bearish")
    else:
        signals.append("neutral")
    bullish_count = signals.count("bullish"); bearish_count = signals.count("bearish")
    final_signal = "bullish" if bullish_count > bearish_count else ("bearish" if bearish_count > bullish_count else "neutral")
    return {
        "signal": final_signal,
        "metrics": {
            "current_price": current_price,
            "sma": sma,
            "upper_band": upper_band,
            "lower_band": lower_band,
            "rsi": rsi,
            "price_deviation_pct": round(price_deviation, 2),
        },
    }


def analyze_momentum(prices_df: pd.DataFrame) -> Dict[str, Any]:
    if prices_df is None or len(prices_df) < 5:
        return {"error": f"Insufficient data for momentum: only {0 if prices_df is None else len(prices_df)} days available, need at least 5", "signal": "neutral"}
    df = prices_df.copy()
    df["returns"] = df["close"].pct_change()
    n = len(df)
    short_p = min(5, n // 3) or 1
    med_p = min(10, n // 2) or 1
    long_p = min(20, n - 2) or 1
    df["momentum_5"] = df["close"] / df["close"].shift(short_p) - 1
    df["momentum_10"] = df["close"] / df["close"].shift(med_p) - 1
    df["momentum_20"] = df["close"] / df["close"].shift(long_p) - 1
    current_price = safe_float(df["close"].iloc[-1])
    m5 = safe_float(df["momentum_5"].iloc[-1])
    m10 = safe_float(df["momentum_10"].iloc[-1])
    m20 = safe_float(df["momentum_20"].iloc[-1])
    vol = safe_float(df["returns"].tail(20).std() * np.sqrt(252))
    signals: list[str] = []
    if m5 > 0.02:
        signals.append("bullish")
    elif m5 < -0.02:
        signals.append("bearish")
    else:
        signals.append("neutral")
    if m10 > 0.05:
        signals.append("bullish")
    elif m10 < -0.05:
        signals.append("bearish")
    else:
        signals.append("neutral")
    if m20 > 0.10:
        signals.append("bullish")
    elif m20 < -0.10:
        signals.append("bearish")
    else:
        signals.append("neutral")
    bullish_count = signals.count("bullish"); bearish_count = signals.count("bearish")
    final_signal = "bullish" if bullish_count > bearish_count else ("bearish" if bearish_count > bullish_count else "neutral")
    return {
        "signal": final_signal,
        "metrics": {
            "current_price": current_price,
            "momentum_5d_pct": round(m5 * 100, 2),
            "momentum_10d_pct": round(m10 * 100, 2),
            "momentum_20d_pct": round(m20 * 100, 2),
            "recent_volatility": round(vol * 100, 2),
        },
    }


def analyze_volatility(prices_df: pd.DataFrame) -> Dict[str, Any]:
    if prices_df is None or len(prices_df) < 5:
        return {"error": f"Insufficient data for volatility: only {0 if prices_df is None else len(prices_df)} days available, need at least 5", "signal": "neutral"}
    df = prices_df.copy()
    df["returns"] = df["close"].pct_change()
    n = len(df)
    short_w = min(10, n // 2) or 2
    med_w = min(20, n - 2) or 5
    long_w = min(60, n - 1) if n > 30 else med_w
    df["vol_10"] = df["returns"].rolling(window=short_w).std() * np.sqrt(252)
    df["vol_20"] = df["returns"].rolling(window=med_w).std() * np.sqrt(252)
    df["vol_60"] = df["returns"].rolling(window=long_w).std() * np.sqrt(252)
    v10 = safe_float(df["vol_10"].iloc[-1]); v20 = safe_float(df["vol_20"].iloc[-1]); v60 = safe_float(df["vol_60"].iloc[-1])
    pct = float(df["vol_20"].rank(pct=True).iloc[-1] * 100) if not math.isnan(v20) else 0.0
    signals: list[str] = []
    if v10 > v20 > v60:
        signals.append("bearish")
    elif v10 < v20 < v60:
        signals.append("bullish")
    else:
        signals.append("neutral")
    if v20 > 0.40:
        signals.append("bearish")
    elif v20 < 0.15:
        signals.append("bullish")
    else:
        signals.append("neutral")
    if pct > 80:
        signals.append("bearish")
    elif pct < 20:
        signals.append("bullish")
    else:
        signals.append("neutral")
    bullish_count = signals.count("bullish"); bearish_count = signals.count("bearish")
    final_signal = "bullish" if bullish_count > bearish_count else ("bearish" if bearish_count > bullish_count else "neutral")
    return {
        "signal": final_signal,
        "metrics": {
            "volatility_10d": round(v10 * 100, 2),
            "volatility_20d": round(v20 * 100, 2),
            "volatility_60d": round(v60 * 100, 2),
            "volatility_percentile": round(pct, 1),
        },
    }


def analyze_insider_trading(trades: list[dict]) -> Dict[str, Any]:
    if not trades:
        return {"signal": "neutral", "metrics": {"total_trades": 0, "buy_trades": 0, "sell_trades": 0, "total_buy_volume": 0, "total_sell_volume": 0, "trade_ratio": 0, "volume_ratio": 0}}
    shares = [t.get("transaction_shares") for t in trades if t.get("transaction_shares") is not None]
    if not shares:
        return {"signal": "neutral", "metrics": {"total_trades": len(trades), "buy_trades": 0, "sell_trades": 0, "total_buy_volume": 0, "total_sell_volume": 0, "trade_ratio": 0, "volume_ratio": 0}}
    buy_trades = sum(1 for s in shares if s > 0)
    sell_trades = sum(1 for s in shares if s < 0)
    total_trades = len(shares)
    total_buy_volume = float(sum(s for s in shares if s > 0))
    total_sell_volume = float(abs(sum(s for s in shares if s < 0)))
    if buy_trades > sell_trades and total_buy_volume > total_sell_volume:
        signal = "bullish"
    elif sell_trades > buy_trades and total_sell_volume > total_buy_volume:
        signal = "bearish"
    else:
        signal = "neutral"
    return {
        "signal": signal,
        "metrics": {
            "total_trades": total_trades,
            "buy_trades": buy_trades,
            "sell_trades": sell_trades,
            "total_buy_volume": total_buy_volume,
            "total_sell_volume": total_sell_volume,
            "trade_ratio": round(buy_trades / max(sell_trades, 1), 2),
            "volume_ratio": round(total_buy_volume / max(total_sell_volume, 1), 2),
        },
    }


def analyze_news_sentiment(news: list[dict]) -> Dict[str, Any]:
    if not news:
        return {"signal": "neutral", "metrics": {"total_articles": 0, "positive_articles": 0, "negative_articles": 0, "neutral_articles": 0, "positive_ratio": 0, "negative_ratio": 0, "neutral_ratio": 0}}
    sentiments = [n.get("sentiment") for n in news if n.get("sentiment")]
    if not sentiments:
        return {"signal": "neutral", "metrics": {"total_articles": len(news), "positive_articles": 0, "negative_articles": 0, "neutral_articles": 0, "positive_ratio": 0, "negative_ratio": 0, "neutral_ratio": 0}}
    pos = sum(1 for s in sentiments if s == "positive")
    neg = sum(1 for s in sentiments if s == "negative")
    neu = sum(1 for s in sentiments if s == "neutral")
    total = len(sentiments)
    if pos > neg:
        signal = "bullish"
    elif neg > pos:
        signal = "bearish"
    else:
        signal = "neutral"
    return {
        "signal": signal,
        "metrics": {
            "total_articles": total,
            "positive_articles": pos,
            "negative_articles": neg,
            "neutral_articles": neu,
            "positive_ratio": round(pos / total * 100, 1) if total else 0,
            "negative_ratio": round(neg / total * 100, 1) if total else 0,
            "neutral_ratio": round(neu / total * 100, 1) if total else 0,
        },
    }


def dcf_valuation(metrics: dict, line_items: list[dict], market_cap: Optional[float]) -> Dict[str, Any]:
    if not line_items or market_cap is None:
        return {"error": "Insufficient data for DCF", "signal": "neutral"}
    current_fcf = line_items[0].get("free_cash_flow")
    if not current_fcf or current_fcf <= 0:
        return {"error": "Invalid free cash flow data", "signal": "neutral"}
    growth_rate = metrics.get("earnings_growth") or 0.05
    discount_rate = 0.10
    terminal_growth = 0.03
    years = 5
    pv_fcf = 0.0
    for y in range(1, years + 1):
        future_fcf = current_fcf * (1 + growth_rate) ** y
        pv_fcf += future_fcf / (1 + discount_rate) ** y
    terminal_fcf = current_fcf * (1 + growth_rate) ** years * (1 + terminal_growth)
    terminal_value = terminal_fcf / (discount_rate - terminal_growth)
    pv_terminal = terminal_value / (1 + discount_rate) ** years
    enterprise_value = pv_fcf + pv_terminal
    value_gap = (enterprise_value - market_cap) / market_cap if market_cap else 0
    signal = "bullish" if value_gap > 0.20 else ("bearish" if value_gap < -0.20 else "neutral")
    return {
        "signal": signal,
        "valuation": {
            "enterprise_value": enterprise_value,
            "market_cap": market_cap,
            "value_gap_pct": round(value_gap * 100, 2),
            "current_fcf": current_fcf,
            "growth_rate": growth_rate,
            "discount_rate": discount_rate,
        },
    }


def owner_earnings_valuation(metrics: dict, li_two: list[dict], market_cap: Optional[float]) -> Dict[str, Any]:
    if len(li_two) < 2 or market_cap is None:
        return {"error": "Insufficient financial data", "signal": "neutral"}
    current, previous = li_two[0], li_two[1]
    net_income = current.get("net_income") or 0
    depreciation = current.get("depreciation_and_amortization") or 0
    capex = current.get("capital_expenditure") or 0
    wc_change = (current.get("working_capital") or 0) - (previous.get("working_capital") or 0)
    owner_earnings = net_income + depreciation - capex - wc_change
    if owner_earnings <= 0:
        return {"error": "Negative owner earnings", "signal": "neutral"}
    growth_rate = metrics.get("earnings_growth") or 0.05
    required_return = 0.15
    margin_of_safety = 0.25
    years = 5
    pv = 0.0
    for y in range(1, years + 1):
        f = owner_earnings * (1 + growth_rate) ** y
        pv += f / (1 + required_return) ** y
    terminal_growth = min(growth_rate, 0.03)
    terminal_earnings = owner_earnings * (1 + growth_rate) ** years * (1 + terminal_growth)
    terminal_value = terminal_earnings / (required_return - terminal_growth)
    pv_terminal = terminal_value / (1 + required_return) ** years
    intrinsic = (pv + pv_terminal) * (1 - margin_of_safety)
    value_gap = (intrinsic - market_cap) / market_cap if market_cap else 0
    signal = "bullish" if value_gap > 0.25 else ("bearish" if value_gap < -0.25 else "neutral")
    return {
        "signal": signal,
        "valuation": {
            "intrinsic_value": intrinsic,
            "market_cap": market_cap,
            "value_gap_pct": round(value_gap * 100, 2),
            "owner_earnings": owner_earnings,
            "growth_rate": growth_rate,
            "required_return": required_return,
            "margin_of_safety": margin_of_safety,
        },
        "components": {
            "net_income": net_income,
            "depreciation": depreciation,
            "capex": capex,
            "wc_change": wc_change,
        },
    }


def ev_ebitda_valuation(financial_metrics: list[dict], market_cap: Optional[float]) -> Dict[str, Any]:
    if not financial_metrics or market_cap is None:
        return {"error": "Insufficient EV/EBITDA data", "signal": "neutral"}
    most = financial_metrics[0]
    ev = most.get("enterprise_value")
    multiple = most.get("enterprise_value_to_ebitda_ratio")
    if not ev or not multiple or multiple <= 0:
        return {"error": "Missing EV or multiple", "signal": "neutral"}
    current_ebitda = ev / multiple
    valid_multiples = [m.get("enterprise_value_to_ebitda_ratio") for m in financial_metrics if m.get("enterprise_value_to_ebitda_ratio") and m.get("enterprise_value_to_ebitda_ratio") > 0]
    if len(valid_multiples) < 3:
        return {"error": "Insufficient historical multiples", "signal": "neutral"}
    median_multiple = median(valid_multiples)
    implied_ev = median_multiple * current_ebitda
    net_debt = (ev or 0) - (market_cap or 0)
    implied_equity = max(implied_ev - net_debt, 0)
    value_gap = (implied_equity - market_cap) / market_cap if market_cap else 0
    multiple_discount = (median_multiple - multiple) / median_multiple
    if value_gap > 0.15 and multiple_discount > 0.10:
        signal = "bullish"
    elif value_gap < -0.15 and multiple_discount < -0.10:
        signal = "bearish"
    else:
        signal = "neutral"
    return {
        "signal": signal,
        "valuation": {
            "implied_equity_value": implied_equity,
            "market_cap": market_cap,
            "value_gap_pct": round(value_gap * 100, 2),
            "current_multiple": multiple,
            "median_multiple": median_multiple,
            "multiple_discount_pct": round(multiple_discount * 100, 2),
            "current_ebitda": current_ebitda,
        },
    }


def residual_income_valuation(metrics: dict, net_income_item: Optional[dict], market_cap: Optional[float]) -> Dict[str, Any]:
    if market_cap is None or not metrics:
        return {"error": "Insufficient data for RIM", "signal": "neutral"}
    pb = metrics.get("price_to_book_ratio")
    if not pb or pb <= 0:
        return {"error": "Invalid P/B ratio", "signal": "neutral"}
    book_value = market_cap / pb
    cost_of_equity = 0.10
    bv_growth = metrics.get("book_value_growth") or 0.03
    terminal_growth = 0.03
    years = 5
    if not net_income_item or not net_income_item.get("net_income"):
        return {"error": "No net income data", "signal": "neutral"}
    net_income = net_income_item.get("net_income")
    initial_ri = net_income - cost_of_equity * book_value
    if initial_ri <= 0:
        return {"error": "Negative residual income", "signal": "neutral"}
    pv_ri = 0.0
    for y in range(1, years + 1):
        future_ri = initial_ri * (1 + bv_growth) ** y
        pv_ri += future_ri / (1 + cost_of_equity) ** y
    terminal_ri = initial_ri * (1 + bv_growth) ** (years + 1)
    terminal_value = terminal_ri / (cost_of_equity - terminal_growth)
    pv_terminal = terminal_value / (1 + cost_of_equity) ** years
    margin_of_safety = 0.20
    intrinsic = (book_value + pv_ri + pv_terminal) * (1 - margin_of_safety)
    value_gap = (intrinsic - market_cap) / market_cap if market_cap else 0
    signal = "bullish" if value_gap > 0.20 else ("bearish" if value_gap < -0.20 else "neutral")
    return {
        "signal": signal,
        "valuation": {
            "intrinsic_value": intrinsic,
            "market_cap": market_cap,
            "value_gap_pct": round(value_gap * 100, 2),
            "book_value": book_value,
            "residual_income": initial_ri,
            "cost_of_equity": cost_of_equity,
            "book_value_growth": bv_growth,
            "margin_of_safety": margin_of_safety,
        },
    }


# ===================== 统一函数 =====================

def analyze_all(ticker: str, analysis_date: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    # 1) 拉取基础数据
    # 为技术分析扩展窗口
    end_dt = datetime.datetime.strptime(analysis_date, "%Y-%m-%d")
    extended_trend_start = (end_dt - datetime.timedelta(days=90)).strftime("%Y-%m-%d")
    extended_mean_start = (end_dt - datetime.timedelta(days=60)).strftime("%Y-%m-%d")
    extended_mom_start = (end_dt - datetime.timedelta(days=45)).strftime("%Y-%m-%d")

    prices_trend = get_prices(ticker, extended_trend_start, analysis_date, api_key)
    prices_mean = prices_trend if extended_trend_start <= extended_mean_start else get_prices(ticker, extended_mean_start, analysis_date, api_key)
    prices_mom = prices_trend if extended_trend_start <= extended_mom_start else get_prices(ticker, extended_mom_start, analysis_date, api_key)

    df_trend = prices_to_df(prices_trend)
    df_mean = prices_to_df(prices_mean)
    df_mom = prices_to_df(prices_mom)

    financial_metrics_list = get_financial_metrics(ticker, analysis_date, period="ttm", limit=10, api_key=api_key)
    most_recent_metrics = financial_metrics_list[0] if financial_metrics_list else {}

    # 内部交易和新闻获取近60天数据
    insider_start_date = (end_dt - datetime.timedelta(days=60)).strftime("%Y-%m-%d")
    insider = get_insider_trades(ticker, end_date=analysis_date, start_date=insider_start_date, limit=1000, api_key=api_key)
    news = get_company_news(ticker, end_date=analysis_date, start_date=insider_start_date, limit=100, api_key=api_key)
    mkt_cap = get_market_cap(ticker, analysis_date, api_key=api_key)

    # DCF/Owner earnings/Residual income所需line items
    line_items_fcf = search_line_items(ticker, ["free_cash_flow"], analysis_date, period="ttm", limit=2, api_key=api_key)
    line_items_owner = search_line_items(ticker, ["net_income", "depreciation_and_amortization", "capital_expenditure", "working_capital"], analysis_date, period="ttm", limit=2, api_key=api_key)
    line_items_net_income = search_line_items(ticker, ["net_income"], analysis_date, period="ttm", limit=1, api_key=api_key)

    # 2) 分析
    profitability = analyze_profitability(most_recent_metrics) if most_recent_metrics else {"error": "No financial metrics"}
    growth = analyze_growth(most_recent_metrics) if most_recent_metrics else {"error": "No financial metrics"}
    health = analyze_financial_health(most_recent_metrics) if most_recent_metrics else {"error": "No financial metrics"}
    valuation_ratios = analyze_valuation_ratios(most_recent_metrics) if most_recent_metrics else {"error": "No financial metrics"}

    trend = analyze_trend_following(df_trend)
    mean_rev = analyze_mean_reversion(df_mean)
    momentum = analyze_momentum(df_mom)
    volatility = analyze_volatility(df_trend)

    insider_view = analyze_insider_trading(insider)
    news_view = analyze_news_sentiment(news)

    dcf = dcf_valuation(most_recent_metrics, line_items_fcf, mkt_cap)
    owner_val = owner_earnings_valuation(most_recent_metrics, line_items_owner, mkt_cap)
    ev_val = ev_ebitda_valuation(financial_metrics_list, mkt_cap)
    rim = residual_income_valuation(most_recent_metrics, line_items_net_income[0] if line_items_net_income else None, mkt_cap)

    # 3) 综合信号
    combined = combine_tool_signals([
        profitability if isinstance(profitability, dict) else {},
        growth if isinstance(growth, dict) else {},
        health if isinstance(health, dict) else {},
        valuation_ratios if isinstance(valuation_ratios, dict) else {},
        trend if isinstance(trend, dict) else {},
        mean_rev if isinstance(mean_rev, dict) else {},
        momentum if isinstance(momentum, dict) else {},
        volatility if isinstance(volatility, dict) else {},
        insider_view if isinstance(insider_view, dict) else {},
        news_view if isinstance(news_view, dict) else {},
        dcf if isinstance(dcf, dict) else {},
        owner_val if isinstance(owner_val, dict) else {},
        ev_val if isinstance(ev_val, dict) else {},
        rim if isinstance(rim, dict) else {},
    ])

    # 4) 汇总输出
    return {
        "ticker": ticker,
        "analysis_date": analysis_date,
        'analysis_report':{
        "combined_signal": combined,
        "fundamental": {
            "profitability": profitability,
            "growth": growth,
            "financial_health": health,
            "valuation_ratios": valuation_ratios,
        },
        "technical": {
            "trend_following": trend,
            "mean_reversion": mean_rev,
            "momentum": momentum,
            "volatility": volatility,
        },
        "sentiment": {
            "insider_trading": insider_view,
            "news_sentiment": news_view,
        },
        "valuation": {
            "dcf": dcf,
            "owner_earnings": owner_val,
            "ev_ebitda": ev_val,
            "residual_income": rim,
        },},
        "raw_data": {
            "prices_for_trend": prices_trend,
            "prices_for_mean": prices_mean,
            "prices_for_momentum": prices_mom,
            "financial_metrics": financial_metrics_list,
            "insider_trades": insider,
            "company_news": news,
        },
    }


__all__ = ["analyze_all"]


