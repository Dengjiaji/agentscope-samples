#!/usr/bin/env python3
"""
测试通信系统修复
"""

import sys
import os
sys.path.append('/root/wuyue.wy/Project/IA')

from dotenv import load_dotenv
load_dotenv('/root/wuyue.wy/Project/IA/.env')

from main_with_communications import AdvancedInvestmentAnalysisEngine

def test_communications():
    """测试通信系统"""
    print("🧪 测试通信系统修复...")
    
    # 创建引擎
    engine = AdvancedInvestmentAnalysisEngine()
    
    # 简化的测试参数
    tickers = ["AAPL"]
    start_date = "2024-01-01"
    end_date = "2024-02-01"
    
    try:
        # 运行带通信的分析（只测试一小部分）
        print("🚀 开始测试运行...")
        results = engine.run_full_analysis_with_communications(
            tickers=tickers,
            start_date=start_date,
            end_date=end_date,
            parallel=False,  # 使用串行模式便于调试
            enable_communications=True
        )
        
        print("✅ 通信系统测试成功!")
        print(f"📊 结果包含的键: {list(results.keys())}")
        
        # 检查通信日志
        if 'communication_logs' in results:
            comm_logs = results['communication_logs']
            print(f"💬 通信日志:")
            print(f"  - 私聊次数: {len(comm_logs.get('private_chats', []))}")
            print(f"  - 会议次数: {len(comm_logs.get('meetings', []))}")
            print(f"  - 通信决策次数: {len(comm_logs.get('communication_decisions', []))}")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_communications()
    sys.exit(0 if success else 1)
