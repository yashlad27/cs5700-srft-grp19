#!/bin/bash
# Start SRFT server on EC2
# Usage: sudo ./scripts/start_server.sh [files_dir] [stats_output]

FILES_DIR=${1:-./files}
STATS_OUT=${2:-./server_output.txt}
PORT=9000
CHUNK=1200

echo "================================================"
echo "  SRFT UDP Server"
echo "================================================"
echo "Files directory: $FILES_DIR"
echo "Stats output:    $STATS_OUT"
echo "Port:            $PORT"
echo "================================================"

if [ "$EUID" -ne 0 ]; then
    echo "ERROR: Run with sudo (raw sockets require root)"
    exit 1
fi

if [ ! -d "$FILES_DIR" ]; then
    echo "ERROR: Files directory not found: $FILES_DIR"
    exit 1
fi

PYTHONPATH=src python3 -m server.srtf_udp_server \
    --host 0.0.0.0 \
    --port $PORT \
    --out "$FILES_DIR" \
    --chunk $CHUNK \
    --stats-out "$STATS_OUT"
