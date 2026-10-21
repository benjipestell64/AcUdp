"""Assetto Corsa shared memory structures and helpers."""
import ctypes
import mmap
import time

import pygetwindow as gw


# Shared memory name for Assetto Corsa physics & graphics data
AC_PHYSICS_MEMORY_NAME = "Local\\acpmf_physics"
AC_GRAPHICS_MEMORY_NAME = "Local\\acpmf_graphics"


# Games that publish the acpmf_* shared memory (AC Rally uses the same layout)
DEFAULT_GAME_WINDOW_TITLES = ("Assetto Corsa", "Assetto Corsa Rally")
DEFAULT_GAME_PROCESS_NAMES = ("acs.exe", "acr.exe")


class _ProcessEntry32(ctypes.Structure):
    _fields_ = [
        ("dwSize", ctypes.c_ulong),
        ("cntUsage", ctypes.c_ulong),
        ("th32ProcessID", ctypes.c_ulong),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", ctypes.c_ulong),
        ("cntThreads", ctypes.c_ulong),
        ("th32ParentProcessID", ctypes.c_ulong),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", ctypes.c_ulong),
        ("szExeFile", ctypes.c_wchar * 260),
    ]


def get_running_process_names():
    """Return the lower-cased exe names of all running processes."""
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
    snapshot = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)  # TH32CS_SNAPPROCESS
    if snapshot in (None, ctypes.c_void_p(-1).value):
        return set()
    names = set()
    entry = _ProcessEntry32()
    entry.dwSize = ctypes.sizeof(_ProcessEntry32)
    try:
        ok = kernel32.Process32FirstW(ctypes.c_void_p(snapshot), ctypes.byref(entry))
        while ok:
            names.add(entry.szExeFile.lower())
            ok = kernel32.Process32NextW(ctypes.c_void_p(snapshot), ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(ctypes.c_void_p(snapshot))
    return names


# Check if a supported game is running, by process name or window title
def is_ac_running(window_titles=DEFAULT_GAME_WINDOW_TITLES, process_names=DEFAULT_GAME_PROCESS_NAMES):
    wanted = {name.strip().lower() for name in process_names}
    if wanted & get_running_process_names():
        return True
    wanted_titles = {title.strip().lower() for title in window_titles}
    return any(title.strip().lower() in wanted_titles for title in gw.getAllTitles())


def shared_memory_exists(name):
    """True if something (normally the game) has already created the named shared memory."""
    kernel32 = ctypes.windll.kernel32
    kernel32.OpenFileMappingW.restype = ctypes.c_void_p
    handle = kernel32.OpenFileMappingW(0x0004, False, name)  # FILE_MAP_READ
    if not handle:
        return False
    kernel32.CloseHandle(ctypes.c_void_p(handle))
    return True


def find_similar_windows(keywords=("assetto", "corsa", "rally", "acr"), exclude=()):
    """Return open window titles containing any keyword, to help configure game_window_titles."""
    return [title for title in gw.getAllTitles()
            if title not in exclude and any(keyword in title.lower() for keyword in keywords)]


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
