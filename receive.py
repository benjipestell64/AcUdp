import socket
import struct

# Set up the UDP server
UDP_IP = "0.0.0.0"  # Listen on all available network interfaces
UDP_PORT = 20777  # Match the port used in your sending script

# Create a UDP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))

print(f"Listening for UDP packets on {UDP_IP}:{UDP_PORT}...\n")

while True:
    data, addr = sock.recvfrom(1024)  # Adjust buffer size if necessary
    values = struct.unpack(f"{len(data) // 4}f", data)  # Assuming all values are 32-bit floats

    print(f"Received {len(values)} values from {addr}:")
    print(values)
    print("-" * 80)
