# timeout / retransmit queue logic
# monitor sent packets, trigger retransmits after TIMEOUT (500ms)
# Max retries = 10 before giving up
# server/retransmit_queue.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Tuple
import time
import heapq
import socket

ClientAddr = Tuple[str, int]

@dataclass(order=True)
class _Item:
    deadline: float
    key: str = field(compare=False)
    payload: bytes = field(compare=False)
    addr: ClientAddr = field(compare=False)
    retries: int = field(compare=False, default=0)

class RetransmitQueue:
    def __init__(self, sock: socket.socket = None, rto_ms: int = 500, max_retries: int = 10,
                 server_state=None, send_func=None):
        self.sock = sock
        self.rto = rto_ms / 1000.0
        self.max_retries = max_retries
        self.heap: list[_Item] = []
        self.items: Dict[str, _Item] = {}
        self.server_state = server_state
        self.send_func = send_func  # callback: (payload_bytes, dst_ip) -> None

    def add(self, key: str, payload: bytes, addr: ClientAddr) -> None:
        item = _Item(deadline=time.time() + self.rto, key=key, payload=payload, addr=addr)
        self.items[key] = item
        heapq.heappush(self.heap, item)

    def ack(self, key: str) -> None:
        # remove logically; heap item will be skipped later
        self.items.pop(key, None)

    def tick(self) -> None:
        now = time.time()
        while self.heap and self.heap[0].deadline <= now:
            item = heapq.heappop(self.heap)
            cur = self.items.get(item.key)
            if cur is None:
                continue  # already acked
            if cur.retries >= self.max_retries:
                self.items.pop(item.key, None)
                continue
            # retransmit
            if self.send_func is not None:
                self.send_func(cur.payload, cur.addr)
            elif self.sock is not None:
                self.sock.sendto(cur.payload, cur.addr)
            cur.retries += 1
            cur.deadline = now + self.rto
            heapq.heappush(self.heap, cur)
            if self.server_state is not None:
                with self.server_state.lock:
                    self.server_state.stats["retransmitted"] += 1