import math
import mmap
import ctypes
import time
from datetime import datetime
from datetime import time as dt_time
import socket
import struct
import configparser
import pygetwindow as gw
from collections import namedtuple
import csv
import os
import sys
import tkinter as tk
from tkinter import ttk
import threading

# Compile with: pyinstaller --onefile --windowed --add-data "dynisma.ico;." --path .\.venv\Lib\site-packages\ --icon .\dynisma.ico "Dynisma AC UDP interface.py"

# Shared memory name for Assetto Corsa physics & graphics data
AC_PHYSICS_MEMORY_NAME = "Local\\acpmf_physics"
AC_GRAPHICS_MEMORY_NAME = "Local\\acpmf_graphics"

DEFAULT_SETTINGS = {
    'Network': {
        'UDP_IP': '192.168.1.100',
        'UDP_PORT': '20777',
        'TRANSMIT_TO_SELF': 'False'
    },
    'Debug': {
        'debug_output': 'False'
    },
    'Logging': {
        'write_tx_to_csv': 'False',
        'write_rx_to_csv': 'False',
        'log_execution_time': 'False',
        'tx_csv_file': 'telemetry_log.csv',
        'rx_csv_file': 'controller_log.csv'
    },
    'Processing': {
        'read_graphics_telemetry': 'False',
        'launch_wait_time': '10'
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

prev_ang_vel = [0.0, 0.0, 0.0]  # previous local angular velocity [rollRate, pitchRate, yawRate]
prev_time = time.time()


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

# Variables for recording and playback
recording = False
playback = False
recorded_data = []
playback_index = 0

# Read network settings
UDP_IP = config.get('Network', 'UDP_IP')
UDP_PORT = config.getint('Network', 'UDP_PORT')
TRANSMIT_TO_SELF = config.getboolean('Network', 'TRANSMIT_TO_SELF')

# Read debug settings
debug_output = config.getboolean('Debug', 'debug_output')

# Read logging settings
write_tx_to_csv = config.getboolean('Logging', 'write_tx_to_csv')
write_rx_to_csv = config.getboolean('Logging', 'write_rx_to_csv')
log_execution_time = config.getboolean('Logging', 'log_execution_time')
tx_csv_file = config.get('Logging', 'tx_csv_file')
rx_csv_file = config.get('Logging', 'rx_csv_file')

# Read processing settings
read_graphics_telemetry = config.getboolean('Processing', 'read_graphics_telemetry')
launch_wait_time = config.getint('Processing', 'launch_wait_time')

# Read model constants
modelConstants = {key: (int(value) if value.isdigit() else float(value)) for key, value in
                  config.items('ModelConstants')}

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

# Define the namedtuple for received controller data
ControllerData = namedtuple('ControllerData', [
    "NAMotorSteer", "NNMotorSteer",
    "gLongChassis", "gLatChassis", "gVertChassis",
    "dnRollChassis", "dnPitchChassis", "dnYawChassis",
    "xLongWorld", "xLatWorld", "xVertWorld",
    "aRollWorld", "aPitchWorld", "aYawWorld",
    "vLongWorld", "vLatWorld", "vVertWorld",
    "nRollWorld", "nPitchWorld", "nYawWorld",
    "xLongDemandWorld", "xLatDemandWorld", "xVertDemandWorld",
    "aRollDemandWorld", "aPitchDemandWorld", "aYawDemandWorld",
    "vLongDemandWorld", "vLatDemandWorld", "vVertDemandWorld",
    "nRollDemandWorld", "nPitchDemandWorld", "nYawDemandWorld",
    "TransmitTimeTenMs"
])

# UDP packet structure
RECEIVE_PACKET_FORMAT = "<" + "i" * 2 + "f" * 30 + "i"  # Big endian, 2 DINT (int32), 30 REAL (float32), 1 USINT (int32)
RECEIVE_PACKET_SIZE = struct.calcsize(RECEIVE_PACKET_FORMAT)
TRANSMIT_PACKET_FORMAT = ">BbbB" + "f" * 56 + "h" + "i"  # Big endian, 1 USINT, 2 SINT, 1 USINT, 56 REAL, 1 short INT, 1 USINT
TRANSMIT_PACKET_SIZE = struct.calcsize(TRANSMIT_PACKET_FORMAT)


def attach_console():
    if not ctypes.windll.kernel32.AllocConsole():
        # Console already exists or failed — could try FreeConsole + AllocConsole if needed
        return
    sys.stdout = open('CONOUT$', 'w')
    sys.stderr = open('CONOUT$', 'w')
    sys.stdin = open('CONIN$', 'r')
    print("Debug console attached! (can disable in config)")


if debug_output:
    print("Debug output enabled.")
    attach_console()


# Check if the ac window is open
def is_ac_running():
    return any(title == "Assetto Corsa" for title in gw.getAllTitles())


def open_shared_memory(name, size, retries=3, delay=2):
    """
    Open a shared memory segment.

    This function attempts to open a shared memory segment with the given name and size.
    If the shared memory segment is not found, it will retry a specified number of times
    with a delay between each attempt.

    Args:
        name (str): The name of the shared memory segment.
        size (int): The size of the shared memory segment.
        retries (int, optional): The number of times to retry if the shared memory segment is not found. Defaults to 3.
        delay (int, optional): The delay in seconds between each retry. Defaults to 2.

    Returns:
        mmap.mmap: The opened shared memory segment.

    Raises:
        SystemExit: If the shared memory segment is not found after the specified number of retries.
    """
    for attempt in range(retries):
        try:
            return mmap.mmap(-1, size, name, access=mmap.ACCESS_READ)
        except FileNotFoundError:
            print(f"Attempt {attempt + 1}/{retries}: Shared memory '{name}' not found. Retrying in {delay}s...")
            time.sleep(delay)
    print(f"Shared memory '{name}' not found. Exiting.")
    exit(1)


ACTIVE_LIGHT = "◆"
INACTIVE_LIGHT = "◇"


def set_tx_activity_light(active=False):
    state = ACTIVE_LIGHT if active else INACTIVE_LIGHT
    tx_activity_light.config(text="Activity: " + state)


def set_rx_activity_light(active=False):
    state = ACTIVE_LIGHT if active else INACTIVE_LIGHT
    rx_activity_light.config(text="Activity: " + state)


def pulse_rx_activity_light(duration=0.1):
    """Turn on RX activity light for a short duration."""
    set_rx_activity_light(True)
    threading.Timer(duration, lambda: set_rx_activity_light(False)).start()


def set_rx_socket_bound_light(active=False):
    state = ACTIVE_LIGHT if active else INACTIVE_LIGHT
    rx_socket_bound_light.config(text="Socket bound: " + state)


class CSVLogger:
    """
    A class to handle CSV logging operations.

    Attributes:
        file_path (str): The path to the CSV file.
        column_headers (list): The column headers for the CSV file.
        log_execution_time (bool): Whether to log execution time.
    """

    def __init__(self, file_path, column_headers, bool_log_execution_time=False):
        """
        Initialize the CSVLogger.

        Args:
            file_path (str): The path to the CSV file.
            column_headers (list): The column headers for the CSV file.
            bool_log_execution_time (bool, optional): Whether to log execution time. Defaults to False.
        """
        self.file_path = file_path
        self.column_headers = column_headers
        self.log_execution_time = bool_log_execution_time

        # Remove existing file if it exists
        if os.path.exists(self.file_path):
            os.remove(self.file_path)

        # Create CSV file with headers
        self.create_csv(column_headers)

    def create_csv(self, column_headers):
        """
        Create a new CSV file with the specified column headers.

        Args:
            column_headers (list): The column headers for the CSV file.
        """
        with open(self.file_path, mode="w", newline="") as file:
            csv_writer = csv.writer(file)
            csv_writer.writerow(column_headers)
            print("Log file created:", self.file_path)

    def log(self, data, additional_data=None):
        """
        Log data to the CSV file.

        Args:
            data (list): The data to log.
            additional_data (list, optional): Additional data to log. Defaults to None.
        """
        with open(self.file_path, mode="a", newline="") as file:
            data = list(data)
            if additional_data:
                data = additional_data + data
            csv_writer = csv.writer(file)
            csv_writer.writerow(data)


# Initialize CSV loggers
csv_tx_logger = None
csv_rx_logger = None
if write_tx_to_csv:
    # noinspection PyRedeclaration
    if log_execution_time:
        headers = ["Latency", "PacketID"] + list(TelemetryData._fields)
    else:
        headers = ["PacketID"] + list(TelemetryData._fields)
    csv_tx_logger = CSVLogger(tx_csv_file, headers, log_execution_time)
if write_rx_to_csv:
    # noinspection PyRedeclaration
    headers = ["Timestamp", "RTT (ms)"] + list(ControllerData._fields)
    csv_rx_logger = CSVLogger(rx_csv_file, headers)


# Define the structure of the physics telemetry data
# noinspection PyTypeChecker,PyUnresolvedReferences
class PhysicsData(ctypes.Structure):
    """
    A ctypes Structure representing the physics telemetry data from Assetto Corsa.

    Attributes:
        packet_id (int): The unique identifier for the data packet.
        gas (float): The amount of gas pedal input.
        brake (float): The amount of brake pedal input.
        fuel (float): The amount of fuel remaining.
        gear (int): The current gear.
        rpms (int): The engine RPM.
        steer_angle (float): The steering angle.
        speed_kmh (float): The speed in kilometers per hour.
        velocity (float * 3): The velocity vector.
        acc_g (float * 3): The acceleration vector in Gs.
        wheel_slip (float * 4): The slip ratio for each wheel.
        wheel_load (float * 4): The load on each wheel.
        wheels_pressure (float * 4): The pressure in each tire.
        wheel_angular_speed (float * 4): The angular speed of each wheel.
        tyre_wear (float * 4): The wear level of each tire.
        tyre_dirty_level (float * 4): The dirt level on each tire.
        tyre_core_temperature (float * 4): The core temperature of each tire.
        camber_rad (float * 4): The camber angle in radians for each wheel.
        suspension_travel (float * 4): The suspension travel for each wheel.
        drs (float): The DRS (Drag Reduction System) status.
        tc (float): The traction control status.
        heading (float): The heading angle.
        pitch (float): The pitch angle.
        roll (float): The roll angle.
        cg_height (float): The height of the center of gravity.
        car_damage (float * 5): The damage levels for various parts of the car.
        number_of_tyres_out (int): The number of tires out of track limits.
        pit_limiter_on (int): Whether the pit limiter is on.
        abs (float): The ABS (Anti-lock Braking System) status.
        kers_charge (float): The KERS (Kinetic Energy Recovery System) charge level.
        kers_input (float): The KERS input level.
        auto_shifter_on (int): Whether the auto shifter is on.
        ride_height (float * 2): The ride height for the front and rear.
        turbo_boost (float): The turbo boost level.
        ballast (float): The ballast weight.
        air_density (float): The air density.
        air_temp (float): The air temperature.
        road_temp (float): The road temperature.
        local_angular_vel (float * 3): The local angular velocity vector.
        final_ff (float): The final force feedback value.
        performance_meter (float): The performance meter value.
        engine_brake (int): The engine brake level.
        ers_recovery_level (int): The ERS (Energy Recovery System) recovery level.
        ers_power_level (int): The ERS power level.
        ers_heat_charging (int): The ERS heat charging status.
        ers_is_charging (int): Whether the ERS is charging.
        kers_current_kj (float): The current KERS energy in kilojoules.
        drs_available (int): Whether DRS is available.
        drs_enabled (int): Whether DRS is enabled.
        brake_temp (float * 4): The temperature of each brake.
        clutch (float): The clutch level.
        tyre_temp_i (float * 4): The inner temperature of each tire.
        tyre_temp_m (float * 4): The middle temperature of each tire.
        tyre_temp_o (float * 4): The outer temperature of each tire.
        is_ai_controlled (int): Whether the car is AI controlled.
        tyre_contact_point (float * 4 * 3): The contact points of each tire.
        tyre_contact_normal (float * 4 * 3): The contact normals of each tire.
        tyre_contact_heading (float * 4 * 3): The contact headings of each tire.
        brake_bias (float): The brake bias.
        local_velocity (float * 3): The local velocity vector.
        p2p_activations (int): The number of push-to-pass activations.
        p2p_status (int): The status of push-to-pass.
        current_max_rpm (int): The current maximum RPM.
        mz (float * 4): The aligning moment for each tire.
        fx (float * 4): The longitudinal force for each tire.
        fy (float * 4): The lateral force for each tire.
        slip_ratio (float * 4): The slip ratio for each tire.
        slip_angle (float * 4): The slip angle for each tire.
        tc_in_action (int): Whether traction control is in action.
        abs_in_action (int): Whether ABS is in action.
        suspension_damage (float * 4): The damage level of each suspension.
        tyre_temp (float * 4): The temperature of each tire.
    """
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


def physics_to_row(phys: PhysicsData):
    """Flatten a PhysicsData struct to a list of floats."""
    row = []
    for field_name, field_type in phys._fields_:
        val = getattr(phys, field_name)

        if isinstance(val, ctypes.Array):
            # Check for nested arrays (e.g., float[4][3])
            if isinstance(val[0], ctypes.Array):
                for subarray in val:
                    row.extend(subarray[:])
            else:
                row.extend(val[:])
        else:
            row.append(val)
    return row


def row_to_physics(row):
    """Reconstruct a PhysicsData object from a flat list of floats."""
    phys = PhysicsData()
    flat_idx = 0

    for field_name, field_type in PhysicsData._fields_:
        if hasattr(field_type, "_length_"):  # It's an array
            if hasattr(field_type._type_, "_length_"):  # Nested array
                for i in range(field_type._length_):
                    for j in range(field_type._type_._length_):
                        getattr(phys, field_name)[i][j] = float(row[flat_idx])
                        flat_idx += 1
            else:
                for i in range(field_type._length_):
                    getattr(phys, field_name)[i] = float(row[flat_idx])
                    flat_idx += 1
        else:
            if field_type == ctypes.c_int:
                setattr(phys, field_name, int(row[flat_idx]))
            elif field_type == ctypes.c_float:
                setattr(phys, field_name, float(row[flat_idx]))
            else:
                # Fallback for unknown types
                setattr(phys, field_name, row[flat_idx])
            flat_idx += 1

    return phys


PHYSICS_UNITS = {
    "packet_id": "",
    "gas": "0-1",
    "brake": "0-1",
    "fuel": "L",
    "gear": "",
    "rpms": "rpm",
    "steer_angle": "rad",
    "speed_kmh": "km/h",
    "velocity": "m/s",
    "acc_g": "g",
    "wheel_slip": "",
    "wheel_load": "N",
    "wheels_pressure": "psi",
    "wheel_angular_speed": "rad/s",
    "tyre_wear": "0-1",
    "tyre_dirty_level": "0-1",
    "tyre_core_temperature": "°C",
    "camber_rad": "rad",
    "suspension_travel": "m",
    "drs": "bool",
    "tc": "bool",
    "heading": "rad",
    "pitch": "rad",
    "roll": "rad",
    "cg_height": "m",
    "car_damage": "0-1",
    "number_of_tyres_out": "",
    "pit_limiter_on": "bool",
    "abs": "bool",
    "kers_charge": "J",
    "kers_input": "W",
    "auto_shifter_on": "bool",
    "ride_height": "m",
    "turbo_boost": "bar",
    "ballast": "kg",
    "air_density": "kg/m³",
    "air_temp": "°C",
    "road_temp": "°C",
    "local_angular_vel": "rad/s",
    "final_ff": "Nm",
    "performance_meter": "",
    "engine_brake": "",
    "ers_recovery_level": "",
    "ers_power_level": "",
    "ers_heat_charging": "bool",
    "ers_is_charging": "bool",
    "kers_current_kj": "kJ",
    "drs_available": "bool",
    "drs_enabled": "bool",
    "brake_temp": "°C",
    "clutch": "0-1",
    "tyre_temp_i": "°C",
    "tyre_temp_m": "°C",
    "tyre_temp_o": "°C",
    "is_ai_controlled": "bool",
    "tyre_contact_point": "m",
    "tyre_contact_normal": "",
    "tyre_contact_heading": "rad",
    "brake_bias": "%",
    "local_velocity": "m/s",
    "p2p_activations": "",
    "p2p_status": "bool",
    "current_max_rpm": "rpm",
    "mz": "Nm",
    "fx": "N",
    "fy": "N",
    "slip_ratio": "",
    "slip_angle": "rad",
    "tc_in_action": "bool",
    "abs_in_action": "bool",
    "suspension_damage": "0-1",
    "tyre_temp": "°C"
}


def get_physics_headers():
    """Generate CSV headers with units based on PhysicsData layout."""
    physics_headers = []
    for field_name, field_type in PhysicsData._fields_:
        unit = PHYSICS_UNITS.get(field_name, "")
        suffix = f" ({unit})" if unit else ""

        if hasattr(field_type, "_length_"):  # It's an array
            length = field_type._length_
            if hasattr(field_type._type_, "_length_"):  # Nested array
                sublen = field_type._type_._length_
                for i in range(length):
                    for j in range(sublen):
                        physics_headers.append(f"{field_name}[{i}][{j}]{suffix}")
            else:
                for i in range(length):
                    physics_headers.append(f"{field_name}[{i}]{suffix}")
        else:
            physics_headers.append(f"{field_name}{suffix}")
    return physics_headers


# Define the structure of the graphics telemetry data
# noinspection PyTypeChecker,PyUnresolvedReferences
class GraphicsData(ctypes.Structure):
    """
    A ctypes Structure representing the graphics telemetry data from Assetto Corsa.

    Attributes:
        packet_id (int): The unique identifier for the data packet.
        status (int): The status of the session.
        session (int): The type of session (e.g., practice, qualifying, race).
        current_time (wchar * 15): The current lap time as a wide character string.
        last_time (wchar * 15): The last lap time as a wide character string.
        best_time (wchar * 15): The best lap time as a wide character string.
        split (wchar * 15): The split time as a wide character string.
        completed_laps (int): The number of completed laps.
        position (int): The current position in the session.
        i_current_time (int): The current lap time in milliseconds.
        i_last_time (int): The last lap time in milliseconds.
        i_best_time (int): The best lap time in milliseconds.
        session_time_left (float): The remaining time in the session.
        distance_traveled (float): The distance traveled in the session.
        is_in_pit (int): Whether the car is in the pit.
        current_sector_index (int): The current sector index.
        last_sector_time (int): The last sector time in milliseconds.
        number_of_laps (int): The total number of laps.
        tyre_compound (wchar * 33): The tyre compound as a wide character string.
        replay_time_multiplier (float): The replay time multiplier.
        normalized_car_position (float): The normalized car position.
        active_cars (int): The number of active cars.
        car_coordinates (float * 60 * 3): The coordinates of the cars.
        car_id (int * 60): The IDs of the cars.
        player_car_id (int): The ID of the player's car.
        penalty_time (float): The penalty time.
        flag (int): The flag status.
        penalty (int): The penalty status.
        ideal_line_on (int): Whether the ideal line is on.
        is_in_pit_lane (int): Whether the car is in the pit lane.
        surface_grip (float): The surface grip level.
        mandatory_pit_done (int): Whether the mandatory pit stop is done.
        wind_speed (float): The wind speed.
        wind_direction (float): The wind direction.
        is_setup_menu_visible (int): Whether the setup menu is visible.
        main_display_index (int): The main display index.
        secondary_display_index (int): The secondary display index.
        TC (int): The traction control level.
        TCCut (int): The traction control cut level.
        EngineMap (int): The engine map setting.
        ABS (int): The anti-lock braking system level.
    """
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


def get_angular_acceleration_demand(physics_data):
    global prev_ang_vel, prev_time

    # Current angular velocity (rad/s)
    ang_vel = physics_data.local_angular_vel  # e.g. [rollRate, pitchRate, yawRate]
    current_time = time.time()
    dt = current_time - prev_time

    if dt <= 0.0001:  # Avoid division by zero or absurd acceleration
        dt = 0.001

    # Calculate angular acceleration (rad/s²)
    ang_acc = [
        (ang_vel[i] - prev_ang_vel[i]) / dt
        for i in range(3)
    ]

    # Apply deadzone to suppress noise
    noise_threshold = 0.01
    ang_acc = [acc if abs(acc) >= noise_threshold else 0.0 for acc in ang_acc]

    # Update previous values
    prev_ang_vel = list(ang_vel)
    prev_time = current_time

    # Return acceleration demand
    return ang_acc  # [acc_roll, acc_pitch, acc_yaw]


def get_current_time_in_milliseconds() -> int:
    """Returns the current time of day in milliseconds (since midnight)."""
    now = datetime.now()
    midnight = datetime.combine(now.date(), dt_time(0))
    return int((now - midnight).total_seconds() * 1000)


# noinspection PyTypeChecker
def transmit_loop():
    """
    Main loop for transmitting telemetry data.

    This function continuously checks if Assetto Corsa is running, reads physics data from shared memory,
    constructs a telemetry data packet, and sends it via UDP. It also updates the UI and logs data if required.
    """
    # noinspection PyGlobalUndefined
    global running, txbuf

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # Setup initial values
    heartbeat = True
    last_packet_id = -1
    last_time = time.time()
    time_taken = 0

    while running:

        ac_was_running = True
        while not is_ac_running():
            searching_for_assetto()
            time.sleep(1)
            ac_was_running = False

        if not ac_was_running:
            # Assetto Corsa now launching
            for i in range(launch_wait_time):
                waiting_for_launch(launch_wait_time - i)
                time.sleep(1)
        running = True

        print("Assetto Corsa running.")

        check_counter = 0
        ac_running_cached = True  # assume running at this point

        while running and ac_running_cached:
            # Reduce the frequency of checking if AC is running
            if check_counter == 0:
                ac_running_cached = is_ac_running()
                check_counter = 100  # reset counter
            else:
                check_counter -= 1
            if not ac_running_cached:
                break

            if log_execution_time:
                current_time = time.time()
                time_taken = current_time - last_time
                last_time = current_time

            # Read physics data from shared memory
            global recorded_data, playback_index

            if playback and recorded_data:
                if playback_index >= len(recorded_data):
                    playback_index = 0  # Loop playback
                physics_data = recorded_data[playback_index]
                playback_index += 1
                time.sleep(1 / 60)  # Match AC update rate ~60Hz
            else:
                physics_file_handle = open_shared_memory(AC_PHYSICS_MEMORY_NAME, PHYSICS_DATA_SIZE)
                physics_file_handle.seek(0)
                try:
                    raw_data = physics_file_handle.read(PHYSICS_DATA_SIZE)
                except OSError:
                    continue
                physics_data = PhysicsData.from_buffer_copy(raw_data)
                if recording:
                    recorded_data.append(physics_to_row(physics_data))

            # # Read graphics data from shared memory
            # if read_graphics_telemetry:
            #     graphics_file_handle = open_shared_memory(AC_GRAPHICS_MEMORY_NAME, GRAPHICS_DATA_SIZE)
            #     graphics_file_handle.seek(0)
            #     try:
            #         raw_data = graphics_file_handle.read(GRAPHICS_DATA_SIZE)
            #     except OSError:
            #         continue  # Skip this iteration if shared memory is temporarily unavailable
            #     graphics_data = GraphicsData.from_buffer_copy(raw_data)

            # If new data is available, assemble and send it
            if physics_data.packet_id != last_packet_id:
                set_tx_activity_light(True)  # Activity light on
                last_packet_id = physics_data.packet_id
                heartbeat = not heartbeat  # Beat heart

                # Suppress demands if speed is below a threshold
                if physics_data.speed_kmh < 20.0:
                    g_long = g_lat = g_vert = 0.0
                    acc_roll = acc_pitch = acc_yaw = 0.0
                else:
                    g_long = physics_data.acc_g[2] * 9.81
                    g_lat = physics_data.acc_g[0] * 9.81
                    g_vert = physics_data.acc_g[1] * 9.81
                    acc_pitch, acc_yaw, acc_roll = get_angular_acceleration_demand(physics_data)

                # Construct tx buffer using namedTuple (TwinCAT format)
                txbuf = TelemetryData(
                    Heartbeat=int(heartbeat),
                    NSimRequest=int(modelConstants["NSimRequest"]),
                    NCueingMode=int(modelConstants["NCueingMode"]),
                    BEnableBrakeBooster=int(modelConstants["BEnableBrakeBooster"]),
                    gLongDemand=g_long,
                    gLatDemand=g_lat,
                    gVertDemand=g_vert,
                    dnRollDemand=acc_roll,
                    dnPitchDemand=acc_pitch,
                    dnYawDemand=acc_yaw,
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
                    aRollExternalCueing=physics_data.roll * -1 * 0.3,
                    aPitchExternalCueing=physics_data.pitch * -1 * 0.3,
                    aYawExternalCueing=physics_data.heading * -1 * 0,  # This seems like a bad idea?
                    nEngine=physics_data.rpms * (2 * 3.142 / 60),
                    NGear=float(physics_data.gear - 1),
                    rUpshiftCue=1.25 - 0.8,
                    rDownshiftCue=1.2 - 0.8,  # This is a vector in GT DiL settings: [2, 2, 2, 1, 1, 1]
                    rEngineCue=1.0 * (physics_data.gas * 0.3 + 0.7),
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
                    xLongSpeedPreposMax=0.2,
                    vCarSpeedPreposMin=30,
                    vCarSpeedPreposMax=85,
                    NMSteer=int(physics_data.final_ff * float(modelConstants["TorqueMultiplier"]))
                )

                current_time_ms = get_current_time_in_milliseconds()

                # Pack the buffer into the pre-defined binary format
                udp_packet = struct.pack(
                    TRANSMIT_PACKET_FORMAT,  # Format string
                    txbuf.Heartbeat,  # USINT (8-bit unsigned)
                    txbuf.NSimRequest,  # SINT (8-bit signed)
                    txbuf.NCueingMode,  # SINT (8-bit signed)
                    txbuf.BEnableBrakeBooster,  # USINT (8-bit unsigned)
                    *txbuf[4:-1],  # 56 floats as they are
                    txbuf.NMSteer,  # INT (16-bit signed)
                    current_time_ms * 10  # INT (32-bit signed)
                )

                # hex_data = ' '.join(f'{byte:02X}' for byte in udp_packet)

                # Send UDP packet
                sock.sendto(udp_packet, (UDP_IP, UDP_PORT))

                # Update UI
                status_label.config(text="State: Run")
                speed_label.config(text=f"Speed: {int(physics_data.speed_kmh):03d} km/h")
                gear = round(txbuf.NGear)
                if gear == -1:
                    gear = "R"
                elif gear == 0:
                    gear = "N"
                gear_label.config(text=f"Gear: {gear}")

                # Console output (for debugging)
                if debug_output:
                    print(
                        f"Packet sent - Speed: {physics_data.speed_kmh:.1f} km/h, RPM: {physics_data.rpms}, throttle: {physics_data.gas:.1f}, brake: {physics_data.brake:.1f}, Steering Torque: {physics_data.final_ff:.1f}")

                if write_tx_to_csv:
                    packet_id = physics_data.packet_id
                    if log_execution_time:
                        csv_tx_logger.log(txbuf, [time_taken, packet_id])
                    else:
                        csv_tx_logger.log(txbuf, [packet_id])

            else:
                # No new data
                set_tx_activity_light(False)


# noinspection PyGlobalUndefined,PyTypeChecker
def receive_loop():
    """Thread to listen for incoming UDP packets."""
    global running
    start_time_ms = get_current_time_in_milliseconds()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind(("0.0.0.0", UDP_PORT))
        socket_bound = True
        set_rx_socket_bound_light(True)
    except OSError:
        print(f"Error: Receive loop unable to bind to {UDP_IP}:{UDP_PORT}.")
        socket_bound = False
        set_rx_socket_bound_light(False)

    while running and socket_bound:
        data, addr = sock.recvfrom(RECEIVE_PACKET_SIZE)
        if len(data) == RECEIVE_PACKET_SIZE or True:  # Always process data for testing
            current_time_ms = get_current_time_in_milliseconds()
            timestamp = current_time_ms - start_time_ms

            unpacked_data = struct.unpack(RECEIVE_PACKET_FORMAT, data)
            received_data = ControllerData(*unpacked_data)

            pulse_rx_activity_light()

            received_tot = received_data.TransmitTimeTenMs / 10.0  # undo the 10x factor in the transmit loop
            round_trip_time = current_time_ms - received_tot

            rx_timestamp_label.config(text=f"Timestamp: {timestamp/1000}s")
            csv_rx_logger.log(received_data, [current_time_ms, round_trip_time])


# noinspection PyGlobalUndefined
def start():
    """
    Start the transmission of telemetry data.

    This function sets the `running` flag to True and starts two threads:
    one for transmitting telemetry data (`transmit_thread`) and one for
    receiving incoming UDP packets (`receive_thread`).
    """
    global running
    running = True
    transmit_thread = threading.Thread(target=transmit_loop, daemon=True)
    transmit_thread.start()
    receive_thread = threading.Thread(target=receive_loop, daemon=True)
    receive_thread.start()


# noinspection PyGlobalUndefined
def stop():
    """
    Stop the transmission of telemetry data.

    This function sets the `running` flag to False, updates the status, speed,
    and gear labels to indicate that the transmission has stopped, and turns off
    the activity light.
    """
    global running
    running = False
    status_label.config(text="State: Stop")
    speed_label.config(text="Speed: 000 km/h")
    gear_label.config(text="Gear: 0")
    set_tx_activity_light(False)


def toggle_record():
    global recording, recorded_data
    if not recording:
        recorded_data = []
        recording = True
        record_button.config(text="Stop Recording")
    else:
        recording = False
        record_button.config(text="Record")
        physics_headers = get_physics_headers()

        # Sanity check
        test_row = physics_to_row(PhysicsData())
        if len(physics_headers) != len(test_row):
            print(f"❌ Mismatch: {len(physics_headers)} headers vs {len(test_row)} values!")

        with open("recorded_physics.csv", "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(physics_headers)
            for data in recorded_data:
                writer.writerow(data)
        print("Saved", len(recorded_data), "frames to CSV.")


def toggle_playback():
    global playback, recorded_data, playback_index
    if not playback:
        try:
            with open("recorded_physics.csv", "r") as f:
                reader = csv.reader(f)
                next(reader)  # Skip header
                recorded_data = [row_to_physics(list(map(float, row))) for row in reader if any(row)]
            playback_index = 0
            playback = True
            playback_button.config(text="Stop Playback")
            print("Loaded", len(recorded_data), "frames from CSV.")
        except Exception as e:
            import traceback
            traceback.print_exc()
            print("Playback load failed:", e)
    else:
        playback = False
        playback_button.config(text="Playback")


# noinspection PyGlobalUndefined
def searching_for_assetto():
    """
    Update the UI to indicate that Assetto Corsa is not running.

    This function sets the `running` flag to False and updates the status, speed,
    and gear labels to reflect that no data is being received from Assetto Corsa.
    """
    global running
    running = False
    status_label.config(text="State: No data")
    speed_label.config(text="Speed: N/A")
    gear_label.config(text="Gear: N/A")


def waiting_for_launch(seconds_remaining=None):
    """
    Update the UI to indicate the waiting state during the launch of Assetto Corsa.

    This function updates the status, speed, and gear labels to reflect that the system
    is waiting for the game to launch. If the number of seconds remaining is provided,
    it will be displayed in the status label.

    Args:
        seconds_remaining (int, optional): The number of seconds remaining until the launch is complete. Defaults to None.
    """
    if seconds_remaining:
        status_label.config(text=f"State: Wait ({seconds_remaining}s)")
    else:
        status_label.config(text="State: Wait")
    speed_label.config(text="Speed: N/A")
    gear_label.config(text="Gear: N/A")


def resource_path(relative_path):
    """
    Get the absolute path to a resource.

    This function is used to get the absolute path to a resource, whether the script is running
    in a PyInstaller bundle or as a standard Python script.

    Args:
        relative_path (str): The relative path to the resource.

    Returns:
        str: The absolute path to the resource.
    """
    # noinspection PyBroadException
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        # noinspection PyProtectedMember
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


root = tk.Tk()
root.title("Assetto Corsa UDP Interface")
root.iconbitmap(resource_path("dynisma.ico"))

frame = ttk.Frame(root, padding=10)
# noinspection PyTypeChecker
frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

transmit_label = ttk.Label(frame, text="Target: " + UDP_IP + " Port: " + str(UDP_PORT), foreground="gray20")
transmit_label.grid(row=0, column=0, columnspan=8, pady=5)

# Transmit
transmit_label = ttk.Label(frame, text="Transmit", background="gray80")
transmit_label.grid(row=1, column=0, columnspan=4, pady=5)

tx_activity_light = ttk.Label(frame, text="")
tx_activity_light.grid(row=2, column=0, columnspan=1, padx=5, pady=5, sticky="w")
set_tx_activity_light()

status_label = ttk.Label(frame, text="State: Stop")
status_label.grid(row=3, column=0, columnspan=1, padx=5, pady=5, sticky="w")

speed_label = ttk.Label(frame, text="Speed: N/A")
speed_label.grid(row=2, column=2, columnspan=1, padx=5, pady=5, sticky="w")

gear_label = ttk.Label(frame, text="Gear: N/A")
gear_label.grid(row=3, column=2, columnspan=1, padx=5, pady=5, sticky="w")

tx_logging_label = ttk.Label(frame, text="Log: " + tx_csv_file if write_tx_to_csv else "Log: Disabled",
                             foreground="gray20")
tx_logging_label.grid(row=4, column=0, columnspan=3, padx=5, pady=5, sticky="w")

# Receive
transmit_label = ttk.Label(frame, text="Receive", background="grey80")
transmit_label.grid(row=1, column=4, columnspan=4, pady=5)

rx_activity_light = ttk.Label(frame, text="")
rx_activity_light.grid(row=2, column=4, columnspan=1, padx=5, pady=5, sticky="w")
set_rx_activity_light()

rx_timestamp_label = ttk.Label(frame, text="Timestamp: 0000.00")
rx_timestamp_label.grid(row=2, column=5, columnspan=1, padx=5, pady=5, sticky="w")

rx_socket_bound_light = ttk.Label(frame, text="")
rx_socket_bound_light.grid(row=3, column=4, columnspan=2, padx=5, pady=5, sticky="w")
set_rx_socket_bound_light()

rx_logging_label = ttk.Label(frame, text="Log: " + rx_csv_file if write_rx_to_csv else "Log: Disabled",
                             foreground="gray20")
rx_logging_label.grid(row=4, column=4, columnspan=3, padx=5, pady=5, sticky="w")

# Buttons
open_tx_log_button = ttk.Button(frame, text="Open", width=5, command=lambda: os.system(f"start {tx_csv_file}"))
open_tx_log_button.grid(row=4, column=2, columnspan=1, padx=0, pady=5, sticky="e")

open_rx_log_button = ttk.Button(frame, text="Open", width=5, command=lambda: os.system(f"start {rx_csv_file}"))
open_rx_log_button.grid(row=4, column=5, columnspan=1, padx=0, pady=5, sticky="e")

config_button = ttk.Button(frame, text="Configure ⚙️", width=50, command=lambda: os.system(f"start {CONFIG_FILE}"))
config_button.grid(row=6, column=0, columnspan=8, padx=10, pady=5)

start_button = ttk.Button(frame, text="Start", width=25, command=start)
start_button.grid(row=7, column=0, columnspan=4, padx=5, pady=5)

stop_button = ttk.Button(frame, text="Stop", width=25, command=stop)
stop_button.grid(row=7, column=4, columnspan=4, padx=5, pady=5)

record_button = ttk.Button(frame, text="Record", width=25, command=toggle_record)
record_button.grid(row=8, column=0, columnspan=4, padx=5, pady=5)

playback_button = ttk.Button(frame, text="Playback", width=25, command=toggle_playback)
playback_button.grid(row=8, column=4, columnspan=4, padx=5, pady=5)

start()
root.mainloop()
