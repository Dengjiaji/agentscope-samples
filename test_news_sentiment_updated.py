#!/usr/bin/env python3
"""
测试更新后的 analyze_news_sentiment 工具
验证它能根据不同的API返回不同格式的数据
"""

import os
import json
from dotenv import load_dotenv
from src.tools.analysis_tools_unified import analyze_news_sentiment

# 加载环境变量
load_dotenv()

def print_section(title: str):
    """打印分隔线"""
    print("\n" + "=" * 80)
    print(f"🧪 {title}")
    print("=" * 80 + "\n")

def test_finnhub_api():
    """测试使用 Finnhub API 的情况"""
    print_section("测试 Finnhub API - 应返回新闻列表")
    
    ticker = "META"
    end_date = "2025-11-02"
    api_key = os.environ.get("FINNHUB_API_KEY")
    
    if not api_key:
        print("❌ FINNHUB_API_KEY 未配置")
        return
    
    print(f"📊 参数:")
    print(f"   股票: {ticker}")
    print(f"   结束日期: {end_date}")
    print(f"   API: Finnhub")
    
    result = analyze_news_sentiment(
        ticker=ticker,
        end_date=end_date,
        api_key=api_key,
        start_date=None
    )
    
    print(f"\n📋 返回结果:")
    print(f"   数据源: {result.get('data_source', 'unknown')}")
    print(f"   信号: {result.get('signal')}")
    
    if result.get('data_source') == 'finnhub':
        print(f"   总新闻数: {result.get('total_news_count')}")
        print(f"   返回新闻数: {len(result.get('news_list', []))}")
        
        print(f"\n📰 新闻列表:")
        for news in result.get('news_list', [])[:5]:  # 只显示前5条
            print(f"\n   [{news['index']}] {news['title']}")
            print(f"       来源: {news['source']}")
            print(f"       日期: {news['date']}")
            print(f"       链接: {news['url'][:60]}...")
        
        print(f"\n💡 详细信息:")
        for detail in result.get('details', []):
            print(f"   - {detail}")
        
        print(f"\n🔍 推理:")
        print(f"   {result.get('reasoning')}")
        
        print("\n✅ Finnhub API 测试通过 - 返回了新闻列表格式")
    else:
        print(f"\n⚠️  预期返回 finnhub 格式，但得到: {result.get('data_source')}")
        print(f"\n完整结果:")
        print(json.dumps(result, indent=2, ensure_ascii=False))

def test_financial_datasets_api():
    """测试使用 Financial Datasets API 的情况（如果有的话）"""
    print_section("测试 Financial Datasets API - 应返回情绪统计")
    
    api_key = os.environ.get("FINANCIAL_DATASETS_API_KEY")
    
    if not api_key:
        print("ℹ️  FINANCIAL_DATASETS_API_KEY 未配置，跳过此测试")
        print("   （这是正常的，如果你只使用 Finnhub API）")
        return
    
    ticker = "AAPL"
    end_date = "2025-11-02"
    
    print(f"📊 参数:")
    print(f"   股票: {ticker}")
    print(f"   结束日期: {end_date}")
    print(f"   API: Financial Datasets")
    
    # 注意：这里需要修改 get_company_news 的调用方式来指定 data_source
    # 目前的实现会自动检测，但我们可以通过结果来验证
    result = analyze_news_sentiment(
        ticker=ticker,
        end_date=end_date,
        api_key=api_key,
        start_date=None
    )
    
    print(f"\n📋 返回结果:")
    print(f"   数据源: {result.get('data_source', 'unknown')}")
    print(f"   信号: {result.get('signal')}")
    
    if result.get('data_source') == 'financial_datasets':
        metrics = result.get('metrics', {})
        print(f"\n📊 情绪统计:")
        print(f"   总新闻数: {metrics.get('total_articles')}")
        print(f"   正面新闻: {metrics.get('positive_articles')} ({metrics.get('positive_ratio')}%)")
        print(f"   负面新闻: {metrics.get('negative_articles')} ({metrics.get('negative_ratio')}%)")
        print(f"   中性新闻: {metrics.get('neutral_articles')} ({metrics.get('neutral_ratio')}%)")
        
        print(f"\n💡 详细信息:")
        for detail in result.get('details', []):
            print(f"   - {detail}")
        
        print(f"\n🔍 推理:")
        print(f"   {result.get('reasoning')}")
        
        print("\n✅ Financial Datasets API 测试通过 - 返回了统计格式")
    else:
        print(f"\n⚠️  预期返回 financial_datasets 格式，但得到: {result.get('data_source')}")
        print(f"\n完整结果:")
        print(json.dumps(result, indent=2, ensure_ascii=False))

def test_json_serialization():
    """测试返回结果是否可以正确序列化为JSON"""
    print_section("测试 JSON 序列化")
    
    ticker = "AMZN"
    end_date = "2025-11-02"
    api_key = os.environ.get("FINNHUB_API_KEY")
    
    if not api_key:
        print("❌ FINNHUB_API_KEY 未配置")
        return
    
    result = analyze_news_sentiment(
        ticker=ticker,
        end_date=end_date,
        api_key=api_key
    )
    
    try:
        json_str = json.dumps(result, indent=2, ensure_ascii=False)
        print("✅ JSON 序列化成功")
        print(f"\n📄 JSON 大小: {len(json_str)} 字符")
        print(f"\n前500个字符:")
        print(json_str[:500])
        print("...")
    except Exception as e:
        print(f"❌ JSON 序列化失败: {e}")

def main():
    """主测试函数"""
    print("\n" + "=" * 80)
    print("🚀 analyze_news_sentiment 工具更新测试")
    print("=" * 80)
    
    # 测试 Finnhub API
    test_finnhub_api()
    
    # 测试 Financial Datasets API（如果配置了）
    test_financial_datasets_api()
    
    # 测试 JSON 序列化
    test_json_serialization()
    
    print("\n" + "=" * 80)
    print("✅ 所有测试完成!")
    print("=" * 80)
    print("\n💡 总结:")
    print("   - Finnhub API: 返回新闻列表（标题、来源、日期、链接）")
    print("   - Financial Datasets API: 返回情绪统计（正面/负面/中性比例）")
    print("   - LLM 可以根据 data_source 字段判断如何处理数据")
    print()

if __name__ == "__main__":
    main()

