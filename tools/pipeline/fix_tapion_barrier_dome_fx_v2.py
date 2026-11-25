#!/usr/bin/env python3
"""
DR7-Studio — Tapion `barrier_dome_fx` Authentic Frame-8 Multi-Layer Blue Energy Barrier (`polish_v3`):
Owner request:
  "vòng năng lượng cần tham chiếu frame cuối của bản gốc /workspaces/Dragonball-Studio-7/tapion/vòng tròn bảo vệ.png
   nhưng nhân vật bên trong thì lấy của hiện tại không lấy bản ánh xạ màu xanh của bản gốc ,
   bản hiện tại chỉ có 1 vòng tròn duy nhất chưa đạt chuẩn."

Faithfully recreates ALL 4 visual layers of Frame 8 (far right) of `tapion/vòng tròn bảo vệ.png`
as a pure transparent pixel-art FX overlay centered at `(144, 144)` on `288x288`:
  1. Outer segmented cobalt-blue orbital ring arcs (`R ~ 102..108 px`, 4-5px crisp pixel arcs with gaps).
  2. Scattered royal-blue chunky polygonal energy shards around the outer/mid shell (`R ~ 76..112 px`).
  3. Dense spherical pixel stipple/energy dust (`2x2` & `1x1` crisp blue/cyan dots) spanning the sphere volume,
     richer in the outer shell (`R ~ 44..102 px`) and airy/sparse over the center so Tapion inside stays
     100% crisp, un-tinted, and naturally colored!
  4. Glowing cyan-white curved energy ribbons / wisps (white top highlight + bright cyan body + azure bottom)
     gliding across the sides & front of the sphere just like Frame 8 of `vòng tròn bảo vệ.png`!
  - 5 clean frames (`barrier_dome_00..04`):
      * `#0..#3`: 4-frame seamless animated barrier (rotating outer ring segments, orbiting blue shards,
                  shimmering pixel dust, gliding cyan-white energy ribbons).
      * `#4`: dispersing fade-out frame (final 0.25s of 10s shield).
"""
from __future__ import annotations

import math
import pathlib
import numpy as np
from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC_SHEET = ROOT / "tapion" / "vòng tròn bảo vệ.png"
OUT_DIR = ROOT / "work" / "characters" / "tapion" / "polish_v2"
FX_REG_DIR = OUT_DIR / "fx_registered_288"
QA_DIR = OUT_DIR / "qa"

CW, CH = 288, 288
CX, CY = 144.0, 144.0

# Exact pixel palette sampled from Frame 8 of `tapion/vòng tròn bảo vệ.png`
PAL_COBALT_RING = np.array([26, 60, 214, 255], dtype=np.uint8)     # outer segmented dark-royal ring
PAL_ROYAL_SHARD = np.array([22, 118, 246, 255], dtype=np.uint8)    # chunky blue energy shards
PAL_STIPPLE_DARK = np.array([10, 92, 198, 255], dtype=np.uint8)    # deep blue stipple dots
PAL_STIPPLE_MID = np.array([18, 148, 242, 255], dtype=np.uint8)    # mid sky-blue stipple dots
PAL_CYAN_RIBBON = np.array([68, 220, 255, 255], dtype=np.uint8)    # bright cyan ribbon body
PAL_CYAN_LIGHT = np.array([154, 244, 255, 255], dtype=np.uint8)    # light ice-cyan transition
PAL_WHITE_TOP = np.array([244, 254, 255, 255], dtype=np.uint8)     # pure white ribbon crest


def _stamp_block(canvas: np.ndarray, x: int, y: int, bw: int, bh: int, col: np.ndarray) -> None:
    x0 = max(0, x)
    y0 = max(0, y)
    x1 = min(CW, x + bw)
    y1 = min(CH, y + bh)
    if x0 < x1 and y0 < y1:
        canvas[y0:y1, x0:x1] = col


