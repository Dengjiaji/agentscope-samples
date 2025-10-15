# src/server.py
import asyncio, json, websockets, logging
from pathlib import Path
from mock import sandbox_json_to_events

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

async def stream_sandbox(ws, date):
    try:
        fp = Path(f'./sandbox_logs/sandbox_day_{date.replace("-", "_")}.json')
        data = json.loads(fp.read_text(encoding="utf-8"))
        events = sandbox_json_to_events(data)
        for e in events:
            await ws.send(json.dumps(e, ensure_ascii=False))
            await asyncio.sleep(5.0)
    except Exception as e:
        logging.exception("stream_sandbox 出错")
        await ws.send(json.dumps({"type":"system","content":f"Error: {e}"}))

async def handler(ws):
    logging.info("client connected")
    try:
        async for msg in ws:
            req = json.loads(msg)
            if req.get('type') == 'run':
                cfg = req.get('config', {})
                date = cfg.get('date', '2024-01-05')
                await ws.send(json.dumps({"type":"system","content":"Run accepted"}))
                await stream_sandbox(ws, date)
                await ws.send(json.dumps({"type":"system","content":"Replay finished."}))
    except websockets.ConnectionClosed:
        logging.info("client disconnected")
    except Exception:
        logging.exception("handler 出错")

async def main():
    host, port = '0.0.0.0', 8765
    logging.info(f"starting websocket server on ws://{host}:{port}")
    async with websockets.serve(handler, host, port):
        logging.info("server is listening; press Ctrl+C to stop.")
        # 持续运行
        await asyncio.Future()

if __name__=="__main__":
    try:
        import os
        print(os.getcwd())
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nbye")