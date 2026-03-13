# Raw Socket Implementation - March 11, 2026

## Overview

This document details the implementation of raw sockets (SOCK_RAW) with manual IP and UDP header construction for the SRFT protocol, as required by the project specification.

## Architecture Changes

### Socket Architecture

**Before:**
- Server: Regular UDP socket (`SOCK_DGRAM`)
- Client: Regular UDP socket (`SOCK_DGRAM`)
- Kernel handled all IP/UDP headers

**After:**
- Server: Dual raw sockets
  - Receive socket: `SOCK_RAW` with `IPPROTO_UDP` for receiving packets
  - Send socket: `SOCK_RAW` with `IPPROTO_RAW` for sending packets with custom headers
- Client: Dual raw sockets (same architecture)
- Manual IP and UDP header construction for all packets

### Raw Socket Implementation (`src/common/rawsocket.py`)

#### Key Functions:

1. **`create_send_socket()`**
   - Creates `SOCK_RAW` socket with `IPPROTO_RAW`
   - Sets `IP_HDRINCL` option to provide custom IP headers
   - Requires `sudo` privileges (CAP_NET_RAW)

2. **`create_recv_socket(port)`**
   - Creates `SOCK_RAW` socket with `IPPROTO_UDP`
   - Binds to specified port
   - Receives all UDP packets, filters by destination port

3. **`send_packet(sock, packet_bytes, src_ip, dst_ip, src_port, dst_port)`**
   - Builds IP header (20 bytes)
   - Builds UDP header (8 bytes)
   - Constructs: `[IP header][UDP header][Custom packet]`
   - Sends via raw socket to destination

4. **`receive_packet(sock, expected_port, timeout)`**
   - Receives raw packet
   - Parses IP header to extract IHL (IP header length)
   - Parses UDP header to extract ports
   - Filters by destination port
   - Returns `(packet_dict, sender_ip, src_port)`

#### IP Header Structure (20 bytes):
```
Version (4 bits) + IHL (4 bits)
Type of Service (8 bits)
Total Length (16 bits)
Identification (16 bits)
Flags (3 bits) + Fragment Offset (13 bits)
TTL (8 bits)
Protocol (8 bits) = 17 (UDP)
Header Checksum (16 bits)
Source IP (32 bits)
Destination IP (32 bits)
```

#### UDP Header Structure (8 bytes):
```
Source Port (16 bits)
Destination Port (16 bits)
Length (16 bits)
Checksum (16 bits) = 0 (disabled)
```

## Server Changes (`src/server/srtf_udp_server.py`)

### Socket Creation:
```python
recv_sock = create_recv_socket(cfg.listen_port)  # Receive raw packets
recv_sock.setblocking(False)
send_sock = create_send_socket()                  # Send raw packets
```

### Packet Reception:
```python
result = receive_packet(recv_sock, cfg.listen_port, timeout=0)
if result is None:
    continue
packet_dict, sender_ip, src_port = result
addr = (sender_ip, src_port)
res = receiver.handle_decoded_packet(packet_dict, addr)
```

### Server Receiver (`src/server/receiver.py`)

Added `handle_decoded_packet()` method:
- Accepts pre-parsed packet dictionary from `receive_packet()`
- Dispatches by packet type (SYN, ACK, DATA, FIN)
- No longer needs to decode raw bytes

### Server Sender (`src/server/sender.py`)

Updated all send methods to use `send_packet()`:
- `send_syn_ack()` - Uses raw socket wrapper
- `send_ack()` - Uses raw socket wrapper
- `send_data_chunk()` - Uses raw socket wrapper

Added `_get_local_ip()` to determine server's IP address for packet construction.

## Client Architecture

Client already used raw sockets in initial implementation, no major changes needed.

## Packet Decoder Enhancement (`src/common/packet.py`)

### Added Type Field

`decode_packet()` now returns packet type string based on flags:

```python
if flags == FLAG_SYN:
    pkt_type = "SYN"
elif flags == FLAG_SYN_ACK:
    pkt_type = "SYN_ACK"
elif flags == FLAG_ACK:
    pkt_type = "ACK"
elif flags == FLAG_DATA:
    pkt_type = "DATA"
elif flags == FLAG_FIN:
    pkt_type = "FIN"
elif flags == FLAG_FIN_DATA:
    pkt_type = "FIN_DATA"
elif flags == FLAG_FIN_ACK:
    pkt_type = "FIN_ACK"
```

Returns dictionary with:
- `'type'`: Packet type string
- `'seq'`, `'seq_num'`: Sequence number
- `'ack'`, `'ack_num'`: Acknowledgment number
- `'flags'`: Raw flag byte
- `'conn_id'`: Connection ID
- `'payload'`: Payload bytes

## Port Configuration (`src/common/constants.py`)

Updated ports to match AWS EC2 deployment:
```python
SERVER_PORT = 9000  # Changed from 5005
CLIENT_PORT = 9001  # Changed from 5006
```

## AWS EC2 Deployment

### Instance Configuration:
- **AMI**: Ubuntu 24.04 LTS (`ubuntu-noble-24.04-amd64-server-20251212`)
- **Server Instance**: 
  - Public IP: `98.81.117.19`
  - Private IP: `172.31.22.79`
- **Client Instance**:
  - Public IP: `107.20.72.238`
  - Private IP: `172.31.17.63`

