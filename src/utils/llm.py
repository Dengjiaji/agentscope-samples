"""Helper functions for LLM"""

import json
from pydantic import BaseModel
from typing import Optional, Dict, Any, Union

# 导入 AgentScope 模型
from src.llm.agentscope_models import get_model as get_agentscope_model, ModelProvider
from src.utils.progress import progress
from src.graph.state import AgentState


def call_llm(
    prompt: Union[str, list],
    pydantic_model: type[BaseModel],
    agent_name: Optional[str] = None,
    state: Optional[AgentState] = None,
    max_retries: int = 3,
    default_factory=None,
) -> BaseModel:
    """
    使用 AgentScope 模型包装器调用 LLM，支持结构化输出
    
    Args:
        prompt: 提示内容（字符串或消息列表）
        pydantic_model: Pydantic 模型类用于结构化输出
        agent_name: Agent 名称（可选，用于进度更新和模型配置提取）
        state: AgentState 对象（可选，用于提取 agent 特定的模型配置）
        max_retries: 最大重试次数（默认: 3）
        default_factory: 默认响应工厂函数（可选）
    
    Returns:
        Pydantic 模型实例
    """
    
    # 提取模型配置
    if state and agent_name:
        model_name, model_provider = get_agent_model_config(state, agent_name)
    else:
        # 使用系统默认配置
        model_name = "gpt-4o-mini"
        model_provider = "OPENAI"

    # 提取 API keys
    api_keys = None
    if state:
        request = state.get("metadata", {}).get("request")
        if request and hasattr(request, 'api_keys'):
            api_keys = request.api_keys

    # 获取模型实例（使用 AgentScope）
    llm = get_agentscope_model(model_name, model_provider, api_keys)

    # 准备 prompt（添加 JSON 格式要求）
    if isinstance(prompt, str):
        json_schema = pydantic_model.model_json_schema()
        enhanced_prompt = f"""{prompt}

请以 JSON 格式返回结果，严格遵循以下 schema：
{json.dumps(json_schema, indent=2, ensure_ascii=False)}

只返回 JSON，不要添加任何其他文字。"""
        messages = [{"role": "user", "content": enhanced_prompt}]
    else:
        messages = prompt

    # 调用 LLM（带重试逻辑）
    for attempt in range(max_retries):
        try:
            # 使用 AgentScope 模型
            response = llm(
                messages,
                temperature=0.7,
                response_format={"type": "json_object"} if model_provider == ModelProvider.OPENAI else None
            )
            content = response["content"]

            # 解析 JSON 响应
            parsed_result = extract_json_from_response(content)
            if parsed_result:
                return pydantic_model(**parsed_result)
            
            # 如果解析失败，尝试直接解析
            try:
                return pydantic_model(**json.loads(content))
            except:
                pass

        except Exception as e:
            # 打印详细错误信息
            error_details = f"LLM Error - Agent: {agent_name}, Model: {model_name} ({model_provider}), Attempt: {attempt + 1}/{max_retries}"
            print(f"{error_details}")
            print(f"Error Type: {type(e).__name__}")
            print(f"Error Message: {str(e)}")
            
            import traceback
            print(f"Full Traceback:\n{traceback.format_exc()}")
            
            # if agent_name:
            #     progress.update_status(agent_name, None, f"Error - retry {attempt + 1}/{max_retries}: {type(e).__name__}")

            if attempt == max_retries - 1:
                print(f"🚨 FINAL ERROR: LLM call failed after {max_retries} attempts")
                print(f"🚨 Agent: {agent_name}, Model: {model_name} ({model_provider})")
                print(f"🚨 Final Error: {e}")
                
                # 使用 default_factory 或创建默认响应
                if default_factory:
                    return default_factory()
                return create_default_response(pydantic_model)

    # 不应该到达这里
    return create_default_response(pydantic_model)


def create_default_response(model_class: type[BaseModel]) -> BaseModel:
    """Creates a safe default response based on the model's fields."""
    default_values = {}
    for field_name, field in model_class.model_fields.items():
        if field.annotation == str:
            default_values[field_name] = "Error in analysis, using default"
        elif field.annotation == float:
            default_values[field_name] = 0.0
        elif field.annotation == int:
            default_values[field_name] = 0
        elif hasattr(field.annotation, "__origin__") and field.annotation.__origin__ == dict:
            default_values[field_name] = {}
        else:
            # For other types (like Literal), try to use the first allowed value
            if hasattr(field.annotation, "__args__"):
                default_values[field_name] = field.annotation.__args__[0]
            else:
                default_values[field_name] = None

    return model_class(**default_values)


def extract_json_from_response(content: str) -> dict | None:
    """Extracts JSON from markdown-formatted response."""
    try:
        json_start = content.find("```json")
        if json_start != -1:
            json_text = content[json_start + 7 :]  # Skip past ```json
            json_end = json_text.find("```")
            if json_end != -1:
                json_text = json_text[:json_end].strip()
                return json.loads(json_text)
    except Exception as e:
        print(f"Error extracting JSON from response: {e}")
    return None


def get_agent_model_config(state, agent_name):
    """
    Get model configuration for a specific agent from the state.
    Falls back to global model configuration if agent-specific config is not available.
    Always returns valid model_name and model_provider values.
    """
    request = state.get("metadata", {}).get("request")
    
    if request and hasattr(request, 'get_agent_model_config'):
        # Get agent-specific model configuration
        model_name, model_provider = request.get_agent_model_config(agent_name)
        # Ensure we have valid values
        if model_name and model_provider:
            return model_name, model_provider.value if hasattr(model_provider, 'value') else str(model_provider)
    
    # Fall back to global configuration (system defaults)
    model_name = state.get("metadata", {}).get("model_name") or "gpt-4.1"
    model_provider = state.get("metadata", {}).get("model_provider") or "OPENAI"
    
    # Convert enum to string if necessary
    if hasattr(model_provider, 'value'):
        model_provider = model_provider.value
    
    return model_name, model_provider
