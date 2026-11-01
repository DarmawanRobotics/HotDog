"""Put the Dharma package checkouts on sys.path, so the experiments import their cores."""

from __future__ import annotations

import os
from pathlib import Path
import sys

HUB = Path(__file__).resolve().parents[2]
PACKAGES = (
    'dharma_utils',
    'dharma_sim',
    'dharma_perception',
    'dharma_localization',
    'dharma_navigation/dharma_navigation',
    'dharma_navigation/dharma_control',
)


def roots() -> list[Path]:
    """Return the directories searched for checkouts: $DHARMA_SRC, src/dharma, the hub's parent."""
    found = [Path(p) for p in os.environ.get('DHARMA_SRC', '').split(os.pathsep) if p]
    return [*found, HUB / 'src' / 'dharma', HUB.parent]


def add_paths():
    """Add every package checkout found to sys.path (the first root that has it wins)."""
    for package in PACKAGES:
        for root in roots():
            path = root / package
            if (path / Path(package).name).is_dir():
                if str(path) not in sys.path:
                    sys.path.insert(0, str(path))
                break
        else:
            raise ImportError(f'{package} not found under {[str(r) for r in roots()]}')
