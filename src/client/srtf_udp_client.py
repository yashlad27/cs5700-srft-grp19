# entry point for the client
import argparse
import os
import random
from common.rawsocket import create_send_socket, create_recv_socket
from client.request_handler import send_syn_request, get_local_ip
from client.receiver import receive_file
from common.constants import CLIENT_PORT
from common.stats import TransferStats

def main():
    parser = argparse.ArgumentParser(description="SRFT UDP CLIENT")
    parser.add_argument("server_ip", help="Server IP address")
    parser.add_argument("filename", help="Filename to request from server")
    parser.add_argument("-o", "--output", default=None, help="Output file path")
    args = parser.parse_args()

    server_ip = args.server_ip
    filename = args.filename
    output_path = args.output or os.path.join(".", os.path.basename(filename))

    # Generate unique connection ID
    conn_id = random.randint(1, 65535)

    # determine source IP for IP header construction
    client_ip = get_local_ip(server_ip)

    # create sockets
    send_sock = create_send_socket()
    recv_sock = create_recv_socket(CLIENT_PORT)

    # Initialize stats
    stats = TransferStats()

    try:
        # debug printing
        print(f"Client: client_ip={client_ip}, server_ip={server_ip}")
        print(f"Client: requesting file '{filename}', storing in '{output_path}'")
        print(f"Client: connection_id={conn_id}")

        # Start transfer timing
        stats.start_transfer()

        # handshake
        handshake_status = send_syn_request(send_sock, recv_sock, client_ip, server_ip, filename, conn_id=conn_id)
        if not handshake_status:
            print("Client: Handshake failed: no SYN_ACK received.")
            return 1
        print("Client: handshake success, receiving file...")

        # receive file
        state = receive_file(send_sock, recv_sock, client_ip, server_ip, output_path, stats, conn_id=conn_id)

        # End transfer timing
        stats.end_transfer()

        # print result
        print("\n" + "="*50)
        print("Client: Transfer Complete")
        print("="*50)
        print(f"Packet Stats:")
        print(f"  Total packets received: {state.p_total}")
        print(f"  Valid packets: {state.p_valid}")
        print(f"  Invalid/corrupted: {state.p_invalid}")
        print(f"  Duplicate packets: {state.p_duplicate}")
        print(f"  Chunks written: {state.chunks_written}")
        print(f"  Final sequence: {state.fin_seq}")
        print(f"\nFile saved to: {output_path}")
        
        # Print transfer statistics
        print("\n")
        stats.print_report()

        return 0
    
    finally:
        # Always close sockets
        send_sock.close()
        recv_sock.close()

if __name__ == "__main__":
    raise SystemExit(main())
