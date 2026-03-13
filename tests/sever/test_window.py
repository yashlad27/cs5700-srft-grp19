import pytest
from server.window_manager import WindowManager


def test_in_window_left_boundary():
    wm = WindowManager(window_size=10, expected_seq=5)
    assert wm.in_window(5) is True


def test_in_window_middle():
    wm = WindowManager(window_size=10, expected_seq=5)
    assert wm.in_window(10) is True


def test_in_window_right_boundary_exclusive():
    wm = WindowManager(window_size=10, expected_seq=5)
    assert wm.in_window(15) is False


def test_in_window_below_expected_seq():
    wm = WindowManager(window_size=10, expected_seq=5)
    assert wm.in_window(4) is False


def test_mark_received_in_order_packet():
    wm = WindowManager(window_size=10, expected_seq=0)

    is_new, trigger = wm.mark_received(0, b"pkt0")

    assert is_new is True
    assert trigger is True
    assert wm.buffer[0] == b"pkt0"
    assert 0 in wm.received


def test_mark_received_out_of_order_but_in_window_packet():
    wm = WindowManager(window_size=10, expected_seq=0)

    is_new, trigger = wm.mark_received(3, b"pkt3")

    assert is_new is True
    assert trigger is False
    assert wm.buffer[3] == b"pkt3"
    assert 3 in wm.received


def test_mark_received_old_packet_returns_false_false():
    wm = WindowManager(window_size=10, expected_seq=5)

    is_new, trigger = wm.mark_received(3, b"old")

    assert is_new is False
    assert trigger is False
    assert 3 not in wm.buffer
    assert 3 not in wm.received


def test_mark_received_duplicate_packet_returns_false_false():
    wm = WindowManager(window_size=10, expected_seq=0)

    first = wm.mark_received(2, b"pkt2")
    second = wm.mark_received(2, b"pkt2-duplicate")

    assert first == (True, False)
    assert second == (False, False)
    assert wm.buffer[2] == b"pkt2"
    assert len(wm.buffer) == 1


def test_mark_received_out_of_window_packet_not_stored():
    wm = WindowManager(window_size=10, expected_seq=0)

    is_new, trigger = wm.mark_received(10, b"pkt10")

    assert is_new is True
    assert trigger is False
    assert 10 not in wm.buffer
    assert 10 not in wm.received


def test_pop_in_order_empty_buffer():
    wm = WindowManager(window_size=10, expected_seq=0)

    result = wm.pop_in_order()

    assert result == []
    assert wm.expected_seq == 0


def test_pop_in_order_single_packet():
    wm = WindowManager(window_size=10, expected_seq=0)
    wm.mark_received(0, b"pkt0")

    result = wm.pop_in_order()

    assert result == [(0, b"pkt0")]
    assert wm.expected_seq == 1
    assert 0 not in wm.buffer


def test_pop_in_order_multiple_contiguous_packets():
    wm = WindowManager(window_size=10, expected_seq=0)
    wm.mark_received(0, b"pkt0")
    wm.mark_received(1, b"pkt1")
    wm.mark_received(2, b"pkt2")

    result = wm.pop_in_order()

    assert result == [
        (0, b"pkt0"),
        (1, b"pkt1"),
        (2, b"pkt2"),
    ]
    assert wm.expected_seq == 3
    assert wm.buffer == {}


def test_pop_in_order_stops_at_gap():
    wm = WindowManager(window_size=10, expected_seq=0)
    wm.mark_received(0, b"pkt0")
    wm.mark_received(2, b"pkt2")
    wm.mark_received(3, b"pkt3")

    result = wm.pop_in_order()

    assert result == [(0, b"pkt0")]
    assert wm.expected_seq == 1
    assert 2 in wm.buffer
    assert 3 in wm.buffer


def test_pop_in_order_after_gap_is_filled():
    wm = WindowManager(window_size=10, expected_seq=0)
    wm.mark_received(0, b"pkt0")
    wm.mark_received(2, b"pkt2")
    wm.mark_received(3, b"pkt3")

    first = wm.pop_in_order()
    assert first == [(0, b"pkt0")]
    assert wm.expected_seq == 1

    wm.mark_received(1, b"pkt1")
    second = wm.pop_in_order()

    assert second == [
        (1, b"pkt1"),
        (2, b"pkt2"),
        (3, b"pkt3"),
    ]
    assert wm.expected_seq == 4
    assert wm.buffer == {}