import time
import socket
import csv
import os
import sys
import tkinter as tk
from tkinter import ttk
import threading

from ac_udp.settings import CONFIG_FILE, DEFAULT_SETTINGS, load_config
from ac_udp.packet_spec import load_forward_spec, load_packet_spec
from ac_udp.csv_logger import CSVLogger
from ac_udp.ac_shared_memory import (AC_PHYSICS_MEMORY_NAME, PHYSICS_DATA_SIZE, PhysicsData, get_physics_headers,
                                     find_similar_windows, is_ac_running, open_shared_memory, physics_to_row,
                                     row_to_physics, shared_memory_exists)
from ac_udp.motion_cues import get_angular_acceleration_demand, get_linear_acceleration_demand
from ac_udp.utils import attach_console, get_current_time_in_milliseconds, resource_path

# from receive import NSimRequest

# Packet layouts live in packets/*.json; pick one with [Packet] spec_file in config.txt
# Compile with: pyinstaller --onefile --windowed --add-data "dynisma.ico;." --path .\.venv\Lib\site-packages\ --icon .\dynisma.ico "Dynisma AC UDP interface.py"

# Load config if it exists, otherwise create it
config = load_config()

# Variables for recording and playback
recording = False
playback = False
recorded_data = []
playback_index = 0

# Read packet spec (which motion system we're talking to)
PACKET_SPEC_FILE = config.get('Packet', 'spec_file', fallback=DEFAULT_SETTINGS['Packet']['spec_file'])

# Read network settings
UDP_IP = config.get('Network', 'UDP_IP')
UDP_RECEIVE_IP = "0.0.0.0"
UDP_PORT = config.getint('Network', 'UDP_PORT')
TRANSMIT_TO_SELF = config.getboolean('Network', 'TRANSMIT_TO_SELF')

# Read OpenTrack forwarding settings (received platform pose -> OpenTrack "UDP over network" input)
OPENTRACK_ENABLED = config.getboolean('OpenTrack', 'enabled', fallback=DEFAULT_SETTINGS['OpenTrack']['enabled'] == 'True')
OPENTRACK_IP = config.get('OpenTrack', 'ip', fallback=DEFAULT_SETTINGS['OpenTrack']['ip'])
OPENTRACK_PORT = config.getint('OpenTrack', 'port', fallback=int(DEFAULT_SETTINGS['OpenTrack']['port']))

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
game_window_titles = tuple(title.strip() for title in config.get(
    'Processing', 'game_window_titles',
    fallback=DEFAULT_SETTINGS['Processing']['game_window_titles']).split(',') if title.strip())
game_process_names = tuple(name.strip() for name in config.get(
    'Processing', 'game_process_names',
    fallback=DEFAULT_SETTINGS['Processing']['game_process_names']).split(',') if name.strip())

# Read model constants
modelConstants = {key: (int(value) if value.isdigit() else float(value)) for key, value in
                  config.items('ModelConstants')}

nSimRequest = modelConstants['NSimRequest']
last_spec_signals = None  # Signals used for the last transmitted packet



def read_tuning(tuning_config):
    """Read the washout settings and steady state gains, which can be reloaded while running."""
    washout = {key: float(value) for key, value in tuning_config.items('WashoutSettings')}
    gains = {key: float(tuning_config.get('SteadyStateGains', key, fallback=default))
             for key, default in DEFAULT_SETTINGS['SteadyStateGains'].items()}
    return washout, gains


# Read washout settings and steady state gains
washoutSettings, steadyStateGains = read_tuning(config)

# Adjust IP if TRANSMIT_TO_SELF is True
if TRANSMIT_TO_SELF:
    UDP_IP = socket.gethostbyname(socket.gethostname())


try:
    PACKET_DESCRIPTION, TX_SPEC, RX_SPEC = load_packet_spec(PACKET_SPEC_FILE)
    FORWARD_SPEC = load_forward_spec(PACKET_SPEC_FILE) if OPENTRACK_ENABLED else None
