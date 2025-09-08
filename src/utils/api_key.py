

def get_api_key_from_state(state: dict, api_key_name: str) -> str:
    """Get an API key from the state object."""
    # 首先尝试从data.api_keys获取 (新的存储位置)
    if state and state.get("data", {}).get("api_keys"):
        api_key = state["data"]["api_keys"].get(api_key_name)
        if api_key:
            return api_key
    
    # 然后尝试从metadata.request.api_keys获取 (旧的存储位置，向后兼容)
    if state and state.get("metadata", {}).get("request"):
        request = state["metadata"]["request"]
        if hasattr(request, 'api_keys') and request.api_keys:
            api_key = request.api_keys.get(api_key_name)
            if api_key:
                return api_key
    
    return None