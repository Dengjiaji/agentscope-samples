#!/usr/bin/env python3
"""
OKR机制使用示例
演示如何在多日投资策略中启用和使用OKR机制
"""

import subprocess
import sys
from datetime import datetime, timedelta

def run_okr_example():
    """运行OKR机制示例"""
    print("🚀 OKR机制使用示例")
    print("=" * 60)
    
    # 计算日期范围（最近10个交易日，确保能触发5日复盘）
    end_date = datetime.now()
    start_date = end_date - timedelta(days=15)  # 15天确保包含10个工作日
    
    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_str = end_date.strftime("%Y-%m-%d")
    
    print(f"📅 分析时间范围: {start_date_str} 到 {end_date_str}")
    print(f"📊 分析标的: AAPL, MSFT")
    print(f"🏁 OKR机制: 启用")
    print(f"💬 通信机制: 启用")
    print(f"🔔 通知机制: 启用")
    print()
    
    # 构建命令
    cmd = [
        "python", "main_multi_day.py",
        "--tickers", "AAPL,MSFT",
        "--start-date", start_date_str,
        "--end-date", end_date_str,
        "--enable-okr",  # 启用OKR机制
        "--max-comm-cycles", "2",  # 减少通信轮数以加快测试
        "--verbose",  # 详细输出
        "--show-reasoning"  # 显示推理过程
    ]
    
    print("🔧 执行命令:")
    print(" ".join(cmd))
    print()
    
    print("📝 OKR机制说明:")
    print("  • 每5个交易日会进行一次分析师绩效复盘")
    print("  • 根据投资信号准确性计算权重：")
    print("    - 信号方向正确: +1分")
    print("    - 信号为中性或实际无变化: 0分")
    print("    - 信号方向错误: -1分")
    print("  • 每30个交易日进行OKR评估:")
    print("    - 平均权重最低的分析师会被淘汰")
    print("    - 淘汰的分析师会重置记忆，标记为新员工")
    print("  • 投资组合管理器会收到分析师权重信息")
    print("  • 权重高的分析师建议会获得更多关注")
    print()
    
    try:
        print("🎬 开始执行...")
        print("-" * 60)
        
        # 执行命令
        result = subprocess.run(cmd, cwd="/home/wuyue23/Project/IA", 
                              capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            print("✅ 执行成功!")
            print("\n📋 输出摘要:")
            output_lines = result.stdout.split('\n')
            
            # 提取关键信息
            for line in output_lines:
                if any(keyword in line for keyword in [
                    "OKR", "权重", "复盘", "淘汰", "分析师权重", 
                    "绩效", "声誉", "新入职", "评估"
                ]):
                    print(f"  {line}")
            
            # 显示错误输出（如果有）
            if result.stderr:
                print("\n⚠️ 警告信息:")
                stderr_lines = result.stderr.split('\n')
                for line in stderr_lines[:10]:  # 只显示前10行
                    if line.strip():
                        print(f"  {line}")
        else:
            print("❌ 执行失败!")
            print(f"返回码: {result.returncode}")
            print("\n错误输出:")
            print(result.stderr)
            
    except subprocess.TimeoutExpired:
        print("⏰ 执行超时 (5分钟)")
        print("这可能是因为网络请求或数据获取时间较长")
        
    except Exception as e:
        print(f"❌ 执行出错: {str(e)}")
    
    print("\n" + "=" * 60)
    print("📖 OKR功能说明:")
    print("1. 启用OKR: 在命令中添加 --enable-okr 参数")
    print("2. 查看权重: 在分析过程中会显示分析师权重信息")
    print("3. 复盘机制: 每5个交易日自动进行绩效复盘和权重更新")
    print("4. 淘汰机制: 每30个交易日进行OKR评估和人员调整")
    print("5. 权重应用: 投资组合管理器会根据权重调整对不同分析师建议的重视程度")
    print("\n🎯 OKR机制有助于:")
    print("• 提高投资信号质量")
    print("• 激励分析师表现")
    print("• 自动淘汰表现不佳的分析师")
    print("• 为新分析师提供成长机会")

if __name__ == "__main__":
    run_okr_example()
