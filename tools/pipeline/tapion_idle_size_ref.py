#!/usr/bin/env python3
"""
DR7-Studio — Canonical `idle` Size Reference & Pose Scale Synchronizer for Tapion.
Owner Rule (2026-11-25):
  `idle` (`idle_04` master + `idle_00..03`) is the official canonical size reference
  for synchronizing any mismatched frame across all Tapion animations.

Canonical `idle` anatomical invariants (on 288x288 canvas, anchor [144, 248]):
  - Standing height: 125 px (`idle_04`: 68x125, `idle_00..03`: 68..70 x 127..128)
  - Head crown-to-chin (vermilion/crimson mohawk top -> tan face chin, arms/gloves/hilt excluded): 56 px (range 54..57)
  - Head-only width (mohawk + tan face skin, arms/gloves/hilt excluded): 54 px (range 53..55)
  - Head pixel area (mohawk + tan face skin): ~1511 px (range 1483..1538)
  - Upright crown-to-belt: 72..76 px
"""
from __future__ import annotations

import json
import math
import pathlib
import sys
from typing import Dict, Tuple

import numpy as np
from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "pipeline"))
import build_tapion_phase1_bundle as p1b  # noqa: E402
import qc_tapion_master_gate as qc_gate  # noqa: E402

RAW_DIR = ROOT / "review" / "tapion_demo" / "source" / "raw_frames"
P1_GEN = ROOT / "work" / "characters" / "tapion" / "phase1" / "generated"
CANON_REF_JSON = ROOT / "work" / "characters" / "tapion" / "canonical_idle_size_ref.json"
JUMP_V2_DIR = ROOT / "work" / "characters" / "tapion" / "jump_v2"

CANVAS_W = 288
CANVAS_H = 288
ANCHOR_X = 144
ANCHOR_Y = 248


def measure_pure_head_and_body(arr: np.ndarray) -> Dict[str, float]:
    """Measure pure head (mohawk + tan face skin ONLY, strictly excluding brown gloves, green sleeves & silver hilt!)."""
    vis = arr[:, :, 3] > 0
    ys, xs = np.where(vis)
    y0, y1, x0, x1 = int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max())
    w, h = int(x1 - x0 + 1), int(y1 - y0 + 1)

    r = arr[:, :, 0].astype(int)
    g = arr[:, :, 1].astype(int)
    b = arr[:, :, 2].astype(int)

    # Top 52% band for head search
    top_band = np.zeros_like(vis)
    top_band[y0 : min(arr.shape[0], y0 + int(round(h * 0.54))), :] = True

    # Vermilion/orange/crimson hair (bright red-orange, low blue; excludes brown gloves where r-g <= 55 and r < 160)
    hair = vis & top_band & (r > 145) & (r > g + 28) & (b < 72)
    hys, hxs = np.where(hair)
    hair_y0 = int(hys.min()) if len(hys) else y0

    # Tan face/ear skin ONLY (bright warm peach/tan: r > 185, g > 125, b > 88 — completely excludes brown leather gloves!)
    face_band = np.zeros_like(vis)
    face_band[hair_y0 : min(arr.shape[0], hair_y0 + int(round(h * 0.48))), :] = True
    face_skin = vis & face_band & (r > 182) & (g > 122) & (b > 85) & (r > b + 38)
    fys, fxs = np.where(face_skin)
    chin_y = int(fys.max()) if len(fys) else (hair_y0 + int(round(h * 0.44)))

    pure_head = hair | face_skin
    phys, phxs = np.where(pure_head)
    pure_head_w = int(phxs.max() - phxs.min() + 1) if len(phxs) else w
    crown_to_chin = int(chin_y - hair_y0 + 1)
    pure_head_area = int(pure_head.sum())

    return {
        "bbox": [x0, y0, w, h],
        "crown_to_chin_px": crown_to_chin,
        "pure_head_w_px": pure_head_w,
        "pure_head_area_px": pure_head_area,
        "total_area_px": int(vis.sum()),
    }


