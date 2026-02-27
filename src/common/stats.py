# Track and Report stats
# Metrics: packets_sent, retransmitted, lost, throughput, transfer_time
# needed in final report

# Track and Report stats
# Metrics: packets_sent, retransmitted, lost, throughput, transfer_time
# needed in final report

import threading
import time


class TransferStats:
    """
    Thread-safe statistics tracker for file transfer metrics
    
    Used by both server and client to track:
    - Packets sent/received
    - Retransmissions
    - Bytes transferred
    - Throughput calculation
    
    Thread-safety: All methods use locks to prevent race conditions
    when send/receive threads update stats concurrently.
    """
    
    def __init__(self):
        """Initialize stats with zero values and create lock"""
        self.lock = threading.Lock()
        
        # Packet counters
        self.packets_sent = 0
        self.packets_received = 0
        self.packets_retransmitted = 0
        self.acks_sent = 0
        self.acks_received = 0
        
        # Byte counters
        self.bytes_sent = 0
        self.bytes_received = 0
        
        # Timing
        self.start_time = None
        self.end_time = None
    
    def record_send(self, packet_size: int):
        """
        Record a packet send event
        
        Args:
            packet_size: Size of packet in bytes (header + payload)
        """
        with self.lock:
            self.packets_sent += 1
            self.bytes_sent += packet_size
    
    def record_receive(self, packet_size: int):
        """
        Record a packet receive event
        
        Args:
            packet_size: Size of packet in bytes (header + payload)
        """
        with self.lock:
            self.packets_received += 1
            self.bytes_received += packet_size
    
    def record_retransmit(self):
        """
        Record a retransmission event
        
        Called when a packet is resent due to timeout or missing ACK
        """
        with self.lock:
            self.packets_retransmitted += 1
    
    def record_ack_sent(self):
        """Record an ACK packet sent"""
        with self.lock:
            self.acks_sent += 1
    
    def record_ack_received(self):
        """Record an ACK packet received"""
        with self.lock:
            self.acks_received += 1
    
    def start_transfer(self):
        """
        Mark the start of file transfer
        
        Records current timestamp for duration calculation
        """
        with self.lock:
            self.start_time = time.time()
    
    def end_transfer(self):
        """
        Mark the end of file transfer
        
        Records current timestamp for duration calculation
        """
        with self.lock:
            self.end_time = time.time()
    
    def get_duration(self) -> float:
        """
        Calculate transfer duration in seconds
        
        Returns:
            Duration in seconds, or 0 if transfer hasn't started/ended
        """
        with self.lock:
            if self.start_time is None or self.end_time is None:
                return 0.0
            return self.end_time - self.start_time
    
    def get_throughput(self) -> float:
        """
        Calculate throughput in Mbps (megabits per second)
        
        Formula: (bytes_received * 8) / (duration * 1,000,000)
        
        Returns:
            Throughput in Mbps, or 0 if duration is 0
        """
        duration = self.get_duration()
        
        if duration == 0:
            return 0.0
        
        with self.lock:
            # Convert bytes to bits (* 8)
            # Convert to megabits (/ 1,000,000)
            bits_received = self.bytes_received * 8
            throughput_mbps = bits_received / (duration * 1_000_000)
            return throughput_mbps
    
    def get_retransmit_rate(self) -> float:
        """
        Calculate retransmission rate as percentage
        
        Formula: (packets_retransmitted / packets_sent) * 100
        
        Returns:
            Percentage of packets that were retransmitted (0-100)
        """
        with self.lock:
            if self.packets_sent == 0:
                return 0.0
            return (self.packets_retransmitted / self.packets_sent) * 100
    
    def get_report(self) -> dict:
        """
        Generate complete statistics report
        
        Returns:
            Dictionary with all metrics:
            {
                'packets_sent': int,
                'packets_received': int,
                'packets_retransmitted': int,
                'acks_sent': int,
                'acks_received': int,
                'bytes_sent': int,
                'bytes_received': int,
                'duration_seconds': float,
                'throughput_mbps': float,
                'retransmit_rate_percent': float
            }
        """
        with self.lock:
            # Calculate duration
            duration = 0.0
            if self.start_time is not None and self.end_time is not None:
                duration = self.end_time - self.start_time
            
            # Calculate throughput
            throughput = 0.0
            if duration > 0:
                bits_received = self.bytes_received * 8
                throughput = bits_received / (duration * 1_000_000)
            
            # Calculate retransmit rate
            retransmit_rate = 0.0
            if self.packets_sent > 0:
                retransmit_rate = (self.packets_retransmitted / self.packets_sent) * 100
            
            return {
                'packets_sent': self.packets_sent,
                'packets_received': self.packets_received,
                'packets_retransmitted': self.packets_retransmitted,
                'acks_sent': self.acks_sent,
                'acks_received': self.acks_received,
                'bytes_sent': self.bytes_sent,
                'bytes_received': self.bytes_received,
                'duration_seconds': duration,
                'throughput_mbps': throughput,
                'retransmit_rate_percent': retransmit_rate
            }
    
    def print_report(self):
        """
        Print formatted statistics report to console
        
        Example output:
        ===== Transfer Statistics =====
        Packets Sent: 150
        Packets Received: 145
        Packets Retransmitted: 5 (3.33%)
        ACKs Sent: 50
        ACKs Received: 48
        Bytes Sent: 210000
        Bytes Received: 203000
        Duration: 2.45 seconds
        Throughput: 0.66 Mbps
        ===============================
        """
        report = self.get_report()
        
        print("=" * 40)
        print("Transfer Statistics".center(40))
        print("=" * 40)
        print(f"Packets Sent:         {report['packets_sent']}")
        print(f"Packets Received:     {report['packets_received']}")
        print(f"Packets Retransmitted: {report['packets_retransmitted']} "
              f"({report['retransmit_rate_percent']:.2f}%)")
        print(f"ACKs Sent:            {report['acks_sent']}")
        print(f"ACKs Received:        {report['acks_received']}")
        print(f"Bytes Sent:           {report['bytes_sent']}")
        print(f"Bytes Received:       {report['bytes_received']}")
        print(f"Duration:             {report['duration_seconds']:.2f} seconds")
        print(f"Throughput:           {report['throughput_mbps']:.2f} Mbps")
        print("=" * 40)