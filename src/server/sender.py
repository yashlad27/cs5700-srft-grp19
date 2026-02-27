# send file chunks to client, and handle ACKs
# server/sender.py
from __future__ import annotations
from typing import Tuple, Optional
import socket
from .server_state import ServerState
from ..common.packet import encode_packet, Packet, MsgType

ClientAddr = Tuple[str, int]

# todo: integrate common packet builder for ACK and handshake reply
# from common.protocol import build_ack_packet, build_handshake_reply

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
        return encode_packet(Packet(msg_type=MsgType.ACK, ack=ack_seq))