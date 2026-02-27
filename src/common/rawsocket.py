# SOCK_RAW socket wrapper - manually build IP + UDP headers
# Functions: create_send_socket(), create_recv_socket(), send_packet(), receive_packet()
# set IP_HDRINCL socket option to disable kernel IP header generation
# filter incoming UDP by port

import socket
import struct
from common.constants import RECV_BUFFER_SIZE, CUSTOM_HEADER_SIZE
from common.packet import decode_packet

def create_send_socket() -> socket.socket:
    """
    create raw socket for sending packets with manual IP headers

    REQUIRED: sudo privileges (CAP_NET_RAW)

    Returns:
        configured SOCK_RAW socket for sending
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW)           # we provide IP header 

    sock.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)        # we provide IP header and kernel doesnt

    return sock

def create_recv_socket(port: int) -> socket.socket:
    """
    create raw socket for receiving udp packets

    Returns:
        SOCK_RAW socket that receives UDP packets
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_UDP)          # checks for all UDP packets
    
    sock.bind(('', port))           # we bind to a port

    return sock

def build_ip_header(src_ip: str, dst_ip: str, udp_length: int) -> bytes:
    """
    IP HEADER STRUCTURE (20 BYTES):

    Version (4bits) + IHL (4bits) = 1 byte
    Type of Service = 1 byte
    Total length = 2 bytes
    Identification = 2 bytes
    Flags (3bits) + Fragment Offset (13 bits) = 2 bytes
    TTL = 1 byte
    Protocol = 1 byte
    Destination IP = 4 bytes

    Returns:
        20-byte IP header
    """
    version = 4                         # IPV4
    ihl = 5                             # Header length = 5 * 4 = 20 bytes
    version_ihl = (version << 4) + ihl  # Combine into 1 byte

    tos = 0                             # Type of service
    total_length = 20 + udp_length      # IP HEADER (20) + UDP HEADER + UDP PAYLOAD
    identification = 54321              # Packet ID
    flags = 0                           # Dont fragment
    fragment_offset = 0
    flags_fragment = (flags << 13) + fragment_offset        # combine into 2 bytes

    ttl = 64                            # time to live 
    protocol = 17                       # 17 = UDP (IPROTO_UDP)
    header_checksum = 0                 # initialized to 0

    src_ip_bytes = socket.inet_aton(src_ip)                 # convert IP addr from string to 4-byte format
    dst_ip_bytes = socket.inet_aton(dst_ip)

    # Pack IP header (without checksum first)
    # Format: !BBHHHBBH4s4s
    # ! = network byte order (big-endian)
    # B = unsigned char (1 byte)
    # H = unsigned short (2 bytes)
    # 4s = 4-byte string
    ip_header = struct.pack(
        '!BBHHHBBH4s4s',
        version_ihl,
        tos,
        total_length,
        identification,
        flags_fragment,
        ttl,
        protocol,
        header_checksum,
        src_ip_bytes,
        dst_ip_bytes
    )

    checksum = 0

    for i in range(0, len(ip_header), 2):
        word = (ip_header[i] << 8) + ip_header[i+1]
        checksum += word
        checksum = (checksum & 0xFFFF) + (checksum >> 16)
    checksum = ~checksum & 0xFFFF

    # rebuild IP header with actual checksum 
    ip_header = struct.pack(
        '!BBHHHBBH4s4s',
        version_ihl,
        tos,
        total_length,
        identification,
        flags_fragment,
        ttl,
        protocol,
        checksum, 
        src_ip_bytes,
        dst_ip_bytes
    )

    return ip_header

def build_udp_header(src_port: int, dst_port: int, payload_length: int) -> bytes:
    """
    Manually construct 8-byte UDP header
    
    UDP Header Structure (8 bytes):
    - Source Port = 2 bytes
    - Destination Port = 2 bytes
    - Length = 2 bytes (UDP header + UDP payload)
    - Checksum = 2 bytes (optional for IPv4, we set to 0)
    
    Args:
        src_port: Source port number
        dst_port: Destination port number
        payload_length: Length of data after UDP header
    
    Returns:
        8-byte UDP header
    """

    udp_length = 8 + payload_length
    udp_checksum = 0

    udp_header = struct.pack(
        '!HHH', src_port, dst_port, udp_length, udp_checksum
    )

    return udp_header

def send_packet(sock: socket.socket, packet_bytes: bytes, src_ip: str, dst_ip: str, src_port: int, dst_port: int) -> None:
    """
    Send complete packet with IP + UDP + Custom headers
    
    Packet structure on wire:
    [ IP Header (20B) ][ UDP Header (8B) ][ Custom Header (15B) ][ Payload ]
    
    Args:
        sock: Send socket from create_send_socket()
        packet_bytes: Complete packet from packet.encode_packet()
                     (Custom header + payload)
        src_ip: Source IP address
        dst_ip: Destination IP address
        src_port: Source port
        dst_port: Destination port
    
    Raises:
        OSError: If send fails (permission denied, network unreachable, etc.)
    """

    # this is udp header
    # udp payload = custom packet (header and payload)
    udp_header = build_udp_header(src_port, dst_port, len(packet_bytes))

    # udp length = udp header (8) + custom packet
    udp_length = len(udp_header) + len(packet_bytes)
    ip_header = build_ip_header(src_ip, dst_ip, udp_length)

    # ip header + udp header + custom packet
    full_packet = ip_header + udp_header + packet_bytes

    # send packet
    sock.sendto(full_packet, (dst_ip, 0))

def receive_packet(sock: socket.socket, expected_port: int, timeout: float = None) -> tuple | None:
    """
    receive and parse incoming packet
    """

    if timeout is not None:
        sock.settimeout(timeout)

    try:
        raw_data, addr = sock.recvfrom(RECV_BUFFER_SIZE)
        sender_ip = addr[0]
    
    except socket.timeout:
        return None
    except OSError:
        return None
    
    # now parse the received packet 
    # raw data is [ IP Header (20B) ][ UDP Header (8B) ][ Custom Header + Payload ]
    # now we reverse the raw data and strip each part out into individual parts

    # 1. IP HEADER (20 Bytes)
    if len(raw_data) < 20:
        return None
    
    # extract IHL from IP header 
    # first_byte = version (4 bits) + IHL (4 bits)
    ihl = (raw_data[0] & 0x0F) * 4      # ihl is in 4-byte words

    if len(raw_data) < ihl + 8:
        return None # data too short
    
    # 2. UDP HEADER (which is next 8 bytes after IP Header)
    udp_header = raw_data[ihl:ihl + 8]

    # extract ports from udp_header
    # src_port (2B), dst_port (2B), length (2B), checksum (2B)
    src_port, dst_port, udp_length, udp_checksum = struct.unpack('!HHHH', udp_header)

    # 3. FIND Destination Port
    if dst_port != expected_port:
        return None
    
    # 4. CUSTOM PACKET extraction
    custom_packet = raw_data[ihl + 8:]

    # 5. DECODE PROCESS for custom packet
    packet_dict = decode_packet(custom_packet)

    return (packet_dict, sender_ip, src_port)
