#!/usr/bin/env python3
"""
独立测试get_prices函数的脚本
用于诊断API数据获取问题
"""

import os
import sys
import traceback
from datetime import datetime

# 添加src路径以便导入模块
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

def test_api_connection():
    """测试基本的API连接"""
    import requests
    
    print("=== 测试API连接 ===")
    
    # 检查环境变量
    api_key = os.environ.get("FINANCIAL_DATASETS_API_KEY")
    print(f"API Key配置: {'已设置' if api_key else '未设置'}")
    if api_key:
        print(f"API Key前6位: {api_key[:6]}...")
    
    # 测试基本连接
    headers = {}
    if api_key:
        headers["X-API-KEY"] = api_key
    
    test_url = "https://api.financialdatasets.ai/prices/?ticker=AAPL&interval=day&interval_multiplier=1&start_date=2024-01-01&end_date=2024-01-02"
    
    try:
        print(f"\n尝试连接: {test_url}")
        response = requests.get(test_url, headers=headers, timeout=30)
        print(f"响应状态码: {response.status_code}")
        print(f"响应头: {dict(response.headers)}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"响应数据类型: {type(data)}")
            print(f"数据键: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
            if isinstance(data, dict) and 'prices' in data:
                prices = data['prices']
                print(f"价格数据数量: {len(prices) if prices else 0}")
                if prices:
                    print(f"第一条价格数据: {prices[0]}")
        else:
            print(f"错误响应: {response.text}")
            
    except Exception as e:
        print(f"连接失败: {str(e)}")
        traceback.print_exc()
    
    print()

def test_get_prices_function():
    """测试get_prices函数"""
    print("=== 测试get_prices函数 ===")
    
    try:
        from src.tools.api import get_prices
        from src.data.models import Price
        
        print("成功导入get_prices函数")
        
        # 测试参数
        test_cases = [
            {
                "ticker": "AAPL", 
                "start_date": "2024-01-01", 
                "end_date": "2024-01-02",
                "description": "AAPL (免费股票)"
            },
            {
                "ticker": "MSFT", 
                "start_date": "2024-01-01", 
                "end_date": "2024-01-02",
                "description": "MSFT (免费股票)"
            },
            {
                "ticker": "GOOGL", 
                "start_date": "2024-01-01", 
                "end_date": "2024-01-02",
                "description": "GOOGL (免费股票)"
            }
        ]
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n--- 测试用例 {i}: {test_case['description']} ---")
            
            try:
                prices = get_prices(
                    ticker=test_case["ticker"],
                    start_date=test_case["start_date"],
                    end_date=test_case["end_date"]
                )
                
                print(f"返回类型: {type(prices)}")
                print(f"数据数量: {len(prices) if prices else 0}")
                
                if prices:
                    first_price = prices[0]
                    print(f"第一条数据类型: {type(first_price)}")
                    print(f"第一条数据: {first_price}")
                    
                    if hasattr(first_price, 'model_dump'):
                        print(f"模型数据: {first_price.model_dump()}")
                        
                    # 尝试转换为DataFrame
                    try:
                        from src.tools.api import prices_to_df
                        df = prices_to_df(prices)
                        print(f"DataFrame形状: {df.shape}")
                        print(f"DataFrame列: {list(df.columns)}")
                        if not df.empty:
                            print(f"最新价格: {df['close'].iloc[-1]}")
                    except Exception as df_error:
                        print(f"DataFrame转换失败: {str(df_error)}")
                        
                else:
                    print("❌ 未获取到价格数据")
                    
            except Exception as e:
                print(f"❌ 测试失败: {str(e)}")
                traceback.print_exc()
    
    except ImportError as e:
        print(f"❌ 导入失败: {str(e)}")
        traceback.print_exc()
    
    print()

def test_cache_functionality():
    """测试缓存功能"""
    print("=== 测试缓存功能 ===")
    
    try:
        from src.data.cache import get_cache
        
        cache = get_cache()
        print(f"缓存类型: {type(cache)}")
        
        # 测试缓存读写
        test_key = "test_AAPL_2024-01-01_2024-01-02"
        test_data = [{"date": "2024-01-01", "close": 192.53}]
        
        # 写入缓存
        cache.set_prices(test_key, test_data)
        print("写入测试数据到缓存")
        
        # 读取缓存
        cached_data = cache.get_prices(test_key)
        print(f"从缓存读取: {cached_data}")
        
    except Exception as e:
        print(f"❌ 缓存测试失败: {str(e)}")
        traceback.print_exc()
    
    print()

def test_risk_manager_data_flow():
    """测试风险管理代理的数据流"""
    print("=== 测试风险管理代理数据流 ===")
    
    try:
        from src.tools.api import get_prices, prices_to_df
        
        ticker = "AAPL"
        start_date = "2024-01-01"
        end_date = "2024-01-02"
        
        print(f"模拟风险管理代理获取 {ticker} 价格数据...")
        
        # 步骤1: 获取价格
        prices = get_prices(ticker=ticker, start_date=start_date, end_date=end_date)
        print(f"获取到价格数据: {len(prices) if prices else 0} 条")
        
        if not prices:
            print(f"❌ 无价格数据 -> current_price = 0")
            print(f"❌ 无价格数据 -> remaining_position_limit = 0")
            return
        
        # 步骤2: 转换为DataFrame
        prices_df = prices_to_df(prices)
        print(f"DataFrame转换成功: {prices_df.shape}")
        
        if not prices_df.empty and len(prices_df) >= 1:
            current_price = prices_df["close"].iloc[-1]
            print(f"✅ 当前价格: {current_price}")
            
            # 步骤3: 模拟仓位限制计算
            total_portfolio_value = 100000  # 假设10万美元组合
            vol_adjusted_limit = 0.05  # 5%的仓位限制
            position_limit = total_portfolio_value * vol_adjusted_limit
            
            if current_price > 0:
                max_shares = int(position_limit / current_price)
                print(f"✅ 仓位限制: ${position_limit:.2f}")
                print(f"✅ 最大股数: {max_shares}")
            else:
                print(f"❌ 价格为0 -> max_shares = 0")
        else:
            print(f"❌ DataFrame为空或数据不足")
            
    except Exception as e:
        print(f"❌ 数据流测试失败: {str(e)}")
        traceback.print_exc()
    
    print()

def main():
    """主测试函数"""
    print("Portfolio Manager价格数据获取测试")
    print("=" * 50)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"当前工作目录: {os.getcwd()}")
    print(f"Python路径: {sys.path[:3]}...")
    print()
    
    # 运行所有测试
    test_api_connection()
    test_get_prices_function()
    test_cache_functionality()
    test_risk_manager_data_flow()
    
    print("=" * 50)
    print("测试完成")

if __name__ == "__main__":
    main()
