Secure File transfer over UDP 

Adding guarantee delivery for UDP + Reliability and also adding encryption for it

File  
  ↓  
Our Protocol (Reliability + Security)  
  ↓  
UDP  
  ↓  
IP  
  ↓  
Network  

PHASE - 1 : MAKE UDP RELIABLE
need to tackle problems of udp like:
1. pages get lost
2. pages arrive out of order
3. pages are duplicated
4. pages might be corrupted

to do:
1. number each page (sequence numbers)
2. confirm how many pages arrived (acks)
3. resend missing pages (retransmission)
4. check if pages are damaged (checksum)

'!BBHHHBBH4s4s'
 │ │││││││└─ 4-byte string (destination IP)
 │ ││││││└── 4-byte string (source IP)
 │ │││││└─── 1 byte (header checksum - high byte)
 │ ││││└──── 1 byte (header checksum - low byte)
 │ │││└───── 1 byte (protocol = 17 for UDP)
 │ ││└────── 1 byte (TTL)
 │ │└─────── 2 bytes (flags + fragment offset)
 │ └──────── 2 bytes (identification)
 └────────── 2 bytes (total length)

Total size: 1+1+2+2+2+1+1+2+4+4 = 20 bytes (IP header)

essentially => MINI TCP

LOCAL TESTING WORKFLOW:

TEST-1: Basic File Transfer (no loss)
# Terminal 1 - Server
sudo python3 -m src.server.srtf_udp_server --port 5005 --directory ./files/

# Terminal 2 - Client
sudo python3 -m src.client.srtf_udp_client 127.0.0.1 test_1MB.bin -o received.bin

# Verify
diff files/test_1MB.bin received.bin

TEST-2: Basic File Transfer (with 3% PC loss)
# Enable packet loss
sudo ./scripts/tc_loss_on.sh

# Run transfer (same as above)

# Verify retransmissions occurred
# Check stats show >0 retransmitted packets

# Disable packet loss
sudo ./scripts/tc_loss_off.sh


PHASE - 2 : MAKE IT SECURE

problems in security / unencrypted file transfer for udp: CIA violation

to do:
1. encrypt pages => confidentiality
2. add authentication tags => integrity
3. provide identity => authentication
4. reject duplicate pages => replay protection
5. verify hash =? SHA 256

essentially => MINI TLS

