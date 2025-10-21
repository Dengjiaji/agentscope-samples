from __future__ import annotations
from typing import Any, Dict, List, Optional
import math, random, time
from src.servers.config import ROLE_TO_AGENT

def sandbox_json_to_events(
    data: Dict[str, Any],
    *,
    now_ms: Optional[int] = None,
    step_ms: int = 900,
    include_prices: bool = True,
    synth_price_len: int = 300,
    seed_price: float = 100.0,
) -> List[Dict[str, Any]]:
    """
    将 sandbox JSON（形如 sandbox_day_YYYY_MM_DD.json）映射为统一事件序列。
    事件格式（与前端一致）：
      - {'type': 'agent_message', 'agentId': <str>, 'content': <str>, 'ts': <int>}
      - {'type': 'system',        'content': <str>,                  'ts': <int>}
      - {'type': 'price',         'price':   <float>,                'ts': <int>}

    参数：
      now_ms: 事件时间戳的起点（毫秒）。默认 time.time()*1000。
      step_ms: 相邻事件之间的时间间隔（毫秒）。
      include_prices: 若 True 且找不到真实价格事件，则合成一条价格轨迹。
      synth_price_len: 合成价格的点数。
      seed_price: 合成价格的起始价。

    返回：
      事件列表，按时间顺序排列。
    """
    ts = int(now_ms if now_ms is not None else time.time() * 1000)
    events: List[Dict[str, Any]] = []

    def push_system(content: str):
        nonlocal ts
        ts += step_ms
        events.append({"type": "system", "content": content, "ts": ts})

    def push_agent(role_key: Optional[str], content: str):
        nonlocal ts
        ts += step_ms
        agent_id = ROLE_TO_AGENT.get(role_key or "", ROLE_TO_AGENT["_default"])
        events.append({"type": "agent_message", "agentId": agent_id, "content": content, "ts": ts})

    def push_price(p: float):
        nonlocal ts
        ts += step_ms
        events.append({"type": "price", "price": float(p), "ts": ts})

    # ========= 解析 pre_market =========
    pre = (data or {}).get("pre_market", {})
    pre_details = pre.get("details", {}) if isinstance(pre, dict) else {}

    # 1) 一致性信号（预市场汇总）
    #    data['pre_market']['details']['signals'][ticker] => {signal, confidence, reasoning, action...}
    signals = pre_details.get("signals") or {}
    if isinstance(signals, dict):
        for ticker, sig in signals.items():
            if not isinstance(sig, dict):
                continue
            signal = sig.get("signal") or "neutral"
            conf = sig.get("confidence")
            reasoning = sig.get("reasoning") or ""
            # 作为“情绪分析师（delta）”发的一条共识说明
            msg = f"[Consensus] {ticker}: {signal}"
            if conf is not None:
                try:
                    msg += f" ({float(conf):.1f}%)"
                except Exception:
                    pass
            if reasoning:
                msg += f" — {reasoning}"
            push_agent("portfolio_manager", msg)

    # 2) 各角色逐票信号
    #    data['pre_market']['details']['live_env']['ana_signals'][role][ticker] = 'bearish' | 'bullish' | 'neutral'
    live_env = pre_details.get("live_env") or {}
    ana_signals = live_env.get("ana_signals") or {}
    if isinstance(ana_signals, dict):
        for role_key, per_ticker in ana_signals.items():
            if not isinstance(per_ticker, dict):
                continue
            for ticker, sig in per_ticker.items():
                msg = f"{ticker}: {sig}"
                push_agent(role_key, msg)

    # 3) 预市场的“真实收益率代理” -> system
    #    data['pre_market']['details']['live_env']['real_returns'][ticker] = float
    real_returns = live_env.get("real_returns") or {}
    rr_values = []
    if isinstance(real_returns, dict):
        for ticker, r in real_returns.items():
            try:
                pct = float(r) * 100.0
                rr_values.append(float(r))
                push_system(f"Pre-market real return proxy: {ticker} {pct:+.2f}%")
            except Exception:
                continue

    # ========= 解析 post_market =========
    post = (data or {}).get("post_market", {})

    # 4) 记忆工具调用结果
    #    data['post_market']['memory_tool_calls_results'] 是一个 list
    mtcr = post.get("memory_tool_calls_results") or []
    if isinstance(mtcr, list):
        for item in mtcr:
            args = (item or {}).get("args") or {}
            new_content = args.get("new_content") or ""
            if new_content:
                push_system(f"memory updated: {new_content}")

    # ========= 价格轨迹（如无价格事件则合成） =========
    has_price = any(e.get("type") == "price" for e in events)
    if include_prices and not has_price:
        # 用预市场 real_returns 的“均值方向”暗示当天 drift，增强一点真实感
        drift = 0.0
        if rr_values:
            drift = sum(rr_values) / max(len(rr_values), 1)  # 平均真实收益率
            # 缩小到每步的微弱漂移
            drift = drift / 50.0

        p = float(seed_price)
        vol = 0.6  # 步进波动（可调）
        for i in range(synth_price_len):
            step = (random.random() - 0.5) * (2 * vol) + drift
            p = max(1.0, p + step)
            push_price(p)

    # 最后保证时间顺序
    events.sort(key=lambda e: e.get("ts", 0))
    return events