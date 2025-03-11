import mmap
import ctypes
import time
import socket
import struct
import configparser
import pygetwindow as gw
from collections import namedtuple
import sys
import csv
import os

# Shared memory name for Assetto Corsa physics & graphics data
AC_PHYSICS_MEMORY_NAME = "Local\\acpmf_physics"
AC_GRAPHICS_MEMORY_NAME = "Local\\acpmf_graphics"

DEFAULT_SETTINGS = {
    'Network': {
        'UDP_IP': '192.168.1.100',
        'UDP_TX_PORT': '20777',
        'TRANSMIT_TO_SELF': 'False'
    },
    'Debug': {
        'debug_output': 'False'
    },
    'Logging': {
        'write_tx_to_csv': 'False',
        'log_execution_time': 'False',
        'tx_csv_file': 'telemetry_log.csv'
    },
    'Processing': {
        'read_graphics_telemetry': 'False'
    },
    'ModelConstants': {
        'NSimRequest': '1',
        'NCueingMode': '1',
        'BEnableBrakeBooster': '0',
        'TorqueMultiplier': '1.0'
    },
    'WashoutSettings': {
        'rWashoutLong': '1', 'rWashoutLat': '1', 'rWashoutVert': '1',
        'rWashoutRoll': '1', 'rWashoutPitch': '1', 'rWashoutYaw': '1',
        'fWashoutLong': '1', 'fWashoutLat': '2', 'fWashoutVert': '2',
        'fWashoutRoll': '1.5', 'fWashoutPitch': '1.5', 'fWashoutYaw': '0.5',
        'zetaWashoutLong': '3', 'zetaWashoutLat': '2', 'zetaWashoutVert': '4',
        'zetaWashoutRoll': '4', 'zetaWashoutPitch': '3', 'zetaWashoutYaw': '2'
    }
}

CONFIG_FILE = 'config.txt'


# Function to create config file with default settings
def create_default_config():
    config.read_dict(DEFAULT_SETTINGS)
    with open(CONFIG_FILE, 'w') as configfile:
        # noinspection PyTypeChecker
        config.write(configfile)


# Load config if it exists, otherwise create it
config = configparser.ConfigParser()
config.optionxform = str  # Preserve original case of keys
if not os.path.exists(CONFIG_FILE):
    print(f"{CONFIG_FILE} not found. Creating with default settings.")
    create_default_config()

config.read(CONFIG_FILE)

# Read network settings
UDP_IP = config.get('Network', 'UDP_IP')
UDP_TX_PORT = config.getint('Network', 'UDP_TX_PORT')
TRANSMIT_TO_SELF = config.getboolean('Network', 'TRANSMIT_TO_SELF')

# Read debug settings
debug_output = config.getboolean('Debug', 'debug_output')

# Read logging settings
write_tx_to_csv = config.getboolean('Logging', 'write_tx_to_csv')
log_execution_time = config.getboolean('Logging', 'log_execution_time')
tx_csv_file = config.get('Logging', 'tx_csv_file')

# Read processing settings
read_graphics_telemetry = config.getboolean('Processing', 'read_graphics_telemetry')

# Read model constants
modelConstants = {
    "NSimRequest": config.getint('ModelConstants', 'NSimRequest'),
    "NCueingMode": config.getint('ModelConstants', 'NCueingMode'),
    "BEnableBrakeBooster": config.getint('ModelConstants', 'BEnableBrakeBooster'),
    "TorqueMultiplier": config.getfloat('ModelConstants', 'TorqueMultiplier')
}

# Read washout settings
washoutSettings = {key: float(value) for key, value in config.items('WashoutSettings')}

# Adjust IP if TRANSMIT_TO_SELF is True
if TRANSMIT_TO_SELF:
    UDP_IP = socket.gethostbyname(socket.gethostname())

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


# Check if the game window is open
def is_game_running():
    windows = gw.getAllTitles()
    for title in windows:
        if title == "Assetto Corsa":
            return True
    return False


