import asyncio, json, time, logging
import contextlib
from src.servers.config import ROLE_TO_AGENT


class BaseStreamer:
    def __init__(self, step_ms: int = 900):
        self.ts = int(time.time() * 1000)
        self.step_ms = step_ms

    def _bump(self):
        self.ts += self.step_ms
        return self.ts

    def system(self, content: str):
        raise NotImplementedError

    def agent(self, role_key: str, content: str):
        raise NotImplementedError

    def price(self, value: float):
        raise NotImplementedError


class ConsoleStreamer(BaseStreamer):
    def system(self, content: str):
        ts = self._bump()
        print(f"[system] {content}")

    def agent(self, role_key: str, content: str):
        ts = self._bump()
        agent_id = ROLE_TO_AGENT.get(role_key or "", ROLE_TO_AGENT["_default"])
        print(f"[agent:{agent_id}] {content}")

    def price(self, value: float):
        ts = self._bump()
        print(f"[price] {float(value):.4f}")

class WebSocketStreamer(BaseStreamer):
    def __init__(self, ws, step_ms: int = 900):
        super().__init__(step_ms=step_ms)
        self.ws = ws
        self._queue = asyncio.Queue()
        self._worker = asyncio.create_task(self._send_worker())
        self._closed = False

    async def _send_worker(self):
        try:
            while True:
                payload = await self._queue.get()
                try:
                    await self.ws.send(json.dumps(payload, ensure_ascii=False))
                except Exception:
                    logging.exception("WebSocket send failed")
                finally:
                    self._queue.task_done()
        except asyncio.CancelledError:
            # flush remaining (best-effort)
            while not self._queue.empty():
                payload = await self._queue.get()
                try:
                    await self.ws.send(json.dumps(payload, ensure_ascii=False))
                except Exception:
                    logging.exception("WebSocket send failed during cancel flush")
                finally:
                    self._queue.task_done()
            raise

    def _enqueue(self, payload: dict):
        if self._closed:
            return
        self._queue.put_nowait(payload)

    async def drain(self):
        # 等待所有已入队的消息发送完毕
        await self._queue.join()

    async def aclose(self):
        # 关闭 worker 任务（在连接结束或 server 退出时调用）
        if not self._closed:
            self._closed = True
            self._worker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._worker

    def system(self, content: str):
        ts = self._bump()
        self._enqueue({"type": "system", "content": content, "ts": ts})

    def agent(self, role_key: str, content: str):
        ts = self._bump()
        agent_id = ROLE_TO_AGENT.get(role_key or "", ROLE_TO_AGENT["_default"])
        self._enqueue({"type": "agent_message", "agentId": agent_id, "content": content, "ts": ts})

    def price(self, value: float):
        ts = self._bump()
        self._enqueue({"type": "price", "price": float(value), "ts": ts})



class MultiStreamer(BaseStreamer):
    def __init__(self, *streamers, step_ms: int = 900):
        super().__init__(step_ms=step_ms)
        self.streamers = list(streamers)

    def _fanout(self, fn_name: str, *args, **kwargs):
        # 统一步进，再把同一个 ts“复制”给子 streamer：
        ts = self._bump()
        for s in self.streamers:
            # 对齐子 streamer 的 ts（保持时间线有序）
            s.ts = ts - s.step_ms  # 让子 streamer 下一次 _bump() 等于 ts
            getattr(s, fn_name)(*args, **kwargs)

    def system(self, content: str):
        self._fanout("system", content)

    def agent(self, role_key: str, content: str):
        self._fanout("agent", role_key, content)

    def price(self, value: float):
        self._fanout("price", value)