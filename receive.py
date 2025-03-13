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
        ">BBBB"  # 4 bytes: BHeartbeat, NSimRequest, NCueingMode, BEnableBrakeBooster
        + "f" * 56  # 56 floats (REAL values)
        + "h"  # 1 INT (16-bit) for NMSteer
)

expected_size = struct.calcsize(packet_format)

# Float signal names (in order)
float_labels = [
    "gLongDemand", "gLatDemand", "gVertDemand", "dnRollDemand", "dnPitchDemand", "dnYawDemand",
    "vLongCar", "gLongExternalCueing", "gLatExternalCueing", "gVertExternalCueing",
    "dnRollExternalCueing", "dnPitchExternalCueing", "dnYawExternalCueing",
    "vLongExternalCueing", "vLatExternalCueing", "vVertExternalCueing",
    "nRollExternalCueing", "nPitchExternalCueing", "nYawExternalCueing",
    "xLongExternalCueing", "xLatExternalCueing", "xVertExternalCueing",
    "aRollExternalCueing", "aPitchExternalCueing", "aYawExternalCueing",
    "nEngine", "NGear", "rUpshiftCue", "rDownshiftCue", "rEngineCue",
    "aSlipCar", "nSlipCar", "dnSlipCar", "rSideSlipCue",
    "rWashoutLong", "rWashoutLat", "rWashoutVert", "rWashoutRoll", "rWashoutPitch", "rWashoutYaw",
    "fWashoutLong", "fWashoutLat", "fWashoutVert", "fWashoutRoll", "fWashoutPitch", "fWashoutYaw",
    "zetaWashoutLong", "zetaWashoutLat", "zetaWashoutVert", "zetaWashoutRoll", "zetaWashoutPitch", "zetaWashoutYaw",
    "xLongSpeedPreposMin", "xLongSpeedPreposMax", "vCarSpeedPreposMin", "vCarSpeedPreposMax"
]

while True:
    data, addr = sock.recvfrom(1024)

    if len(data) != expected_size:
        print(f"Warning: Received unexpected packet size ({len(data)} bytes). Expected {expected_size} bytes.")
        continue

        # Unpack the data using the corrected format
    unpacked_data = struct.unpack(packet_format, data)

    # Extract the first four values as unsigned/signed 8-bit integers
    BHeartbeat = unpacked_data[0]
    NSimRequest = unpacked_data[1]
    NCueingMode = unpacked_data[2]
    BEnableBrakeBooster = unpacked_data[3]

    # Extract the next 56 values as floats
    float_values = unpacked_data[4:-1]

    # Extract the last value as a 16-bit integer
    NMSteer = unpacked_data[-1]

    print(f"Received packet from {addr}:")
    print(f"  BHeartbeat: {BHeartbeat}")
    print(f"  NSimRequest: {NSimRequest}")
    print(f"  NCueingMode: {NCueingMode}")
    print(f"  BEnableBrakeBooster: {BEnableBrakeBooster}")

    # Print labeled floats
    print("  Float Values:")
    for label, value in zip(float_labels, float_values):
        print(f"    {label}: {value:.6f}")

    print(f"  NMSteer: {NMSteer}")
    print("-" * 80)
