# encode and decode custom protocol headers (15 bytes)
# Functions: encode_packet(), decode_packet()
# Must handle: seq_num, ack_num, flags, checksum, payload_length, flags, conn_id

import struct
from common.constants import HEADER_FORMAT, CUSTOM_HEADER_SIZE, MAX_PAYLOAD_SIZE
from common.checksum import compute_checksum, verify_checksum

def encode_packet(seq_num: int, ack_num: int, flags: int, payload:bytes, conn_id: int) -> bytes:
    """
    encode packet: 15 byte header + payload

    Algorithm:
    1. validate inputs
    2. compute_checksum 
    3. pack header with actual checksum
    4. append payload

    """

    if len(payload) > MAX_PAYLOAD_SIZE:
        raise ValueError(f"Payload size {len(payload)} exceeds maximum {MAX_PAYLOAD_SIZE}.")
    

    payload_length = len(payload)

    header_no_checksum = struct.pack(
        HEADER_FORMAT, seq_num, ack_num, 0, payload_length, flags, conn_id
    )
    
    # 0 is placeholder as checksum hasnt been calculated yet.

    data_to_checksum = header_no_checksum + payload
    checksum = compute_checksum(data_to_checksum)

    final_header = struct.pack(
        HEADER_FORMAT, seq_num, ack_num, checksum, payload_length, flags, conn_id
    )

    return final_header + payload


def decode_packet(raw_data: bytes) -> dict | None:
    """
    decode the incoming packet bytes to a dict

    Algorithm:
    1. validate packet (needs to be atleast 15 bytes)
    2. unpack header
    3. extract payload
    4. verify checksum
    5. validate payload_length so that it matches actual payload
    """

    if len(raw_data) < CUSTOM_HEADER_SIZE:
        return None
    
    header_bytes = raw_data[:CUSTOM_HEADER_SIZE]

    try:
        seq_num, ack_num, checksum, payload_length, flags, conn_id = struct.unpack(
            HEADER_FORMAT, header_bytes
        )
    except struct.error:
        return None
    
    payload = raw_data[CUSTOM_HEADER_SIZE:]
    
    if len(payload) != payload_length:
        return None
    
    header_no_checksum = struct.pack(
        HEADER_FORMAT, seq_num, ack_num, 0, payload_length, flags, conn_id
    )

    if not verify_checksum(header_no_checksum + payload, checksum):
        return None
    
    # Determine packet type from flags
    from common.constants import FLAG_SYN, FLAG_ACK, FLAG_FIN, FLAG_DATA, FLAG_SYN_ACK, FLAG_FIN_DATA, FLAG_FIN_ACK
    
    if flags == FLAG_SYN:
        pkt_type = "SYN"
    elif flags == FLAG_SYN_ACK:
        pkt_type = "SYN_ACK"
    elif flags == FLAG_ACK:
        pkt_type = "ACK"
    elif flags == FLAG_DATA:
        pkt_type = "DATA"
    elif flags == FLAG_FIN:
        pkt_type = "FIN"
    elif flags == FLAG_FIN_DATA:
        pkt_type = "FIN_DATA"
    elif flags == FLAG_FIN_ACK:
        pkt_type = "FIN_ACK"
    else:
        pkt_type = "UNKNOWN"
    
    return {
        'seq': seq_num,       # Use 'seq' for consistency
        'ack': ack_num,       # Use 'ack' for consistency
        'seq_num': seq_num,
        'ack_num': ack_num,
        'checksum': checksum,
        'payload_length': payload_length,
        'flags': flags,
        'type': pkt_type,
        'conn_id': conn_id,
        'payload': payload
    }
