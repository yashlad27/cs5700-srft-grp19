"""
Unit tests for stats.py
Tests thread-safe statistics tracking
"""

import pytest
import time
import threading
from common.stats import TransferStats


class TestStatsInitialization:
    """Test TransferStats initialization"""
    
    def test_initial_values(self):
        """All counters should start at zero"""
        stats = TransferStats()
        
        assert stats.packets_sent == 0
        assert stats.packets_received == 0
        assert stats.packets_retransmitted == 0
        assert stats.acks_sent == 0
        assert stats.acks_received == 0
        assert stats.bytes_sent == 0
        assert stats.bytes_received == 0
        assert stats.start_time is None
        assert stats.end_time is None


class TestRecordOperations:
    """Test recording stats"""
    
    def test_record_send(self):
        """Record send increments counters"""
        stats = TransferStats()
        
        stats.record_send(100)
        assert stats.packets_sent == 1
        assert stats.bytes_sent == 100
        
        stats.record_send(200)
        assert stats.packets_sent == 2
        assert stats.bytes_sent == 300
    
    def test_record_receive(self):
        """Record receive increments counters"""
        stats = TransferStats()
        
        stats.record_receive(150)
        assert stats.packets_received == 1
        assert stats.bytes_received == 150
        
        stats.record_receive(250)
        assert stats.packets_received == 2
        assert stats.bytes_received == 400
    
    def test_record_retransmit(self):
        """Record retransmit increments counter"""
        stats = TransferStats()
        
        stats.record_retransmit()
        assert stats.packets_retransmitted == 1
        
        stats.record_retransmit()
        stats.record_retransmit()
        assert stats.packets_retransmitted == 3
    
    def test_record_acks(self):
        """Record ACK sent/received"""
        stats = TransferStats()
        
        stats.record_ack_sent()
        stats.record_ack_sent()
        assert stats.acks_sent == 2
        
        stats.record_ack_received()
        assert stats.acks_received == 1


class TestTiming:
    """Test transfer timing"""
    
    def test_start_transfer(self):
        """Start transfer sets start_time"""
        stats = TransferStats()
        
        stats.start_transfer()
        assert stats.start_time is not None
        assert isinstance(stats.start_time, float)
    
    def test_end_transfer(self):
        """End transfer sets end_time"""
        stats = TransferStats()
        
        stats.start_transfer()
        time.sleep(0.1)
        stats.end_transfer()
        
        assert stats.end_time is not None
        assert stats.end_time > stats.start_time
    
    def test_get_duration(self):
        """Calculate duration correctly"""
        stats = TransferStats()
        
        # Before start/end
        assert stats.get_duration() == 0.0
        
        # After start/end
        stats.start_transfer()
        time.sleep(0.1)
        stats.end_transfer()
        
        duration = stats.get_duration()
        assert duration >= 0.1
        assert duration < 0.2  # Should be close to 0.1


class TestCalculations:
    """Test metric calculations"""
    
    def test_throughput_calculation(self):
        """Throughput in Mbps calculated correctly"""
        stats = TransferStats()
        
        stats.start_transfer()
        stats.record_receive(1_000_000)  # 1 MB
        time.sleep(1.0)  # 1 second
        stats.end_transfer()
        
        throughput = stats.get_throughput()
        
        # 1 MB in 1 second = 8 Mbps
        # Allow some tolerance for timing
        assert 7.5 <= throughput <= 8.5
    
    def test_throughput_zero_duration(self):
        """Throughput is 0 if duration is 0"""
        stats = TransferStats()
        assert stats.get_throughput() == 0.0
    
    def test_retransmit_rate(self):
        """Retransmit rate calculated correctly"""
        stats = TransferStats()
        
        # Send 100 packets, retransmit 3
        for _ in range(100):
            stats.record_send(100)
        for _ in range(3):
            stats.record_retransmit()
        
        rate = stats.get_retransmit_rate()
        assert rate == 3.0  # 3%
    
    def test_retransmit_rate_no_sends(self):
        """Retransmit rate is 0 if no packets sent"""
        stats = TransferStats()
        assert stats.get_retransmit_rate() == 0.0


class TestReport:
    """Test report generation"""
    
    def test_get_report(self):
        """Get report returns dict with all fields"""
        stats = TransferStats()
        
        stats.start_transfer()
        stats.record_send(1000)
        stats.record_receive(900)
        stats.record_retransmit()
        stats.record_ack_sent()
        stats.record_ack_received()
        time.sleep(0.1)
        stats.end_transfer()
        
        report = stats.get_report()
        
        # Check all keys exist
        assert 'packets_sent' in report
        assert 'packets_received' in report
        assert 'packets_retransmitted' in report
        assert 'acks_sent' in report
        assert 'acks_received' in report
        assert 'bytes_sent' in report
        assert 'bytes_received' in report
        assert 'duration_seconds' in report
        assert 'throughput_mbps' in report
        assert 'retransmit_rate_percent' in report
        
        # Check values
        assert report['packets_sent'] == 1
        assert report['packets_received'] == 1
        assert report['packets_retransmitted'] == 1
        assert report['bytes_sent'] == 1000
        assert report['bytes_received'] == 900


class TestThreadSafety:
    """Test thread safety with concurrent access"""
    
    def test_concurrent_sends(self):
        """Multiple threads calling record_send"""
        stats = TransferStats()
        num_threads = 10
        operations_per_thread = 100
        
        def send_packets():
            for _ in range(operations_per_thread):
                stats.record_send(100)
        
        threads = [threading.Thread(target=send_packets) for _ in range(num_threads)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Should have exactly num_threads * operations_per_thread
        expected_packets = num_threads * operations_per_thread
        expected_bytes = expected_packets * 100
        
        assert stats.packets_sent == expected_packets
        assert stats.bytes_sent == expected_bytes
    
    def test_concurrent_mixed_operations(self):
        """Multiple threads doing different operations"""
        stats = TransferStats()
        iterations = 100
        
        def sender():
            for _ in range(iterations):
                stats.record_send(100)
        
        def receiver():
            for _ in range(iterations):
                stats.record_receive(90)
        
        def retransmitter():
            for _ in range(iterations // 10):
                stats.record_retransmit()
        
        threads = [
            threading.Thread(target=sender),
            threading.Thread(target=sender),
            threading.Thread(target=receiver),
            threading.Thread(target=retransmitter),
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Verify counts
        assert stats.packets_sent == 200  # 2 sender threads
        assert stats.packets_received == 100  # 1 receiver thread
        assert stats.packets_retransmitted == 10  # 1 retransmit thread
    
    def test_no_race_condition_in_calculations(self):
        """Calculations remain consistent under concurrent updates"""
        stats = TransferStats()
        stats.start_transfer()
        
        def worker():
            for _ in range(50):
                stats.record_send(100)
                stats.record_receive(100)
                # These calculations should not crash
                _ = stats.get_throughput()
                _ = stats.get_retransmit_rate()
        
        threads = [threading.Thread(target=worker) for _ in range(5)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        stats.end_transfer()
        
        # Should complete without errors
        report = stats.get_report()
        assert report['packets_sent'] == 250  # 5 threads * 50
        assert report['packets_received'] == 250