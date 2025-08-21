#!/usr/bin/env python3
"""
并行性能测试脚本
比较串行和并行执行的性能差异
"""

import sys
import os
import time
from datetime import datetime
from dotenv import load_dotenv

# 添加项目路径
sys.path.append('/root/wuyue.wy/Project/IA')

# 加载环境变量
load_dotenv('/root/wuyue.wy/Project/IA/.env')

from main_with_notifications import InvestmentAnalysisEngine


def performance_test():
    """性能测试函数"""
    print("🚀 并行性能测试")
    print("=" * 60)
    
    # 检查环境变量
    api_key = os.getenv('FINANCIAL_DATASETS_API_KEY')
    openai_key = os.getenv('OPENAI_API_KEY')
    
    if not api_key or not openai_key:
        print("❌ 缺少必要的API密钥，请检查.env文件")
        return
    
    # 创建分析引擎
    engine = InvestmentAnalysisEngine()
    
    # 测试参数
    tickers = ["AAPL"]  # 使用单个股票进行快速测试
    start_date = "2024-01-01"
    end_date = "2024-02-01"
    
    print(f"📊 测试配置:")
    print(f"  - 股票: {', '.join(tickers)}")
    print(f"  - 时间范围: {start_date} 至 {end_date}")
    print(f"  - 分析师数量: {len(engine.core_analysts)}")
    print("=" * 60)
    
    results = {}
    
    # 测试串行执行
    print("\n🔄 测试串行执行...")
    try:
        start_time = time.time()
        sequential_results = engine.run_full_analysis(
            tickers, start_date, end_date, parallel=False
        )
        sequential_time = time.time() - start_time
        
        results['sequential'] = {
            'time': sequential_time,
            'success': True,
            'analysts_completed': len([r for r in sequential_results['analyst_results'].values() 
                                     if r.get('status') == 'success'])
        }
        
        print(f"✅ 串行执行完成，耗时: {sequential_time:.2f} 秒")
        
    except Exception as e:
        print(f"❌ 串行执行失败: {str(e)}")
        results['sequential'] = {'success': False, 'error': str(e)}
    
    # 等待一下，清理状态
    print("\n⏳ 等待 3 秒后进行并行测试...")
    time.sleep(3)
    
    # 测试并行执行
    print("\n🚀 测试并行执行...")
    try:
        start_time = time.time()
        parallel_results = engine.run_full_analysis(
            tickers, start_date, end_date, parallel=True
        )
        parallel_time = time.time() - start_time
        
        results['parallel'] = {
            'time': parallel_time,
            'success': True,
            'analysts_completed': len([r for r in parallel_results['analyst_results'].values() 
                                     if r.get('status') == 'success'])
        }
        
        print(f"✅ 并行执行完成，耗时: {parallel_time:.2f} 秒")
        
    except Exception as e:
        print(f"❌ 并行执行失败: {str(e)}")
        results['parallel'] = {'success': False, 'error': str(e)}
    
    # 生成性能报告
    print("\n" + "=" * 60)
    print("📊 性能测试报告")
    print("=" * 60)
    
    if results['sequential']['success'] and results['parallel']['success']:
        seq_time = results['sequential']['time']
        par_time = results['parallel']['time']
        speedup = seq_time / par_time
        efficiency = speedup / len(engine.core_analysts) * 100
        
        print(f"串行执行时间:    {seq_time:.2f} 秒")
        print(f"并行执行时间:    {par_time:.2f} 秒")
        print(f"加速比:         {speedup:.2f}x")
        print(f"并行效率:       {efficiency:.1f}%")
        print(f"时间节省:       {seq_time - par_time:.2f} 秒 ({(1-par_time/seq_time)*100:.1f}%)")
        
        if speedup > 1.5:
            print("🎉 并行执行显著提升了性能！")
        elif speedup > 1.1:
            print("✅ 并行执行有效提升了性能")
        else:
            print("⚠️ 并行执行效果不明显，可能由于网络延迟或CPU限制")
    else:
        print("❌ 测试未能完成，请检查错误信息")
        if not results['sequential']['success']:
            print(f"串行执行错误: {results['sequential'].get('error', '未知错误')}")
        if not results['parallel']['success']:
            print(f"并行执行错误: {results['parallel'].get('error', '未知错误')}")
    
    print("=" * 60)


def simple_test():
    """简化测试，只验证并行功能是否正常"""
    print("🧪 简化并行功能测试")
    print("=" * 50)
    
    try:
        engine = InvestmentAnalysisEngine()
        
        # 使用最小配置进行快速测试
        tickers = ["AAPL"]
        start_date = "2024-01-01"
        end_date = "2024-01-15"  # 更短的时间范围
        
        print("🚀 测试并行执行...")
        start_time = time.time()
        
        results = engine.run_full_analysis(tickers, start_date, end_date, parallel=True)
        
        execution_time = time.time() - start_time
        
        # 检查结果
        successful_analyses = len([r for r in results['analyst_results'].values() 
                                 if r.get('status') == 'success'])
        
        print(f"\n✅ 测试完成！")
        print(f"⏱️ 执行时间: {execution_time:.2f} 秒")
        print(f"📊 成功分析: {successful_analyses}/{len(engine.core_analysts)}")
        
        # 显示通知活动
        notification_activity = results['final_report']['notification_activity']
        print(f"📢 通知数量: {notification_activity['total_notifications']}")
        
        if successful_analyses == len(engine.core_analysts):
            print("🎉 所有分析师并行执行成功！")
        else:
            print("⚠️ 部分分析师执行失败，请检查日志")
            
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()


def main():
    """主函数"""
    print("🎯 选择测试模式:")
    print("  1 - 完整性能对比测试 (较慢，需要API调用)")
    print("  2 - 简化功能验证测试 (较快)")
    print("  q - 退出")
    
    choice = input("\n请选择: ").strip().lower()
    
    if choice == '1':
        performance_test()
    elif choice == '2':
        simple_test()
    elif choice == 'q':
        print("👋 退出测试")
    else:
        print("❌ 无效选择")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--simple":
        simple_test()
    elif len(sys.argv) > 1 and sys.argv[1] == "--full":
        performance_test()
    else:
        main()
