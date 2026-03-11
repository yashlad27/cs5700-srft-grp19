# entry point
# server/srtf_udp_server.py
from __future__ import annotations

import argparse
import socket
import select
import signal
import sys

from server.server_state import ServerState, ServerConfig
from server.window_manager import WindowManager
from server.receiver import Receiver
from server.sender import Sender
from server.retransmit_queue import RetransmitQueue
from common.rawsocket import create_recv_socket, create_send_socket

# Global flag for graceful shutdown
shutdown_requested = False

def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    global shutdown_requested
    print("\n[server] Shutdown signal received (Ctrl+C), cleaning up...")
    shutdown_requested = True

def run_server(cfg: ServerConfig):
    global shutdown_requested
    
    state = ServerState(cfg=cfg)
    wm = WindowManager(window_size=cfg.window_size)

    sock = create_recv_socket(cfg.listen_port)
    sock.setblocking(False)

    receiver = Receiver(state, wm)
    sender = Sender(state, sock)
    rtx = RetransmitQueue(sock, cfg.rto_ms, cfg.max_retries)

    print(f"[server] listening on {cfg.listen_ip}:{cfg.listen_port}")
    print("[server] Press Ctrl+C to stop")

    running = True
    file_sent = False
    
    while running and not shutdown_requested:
        # wait for data or timeout for retransmit tick
        r, _, _ = select.select([sock], [], [], 0.01)

        if r:
            data, addr = sock.recvfrom(65535)
            res = receiver.handle_datagram(data, addr)
            
            # Handle SYN_ACK response
            if res.ack_seq == -999:
                conn_id = state.sec.conn_id
                filename = state.file_ctx.filename
                
                # Send SYN_ACK
                sender.send_syn_ack(addr, conn_id)
                print(f"[server] Sent SYN_ACK to {addr}")
                
                # Send file
                import os
                filepath = os.path.join(cfg.out_dir, filename)
                if os.path.exists(filepath):
                    sender.send_file(addr, filepath, cfg.chunk_size, conn_id)
                    file_sent = True
                else:
                    print(f"[server] ERROR: File not found: {filepath}")
                    running = False
            
            # Handle normal ACKs
            elif res.ack_seq is not None and res.ack_seq >= 0:
                sender.send_ack(addr, res.ack_seq)
            
            # Handle close
            if res.close:
                print("[server] Received FIN, closing connection")
                running = False

        rtx.tick()

    sock.close()
    print("[server] stopped")


def main():
    # Register signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
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
    
    try:
        run_server(cfg)
    except KeyboardInterrupt:
        print("\n[server] Interrupted by user")
    finally:
        print("[server] Cleanup complete")
        sys.exit(0)

if __name__ == "__main__":
    main()