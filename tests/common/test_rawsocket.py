"""
Unit tests for rawsocket.py
Tests raw socket functions for IP/UDP header construction and packet send/receive
"""

import struct
import socket
from unittest.mock import Mock, patch, MagicMock
import pytest

from common.rawsocket import (
    build_ip_header,
    build_udp_header,
    send_packet,
    receive_packet,
    create_send_socket,
    create_recv_socket
)
from common.checksum import compute_checksum


class TestBuildIPHeader:
    def test_ip_header_length(self):
        """IP header should be exactly 20 bytes"""
        header = build_ip_header("192.168.1.1", "192.168.1.2", 100)
        assert len(header) == 20

    def test_ip_header_version_and_ihl(self):
        """First byte should be 0x45 (version 4, IHL 5)"""
        header = build_ip_header("192.168.1.1", "192.168.1.2", 100)
        assert header[0] == 0x45

    def test_ip_header_protocol(self):
        """Protocol field should be 17 (UDP)"""
        header = build_ip_header("192.168.1.1", "192.168.1.2", 100)
        assert header[9] == 17  # Byte 9 is protocol

    def test_ip_header_total_length(self):
        """Total length field should include IP header + UDP data"""
        udp_length = 100
        header = build_ip_header("192.168.1.1", "192.168.1.2", udp_length)
        total_length = struct.unpack('!H', header[2:4])[0]
        assert total_length == 20 + udp_length

    def test_ip_addresses_encoded_correctly(self):
        """Source and destination IPs should be in bytes 12-19"""
        src_ip = "10.0.0.1"
        dst_ip = "10.0.0.2"
        header = build_ip_header(src_ip, dst_ip, 100)
        
        # Extract IPs from header
        src_bytes = socket.inet_aton(src_ip)
        dst_bytes = socket.inet_aton(dst_ip)
        
        assert header[12:16] == src_bytes
        assert header[16:20] == dst_bytes


class TestBuildUDPHeader:
    def test_udp_header_length(self):
        """UDP header should be exactly 8 bytes"""
        header = build_udp_header(5000, 6000, 100)
        assert len(header) == 8

    def test_udp_ports_encoded(self):
        """Source and destination ports should be in first 4 bytes"""
        src_port = 9000
        dst_port = 9001
        header = build_udp_header(src_port, dst_port, 100)
        
        extracted_src = struct.unpack('!H', header[0:2])[0]
        extracted_dst = struct.unpack('!H', header[2:4])[0]
        
        assert extracted_src == src_port
        assert extracted_dst == dst_port

    def test_udp_length_field(self):
        """UDP length should include header (8) + payload length"""
        payload_len = 100
        header = build_udp_header(5000, 6000, payload_len)
        
        udp_length = struct.unpack('!H', header[4:6])[0]
        assert udp_length == 8 + payload_len

    def test_udp_checksum_disabled(self):
        """Checksum should be 0 (disabled)"""
        header = build_udp_header(5000, 6000, 100)
        checksum_val = struct.unpack('!H', header[6:8])[0]
        assert checksum_val == 0


class TestChecksum:
    def test_checksum_even_length(self):
        """Checksum should handle even-length data"""
        data = b"\x00\x01\x02\x03"
        result = compute_checksum(data)
        assert isinstance(result, int)
        assert 0 <= result <= 0xFFFF

    def test_checksum_odd_length(self):
        """Checksum should handle odd-length data with padding"""
        data = b"\x00\x01\x02"
        result = compute_checksum(data)
        assert isinstance(result, int)
        assert 0 <= result <= 0xFFFF

    def test_checksum_deterministic(self):
        """Same data should produce same checksum"""
        data = b"hello world"
        result1 = compute_checksum(data)
        result2 = compute_checksum(data)
        assert result1 == result2

    def test_checksum_empty_data(self):
        """Empty data should have checksum 0xFFFF"""
        result = compute_checksum(b"")
        assert result == 0xFFFF


