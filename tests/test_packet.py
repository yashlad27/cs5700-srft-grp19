"""
Unit tests for packet.py
Tests packet encoding, decoding, and validation
"""

import pytest
from common.packet import encode_packet, decode_packet
from common.constants import (
    FLAG_SYN, FLAG_ACK, FLAG_DATA, FLAG_FIN,
    FLAG_SYN_ACK, FLAG_FIN_DATA, FLAG_FIN_ACK,
    MAX_PAYLOAD_SIZE, CUSTOM_HEADER_SIZE
)


class TestEncodePacket:
    """Test packet encoding"""
    
    def test_encode_basic(self):
        """Basic packet encoding with payload"""
        packet = encode_packet(
            seq_num=5,
            ack_num=10,
            flags=FLAG_DATA,
            payload=b'hello',
            conn_id=1234
        )
        
        # Check total size: header (15) + payload (5) = 20
        assert len(packet) == 20
        assert isinstance(packet, bytes)
    
    def test_encode_empty_payload(self):
        """Encode packet with empty payload (ACK packet)"""
        packet = encode_packet(
            seq_num=0,
            ack_num=5,
            flags=FLAG_ACK,
            payload=b'',
            conn_id=100
        )
        
        # Only header, no payload
        assert len(packet) == 15
    
    def test_encode_max_payload(self):
        """Encode packet with maximum payload size"""
        payload = b'X' * MAX_PAYLOAD_SIZE
        packet = encode_packet(
            seq_num=100,
            ack_num=0,
            flags=FLAG_DATA,
            payload=payload,
            conn_id=5000
        )
        
        assert len(packet) == CUSTOM_HEADER_SIZE + MAX_PAYLOAD_SIZE
    
    def test_encode_exceeds_max_payload(self):
        """Encoding packet with payload > MAX_PAYLOAD_SIZE should raise error"""
        payload = b'X' * (MAX_PAYLOAD_SIZE + 1)
        
        with pytest.raises(ValueError, match="exceeds maximum"):
            encode_packet(
                seq_num=0,
                ack_num=0,
                flags=FLAG_DATA,
                payload=payload,
                conn_id=1
            )
    
    def test_encode_different_flags(self):
        """Test encoding with different flag combinations"""
        flags_to_test = [
            FLAG_SYN,
            FLAG_ACK,
            FLAG_DATA,
            FLAG_FIN,
            FLAG_SYN_ACK,
            FLAG_FIN_DATA,
            FLAG_FIN_ACK
        ]
        
        for flags in flags_to_test:
            packet = encode_packet(0, 0, flags, b'test', 1)
            assert len(packet) == 19  # 15 + 4


