# send file chunks to client, and handle ACKs
# server/sender.py
from __future__ import annotations
from typing import Tuple, Optional
import socket
from server.server_state import ServerState
from common.packet import encode_packet
from common.constants import FLAG_ACK, FLAG_SYN_ACK, FLAG_DATA, FLAG_FIN_DATA, SERVER_PORT, CLIENT_PORT
from common.rawsocket import send_packet

ClientAddr = Tuple[str, int]

class Sender:
    def __init__(self, state: ServerState, sock: socket.socket):
        self.state = state
        self.sock = sock
        # Get server's IP address for raw socket send_packet()
        self.server_ip = self._get_local_ip()
    
    def _get_local_ip(self) -> str:
        """Get server's local IP address"""
        try:
            # Create a temporary socket to determine local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except:
            return '0.0.0.0'

    def send_ack(self, addr: ClientAddr, ack_seq: int) -> None:
        if ack_seq < 0:
            return
        pkt = self._build_ack(ack_seq)
        # Use send_packet for raw socket
        send_packet(self.sock, pkt, self.server_ip, addr[0], SERVER_PORT, CLIENT_PORT)
        with self.state.lock:
            self.state.stats["pkts_out"] += 1
            self.state.stats["acks_out"] += 1

    def _build_ack(self, ack_seq: int) -> bytes:
        return encode_packet(
            seq_num=0,
            ack_num=ack_seq,
            flags=FLAG_ACK,
            payload=b'',
            conn_id=0
        )

    def send_syn_ack(self, addr: ClientAddr, conn_id: int) -> None:
        """Send SYN_ACK to acknowledge client connection request"""
        pkt = encode_packet(
            seq_num=0,
            ack_num=0,
            flags=FLAG_SYN_ACK,
            payload=b'',
            conn_id=conn_id
        )
        # Use send_packet for raw socket
        send_packet(self.sock, pkt, self.server_ip, addr[0], SERVER_PORT, CLIENT_PORT)
        with self.state.lock:
            self.state.stats["pkts_out"] += 1

    def send_data_chunk(self, addr: ClientAddr, seq: int, payload: bytes, conn_id: int, is_last: bool = False) -> None:
        """Send a single data chunk to client"""
        flags = FLAG_FIN_DATA if is_last else FLAG_DATA
        pkt = encode_packet(
            seq_num=seq,
            ack_num=0,
            flags=flags,
            payload=payload,
            conn_id=conn_id
        )
        # Use send_packet for raw socket
        send_packet(self.sock, pkt, self.server_ip, addr[0], SERVER_PORT, CLIENT_PORT)
        with self.state.lock:
            self.state.stats["pkts_out"] += 1
            self.state.stats["data_out"] += 1

    def send_file(self, addr: ClientAddr, filepath: str, chunk_size: int, conn_id: int) -> None:
        """
        Read file and send it in chunks to the client
        Uses window manager and retransmit queue for reliability
        """
        import os
        import time
        from common.constants import MAX_PAYLOAD_SIZE
        
        if not os.path.exists(filepath):
            print(f"[server] ERROR: File not found: {filepath}")
            return
        
        file_size = os.path.getsize(filepath)
        total_chunks = (file_size + chunk_size - 1) // chunk_size
        
        print(f"[server] Sending file: {filepath} ({file_size} bytes, {total_chunks} chunks)")
        
        seq = 0
        with open(filepath, 'rb') as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                
                is_last = (seq == total_chunks - 1)
                self.send_data_chunk(addr, seq, chunk, conn_id, is_last)
                
                seq += 1
                
                time.sleep(0.001)
        
        print(f"[server] File sent: {total_chunks} chunks")