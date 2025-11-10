import datetime
import os
import pandas as pd
import requests
import time
import finnhub
import pdb
from src.data.cache import get_cache
from src.data.models import (
    CompanyNews,
    CompanyNewsResponse,
    FinancialMetrics,
    FinancialMetricsResponse,
    Price,
    PriceResponse,
    LineItem,
    LineItemResponse,
    InsiderTrade,
    InsiderTradeResponse,
    CompanyFactsResponse,
)

# 尝试导入交易日历包
try:
    import pandas_market_calendars as mcal
    _NYSE_CALENDAR = mcal.get_calendar('NYSE')
    US_TRADING_CALENDAR_AVAILABLE = True
except ImportError:
    try:
        import exchange_calendars as xcals
        _NYSE_CALENDAR = xcals.get_calendar('XNYS')
        US_TRADING_CALENDAR_AVAILABLE = True
    except ImportError:
        _NYSE_CALENDAR = None
        US_TRADING_CALENDAR_AVAILABLE = False

# Global cache instance
_cache = get_cache()


def get_last_tradeday(date: str) -> str:
    """
    获取指定日期的上一个交易日
    
    Args:
        date: 日期字符串 (YYYY-MM-DD)
        
    Returns:
        上一个交易日的日期字符串 (YYYY-MM-DD)
    """
    current_date = datetime.datetime.strptime(date, "%Y-%m-%d")
    
    if US_TRADING_CALENDAR_AVAILABLE and _NYSE_CALENDAR is not None:
        # 获取当前日期之前的交易日
        # 从当前日期往前推90天，获取所有交易日
        start_search = current_date - datetime.timedelta(days=90)
        
        if hasattr(_NYSE_CALENDAR, 'valid_days'):
            # pandas_market_calendars
            trading_dates = _NYSE_CALENDAR.valid_days(
                start_date=start_search.strftime("%Y-%m-%d"),
                end_date=current_date.strftime("%Y-%m-%d")
            )
        else:
            # exchange_calendars
            trading_dates = _NYSE_CALENDAR.sessions_in_range(
                start_search.strftime("%Y-%m-%d"),
                current_date.strftime("%Y-%m-%d")
            )
        
        # 转换为日期列表
        trading_dates_list = [pd.Timestamp(d).strftime("%Y-%m-%d") for d in trading_dates]
        
        # 查找当前日期在列表中的位置
        if date in trading_dates_list:
            # 如果当前日期是交易日，返回前一个交易日
            idx = trading_dates_list.index(date)
            if idx > 0:
                return trading_dates_list[idx - 1]
            else:
                # 如果是第一个交易日，再往前推
                prev_date = current_date - datetime.timedelta(days=1)
                return get_last_tradeday(prev_date.strftime("%Y-%m-%d"))
        else:
            # 如果当前日期不是交易日，返回最近的交易日
            if trading_dates_list:
                return trading_dates_list[-1]
    
    return prev_date.strftime("%Y-%m-%d")


def _make_api_request(url: str, headers: dict, method: str = "GET", json_data: dict = None, max_retries: int = 3) -> requests.Response:
    """
    Make an API request with rate limiting handling and moderate backoff.
    
    Args:
        url: The URL to request
        headers: Headers to include in the request
        method: HTTP method (GET or POST)
        json_data: JSON data for POST requests
        max_retries: Maximum number of retries (default: 3)
    
    Returns:
        requests.Response: The response object
    
    Raises:
        Exception: If the request fails with a non-429 error
    """
    for attempt in range(max_retries + 1):  # +1 for initial attempt
        if method.upper() == "POST":
            response = requests.post(url, headers=headers, json=json_data)
        else:
            response = requests.get(url, headers=headers)
        
        if response.status_code == 429 and attempt < max_retries:
            # Linear backoff: 60s, 90s, 120s, 150s...
            delay = 60 + (30 * attempt)
            print(f"Rate limited (429). Attempt {attempt + 1}/{max_retries + 1}. Waiting {delay}s before retrying...")
            time.sleep(delay)
            continue
        
        # Return the response (whether success, other errors, or final 429)
        return response


