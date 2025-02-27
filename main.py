import mmap
import ctypes
import time
import socket
import struct

import csv
import os

# Shared memory name for Assetto Corsa physics data
AC_SHARED_MEMORY_NAME = "Local\\acpmf_physics"

# Define UDP target (adjust to match your motion simulator's settings)
UDP_IP = "192.168.1.100"  # Replace with your simulator's IP
UDP_PORT = 20777  # Replace with your target UDP port

# Define CSV file path
write_tx_to_csv = True
csv_file = "telemetry_log.csv"

# Write header if the file doesn't exist
if not os.path.exists(csv_file) and write_tx_to_csv:
    with open(csv_file, mode="w", newline="") as file:
        writer = csv.writer(file)
        header = [
            "Heartbeat",
            "NSimRequest",
            "NCueingMode",
            "BEnableBrakeBooster",
            "gLongDemand",
            "gLatDemand",
            "gVertDemand",
            "dnRollDemand",
            "dnPitchDemand",
            "dnYawDemand",
            "vLongCar",
            "gLongExternalCueing",
            "gLatExternalCueing",
            "gVertExternalCueing",
            "dnRollExternalCueing",
            "dnPitchExternalCueing",
            "dnYawExternalCueing",
            "vLongExternalCueing",
            "vLatExternalCueing",
            "vVertExternalCueing",
            "nRollExternalCueing",
            "nPitchExternalCueing",
            "nYawExternalCueing",
            "xLongExternalCueing",
            "xLatExternalCueing",
            "xVertExternalCueing",
            "aRollExternalCueing",
            "aPitchExternalCueing",
            "aYawExternalCueing",
            "nEngine",
            "NGear",
            "rUpshiftCue",
            "rDownshiftCue",
            "rEngineCue",
            "aSlipCue",
            "nSlipCar",
            "dnSlipCar",
            "rSideSlipCue",
            "rWashoutLong",
            "rWashoutLat",
            "rWashoutVert",
            "rWashoutRoll",
            "rWashoutPitch",
            "rWashoutYaw",
            "fWashoutLong",
            "fWashoutLat",
            "fWashoutVert",
            "fWashoutRoll",
            "fWashoutPitch",
            "fWashoutYaw",
            "zetaWashoutLong",
            "zetaWashoutLat",
            "zetaWashoutVert",
            "zetaWashoutRoll",
            "zetaWashoutPitch",
            "zetaWashoutYaw",
            "xLongSpeedPreposMin",
            "xLongSpeedPreposMax",
            "vCarSpeedPreposMin",
            "vCarSpeedPreposMax",
            "NMSteer"
        ]
        writer.writerow(header)


