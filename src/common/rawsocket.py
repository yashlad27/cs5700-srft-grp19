# UDP socket wrapper for SRFT protocol
# Functions: create_send_socket(), create_recv_socket(), send_packet(), receive_packet()
# Uses regular UDP sockets (SOCK_DGRAM) - no sudo required, works on localhost

import socket
from common.constants import RECV_BUFFER_SIZE
from common.packet import decode_packet

def create_send_socket() -> socket.socket:
    """
    Create UDP socket for sending packets
    
    No special privileges required - uses kernel's IP/UDP headers

    Returns:
        Standard UDP socket for sending
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return sock

def create_recv_socket(port: int) -> socket.socket:
    """
    Create UDP socket for receiving packets on specified port

    Args:
        port: Port number to bind to

    Returns:
        UDP socket bound to the specified port
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('', port))
    return sock

def send_packet(sock: socket.socket, packet_bytes: bytes, dst_ip: str, dst_port: int) -> None:
    """
    Send packet using UDP socket
    
    Packet structure:
    [ Custom Header (15B) ][ Payload ]
    (IP and UDP headers added automatically by kernel)
    
    Args:
        sock: UDP socket from create_send_socket()
        packet_bytes: Complete packet from packet.encode_packet()
                     (Custom header + payload)
        dst_ip: Destination IP address
        dst_port: Destination port
    
    Raises:
        OSError: If send fails (network unreachable, etc.)
    """
    sock.sendto(packet_bytes, (dst_ip, dst_port))

def receive_packet(sock: socket.socket, expected_port: int = None, timeout: float = None) -> tuple | None:
    """
    Receive and decode incoming packet
    
    Args:
        sock: UDP socket from create_recv_socket()
        expected_port: Ignored (kept for API compatibility)
        timeout: Timeout in seconds (None for blocking)
    
    Returns:
        Tuple of (packet_dict, sender_ip, sender_port) or None if error/timeout
    """
    if timeout is not None:
        sock.settimeout(timeout)

    try:
        raw_data, addr = sock.recvfrom(RECV_BUFFER_SIZE)
        sender_ip, sender_port = addr
    except socket.timeout:
        return None
    except OSError:
        return None
    
    # Decode the custom packet (kernel already stripped IP/UDP headers)
    packet_dict = decode_packet(raw_data)
    
    if packet_dict is None:
        return None
    
    return (packet_dict, sender_ip, sender_port)
