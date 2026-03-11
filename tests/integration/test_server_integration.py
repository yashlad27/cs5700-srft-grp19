from unittest.mock import Mock

from server.server_state import ServerConfig, ServerState
from server.window_manager import WindowManager
from server.receiver import Receiver
from server.sender import Sender

from common.packet import encode_packet, decode_packet
from common.constants import FLAG_DATA, FLAG_ACK, FLAG_FIN


def make_components(tmp_path):
    cfg = ServerConfig(out_dir=str(tmp_path / "received"))
    state = ServerState(cfg=cfg)
    wm = WindowManager(window_size=10)
    receiver = Receiver(state=state, wm=wm)
    mock_socket = Mock()
    sender = Sender(state=state, sock=mock_socket)
    addr = ("127.0.0.1", 9999)
    return state, wm, receiver, sender, mock_socket, addr


def close_file_if_open(state: ServerState):
    if state.file_ctx.fp is not None:
        state.file_ctx.fp.close()
        state.file_ctx.fp = None


def test_end_to_end_single_data_chunk_ack_and_file_write(tmp_path):
    state, wm, receiver, sender, mock_socket, addr = make_components(tmp_path)
    state.file_ctx.filename = "output.bin"

    data_pkt = encode_packet(
        seq_num=0,
        ack_num=0,
        flags=FLAG_DATA,
        payload=b"hello",
        conn_id=0,
    )

    result = receiver.handle_datagram(data_pkt, addr)

    assert result.close is False
    assert result.ack_seq == 0

    sender.send_ack(addr, result.ack_seq)

    mock_socket.sendto.assert_called_once()
    sent_bytes, sent_addr = mock_socket.sendto.call_args[0]

    assert sent_addr == addr

    ack_pkt = decode_packet(sent_bytes)
    assert ack_pkt is not None
    assert ack_pkt["ack_num"] == 0
    assert ack_pkt["flags"] & FLAG_ACK

    close_file_if_open(state)

    output_path = tmp_path / "received" / "output.bin"
    assert output_path.exists()
    assert output_path.read_bytes() == b"hello"

    assert state.stats["pkts_in"] == 1
    assert state.stats["pkts_out"] == 1
    assert state.stats["acks_out"] == 1
    assert state.stats["delivered"] == 1
    assert state.file_ctx.written_chunks == 1
    assert state.client == addr


def test_end_to_end_out_of_order_then_in_order_reassembles_file(tmp_path):
    state, wm, receiver, sender, mock_socket, addr = make_components(tmp_path)
    state.file_ctx.filename = "reassembled.bin"

    pkt1 = encode_packet(
        seq_num=1,
        ack_num=0,
        flags=FLAG_DATA,
        payload=b"world",
        conn_id=0,
    )
    pkt0 = encode_packet(
        seq_num=0,
        ack_num=0,
        flags=FLAG_DATA,
        payload=b"hello ",
        conn_id=0,
    )

    result1 = receiver.handle_datagram(pkt1, addr)
    assert result1.close is False
    assert result1.ack_seq == -1

    sender.send_ack(addr, result1.ack_seq)
    mock_socket.sendto.assert_not_called()

    result0 = receiver.handle_datagram(pkt0, addr)
    assert result0.close is False
    assert result0.ack_seq == 1

    sender.send_ack(addr, result0.ack_seq)
    mock_socket.sendto.assert_called_once()

    sent_bytes, sent_addr = mock_socket.sendto.call_args[0]
    assert sent_addr == addr

    ack_pkt = decode_packet(sent_bytes)
    assert ack_pkt is not None
    assert ack_pkt["ack_num"] == 1
    assert ack_pkt["flags"] & FLAG_ACK

    close_file_if_open(state)

    output_path = tmp_path / "received" / "reassembled.bin"
    assert output_path.exists()
    assert output_path.read_bytes() == b"hello world"

    assert state.stats["pkts_in"] == 2
    assert state.stats["pkts_out"] == 1
    assert state.stats["acks_out"] == 1
    assert state.stats["delivered"] == 2
    assert state.file_ctx.written_chunks == 2
    assert wm.expected_seq == 2


def test_end_to_end_duplicate_packet_only_writes_once(tmp_path):
    state, wm, receiver, sender, mock_socket, addr = make_components(tmp_path)
    state.file_ctx.filename = "dup.bin"

    pkt0 = encode_packet(
        seq_num=0,
        ack_num=0,
        flags=FLAG_DATA,
        payload=b"chunk0",
        conn_id=0,
    )

    result1 = receiver.handle_datagram(pkt0, addr)
    assert result1.ack_seq == 0
    sender.send_ack(addr, result1.ack_seq)

    result2 = receiver.handle_datagram(pkt0, addr)
    assert result2.ack_seq == 0
    sender.send_ack(addr, result2.ack_seq)

    assert mock_socket.sendto.call_count == 2

    close_file_if_open(state)

    output_path = tmp_path / "received" / "dup.bin"
    assert output_path.exists()
    assert output_path.read_bytes() == b"chunk0"

    assert state.stats["pkts_in"] == 2
    assert state.stats["pkts_out"] == 2
    assert state.stats["acks_out"] == 2
    assert state.stats["dup_in"] == 1
    assert state.stats["delivered"] == 1
    assert state.file_ctx.written_chunks == 1


def test_end_to_end_fin_packet_requests_close(tmp_path):
    state, wm, receiver, sender, mock_socket, addr = make_components(tmp_path)

    fin_pkt = encode_packet(
        seq_num=0,
        ack_num=0,
        flags=FLAG_FIN,
        payload=b"",
        conn_id=0,
    )

    result = receiver.handle_datagram(fin_pkt, addr)

    assert result.close is True
    assert result.ack_seq is None
    assert state.stats["pkts_in"] == 1
    mock_socket.sendto.assert_not_called()