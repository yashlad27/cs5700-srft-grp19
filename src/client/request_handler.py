# send request + ACKS
import time
import socket

from common.constants import CLIENT_PORT, SERVER_PORT, FLAG_SYN, FLAG_SYN_ACK
from common.packet import encode_packet
from common.rawsocket import send_packet, receive_packet

def get_local_ip(server_ip: str) -> str:
    '''
    find local IP address to reach server_ip
    '''
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((server_ip, 80))
        return s.getsockname()[0]
    finally:
        s.close()

def send_syn_request(
        send_sock,
        recv_sock,
        client_ip: str,
        server_ip: str,
        filename: str,
        conn_id: int = 0,
        retries: int = 5,
        max_wait_time: float = 2.0,
) -> bool:
    '''
    send SYN request with filename and wait for SYN_ACK
    return: T if handshake succeeds, F otherwise
    '''
    # creates a syn packet
    syn_packet = encode_packet(
        seq_num=0,
        ack_num=0,
        flags=FLAG_SYN,
        payload=filename.encode("utf-8"),
        conn_id=conn_id
    )
    for attempt in range(retries):
        # send SYN
        send_packet(
            send_sock,
            syn_packet,
            src_ip=client_ip,
            dst_ip=server_ip,
            src_port=CLIENT_PORT,
            dst_port=SERVER_PORT
        )

        # wait for SYN_ACK
        deadline = time.time() + max_wait_time
        while time.time() < deadline:
            res = receive_packet(recv_sock, expected_port=CLIENT_PORT, timeout=0.5)
            if res is None:
                continue
            packet, sender_ip, sender_port = res
            if packet is None: # packet is corrupted or invalid
                continue

            # check for SYN_ACK
            if packet["flags"] == FLAG_SYN_ACK:
                return True
            
        # no SYN_ACK returned, retry next attempt
    
    # All retries exhausted
    return False