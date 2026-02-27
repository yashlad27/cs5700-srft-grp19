# src/common/protocol.py
from __future__ import annotations
import enum
import struct
import zlib
from dataclasses import dataclass
from typing import Tuple

class MsgType(enum.IntEnum):
    DATA = 0
    ACK = 1
    HELLO = 2
    FIN = 3

VERSION = 1
HEADER_FMT = "!BBIIHI"
HEADER_SIZE = struct.calcsize(HEADER_FMT)

@dataclass
class Packet:
    msg_type: MsgType
    seq: int = 0
    ack: int = 0
    payload: bytes = b""

def _crc32(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF

def encode_packet(pkt: Packet) -> bytes:
    payload = pkt.payload or b""
    payload_len = len(payload)

    # checksum field initially 0 for computing
    header_wo_checksum = struct.pack(
        HEADER_FMT,
        VERSION,
        int(pkt.msg_type),
        pkt.seq,
        pkt.ack,
        payload_len,
        0
    )

    checksum = _crc32(header_wo_checksum + payload)

    header = struct.pack(
        HEADER_FMT,
        VERSION,
        int(pkt.msg_type),
        pkt.seq,
        pkt.ack,
        payload_len,
        checksum
    )
    return header + payload

def decode_packet(raw: bytes) -> Tuple[Packet, bool]:
    """
    Returns (packet, ok). ok=False means checksum/version/length invalid.
    """
    if len(raw) < HEADER_SIZE:
        return Packet(MsgType.DATA), False

    version, t, seq, ack, payload_len, checksum = struct.unpack(
        HEADER_FMT, raw[:HEADER_SIZE]
    )

    if version != VERSION:
        return Packet(MsgType.DATA), False
    if len(raw) != HEADER_SIZE + payload_len:
        return Packet(MsgType.DATA), False

    payload = raw[HEADER_SIZE:HEADER_SIZE + payload_len]

    header_wo_checksum = struct.pack(
        HEADER_FMT,
        version,
        t,
        seq,
        ack,
        payload_len,
        0
    )
    calc = _crc32(header_wo_checksum + payload)
    if calc != checksum:
        return Packet(MsgType.DATA), False

    try:
        msg_type = MsgType(t)
    except ValueError:
        return Packet(MsgType.DATA), False

    return Packet(msg_type=msg_type, seq=seq, ack=ack, payload=payload), True