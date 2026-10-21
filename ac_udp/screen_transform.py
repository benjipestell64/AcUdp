"""
Turn the platform pose into the camera pose a world-fixed screen needs.

The cockpit moves with the platform but the screen is fixed in the room. The virtual world has to stay consistent with
the cockpit (it stands in for the car), so the image must be rendered from the driver's eye, which is fixed in the
cockpit, onto the screen as it sits relative to the cockpit right now. When the platform rotates, the screen rotates the
opposite way relative to the driver, so the camera does too, by the full amount. When the eye moves relative to the
screen (platform translation, or rotation with the eye away from the pivot), the screen centre is no longer straight
ahead, so the camera is aimed at it. The game can only point its camera (no off-axis projection), so aiming at the
screen centre is the closest it can get, and that's where the screen distance comes in.

The eye doesn't move relative to the cockpit, so the camera isn't translated.

Axes follow ISO 8855, the same as the platform pose: x forward, y left, z up; roll about x, pitch about y, yaw about z.
"""
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class ScreenGeometry:
    enabled: bool = True
    screen_distance_m: float = 1.5  # Screen centre, straight ahead of the eye with the platform at rest
    eye_offset_m: tuple = (0.0, 0.0, 0.0)  # Eye relative to the platform pose reference point (x fwd, y left, z up)


def rotation_matrix(roll, pitch, yaw):
    """R = Rz(yaw) * Ry(pitch) * Rx(roll), as rows."""
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    return ((cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr),
            (sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr),
            (-sp, cp * sr, cp * cr))


def euler_angles(matrix):
    """Inverse of rotation_matrix: (roll, pitch, yaw)."""
    pitch = math.asin(max(-1.0, min(1.0, -matrix[2][0])))
    return math.atan2(matrix[2][1], matrix[2][2]), pitch, math.atan2(matrix[1][0], matrix[0][0])


def multiply(matrix, vector):
    return tuple(sum(matrix[row][i] * vector[i] for i in range(3)) for row in range(3))


def multiply_transposed(matrix, vector):
    return tuple(sum(matrix[i][column] * vector[i] for i in range(3)) for column in range(3))


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def normalise(v):
    length = math.sqrt(sum(c * c for c in v))
    return tuple(c / length for c in v)


def view_pose(geometry, x_long, x_lat, x_vert, a_roll, a_pitch, a_yaw):
    """
    Camera pose for the platform pose (metres, radians), as a dict of long_m, lat_m, vert_m, roll_rad, pitch_rad
    and yaw_rad. With the transform disabled, the platform pose is passed through unchanged.
    """
    if not geometry.enabled:
        return {"long_m": x_long, "lat_m": x_lat, "vert_m": x_vert,
                "roll_rad": a_roll, "pitch_rad": a_pitch, "yaw_rad": a_yaw}

    platform = rotation_matrix(a_roll, a_pitch, a_yaw)
    eye = geometry.eye_offset_m

    # Screen centre in room coordinates (origin at the platform reference point at rest), then in cockpit coordinates
    screen_room = (eye[0] + geometry.screen_distance_m, eye[1], eye[2])
    screen_cockpit = multiply_transposed(platform, (screen_room[0] - x_long, screen_room[1] - x_lat,
                                                    screen_room[2] - x_vert))

    # Camera looks from the eye at the screen centre, with its up matching the screen's up (so roll follows the screen)
    forward = normalise(tuple(screen_cockpit[i] - eye[i] for i in range(3)))
    screen_up = multiply_transposed(platform, (0.0, 0.0, 1.0))
    left = normalise(cross(screen_up, forward))
    up = cross(forward, left)
    camera = tuple(tuple((forward, left, up)[column][row] for column in range(3)) for row in range(3))
    roll, pitch, yaw = euler_angles(camera)

    return {"long_m": 0.0, "lat_m": 0.0, "vert_m": 0.0,
            "roll_rad": roll, "pitch_rad": pitch, "yaw_rad": yaw}
