# -*- coding: utf-8 -*-
"""Helper functions for LLM"""
# flake8: noqa: E501
# pylint: disable=E501
import json
from typing import Optional, Union

from pydantic import BaseModel

from backend.graph.state import AgentState
from backend.llm.models import ModelProvider, get_model


def tool_call(
    messages: Union[str, list],
    pydantic_model: type[BaseModel],
    agent_name: Optional[str] = None,
    state: Optional[AgentState] = None,
    max_retries: int = 3,
    default_factory=None,
) -> BaseModel:
    """
    Call LLM using AgentScope model wrapper, supports structured output

    Args:
        messages: Prompt content (string or message list)
        pydantic_model: Pydantic model class for structured output
        agent_name: Agent name (optional, for progress updates and model config extraction)
        state: AgentState object (optional, for extracting agent-specific model config)
        max_retries: Maximum retry count (default: 3)
        default_factory: Default response factory function (optional)

    Returns:
        Pydantic model instance
    """

    # Extract model configuration and API keys
    api_keys = {}
    if state:
        # Extract API keys from state
        if "data" in state and "api_keys" in state["data"]:
            api_keys = state["data"]["api_keys"]
        elif "metadata" in state:
            request = state.get("metadata", {}).get("request")
            if request and hasattr(request, "api_keys"):
                api_keys = request.api_keys

    if state and agent_name:
        model_name, model_provider = get_agent_model_config(state, agent_name)
    else:
        # Use system default configuration
        model_name = "gpt-4o-mini"
        model_provider = "OPENAI"

    llm = get_model(model_name, model_provider, api_keys=api_keys or {})

    # Call LLM (with retry logic)
    for attempt in range(max_retries):
        try:
            response = llm(
                messages,
                temperature=0.7,
                response_format=(
                    {"type": "json_object"}
                    if model_provider == ModelProvider.OPENAI
                    else None
                ),
            )
            content = response["content"]

            # Parse JSON response
            parsed_result = extract_json_from_response(content)
            if parsed_result:
                result = pydantic_model(**parsed_result)

                # ✅ Check if key fields are empty (for SecondRoundAnalysis)
                if hasattr(result, "ticker_signals") and (
                    not result.ticker_signals
                    or len(result.ticker_signals) == 0
                ):
                    # 🔍 Only print debug log when empty response detected
                    print(
                        f"\n⚠️ [{agent_name}] LLM returned empty ticker_signals "
                        f"(attempt {attempt + 1}/{max_retries})",
                    )
                    print(f"   Response length: {len(content)} characters")
                    print(f"   Response preview: {content[:500]}...")

                    if attempt < max_retries - 1:
                        print("   Preparing to retry...")
                        continue  # Retry
                    else:
                        # ❌ Reached maximum retries, pause program
                        print(
                            f"\n❌❌❌ [{agent_name}] Reached maximum retry count ({max_retries}), "
                            f"LLM continues to return empty signals",
                        )

                        import pdb

                        pdb.set_trace()

                        # If user chooses to continue, raise exception
                        raise ValueError(
                            f"LLM return empty ticker_signals after {max_retries} attempts",
                        )

                return result

            # If parsing failed, try direct parsing
            try:
                result = pydantic_model(**json.loads(content))

                # ✅ Also check directly parsed result
                if hasattr(result, "ticker_signals") and (
                    not result.ticker_signals
                    or len(result.ticker_signals) == 0
                ):
                    # 🔍 Only print debug log when empty response detected
                    print(
                        f"\n⚠️ [{agent_name}] LLM returned empty ticker_signals "
                        f"(attempt {attempt + 1}/{max_retries})",
                    )
                    print(f"   Response length: {len(content)} characters")
                    print(f"   Response preview: {content[:500]}...")

                    if attempt < max_retries - 1:
                        print("   Preparing to retry...")
                        continue  # Retry
                    else:
                        # Reached maximum retries, pause program
                        print(
                            f"\n❌❌❌ [{agent_name}] Reached maximum retry count ({max_retries}), "
                            f"LLM continues to return empty signals",
                        )

                        # If user chooses to continue, raise exception
                        raise ValueError(
                            f"LLM continues to return empty ticker_signals "
                            f"after {max_retries} attempts",
                        )

                return result
            except ValueError as ve:
                # Re-raise our own ValueError
                raise ve
            except:
                pass

        except Exception as e:
            # Print detailed error information
            error_details = (
                f"LLM Error - Agent: {agent_name}, "
                f"Model: {model_name} ({model_provider}), "
                f"Attempt: {attempt + 1}/{max_retries}"
            )
            print(f"{error_details}")
            print(f"Error Type: {type(e).__name__}")
            print(f"Error Message: {str(e)}")

            import traceback

            print(f"Full Traceback:\n{traceback.format_exc()}")

            if attempt == max_retries - 1:
                print(
                    f"🚨 FINAL ERROR: LLM call failed after {max_retries} attempts",
                )
                print(
                    f"🚨 Agent: {agent_name}, Model: {model_name} ({model_provider})",
                )
                print(f"🚨 Final Error: {e}")
                return create_default_response(pydantic_model)
            else:
                # Not the last attempt - retry with exponential backoff
                import time

                wait_time = 2**attempt  # 1s, 2s, 4s, ...
                print(f"⏳ Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
                print(f"🔄 Retrying (attempt {attempt + 2}/{max_retries})...")
                continue  # ✨ Enter next iteration of the loop


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
        elif (
            hasattr(field.annotation, "__origin__")
            and field.annotation.__origin__ == dict
        ):
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

    if request and hasattr(request, "get_agent_model_config"):
        # Get agent-specific model configuration
        model_name, model_provider = request.get_agent_model_config(agent_name)
        # Ensure we have valid values
        if model_name and model_provider:
            # Convert ModelProvider enum to string if needed
            if hasattr(model_provider, "value"):
                model_provider = model_provider.value
            elif isinstance(model_provider, ModelProvider):
                model_provider = model_provider.value
            return model_name, str(model_provider)

    # Fall back to global configuration (system defaults)
    model_name = state.get("metadata", {}).get("model_name") or "gpt-4.1"
    model_provider = (
        state.get("metadata", {}).get("model_provider") or "OPENAI"
    )

    # Convert enum to string if necessary
    if hasattr(model_provider, "value"):
        model_provider = model_provider.value

    return model_name, model_provider
