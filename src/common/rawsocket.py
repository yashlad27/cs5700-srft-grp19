# SOCK_RAW socket wrapper - manually build IP + UDP headers
# Functions: create_send_socket(), create_recv_socket(), send_packet(), receive_packet()
# set IP_HDRINCL socket option to disable kernel IP header generation
# filter incoming UDP by port