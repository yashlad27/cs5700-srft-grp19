"""
UNIT TESTS FOR client_state.py
"""

import io
import pytest

from client.client_state import ClientState
from common.constants import MAX_PAYLOAD_SIZE


class TestStoreChunk:
    def test_store_valid_chunk(self):
        """Valid chunk should be stored in buffer"""
        state = ClientState()

        state.store_chunk(0, b"hello")

        assert 0 in state.buffer
        assert state.buffer[0] == b"hello"
        assert state.p_duplicate == 0

    def test_drop_payload_too_large(self):
        """Payload larger than MAX_PAYLOAD_SIZE should be dropped"""
        state = ClientState()
        payload = b"a" * (MAX_PAYLOAD_SIZE + 1)

        state.store_chunk(0, payload)

        assert 0 not in state.buffer
        assert len(state.buffer) == 0

    def test_allow_max_payload_size(self):
        """Payload exactly MAX_PAYLOAD_SIZE should be stored"""
        state = ClientState()
        payload = b"a" * MAX_PAYLOAD_SIZE

        state.store_chunk(0, payload)

        assert 0 in state.buffer
        assert state.buffer[0] == payload

    def test_drop_sequence_too_large(self):
        """Sequence number above safety bound should be dropped"""
        state = ClientState()

        state.store_chunk(1_000_001, b"hello")

        assert 1_000_001 not in state.buffer
        assert len(state.buffer) == 0

    def test_allow_sequence_at_upper_bound(self):
        """Sequence number at safety bound should still be stored"""
        state = ClientState()

        state.store_chunk(1_000_000, b"hello")

        assert 1_000_000 in state.buffer
        assert state.buffer[1_000_000] == b"hello"

    def test_drop_duplicate_already_written(self):
        """Chunk with seq < expected_seq should be treated as duplicate"""
        state = ClientState(expected_seq=3)

        state.store_chunk(1, b"old")

        assert 1 not in state.buffer
        assert state.p_duplicate == 1

    def test_drop_duplicate_already_buffered(self):
        """Chunk already in buffer should be treated as duplicate"""
        state = ClientState()
        state.buffer[2] = b"data"

        state.store_chunk(2, b"new_data")

        assert state.buffer[2] == b"data"
        assert state.p_duplicate == 1

    def test_store_out_of_order_chunk(self):
        """Out-of-order chunk should still be stored in buffer"""
        state = ClientState(expected_seq=0)

        state.store_chunk(2, b"C")

        assert 2 in state.buffer
        assert state.buffer[2] == b"C"
        assert state.expected_seq == 0

    def test_empty_payload_is_allowed(self):
        """Empty payload should still be stored if seq is valid"""
        state = ClientState()

        state.store_chunk(0, b"")

        assert 0 in state.buffer
        assert state.buffer[0] == b""


class TestWriteChunk:
    def test_write_single_chunk(self):
        """Single in-order chunk should be written"""
        state = ClientState()
        fake_file = io.BytesIO()

        state.store_chunk(0, b"A")
        state.write_chunk(fake_file)

        assert fake_file.getvalue() == b"A"
        assert state.expected_seq == 1
        assert state.chunks_written == 1
        assert state.buffer == {}

    def test_write_multiple_contiguous_chunks(self):
        """Multiple contiguous chunks should all be written"""
        state = ClientState()
        fake_file = io.BytesIO()

        state.store_chunk(0, b"A")
        state.store_chunk(1, b"B")
        state.store_chunk(2, b"C")

        state.write_chunk(fake_file)

        assert fake_file.getvalue() == b"ABC"
        assert state.expected_seq == 3
        assert state.chunks_written == 3
        assert state.buffer == {}

    def test_stop_writing_at_gap(self):
        """Writing should stop when a missing chunk is encountered"""
        state = ClientState()
        fake_file = io.BytesIO()

        state.store_chunk(0, b"A")
        state.store_chunk(2, b"C")

        state.write_chunk(fake_file)

        assert fake_file.getvalue() == b"A"
        assert state.expected_seq == 1
        assert state.chunks_written == 1
        assert state.buffer == {2: b"C"}

    def test_out_of_order_then_gap_filled(self):
        """Buffered out-of-order chunks should write once gap is filled"""
        state = ClientState()
        fake_file = io.BytesIO()

        state.store_chunk(2, b"C")
        state.store_chunk(0, b"A")
        state.write_chunk(fake_file)

        assert fake_file.getvalue() == b"A"
        assert state.expected_seq == 1
        assert state.buffer == {2: b"C"}

        state.store_chunk(1, b"B")
        state.write_chunk(fake_file)

        assert fake_file.getvalue() == b"ABC"
        assert state.expected_seq == 3
        assert state.chunks_written == 3
        assert state.buffer == {}

    def test_write_nothing_when_expected_not_present(self):
        """Nothing should be written if expected_seq is missing"""
        state = ClientState()
        fake_file = io.BytesIO()

        state.store_chunk(3, b"D")
        state.write_chunk(fake_file)

        assert fake_file.getvalue() == b""
        assert state.expected_seq == 0
        assert state.chunks_written == 0
        assert state.buffer == {3: b"D"}

    def test_write_empty_payload_chunk(self):
        """Empty payload chunk should still advance expected_seq"""
        state = ClientState()
        fake_file = io.BytesIO()

        state.store_chunk(0, b"")
        state.write_chunk(fake_file)

        assert fake_file.getvalue() == b""
        assert state.expected_seq == 1
        assert state.chunks_written == 1
        assert state.buffer == {}


class TestClientStateFields:
    def test_initial_state(self):
        """ClientState should initialize with correct defaults"""
        state = ClientState()

        assert state.expected_seq == 0
        assert state.buffer == {}
        assert state.fin_seq is None
        assert state.p_total == 0
        assert state.p_valid == 0
        assert state.p_invalid == 0
        assert state.p_duplicate == 0
        assert state.chunks_written == 0

    def test_fin_seq_can_be_set(self):
        """fin_seq should be assignable"""
        state = ClientState()

        state.fin_seq = 5

        assert state.fin_seq == 5


class TestEdgeCases:
    """Test boundary and unusual cases"""

    @pytest.mark.parametrize(
        "seq,payload,should_store",
        [
            (0, b"A", True),
            (10, b"data", True),
            (1_000_000, b"maxseq", True),
            (1_000_001, b"toolarge", False),
        ],
    )
    def test_sequence_boundaries(self, seq, payload, should_store):
        """Test sequence boundary conditions"""
        state = ClientState()

        state.store_chunk(seq, payload)

        if should_store:
            assert seq in state.buffer
        else:
            assert seq not in state.buffer

    @pytest.mark.parametrize(
        "payload_len,should_store",
        [
            (0, True),
            (1, True),
            (100, True),
            (MAX_PAYLOAD_SIZE, True),
            (MAX_PAYLOAD_SIZE + 1, False),
        ],
    )
    def test_payload_size_boundaries(self, payload_len, should_store):
        """Test payload size boundary conditions"""
        state = ClientState()
        payload = b"x" * payload_len

        state.store_chunk(0, payload)

        if should_store:
            assert 0 in state.buffer
        else:
            assert 0 not in state.buffer