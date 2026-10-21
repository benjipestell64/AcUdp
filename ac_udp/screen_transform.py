"""
Turn the platform pose into the camera pose a world-fixed screen needs.

The driver's eye moves with the platform but the screen doesn't, so the image should be rendered from where the eye
actually is relative to the screen, as if looking through a window. The game can only move and point its camera (no
off-axis projection), so the camera is placed at the eye and aimed at the screen centre. This keeps distant objects
where they should be on the screen. Turning your head doesn't change what a window shows, so platform rotation only
matters through how it moves the eye.

Axes follow ISO 8855, the same as the platform pose: x forward, y left, z up; roll about x, pitch about y, yaw about z.
"""
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class ScreenGeometry:
    enabled: bool = True
    screen_distance_m: float = 1.5  # Screen centre, straight ahead of the eye with the platform at rest
    eye_offset_m: tuple = (0.0, 0.0, 0.0)  # Eye relative to the platform pose reference point (x fwd, y left, z up)


def rotate(roll, pitch, yaw, vector):
    """Apply the rotation R = Rz(yaw) * Ry(pitch) * Rx(roll) to a 3-vector."""
    x, y, z = vector
    # Roll about x
    cr, sr = math.cos(roll), math.sin(roll)
    y, z = cr * y - sr * z, sr * y + cr * z
    # Pitch about y
    cp, sp = math.cos(pitch), math.sin(pitch)
    x, z = cp * x + sp * z, -sp * x + cp * z
    # Yaw about z
    cy, sy = math.cos(yaw), math.sin(yaw)
    x, y = cy * x - sy * y, sy * x + cy * y
    return x, y, z


def view_pose(geometry, x_long, x_lat, x_vert, a_roll, a_pitch, a_yaw):
    """
    Camera pose for the platform pose (metres, radians), as a dict of long_m, lat_m, vert_m, roll_rad, pitch_rad
    and yaw_rad. With the transform disabled, the platform pose is passed through unchanged.
    """
    if not geometry.enabled:
        return {"long_m": x_long, "lat_m": x_lat, "vert_m": x_vert,
                "roll_rad": a_roll, "pitch_rad": a_pitch, "yaw_rad": a_yaw}

    # Eye displacement from its rest position: platform translation plus the eye swinging about the reference point
    offset = geometry.eye_offset_m
    rotated = rotate(a_roll, a_pitch, a_yaw, offset)
    eye_long = x_long + rotated[0] - offset[0]
    eye_lat = x_lat + rotated[1] - offset[1]
    eye_vert = x_vert + rotated[2] - offset[2]

    # Aim from the eye at the screen centre, which stays at (screen_distance, 0, 0) relative to the rest eye position
    to_long = geometry.screen_distance_m - eye_long
    to_lat = -eye_lat
    to_vert = -eye_vert
    yaw = math.atan2(to_lat, to_long)
    pitch = -math.atan2(to_vert, math.hypot(to_long, to_lat))  # ISO: positive pitch is nose down

    return {"long_m": eye_long, "lat_m": eye_lat, "vert_m": eye_vert,
            "roll_rad": 0.0, "pitch_rad": pitch, "yaw_rad": yaw}
