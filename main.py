import mmap
import ctypes
import time
import socket
import struct
from collections import namedtuple

import csv
import os

# Shared memory name for Assetto Corsa physics data
AC_SHARED_MEMORY_NAME = "Local\\acpmf_physics"

# Define UDP target
UDP_IP = "192.168.1.100"
UDP_TX_PORT = 20777
TRANSMIT_TO_SELF = False

UDP_IP = socket.gethostbyname(socket.gethostname()) if TRANSMIT_TO_SELF else UDP_IP

# Debug console output
debug_output = False

# Define CSV file path
write_tx_to_csv = True
tx_csv_file = "telemetry_log.csv"
os.remove(tx_csv_file) if os.path.exists(tx_csv_file) and write_tx_to_csv else None

# Write header to CSV file
if write_tx_to_csv:
    with open(tx_csv_file, mode="w", newline="") as file:
        writer = csv.writer(file)
        header = [
            "PacketID",
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


# Append current data to the CSV file
def log_to_csv(data, additional_data=None):
    with open(tx_csv_file, mode="a", newline="") as f:
        data = list(data)
        if additional_data:
            data = additional_data + data
        csv_writer = csv.writer(f)
        csv_writer.writerow(data)


def open_shared_memory(retries=3, delay=2):
    for attempt in range(retries):
        try:
            return mmap.mmap(-1, PHYSICS_DATA_SIZE, AC_SHARED_MEMORY_NAME, access=mmap.ACCESS_READ)
        except FileNotFoundError:
            print(f"Attempt {attempt + 1}/{retries}: Shared memory not found. Retrying in {delay}s...")
            time.sleep(delay)
    print("Assetto Corsa shared memory not found. Exiting.")
    exit(1)


# Define the structure of the physics telemetry data
# noinspection PyTypeChecker
class PhysicsData(ctypes.Structure):
    _fields_ = [
        ("packet_id", ctypes.c_int),
        ("gas", ctypes.c_float),
        ("brake", ctypes.c_float),
        ("fuel", ctypes.c_float),
        ("gear", ctypes.c_int),
        ("rpms", ctypes.c_int),
        ("steer_angle", ctypes.c_float),
        ("speed_kmh", ctypes.c_float),
        ("velocity", ctypes.c_float * 3),
        ("acc_g", ctypes.c_float * 3),
        ("wheel_slip", ctypes.c_float * 4),
        ("wheel_load", ctypes.c_float * 4),
        ("wheels_pressure", ctypes.c_float * 4),
        ("wheel_angular_speed", ctypes.c_float * 4),
        ("tyre_wear", ctypes.c_float * 4),
        ("tyre_dirty_level", ctypes.c_float * 4),
        ("tyre_core_temperature", ctypes.c_float * 4),
        ("camber_rad", ctypes.c_float * 4),
        ("suspension_travel", ctypes.c_float * 4),
        ("drs", ctypes.c_float),
        ("tc", ctypes.c_float),
        ("heading", ctypes.c_float),
        ("pitch", ctypes.c_float),
        ("roll", ctypes.c_float),
        ("cg_height", ctypes.c_float),
        ("car_damage", ctypes.c_float * 5),
        ("number_of_tyres_out", ctypes.c_int),
        ("pit_limiter_on", ctypes.c_int),
        ("abs", ctypes.c_float),
        ("kers_charge", ctypes.c_float),
        ("kers_input", ctypes.c_float),
        ("auto_shifter_on", ctypes.c_int),
        ("ride_height", ctypes.c_float * 2),
        ("turbo_boost", ctypes.c_float),
        ("ballast", ctypes.c_float),
        ("air_density", ctypes.c_float),
        ("air_temp", ctypes.c_float),
        ("road_temp", ctypes.c_float),
        ("local_angular_vel", ctypes.c_float * 3),
        ("final_ff", ctypes.c_float),
        ("performance_meter", ctypes.c_float),
        ("engine_brake", ctypes.c_int),
        ("ers_recovery_level", ctypes.c_int),
        ("ers_power_level", ctypes.c_int),
        ("ers_heat_charging", ctypes.c_int),
        ("ers_is_charging", ctypes.c_int),
        ("kers_current_kj", ctypes.c_float),
        ("drs_available", ctypes.c_int),
        ("drs_enabled", ctypes.c_int),
        ("brake_temp", ctypes.c_float * 4),
        ("clutch", ctypes.c_float),
        ("tyre_temp_i", ctypes.c_float * 4),
        ("tyre_temp_m", ctypes.c_float * 4),
        ("tyre_temp_o", ctypes.c_float * 4),
        ("is_ai_controlled", ctypes.c_int),
        ("tyre_contact_point", ctypes.c_float * 4 * 3),
        ("tyre_contact_normal", ctypes.c_float * 4 * 3),
        ("tyre_contact_heading", ctypes.c_float * 4 * 3),
        ("brake_bias", ctypes.c_float),
        ("local_velocity", ctypes.c_float * 3),
        ("p2p_activations", ctypes.c_int),
        ("p2p_status", ctypes.c_int),
        ("current_max_rpm", ctypes.c_int),
        ("mz", ctypes.c_float * 4),
        ("fx", ctypes.c_float * 4),
        ("fy", ctypes.c_float * 4),
        ("slip_ratio", ctypes.c_float * 4),
        ("slip_angle", ctypes.c_float * 4),
        ("tc_in_action", ctypes.c_int),
        ("abs_in_action", ctypes.c_int),
        ("suspension_damage", ctypes.c_float * 4),
        ("tyre_temp", ctypes.c_float * 4),
    ]


PHYSICS_DATA_SIZE = ctypes.sizeof(PhysicsData)

# Default values for model constants & washout setting
modelConstants = {
    "NSimRequest": 1,
    "NCueingMode": 1,
    "BEnableBrakeBooster": 0,
    "TorqueMultiplier": 1.0
}

washoutSettings = {
    "rWashoutLong": 1, "rWashoutLat": 1, "rWashoutVert": 1,
    "rWashoutRoll": 1, "rWashoutPitch": 1, "rWashoutYaw": 1,
    "fWashoutLong": 1, "fWashoutLat": 2, "fWashoutVert": 2,
    "fWashoutRoll": 1.5, "fWashoutPitch": 1.5, "fWashoutYaw": 0.5,
    "zetaWashoutLong": 3, "zetaWashoutLat": 2, "zetaWashoutVert": 4,
    "zetaWashoutRoll": 4, "zetaWashoutPitch": 3, "zetaWashoutYaw": 2
}

# Define the namedtuple for telemetry data
TelemetryData = namedtuple('TelemetryData', [
    "Heartbeat", "NSimRequest", "NCueingMode", "BEnableBrakeBooster",
    "gLongDemand", "gLatDemand", "gVertDemand",
    "dnRollDemand", "dnPitchDemand", "dnYawDemand",
    "vLongCar", "gLongExternalCueing", "gLatExternalCueing", "gVertExternalCueing",
    "dnRollExternalCueing", "dnPitchExternalCueing", "dnYawExternalCueing",
    "vLongExternalCueing", "vLatExternalCueing", "vVertExternalCueing",
    "nRollExternalCueing", "nPitchExternalCueing", "nYawExternalCueing",
    "xLongExternalCueing", "xLatExternalCueing", "xVertExternalCueing",
    "aRollExternalCueing", "aPitchExternalCueing", "aYawExternalCueing",
    "nEngine", "NGear", "rUpshiftCue", "rDownshiftCue", "rEngineCue",
    "aSlipCue", "nSlipCar", "dnSlipCar", "rSideSlipCue",
    "rWashoutLong", "rWashoutLat", "rWashoutVert",
    "rWashoutRoll", "rWashoutPitch", "rWashoutYaw",
    "fWashoutLong", "fWashoutLat", "fWashoutVert",
    "fWashoutRoll", "fWashoutPitch", "fWashoutYaw",
    "zetaWashoutLong", "zetaWashoutLat", "zetaWashoutVert",
    "zetaWashoutRoll", "zetaWashoutPitch", "zetaWashoutYaw",
    "xLongSpeedPreposMin", "xLongSpeedPreposMax",
    "vCarSpeedPreposMin", "vCarSpeedPreposMax",
    "NMSteer"
])

# Open shared memory
file_handle = open_shared_memory()

# Setup UDP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

bHeartbeat = True
last_packet_id = -1

print("Reading telemetry data and sending UDP packets...\n")

last_time = time.time()

while True:
    # Read physics data from shared memory
    file_handle.seek(0)
    raw_data = file_handle.read(PHYSICS_DATA_SIZE)
    physics_data = PhysicsData.from_buffer_copy(raw_data)

    # If new data is available, assemble and send it
    if physics_data.packet_id != last_packet_id:
        last_packet_id = physics_data.packet_id
        bHeartbeat = not bHeartbeat  # Beat the heart

        # Construct tx buffer using namedTuple (TwinCAT format)
        txbuf = TelemetryData(
            Heartbeat=float(bHeartbeat),
            NSimRequest=float(modelConstants["NSimRequest"]),
            NCueingMode=float(modelConstants["NCueingMode"]),
            BEnableBrakeBooster=float(modelConstants["BEnableBrakeBooster"]),
            gLongDemand=physics_data.acc_g[2],
            gLatDemand=physics_data.acc_g[0],
            gVertDemand=physics_data.acc_g[1],
            dnRollDemand=0.0,
            dnPitchDemand=0.0,
            dnYawDemand=0.0,
            vLongCar=physics_data.speed_kmh / 3.6,
            gLongExternalCueing=0.0,
            gLatExternalCueing=0.0,
            gVertExternalCueing=0.0,
            dnRollExternalCueing=0.0,
            dnPitchExternalCueing=0.0,
            dnYawExternalCueing=0.0,
            vLongExternalCueing=0.0,
            vLatExternalCueing=0.0,
            vVertExternalCueing=0.0,
            nRollExternalCueing=0.0,
            nPitchExternalCueing=0.0,
            nYawExternalCueing=0.0,
            xLongExternalCueing=0.0,
            xLatExternalCueing=0.0,
            xVertExternalCueing=0.0,
            aRollExternalCueing=0.0,
            aPitchExternalCueing=0.0,
            aYawExternalCueing=0.0,
            nEngine=physics_data.rpms * (2 * 3.142 / 60),
            NGear=float(physics_data.gear),
            rUpshiftCue=0.0,
            rDownshiftCue=0.0,
            rEngineCue=0.0,
            aSlipCue=0.0,
            nSlipCar=0.0,
            dnSlipCar=0.0,
            rSideSlipCue=0.0,
            rWashoutLong=float(washoutSettings["rWashoutLong"]),
            rWashoutLat=float(washoutSettings["rWashoutLat"]),
            rWashoutVert=float(washoutSettings["rWashoutVert"]),
            rWashoutRoll=float(washoutSettings["rWashoutRoll"]),
            rWashoutPitch=float(washoutSettings["rWashoutPitch"]),
            rWashoutYaw=float(washoutSettings["rWashoutYaw"]),
            fWashoutLong=float(washoutSettings["fWashoutLong"]),
            fWashoutLat=float(washoutSettings["fWashoutLat"]),
            fWashoutVert=float(washoutSettings["fWashoutVert"]),
            fWashoutRoll=float(washoutSettings["fWashoutRoll"]),
            fWashoutPitch=float(washoutSettings["fWashoutPitch"]),
            fWashoutYaw=float(washoutSettings["fWashoutYaw"]),
            zetaWashoutLong=float(washoutSettings["zetaWashoutLong"]),
            zetaWashoutLat=float(washoutSettings["zetaWashoutLat"]),
            zetaWashoutVert=float(washoutSettings["zetaWashoutVert"]),
            zetaWashoutRoll=float(washoutSettings["zetaWashoutRoll"]),
            zetaWashoutPitch=float(washoutSettings["zetaWashoutPitch"]),
            zetaWashoutYaw=float(washoutSettings["zetaWashoutYaw"]),
            xLongSpeedPreposMin=0.0,
            xLongSpeedPreposMax=0.0,
            vCarSpeedPreposMin=0.0,
            vCarSpeedPreposMax=0.0,
            NMSteer=physics_data.final_ff * float(modelConstants["TorqueMultiplier"])
        )

        # Pack the buffer into a binary format (struct.pack for 60 floats)
        udp_packet = struct.pack(f"{len(txbuf)}f", *txbuf)

        # Send UDP packet
        sock.sendto(udp_packet, (UDP_IP, UDP_TX_PORT))

        # Console output (for debugging)
        if debug_output:
            print(f"Packet sent - Speed: {physics_data.speed_kmh:.1f} km/h, RPM: {physics_data.rpms}, throttle: {physics_data.gas:.1f}, brake: {physics_data.brake:.1f}, Steering Torque: {physics_data.final_ff:.1f}")

        if write_tx_to_csv:
            packet_id = physics_data.packet_id
            log_to_csv(txbuf, [packet_id])