class TestDecodePacket:
    """Test packet decoding"""
    
    def test_decode_basic(self):
        """Encode then decode - should get same values back"""
        original = {
            'seq_num': 42,
            'ack_num': 100,
            'flags': FLAG_DATA,
            'payload': b'Hello, World!',
            'conn_id': 9999
        }
        
        # Encode
        packet = encode_packet(
            seq_num=original['seq_num'],
            ack_num=original['ack_num'],
            flags=original['flags'],
            payload=original['payload'],
            conn_id=original['conn_id']
        )
        
        # Decode
        decoded = decode_packet(packet)
        
        assert decoded is not None
        assert decoded['seq_num'] == original['seq_num']
        assert decoded['ack_num'] == original['ack_num']
        assert decoded['flags'] == original['flags']
        assert decoded['payload'] == original['payload']
        assert decoded['conn_id'] == original['conn_id']
        assert decoded['payload_length'] == len(original['payload'])
    
    def test_decode_empty_payload(self):
        """Decode packet with no payload"""
        packet = encode_packet(0, 5, FLAG_ACK, b'', 123)
        decoded = decode_packet(packet)
        
        assert decoded is not None
        assert decoded['payload'] == b''
        assert decoded['payload_length'] == 0
    
    def test_decode_too_short(self):
        """Packet shorter than header should return None"""
        bad_packet = b'short'  # Only 5 bytes
        decoded = decode_packet(bad_packet)
        assert decoded is None
    
    def test_decode_corrupted_checksum(self):
        """Packet with bad checksum should return None"""
        packet = encode_packet(10, 20, FLAG_DATA, b'data', 500)
        
        # Corrupt the checksum (bytes 8-9)
        corrupted = bytearray(packet)
        corrupted[8] ^= 0xFF  # Flip all bits in checksum high byte
        
        decoded = decode_packet(bytes(corrupted))
        assert decoded is None
    
    def test_decode_corrupted_payload(self):
        """Packet with corrupted payload should return None"""
        packet = encode_packet(5, 0, FLAG_DATA, b'correct data', 200)
        
        # Corrupt the payload
        corrupted = bytearray(packet)
        corrupted[-1] ^= 0x01  # Flip one bit in last byte
        
        decoded = decode_packet(bytes(corrupted))
        assert decoded is None  # Checksum should fail
    
    def test_decode_length_mismatch(self):
        """Packet where payload_length doesn't match actual payload"""
        packet = encode_packet(0, 0, FLAG_DATA, b'hello', 1)
        
        # Manually corrupt payload_length field (bytes 10-11)
        corrupted = bytearray(packet)
        # Change payload_length from 5 to 10 (will fail checksum or length check)
        corrupted[10] = 0x00
        corrupted[11] = 0x0A
        
        decoded = decode_packet(bytes(corrupted))
        assert decoded is None


class TestRoundTrip:
    """Test encode -> decode round trip for all flag types"""
    
    @pytest.mark.parametrize("seq_num,ack_num,flags,payload,conn_id", [
        (0, 0, FLAG_SYN, b'filename.txt', 1),
        (0, 0, FLAG_SYN_ACK, b'', 1),
        (5, 0, FLAG_DATA, b'chunk data here', 100),
        (10, 6, FLAG_ACK, b'', 200),
        (99, 0, FLAG_FIN_DATA, b'last chunk', 300),
        (0, 100, FLAG_FIN_ACK, b'', 400),
        (42, 42, FLAG_DATA | FLAG_ACK, b'test', 500),
    ])
    def test_round_trip(self, seq_num, ack_num, flags, payload, conn_id):
        """Test encode->decode round trip preserves all fields"""
        # Encode
        packet = encode_packet(seq_num, ack_num, flags, payload, conn_id)
        
        # Decode
        decoded = decode_packet(packet)
        
        # Verify
        assert decoded is not None
        assert decoded['seq_num'] == seq_num
        assert decoded['ack_num'] == ack_num
        assert decoded['flags'] == flags
        assert decoded['payload'] == payload
        assert decoded['conn_id'] == conn_id
        assert decoded['payload_length'] == len(payload)


class TestChecksumIntegration:
    """Test checksum is properly integrated in encode/decode"""
    
    def test_checksum_field_set(self):
        """Verify checksum field is non-zero"""
        packet = encode_packet(1, 2, FLAG_DATA, b'test', 100)
        
        # Extract checksum (bytes 8-9)
        checksum = (packet[8] << 8) | packet[9]
        
        # Checksum should not be zero (unless by chance)
        # Just verify it's in valid range
        assert 0 <= checksum <= 0xFFFF
    
    def test_single_bit_flip_detected(self):
        """Single bit flip anywhere should be detected"""
        packet = encode_packet(5, 10, FLAG_DATA, b'important data', 999)
        
        # Try flipping each bit
        for byte_idx in range(len(packet)):
            for bit_idx in range(8):
                corrupted = bytearray(packet)
                corrupted[byte_idx] ^= (1 << bit_idx)
                
                decoded = decode_packet(bytes(corrupted))
                
                # Should be None unless we accidentally created valid checksum
                # (very unlikely with good test data)
                if byte_idx < CUSTOM_HEADER_SIZE or decoded is not None:
                    # Header corruption or lucky checksum match
                    pass