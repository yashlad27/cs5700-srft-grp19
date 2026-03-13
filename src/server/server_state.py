# state management
# server/server_state.py
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
import threading
import time
import os

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
    file_size: int = 0  # size of file being transferred

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
        "data_out": 0,
        "acks_in": 0,
        "acks_out": 0,
        "dup_in": 0,
        "corrupt_in": 0,
        "out_of_order_in": 0,
        "delivered": 0,
        "retransmitted": 0,
    })

    # timing
    transfer_start: Optional[float] = None
    transfer_end: Optional[float] = None

    def ensure_out_dir(self) -> Path:
        p = Path(self.cfg.out_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    def start_transfer_timer(self):
        self.transfer_start = time.time()

    def stop_transfer_timer(self):
        self.transfer_end = time.time()

    def get_transfer_duration(self) -> float:
        if self.transfer_start is None or self.transfer_end is None:
            return 0.0
        return self.transfer_end - self.transfer_start

    def format_duration(self, seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def write_stats_report(self, output_path: Optional[str] = None) -> str:
        duration = self.get_transfer_duration()
        duration_str = self.format_duration(duration)
        filename = self.file_ctx.filename or "unknown"
        file_size = self.file_ctx.file_size

        report_lines = [
            f"Name of the transferred file: {filename}",
            f"Size of the transferred file: {file_size}",
            f"The number of packets sent from the server: {self.stats['pkts_out']}",
            f"The number of retransmitted packets from the server: {self.stats['retransmitted']}",
            f"The number of packets received from the client: {self.stats['pkts_in']}",
            f"The time duration of the file transfer ({duration_str}): {duration:.2f}s",
        ]
        report = "\n".join(report_lines) + "\n"

        if output_path is None:
            out_dir = self.ensure_out_dir()
            output_path = str(out_dir / "transfer_stats.txt")

        with open(output_path, "w") as f:
            f.write(report)

        print(f"[server] Stats report written to {output_path}")
        print(report)
        return report