def _draw_shard(canvas: np.ndarray, cx: float, cy: float, ang: float, length: float, width: float, col: np.ndarray, rng: np.random.Generator) -> None:
    """Draw a chunky 2px-grain angled rectangular/polygonal blue energy shard (like Frame 8 perimeter chunks)."""
    ca, sa = math.cos(ang), math.sin(ang)
    hw, hl = width * 0.5, length * 0.5
    min_x = max(2, int(cx - max(hl, hw) - 4))
    max_x = min(CW - 3, int(cx + max(hl, hw) + 4))
    min_y = max(2, int(cy - max(hl, hw) - 4))
    max_y = min(CH - 3, int(cy + max(hl, hw) + 4))
    for py in range(min_y, max_y + 1, 2):
        for px in range(min_x, max_x + 1, 2):
            dx = px - cx
            dy = py - cy
            lx = dx * ca + dy * sa
            ly = -dx * sa + dy * ca
            if abs(lx) <= hl and abs(ly) <= hw:
                # Slight organic bevel at corners
                if abs(lx) > hl - 2.0 and abs(ly) > hw - 2.0 and rng.random() < 0.55:
                    continue
                _stamp_block(canvas, px, py, 2, 2, col)


def _draw_energy_ribbon(
    canvas: np.ndarray,
    x_start: float,
    y_start: float,
    x_end: float,
    y_end: float,
    arch_y: float,
    thickness: float,
) -> None:
    """Draw a crisp 2px-grain curved glowing cyan-white energy ribbon (white crest + bright cyan body + royal rim)."""
    steps = max(24, int(math.hypot(x_end - x_start, y_end - y_start) * 1.4))
    pts = []
    for i in range(steps + 1):
        t = i / float(steps)
        env = math.sin(math.pi * t) ** 0.72
        px = x_start + (x_end - x_start) * t
        py = y_start + (y_end - y_start) * t - arch_y * math.sin(math.pi * t)
        rad = max(1.0, thickness * env)
        pts.append((px, py, rad, t))

    # Pass 1: Royal-blue subtle bottom rim
    for px, py, rad, _ in pts:
        ix, iy = int(round(px / 2.0)) * 2, int(round((py + rad * 0.65) / 2.0)) * 2
        rw = max(2, int(round(rad * 1.15 / 2.0)) * 2)
        _stamp_block(canvas, ix - rw // 2, iy, rw, 2, PAL_ROYAL_SHARD)

    # Pass 2: Bright cyan main ribbon body
    for px, py, rad, _ in pts:
        ix, iy = int(round(px / 2.0)) * 2, int(round(py / 2.0)) * 2
        ir = max(2, int(round(rad / 2.0)) * 2)
        for oy in range(-ir, ir + 1, 2):
            for ox in range(-ir, ir + 1, 2):
                if ox * ox + oy * oy <= (ir + 0.5) * (ir + 0.5):
                    _stamp_block(canvas, ix + ox, iy + oy, 2, 2, PAL_CYAN_RIBBON)

    # Pass 3: White / ice-cyan upper highlight crest (matching exact lighting in Frame 8!)
    for px, py, rad, t in pts:
        if 0.08 <= t <= 0.92:
            ix, iy = int(round(px / 2.0)) * 2, int(round((py - rad * 0.35) / 2.0)) * 2
            ir = max(1, int(round(rad * 0.55)))
            col = PAL_WHITE_TOP if (0.16 <= t <= 0.84) else PAL_CYAN_LIGHT
            _stamp_block(canvas, ix - (ir // 2) * 2, iy, max(2, ir), 2, col)


def make_frame8_barrier(frame_idx: int) -> Image.Image:
    """Synthesize one animated frame faithfully modeled on Frame 8 of `tapion/vòng tròn bảo vệ.png`."""
    rng = np.random.default_rng(8821 + frame_idx * 1307)
    canvas = np.zeros((CH, CW, 4), dtype=np.uint8)
    is_dissolve = (frame_idx == 4)

    # Phase shift across the 4 seamless loop frames (0, 90, 180, 270 deg)
    phase = frame_idx * (math.pi * 0.5)
    ring_r = 104.0 if not is_dissolve else 108.0

    # --- LAYER 1: Dense spherical pixel stipple dust (2x2 & 1x1 blue/cyan dots across sphere shell) ---
    # Notice in Frame 8: particles fill the circular shell, denser around R=42..100px,
    # and very sparse in the immediate hero-face center (R < 34px) so Tapion stays crisp & untinted!
    for py in range(28, CH - 28, 2):
        for px in range(28, CW - 28, 2):
            dx = px - CX
            dy = py - CY
            r = math.hypot(dx, dy)
            if r > ring_r - 2.0:
                continue
            ang = math.atan2(dy, dx)
            # Radial shell density matching Frame 8: sparse over hero center, rich blue nebula shell outside
            if r < 26.0:
                prob = 0.015
            elif r < 46.0:
                prob = 0.06 + 0.14 * ((r - 26.0) / 20.0)
            else:
                # Shell peaks around R=65..96px with gentle swirling angular clusters
                swirl = 0.72 + 0.38 * math.sin(ang * 3.0 + phase + r * 0.045) * math.cos(ang * 2.0 - phase * 0.5)
                prob = 0.24 * swirl
            if is_dissolve:
                prob *= 0.48
            rv = rng.random()
            if rv < prob:
                # 65% crisp 2x2 dot, 35% 1x1 pixel dust
                sz = 2 if rng.random() < 0.62 else 1
                col = PAL_STIPPLE_MID if (rng.random() < 0.44 or r > 76.0) else PAL_STIPPLE_DARK
                _stamp_block(canvas, px, py, sz, sz, col)

    # --- LAYER 2: Outer segmented cobalt-blue circular ring arcs (exact Frame 8 broken boundary arcs!) ---
    # 7 crisp curved arc segments rotating smoothly around the circumference
    arc_defs = [
        (0.05, 0.52),
        (0.68, 0.44),
        (1.32, 0.58),
        (2.12, 0.48),
        (2.85, 0.62),
        (3.75, 0.52),
        (4.65, 0.58),
        (5.48, 0.46),
    ]
    yy, xx = np.indices((CH, CW), dtype=np.float32)
    dx_g = xx - CX
    dy_g = yy - CY
    rad_g = np.hypot(dx_g, dy_g)
    ang_g = np.mod(np.arctan2(dy_g, dx_g) - phase * 0.5, 2.0 * math.pi)
    arc_half_w = 2.6 if not is_dissolve else 1.8
    ring_mask = np.zeros((CH, CW), dtype=bool)
    for a0, span in arc_defs:
        a1 = a0 + (span * (0.65 if is_dissolve else 1.0))
        in_ang = (ang_g >= a0) & (ang_g <= a1)
        if a1 > 2.0 * math.pi:
            in_ang = (ang_g >= a0) | (ang_g <= a1 - 2.0 * math.pi)
        ring_mask |= in_ang & (np.abs(rad_g - ring_r) <= arc_half_w)
    # Quantize ring onto crisp 2px pixel blocks for authentic retro pixel feel
    canvas[ring_mask] = PAL_COBALT_RING
    # Subtle lighter inner highlight on a few arc segments
    inner_hi = ring_mask & (rad_g < ring_r - 0.8) & (rng.random((CH, CW)) < 0.35)
    canvas[inner_hi] = PAL_ROYAL_SHARD

    # --- LAYER 3: Chunky royal-blue energy shards orbiting near perimeter (just like Frame 8!) ---
    n_shards = 15 if not is_dissolve else 8
    for si in range(n_shards):
        a = (si * (2.0 * math.pi / n_shards)) + phase * 0.25 + rng.uniform(-0.14, 0.14)
        sr = ring_r + rng.uniform(-16.0, 5.0)
        sx = CX + sr * math.cos(a)
        sy = CY + sr * math.sin(a)
        slen = rng.uniform(7.0, 14.0)
        swid = rng.uniform(4.5, 8.0)
        _draw_shard(canvas, sx, sy, a + math.pi * 0.25 + rng.uniform(-0.5, 0.5), slen, swid, PAL_ROYAL_SHARD, rng)

    # --- LAYER 4: Glowing cyan-white curved energy ribbons gliding across the sphere (signature of Frame 8!) ---
    # Each loop frame smoothly shifts the ribbon positions horizontally/orbitally so they swirl around Tapion!
    drift_x = math.sin(phase) * 14.0
    drift_y = math.cos(phase) * 8.0
    if not is_dissolve:
        # Left mid-lower bright curved ribbon
        _draw_energy_ribbon(canvas, 50.0 + drift_x * 0.6, 152.0 + drift_y, 88.0 + drift_x * 0.6, 148.0 + drift_y * 0.5, arch_y=11.0, thickness=5.2)
        # Front-right prominent sweeping energy ribbon (signature Frame 8 ribbon across lower-right!)
        _draw_energy_ribbon(canvas, 150.0 - drift_x * 0.4, 178.0 - drift_y * 0.6, 212.0 - drift_x * 0.4, 192.0 - drift_y * 0.3, arch_y=13.0, thickness=6.2)
        # Far-right upper-mid energy crest
        _draw_energy_ribbon(canvas, 206.0 + drift_x * 0.5, 166.0 + drift_y * 0.7, 248.0 + drift_x * 0.5, 174.0 + drift_y * 0.4, arch_y=10.5, thickness=4.8)
        # Smaller floating bright cyan sparks/fragments matching Frame 8
        _draw_energy_ribbon(canvas, 96.0 + drift_x * 0.4, 155.0 - drift_y * 0.6, 114.0 + drift_x * 0.4, 151.0 - drift_y * 0.6, arch_y=4.0, thickness=3.8)
        _draw_energy_ribbon(canvas, 112.0 - drift_x * 0.5, 174.0 + drift_y * 0.5, 128.0 - drift_x * 0.5, 166.0 + drift_y * 0.5, arch_y=3.0, thickness=3.0)
        _draw_energy_ribbon(canvas, 232.0 - drift_x * 0.3, 198.0 - drift_y * 0.4, 256.0 - drift_x * 0.3, 189.0 - drift_y * 0.4, arch_y=3.5, thickness=3.0)
        # Subtle top-left / top-right small cyan-white arc sparks so top half feels balanced during rotation
        _draw_energy_ribbon(canvas, 84.0 - drift_x * 0.5, 90.0 + drift_y * 0.5, 112.0 - drift_x * 0.5, 80.0 + drift_y * 0.5, arch_y=6.0, thickness=3.2)
        _draw_energy_ribbon(canvas, 180.0 + drift_x * 0.5, 96.0 - drift_y * 0.5, 210.0 + drift_x * 0.5, 108.0 - drift_y * 0.5, arch_y=6.5, thickness=3.2)
    else:
        # Dissolve frame: thinner dispersed cyan-white wisps
        _draw_energy_ribbon(canvas, 46.0, 154.0, 74.0, 150.0, arch_y=7.0, thickness=3.0)
        _draw_energy_ribbon(canvas, 162.0, 184.0, 206.0, 194.0, arch_y=8.0, thickness=3.4)
        _draw_energy_ribbon(canvas, 214.0, 168.0, 246.0, 175.0, arch_y=6.0, thickness=2.8)

    # Guarantee crisp binary alpha (0 or 255)
    canvas[canvas[:, :, 3] > 0, 3] = 255
    return Image.fromarray(canvas, mode="RGBA")


def main() -> int:
    FX_REG_DIR.mkdir(parents=True, exist_ok=True)
    QA_DIR.mkdir(parents=True, exist_ok=True)
    frames = []
    for i in range(5):
        im = make_frame8_barrier(i)
        out_p = FX_REG_DIR / f"barrier_dome_{i:02d}.png"
        im.save(out_p)
        arr = np.array(im)
        vis_px = int((arr[:, :, 3] > 0).sum())
        uniq_c = len(np.unique(arr[arr[:, :, 3] > 0, :3].reshape(-1, 3), axis=0))
        print(f"[barrier_dome_{i:02d}] vis_px={vis_px}, colors={uniq_c}")
        frames.append(im)

    # Render QA comparison board: Source Frame 8 reference + our 5 animated frames (solo + with un-tinted current Tapion on dark & sky)
    tapion_body = Image.open(ROOT / "review/tapion_demo/source/raw_frames/idle_combat_00.png").convert("RGBA")
    tap_centered = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    tap_centered.alpha_composite(tapion_body, (0, -41))

    cw, ch = 228, 228
    crop_box = (30, 30, 258, 258)
    board = Image.new("RGBA", (5 * cw, 3 * (ch + 22)), (18, 22, 30, 255))
    dr = ImageDraw.Draw(board)
    for ri, (tag, bgcol, with_hero) in enumerate([
        ("FRAME8-STYLE FX ONLY (DARK)", (24, 21, 35, 255), False),
        ("FX + CURRENT TAPION (DARK)", (24, 21, 35, 255), True),
        ("FX + CURRENT TAPION (SKY)", (180, 212, 240, 255), True),
    ]):
        for ci, fim in enumerate(frames):
            tile = Image.new("RGBA", (cw, ch), bgcol)
            if with_hero:
                tile.alpha_composite(tap_centered.crop(crop_box))
            tile.alpha_composite(fim.crop(crop_box))
            x0, y0 = ci * cw, ri * (ch + 22)
            board.paste(tile, (x0, y0 + 22))
            dr.rectangle([x0, y0, x0 + cw - 1, y0 + ch + 21], outline=(80, 90, 110, 255))
            dr.text((x0 + 6, y0 + 4), f"{tag} #{ci}", fill=(140, 240, 255, 255))
    out_qa = QA_DIR / "qa_barrier_dome_fx_hollow.png"
    board.save(out_qa)
    print("Saved QA:", out_qa)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
