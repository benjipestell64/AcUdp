import socket
import struct

# UDP server setup
UDP_IP = "0.0.0.0"
UDP_PORT = 10000

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))

print(f"Listening for UDP packets on {UDP_IP}:{UDP_PORT}...\n")

# Define the correct packet format:
packet_format = (
        ">"  # Big-endian
        + "f"*6  # 6 FLOAT (32-bit)
)

expected_size = struct.calcsize(packet_format)

# Signal names (in order)
labels = [
    "xLongWorld",
    "xLatWorld",
    "xVertWorld",
    "aRollWorld",
    "aPitchWorld",
    "aYawWorld"
]

while True:
    data, addr = sock.recvfrom(1024)

    if len(data) != expected_size:
        # print(f"Warning: Received unexpected packet size ({len(data)} bytes). Expected {expected_size} bytes.")
        continue

    # Unpack the data using the corrected format
    unpacked_data = struct.unpack(packet_format, data)

    values = unpacked_data

    print(f"Received packet from {addr}:")

    # Print labeled floats
    print("  Values:")
    for label, value in zip(labels, values):
        print(f"    {label}: {value:.6f}")
