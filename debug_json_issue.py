#!/usr/bin/env python3
"""
Debug JSON解析问题
"""

import json
import re

def debug_json_parsing():
    """调试JSON解析问题"""
    
    # 模拟从LLM获得的可能有问题的响应
    problematic_responses = [
        # 情况1: 包含额外的文本
        'Here is my response: {"response": "我同意这个观点", "signal_adjustment": false}',
        
        # 情况2: 多行JSON
        '''
        {
          "response": "基于当前分析，我认为应该调整策略",
          "signal_adjustment": true,
          "adjusted_signal": {
            "ticker": "AAPL",
            "signal": "neutral"
          }
        }
        ''',
        
        # 情况3: 包含markdown格式
        '''```json
        {
          "response": "我需要重新评估",
          "signal_adjustment": false
        }
        ```''',
        
        # 情况4: 单引号而非双引号
        "{'response': '我同意这个观点', 'signal_adjustment': false}",
        
        # 情况5: 不完整的JSON
        '{"response": "我同意这个观点", "signal_adjustment": false',
        
        # 情况6: 包含注释
        '''{
          "response": "我的回应", // 这是注释
          "signal_adjustment": false
        }''',
        
        # 情况7: 正确的JSON
        '{"response": "我同意这个观点", "signal_adjustment": false}',
    ]
    
    print("🔍 调试JSON解析问题")
    print("=" * 50)
    
    for i, response in enumerate(problematic_responses, 1):
        print(f"\n测试案例 {i}:")
        print(f"原始响应: {repr(response[:100])}...")
        
        # 尝试直接解析
        try:
            result = json.loads(response)
            print(f"✅ 直接解析成功: {result}")
            continue
        except json.JSONDecodeError as e:
            print(f"❌ 直接解析失败: {e}")
        
        # 尝试清理后解析
        cleaned = clean_json_response(response)
        if cleaned != response:
            print(f"🧹 清理后: {repr(cleaned[:100])}...")
            try:
                result = json.loads(cleaned)
                print(f"✅ 清理后解析成功: {result}")
                continue
            except json.JSONDecodeError as e:
                print(f"❌ 清理后仍失败: {e}")
        
        # 提取JSON
        extracted = extract_json_from_response(response)
        if extracted:
            print(f"🎯 提取的JSON: {extracted}")
        else:
            print(f"💥 无法提取有效JSON")


def clean_json_response(response: str) -> str:
    """清理JSON响应"""
    # 移除markdown代码块
    response = re.sub(r'```json\s*\n?', '', response)
    response = re.sub(r'\n?\s*```', '', response)
    
    # 移除前后的额外文本，查找JSON部分
    json_match = re.search(r'\{.*\}', response, re.DOTALL)
    if json_match:
        response = json_match.group()
    
    # 移除单行注释
    response = re.sub(r'//.*', '', response)
    
    # 替换单引号为双引号（简单情况）
    response = response.replace("'", '"')
    
    # 移除多余的空白
    response = response.strip()
    
    return response


def extract_json_from_response(response: str) -> dict:
    """从响应中提取JSON"""
    try:
        # 首先尝试直接解析
        return json.loads(response)
    except:
        pass
    
    try:
        # 清理后解析
        cleaned = clean_json_response(response)
        return json.loads(cleaned)
    except:
        pass
    
    # 尝试找到最内层的大括号内容
    try:
        # 找到第一个{和最后一个}
        start = response.find('{')
        end = response.rfind('}')
        if start != -1 and end != -1 and end > start:
            json_str = response[start:end+1]
            return json.loads(json_str)
    except:
        pass
    
    return None


def create_robust_json_parser():
    """创建健壮的JSON解析函数"""
    
    def parse_llm_response(response_content: str) -> dict:
        """健壮的LLM响应解析"""
        if not response_content:
            return {"response": "空响应", "signal_adjustment": False}
        
        # 尝试直接解析
        try:
            return json.loads(response_content)
        except json.JSONDecodeError:
            pass
        
        # 尝试清理后解析
        try:
            cleaned = clean_json_response(response_content)
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
        
        # 提取关键信息（降级方案）
        response_text = response_content
        signal_adjustment = False
        
        # 尝试提取response字段
        response_match = re.search(r'"response"\s*:\s*"([^"]*)"', response_content)
        if response_match:
            response_text = response_match.group(1)
        
        # 尝试提取signal_adjustment字段
        adj_match = re.search(r'"signal_adjustment"\s*:\s*(true|false)', response_content)
        if adj_match:
            signal_adjustment = adj_match.group(1) == 'true'
        
        return {
            "response": response_text,
            "signal_adjustment": signal_adjustment,
            "_fallback": True
        }
    
    return parse_llm_response


if __name__ == "__main__":
    debug_json_parsing()
    
    print("\n" + "=" * 50)
    print("🛠️ 健壮解析器测试")
    
    parser = create_robust_json_parser()
    
    test_cases = [
        '{"response": "正常JSON", "signal_adjustment": false}',
        'Some text before {"response": "有前缀的JSON", "signal_adjustment": true} some text after',
        '"response": "无效JSON，缺少大括号", "signal_adjustment": false',
        'I think the response is: "很难解析的情况"',
        ''
    ]
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n案例 {i}: {repr(case[:50])}...")
        result = parser(case)
        print(f"结果: {result}")
        if result.get('_fallback'):
            print("⚠️ 使用了降级方案")
