"""scripts/hotdog.sh against a stand-in ros2: the calls each command makes (no ROS)."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess

import pytest

CLI = Path(__file__).resolve().parents[1] / 'hotdog.sh'
STUB = """#!/bin/bash
echo "ros2 $*" >> "$CALLS"
case "$1" in
  service) printf 'requester: making request\\n\\nresponse:\\nok\\n' ;;
  topic) printf 'site: gi\\n---\\n' ;;
  param) echo 'Boolean value is: True' ;;
esac
"""


@pytest.fixture
def run(tmp_path):
    (tmp_path / 'bin').mkdir()
    stub = tmp_path / 'bin' / 'ros2'
    stub.write_text(STUB)
    stub.chmod(0o755)
    calls = tmp_path / 'calls'
    env = {**os.environ, 'PATH': f'{tmp_path / "bin"}:{os.environ["PATH"]}',
           'CALLS': str(calls), 'HOTDOG_ENV': str(tmp_path / 'none.env'),
           'ROS_DISTRO': 'none', 'ROBOT_NS': 'm20', 'HOME': str(tmp_path)}  # fmt: skip

    def call(*args) -> tuple[int, list[str]]:
        if calls.exists():
            calls.unlink()
        done = subprocess.run(['bash', str(CLI), *args], env=env, capture_output=True,
                              text=True, timeout=30, check=False)  # fmt: skip
        made = calls.read_text().splitlines() if calls.exists() else []
        return done.returncode, made

    return call


def test_patrol_commands(run):
    assert run('patrol') == (
        0,
        ["ros2 service call /patrol/start hotdog_interfaces/srv/StartPatrol {route: ''}"],
    )
    code, made = run('patrol', '2026-11-01_09-30-00')
    assert made == ["ros2 service call /patrol/start hotdog_interfaces/srv/StartPatrol "
                    "{route: '2026-11-01_09-30-00'}"]  # fmt: skip
    for command, service in (('return', '/patrol/return'), ('stop', '/patrol/stop'),
                              ('estop', '/control/estop/engage'), ('dock', '/m20/charge_start'),
                              ('anchor', '/localization/assume_origin')):  # fmt: skip
        code, made = run(command)
        assert code == 0 and made == [f'ros2 service call {service} std_srvs/srv/Trigger {{}}']


def test_teaching(run):
    code, made = run('teach', 'start')
    assert code == 0 and [m.split()[3] for m in made] == [
        '/localization/assume_origin',
        '/route/start',
    ]
    assert run('teach', 'point', '8')[1][0].endswith('{dwell_sec: 8.0}')
    code, made = run('teach', 'target', 'bay1_clamps', 'strips=3', 'acoustic')
    assert made[0].endswith("{name: 'bay1_clamps', thermal: true, acoustic: true, strips: 3, "
                            'max_temp_c: 0.0}')  # fmt: skip
    code, made = run('teach', 'target', 'bay2', 'max=95')
    assert 'thermal: true, acoustic: false, strips: 0, max_temp_c: 95.0' in made[0]
    assert run('teach', 'point', 'x') == (1, [])
    assert run('teach', 'target')[0] == 1


def test_parameters(run):
    assert run('ambient', '33') == (0, ['ros2 param set /inspection_node thermal.ambient_c 33.0'])
    assert run('ambient', 'warm') == (1, [])
    assert run('schedule', 'on')[1] == ['ros2 param set /patrol_node schedule.enabled true']


def test_help_and_unknown(run):
    assert run('help')[0] == 0
    assert run('fly')[0] == 1