except Exception as e:
    from tkinter import messagebox
    messagebox.showerror("Packet spec error", f"Could not load packet spec '{PACKET_SPEC_FILE}':\n\n{e}")
    sys.exit(1)

APP_WINDOW_TITLE = f"Assetto Corsa UDP Interface - {PACKET_DESCRIPTION}"

# Packet field names, used for CSV headers
TelemetryData = TX_SPEC.tuple
ControllerData = RX_SPEC.tuple


if debug_output:
    print("Debug output enabled.")
    attach_console()


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


# noinspection PyTypeChecker
def transmit_loop():
    """
    Main loop for transmitting telemetry data.

    This function continuously checks if Assetto Corsa is running, reads physics data from shared memory,
    constructs a telemetry data packet, and sends it via UDP. It also updates the UI and logs data if required.
    """
    # noinspection PyGlobalUndefined
    global running, last_spec_signals, nSimRequest

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # Setup initial values
    heartbeat = True
    last_packet_id = -1
    last_time = time.time()
    time_taken = 0

    while running:

        ac_was_running = True
        reported_windows = None
        while not is_ac_running(game_window_titles, game_process_names):
            searching_for_assetto()
            # Show near-miss window titles so game_window_titles can be corrected in config.txt
            similar_windows = find_similar_windows(exclude=(APP_WINDOW_TITLE,))
            if similar_windows != reported_windows:
                print(f"Looking for processes {list(game_process_names)} or windows {list(game_window_titles)}; "
                      f"similar open windows: {[repr(title) for title in similar_windows]}")
                reported_windows = similar_windows
            time.sleep(1)
            ac_was_running = False

        if not ac_was_running:
            # Assetto Corsa now launching
            for i in range(launch_wait_time):
                waiting_for_launch(launch_wait_time - i)
                time.sleep(1)
        running = True

        print("Assetto Corsa running.")
        if not playback:
            if shared_memory_exists(AC_PHYSICS_MEMORY_NAME):
                print(f"Shared memory {AC_PHYSICS_MEMORY_NAME} found.")
            else:
                print(f"Shared memory {AC_PHYSICS_MEMORY_NAME} has not been created by the game yet "
                      f"(it may only appear once you are on a stage).")
        last_new_packet_time = time.time()
        stale_reported = False

        check_counter = 0
        ac_running_cached = True  # assume running at this point

        while running and ac_running_cached:
            # Reduce the frequency of checking if AC is running
            if check_counter == 0:
                ac_running_cached = is_ac_running(game_window_titles, game_process_names)
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
                if stale_reported or last_packet_id == -1:
                    print(f"Receiving physics data (packet_id {physics_data.packet_id}, "
                          f"speed {physics_data.speed_kmh:.1f} km/h).")
                last_new_packet_time = time.time()
                stale_reported = False
                set_tx_activity_light(True)  # Activity light on
                last_packet_id = physics_data.packet_id
                heartbeat = not heartbeat  # Beat heart

                # Suppress demands if speed is below a threshold
                if physics_data.speed_kmh < 20.0:
                    g_long = g_lat = g_vert = 0.0
                    acc_roll = acc_pitch = acc_yaw = 0.0
                else:
                    # Filtered angular acceleration
                    acc_pitch, acc_yaw, acc_roll = get_angular_acceleration_demand(physics_data)

                    # Filtered linear accelerations
                    g_lat, g_vert, g_long = get_linear_acceleration_demand(physics_data)

                # Signals available to "value" expressions in the packet spec file
                spec_signals = {
                    "physics_data": physics_data,
                    "heartbeat": heartbeat,
                    "nSimRequest": nSimRequest,
                    "g_long": g_long, "g_lat": g_lat, "g_vert": g_vert,
                    "acc_roll": acc_roll, "acc_pitch": acc_pitch, "acc_yaw": acc_yaw,
                    "washoutSettings": washoutSettings,
                    "steadyStateGains": steadyStateGains,
                    "modelConstants": modelConstants,
                    "time_ms": get_current_time_in_milliseconds(),
                }
                last_spec_signals = spec_signals

                # Build and pack the tx buffer as defined by the packet spec
                txbuf = TX_SPEC.build(spec_signals)
                udp_packet = TX_SPEC.pack(txbuf)

                # hex_data = ' '.join(f'{byte:02X}' for byte in udp_packet)

                # Send UDP packet
                sock.sendto(udp_packet, (UDP_IP, UDP_PORT))

                # Update UI
                status_label.config(text="State: Run")
                speed_label.config(text=f"Speed: {int(physics_data.speed_kmh):03d} km/h")
                gear = physics_data.gear - 1
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
                if not stale_reported and time.time() - last_new_packet_time > 5:
                    print(f"No new physics data for 5 s (packet_id stuck at {physics_data.packet_id}). "
                          f"Is the game paused or in a menu? Shared memory present: "
                          f"{shared_memory_exists(AC_PHYSICS_MEMORY_NAME)}")
                    stale_reported = True


