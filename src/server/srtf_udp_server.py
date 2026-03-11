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
from common.rawsocket import create_recv_socket, create_send_socket, receive_packet

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

    # Create separate send and receive raw sockets
    recv_sock = create_recv_socket(cfg.listen_port)
    recv_sock.setblocking(False)
    send_sock = create_send_socket()

    receiver = Receiver(state, wm)
    sender = Sender(state, send_sock)
    rtx = RetransmitQueue(send_sock, cfg.rto_ms, cfg.max_retries)

    print(f"[server] listening on {cfg.listen_ip}:{cfg.listen_port}")
    print("[server] Press Ctrl+C to stop")

    running = True
    file_sent = False
    
    while running and not shutdown_requested:
        # wait for data or timeout for retransmit tick
        r, _, _ = select.select([recv_sock], [], [], 0.01)

        if r:
            print("[DEBUG] Socket has data, calling receive_packet()")
            # Use receive_packet() to parse raw socket data
            try:
                result = receive_packet(recv_sock, cfg.listen_port, timeout=0)
                print(f"[DEBUG] receive_packet returned: {result is not None}")
                if result is None:
                    print("[DEBUG] Packet filtered out or timeout")
                    continue
                
                packet_dict, sender_ip, src_port = result
                print(f"[DEBUG] Packet from {sender_ip}:{src_port}, type={packet_dict.get('type', 'UNKNOWN')}")
                # Reconstruct addr tuple for compatibility
                addr = (sender_ip, src_port)
                
                # Pass the decoded packet to receiver (already parsed)
                print(f"[DEBUG] Calling handle_decoded_packet()")
                res = receiver.handle_decoded_packet(packet_dict, addr)
                print(f"[DEBUG] handle_decoded_packet returned: ack_seq={res.ack_seq}, close={res.close}")
            except Exception as e:
                print(f"[DEBUG] EXCEPTION in packet handling: {e}")
                import traceback
                traceback.print_exc()
                continue
            
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

    recv_sock.close()
    send_sock.close()
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
    except Exception as e:
        print(f"\n[server] FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("[server] Cleanup complete")
        sys.exit(0)

if __name__ == "__main__":
    main()