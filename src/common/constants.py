"""
constants.py — SRFT Protocol Constants
=======================================
THIS IS THE SINGLE SOURCE OF TRUTH.
Every team member imports from here. Nobody hardcodes values.

Usage: from common.constants import *
"""

import struct

# ============================================================
# NETWORK CONSTANTS
# ============================================================

SERVER_PORT = 5005          # Server listens on this port
CLIENT_PORT = 5006          # Client listens on this port (for ACKs/data back)
MTU = 1500                  # Standard Maximum Transmission Unit

# ============================================================
# PACKET SIZE CONSTANTS
# ============================================================

IP_HEADER_SIZE = 20         # Standard IPv4 header (no options)
UDP_HEADER_SIZE = 8         # Fixed UDP header
CUSTOM_HEADER_SIZE = 15     # Our protocol header (see layout below)
OVERHEAD = IP_HEADER_SIZE + UDP_HEADER_SIZE + CUSTOM_HEADER_SIZE  # = 43 bytes

MAX_PAYLOAD_SIZE = 1400     # Safe payload size (1500 - 43 = 1457, rounded down)
MAX_PACKET_SIZE = OVERHEAD + MAX_PAYLOAD_SIZE  # = 1443 bytes total on wire
RECV_BUFFER_SIZE = 65535    # Max size for recvfrom()

# ============================================================
# RELIABILITY CONSTANTS
# ============================================================

WINDOW_SIZE = 10            # Number of unacknowledged packets in flight
TIMEOUT = 0.5               # Retransmission timeout in seconds (500ms)
MAX_RETRIES = 10            # Max retransmits per packet before giving up
ACK_TIMEOUT = 2.0           # How long server waits for any ACK before resending
FIN_WAIT_TIME = 2.0         # Time to wait after sending FIN for final ACKs

# ============================================================
# FLAG CONSTANTS (1 byte = 8 bits)
# ============================================================
# 
# Bit layout: 0 0 0 0  D F A S
#                       | | | └─ SYN  (bit 0)
#                       | | └─── ACK  (bit 1)
#                       | └───── FIN  (bit 2)
#                       └─────── DATA (bit 3)
#
# Bits 4-7 reserved for Phase 2 (SEC, HANDSHAKE, etc.)

FLAG_SYN  = 0x01    # 0000 0001 — Request to start transfer
FLAG_ACK  = 0x02    # 0000 0010 — Acknowledgment
FLAG_FIN  = 0x04    # 0000 0100 — Transfer complete
FLAG_DATA = 0x08    # 0000 1000 — Packet contains file data

# Common flag combinations
FLAG_SYN_ACK = FLAG_SYN | FLAG_ACK   # 0x03 — Server acknowledges request
FLAG_FIN_DATA = FLAG_FIN | FLAG_DATA  # 0x0C — Last chunk of file
FLAG_FIN_ACK = FLAG_FIN | FLAG_ACK    # 0x06 — Acknowledge transfer complete

# ============================================================
# CUSTOM HEADER FORMAT (15 bytes)
# ============================================================
#
# ┌────────────────────────────────────────────────────────┐
# │ Offset │ Size   │ Field          │ Format │ Description│
# ├────────┼────────┼────────────────┼────────┼────────────┤
# │ 0      │ 4 bytes│ seq_num        │  !I    │ Chunk #    │
# │ 4      │ 4 bytes│ ack_num        │  !I    │ Cum. ACK   │
# │ 8      │ 2 bytes│ checksum       │  !H    │ Integrity  │
# │ 10     │ 2 bytes│ payload_length │  !H    │ Data size  │
# │ 12     │ 1 byte │ flags          │  !B    │ Pkt type   │
# │ 13     │ 2 bytes│ conn_id        │  !H    │ Connection │
# └────────┴────────┴────────────────┴────────┴────────────┘
#
# Total: 4 + 4 + 2 + 2 + 1 + 2 = 15 bytes

HEADER_FORMAT = '!IIHHBH'    # network byte order (big-endian)
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)  # should be 15

# Verify at import time
assert HEADER_SIZE == CUSTOM_HEADER_SIZE, \
    f"Header size mismatch: {HEADER_SIZE} != {CUSTOM_HEADER_SIZE}"

# ============================================================
# PROTOCOL FLOW REFERENCE
# ============================================================
#
# STEP 1 — Client requests file:
#   flags=SYN, seq=0, payload=b"filename.txt"
#
# STEP 2 — Server acknowledges:
#   flags=SYN_ACK, seq=0, ack=0
#
# STEP 3 — Server sends data chunks:
#   flags=DATA, seq=0,1,2,..., payload=<file bytes>
#
# STEP 4 — Client ACKs periodically:
#   flags=ACK, ack=N (meaning "I have all chunks up to N")
#
# STEP 5 — Server sends last chunk:
#   flags=FIN_DATA, seq=last, payload=<final bytes>
#
# STEP 6 — Client confirms completion:
#   flags=FIN_ACK, ack=last
#
# ============================================================
