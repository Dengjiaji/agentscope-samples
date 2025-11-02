#!/usr/bin/env python3
"""
测试 API Key 修复是否正常工作
"""

import os
import sys

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.agents.llm_tool_selector import LLMToolSelector

def test_api_key_selection():
    """测试 API key 选择逻辑"""
    
    print("=" * 60)
    print("测试 API Key 选择逻辑")
    print("=" * 60)
    
    selector = LLMToolSelector()
    
    # 测试不同工具类别
    test_cases = [
        ("fundamental", "FINANCIAL_DATASETS_API_KEY"),
        ("valuation", "FINANCIAL_DATASETS_API_KEY"),
        ("technical", "FINNHUB_API_KEY"),
        ("sentiment", "FINNHUB_API_KEY"),
    ]
    
    print("\n📋 测试工具类别 → API Key 映射:\n")
    
    for category, expected_key in test_cases:
        # 模拟 state 对象
        mock_state = {
            "data": {
                "api_keys": {
                    "FINNHUB_API_KEY": "test_finnhub_key",
                    "FINANCIAL_DATASETS_API_KEY": "test_financial_key"
                }
            }
        }
        
        api_key = selector._get_api_key_for_tool(category, mock_state)
        
        status = "✅" if api_key else "❌"
        print(f"{status} {category:15} → 期望: {expected_key:30} | 获取到: {api_key is not None}")
    
    print("\n" + "=" * 60)
    print("📊 测试环境变量读取:\n")
    
    # 测试从环境变量读取
    os.environ["FINNHUB_API_KEY"] = "env_finnhub_key"
    os.environ["FINANCIAL_DATASETS_API_KEY"] = "env_financial_key"
    
    for category, expected_key in test_cases:
        api_key = selector._get_api_key_for_tool(category, None)  # 不传 state
        status = "✅" if api_key else "❌"
        print(f"{status} {category:15} → 从环境变量获取: {api_key is not None}")
    
    # 清理环境变量
    del os.environ["FINNHUB_API_KEY"]
    del os.environ["FINANCIAL_DATASETS_API_KEY"]
    
    print("\n" + "=" * 60)
    print("⚠️  测试缺失 API Key 的情况:\n")
    
    # 测试缺失 API key
    for category, expected_key in test_cases:
        api_key = selector._get_api_key_for_tool(category, None)
        status = "✅" if api_key is None else "❌"
        print(f"{status} {category:15} → 应该返回 None: {api_key is None}")
    
    print("\n" + "=" * 60)
    print("✅ 测试完成!")
    print("=" * 60)


def check_env_file():
    """检查 .env 文件配置"""
    
    print("\n" + "=" * 60)
    print("检查 .env 文件配置")
    print("=" * 60)
    
    env_file = ".env"
    
    if not os.path.exists(env_file):
        print(f"\n❌ 未找到 {env_file} 文件")
        print("   请创建 .env 文件并配置以下变量:")
        print("   - FINNHUB_API_KEY")
        print("   - FINANCIAL_DATASETS_API_KEY")
        print("   - OPENAI_API_KEY")
        return
    
    print(f"\n✅ 找到 {env_file} 文件")
    
    # 读取 .env 文件
    required_keys = [
        "FINNHUB_API_KEY",
        "FINANCIAL_DATASETS_API_KEY",
        "OPENAI_API_KEY"
    ]
    
    found_keys = {}
    
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                for key in required_keys:
                    if line.startswith(f"{key}="):
                        value = line.split('=', 1)[1].strip()
                        found_keys[key] = len(value) > 0
    
    print("\n📋 API Keys 配置状态:\n")
    
    for key in required_keys:
        if key in found_keys and found_keys[key]:
            print(f"   ✅ {key}: 已配置")
        else:
            print(f"   ❌ {key}: 未配置或为空")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    print("\n🔧 API Key 修复验证脚本\n")
    
    # 测试 API key 选择逻辑
    test_api_key_selection()
    
    # 检查 .env 文件
    check_env_file()
    
    print("\n💡 提示:")
    print("   1. 确保 .env 文件中配置了所有必需的 API keys")
    print("   2. 技术/情绪工具需要 FINNHUB_API_KEY")
    print("   3. 基本面/估值工具需要 FINANCIAL_DATASETS_API_KEY")
    print("   4. 重启服务器以应用更改: sh start_continuous_server.sh --clean")
    print()

