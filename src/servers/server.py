# src/servers/server.py
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

import websockets

from src.memory.mem0_core import initialize_mem0_integration

# --- logging ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from src.servers.replay import sandbox_json_to_events
from src.servers.streamer import WebSocketStreamer, ConsoleStreamer, MultiStreamer

# Core simulation + config
from live_trading_thinking_fund import LiveTradingThinkingFund
from src.config.env_config import LiveThinkingFundConfig


async def run_replay_to_ws(ws, date: str):
    """
    Replay mode: stream events from sandbox_logs/sandbox_day_YYYY_MM_DD.json to frontend.
    """
    try:
        fp = Path(f'./sandbox_logs/sandbox_day_{date.replace("-", "_")}.json')
        data = json.loads(fp.read_text(encoding="utf-8"))
        events = sandbox_json_to_events(data)
        for e in events:
            await ws.send(json.dumps(e, ensure_ascii=False))
            # keep a small cadence so frontend can animate progressively
            await asyncio.sleep(5.0)
    except Exception as e:
        logging.exception("stream_sandbox 出错")
        await ws.send(json.dumps({"type": "system", "content": f"Error: {e}"}))


async def run_realtime_to_ws(ws, cfg: dict):
    """
    Realtime mode: run LiveTradingThinkingFund for a single day and stream outputs to the frontend
    via WebSocketStreamer (optionally also echo to console).

    cfg keys (all optional except mode):
      - date: 'YYYY-MM-DD' (default: '2024-01-05')
      - tickers: 'AAPL,MSFT' or ['AAPL','MSFT'] (default: from LiveThinkingFundConfig)
      - config_name: str (used as data/config directory name)
      - max_comm_cycles: int (default: from LiveThinkingFundConfig)
      - force_run: bool
    """
    try:
        await ws.send(json.dumps({"type": "system", "content": "Run accepted"}))

        date = cfg.get("date", "2024-01-05")
        tickers = cfg.get("tickers")
        if isinstance(tickers, str):
            tickers = [s.strip() for s in tickers.split(",") if s.strip()]

        # load default env/config and allow overrides from cfg
        env_config = LiveThinkingFundConfig()
        config_name = cfg.get("config_name","test")
        mem0_integration = initialize_mem0_integration(base_dir=config_name)

        if config_name:
            env_config.config_name = config_name

        if not tickers:
            tickers = env_config.tickers

        # Build a streamer that outputs to WS
        ws_streamer = WebSocketStreamer(ws)

        # If you also want local console logs at the same time, uncomment MultiStreamer:
        streamer = MultiStreamer(ws_streamer, ConsoleStreamer())
        # streamer = ws_streamer

        # Initialize core fund with streamer so it can emit events to the frontend
        fund = LiveTradingThinkingFund(base_dir=env_config.config_name, streamer=streamer)

        # NOTE: This is synchronous; emitted websocket sends are scheduled via create_task and
        # will flush when control returns to the event loop.
        result = await asyncio.to_thread(
            fund.run_full_day_simulation,
            date=date,
            tickers=tickers,
            max_comm_cycles=cfg.get("max_comm_cycles", env_config.max_comm_cycles),
            force_run=cfg.get("force_run", False),
            enable_communications=not env_config.disable_communications,
            enable_notifications=not env_config.disable_notifications,
        )

        await ws.send(json.dumps({"type": "system", "content": "Run finished."}))
    except Exception as e:
        logging.exception("run_realtime_to_ws 出错")
        await ws.send(json.dumps({"type": "system", "content": f"Error: {e}"}))


async def handler(ws):
    logging.info("client connected")
    try:
        async for msg in ws:
            req = json.loads(msg)
            if req.get("type") == "run":
                cfg = req.get("config", {})
                date = cfg.get("date", "2024-01-05")
                mode = cfg.get("mode")
                if mode == "realtime":
                    # NEW: true realtime — run the core system and stream outputs to frontend
                    await run_realtime_to_ws(ws, cfg)
                elif mode == "replay":
                    await ws.send(json.dumps({"type": "system", "content": "Run accepted"}))
                    await run_replay_to_ws(ws, date)
                    await ws.send(json.dumps({"type": "system", "content": "Replay finished."}))
                else:
                    logging.exception("unknown pattern, only support realtime or replay")
                    await ws.send(json.dumps({"type": "system", "content": "Error: unknown mode"}))

    except websockets.ConnectionClosed:
        logging.info("client disconnected")
    except Exception:
        logging.exception("handler 出错")


async def main():
    host, port = "0.0.0.0", 8765
    logging.info(f"starting websocket server on ws://{host}:{port}")
    async with websockets.serve(handler, host, port):
        logging.info("server is listening; press Ctrl+C to stop.")
        # keep running
        await asyncio.Future()


if __name__ == "__main__":
    try:
        print(os.getcwd())
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nbye")