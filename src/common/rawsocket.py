# SOCK_RAW socket wrapper - manually build IP + UDP headers
# Functions: create_send_socket(), create_recv_socket(), send_packet(), receive_packet()
# set IP_HDRINCL socket option to disable kernel IP header generation
# filter incoming UDP by port

import socket
import struct
from common.constants import RECV_BUFFER_SIZE, CUSTOM_HEADER_SIZE

def create_send_socket() -> socket.socket:

    return sock

def create_recv_socket(port: int) -> socket.socket:

    return sock

def build_ip_header(src_ip: str, dst_ip: str, udp_length: int) -> bytes:

    return ip_header

def build_udp_header(src_port: int, dst_port: int, payload_length: int) -> bytes:

    return udp_header

def  send_packet(sock: socket.socket, packet_bytes: bytes, src_ip: str, dst_ip: str, src_port: int, dst_port: int) -> None:

def receive_packet(sock: socket.socket, expected_port: int, timeout: float = None) -> tuple | None:

    return (packet_dict, sender_ip, src_port)