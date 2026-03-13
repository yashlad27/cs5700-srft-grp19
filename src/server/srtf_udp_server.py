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
from common.rawsocket import create_recv_socket, create_send_socket, receive_packet, send_packet
from common.constants import SERVER_PORT, CLIENT_PORT

# Global flag for graceful shutdown
shutdown_requested = False

def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    global shutdown_requested
    print("\n[server] Shutdown signal received (Ctrl+C), cleaning up...")
    shutdown_requested = True

_server_state = None  # module-level ref for cleanup on interrupt

def run_server(cfg: ServerConfig):
    global shutdown_requested, _server_state
    
    state = ServerState(cfg=cfg)
    _server_state = state
    wm = WindowManager(window_size=cfg.window_size)

    # Create separate send and receive raw sockets
    recv_sock = create_recv_socket(cfg.listen_port)
    recv_sock.setblocking(False)
    send_sock = create_send_socket()

    receiver = Receiver(state, wm)
    sender = Sender(state, send_sock)

    # Create retransmit send function for raw sockets
    def rtx_send(pkt_bytes, dst_ip):
        send_packet(send_sock, pkt_bytes, sender.server_ip, dst_ip, SERVER_PORT, CLIENT_PORT)
        with state.lock:
            state.stats["pkts_out"] += 1

    rtx = RetransmitQueue(
        rto_ms=cfg.rto_ms,
        max_retries=cfg.max_retries,
        server_state=state,
        send_func=rtx_send
    )

    print(f"[server] listening on {cfg.listen_ip}:{cfg.listen_port}")
    print("[server] Press Ctrl+C to stop")

    running = True
    client_addr = None
    
    while running and not shutdown_requested:
        # If transfer is active, send chunks within window
        if sender.is_transfer_active():
            sender.send_next_chunks()

        # wait for data or timeout for retransmit tick
        r, _, _ = select.select([recv_sock], [], [], 0.01)

        if r:
            try:
                result = receive_packet(recv_sock, cfg.listen_port, timeout=0)
                if result is None:
                    continue
                
                packet_dict, sender_ip, src_port = result
                addr = (sender_ip, src_port)
                
                res = receiver.handle_decoded_packet(packet_dict, addr)
            except Exception as e:
                print(f"[server] Error handling packet: {e}")
                continue
            
            # Handle SYN → send SYN_ACK and prepare file transfer
            if res.ack_seq == -999:
                import os
                conn_id = state.sec.conn_id
                filename = state.file_ctx.filename
                client_addr = addr
                
                sender.send_syn_ack(addr, conn_id)
                print(f"[server] Sent SYN_ACK to {addr}")
                
                filepath = os.path.join(cfg.out_dir, filename)
                if sender.prepare_file_transfer(addr, filepath, cfg.chunk_size, conn_id, rtx):
                    # Initial burst of chunks will happen at top of next loop iteration
                    pass
                else:
                    print(f"[server] ERROR: File not found: {filepath}")
                    running = False
            
            # Handle cumulative ACK from client → slide window
            if res.data_ack is not None:
                sender.handle_data_ack(res.data_ack)
            
            # Handle ACK for receiver-side data (if server is receiving)
            elif res.ack_seq is not None and res.ack_seq >= 0:
                sender.send_ack(addr, res.ack_seq)
            
            # Handle close (FIN / FIN_ACK)
            if res.close:
                print("[server] Received FIN/FIN_ACK, closing connection")
                state.stop_transfer_timer()
                running = False

        rtx.tick()

    # Close file handle if open
    if state.file_ctx.fp is not None:
        state.file_ctx.fp.close()

    # Write stats report
    state.write_stats_report()

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
    parser.add_argument("--stats-out", default=None, help="path for server output/stats file")
    args = parser.parse_args()

    cfg = ServerConfig(
        listen_ip=args.host,
        listen_port=args.port,
        out_dir=args.out,
        chunk_size=args.chunk,
        window_size=args.window,
        rto_ms=args.rto,
        stats_out=args.stats_out,
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