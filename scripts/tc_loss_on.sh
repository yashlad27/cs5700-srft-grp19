#!/bin/bash
# Enable packet loss simulation using Linux tc (traffic control)
# Usage: sudo ./scripts/tc_loss_on.sh [loss_percent] [interface]

LOSS_PERCENT=${1:-3}  # Default 3% packet loss
INTERFACE=${2:-lo}     # Default loopback interface

echo "================================================"
echo "  Enabling Packet Loss Simulation"
echo "================================================"
echo "Interface: $INTERFACE"
echo "Loss Rate: ${LOSS_PERCENT}%"
echo "================================================"

# Check if running with sudo
if [ "$EUID" -ne 0 ]; then 
    echo "ERROR: Please run with sudo"
    echo "Usage: sudo ./scripts/tc_loss_on.sh [loss_percent] [interface]"
    exit 1
fi

# Add packet loss using netem
tc qdisc add dev $INTERFACE root netem loss ${LOSS_PERCENT}%

if [ $? -eq 0 ]; then
    echo "✓ Packet loss enabled successfully"
    echo ""
    echo "Current tc configuration:"
    tc qdisc show dev $INTERFACE
else
    echo "✗ Failed to enable packet loss"
    echo "  (Interface may already have tc rules - run tc_loss_off.sh first)"
    exit 1
fi

echo ""
echo "To disable: sudo ./scripts/tc_loss_off.sh"