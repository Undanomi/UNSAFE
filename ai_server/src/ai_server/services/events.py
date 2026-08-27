from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from collections.abc import AsyncIterator
from dataclasses import dataclass


@dataclass(frozen=True)
class ServerEvent:
    event: str
    data: dict

    def encode(self) -> str:
        return f"event: {self.event}\ndata: {json.dumps(self.data, ensure_ascii=False)}\n\n"


class EventBroker:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[ServerEvent | None]]] = defaultdict(set)

    async def publish(self, session_id: str, event: ServerEvent) -> None:
        for queue in list(self._subscribers[session_id]):
            await queue.put(event)

    async def close(self, session_id: str) -> None:
        for queue in list(self._subscribers[session_id]):
            await queue.put(None)

    def subscribe(self, session_id: str) -> asyncio.Queue[ServerEvent | None]:
        queue: asyncio.Queue[ServerEvent | None] = asyncio.Queue()
        self._subscribers[session_id].add(queue)
        return queue

    async def events(
        self, session_id: str, queue: asyncio.Queue[ServerEvent | None]
    ) -> AsyncIterator[ServerEvent]:
        try:
            while True:
                event = await queue.get()
                if event is None:
                    return
                yield event
        finally:
            self._subscribers[session_id].discard(queue)
            if not self._subscribers[session_id]:
                self._subscribers.pop(session_id, None)
