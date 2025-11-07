#!/usr/bin/env python3
"""
测试价格更新逻辑
验证更新 holdings.json 和 stats.json 的功能是否正常
"""
import json
from pathlib import Path

def test_price_update():
    """测试价格更新逻辑"""
    
    # 模拟文件路径
    test_dir = Path("./test_dashboard")
    test_dir.mkdir(exist_ok=True)
    
    holdings_file = test_dir / "holdings.json"
    stats_file = test_dir / "stats.json"
    
    # 创建初始数据
    initial_holdings = [
        {
            "ticker": "CASH",
            "quantity": 1,
            "currentPrice": 38621.27,
            "marketValue": 38621.27,
            "weight": 0.3793
        },
        {
            "ticker": "AMZN",
            "quantity": 159,
            "currentPrice": 220.66,
            "marketValue": 35084.94,
            "weight": 0.3446
        },
        {
            "ticker": "META",
            "quantity": 46,
            "currentPrice": 611.3,
            "marketValue": 28119.8,
            "weight": 0.2762
        }
    ]
    
    initial_stats = {
        "totalAssetValue": 101826.01,
        "totalReturn": 1.83,
        "cashPosition": 38621.27,
        "tickerWeights": {
            "META": 0.2762,
            "AMZN": 0.3446
        },
        "totalTrades": 4,
        "winRate": 0.75,
        "bullBear": {
            "bull": {"n": 3, "win": 2},
            "bear": {"n": 1, "win": 1}
        }
    }
    
    # 保存初始数据
    with open(holdings_file, 'w', encoding='utf-8') as f:
        json.dump(initial_holdings, f, indent=2, ensure_ascii=False)
    
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump(initial_stats, f, indent=2, ensure_ascii=False)
    
    print("✅ 初始数据已创建")
    print(f"   AMZN 初始价格: ${initial_holdings[1]['currentPrice']:.2f}")
    print(f"   总资产价值: ${initial_stats['totalAssetValue']:.2f}")
    print(f"   总收益率: {initial_stats['totalReturn']:.2f}%")
    print()
    
    # 模拟价格更新
    symbol = "AMZN"
    new_price = 225.50  # 价格上涨
    initial_cash = 100000.0
    
    print(f"🔄 模拟更新 {symbol} 价格: ${new_price:.2f}")
    
    # 读取 holdings.json
    with open(holdings_file, 'r', encoding='utf-8') as f:
        holdings = json.load(f)
    
    # 读取 stats.json
    with open(stats_file, 'r', encoding='utf-8') as f:
        stats = json.load(f)
    
    # 更新 holdings 中的价格
    updated = False
    total_value = 0.0
    cash = 0.0
    
    for holding in holdings:
        ticker = holding.get('ticker')
        quantity = holding.get('quantity', 0)
        
        if ticker == 'CASH':
            cash = holding.get('currentPrice', 0)
            total_value += cash
        elif ticker == symbol:
            # 更新当前价格
            holding['currentPrice'] = round(new_price, 2)
            market_value = quantity * new_price
            holding['marketValue'] = round(market_value, 2)
            total_value += market_value
            updated = True
        else:
            # 累加其他持仓的市值
            total_value += holding.get('marketValue', 0)
    
    # 重新计算权重
    if total_value > 0:
        for holding in holdings:
            market_value = holding.get('marketValue', 0)
            weight = market_value / total_value
            holding['weight'] = round(weight, 4)
    
    # 保存 holdings.json
    if updated:
        with open(holdings_file, 'w', encoding='utf-8') as f:
            json.dump(holdings, f, indent=2, ensure_ascii=False)
        print(f"✅ 已更新 holdings.json")
    
    # 更新 stats.json
    total_return = ((total_value - initial_cash) / initial_cash * 100) if initial_cash > 0 else 0.0
    
    # 更新 tickerWeights
    ticker_weights = {}
    for holding in holdings:
        ticker = holding.get('ticker')
        if ticker != 'CASH':
            ticker_weights[ticker] = holding.get('weight', 0)
    
    stats['totalAssetValue'] = round(total_value, 2)
    stats['totalReturn'] = round(total_return, 2)
    stats['cashPosition'] = round(cash, 2)
    stats['tickerWeights'] = ticker_weights
    
    # 保存 stats.json
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    print(f"✅ 已更新 stats.json")
    print()
    
    # 验证结果
    print("📊 更新后的结果:")
    for holding in holdings:
        ticker = holding.get('ticker')
        if ticker == symbol:
            print(f"   {ticker}:")
            print(f"     - 数量: {holding['quantity']}")
            print(f"     - 当前价格: ${holding['currentPrice']:.2f}")
            print(f"     - 市值: ${holding['marketValue']:.2f}")
            print(f"     - 权重: {holding['weight']:.2%}")
    
    print(f"\n   总资产价值: ${stats['totalAssetValue']:.2f}")
    print(f"   总收益率: {stats['totalReturn']:.2f}%")
    print(f"   现金仓位: ${stats['cashPosition']:.2f}")
    print()
    
    # 计算变化
    old_total = initial_stats['totalAssetValue']
    new_total = stats['totalAssetValue']
    change = new_total - old_total
    change_pct = (change / old_total * 100) if old_total > 0 else 0
    
    print(f"💰 变化:")
    print(f"   总资产变化: ${change:+.2f} ({change_pct:+.2f}%)")
    print(f"   收益率变化: {stats['totalReturn'] - initial_stats['totalReturn']:+.2f}%")
    print()
    
    print("✅ 测试完成！")
    print(f"   测试文件位置: {test_dir}")
    print(f"   请检查 {holdings_file.name} 和 {stats_file.name}")

if __name__ == "__main__":
    test_price_update()

