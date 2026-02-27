# entry point
# server/srtf_udp_server.py
from __future__ import annotations
import socket
import select

from .server_state import ServerState, ServerConfig
from .window_manager import WindowManager
from .receiver import Receiver
from .sender import Sender
from .retransmit_queue import RetransmitQueue

def run_server(cfg: ServerConfig):
    state = ServerState(cfg=cfg)
    wm = WindowManager(window_size=cfg.window_size)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((cfg.listen_ip, cfg.listen_port))
    sock.setblocking(False)

    receiver = Receiver(state, wm)
    sender = Sender(state, sock)
    rtx = RetransmitQueue(sock, cfg.rto_ms, cfg.max_retries)

    print(f"[server] listening on {cfg.listen_ip}:{cfg.listen_port}")

    running = True
    while running:
        # wait for data or timeout for retransmit tick
        r, _, _ = select.select([sock], [], [], 0.01)

        if r:
            data, addr = sock.recvfrom(65535)
            res = receiver.handle_datagram(data, addr)
            if res.ack_seq is not None:
                sender.send_ack(addr, res.ack_seq)
            if res.close:
                running = False

        rtx.tick()

    sock.close()
    print("[server] stopped")