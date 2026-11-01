#!/usr/bin/env python3
"""
Draw the logo and the diagrams of the guides (docs/logo.png, docs/manual/img/*.png).

    python3 docs/pdf/diagrams.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

DOCS = Path(__file__).resolve().parents[1]
FONTS = DOCS / 'pdf' / 'fonts'
IMG = DOCS / 'manual' / 'img'
INK, MUTED, LINE = '#16212a', '#5b6b75', '#c8d2d7'
BLUE, BLUE_SOFT, AMBER, AMBER_SOFT = '#1f6fb2', '#e6eff8', '#e8892c', '#fdf0e2'
NAVY, RED, RED_SOFT = '#0f2742', '#c62828', '#fbe9e9'


def font(weight: str, size: int):
    """Return Barlow Semi Condensed in a weight (Regular, Medium, SemiBold, Bold)."""
    return ImageFont.truetype(str(FONTS / f'BarlowSemiCondensed-{weight}.ttf'), size)


def box(draw, xy, title, lines=(), fill='#ffffff', outline=LINE, title_fill=INK, width=3):
    """Draw a rounded box with a bold title and smaller lines under it."""
    draw.rounded_rectangle(xy, radius=22, fill=fill, outline=outline, width=width)
    x0, y0, x1, _ = xy
    cx = (x0 + x1) / 2
    draw.text((cx, y0 + 34), title, fill=title_fill, font=font('Bold', 40), anchor='mm')
    for i, line in enumerate(lines):
        draw.text((cx, y0 + 82 + i * 38), line, fill=MUTED, font=font('Medium', 31), anchor='mm')


def arrow(draw, start, end, label='', color=BLUE, both=False):
    """Draw a straight arrow (heads on both ends when both) with a label above its middle."""
    draw.line([start, end], fill=color, width=7)
    for tip, tail in [(end, start), (start, end)] if both else [(end, start)]:
        dx, dy = tip[0] - tail[0], tip[1] - tail[1]
        length = (dx * dx + dy * dy) ** 0.5
        ux, uy = dx / length, dy / length
        left = (tip[0] - 30 * ux + 16 * uy, tip[1] - 30 * uy - 16 * ux)
        right = (tip[0] - 30 * ux - 16 * uy, tip[1] - 30 * uy + 16 * ux)
        draw.polygon([tip, left, right], fill=color)
    if label:
        mx, my = (start[0] + end[0]) / 2, (start[1] + end[1]) / 2
        if abs(end[0] - start[0]) < 1:  # vertical: the label beside the line
            draw.text((mx + 20, my), label, fill=color, font=font('SemiBold', 30), anchor='lm')
        else:
            draw.text((mx, my - 40), label, fill=color, font=font('SemiBold', 30), anchor='mm')


def logo():
    """Draw the logo: a lightning bolt in a rounded square, the robot's trade in one sign."""
    size = 600
    image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((20, 20, size - 20, size - 20), radius=120, fill=NAVY)
    draw.rounded_rectangle((60, 60, size - 60, size - 60), radius=90, outline='#ffb020', width=14)
    bolt = [(330, 110), (190, 330), (290, 330), (250, 490), (410, 250), (305, 250), (350, 110)]
    draw.polygon(bolt, fill='#ffb020')
    image.save(DOCS / 'logo.png', optimize=True)


def system():
    """Draw the parts: the M20 with its sensors and payload computer, the operator side."""
    image = Image.new('RGB', (2300, 940), '#ffffff')
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((560, 30, 1700, 900), radius=34, fill='#f6f9fa', outline=BLUE, width=5)
    draw.text((1130, 88), 'Robot: Deep Robotics Lynx M20', fill=BLUE, font=font('Bold', 46),
              anchor='mm')  # fmt: skip
    airy = ['2 × RoboSense', 'Airy: obstacles', 'all around']  # noqa: RUF001
    box(draw, (610, 140, 900, 360), 'LiDAR', airy)
    box(
        draw,
        (930, 140, 1330, 360),
        'UniPod MT11',
        ['zoom + thermal', 'camera on a gimbal:', 'overheating'],
    )
    box(draw, (1360, 140, 1650, 360), 'HZ-FA-371', ['acoustic camera:', 'partial', 'discharge'])
    box(
        draw,
        (610, 460, 1650, 620),
        'Payload computer (Ubuntu 20.04, ROS 2 Foxy)',
        ['HotDog: patrols from the dock, safety, inspection,', 'reports, alerts, the watchdog'],
        fill=BLUE_SOFT,
        outline=BLUE,
    )
    box(draw, (610, 720, 1650, 850), 'M20 motion computer', ['walks, rolls, balances, docks'])
    for x in (755, 1130, 1505):
        arrow(draw, (x, 362), (x, 458))
    arrow(draw, (1130, 622), (1130, 718), both=True)
    box(draw, (30, 380, 470, 600), 'Operator', ['SSH: hotdog status,', 'teach, patrol', 'M20 remote: drive'],  # noqa: E501
        fill=AMBER_SOFT, outline=AMBER)  # fmt: skip
    arrow(draw, (472, 490), (608, 490), color=AMBER, both=True)
    box(draw, (1830, 160, 2270, 360), 'Reports', ['browser on the', 'substation network', ':8088'])
    box(
        draw,
        (1830, 440, 2270, 640),
        'Telegram',
        ['alerts to the crew,', 'with the thermal', 'image'],
    )
    box(draw, (1830, 720, 2270, 880), 'Webhook', ['control room,', 'tickets'])
    for y in (260, 540, 790):
        arrow(draw, (1652, 540), (1828, y))
    image.save(IMG / 'system.png', optimize=True)


