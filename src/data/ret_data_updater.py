#!/usr/bin/env python3
"""
自动增量更新历史数据模块

功能:
1. 从 Finnhub API 获取股票历史数据
2. 增量更新 ret_data 目录中的 CSV 文件
3. 自动检测最后更新日期,只下载新数据
4. 计算收益率 (ret)
5. 支持批量更新多个股票
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import logging
from typing import List, Optional, Dict
from dotenv import load_dotenv

# 添加项目根目录到路径
BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


class DataUpdater:
    """数据更新器"""
    
    def __init__(
        self, 
        api_key: str,
        data_dir: str = None,
        start_date: str = "2022-01-01"
    ):
        """
        初始化数据更新器
        
        Args:
            api_key: Finnhub API key
            data_dir: 数据存储目录,默认为 src/data/ret_data
            start_date: 历史数据起始日期 (YYYY-MM-DD)
        """
        self.api_key = api_key
        
        # 设置数据目录
        if data_dir is None:
            self.data_dir = BASE_DIR / "src" / "data" / "ret_data"
        else:
            self.data_dir = Path(data_dir)
        
        # 确保目录存在
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.start_date = start_date
        
        # 延迟导入 finnhub (避免在没有安装时报错)
        try:
            import finnhub
            self.finnhub = finnhub
            self.client = finnhub.Client(api_key=api_key)
            logger.info("✅ Finnhub 客户端初始化成功")
        except ImportError:
            logger.error("❌ 未安装 finnhub-python 包,请运行: pip install finnhub-python")
            raise
    
    def get_last_date_from_csv(self, ticker: str) -> Optional[datetime]:
        """
        从 CSV 文件中获取最后一条数据的日期
        
        Args:
            ticker: 股票代码
            
        Returns:
            最后日期的 datetime 对象,如果文件不存在返回 None
        """
        csv_path = self.data_dir / f"{ticker}.csv"
        
        if not csv_path.exists():
            logger.info(f"📂 {ticker}.csv 不存在,将创建新文件")
            return None
        
        try:
            df = pd.read_csv(csv_path)
            if df.empty or 'time' not in df.columns:
                return None
            
            # 获取最后一行的日期
            last_date_str = df['time'].iloc[-1]
            last_date = datetime.strptime(last_date_str, '%Y-%m-%d')
            logger.info(f"📅 {ticker} 最后数据日期: {last_date_str}")
            return last_date
        except Exception as e:
            logger.warning(f"⚠️ 读取 {ticker}.csv 失败: {e}")
            return None
    
    def fetch_data_from_api(
        self, 
        ticker: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> Optional[pd.DataFrame]:
        """
        从 Finnhub API 获取数据
        
        Args:
            ticker: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            DataFrame 或 None
        """
        try:
            start_timestamp = int(start_date.timestamp())
            end_timestamp = int(end_date.timestamp())
            
            logger.info(f"🔄 正在获取 {ticker} 数据: {start_date.date()} 到 {end_date.date()}")
            
            # 调用 API
            data = self.client.stock_candles(
                ticker, 
                'D',  # 日线数据
                start_timestamp, 
                end_timestamp
            )
            
            # 检查返回状态
            if data.get('s') != 'ok':
                logger.warning(f"⚠️ {ticker} API 返回状态异常: {data.get('s')}")
                return None
            
            # 转换为 DataFrame
            df = pd.DataFrame(data)
            
            # 重命名列
            df = df.rename(columns={
                'o': 'open',
                'c': 'close',
                'h': 'high',
                'l': 'low',
                'v': 'volume',
                't': 'timestamp'
            })
            
            # 转换时间戳
            df['Date'] = pd.to_datetime(df['timestamp'], unit='s', utc=True)
            df['time'] = df['Date'].dt.strftime('%Y-%m-%d')
            
            # 计算收益率 (下一日收益率)
            df['ret'] = df['close'].pct_change().shift(-1)
            
            # 选择需要的列
            df = df[['open', 'close', 'high', 'low', 'volume', 'time', 'ret']]
            
            logger.info(f"✅ 成功获取 {ticker} 数据: {len(df)} 条记录")
            return df
            
        except Exception as e:
            logger.error(f"❌ 获取 {ticker} 数据失败: {e}")
            return None
    
    def merge_and_save(
        self, 
        ticker: str, 
        new_data: pd.DataFrame
    ) -> bool:
        """
        合并新旧数据并保存
        
        Args:
            ticker: 股票代码
            new_data: 新数据 DataFrame
            
        Returns:
            是否成功
        """
        csv_path = self.data_dir / f"{ticker}.csv"
        
        try:
            if csv_path.exists():
                # 读取现有数据
                old_data = pd.read_csv(csv_path)
                logger.info(f"📊 {ticker} 现有数据: {len(old_data)} 条")
                
                # 合并数据 (去重)
                combined = pd.concat([old_data, new_data], ignore_index=True)
                combined = combined.drop_duplicates(subset=['time'], keep='last')
                combined = combined.sort_values('time').reset_index(drop=True)
                
                # 重新计算收益率 (确保连续性)
                combined['ret'] = combined['close'].pct_change().shift(-1)
                
                logger.info(f"📊 {ticker} 合并后数据: {len(combined)} 条")
            else:
                combined = new_data
                logger.info(f"📊 {ticker} 新建文件: {len(combined)} 条")
            
            # 保存到 CSV
            combined.to_csv(csv_path, index=False)
            logger.info(f"💾 {ticker} 数据已保存到: {csv_path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 保存 {ticker} 数据失败: {e}")
            return False
    
    def update_ticker(
        self, 
        ticker: str, 
        force_full_update: bool = False
    ) -> bool:
        """
        更新单个股票的数据
        
        Args:
            ticker: 股票代码
            force_full_update: 是否强制全量更新
            
        Returns:
            是否成功
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"📈 开始更新 {ticker}")
        logger.info(f"{'='*60}")
        
        # 确定起始日期
        if force_full_update:
            start_date = datetime.strptime(self.start_date, '%Y-%m-%d')
            logger.info(f"🔄 强制全量更新,起始日期: {start_date.date()}")
        else:
            last_date = self.get_last_date_from_csv(ticker)
            if last_date:
                # 从最后日期的下一天开始更新
                start_date = last_date + timedelta(days=1)
                logger.info(f"📅 增量更新,起始日期: {start_date.date()}")
            else:
                start_date = datetime.strptime(self.start_date, '%Y-%m-%d')
                logger.info(f"📅 首次更新,起始日期: {start_date.date()}")
        
        # 结束日期为今天
        end_date = datetime.now()
        
        # 检查是否需要更新
        if start_date.date() >= end_date.date():
            logger.info(f"✅ {ticker} 数据已是最新,无需更新")
            return True
        
        # 获取新数据
        new_data = self.fetch_data_from_api(ticker, start_date, end_date)
        
        if new_data is None or new_data.empty:
            # 检查是否是周末或最近的日期（可能是数据延迟）
            days_diff = (end_date - start_date).days
            if days_diff <= 3:  # 如果只差1-3天，可能是周末或数据延迟
                logger.info(f"ℹ️ {ticker} 暂无新数据 (可能是周末/假期/数据延迟)，现有数据已足够")
                return True  # 返回成功，让脚本继续
            else:
                logger.warning(f"⚠️ {ticker} 没有新数据")
                return False
        
        # 合并并保存
        success = self.merge_and_save(ticker, new_data)
        
        if success:
            logger.info(f"✅ {ticker} 更新完成")
        else:
            logger.error(f"❌ {ticker} 更新失败")
        
        return success
    
    def update_all_tickers(
        self, 
        tickers: List[str], 
        force_full_update: bool = False
    ) -> Dict[str, bool]:
        """
        批量更新多个股票
        
        Args:
            tickers: 股票代码列表
            force_full_update: 是否强制全量更新
            
        Returns:
            更新结果字典 {ticker: success}
        """
        results = {}
        
        logger.info(f"\n{'='*60}")
        logger.info(f"🚀 开始批量更新 {len(tickers)} 只股票")
        logger.info(f"📋 股票列表: {', '.join(tickers)}")
        logger.info(f"{'='*60}\n")
        
        for i, ticker in enumerate(tickers, 1):
            logger.info(f"\n[{i}/{len(tickers)}] 处理 {ticker}")
            results[ticker] = self.update_ticker(ticker, force_full_update)
            
            # API 限流 (Finnhub 免费版有限制)
            if i < len(tickers):
                import time
                time.sleep(1)  # 每次请求间隔 1 秒
        
        # 打印汇总
        logger.info(f"\n{'='*60}")
        logger.info(f"📊 更新汇总")
        logger.info(f"{'='*60}")
        
        success_count = sum(results.values())
        fail_count = len(results) - success_count
        
        logger.info(f"✅ 成功: {success_count}")
        logger.info(f"❌ 失败: {fail_count}")
        
        if fail_count > 0:
            failed_tickers = [t for t, s in results.items() if not s]
            logger.warning(f"失败的股票: {', '.join(failed_tickers)}")
        
        logger.info(f"{'='*60}\n")
        
        return results


