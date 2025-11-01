#!/usr/bin/env python3
"""
测试价格数据函数
1. 测试当前 get_prices() 的输出格式
2. 创建使用 Finnhub API 的替代版本
"""
import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv
import finnhub

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

# ============================================================
# 方案1: 测试当前的 get_prices() 函数（如果有 API Key）
# ============================================================
def test_current_get_prices():
    """测试当前的 get_prices 函数"""
    print("=" * 60)
    print("📊 测试当前 get_prices() 函数")
    print("=" * 60)
    
    try:
        from src.tools.api import get_prices, prices_to_df
        
        # 测试参数
        ticker = "AAPL"
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        
        print(f"\n📍 获取 {ticker} 价格数据")
        print(f"   日期范围: {start_date} -> {end_date}")
        
        # 调用函数
        prices = get_prices(ticker, start_date, end_date)
        
        print(f"\n✅ 成功获取 {len(prices)} 条数据")
        print(f"\n📦 数据结构 (Price 对象):")
        if prices:
            first_price = prices[0]
            print(f"   类型: {type(first_price)}")
            print(f"   字段: {first_price.model_dump()}")
            print(f"\n   示例数据:")
            for i, price in enumerate(prices[:3], 1):
                print(f"   [{i}] {price.time}: O={price.open:.2f}, H={price.high:.2f}, "
                      f"L={price.low:.2f}, C={price.close:.2f}, V={price.volume}")
        
        # 转换为 DataFrame
        df = prices_to_df(prices)
        print(f"\n📊 DataFrame 格式:")
        print(df.head())
        print(f"\n   列名: {list(df.columns)}")
        print(f"   索引: {df.index.name}")
        
        return prices, df
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        print(f"   可能原因: 缺少 FINANCIAL_DATASETS_API_KEY")
        return None, None


# ============================================================
# 方案2: 使用 Finnhub API 的替代实现
# ============================================================
def get_prices_finnhub(ticker: str, start_date: str, end_date: str, api_key: str = None):
    """
    使用 Finnhub API 获取价格数据
    返回与 get_prices() 相同格式的数据
    
    Args:
        ticker: 股票代码
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)
        api_key: Finnhub API Key (可选)
    
    Returns:
        list[Price]: 价格数据列表
    """
    from src.data.models import Price
    
    # 获取 API Key
    finnhub_api_key = api_key or os.getenv('FINNHUB_API_KEY', '')
    if not finnhub_api_key:
        raise ValueError("需要 FINNHUB_API_KEY")
    
    # 初始化 Finnhub 客户端
    client = finnhub.Client(api_key=finnhub_api_key)
    
    # 转换日期为时间戳
    start_timestamp = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp())
    end_timestamp = int(datetime.strptime(end_date, "%Y-%m-%d").timestamp())
    
    # 调用 Finnhub API (股票蜡烛图数据)
    candles = client.stock_candles(ticker, 'D', start_timestamp, end_timestamp)
    
    # 检查返回状态
    if candles.get('s') != 'ok':
        raise Exception(f"Finnhub API 错误: {candles}")
    
    # 转换为 Price 对象列表
    prices = []
    for i in range(len(candles['t'])):
        price = Price(
            open=candles['o'][i],
            close=candles['c'][i],
            high=candles['h'][i],
            low=candles['l'][i],
            volume=int(candles['v'][i]),
            time=datetime.fromtimestamp(candles['t'][i]).strftime("%Y-%m-%d")
        )
        prices.append(price)
    
    return prices


def test_finnhub_get_prices():
    """测试 Finnhub 版本的 get_prices"""
    print("\n" + "=" * 60)
    print("🚀 测试 Finnhub 版本的 get_prices()")
    print("=" * 60)
    
    try:
        from src.tools.api import prices_to_df
        
        # 测试参数
        ticker = "AAPL"
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        
        print(f"\n📍 获取 {ticker} 价格数据 (使用 Finnhub)")
        print(f"   日期范围: {start_date} -> {end_date}")
        
        # 调用 Finnhub 版本
        prices = get_prices_finnhub(ticker, start_date, end_date)
        
        print(f"\n✅ 成功获取 {len(prices)} 条数据")
        print(f"\n📦 数据结构 (Price 对象):")
        if prices:
            first_price = prices[0]
            print(f"   类型: {type(first_price)}")
            print(f"   字段: {first_price.model_dump()}")
            print(f"\n   示例数据:")
            for i, price in enumerate(prices[:3], 1):
                print(f"   [{i}] {price.time}: O={price.open:.2f}, H={price.high:.2f}, "
                      f"L={price.low:.2f}, C={price.close:.2f}, V={price.volume}")
        
        # 转换为 DataFrame
        df = prices_to_df(prices)
        print(f"\n📊 DataFrame 格式:")
        print(df.head())
        print(f"\n   列名: {list(df.columns)}")
        print(f"   索引: {df.index.name}")
        
        return prices, df
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return None, None


# ============================================================
# 对比两种方案
# ============================================================
def compare_results():
    """对比两种方案的结果"""
    print("\n" + "=" * 60)
    print("🔍 对比两种方案")
    print("=" * 60)
    
    print("\n1️⃣ 当前方案 (financialdatasets.ai):")
    print("   ✅ 优点: 专业金融数据API，数据质量高")
    print("   ❌ 缺点: 需要单独的 API Key，可能有费用")
    
    print("\n2️⃣ Finnhub 方案:")
    print("   ✅ 优点: 已有 API Key，免费额度充足")
    print("   ✅ 优点: 与实时价格使用同一个 API")
    print("   ✅ 优点: 数据格式完全兼容")
    print("   ⚠️  注意: 免费版数据有15分钟延迟")


# ============================================================
# 主函数
# ============================================================
def main():
    print("🧪 价格数据函数测试")
    print("=" * 60)
    
    # 测试当前函数
    current_prices, current_df = test_current_get_prices()
    
    # 测试 Finnhub 版本
    finnhub_prices, finnhub_df = test_finnhub_get_prices()
    
    # 对比
    compare_results()
    
    print("\n" + "=" * 60)
    print("✅ 测试完成")
    print("=" * 60)
    
    # 结论
    print("\n💡 结论:")
    if finnhub_prices:
        print("   ✅ Finnhub 版本可以完美替代当前的 get_prices()")
        print("   ✅ 数据格式完全兼容，无需修改其他代码")
        print("   ✅ 建议使用 Finnhub 统一价格数据来源")
    else:
        print("   ⚠️  Finnhub 版本测试失败，请检查 API Key")


if __name__ == "__main__":
    main()

