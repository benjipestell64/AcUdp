import mmap
import struct
import time
import ctypes

# Shared memory file name for Assetto Corsa telemetry data
AC_SHARED_MEMORY_NAME = "Local\\acpmf_physics"

# Define the structure of the telemetry data
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
        ("best_lap", ctypes.c_int)
    ]

# Correct way to get the structure size
PHYSICS_DATA_SIZE = ctypes.sizeof(PhysicsData)

# Open shared memory
try:
    file_handle = mmap.mmap(-1, PHYSICS_DATA_SIZE, AC_SHARED_MEMORY_NAME, access=mmap.ACCESS_READ)
except FileNotFoundError:
    print("Assetto Corsa shared memory not found. Is the game running?")
    exit(1)

last_packet_id = -1

print("Reading telemetry data from Assetto Corsa...\n")

while True:
    file_handle.seek(0)  # Reset read position
    raw_data = file_handle.read(PHYSICS_DATA_SIZE)

    # Unpack the raw data
    physics_data = PhysicsData.from_buffer_copy(raw_data)

    if physics_data.packet_id != last_packet_id:  # Update only on new packet
        last_packet_id = physics_data.packet_id

        # Clear console
        print("\033[H\033[J", end="")
        print(f"Packet ID: {physics_data.packet_id}")
        print(f"Speed: {physics_data.speed * 3.6:.1f} km/h")  # Convert from m/s to km/h
        print(f"RPM: {physics_data.rpms}")
        print(f"Gear: {physics_data.gear}")
        print(f"Throttle: {physics_data.gas * 100:.1f}%")
        print(f"Brake: {physics_data.brake * 100:.1f}%")
        print(f"Fuel: {physics_data.fuel:.2f} L")
        print(f"Steering Angle: {physics_data.steer_angle:.1f}°")
        print(f"Tyre Temperatures: {[round(t, 1) for t in physics_data.tyre_temp]}")
        print(f"Lap Time: {physics_data.lap_time / 1000:.3f} s")
        print(f"Last Lap: {physics_data.last_lap / 1000:.3f} s")
        print(f"Best Lap: {physics_data.best_lap / 1000:.3f} s")

    time.sleep(0.01)  # Small delay to prevent excessive CPU usage
