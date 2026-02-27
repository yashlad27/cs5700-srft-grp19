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



PHASE - 2 : MAKE IT SECURE

problems in security / unencrypted file transfer for udp: CIA violation

to do:
1. encrypt pages => confidentiality
2. add authentication tags => integrity
3. provide identity => authentication
4. reject duplicate pages => replay protection
5. verify hash =? SHA 256

essentially => MINI TLS
