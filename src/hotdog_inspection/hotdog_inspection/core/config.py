"""Configuration of inspection_node: sites and reports, the pod, thermal criteria, timing."""

from __future__ import annotations

from dataclasses import dataclass

from dharma_utils.config import nested, param


def ordered(levels) -> list[str]:
    """Return a problem unless attention <= warning <= critical."""
    ok = levels.attention <= levels.warning <= levels.critical
    return [] if ok else ['attention <= warning <= critical']


@dataclass(frozen=True)
class AbsoluteLevels:
    """Hottest temperature itself (degC; a target's max_temp_c replaces critical)."""

    attention: float = param(80.0, min=0.0, max=500.0, unit='degC', doc='possible deficiency')
    warning: float = param(90.0, min=0.0, max=500.0, unit='degC', doc='probable deficiency')
    critical: float = param(105.0, min=0.0, max=500.0, unit='degC', doc='major deficiency')

    def validate(self) -> list[str]:
        """Return cross-field problems."""
        return ordered(self)


@dataclass(frozen=True)
class AmbientLevels:
    """Hottest temperature over the ambient (NETA MTS: 1-10, 11-20, 21-40, > 40 degC)."""

    attention: float = param(11.0, min=0.0, max=500.0, unit='degC', doc='possible deficiency')
    warning: float = param(21.0, min=0.0, max=500.0, unit='degC', doc='probable deficiency')
    critical: float = param(41.0, min=0.0, max=500.0, unit='degC', doc='major deficiency')

    def validate(self) -> list[str]:
        """Return cross-field problems."""
        return ordered(self)


@dataclass(frozen=True)
class SimilarLevels:
    """Hottest of similar components over the others (NETA MTS: 1-3, 4-15, > 15 degC)."""

    attention: float = param(2.0, min=0.0, max=500.0, unit='degC', doc='possible deficiency')
    warning: float = param(4.0, min=0.0, max=500.0, unit='degC', doc='probable deficiency')
    critical: float = param(16.0, min=0.0, max=500.0, unit='degC', doc='major deficiency')

    def validate(self) -> list[str]:
        """Return cross-field problems."""
        return ordered(self)


@dataclass(frozen=True)
class ThermalConfig:
    """How temperatures are measured and judged."""

    ambient_c: float = param(
        30.0, min=-40.0, max=60.0, unit='degC', doc='air temperature at the site (live: set it)'
    )
    width: int = param(640, min=16, max=4096, doc='thermal image width (pod temperature pixels)')
    height: int = param(512, min=16, max=4096, doc='thermal image height')
    samples: int = param(3, min=1, max=20, doc='measurements per region; the median is used')
    sample_interval_sec: float = param(
        0.3, min=0.0, max=5.0, unit='s', doc='between two measurements'
    )
    refresh_shutter: bool = param(True, doc='flat-field correction once per point, before')
    absolute: AbsoluteLevels = nested(AbsoluteLevels)
    ambient: AmbientLevels = nested(AmbientLevels)
    similar: SimilarLevels = nested(SimilarLevels)


@dataclass(frozen=True)
class PodConfig:
    """The UniPod MT11 driver (unipod_driver) and how long it takes to settle."""

    namespace: str = param('/unipod', live=False, doc='unipod_driver namespace')
    thermal_image: str = param(
        'sub/image_raw', live=False, doc='thermal camera image in the namespace (video2)'
    )
    visible_image: str = param(
        'main/image_raw', live=False, doc='zoom camera image in the namespace (video1)'
    )
    call_timeout_sec: float = param(3.0, min=0.1, max=30.0, unit='s', doc='each pod service call')
    settle_sec: float = param(
        2.5, min=0.0, max=30.0, unit='s', doc='after pointing and zooming, before measuring'
    )
    image_timeout_sec: float = param(
        3.0, min=0.1, max=30.0, unit='s', doc='wait this long for a fresh image'
    )
    recenter_after: bool = param(True, doc='point the pod back to its centre after a point')
    jpeg_quality: int = param(90, min=10, max=100, doc='evidence images')


SEVERITIES = ('normal', 'attention', 'warning', 'critical')


@dataclass(frozen=True)
class AcousticConfig:
    """The Hertzinno HZ-FA-371 (partial discharge) and how its results are judged."""

    enabled: bool = param(True, doc='false: acoustic targets are skipped')
    host: str = param('192.168.2.204', live=False, doc='camera address (factory 192.168.2.204)')
    port: int = param(80, min=1, max=65535, live=False, doc='HTTP port')
    user: str = param('admin', live=False, doc='login user; the password: $HERTZINO_PASSWORD')
    timeout_sec: float = param(5.0, min=0.5, max=60.0, unit='s', doc='each HTTP request')
    duration_sec: float = param(
        5.0, min=1.0, max=60.0, unit='s', doc='detection time when the target sets none'
    )
    margin_sec: float = param(
        15.0, min=1.0, max=120.0, unit='s', doc='wait this long for the result after the time'
    )
    photo_wait_sec: float = param(
        8.0, min=0.0, max=60.0, unit='s', doc='retry photos the camera is still writing'
    )
    corona: str = param('attention', choices=SEVERITIES, doc='severity of corona discharge')
    surface: str = param('warning', choices=SEVERITIES, doc='severity of surface discharge')
    floating: str = param('critical', choices=SEVERITIES, doc='severity of floating discharge')
    intensity_warning: float = param(
        0.0, min=0.0, max=1000.0, doc='a discharge at least this intense is a warning; 0: off'
    )
    intensity_critical: float = param(
        0.0, min=0.0, max=1000.0, doc='a discharge at least this intense is critical; 0: off'
    )


@dataclass(frozen=True)
class InspectionConfig:
    """Everything inspection_node reads."""

    enabled: bool = param(True, doc='false: stop points pass without inspection')
    sites_dir: str = param(
        '~/.hotdog/sites', live=False, doc='<site>/inspection.yaml holds the points and targets'
    )
    reports_dir: str = param('~/.hotdog/reports', live=False, doc='one folder per inspection')
    match_radius_m: float = param(
        1.5, min=0.1, max=10.0, unit='m', doc='a stop this close to a point inspects it'
    )
    max_duration_sec: float = param(
        150.0, min=5.0, max=1800.0, unit='s', doc='one point; later targets are skipped'
    )
    stop_max_age_sec: float = param(
        60.0, min=1.0, max=3600.0, unit='s', doc='a stop point event older than this is stale'
    )
    pod: PodConfig = nested(PodConfig)
    thermal: ThermalConfig = nested(ThermalConfig)
    acoustic: AcousticConfig = nested(AcousticConfig)
