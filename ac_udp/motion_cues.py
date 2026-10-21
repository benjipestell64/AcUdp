"""Filtered motion demands derived from AC physics telemetry."""
import time


# Define global state variables
prev_ang_vel = [0.0, 0.0, 0.0]
prev_time = time.time()
filtered_ang_acc = [0.0, 0.0, 0.0]  # Low-pass filtered angular acceleration


def get_angular_acceleration_demand(physics_data):
    global prev_ang_vel, prev_time, filtered_ang_acc

    # Current angular velocity (rad/s)
    ang_vel = physics_data.local_angular_vel
    current_time = time.time()
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

    # Low-pass filter (tunable alpha, e.g., 0.1 = heavy filtering)
    alpha = 0.3
    filtered_ang_acc = [
        alpha * raw_ang_acc[i] + (1 - alpha) * filtered_ang_acc[i]
        for i in range(3)
    ]

    # Update previous values
    prev_ang_vel = list(ang_vel)
    prev_time = current_time

    return filtered_ang_acc


prev_lin_vel = [0.0, 0.0, 0.0]
filtered_lin_acc = [0.0, 0.0, 0.0]
prev_time_lin = time.time()


def get_linear_acceleration_demand(physics_data):
    global prev_lin_vel, prev_time_lin, filtered_lin_acc

    # # Current linear velocity (m/s) — change to whatever your API uses
    # lin_vel = physics_data.local_velocity  # e.g. [vx, vy, vz]
    # current_time = time.time()
    # dt = current_time - prev_time_lin
    # if dt <= 0.0001:
    #     dt = 0.001
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
    alpha = 0.3
    filtered_lin_acc = [
        alpha * raw_lin_acc[i] + (1 - alpha) * filtered_lin_acc[i]
        for i in range(3)
    ]

    # # Update previous values
    # prev_lin_vel = list(lin_vel)
    # prev_time_lin = current_time

    return filtered_lin_acc  # [ax, ay, az] filtered
