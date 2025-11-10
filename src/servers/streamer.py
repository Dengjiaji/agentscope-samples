import asyncio, json, time, logging
import contextlib
from src.config.constants import ROLE_TO_AGENT


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

    def print(self, type: str="", content: str = "", **kwargs):
        """
        通用打印接口
        :param content: 输出内容
        :param type: 消息类型，可选 system / agent / price / 自定义
        """
        if type == "system" or type == "":
            self.system(content)
        elif type == "agent":
            # 允许 kwargs 里传 role_key
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
        ts = self._bump()
        print(f"[system] {content}")

    def agent(self, role_key: str, content: str):
        ts = self._bump()
        agent_id = ROLE_TO_AGENT.get(role_key or "", ROLE_TO_AGENT["_default"])
        print(f"[agent:{agent_id}] {content}")

    def price(self, value: float):
        ts = self._bump()
        print(f"[price] {float(value):.4f}")

    def default_print(self, content: str, type: str):
        ts = self._bump()
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

    def default_print(self, content: str, type: str):
        ts = self._bump()
        self._enqueue({"type": type, "content": content, "ts": ts})



class MultiStreamer(BaseStreamer):
    def __init__(self, *streamers, step_ms: int = 900):
        super().__init__(step_ms=step_ms)
        self.streamers = list(streamers)

    def _fanout(self, fn_name: str, *args, **kwargs):
        # 统一步进，再把同一个 ts"复制"给子 streamer：
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

    def default_print(self, content: str, type: str):
        self._fanout("default_print", content, type)


class BroadcastStreamer(BaseStreamer):
    """
    线程安全的广播Streamer，用于将消息从同步代码转发到异步广播系统
    """
    def __init__(self, broadcast_callback, event_loop, step_ms: int = 900, console_output: bool = True):
        """
        Args:
            broadcast_callback: 异步回调函数，接收消息字典作为参数
            event_loop: asyncio事件循环
            step_ms: 时间步长（毫秒）
            console_output: 是否同时输出到控制台
        """
        super().__init__(step_ms=step_ms)
        self.broadcast_callback = broadcast_callback
        self.loop = event_loop
        self.console_output = console_output
    
    def _broadcast(self, message: dict):
        """使用run_coroutine_threadsafe安全地调度异步广播"""
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.broadcast_callback(message),
                self.loop
            )
        
        # 可选的控制台输出
        if self.console_output:
            msg_type = message.get('type', 'unknown')
            content = message.get('content', '')
            print(f"[{msg_type}] {content}")
    
    def _normalize_message(self, event_type: str, content: str, **kwargs) -> dict:
        """标准化消息格式，处理各种特殊类型"""
        from datetime import datetime
        
        message = {
            'type': event_type,
            'content': content,
            'timestamp': datetime.now().isoformat(),
            'ts': self._bump(),
            **kwargs
        }
        
        # 特殊处理：conference事件
        if event_type == 'conference_start':
            message['conferenceId'] = kwargs.get('conferenceId') or kwargs.get('conference_id') or f'conf-{message["ts"]}'
            message['title'] = kwargs.get('title', content)
            message['participants'] = kwargs.get('participants', [])
        
        elif event_type == 'conference_message':
            message['conferenceId'] = kwargs.get('conferenceId') or kwargs.get('conference_id')
            message['agent'] = kwargs.get('agent') or kwargs.get('agentId')
            message['role'] = kwargs.get('role', 'Agent')
        
        elif event_type == 'conference_end':
            message['conferenceId'] = kwargs.get('conferenceId') or kwargs.get('conference_id')
        
        elif event_type in ('agent_message', 'agent'):
            # 统一处理 agent 和 agent_message 类型
            message['type'] = 'agent_message'
            message['agentId'] = kwargs.get('agentId') or kwargs.get('agent_id') or kwargs.get('agent', 'unknown')
            if 'agent_name' in kwargs:
                message['agentName'] = kwargs['agent_name']
            if 'role' in kwargs:
                message['role'] = kwargs['role']
        
        return message
    
    def system(self, content: str):
        """系统消息"""
        message = self._normalize_message('system', content)
        self._broadcast(message)
    
    def agent(self, role_key: str, content: str):
        """Agent消息"""
        agent_id = ROLE_TO_AGENT.get(role_key or "", ROLE_TO_AGENT["_default"])
        message = self._normalize_message('agent_message', content, agentId=agent_id)
        self._broadcast(message)
    
    def price(self, value: float):
        """价格更新"""
        message = self._normalize_message('price', str(value), price=float(value))
        self._broadcast(message)
    
    def default_print(self, content: str, type: str):
        """默认打印（通用接口）"""
        message = self._normalize_message(type, content)
        self._broadcast(message)
    
    def print(self, event_type: str = "", content: str = "", **kwargs):
        """
        通用打印接口（增强版）
        支持任意事件类型和自定义字段
        """
        if event_type in ("system", ""):
            self.system(content)
        elif event_type == "agent":
            role_key = kwargs.get("role_key", "_default")
            self.agent(role_key, content)
        elif event_type == "price":
            try:
                value = float(content)
                self.price(value)
            except ValueError:
                self.price(0.0)
        else:
            # 处理所有其他类型的消息
            message = self._normalize_message(event_type, content, **kwargs)
            self._broadcast(message)