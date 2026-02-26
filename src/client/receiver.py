# receive data + reordering

from common.constants import (
    CLIENT_PORT, SERVER_PORT,
    FLAG_DATA, FLAG_ACK, FLAG_FIN_DATA, FLAG_FIN_ACK
)
from common.packet import encode_packet
from common.rawsocket import send_packet, receive_packet
from client.client_state import ClientState

def receive_file(
        send_sock,
        recv_sock,
        client_ip: str,
        server_ip: str,
        output_path: str,
        conn_id: int = 0,
) -> ClientState:
    '''
    receive DATA/FIN_DATA packets, reorder the packets, write file to disk,
    and send ACKs

    return ClientState with stats and expected_seq
    '''
    state = ClientState()

    with open(output_path, "wb") as fp:
        while True:
            res = receive_packet(recv_sock, expected_port=CLIENT_PORT, timeout=2.0)
            if res is None:
                continue
            packet, sender_ip, sender_port = res
            state.p_total += 1
            # check for corrupted or invalid packet
            if packet is None:
                state.p_invalid += 1
                continue
            state.p_valid += 1
            flags = packet["flags"]
            # find the packets that contain actual data
            if flags & FLAG_DATA:
                seq_num = packet["seq_num"]
                payload = packet["payload"]

                # store the chunk if it is not duplicate
                state.store_chunk(seq_num, payload)

                # if it is the last chunk, remember the seq num
                if (flags & FLAG_FIN_DATA) == FLAG_FIN_DATA:
                    state.fin_seq = seq_num
                
                # write everything up to now
                state.write_chunk(fp)

                # send ACK 
                ack_packet = encode_packet(
                    seq_num=0,
                    ack_num=state.expected_seq,
                    flags=FLAG_ACK,
                    payload=b"", # empty payload
                    conn_id=conn_id
                )
                send_packet(
                    send_sock,
                    ack_packet,
                    src_ip=client_ip,
                    dst_ip=server_ip,
                    src_port=CLIENT_PORT,
                    dst_port=SERVER_PORT
                )

                # check if all chuncks are written, send FIN_ACK
                if state.fin_seq is not None and state.expected_seq == state.fin_seq + 1:
                    fin_ack = encode_packet(
                        seq_num=0,
                        ack_num=state.expected_seq,
                        flags=FLAG_FIN_ACK,
                        payload=b"",
                        conn_id=conn_id
                    )
                    send_packet(
                        send_sock,
                        fin_ack,
                        src_ip=client_ip,
                        dst_ip=server_ip,
                        src_port=CLIENT_PORT,
                        dst_port=SERVER_PORT
                    )
                    break
        return state
                

