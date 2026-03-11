from unittest.mock import Mock, patch

from server.retransmit_queue import RetransmitQueue


def test_add_inserts_item_into_queue():
    mock_socket = Mock()

    with patch("server.retransmit_queue.time.time", return_value=100.0):
        rq = RetransmitQueue(sock=mock_socket, rto_ms=500, max_retries=10)
        rq.add("pkt1", b"hello", ("127.0.0.1", 9000))

    assert "pkt1" in rq.items
    item = rq.items["pkt1"]
    assert item.key == "pkt1"
    assert item.payload == b"hello"
    assert item.addr == ("127.0.0.1", 9000)
    assert item.retries == 0
    assert item.deadline == 100.5
    assert len(rq.heap) == 1


def test_ack_removes_item_logically():
    mock_socket = Mock()

    with patch("server.retransmit_queue.time.time", return_value=100.0):
        rq = RetransmitQueue(sock=mock_socket, rto_ms=500, max_retries=10)
        rq.add("pkt1", b"hello", ("127.0.0.1", 9000))

    rq.ack("pkt1")

    assert "pkt1" not in rq.items
    assert len(rq.heap) == 1


def test_tick_does_nothing_before_deadline():
    mock_socket = Mock()

    with patch("server.retransmit_queue.time.time", return_value=100.0):
        rq = RetransmitQueue(sock=mock_socket, rto_ms=500, max_retries=10)
        rq.add("pkt1", b"hello", ("127.0.0.1", 9000))

    with patch("server.retransmit_queue.time.time", return_value=100.4):
        rq.tick()

    mock_socket.sendto.assert_not_called()
    assert "pkt1" in rq.items
    assert rq.items["pkt1"].retries == 0


def test_tick_retransmits_expired_item_and_updates_retry_and_deadline():
    mock_socket = Mock()

    with patch("server.retransmit_queue.time.time", return_value=100.0):
        rq = RetransmitQueue(sock=mock_socket, rto_ms=500, max_retries=10)
        rq.add("pkt1", b"hello", ("127.0.0.1", 9000))

    with patch("server.retransmit_queue.time.time", return_value=100.6):
        rq.tick()

    mock_socket.sendto.assert_called_once_with(b"hello", ("127.0.0.1", 9000))
    assert "pkt1" in rq.items
    assert rq.items["pkt1"].retries == 1
    assert rq.items["pkt1"].deadline == 101.1


def test_tick_skips_acked_items_in_heap():
    mock_socket = Mock()

    with patch("server.retransmit_queue.time.time", return_value=100.0):
        rq = RetransmitQueue(sock=mock_socket, rto_ms=500, max_retries=10)
        rq.add("pkt1", b"hello", ("127.0.0.1", 9000))

    rq.ack("pkt1")

    with patch("server.retransmit_queue.time.time", return_value=100.6):
        rq.tick()

    mock_socket.sendto.assert_not_called()
    assert "pkt1" not in rq.items


def test_tick_removes_item_after_max_retries_reached():
    mock_socket = Mock()

    with patch("server.retransmit_queue.time.time", return_value=100.0):
        rq = RetransmitQueue(sock=mock_socket, rto_ms=500, max_retries=2)
        rq.add("pkt1", b"hello", ("127.0.0.1", 9000))

    # first retransmission
    with patch("server.retransmit_queue.time.time", return_value=100.6):
        rq.tick()

    # second retransmission
    with patch("server.retransmit_queue.time.time", return_value=101.2):
        rq.tick()

    # now retries == max_retries, next expiration should remove it
    with patch("server.retransmit_queue.time.time", return_value=101.8):
        rq.tick()

    assert mock_socket.sendto.call_count == 2
    assert "pkt1" not in rq.items


def test_tick_handles_multiple_expired_items():
    mock_socket = Mock()

    with patch("server.retransmit_queue.time.time", return_value=100.0):
        rq = RetransmitQueue(sock=mock_socket, rto_ms=500, max_retries=10)
        rq.add("pkt1", b"a", ("127.0.0.1", 9001))
        rq.add("pkt2", b"b", ("127.0.0.1", 9002))

    with patch("server.retransmit_queue.time.time", return_value=100.6):
        rq.tick()

    assert mock_socket.sendto.call_count == 2
    mock_socket.sendto.assert_any_call(b"a", ("127.0.0.1", 9001))
    mock_socket.sendto.assert_any_call(b"b", ("127.0.0.1", 9002))
    assert rq.items["pkt1"].retries == 1
    assert rq.items["pkt2"].retries == 1


def test_ack_nonexistent_key_is_safe():
    mock_socket = Mock()
    rq = RetransmitQueue(sock=mock_socket, rto_ms=500, max_retries=10)

    rq.ack("missing-key")

    assert rq.items == {}
    assert rq.heap == []


def test_add_same_key_overwrites_active_item_mapping():
    mock_socket = Mock()

    with patch("server.retransmit_queue.time.time", return_value=100.0):
        rq = RetransmitQueue(sock=mock_socket, rto_ms=500, max_retries=10)
        rq.add("pkt1", b"old", ("127.0.0.1", 9000))

    with patch("server.retransmit_queue.time.time", return_value=101.0):
        rq.add("pkt1", b"new", ("127.0.0.1", 9001))

    assert rq.items["pkt1"].payload == b"new"
    assert rq.items["pkt1"].addr == ("127.0.0.1", 9001)
    assert rq.items["pkt1"].deadline == 101.5