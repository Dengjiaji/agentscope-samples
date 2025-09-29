#!/usr/bin/env python3
"""
IA项目Mem0迁移脚本
将现有的记忆系统迁移到Mem0
"""

import os
import sys
import json
from datetime import datetime
from typing import Dict, Any
from dotenv import load_dotenv

# 添加项目路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

# 加载环境变量
env_path = os.path.join(current_dir, '.mem0_env')
if os.path.exists(env_path):
    load_dotenv(env_path)

from mem0_config import get_mem0_config, check_environment
from src.memory import unified_memory_manager


def backup_existing_data():
    """备份现有数据"""
    backup_dir = os.path.join(current_dir, "memory_backup", datetime.now().strftime("%Y%m%d_%H%M%S"))
    os.makedirs(backup_dir, exist_ok=True)
    
    print(f"📦 创建备份目录: {backup_dir}")
    
    # 备份分析结果日志
    logs_dir = os.path.join(current_dir, "analysis_results_logs")
    if os.path.exists(logs_dir):
        import shutil
        backup_logs_dir = os.path.join(backup_dir, "analysis_results_logs")
        shutil.copytree(logs_dir, backup_logs_dir)
        print(f"✅ 已备份分析日志到: {backup_logs_dir}")
    
    # 备份通信日志
    comm_log = os.path.join(current_dir, "investment_analysis_communications.log")
    if os.path.exists(comm_log):
        import shutil
        shutil.copy2(comm_log, os.path.join(backup_dir, "investment_analysis_communications.log"))
        print(f"✅ 已备份通信日志")
    
    return backup_dir


def setup_mem0_directories():
    """设置Mem0存储目录"""
    memory_data_dir = os.path.join(current_dir, "memory_data")
    os.makedirs(memory_data_dir, exist_ok=True)
    
    chroma_db_dir = os.path.join(memory_data_dir, "ia_chroma_db")
    os.makedirs(chroma_db_dir, exist_ok=True)
    
    print(f"📁 创建Mem0存储目录: {memory_data_dir}")
    return memory_data_dir


def test_mem0_integration():
    """测试Mem0集成"""
    print("\n🧪 测试Mem0集成...")
    
    try:
        # 测试统一记忆管理器
        status = unified_memory_manager.get_system_status()
        print(f"✅ 统一记忆管理器状态: {status['memory_system']}")
        print(f"   - 注册的分析师: {len(status['registered_analysts'])}")
        print(f"   - Mem0实例: {len(status['mem0_instances'])}")
        
        # 测试分析师注册
        test_analyst_id = "test_analyst"
        test_analyst_name = "测试分析师"
        unified_memory_manager.register_analyst(test_analyst_id, test_analyst_name)
        
        # 测试记忆功能
        memory = unified_memory_manager.get_analyst_memory(test_analyst_id)
        if memory:
            session_id = memory.start_analysis_session("test_session", ["AAPL"], {"test": True})
            memory.add_analysis_message(session_id, "system", "这是一个测试消息")
            memory.complete_analysis_session(session_id, {"test_result": "success"})
            
            # 测试记忆检索
            memories = memory.get_relevant_memories("测试", limit=5)
            print(f"✅ 记忆存储和检索测试通过，找到 {len(memories)} 条相关记忆")
            
            # 清理测试数据
            unified_memory_manager.reset_analyst(test_analyst_id)
        else:
            print("❌ 无法获取测试分析师记忆")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Mem0集成测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def create_migration_report(backup_dir: str, success: bool):
    """创建迁移报告"""
    report = {
        "migration_time": datetime.now().isoformat(),
        "backup_directory": backup_dir,
        "migration_success": success,
        "mem0_config": get_mem0_config(),
        "system_status": unified_memory_manager.get_system_status() if success else None
    }
    
    report_file = os.path.join(backup_dir, "migration_report.json")
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"📄 迁移报告已保存到: {report_file}")
    return report_file


def update_import_statements():
    """更新导入语句的建议"""
    print("\n📝 代码迁移建议:")
    print("=" * 60)
    print("1. 在需要使用记忆系统的文件中，将原来的导入:")
    print("   from src.communication.analyst_memory import memory_manager")
    print("   替换为:")
    print("   from src.communication.analyst_memory_mem0 import memory_manager_mem0_adapter as memory_manager")
    print()
    print("2. 或者直接使用统一记忆管理器:")
    print("   from src.memory import unified_memory_manager")
    print()
    print("3. 主要文件需要更新:")
    print("   - advanced_investment_engine.py")
    print("   - src/communication/chat_tools.py")
    print("   - src/communication/notification_system.py")
    print()
    print("4. 配置环境变量:")
    print("   export OPENAI_API_KEY=your_api_key")
    print("   export OPENAI_BASE_URL=your_base_url  # 可选")
    print("   export MEMORY_LLM_MODEL=gpt-3.5-turbo  # 可选")


def main():
    """主迁移流程"""
    print("🚀 IA项目Mem0迁移开始")
    print("=" * 60)
    
    # 1. 环境检查
    print("1️⃣ 检查环境...")
    if not check_environment():
        print("❌ 环境检查失败，请先配置必要的环境变量")
        return False
    
    # 2. 备份现有数据
    print("\n2️⃣ 备份现有数据...")
    backup_dir = backup_existing_data()
    
    # 3. 设置Mem0目录
    print("\n3️⃣ 设置Mem0存储目录...")
    memory_data_dir = setup_mem0_directories()
    
    # 4. 测试Mem0集成
    print("\n4️⃣ 测试Mem0集成...")
    test_success = test_mem0_integration()
    
    # 5. 创建迁移报告
    print("\n5️⃣ 创建迁移报告...")
    report_file = create_migration_report(backup_dir, test_success)
    
    # 6. 显示结果
    print("\n" + "=" * 60)
    if test_success:
        print("✅ Mem0迁移成功完成！")
        print(f"📦 备份目录: {backup_dir}")
        print(f"📁 Mem0存储: {memory_data_dir}")
        print(f"📄 迁移报告: {report_file}")
        
        # 显示代码更新建议
        update_import_statements()
        
        print("\n🎉 可以开始使用基于Mem0的记忆系统了！")
    else:
        print("❌ Mem0迁移失败")
        print("请检查错误信息并解决问题后重新运行")
    
    return test_success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