# noinspection PyGlobalUndefined,PyTypeChecker
def receive_loop():
    """
    Thread to listen for incoming UDP packets from the platform, for the lifetime of the app.

    Runs independently of the game and of Start/Stop, and forwards each packet (e.g. to OpenTrack) as soon as it
    arrives, so the forwarded pose follows the platform's clock rather than the game's.
    """
    start_time_ms = get_current_time_in_milliseconds()
    # Separate socket for forwarding: on Windows, an ICMP "port unreachable" from a send (OpenTrack not running)
    # would otherwise make the next recvfrom on the receive socket fail
    forward_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) if FORWARD_SPEC else None
    forward_error_reported = False
    if FORWARD_SPEC:
        print(f"Forwarding received platform pose to OpenTrack at {OPENTRACK_IP}:{OPENTRACK_PORT}.")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind((UDP_RECEIVE_IP, UDP_PORT))
        socket_bound = True
        set_rx_socket_bound_light(True)
    except OSError:
        print(f"Error: Receive loop unable to bind to {UDP_RECEIVE_IP}:{UDP_PORT}.")
        socket_bound = False
        set_rx_socket_bound_light(False)

    while socket_bound:
        try:
            data, addr = sock.recvfrom(65535)  # Full buffer so oversized packets are rejected, not an error
        except OSError as e:
            if debug_output:
                print(f"Receive error: {e}")
            continue
        if len(data) != RX_SPEC.size:
            if debug_output:
                print(f"Ignoring {len(data)} byte packet, expected {RX_SPEC.size} bytes")
            continue
        current_time_ms = get_current_time_in_milliseconds()
        timestamp = current_time_ms - start_time_ms

        received_data = RX_SPEC.unpack(data)

        if forward_sock:
            try:
                forward_packet = FORWARD_SPEC.build(received_data._asdict())
                forward_sock.sendto(FORWARD_SPEC.pack(forward_packet), (OPENTRACK_IP, OPENTRACK_PORT))
                forward_error_reported = False
            except (OSError, ValueError) as e:
                if not forward_error_reported:
                    print(f"OpenTrack forward failed: {e}")
                    forward_error_reported = True

        pulse_rx_activity_light()

        # received_tot = received_data.TransmitTimeTenMs / 10.0  # undo the 10x factor in the transmit loop
        # round_trip_time = current_time_ms - received_tot
        round_trip_time = "None"

        rx_timestamp_label.config(text=f"Timestamp: {timestamp / 1000}s")
        if csv_rx_logger:
            csv_rx_logger.log(received_data, [current_time_ms, round_trip_time])


def send_demand_packet():
    # if txbuf.vLongCar < 5:  # m/s
    #     txbuf.gLongDemand = 0
    #     txbuf.gLatDemand = 0
    #     txbuf.gVertDemand = 0
    #     txbuf.dnRollDemand = 0
    #     txbuf.dnPitchDemand = 0
    #     txbuf.dnYawDemand = 0
    #     txbuf.vLongDemand = 0
    #     txbuf.vLatDemand = 0
    #     txbuf.vVertDemand = 0

    if last_spec_signals is None:
        return  # Nothing transmitted yet

    # Rebuild the last packet with the new sim request
    udp_packet = TX_SPEC.pack(TX_SPEC.build(dict(last_spec_signals, nSimRequest=nSimRequest)))

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # Send UDP packet
    sock.sendto(udp_packet, (UDP_IP, UDP_PORT))


