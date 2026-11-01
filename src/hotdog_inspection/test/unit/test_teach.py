"""inspection/add_target requests and evidence images (no ROS)."""

from __future__ import annotations

from types import SimpleNamespace

from hotdog_inspection.core.images import to_bgr, write_jpeg
from hotdog_inspection.core.plan import PlanError
from hotdog_inspection.utils.teach import target_of
import numpy as np
import pytest


def request(**fields):
    base = {'name': 'ds_clamps', 'point': '', 'thermal': True, 'acoustic': False,
            'strips': 3, 'max_temp_c': 0.0}  # fmt: skip
    return SimpleNamespace(**{**base, **fields})


def test_target_takes_the_pods_view():
    target = target_of(request(), 34.96, -12.04, 4.02)
    assert (target.pan_deg, target.tilt_deg, target.zoom) == (35.0, -12.0, 4.0)
    assert target.thermal.strips == 3 and not target.acoustic.enabled


def test_view_is_clamped_to_the_pod():
    target = target_of(request(), 0.0, -120.0, 0.5)
    assert (target.tilt_deg, target.zoom) == (-90.0, 1.0)


@pytest.mark.parametrize(
    ('fields', 'error'),
    [
        ({'name': 'DS 1'}, 'name'),
        ({'thermal': False, 'acoustic': False}, 'thermal, acoustic'),
        ({'max_temp_c': -5.0}, 'max_temp_c'),
    ],
)
def test_bad_requests(fields, error):
    with pytest.raises(PlanError, match=error):
        target_of(request(**fields), 0.0, 0.0, 1.0)


def test_images_to_jpeg(tmp_path):
    pytest.importorskip('cv2')
    rgb = np.zeros((4, 6, 3), np.uint8)
    rgb[..., 0] = 255  # red in rgb8
    bgr = to_bgr('rgb8', 4, 6, 18, rgb.tobytes())
    assert bgr.shape == (4, 6, 3) and bgr[0, 0].tolist() == [0, 0, 255]
    assert to_bgr('mono8', 4, 6, 6, bytes(24)).shape == (4, 6, 3)
    assert to_bgr('yuv422', 4, 6, 12, bytes(48)) is None
    assert to_bgr('bgr8', 4, 6, 18, bytes(10)) is None
    path = tmp_path / 'x.jpg'
    assert write_jpeg(str(path), bgr)
    assert path.read_bytes()[:2] == b'\xff\xd8'
    assert not write_jpeg(str(tmp_path / 'missing' / 'x.jpg'), bgr)
