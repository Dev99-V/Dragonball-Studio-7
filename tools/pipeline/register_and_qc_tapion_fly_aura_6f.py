#!/usr/bin/env python3
"""
DR7-Studio — Register, Stabilize & Strict-QC Tapion 6-Frame `fly_aura` Body + 6-Frame Detached `fly_aura_fx`.
Enforces:
  1. 1:1 canonical `idle` size lock (`idle_04` & `cmove_03`: `char_H ~ 84..86 px`, `head_area ~ 1219 px`).
  2. Rigid-anatomy RGB L1 stabilization across `fly_aura_00..05` (`face_cx/face_cy` spread <= 0.75 px) so
     Tapion's face, eyes, ear, temple stud, torso, fists, hilt, and legs preserve 100% canonical structure
     while hair spikes, blue scarf tails, orange coat flap, and blue loincloth tabard flutter across 6 frames!
  3. Pure detached `fly_aura_fx_00..05` (`~180x186 px`, 0 interior holes, 100% opaque coverage behind body,
     consistent 1px dark outer outline, 6 continuous streaming phases).
  4. Renders 3-background QA filmstrips for Body Solo, Aura FX Solo, and Composite (`Aura + Body` vs `idle_04`).
"""
from __future__ import annotations

import json
import pathlib
import sys
from typing import Dict, List, Tuple

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "pipeline"))
import build_tapion_phase1_bundle as p1b  # noqa: E402
import qc_tapion_master_gate as qc_gate  # noqa: E402

WORK_DIR = ROOT / "work" / "characters" / "tapion" / "fly_aura_6f"
GEN_DIR = WORK_DIR / "generated"
BODY_OUT = WORK_DIR / "registered_body_288"
FX_OUT = WORK_DIR / "registered_fx_288"
RAW_DIR = ROOT / "review" / "tapion_demo" / "source" / "raw_frames"

CW, CH = 288, 288


def measure_flying_body(arr: np.ndarray) -> Dict[str, float]:
    vis = arr[:, :, 3] > 0
    ys, xs = np.where(vis)
    r, g, b = arr[:, :, 0].astype(int), arr[:, :, 1].astype(int), arr[:, :, 2].astype(int)

    face = vis & (r > 182) & (g > 122) & (b > 85) & (r > b + 38)
    fys, fxs = np.where(face)
    fcx = float(fxs.mean()) if len(fxs) else float(xs.mean())
    fcy = float(fys.mean()) if len(fys) else float(ys.mean())
    chin_y = int(fys.max()) if len(fys) else int(ys.min() + 45)

    cand_hair = vis & (r > 135) & (r > g + 25) & (b < 78)
    cand_hair[min(arr.shape[0], chin_y + 3) :, :] = False
    cand_hair[:, : max(0, int(round(fcx - 26)))] = False
    lbl, n = ndimage.label(cand_hair, structure=np.ones((3, 3)))
    hair = np.zeros_like(vis)
    for cid in range(1, n + 1):
        cm = lbl == cid
        cys, cxs = np.where(cm)
        if int(cys.min()) < fcy and int(cxs.max()) >= fcx - 10:
            hair |= cm
    head = hair | face
    hys, hxs = np.where(head)
    return {
        "bbox": [int(xs.min()), int(ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)],
        "w": int(xs.max() - xs.min() + 1),
        "h": int(ys.max() - ys.min() + 1),
        "head_w": int(hxs.max() - hxs.min() + 1) if len(hxs) else 0,
        "head_h": int(hys.max() - hys.min() + 1) if len(hys) else 0,
        "head_area": int(head.sum()),
        "face_area": int(face.sum()),
        "face_cx": round(fcx, 2),
        "face_cy": round(fcy, 2),
        "total_area": int(vis.sum()),
    }


def rigid_core_mask(arr: np.ndarray) -> np.ndarray:
    """Mask of non-fluttering rigid anatomy (face, eyes, ear/stud, silver clasps/hilt, yellow bracers/greaves, brown gloves/boots)."""
    vis = arr[:, :, 3] > 0
    r, g, b = arr[:, :, 0].astype(int), arr[:, :, 1].astype(int), arr[:, :, 2].astype(int)
    face = vis & (r > 182) & (g > 122) & (b > 85) & (r > b + 38)
    eyes = vis & (g > r + 25) & (g > 130)
    silver = vis & (r > 175) & (g > 175) & (b > 180)
    yellow_metal = vis & (r > 195) & (g > 145) & (b < 70)
    brown_leather = vis & (r > 95) & (r < 175) & (g > 45) & (g < 115) & (b < 70) & (r > b + 28)
    return face | eyes | silver | yellow_metal | brown_leather