def get_prices(
    ticker: str, 
    start_date: str, 
    end_date: str, 
    api_key: str = None,
    data_source: str = "finnhub"
) -> list[Price]:
    """
    Fetch price data from cache or API.
    
    Args:
        ticker: Stock ticker symbol
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        api_key: API key (optional, will use FINNHUB_API_KEY or FINANCIAL_DATASETS_API_KEY from env)
        data_source: Data source ("finnhub" or "financial_datasets", default: "finnhub")
    
    Returns:
        list[Price]: List of Price objects
    """
    # Create a cache key that includes all parameters to ensure exact matches
    cache_key = f"{ticker}_{start_date}_{end_date}_{data_source}"
    
    # Check cache first - simple exact match
    if cached_data := _cache.get_prices(cache_key):
        return [Price(**price) for price in cached_data]

    prices = []
    
    if data_source == "finnhub":
        # Use Finnhub API
        finnhub_api_key = api_key or os.environ.get("FINNHUB_API_KEY")
        if not finnhub_api_key:
            raise ValueError("FINNHUB_API_KEY is required. Please set it in your .env file.")
        
        # Initialize Finnhub client
        client = finnhub.Client(api_key=finnhub_api_key)
        
        # Convert dates to timestamps
        start_timestamp = int(datetime.datetime.strptime(start_date, "%Y-%m-%d").timestamp())
        end_timestamp = int(datetime.datetime.strptime(end_date, "%Y-%m-%d").timestamp())
        
        # Fetch candle data from Finnhub
        candles = client.stock_candles(ticker, 'D', start_timestamp, end_timestamp)
        # Check response status
        if candles.get('s') != 'ok':
            raise Exception(f"Error fetching data from Finnhub: {ticker} - {candles}")
        
        # Convert to Price objects
        for i in range(len(candles['t'])):
            price = Price(
                open=candles['o'][i],
                close=candles['c'][i],
                high=candles['h'][i],
                low=candles['l'][i],
                volume=int(candles['v'][i]),
                time=datetime.datetime.fromtimestamp(candles['t'][i]).strftime("%Y-%m-%d")
            )
            prices.append(price)
    
    elif data_source == "financial_datasets":
        # Use Financial Datasets API
        headers = {}
        financial_api_key = api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY")
        if financial_api_key:
            headers["X-API-KEY"] = financial_api_key

        url = f"https://api.financialdatasets.ai/prices/?ticker={ticker}&interval=day&interval_multiplier=1&start_date={start_date}&end_date={end_date}"
        response = _make_api_request(url, headers)
        if response.status_code != 200:
            raise Exception(f"Error fetching data: {ticker} - {response.status_code} - {response.text}")

        # Parse response with Pydantic model
        price_response = PriceResponse(**response.json())
        prices = price_response.prices
    
    else:
        raise ValueError(f"Invalid data_source: {data_source}. Must be 'finnhub' or 'financial_datasets'")

    if not prices:
        return []

    # Cache the results using the comprehensive cache key
    _cache.set_prices(cache_key, [p.model_dump() for p in prices])
    return prices


