"""
UNIT TESTS FOR srtf_udp_client.py
"""

import pytest

from client import srtf_udp_client


class DummySocket:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class DummyStats:
    def __init__(self):
        self.started = False
        self.ended = False
        self.report_printed = False

    def start_transfer(self):
        self.started = True

    def end_transfer(self):
        self.ended = True

    def print_report(self):
        self.report_printed = True


class DummyState:
    def __init__(self):
        self.p_total = 10
        self.p_valid = 8
        self.p_invalid = 2
        self.p_duplicate = 1
        self.chunks_written = 5
        self.fin_seq = 4


class TestMain:
    def test_main_success(self, monkeypatch, tmp_path):
        """main() should return 0 on successful handshake + receive"""

        output_file = tmp_path / "out.bin"

        monkeypatch.setattr(
            "sys.argv",
            ["srtf_udp_client.py", "10.0.0.1", "test.txt", "-o", str(output_file)]
        )

        send_sock = DummySocket()
        recv_sock = DummySocket()
        stats = DummyStats()

        monkeypatch.setattr("client.srtf_udp_client.create_send_socket", lambda: send_sock)
        monkeypatch.setattr("client.srtf_udp_client.create_recv_socket", lambda port: recv_sock)
        monkeypatch.setattr("client.srtf_udp_client.get_local_ip", lambda server_ip: "10.0.0.2")
        monkeypatch.setattr("client.srtf_udp_client.TransferStats", lambda: stats)
        monkeypatch.setattr("client.srtf_udp_client.send_syn_request", lambda *args, **kwargs: True)
        monkeypatch.setattr("client.srtf_udp_client.receive_file", lambda *args, **kwargs: DummyState())
        monkeypatch.setattr("client.srtf_udp_client.random.randint", lambda a, b: 1234)

        rc = srtf_udp_client.main()

        assert rc == 0
        assert stats.started is True
        assert stats.ended is True
        assert stats.report_printed is True
        assert send_sock.closed is True
        assert recv_sock.closed is True

    def test_main_handshake_failure(self, monkeypatch, tmp_path):
        """main() should return 1 if handshake fails"""

        output_file = tmp_path / "out.bin"

        monkeypatch.setattr(
            "sys.argv",
            ["srtf_udp_client.py", "10.0.0.1", "test.txt", "-o", str(output_file)]
        )

        send_sock = DummySocket()
        recv_sock = DummySocket()
        stats = DummyStats()

        monkeypatch.setattr("client.srtf_udp_client.create_send_socket", lambda: send_sock)
        monkeypatch.setattr("client.srtf_udp_client.create_recv_socket", lambda port: recv_sock)
        monkeypatch.setattr("client.srtf_udp_client.get_local_ip", lambda server_ip: "10.0.0.2")
        monkeypatch.setattr("client.srtf_udp_client.TransferStats", lambda: stats)
        monkeypatch.setattr("client.srtf_udp_client.send_syn_request", lambda *args, **kwargs: False)
        monkeypatch.setattr("client.srtf_udp_client.random.randint", lambda a, b: 1234)

        rc = srtf_udp_client.main()

        assert rc == 1
        assert send_sock.closed is True
        assert recv_sock.closed is True

    def test_main_uses_default_output_path(self, monkeypatch):
        """If -o is not provided, output path should default to ./basename(filename)"""

        monkeypatch.setattr(
            "sys.argv",
            ["srtf_udp_client.py", "10.0.0.1", "folder/test.txt"]
        )

        send_sock = DummySocket()
        recv_sock = DummySocket()
        stats = DummyStats()
        captured = {}

        def fake_receive_file(send_sock_arg, recv_sock_arg, client_ip, server_ip, output_path, stats_arg, conn_id=0):
            captured["output_path"] = output_path
            return DummyState()

        monkeypatch.setattr("client.srtf_udp_client.create_send_socket", lambda: send_sock)
        monkeypatch.setattr("client.srtf_udp_client.create_recv_socket", lambda port: recv_sock)
        monkeypatch.setattr("client.srtf_udp_client.get_local_ip", lambda server_ip: "10.0.0.2")
        monkeypatch.setattr("client.srtf_udp_client.TransferStats", lambda: stats)
        monkeypatch.setattr("client.srtf_udp_client.send_syn_request", lambda *args, **kwargs: True)
        monkeypatch.setattr("client.srtf_udp_client.receive_file", fake_receive_file)
        monkeypatch.setattr("client.srtf_udp_client.random.randint", lambda a, b: 1234)

        rc = srtf_udp_client.main()

        assert rc == 0
        assert captured["output_path"].endswith("test.txt")