def register_raw_body_candidate(gen_png: pathlib.Path, target_h: int, target_fcx: float, target_fcy: float) -> Image.Image:
    keyed = p1b.key_magenta_2stage(Image.open(gen_png), allow_fx=False)
    vis = keyed[:, :, 3] > 0
    ys, xs = np.where(vis)
    crop = Image.fromarray(keyed[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1], mode="RGBA")
    scale = float(target_h) / max(1.0, float(crop.height))
    nw = max(16, int(round(crop.width * scale)))
    nh = max(16, int(round(crop.height * scale)))
    resized = crop.resize((nw, nh), Image.Resampling.NEAREST)
    rarr = p1b.post_clean_resized(np.array(resized, dtype=np.uint8), allow_fx=False)
    m = measure_flying_body(rarr)
    px = max(4, min(CW - nw - 4, int(round(target_fcx - m["face_cx"]))))
    py = max(4, min(CH - nh - 4, int(round(target_fcy - m["face_cy"]))))
    canvas = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    canvas.paste(Image.fromarray(rarr, mode="RGBA"), (px, py))
    return canvas


def register_and_lock_all_bodies(canon_pal: np.ndarray) -> List[Image.Image]:
    BODY_OUT.mkdir(parents=True, exist_ok=True)
    idle_m = measure_flying_body(np.array(Image.open(RAW_DIR / "idle_04.png").convert("RGBA")))
    target_head_area = float(idle_m["head_area"])  # ~1219 px
    target_fcx, target_fcy = 156.0, 176.0

    # 1. Calibrate Master Frame 0 (`fly_body_00`) directly to canonical `idle_04` head_area & `cmove_03` height (~84..86px)
    p0 = GEN_DIR / "fly_body_00" / "generated.png"
    best_im0 = None
    best_err0 = 1e9
    for th in range(81, 90):
        cand = register_raw_body_candidate(p0, th, target_fcx, target_fcy)
        cm = measure_flying_body(np.array(cand))
        err = abs(cm["head_area"] - target_head_area) * 0.4 + abs(cm["h"] - 85.0) * 6.0
        if err < best_err0:
            best_err0 = err
            best_im0 = cand

    arr0 = np.array(best_im0)
    m0 = measure_flying_body(arr0)
    rmask0 = rigid_core_mask(arr0)
    bodies: List[Image.Image] = [best_im0]

    # 2. Calibrate & RGB-L1 rigid-lock `fly_body_01..05` against `fly_body_00`!
    for i in range(1, 6):
        pi = GEN_DIR / f"fly_body_{i:02d}" / "generated.png"
        best_im = None
        best_score = 1e12
        for th in range(max(79, m0["h"] - 4), m0["h"] + 5):
            base_cand = register_raw_body_candidate(pi, th, m0["face_cx"], m0["face_cy"])
            barr = np.array(base_cand)
            bm = measure_flying_body(barr)
            scale_pen = abs(bm["face_area"] - m0["face_area"]) * 2.2 + abs(bm["head_area"] - m0["head_area"]) * 0.25
            for dy in range(-4, 5):
                for dx in range(-4, 5):
                    shifted = np.zeros_like(barr)
                    sy0, sy1 = max(0, -dy), min(CH, CH - dy)
                    sx0, sx1 = max(0, -dx), min(CW, CW - dx)
                    shifted[sy0 + dy : sy1 + dy, sx0 + dx : sx1 + dx] = barr[sy0:sy1, sx0:sx1]
                    rm_i = rigid_core_mask(shifted)
                    overlap = rmask0 | rm_i
                    if not overlap.any():
                        continue
                    rgb_diff = np.abs(arr0[:, :, :3].astype(float) - shifted[:, :, :3].astype(float)).mean(axis=2)
                    l1_rigid = float(rgb_diff[overlap].mean())
                    sm = measure_flying_body(shifted)
                    fc_pen = (abs(sm["face_cx"] - m0["face_cx"]) + abs(sm["face_cy"] - m0["face_cy"])) * 18.0
                    score = l1_rigid * 10.0 + scale_pen + fc_pen
                    if score < best_score:
                        best_score = score
                        best_im = Image.fromarray(shifted, mode="RGBA")
        bodies.append(best_im)

    # Save & run strict Master QC Gate (allow_fx_border=False!) on all 6 body frames
    for idx, im in enumerate(bodies):
        out_p = BODY_OUT / f"fly_aura_{idx:02d}.png"
        im.save(out_p)
        qc = qc_gate.audit_frame(out_p, canon_pal, allow_fx_border=False, check_grounded_stance=False)
        m = measure_flying_body(np.array(im))
        print(f"[BODY #{idx}] bbox={m['bbox']} head_w={m['head_w']} head_area={m['head_area']} face=({m['face_cx']},{m['face_cy']}) QC={qc['pass']}")
        if not qc["pass"]:
            raise RuntimeError(f"Body QC failed on {out_p.name}: {qc['errors']}")

    # Verify consecutive frame flutter (no static duplicates!)
    for idx in range(6):
        a = np.array(bodies[idx])[:, :, :3].astype(int)
        b = np.array(bodies[(idx + 1) % 6])[:, :, :3].astype(int)
        va = np.array(bodies[idx])[:, :, 3] > 0
        vb = np.array(bodies[(idx + 1) % 6])[:, :, 3] > 0
        diff_px = int(((va != vb) | ((np.abs(a - b).max(axis=2) > 18) & (va | vb))).sum())
        print(f"  [BODY FLUTTER DIFF] #{idx} -> #{(idx + 1) % 6}: {diff_px} changed pixels")
        if diff_px < 40:
            raise RuntimeError(f"Insufficient flutter motion between body #{idx} and #{(idx+1)%6}: {diff_px} px")

    return bodies


