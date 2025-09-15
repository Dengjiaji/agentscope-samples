#!/usr/bin/env python3
"""
JSON序列化工具模块
提供安全的JSON序列化功能，处理numpy、pandas等类型
"""

import json
import math
from datetime import datetime
from typing import Any

try:
    import numpy as _np
except Exception:
    _np = None

try:
    import pandas as _pd
except Exception:
    _pd = None


def make_json_safe(obj: Any) -> Any:
    """将对象递归转换为可JSON序列化的原生类型。
    - numpy整/浮/布尔 -> int/float/bool
    - pandas/NumPy NaN/NaT -> None
    - datetime -> isoformat 字符串
    - dict/list/tuple 递归处理
    其他不可序列化对象 -> str(obj)
    """
    # None与基础类型
    if obj is None or isinstance(obj, (str, int, float, bool)):
        # 处理float中的nan/inf
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
        return obj

    # datetime
    if isinstance(obj, datetime):
        return obj.isoformat()

    # numpy 标量
    if _np is not None:
        if isinstance(obj, (_np.integer,)):
            return int(obj)
        if isinstance(obj, (_np.floating,)):
            val = float(obj)
            return None if math.isnan(val) or math.isinf(val) else val
        if isinstance(obj, (_np.bool_,)):
            return bool(obj)
        if obj is _np.nan:
            return None

    # pandas 标量
    if _pd is not None:
        try:
            if _pd.isna(obj):
                return None
        except Exception:
            pass

    # 容器类型
    if isinstance(obj, dict):
        return {str(make_json_safe(k)): make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [make_json_safe(v) for v in obj]

    # 兜底：尝试获取__dict__
    if hasattr(obj, "__dict__"):
        try:
            return make_json_safe(vars(obj))
        except Exception:
            pass

    # 最终兜底：转为字符串
    try:
        return str(obj)
    except Exception:
        return "<不可序列化对象>"


def safe_json_dumps(obj, debug=True, **kwargs):
    """安全的JSON序列化，包含错误处理和调试信息
    
    Args:
        obj: 要序列化的对象
        debug: 是否显示调试信息（默认True）
        **kwargs: 传递给json.dumps的其他参数
    
    Returns:
        JSON字符串
    """
    try:
        # 首先尝试直接序列化
        return json.dumps(obj, **kwargs)
    except (TypeError, ValueError) as e:
        # 尝试使用make_json_safe清理数据
        try:
            cleaned_obj = make_json_safe(obj)
            result = json.dumps(cleaned_obj, **kwargs)
            
            # 只有在debug模式下才显示清理信息
            if debug:
                print("🔧 JSON数据已自动清理并成功序列化")
            
            return result
        except Exception as e2:
            # 只有在真正失败时才显示错误信息
            if debug:
                print(f"❌ JSON序列化错误: {str(e)}")
                print(f"🔍 尝试序列化的数据类型: {type(obj)}")
                print(f"🔍 数据内容预览:")
                
                # 递归检查数据结构中的问题类型
                def find_problematic_types(data, path="root", max_depth=3, current_depth=0):
                    if current_depth >= max_depth:
                        return
                        
                    if isinstance(data, dict):
                        for key, value in data.items():
                            current_path = f"{path}.{key}"
                            if not isinstance(value, (str, int, float, bool, list, dict, type(None))):
                                print(f"  ⚠️  {current_path}: {type(value)} = {repr(value)[:100]}...")
                            elif isinstance(value, (dict, list)) and current_depth < max_depth - 1:
                                find_problematic_types(value, current_path, max_depth, current_depth + 1)
                    elif isinstance(data, list):
                        for i, item in enumerate(data[:5]):  # 只检查前5个元素
                            current_path = f"{path}[{i}]"
                            if not isinstance(item, (str, int, float, bool, list, dict, type(None))):
                                print(f"  ⚠️  {current_path}: {type(item)} = {repr(item)[:100]}...")
                            elif isinstance(item, (dict, list)) and current_depth < max_depth - 1:
                                find_problematic_types(item, current_path, max_depth, current_depth + 1)
                
                find_problematic_types(obj)
                print(f"❌ 数据清理后仍然失败: {str(e2)}")
            
            # 返回错误信息的JSON
            return json.dumps({
                "error": "JSON serialization failed",
                "original_error": str(e),
                "cleanup_error": str(e2),
                "data_type": str(type(obj))
            }, **kwargs)


def quiet_json_dumps(obj, **kwargs):
    """静默的JSON序列化，不显示任何调试信息，只在真正失败时抛出异常"""
    return safe_json_dumps(obj, debug=False, **kwargs)
