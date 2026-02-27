# state management for client
from dataclasses import dataclass, field
from typing import Dict, Optional, BinaryIO
from common.constants import MAX_PAYLOAD_SIZE

@dataclass
class ClientState:
    '''
    Stores all runtime state for the receiving side
    '''
    expected_seq: int = 0 # index of next chunk
    buffer: Dict[int, bytes] = field(default_factory=dict) # buffer that stores out of order
    fin_seq: Optional[int] = None # seq number of the last chunk

    # Packets stats
    p_total: int = 0
    p_valid: int = 0
    p_invalid: int = 0
    p_duplicate: int = 0
    chunks_written: int = 0

    def store_chunk(self, seq: int, payload: bytes) -> None:
        '''
        store a chunk in the buffer if it is not duplicated
        '''
        # Validate payload size
        if len(payload) > MAX_PAYLOAD_SIZE:
            return  # Invalid payload size, drop packet
        
        # Validate sequence number bounds (prevent memory exhaustion)
        # Allow up to 1 million chunks max (safety check)
        if seq > 1_000_000:
            return  # Invalid sequence number, drop packet
        
        # received duplicated packets (ignore)
        if seq < self.expected_seq: 
            self.p_duplicate += 1
            return
        if seq in self.buffer:
            self.p_duplicate += 1
            return
        
        # if it is not a duplicate, add to buffer
        self.buffer[seq] = payload
    
    def write_chunk(self, fp: BinaryIO) -> None:
        '''
        write chunks in correct order.
        write, remove, and move expected_seq to current one
        '''
        while self.expected_seq in self.buffer:
            fp.write(self.buffer.pop(self.expected_seq))
            self.expected_seq += 1
            self.chunks_written += 1
        