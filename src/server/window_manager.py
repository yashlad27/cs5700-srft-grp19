#Sliding window management for UNACKed packets
# Track which packets are in-flight, handle ACKs, slide window forward
# Window size: 10 (pulling from constants.py)
# server/window_manager.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

@dataclass
class WindowManager:
    window_size: int
    expected_seq: int = 0
    # cache: seq -> payload bytes
    buffer: Dict[int, bytes] = field(default_factory=dict)
    # record received seq for dedup (optional, can infer from buffer + expected)
    received: set[int] = field(default_factory=set)

    def in_window(self, seq: int) -> bool:
        return self.expected_seq <= seq < self.expected_seq + self.window_size

    def mark_received(self, seq: int, payload: bytes) -> Tuple[bool, bool]:
        """
        Returns: (is_new, is_in_order_delivery_trigger)
        - is_new: False if duplicate
        - is_in_order_delivery_trigger: True if seq == expected_seq (may unlock delivery)
        """
        if seq < self.expected_seq:
            return (False, False)  # old/duplicate
        if seq in self.received:
            return (False, False)

        if not self.in_window(seq):
            # out of window: you can drop or keep (I recommend drop, ask sender to retransmit)
            return (True, False)  # treat as new but not stored (caller decides)

        self.received.add(seq)
        self.buffer[seq] = payload
        return (True, seq == self.expected_seq)

    def pop_in_order(self) -> List[Tuple[int, bytes]]:
        """
        Pop and return all contiguous packets starting at expected_seq.
        """
        out: List[Tuple[int, bytes]] = []
        while self.expected_seq in self.buffer:
            payload = self.buffer.pop(self.expected_seq)
            out.append((self.expected_seq, payload))
            self.expected_seq += 1
        return out