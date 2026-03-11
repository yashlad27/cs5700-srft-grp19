#!/bin/bash
# Generate test files of various sizes
# Usage: ./scripts/generate_test_file.sh [size] [filename]

SIZE=${1:-1M}
FILENAME=${2:-test_file.bin}
OUTPUT_DIR="test_files"

echo "================================================"
echo "  Generating Test File"
echo "================================================"
echo "Size: $SIZE"
echo "Filename: $FILENAME"
echo "================================================"

# Create output directory if it doesn't exist
mkdir -p $OUTPUT_DIR

# Generate random file
if command -v dd &> /dev/null; then
    case $SIZE in
        1K|1k)
            dd if=/dev/urandom of=$OUTPUT_DIR/$FILENAME bs=1024 count=1 2>/dev/null
            ;;
        10K|10k)
            dd if=/dev/urandom of=$OUTPUT_DIR/$FILENAME bs=1024 count=10 2>/dev/null
            ;;
        100K|100k)
            dd if=/dev/urandom of=$OUTPUT_DIR/$FILENAME bs=1024 count=100 2>/dev/null
            ;;
        1M|1m)
            dd if=/dev/urandom of=$OUTPUT_DIR/$FILENAME bs=1048576 count=1 2>/dev/null
            ;;
        10M|10m)
            dd if=/dev/urandom of=$OUTPUT_DIR/$FILENAME bs=1048576 count=10 2>/dev/null
            ;;
        100M|100m)
            dd if=/dev/urandom of=$OUTPUT_DIR/$FILENAME bs=1048576 count=100 2>/dev/null
            ;;
        *)
            echo "ERROR: Unknown size '$SIZE'"
            echo "Supported: 1K, 10K, 100K, 1M, 10M, 100M"
            exit 1
            ;;
    esac
    
    echo "✓ File generated: $OUTPUT_DIR/$FILENAME"
    ls -lh $OUTPUT_DIR/$FILENAME
else
    echo "ERROR: dd command not found"
    exit 1
fi