#!/bin/bash
# Start SRFT client on EC2
# Usage: sudo ./scripts/start_client.sh <server_ip> <filename> [output_file]

if [ -z "$1" ] || [ -z "$2" ]; then
    echo "Usage: sudo ./scripts/start_client.sh <server_ip> <filename> [output_file]"
    echo "Example: sudo ./scripts/start_client.sh 172.31.22.79 test_1kb.bin received_1kb.bin"
    exit 1
fi

SERVER_IP=$1
FILENAME=$2
OUTPUT=${3:-received_$(basename $FILENAME)}

echo "================================================"
echo "  SRFT UDP Client"
echo "================================================"
echo "Server IP: $SERVER_IP"
echo "Filename:  $FILENAME"
echo "Output:    $OUTPUT"
echo "================================================"

if [ "$EUID" -ne 0 ]; then
    echo "ERROR: Run with sudo (raw sockets require root)"
    exit 1
fi

PYTHONPATH=src python3 -m client.srtf_udp_client \
    "$SERVER_IP" \
    "$FILENAME" \
    -o "$OUTPUT"

echo ""
echo "================================================"
echo "  MD5 Verification"
echo "================================================"
md5sum "$OUTPUT"
echo "================================================"