# Open shared memory
def open_shared_memory(name, size, retries=3, delay=2):
    for attempt in range(retries):
        try:
            return mmap.mmap(-1, size, name, access=mmap.ACCESS_READ)
        except FileNotFoundError:
            print(f"Attempt {attempt + 1}/{retries}: Shared memory '{name}' not found. Retrying in {delay}s...")
            time.sleep(delay)
    print(f"Shared memory '{name}' not found. Exiting.")
    exit(1)


def update_console_state(state):
    # Move cursor back to the start of the line and print the activity
    sys.stdout.write(f"\rActivity: [{state}]")
    sys.stdout.flush()


# CSVLogger class to handle CSV operations
class CSVLogger:
    def __init__(self, file_path, headers, bool_log_execution_time=False):
        self.file_path = file_path
        self.log_execution_time = bool_log_execution_time

        # Remove existing file if it exists
        if os.path.exists(self.file_path):
            os.remove(self.file_path)

        # Create CSV file with headers
        self.create_csv(headers)

    def create_csv(self, column_headers):
        with open(self.file_path, mode="w", newline="") as file:
            csv_writer = csv.writer(file)
            if self.log_execution_time:
                csv_writer.writerow(["Latency", "PacketID"] + list(column_headers))
            else:
                csv_writer.writerow(["PacketID"] + list(column_headers))

    def log(self, data, additional_data=None):
        with open(self.file_path, mode="a", newline="") as file:
            data = list(data)
            if additional_data:
                data = additional_data + data
            csv_writer = csv.writer(file)
            csv_writer.writerow(data)


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


# Define the structure of the graphics telemetry data
# noinspection PyTypeChecker
class GraphicsData(ctypes.Structure):
    _fields_ = [
        ("packet_id", ctypes.c_int),
        ("status", ctypes.c_int),
        ("session", ctypes.c_int),
        ("current_time", ctypes.c_wchar * 15),
        ("last_time", ctypes.c_wchar * 15),
        ("best_time", ctypes.c_wchar * 15),
        ("split", ctypes.c_wchar * 15),
        ("completed_laps", ctypes.c_int),
        ("position", ctypes.c_int),
        ("i_current_time", ctypes.c_int),
        ("i_last_time", ctypes.c_int),
        ("i_best_time", ctypes.c_int),
        ("session_time_left", ctypes.c_float),
        ("distance_traveled", ctypes.c_float),
        ("is_in_pit", ctypes.c_int),
        ("current_sector_index", ctypes.c_int),
        ("last_sector_time", ctypes.c_int),
        ("number_of_laps", ctypes.c_int),
        ("tyre_compound", ctypes.c_wchar * 33),
        ("replay_time_multiplier", ctypes.c_float),
        ("normalized_car_position", ctypes.c_float),
        ("active_cars", ctypes.c_int),
        ("car_coordinates", ctypes.c_float * 60 * 3),
        ("car_id", ctypes.c_int * 60),
        ("player_car_id", ctypes.c_int),
        ("penalty_time", ctypes.c_float),
        ("flag", ctypes.c_int),
        ("penalty", ctypes.c_int),
        ("ideal_line_on", ctypes.c_int),
        ("is_in_pit_lane", ctypes.c_int),
        ("surface_grip", ctypes.c_float),
        ("mandatory_pit_done", ctypes.c_int),
        ("wind_speed", ctypes.c_float),
        ("wind_direction", ctypes.c_float),
        ("is_setup_menu_visible", ctypes.c_int),
        ("main_display_index", ctypes.c_int),
        ("secondary_display_index", ctypes.c_int),
        ("TC", ctypes.c_int),
        ("TCCut", ctypes.c_int),
        ("EngineMap", ctypes.c_int),
        ("ABS", ctypes.c_int)
    ]


GRAPHICS_DATA_SIZE = ctypes.sizeof(GraphicsData)

