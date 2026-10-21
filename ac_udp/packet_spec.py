"""UDP packet layouts loaded from packets/*.json, so each motion system's interface can be swapped."""
import json
import math
import os
import struct
import types
from collections import namedtuple


# PLC type -> struct format character. No padding is inserted, matching TwinCAT pack_mode 1.
PLC_TYPES = {
    "BOOL": "?", "BYTE": "B", "USINT": "B", "SINT": "b",
    "WORD": "H", "UINT": "H", "INT": "h",
    "DWORD": "I", "UDINT": "I", "DINT": "i",
    "REAL": "f", "LREAL": "d",
}

# Integer ranges, so out-of-range values are clamped rather than crashing struct.pack
INT_RANGES = {
    "b": (-2 ** 7, 2 ** 7 - 1), "B": (0, 2 ** 8 - 1),
    "h": (-2 ** 15, 2 ** 15 - 1), "H": (0, 2 ** 16 - 1),
    "i": (-2 ** 31, 2 ** 31 - 1), "I": (0, 2 ** 32 - 1),
}

# Builtins available to "value" expressions in a packet spec
SPEC_BUILTINS = {"abs": abs, "min": min, "max": max, "int": int, "float": float, "round": round, "bool": bool,
                 "math": math}


class PacketSpec:
    """
    One direction (transmit or receive) of a packet spec file.

    Each field has a "name" and a PLC "type". Transmit fields also have a "value": either a constant, or a
    Python expression evaluated against the signals passed to build() (see transmit_loop for what's available).
    """

    def __init__(self, tuple_name, section, source):
        self.fields = section["fields"]
        self.tuple = namedtuple(tuple_name, [field["name"] for field in self.fields])
        try:
            type_chars = [PLC_TYPES[field["type"].upper()] for field in self.fields]
        except KeyError as e:
            raise ValueError(f"{source}: unknown PLC type {e}. Supported: {', '.join(PLC_TYPES)}")
        self.format = section.get("byte_order", "<") + "".join(type_chars)
        self.size = struct.calcsize(self.format)

        self._values = []
        for field, type_char in zip(self.fields, type_chars):
            value = field.get("value", 0)
            if isinstance(value, str):
                value = compile(value, f"{source}:{field['name']}", "eval")
            self._values.append((field["name"], value, type_char))

    def build(self, signals):
        """Evaluate every field's value against signals and return the packet as a namedtuple."""
        values = []
        for name, value, type_char in self._values:
            if isinstance(value, types.CodeType):
                try:
                    value = eval(value, {"__builtins__": SPEC_BUILTINS}, signals)
                except Exception as e:
                    raise ValueError(f"Packet spec field '{name}' failed: {e}") from e
            if type_char == "?":
                value = bool(value)
            elif type_char in INT_RANGES:
                low, high = INT_RANGES[type_char]
                value = max(low, min(high, int(value)))
            else:
                value = float(value)
            values.append(value)
        return self.tuple(*values)

    def pack(self, packet):
        return struct.pack(self.format, *packet)

    def unpack(self, data):
        return self.tuple(*struct.unpack(self.format, data))


def load_packet_spec(path):
    """Load a packet spec JSON file, returning (description, transmit spec, receive spec)."""
    with open(path, encoding="utf-8") as f:
        spec = json.load(f)
    return (spec.get("description", os.path.basename(path)),
            PacketSpec("TelemetryData", spec["transmit"], path),
            PacketSpec("ControllerData", spec["receive"], path))
