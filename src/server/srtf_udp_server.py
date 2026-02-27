# entry point
# server/srtf_udp_server.py
from __future__ import annotations

import argparse
import socket
import select

from server.server_state import ServerState, ServerConfig
from server.window_manager import WindowManager
from server.receiver import Receiver
from server.sender import Sender
from server.retransmit_queue import RetransmitQueue

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


def main():
    # we can adjust this part if we need to upload it to aws.
    parser = argparse.ArgumentParser(description="SRTF UDP Server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--out", default="./received")
    parser.add_argument("--chunk", type=int, default=1200)
    parser.add_argument("--window", type=int, default=64)
    parser.add_argument("--rto", type=int, default=200, help="retransmit timeout (ms)")
    args = parser.parse_args()

    cfg = ServerConfig(
        listen_ip=args.host,
        listen_port=args.port,
        out_dir=args.out,
        chunk_size=args.chunk,
        window_size=args.window,
        rto_ms=args.rto,
    )
    run_server(cfg)

if __name__ == "__main__":
    main()