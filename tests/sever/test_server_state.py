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