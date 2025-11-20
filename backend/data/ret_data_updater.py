#!/usr/bin/env python3
"""
Automatic Incremental Historical Data Update Module

Features:
1. Fetch stock historical data from Finnhub API
2. Incrementally update CSV files in ret_data directory
3. Automatically detect last update date, only download new data
4. Calculate returns (ret)
5. Support batch updates for multiple stocks
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import logging
from typing import List, Optional, Dict
from dotenv import load_dotenv

# Try importing US trading calendar packages
try:
    import pandas_market_calendars as mcal
except ImportError:
    mcal = None

try:
    import exchange_calendars as xcals
except ImportError:
    xcals = None

# Add project root directory to path
BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


class DataUpdater:
    """Data updater"""
    
    def __init__(
        self, 
        api_key: str,
        data_dir: str = None,
        start_date: str = "2022-01-01"
    ):
        """
        Initialize data updater
        
        Args:
            api_key: Finnhub API key
            data_dir: Data storage directory, defaults to backend/data/ret_data
            start_date: Historical data start date (YYYY-MM-DD)
        """
        self.api_key = api_key
        
        # Set data directory
        if data_dir is None:
            self.data_dir = BASE_DIR / "backend" / "data" / "ret_data"
        else:
            self.data_dir = Path(data_dir)
        
        # Ensure directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.start_date = start_date
        
        # Lazy import finnhub (avoid errors if not installed)
        try:
            import finnhub
            self.finnhub = finnhub
            self.client = finnhub.Client(api_key=api_key)
            logger.info("✅ Finnhub client initialized successfully")
        except ImportError:
            logger.error("❌ finnhub-python package not installed, please run: pip install finnhub-python")
            raise
    
    def get_trading_dates(self, start_date: str, end_date: str) -> List[str]:
        """
        Get US stock market trading date sequence (same as main program)
        
        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            List of trading dates
        """
        try:
            # Priority: use pandas_market_calendars
            if mcal is not None:
                nyse = mcal.get_calendar('NYSE')
                trading_dates = nyse.valid_days(start_date=start_date, end_date=end_date)
                return [date.strftime("%Y-%m-%d") for date in trading_dates]
            
            # Alternative: use exchange_calendars
            elif xcals is not None:
                nyse = xcals.get_calendar('XNYS')  # NYSE ISO code
                trading_dates = nyse.sessions_in_range(start_date, end_date)
                return [date.strftime("%Y-%m-%d") for date in trading_dates]
                
        except Exception as e:
            logger.warning(f"⚠️ Failed to get US trading calendar, falling back to simple business days: {e}")
       
        # Fallback to simple business day method
        date_range = pd.date_range(start_date, end_date, freq="B")
        return [date.strftime("%Y-%m-%d") for date in date_range]
    
    def get_last_date_from_csv(self, ticker: str) -> Optional[datetime]:
        """
        Get last data date from CSV file
        
        Args:
            ticker: Stock ticker
            
        Returns:
            datetime object of last date, or None if file doesn't exist
        """
        csv_path = self.data_dir / f"{ticker}.csv"
        
        if not csv_path.exists():
            logger.info(f"📂 {ticker}.csv does not exist, will create new file")
            return None
        
        try:
            df = pd.read_csv(csv_path)
            if df.empty or 'time' not in df.columns:
                return None
            
            # Get last row date
            last_date_str = df['time'].iloc[-1]
            last_date = datetime.strptime(last_date_str, '%Y-%m-%d')
            logger.info(f"📅 {ticker} last data date: {last_date_str}")
            return last_date
        except Exception as e:
            logger.warning(f"⚠️ Failed to read {ticker}.csv: {e}")
            return None
    
    def fetch_data_from_api(
        self, 
        ticker: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> Optional[pd.DataFrame]:
        """
        Fetch data from Finnhub API
        
        Args:
            ticker: Stock ticker
            start_date: Start date
            end_date: End date
            
        Returns:
            DataFrame or None
        """
        try:
            start_timestamp = int(start_date.timestamp())
            end_timestamp = int(end_date.timestamp())
            
            logger.info(f"🔄 Fetching {ticker} data: {start_date.date()} to {end_date.date()}")
            
            # Call API
            data = self.client.stock_candles(
                ticker, 
                'D',  # Daily data
                start_timestamp, 
                end_timestamp
            )
            
            # Check return status
            if data.get('s') != 'ok':
                logger.warning(f"⚠️ {ticker} API returned abnormal status: {data.get('s')}")
                return None
            
            # Convert to DataFrame
            df = pd.DataFrame(data)
            
            # Rename columns
            df = df.rename(columns={
                'o': 'open',
                'c': 'close',
                'h': 'high',
                'l': 'low',
                'v': 'volume',
                't': 'timestamp'
            })
            
            # Convert timestamp
            df['Date'] = pd.to_datetime(df['timestamp'], unit='s', utc=True)
            df['time'] = df['Date'].dt.strftime('%Y-%m-%d')
            
            # Calculate returns (next day return)
            df['ret'] = df['close'].pct_change().shift(-1)
            
            # Select needed columns
            df = df[['open', 'close', 'high', 'low', 'volume', 'time', 'ret']]
            
            logger.info(f"✅ Successfully fetched {ticker} data: {len(df)} records")
            return df
            
        except Exception as e:
            logger.error(f"❌ Failed to fetch {ticker} data: {e}")
            return None
    
    def merge_and_save(
        self, 
        ticker: str, 
        new_data: pd.DataFrame
    ) -> bool:
        """
        Merge old and new data and save
        
        Args:
            ticker: Stock ticker
            new_data: New data DataFrame
            
        Returns:
            Whether successful
        """
        csv_path = self.data_dir / f"{ticker}.csv"
        
        try:
            if csv_path.exists():
                # Read existing data
                old_data = pd.read_csv(csv_path)
                logger.info(f"📊 {ticker} existing data: {len(old_data)} records")
                
                # Merge data (deduplicate)
                combined = pd.concat([old_data, new_data], ignore_index=True)
                combined = combined.drop_duplicates(subset=['time'], keep='last')
                combined = combined.sort_values('time').reset_index(drop=True)
                
                # Recalculate returns (ensure continuity)
                combined['ret'] = combined['close'].pct_change().shift(-1)
                
                logger.info(f"📊 {ticker} merged data: {len(combined)} records")
            else:
                combined = new_data
                logger.info(f"📊 {ticker} new file: {len(combined)} records")
            
            # Fill missing dates (for trading days)
            combined = self._fill_missing_dates(ticker, combined)
            
            # Save to CSV
            combined.to_csv(csv_path, index=False)
            logger.info(f"💾 {ticker} data saved to: {csv_path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to save {ticker} data: {e}")
            return False
    
    def _fill_missing_dates(self, ticker: str, df: pd.DataFrame) -> pd.DataFrame:
        """
        Fill missing trading dates with forward fill method
        
        Args:
            ticker: Stock ticker
            df: DataFrame with time column
            
        Returns:
            DataFrame with filled dates
        """
        if df.empty or 'time' not in df.columns:
            return df
        
        try:
            # Convert time to datetime
            df['time'] = pd.to_datetime(df['time'])
            
            # Get date range
            start_date = df['time'].min().strftime('%Y-%m-%d')
            end_date = df['time'].max().strftime('%Y-%m-%d')
            
            # Get all trading dates using the same method as main program
            all_trading_dates_str = self.get_trading_dates(start_date, end_date)
            all_trading_dates = pd.to_datetime(all_trading_dates_str)
            
            # Find missing dates
            existing_dates = set(df['time'].dt.date)
            missing_dates = [d for d in all_trading_dates if d.date() not in existing_dates]
            
            if missing_dates:
                logger.warning(f"⚠️ {ticker} found {len(missing_dates)} missing trading days: {[str(d.date()) for d in missing_dates[:5]]}")
                
                # Set time as index for reindexing
                df = df.set_index('time')
                
                # Reindex to include all trading days
                df = df.reindex(all_trading_dates)
                
                # Forward fill prices (use previous day's close as current day's prices)
                df['close'] = df['close'].ffill()
                df['open'] = df['open'].fillna(df['close'])
                df['high'] = df['high'].fillna(df['close'])
                df['low'] = df['low'].fillna(df['close'])
                df['volume'] = df['volume'].fillna(0)
                
                # Recalculate returns
                df['ret'] = df['close'].pct_change().shift(-1)
                
                # Reset index
                df = df.reset_index()
                df = df.rename(columns={'index': 'time'})
                
                logger.info(f"✅ {ticker} filled {len(missing_dates)} missing dates")
            
            # Convert time back to string format
            df['time'] = df['time'].dt.strftime('%Y-%m-%d')
            
            return df
            
        except Exception as e:
            logger.error(f"❌ Failed to fill missing dates for {ticker}: {e}")
            return df
    
    def update_ticker(
        self, 
        ticker: str, 
        force_full_update: bool = False
    ) -> bool:
        """
        Update data for a single stock
        
        Args:
            ticker: Stock ticker
            force_full_update: Whether to force full update
            
        Returns:
            Whether successful
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"📈 Starting update for {ticker}")
        logger.info(f"{'='*60}")
        
        # Determine start date
        if force_full_update:
            start_date = datetime.strptime(self.start_date, '%Y-%m-%d')
            logger.info(f"🔄 Force full update, start date: {start_date.date()}")
        else:
            last_date = self.get_last_date_from_csv(ticker)
            if last_date:
                # Start update from day after last date
                start_date = last_date + timedelta(days=1)
                logger.info(f"📅 Incremental update, start date: {start_date.date()}")
            else:
                start_date = datetime.strptime(self.start_date, '%Y-%m-%d')
                logger.info(f"📅 First update, start date: {start_date.date()}")
        
        # End date is today
        end_date = datetime.now()
        
        # Check if update is needed
        if start_date.date() >= end_date.date():
            logger.info(f"✅ {ticker} data is up to date, no update needed")
            return True
        
        # Fetch new data
        new_data = self.fetch_data_from_api(ticker, start_date, end_date)
        
        if new_data is None or new_data.empty:
            # Check if it's weekend or recent date (may be data delay)
            days_diff = (end_date - start_date).days
            if days_diff <= 3:  # If only 1-3 days difference, may be weekend or data delay
                logger.info(f"ℹ️ {ticker} has no new data (may be weekend/holiday/data delay), existing data is sufficient")
                return True  # Return success to let script continue
            else:
                logger.warning(f"⚠️ {ticker} has no new data")
                return False
        
        # Merge and save
        success = self.merge_and_save(ticker, new_data)
        
        if success:
            logger.info(f"✅ {ticker} update completed")
        else:
            logger.error(f"❌ {ticker} update failed")
        
        return success
    
    def update_all_tickers(
        self, 
        tickers: List[str], 
        force_full_update: bool = False
    ) -> Dict[str, bool]:
        """
        Batch update multiple stocks
        
        Args:
            tickers: Stock ticker list
            force_full_update: Whether to force full update
            
        Returns:
            Update results dictionary {ticker: success}
        """
        results = {}
        
        logger.info(f"\n{'='*60}")
        logger.info(f"🚀 Starting batch update for {len(tickers)} stocks")
        logger.info(f"📋 Stock list: {', '.join(tickers)}")
        logger.info(f"{'='*60}\n")
        
        for i, ticker in enumerate(tickers, 1):
            logger.info(f"\n[{i}/{len(tickers)}] Processing {ticker}")
            results[ticker] = self.update_ticker(ticker, force_full_update)
            
            # API rate limiting (Finnhub free tier has limits)
            if i < len(tickers):
                import time
                time.sleep(1)  # 1 second interval between requests
        
        # Print summary
        logger.info(f"\n{'='*60}")
        logger.info(f"📊 Update Summary")
        logger.info(f"{'='*60}")
        
        success_count = sum(results.values())
        fail_count = len(results) - success_count
        
        logger.info(f"✅ Success: {success_count}")
        logger.info(f"❌ Failed: {fail_count}")
        
        if fail_count > 0:
            failed_tickers = [t for t, s in results.items() if not s]
            logger.warning(f"Failed stocks: {', '.join(failed_tickers)}")
        
        logger.info(f"{'='*60}\n")
        
        return results


