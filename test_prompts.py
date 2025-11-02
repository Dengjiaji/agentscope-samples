#!/usr/bin/env python3
"""
测试所有 Prompt 文件的加载和渲染
"""

from src.agents.prompt_loader import get_prompt_loader
from pathlib import Path
from langchain_core.prompts import ChatPromptTemplate

def test_prompt_loader_format():
    """测试 PromptLoader 格式的 prompts"""
    print("🧪 测试 PromptLoader 格式 Prompts ({{ variable }})...\n")
    
    loader = get_prompt_loader()
    
    tests = [
        {
            "agent_type": "analyst",
            "prompt_name": "tool_selection",
            "variables": {
                "analyst_persona": "Fundamental Analyst",
                "ticker": "AAPL",
                "analysis_objective": "Evaluate fundamentals",
                "tools_description": "Tool 1, Tool 2",
                "persona_description": "Expert in financial analysis"
            },
            "check": ["Fundamental Analyst", "AAPL", "{{"]
        },
        {
            "agent_type": "analyst",
            "prompt_name": "tool_synthesis",
            "variables": {
                "analyst_persona": "Technical Analyst",
                "ticker": "MSFT",
                "analysis_strategy": "Test strategy",
                "synthesis_approach": "Test approach",
                "tool_summaries": "Test summaries"
            },
            "check": ["Technical Analyst", "MSFT", "{{"]
        },
        {
            "agent_type": "portfolio_manager",
            "prompt_name": "direction_decision_human",
            "variables": {
                "signals_by_ticker": "test signals",
                "analyst_weights_info": "test weights",
                "analyst_weights_separator": ""
            },
            "check": ["test signals", "{{"]
        },
        {
            "agent_type": "portfolio_manager",
            "prompt_name": "portfolio_decision_human",
            "variables": {
                "signals_by_ticker": "test",
                "current_prices": "test",
                "max_shares": "test",
                "portfolio_cash": "100000",
                "portfolio_positions": "{}",
                "margin_requirement": "0",
                "total_margin_used": "0",
                "analyst_weights_info": "test",
                "analyst_weights_separator": ""
            },
            "check": ["{{", "test"]
        }
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            prompt = loader.load_prompt(
                test["agent_type"],
                test["prompt_name"],
                test["variables"]
            )
            
            # 检查关键内容
            all_checks_pass = all(check in prompt for check in test["check"])
            
            if all_checks_pass:
                print(f"✅ {test['agent_type']}/{test['prompt_name']}")
                passed += 1
            else:
                print(f"❌ {test['agent_type']}/{test['prompt_name']} - 内容检查失败")
                failed += 1
                
        except Exception as e:
            print(f"❌ {test['agent_type']}/{test['prompt_name']} - {e}")
            failed += 1
    
    print(f"\n📊 PromptLoader 格式测试: {passed} 通过, {failed} 失败\n")
    return failed == 0


def test_langchain_format():
    """测试 LangChain 格式的 prompts"""
    print("🧪 测试 LangChain 格式 Prompts ({ variable })...\n")
    
    try:
        prompts_dir = Path("src/agents/prompts/analyst")
        
        # 读取 second_round prompts
        with open(prompts_dir / "second_round_system.md", 'r', encoding='utf-8') as f:
            system_template = f.read()
        
        with open(prompts_dir / "second_round_human.md", 'r', encoding='utf-8') as f:
            human_template = f.read()
        
        # 创建 LangChain 模板
        template = ChatPromptTemplate.from_messages([
            ("system", system_template),
            ("human", human_template)
        ])
        
        # 测试格式化
        prompt = template.format_messages(
            analyst_name="Test Analyst",
            specialty="Testing",
            analysis_focus="Test focus",
            decision_style="Test style",
            risk_preference="Test preference",
            ticker_reports="Test reports",
            notifications="Test notifications",
            agent_id="test_agent"
        )
        
        # 检查是否成功
        if len(prompt) == 2:  # system + human messages
            print("✅ analyst/second_round_system.md")
            print("✅ analyst/second_round_human.md")
            print("\n📊 LangChain 格式测试: 通过\n")
            return True
        else:
            print("❌ LangChain 格式测试失败")
            return False
            
    except Exception as e:
        print(f"❌ LangChain 格式测试失败: {e}\n")
        return False


def main():
    print("=" * 60)
    print("   Prompt 文件测试")
    print("=" * 60)
    print()
    
    # 测试 PromptLoader 格式
    test1_pass = test_prompt_loader_format()
    
    # 测试 LangChain 格式
    test2_pass = test_langchain_format()
    
    # 总结
    print("=" * 60)
    if test1_pass and test2_pass:
        print("🎉 所有测试通过！")
    else:
        print("⚠️ 部分测试失败，请检查上面的错误信息")
    print("=" * 60)
    print()
    
    print("💡 提示:")
    print("  - PromptLoader 格式使用 {{ variable }}")
    print("  - LangChain 格式使用 {variable}")
    print("  - 详见: src/agents/prompts/README.md")
    print()


if __name__ == "__main__":
    main()


