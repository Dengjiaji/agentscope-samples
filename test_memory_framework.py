#!/usr/bin/env python3
"""
记忆框架测试脚本
测试 Mem0 和 ReMe 框架的切换和基本功能
"""

import os
import sys
from pathlib import Path

# 添加项目路径
sys.path.append(str(Path(__file__).parent))

def test_memory_framework(framework_name: str, config_name: str = "test_memory"):
    """
    测试指定的记忆框架
    
    Args:
        framework_name: 框架名称 ('mem0' 或 'reme')
        config_name: 配置名称
    """
    print("=" * 70)
    print(f"测试记忆框架: {framework_name.upper()}")
    print("=" * 70)
    
    # 设置环境变量
    os.environ['MEMORY_FRAMEWORK'] = framework_name
    
    try:
        # 导入记忆工厂
        from src.memory.memory_factory import initialize_memory_system
        
        print(f"\n1️⃣  初始化记忆系统...")
        memory = initialize_memory_system(base_dir=config_name)
        print(f"   ✅ 成功! 当前框架: {memory.get_framework_name()}")
        
        # 测试添加记忆
        print(f"\n2️⃣  测试添加记忆...")
        add_result = memory.add(
            messages="这是一个测试记忆：苹果股票表现良好",
            user_id="test_analyst",
            metadata={"test": True, "framework": framework_name}
        )
        print(f"   ✅ 添加成功: {add_result.get('status', 'N/A')}")
        
        # 测试搜索记忆
        print(f"\n3️⃣  测试搜索记忆...")
        search_results = memory.search(
            query="苹果股票",
            user_id="test_analyst",
            top_k=3
        )
        results = search_results.get('results', [])
        print(f"   ✅ 搜索成功: 找到 {len(results)} 条记忆")
        if results:
            print(f"   📝 第一条记忆: {results[0].get('memory', 'N/A')[:50]}...")
        
        # 测试获取所有记忆
        print(f"\n4️⃣  测试获取所有记忆...")
        all_memories = memory.get_all(user_id="test_analyst")
        all_results = all_memories.get('results', [])
        print(f"   ✅ 获取成功: 共 {len(all_results)} 条记忆")
        
        # 测试框架特定功能
        print(f"\n5️⃣  测试框架特定功能...")
        if framework_name == 'mem0':
            print(f"   ℹ️  Mem0 支持完整的 CRUD 操作")
            # 可以测试 update 和 delete
        elif framework_name == 'reme':
            print(f"   ℹ️  ReMe 支持 workspace 导入/导出")
            # 可以测试导出功能
            try:
                from src.memory.reme_adapter import ReMeAdapter
                if isinstance(memory, ReMeAdapter):
                    export_result = memory.export_workspace(
                        user_id="test_analyst"
                    )
                    print(f"   ✅ 导出成功: {export_result.get('export_path', 'N/A')}")
            except Exception as e:
                print(f"   ⚠️  导出测试跳过: {e}")
        
        print(f"\n✅ {framework_name.upper()} 框架测试通过!")
        
    except ImportError as e:
        print(f"\n❌ 导入错误: {e}")
        print(f"   提示: {framework_name} 框架可能未安装")
        if framework_name == 'reme':
            print(f"   解决方法: pip install flowllm")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 70 + "\n")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="记忆框架测试脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 测试 Mem0 框架
  python test_memory_framework.py --framework mem0
  
  # 测试 ReMe 框架
  python test_memory_framework.py --framework reme
  
  # 测试所有框架
  python test_memory_framework.py --all
        """
    )
    
    parser.add_argument(
        '--framework',
        type=str,
        choices=['mem0', 'reme'],
        help='指定要测试的框架'
    )
    
    parser.add_argument(
        '--all',
        action='store_true',
        help='测试所有可用框架'
    )
    
    parser.add_argument(
        '--config',
        type=str,
        default='test_memory',
        help='配置名称 (默认: test_memory)'
    )
    
    args = parser.parse_args()
    
    if args.all:
        # 测试所有框架
        test_memory_framework('mem0', args.config)
        test_memory_framework('reme', args.config)
    elif args.framework:
        # 测试指定框架
        test_memory_framework(args.framework, args.config)
    else:
        # 从环境变量读取
        framework = os.getenv('MEMORY_FRAMEWORK', 'mem0')
        print(f"使用环境变量 MEMORY_FRAMEWORK={framework}")
        test_memory_framework(framework, args.config)


if __name__ == "__main__":
    main()