### Security Group Rules:
```
1. SSH (TCP port 22): 0.0.0.0/0
2. ICMP (All ICMP - IPv4): 172.31.0.0/16
3. UDP port 9000: 0.0.0.0/0
4. All traffic: 172.31.0.0/16 (for raw sockets)
```

### Network Interface:
- AWS uses `ens5` (not `eth0`)
- Private IPs used for VPC communication
- Public IPs for SSH access

## Testing Results

### Test 1: 1KB File Transfer
```
Server: test_files/test_1kb.bin (1024 bytes)
Client: received.bin (1024 bytes)

MD5 Checksum Verification:
Server: 6a5e9d3eb58b178204909825ef1b74a2
Client: 6a5e9d3eb58b178204909825ef1b74a2
✅ FILES IDENTICAL

Transfer Statistics:
- Duration: 0.30 seconds
- Throughput: 0.03 Mbps
- Packets Sent: 4
- Packets Received: 1
- Chunks: 1
- Retransmissions: 0
```

### Packet Flow:
```
1. Client → Server: SYN (filename: "test_1kb.bin")
2. Server → Client: SYN_ACK
3. Server → Client: DATA (seq=0, 1024 bytes, FIN_DATA flag)
4. Client → Server: ACK
5. Client → Server: FIN_ACK
```

## Bugs Fixed

### Bug 1: Server Using Regular UDP Socket
**Problem**: Server used `SOCK_DGRAM` while client sent raw IP packets
**Solution**: Changed server to use dual raw sockets (recv + send)

### Bug 2: Port Mismatch
**Problem**: Client sent to port 5005, server listened on 9000
**Solution**: Updated `constants.py` to use ports 9000/9001

### Bug 3: Missing 'type' Field in decode_packet()
**Problem**: `decode_packet()` returned flags but not packet type string
**Solution**: Added type interpretation logic to decode flags into type strings

### Bug 4: Server Using sendto() on Raw Socket
**Problem**: Server used `sendto()` directly instead of building headers
**Solution**: Updated all server send methods to use `send_packet()` wrapper

### Bug 5: Receiver Expected Raw Bytes
**Problem**: Receiver tried to decode already-decoded packets
**Solution**: Added `handle_decoded_packet()` for pre-parsed packets

## Verification Commands

### Upload Code to EC2:
```bash
# Server
scp -i ~/Downloads/srtf-key.pem src/server/*.py ubuntu@98.81.117.19:~/src/server/
scp -i ~/Downloads/srtf-key.pem src/common/*.py ubuntu@98.81.117.19:~/src/common/

# Client
scp -i ~/Downloads/srtf-key.pem src/common/*.py ubuntu@107.20.72.238:~/src/common/
```

### Run Server:
```bash
ssh -i ~/Downloads/srtf-key.pem ubuntu@98.81.117.19
sudo PYTHONPATH=src python3 -m server.srtf_udp_server --host 0.0.0.0 --port 9000 --out test_files
```

### Run Client:
```bash
ssh -i ~/Downloads/srtf-key.pem ubuntu@107.20.72.238
sudo PYTHONPATH=src python3 -m client.srtf_udp_client 172.31.22.79 test_1kb.bin -o received.bin
```

### Verify File Integrity:
```bash
# Server
md5sum test_files/test_1kb.bin

# Client
md5sum received.bin
```

## Key Requirements Met

✅ **Raw Sockets**: Using `SOCK_RAW` with `IPPROTO_RAW` and `IPPROTO_UDP`
✅ **Manual IP Headers**: Built with `struct.pack()` including version, TTL, protocol, addresses
✅ **Manual UDP Headers**: Built with source/dest ports, length, checksum
✅ **IP_HDRINCL Option**: Set on send socket to prevent kernel header generation
✅ **Sudo Required**: Raw sockets require CAP_NET_RAW capability
✅ **Linux Testing**: Verified on AWS EC2 Ubuntu 24.04 instances
✅ **Correct Delivery**: MD5 checksums match perfectly

## Performance Characteristics

- **Overhead**: IP (20B) + UDP (8B) + Custom Header (15B) = 43 bytes per packet
- **Maximum Payload**: 1400 bytes (safe within 1500 MTU)
- **Socket Type**: Non-blocking receive socket with select() for timeout handling
- **Port Filtering**: Raw socket receives all UDP, filters by destination port in software

## Security Considerations

1. **Requires Root**: Raw socket creation needs `sudo` or CAP_NET_RAW
2. **No Kernel Filtering**: Application must validate all received packets
3. **Manual Checksum**: IP checksum calculated manually, UDP checksum disabled (0)
4. **Security Group**: AWS security group acts as firewall for EC2 instances

## Future Enhancements

- Test with larger files (10KB, 100KB, 1MB)
- Test with network packet loss (tc netem)
- Measure retransmission behavior
- Performance profiling with congestion control
- IPv6 support (currently IPv4 only)
- UDP checksum validation (currently disabled)

## References

- **Raw Socket Programming**: [Linux man pages - raw(7)](https://man7.org/linux/man-pages/man7/raw.7.html)
- **IP Header Format**: [RFC 791 - Internet Protocol](https://www.rfc-editor.org/rfc/rfc791)
- **UDP Header Format**: [RFC 768 - User Datagram Protocol](https://www.rfc-editor.org/rfc/rfc768)
- **Python Socket Module**: [socket — Low-level networking interface](https://docs.python.org/3/library/socket.html)

---

**Last Updated**: March 11, 2026
**Status**: ✅ Fully Implemented and Verified
