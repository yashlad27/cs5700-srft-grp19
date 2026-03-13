"""
Integration tests for client modules that execute actual code paths
These tests use real implementations instead of mocks to increase coverage
"""

import io
import pytest
from unittest.mock import Mock, patch, MagicMock

from client.client_state import ClientState
from client.request_handler import get_local_ip, send_syn_request
from common.packet import encode_packet, decode_packet
from common.constants import FLAG_DATA, FLAG_FIN_DATA, FLAG_SYN_ACK, FLAG_ACK


class TestClientStateIntegration:
    """Test ClientState with real file operations"""
    
    def test_store_and_write_real_chunks(self, tmp_path):
        """Test storing chunks and writing to real file"""
        state = ClientState()
        output_file = tmp_path / "output.bin"
        
        # Store chunks out of order
        state.store_chunk(2, b"world")
        state.store_chunk(0, b"hello ")
        state.store_chunk(1, b"cruel ")
        
        # Write to file - write_chunk writes ALL contiguous chunks
        with open(output_file, 'wb') as f:
            state.write_chunk(f)
        
        # All chunks written since they're all contiguous from 0
        assert state.expected_seq == 3
        assert state.chunks_written == 3
        assert len(state.buffer) == 0
        
        # Verify file contents
        assert output_file.read_bytes() == b"hello cruel world"
    
    def test_handle_fin_seq(self, tmp_path):
        """Test FIN sequence handling"""
        state = ClientState()
        output_file = tmp_path / "test.bin"
        
        # Store chunks including FIN
        state.store_chunk(0, b"data1")
        state.store_chunk(1, b"data2")
        state.fin_seq = 1  # Mark seq 1 as last
        
        with open(output_file, 'wb') as f:
            state.write_chunk(f)
        
        assert state.expected_seq == 2
        assert state.chunks_written == 2
        assert output_file.read_bytes() == b"data1data2"


class TestPacketDecoding:
    """Test packet encoding/decoding integration with client state"""
    
    def test_encode_decode_data_packet(self):
        """Test encoding and decoding DATA packet"""
        original_payload = b"test_data_chunk"
        
        # Encode packet
        encoded = encode_packet(
            seq_num=5,
            ack_num=0,
            flags=FLAG_DATA,
            payload=original_payload,
            conn_id=100
        )
        
        # Decode it back
        decoded = decode_packet(encoded)
        
        assert decoded is not None
        assert decoded['seq_num'] == 5
        assert decoded['flags'] == FLAG_DATA
        assert decoded['payload'] == original_payload
        assert decoded['conn_id'] == 100
        assert decoded['type'] == 'DATA'
    
    def test_encode_decode_fin_data_packet(self):
        """Test encoding and decoding FIN_DATA packet"""
        payload = b"last_chunk"
        
        encoded = encode_packet(
            seq_num=10,
            ack_num=0,
            flags=FLAG_FIN_DATA,
            payload=payload,
            conn_id=200
        )
        
        decoded = decode_packet(encoded)
        
        assert decoded is not None
        assert decoded['seq_num'] == 10
        assert decoded['flags'] == FLAG_FIN_DATA
        assert decoded['payload'] == payload
        assert decoded['type'] == 'FIN_DATA'
    
    def test_corrupted_packet_returns_none(self):
        """Test that corrupted packet is rejected"""
        # Too short packet
        corrupted = b"short"
        
        decoded = decode_packet(corrupted)
        assert decoded is None


class TestRequestHandlerIntegration:
    """Test request_handler with real operations"""
    
    def test_get_local_ip_returns_valid_ip(self):
        """Test that get_local_ip returns a valid IP address"""
        ip = get_local_ip("8.8.8.8")
        
        # Should return a valid IP string
        assert isinstance(ip, str)
        assert len(ip.split('.')) == 4
        # Should not be empty or localhost only
        assert ip != ""
    
    @patch('client.request_handler.receive_packet')
    @patch('client.request_handler.send_packet')
    def test_send_syn_request_success(self, mock_send, mock_recv):
        """Test SYN request with actual packet encoding"""
        mock_send_sock = Mock()
        mock_recv_sock = Mock()
        
        # Mock receive to return SYN_ACK
        syn_ack_pkt = encode_packet(seq_num=0, ack_num=0, flags=FLAG_SYN_ACK,
                                    payload=b"", conn_id=100)
        # receive_packet returns (packet_dict, sender_ip, src_port)
        mock_recv.return_value = (decode_packet(syn_ack_pkt), "10.0.0.1", 9000)
        
        result = send_syn_request(
            mock_send_sock,
            mock_recv_sock,
            "10.0.0.2",
            "10.0.0.1",
            "test.bin",
            conn_id=100,
            retries=1,
            max_wait_time=0.1
        )
        
        assert result == True
        assert mock_send.called
    
    @patch('client.request_handler.receive_packet')
    @patch('client.request_handler.send_packet')
    def test_send_syn_request_timeout(self, mock_send, mock_recv):
        """Test SYN request timeout"""
        mock_send_sock = Mock()
        mock_recv_sock = Mock()
        
        # Mock receive to return None (timeout)
        mock_recv.return_value = None
        
        result = send_syn_request(
            mock_send_sock,
            mock_recv_sock,
            "10.0.0.2",
            "10.0.0.1",
            "test.bin",
            conn_id=100,
            retries=2,
            max_wait_time=0.01
        )
        
        assert result == False
        # Should retry 2 times
        assert mock_send.call_count >= 2


class TestClientStateEdgeCases:
    """Test edge cases for better coverage"""
    
    def test_duplicate_detection(self):
        """Test that duplicates are properly detected"""
        state = ClientState()
        
        # Store initial chunk
        state.store_chunk(0, b"data")
        assert state.p_duplicate == 0
        
        # Try to store same chunk again
        state.store_chunk(0, b"data")
        assert state.p_duplicate == 1
        
        # Old chunk (already written)
        state.expected_seq = 5
        state.store_chunk(3, b"old")
        assert state.p_duplicate == 2
    
    def test_empty_payload_handling(self, tmp_path):
        """Test handling of empty payloads"""
        state = ClientState()
        output_file = tmp_path / "empty.bin"
        
        state.store_chunk(0, b"")
        
        with open(output_file, 'wb') as f:
            state.write_chunk(f)
        
        assert output_file.read_bytes() == b""
        assert state.chunks_written == 1
    
    def test_large_sequence_numbers(self):
        """Test handling large sequence numbers"""
        state = ClientState()
        
        # Store chunk with large seq number
        state.store_chunk(999999, b"data")
        assert 999999 in state.buffer
        
        # But within safety bound
        state.store_chunk(1000000, b"max")
        assert 1000000 in state.buffer
        
        # Beyond safety bound should be rejected
        state.store_chunk(1000001, b"too_large")
        assert 1000001 not in state.buffer
