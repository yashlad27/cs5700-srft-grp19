# calculate and verify packet integrity using checksum
# functions: compute_checksum(data: bytes), verify_checksum(packet: bytes) -> bool
# used by packet.py during encode/decode

def compute_checksum(data: bytes) -> int:
    """
    calculate 16 bit 1's complement checksum (RFC 1071)
    
    Algorithm:
    1. split the data into 16-bit words
    2. sum all words (use carry back to handle overflow)
    3. take 1's complement of the sum
    """
    checksum = 0

    for i in range(0, len(data), 2):
        if i + 1 < len(data):
            word = (data[i] << 8) + data[i + 1]
        else:
            word = data[i] << 8

        checksum += word

        checksum = (checksum & 0xFFFF) + (checksum >> 16)
    
    checksum = ~checksum & 0xFFFF

    return checksum

def verify_checksum(data: bytes, expected_checksum: int) -> bool:
    """
    verify packet integrity by recomputing checksum
    """

    computed = compute_checksum(data)
    return computed == expected_checksum


 # when encoding a packet, compute the checksum with the checksum field set to 0, then insert result to header.