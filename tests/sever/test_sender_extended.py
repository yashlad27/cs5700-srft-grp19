"""
Extended tests for sender.py to increase coverage
Tests for send_syn_ack, send_data_chunk, and send_file methods
"""

import os
from unittest.mock import Mock, patch, call
import pytest

from server.sender import Sender
from server.server_state import ServerConfig, ServerState
from common.constants import FLAG_SYN_ACK, FLAG_DATA, FLAG_FIN_DATA


def make_state(tmp_path):
    cfg = ServerConfig(out_dir=str(tmp_path / "received"))
    return ServerState(cfg=cfg)


class TestSendSynAck:
    @patch("server.sender.send_packet")
    @patch("server.sender.encode_packet")
    def test_send_syn_ack_creates_correct_packet(self, mock_encode, mock_send, tmp_path):
        """Test that send_syn_ack creates packet with correct parameters"""
        state = make_state(tmp_path)
        mock_socket = Mock()
        sender = Sender(state=state, sock=mock_socket)
        
        mock_encode.return_value = b"syn-ack-packet"
        addr = ("192.168.1.10", 8080)
        conn_id = 42
        
        sender.send_syn_ack(addr, conn_id)
        
        # Verify packet encoding
        mock_encode.assert_called_once_with(
            seq_num=0,
            ack_num=0,
            flags=FLAG_SYN_ACK,
            payload=b'',
            conn_id=conn_id
        )
        
        # Verify send_packet was called
        assert mock_send.called
        assert state.stats["pkts_out"] == 1
    
    @patch("server.sender.send_packet")
    @patch("server.sender.encode_packet")
    def test_send_syn_ack_with_different_conn_ids(self, mock_encode, mock_send, tmp_path):
        """Test send_syn_ack with various connection IDs"""
        state = make_state(tmp_path)
        mock_socket = Mock()
        sender = Sender(state=state, sock=mock_socket)
        
        mock_encode.return_value = b"packet"
        addr = ("10.0.0.1", 9000)
        
        # Test different conn_ids
        for conn_id in [0, 100, 65535]:
            sender.send_syn_ack(addr, conn_id)
            call_args = mock_encode.call_args
            assert call_args[1]['conn_id'] == conn_id


class TestSendDataChunk:
    @patch("server.sender.send_packet")
    @patch("server.sender.encode_packet")
    def test_send_data_chunk_regular(self, mock_encode, mock_send, tmp_path):
        """Test sending regular DATA chunk (not last)"""
        state = make_state(tmp_path)
        mock_socket = Mock()
        sender = Sender(state=state, sock=mock_socket)
        
        mock_encode.return_value = b"data-packet"
        addr = ("10.0.0.2", 9001)
        
        sender.send_data_chunk(addr, seq=5, payload=b"chunk_data", conn_id=100, is_last=False)
        
        # Verify DATA flag (not FIN_DATA)
        mock_encode.assert_called_once_with(
            seq_num=5,
            ack_num=0,
            flags=FLAG_DATA,
            payload=b"chunk_data",
            conn_id=100
        )
        
        assert state.stats["pkts_out"] == 1
        assert state.stats["data_out"] == 1
    
    @patch("server.sender.send_packet")
    @patch("server.sender.encode_packet")
    def test_send_data_chunk_last(self, mock_encode, mock_send, tmp_path):
        """Test sending last DATA chunk with FIN flag"""
        state = make_state(tmp_path)
        mock_socket = Mock()
        sender = Sender(state=state, sock=mock_socket)
        
        mock_encode.return_value = b"fin-data-packet"
        addr = ("10.0.0.2", 9001)
        
        sender.send_data_chunk(addr, seq=10, payload=b"last_chunk", conn_id=200, is_last=True)
        
        # Verify FIN_DATA flag
        mock_encode.assert_called_once_with(
            seq_num=10,
            ack_num=0,
            flags=FLAG_FIN_DATA,
            payload=b"last_chunk",
            conn_id=200
        )
        
        assert state.stats["pkts_out"] == 1
        assert state.stats["data_out"] == 1
    
    @patch("server.sender.send_packet")
    @patch("server.sender.encode_packet")
    def test_send_multiple_data_chunks(self, mock_encode, mock_send, tmp_path):
        """Test sending multiple chunks updates stats correctly"""
        state = make_state(tmp_path)
        mock_socket = Mock()
        sender = Sender(state=state, sock=mock_socket)
        
        mock_encode.return_value = b"packet"
        addr = ("10.0.0.1", 5000)
        
        # Send 3 chunks
        sender.send_data_chunk(addr, 0, b"a", 1, False)
        sender.send_data_chunk(addr, 1, b"b", 1, False)
        sender.send_data_chunk(addr, 2, b"c", 1, True)
        
        assert state.stats["pkts_out"] == 3
        assert state.stats["data_out"] == 3
        assert mock_send.call_count == 3


