"""Writing the report pages: a patrol's page, its day, the front page (atomic writes)."""

from __future__ import annotations

from dataclasses import dataclass
import os

from dharma_utils.io import write_json_atomic, write_text_atomic
from hotdog_reports.core import index, render
from hotdog_reports.core.model import day_dirs, load_patrol, patrol_files
from hotdog_reports.core.trends import history


@dataclass
class Builder:
    """Renders the reports under root."""

    root: str
    title: str = 'HotDog substation patrol'
    robot: str = 'HotDog'
    trend_days: int = 30

    def patrol(self, summary_path: str, front: bool = True) -> str:
        """Render a patrol and its day; return the page (raise OSError, ValueError)."""
        patrol = load_patrol(summary_path)
        if patrol is None:
            raise ValueError(f'{summary_path}: not a readable patrol summary')
        hist = history(self.root, patrol.started, self.trend_days)
        write_text_atomic(patrol.html, render.patrol_page(patrol, hist, self.title, self.robot))
        self.day(os.path.dirname(summary_path), front)
        return patrol.html

    def day(self, day_dir: str, front: bool = True):
        """Render a day's page and figures, then the front page."""
        write_json_atomic(os.path.join(day_dir, 'day.json'), index.day_figures(day_dir), False)
        write_text_atomic(
            os.path.join(day_dir, 'index.html'), index.day_page(day_dir, self.title, self.robot)
        )
        if front:
            self.front()

    def front(self):
        """Render the front page."""
        figures = index.read_figures(self.root)
        page = index.front_page(self.root, self.title, self.robot, figures)
        write_text_atomic(os.path.join(self.root, 'index.html'), page)

    def missing(self) -> list[str]:
        """Return the patrol summaries without a page yet."""
        out = []
        for day in day_dirs(self.root):
            for path in patrol_files(os.path.join(self.root, day)):
                if not os.path.isfile(os.path.splitext(path)[0] + '.html'):
                    out.append(path)
        return out

    def rebuild(self, everything: bool = False) -> tuple[int, list[str]]:
        """Render the missing patrol pages (every one with everything); (pages, errors)."""
        targets = self.missing()
        if everything:
            targets = [
                p for d in day_dirs(self.root) for p in patrol_files(os.path.join(self.root, d))
            ]
        errors = []
        for path in targets:
            try:
                self.patrol(path, front=False)
            except (OSError, ValueError) as error:
                errors.append(f'{path}: {error}')
        for day in day_dirs(self.root):
            if not os.path.isfile(os.path.join(self.root, day, 'index.html')) or everything:
                self.day(os.path.join(self.root, day), front=False)
        if os.path.isdir(self.root):
            self.front()
        return len(targets) - len(errors), errors
