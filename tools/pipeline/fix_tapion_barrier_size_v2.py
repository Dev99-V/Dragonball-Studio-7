#!/usr/bin/env python3
"""
DR7-Studio — Tapion `barrier_cast` Frame #0 & #2 Size Uniformity Fix (`polish_v2`):
Owner request: "barrier_cast kích thước frame 0 và 2 lệch với các frame còn lại."
Measured evidence:
  - `barrier_01, 03, 04, 05, 06, 07, 08` all share uniform body scale (`head_w=53..55`, `skin_px=234..238`, `body_h=108..114`, `body_px≈3272..3464`).
  - `barrier_00` (raw copy of `idle_03` at `H=127`, `skin_px=367`, `body_px=4561`) and `barrier_02` (`skin_px=356`, `body_px=3784`) were oversized!
Fix:
  - Re-register `barrier_00` (1-pass Nearest directly from `sword_fix_w1/generated/idle_03/generated.png`) and
    `barrier_02` (1-pass Nearest directly from `sword_fix_w2/generated/barrier_02/generated.png`)
    to match the EXACT body/head scale of `barrier_03` & `barrier_04..08` (`skin_px≈236`, `head_w≈53..55`, `body_px≈3350..3480`),
    with smooth levitation Y progression (`#0 y1=242 -> #1 y1=234 -> #2 y1=228 -> #3 y1=228`) and aligned horizontal center X!
"""
from __future__ import annotations

import pathlib
import sys
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "pipeline"))
import build_tapion_phase1_bundle as p1b  # noqa: E402
import qc_tapion_master_gate as qc_gate  # noqa: E402

RAW_DIR = ROOT / "review" / "tapion_demo" / "source" / "raw_frames"
W1_GEN = ROOT / "work" / "characters" / "tapion" / "sword_fix_w1" / "generated"
W2_GEN = ROOT / "work" / "characters" / "tapion" / "sword_fix_w2" / "generated"
OUT_DIR = ROOT / "work" / "characters" / "tapion" / "polish_v2"
REG_DIR = OUT_DIR / "registered_288"
QA_DIR = OUT_DIR / "qa"

CW, CH = 288, 288


def measure_barrier_head_body(arr: np.ndarray) -> dict:
    vis = arr[:, :, 3] > 0
    r, g, b = arr[:, :, 0].astype(int), arr[:, :, 1].astype(int), arr[:, :, 2].astype(int)
    dome = vis & (((b - r) > 25) & (b > 100) | ((r > 195) & (g > 215) & (b > 225)))
    body = vis & ~dome
    lbl, n = ndimage.label(body, structure=np.ones((3, 3)))
    if n > 0:
        sizes = ndimage.sum(body, lbl, range(1, n + 1))
        body = lbl == (int(np.argmax(sizes)) + 1)
    bys, bxs = np.where(body)
    hair = body & (r > 160) & (r > g + 35) & (b < 70)
    skin = body & (r > 190) & (g > 130) & (b > 85) & (r > b + 40) & (r - g < 85)
    head = hair | skin
    # Upper 52% of body so crimson scabbard doesn't pollute hair
    if len(bys) > 0:
        head[int(bys.min() + 0.52 * (bys.max() - bys.min())) :, :] = False
    hys, hxs = np.where(head)
    return {
        "body_w": int(bxs.max() - bxs.min() + 1) if len(bxs) else 0,
        "body_h": int(bys.max() - bys.min() + 1) if len(bys) else 0,
        "y0": int(bys.min()) if len(bys) else 0,
        "y1": int(bys.max()) if len(bys) else 0,
        "body_px": int(body.sum()),
        "head_w": int(hxs.max() - hxs.min() + 1) if len(hxs) else 0,
        "head_px": int(head.sum()),
        "skin_px": int((skin & head).sum()),
        "cx": float(bxs.mean()) if len(bxs) else 144.0,
        "hcx": float(hxs.mean()) if len(hxs) else 144.0,
    }


