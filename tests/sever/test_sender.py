from unittest.mock import Mock, patch

from server.sender import Sender
from server.server_state import ServerConfig, ServerState
from common.constants import FLAG_ACK


def make_state(tmp_path):
    cfg = ServerConfig(out_dir=str(tmp_path / "received"))
    return ServerState(cfg=cfg)


@patch("server.sender.send_packet")
def test_send_ack_with_negative_ack_seq_does_nothing(mock_send_packet, tmp_path):
    state = make_state(tmp_path)
    mock_socket = Mock()

    sender = Sender(state=state, sock=mock_socket)
    sender.send_ack(("127.0.0.1", 9999), -1)

    mock_send_packet.assert_not_called()
    assert state.stats["pkts_out"] == 0
    assert state.stats["acks_out"] == 0


@patch("server.sender.encode_packet")
def test_build_ack_calls_encode_packet_with_correct_arguments(mock_encode_packet, tmp_path):
    state = make_state(tmp_path)
    mock_socket = Mock()
    sender = Sender(state=state, sock=mock_socket)

    mock_encode_packet.return_value = b"encoded-ack"

    result = sender._build_ack(7)

    assert result == b"encoded-ack"
    mock_encode_packet.assert_called_once_with(
        seq_num=0,
        ack_num=7,
        flags=FLAG_ACK,
        payload=b"",
        conn_id=0,
    )


@patch("server.sender.send_packet")
@patch("server.sender.encode_packet")
def test_send_ack_sends_packet_and_updates_stats(mock_encode_packet, mock_send_packet, tmp_path):
    state = make_state(tmp_path)
    mock_socket = Mock()
    sender = Sender(state=state, sock=mock_socket)

    mock_encode_packet.return_value = b"ack-packet"
    addr = ("127.0.0.1", 9999)

    sender.send_ack(addr, 5)

    # Verify send_packet was called with encoded packet
    mock_send_packet.assert_called_once()
    assert state.stats["pkts_out"] == 1
    assert state.stats["acks_out"] == 1


@patch("server.sender.send_packet")
@patch("server.sender.encode_packet")
def test_send_ack_can_be_called_multiple_times(mock_encode_packet, mock_send_packet, tmp_path):
    state = make_state(tmp_path)
    mock_socket = Mock()
    sender = Sender(state=state, sock=mock_socket)

    mock_encode_packet.return_value = b"ack-packet"
    addr = ("127.0.0.1", 9999)

    sender.send_ack(addr, 1)
    sender.send_ack(addr, 2)

    assert mock_send_packet.call_count == 2
    assert state.stats["pkts_out"] == 2
    assert state.stats["acks_out"] == 2


@patch("server.sender.send_packet")
@patch("server.sender.encode_packet")
def test_send_ack_uses_build_ack_result_as_packet(mock_encode_packet, mock_send_packet, tmp_path):
    state = make_state(tmp_path)
    mock_socket = Mock()
    sender = Sender(state=state, sock=mock_socket)

    mock_encode_packet.return_value = b"special-ack"
    addr = ("192.168.1.10", 8080)

    sender.send_ack(addr, 12)

    # Verify send_packet was called with the encoded packet
    assert mock_send_packet.called
    call_args = mock_send_packet.call_args[0]
    sent_packet = call_args[1]  # Second arg to send_packet is the packet
    assert sent_packet == b"special-ack"