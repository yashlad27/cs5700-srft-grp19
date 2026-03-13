"""
UNIT TESTS FOR request_handler.py
"""

import socket
import pytest

from client.request_handler import get_local_ip, send_syn_request
from common.constants import CLIENT_PORT, SERVER_PORT, FLAG_SYN, FLAG_SYN_ACK


class TestGetLocalIP:
    def test_get_local_ip_returns_string(self, monkeypatch):
        """get_local_ip should return the local IP selected by the OS"""

        class FakeSocket:
            def __init__(self, *args, **kwargs):
                self.closed = False

            def connect(self, addr):
                self.addr = addr

            def getsockname(self):
                return ("192.168.1.100", 54321)

            def close(self):
                self.closed = True

        monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: FakeSocket())

        ip = get_local_ip("8.8.8.8")

        assert ip == "192.168.1.100"


class TestSendSynRequest:
    def test_send_syn_request_success_first_try(self, monkeypatch):
        """Client should send SYN and return True when SYN_ACK is received"""
        sent_packets = []

        def fake_encode_packet(seq_num, ack_num, flags, payload, conn_id):
            return {
                "seq_num": seq_num,
                "ack_num": ack_num,
                "flags": flags,
                "payload": payload,
                "conn_id": conn_id,
            }

        def fake_send_packet(sock, packet_bytes, src_ip, dst_ip, src_port, dst_port):
            sent_packets.append(
                {
                    "packet": packet_bytes,
                    "src_ip": src_ip,
                    "dst_ip": dst_ip,
                    "src_port": src_port,
                    "dst_port": dst_port,
                }
            )

        responses = [
            (
                {
                    "seq_num": 0,
                    "ack_num": 0,
                    "flags": FLAG_SYN_ACK,
                    "payload": b"",
                    "conn_id": 0,
                },
                "10.0.0.1",
                SERVER_PORT,
            )
        ]

        def fake_receive_packet(sock, expected_port, timeout=None):
            if responses:
                return responses.pop(0)
            return None

        monkeypatch.setattr("client.request_handler.encode_packet", fake_encode_packet)
        monkeypatch.setattr("client.request_handler.send_packet", fake_send_packet)
        monkeypatch.setattr("client.request_handler.receive_packet", fake_receive_packet)

        ok = send_syn_request(
            send_sock=object(),
            recv_sock=object(),
            client_ip="10.0.0.2",
            server_ip="10.0.0.1",
            filename="test.txt",
            conn_id=0,
            retries=3,
            max_wait_time=0.1,
        )

        assert ok is True
        assert len(sent_packets) == 1
        assert sent_packets[0]["packet"]["flags"] == FLAG_SYN
        assert sent_packets[0]["packet"]["payload"] == b"test.txt"
        assert sent_packets[0]["src_port"] == CLIENT_PORT
        assert sent_packets[0]["dst_port"] == SERVER_PORT

    def test_send_syn_request_retries_then_succeeds(self, monkeypatch):
        """Client should retry SYN if no SYN_ACK arrives immediately"""
        sent_packets = []

        def fake_encode_packet(seq_num, ack_num, flags, payload, conn_id):
            return {
                "seq_num": seq_num,
                "ack_num": ack_num,
                "flags": flags,
                "payload": payload,
                "conn_id": conn_id,
            }

        def fake_send_packet(sock, packet_bytes, src_ip, dst_ip, src_port, dst_port):
            sent_packets.append(packet_bytes)

        responses = [
            None,  # timeout
            None,  # timeout
            (
                {
                    "seq_num": 0,
                    "ack_num": 0,
                    "flags": FLAG_SYN_ACK,
                    "payload": b"",
                    "conn_id": 0,
                },
                "10.0.0.1",
                SERVER_PORT,
            ),
        ]

        def fake_receive_packet(sock, expected_port, timeout=None):
            if responses:
                return responses.pop(0)
            return None

        monkeypatch.setattr("client.request_handler.encode_packet", fake_encode_packet)
        monkeypatch.setattr("client.request_handler.send_packet", fake_send_packet)
        monkeypatch.setattr("client.request_handler.receive_packet", fake_receive_packet)

        ok = send_syn_request(
            send_sock=object(),
            recv_sock=object(),
            client_ip="10.0.0.2",
            server_ip="10.0.0.1",
            filename="file.bin",
            conn_id=7,
            retries=3,
            max_wait_time=0.1,
        )

        assert ok is True
        assert len(sent_packets) >= 1

    def test_send_syn_request_ignores_invalid_packet(self, monkeypatch):
        """Corrupted/invalid packet (packet=None) should be ignored"""
        sent_packets = []

        def fake_encode_packet(seq_num, ack_num, flags, payload, conn_id):
            return {"flags": flags, "payload": payload, "conn_id": conn_id}

        def fake_send_packet(sock, packet_bytes, src_ip, dst_ip, src_port, dst_port):
            sent_packets.append(packet_bytes)

        responses = [
            (None, "10.0.0.1", SERVER_PORT),  # invalid packet
            (
                {
                    "seq_num": 0,
                    "ack_num": 0,
                    "flags": FLAG_SYN_ACK,
                    "payload": b"",
                    "conn_id": 0,
                },
                "10.0.0.1",
                SERVER_PORT,
            ),
        ]

        def fake_receive_packet(sock, expected_port, timeout=None):
            if responses:
                return responses.pop(0)
            return None

        monkeypatch.setattr("client.request_handler.encode_packet", fake_encode_packet)
        monkeypatch.setattr("client.request_handler.send_packet", fake_send_packet)
        monkeypatch.setattr("client.request_handler.receive_packet", fake_receive_packet)

        ok = send_syn_request(
            send_sock=object(),
            recv_sock=object(),
            client_ip="10.0.0.2",
            server_ip="10.0.0.1",
            filename="hello.txt",
            conn_id=0,
            retries=2,
            max_wait_time=0.1,
        )

        assert ok is True

    def test_send_syn_request_fails_after_all_retries(self, monkeypatch):
        """If no SYN_ACK is ever received, function should return False"""

        def fake_encode_packet(seq_num, ack_num, flags, payload, conn_id):
            return {"flags": flags, "payload": payload, "conn_id": conn_id}

        def fake_send_packet(sock, packet_bytes, src_ip, dst_ip, src_port, dst_port):
            pass

        def fake_receive_packet(sock, expected_port, timeout=None):
            return None

        monkeypatch.setattr("client.request_handler.encode_packet", fake_encode_packet)
        monkeypatch.setattr("client.request_handler.send_packet", fake_send_packet)
        monkeypatch.setattr("client.request_handler.receive_packet", fake_receive_packet)

        ok = send_syn_request(
            send_sock=object(),
            recv_sock=object(),
            client_ip="10.0.0.2",
            server_ip="10.0.0.1",
            filename="missing.txt",
            conn_id=0,
            retries=2,
            max_wait_time=0.05,
        )

        assert ok is False