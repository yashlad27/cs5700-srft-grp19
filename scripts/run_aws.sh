#!/bin/bash
# Deploy and run tests on AWS EC2 instances
# Usage: ./scripts/run_aws.sh <server_ip> <key_file>

if [ $# -ne 2 ]; then
    echo "Usage: ./scripts/run_aws.sh <server_ip> <key_file>"
    echo "Example: ./scripts/run_aws.sh 54.123.45.67 ~/.ssh/aws-key.pem"
    exit 1
fi

SERVER_IP=$1
KEY_FILE=$2
PROJECT_DIR=$(pwd)
REMOTE_DIR="/home/ubuntu/srft"

echo "================================================"
echo "  AWS Deployment and Testing"
echo "================================================"
echo "Server IP: $SERVER_IP"
echo "Key file:  $KEY_FILE"
echo "================================================"

# Check key file exists
if [ ! -f "$KEY_FILE" ]; then
    echo "ERROR: Key file not found: $KEY_FILE"
    exit 1
fi

echo ""
echo "Step 1: Copying project to server..."
rsync -avz --progress -e "ssh -i $KEY_FILE" \
    --exclude '.git' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.pytest_cache' \
    $PROJECT_DIR/ ubuntu@$SERVER_IP:$REMOTE_DIR/

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to copy files to server"
    exit 1
fi

echo ""
echo "Step 2: Installing dependencies on server..."
ssh -i $KEY_FILE ubuntu@$SERVER_IP << 'EOF'
cd ~/srft
sudo apt-get update
sudo apt-get install -y python3-pip
pip3 install -r requirements.txt
EOF

echo ""
echo "Step 3: Generating test file on server..."
ssh -i $KEY_FILE ubuntu@$SERVER_IP << 'EOF'
cd ~/srft
chmod +x scripts/*.sh
./scripts/generate_test_file.sh 1M test_1M.bin
EOF

echo ""
echo "Step 4: Starting server..."
ssh -i $KEY_FILE ubuntu@$SERVER_IP << 'EOF'
cd ~/srft
sudo python3 -m src.server.srtf_udp_server --port 5005 --directory test_files/ &
echo "Server started"
EOF

echo ""
echo "================================================"
echo "Server is running on $SERVER_IP:5005"
echo "================================================"
echo ""
echo "To test from local machine:"
echo "  sudo python3 -m src.client.srtf_udp_client $SERVER_IP test_1M.bin -o received.bin"
echo ""
echo "To stop server:"
echo "  ssh -i $KEY_FILE ubuntu@$SERVER_IP 'sudo pkill -f srtf_udp_server'"