"""
测试 analyze_efficiency_ratios 工具
"""
import os
import sys

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.tools.analysis_tools_unified import analyze_efficiency_ratios

def test_efficiency_ratios():
    """测试效率比率分析工具"""
    
    # 获取API密钥 - 使用系统环境变量中的 FINANCIAL_DATASETS_API_KEY
    api_key = os.getenv("FINANCIAL_DATASETS_API_KEY")
    if not api_key:
        print("❌ 错误: 未找到 FINANCIAL_DATASETS_API_KEY 环境变量")
        print("   请确保在环境中设置了 FINANCIAL_DATASETS_API_KEY")
        return
    
    # 测试参数
    ticker = "AAPL"
    end_date = "2024-12-31"
    
    print(f"\n{'='*60}")
    print(f"测试 analyze_efficiency_ratios 工具")
    print(f"{'='*60}")
    print(f"股票代码: {ticker}")
    print(f"结束日期: {end_date}")
    print(f"{'='*60}\n")
    
    try:
        # 调用工具
        print("🔍 正在调用工具...")
        result = analyze_efficiency_ratios.invoke({
            "ticker": ticker,
            "end_date": end_date,
            "api_key": api_key
        })
        
        # 打印结果
        print("✅ 工具调用成功!\n")
        
        if "error" in result:
            print(f"⚠️  工具返回错误: {result['error']}")
            print(f"   信号: {result.get('signal', 'N/A')}")
        else:
            print(f"📊 分析结果:")
            print(f"   信号: {result.get('signal', 'N/A').upper()}")
            print(f"   推理: {result.get('reasoning', 'N/A')}")
            
            print(f"\n📈 效率指标:")
            metrics = result.get('metrics', {})
            for key, value in metrics.items():
                if value is not None:
                    print(f"   {key}: {value:.2f}")
                else:
                    print(f"   {key}: N/A")
            
            print(f"\n📝 详细信息:")
            details = result.get('details', [])
            for detail in details:
                print(f"   • {detail}")
        
        print(f"\n{'='*60}")
        print("✅ 测试完成!")
        print(f"{'='*60}\n")
        
        return result
        
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    test_efficiency_ratios()