def register_to_idle_canonical_scale(
    gen_path: pathlib.Path,
    target_h: int,
    y1_target: int,
    cx_target: float = 144.0,
    allow_fx: bool = False,
) -> Image.Image:
    """1-pass Nearest registration from 1024x1024 raw pose directly to exact idle-matched height without arm/head_w distortion."""
    keyed = p1b.key_magenta_2stage(Image.open(gen_path), allow_fx=allow_fx)
    vis = keyed[:, :, 3] > 0
    ys, xs = np.where(vis)
    crop_arr = keyed[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    crop = Image.fromarray(crop_arr, mode="RGBA")

    scale = float(target_h) / float(crop.height)
    nw = max(16, int(round(crop.width * scale)))
    nh = target_h
    resized = crop.resize((nw, nh), Image.Resampling.NEAREST)
    rarr = p1b.post_clean_resized(np.array(resized, dtype=np.uint8), allow_fx=allow_fx)

    rmask = rarr[:, :, 3] > 0
    rys, rxs = np.where(rmask)
    ry1 = int(rys.max())
    anchor_local_x = p1b.detect_body_core_center_x(rarr, has_fx=allow_fx)

    paste_y = max(2, min(CANVAS_H - nh - 2, y1_target - ry1))
    paste_x = max(2, min(CANVAS_W - nw - 2, int(round(cx_target - anchor_local_x))))

    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    canvas.paste(Image.fromarray(rarr, mode="RGBA"), (paste_x, paste_y))
    return canvas


def main() -> int:
    JUMP_V2_DIR.mkdir(parents=True, exist_ok=True)
    canon_pal, _ = qc_gate.load_master_palette()

    # 1. Measure & persist canonical `idle` reference metrics
    idle_frames = ["idle_04", "idle_03", "idle_02", "idle_00", "idle_01"]
    idle_measurements = {}
    for fn in idle_frames:
        idle_measurements[fn] = measure_pure_head_and_body(np.array(Image.open(RAW_DIR / f"{fn}.png").convert("RGBA")))

    canon_crown_to_chin = round(float(np.mean([m["crown_to_chin_px"] for m in idle_measurements.values()])), 2)
    canon_head_w = round(float(np.mean([m["pure_head_w_px"] for m in idle_measurements.values()])), 2)
    canon_head_area = round(float(np.mean([m["pure_head_area_px"] for m in idle_measurements.values()])), 1)
    canon_total_area = round(float(np.mean([m["total_area_px"] for m in idle_measurements.values()])), 1)

    canon_doc = {
        "schema": "dr7.tapion.canonical_size_reference.v1",
        "reference_clip": "idle",
        "owner_rule": "Mặc định idle là kích thước chuẩn để tham chiếu đồng nhất cho mọi hoạt ảnh bị lệch kích thước.",
        "canonical_targets": {
            "standing_height_px": 125,
            "standing_width_px": 68,
            "crown_to_chin_px": canon_crown_to_chin,
            "pure_head_w_px": canon_head_w,
            "pure_head_area_px": canon_head_area,
            "standing_total_area_px": canon_total_area,
        },
        "idle_frames": idle_measurements,
    }
    CANON_REF_JSON.write_text(json.dumps(canon_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[CANONICAL IDLE LOCKED] crown_to_chin={canon_crown_to_chin}px, head_w={canon_head_w}px, head_area={canon_head_area}px")

    # 2. Calibrate jump_03 (step #3) & jump_04 (step #4) directly to canonical `idle` head/body scale:
    # - jump_03: target_h = 116 -> pure_head_area = 1513px (exact match to idle_04 = 1513px!), crown_to_chin = 54px, W=69px
    # - jump_04: uses full-proportion `gen_jump_04/generated.png` (non-pinched legs matching `idle`) calibrated to `idle_04`!
    j3_im = register_to_idle_canonical_scale(P1_GEN / "jump_03" / "generated.png", target_h=116, y1_target=239, cx_target=144.0)
    j4_src = JUMP_V2_DIR / "gen_jump_04" / "generated.png"
    if not j4_src.is_file():
        j4_src = P1_GEN / "jump_04" / "generated.png"
    # Auto-solve exact target_h in [122..130] so jump_04's pure_head_area & crown_to_chin match canonical `idle` (1511px, 56px)!
    best_h4 = 126
    best_err = 1e9
    for cand_h in range(120, 132):
        cand_im = register_to_idle_canonical_scale(j4_src, target_h=cand_h, y1_target=244, cx_target=144.0)
        cm = measure_pure_head_and_body(np.array(cand_im))
        err = abs(cm["crown_to_chin_px"] - canon_crown_to_chin) * 25.0 + abs(cm["pure_head_area_px"] - canon_head_area) * 0.25
        if err < best_err:
            best_err = err
            best_h4 = cand_h
    j4_im = register_to_idle_canonical_scale(j4_src, target_h=best_h4, y1_target=244, cx_target=144.0)
    j3_im.save(JUMP_V2_DIR / "jump_03.png")
    j4_im.save(JUMP_V2_DIR / "jump_04.png")

    # 3. Audit QC on jump_03 & jump_04 and compare all 6 jump frames against idle!
    for fn in ("jump_03", "jump_04"):
        qc_res = qc_gate.audit_frame(JUMP_V2_DIR / f"{fn}.png", canon_pal, allow_fx_border=False, check_grounded_stance=False)
        assert qc_res["pass"], f"QC failed on {fn}: {qc_res['errors']}"

    jump_seq = [
        Image.open(RAW_DIR / "jump_00.png").convert("RGBA"),
        Image.open(RAW_DIR / "jump_01.png").convert("RGBA"),
        Image.open(RAW_DIR / "jump_02.png").convert("RGBA"),
        j3_im,
        j4_im,
        Image.open(RAW_DIR / "jump_05.png").convert("RGBA"),
    ]
    p1b.render_3bg_filmstrip(jump_seq, JUMP_V2_DIR / "filmstrip_3bg_jump_v2.png", title="Tapion jump_v2 (frames #3 & #4 synced 1:1 to canonical idle)")

    print("\n=== JUMP V2 METRICS VS CANONICAL IDLE ===")
    print(f"  [REF] idle_04 : {idle_measurements['idle_04']}")
    for idx, im in enumerate(jump_seq):
        m = measure_pure_head_and_body(np.array(im))
        print(f"  jump step #{idx}: {m}")

    # Render 2x zoomed visual comparison: IDLE #0 (idle_04) + IDLE #3 (idle_00) + JUMP #0..#5
    cw, ch = 190, 304
    comp = Image.new("RGBA", (8 * cw, ch), (238, 240, 245, 255))
    draw = ImageDraw.Draw(comp)
    items = [
        ("IDLE #0 (Master 125)", Image.open(RAW_DIR / "idle_04.png").convert("RGBA")),
        ("IDLE #3 (Flute)", Image.open(RAW_DIR / "idle_00.png").convert("RGBA")),
    ] + [(f"JUMP #{i}", jump_seq[i]) for i in range(6)]
    for ci, (lbl, im) in enumerate(items):
        crop = im.crop((95, 106, 190, 258)).resize((cw, ch), Image.Resampling.NEAREST)
        comp.alpha_composite(crop, (ci * cw, 0))
        draw.text((ci * cw + 4, 4), lbl, fill=(20, 50, 160, 255) if "IDLE" in lbl else (175, 20, 20, 255))
    draw.line([(0, (123 - 106) * 2), (8 * cw, (123 - 106) * 2)], fill=(20, 170, 60, 160))
    draw.line([(0, (248 - 106) * 2), (8 * cw, (248 - 106) * 2)], fill=(225, 50, 50, 190))
    comp.save(JUMP_V2_DIR / "zoom_idle_vs_jump_v2.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
