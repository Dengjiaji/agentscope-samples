#!/usr/bin/env python3
"""
第二轮分析功能测试脚本
测试完整的两轮分析流程
"""

import sys
import os
from datetime import datetime
from dotenv import load_dotenv

# 添加项目路径
sys.path.append('/root/wuyue.wy/Project/IA')

# 加载环境变量
load_dotenv('/root/wuyue.wy/Project/IA/.env')

from main_with_notifications import InvestmentAnalysisEngine


def test_two_round_analysis():
    """测试完整的两轮分析流程"""
    print("🧪 测试两轮分析流程")
    print("=" * 60)
    
    # 检查环境变量
    api_key = os.getenv('FINANCIAL_DATASETS_API_KEY')
    openai_key = os.getenv('OPENAI_API_KEY')
    
    if not api_key or not openai_key:
        print("❌ 缺少必要的API密钥，请检查.env文件")
        return
    
    try:
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
        
        # 运行完整的两轮分析
        print("\n🚀 开始两轮分析测试...")
        start_time = datetime.now()
        
        results = engine.run_full_analysis(tickers, start_date, end_date, parallel=True)
        
        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds()
        
        # 分析结果
        print(f"\n✅ 两轮分析完成！总耗时: {total_time:.2f} 秒")
        
        # 检查第一轮结果
        first_round_results = results.get('first_round_results', {})
        first_round_success = len([r for r in first_round_results.values() if r.get('status') == 'success'])
        print(f"🔄 第一轮分析: {first_round_success}/{len(first_round_results)} 成功")
        
        # 检查第二轮结果
        second_round_results = results.get('final_analyst_results', {})
        second_round_success = len([r for r in second_round_results.values() if r.get('status') == 'success'])
        print(f"🔄 第二轮分析: {second_round_success}/{len(second_round_results)} 成功")
        
        # 检查通知活动
        notification_activity = results['final_report']['notification_activity']
        total_notifications = notification_activity.get('total_notifications', 0)
        print(f"📢 通知数量: {total_notifications}")
        
        # 比较两轮结果
        print(f"\n📊 结果对比:")
        for agent_id in engine.core_analysts.keys():
            agent_name = engine.core_analysts[agent_id]['name']
            
            first_result = first_round_results.get(agent_id, {})
            second_result = second_round_results.get(agent_id, {})
            
            first_status = "✅" if first_result.get('status') == 'success' else "❌"
            second_status = "✅" if second_result.get('status') == 'success' else "❌"
            
            print(f"  {agent_name}: 第一轮 {first_status} | 第二轮 {second_status}")
        
        # 保存测试结果
        output_file = f"two_round_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        import json
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"\n💾 测试结果已保存到: {output_file}")
        
        if first_round_success > 0 and second_round_success > 0:
            print("🎉 两轮分析功能测试成功！")
        else:
            print("⚠️ 部分分析失败，请检查日志")
            
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()


def test_pipeline_configuration():
    """测试Pipeline配置功能"""
    print("\n🔧 测试Pipeline配置功能")
    print("=" * 50)
    
    try:
        engine = InvestmentAnalysisEngine()
        
        # 测试获取Pipeline信息
        pipeline_info = engine.get_pipeline_information()
        
        print("✅ Pipeline信息获取成功")
        print(f"📋 包含的信息类型:")
        
        for key, value in pipeline_info.items():
            if isinstance(value, dict) and 'description' in value:
                print(f"  - {value['description']}")
        
        print(f"\n💡 提示：你可以修改 pipeline_config_example.py 来自定义Pipeline信息")
        
    except Exception as e:
        print(f"❌ Pipeline配置测试失败: {str(e)}")


def main():
    """主测试函数"""
    print("🎯 第二轮分析功能测试")
    print("=" * 60)
    
    # 首先测试Pipeline配置
    test_pipeline_configuration()
    
    # 询问是否进行完整测试
    print("\n" + "=" * 60)
    choice = input("是否进行完整的两轮分析测试？(y/n): ").strip().lower()
    
    if choice == 'y':
        test_two_round_analysis()
    else:
        print("👋 跳过完整测试")


if __name__ == "__main__":
    main()
