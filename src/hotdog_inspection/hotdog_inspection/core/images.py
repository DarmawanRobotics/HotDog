"""Camera frames as BGR arrays and JPEG evidence files (OpenCV, no ROS)."""

from __future__ import annotations

import numpy as np

# encoding -> (channels, name of the cv2 conversion to BGR or None)
ENCODINGS = {
    'rgb8': (3, 'COLOR_RGB2BGR'),
    'bgr8': (3, None),
    'rgba8': (4, 'COLOR_RGBA2BGR'),
    'bgra8': (4, 'COLOR_BGRA2BGR'),
    'mono8': (1, 'COLOR_GRAY2BGR'),
}


def to_bgr(encoding: str, height: int, width: int, step: int, data) -> np.ndarray | None:
    """Return a BGR copy of a raw image, None for an unsupported encoding or size."""
    import cv2

    spec = ENCODINGS.get(encoding.lower())
    if spec is None or height <= 0 or width <= 0 or step < width * spec[0]:
        return None
    channels, conversion = spec
    buffer = np.frombuffer(bytes(data), np.uint8)
    if buffer.size < height * step:
        return None
    rows = buffer[: height * step].reshape(height, step)
    img = rows[:, : width * channels].reshape(height, width, channels)
    img = img[:, :, 0] if channels == 1 else img
    return cv2.cvtColor(img, getattr(cv2, conversion)) if conversion else img.copy()


def write_jpeg(path: str, img: np.ndarray, quality: int = 90) -> bool:
    """Write img as a JPEG file; False when it cannot be encoded or written."""
    import cv2

    ok, buffer = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, int(quality)])
    if not ok:
        return False
    try:
        with open(path, 'wb') as f:
            f.write(buffer.tobytes())
    except OSError:
        return False
    return True
