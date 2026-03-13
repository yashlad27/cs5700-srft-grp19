#!/bin/bash
# Disable packet loss on CLIENT EC2 instance
# Usage: sudo ./scripts/tc_loss_off.sh [interface]

IFACE=${1:-ens5}

echo "Removing packet loss from $IFACE..."
sudo tc qdisc del dev $IFACE root 2>/dev/null
echo "Done. Packet loss removed."
