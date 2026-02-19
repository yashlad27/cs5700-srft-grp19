#Sliding window management for UNACKed packets
# Track which packets are in-flight, handle ACKs, slide window forward
# Window size: 10 (pulling from constants.py)