def workflow():
    """Draw the operator's steps: teach once from the dock, then patrol and act."""
    steps = [
        ('1', 'Teach', ['from the dock:', 'drive, stop points,', 'aim the pod']),
        ('2', 'Patrol', ['on demand or', 'on a schedule,', 'from the dock']),
        ('3', 'Inspect', ['at every stop:', 'thermal and', 'partial discharge']),
        ('4', 'Report', ['page per patrol,', 'Telegram alerts,', 'last round']),
        ('5', 'Act', ['attention, warning,', 'critical: the', 'crew decides']),
    ]
    image = Image.new('RGB', (2160, 560), '#ffffff')
    draw = ImageDraw.Draw(image)
    width, gap = 360, 70
    for i, (number, title, lines) in enumerate(steps):
        x0 = 40 + i * (width + gap)
        fill, outline = (AMBER_SOFT, AMBER) if i == 0 else (BLUE_SOFT, BLUE)
        draw.rounded_rectangle(
            (x0, 110, x0 + width, 500), radius=26, fill=fill, outline=outline, width=4
        )
        cx = x0 + width / 2
        draw.ellipse((cx - 46, 64, cx + 46, 156), fill=outline)
        draw.text((cx, 110), number, fill='#ffffff', font=font('Bold', 50), anchor='mm')
        draw.text((cx, 215), title, fill=INK, font=font('Bold', 52), anchor='mm')
        for j, line in enumerate(lines):
            draw.text((cx, 292 + j * 44), line, fill=MUTED, font=font('Medium', 36), anchor='mm')
        if i < len(steps) - 1:
            arrow(draw, (x0 + width + 8, 305), (x0 + width + gap - 8, 305))
    image.save(IMG / 'workflow.png', optimize=True)


def patrol():
    """Draw one patrol: checks, re-anchor, stand, route, stops; the watchdog's way back."""
    image = Image.new('RGB', (2300, 730), '#ffffff')
    draw = ImageDraw.Draw(image)
    steps = [
        ('Checks', ['health, e-stop,', 'battery ≥ 30 %']),
        ('Re-anchor', ['the dock is', 'the origin']),
        ('Stand up', ['M20 RL', 'control']),
        ('Route', ['follow it,', 'avoid, slow']),
        ('Stop points', ['aim the pod,', 'measure, report']),
        ('Dock', ['charge_start,', 'summary']),
    ]
    width, gap = 320, 58
    centers = []
    for i, (title, lines) in enumerate(steps):
        x0 = 30 + i * (width + gap)
        centers.append(x0 + width / 2)
        box(draw, (x0, 60, x0 + width, 250), title, lines, fill=BLUE_SOFT, outline=BLUE)
        if i < len(steps) - 1:
            arrow(draw, (x0 + width + 6, 155), (x0 + width + gap - 6, 155))
    box(
        draw,
        (330, 520, 2210, 690),
        'Watchdog: the way back along the taught route',
        ['battery < 20 %, longer than 2 h, blocked 3 min: walk the route backwards, dock',
         'off the route, lost, silent follower: stop where it stands, alert the crew'],
        fill=RED_SOFT,
        outline=RED,
    )  # fmt: skip
    arrow(draw, (centers[3], 252), (centers[3], 516), 'trouble', color=RED)
    arrow(draw, (centers[5], 516), (centers[5], 252), 'docks', color=RED)
    image.save(IMG / 'patrol.png', optimize=True)


if __name__ == '__main__':
    IMG.mkdir(parents=True, exist_ok=True)
    logo()
    system()
    workflow()
    patrol()
    print('docs/logo.png, docs/manual/img/system.png, workflow.png, patrol.png')
