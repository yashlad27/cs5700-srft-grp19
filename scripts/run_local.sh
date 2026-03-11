#!/bin/bash
# Run local file transfer test (server + client on localhost)
# Usage: sudo ./scripts/run_local.sh [test_file]

TEST_FILE=${1:-test_files/test_1kb.bin}
SERVER_PORT=9000
OUTPUT_DIR="received_files"
OUTPUT_FILE="$OUTPUT_DIR/$(basename $TEST_FILE)"

echo "================================================"
echo "  SRFT Local File Transfer Test"
echo "================================================"
echo "Test file: $TEST_FILE"
echo "Server port: $SERVER_PORT"
echo "Output: $OUTPUT_FILE"
echo "================================================"

# No sudo required for UDP sockets
# (keeping check commented for reference)
# if [ "$EUID" -ne 0 ]; then 
#     echo "ERROR: Please run with sudo (raw sockets require root)"
#     exit 1
# fi

# Check if test file exists
if [ ! -f "$TEST_FILE" ]; then
    echo "ERROR: Test file not found: $TEST_FILE"
    echo "Generate one with: ./scripts/generate_test_file.sh 1K test_1kb.bin"
    exit 1
fi

# Create output directory
mkdir -p $OUTPUT_DIR

# Cleanup handler
cleanup() {
    echo ""
    echo "Stopping server (PID: $SERVER_PID)..."
    kill $SERVER_PID 2>/dev/null
    wait $SERVER_PID 2>/dev/null
    echo "Server stopped"
}
trap cleanup EXIT

echo "Starting server in background..."
PYTHONPATH=src python3 -m server.srtf_udp_server --host 127.0.0.1 --port $SERVER_PORT --out test_files --chunk 1200 > server.log 2>&1 &
SERVER_PID=$!
echo "Server PID: $SERVER_PID"

# Wait for server to initialize
sleep 2

echo ""
echo "Starting client..."
PYTHONPATH=src python3 -m client.srtf_udp_client 127.0.0.1 $(basename $TEST_FILE) -o $OUTPUT_FILE

# Wait for transfer to complete
sleep 1

echo ""
echo "================================================"
echo "Verifying transfer..."
./scripts/verify_transfer.sh $TEST_FILE $OUTPUT_FILE

echo ""
echo "================================================"
echo "Server log:"
cat server.log
echo "================================================"