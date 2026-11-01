"""scripts/timesync.sh against stub chronyc, systemctl, ip and ptp4l in a test /etc."""

from __future__ import annotations

import os
from pathlib import Path
import stat
import subprocess

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / 'timesync.sh'

TRACKING = """Reference ID    : C0A87B01 (192.168.123.1)
Stratum         : 3
System time     : {offset} seconds {side} of NTP time
Leap status     : {leap}
"""

STUBS = {
    'chronyc': 'cat "$FAKE/tracking" 2>/dev/null || exit 1',
    'systemctl': 'echo "$*" >> "$FAKE/systemctl.log"\n'
    '[[ "$1" == is-active ]] && exit "$(cat "$FAKE/active" 2>/dev/null || echo 0)"\nexit 0',
    'ip': '[[ -f "$FAKE/noroute" ]] || echo "192.168.123.20 dev eth7 src 192.168.123.10 uid 0"',
    'ptp4l': 'cat "$FAKE/ptp_version"',
}


@pytest.fixture
def rig(tmp_path):
    fake = tmp_path / 'fake'
    bin_dir = fake / 'bin'
    bin_dir.mkdir(parents=True)
    for name, body in STUBS.items():
        path = bin_dir / name
        path.write_text(f'#!/usr/bin/env bash\n{body}\n')
        path.chmod(path.stat().st_mode | stat.S_IEXEC)
    (fake / 'ptp_version').write_text('3.1.1\n')
    root = tmp_path / 'root'
    (root / 'etc' / 'chrony').mkdir(parents=True)
    (root / 'etc' / 'chrony' / 'chrony.conf').write_text('pool ntp.ubuntu.com iburst\n')
    return fake, root


def run(rig, *args, **env):
    fake, root = rig
    environ = {
        'PATH': f'{fake / "bin"}:{os.environ["PATH"]}',
        'FAKE': str(fake),
        'TIMESYNC_ROOT': str(root),
        'HOME': str(fake),
        **env,
    }
    return subprocess.run(
        ['bash', str(SCRIPT), *args], capture_output=True, text=True, env=environ, check=False
    )


def tracking(rig, offset='0.000012', side='fast', leap='Normal'):
    rig[0].joinpath('tracking').write_text(TRACKING.format(offset=offset, side=side, leap=leap))


def test_check_chrony_synchronised(rig):
    tracking(rig)
    done = run(rig, 'check', 'chrony')
    assert done.returncode == 0, done.stdout + done.stderr
    assert 'offset 0.000012 s to C0A87B01 (192.168.123.1)' in done.stdout


def test_check_chrony_not_synchronised_or_far_off(rig):
    tracking(rig, leap='Not synchronised')
    assert run(rig, 'check', 'chrony').returncode == 1
    tracking(rig, offset='0.200000', side='slow')
    done = run(rig, 'check', 'chrony')
    assert done.returncode == 1 and 'offset -0.2 s' in done.stdout and 'more than' in done.stdout
    assert run(rig, 'check', 'chrony', TIME_MAX_OFFSET='0.5').returncode == 0


def test_check_chrony_without_daemon(rig):
    done = run(rig, 'check', 'chrony')
    assert done.returncode == 1 and 'chronyd not running' in done.stdout


def test_install_chrony_writes_the_sources_and_the_served_subnets(rig):
    fake, root = rig
    done = run(rig, 'install', 'chrony', TIME_SERVERS='netra.lan 10.0.0.1',
               TIME_ALLOW='192.168.123.0/24')  # fmt: skip
    assert done.returncode == 0, done.stderr
    dropin = (root / 'etc/chrony/conf.d/robot-timesync.conf').read_text()
    assert 'server netra.lan iburst prefer' in dropin and 'server 10.0.0.1 iburst prefer' in dropin
    assert 'allow 192.168.123.0/24' in dropin and 'local stratum 10' in dropin
    conf = (root / 'etc/chrony/chrony.conf').read_text()
    assert conf.endswith('include /etc/chrony/conf.d/*.conf\n')  # chrony 3: no confdir
    assert 'restart chrony' in (fake / 'systemctl.log').read_text()
    run(rig, 'install', 'chrony')
    assert (root / 'etc/chrony/chrony.conf').read_text() == conf  # included once


def test_install_chrony_keeps_a_confdir_configuration(rig):
    _, root = rig
    conf = root / 'etc/chrony/chrony.conf'
    conf.write_text('confdir /etc/chrony/conf.d\npool ntp.ubuntu.com iburst\n')
    assert run(rig, 'install', 'chrony').returncode == 0
    assert 'include' not in conf.read_text()
    dropin = (root / 'etc/chrony/conf.d/robot-timesync.conf').read_text()
    assert 'server' not in dropin and 'allow' not in dropin


def test_install_ptp_on_the_interface_of_the_lidar(rig):
    fake, root = rig
    done = run(rig, 'install', 'ptp', LIVOX_IP='192.168.123.20')
    assert done.returncode == 0, done.stderr
    conf = (root / 'etc/linuxptp/lidar-ptp.conf').read_text()
    assert 'masterOnly 1' in conf and 'time_stamping software' in conf
    assert 'network_transport UDPv4' in conf
    unit = (root / 'etc/systemd/system/lidar-ptp.service').read_text()
    assert '-i eth7' in unit and '/etc/linuxptp/lidar-ptp.conf' in unit
    assert not (root / 'etc/systemd/system/lidar-phc2sys.service').exists()
    log = (fake / 'systemctl.log').read_text()
    assert 'daemon-reload' in log and 'restart lidar-ptp' in log
    assert run(rig, 'check', 'ptp', LIVOX_IP='192.168.123.20').returncode == 0
    (fake / 'active').write_text('3')
    done = run(rig, 'check', 'ptp', LIVOX_IP='192.168.123.20')
    assert done.returncode == 1 and 'lidar-ptp not running (LiDAR on eth7)' in done.stdout


def test_install_ptp_with_hardware_timestamps_and_linuxptp_4(rig):
    fake, root = rig
    (fake / 'ptp_version').write_text('4.0\n')
    done = run(rig, 'install', 'ptp', PTP_IFACE='enp3s0', PTP_TIMESTAMPING='hardware')
    assert done.returncode == 0, done.stderr
    conf = (root / 'etc/linuxptp/lidar-ptp.conf').read_text()
    assert 'serverOnly 1' in conf and 'time_stamping hardware' in conf
    phc = (root / 'etc/systemd/system/lidar-phc2sys.service').read_text()
    assert 'phc2sys -s CLOCK_REALTIME -c enp3s0' in phc
    assert 'restart lidar-ptp lidar-phc2sys' in (fake / 'systemctl.log').read_text()
    bad = run(rig, 'install', 'ptp', PTP_IFACE='enp3s0', PTP_TIMESTAMPING='fast')
    assert bad.returncode == 1


def test_without_a_lidar_address_ptp_is_skipped(rig):
    _, root = rig
    for action in ('check', 'install'):
        done = run(rig, action, 'ptp')
        assert done.returncode == 0 and 'skipped' in done.stdout
    assert not (root / 'etc/linuxptp').exists()


def test_unknown_part_is_refused(rig):
    assert run(rig, 'check', 'ntp').returncode == 2


def test_a_lidar_address_without_a_route_is_reported(rig):
    fake, _ = rig
    (fake / 'noroute').write_text('')
    for action in ('check', 'install'):
        done = run(rig, action, 'ptp', LIDAR_IP='10.9.9.9')
        assert done.returncode == 1
        assert 'no interface routes to the LiDAR at 10.9.9.9' in done.stdout + done.stderr
