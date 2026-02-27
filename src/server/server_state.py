# state management
# server/server_state.py
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
import threading

ClientAddr = Tuple[str, int]

@dataclass
class ServerConfig:
    listen_ip: str = "0.0.0.0"
    listen_port: int = 9000
    out_dir: str = "./received"
    chunk_size: int = 1200
    window_size: int = 64
    recv_buffer_limit: int = 4096  # max cached out-of-order packets
    rto_ms: int = 200              # retransmit timeout
    max_retries: int = 20

@dataclass
class SecurityContext:
    # Phase2: fill these once handshake completes
    enabled: bool = False
    conn_id: int = 0
    # e.g. k_enc, k_iv, replay window, etc.
    keys: Dict[str, bytes] = field(default_factory=dict)
    # for replay protection (packet_number window)
    highest_pn: int = -1
    seen_pn: set[int] = field(default_factory=set)

@dataclass
class FileReceiveContext:
    filename: Optional[str] = None
    expected_total_chunks: Optional[int] = None
    written_chunks: int = 0
    fp: Any = None  # file handle

@dataclass
class ServerState:
    cfg: ServerConfig
    lock: threading.Lock = field(default_factory=threading.Lock)

    # single active client (easy version)
    client: Optional[ClientAddr] = None

    # file receive info
    file_ctx: FileReceiveContext = field(default_factory=FileReceiveContext)

    # security
    sec: SecurityContext = field(default_factory=SecurityContext)

    # statistics (for debugging/report)
    stats: Dict[str, int] = field(default_factory=lambda: {
        "pkts_in": 0,
        "pkts_out": 0,
        "data_in": 0,
        "acks_out": 0,
        "dup_in": 0,
        "corrupt_in": 0,
        "out_of_order_in": 0,
        "delivered": 0,
    })

    def ensure_out_dir(self) -> Path:
        p = Path(self.cfg.out_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p