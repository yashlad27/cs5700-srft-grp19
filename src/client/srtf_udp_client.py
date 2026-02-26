# entry point for the client
import argparse
import os
from common.rawsocket import create_send_socket, create_recv_socket
from client.request_handler import send_syn_request, get_local_ip
from client.receiver import receive_file
from common.constants import CLIENT_PORT

def main():
    parser = argparse.ArgumentParser(description="SRFT UDP CLIENT")
    parser.add_argument("server_ip", help="Server IP address")
    parser.add_argument("filename", help="Filename to request from server")
    parser.add_argument("-o", "--output", default=None, help="Output file path")
    args = parser.parse_args()

    server_ip = args.server_ip
    filename = args.filename
    output_path = args.output or os.path.join(".", os.path.basename(filename))

    # determine source IP for IP header construction
    client_ip = get_local_ip(server_ip)

    # create sockets
    send_sock = create_send_socket()
    recv_sock = create_recv_socket(CLIENT_PORT)

    # debug printing
    print(f"Client: client_ip={client_ip}, server_ip={server_ip}")
    print(f"Client: requesting file '{filename}', storing in '{output_path}'")

    # handshake
    handshake_status = send_syn_request(send_sock, recv_sock, client_ip, server_ip, filename, conn_id=0)
    if not handshake_status:
        print("Client: Handshake failed: no SYN_ACK received.")
        return 1
    print("Client: handshake success, receiving file...")

    # receive file
    state = receive_file(send_sock, recv_sock, client_ip, server_ip, output_path, conn_id=0)

    # print result
    print("Client: Done")
    print(f"Client: total packets = {state.p_total}, valid packets = {state.p_valid}, invalid packets = {state.p_invalid}, duplicate packets = {state.p_duplicate}")
    print(f"Client: chuncks written = {state.chunks_written}, expected end sequence = {state.expected_seq}, final sequence = {state.fin_seq}")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
