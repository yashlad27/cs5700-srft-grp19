#!/bin/bash
# Verify file transfer by comparing MD5 hashes
# Usage: ./scripts/verify_transfer.sh <original_file> <received_file>

if [ -z "$1" ] || [ -z "$2" ]; then
    echo "Usage: ./scripts/verify_transfer.sh <original_file> <received_file>"
    exit 1
fi

ORIGINAL=$1
RECEIVED=$2

if [ ! -f "$ORIGINAL" ]; then
    echo "ERROR: Original file not found: $ORIGINAL"
    exit 1
fi

if [ ! -f "$RECEIVED" ]; then
    echo "ERROR: Received file not found: $RECEIVED"
    exit 1
fi

HASH1=$(md5sum "$ORIGINAL" | awk '{print $1}')
HASH2=$(md5sum "$RECEIVED" | awk '{print $1}')

echo "Original: $HASH1  $ORIGINAL"
echo "Received: $HASH2  $RECEIVED"

if [ "$HASH1" == "$HASH2" ]; then
    echo "✓ PASS: MD5 hashes match — file transfer verified!"
    exit 0
else
    echo "✗ FAIL: MD5 hashes DO NOT match — transfer corrupted!"
    exit 1
fi
