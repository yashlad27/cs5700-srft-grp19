"""
UNIT TESTS FOR receiver.py
"""

import os
import pytest

from client.receiver import receive_file
from common.constants import (
    FLAG_DATA,
    FLAG_FIN_DATA,
    FLAG_ACK,
    FLAG_FIN_ACK,
)


class DummyStats:
    """Simple fake stats object for testing."""

    def __init__(self):
        self.received = []
        self.sent = []
        self.acks_sent = 0

    def record_receive(self, n):
        self.received.append(n)

    def record_send(self, n):
        self.sent.append(n)

    def record_ack_sent(self):
        self.acks_sent += 1


class TestReceiveFile:
    def test_receive_single_data_then_fin_data(self, tmp_path, monkeypatch):
        """
        Client should:
        - receive seq 0 DATA
        - receive seq 1 FIN_DATA
        - write both chunks in order
        - send ACKs
        - send FIN_ACK and exit
        """
        output_file = tmp_path / "out.bin"
        stats = DummyStats()

        packets = [
            (
                {
                    "seq_num": 0,
                    "ack_num": 0,
                    "payload_length": 1,
                    "flags": FLAG_DATA,
                    "conn_id": 0,
                    "payload": b"A",
                },
                "1.2.3.4",
                5005,
            ),
            (
                {
                    "seq_num": 1,
                    "ack_num": 0,
                    "payload_length": 1,
                    "flags": FLAG_FIN_DATA,
                    "conn_id": 0,
                    "payload": b"B",
                },
                "1.2.3.4",
                5005,
            ),
        ]

        sent_packets = []

        def fake_receive_packet(sock, expected_port, timeout=None):
            if packets:
                return packets.pop(0)
            return None

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

        monkeypatch.setattr("client.receiver.receive_packet", fake_receive_packet)
        monkeypatch.setattr("client.receiver.encode_packet", fake_encode_packet)
        monkeypatch.setattr("client.receiver.send_packet", fake_send_packet)

        state = receive_file(
            send_sock=object(),
            recv_sock=object(),
            client_ip="10.0.0.2",
            server_ip="10.0.0.1",
            output_path=str(output_file),
            stats=stats,
            conn_id=0,
        )

        assert output_file.read_bytes() == b"AB"
        assert state.expected_seq == 2
        assert state.fin_seq == 1
        assert state.chunks_written == 2
        assert state.p_valid == 2
        assert state.p_invalid == 0

        # First two sends should be ACKs for expected_seq 1 and 2
        assert sent_packets[0]["packet"]["flags"] == FLAG_ACK
        assert sent_packets[0]["packet"]["ack_num"] == 1

        assert sent_packets[1]["packet"]["flags"] == FLAG_ACK
        assert sent_packets[1]["packet"]["ack_num"] == 2

        # Then FIN_ACK is sent 3 times
        fin_acks = [p for p in sent_packets if p["packet"]["flags"] == FLAG_FIN_ACK]
        assert len(fin_acks) == 3
        for p in fin_acks:
            assert p["packet"]["ack_num"] == 2

        assert stats.acks_sent == 2

    def test_receive_out_of_order_then_reassemble(self, tmp_path, monkeypatch):
        """
        seq 1 arrives before seq 0.
        Client should buffer seq 1, ACK 0, then after seq 0 arrives write both.
        """
        output_file = tmp_path / "out.bin"
        stats = DummyStats()

        packets = [
            (
                {
                    "seq_num": 1,
                    "ack_num": 0,
                    "payload_length": 1,
                    "flags": FLAG_DATA,
                    "conn_id": 0,
                    "payload": b"B",
                },
                "1.2.3.4",
                5005,
            ),
            (
                {
                    "seq_num": 0,
                    "ack_num": 0,
                    "payload_length": 1,
                    "flags": FLAG_FIN_DATA,
                    "conn_id": 0,
                    "payload": b"A",
                },
                "1.2.3.4",
                5005,
            ),
        ]

        sent_packets = []

        def fake_receive_packet(sock, expected_port, timeout=None):
            if packets:
                return packets.pop(0)
            return None

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

        monkeypatch.setattr("client.receiver.receive_packet", fake_receive_packet)
        monkeypatch.setattr("client.receiver.encode_packet", fake_encode_packet)
        monkeypatch.setattr("client.receiver.send_packet", fake_send_packet)

        state = receive_file(
            send_sock=object(),
            recv_sock=object(),
            client_ip="10.0.0.2",
            server_ip="10.0.0.1",
            output_path=str(output_file),
            stats=stats,
            conn_id=0,
        )

        # Because seq 1 came first, it gets buffered until seq 0 arrives
        assert output_file.read_bytes() == b"AB"
        assert state.p_valid == 2

        # First ACK should still be 0 because seq 0 was missing
        assert sent_packets[0]["flags"] == FLAG_ACK
        assert sent_packets[0]["ack_num"] == 0

    def test_drop_invalid_packet(self, tmp_path, monkeypatch):
        """
        If receive_packet returns (None, ip, port), packet is invalid and should be dropped.
        """
        output_file = tmp_path / "out.bin"
        stats = DummyStats()

        packets = [
            (None, "1.2.3.4", 5005),
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
        ]

        sent_packets = []

        def fake_receive_packet(sock, expected_port, timeout=None):
            if packets:
                return packets.pop(0)
            return None

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

        monkeypatch.setattr("client.receiver.receive_packet", fake_receive_packet)
        monkeypatch.setattr("client.receiver.encode_packet", fake_encode_packet)
        monkeypatch.setattr("client.receiver.send_packet", fake_send_packet)

        state = receive_file(
            send_sock=object(),
            recv_sock=object(),
            client_ip="10.0.0.2",
            server_ip="10.0.0.1",
            output_path=str(output_file),
            stats=stats,
            conn_id=0,
        )

        assert output_file.read_bytes() == b""
        assert state.p_invalid == 1
        assert state.p_valid == 0
        assert len(sent_packets) == 0

    def test_drop_wrong_conn_id(self, tmp_path, monkeypatch):
        """
        Packet with wrong conn_id should be dropped.
        """
        output_file = tmp_path / "out.bin"
        stats = DummyStats()

        packets = [
            (
                {
                    "seq_num": 0,
                    "ack_num": 0,
                    "payload_length": 1,
                    "flags": FLAG_DATA,
                    "conn_id": 999,
                    "payload": b"A",
                },
                "1.2.3.4",
                5005,
            ),
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
        ]

        sent_packets = []

        def fake_receive_packet(sock, expected_port, timeout=None):
            if packets:
                return packets.pop(0)
            return None

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

        monkeypatch.setattr("client.receiver.receive_packet", fake_receive_packet)
        monkeypatch.setattr("client.receiver.encode_packet", fake_encode_packet)
        monkeypatch.setattr("client.receiver.send_packet", fake_send_packet)

        state = receive_file(
            send_sock=object(),
            recv_sock=object(),
            client_ip="10.0.0.2",
            server_ip="10.0.0.1",
            output_path=str(output_file),
            stats=stats,
            conn_id=0,
        )

        assert output_file.read_bytes() == b""
        assert state.p_invalid == 1
        assert state.p_valid == 0
        assert len(sent_packets) == 0

    def test_duplicate_packet_only_written_once(self, tmp_path, monkeypatch):
        """
        Duplicate DATA packet should only written once.
        """
        output_file = tmp_path / "out.bin"
        stats = DummyStats()

        packets = [
            (
                {
                    "seq_num": 0,
                    "ack_num": 0,
                    "payload_length": 1,
                    "flags": FLAG_DATA,
                    "conn_id": 0,
                    "payload": b"A",
                },
                "1.2.3.4",
                5005,
            ),
            (
                {
                    "seq_num": 0,
                    "ack_num": 0,
                    "payload_length": 1,
                    "flags": FLAG_FIN_DATA,
                    "conn_id": 0,
                    "payload": b"A",
                },
                "1.2.3.4",
                5005,
            ),
        ]

        sent_packets = []

        def fake_receive_packet(sock, expected_port, timeout=None):
            if packets:
                return packets.pop(0)
            return None

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

        monkeypatch.setattr("client.receiver.receive_packet", fake_receive_packet)
        monkeypatch.setattr("client.receiver.encode_packet", fake_encode_packet)
        monkeypatch.setattr("client.receiver.send_packet", fake_send_packet)

        state = receive_file(
            send_sock=object(),
            recv_sock=object(),
            client_ip="10.0.0.2",
            server_ip="10.0.0.1",
            output_path=str(output_file),
            stats=stats,
            conn_id=0,
        )

        assert output_file.read_bytes() == b"A"
        assert state.p_duplicate >= 1
        assert state.chunks_written == 1