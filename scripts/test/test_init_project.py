"""scripts/init_project.py: pure helpers and a conversion of a copy of this repository."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import py_compile
import shutil
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('init_project', ROOT / 'scripts' / 'init_project.py')
init = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = init  # dataclasses resolve string annotations through sys.modules
SPEC.loader.exec_module(init)


def options(**kwargs):
    values = {'name': 'MyRobot', 'package': 'my_robot_bringup', 'robot_ns': 'lite3'}
    return init.Options(**{**values, **kwargs})


def test_snake():
    assert init.snake('MyRobot') == 'my_robot'
    assert init.snake('Molly') == 'molly'
    assert init.snake('LiDARBot2') == 'li_dar_bot2'
    assert init.snake('ABCRobot') == 'abc_robot'


def test_validate():
    assert init.validate(options()) == []
    assert len(init.validate(options(name='my_robot', package='MyPkg', robot_ns='1x'))) == 3
    assert init.validate(options(package='dharma_bringup'))
    assert init.validate(options(package='robot_bringup'))
    assert init.validate(options(package='bad__name'))


def test_replace_package_boundaries():
    text = "robot_bringup robot_bringup/x 'robot_bringup' robot_bringup_ my_robot_bringup2"
    assert init.replace_package(text, 'pkg') == "pkg pkg/x 'pkg' pkg_ my_robot_bringup2"
    assert init.replace_package('ROBOT_BRINGUP probot_bringup', 'pkg') == (
        'ROBOT_BRINGUP probot_bringup'
    )


def test_rename_and_removed():
    rel = 'src/robot_bringup/robot_bringup/bringup.py'
    assert init.rename_path(rel, 'pkg') == 'src/pkg/pkg/bringup.py'
    assert init.rename_path('src/robot_bringup/resource/robot_bringup', 'p') == 'src/p/resource/p'
    o = options()
    assert init.removed('tooling/ruff.toml', o)
    assert init.removed('scripts/init_project.py', o)
    assert init.removed('docs/paper/dharma.tex', o)
    assert init.removed('docs/guide/Safety.md', o)
    assert init.removed('docs/pdf/dharma_paper.pdf', o)
    assert not init.removed('.github/workflows/ci.yml', o)
    assert not init.removed('docs/README.md', o)
    assert not init.removed('docs/paper/dharma.tex', options(keep_docs=True))
    assert not init.removed('toolingx/file', o)


def test_edits():
    o = options()
    bringup = "DEFAULT_ROBOT_NS = 'robot'\n"
    assert init.edit('src/robot_bringup/robot_bringup/bringup.py', bringup, o) == (
        "DEFAULT_ROBOT_NS = 'lite3'\n"
    )
    compose = 'name: dharma\n    image: dharma-dev:humble\n    hostname: dharma-humble\n'
    assert init.edit('compose.yaml', compose, o) == (
        'name: my_robot\n    image: my_robot-dev:humble\n    hostname: my_robot-humble\n'
    )
    assert 'MyRobot' in init.edit('README.md', '# Dharma', o)
    assert '[Unreleased]' in init.edit('CHANGELOG.md', '', o)


@pytest.fixture
def copy(tmp_path):
    """A copy of this repository (no git, no build output)."""
    target = tmp_path / 'repo'
    ignore = shutil.ignore_patterns('.git', 'build', 'install', 'log', '__pycache__', '.*_cache')
    shutil.copytree(ROOT, target, ignore=ignore, symlinks=True)
    for path in ('docs/paper', 'docs/manual'):
        (target / path).mkdir(parents=True, exist_ok=True)
        (target / path / 'x.tex').write_text('dharma\n')
    return target


def all_text(root: Path) -> str:
    return '\n'.join(
        p.read_text(encoding='utf-8', errors='ignore') for p in root.rglob('*') if p.is_file()
    )


def test_dry_run_changes_nothing(copy, capsys):
    before = sorted(p.relative_to(copy) for p in copy.rglob('*'))
    assert init.main(['--name', 'MyRobot', '--package', 'mr_bringup', '--root', str(copy),
                      '--dry-run']) == 0  # fmt: skip
    assert sorted(p.relative_to(copy) for p in copy.rglob('*')) == before
    out = capsys.readouterr().out
    assert 'remove  tooling/ruff.toml' in out
    assert 'src/robot_bringup/package.xml -> src/mr_bringup/package.xml' in out


def test_conversion(copy):
    assert init.main(['--name', 'MyRobot', '--package', 'mr_bringup', '--robot-ns', 'lite3',
                      '--root', str(copy)]) == 0  # fmt: skip
    package = copy / 'src' / 'mr_bringup'
    assert (package / 'mr_bringup' / 'bringup.py').is_file()
    assert (package / 'resource' / 'mr_bringup').is_file()
    assert not (copy / 'src' / 'robot_bringup').exists()
    assert not (copy / 'tooling').exists()
    assert not (copy / 'scripts' / 'init_project.py').exists()
    assert not (copy / 'docs' / 'paper').exists()
    assert not (copy / 'docs' / 'guide').exists()
    assert not (copy / 'docs' / 'pdf').exists()
    assert (copy / 'ruff.toml').is_file()  # the lint configuration stays
    assert 'robot_bringup' not in all_text(copy)
    assert "DEFAULT_ROBOT_NS = 'lite3'" in (package / 'mr_bringup' / 'bringup.py').read_text()
    assert '<version>0.1.0</version>' in (package / 'package.xml').read_text()
    assert '# MyRobot' in (copy / 'README.md').read_text()
    assert 'name: my_robot' in (copy / 'compose.yaml').read_text()
    for source in package.rglob('*.py'):
        py_compile.compile(str(source), doraise=True)
    for script in ('dev.sh', 'setup.sh', 'start_tmux.sh'):
        assert (copy / 'scripts' / script).stat().st_mode & 0o100  # still executable
    with pytest.raises(SystemExit):  # the placeholder is gone: a second run refuses
        init.main(['--name', 'MyRobot', '--package', 'mr_bringup', '--root', str(copy)])


def test_keep_docs(copy):
    init.main(['--name', 'MyRobot', '--package', 'mr_bringup', '--keep-docs', '--root', str(copy)])
    assert (copy / 'docs' / 'paper' / 'x.tex').is_file()
    assert (copy / 'docs' / 'guide' / 'Safety.md').is_file()
    assert not (copy / 'tooling').exists()


def test_invalid_arguments_exit(copy):
    with pytest.raises(SystemExit):
        init.main(['--name', 'my robot', '--package', 'mr_bringup', '--root', str(copy)])
    assert (copy / 'src' / 'robot_bringup').is_dir()
