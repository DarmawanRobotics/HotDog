"""
Run E1-E5 for every seed and write results/*.csv, then the paper's tables and figures.

    python3 experiments/run_all.py              # 20 seeds, every experiment (2 processes)
    python3 experiments/run_all.py --seeds 2 e1 # quick look at one experiment
    python3 experiments/run_all.py --report     # tables and figures from the committed CSVs
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import os
import sys
import time

import common  # noqa: F401  (puts the stack on sys.path)
from common.metrics import write_rows
import e1_stopping
import e2_blind
import e3_localization
import e4_path_shift
import e5_backup

EXPERIMENTS = {
    'e1': ('e1_stopping', e1_stopping.run, lambda s: [
        (v, x, h) for h in e1_stopping.HUMAN_SPEEDS for v in e1_stopping.SPEEDS for x in s]),
    'e2': ('e2_blind', e2_blind.run, lambda s: [
        (k, m, v, x) for k in e2_blind.KINDS for m in e2_blind.MODES
        for v in e2_blind.VERSIONS for x in s]),
    'e3': ('e3_localization', e3_localization.run, lambda s: [(x,) for x in s]),
    'e4': ('e4_path_shift', e4_path_shift.run, lambda s: [
        (m, x, layout) for layout in e4_path_shift.LAYOUTS for m in e4_path_shift.MODES
        for x in s]),
    'e5': ('e5_backup', e5_backup.run, lambda s: [(c, x) for c in e5_backup.CONDITIONS
                                                  for x in s]),
}  # fmt: skip


def _call(job):
    fn, args = job
    return fn(*args)


def run(name: str, seeds, workers: int) -> float:
    """Run one experiment over the seeds in parallel; write its CSV; return the seconds."""
    csv_name, fn, jobs = EXPERIMENTS[name]
    start = time.monotonic()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(_call, [(fn, args) for args in jobs(seeds)]))
    rows = [row for result in results for row in (result if isinstance(result, list)
                                                  else [result])]  # fmt: skip
    write_rows(csv_name, rows)
    return time.monotonic() - start


def main():
    """Parse the arguments and run."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument('experiments', nargs='*', default=sorted(EXPERIMENTS))
    parser.add_argument('--seeds', type=int, default=20, help='seeds 1..N per condition')
    parser.add_argument('--workers', type=int, default=min(2, os.cpu_count() or 1))
    parser.add_argument('--report', action='store_true', help='only tables and figures')
    args = parser.parse_args()
    if not args.report:
        seeds = tuple(range(1, args.seeds + 1))
        for name in args.experiments:
            seconds = run(name, seeds, args.workers)
            sys.stdout.write(f'{name}: {len(seeds)} seeds in {seconds:.0f} s\n')
    import report

    report.main()


if __name__ == '__main__':
    main()