def get_financial_metrics(
    ticker: str,
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str = None,
    data_source: str = "finnhub"
) -> list[FinancialMetrics]:
    """
    Fetch financial metrics from cache or API.
    
    Args:
        ticker: Stock ticker symbol
        end_date: End date (YYYY-MM-DD)
        period: Period type (default: "ttm")
        limit: Number of records to fetch
        api_key: API key (optional)
        data_source: Data source ("finnhub" or "financial_datasets", default: "finnhub")
    
    Returns:
        list[FinancialMetrics]: List of financial metrics
    """
    # Create a cache key that includes all parameters to ensure exact matches
    cache_key = f"{ticker}_{period}_{end_date}_{limit}_{data_source}"
    
    # Check cache first - simple exact match
    if cached_data := _cache.get_financial_metrics(cache_key):
        return [FinancialMetrics(**metric) for metric in cached_data]

    financial_metrics = []
    
    if data_source == "finnhub":
        # Use Finnhub API - Basic Financials
        finnhub_api_key = api_key or os.environ.get("FINNHUB_API_KEY")
        if not finnhub_api_key:
            raise ValueError("FINNHUB_API_KEY is required. Please set it in your .env file.")
        
        client = finnhub.Client(api_key=finnhub_api_key)
        
        # Fetch basic financials from Finnhub
        # metric='all' returns all available metrics
        financials = client.company_basic_financials(ticker, 'all')
        
        if not financials or 'metric' not in financials:
            return []
        
        # Finnhub returns {series: {...}, metric: {...}, metricType: ..., symbol: ...}
        # We need to create a FinancialMetrics object from this
        metric_data = financials.get('metric', {})
        
        # Create a FinancialMetrics object with available data
        # Note: Finnhub's metric names don't match our model exactly, so we map what we can
        metric = FinancialMetrics(
            ticker=ticker,
            report_period=end_date,
            period=period,
            currency="USD",  # Finnhub doesn't provide currency, assume USD
            market_cap=metric_data.get('marketCapitalization'),
            enterprise_value=None,  # Not directly available
            price_to_earnings_ratio=metric_data.get('peBasicExclExtraTTM'),
            price_to_book_ratio=metric_data.get('pbAnnual'),
            price_to_sales_ratio=metric_data.get('psAnnual'),
            enterprise_value_to_ebitda_ratio=None,
            enterprise_value_to_revenue_ratio=None,
            free_cash_flow_yield=None,
            peg_ratio=None,
            gross_margin=metric_data.get('grossMarginTTM'),
            operating_margin=metric_data.get('operatingMarginTTM'),
            net_margin=metric_data.get('netProfitMarginTTM'),
            return_on_equity=metric_data.get('roeTTM'),
            return_on_assets=metric_data.get('roaTTM'),
            return_on_invested_capital=metric_data.get('roicTTM'),
            asset_turnover=metric_data.get('assetTurnoverTTM'),
            inventory_turnover=metric_data.get('inventoryTurnoverTTM'),
            receivables_turnover=metric_data.get('receivablesTurnoverTTM'),
            days_sales_outstanding=None,
            operating_cycle=None,
            working_capital_turnover=None,
            current_ratio=metric_data.get('currentRatioAnnual'),
            quick_ratio=metric_data.get('quickRatioAnnual'),
            cash_ratio=None,
            operating_cash_flow_ratio=None,
            debt_to_equity=metric_data.get('totalDebt/totalEquityAnnual'),
            debt_to_assets=None,
            interest_coverage=None,
            revenue_growth=metric_data.get('revenueGrowthTTMYoy'),
            earnings_growth=None,
            book_value_growth=None,
            earnings_per_share_growth=metric_data.get('epsGrowthTTMYoy'),
            free_cash_flow_growth=None,
            operating_income_growth=None,
            ebitda_growth=None,
            payout_ratio=metric_data.get('payoutRatioAnnual'),
            earnings_per_share=metric_data.get('epsBasicExclExtraItemsTTM'),
            book_value_per_share=metric_data.get('bookValuePerShareAnnual'),
            free_cash_flow_per_share=None
        )
        financial_metrics = [metric]
    
    elif data_source == "financial_datasets":
        # Use Financial Datasets API
        headers = {}
        financial_api_key = api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY")
        if financial_api_key:
            headers["X-API-KEY"] = financial_api_key

        url = f"https://api.financialdatasets.ai/financial-metrics/?ticker={ticker}&report_period_lte={end_date}&limit={limit}&period={period}"
        response = _make_api_request(url, headers)
        if response.status_code != 200:
            raise Exception(f"Error fetching data: {ticker} - {response.status_code} - {response.text}")

        # Parse response with Pydantic model
        metrics_response = FinancialMetricsResponse(**response.json())
        financial_metrics = metrics_response.financial_metrics
    
    else:
        raise ValueError(f"Invalid data_source: {data_source}. Must be 'finnhub' or 'financial_datasets'")

    if not financial_metrics:
        return []

    # Cache the results as dicts using the comprehensive cache key
    _cache.set_financial_metrics(cache_key, [m.model_dump() for m in financial_metrics])
    return financial_metrics


def search_line_items(
    ticker: str,
    line_items: list[str],
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str = None,
) -> list[LineItem]:
    """Fetch line items from API."""
    # If not in cache or insufficient data, fetch from API
    headers = {}
    financial_api_key = api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY")
    if financial_api_key:
        headers["X-API-KEY"] = financial_api_key

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
        raise Exception(f"Error fetching data: {ticker} - {response.status_code} - {response.text}")
    data = response.json()
    response_model = LineItemResponse(**data)
    search_results = response_model.search_results
    if not search_results:
        return []

    # Cache the results
    return search_results[:limit]