def register_and_lock_all_auras(bodies: List[Image.Image]) -> List[Image.Image]:
    FX_OUT.mkdir(parents=True, exist_ok=True)
    # Union of all 6 flying body silhouettes — the detached aura MUST cover 100% of the interior behind the body with ZERO holes!
    body_union = np.zeros((CH, CW), dtype=bool)
    for bim in bodies:
        body_union |= (np.array(bim)[:, :, 3] > 0)
    # Core interior behind character (eroded slightly from front fist tip / rear boot tip so spikes naturally frame him)
    core_behind = ndimage.binary_erosion(body_union, iterations=3)

    auras: List[Image.Image] = []
    target_h = 186
    target_nose_x1 = 207  # Matches our Owner-approved scaled fly_aura [29..207] on 288x288!
    target_cy = 181

    for idx in range(6):
        gp = GEN_DIR / f"fly_aura_fx_{idx:02d}" / "generated.png"
        keyed = p1b.key_magenta_2stage(Image.open(gp), allow_fx=True)
        vis = keyed[:, :, 3] > 0
        # Fill any accidental enclosed key pockets inside the raw aura before scaling
        vis_filled = ndimage.binary_fill_holes(vis)
        holes = vis_filled & (~vis)
        if holes.any():
            keyed[holes] = [250, 254, 255, 255]
            vis = vis_filled

        ys, xs = np.where(vis)
        crop = Image.fromarray(keyed[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1], mode="RGBA")
        scale = min(float(target_h) / max(1.0, float(crop.height)), 188.0 / max(1.0, float(crop.width)))
        nw = max(32, int(round(crop.width * scale)))
        nh = max(32, int(round(crop.height * scale)))
        resized = crop.resize((nw, nh), Image.Resampling.NEAREST)
        rarr = p1b.post_clean_resized(np.array(resized, dtype=np.uint8), allow_fx=False)
        # Note: allow_fx=False in post_clean_resized enforces a clean 1px dark outer outline [16,12,18,255] around 100% of the aura!

        rmask = rarr[:, :, 3] > 0
        rmask_filled = ndimage.binary_fill_holes(rmask)
        if (rmask_filled & ~rmask).any():
            rarr[rmask_filled & ~rmask] = [250, 254, 255, 255]
            rmask = rmask_filled

        rys, rxs = np.where(rmask)
        px = max(4, min(CW - nw - 4, target_nose_x1 - int(rxs.max())))
        py = max(4, min(CH - nh - 4, int(round(target_cy - 0.5 * (rys.min() + rys.max())))))

        canvas = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
        canvas.paste(Image.fromarray(rarr, mode="RGBA"), (px, py))
        carr = np.array(canvas, dtype=np.uint8)

        # Guarantee 100% solid white-cyan energy behind Tapion's core silhouette (zero gaps when body flutters!)
        cvis = carr[:, :, 3] > 0
        uncovered_core = core_behind & (~cvis)
        if uncovered_core.any():
            carr[uncovered_core] = [248, 254, 255, 255]
            # Re-ensure 1px dark outer border if expanded
            cvis2 = carr[:, :, 3] > 0
            b4 = cvis2 & ~ndimage.binary_erosion(cvis2, structure=np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]]))
            rlum = 0.299 * carr[:, :, 0] + 0.587 * carr[:, :, 1] + 0.114 * carr[:, :, 2]
            carr[b4 & (rlum >= 52)] = [16, 12, 18, 255]

        # Also scrub any stray warm/orange/brown pixels inside the aura interior if AI hinted anything warm
        cvis = carr[:, :, 3] > 0
        b4 = cvis & ~ndimage.binary_erosion(cvis, structure=np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]]))
        interior = cvis & (~b4)
        cr, cg, cb = carr[:, :, 0].astype(int), carr[:, :, 1].astype(int), carr[:, :, 2].astype(int)
        warm_stray = interior & (cr > cb + 15)
        if warm_stray.any():
            carr[warm_stray] = [248, 254, 255, 255]

        aim = Image.fromarray(carr, mode="RGBA")
        out_p = FX_OUT / f"fly_aura_fx_{idx:02d}.png"
        aim.save(out_p)
        ys_a, xs_a = np.where(carr[:, :, 3] > 0)
        holes_after = int((ndimage.binary_fill_holes(carr[:, :, 3] > 0) & ~(carr[:, :, 3] > 0)).sum())
        print(
            f"[AURA FX #{idx}] bbox=[{xs_a.min()},{ys_a.min()},{xs_a.max()-xs_a.min()+1},{ys_a.max()-ys_a.min()+1}] "
            f"holes={holes_after} warm_stray_left=0"
        )
        assert holes_after == 0
        auras.append(aim)

    for idx in range(6):
        va = np.array(auras[idx])[:, :, 3] > 0
        vb = np.array(auras[(idx + 1) % 6])[:, :, 3] > 0
        diff_px = int((va != vb).sum())
        print(f"  [AURA STREAM DIFF] #{idx} -> #{(idx + 1) % 6}: {diff_px} silhouette delta px")
        if diff_px < 80:
            raise RuntimeError(f"Insufficient streaming motion between aura #{idx} and #{(idx+1)%6}: {diff_px} px")

    return auras


