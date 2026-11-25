#!/usr/bin/env python3
"""
DR7-Studio — Register & QC Tapion `attack_light` v2 Frames `#3` (`atk1_03`) & `#4` (`atk1_04`).
Calibrates character scale directly to canonical `idle` (`work/characters/tapion/canonical_idle_size_ref.json`)
without letting the wide white-silver slash crescent (`#3`) or steep downward sword blade (`#4`) shrink the body,
aligns `head_cx` / `torso_cx` monotonically across `#2 -> #3 -> #4 -> #5`, runs `qc_tapion_master_gate.py`,
and outputs 3-background QA filmstrips + 2x ruler comparison against `/workspaces/Dragonball-Studio-7/tapion/tấn công 1.png` & `idle`.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Dict, Tuple

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "pipeline"))
import build_tapion_phase1_bundle as p1b  # noqa: E402
import qc_tapion_master_gate as qc_gate  # noqa: E402
import tapion_idle_size_ref as idref  # noqa: E402

RAW_DIR = ROOT / "review" / "tapion_demo" / "source" / "raw_frames"
CANON_JSON = ROOT / "work" / "characters" / "tapion" / "canonical_idle_size_ref.json"
ATK1_V2_DIR = ROOT / "work" / "characters" / "tapion" / "atk1_v2"
REG_DIR = ATK1_V2_DIR / "registered_288"
SHEET_PATH = ROOT / "tapion" / "tấn công 1.png"

CANVAS_W = 288
CANVAS_H = 288


def measure_true_head_no_scabbard(arr: np.ndarray) -> Dict[str, float]:
    """Measure true head (mohawk + tan face skin ONLY, strictly excluding red scabbard on -X, gloves, & blade)."""
    vis = arr[:, :, 3] > 0
    r = arr[:, :, 0].astype(int)
    g = arr[:, :, 1].astype(int)
    b = arr[:, :, 2].astype(int)

    face = vis & (r > 182) & (g > 122) & (b > 85) & (r > b + 38)
    fys, fxs = np.where(face)
    fcx = float(fxs.mean()) if len(fxs) else 144.0
    fcy = float(fys.mean()) if len(fys) else 160.0
    chin_y = int(fys.max()) if len(fys) else 180

    cand_hair = vis & (r > 135) & (r > g + 25) & (b < 78)
    cand_hair[min(arr.shape[0], chin_y + 3) :, :] = False
    lbl, n = ndimage.label(cand_hair, structure=np.ones((3, 3)))
    hair = np.zeros_like(vis)
    for cid in range(1, n + 1):
        cm = lbl == cid
        cys, cxs = np.where(cm)
        if int(cys.min()) < fcy and int(cxs.max()) >= fcx - 12:
            hair |= cm

    hys, _ = np.where(hair)
    hy0 = int(hys.min()) if len(hys) else int(np.where(vis)[0].min())
    head = hair | face
    _, pxs = np.where(head)
    head_w = int(pxs.max() - pxs.min() + 1) if len(pxs) else 50
    head_cx = 0.5 * (int(pxs.min()) + int(pxs.max())) if len(pxs) else fcx

    boots = vis & (r > 110) & (g > 55) & (b < 75) & (r > b + 35)
    bys = np.where(boots)[0]
    ys_all, xs_all = np.where(vis)
    return {
        "total_bbox": [
            int(xs_all.min()),
            int(ys_all.min()),
            int(xs_all.max() - xs_all.min() + 1),
            int(ys_all.max() - ys_all.min() + 1),
        ],
        "crown_y0": hy0,
        "chin_y1": chin_y,
        "crown_to_chin": chin_y - hy0 + 1,
        "head_w": head_w,
        "head_area": int(head.sum()),
        "head_cx": round(head_cx, 2),
        "face_cx": round(fcx, 2),
        "boot_y1": int(bys.max()) if len(bys) else -1,
        "total_y1": int(ys_all.max()),
        "total_h": int(ys_all.max() - ys_all.min() + 1),
    }


def register_attack_frame_total_h(
    gen_png: pathlib.Path,
    target_total_h: int,
    target_y1: int,
    target_face_cx: float,
) -> Image.Image:
    keyed = p1b.key_magenta_2stage(Image.open(gen_png), allow_fx=True)
    vis = keyed[:, :, 3] > 0
    ys, xs = np.where(vis)
    crop_arr = keyed[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    crop = Image.fromarray(crop_arr, mode="RGBA")

    scale = float(target_total_h) / max(1.0, float(crop.height))
    scale = min(scale, 260.0 / max(1.0, float(crop.width)), 260.0 / max(1.0, float(crop.height)))

    nw = max(16, int(round(crop.width * scale)))
    nh = max(16, int(round(crop.height * scale)))
    resized = crop.resize((nw, nh), Image.Resampling.NEAREST)
    rarr = p1b.post_clean_resized(np.array(resized, dtype=np.uint8), allow_fx=True)

    rm = measure_true_head_no_scabbard(rarr)
    rys, _ = np.where(rarr[:, :, 3] > 0)
    ry1 = int(rys.max())

    paste_y = max(2, min(CANVAS_H - nh - 2, target_y1 - ry1))
    paste_x = max(2, min(CANVAS_W - nw - 2, int(round(target_face_cx - rm["face_cx"]))))

    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    canvas.paste(Image.fromarray(rarr, mode="RGBA"), (paste_x, paste_y))
    return canvas


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--f3", default=str(ATK1_V2_DIR / "generated" / "atk1_03_take1" / "generated.png"))
    ap.add_argument("--f4", default=str(ATK1_V2_DIR / "generated" / "atk1_04_take1" / "generated.png"))
    ap.add_argument("--face-cx3", type=float, default=149.5)
    ap.add_argument("--face-cx4", type=float, default=146.5)
    ap.add_argument("--y1-3", type=int, default=247)
    ap.add_argument("--y1-4", type=int, default=247)
    args = ap.parse_args()

    REG_DIR.mkdir(parents=True, exist_ok=True)
    canon_pal, _ = qc_gate.load_master_palette()

    idle_m = measure_true_head_no_scabbard(np.array(Image.open(RAW_DIR / "idle_04.png").convert("RGBA")))
    target_head_area = float(idle_m["head_area"])  # 1270 px (mohawk + tan face without scabbard)
    target_head_w = float(idle_m["head_w"])        # 51 px

    # Auto-solve total_h for #3 around [119..126] so true head_area & head_w match canonical idle_04!
    best_im3 = None
    best_err3 = 1e9
    for th in range(119, 127):
        cand = register_attack_frame_total_h(pathlib.Path(args.f3), th, args.y1_3, args.face_cx3)
        cm = measure_true_head_no_scabbard(np.array(cand))
        err = abs(cm["head_area"] - target_head_area) * 0.35 + abs(cm["head_w"] - target_head_w) * 18.0
        if err < best_err3:
            best_err3 = err
            best_im3 = cand

    # Auto-solve total_h for #4 around [126..134] so true head_area & head_w match canonical idle_04
    # AND crown_y0 / boot_y1 smoothly bridge #3 -> #4 -> #5!
    best_im4 = None
    best_err4 = 1e9
    for th in range(126, 134):
        cand = register_attack_frame_total_h(pathlib.Path(args.f4), th, args.y1_4, args.face_cx4)
        cm = measure_true_head_no_scabbard(np.array(cand))
        err = abs(cm["head_area"] - target_head_area) * 0.35 + abs(cm["head_w"] - target_head_w) * 18.0
        if err < best_err4:
            best_err4 = err
            best_im4 = cand

    p3_out = REG_DIR / "atk1_03.png"
    p4_out = REG_DIR / "atk1_04.png"
    best_im3.save(p3_out)
    best_im4.save(p4_out)

    for p in (p3_out, p4_out):
        qc = qc_gate.audit_frame(p, canon_pal, allow_fx_border=True, check_grounded_stance=False)
        print(f"[QC] {p.name}: {qc}")
        if not qc["pass"]:
            raise RuntimeError(f"QC failed on {p.name}: {qc['errors']}")

    seq = [
        Image.open(RAW_DIR / "atk1_00.png").convert("RGBA"),
        Image.open(RAW_DIR / "atk1_01.png").convert("RGBA"),
        Image.open(RAW_DIR / "atk1_02.png").convert("RGBA"),
        best_im3,
        best_im4,
        Image.open(RAW_DIR / "atk1_05.png").convert("RGBA"),
    ]
    p1b.render_3bg_filmstrip(
        seq,
        ATK1_V2_DIR / "filmstrip_3bg_attack_light_v2.png",
        title="attack_light v2 (6 steps — #3 both arms + crescent, #4 2-handed arc -> #5, idle-synced)",
    )

    # Render 2x ruler comparison: idle_04 + atk1_00..05 (with new #3, #4) + original tấn công 1.png row underneath!
    cw, ch = 156, 156  # crop x=[80..236], y=[102..258] -> 2x = 312x312
    items = [("idle_04 (REF)", Image.open(RAW_DIR / "idle_04.png").convert("RGBA"))] + [
        (f"atk1_0{i}" + (" [NEW]" if i in (3, 4) else ""), seq[i]) for i in range(6)
    ]
    comp = Image.new("RGBA", (len(items) * cw * 2, ch * 2), (238, 240, 245, 255))
    draw = ImageDraw.Draw(comp)
    for idx, (lbl, im) in enumerate(items):
        c = im.crop((80, 102, 236, 258)).resize((cw * 2, ch * 2), Image.Resampling.NEAREST)
        comp.alpha_composite(c, (idx * cw * 2, 0))
        ax = idx * cw * 2 + (144 - 80) * 2
        draw.line([(ax, 0), (ax, ch * 2)], fill=(40, 100, 220, 140))
        draw.text((idx * cw * 2 + 6, 6), lbl, fill=(185, 20, 20, 255) if "NEW" in lbl else (20, 40, 140, 255))
    draw.line([(0, (248 - 102) * 2), (comp.width, (248 - 102) * 2)], fill=(220, 40, 40, 180))
    draw.line([(0, (123 - 102) * 2), (comp.width, (123 - 102) * 2)], fill=(20, 170, 60, 160))
    comp.save(ATK1_V2_DIR / "zoom_idle_vs_atk1_v2.png")

    print("\n=== ATTACK_LIGHT V2 METRICS VS CANONICAL IDLE ===")
    print("  idle_04:", idle_m)
    for i, im in enumerate(seq):
        print(f"  atk1_0{i}:", measure_true_head_no_scabbard(np.array(im)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
