#!/bin/bash
# Generate test files for SRFT transfer testing
# Usage: ./scripts/generate_test_file.sh [files_dir]

FILES_DIR=${1:-./files}
mkdir -p "$FILES_DIR"

echo "Generating test files in $FILES_DIR..."

dd if=/dev/urandom of="$FILES_DIR/test_1kb.bin" bs=1024 count=1 2>/dev/null
dd if=/dev/urandom of="$FILES_DIR/test_10kb.bin" bs=1024 count=10 2>/dev/null
dd if=/dev/urandom of="$FILES_DIR/test_100kb.bin" bs=1024 count=100 2>/dev/null
dd if=/dev/urandom of="$FILES_DIR/test_1mb.bin" bs=1024 count=1024 2>/dev/null

echo ""
echo "Files created:"
ls -lh "$FILES_DIR"/test_*.bin

echo ""
echo "MD5 checksums:"
md5sum "$FILES_DIR"/test_*.bin
