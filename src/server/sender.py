# send file chunks to client, and handle ACKs
# server/sender.py
from __future__ import annotations
from typing import Tuple, Optional
import socket
from server.server_state import ServerState
from common.packet import encode_packet
from common.constants import FLAG_ACK, FLAG_SYN_ACK, FLAG_DATA, FLAG_FIN_DATA

ClientAddr = Tuple[str, int]

class Sender:
    def __init__(self, state: ServerState, sock: socket.socket):
        self.state = state
        self.sock = sock

    def send_ack(self, addr: ClientAddr, ack_seq: int) -> None:
        if ack_seq < 0:
            return
        pkt = self._build_ack(ack_seq)
        self.sock.sendto(pkt, addr)
        with self.state.lock:
            self.state.stats["pkts_out"] += 1
            self.state.stats["acks_out"] += 1

    def _build_ack(self, ack_seq: int) -> bytes:
        return encode_packet(
            seq_num=0,
            ack_num=ack_seq,
            flags=FLAG_ACK,
            payload=b'',
            conn_id=0
        )