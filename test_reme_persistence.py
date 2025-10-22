#!/usr/bin/env python3
"""
测试ReMe记忆持久化功能

验证相同config_name下记忆是否会累积而不是覆盖
"""

import os
import sys
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.memory.reme_adapter import ReMeAdapter


def test_memory_persistence():
    """测试记忆持久化"""
    
    print("\n" + "="*80)
    print("测试ReMe记忆持久化功能")
    print("="*80)
    
    # 使用测试专用的config_name
    test_config = "test_persistence"
    test_user_id = "test_analyst"
    
    print(f"\n✅ 使用config_name: {test_config}")
    print(f"✅ 使用user_id: {test_user_id}")
    
    # 第一次运行：添加记忆1和记忆2
    print("\n" + "-"*80)
    print("第1次运行：创建适配器并添加2条记忆")
    print("-"*80)
    
    adapter1 = ReMeAdapter(base_dir=test_config)
    
    result1 = adapter1.add(
        messages="这是第1条测试记忆，时间: " + datetime.now().isoformat(),
        user_id=test_user_id,
        metadata={"test_run": 1, "memory_number": 1}
    )
    print(f"✅ 添加记忆1: {result1}")
    
    result2 = adapter1.add(
        messages="这是第2条测试记忆，时间: " + datetime.now().isoformat(),
        user_id=test_user_id,
        metadata={"test_run": 1, "memory_number": 2}
    )
    print(f"✅ 添加记忆2: {result2}")
    
    # 查看当前所有记忆
    all_memories_1 = adapter1.get_all(user_id=test_user_id)
    print(f"\n📊 第1次运行后的记忆总数: {len(all_memories_1['results'])}")
    for i, mem in enumerate(all_memories_1['results'], 1):
        print(f"  {i}. {mem['memory'][:80]}...")
    
    # 第二次运行：模拟程序重启，创建新的适配器实例
    print("\n" + "-"*80)
    print("第2次运行：重新创建适配器（模拟程序重启），添加1条新记忆")
    print("-"*80)
    
    # 删除第一个适配器，模拟程序关闭
    del adapter1
    
    # 创建新的适配器实例（同样的config_name）
    adapter2 = ReMeAdapter(base_dir=test_config)
    
    result3 = adapter2.add(
        messages="这是第3条测试记忆（第2次运行），时间: " + datetime.now().isoformat(),
        user_id=test_user_id,
        metadata={"test_run": 2, "memory_number": 3}
    )
    print(f"✅ 添加记忆3: {result3}")
    
    # 查看当前所有记忆
    all_memories_2 = adapter2.get_all(user_id=test_user_id)
    print(f"\n📊 第2次运行后的记忆总数: {len(all_memories_2['results'])}")
    for i, mem in enumerate(all_memories_2['results'], 1):
        print(f"  {i}. {mem['memory'][:80]}...")
    
    # 第三次运行：再次模拟程序重启
    print("\n" + "-"*80)
    print("第3次运行：再次重新创建适配器，添加1条新记忆")
    print("-"*80)
    
    del adapter2
    
    adapter3 = ReMeAdapter(base_dir=test_config)
    
    result4 = adapter3.add(
        messages="这是第4条测试记忆（第3次运行），时间: " + datetime.now().isoformat(),
        user_id=test_user_id,
        metadata={"test_run": 3, "memory_number": 4}
    )
    print(f"✅ 添加记忆4: {result4}")
    
    # 查看当前所有记忆
    all_memories_3 = adapter3.get_all(user_id=test_user_id)
    print(f"\n📊 第3次运行后的记忆总数: {len(all_memories_3['results'])}")
    for i, mem in enumerate(all_memories_3['results'], 1):
        print(f"  {i}. {mem['memory'][:80]}...")
    
    # 验证结果
    print("\n" + "="*80)
    print("测试结果验证")
    print("="*80)
    
    expected_count = 4
    actual_count = len(all_memories_3['results'])
    
    if actual_count == expected_count:
        print(f"✅ 测试通过！记忆持久化正常工作")
        print(f"   预期记忆数: {expected_count}")
        print(f"   实际记忆数: {actual_count}")
        print(f"   记忆已正确累积，未被覆盖")
    else:
        print(f"❌ 测试失败！记忆持久化有问题")
        print(f"   预期记忆数: {expected_count}")
        print(f"   实际记忆数: {actual_count}")
        print(f"   记忆可能被覆盖了")
    
    # 清理测试数据（可选）
    print("\n" + "-"*80)
    cleanup = input("是否清理测试数据？(y/N): ").strip().lower()
    if cleanup == 'y':
        print("清理测试数据...")
        adapter3.reset(user_id=test_user_id)
        print("✅ 测试数据已清理")
    else:
        print(f"测试数据保留在: logs_and_memory/{test_config}/memory_data/reme_vector_store/{test_user_id}.jsonl")
    
    print("\n" + "="*80)
    print("测试完成")
    print("="*80 + "\n")


if __name__ == "__main__":
    try:
        test_memory_persistence()
    except Exception as e:
        print(f"\n❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()

