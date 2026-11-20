#!/usr/bin/env python3
"""
DR7-Studio — Songoku Hero Demo v9 Fixes Registration, Walk-QC & Repack Pipeline.
- Keeps 24/24 approved Base Goku frames SHA-256 locked (QA GATE 0).
- Keys & registers all 8 newly generated attack frames (`atk1_02`, `atk1_04`, `atk1_08`,
  `atk1_10`, `atk2_02`, `atk5_05`, `atk5_06`, `atk6_02`) on #FF00FF while preserving
  legitimate nearby punch/slash streaks (2D proximity component ownership), zero magenta
  spill, zero enclosed pockets, 100% hard binary alpha, and crisp dark body outlines.
- Syncs shared combo slots (`atk2_01 = atk1_04`, `atk5_01 = atk1_10`, `atk5_07 = atk1_08`).
- Runs Walk-Referenced Concept QC Gate (`qc_songoku_walk_gate.py`).
- Renders 3-background QA filmstrips for `idle_combat`, `attack_light`, `attack_2`, `attack_5`, `attack_6`.
- Repacks `review/songoku_hero_demo` (1 PNG page, Nearest, 60Hz) and updates `review-roster.json`.
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys
from typing import Dict, List, Tuple

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = pathlib.Path(__file__).resolve().parents[2]
DEMO_DIR = ROOT / "review" / "songoku_hero_demo"
RAW_DIR = DEMO_DIR / "source" / "raw_frames"
WORK_DIR = ROOT / "work" / "characters" / "songoku_ssj1" / "v9_fixes"

sys.path.insert(0, str(ROOT / "tools" / "pipeline"))
import repack_songoku_hero_demo as repacker  # noqa: E402
import qc_songoku_walk_gate as walk_qc  # noqa: E402

CANVAS_W = 288
CANVAS_H = 288
ANCHOR_X = 144
ANCHOR_Y = 248

# Frames that legitimately include detached motion streaks / slash arcs near the body
STREAK_FRAMES = {"atk1_02", "atk1_04", "atk1_08", "atk1_10"}

# Shared frame copies across combo clips (keeps combo links 100% consistent)
SHARED_COPIES = {
    "atk1_04": ["atk2_01"],
    "atk1_08": ["atk5_07"],
    "atk1_10": ["atk5_01"],
}

# Exact target placements & scale targets (measured against walk_ssj 125px & original sheet proportions)
FRAME_SPECS = {
    "atk1_02": {"target_h": 119, "y1": 247, "cx": 144.0, "has_streak": True},
    "atk1_04": {"target_h": 105, "y1": 247, "cx": 144.0, "has_streak": True},
    "atk1_08": {"target_h": 131, "y1": 247, "cx": 141.0, "has_streak": True},
    "atk1_10": {"target_h": 133, "y1": 247, "cx": 146.0, "has_streak": True},
    "atk2_02": {"target_h": 105, "y1": 247, "cx": 141.0, "has_streak": False},
    "atk5_05": {"target_h": 92,  "y1": 247, "cx": 145.0, "has_streak": False},
    "atk5_06": {"target_h": 126, "y1": 247, "cx": 143.0, "has_streak": False},
    "atk6_02": {"target_h": 112, "y1": 247, "cx": 143.0, "has_streak": False},
}


def key_magenta_preserve_streaks(img: Image.Image, allow_streaks: bool) -> Tuple[np.ndarray, Dict[str, int]]:
    """Pocket-first 2-stage chroma key on #FF00FF that preserves nearby punch/slash FX streaks."""
    arr = np.array(img.convert("RGBA"), dtype=np.uint8)
    r = arr[:, :, 0].astype(np.int16)
    g = arr[:, :, 1].astype(np.int16)
    b = arr[:, :, 2].astype(np.int16)

    # Stage 1: Remove magenta background (exterior + enclosed interior pockets)
    is_magenta = (
        ((r > 155) & (b > 155) & (g < 135) & ((r - g) > 48) & ((b - g) > 48))
        | ((r > 190) & (b > 190) & (g < 170) & ((r - g) > 35) & ((b - g) > 35))
        | ((r > 215) & (b > 215) & (g < 195) & ((r - g) > 25) & ((b - g) > 25))
    )
    fg = ~is_magenta

    # 2D Component Ownership Masking
    labeled, n_comp = ndimage.label(fg, structure=np.ones((3, 3), dtype=np.int32))
    if n_comp > 1:
        sizes = np.array(ndimage.sum(fg, labeled, range(1, n_comp + 1)))
        main_idx = int(np.argmax(sizes)) + 1
        main_mask = labeled == main_idx
        if allow_streaks:
            # Keep components >= 120 px (at 1024px source res) that are within 140px of main body
            near_body = ndimage.binary_dilation(main_mask, iterations=1)
            ys_m, xs_m = np.where(main_mask)
            my0, my1 = max(0, int(ys_m.min()) - 120), min(arr.shape[0], int(ys_m.max()) + 120)
            mx0, mx1 = max(0, int(xs_m.min()) - 180), min(arr.shape[1], int(xs_m.max()) + 180)
            keep = main_mask.copy()
            for cid in range(1, n_comp + 1):
                if cid == main_idx:
                    continue
                if sizes[cid - 1] >= 120:
                    cm = labeled == cid
                    cys, cxs = np.where(cm)
                    cy, cx = float(cys.mean()), float(cxs.mean())
                    if my0 <= cy <= my1 and mx0 <= cx <= mx1:
                        keep |= cm
            fg = keep
        else:
            fg = main_mask

    # Stage 2: 2px outer ring magenta spill removal
    dilated_bg = ndimage.binary_dilation(~fg, iterations=2)
    ring = fg & dilated_bg
    spill = ring & ((r - g) > 22) & ((b - g) > 22) & (g < 190)
    fg = fg & ~spill

    # Re-filter tiny stray fragments (< 40 px at 1024px res)
    labeled2, n_comp2 = ndimage.label(fg, structure=np.ones((3, 3), dtype=np.int32))
    if n_comp2 > 1:
        sizes2 = np.array(ndimage.sum(fg, labeled2, range(1, n_comp2 + 1)))
        main_idx2 = int(np.argmax(sizes2)) + 1
        if allow_streaks:
            keep2 = labeled2 == main_idx2
            for cid in range(1, n_comp2 + 1):
                if cid != main_idx2 and sizes2[cid - 1] >= 60:
                    keep2 |= (labeled2 == cid)
            fg = keep2
        else:
            fg = labeled2 == main_idx2

    out = arr.copy()
    out[~fg] = [0, 0, 0, 0]
    out[fg, 3] = 255

    # Neutralize any subtle magenta tint on remaining outer 1px ring (e.g. pale streaks near magenta)
    r2 = out[:, :, 0].astype(np.int16)
    g2 = out[:, :, 1].astype(np.int16)
    b2 = out[:, :, 2].astype(np.int16)
    b4 = fg & ~ndimage.binary_erosion(fg, structure=np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]]))
    tint = b4 & ((r2 - g2) > 16) & ((b2 - g2) > 16)
    if tint.any():
        # For dark outline pixels, snap cleanly to dark outline; for bright streak pixels, push toward warm white
        lum = 0.299 * r2 + 0.587 * g2 + 0.114 * b2
        dark_tint = tint & (lum < 140)
        bright_tint = tint & (lum >= 140)
        out[dark_tint] = [16, 12, 18, 255]
        if bright_tint.any():
            out[bright_tint, 1] = np.minimum(255, ((r2[bright_tint] + b2[bright_tint]) // 2)).astype(np.uint8)

    opaque_key_px = int((fg & is_magenta).sum())
    return out, {"opaque_key_px": opaque_key_px}


def register_attack_frame(name: str, gen_path: pathlib.Path, spec: Dict[str, object]) -> Tuple[Image.Image, Dict[str, object]]:
    has_streak = bool(spec["has_streak"])
    keyed, stats = key_magenta_preserve_streaks(Image.open(gen_path), allow_streaks=has_streak)
    vis = keyed[:, :, 3] > 0
    ys, xs = np.where(vis)
    y0, y1 = int(ys.min()), int(ys.max())
    x0, x1 = int(xs.min()), int(xs.max())
    crop = Image.fromarray(keyed[y0 : y1 + 1, x0 : x1 + 1], mode="RGBA")

    # Scale cleanly by target height with 1-pass Nearest (1px chunky gameplay pixel art!)
    target_h = int(spec["target_h"])
    scale = float(target_h) / max(1.0, float(crop.height))
    new_w = max(16, int(round(crop.width * scale)))
    new_h = max(16, int(round(crop.height * scale)))
    resized = crop.resize((new_w, new_h), Image.Resampling.NEAREST)
    rarr = np.array(resized, dtype=np.uint8)
    rmask = rarr[:, :, 3] >= 128
    rarr[~rmask] = [0, 0, 0, 0]
    rarr[rmask, 3] = 255

    # Remove any 1-2px detached dust specks after downscaling
    rlbl, rn = ndimage.label(rmask, structure=np.ones((3, 3)))
    if rn > 1:
        rsizes = np.array(ndimage.sum(rmask, rlbl, range(1, rn + 1)))
        rmain = int(np.argmax(rsizes)) + 1
        rkeep = rlbl == rmain
        if has_streak:
            for cid in range(1, rn + 1):
                if cid != rmain and rsizes[cid - 1] >= 4:
                    rkeep |= (rlbl == cid)
        rarr[~rkeep] = [0, 0, 0, 0]
        rmask = rkeep

    # Final post-resize border fringe cleanup on non-streak body edges
    rr = rarr[:, :, 0].astype(np.int16)
    rg = rarr[:, :, 1].astype(np.int16)
    rb = rarr[:, :, 2].astype(np.int16)
    rlum = 0.299 * rr + 0.587 * rg + 0.114 * rb
    rb4 = rmask & ~ndimage.binary_erosion(rmask, structure=np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]]))
    pink_b = rb4 & ((rr - rg) > 18) & ((rb - rg) > 18) & (rg < 180)
    rarr[pink_b] = [16, 12, 18, 255]
    if not has_streak:
        # Clean stray bright/gray border speckles on body-only frames (matching walk_ssj crisp dark outline)
        rarr[rb4 & (rlum >= 50)] = [16, 12, 18, 255]

    # Measure body-only center X (exclude white/cyan streak pixels so body stays centered at anchor!)
    rmask = rarr[:, :, 3] > 0
    body_lbl, _ = ndimage.label(rmask, structure=np.ones((3, 3)))
    if body_lbl.max() > 0:
        bsizes = np.array(ndimage.sum(rmask, body_lbl, range(1, int(body_lbl.max()) + 1)))
        main_body = body_lbl == (int(np.argmax(bsizes)) + 1)
    else:
        main_body = rmask
    bys, bxs = np.where(main_body)
    body_cx = float(np.median(bxs))
    body_y1 = int(bys.max())

    paste_x = int(round(float(spec["cx"]) - body_cx))
    paste_y = int(spec["y1"]) - body_y1
    # Clamp safely inside 288x288 canvas
    paste_x = max(2, min(CANVAS_W - new_w - 2, paste_x))
    paste_y = max(2, min(CANVAS_H - new_h - 2, paste_y))

    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    canvas.paste(Image.fromarray(rarr, mode="RGBA"), (paste_x, paste_y))
    return canvas, stats