# Append data to the CSV file
def log_to_csv(data):
    with open(csv_file, mode="a", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(data)


# Define the structure of the telemetry data
# noinspection PyTypeChecker
class PhysicsData(ctypes.Structure):
    _fields_ = [
        ("packet_id", ctypes.c_int),
        ("gas", ctypes.c_float),
        ("brake", ctypes.c_float),
        ("fuel", ctypes.c_float),
        ("speed", ctypes.c_float),
        ("rpms", ctypes.c_int),
        ("gear", ctypes.c_int),
        ("steer_angle", ctypes.c_float),
        ("tyre_temp", ctypes.c_float * 4),
        ("lap_time", ctypes.c_int),
        ("last_lap", ctypes.c_int),
        ("best_lap", ctypes.c_int),
        ("accG", ctypes.c_float * 3),  # [gLong, gLat, gVert]
        ("finalFF", ctypes.c_float)  # Force feedback torque
    ]


PHYSICS_DATA_SIZE = ctypes.sizeof(PhysicsData)

# Default values for model constants & washout settings (adjust as needed)
modelConstants = {
    "NSimRequest": 1,
    "NCueingMode": 1,
    "BEnableBrakeBooster": 0,
    "TorqueMultiplier": 1.0
}

washoutSettings = {
    "rWashoutLong": 0, "rWashoutLat": 0, "rWashoutVert": 0,
    "rWashoutRoll": 0, "rWashoutPitch": 0, "rWashoutYaw": 0,
    "fWashoutLong": 0, "fWashoutLat": 0, "fWashoutVert": 0,
    "fWashoutRoll": 0, "fWashoutPitch": 0, "fWashoutYaw": 0,
    "zetaWashoutLong": 0, "zetaWashoutLat": 0, "zetaWashoutVert": 0,
    "zetaWashoutRoll": 0, "zetaWashoutPitch": 0, "zetaWashoutYaw": 0
}

# Open shared memory
try:
    file_handle = mmap.mmap(-1, PHYSICS_DATA_SIZE, AC_SHARED_MEMORY_NAME, access=mmap.ACCESS_READ)
except FileNotFoundError:
    print("Assetto Corsa shared memory not found. Is the game running?")
    exit(1)

# Setup UDP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

heartbeat = True
last_packet_id = -1

print("Reading telemetry data and sending UDP packets...\n")

while True:
    file_handle.seek(0)
    raw_data = file_handle.read(PHYSICS_DATA_SIZE)
    physics_data = PhysicsData.from_buffer_copy(raw_data)

    if physics_data.packet_id != last_packet_id:  # Send only when new data is available
        last_packet_id = physics_data.packet_id
        heartbeat = not heartbeat  # Beat the heart

        # Construct tx buffer (TwinCAT format)
        txbuf = [
            # Heartbeat
            float(heartbeat),                                           # Heartbeat
            # Model constants
            float(modelConstants["NSimRequest"]),                       # NSimRequest
            float(modelConstants["NCueingMode"]),                       # NCueingMode
            float(modelConstants["BEnableBrakeBooster"]),               # BEnableBrakeBooster
            # Physics data
            physics_data.accG[2],                                       # gLongDemand
            physics_data.accG[0],                                       # gLatDemand
            physics_data.accG[1],                                       # gVertDemand
            0,                                                          # dnRollDemand
            0,                                                          # dnPitchDemand
            0,                                                          # dnYawDemand
            # External cueing
            physics_data.speed / 3.6,                                   # vLongCar (converted to m/s)
            # -
            0,                                                          # gLongExternalCueing
            0,                                                          # gLatExternalCueing
            0,                                                          # gVertExternalCueing
            0,                                                          # dnRollExternalCueing
            0,                                                          # dnPitchExternalCueing
            0,                                                          # dnYawExternalCueing
            # -
            0,                                                          # vLongExternalCueing
            0,                                                          # vLatExternalCueing
            0,                                                          # vVertExternalCueing
            0,                                                          # nRollExternalCueing
            0,                                                          # nPitchExternalCueing
            0,                                                          # nYawExternalCueing
            0,                                                          # xLongExternalCueing
            0,                                                          # xLatExternalCueing
            0,                                                          # xVertExternalCueing
            0,                                                          # aRollExternalCueing
            0,                                                          # aPitchExternalCueing
            0,                                                          # aYawExternalCueing
            # Drive train
            physics_data.rpms * (2 * 3.142 / 60),                       # nEngine (convert RPM to rad/s)
            float(physics_data.gear),                                   # NGear
            0,                                                          # rUpshiftCue
            0,                                                          # rDownshiftCue
            0,                                                          # rEngineCue
            # Slip cueing
            0,                                                          # aSlipCue
            0,                                                          # nSlipCar
            0,                                                          # dnSlipCar
            0,                                                          # rSideSlipCue
            # Washout settings
            float(washoutSettings["rWashoutLong"]),                     # rWashoutLong
            float(washoutSettings["rWashoutLat"]),                      # rWashoutLat
            float(washoutSettings["rWashoutVert"]),                     # rWashoutVert
            float(washoutSettings["rWashoutRoll"]),                     # rWashoutRoll
            float(washoutSettings["rWashoutPitch"]),                    # rWashoutPitch
            float(washoutSettings["rWashoutYaw"]),                      # rWashoutYaw
            float(washoutSettings["fWashoutLong"]),                     # fWashoutLong
            float(washoutSettings["fWashoutLat"]),                      # fWashoutLat
            float(washoutSettings["fWashoutVert"]),                     # fWashoutVert
            float(washoutSettings["fWashoutRoll"]),                     # fWashoutRoll
            float(washoutSettings["fWashoutPitch"]),                    # fWashoutPitch
            float(washoutSettings["fWashoutYaw"]),                      # fWashoutYaw
            float(washoutSettings["zetaWashoutLong"]),                  # zetaWashoutLong
            float(washoutSettings["zetaWashoutLat"]),                   # zetaWashoutLat
            float(washoutSettings["zetaWashoutVert"]),                  # zetaWashoutVert
            float(washoutSettings["zetaWashoutRoll"]),                  # zetaWashoutRoll
            float(washoutSettings["zetaWashoutPitch"]),                 # zetaWashoutPitch
            float(washoutSettings["zetaWashoutYaw"]),                   # zetaWashoutYaw
            0,                                                          # xLongSpeedPreposMin
            0,                                                          # xLongSpeedPreposMax
            0,                                                          # vCarSpeedPreposMin
            0,                                                          # vCarSpeedPreposMax
            modelConstants["TorqueMultiplier"] * physics_data.finalFF   # NMSteer
        ]

        # Pack the buffer into a binary format (struct.pack for 60 floats)
        udp_packet = struct.pack(f"{len(txbuf)}f", *txbuf)

        # Send UDP packet
        sock.sendto(udp_packet, (UDP_IP, UDP_PORT))

        # Console output (for debugging)
        print(
            f"Sent packet {heartbeat} - Speed: {physics_data.speed * 3.6:.1f} km/h, RPM: {physics_data.rpms}, throttle: {physics_data.gas:.1f}, brake: {physics_data.brake:.1f}, Steering Torque: {physics_data.finalFF:.1f}")

        if write_tx_to_csv:
            log_to_csv(txbuf)

    time.sleep(0.01)  # Reduce CPU usage