class TestSendPacket:
    @patch('common.rawsocket.build_ip_header')
    @patch('common.rawsocket.build_udp_header')
    def test_send_packet_calls_header_builders(self, mock_udp, mock_ip):
        """send_packet should build IP and UDP headers"""
        mock_sock = Mock()
        mock_ip.return_value = b'\x00' * 20
        mock_udp.return_value = b'\x00' * 8
        
        packet = b"test-payload"
        send_packet(mock_sock, packet, "10.0.0.1", "10.0.0.2", 9000, 9001)
        
        mock_ip.assert_called_once()
        mock_udp.assert_called_once()

    @patch('common.rawsocket.build_ip_header')
    @patch('common.rawsocket.build_udp_header')
    def test_send_packet_calls_sendto(self, mock_udp, mock_ip):
        """send_packet should call socket.sendto"""
        mock_sock = Mock()
        mock_ip.return_value = b'\x00' * 20
        mock_udp.return_value = b'\x00' * 8
        
        packet = b"test-payload"
        dst_ip = "10.0.0.2"
        send_packet(mock_sock, packet, "10.0.0.1", dst_ip, 9000, 9001)
        
        mock_sock.sendto.assert_called_once()
        call_args = mock_sock.sendto.call_args[0]
        assert call_args[1][0] == dst_ip  # Destination IP
        assert call_args[1][1] == 0  # Port is 0 for raw sockets


class TestReceivePacket:
    def test_receive_packet_timeout_returns_none(self):
        """receive_packet should return None on timeout"""
        mock_sock = Mock()
        mock_sock.recvfrom.side_effect = socket.timeout
        
        result = receive_packet(mock_sock, 9000, timeout=0.1)
        assert result is None

    def test_receive_packet_os_error_returns_none(self):
        """receive_packet should return None on OSError"""
        mock_sock = Mock()
        mock_sock.recvfrom.side_effect = OSError
        
        result = receive_packet(mock_sock, 9000, timeout=0.1)
        assert result is None

    def test_receive_packet_filters_wrong_port(self):
        """receive_packet should filter packets to different ports"""
        # Build a fake raw packet with wrong destination port
        ip_header = build_ip_header("10.0.0.2", "10.0.0.1", 35)
        udp_header = build_udp_header(9001, 8888, 15)  # Wrong port
        custom_packet = b"A" * 15
        raw_packet = ip_header + udp_header + custom_packet
        
        mock_sock = Mock()
        mock_sock.recvfrom.return_value = (raw_packet, ("10.0.0.2", 0))
        
        result = receive_packet(mock_sock, 9000, timeout=0.1)  # Expect port 9000
        assert result is None  # Should be filtered out


class TestSocketCreation:
    @patch('socket.socket')
    def test_create_send_socket_creates_raw_socket(self, mock_socket_class):
        """create_send_socket should create SOCK_RAW with IPPROTO_RAW"""
        mock_sock = Mock()
        mock_socket_class.return_value = mock_sock
        
        result = create_send_socket()
        
        mock_socket_class.assert_called_once_with(
            socket.AF_INET, 
            socket.SOCK_RAW, 
            socket.IPPROTO_RAW
        )
        mock_sock.setsockopt.assert_called_once_with(
            socket.IPPROTO_IP,
            socket.IP_HDRINCL,
            1
        )

    @patch('socket.socket')
    def test_create_recv_socket_creates_udp_raw_socket(self, mock_socket_class):
        """create_recv_socket should create SOCK_RAW with IPPROTO_UDP"""
        mock_sock = Mock()
        mock_socket_class.return_value = mock_sock
        
        port = 9000
        result = create_recv_socket(port)
        
        mock_socket_class.assert_called_once_with(
            socket.AF_INET,
            socket.SOCK_RAW,
            socket.IPPROTO_UDP
        )
        mock_sock.bind.assert_called_once_with(('', port))


class TestEdgeCases:
    def test_ip_header_with_max_udp_length(self):
        """IP header should handle maximum UDP length"""
        max_udp = 65535 - 20  # Max IP packet - IP header
        header = build_ip_header("1.1.1.1", "2.2.2.2", max_udp)
        assert len(header) == 20

    def test_udp_header_with_max_ports(self):
        """UDP header should handle max port numbers"""
        header = build_udp_header(65535, 65535, 100)
        assert len(header) == 8

    def test_checksum_handles_large_data(self):
        """Checksum should handle large payloads"""
        large_data = b"X" * 10000
        result = compute_checksum(large_data)
        assert isinstance(result, int)
        assert 0 <= result <= 0xFFFF
