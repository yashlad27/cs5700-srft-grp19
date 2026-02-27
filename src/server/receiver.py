# recieve ACKs from clients and update state

# server/receiver.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple, Optional

from .server_state import ServerState
from .window_manager import WindowManager

ClientAddr = Tuple[str, int]

# TODO: need to integrate common protocol utils here (decode + checksum verify)
# from common.constant import decode_packet, Packet, MsgType, verify_checksum

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

    def _decode_and_verify(self, raw: bytes):
        """
        Replace this with your real common.decode + checksum/tag verify.
        Expected to return dict-like: {"type","seq","payload"...}
        """
        # TODO: integrate common protocol
        return None