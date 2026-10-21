"""Filtered motion demands derived from AC physics telemetry."""
import math
import time


# Low-pass filter cutoffs (Hz) per AC axis, set from [MotionFilters] in config.txt via set_filter_cutoffs.
# AC orders angular vectors [pitch, yaw, roll] and acc_g [lat, vert, long]. 0 disables filtering on that axis.
angular_cutoffs_hz = [5.0, 3.0, 5.0]
linear_cutoffs_hz = [15.0, 15.0, 15.0]


def set_filter_cutoffs(angular, linear):
    """Set cutoffs (Hz) as (roll, pitch, yaw) and (long, lat, vert), mapped to AC's axis order."""
    global angular_cutoffs_hz, linear_cutoffs_hz
    roll, pitch, yaw = angular
    long, lat, vert = linear
    # Replace the lists whole, so the transmit loop never sees a half-updated set
    angular_cutoffs_hz = [pitch, yaw, roll]
    linear_cutoffs_hz = [lat, vert, long]


def low_pass(previous, raw, cutoff_hz, dt):
    """
    First-order low-pass filter step. Using the real dt keeps the cutoff the same whatever the game's packet rate,
    unlike a fixed per-packet alpha.
    """
    if cutoff_hz <= 0:
        return raw
    alpha = 1.0 - math.exp(-2.0 * math.pi * cutoff_hz * dt)
    return previous + alpha * (raw - previous)


# Define global state variables
prev_ang_vel = [0.0, 0.0, 0.0]
prev_time = time.perf_counter()
filtered_ang_acc = [0.0, 0.0, 0.0]  # Low-pass filtered angular acceleration


def get_angular_acceleration_demand(physics_data):
    global prev_ang_vel, prev_time, filtered_ang_acc

    # Current angular velocity (rad/s)
    ang_vel = physics_data.local_angular_vel
    # perf_counter, not time.time: on Windows time.time can tick in 1-15.6 ms steps, which is coarser than
    # AC's ~3 ms physics step, so dt (and the differentiated acceleration) would jump around
    current_time = time.perf_counter()
    dt = current_time - prev_time

    if dt <= 0.0001:
        dt = 0.001

    # Calculate raw angular acceleration (rad/s²)
    raw_ang_acc = [
        (ang_vel[i] - prev_ang_vel[i]) / dt
        for i in range(3)
    ]

    # Apply deadzone
    noise_threshold = 0.005
    raw_ang_acc = [acc if abs(acc) >= noise_threshold else 0.0 for acc in raw_ang_acc]

    # Low-pass filter: differentiating turns steps in yaw rate (e.g. keyboard steering) into spikes
    cutoffs = angular_cutoffs_hz
    filtered_ang_acc = [
        low_pass(filtered_ang_acc[i], raw_ang_acc[i], cutoffs[i], dt)
        for i in range(3)
    ]

    # Update previous values
    prev_ang_vel = list(ang_vel)
    prev_time = current_time

    return filtered_ang_acc


prev_lin_vel = [0.0, 0.0, 0.0]
filtered_lin_acc = [0.0, 0.0, 0.0]
prev_time_lin = time.perf_counter()


def get_linear_acceleration_demand(physics_data):
    global prev_lin_vel, prev_time_lin, filtered_lin_acc

    current_time = time.perf_counter()
    dt = current_time - prev_time_lin
    if dt <= 0.0001:
        dt = 0.001

    # # Current linear velocity (m/s) — change to whatever your API uses
    # lin_vel = physics_data.local_velocity  # e.g. [vx, vy, vz]
    #
    # # Raw linear acceleration (m/s²)
    # raw_lin_acc = [
    #     (lin_vel[i] - prev_lin_vel[i]) / dt
    #     for i in range(3)
    # ]

    raw_lin_acc = physics_data.acc_g

    # Deadzone to kill noise
    noise_threshold = 0.005
    raw_lin_acc = [acc if abs(acc) >= noise_threshold else 0.0 for acc in raw_lin_acc]

    # Low-pass filter
    cutoffs = linear_cutoffs_hz
    filtered_lin_acc = [
        low_pass(filtered_lin_acc[i], raw_lin_acc[i], cutoffs[i], dt)
        for i in range(3)
    ]

    # # Update previous values
    # prev_lin_vel = list(lin_vel)
    prev_time_lin = current_time

    return filtered_lin_acc  # [ax, ay, az] filtered
