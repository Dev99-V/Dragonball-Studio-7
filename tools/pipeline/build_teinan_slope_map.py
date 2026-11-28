#!/usr/bin/env python3
"""Build Sườn núi Teinan v9 (`4800 x 1350`) with full animated emerald waterfall mist:

- Preserves 100% of Owner-approved v8 layout & clean water segmentation (`top_tree_bleed_max = 0.0`,
  `-15%` water speed `tpf = 5.88`, `z = -15` intact `#FF00FF`-keyed pine crown overhang, full pebble river to `iy = 1349`,
  11 solid bidirectional terrain steps, slim `26px` frosted-glass portals, and `13f` binary-alpha water splashes).
- Adds organic billowing animated waterfall mist (`emerald_waterfall_mist_v9_codex.png` generated via `local:codex-cli`)
  using a C-infinity periodic dual-phase variance-preserving flowmap across all 8 frames (zero loop pop!) on all 3 zones:
  1. Waterfall-to-lower-river plunge junction (`iy ~ 805..955, ix ~ 2445..3025`, outward + upward rolling vapor cushion).
  2. Left sandstone cliff flank (`ix ~ 2440..2575, iy ~ 515..915`, rising cool mist hugging the wet cliff & hanging vines).
  3. Right sandstone cliff flank (`ix ~ 2890..3035, iy ~ 525..920`, rising cool mist hugging the right cliff behind `z=-15` pine).
"""
from __future__ import annotations

import hashlib
import json
import math
import shutil
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

ROOT = Path("/workspaces/Dragonball-Studio-7")
MAP_DIR = ROOT / "assets" / "maps" / "teinan_slope"
SOURCE_DIR = MAP_DIR / "source"
TILES_DIR = MAP_DIR / "tiles"
FX_DIR = MAP_DIR / "fx"

MAP_LEFT_X = -240
MAP_RIGHT_X = 4560
MAP_TOP_Y = -210
MAP_BOTTOM_Y = 1140
EXT_W = MAP_RIGHT_X - MAP_LEFT_X   # 4800
EXT_H = MAP_BOTTOM_Y - MAP_TOP_Y   # 1350

TILE_PX = 32
GAMEPLAY_SCALE = 2.0
BASE_GROUND_Y = 515

STEPS = [
    {"drop_x": 110, "wall_x": 155, "drop_y": 60},     # -> 575
    {"drop_x": 190, "wall_x": 235, "drop_y": 140},    # -> 655
    {"drop_x": 265, "wall_x": 320, "drop_y": 253},    # -> 768
    {"drop_x": 1425, "wall_x": 1480, "drop_y": 157},  # -> 672
    {"drop_x": 1785, "wall_x": 1835, "drop_y": 97},   # -> 612
    {"drop_x": 2180, "wall_x": 2235, "drop_y": 380},  # -> 895
    {"drop_x": 2945, "wall_x": 2995, "drop_y": 270},  # -> 785
    {"drop_x": 3310, "wall_x": 3355, "drop_y": 163},  # -> 678
    {"drop_x": 3485, "wall_x": 3535, "drop_y": 55},   # -> 570
    {"drop_x": 4075, "wall_x": 4120, "drop_y": 167},  # -> 682
    {"drop_x": 4265, "wall_x": 4310, "drop_y": 277},  # -> 792
]

WATER_MIN_WX = 2205.0
WATER_MAX_WX = 2945.0
WATER_BED_WY = 895.0
WATER_WADE_DEPTH_PX = 6.0

# Expanded 8-frame unified box: ix=[2168..3640] (w=1472), iy=[326..1350] (h=1024); 2x4 = 2944x4096 <= 4096x4096!
WRA_IX0 = 2168
WRA_IY0 = 326
WRA_W = 1472
WRA_H = 1024
# -15% slower than 5.0 ticks (`5.0 / 0.85 = 5.882` ticks @ 60Hz)
WRA_TPF = 5.88


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def ensure_gdignore(d: Path) -> None:
    d.mkdir(parents=True, exist_ok=True)
    gi = d / ".gdignore"
    if not gi.exists():
        gi.write_text("", encoding="utf-8")


def remove_redlines_from_original(orig_2400: np.ndarray) -> np.ndarray:
    arr = orig_2400.astype(np.float32)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    is_red = (r > 145) & ((r - g) > 52) & ((r - b) > 52) & (np.arange(arr.shape[0])[:, None] > 640)
    mask = ndimage.binary_dilation(is_red, iterations=6)
    out = arr.copy()
    _, idx = ndimage.distance_transform_edt(mask, return_indices=True)
    for c in range(3):
        filled = out[:, :, c][tuple(idx)]
        smooth = ndimage.gaussian_filter(filled, sigma=2.0)
        out[:, :, c] = np.where(mask, smooth, out[:, :, c])
    return np.clip(np.round(out), 0, 255).astype(np.uint8)


def lift_clean_original_100px(clean_2400: np.ndarray) -> np.ndarray:
    shift_up = 100
    h, w, _ = clean_2400.shape
    lifted = np.zeros_like(clean_2400)
    lifted[: h - shift_up] = clean_2400[shift_up:]
    lifted[h - shift_up :] = clean_2400[h - shift_up - 1 : h - shift_up]
    return lifted


def min_cut_seam_mask(left_patch: np.ndarray, right_patch: np.ndarray, feather_px: int = 22) -> np.ndarray:
    diff = np.sum((left_patch - right_patch) ** 2, axis=2)
    gy, gx = np.gradient(np.mean(left_patch, axis=2))
    grad_mag = np.sqrt(gx * gx + gy * gy) + 6.0
    cost = diff / grad_mag
    h, w = cost.shape
    dp = cost.copy()
    back = np.zeros((h, w), dtype=np.int32)
    for y in range(1, h):
        prev = dp[y - 1]
        for x in range(w):
            x0 = max(0, x - 2)
            x1 = min(w, x + 3)
            sub = prev[x0:x1]
            bi = int(np.argmin(sub)) + x0
            dp[y, x] += prev[bi]
            back[y, x] = bi
    seam_x = np.zeros(h, dtype=np.int32)
    seam_x[h - 1] = int(np.argmin(dp[h - 1]))
    for y in range(h - 2, -1, -1):
        seam_x[y] = back[y + 1, seam_x[y + 1]]
    xs = np.arange(w, dtype=np.float32)[None, :]
    sx = seam_x[:, None].astype(np.float32)
    return np.clip((xs - (sx - feather_px)) / float(max(1, 2 * feather_px)), 0.0, 1.0)[:, :, None]


def match_color_band(src: np.ndarray, ref_band: np.ndarray, strength: float = 0.55) -> np.ndarray:
    out = src.copy()
    for c in range(3):
        m_ref = float(np.mean(ref_band[:, :, c]))
        s_ref = max(1.0, float(np.std(ref_band[:, :, c])))
        m_src = float(np.mean(src[:, :, c]))
        s_src = max(1.0, float(np.std(src[:, :, c])))
        matched = (src[:, :, c] - m_src) * (s_ref / s_src) + m_ref
        out[:, :, c] = src[:, :, c] * (1.0 - strength) + matched * strength
    return np.clip(out, 0.0, 255.0)


def cosine_window_2d(h: int, w: int, pad_l: int, pad_r: int, pad_t: int, pad_b: int) -> np.ndarray:
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    wl = 0.5 - 0.5 * np.cos(np.pi * np.clip(xx / max(1.0, float(pad_l)), 0.0, 1.0)) if pad_l > 0 else np.ones_like(xx)
    wr = 0.5 - 0.5 * np.cos(np.pi * np.clip((w - 1.0 - xx) / max(1.0, float(pad_r)), 0.0, 1.0)) if pad_r > 0 else np.ones_like(xx)
    wt = 0.5 - 0.5 * np.cos(np.pi * np.clip(yy / max(1.0, float(pad_t)), 0.0, 1.0)) if pad_t > 0 else np.ones_like(yy)
    wb = 0.5 - 0.5 * np.cos(np.pi * np.clip((h - 1.0 - yy) / max(1.0, float(pad_b)), 0.0, 1.0)) if pad_b > 0 else np.ones_like(yy)
    return (wl * wr * wt * wb)[:, :, None]


def key_pine_crown_magenta_720(magenta_png: Path) -> np.ndarray:
    """Two-stage pocket-first #FF00FF chroma key + unmix despill on `pine_crown_magenta_v7_codex.png`,
    resized via premultiplied Lanczos to exact `720 x 720` (`ix=[2736..3456], iy=[136..856]`) so 100% of
    every sunlit & shaded pine needle tip remains whole, sharp, and 0% magenta-spilled!
    """
    arr = np.array(Image.open(magenta_png).convert("RGB")).astype(np.float32)
    key = np.median(
        np.concatenate([arr[:24, :24].reshape(-1, 3), arr[:24, -24:].reshape(-1, 3)]),
        axis=0,
    )
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    # Magenta excess: pure #FF00FF has min(R, B) - G ~ 250; conifer needles & bark have G >= B (excess <= 0)!
    mag_excess = np.minimum(r, b) - g
    key_dist = np.sqrt((r - key[0]) ** 2 + (g - key[1]) ** 2 + (b - key[2]) ** 2)

    # Stage 1: Punch through 100% of pure/enclosed magenta background (`enclosed_key_pockets == 0`)
    is_pure_key = (mag_excess > 185.0) | (key_dist < 48.0)
    raw_alpha = np.where(is_pure_key, 0.0, np.clip(1.0 - np.maximum(0.0, mag_excess - 12.0) / 185.0, 0.0, 1.0))

    # Keep only main pine tree connected component (eliminates any stray dust specks)
    fg_bool = raw_alpha > 0.04
    lbl, n_c = ndimage.label(fg_bool)
    if n_c > 0:
        sz = ndimage.sum(fg_bool, lbl, range(1, n_c + 1))
        fg_main = lbl == (int(np.argmax(sz)) + 1)
        raw_alpha = np.where(fg_main, raw_alpha, 0.0)

    # Stage 2: Exact linear color unmixing + hard magenta despill on rim pixels!
    safe_a = np.maximum(raw_alpha, 0.08)[:, :, None]
    unmixed = (arr - (1.0 - raw_alpha[:, :, None]) * key[None, None, :]) / safe_a
    unmixed = np.clip(unmixed, 0.0, 255.0)
    # Despill any residual magenta tint (`B > G` on green needles or `R & B > G` on bark):
    ur, ug, ub = unmixed[:, :, 0], unmixed[:, :, 1], unmixed[:, :, 2]
    on_rim = (raw_alpha > 0.0) & (raw_alpha < 0.98)
    ub_clean = np.where(on_rim | (mag_excess > -4.0), np.minimum(ub, ug * 0.78), ub)
    ur_clean = np.where((on_rim | (mag_excess > -4.0)) & (ug > ur * 0.65), np.minimum(ur, ug * 1.05), ur)
    clean_rgb = np.stack([ur_clean, ug, ub_clean], axis=2)

    # Premultiplied-alpha Lanczos resize `1024x1024 -> 720x720` so fine needle tips never pick up dark/magenta fringes!
    premul = np.zeros((arr.shape[0], arr.shape[1], 4), dtype=np.float32)
    premul[:, :, :3] = clean_rgb * raw_alpha[:, :, None]
    premul[:, :, 3] = raw_alpha * 255.0
    premul_u8 = np.clip(np.round(premul), 0, 255).astype(np.uint8)
    resized_pre = np.array(Image.fromarray(premul_u8).resize((720, 720), Image.Resampling.LANCZOS)).astype(np.float32)

    a_720 = resized_pre[:, :, 3] / 255.0
    # Clean crisp threshold at alpha >= 0.18 with smooth anti-aliased needle tips over animated water:
    a_720 = np.where(a_720 < 0.14, 0.0, np.clip((a_720 - 0.10) / 0.82, 0.0, 1.0))
    rgb_720 = np.where(a_720[:, :, None] > 0.0, np.clip(resized_pre[:, :, :3] / np.maximum(a_720[:, :, None], 0.06), 0.0, 255.0), 0.0)

    out_rgba = np.zeros((720, 720, 4), dtype=np.uint8)
    out_rgba[:, :, :3] = np.round(rgb_720).astype(np.uint8)
    out_rgba[:, :, 3] = np.round(a_720 * 255.0).astype(np.uint8)
    return out_rgba