# Setup UDP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Setup initial values
bHeartbeat = True
last_packet_id = -1
last_time = time.time()
time_taken = 0

# Initialize CSV logger
csv_logger = None
if write_tx_to_csv:
    # noinspection PyRedeclaration
    csv_logger = CSVLogger(tx_csv_file, TelemetryData._fields, log_execution_time)

while True:
    retry_logged = False
    while not is_game_running():
        if not retry_logged:
            print("\nAssetto Corsa not detected. Waiting...\n")
            retry_logged = True
        time.sleep(3)

    print("Assetto Corsa detected! Allowing time for game start...")
    time.sleep(10)  # Wait for the game to fully load

    # Open shared memory
    physics_file_handle = open_shared_memory(AC_PHYSICS_MEMORY_NAME, PHYSICS_DATA_SIZE)
    graphics_file_handle = open_shared_memory(AC_GRAPHICS_MEMORY_NAME, GRAPHICS_DATA_SIZE)

    print("Reading telemetry data and sending UDP packets...\n")
    update_console_state("")
    while is_game_running():
        if log_execution_time:
            current_time = time.time()
            time_taken = current_time - last_time
            last_time = current_time

        # Read physics data from shared memory
        physics_file_handle.seek(0)
        try:
            raw_data = physics_file_handle.read(PHYSICS_DATA_SIZE)
        except OSError:
            continue  # Skip this iteration if shared memory is temporarily unavailable
        physics_data = PhysicsData.from_buffer_copy(raw_data)

        # Read graphics data from shared memory
        if read_graphics_telemetry:
            graphics_file_handle.seek(0)
            try:
                raw_data = graphics_file_handle.read(GRAPHICS_DATA_SIZE)
            except OSError:
                continue  # Skip this iteration if shared memory is temporarily unavailable
            graphics_data = GraphicsData.from_buffer_copy(raw_data)

        # If new data is available, assemble and send it
        if physics_data.packet_id != last_packet_id:
            update_console_state("●")  # Activity light on
            last_packet_id = physics_data.packet_id
            bHeartbeat = not bHeartbeat  # Beat heart

            # Construct tx buffer using namedTuple (TwinCAT format)
            txbuf = TelemetryData(
                Heartbeat=float(bHeartbeat),
                NSimRequest=int(modelConstants["NSimRequest"]),
                NCueingMode=int(modelConstants["NCueingMode"]),
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

            # Pack the buffer into the pre-defined binary format
            udp_packet = struct.pack(
                ">BbbB" + "f" * 56 + "h",  # Format string: big-endian (>), 4 bytes for USINT/SINT + 56 floats + 1 short
                int(txbuf.Heartbeat),  # USINT (8-bit unsigned)
                int(txbuf.NSimRequest),  # SINT (8-bit signed)
                int(txbuf.NCueingMode),  # SINT (8-bit signed)
                int(txbuf.BEnableBrakeBooster),  # USINT (8-bit unsigned)
                *txbuf[4:-1],  # 56 floats as they are
                int(txbuf.NMSteer)  # INT (16-bit signed)
            )

            hex_data = ' '.join(f'{byte:02X}' for byte in udp_packet)

            # Send UDP packet
            sock.sendto(udp_packet, (UDP_IP, UDP_TX_PORT))

            # Console output (for debugging)
            if debug_output:
                print(
                    f"Packet sent - Speed: {physics_data.speed_kmh:.1f} km/h, RPM: {physics_data.rpms}, throttle: {physics_data.gas:.1f}, brake: {physics_data.brake:.1f}, Steering Torque: {physics_data.final_ff:.1f}")

            if write_tx_to_csv:
                packet_id = physics_data.packet_id
                if log_execution_time:
                    csv_logger.log(txbuf, [time_taken, packet_id])
                else:
                    csv_logger.log(txbuf, [packet_id])

        else:
            update_console_state("○")  # Activity light off
