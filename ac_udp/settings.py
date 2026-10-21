"""Default settings and loading of config.txt."""
import configparser
import os


DEFAULT_SETTINGS = {
    'Packet': {
        'spec_file': 'packets/DMG-1.json'
    },
    'Network': {
        'UDP_IP': '192.168.17.190',
        'UDP_PORT': '10000',
        'TRANSMIT_TO_SELF': 'False'
    },
    'OpenTrack': {
        'enabled': 'True',
        'ip': '127.0.0.1',
        'port': '4242'
    },
    'ScreenTransform': {
        'enabled': 'True',
        'screen_distance_mm': '1500',
        'eye_offset_long_mm': '0',
        'eye_offset_lat_mm': '0',
        'eye_offset_vert_mm': '0'
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
        'launch_wait_time': '10',
        'game_window_titles': 'Assetto Corsa, Assetto Corsa Rally',
        'game_process_names': 'acs.exe, acr.exe'
    },
    'ModelConstants': {
        'MotionConsent': '1',
        'NSimRequest': '1',
        'SteeringTorqueEnableRequest': '0',
        'TorqueMultiplier': '1.0'
    },
    'WashoutSettings': {
        'rWashoutLong': '1', 'rWashoutLat': '1', 'rWashoutVert': '1',
        'rWashoutRoll': '1', 'rWashoutPitch': '1', 'rWashoutYaw': '1',
        'fWashoutLong': '1', 'fWashoutLat': '2', 'fWashoutVert': '2',
        'fWashoutRoll': '1.5', 'fWashoutPitch': '1.5', 'fWashoutYaw': '0.5',
        'zetaWashoutLong': '3', 'zetaWashoutLat': '2', 'zetaWashoutVert': '4',
        'zetaWashoutRoll': '4', 'zetaWashoutPitch': '3', 'zetaWashoutYaw': '2'
    },
    'SteadyStateGains': {
        'aRoll': '0.3', 'aPitch': '0.3', 'aYaw': '0'
    }
}

CONFIG_FILE = 'config.txt'


def load_config():
    """Load config.txt, creating it with default settings if it doesn't exist."""
    config = configparser.ConfigParser()
    config.optionxform = str  # Preserve original case of keys
    if not os.path.exists(CONFIG_FILE):
        print(f"{CONFIG_FILE} not found. Creating with default settings.")
        config.read_dict(DEFAULT_SETTINGS)
        with open(CONFIG_FILE, 'w') as configfile:
            # noinspection PyTypeChecker
            config.write(configfile)

    config.read(CONFIG_FILE)
    return config