def get_insider_trades(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
    api_key: str = None,
    data_source: str = "finnhub"
) -> list[InsiderTrade]:
    """
    Fetch insider trades from cache or API.
    
    Args:
        ticker: Stock ticker symbol
        end_date: End date (YYYY-MM-DD)
        start_date: Start date (YYYY-MM-DD, optional)
        limit: Number of records to fetch
        api_key: API key (optional)
        data_source: Data source ("finnhub" or "financial_datasets", default: "finnhub")
    
    Returns:
        list[InsiderTrade]: List of insider trades
    """
    # Create a cache key that includes all parameters to ensure exact matches
    cache_key = f"{ticker}_{start_date or 'none'}_{end_date}_{limit}_{data_source}"
    
    # Check cache first - simple exact match
    if cached_data := _cache.get_insider_trades(cache_key):
        return [InsiderTrade(**trade) for trade in cached_data]

    all_trades = []
    
    if data_source == "finnhub":
        # Use Finnhub API - Insider Transactions
        finnhub_api_key = api_key or os.environ.get("FINNHUB_API_KEY")
        if not finnhub_api_key:
            raise ValueError("FINNHUB_API_KEY is required. Please set it in your .env file.")
        
        client = finnhub.Client(api_key=finnhub_api_key)
        
        # Finnhub API: stock_insider_transactions(symbol, from_date, to_date)
        # Convert date format if needed
        from_date = start_date if start_date else (datetime.datetime.strptime(end_date, "%Y-%m-%d") - datetime.timedelta(days=365)).strftime("%Y-%m-%d")
        
        try:
            insider_data = client.stock_insider_transactions(ticker, from_date, end_date)
            
            if insider_data and 'data' in insider_data:
                # Convert Finnhub format to InsiderTrade format
                for trade in insider_data['data'][:limit]:  # Limit results
                    # Calculate shares owned after from share and change
                    shares_after = trade.get('share', 0)
                    
                    insider_trade = InsiderTrade(
                        ticker=ticker,
                        issuer=None,  # Not provided by Finnhub
                        name=trade.get('name', ''),
                        title=None,  # Not provided by Finnhub
                        is_board_director=None,  # Not provided by Finnhub
                        transaction_date=trade.get('transactionDate', ''),
                        transaction_shares=abs(trade.get('change', 0)),  # Number of shares in transaction
                        transaction_price_per_share=trade.get('transactionPrice', 0.0),
                        transaction_value=abs(trade.get('change', 0)) * trade.get('transactionPrice', 0.0),
                        shares_owned_before_transaction=shares_after - trade.get('change', 0) if shares_after and trade.get('change') else None,
                        shares_owned_after_transaction=float(shares_after) if shares_after else None,
                        security_title=None,  # Not provided by Finnhub
                        filing_date=trade.get('filingDate', '')
                    )
                    all_trades.append(insider_trade)
        except Exception as e:
            # Finnhub may not have data for all tickers
            print(f"Warning: Finnhub insider trades error for {ticker}: {e}")
            return []
    
    elif data_source == "financial_datasets":
        # Use Financial Datasets API
        headers = {}
        financial_api_key = api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY")
        if financial_api_key:
            headers["X-API-KEY"] = financial_api_key

        current_end_date = end_date

        while True:
            url = f"https://api.financialdatasets.ai/insider-trades/?ticker={ticker}&filing_date_lte={current_end_date}"
            if start_date:
                url += f"&filing_date_gte={start_date}"
            url += f"&limit={limit}"

            response = _make_api_request(url, headers)
            if response.status_code != 200:
                raise Exception(f"Error fetching data: {ticker} - {response.status_code} - {response.text}")

            data = response.json()
            response_model = InsiderTradeResponse(**data)
            insider_trades = response_model.insider_trades

            if not insider_trades:
                break

            all_trades.extend(insider_trades)

            # Only continue pagination if we have a start_date and got a full page
            if not start_date or len(insider_trades) < limit:
                break

            # Update end_date to the oldest filing date from current batch for next iteration
            current_end_date = min(trade.filing_date for trade in insider_trades).split("T")[0]

            # If we've reached or passed the start_date, we can stop
            if current_end_date <= start_date:
                break
    
    else:
        raise ValueError(f"Invalid data_source: {data_source}. Must be 'finnhub' or 'financial_datasets'")

    if not all_trades:
        return []

    # Cache the results using the comprehensive cache key
    _cache.set_insider_trades(cache_key, [trade.model_dump() for trade in all_trades])
    return all_trades


