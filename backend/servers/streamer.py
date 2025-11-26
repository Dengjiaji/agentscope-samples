# -*- coding: utf-8 -*-
import asyncio, json, time, logging
import contextlib
from backend.config.constants import ROLE_TO_AGENT


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

    def default_print(self, content: str, type: str):
        raise NotImplementedError

    def print(self, type: str = "", content: str = "", **kwargs):
        """
        Generic print interface
        :param content: Output content
        :param type: Message type, options: system / agent / price / custom
        """
        if type == "system" or type == "":
            self.system(content)
        elif type == "agent":
            # Allow passing role_key in kwargs
            role_key = kwargs.get("role_key", "_default")
            self.agent(role_key, content)
        elif type == "price":
            try:
                value = float(content)
            except ValueError:
                value = 0.0
            self.price(value)
        else:
            self.default_print(content, type)


class ConsoleStreamer(BaseStreamer):
    def system(self, content: str):
        print(f"[system] {content}")

    def agent(self, role_key: str, content: str):
        agent_id = ROLE_TO_AGENT.get(role_key or "", ROLE_TO_AGENT["_default"])
        print(f"[agent:{agent_id}] {content}")

    def price(self, value: float):
        print(f"[price] {float(value):.4f}")

    def default_print(self, content: str, type: str):
        print(f"[{type}] {content}")


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
                    logging.exception(
                        "WebSocket send failed during cancel flush",
                    )
                finally:
                    self._queue.task_done()
            raise

    def _enqueue(self, payload: dict):
        if self._closed:
            return
        self._queue.put_nowait(payload)

    async def drain(self):
        # Wait for all queued messages to be sent
        await self._queue.join()

    async def aclose(self):
        # Close worker task (called when connection ends or server exits)
        if not self._closed:
            self._closed = True
            self._worker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._worker

    def system(self, content: str):
        self._enqueue({"type": "system", "content": content, "ts": ts})

    def agent(self, role_key: str, content: str):
        agent_id = ROLE_TO_AGENT.get(role_key or "", ROLE_TO_AGENT["_default"])
        self._enqueue(
            {
                "type": "agent_message",
                "agentId": agent_id,
                "content": content,
                "ts": ts,
            },
        )

    def price(self, value: float):
        self._enqueue({"type": "price", "price": float(value), "ts": ts})

    def default_print(self, content: str, type: str):
        self._enqueue({"type": type, "content": content, "ts": ts})


class MultiStreamer(BaseStreamer):
    def __init__(self, *streamers, step_ms: int = 900):
        super().__init__(step_ms=step_ms)
        self.streamers = list(streamers)

    def _fanout(self, fn_name: str, *args, **kwargs):
        # Unified step, then "copy" the same ts to child streamers:

        for s in self.streamers:
            # Align child streamer's ts (maintain timeline order)
            s.ts = (
                ts - s.step_ms
            )  # Make child streamer's next _bump() equal to ts
            getattr(s, fn_name)(*args, **kwargs)

    def system(self, content: str):
        self._fanout("system", content)

    def agent(self, role_key: str, content: str):
        self._fanout("agent", role_key, content)

    def price(self, value: float):
        self._fanout("price", value)

    def default_print(self, content: str, type: str):
        self._fanout("default_print", content, type)


class BroadcastStreamer(BaseStreamer):
    """
    Thread-safe broadcast Streamer, used to forward messages from synchronous code to asynchronous broadcast system
    """

    def __init__(
        self,
        broadcast_callback,
        event_loop,
        step_ms: int = 900,
        console_output: bool = True,
    ):
        """
        Args:
            broadcast_callback: Async callback function, receives message dict as parameter
            event_loop: asyncio event loop
            step_ms: Time step (milliseconds)
            console_output: Whether to also output to console
        """
        super().__init__(step_ms=step_ms)
        self.broadcast_callback = broadcast_callback
        self.loop = event_loop
        self.console_output = console_output

    def _broadcast(self, message: dict):
        """Use run_coroutine_threadsafe to safely schedule async broadcast"""
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.broadcast_callback(message),
                self.loop,
            )

        # Optional console output
        if self.console_output:
            msg_type = message.get("type", "unknown")
            content = message.get("content", "")
            print(f"[{msg_type}] {content}")

    def _normalize_message(
        self,
        event_type: str,
        content: str,
        **kwargs,
    ) -> dict:
        """Normalize message format, handle various special types"""
        from datetime import datetime

        message = {
            "type": event_type,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "ts": self._bump(),
            **kwargs,
        }

        # Special handling: conference events
        if event_type == "conference_start":
            message["conferenceId"] = (
                kwargs.get("conferenceId")
                or kwargs.get("conference_id")
                or f'conf-{message["ts"]}'
            )
            message["title"] = kwargs.get("title", content)
            message["participants"] = kwargs.get("participants", [])

        elif event_type == "conference_message":
            message["conferenceId"] = kwargs.get("conferenceId") or kwargs.get(
                "conference_id",
            )
            message["agent"] = kwargs.get("agent") or kwargs.get("agentId")
            message["role"] = kwargs.get("role", "Agent")

        elif event_type == "conference_end":
            message["conferenceId"] = kwargs.get("conferenceId") or kwargs.get(
                "conference_id",
            )

        elif event_type in ("agent_message", "agent"):
            # Unified handling of agent and agent_message types
            message["type"] = "agent_message"
            message["agentId"] = (
                kwargs.get("agentId")
                or kwargs.get("agent_id")
                or kwargs.get("agent", "unknown")
            )
            if "agent_name" in kwargs:
                message["agentName"] = kwargs["agent_name"]
            if "role" in kwargs:
                message["role"] = kwargs["role"]

        return message

    def system(self, content: str):
        """System message"""
        message = self._normalize_message("system", content)
        self._broadcast(message)

    def agent(self, role_key: str, content: str):
        """Agent message"""
        agent_id = ROLE_TO_AGENT.get(role_key or "", ROLE_TO_AGENT["_default"])
        message = self._normalize_message(
            "agent_message",
            content,
            agentId=agent_id,
        )
        self._broadcast(message)

    def price(self, value: float):
        """Price update"""
        message = self._normalize_message(
            "price",
            str(value),
            price=float(value),
        )
        self._broadcast(message)

    def default_print(self, content: str, type: str):
        """Default print (generic interface)"""
        message = self._normalize_message(type, content)
        self._broadcast(message)

    def print(self, type: str = "", content: str = "", **kwargs):
        """
        Generic print interface (enhanced version)
        Supports arbitrary event types and custom fields
        """
        if type in ("system", ""):
            self.system(content)
        elif type == "agent":
            role_key = kwargs.get("role_key", "_default")
            self.agent(role_key, content)
        elif type == "price":
            try:
                value = float(content)
                self.price(value)
            except ValueError:
                self.price(0.0)
        else:
            # Handle all other message types
            message = self._normalize_message(type, content, **kwargs)
            self._broadcast(message)
