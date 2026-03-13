from unittest.mock import Mock, patch

from server.receiver import Receiver, ReceiveResult
from server.server_state import ServerConfig, ServerState
from server.window_manager import WindowManager


def make_state(tmp_path):
    cfg = ServerConfig(out_dir=str(tmp_path / "received"))
    return ServerState(cfg=cfg)


def make_receiver(tmp_path):
    state = make_state(tmp_path)
    wm = WindowManager(window_size=10)
    return Receiver(state, wm), state, wm


def test_first_client_is_bound(tmp_path):
    receiver, state, wm = make_receiver(tmp_path)

    with patch.object(receiver, "_decode_and_verify") as mock_decode:
        mock_decode.return_value = {
            "type": "DATA",
            "seq": 0,
            "payload": b"x"
        }

        receiver.handle_datagram(b"packet", ("127.0.0.1", 9001))

        assert state.client == ("127.0.0.1", 9001)


def test_other_clients_are_ignored(tmp_path):
    receiver, state, wm = make_receiver(tmp_path)

    state.client = ("127.0.0.1", 9001)

    result = receiver.handle_datagram(b"packet", ("127.0.0.1", 9002))

    assert result == ReceiveResult()


def test_corrupt_packet_updates_stats(tmp_path):
    receiver, state, wm = make_receiver(tmp_path)

    with patch.object(receiver, "_decode_and_verify", return_value=None):

        receiver.handle_datagram(b"bad", ("127.0.0.1", 9001))

        assert state.stats["corrupt_in"] == 1


def test_fin_packet_closes_connection(tmp_path):
    receiver, state, wm = make_receiver(tmp_path)

    with patch.object(receiver, "_decode_and_verify") as mock_decode:
        mock_decode.return_value = {
            "type": "FIN",
            "seq": 0,
            "payload": b""
        }

        result = receiver.handle_datagram(b"x", ("127.0.0.1", 9001))

        assert result.close is True


def test_duplicate_packet_updates_dup_stats(tmp_path):
    receiver, state, wm = make_receiver(tmp_path)

    with patch.object(receiver, "_decode_and_verify") as mock_decode:
        mock_decode.return_value = {
            "type": "DATA",
            "seq": 5,
            "payload": b"abc"
        }

        wm.mark_received = Mock(return_value=(False, False))

        result = receiver.handle_datagram(b"x", ("127.0.0.1", 9001))

        assert state.stats["dup_in"] == 1
        assert result.ack_seq == 5


def test_out_of_window_packet(tmp_path):
    receiver, state, wm = make_receiver(tmp_path)

    wm.expected_seq = 10

    with patch.object(receiver, "_decode_and_verify") as mock_decode:
        mock_decode.return_value = {
            "type": "DATA",
            "seq": 30,
            "payload": b"x"
        }

        wm.mark_received = Mock(return_value=(True, False))
        wm.in_window = Mock(return_value=False)

        result = receiver.handle_datagram(b"x", ("127.0.0.1", 9001))

        assert state.stats["out_of_order_in"] == 1
        assert result.ack_seq == 9


def test_in_order_delivery(tmp_path):
    receiver, state, wm = make_receiver(tmp_path)

    with patch.object(receiver, "_decode_and_verify") as mock_decode:
        mock_decode.return_value = {
            "type": "DATA",
            "seq": 0,
            "payload": b"abc"
        }

        wm.mark_received = Mock(return_value=(True, True))
        wm.in_window = Mock(return_value=True)
        wm.pop_in_order = Mock(return_value=[(0, b"abc")])

        result = receiver.handle_datagram(b"x", ("127.0.0.1", 9001))

        assert result.ack_seq == wm.expected_seq - 1