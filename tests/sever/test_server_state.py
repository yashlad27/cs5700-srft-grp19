from pathlib import Path

from server.server_state import (
    ServerConfig,
    SecurityContext,
    FileReceiveContext,
    ServerState,
)


def test_server_config_default_values():
    cfg = ServerConfig()

    assert cfg.listen_ip == "0.0.0.0"
    assert cfg.listen_port == 9000
    assert cfg.out_dir == "./received"
    assert cfg.chunk_size == 1200
    assert cfg.window_size == 64
    assert cfg.recv_buffer_limit == 4096
    assert cfg.rto_ms == 200
    assert cfg.max_retries == 20


def test_security_context_default_values():
    sec = SecurityContext()

    assert sec.enabled is False
    assert sec.conn_id == 0
    assert sec.keys == {}
    assert sec.highest_pn == -1
    assert sec.seen_pn == set()


def test_file_receive_context_default_values():
    ctx = FileReceiveContext()

    assert ctx.filename is None
    assert ctx.expected_total_chunks is None
    assert ctx.written_chunks == 0
    assert ctx.fp is None


def test_server_state_initial_defaults(tmp_path):
    cfg = ServerConfig(out_dir=str(tmp_path / "received_files"))
    state = ServerState(cfg=cfg)

    assert state.cfg == cfg
    assert state.client is None
    assert state.file_ctx.filename is None
    assert state.file_ctx.expected_total_chunks is None
    assert state.file_ctx.written_chunks == 0

    assert state.sec.enabled is False
    assert state.sec.conn_id == 0
    assert state.sec.keys == {}
    assert state.sec.highest_pn == -1
    assert state.sec.seen_pn == set()

    expected_stats = {
        "pkts_in": 0,
        "pkts_out": 0,
        "data_in": 0,
        "data_out": 0,
        "acks_in": 0,
        "acks_out": 0,
        "dup_in": 0,
        "corrupt_in": 0,
        "out_of_order_in": 0,
        "delivered": 0,
        "retransmitted": 0,
    }
    assert state.stats == expected_stats


def test_server_state_stats_are_independent_between_instances(tmp_path):
    cfg1 = ServerConfig(out_dir=str(tmp_path / "dir1"))
    cfg2 = ServerConfig(out_dir=str(tmp_path / "dir2"))

    state1 = ServerState(cfg=cfg1)
    state2 = ServerState(cfg=cfg2)

    state1.stats["pkts_in"] += 1

    assert state1.stats["pkts_in"] == 1
    assert state2.stats["pkts_in"] == 0


def test_ensure_out_dir_creates_directory(tmp_path):
    out_dir = tmp_path / "new_received_dir"
    cfg = ServerConfig(out_dir=str(out_dir))
    state = ServerState(cfg=cfg)

    result = state.ensure_out_dir()

    assert isinstance(result, Path)
    assert result == out_dir
    assert out_dir.exists()
    assert out_dir.is_dir()


def test_ensure_out_dir_is_idempotent(tmp_path):
    out_dir = tmp_path / "existing_dir"
    cfg = ServerConfig(out_dir=str(out_dir))
    state = ServerState(cfg=cfg)

    first = state.ensure_out_dir()
    second = state.ensure_out_dir()

    assert first == second
    assert out_dir.exists()
    assert out_dir.is_dir()


def test_server_state_can_store_active_client(tmp_path):
    cfg = ServerConfig(out_dir=str(tmp_path / "received"))
    state = ServerState(cfg=cfg)

    client_addr = ("127.0.0.1", 9999)
    state.client = client_addr

    assert state.client == client_addr


def test_file_receive_context_fields_can_be_updated(tmp_path):
    cfg = ServerConfig(out_dir=str(tmp_path / "received"))
    state = ServerState(cfg=cfg)

    state.file_ctx.filename = "test.txt"
    state.file_ctx.expected_total_chunks = 10
    state.file_ctx.written_chunks = 3

    assert state.file_ctx.filename == "test.txt"
    assert state.file_ctx.expected_total_chunks == 10
    assert state.file_ctx.written_chunks == 3


def test_security_context_fields_can_be_updated():
    sec = SecurityContext()

    sec.enabled = True
    sec.conn_id = 42
    sec.keys["k_enc"] = b"secret"
    sec.highest_pn = 100
    sec.seen_pn.add(100)

    assert sec.enabled is True
    assert sec.conn_id == 42
    assert sec.keys["k_enc"] == b"secret"
    assert sec.highest_pn == 100
    assert 100 in sec.seen_pn


def test_file_receive_context_file_size_default():
    ctx = FileReceiveContext()
    assert ctx.file_size == 0


def test_transfer_timer(tmp_path):
    import time
    cfg = ServerConfig(out_dir=str(tmp_path / "received"))
    state = ServerState(cfg=cfg)

    assert state.get_transfer_duration() == 0.0

    state.start_transfer_timer()
    time.sleep(0.05)
    state.stop_transfer_timer()

    duration = state.get_transfer_duration()
    assert duration >= 0.04
    assert duration < 1.0


def test_format_duration(tmp_path):
    cfg = ServerConfig(out_dir=str(tmp_path / "received"))
    state = ServerState(cfg=cfg)

    assert state.format_duration(0) == "00:00:00"
    assert state.format_duration(61) == "00:01:01"
    assert state.format_duration(3661) == "01:01:01"
    assert state.format_duration(7200.5) == "02:00:00"


def test_write_stats_report(tmp_path):
    cfg = ServerConfig(out_dir=str(tmp_path / "received"))
    state = ServerState(cfg=cfg)
    state.file_ctx.filename = "test_file.bin"
    state.file_ctx.file_size = 10240
    state.stats["pkts_out"] = 15
    state.stats["retransmitted"] = 2
    state.stats["pkts_in"] = 12
    state.transfer_start = 1000.0
    state.transfer_end = 1005.0

    output_path = str(tmp_path / "stats.txt")
    report = state.write_stats_report(output_path=output_path)

    assert "Name of the transferred file: test_file.bin" in report
    assert "Size of the transferred file: 10240" in report
    assert "packets sent from the server: 15" in report
    assert "retransmitted packets from the server: 2" in report
    assert "packets received from the client: 12" in report
    assert "00:00:05" in report

    with open(output_path) as f:
        contents = f.read()
    assert contents == report


def test_write_stats_report_default_path(tmp_path):
    cfg = ServerConfig(out_dir=str(tmp_path / "received"))
    state = ServerState(cfg=cfg)
    state.file_ctx.filename = "data.bin"
    state.transfer_start = 0.0
    state.transfer_end = 0.0

    report = state.write_stats_report()

    expected_path = tmp_path / "received" / "transfer_stats.txt"
    assert expected_path.exists()
    with open(expected_path) as f:
        assert f.read() == report