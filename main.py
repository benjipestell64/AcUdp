import mmap
import ctypes
import time
import socket
import struct

# Shared memory name for Assetto Corsa physics data
AC_SHARED_MEMORY_NAME = "Local\\acpmf_physics"

# Define UDP target (adjust to match your motion simulator's settings)
UDP_IP = "192.168.1.100"  # Replace with your simulator's IP
UDP_PORT = 20777  # Replace with your target UDP port


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
            float(heartbeat),  # Heartbeat
            float(modelConstants["NSimRequest"]),
            float(modelConstants["NCueingMode"]),
            float(modelConstants["BEnableBrakeBooster"]),
            physics_data.accG[2],  # gLongDemand
            physics_data.accG[0],  # gLatDemand
            physics_data.accG[1],  # gVertDemand
            0, 0, 0,  # dnRollDemand, dnPitchDemand, dnYawDemand
            physics_data.speed / 3.6,  # vLongCar (converted to m/s)
            0, 0, 0, 0, 0, 0,  # External cueing values
            0, 0, 0, 0, 0, 0, 0, 0, 0,  # More external cueing
            0, 0, 0, 0, 0, 0,  # Slip & shift cues
            physics_data.rpms * (2 * 3.142 / 60),  # nEngine (convert RPM to rad/s)
            float(physics_data.gear),  # NGear
            0, 0, 0, 0, 0, 0,  # More placeholders
            float(washoutSettings["rWashoutLong"]),  # Washout parameters
            float(washoutSettings["rWashoutLat"]),
            float(washoutSettings["rWashoutVert"]),
            float(washoutSettings["rWashoutRoll"]),
            float(washoutSettings["rWashoutPitch"]),
            float(washoutSettings["rWashoutYaw"]),
            float(washoutSettings["fWashoutLong"]),
            float(washoutSettings["fWashoutLat"]),
            float(washoutSettings["fWashoutVert"]),
            float(washoutSettings["fWashoutRoll"]),
            float(washoutSettings["fWashoutPitch"]),
            float(washoutSettings["fWashoutYaw"]),
            float(washoutSettings["zetaWashoutLong"]),
            float(washoutSettings["zetaWashoutLat"]),
            float(washoutSettings["zetaWashoutVert"]),
            float(washoutSettings["zetaWashoutRoll"]),
            float(washoutSettings["zetaWashoutPitch"]),
            float(washoutSettings["zetaWashoutYaw"]),
            0, 0, 0, 0,  # Speed prepositioning placeholders
            modelConstants["TorqueMultiplier"] * physics_data.finalFF  # NMSteer
        ]

        # Pack the buffer into a binary format (struct.pack for 60 floats)
        udp_packet = struct.pack(f"{len(txbuf)}f", *txbuf)

        # Send UDP packet
        sock.sendto(udp_packet, (UDP_IP, UDP_PORT))

        # Console output (for debugging)
        print(f"Sent packet {heartbeat} - Speed: {physics_data.speed * 3.6:.1f} km/h, RPM: {physics_data.rpms}")

    time.sleep(0.01)  # Reduce CPU usage