def register_to_barrier_ref(gen_png: pathlib.Path, ref_m: dict, y1_target: int, target_h: int, fid: str) -> Image.Image:
    keyed = p1b.key_magenta_2stage(Image.open(gen_png), allow_fx=False)
    vis = keyed[:, :, 3] > 0
    ys, xs = np.where(vis)
    crop_arr = keyed[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    crop_im = Image.fromarray(crop_arr, mode="RGBA")

    # Search exact 1-pass Nearest scale matching ref_m's head_px, skin_px, and body_px!
    nom_s = float(target_h) / max(1.0, float(crop_im.height))
    best_s = nom_s
    best_err = 1e9
    for mult in np.linspace(0.84, 1.12, 57):
        s = nom_s * mult
        nw = max(16, int(round(crop_im.width * s)))
        nh = max(16, int(round(crop_im.height * s)))
        test_arr = np.array(crop_im.resize((nw, nh), Image.Resampling.NEAREST))
        m = measure_barrier_head_body(test_arr)
        err = (
            1.4 * abs(m["head_px"] - ref_m["head_px"]) / max(1.0, ref_m["head_px"])
            + 1.0 * abs(m["skin_px"] - ref_m["skin_px"]) / max(1.0, ref_m["skin_px"])
            + 0.8 * abs(m["body_px"] - ref_m["body_px"]) / max(1.0, ref_m["body_px"])
            + 0.6 * abs(m["head_w"] - ref_m["head_w"]) / max(1.0, ref_m["head_w"])
        )
        if err < best_err:
            best_err = err
            best_s = s

    nw = max(16, int(round(crop_im.width * best_s)))
    nh = max(16, int(round(crop_im.height * best_s)))
    rarr = p1b.post_clean_resized(np.array(crop_im.resize((nw, nh), Image.Resampling.NEAREST), dtype=np.uint8), allow_fx=False)
    m_got = measure_barrier_head_body(rarr)

    rmask = rarr[:, :, 3] > 0
    rys, rxs = np.where(rmask)
    ry1 = int(rys.max())
    # Align horizontal center smoothly to ref_m["hcx"] (around 142..144)
    px = max(2, min(CW - nw - 2, int(round(ref_m["hcx"] - m_got["hcx"]))))
    py = max(2, min(CH - nh - 2, y1_target - ry1))
    canvas = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    canvas.paste(Image.fromarray(rarr, mode="RGBA"), (px, py))
    final_m = measure_barrier_head_body(np.array(canvas))
    print(f"[{fid}] scale={best_s:.4f} -> {final_m}")
    return canvas


def main() -> int:
    REG_DIR.mkdir(parents=True, exist_ok=True)
    QA_DIR.mkdir(parents=True, exist_ok=True)

    # Measure reference frames barrier_01, barrier_03, barrier_04
    m1 = measure_barrier_head_body(np.array(Image.open(RAW_DIR / "barrier_01.png").convert("RGBA")))
    m3 = measure_barrier_head_body(np.array(Image.open(RAW_DIR / "barrier_03.png").convert("RGBA")))
    m4 = measure_barrier_head_body(np.array(Image.open(RAW_DIR / "barrier_04.png").convert("RGBA")))
    print("REF barrier_01:", m1)
    print("REF barrier_03:", m3)
    print("REF barrier_04:", m4)

    # Target canonical barrier body metrics = average of barrier_03 and barrier_04
    ref_target = {
        "head_px": 0.5 * (m3["head_px"] + m4["head_px"]),
        "skin_px": 0.5 * (m3["skin_px"] + m4["skin_px"]),
        "body_px": 0.5 * (m3["body_px"] + m4["body_px"]),
        "head_w": 0.5 * (m3["head_w"] + m4["head_w"]),
        "hcx": 0.5 * (m1["hcx"] + m3["hcx"]),
    }

    # Re-register barrier_00 (standing start pose from idle_03 1024px) & barrier_02 (airborne windup from barrier_02 1024px)
    im0 = register_to_barrier_ref(W1_GEN / "idle_03" / "generated.png", ref_target, y1_target=242, target_h=112, fid="barrier_00")
    im0.save(REG_DIR / "barrier_00.png")

    im2 = register_to_barrier_ref(W2_GEN / "barrier_02" / "generated.png", ref_target, y1_target=228, target_h=106, fid="barrier_02")
    im2.save(REG_DIR / "barrier_02.png")

    # QC check
    canon_pal, _ = qc_gate.load_master_palette()
    for fid in ("barrier_00", "barrier_02"):
        res = qc_gate.audit_frame(REG_DIR / f"{fid}.png", canon_pal, allow_fx_border=False, check_grounded_stance=False)
        print(f"[QC {fid}] pass={res['pass']} pal={res['pal_median_dist']} bdark={res['border_dark_frac']} errors={res['errors']}")

    # Render full 9-frame barrier_cast comparison (BEFORE row vs AFTER row)
    box = (60, 68, 228, 260)
    sc = 1
    cw, ch = (box[2] - box[0]) * sc, (box[3] - box[1]) * sc
    board = Image.new("RGBA", (9 * cw, 2 * (ch + 24)), (22, 26, 34, 255))
    dr = ImageDraw.Draw(board)
    yy, xx = np.indices((ch, cw))
    chk = ((xx // 10) + (yy // 10)) % 2 == 0
    for row_i, label_prefix in enumerate(["BEFORE", "AFTER"]):
        for i in range(9):
            p = (REG_DIR / f"barrier_{i:02d}.png") if (row_i == 1 and i in (0, 2)) else (RAW_DIR / f"barrier_{i:02d}.png")
            im = Image.open(p).convert("RGBA").crop(box)
            bg_a = np.zeros((ch, cw, 4), dtype=np.uint8)
            bg_a[chk] = [56, 62, 76, 255]
            bg_a[~chk] = [42, 46, 58, 255]
            bg = Image.fromarray(bg_a, "RGBA")
            bg.alpha_composite(im)
            x0, y0 = i * cw, row_i * (ch + 24)
            board.paste(bg, (x0, y0 + 24))
            dr.rectangle([x0, y0, x0 + cw - 1, y0 + ch + 23], outline=(90, 100, 120, 255))
            # Draw horizontal guide lines at y=115 and y=234 (relative to crop y0=68 -> 47 and 166)
            dr.line([(x0, y0 + 24 + 47), (x0 + cw - 1, y0 + 24 + 47)], fill=(255, 100, 100, 120))
            dr.line([(x0, y0 + 24 + 166), (x0 + cw - 1, y0 + 24 + 166)], fill=(100, 255, 160, 120))
            col = (140, 255, 180, 255) if (row_i == 1 and i in (0, 2)) else (255, 220, 120, 255)
            dr.text((x0 + 4, y0 + 5), f"{label_prefix} #{i}", fill=col)
    out_qa = QA_DIR / "qa_barrier_cast_size_9f.png"
    board.save(out_qa)
    print("Saved QA:", out_qa)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