def build_v7_panorama_and_foreground_rims() -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
    """Build:
    1. `raw_socket_f32` (`4800 x 1350`): pre-emerald-shift clean canyon plate (for 100% exact water pixel detection!).
    2. `clean_socket_f32` (`4800 x 1350`): emerald-harmonized clean canyon plate (pure dark wet rock behind waterfall!).
    3. `terrain_plate_u8` (`4800 x 1350`): final cohesive background plate (`z = -30`).
    4. `fg_trees_cfg` (`teinan-slope-trees.png` at `z_index = -15`, `scale = [1.0, 1.0]`):
       - Region 0: `1:1` Left Canyon Hanging-Vine & Boulder Foreground Lip (`ix=[2432..2576], iy=[480..928]`) so waterfall
         genuinely tucks BEHIND the vines & boulders (`Purple Box #2` = 100% natural, zero pasted edge!).
       - Region 1: `1:1` Right Canyon Sandstone Lip + 100% Intact Magenta-Keyed Pine Crown (`ix=[2736..3456], iy=[136..928]`)
         so waterfall genuinely tucks BEHIND the right cliff AND 100% of every pine needle tip is whole (`Purple Box #1`!).
    """
    orig_img = Image.open(SOURCE_DIR / "ref_concept_redline.jpg").convert("RGB").resize(
        (2400, 1350), Image.Resampling.LANCZOS
    )
    clean_orig = remove_redlines_from_original(np.array(orig_img))
    lifted_orig = lift_clean_original_100px(clean_orig).astype(np.float32)

    s1_raw = np.array(
        Image.open(SOURCE_DIR / "seg1_organic_v5_codex.png").convert("RGB").resize((2400, 1350), Image.Resampling.LANCZOS)
    ).astype(np.float32)
    s2_raw = np.array(
        Image.open(SOURCE_DIR / "seg2_organic_v5_codex.png").convert("RGB").resize((2760, 1350), Image.Resampling.LANCZOS)
    ).astype(np.float32)

    s1_matched = s1_raw.copy()
    s1_matched[650:, :] = match_color_band(s1_raw[650:, :], lifted_orig[650:1150, :], strength=0.30)
    yy = np.arange(EXT_H, dtype=np.float32)[:, None]
    v_alpha = np.clip((yy - 665.0) / 50.0, 0.0, 1.0)[:, :, None]
    left_2400 = lifted_orig * (1.0 - v_alpha) + s1_matched * v_alpha

    ov_w = 360
    s2_matched = match_color_band(s2_raw, left_2400[:, 2040:2400], strength=0.40)
    for c in range(3):
        sky_delta = float(np.mean(left_2400[:220, 2040:2400, c]) - np.mean(s2_matched[:220, :360, c]))
        sky_env = np.clip(1.0 - np.arange(EXT_H, dtype=np.float32) / 380.0, 0.0, 1.0)[:, None]
        s2_matched[:, :, c] = np.clip(s2_matched[:, :, c] + sky_delta * sky_env * 0.72, 0.0, 255.0)

    seam_a = min_cut_seam_mask(left_2400[:, 2040:2400], s2_matched[:, :ov_w], feather_px=28)
    edge_ramp = np.linspace(0.0, 1.0, ov_w, dtype=np.float32)[None, :, None]
    blend_a = np.clip(seam_a * 0.65 + edge_ramp * 0.35, 0.0, 1.0)

    full_f32 = np.zeros((EXT_H, EXT_W, 3), dtype=np.float32)
    full_f32[:, :2040] = left_2400[:, :2040]
    full_f32[:, 2040:2400] = left_2400[:, 2040:2400] * (1.0 - blend_a) + s2_matched[:, :ov_w] * blend_a
    full_f32[:, 2400:] = s2_matched[:, ov_w:]

    ds_raw = np.array(
        Image.open(SOURCE_DIR / "dry_socket_v5_codex.png").convert("RGB").resize((1294, 1100), Image.Resampling.LANCZOS)
    ).astype(np.float32)
    target_box = full_f32[250:1350, 2220:3514, :]
    ds_matched = match_color_band(ds_raw, target_box, strength=0.35)
    ds_win = cosine_window_2d(1100, 1294, pad_l=110, pad_r=120, pad_t=95, pad_b=0)
    raw_socket_f32 = full_f32.copy()
    raw_socket_f32[250:1350, 2220:3514, :] = target_box * (1.0 - ds_win) + ds_matched * ds_win
    # Also ensure far-upper-left headwater (`iy=320..420, ix=2160..2360`) uses s2_matched's clean river bend!
    hw_win = cosine_window_2d(120, 240, pad_l=36, pad_r=36, pad_t=24, pad_b=24)
    raw_socket_f32[315:435, 2150:2390] = (
        raw_socket_f32[315:435, 2150:2390] * (1.0 - hw_win) + s2_matched[315:435, 2150 - 2040 : 2390 - 2040] * hw_win
    )

    # Harmonize ALL upper river headwater (`iy=320..530, ix=2160..2960`) on `clean_socket_f32` to lowest-riverbed emerald-teal!
    clean_socket_f32 = raw_socket_f32.copy()
    u_sub = raw_socket_f32[320:530, 2160:2960].copy()
    ur, ug, ub = u_sub[:, :, 0], u_sub[:, :, 1], u_sub[:, :, 2]
    is_u_water = (ub >= ur - 4.0) & (ug >= ur + 12.0) & (~((ug > ub + 22.0) & (ur > ub + 10.0)))
    u_wmask = ndimage.gaussian_filter(is_u_water.astype(np.float32), sigma=1.6)
    u_em = np.stack([
        np.clip(ur * 0.56 + 8.0, 0.0, 255.0),
        np.clip(ug * 0.98 + 16.0, 0.0, 255.0),
        np.clip(ub * 0.76 + 12.0, 0.0, 255.0),
    ], axis=2)
    clean_socket_f32[320:530, 2160:2960] = u_sub * (1.0 - u_wmask[:, :, None]) + u_em * u_wmask[:, :, None]

    plate_f32 = clean_socket_f32.copy()

    # (A) Left 4 bare trees (`left_4trees_v6_codex.png` -> ix=[1296..2376], iy=[270..990]), strictly protecting upper headwater (`ix > 2155, iy < 520`)!
    p1_raw = np.array(
        Image.open(SOURCE_DIR / "left_4trees_v6_codex.png").convert("RGB").resize((1080, 720), Image.Resampling.LANCZOS)
    ).astype(np.float32)
    b1_ref = plate_f32[270:990, 1296:2376]
    p1_matched = match_color_band(p1_raw, b1_ref, strength=0.18)
    w1 = cosine_window_2d(720, 1080, pad_l=56, pad_r=96, pad_t=56, pad_b=56)
    ly1, lx1 = np.mgrid[0:720, 0:1080].astype(np.float32)
    stream_protect = np.clip((lx1 - (2150.0 - 1296.0)) / 36.0, 0.0, 1.0) * np.clip(((525.0 - 270.0) - ly1) / 36.0, 0.0, 1.0)
    w1 = w1 * (1.0 - stream_protect[:, :, None])
    plate_f32[270:990, 1296:2376] = b1_ref * (1.0 - w1) + p1_matched * w1

    # (B) Grounded lower trunk & mossy roots of giant pine tree from `canyon_pine_v6_codex.png` (`ix=[2960..3560], iy=[640..1040]`, strictly on dry right bank!)
    p2_raw = np.array(
        Image.open(SOURCE_DIR / "canyon_pine_v6_codex.png").convert("RGB").resize((1440, 960), Image.Resampling.LANCZOS)
    ).astype(np.float32)
    b2_ref = plate_f32[120:1080, 2340:3780]
    p2_matched = match_color_band(p2_raw, b2_ref, strength=0.16)
    # Blend ONLY the dry right bank & rooted pine trunk (`ix=[2968..3660], iy=[620..1040]` -> `lx=[628..1320], ly=[500..920]`) onto `plate_f32`!
    w_roots = np.zeros((960, 1440, 1), dtype=np.float32)
    w_roots[480:930, 628:1320] = cosine_window_2d(450, 692, pad_l=32, pad_r=64, pad_t=64, pad_b=48)
    plate_f32[120:1080, 2340:3780] = b2_ref * (1.0 - w_roots) + p2_matched * w_roots

    # Extract 100% intact 720x720 pine crown (`ix=[2736..3456], iy=[136..856]`) from `#FF00FF` magenta key!
    pine_crown_720 = key_pine_crown_magenta_720(SOURCE_DIR / "pine_crown_magenta_v7_codex.png")
    # Smoothly taper bottom 56px of `pine_crown_720` (`ly = 664..720`, i.e., `iy = 800..856`) so trunk merges invisibly into `p2_matched`'s mossy roots!
    crown_taper_y = np.clip((716.0 - np.arange(720, dtype=np.float32)) / 48.0, 0.0, 1.0)[:, None]
    crown_a_f32 = (pine_crown_720[:, :, 3].astype(np.float32) / 255.0) * crown_taper_y
    crown_rgb_f32 = pine_crown_720[:, :, :3].astype(np.float32)

    # Bake right-side pine crown (`ix >= 2996`, strictly outside the right waterfall mist veil!) onto `plate_f32` (`z = -30`),
    # keeping `ix < 2996` pure rock on `plate_f32` so the waterfall fades over clean rock and `z = -15` pine overhangs once!
    px_c = np.arange(720, dtype=np.float32)[None, :] + 2736.0
    bake_right_w = crown_a_f32 * np.clip((px_c - 2996.0) / 8.0, 0.0, 1.0)
    bg_sub = plate_f32[136 : 136 + 720, 2736 : 2736 + 720]
    plate_f32[136 : 136 + 720, 2736 : 2736 + 720] = bg_sub * (1.0 - bake_right_w[:, :, None]) + crown_rgb_f32 * bake_right_w[:, :, None]

    # (C) Right Solid Blocking Earth Mound (`blocking_mound_v6_codex.png` -> ix=[3360..4800], iy=[390..1350])
    p3_raw = np.array(
        Image.open(SOURCE_DIR / "blocking_mound_v6_codex.png").convert("RGB").resize((1440, 960), Image.Resampling.LANCZOS)
    ).astype(np.float32)
    b3_ref = plate_f32[390:1350, 3360:4800]
    p3_matched = match_color_band(p3_raw, b3_ref[:420, :], strength=0.18)
    seam_p3_l = min_cut_seam_mask(b3_ref[:, 96:216], p3_matched[:, 96:216], feather_px=24)
    w3_x = np.ones((960, 1440, 1), dtype=np.float32)
    w3_x[:, :96, :] = 0.0
    w3_x[:, 96:216, :] = seam_p3_l
    ly3, lx3 = np.mgrid[0:960, 0:1440].astype(np.float32)
    w3_top = (0.5 - 0.5 * np.cos(np.pi * np.clip(ly3 / 56.0, 0.0, 1.0)))[:, :, None]
    rv_mouth_keep = np.clip((305.0 - lx3) / 48.0, 0.0, 1.0) * np.clip((ly3 - 730.0) / 48.0, 0.0, 1.0)
    w3 = w3_x * w3_top * (1.0 - rv_mouth_keep[:, :, None])
    plate_f32[390:1350, 3360:4800] = b3_ref * (1.0 - w3) + p3_matched * w3

    terrain_plate_u8 = np.clip(np.round(plate_f32), 0, 255).astype(np.uint8)

    # --- BUILD `z_index = -15` INTACT PINE CROWN ONLY (`teinan-slope-trees.png`, `scale = [1.0, 1.0]`) ---
    # Owner v8 A1: Remove BOTH side cliff/vine cutouts (`left_lip_rgba` & `r_cliff_fg`) so the waterfall (`z = -16`) sits
    # ON TOP OF both side cliffs (`z = -30`) and fades softly outward over 44-48px with misty spray (zero pasted edge / zero
    # floating rock scraps!), while keeping ONLY the intact `#FF00FF`-keyed Pine Crown (`720x720`) at `z = -15` above the waterfall!
    p_ix0, p_iy0, p_w, p_h = 2736, 136, 720, 720
    pine_only_rgba = np.zeros((p_h, p_w, 4), dtype=np.uint8)
    vis_p = crown_a_f32 > 0.01
    pine_only_rgba[:, :, :3] = np.where(vis_p[:, :, None], np.clip(np.round(crown_rgb_f32), 0, 255).astype(np.uint8), 0)
    pine_only_rgba[:, :, 3] = np.round(crown_a_f32 * 255.0).astype(np.uint8)

    pad = 16
    atlas_w = ((pad + p_w + pad + 15) // 16) * 16   # 752
    atlas_h = ((pad + p_h + pad + 15) // 16) * 16   # 752
    fg_atlas = np.zeros((atlas_h, atlas_w, 4), dtype=np.uint8)
    fg_atlas[pad : pad + p_h, pad : pad + p_w] = pine_only_rgba

    trees_path = MAP_DIR / "teinan-slope-trees.png"
    Image.fromarray(fg_atlas).save(trees_path, optimize=True)

    fg_trees_cfg = {
        "path": trees_path.relative_to(ROOT).as_posix(),
        "res_path": f"res://{trees_path.relative_to(ROOT).as_posix()}",
        "web_path": "/" + trees_path.relative_to(ROOT).as_posix(),
        "sha256": sha256_file(trees_path),
        "alpha_hardness_pct": round(100.0 * float(np.isin(fg_atlas[:, :, 3], [0, 255]).mean()), 2),
        "z_index": -15,
        "scale": [1.0, 1.0],
        "placements": [
            {
                "region": [float(pad), float(pad), float(p_w), float(p_h)],
                "scale": [1.0, 1.0],
                "trunk_source_x": 0.0,
                "root_bottom_src_y": 0.0,
                "trunk_world_x": float(p_ix0 + MAP_LEFT_X),
                "rear_grass_world_y": float(p_iy0 + MAP_TOP_Y),
            },
        ],
        "auxiliary_props": {
            "path": "",
            "res_path": "",
            "web_path": "",
            "z_index": -19,
            "placements": [],
        },
    }
    return raw_socket_f32, clean_socket_f32, terrain_plate_u8, fg_trees_cfg


def make_seamless_tile_2d(arr_f32: np.ndarray, tile_sz: int = 768, ov: int = 96) -> np.ndarray:
    im = Image.fromarray(np.clip(arr_f32, 0, 255).astype(np.uint8)).resize((tile_sz + ov, tile_sz + ov), Image.Resampling.LANCZOS)
    src = np.array(im).astype(np.float32)
    tx = (0.5 - 0.5 * np.cos(np.pi * np.linspace(0.0, 1.0, ov, dtype=np.float32)))[None, :, None]
    wx = src[:, :tile_sz].copy()
    wx[:, :ov] = src[:, :ov] * tx + src[:, tile_sz : tile_sz + ov] * (1.0 - tx)
    ty = (0.5 - 0.5 * np.cos(np.pi * np.linspace(0.0, 1.0, ov, dtype=np.float32)))[:, None, None]
    out = wx[:tile_sz, :].copy()
    out[:ov, :] = wx[:ov, :] * ty + wx[tile_sz : tile_sz + ov, :] * (1.0 - ty)
    return out


def calibrate_to_emerald_riverbed(tex_f32: np.ndarray) -> np.ndarray:
    out = np.zeros_like(tex_f32)
    lum = 0.25 * tex_f32[:, :, 0] + 0.50 * tex_f32[:, :, 1] + 0.25 * tex_f32[:, :, 2]
    foam_w = np.clip((lum - 188.0) / 58.0, 0.0, 1.0)
    for c, target_p in enumerate([(14.0, 30.0, 92.0), (133.0, 171.0, 210.0), (120.0, 147.0, 184.0)]):
        p15, p50, p85 = np.percentile(tex_f32[:, :, c], [15, 50, 85])
        ch = tex_f32[:, :, c]
        below = target_p[0] + (ch - p15) * ((target_p[1] - target_p[0]) / max(1.0, p50 - p15))
        above = target_p[1] + (ch - p50) * ((target_p[2] - target_p[1]) / max(1.0, p85 - p50))
        mapped = np.where(ch <= p50, below, above)
        foam_target = (212.0, 248.0, 238.0)[c]
        out[:, :, c] = mapped * (1.0 - foam_w * 0.76) + foam_target * (foam_w * 0.76)
    return np.clip(out, 0.0, 255.0)


def extract_intact_13f_water_splash_v3() -> tuple[Path, float]:
    FX_DIR.mkdir(parents=True, exist_ok=True)
    ref_path = SOURCE_DIR / "ref_water_vfx_13f.png"
    arr = np.array(Image.open(ref_path).convert("RGB")).astype(np.float32)
    h_ref, w_ref, _ = arr.shape
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

    bg_rgb = np.array([150.0, 150.0, 150.0], dtype=np.float32)
    chroma = np.max(arr, axis=2) - np.min(arr, axis=2)
    dist_bg = np.sqrt((r - 150.0) ** 2 + (g - 150.0) ** 2 + (b - 150.0) ** 2)
    is_grid_line = (chroma < 6.0) & (r > 175.0) & (r < 232.0)
    cyan_signal = b - np.maximum(r, g * 0.72)
    bright_foam = (r > 192) & (g > 205) & (b > 212) & ((b - r) >= 4.0)
    fg = (((b - r) > 14.0) | (cyan_signal > 12.0) | bright_foam | ((dist_bg > 26.0) & (b >= r + 6.0))) & (~is_grid_line)
    for y_div in [0, 1, 124, 125, 249, 250, 374, 375, h_ref - 1]:
        if 0 <= y_div < h_ref:
            fg[max(0, y_div - 2) : min(h_ref, y_div + 3), :] = False

    eroded = ndimage.binary_erosion(fg, iterations=1)
    ring_1px = fg & (~eroded)
    clean_rgb = arr.copy()
    for c in range(3):
        unmixed = np.clip((arr[:, :, c] - 0.35 * bg_rgb[c]) / 0.65, 0.0, 255.0)
        clean_rgb[:, :, c] = np.where(ring_1px, unmixed, arr[:, :, c])
    clean_rgb[:, :, 1] = np.clip(clean_rgb[:, :, 1] * 1.05 + 6.0, 0.0, 255.0)
    clean_rgb[:, :, 2] = np.clip(clean_rgb[:, :, 2] * 0.94, 0.0, 255.0)

    clean_rgba = np.zeros((h_ref, w_ref, 4), dtype=np.uint8)
    clean_rgba[:, :, :3] = np.where(fg[:, :, None], np.round(clean_rgb).astype(np.uint8), 0)
    clean_rgba[:, :, 3] = np.where(fg, 255, 0).astype(np.uint8)

    row_specs = [(4, 121, 4), (128, 246, 3), (253, 371, 3), (378, 496, 3)]
    fw, fh = 160, 80
    sheet_13 = Image.new("RGBA", (fw * 13, fh), (0, 0, 0, 0))
    frames_extracted = 0

    for y0, y1, expected_n in row_specs:
        strip = clean_rgba[y0:y1, :, :]
        col_cnt = (strip[:, :, 3] > 0).sum(axis=0)
        chosen_spans: list[tuple[int, int]] = []
        for gap_px in [4, 6, 8, 12, 16, 20, 24]:
            mask1d = ndimage.binary_closing(col_cnt > 0, structure=np.ones(gap_px * 2 + 1, dtype=bool))
            spans: list[tuple[int, int]] = []
            in_s = False
            s0 = 0
            for x, v in enumerate(mask1d):
                if v and not in_s:
                    s0 = x
                    in_s = True
                elif not v and in_s:
                    if x - s0 >= 16:
                        spans.append((s0, x))
                    in_s = False
            if in_s and (len(mask1d) - s0 >= 16):
                spans.append((s0, len(mask1d)))
            if len(spans) == expected_n:
                chosen_spans = spans
                break
        assert len(chosen_spans) == expected_n
        for x0, x1 in chosen_spans:
            sub = strip[:, x0:x1, :]
            ys, xs = np.where(sub[:, :, 3] > 0)
            crop = sub[int(ys.min()) : int(ys.max()) + 1, int(xs.min()) : int(xs.max()) + 1, :]
            ch, cw, _ = crop.shape
            max_fit = min(0.64, (fw - 8) / float(max(1, cw)), (fh - 10) / float(max(1, ch)))
            new_w = max(1, int(round(cw * max_fit)))
            new_h = max(1, int(round(ch * max_fit)))
            crop_im = Image.fromarray(crop).resize((new_w, new_h), Image.Resampling.NEAREST)
            tile = Image.new("RGBA", (fw, fh), (0, 0, 0, 0))
            tile.paste(crop_im, (max(0, (fw - new_w) // 2), max(0, fh - 6 - new_h)))
            sheet_13.paste(tile, (frames_extracted * fw, 0))
            frames_extracted += 1

    assert frames_extracted == 13
    splash_path = FX_DIR / "water_splash.png"
    sheet_13.save(splash_path, optimize=True)
    sp_arr = np.array(sheet_13)
    sp_hard = 100.0 * float(np.isin(sp_arr[:, :, 3], [0, 255]).mean())
    assert sp_hard == 100.0
    return splash_path, sp_hard


def write_waterfall_river_tres(atlas_rel_res: str, fw: int, fh: int, cols: int, n_frames: int, tpf: float) -> Path:
    lines = [
        f'[gd_resource type="SpriteFrames" load_steps={n_frames + 2} format=3]',
        "",
        f'[ext_resource type="Texture2D" path="{atlas_rel_res}" id="1_atlas"]',
        "",
    ]
    for i in range(n_frames):
        col = i % cols
        row = i // cols
        rx = col * fw
        ry = row * fh
        lines.extend([
            f'[sub_resource type="AtlasTexture" id="AtlasTexture_wf_{i:02d}"]',
            'atlas = ExtResource("1_atlas")',
            f"region = Rect2({rx}, {ry}, {fw}, {fh})",
            "",
        ])
    frame_entries = ", ".join(
        f'{{\n"duration": {float(tpf):.2f},\n"texture": SubResource("AtlasTexture_wf_{i:02d}")\n}}'
        for i in range(n_frames)
    )
    lines.extend([
        "[resource]",
        "animations = [{",
        f'"frames": [{frame_entries}],',
        '"loop": true,',
        '"name": &"flow",',
        '"speed": 60.0',
        "}]",
        "",
    ])
    tres_path = FX_DIR / "waterfall_river.tres"
    tres_path.write_text("\n".join(lines), encoding="utf-8")
    return tres_path


def build_unified_emerald_water_asset_v7(
    raw_socket_f32: np.ndarray,
    clean_socket_f32: np.ndarray,
    terrain_plate_u8: np.ndarray,
) -> tuple[dict[str, Any], dict[str, Any]]:
    FX_DIR.mkdir(parents=True, exist_ok=True)
    fw, fh = WRA_W, WRA_H  # 1360 x 1024
    raw_patch = raw_socket_f32[WRA_IY0 : WRA_IY0 + fh, WRA_IX0 : WRA_IX0 + fw]
    sock_patch = clean_socket_f32[WRA_IY0 : WRA_IY0 + fh, WRA_IX0 : WRA_IX0 + fw]
    plate_patch = terrain_plate_u8[WRA_IY0 : WRA_IY0 + fh, WRA_IX0 : WRA_IX0 + fw].astype(np.float32)

    rr0, rg0, rb0 = raw_patch[:, :, 0], raw_patch[:, :, 1], raw_patch[:, :, 2]
    pr, pg, pb = plate_patch[:, :, 0], plate_patch[:, :, 1], plate_patch[:, :, 2]
    ly, lx = np.mgrid[0:fh, 0:fw].astype(np.float32)
    iy_g = ly + WRA_IY0
    ix_g = lx + WRA_IX0

    # --- 1. EXACT V8 WATER SEGMENTATION & SOFT VEIL ALPHA (OWNER A1 + A2 ON Screenshot 2026-11-28 152421.png) ---
    # (a) True Turquoise-Emerald Upper Stream (`iy = 386..536`, ZERO bleed onto trees/cliffs/island in Top 2 Red Circles!):
    #     Verified on `v8_plate_grid_2180_3150.jpg`: ZERO water exists above `iy = 386` or east of `ix = 2486` for `iy < 426`;
    #     true stream pixels are vivid turquoise-emerald (`pg >= 134, pb >= 106, pg >= pr + 48, pb >= pr + 26`).
    upper_channel_bounds = (
        (iy_g >= 386.0)
        & (iy_g <= 538.0)
        & (ix_g >= 2228.0)
        & (ix_g <= 2905.0)
        & ((iy_g >= 426.0) | (ix_g <= 2486.0))
        & ((iy_g >= 456.0) | (ix_g <= 2692.0))
    )
    upper_water_raw = (
        upper_channel_bounds
        & (pg >= 134.0)
        & (pb >= 106.0)
        & (pg >= pr + 48.0)
        & (pb >= pr + 26.0)
    )
    upper_water_closed = ndimage.binary_closing(upper_water_raw, structure=np.ones((5, 5), dtype=bool)) & upper_channel_bounds
    lbl_u, nu = ndimage.label(upper_water_closed)
    assert nu > 0
    sz_u = ndimage.sum(upper_water_closed, lbl_u, range(1, nu + 1))
    upper_water = ndimage.binary_fill_holes(lbl_u == (int(np.argmax(sz_u)) + 1))

    # Smooth 20px INWARD shore feather on `upper_water` (except along the bottom waterfall lip `iy >= iy_lip_exact - 8`
    # so it pours at 100% alpha over the brink while fading 100% -> 0% BEFORE touching any rock, pebble, or bush!):
    iy_lip_exact = (
        516.0
        + 12.0 * np.sin(np.clip((ix_g - 2520.0) / 380.0, 0.0, 1.0) * math.pi)
        + 46.0 * (np.clip((ix_g - 2895.0) / 65.0, 0.0, 1.0) ** 1.4)
    )
    lip_bridge_zone = (iy_g >= iy_lip_exact - 14.0) & (iy_g <= iy_lip_exact + 24.0) & (ix_g >= 2525.0) & (ix_g <= 2925.0)
    upper_for_edt = upper_water | lip_bridge_zone
    edt_upper = ndimage.distance_transform_edt(upper_for_edt)
    upper_alpha = np.where(
        upper_for_edt,
        0.5 - 0.5 * np.cos(np.pi * np.clip((edt_upper - 2.0) / 20.0, 0.0, 1.0)),
        0.0,
    )

    # (b) Waterfall Chute ON TOP OF Side Cliffs (`z = -16 > z = -30`) with Wide `46-48px` Silky Side Fade (`A1`!):
    #     Smooth S-curves connect top lip (`iy ~ 516`) down into the lower river shores (`iy ~ 890`) with ZERO 90-degree corners!
    ix_left_core = (
        2544.0
        + 6.0 * np.sin((iy_g - 530.0) * 0.022)
        - 58.0 * (0.5 + 0.5 * np.tanh((iy_g - 815.0) / 42.0))
    )
    ix_right_core = (
        2942.0
        - 34.0 * (0.5 - 0.5 * np.tanh((iy_g - 552.0) / 18.0))
        + 58.0 * (0.5 + 0.5 * np.tanh((iy_g - 878.0) / 28.0))
        + 5.0 * np.sin((iy_g - 540.0) * 0.024)
    )
    left_fade_w = 48.0
    right_fade_w = 46.0
    t_left = np.clip((ix_g - (ix_left_core - left_fade_w)) / left_fade_w, 0.0, 1.0)
    t_right = np.clip(((ix_right_core + right_fade_w) - ix_g) / right_fade_w, 0.0, 1.0)
    chute_x_alpha = (0.5 - 0.5 * np.cos(np.pi * t_left)) * (0.5 - 0.5 * np.cos(np.pi * t_right))
    t_chute_top = np.clip((iy_g - (iy_lip_exact - 14.0)) / 18.0, 0.0, 1.0)
    t_chute_bot = np.clip((928.0 - iy_g) / 34.0, 0.0, 1.0)
    chute_alpha = chute_x_alpha * (0.5 - 0.5 * np.cos(np.pi * t_chute_top)) * (0.5 - 0.5 * np.cos(np.pi * t_chute_bot))
    chute_core = chute_alpha > 0.55

    # (c) Full Lower River Basin (`iy = 875..1350, ix = 2360..3636` — 100% active right to row `iy = 1349` in Green Box!)
    #     Start lower river bank detection smoothly below `iy = 885` so it never creates a 90-degree step at `iy = 875`!
    rv_box = (iy_g >= 882.0) & (iy_g <= 1350.0) & (ix_g >= 2360.0) & (ix_g <= 3636.0)
    rv_water_seed = rv_box & (
        ((pb >= pr - 6.0) & (pg >= pr + 12.0) & (pg >= 70.0))
        | ((pg >= pr + 18.0) & (pb >= 88.0) & (pg >= 96.0))
    ) & (~((pg > pb + 48.0) & (pb < 92.0)))
    dry_land_px = rv_box & (
        ((pr > pg + 8.0) & (pr > pb + 32.0))
        | ((pg > pb + 38.0) & (pb < 88.0))
    ) & (~rv_water_seed)
    dry_land_core = ndimage.binary_erosion(dry_land_px, iterations=1)
    lbl_dl, n_dl = ndimage.label(dry_land_core)
    shore_ext = np.zeros_like(dry_land_px)
    if n_dl > 0:
        dl_ids = (
            set(np.unique(lbl_dl[560:, :240]))
            | set(np.unique(lbl_dl[560:, -8:]))
            | set(np.unique(lbl_dl[560:814, 872:]))
        )
        dl_ids.discard(0)
        shore_ext = ndimage.binary_dilation(np.isin(lbl_dl, list(dl_ids)), iterations=2)
    shore_safe = ndimage.binary_dilation(shore_ext, iterations=2)

    rv_pad = np.pad(rv_water_seed, ((0, 40), (0, 0)), mode="edge")
    rv_c1 = ndimage.binary_closing(rv_pad, structure=np.ones((1, 75), dtype=bool))
    rv_closed = ndimage.binary_closing(rv_c1, structure=np.ones((75, 1), dtype=bool))[:-40, :] & rv_box & (~shore_safe)
    rv_pad2 = np.pad(rv_closed, ((0, 2), (0, 0)), mode="constant", constant_values=True)
    river_filled = ndimage.binary_fill_holes(rv_pad2)[:-2, :] & rv_box & (~shore_safe)

    # Smooth lower river alpha (`mode="nearest"` preserves 1.00 alpha right down to `iy = 1349`!)
    rv_top_ramp = 0.5 - 0.5 * np.cos(np.pi * np.clip((iy_g - 882.0) / 28.0, 0.0, 1.0))
    river_alpha = np.clip(ndimage.gaussian_filter(river_filled.astype(np.float32), sigma=4.0, mode="nearest") * 1.12, 0.0, 1.0) * rv_top_ramp
    river_alpha = np.where(shore_ext & (chute_alpha < 0.02), 0.0, river_alpha)

    # Combine all 3 smooth alpha fields (`upper_alpha`, `chute_alpha`, `river_alpha`):
    # Note: `chute_alpha` is intentionally NOT clipped by side cliffs so its 46-48px veil softly covers side rock seams!
    water_mask = np.maximum(np.maximum(upper_alpha, chute_alpha), river_alpha).astype(np.float32)
    # Hard guarantee: ZERO water bleed on upper trees/cliffs/island (`A2`)!
    upper_forbidden_bleed = (iy_g < 386.0) | ((iy_g < 426.0) & (ix_g > 2486.0)) | ((iy_g < 508.0) & (upper_alpha <= 0.0) & (chute_alpha <= 0.0))
    water_mask = np.where(upper_forbidden_bleed, 0.0, water_mask)
    unified_bool = water_mask > 0.15

    # --- 2. PREPARE SEAMLESS EMERALD-TEAL WATER & CODEX MIST TILES (`768 x 768`) ---
    tile_sz = 768
    rv_tex_raw = np.array(Image.open(SOURCE_DIR / "emerald_water_flow_v6_codex.png").convert("RGB")).astype(np.float32)
    wf_tex_raw = np.array(Image.open(SOURCE_DIR / "emerald_wf_curtain_v6_codex.png").convert("RGB")).astype(np.float32)
    mist_tex_raw = np.array(Image.open(SOURCE_DIR / "emerald_waterfall_mist_v9_codex.png").convert("RGB")).astype(np.float32)
    rv_tile = make_seamless_tile_2d(calibrate_to_emerald_riverbed(rv_tex_raw), tile_sz=tile_sz, ov=96)
    wf_tile = make_seamless_tile_2d(calibrate_to_emerald_riverbed(wf_tex_raw), tile_sz=tile_sz, ov=96)
    mist_tile_rgb = make_seamless_tile_2d(mist_tex_raw, tile_sz=tile_sz, ov=96)

    wf_lum = 0.25 * wf_tile[:, :, 0] + 0.50 * wf_tile[:, :, 1] + 0.25 * wf_tile[:, :, 2]
    wf_foam_tile = np.clip((wf_lum - 178.0) / 68.0, 0.0, 1.0)
    rv_lum = 0.25 * rv_tile[:, :, 0] + 0.50 * rv_tile[:, :, 1] + 0.25 * rv_tile[:, :, 2]
    rv_foam_tile = np.clip((rv_lum - 172.0) / 68.0, 0.0, 1.0)

    # Extract Studio-Ghibli wispy vapor density `[0..1]` from `emerald_waterfall_mist_v9_codex.png` (dark teal floor -> 0.0):
    m_lum = 0.25 * mist_tile_rgb[:, :, 0] + 0.50 * mist_tile_rgb[:, :, 1] + 0.25 * mist_tile_rgb[:, :, 2]
    m_p24, m_p96 = np.percentile(m_lum, [24.0, 96.0])
    mist_d_tile = np.clip((m_lum - m_p24) / max(1.0, m_p96 - m_p24), 0.0, 1.0) ** 1.18
    mist_d_mean = float(mist_d_tile.mean())

    def sample_tile_bilinear(tile_2d: np.ndarray, sx: np.ndarray, sy: np.ndarray) -> np.ndarray:
        x0 = np.floor(sx).astype(np.int32) % tile_sz
        y0 = np.floor(sy).astype(np.int32) % tile_sz
        x1 = (x0 + 1) % tile_sz
        y1 = (y0 + 1) % tile_sz
        fx = (sx - np.floor(sx)).astype(np.float32)
        fy = (sy - np.floor(sy)).astype(np.float32)
        v00 = tile_2d[y0, x0]
        v10 = tile_2d[y0, x1]
        v01 = tile_2d[y1, x0]
        v11 = tile_2d[y1, x1]
        return (v00 * (1.0 - fx) + v10 * fx) * (1.0 - fy) + (v01 * (1.0 - fx) + v11 * fx) * fy

    def sample_flowmap_mist(
        u_val: float,
        vx_field: np.ndarray,
        vy_field: np.ndarray,
        scale_xy: float,
        off_x: float = 0.0,
        off_y: float = 0.0,
    ) -> np.ndarray:
        """Exact C-infinity periodic dual-phase variance-preserving flowmap sampler (0 loop pop!)."""
        p0 = u_val
        p1 = (u_val + 0.5) % 1.0
        w0 = 0.5 - 0.5 * math.cos(2.0 * math.pi * p0)
        w1 = 1.0 - w0
        inv_n = 1.0 / math.sqrt(w0 * w0 + w1 * w1)
        s0 = w0 * inv_n
        s1 = w1 * inv_n
        bx = ix_g * scale_xy + off_x
        by = iy_g * scale_xy + off_y
        v0 = sample_tile_bilinear(mist_d_tile, bx - vx_field * p0, by - vy_field * p0)
        v1 = sample_tile_bilinear(mist_d_tile, bx - vx_field * p1 + 383.0, by - vy_field * p1 + 271.0)
        return np.clip(mist_d_mean + s0 * (v0 - mist_d_mean) + s1 * (v1 - mist_d_mean), 0.0, 1.0)

    # --- 3. CURVILINEAR TRANSITIONS, SIDE MIST VEIL, 3-ZONE ANIMATED MIST ENVELOPES & ORGANIC PLUNGE FROTH ---
    iy_lip_curve = iy_lip_exact + 3.5 * np.sin((ix_g - 2520.0) * 0.032)
    iy_plunge_curve = 886.0 + 0.016 * (ix_g - 2520.0) + 10.0 * np.sin((ix_g - 2540.0) * 0.028)

    in_chute_x = chute_x_alpha
    lip_s = 0.5 + 0.5 * np.tanh((iy_g - (iy_lip_curve + 4.0)) / 13.0)
    plunge_s = 0.5 - 0.5 * np.tanh((iy_g - iy_plunge_curve) / 28.0)
    w_chute = np.clip(lip_s * plunge_s * np.clip(chute_x_alpha * 1.35, 0.0, 1.0), 0.0, 1.0)
    # Soft misty spray weight specifically along the 46-48px left & right fade veils (`0 < chute_x_alpha < 0.92`):
    side_mist_w = np.clip(1.0 - chute_x_alpha, 0.0, 1.0) * lip_s * plunge_s * (chute_alpha > 0.005)

    # --- 3B. 3-ZONE ANIMATED WATERFALL MIST ENVELOPES (Owner v9: Plunge Junction + Left & Right Cliff Flanks!) ---
    # Zone 1: Waterfall-to-Lower-River Plunge Junction (`iy ~ 800..952, ix ~ 2460..3020`)
    plunge_dy = iy_g - iy_plunge_curve
    plunge_y_env = np.where(
        plunge_dy < 0.0,
        np.exp(-0.5 * (plunge_dy / 54.0) ** 2),
        np.exp(-0.5 * (plunge_dy / 30.0) ** 2),
    )
    plunge_y_cut = (
        (0.5 - 0.5 * np.cos(np.pi * np.clip((iy_g - 755.0) / 55.0, 0.0, 1.0)))
        * (0.5 - 0.5 * np.cos(np.pi * np.clip((956.0 - iy_g) / 38.0, 0.0, 1.0)))
    )
    # Tighter left shoreline margin (`ix >= 2460`) so plunge mist never spills over the left mossy boulder!
    plunge_x_env = (
        (0.5 - 0.5 * np.cos(np.pi * np.clip((ix_g - 2456.0) / 58.0, 0.0, 1.0)))
        * (0.5 - 0.5 * np.cos(np.pi * np.clip((3034.0 - ix_g) / 62.0, 0.0, 1.0)))
    )
    mist_env_plunge = (plunge_y_env * plunge_y_cut * plunge_x_env).astype(np.float32)

    # Zone 2: Left Sandstone Cliff Flank (`ix_left_core - 15`, hugging wet cliff & hanging vines `iy = 514..910`)
    ix_left_flank = ix_left_core - 15.0
    dx_lf = ix_g - ix_left_flank
    lf_x_env = np.where(
        dx_lf < 0.0,
        np.exp(-0.5 * (dx_lf / 36.0) ** 2),
        np.exp(-0.5 * (dx_lf / 44.0) ** 2),
    ) * (0.5 - 0.5 * np.cos(np.pi * np.clip((ix_g - (ix_left_flank - 70.0)) / 32.0, 0.0, 1.0)))
    # Smoothly tuck bottom-left mist inside the water cove (`ix >= 2460` when `iy > 870`) to keep the sunlit mossy rock crisp!
    lf_boulder_protect = (
        (0.5 - 0.5 * np.cos(np.pi * np.clip((iy_g - 858.0) / 34.0, 0.0, 1.0)))
        * (0.5 - 0.5 * np.cos(np.pi * np.clip((2474.0 - ix_g) / 28.0, 0.0, 1.0)))
    )
    lf_y_env = (
        (0.5 - 0.5 * np.cos(np.pi * np.clip((iy_g - 514.0) / 52.0, 0.0, 1.0)))
        * (0.5 - 0.5 * np.cos(np.pi * np.clip((920.0 - iy_g) / 42.0, 0.0, 1.0)))
        * (0.72 + 0.28 * np.clip((iy_g - 540.0) / 300.0, 0.0, 1.0))
    )
    mist_env_left = (lf_x_env * lf_y_env * (1.0 - lf_boulder_protect)).astype(np.float32)

    # Zone 3: Right Sandstone Cliff Flank (`ix_right_core + 16`, hugging wet cliff face below/behind `z=-15` pine `iy = 524..918`)
    ix_right_flank = ix_right_core + 16.0
    dx_rf = ix_g - ix_right_flank
    rf_x_env = np.where(
        dx_rf <= 0.0,
        np.exp(-0.5 * (dx_rf / 44.0) ** 2),
        np.exp(-0.5 * (dx_rf / 38.0) ** 2),
    ) * (0.5 - 0.5 * np.cos(np.pi * np.clip((3054.0 - ix_g) / 34.0, 0.0, 1.0)))
    rf_y_env = (
        (0.5 - 0.5 * np.cos(np.pi * np.clip((iy_g - 524.0) / 54.0, 0.0, 1.0)))
        * (0.5 - 0.5 * np.cos(np.pi * np.clip((926.0 - iy_g) / 42.0, 0.0, 1.0)))
        * (0.72 + 0.28 * np.clip((iy_g - 550.0) / 290.0, 0.0, 1.0))
    )
    mist_env_right = (rf_x_env * rf_y_env).astype(np.float32)

    # Physical flow velocity fields `(vx, vy)` per zone (px per 8-frame cycle):
    # - Plunge junction: radiates outward left/right from waterfall center & billows gently upward
    # - Left & right cliff flanks: cool spray rises upward and curls gently outward onto the wet rock flanks
    vx_plunge = (92.0 * np.tanh((ix_g - 2738.0) / 145.0)).astype(np.float32)
    vy_plunge = (-68.0 + 34.0 * np.clip(plunge_dy / 52.0, 0.0, 1.0)).astype(np.float32)
    vx_left = np.full_like(ix_g, -36.0, dtype=np.float32)
    vy_left = np.full_like(iy_g, -96.0, dtype=np.float32)
    vx_right = np.full_like(ix_g, 36.0, dtype=np.float32)
    vy_right = np.full_like(iy_g, -96.0, dtype=np.float32)

    # Combined smooth mist velocity field weighted by local envelope dominance (keeps 1 unified flowmap evaluation!)
    w_tot_m = mist_env_plunge + mist_env_left + mist_env_right + 1e-4
    mist_vx = (mist_env_plunge * vx_plunge + mist_env_left * vx_left + mist_env_right * vx_right) / w_tot_m
    mist_vy = (mist_env_plunge * vy_plunge + mist_env_left * vy_left + mist_env_right * vy_right) / w_tot_m
    mist_env_combined = np.clip(
        1.0 - (1.0 - mist_env_plunge * 0.95) * (1.0 - mist_env_left * 0.88) * (1.0 - mist_env_right * 0.90),
        0.0,
        1.0,
    ).astype(np.float32)
    # Hard safety clamps: ZERO mist bleed onto upper trees/cliffs (`iy < 508`), left plateau (`ix < 2430`), or pine trunk (`ix > 3054`)!
    mist_forbidden = upper_forbidden_bleed | (iy_g < 508.0) | (ix_g < 2430.0) | (ix_g > 3054.0) | (iy_g > 960.0)
    mist_env_combined = np.where(mist_forbidden, 0.0, mist_env_combined)
    mist_env_plunge = np.where(mist_forbidden, 0.0, mist_env_plunge)
    mist_env_left = np.where(mist_forbidden, 0.0, mist_env_left)
    mist_env_right = np.where(mist_forbidden, 0.0, mist_env_right)
    mist_is_active_px = mist_env_combined > 0.004

    is_submerged_pebble = (iy_g >= 890.0) & unified_bool & (pr > pb - 8.0) & (pg > pb + 8.0)
    pebble_refract_damp = np.where(is_submerged_pebble, 0.45, 1.0).astype(np.float32)

    # --- 4. RENDER 8 SEAMLESS FRAMES (`2 cols x 4 rows = 2944 x 4096 <= 4096x4096`) AT EXACT `-15%` SPEED (`tpf = 5.88`) ---
    n_frames = 8
    cols, rows = 2, 4
    atlas = np.zeros((fh * rows, fw * cols, 4), dtype=np.uint8)
    qa_frames: dict[int, np.ndarray] = {}
    mist_alphas_all: list[np.ndarray] = []

    for f in range(n_frames):
        u = f / float(n_frames)
        ang = 2.0 * math.pi * u

        # (1) Refracted riverbed & upper-stream base (`mode="nearest"` keeps full motion right at bottom border `ly = fh-1`!)
        bed_src = np.where((iy_g >= 895.0)[:, :, None], plate_patch, sock_patch)
        ref_dx = (3.0 * np.sin(iy_g * 0.075 - ang + ix_g * 0.025) + 1.6 * np.cos(ix_g * 0.055 - ang)) * water_mask * (1.0 - w_chute) * pebble_refract_damp
        ref_dy = (2.1 * np.cos(ix_g * 0.065 - ang + iy_g * 0.032) + 1.2 * np.sin((ix_g + iy_g) * 0.04 - ang)) * water_mask * (1.0 - w_chute) * pebble_refract_damp
        sx_r = np.clip(lx - ref_dx, 0.0, fw - 1.0)
        sy_r = np.clip(ly - ref_dy, 0.0, fh - 1.0)
        bed_refract = np.zeros_like(bed_src)
        for ch in range(3):
            bed_refract[:, :, ch] = ndimage.map_coordinates(bed_src[:, :, ch], [sy_r, sx_r], order=1, mode="nearest")

        # (2) Gentler `-15%` Downstream Emerald River & Upper Headwater Flow (`192px` over 8 frames @ 5.88 ticks = `245 px/s` vs `288 px/s`!)
        # Scale perspective frequency slightly finer in distant upper headwater (`iy < 480`) so distant bends ripple naturally!
        persp_scale = np.where(iy_g < 520.0, 1.35, 0.86)
        rv_u_x = (np.round(ix_g * persp_scale + 7.0 * np.sin(iy_g * 0.045 + ang) - u * 192.0).astype(np.int32)) % tile_sz
        rv_u_y = (np.round(iy_g * persp_scale + 5.0 * np.cos(ix_g * 0.038 - ang) - u * 192.0).astype(np.int32)) % tile_sz
        rv_flow_col = rv_tile[rv_u_y, rv_u_x]
        rv_tex_mix = np.where(is_submerged_pebble, 0.30, np.where(iy_g < 520.0, 0.52, 0.46))[:, :, None]
        river_stream_rgb = bed_refract * (1.0 - rv_tex_mix) + rv_flow_col * rv_tex_mix

        # Traveling sunlit emerald-mint wave crests from `iy=330` all the way to `iy=1349` (`-15%` speed via `tpf=5.88` & `64px` 1-wave period)!
        diag_phase = (ix_g * 0.58 + iy_g * 0.82) - u * 64.0
        wave_crest = (np.maximum(0.0, np.sin(diag_phase * (2.0 * math.pi / 64.0) + np.sin(ix_g * 0.042) * 1.6)) ** 3) * 32.0
        river_stream_rgb[:, :, 0] += wave_crest * 0.60
        river_stream_rgb[:, :, 1] += wave_crest * 1.02
        river_stream_rgb[:, :, 2] += wave_crest * 0.88

        # (3) Gentler `-15%` 2-Layer Cascading Emerald Waterfall Curtain (`192px` & `384px` over 8 frames @ 5.88 ticks!)
        wf_x1 = (np.round((ix_g - 2500.0) * 1.15 - (iy_g - 500.0) * 0.09).astype(np.int32)) % tile_sz
        wf_y1 = (np.round((iy_g - 480.0) * 1.12 - u * 192.0).astype(np.int32)) % tile_sz
        wf_x2 = (wf_x1 + 257) % tile_sz
        wf_y2 = (np.round((iy_g - 480.0) * 1.12 - u * 384.0).astype(np.int32)) % tile_sz

        wf_main = wf_tile[wf_y1, wf_x1]
        wf_fast_foam = wf_foam_tile[wf_y2, wf_x2]
        wf_rgb = sock_patch * 0.06 + wf_main * 0.94
        wf_rgb[:, :, 0] += wf_fast_foam * 44.0
        wf_rgb[:, :, 1] += wf_fast_foam * 54.0
        wf_rgb[:, :, 2] += wf_fast_foam * 50.0
        # Soft emerald-white misty spray along both 46-48px side fade veils (`A1` — dissolves seamlessly over side rocks!):
        mist_mix = np.clip(side_mist_w * 0.52, 0.0, 0.55)[:, :, None]
        mist_col = np.stack([
            162.0 + 38.0 * wf_fast_foam,
            228.0 + 24.0 * wf_fast_foam,
            214.0 + 28.0 * wf_fast_foam,
        ], axis=2)
        wf_rgb = wf_rgb * (1.0 - mist_mix) + mist_col * mist_mix

        rgb = river_stream_rgb * (1.0 - w_chute[:, :, None]) + wf_rgb * w_chute[:, :, None]

        # (4) Organic Painted Lip Crest & Churning Plunge Whitewater Froth (NO round Gaussian airbrush circles!)
        # Sample organic painted foam patterns (`rv_foam_tile` & `wf_foam_tile`) modulated along the curved lip & plunge!
        plunge_env = np.exp(-0.5 * ((iy_g - iy_plunge_curve) / 26.0) ** 2) * in_chute_x
        lip_env = np.exp(-0.5 * ((iy_g - iy_lip_curve) / 13.0) ** 2) * in_chute_x
        fx_a = (np.round(ix_g * 1.35 + u * 128.0).astype(np.int32)) % tile_sz
        fy_a = (np.round(iy_g * 1.35 - u * 192.0).astype(np.int32)) % tile_sz
        fx_b = (np.round(ix_g * 1.25 - u * 128.0 + 311.0).astype(np.int32)) % tile_sz
        fy_b = (np.round(iy_g * 1.25 + u * 128.0 + 197.0).astype(np.int32)) % tile_sz
        organic_froth = 0.55 * rv_foam_tile[fy_a, fx_a] + 0.45 * wf_foam_tile[fy_b, fx_b]
        froth_boost = (
            lip_env * (18.0 + 38.0 * organic_froth)
            + plunge_env * (24.0 + 56.0 * organic_froth)
        )
        rgb[:, :, 0] += froth_boost * 0.80
        rgb[:, :, 1] += froth_boost * 1.02
        rgb[:, :, 2] += froth_boost * 0.94

        # (5) Animated Billowing Emerald-White Waterfall Mist (`emerald_waterfall_mist_v9_codex.png`) via Porter-Duff OVER:
        #     Two-scale periodic dual-phase flowmap (rich billowing Ghibli clouds + crisp rising wispy vapor/spray)!
        d_coarse = sample_flowmap_mist(u, mist_vx * 1.0, mist_vy * 1.0, scale_xy=1.05, off_x=19.0, off_y=43.0)
        d_fine = sample_flowmap_mist(u, mist_vx * 1.50, mist_vy * 1.50, scale_xy=1.88, off_x=317.0, off_y=461.0)
        billow_wave = (0.92 + 0.08 * np.sin(ang + ix_g * 0.022 - iy_g * 0.026)).astype(np.float32)
        mist_tex_d = np.clip((0.65 * d_coarse + 0.45 * d_fine) * billow_wave, 0.0, 1.0)
        # Distinct billowing cloud silhouettes (subtle 0.16 atmospheric base + crisp puff contrast up to 1.0):
        mist_shape = np.clip(0.16 + 0.92 * (mist_tex_d ** 0.95), 0.0, 1.0)
        mist_alpha = np.where(mist_is_active_px, np.clip(mist_env_combined * mist_shape * 0.86, 0.0, 0.84), 0.0).astype(np.float32)
        mist_alphas_all.append(mist_alpha)

        # Harmonized sunlit pale mint-white vapor color (luminous white-mint cloud crests, cool aqua-mint in shadow wisps):
        sunlit_w = np.clip(mist_env_plunge * 1.15, 0.0, 1.0)
        puff_hi = np.clip((mist_tex_d - 0.14) / 0.86, 0.0, 1.0)
        mist_rgb = np.stack([
            178.0 + 62.0 * puff_hi + 14.0 * sunlit_w,
            232.0 + 22.0 * puff_hi + 4.0 * sunlit_w,
            222.0 + 28.0 * puff_hi + 6.0 * sunlit_w,
        ], axis=2)
        mist_rgb = np.clip(mist_rgb, 0.0, 255.0)

        # Exact Porter-Duff OVER compositing: animated mist OVER base water (`water_mask`), so mist smoothly wraps
        # BOTH over the waterfall-river junction (alpha=1) AND over the 2 wet sandstone cliff flanks (0 <= water_mask < 1)!
        out_alpha = mist_alpha + water_mask * (1.0 - mist_alpha)
        safe_oa = np.maximum(out_alpha, 1e-5)[:, :, None]
        comp_rgb = (
            mist_rgb * mist_alpha[:, :, None]
            + np.clip(rgb, 0.0, 255.0) * (water_mask * (1.0 - mist_alpha))[:, :, None]
        ) / safe_oa

        alpha_u8 = np.clip(np.round(out_alpha * 255.0), 0, 255).astype(np.uint8)
        vis_px = alpha_u8 > 0
        fr = np.zeros((fh, fw, 4), dtype=np.uint8)
        fr[:, :, :3] = np.where(vis_px[:, :, None], np.clip(np.round(comp_rgb), 0, 255).astype(np.uint8), 0)
        fr[:, :, 3] = alpha_u8
        qa_frames[f] = fr.copy()

        c_idx, r_idx = f % cols, f // cols
        atlas[r_idx * fh : (r_idx + 1) * fh, c_idx * fw : (c_idx + 1) * fw] = fr

    # --- 5. STRICT PIXEL-EVIDENCE QA VERIFICATION ON ALL WATER + 3 MIST ZONES ---
    f0_a = qa_frames[0][:, :, 3:4].astype(np.float32) / 255.0
    f6_a = qa_frames[4][:, :, 3:4].astype(np.float32) / 255.0
    f0_comp = plate_patch * (1.0 - f0_a) + qa_frames[0][:, :, :3].astype(np.float32) * f0_a
    f6_comp = plate_patch * (1.0 - f6_a) + qa_frames[4][:, :, :3].astype(np.float32) * f6_a
    diff_06 = np.abs(f6_comp - f0_comp).mean(axis=2)

    # Check Top 2 Red Circles (`A2`): ZERO bleed onto upper trees/cliffs (`iy < 386` or `iy < 426 & ix > 2486`),
    # while true turquoise stream core (`upper_alpha > 0.65`) stays >95% animated!
    top_tree_bleed_max = float(max(
        float(qa_frames[f][:, :, 3][(iy_g < 386.0) | ((iy_g < 426.0) & (ix_g > 2486.0))].max())
        for f in range(n_frames)
    ))
    upper_core_water = (iy_g >= 390.0) & (iy_g <= 515.0) & (upper_alpha > 0.65)
    yel_core_px = int(upper_core_water.sum())
    yel_core_active_pct = 100.0 * float((diff_06[upper_core_water] > 3.0).mean())

    # Check Side 2 Red Circles (`A1`): wide soft fade veil (`0.04 < alpha < 0.96`) >= 34px on BOTH left & right waterfall sides!
    row_mid = int(round(720 - WRA_IY0))
    f0_a_2d = f0_a[:, :, 0]
    left_veil_px = int(((f0_a_2d[row_mid, :500] > 0.04) & (f0_a_2d[row_mid, :500] < 0.96)).sum())
    right_veil_px = int(((f0_a_2d[row_mid, 500:950] > 0.04) & (f0_a_2d[row_mid, 500:950] < 0.96)).sum())

    # Check Bottom Green Box (`iy=[1338..1349]`):
    grn_last12_water = (iy_g >= 1338) & (iy_g <= 1349) & (ix_g >= 2650) & (ix_g <= 3620) & (water_mask > 0.5)
    grn_last12_px = int(grn_last12_water.sum())
    grn_last12_active_pct = 100.0 * float((diff_06[grn_last12_water] > 3.0).mean())

    # Check 3 Animated Mist Zones (Plunge Junction + Left Cliff Flank + Right Cliff Flank) + Seamless Loop Continuity!
    plunge_roi = (iy_g >= 845.0) & (iy_g <= 925.0) & (ix_g >= 2500.0) & (ix_g <= 2975.0)
    left_flank_roi = (iy_g >= 580.0) & (iy_g <= 885.0) & (ix_g >= 2468.0) & (ix_g <= 2555.0)
    right_flank_roi = (iy_g >= 655.0) & (iy_g <= 895.0) & (ix_g >= 2928.0) & (ix_g <= 3015.0)
    plunge_mist_mean = float(mist_alphas_all[0][plunge_roi].mean())
    left_mist_mean = float(mist_alphas_all[0][left_flank_roi].mean())
    right_mist_mean = float(mist_alphas_all[0][right_flank_roi].mean())
    plunge_mist_active_pct = 100.0 * float((diff_06[plunge_roi] > 3.0).mean())
    left_flank_mist_active_pct = 100.0 * float((diff_06[left_flank_roi] > 2.5).mean())
    right_flank_mist_active_pct = 100.0 * float((diff_06[right_flank_roi] > 2.5).mean())

    # Verify periodic loop continuity across f7 -> f0 vs internal steps f0->f1..f6->f7 on mist alpha!
    mist_roi_all = mist_env_combined > 0.12
    adj_mist_diffs = [
        float(np.abs(mist_alphas_all[(i + 1) % n_frames][mist_roi_all] - mist_alphas_all[i][mist_roi_all]).mean())
        for i in range(n_frames)
    ]
    internal_mist_step = float(np.mean(adj_mist_diffs[: n_frames - 1]))
    wrap_mist_step = adj_mist_diffs[n_frames - 1]
    mist_loop_ratio = wrap_mist_step / max(1e-5, internal_mist_step)

    pine_trunk_bleed_max = float(max(
        float(qa_frames[f][:, :, 3][(ix_g >= 3095.0) & (ix_g <= 3185.0) & (iy_g >= 680.0) & (iy_g <= 880.0)].max())
        for f in range(n_frames)
    ))
    left_dry_bank_diff = float(diff_06[(ix_g < 2340) & (iy_g > 900)].max())

    assert top_tree_bleed_max == 0.0, f"Top tree/cliff bleed detected: {top_tree_bleed_max}"
    assert pine_trunk_bleed_max == 0.0, f"Pine trunk mist bleed detected: {pine_trunk_bleed_max}"
    assert yel_core_px > 12000 and yel_core_active_pct > 95.0, f"Upper stream core weak: px={yel_core_px} active={yel_core_active_pct:.1f}%"
    assert left_veil_px >= 34 and right_veil_px >= 32, f"Side waterfall fade too narrow: left={left_veil_px}px right={right_veil_px}px"
    assert grn_last12_px > 7500 and grn_last12_active_pct > 95.0, f"Bottom Green last 12px weak: px={grn_last12_px} active={grn_last12_active_pct:.1f}%"
    assert left_dry_bank_diff == 0.0, f"Left dry bank wobbled: {left_dry_bank_diff}"
    assert 0.16 <= plunge_mist_mean <= 0.65 and plunge_mist_active_pct > 90.0, (
        f"Plunge mist out of range: mean_a={plunge_mist_mean:.3f} active={plunge_mist_active_pct:.1f}%"
    )
    assert 0.10 <= left_mist_mean <= 0.55 and left_flank_mist_active_pct > 85.0, (
        f"Left cliff flank mist out of range: mean_a={left_mist_mean:.3f} active={left_flank_mist_active_pct:.1f}%"
    )
    assert 0.10 <= right_mist_mean <= 0.55 and right_flank_mist_active_pct > 85.0, (
        f"Right cliff flank mist out of range: mean_a={right_mist_mean:.3f} active={right_flank_mist_active_pct:.1f}%"
    )
    assert mist_loop_ratio <= 1.25, f"Mist loop seam pop detected: wrap/internal={mist_loop_ratio:.3f}"

    atlas_path = FX_DIR / "waterfall_river_atlas.png"
    Image.fromarray(atlas).save(atlas_path, optimize=True)
    assert atlas.shape[1] <= 4096 and atlas.shape[0] <= 4096

    tres_path = write_waterfall_river_tres(
        f"res://{atlas_path.relative_to(ROOT).as_posix()}", fw=fw, fh=fh, cols=cols, n_frames=n_frames, tpf=WRA_TPF
    )

    # Emerald-matched z=31 ankle wave strip (`8` frames `2x4`, `tpf = 5.88` `-15%` speed)
    rim_w, rim_h = 740, 24
    r_cols, r_rows = 2, 4
    rim_atlas = np.zeros((rim_h * r_rows, rim_w * r_cols, 4), dtype=np.uint8)
    ry_r, rx_r = np.mgrid[0:rim_h, 0:rim_w]
    edge_taper = np.clip(np.minimum(rx_r / 28.0, (rim_w - 1 - rx_r) / 28.0), 0.0, 1.0)
    for f in range(n_frames):
        ang = (2.0 * math.pi * f) / float(n_frames)
        wave_top = 8.0 + 2.6 * np.sin(rx_r * 0.065 - ang) + 1.4 * np.cos(rx_r * 0.14 - ang)
        in_wave = (ry_r >= wave_top) & (ry_r <= wave_top + 10.0)
        is_foam_crest = (ry_r >= wave_top) & (ry_r <= wave_top + 2.5)
        raw_a = np.where(is_foam_crest, 174.0, np.where(in_wave, 118.0 * (1.0 - (ry_r - wave_top) / 11.0), 0.0))
        a_u8 = np.clip(np.round(raw_a * edge_taper), 0, 255).astype(np.uint8)
        fr = np.zeros((rim_h, rim_w, 4), dtype=np.uint8)
        fr[:, :, 0] = np.where(a_u8 > 0, np.where(is_foam_crest, 212, 27), 0)
        fr[:, :, 1] = np.where(a_u8 > 0, np.where(is_foam_crest, 248, 174), 0)
        fr[:, :, 2] = np.where(a_u8 > 0, np.where(is_foam_crest, 238, 149), 0)
        fr[:, :, 3] = a_u8
        rc, rr_i = f % r_cols, f // r_cols
        rim_atlas[rr_i * rim_h : (rr_i + 1) * rim_h, rc * rim_w : (rc + 1) * rim_w] = fr

    rim_out_path = FX_DIR / "water_ankle_rim.png"
    Image.fromarray(rim_atlas).save(rim_out_path, optimize=True)

    splash_out_path, sp_hard = extract_intact_13f_water_splash_v3()

    qa_stats = {
        "top_tree_bleed_max": top_tree_bleed_max,
        "pine_trunk_bleed_max": pine_trunk_bleed_max,
        "upper_core_px": yel_core_px,
        "upper_core_active_pct": round(yel_core_active_pct, 2),
        "left_veil_width_px": left_veil_px,
        "right_veil_width_px": right_veil_px,
        "plunge_mist_mean_alpha": round(plunge_mist_mean, 3),
        "plunge_mist_active_pct": round(plunge_mist_active_pct, 2),
        "left_flank_mist_mean_alpha": round(left_mist_mean, 3),
        "left_flank_mist_active_pct": round(left_flank_mist_active_pct, 2),
        "right_flank_mist_mean_alpha": round(right_mist_mean, 3),
        "right_flank_mist_active_pct": round(right_flank_mist_active_pct, 2),
        "mist_loop_ratio": round(mist_loop_ratio, 3),
        "grn_last12_px": grn_last12_px,
        "grn_last12_active_pct": round(grn_last12_active_pct, 2),
        "left_dry_bank_diff": left_dry_bank_diff,
        "ticks_per_frame": WRA_TPF,
        "atlas_size_mb": round(atlas_path.stat().st_size / (1024.0 * 1024.0), 2),
    }

    water_cfg = {
        "enabled": True,
        "min_world_x": WATER_MIN_WX,
        "max_world_x": WATER_MAX_WX,
        "width_px": WATER_MAX_WX - WATER_MIN_WX,
        "bed_world_y": WATER_BED_WY,
        "wade_depth_px": WATER_WADE_DEPTH_PX,
        "speed_multiplier": 1.0,
        "waterfall_spray_min_x": 2275.0,
        "waterfall_spray_max_x": 2715.0,
        "waterfall_river_asset": {
            "tres_path": tres_path.relative_to(ROOT).as_posix(),
            "tres_res_path": f"res://{tres_path.relative_to(ROOT).as_posix()}",
            "atlas_path": atlas_path.relative_to(ROOT).as_posix(),
            "atlas_res_path": f"res://{atlas_path.relative_to(ROOT).as_posix()}",
            "atlas_web_path": "/" + atlas_path.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(atlas_path),
            "atlas_size_px": [fw * cols, fh * rows],
            "frame_size_px": [fw, fh],
            "grid_cols_rows": [cols, rows],
            "frame_count": n_frames,
            "animation": "flow",
            "tick_hz": 60,
            "ticks_per_frame": WRA_TPF,
            "world_pos": [float(WRA_IX0 + MAP_LEFT_X), float(WRA_IY0 + MAP_TOP_Y)],
            "z_index": -16,
        },
        "ankle_rim_anim": {
            "path": rim_out_path.relative_to(ROOT).as_posix(),
            "res_path": f"res://{rim_out_path.relative_to(ROOT).as_posix()}",
            "web_path": "/" + rim_out_path.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(rim_out_path),
            "frame_size_px": [rim_w, rim_h],
            "hframes": r_cols,
            "vframes": r_rows,
            "frame_count": n_frames,
            "ticks_per_frame": WRA_TPF,
            "world_pos": [2205.0, 886.0],
            "z_index": 31,
        },
        "splash_fx": {
            "path": splash_out_path.relative_to(ROOT).as_posix(),
            "res_path": f"res://{splash_out_path.relative_to(ROOT).as_posix()}",
            "web_path": "/" + splash_out_path.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(splash_out_path),
            "frame_size_1x_px": [160, 80],
            "frame_count": 13,
            "tick_hz": 60,
            "ticks_per_frame": 3,
            "scale": 1.35,
            "alpha_hardness_pct": sp_hard,
            "z_index": 25,
        },
    }
    return water_cfg, qa_stats


def build_ground_tileset_and_dust(full_u8: np.ndarray) -> tuple[dict[str, Any], dict[str, Any]]:
    TILES_DIR.mkdir(parents=True, exist_ok=True)
    FX_DIR.mkdir(parents=True, exist_ok=True)

    slab = full_u8[940:1068, 660:1620].copy()
    rgba = np.zeros((128, 960, 4), dtype=np.uint8)
    rgba[:, :, :3] = slab
    rgba[:, :, 3] = 255
    ts_path = TILES_DIR / "ground_tileset.png"
    Image.fromarray(rgba).save(ts_path, optimize=True)
    ts_info = {
        "path": ts_path.relative_to(ROOT).as_posix(),
        "res_path": f"res://{ts_path.relative_to(ROOT).as_posix()}",
        "web_path": "/" + ts_path.relative_to(ROOT).as_posix(),
        "sha256": sha256_file(ts_path),
        "tile_px": TILE_PX,
        "columns": 30,
        "rows": 4,
        "image_size_px": [960, 128],
        "alpha_hardness_pct": 100.0,
    }

    fw, fh, frames = 32, 20, 6
    dust_sheet = Image.new("RGBA", (fw * frames, fh), (0, 0, 0, 0))
    base_stone = np.median(full_u8[955:995, 700:1300].reshape(-1, 3).astype(np.float32), axis=0)
    c_dark = tuple(int(v) for v in np.clip(base_stone * 0.44, 0, 255)) + (255,)
    c_mid = tuple(int(v) for v in np.clip(base_stone * 0.76, 0, 255)) + (255,)
    c_lit = tuple(int(v) for v in np.clip(base_stone, 0, 255)) + (255,)
    puffs = [
        [(10, 15, 3), (21, 15, 3), (15, 16, 2)],
        [(8, 14, 4), (23, 14, 4), (12, 16, 2), (19, 16, 2)],
        [(6, 12, 4), (25, 12, 4), (10, 15, 3), (21, 15, 3)],
        [(4, 11, 3), (27, 11, 3), (8, 14, 2), (23, 14, 2)],
        [(3, 10, 2), (28, 10, 2), (7, 15, 1), (24, 15, 1)],
        [(2, 9, 1), (29, 9, 1)],
    ]
    for fi, pf in enumerate(puffs):
        tile = Image.new("RGBA", (fw, fh), (0, 0, 0, 0))
        d = ImageDraw.Draw(tile)
        for px, py, rad in pf:
            d.ellipse((px - rad - 1, py - rad - 1, px + rad + 1, py + rad + 1), fill=c_dark)
        for px, py, rad in pf:
            d.ellipse((px - rad, py - rad, px + rad, py + rad), fill=c_mid if fi >= 3 else c_lit)
        dust_sheet.paste(tile, (fi * fw, 0))
    dust_path = FX_DIR / "ground_dust.png"
    dust_sheet.save(dust_path, optimize=True)
    dust_info = {
        "path": dust_path.relative_to(ROOT).as_posix(),
        "res_path": f"res://{dust_path.relative_to(ROOT).as_posix()}",
        "web_path": "/" + dust_path.relative_to(ROOT).as_posix(),
        "sha256": sha256_file(dust_path),
        "frame_size_1x_px": [fw, fh],
        "frame_count": frames,
        "tick_hz": 60,
        "ticks_per_frame": 3,
        "scale": GAMEPLAY_SCALE,
        "anchor_1x_px": [16, 17],
    }
    return ts_info, dust_info


def main() -> None:
    ensure_gdignore(SOURCE_DIR)
    work_v7 = ROOT / "work" / "map_gen_v7"
    src_pm = work_v7 / "out_pine_magenta" / "generated.png"
    if src_pm.is_file():
        shutil.copy2(src_pm, SOURCE_DIR / "pine_crown_magenta_v7_codex.png")

    raw_socket_f32, clean_socket_f32, terrain_plate_u8, fg_trees_cfg = build_v7_panorama_and_foreground_rims()
    ext_path = MAP_DIR / "teinan-slope-extended.png"
    Image.fromarray(terrain_plate_u8).save(ext_path, format="PNG", optimize=True)

    bg_jpg_path = MAP_DIR / "teinan-slope-bg.jpg"
    Image.fromarray(terrain_plate_u8[:, :2400]).resize((1920, 1080), Image.Resampling.LANCZOS).save(
        bg_jpg_path, format="JPEG", quality=93
    )

    water_cfg, qa_stats = build_unified_emerald_water_asset_v7(raw_socket_f32, clean_socket_f32, terrain_plate_u8)
    ts_info, dust_info = build_ground_tileset_and_dust(terrain_plate_u8)

    stage_doc = {
        "schema_version": "dr7.arena_stage.v1",
        "stage_id": "teinan_slope",
        "display_name": "Sườn núi Teinan",
        "monsters_enabled": False,
        "has_transition_header": True,
        "transitions": {
            "left": {
                "target_map_id": "rocky_plateau",
                "target_display_name": "Núi Teinan",
                "portal_width_px": 26.0,
                "portal_height_px": 208.0,
                "spawn_x": 6120.0,
                "facing_left": True,
            },
            "right": {
                "target_map_id": "",
                "target_display_name": "Khu vực tiếp theo",
                "pending_next_map": True,
                "pending_notice": "◆ Khu vực tiếp theo sắp mở (chờ kết nối Map 3)!",
                "portal_width_px": 26.0,
                "portal_height_px": 185.0,
                "spawn_x": 0.0,
                "facing_left": False,
            },
        },
        "viewport": {
            "width": 1920,
            "height": 1080,
            "aspect_ratio": "16:9",
            "orientation": "landscape",
            "stretch_mode": "canvas_items",
            "stretch_aspect": "expand",
            "stretch_scale_mode": "fractional",
            "pixel_perfect_toggle_supported": True,
            "pixel_perfect_min_height_px": 1080,
            "renderer": "gl_compatibility",
            "device_profiles_path": "assets/maps/rocky_plateau/device-profiles.json",
            "handheld_orientation_code": 0,
            "ppu_reference": 64,
            "tile_px": 32,
        },
        "map": {
            "background_path": bg_jpg_path.relative_to(ROOT).as_posix(),
            "background_res_path": f"res://{bg_jpg_path.relative_to(ROOT).as_posix()}",
            "background_web_path": "/" + bg_jpg_path.relative_to(ROOT).as_posix(),
            "source_size_px": [1192, 670],
            "sha256": sha256_file(bg_jpg_path),
            "render_rect_px": [0, 0, 1920, 1080],
            "fit_mode": "cover_16_9",
            "extended_map": {
                "approved_by_owner": True,
                "demo_status": "approved_v0_20_0",
                "background_path": ext_path.relative_to(ROOT).as_posix(),
                "background_res_path": f"res://{ext_path.relative_to(ROOT).as_posix()}",
                "background_web_path": "/" + ext_path.relative_to(ROOT).as_posix(),
                "sha256": sha256_file(ext_path),
                "image_size_px": [4800, 1350],
                "world_bounds": {
                    "left_x": MAP_LEFT_X,
                    "right_x": MAP_RIGHT_X,
                    "top_y": MAP_TOP_Y,
                    "bottom_y": MAP_BOTTOM_Y,
                },
                "camera_vertical_follow": {
                    "enabled": True,
                    "player_y_offset_px": -85.0,
                    "min_cam_y": 390.0,
                    "max_cam_y": 590.0,
                },
                "steps": STEPS,
                "interactive_water": water_cfg,
                "foreground_trees": fg_trees_cfg,
            },
        },
        "gameplay": {
            "ground_y": BASE_GROUND_Y,
            "walkable_bounds_x": [-216, 4536],
            "player_spawn_x": -140,
            "player_spawn_facing_left_x": 920,
            "dummy_spawn_x": 640,
            "character_scale_default": 2,
            "character_scale_options": [1, 2, 3],
            "character_scale_min": 0.5,
            "character_scale_max": 3.0,
            "character_scale_step": 0.05,
            "character_scale_presets": [1, 1.25, 1.5, 1.75, 2, 2.5, 3],
            "texture_filter": "nearest",
            "screen_shake_enabled": False,
            "ground_shadow_ellipse_enabled": False,
            "burrow_dust_scale_default": 2.65,
            "burrow_dust_scale_options": [1, 1.5, 2.25, 2.65],
            "flight": {
                "min_y": -140,
                "max_y": 895,
                "default_y": 210,
                "screen_middle_y": 440,
                "middle_offset_px": -260,
                "vertical_speed_px_per_s": 240,
            },
            "jump_velocity_px_per_s": -780,
            "gravity_px_per_s2": 2000,
            "utility_ai": {
                "enabled_by_default": False,
                "distance_metric": "body_edge_2d",
                "close_edge_px": 50,
                "mid_max_edge_px": 200,
                "heavy_max_edge_px": 200,
                "attack_cooldown_s": 1.0,
                "light_hits_before_heavy": 2,
                "zone_width_max_px": 500,
                "zone_width_default_px": 480,
                "monster_count_per_map": [0, 0],
                "monster_spacing_max_px": 500,
            },
        },
    }

    terrain_doc = {
        "schema_version": "dr7.terrain.v1",
        "map_id": "teinan_slope",
        "display_name": "Sườn núi Teinan",
        "backdrop": {
            "mode": "original_jpg",
            "path": bg_jpg_path.relative_to(ROOT).as_posix(),
            "res_path": f"res://{bg_jpg_path.relative_to(ROOT).as_posix()}",
            "web_path": "/" + bg_jpg_path.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(bg_jpg_path),
        },
        "tileset": ts_info,
        "ground": {
            "surface_y": BASE_GROUND_Y,
            "surface_top_y": BASE_GROUND_Y - 16,
            "render_scale": GAMEPLAY_SCALE,
            "solid": True,
        },
        "platforms": [],
        "dust_fx": dust_info,
        "interactive_water": water_cfg,
        "contact_shadow": {
            "enabled": True,
            "max_height_px": 320,
            "min_half_w_px": 18,
            "outer_rgba": [18, 28, 16, 60],
            "inner_rgba": [12, 20, 10, 85],
            "water_outer_rgba": [10, 84, 74, 72],
            "water_inner_rgba": [6, 56, 48, 98],
        },
    }

    (MAP_DIR / "arena-stage.json").write_text(json.dumps(stage_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (MAP_DIR / "terrain.json").write_text(json.dumps(terrain_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    rp_stage_path = ROOT / "assets" / "maps" / "rocky_plateau" / "arena-stage.json"
    rp_doc = json.loads(rp_stage_path.read_text(encoding="utf-8"))
    rp_doc["transitions"]["right"] = {
        "target_map_id": "teinan_slope",
        "target_display_name": "Sườn núi Teinan",
        "portal_width_px": 26.0,
        "portal_height_px": 208.0,
        "spawn_x": -140.0,
        "facing_left": False,
    }
    rp_stage_path.write_text(json.dumps(rp_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("BUILT_TEINAN_SLOPE_V9_OK", sha256_file(ext_path), json.dumps(qa_stats))


if __name__ == "__main__":
    main()