def request_park():
    global nSimRequest
    nSimRequest = 1  # Park
    send_demand_packet()


def request_centre():
    global nSimRequest
    nSimRequest = 2  # On centre
    send_demand_packet()


def request_target():
    global nSimRequest
    nSimRequest = 3  # Target following
    send_demand_packet()


# noinspection PyGlobalUndefined
def start():
    """
    Start the transmission of telemetry data.

    This function sets the `running` flag to True and starts the thread that transmits telemetry data
    (`transmit_thread`). The receive thread runs for the lifetime of the app and is started separately.
    """
    global running
    running = True
    transmit_thread = threading.Thread(target=transmit_loop, daemon=True)
    transmit_thread.start()


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


def reload_washouts():
    """Re-read washout settings and steady state gains from config.txt without restarting."""
    try:
        new_washout, new_gains = read_tuning(load_config())
    except Exception as e:
        from tkinter import messagebox
        messagebox.showerror("Reload failed", f"Could not read {CONFIG_FILE}; keeping current values.\n\n{e}")
        return
    changes = [f"{key}: {old.get(key)} -> {value}"
               for old, new in ((washoutSettings, new_washout), (steadyStateGains, new_gains))
               for key, value in new.items() if old.get(key) != value]
    # Update in place (no clear, so the transmit loop never sees a missing key) for the next packet
    washoutSettings.update(new_washout)
    steadyStateGains.update(new_gains)
    print("Reloaded washouts / gains:", "; ".join(changes) if changes else "no changes")


def toggle_record():
    global recording, recorded_data
    prev_packet_id = None
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
                if data[0] != prev_packet_id:
                    writer.writerow(data)
                prev_packet_id = data[0]  # Packet ID from data
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


root = tk.Tk()
root.title(APP_WINDOW_TITLE)
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

config_button = ttk.Button(frame, text="Configure ⚙️", width=25, command=lambda: os.system(f"start {CONFIG_FILE}"))
config_button.grid(row=6, column=0, columnspan=4, padx=5, pady=5)

reload_button = ttk.Button(frame, text="Reload washouts / gains", width=25, command=reload_washouts)
reload_button.grid(row=6, column=4, columnspan=4, padx=5, pady=5)

start_button = ttk.Button(frame, text="Start", width=25, command=start)
start_button.grid(row=7, column=0, columnspan=4, padx=5, pady=5)

stop_button = ttk.Button(frame, text="Stop", width=25, command=stop)
stop_button.grid(row=7, column=4, columnspan=4, padx=5, pady=5)

record_button = ttk.Button(frame, text="Record", width=25, command=toggle_record)
record_button.grid(row=8, column=0, columnspan=4, padx=5, pady=5)

playback_button = ttk.Button(frame, text="Playback", width=25, command=toggle_playback)
playback_button.grid(row=8, column=4, columnspan=4, padx=5, pady=5)

# 1: Park request, 2: On centre request, 3: Target follow request
request_label = ttk.Label(frame, text="Platform request: ")
request_label.grid(row=9, column=0, columnspan=8, padx=5, pady=5, sticky="w")

park_button = ttk.Button(frame, text="Park", width=15, command=request_park)
park_button.grid(row=10, column=0, columnspan=2, padx=5, pady=5)

centre_button = ttk.Button(frame, text="On centre", width=15, command=request_centre)
centre_button.grid(row=10, column=2, columnspan=2, padx=5, pady=5)

target_button = ttk.Button(frame, text="Target follow", width=15, command=request_target)
target_button.grid(row=10, column=4, columnspan=2, padx=5, pady=5)

# Receive (and forward to OpenTrack) for the whole lifetime of the app, independent of the game and Start/Stop
threading.Thread(target=receive_loop, daemon=True).start()
start()
root.mainloop()