def get_company_news(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
    api_key: str = None,
    data_source: str = "finnhub"
) -> list[CompanyNews]:
    """
    Fetch company news from cache or API.
    
    Args:
        ticker: Stock ticker symbol
        end_date: End date (YYYY-MM-DD)
        start_date: Start date (YYYY-MM-DD, optional)
        limit: Number of records to fetch
        api_key: API key (optional)
        data_source: Data source ("finnhub" or "financial_datasets", default: "finnhub")
    
    Returns:
        list[CompanyNews]: List of company news
    """
    # Create a cache key that includes all parameters to ensure exact matches
    cache_key = f"{ticker}_{start_date or 'none'}_{end_date}_{limit}_{data_source}"
    
    # Check cache first - simple exact match
    if cached_data := _cache.get_company_news(cache_key):
        return [CompanyNews(**news) for news in cached_data]

    all_news = []
    
    if data_source == "finnhub":
        # Use Finnhub API - Company News
        finnhub_api_key = api_key or os.environ.get("FINNHUB_API_KEY")
        if not finnhub_api_key:
            raise ValueError("FINNHUB_API_KEY is required. Please set it in your .env file.")
        
        client = finnhub.Client(api_key=finnhub_api_key)
        
        # Finnhub API: company_news(symbol, _from, to)
        # Convert date format if needed
        from_date = start_date if start_date else (datetime.datetime.strptime(end_date, "%Y-%m-%d") - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
        
        try:
            news_data = client.company_news(ticker, _from=from_date, to=end_date)
            
            if news_data:
                # Convert Finnhub format to CompanyNews format
                for news_item in news_data[:limit]:  # Limit results
                    company_news = CompanyNews(
                        ticker=ticker,
                        title=news_item.get('headline', ''),
                        author=None,  # Finnhub doesn't provide author
                        source=news_item.get('source', ''),
                        date=datetime.datetime.fromtimestamp(news_item.get('datetime', 0)).strftime("%Y-%m-%d") if news_item.get('datetime') else None,
                        url=news_item.get('url', ''),
                        sentiment=None  # Could be added later if needed
                    )
                    all_news.append(company_news)
        except Exception as e:
            # Finnhub may not have data for all tickers
            print(f"Warning: Finnhub company news error for {ticker}: {e}")
            return []
    
    elif data_source == "financial_datasets":
        # Use Financial Datasets API
        headers = {}
        financial_api_key = api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY")
        if financial_api_key:
            headers["X-API-KEY"] = financial_api_key

        current_end_date = end_date

        while True:
            url = f"https://api.financialdatasets.ai/news/?ticker={ticker}&end_date={current_end_date}"
            if start_date:
                url += f"&start_date={start_date}"
            url += f"&limit={limit}"

            response = _make_api_request(url, headers)
            if response.status_code != 200:
                raise Exception(f"Error fetching data: {ticker} - {response.status_code} - {response.text}")

            data = response.json()
            response_model = CompanyNewsResponse(**data)
            company_news = response_model.news

            if not company_news:
                break

            all_news.extend(company_news)

            # Only continue pagination if we have a start_date and got a full page
            if not start_date or len(company_news) < limit:
                break

            # Update end_date to the oldest date from current batch for next iteration
            current_end_date = min(news.date for news in company_news).split("T")[0]

            # If we've reached or passed the start_date, we can stop
            if current_end_date <= start_date:
                break
    
    else:
        raise ValueError(f"Invalid data_source: {data_source}. Must be 'finnhub' or 'financial_datasets'")

    if not all_news:
        return []

    # Cache the results using the comprehensive cache key
    _cache.set_company_news(cache_key, [news.model_dump() for news in all_news])
    return all_news


def get_market_cap(
    ticker: str,
    end_date: str,
    api_key: str = None,
) -> float | None:
    """Fetch market cap from the API."""
    # Check if end_date is today
    if end_date == datetime.datetime.now().strftime("%Y-%m-%d"):
        # Get the market cap from company facts API
        headers = {}
        financial_api_key = api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY")
        if financial_api_key:
            headers["X-API-KEY"] = financial_api_key

        url = f"https://api.financialdatasets.ai/company/facts/?ticker={ticker}"
        response = _make_api_request(url, headers)
        if response.status_code != 200:
            print(f"Error fetching company facts: {ticker} - {response.status_code}")
            return None

        data = response.json()
        response_model = CompanyFactsResponse(**data)
        return response_model.company_facts.market_cap

    financial_metrics = get_financial_metrics(ticker, end_date, api_key=api_key)
    if not financial_metrics:
        return None

    market_cap = financial_metrics[0].market_cap

    if not market_cap:
        return None

    return market_cap


def prices_to_df(prices: list[Price]) -> pd.DataFrame:
    """Convert prices to a DataFrame."""
    df = pd.DataFrame([p.model_dump() for p in prices])
    df["Date"] = pd.to_datetime(df["time"])
    df.set_index("Date", inplace=True)
    numeric_cols = ["open", "close", "high", "low", "volume"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df.sort_index(inplace=True)
    return df


# Update the get_price_data function to use the new functions
def get_price_data(ticker: str, start_date: str, end_date: str, api_key: str = None) -> pd.DataFrame:
    prices = get_prices(ticker, start_date, end_date, api_key=api_key)
    return prices_to_df(prices)
