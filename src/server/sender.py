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

    def prepare_file_transfer(self, addr: ClientAddr, filepath: str, chunk_size: int,
                              conn_id: int, rtx) -> bool:
        """
        Pre-read file into chunks and initialize windowed sending state.
        Returns False if file not found.
        """
        import os

        if not os.path.exists(filepath):
            print(f"[server] ERROR: File not found: {filepath}")
            return False

        file_size = os.path.getsize(filepath)

        # Pre-read all chunks
        chunks = []
        with open(filepath, 'rb') as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                chunks.append(chunk)

        total_chunks = len(chunks)

        with self.state.lock:
            self.state.file_ctx.file_size = file_size
        self.state.start_transfer_timer()

        self._transfer = {
            'addr': addr,
            'conn_id': conn_id,
            'chunks': chunks,
            'total_chunks': total_chunks,
            'base': 0,          # oldest unacked seq
            'next_seq': 0,      # next seq to send
            'window_size': self.state.cfg.window_size,
            'rtx': rtx,
            'active': True,
        }

        print(f"[server] Sending file: {filepath} ({file_size} bytes, {total_chunks} chunks, window={self.state.cfg.window_size})")
        return True

    def send_next_chunks(self) -> None:
        """Send as many chunks as the window allows. Non-blocking."""
        if not self.is_transfer_active():
            return

        t = self._transfer
        while (t['next_seq'] < t['total_chunks'] and
               t['next_seq'] < t['base'] + t['window_size']):
            seq = t['next_seq']
            payload = t['chunks'][seq]
            is_last = (seq == t['total_chunks'] - 1)

            # Build and send
            self.send_data_chunk(t['addr'], seq, payload, t['conn_id'], is_last)

            # Build packet bytes for RTX queue
            flags = FLAG_FIN_DATA if is_last else FLAG_DATA
            pkt_bytes = encode_packet(
                seq_num=seq, ack_num=0, flags=flags,
                payload=payload, conn_id=t['conn_id']
            )
            t['rtx'].add(str(seq), pkt_bytes, t['addr'][0])

            t['next_seq'] += 1

    def handle_data_ack(self, ack_num: int) -> None:
        """
        Process cumulative ACK from client.
        Client sends ack_num = next expected seq, meaning it has all seqs < ack_num.
        """
        if not self.is_transfer_active():
            return

        t = self._transfer
        if ack_num > t['base']:
            # ACK all seqs from old base up to ack_num
            for seq in range(t['base'], ack_num):
                t['rtx'].ack(str(seq))
            old_base = t['base']
            t['base'] = ack_num

        # Check if all chunks acknowledged
        if t['base'] >= t['total_chunks']:
            t['active'] = False
            print(f"[server] All {t['total_chunks']} chunks acknowledged by client")

    def is_transfer_active(self) -> bool:
        return hasattr(self, '_transfer') and self._transfer is not None and self._transfer.get('active', False)

    def is_transfer_complete(self) -> bool:
        return (hasattr(self, '_transfer') and self._transfer is not None and
                not self._transfer.get('active', True) and
                self._transfer.get('base', 0) >= self._transfer.get('total_chunks', 0))