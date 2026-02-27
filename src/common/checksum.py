# calculate and verify packet integrity using checksum
# functions: compute_checksum(data: bytes), verify_checksum(packet: bytes) -> bool
# used by packet.py during encode/decode

def compute_checksum(data: bytes) -> int:
    """
    calculate 16 bit 1's complement checksum (RFC 1071) same algo used for TCP/UDP.
    
    Algorithm:
    1. split the data into 16-bit words (2 bytes each)
    2. sum all words (use carry back to handle overflow) (1's complement addition)
    3. take 1's complement of the sum 
    """
    checksum = 0

    for i in range(0, len(data), 2):
        # Network byte-order is big-endian (MSB first)
        # data[i] is high order byte then we shift left 8 bits
        # data[i+1] is low order byte then just add it

        if i + 1 < len(data):
            word = (data[i] << 8) + data[i + 1]
        else:
            word = data[i] << 8

        checksum += word

        checksum = (checksum & 0xFFFF) + (checksum >> 16)
    
    # here we flip all bits and masks to 16bits for integrity, requirement of RFC 1071
    # 1's complement
    checksum = ~checksum & 0xFFFF

    return checksum

def verify_checksum(data: bytes, expected_checksum: int) -> bool:
    """
    verify packet integrity by recomputing checksum
    """

    computed = compute_checksum(data)
    return computed == expected_checksum


# when encoding a packet, compute the checksum with the checksum field set to 0, then insert result to header.
# data is of the form => data = [0x12, 0x34, 0x56, 0x78]