class TestSendFile:
    def test_send_file_single_chunk(self, tmp_path):
        """Test sending file that fits in single chunk"""
        # Create test file
        test_file = tmp_path / "small.bin"
        test_data = b"Hello World!"
        test_file.write_bytes(test_data)
        
        state = make_state(tmp_path)
        mock_socket = Mock()
        
        with patch("server.sender.send_packet") as mock_send:
            sender = Sender(state=state, sock=mock_socket)
            addr = ("10.0.0.5", 6000)
            
            sender.send_file(addr, str(test_file), chunk_size=100, conn_id=50)
            
            # Should send 1 chunk
            assert mock_send.call_count == 1
            assert state.stats["pkts_out"] == 1
            assert state.stats["data_out"] == 1
    
    def test_send_file_multiple_chunks(self, tmp_path):
        """Test sending file that requires multiple chunks"""
        # Create larger test file
        test_file = tmp_path / "large.bin"
        test_data = b"X" * 250  # 250 bytes
        test_file.write_bytes(test_data)
        
        state = make_state(tmp_path)
        mock_socket = Mock()
        
        with patch("server.sender.send_packet") as mock_send:
            sender = Sender(state=state, sock=mock_socket)
            addr = ("10.0.0.5", 6000)
            
            # Use small chunk size to force multiple chunks
            sender.send_file(addr, str(test_file), chunk_size=100, conn_id=75)
            
            # Should send 3 chunks (100 + 100 + 50)
            assert mock_send.call_count == 3
            assert state.stats["pkts_out"] == 3
            assert state.stats["data_out"] == 3
    
    def test_send_file_not_found(self, tmp_path):
        """Test sending non-existent file"""
        state = make_state(tmp_path)
        mock_socket = Mock()
        
        with patch("server.sender.send_packet") as mock_send:
            sender = Sender(state=state, sock=mock_socket)
            addr = ("10.0.0.1", 5000)
            
            # Try to send non-existent file
            sender.send_file(addr, "/nonexistent/file.bin", chunk_size=100, conn_id=1)
            
            # Should not send any packets
            assert mock_send.call_count == 0
            assert state.stats["pkts_out"] == 0
    
    def test_send_empty_file(self, tmp_path):
        """Test sending empty file"""
        # Create empty file
        test_file = tmp_path / "empty.bin"
        test_file.write_bytes(b"")
        
        state = make_state(tmp_path)
        mock_socket = Mock()
        
        with patch("server.sender.send_packet") as mock_send:
            sender = Sender(state=state, sock=mock_socket)
            addr = ("10.0.0.1", 5000)
            
            sender.send_file(addr, str(test_file), chunk_size=100, conn_id=10)
            
            # Should not send any packets for empty file
            assert mock_send.call_count == 0
    
    @patch("server.sender.send_packet")
    @patch("server.sender.encode_packet")
    def test_send_file_last_chunk_marked(self, mock_encode, mock_send, tmp_path):
        """Test that last chunk is marked with FIN_DATA flag"""
        # Create test file
        test_file = tmp_path / "test.bin"
        test_file.write_bytes(b"A" * 150)  # 150 bytes
        
        state = make_state(tmp_path)
        mock_socket = Mock()
        mock_encode.return_value = b"packet"
        
        sender = Sender(state=state, sock=mock_socket)
        addr = ("10.0.0.1", 5000)
        
        sender.send_file(addr, str(test_file), chunk_size=100, conn_id=99)
        
        # Check that last call used FIN_DATA flag
        calls = mock_encode.call_args_list
        assert len(calls) == 2  # Should be 2 chunks
        
        # First chunk should be DATA
        assert calls[0][1]['flags'] == FLAG_DATA
        # Last chunk should be FIN_DATA
        assert calls[1][1]['flags'] == FLAG_FIN_DATA


class TestGetLocalIP:
    def test_get_local_ip_success(self, tmp_path):
        """Test _get_local_ip returns valid IP"""
        state = make_state(tmp_path)
        mock_socket = Mock()
        sender = Sender(state=state, sock=mock_socket)
        
        ip = sender._get_local_ip()
        
        # Should return valid IP string
        assert isinstance(ip, str)
        assert len(ip.split('.')) == 4 or ip == '0.0.0.0'
    
    @patch('socket.socket')
    def test_get_local_ip_error_handling(self, mock_socket_class, tmp_path):
        """Test _get_local_ip handles socket errors"""
        state = make_state(tmp_path)
        mock_sock_instance = Mock()
        
        # Make socket operations raise error
        mock_sock_instance.connect.side_effect = OSError("Network error")
        mock_socket_class.return_value = mock_sock_instance
        
        sender = Sender(state=state, sock=Mock())
        ip = sender._get_local_ip()
        
        # Should return fallback IP on error
        assert ip == '0.0.0.0'
