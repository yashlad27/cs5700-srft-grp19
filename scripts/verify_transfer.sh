#!/bin/bash
# Verify transferred file matches original
# Usage: ./scripts/verify_transfer.sh <original_file> <transferred_file>

if [ $# -ne 2 ]; then
    echo "Usage: ./scripts/verify_transfer.sh <original_file> <transferred_file>"
    exit 1
fi

ORIGINAL=$1
TRANSFERRED=$2

echo "================================================"
echo "  File Transfer Verification"
echo "================================================"
echo "Original:    $ORIGINAL"
echo "Transferred: $TRANSFERRED"
echo "================================================"

# Check if files exist
if [ ! -f "$ORIGINAL" ]; then
    echo "✗ ERROR: Original file not found: $ORIGINAL"
    exit 1
fi

if [ ! -f "$TRANSFERRED" ]; then
    echo "✗ ERROR: Transferred file not found: $TRANSFERRED"
    exit 1
fi

# Compare file sizes
ORIG_SIZE=$(wc -c < "$ORIGINAL")
TRANS_SIZE=$(wc -c < "$TRANSFERRED")

echo "Original size:    $ORIG_SIZE bytes"
echo "Transferred size: $TRANS_SIZE bytes"

if [ $ORIG_SIZE -ne $TRANS_SIZE ]; then
    echo "✗ FAILED: File sizes don't match"
    exit 1
fi

# Compute checksums
echo ""
echo "Computing checksums..."

if command -v md5sum &> /dev/null; then
    ORIG_MD5=$(md5sum "$ORIGINAL" | awk '{print $1}')
    TRANS_MD5=$(md5sum "$TRANSFERRED" | awk '{print $1}')
elif command -v md5 &> /dev/null; then
    # macOS uses md5 instead of md5sum
    ORIG_MD5=$(md5 -q "$ORIGINAL")
    TRANS_MD5=$(md5 -q "$TRANSFERRED")
else
    echo "WARNING: md5sum/md5 not available, using diff"
    if diff -q "$ORIGINAL" "$TRANSFERRED" > /dev/null; then
        echo "✓ PASSED: Files are identical (diff)"
        exit 0
    else
        echo "✗ FAILED: Files differ"
        exit 1
    fi
fi

echo "Original MD5:    $ORIG_MD5"
echo "Transferred MD5: $TRANS_MD5"
echo ""

if [ "$ORIG_MD5" == "$TRANS_MD5" ]; then
    echo "✓ PASSED: File transfer verified successfully!"
    echo "  Files are identical"
    exit 0
else
    echo "✗ FAILED: Checksums don't match"
    echo "  File may be corrupted"
    exit 1
fi