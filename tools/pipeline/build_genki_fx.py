#!/usr/bin/env python3
"""Build dedicated independent Genki FX bundle (`assets/fx/genki_fx/`, 1 PNG page <= 4096x4096, 60Hz Nearest).

Preserves 100% of all 16 original `/workspaces/Dragonball-Studio-7/Genki/1..16.png` frames
(fixing `Genki/4.png` white-corner keying cleanly!) plus 8 smooth pixel-art bridge/pulse/flight frames:
  1. `genki_charge_fx` (10 frames @ 120ms): 1, 2, 2b, 3, 3b, 4, 4b, 5, 5b, 6 (smooth small->large formation)
  2. `genki_charge_hold_fx` (3 frames @ 120ms, loop): 6, 6b, 6c (full charged orb pulsing on hands — NO 7/8!)
  3. `genki_fly_fx` (4 frames @ 80ms, loop): 7, 7b, 8, 8b (aerodynamic flying Spirit Bomb!)
  4. `genki_impact_fx` (4 frames @ 100ms, oneshot, ground y=352): 9, 10, 11, 12 (ground touchdown -> ignition!)
  5. `genki_explode_fx` (4 frames @ 120ms, oneshot, ground y=352): 13, 14, 15, 16 (fiery explosion climax!)
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
from typing import Dict, List, Tuple

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "Genki"
GEN_DIR = ROOT / "work" / "polish_round2" / "gen"
GEN_R3_DIR = ROOT / "work" / "polish_round3" / "gen"
WORK_DIR = ROOT / "work" / "characters" / "songoku_genki" / "fx_extract_v2"
QA_DIR = ROOT / "work" / "polish_round3" / "qa"
OUT_FX_DIR = ROOT / "assets" / "fx" / "genki_fx"
BUILD_CLIPS_SCRIPT = ROOT / ".agents" / "skills" / "generate2dsprite" / "scripts" / "build_animation_clips.py"
EXPORT_ENGINE_SCRIPT = ROOT / ".agents" / "skills" / "generate2dsprite" / "scripts" / "export_engine.py"

sys.path.insert(0, str(ROOT / "tools" / "pipeline"))
import repack_songoku_hero_demo as repacker  # noqa: E402

CANVAS_W = 384
CANVAS_H = 384
ORB_CENTER = (192, 192)
EXPLODE_GROUND_Y = 352
KEY_RGB = np.array([101, 101, 129], dtype=np.int16)


def sha256_file(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def key_genki_source_frame(img_path: pathlib.Path) -> Tuple[np.ndarray, Dict[str, int]]:
    """Key original Genki/1..16.png cleanly:
    - Flood-fills BOTH flat backdrop RGB(101,101,129) AND border white corners (Genki/4.png!) strictly from image border.
    - Also removes enclosed RGB(101,101,129) pockets cleanly while preserving internal white orb core 100%!
    """
    im = Image.open(img_path).convert("RGBA")
    arr = np.array(im, dtype=np.uint8)
    rgb = arr[:, :, :3].astype(np.int16)
    h, w = arr.shape[:2]

    # Exact backdrop slate-purple key RGB(101, 101, 129)
    dist_slate = np.abs(rgb - KEY_RGB[None, None, :]).max(axis=2)
    slate_cand = (dist_slate <= 20) & (arr[:, :, 3] > 0)

    # Pure border white corners (ONLY reachable from border — NEVER touches inner white orb core!)
    white_cand = (rgb[:, :, 0] >= 242) & (rgb[:, :, 1] >= 242) & (rgb[:, :, 2] >= 242) & (arr[:, :, 3] > 0)
    border_seed = np.zeros((h, w), dtype=bool)
    border_seed[0, :] = True
    border_seed[-1, :] = True
    border_seed[:, 0] = True
    border_seed[:, -1] = True

    # Connected component from border across slate OR border-white corners (cleans Genki/4.png 100%!)
    bg_union = slate_cand | white_cand
    lbl_b, _ = ndimage.label(bg_union, structure=np.ones((3, 3), dtype=np.int32))
    border_labels = set(np.unique(lbl_b[border_seed & bg_union])) - {0}
    bg_border = np.isin(lbl_b, list(border_labels))

    # Also remove enclosed slate pockets inside rays/rings (slate ONLY, never white core!)
    bg_mask = bg_border | slate_cand

    # 1px fringe cleanup on slate-tinted border pixels adjacent to bg_mask
    dil = ndimage.binary_dilation(bg_mask, iterations=1) & ~bg_mask
    fringe_slate = dil & (dist_slate <= 34)
    # Also clean 1px pale gray-white fringe strictly adjacent to white corner areas
    white_bg = bg_border & white_cand
    if white_bg.any():
        dil_w = ndimage.binary_dilation(white_bg, iterations=2) & ~bg_mask
        fringe_w = dil_w & (rgb[:, :, 0] >= 210) & (rgb[:, :, 1] >= 210) & (rgb[:, :, 2] >= 210) & ((np.abs(rgb[:, :, 0] - rgb[:, :, 2])) <= 18)
        bg_mask = bg_mask | fringe_w
    bg_mask = bg_mask | fringe_slate

    out = arr.copy()
    out[bg_mask] = [0, 0, 0, 0]
    fg = out[:, :, 3] >= 128
    out[~fg] = [0, 0, 0, 0]
    out[fg, 3] = 255

    # Remove tiny isolated 1-2px dust specks far from main FX
    lbl, n = ndimage.label(fg, structure=np.ones((3, 3), dtype=np.int32))
    if n > 1:
        sizes = ndimage.sum(fg, lbl, range(1, n + 1))
        for ci, sz in enumerate(sizes, start=1):
            if sz <= 2:
                out[lbl == ci] = [0, 0, 0, 0]

    rem_slate = int(((out[:, :, 3] > 0) & (dist_slate <= 16)).sum())
    return out, {"opaque_key_px": rem_slate, "fg_px": int((out[:, :, 3] > 0).sum())}


def key_gen_magenta_fx(src_path: pathlib.Path) -> np.ndarray:
    """Key flat #FF00FF magenta background while PRESERVING ALL disconnected rays, rings, sparks & wind streaks!"""
    raw = Image.open(src_path).convert("RGBA")
    arr = np.array(raw, dtype=np.uint8)
    r, g, b = arr[:, :, 0].astype(np.int16), arr[:, :, 1].astype(np.int16), arr[:, :, 2].astype(np.int16)
    a = arr[:, :, 3] > 0
    # Strong magenta background + 1px magenta-tinted fringe (preserves ALL cyan/blue/white VFX pixels!)
    is_mag = a & ((r - g) > 45) & ((b - g) > 45) & (g < 175)
    # Remove any magenta enclosed pockets too (no VFX uses magenta!)
    dil = ndimage.binary_dilation(is_mag, iterations=1) & ~is_mag
    fringe = dil & ((r - g) > 28) & ((b - g) > 28) & (g < 195)
    bg = is_mag | fringe
    out = arr.copy()
    out[bg] = [0, 0, 0, 0]
    fg = out[:, :, 3] >= 128
    out[~fg] = [0, 0, 0, 0]
    out[fg, 3] = 255
    # Remove only isolated <=2px stray noise specks while keeping ALL rays, rings, and aerodynamic streaks intact!
    lbl, n = ndimage.label(fg, structure=np.ones((3, 3), dtype=np.int32))
    if n > 1:
        sizes = ndimage.sum(fg, lbl, range(1, n + 1))
        for ci, sz in enumerate(sizes, start=1):
            if sz <= 2:
                out[lbl == ci] = [0, 0, 0, 0]
    vis = out[:, :, 3] > 0
    ys, xs = np.where(vis)
    return out[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def measure_inner_sphere_diameter(crop: np.ndarray) -> float:
    """Measure the largest solid cyan-white energy sphere diameter (ignoring outer detached streaks/wings)
    so 6/6b/6c and 7/7b/8/8b keep 100% IDENTICAL sphere diameter without size popping!
    """
    a = crop[:, :, 3] > 0
    r, g, b = crop[:, :, 0].astype(np.int16), crop[:, :, 1].astype(np.int16), crop[:, :, 2].astype(np.int16)
    # Dense core + saturated cyan/blue orb body (excludes thin pale white-cyan detached wind streaks)
    orb_body = a & ((b >= 170) & ((r < 190) | ((r >= 230) & (g >= 230) & (b >= 230))))
    # Erode slightly to detach thin wispy wind tails from the round main sphere
    er = ndimage.binary_erosion(orb_body, iterations=max(2, int(round(min(crop.shape[:2]) * 0.012))))
    if not er.any():
        return float(max(crop.shape[0], crop.shape[1]))
    lbl, n = ndimage.label(er, structure=np.ones((3, 3), dtype=np.int32))
    sizes = ndimage.sum(er, lbl, range(1, n + 1))
    main = lbl == (int(np.argmax(sizes)) + 1)
    # Restore eroded boundary
    main = ndimage.binary_dilation(main, iterations=max(2, int(round(min(crop.shape[:2]) * 0.012)))) & a
    ys, xs = np.where(main)
    return 0.5 * float((ys.max() - ys.min() + 1) + (xs.max() - xs.min() + 1))


def place_centered(crop: np.ndarray, scale: float) -> Image.Image:
    nw = max(4, int(round(crop.shape[1] * scale)))
    nh = max(4, int(round(crop.shape[0] * scale)))
    if nw > CANVAS_W - 8 or nh > CANVAS_H - 8:
        fit = min((CANVAS_W - 8) / float(nw), (CANVAS_H - 8) / float(nh))
        nw = max(4, int(round(nw * fit)))
        nh = max(4, int(round(nh * fit)))
    im = Image.fromarray(crop, "RGBA").resize((nw, nh), Image.Resampling.NEAREST)
    arr = np.array(im, dtype=np.uint8)
    m = arr[:, :, 3] >= 128
    r, g, b = arr[:, :, 0].astype(np.int16), arr[:, :, 1].astype(np.int16), arr[:, :, 2].astype(np.int16)
    pink = m & ((r - g) > 38) & ((b - g) > 38) & (g < 165)
    m = m & ~pink
    arr[~m] = [0, 0, 0, 0]
    arr[m, 3] = 255
    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    px = max(2, min(CANVAS_W - nw - 2, ORB_CENTER[0] - nw // 2))
    py = max(2, min(CANVAS_H - nh - 2, ORB_CENTER[1] - nh // 2))
    canvas.paste(Image.fromarray(arr, "RGBA"), (px, py))
    return canvas


def place_ground_anchored(crop: np.ndarray, scale: float) -> Image.Image:
    nw = max(4, int(round(crop.shape[1] * scale)))
    nh = max(4, int(round(crop.shape[0] * scale)))
    if nw > CANVAS_W - 8 or nh > EXPLODE_GROUND_Y - 8:
        fit = min((CANVAS_W - 8) / float(nw), (EXPLODE_GROUND_Y - 8) / float(nh))
        nw = max(4, int(round(nw * fit)))
        nh = max(4, int(round(nh * fit)))
    im = Image.fromarray(crop, "RGBA").resize((nw, nh), Image.Resampling.NEAREST)
    arr = np.array(im, dtype=np.uint8)
    m = arr[:, :, 3] >= 128
    arr[~m] = [0, 0, 0, 0]
    arr[m, 3] = 255
    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    px = max(2, min(CANVAS_W - nw - 2, ORB_CENTER[0] - nw // 2))
    py = max(2, min(CANVAS_H - nh - 2, EXPLODE_GROUND_Y - nh))
    canvas.paste(Image.fromarray(arr, "RGBA"), (px, py))
    return canvas


def render_3bg_strip(items: List[Tuple[str, Image.Image]], out_path: pathlib.Path) -> None:
    tw, th, hdr = 160, 160, 22
    sheet = Image.new("RGBA", (len(items) * tw, hdr + 3 * th), (24, 28, 36, 255))
    draw = ImageDraw.Draw(sheet)
    for i, (lbl, im) in enumerate(items):
        x0 = i * tw
        draw.rectangle([x0, 0, x0 + tw - 1, hdr - 1], fill=(18, 22, 30, 255))
        draw.text((x0 + 4, 4), lbl, fill=(255, 240, 128, 255))
        thumb = im.resize((tw, th), Image.Resampling.NEAREST)
        for ri, mode in enumerate(("light", "dark", "checker")):
            y0 = hdr + ri * th
            if mode == "light":
                bg = Image.new("RGBA", (tw, th), (236, 240, 246, 255))
            elif mode == "dark":
                bg = Image.new("RGBA", (tw, th), (20, 24, 34, 255))
            else:
                bg = Image.new("RGBA", (tw, th), (52, 58, 72, 255))
                bd = ImageDraw.Draw(bg)
                for yy in range(0, th, 16):
                    for xx in range(0, tw, 16):
                        if ((xx // 16) + (yy // 16)) % 2 == 0:
                            bd.rectangle([xx, yy, xx + 15, yy + 15], fill=(74, 82, 98, 255))
            bg.alpha_composite(thumb)
            sheet.paste(bg, (x0, y0))
            draw.rectangle([x0, y0, x0 + tw - 1, y0 + th - 1], outline=(100, 118, 145, 255))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)


def main() -> int:
    if WORK_DIR.exists():
        shutil.rmtree(WORK_DIR)
    raw_dir = WORK_DIR / "raw_frames"
    raw_dir.mkdir(parents=True, exist_ok=True)
    QA_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Extract ALL 16 original Genki/1..16.png cleanly with exact proportions!
    orig_crops: Dict[int, np.ndarray] = {}
    for idx in range(1, 17):
        arr, meta = key_genki_source_frame(SRC_DIR / f"{idx}.png")
        vis = arr[:, :, 3] > 0
        ys, xs = np.where(vis)
        orig_crops[idx] = arr[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        print(f"  [orig Genki/{idx}.png] crop={orig_crops[idx].shape[1]}x{orig_crops[idx].shape[0]} key_rem={meta['opaque_key_px']}")

    # Shared orb scale from original 1..8 (fit largest orb 8.png comfortably in 360x360 so 1..6 preserve exact relative growth!)
    max_orb_side = max(max(orig_crops[i].shape[0], orig_crops[i].shape[1]) for i in range(1, 9))
    orb_scale = 360.0 / float(max_orb_side)
    # Exact inner sphere diameter of Genki/6, 7, 8 after orb_scale!
    orb6_diam = measure_inner_sphere_diameter(orig_crops[6]) * orb_scale
    fly_sphere_diam = 0.5 * (measure_inner_sphere_diameter(orig_crops[7]) + measure_inner_sphere_diameter(orig_crops[8])) * orb_scale

    # Shared ground-impact + explosion scale from original 9..16
    max_exp_w = max(orig_crops[i].shape[1] for i in range(9, 17))
    max_exp_h = max(orig_crops[i].shape[0] for i in range(9, 17))
    explode_scale = min(368.0 / float(max_exp_w), 336.0 / float(max_exp_h))

    # 2. Place all 24 frames with exact smooth size progression!
    placed: Dict[str, Image.Image] = {}
    for i in range(1, 9):
        placed[f"orig_{i:02d}"] = place_centered(orig_crops[i], orb_scale)
    for i in range(9, 17):
        placed[f"orig_{i:02d}"] = place_ground_anchored(orig_crops[i], explode_scale)

    # Bridge & flight frames sized cleanly by outer span (2b..4b) or inner sphere diameter (5b, 6b, 6c, 7b, 8b)!
    gen_specs = {
        "bridge_2b": ("genki_bridge_2b", "outer", 0.5 * (max(orig_crops[2].shape[:2]) + max(orig_crops[3].shape[:2])) * orb_scale),
        "bridge_3b": ("genki_bridge_3b", "outer", 0.5 * (max(orig_crops[3].shape[:2]) + max(orig_crops[4].shape[:2])) * orb_scale),
        "bridge_4b": ("genki_bridge_4b", "outer", 0.5 * (max(orig_crops[4].shape[:2]) + max(orig_crops[5].shape[:2])) * orb_scale),
        "bridge_5b": ("genki_bridge_5b", "sphere", 0.86 * orb6_diam),
        "charge_6b": ("genki_charge_6b", "sphere", orb6_diam),
        "charge_6c": ("genki_charge_6c", "sphere", orb6_diam),
        "fly_7b":    ("genki_fly_7b",    "sphere", fly_sphere_diam),
        "fly_8b":    ("genki_fly_8b",    "sphere", fly_sphere_diam),
    }
    for key, (gname, mode, target_px) in gen_specs.items():
        src_p = (GEN_R3_DIR / gname / "generated.png") if (GEN_R3_DIR / gname / "generated.png").is_file() else (GEN_DIR / gname / "generated.png")
        crop = key_gen_magenta_fx(src_p)
        denom = measure_inner_sphere_diameter(crop) if mode == "sphere" else float(max(crop.shape[0], crop.shape[1]))
        sc = target_px / max(1.0, denom)
        placed[key] = place_centered(crop, sc)

    # Save all 24 raw frames & QA 3-bg strips
    frame_order = [
        "orig_01", "orig_02", "bridge_2b", "orig_03", "bridge_3b",
        "orig_04", "bridge_4b", "orig_05", "bridge_5b", "orig_06",
        "charge_6b", "charge_6c",
        "orig_07", "fly_7b", "orig_08", "fly_8b",
        "orig_09", "orig_10", "orig_11", "orig_12",
        "orig_13", "orig_14", "orig_15", "orig_16",
    ]
    for fid in frame_order:
        placed[fid].save(raw_dir / f"{fid}.png")

    render_3bg_strip([(k, placed[k]) for k in frame_order[:12]], QA_DIR / "qa_genki_fx_v2_charge_12f_3bg.png")
    render_3bg_strip([(k, placed[k]) for k in frame_order[12:16]], QA_DIR / "qa_genki_fx_v2_fly_4f_3bg.png")
    render_3bg_strip([(k, placed[k]) for k in frame_order[16:]], QA_DIR / "qa_genki_fx_v2_impact_explode_8f_3bg.png")

    manifest = {
        "schema": "generate2dsprite.animation_clips.v2",
        "art_source": "existing",
        "pixel_art": True,
        "sampling": "nearest",
        "anchor_px": [ORB_CENTER[0], ORB_CENTER[1]],
        "frames": [
            {"name": fid, "file": f"raw_frames/{fid}.png"}
            for fid in frame_order
        ],
        "clips": {
            "genki_charge_fx": {
                "loop_policy": "oneshot",
                "role": "fx",
                "frames": ["orig_01", "orig_02", "bridge_2b", "orig_03", "bridge_3b", "orig_04", "bridge_4b", "orig_05", "bridge_5b", "orig_06"],
                "duration_ms": [120] * 10,
            },
            "genki_charge_hold_fx": {
                "loop_policy": "cycle",
                "role": "fx",
                "frames": ["orig_06", "charge_6b", "charge_6c"],
                "duration_ms": [120, 120, 120],
            },
            "genki_fly_fx": {
                "loop_policy": "cycle",
                "role": "fx",
                "frames": ["orig_07", "fly_7b", "orig_08", "fly_8b"],
                "duration_ms": [80, 80, 80, 80],
            },
            "genki_impact_fx": {
                "loop_policy": "oneshot",
                "role": "fx",
                "frames": ["orig_09", "orig_10", "orig_11", "orig_12"],
                "duration_ms": [100, 100, 100, 100],
            },
            "genki_explode_fx": {
                "loop_policy": "oneshot",
                "role": "fx",
                "frames": ["orig_13", "orig_14", "orig_15", "orig_16"],
                "duration_ms": [120, 120, 120, 120],
            },
        },
    }
    mpath = WORK_DIR / "clips-manifest.json"
    mpath.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    clips_out = WORK_DIR / "clips_out"
    bundle_out = WORK_DIR / "bundle_out"
    subprocess.run([sys.executable, str(BUILD_CLIPS_SCRIPT), "--manifest", str(mpath), "--output-dir", str(clips_out)], check=True)
    subprocess.run(
        [
            sys.executable, str(EXPORT_ENGINE_SCRIPT),
            "--clips", str(clips_out / "animation-clips.json"),
            "--target", "godot-spriteframes",
            "--output-dir", str(bundle_out),
            "--name", "genki_fx",
            "--sampling", "nearest",
            "--godot-fps", "60",
            "--max-atlas-size", "4096",
            "--padding", "2",
            "--extrude", "1",
        ],
        check=True,
    )

    OUT_FX_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(bundle_out / "godot" / "genki_fx-atlas-00.png", OUT_FX_DIR / "genki_fx-atlas-00.png")
    shutil.copy2(bundle_out / "godot" / "genki_fx.tres", OUT_FX_DIR / "genki_fx.tres")
    exp_meta = json.loads((bundle_out / "engine-export.json").read_text(encoding="utf-8"))
    exp_meta["orb_scale"] = round(orb_scale, 4)
    exp_meta["explode_scale"] = round(explode_scale, 4)
    exp_meta["explode_ground_y_px"] = EXPLODE_GROUND_Y
    (OUT_FX_DIR / "fx-export.json").write_text(json.dumps(exp_meta, indent=2) + "\n", encoding="utf-8")

    atlas_im = Image.open(OUT_FX_DIR / "genki_fx-atlas-00.png")
    assert max(atlas_im.size) <= 4096, f"Genki FX atlas exceeded 4096: {atlas_im.size}"
    print(json.dumps({
        "status": "ok",
        "clips": len(manifest["clips"]),
        "frames": len(frame_order),
        "atlas_size": [atlas_im.width, atlas_im.height],
        "atlas_sha256": sha256_file(OUT_FX_DIR / "genki_fx-atlas-00.png"),
        "tres_sha256": sha256_file(OUT_FX_DIR / "genki_fx.tres"),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
