#!/bin/bash
# Enable packet loss on CLIENT EC2 instance
# Usage: sudo ./scripts/tc_loss_on.sh [loss_percent] [interface]

LOSS=${1:-3}
IFACE=${2:-ens5}

echo "Enabling ${LOSS}% packet loss on $IFACE..."
sudo tc qdisc add dev $IFACE root netem loss ${LOSS}%
echo "Done. Verify with: ping <server_private_ip> -c 20"
