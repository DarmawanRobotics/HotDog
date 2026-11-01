"""Figures of the paper (matplotlib, PDF, one IEEE column wide)."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use('Agg')
from common.metrics import read_rows
import matplotlib.pyplot as plt

COLORS = ('#2a78d6', '#eb6834', '#1baf7a')  # validated categorical slots 1-3
STYLES = ('-', '--', '-.')
LABELS = {
    'hard_replace': 'hard replace (v0.1)',
    'ekf_tags': 'EKF, tags',
    'ekf_tags_scan': 'EKF, tags + scan match',
}


def e3_error(directory: Path):
    """Position error over the distance driven, seed 1, the three estimators."""
    rows = read_rows('e3_errors_seed1')
    distance = [float(r['odom_distance_m']) for r in rows]
    plt.rcParams.update({'font.size': 7, 'font.family': 'serif', 'axes.linewidth': 0.5})
    fig, ax = plt.subplots(figsize=(3.45, 1.35))
    for (method, label), color, style in zip(LABELS.items(), COLORS, STYLES):
        error = [float(r[f'{method}_error_m']) for r in rows]
        ax.plot(distance, error, style, color=color, linewidth=1.0, label=label)
    ax.set_xlabel('distance driven (m)')
    ax.set_ylabel('position error (m)')
    ax.set_xlim(0.0, max(distance))
    ax.set_ylim(bottom=0.0)
    ax.grid(True, linewidth=0.3, color='#d0d0d0')
    for side in ('top', 'right'):
        ax.spines[side].set_visible(False)
    ax.legend(frameon=False, loc='upper left', ncol=3, handlelength=2.2, columnspacing=1.0,
              bbox_to_anchor=(0.0, 1.18))  # fmt: skip
    fig.tight_layout(pad=0.2)
    directory.mkdir(parents=True, exist_ok=True)
    fig.savefig(directory / 'e3_error.pdf')
    plt.close(fig)


def main(directory: Path):
    """Write every figure into directory."""
    e3_error(directory)