def main() -> int:
    repacker.verify_base_lock()

    bak_dir = WORK_DIR / "backup_v8"
    bak_dir.mkdir(parents=True, exist_ok=True)

    # 1. Register all 8 fixed attack frames + update shared copies
    updated_files: List[pathlib.Path] = []
    for nm, spec in FRAME_SPECS.items():
        gen_path = WORK_DIR / f"gen_{nm}" / "generated.png"
        if not gen_path.exists():
            raise FileNotFoundError(f"Missing generated frame: {gen_path}")
        dst = RAW_DIR / f"{nm}.png"
        if not (bak_dir / dst.name).exists():
            shutil.copy2(dst, bak_dir / dst.name)
        im, _ = register_attack_frame(nm, gen_path, spec)
        im.save(dst)
        updated_files.append(dst)
        for copy_nm in SHARED_COPIES.get(nm, []):
            copy_dst = RAW_DIR / f"{copy_nm}.png"
            if not (bak_dir / copy_dst.name).exists():
                shutil.copy2(copy_dst, bak_dir / copy_dst.name)
            shutil.copy2(dst, copy_dst)
            updated_files.append(copy_dst)
            print(f"[SYNC COPY] {nm}.png -> {copy_nm}.png")

    # 2. Run Walk-Referenced Concept QC Gate on idle_combat + all updated attack frames
    canon_pal, walk_stats = walk_qc.load_walk_reference_palette()
    print(f"[WALK QC REF] {json.dumps(walk_stats)}")
    qc_all_ok = True
    qc_report = []
    check_list = [RAW_DIR / f"idle_combat_{i:02d}.png" for i in range(4)] + updated_files
    for fp in check_list:
        allow_fx = fp.stem in STREAK_FRAMES or fp.stem in {"atk2_01", "atk5_01", "atk5_07"}
        res = walk_qc.audit_frame_against_walk(fp, canon_pal, allow_fx_border=allow_fx)
        qc_report.append(res)
        tag = "PASS" if res["pass"] else "FAIL"
        if not res["pass"]:
            qc_all_ok = False
        print(
            f"[WALK QC {tag}] {res['file']}: bbox={res['bbox']} y1={res['y1']} "
            f"bdark={res['border_dark_frac']:.3f} pink={res['border_pink']} "
            f"hair={res['gold_hair_px']} gi={res['orange_gi_px']} blue={res['royal_blue_px']} "
            f"pal_med={res['pal_median_dist']:.1f} errs={res['errors']}"
        )
    (WORK_DIR / "walk_qc_v9_report.json").write_text(json.dumps({"walk_ref": walk_stats, "frames": qc_report}, indent=2) + "\n")

    # 3. Render 3-background QA filmstrips for all modified clips
    repacker.render_3bg_filmstrip(
        [Image.open(RAW_DIR / f"idle_combat_{i:02d}.png").convert("RGBA") for i in range(4)],
        WORK_DIR / "filmstrip_3bg_idle_combat_v9.png",
        (84, 120, 206, 258),
    )
    repacker.render_3bg_filmstrip(
        [Image.open(RAW_DIR / f"atk1_{i:02d}.png").convert("RGBA") for i in [2, 4, 8, 10]],
        WORK_DIR / "filmstrip_3bg_atk1_fixes_v9.png",
        (56, 108, 224, 258),
    )
    repacker.render_3bg_filmstrip(
        [Image.open(RAW_DIR / f"atk2_{i:02d}.png").convert("RGBA") for i in range(4)],
        WORK_DIR / "filmstrip_3bg_atk2_v9.png",
        (56, 118, 224, 258),
    )
    repacker.render_3bg_filmstrip(
        [Image.open(RAW_DIR / f"atk5_{i:02d}.png").convert("RGBA") for i in [1, 5, 6, 7]],
        WORK_DIR / "filmstrip_3bg_atk5_fixes_v9.png",
        (56, 108, 224, 258),
    )
    repacker.render_3bg_filmstrip(
        [Image.open(RAW_DIR / f"atk6_{i:02d}.png").convert("RGBA") for i in [0, 1, 2, 3]],
        WORK_DIR / "filmstrip_3bg_atk6_fixes_v9.png",
        (68, 112, 220, 258),
    )

    if not qc_all_ok:
        print("[WARN] Some frames failed Walk QC Gate — inspect filmstrips before finalizing!")
        return 2

    # 4. Repack songoku_hero_demo bundle (1 page PNG, Nearest, 60Hz) + update review-roster.json
    repacker.verify_base_lock()
    res = repacker.rebuild_bundle_and_roster()
    print(f"[REPACK OK] {json.dumps(res)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
