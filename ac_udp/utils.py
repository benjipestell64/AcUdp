"""Small general-purpose helpers."""
import ctypes
import os
import sys
from datetime import datetime
from datetime import time as dt_time


def attach_console():
    if not ctypes.windll.kernel32.AllocConsole():
        # Console already exists or failed — could try FreeConsole + AllocConsole if needed
        return
    sys.stdout = open('CONOUT$', 'w')
    sys.stderr = open('CONOUT$', 'w')
    sys.stdin = open('CONIN$', 'r')
    print("Debug console attached! (can disable in config)")


def get_current_time_in_milliseconds() -> int:
    """Returns the current time of day in milliseconds (since midnight)."""
    now = datetime.now()
    midnight = datetime.combine(now.date(), dt_time(0))
    return int((now - midnight).total_seconds() * 1000)


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
