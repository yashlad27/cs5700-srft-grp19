"""
UNIT TESTS FOR checksum.py
"""

import pytest
from common.checksum import compute_checksum, verify_checksum

class TestComputeChecksum:
    def test_empty_date(self):
        """Empty data returns 0xFFFF"""
        checksum = compute_checksum(b'')
        assert checksum == 0xFFFF

    def test_single_byte(self):
        """Single byte (odd length) should be padded with 0x00"""
        checksum = compute_checksum(b'\x12')
        assert checksum == 0xEDFF

    def test_two_bytes(self):
        """Two bytes (even length)"""
        checksum = compute_checksum(b'\x12\x34')
        assert checksum == 0xEDCB

    def test_known_value_1(self):
        """test against checksum value"""
        data = b'\x00\x01\x00\x02\x00\x03'
        checksum = compute_checksum(data)
        assert checksum == 0xFFF9

    def test_known_value_2(self):
        """test with all 0xFF bytes"""
        data = b'\xFF\xFF\xFF\xFF'
        checksum = compute_checksum(data)
        assert checksum == 0x0000

    def test_carry_wrapping(self):
        """test that carry bits wrap around correctly"""
        data = b'\xFF\xFF\x00\x01'
        checksum = compute_checksum(data)
        assert checksum == 0xFFFE

    def test_odd_length_large(self):
        """Test odd-length data larger than 2 bytes"""
        data = b'\x12\x34\x56\x78\x9A'
        checksum = compute_checksum(data)
        # words: 0x1234, 0x5678, 0x9A00
        # sum = 0x102AC -> (0x02AC) + (0x0001) = 0x02AD
        # checksum = ~0x02AD = 0xFD52
        assert checksum == 0xFD52
    
    def test_deterministic(self):
        """Same input should always produce same checksum"""
        data = b'Hello, World!'
        checksum1 = compute_checksum(data)
        checksum2 = compute_checksum(data)
        assert checksum1 == checksum2


class TestVerifyChecksum:
    """Test checksum verification"""
    
    def test_valid_checksum(self):
        """Valid checksum should return True"""
        data = b'\x00\x01\x00\x02'
        checksum = compute_checksum(data)
        assert verify_checksum(data, checksum) is True
    
    def test_invalid_checksum(self):
        """Invalid checksum should return False"""
        data = b'\x00\x01\x00\x02'
        checksum = compute_checksum(data)
        # Corrupt the checksum
        bad_checksum = checksum ^ 0x0001  # Flip one bit
        assert verify_checksum(data, bad_checksum) is False
    
    def test_corrupted_data(self):
        """Corrupted data should fail verification"""
        data = b'Hello, World!'
        checksum = compute_checksum(data)
        
        # Corrupt the data
        corrupted = bytearray(data)
        corrupted[0] ^= 0x01  # Flip one bit
        
        assert verify_checksum(bytes(corrupted), checksum) is False
    
    def test_empty_data_verification(self):
        """Empty data verification"""
        data = b''
        checksum = compute_checksum(data)
        assert verify_checksum(data, checksum) is True
 

class TestChecksumEdgeCases:
    """Test edge cases and boundary conditions"""
    
    def test_max_uint16_value(self):
        """Test with maximum 16-bit values"""
        data = b'\xFF\xFF'
        checksum = compute_checksum(data)
        assert 0 <= checksum <= 0xFFFF
    
    def test_alternating_pattern(self):
        """Test with alternating 0x55/0xAA pattern"""
        data = b'\x55\xAA' * 10
        checksum = compute_checksum(data)
        assert 0 <= checksum <= 0xFFFF
    
    def test_large_data(self):
        """Test with larger data (1400 bytes - max payload)"""
        data = b'X' * 1400
        checksum = compute_checksum(data)
        assert 0 <= checksum <= 0xFFFF
        # Verify it
        assert verify_checksum(data, checksum) is True