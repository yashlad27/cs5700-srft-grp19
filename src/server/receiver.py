# recieve ACKs from clients and update state

# server/receiver.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple, Optional

from server_state import ServerState
from window_manager import WindowManager
from common.constants import FLAG_ACK, FLAG_FIN
from common.packet import decode_packet

ClientAddr = Tuple[str, int]


@dataclass
class ReceiveResult:
    ack_seq: Optional[int] = None
    close: bool = False

class Receiver:
    def __init__(self, state: ServerState, wm: WindowManager):
        self.state = state
        self.wm = wm

    def handle_datagram(self, data: bytes, addr: ClientAddr) -> ReceiveResult:
        # 1) bind to single client (optional)
        with self.state.lock:
            self.state.stats["pkts_in"] += 1
            if self.state.client is None:
                self.state.client = addr
            elif self.state.client != addr:
                # ignore other clients in single-client mode
                return ReceiveResult()

        # 2) decode + verify (placeholder)
        pkt = self._decode_and_verify(data)
        if pkt is None:
            with self.state.lock:
                self.state.stats["corrupt_in"] += 1
            return ReceiveResult()

        # 3) dispatch by msg_type
        if pkt["type"] == "DATA":
            return self._on_data(pkt)
        elif pkt["type"] == "FIN":
            return ReceiveResult(close=True)
        elif pkt["type"] == "HELLO":
            # handshake (Phase2): respond from sender module typically
            return ReceiveResult()
        else:
            return ReceiveResult()

    def _on_data(self, pkt) -> ReceiveResult:
        seq = pkt["seq"]
        payload: bytes = pkt["payload"]

        is_new, triggered = self.wm.mark_received(seq, payload)
        if not is_new:
            with self.state.lock:
                self.state.stats["dup_in"] += 1
            return ReceiveResult(ack_seq=seq)

        if not self.wm.in_window(seq):
            with self.state.lock:
                self.state.stats["out_of_order_in"] += 1
            # out-of-window: drop but ACK expected-seq-1 to prompt retransmit
            return ReceiveResult(ack_seq=self.wm.expected_seq - 1)

        # delver in-order chunks to file
        delivered = self.wm.pop_in_order()
        if delivered:
            self._deliver_to_file(delivered)

        # cumulative：expected_seq-1
        return ReceiveResult(ack_seq=self.wm.expected_seq - 1)

    def _deliver_to_file(self, chunks):
        # chunks: list[(seq, payload)]
        with self.state.lock:
            # init file if needed
            if self.state.file_ctx.fp is None:
                out_dir = self.state.ensure_out_dir()
                name = self.state.file_ctx.filename or "output.bin"
                path = out_dir / name
                self.state.file_ctx.fp = open(path, "wb")

            fp = self.state.file_ctx.fp

        for _, payload in chunks:
            fp.write(payload)
            with self.state.lock:
                self.state.stats["delivered"] += 1
                self.state.file_ctx.written_chunks += 1

    def _decode_and_verify(self, raw: bytes, FLAG_HELLO=None):
        """
        Decode and verify a packet.
        - Uses common.packet.decode_packet(), which already verifies checksum.
        - Returns normalized dict for internal handling, or None if invalid/corrupt.
        """
        pkt = decode_packet(raw)
        if pkt is None:
            return None

        flags = pkt["flags"]

        # Normalize "type" so the rest of receiver code is clean.
        # If you们 flags 不是 bitmask，而是枚举值，就按实际改。
        if flags & FLAG_ACK:
            msg_type = "ACK"
        elif flags & FLAG_FIN:
            msg_type = "FIN"
        elif "FLAG_HELLO" in globals() and (flags & FLAG_HELLO):
            msg_type = "HELLO"
        else:
            # default treat as DATA if no explicit type bit set
            msg_type = "DATA"

        return {
            "type": msg_type,
            "seq": pkt["seq_num"],
            "ack": pkt["ack_num"],
            "flags": flags,
            "conn_id": pkt["conn_id"],
            "payload": pkt["payload"],  # bytes
            "payload_len": pkt["payload_length"]
        }