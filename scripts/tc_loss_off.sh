#!/bin/bash
# Disable packet loss simulation
# Usage: sudo ./scripts/tc_loss_off.sh [interface]

INTERFACE=${1:-lo}  # Default loopback interface

echo "================================================"
echo "  Disabling Packet Loss Simulation"
echo "================================================"
echo "Interface: $INTERFACE"
echo "================================================"

# Check if running with sudo
if [ "$EUID" -ne 0 ]; then 
    echo "ERROR: Please run with sudo"
    echo "Usage: sudo ./scripts/tc_loss_off.sh [interface]"
    exit 1
fi

# Remove all tc rules
tc qdisc del dev $INTERFACE root 2>/dev/null

if [ $? -eq 0 ]; then
    echo "✓ Packet loss disabled successfully"
else
    echo "✓ No tc rules to remove (already clean)"
fi

echo ""
echo "Current tc configuration:"
tc qdisc show dev $INTERFACE