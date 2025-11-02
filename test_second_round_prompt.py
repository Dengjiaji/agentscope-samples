#!/usr/bin/env python3
"""
测试 Second Round Prompt 的格式化
"""

from langchain_core.prompts import ChatPromptTemplate
from pathlib import Path

def test_second_round_prompt():
    print("🧪 测试 Second Round Prompt 格式化...\n")
    
    try:
        # 读取 prompt 文件
        prompts_dir = Path("src/agents/prompts/analyst")
        
        with open(prompts_dir / "second_round_system.md", 'r', encoding='utf-8') as f:
            system_template = f.read()
        
        with open(prompts_dir / "second_round_human.md", 'r', encoding='utf-8') as f:
            human_template = f.read()
        
        print("✅ Prompt 文件读取成功\n")
        
        # 创建 LangChain 模板
        template = ChatPromptTemplate.from_messages([
            ("system", system_template),
            ("human", human_template)
        ])
        
        print("✅ ChatPromptTemplate 创建成功\n")
        
        # 测试格式化
        messages = template.format_messages(
            analyst_name="Test Analyst",
            specialty="Testing",
            analysis_focus="- Focus 1\n- Focus 2",
            decision_style="Analytical",
            risk_preference="Moderate",
            ticker_reports="## Stock 1: AAPL\nTest report",
            notifications="- Notification 1",
            agent_id="test_analyst"
        )
        
        print("✅ format_messages 执行成功\n")
        
        # 检查结果
        human_msg = messages[1].content
        
        # 检查 JSON 示例是否正确转义
        if '{{' in human_msg and '"analyst_id"' in human_msg:
            print("✅ JSON 示例正确转义（包含 {{ 和 }}）\n")
        else:
            print("❌ JSON 示例转义可能有问题\n")
            print("Human message 前 500 字符:")
            print(human_msg[:500])
            return False
        
        # 检查变量是否被正确替换
        if "Test Analyst" in str(messages) and "{analyst_name}" not in str(messages):
            print("✅ 变量替换正确\n")
        else:
            print("❌ 变量替换可能有问题\n")
            return False
        
        print("=" * 60)
        print("🎉 Second Round Prompt 测试通过！")
        print("=" * 60)
        print()
        print("💡 关键点:")
        print("  1. JSON 示例使用 {{ }} 转义")
        print("  2. 变量占位符使用 { } 格式")
        print("  3. LangChain 的 format_messages 正常工作")
        print()
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_second_round_prompt()


