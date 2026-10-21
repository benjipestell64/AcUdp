"""
Turn the platform pose into the camera pose for the screen in front of the driver.

The car camera moves with the platform: translation and rotation are passed through 1:1. The platform rotates about
its centre, but the screen is in front of it, so the camera follows a point fixed to the platform at the screen offset.
Rotating the platform swings that point around the centre, which adds a translation (e.g. yawing by theta with the
screen 1.5 m ahead moves it 1.5 * sin(theta) sideways).

Axes follow ISO 8855, the same as the platform pose: x forward, y left, z up; roll about x, pitch about y, yaw about z.
"""
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class ScreenGeometry:
    enabled: bool = True
    screen_offset_m: tuple = (1.5, 0.0, 0.0)  # Screen relative to the platform centre (x fwd, y left, z up)


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

    # Platform translation plus the screen point swinging about the platform centre
    offset = geometry.screen_offset_m
    rotated = rotate(a_roll, a_pitch, a_yaw, offset)
    return {"long_m": x_long + rotated[0] - offset[0],
            "lat_m": x_lat + rotated[1] - offset[1],
            "vert_m": x_vert + rotated[2] - offset[2],
            "roll_rad": a_roll, "pitch_rad": a_pitch, "yaw_rad": a_yaw}