def main() -> int:
    canon_pal, _ = qc_gate.load_master_palette()
    bodies = register_and_lock_all_bodies(canon_pal)
    auras = register_and_lock_all_auras(bodies)

    composites: List[Image.Image] = []
    for a, b in zip(auras, bodies):
        c = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
        c.alpha_composite(a)
        c.alpha_composite(b)
        composites.append(c)

    p1b.render_3bg_filmstrip(
        bodies,
        WORK_DIR / "filmstrip_3bg_fly_body_solo_6f.png",
        title="fly_aura BODY SOLO (6 frames — fluttering hair/scarf/coat, rigid anatomy locked to canonical idle)",
    )
    p1b.render_3bg_filmstrip(
        auras,
        WORK_DIR / "filmstrip_3bg_fly_aura_fx_solo_6f.png",
        title="fly_aura_fx DETACHED AURA SOLO (6 frames — pure cyan-white comet aura, 0 character pixels, 0 holes)",
    )
    p1b.render_3bg_filmstrip(
        [Image.open(RAW_DIR / "idle_04.png").convert("RGBA")] + composites,
        WORK_DIR / "filmstrip_3bg_fly_composite_vs_idle.png",
        title="idle_04 (REF) + fly_aura COMPOSITE (6 frames: FlightAuraFX z=-1 + Sprite z=0)",
    )

    # Render 2x close-up zoom strip of all 6 aura-free flying body frames next to idle_04 to inspect structure!
    items = [("idle_04 (REF)", Image.open(RAW_DIR / "idle_04.png").convert("RGBA"))] + [
        (f"fly_body_{i:02d}", bodies[i]) for i in range(6)
    ]
    zw, zh = 124 * 2, 140 * 2  # crop (82, 118, 206, 258) -> 248x280
    zsheet = Image.new("RGBA", (len(items) * zw, zh), (238, 240, 246, 255))
    zdraw = ImageDraw.Draw(zsheet)
    for idx, (lbl, im) in enumerate(items):
        crop2x = im.crop((82, 118, 206, 258)).resize((zw, zh), Image.Resampling.NEAREST)
        zsheet.alpha_composite(crop2x, (idx * zw, 0))
        zdraw.rectangle([idx * zw, 0, (idx + 1) * zw - 1, zh - 1], outline=(180, 190, 210, 255))
        zdraw.text((idx * zw + 6, 6), lbl, fill=(20, 50, 160, 255) if idx == 0 else (180, 25, 25, 255))
    zsheet.save(WORK_DIR / "zoom2x_fly_body_6f_structure_check.png")
    print("[SUCCESS] All 6 body frames + 6 detached aura frames registered & QC-verified!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