def main():
    """Command line entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Automatically update stock historical data')
    parser.add_argument(
        '--tickers',
        type=str,
        help='Stock ticker list (comma-separated), e.g.: AAPL,MSFT,GOOGL'
    )
    parser.add_argument(
        '--api-key',
        type=str,
        help='Finnhub API Key (can also be set via FINNHUB_API_KEY environment variable)'
    )
    parser.add_argument(
        '--data-dir',
        type=str,
        help='Data storage directory (default: backend/data/ret_data)'
    )
    parser.add_argument(
        '--start-date',
        type=str,
        default='2022-01-01',
        help='Historical data start date (YYYY-MM-DD, default: 2022-01-01)'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force full update (re-download all data)'
    )
    
    args = parser.parse_args()
    
    # Load environment variables
    load_dotenv()
    
    # Get API Key
    api_key = args.api_key or os.getenv('FINNHUB_API_KEY')
    if not api_key:
        logger.error("❌ Finnhub API Key not provided")
        logger.error("   Please set via --api-key parameter or FINNHUB_API_KEY environment variable")
        sys.exit(1)
    
    # Get stock list
    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(',')]
    else:
        # Read from environment variable
        tickers_env = os.getenv('TICKERS', '')
        if tickers_env:
            tickers = [t.strip().upper() for t in tickers_env.split(',')]
        else:
            logger.error("❌ Stock list not provided")
            logger.error("   Please set via --tickers parameter or TICKERS environment variable")
            sys.exit(1)
    
    # Create updater
    updater = DataUpdater(
        api_key=api_key,
        data_dir=args.data_dir,
        start_date=args.start_date
    )
    
    # Execute update
    results = updater.update_all_tickers(tickers, force_full_update=args.force)
    
    # Return status code
    success_count = sum(results.values())
    if success_count == len(results):
        logger.info("🎉 All stocks updated successfully!")
        sys.exit(0)
    elif success_count == 0:
        # All stocks failed, may be weekend/holiday
        logger.warning("⚠️ All stocks have no new data (may be weekend/holiday), will use existing data")
        logger.info("💡 Note: System will continue running")
        sys.exit(0)  # Return success to let server continue starting
    else:
        # Partial success partial failure
        logger.warning("⚠️ Some stocks failed to update, but will continue running")
        sys.exit(0)  # Return success to let server continue starting


if __name__ == '__main__':
    main()

