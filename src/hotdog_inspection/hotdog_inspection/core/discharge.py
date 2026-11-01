"""
Partial discharge detection at a target with the Hertzinno HZ-FA-371.

One detection, taken only after the robot stands at the target: a detection already running
is stopped first, the newest record before the start is noted, then a record that appeared at
least a whole detection time after the start (or once the camera stopped by itself) is the
result. Corona, surface and floating discharge each have a severity (config); the intensity
can raise it. The sound map and PRPD photos are kept as evidence.
"""

from __future__ import annotations

import os
import time

from hotdog_inspection.core.config import SEVERITIES, AcousticConfig
from hotdog_inspection.core.hertzino import (
    LEAKAGE,
    PARTIAL_DISCHARGE,
    HertzinoClient,
    HertzinoError,
    record_id,
    types_of,
)
from hotdog_inspection.core.plan import Target
from hotdog_inspection.core.thermal import Finding, Severity

PHOTOS = (('soundmap_photo_name', 'soundmap'), ('prpd_photo_name', 'prpd'))
POLL_SEC = 1.0


def judge(record: dict, config: AcousticConfig) -> tuple[Severity, str]:
    """Return the severity of a partial discharge record and its label."""
    types = [t for t in types_of(int(record.get('status', 0))) if t != 'noise']
    if not types:
        return Severity.NORMAL, 'noise'
    severity = max(Severity(SEVERITIES.index(getattr(config, t))) for t in types)
    intensity = float(record.get('soundmap_intensity', record.get('intensity', 0)) or 0)
    if config.intensity_critical > 0 and intensity >= config.intensity_critical:
        severity = Severity.CRITICAL
    elif config.intensity_warning > 0 and intensity >= config.intensity_warning:
        severity = max(severity, Severity.WARNING)
    return severity, '+'.join(types)


def finding(target: Target, record: dict, config: AcousticConfig) -> Finding:
    """Return the Finding of a record."""
    severity, label = judge(record, config)
    intensity = float(record.get('soundmap_intensity', record.get('intensity', 0)) or 0)
    probs = ', '.join(f'{name} {float(record.get(f"{name}_prob", 0) or 0):.2f}'
                      for name in ('noise', 'corona', 'surface', 'floating'))  # fmt: skip
    return Finding(target.name, 'acoustic', 'discharge', label, severity, intensity,
                   unit='dB', message=f'{label}, intensity {intensity:.0f} ({probs})')  # fmt: skip


class Detector:
    """Runs one detection on the camera and returns its record."""

    def __init__(self, client: HertzinoClient, config: AcousticConfig,
                 clock=time.monotonic, sleep=time.sleep):  # fmt: skip
        self.client, self.config, self.clock, self.sleep = client, config, clock, sleep

    def prepare(self, duration: float) -> int:
        """Check the mode, set the detection time and stop a running detection; return it."""
        system = self.client.system()
        if int(system.get('work_mode', PARTIAL_DISCHARGE)) == LEAKAGE:
            raise HertzinoError('the camera is in gas leak mode: switch it to partial discharge')
        seconds = max(1, round(duration))
        if int(system.get('detect_times', -1)) != seconds:
            self.client.set_duration(seconds)
        if self.client.detecting():
            self.client.stop()
            end = self.clock() + 2.0
            while self.clock() < end and self.client.detecting():
                self.sleep(0.2)
            self.sleep(0.5)  # its record, if any, lands before the start
        return seconds

    def detect(self, duration: float, cancelled=lambda: False) -> dict:
        """Return the record of one detection measured after now."""
        seconds = self.prepare(duration)
        before = max((record_id(r) for r in self.client.records()), default=-1)
        start = self.clock()
        self.client.start()
        try:
            return self.wait(start, seconds, before, cancelled)
        finally:
            self.client.stop()

    def wait(self, start: float, seconds: int, before: int, cancelled) -> dict:
        """Poll the records until the result of this detection appears."""
        seen: dict[int, float] = {}
        slack = min(1.0, 0.5 * seconds)
        deadline = start + seconds + self.config.margin_sec
        ended = False
        while self.clock() < deadline:
            if cancelled():
                raise HertzinoError('cancelled')
            self.sleep(POLL_SEC)
            now = self.clock() - start
            if now >= seconds - 1.0 and not ended:
                ended = not self.client.detecting()
            new = [r for r in self.client.records() if record_id(r) > before]
            for record in new:
                seen.setdefault(record_id(record), now)
            ready = [r for r in new if seen[record_id(r)] >= seconds - slack]
            if ready or (ended and new):
                return max(ready or new, key=record_id)
        raise HertzinoError(f'no result within {seconds + self.config.margin_sec:.0f} s')

    def photos(self, record: dict, prefix: str) -> list[str]:
        """Save the sound map and PRPD photos as <prefix>_soundmap.jpg, ...; return the files."""
        files = []
        folder = str(record.get('saving_path', ''))
        for key, suffix in PHOTOS:
            name = str(record.get(key, ''))
            data = self.fetch(folder, name) if folder and name else b''
            if data:
                path = f'{prefix}_{suffix}{os.path.splitext(name)[1] or ".jpg"}'
                with open(path, 'wb') as f:
                    f.write(data)
                files.append(os.path.abspath(path))
        return files

    def fetch(self, folder: str, name: str) -> bytes:
        """Return a file the camera may still be writing, b'' after photo_wait_sec."""
        end = self.clock() + self.config.photo_wait_sec
        while True:
            try:
                return self.client.file(folder, name)
            except HertzinoError:
                if self.clock() >= end:
                    return b''
                self.sleep(0.5)


class AcousticCheck:
    """The runner's per-target check: one detection for every acoustic target."""

    def __init__(self, detector: Detector, config: AcousticConfig, cancelled=lambda: False):
        self.detector, self.config, self.cancelled = detector, config, cancelled

    def __call__(self, target: Target, prefix: str, outcome):
        """Detect, judge and keep the photos; errors go to the outcome, never raise."""
        if not target.acoustic.enabled:
            return
        if not self.config.enabled:
            outcome.errors.append('acoustic: off')
            return
        duration = target.acoustic.duration_sec or self.config.duration_sec
        try:
            record = self.detector.detect(duration, self.cancelled)
            files = self.detector.photos(record, prefix)
        except (HertzinoError, OSError) as error:
            outcome.errors.append(f'acoustic: {error}')
            return
        outcome.findings.append(finding(target, record, self.config))
        outcome.files += files
        outcome.measured = outcome.measured or not target.thermal.enabled