def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='自动更新股票历史数据')
    parser.add_argument(
        '--tickers',
        type=str,
        help='股票代码列表 (逗号分隔),例如: AAPL,MSFT,GOOGL'
    )
    parser.add_argument(
        '--api-key',
        type=str,
        help='Finnhub API Key (也可通过 FINNHUB_API_KEY 环境变量设置)'
    )
    parser.add_argument(
        '--data-dir',
        type=str,
        help='数据存储目录 (默认: src/data/ret_data)'
    )
    parser.add_argument(
        '--start-date',
        type=str,
        default='2022-01-01',
        help='历史数据起始日期 (YYYY-MM-DD,默认: 2022-01-01)'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='强制全量更新 (重新下载所有数据)'
    )
    
    args = parser.parse_args()
    
    # 加载环境变量
    load_dotenv()
    
    # 获取 API Key
    api_key = args.api_key or os.getenv('FINNHUB_API_KEY')
    if not api_key:
        logger.error("❌ 未提供 Finnhub API Key")
        logger.error("   请通过 --api-key 参数或 FINNHUB_API_KEY 环境变量设置")
        sys.exit(1)
    
    # 获取股票列表
    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(',')]
    else:
        # 从环境变量读取
        tickers_env = os.getenv('TICKERS', '')
        if tickers_env:
            tickers = [t.strip().upper() for t in tickers_env.split(',')]
        else:
            logger.error("❌ 未提供股票列表")
            logger.error("   请通过 --tickers 参数或 TICKERS 环境变量设置")
            sys.exit(1)
    
    # 创建更新器
    updater = DataUpdater(
        api_key=api_key,
        data_dir=args.data_dir,
        start_date=args.start_date
    )
    
    # 执行更新
    results = updater.update_all_tickers(tickers, force_full_update=args.force)
    
    # 返回状态码
    success_count = sum(results.values())
    if success_count == len(results):
        logger.info("🎉 所有股票更新成功!")
        sys.exit(0)
    elif success_count == 0:
        # 所有股票都失败，可能是周末/假期
        logger.warning("⚠️ 所有股票都无新数据 (可能是周末/假期)，将使用现有数据")
        logger.info("💡 提示: 系统将继续运行")
        sys.exit(0)  # 返回成功，让服务器继续启动
    else:
        # 部分成功部分失败
        logger.warning("⚠️ 部分股票更新失败，但将继续运行")
        sys.exit(0)  # 返回成功，让服务器继续启动


if __name__ == '__main__':
    main()

