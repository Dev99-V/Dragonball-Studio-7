#!/usr/bin/env python3
"""
DR7-Studio — Tapion Whole-Pose Anatomical Fixes (`polish_v2`):
Fixes 3 specific combat pose anatomical defects reported by Owner:
  1. `atk2_04` (`attack_2 #4`): Torso rotated slightly left/back-3/4 while head twisted far right ->
     Regenerate whole pose matching `atk2_03`'s coherent back-3/4 head-to-body alignment + `tapion/tấn công 2.png` #5!
  2. `atk5_01` (`attack_5 #1`, also synced to `atk10_03`): Right arm broken at shoulder pauldron & missing hand ->
     Regenerate whole pose matching `tapion/tấn công 5.png` #2 with clean right shoulder -> right arm -> gloved hand gripping sword hilt + empty red scabbard cleanly behind back (`-X` mouth -> `+X` tip)!
  3. `atk8_04` (`attack_8 #4`): Broken arm/torso/neck/head connection ->
     Regenerate whole pose matching `atk8_03`'s crisp anatomy + `tapion/Tấn công 8.png` #5 airborne follow-through!
"""
from __future__ import annotations

import concurrent.futures
import pathlib
import shutil
import subprocess
import sys
from typing import Tuple

import numpy as np
from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "pipeline"))
import build_tapion_phase1_bundle as p1b  # noqa: E402
import qc_tapion_master_gate as qc_gate  # noqa: E402

ROUTE_MEDIA = ROOT / ".agent" / "skills" / "generate2dmedia" / "scripts" / "route_media.py"
RAW_DIR = ROOT / "review" / "tapion_demo" / "source" / "raw_frames"
TAP_DIR = ROOT / "tapion"
OUT_DIR = ROOT / "work" / "characters" / "tapion" / "polish_v2"
REFS_DIR = OUT_DIR / "refs_attacks"
PROMPTS_DIR = OUT_DIR / "prompts_attacks"
GEN_DIR = OUT_DIR / "gen_attacks"
REG_DIR = OUT_DIR / "registered_288"
QA_DIR = OUT_DIR / "qa"

CW, CH = 288, 288


def make_1024_ref_from_rgba(src_im: Image.Image, out_path: pathlib.Path, pad_box: int = 760) -> None:
    arr = np.array(src_im.convert("RGBA"))
    vis = arr[:, :, 3] > 0
    ys, xs = np.where(vis)
    crop = Image.fromarray(arr[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1], mode="RGBA")
    sc = min(pad_box / max(1, crop.width), pad_box / max(1, crop.height))
    up = crop.resize((max(1, int(round(crop.width * sc))), max(1, int(round(crop.height * sc)))), Image.Resampling.NEAREST)
    canvas = Image.new("RGBA", (1024, 1024), (255, 0, 255, 255))
    canvas.alpha_composite(up, ((1024 - up.width) // 2, (1024 - up.height) // 2))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out_path)


def crop_sheet_frame(sheet_path: pathlib.Path, frame_idx: int, total_frames: int, out_path: pathlib.Path) -> None:
    im = Image.open(sheet_path).convert("RGBA")
    arr = np.array(im)
    # Key dark background (27,21,35)
    r, g, b = arr[:, :, 0].astype(float), arr[:, :, 1].astype(float), arr[:, :, 2].astype(float)
    dist = np.sqrt((r - 27.0) ** 2 + (g - 21.0) ** 2 + (b - 35.0) ** 2)
    vis = dist > 18.0
    # Split columns by x-valleys
    col_cnt = vis.sum(axis=0)
    from scipy import ndimage
    closed = ndimage.binary_closing(col_cnt > 0, structure=np.ones(4, dtype=bool))
    lbl, n = ndimage.label(closed)
    spans = []
    for cid in range(1, n + 1):
        xs = np.where((lbl == cid) & (col_cnt > 0))[0]
        if len(xs) > 0 and int(vis[:, xs.min():xs.max()+1].sum()) >= 30:
            spans.append((int(xs.min()), int(xs.max()) + 1))
    while len(spans) > total_frames:
        bi = min(range(len(spans) - 1), key=lambda i: spans[i + 1][0] - spans[i][1])
        spans[bi : bi + 2] = [(spans[bi][0], spans[bi + 1][1])]
    sx0, sx1 = spans[frame_idx]
    sub = arr[:, sx0:sx1].copy()
    sub[~vis[:, sx0:sx1]] = [0, 0, 0, 0]
    make_1024_ref_from_rgba(Image.fromarray(sub, "RGBA"), out_path)


PROMPT_ATK2_04 = """Create a crisp 2D Dragon Ball Z GBA/DS pixel-art sprite frame of the exact warrior character from Reference Image 1 (clean 1px dark outline, flat solid #FF00FF pure magenta background, NO shadow, NO blur, NO gradient background) in the EXACT sword-finisher follow-through pose shown in Reference Image 2:

CRITICAL HEAD & BODY ALIGNMENT FIX:
- The character is seen from a BACK-3/4 ANGLE with his torso rotated slightly toward the LEFT/away (exactly like Reference Image 1 and Reference Image 2 — his back orange coat skirt and dark waist sash face the camera, with his left leg planted left and right leg planted right).
- HIS HEAD MUST NATURALLY FOLLOW HIS TORSO ROTATION! His head/face turns slightly LEFT/away in the EXACT SAME coherent back-3/4 angle as Reference Image 1 and Reference Image 2 (seeing the back/side of his spiky vermilion-orange mohawk hair, pointed elf ear on the left with gold earring, and only a subtle side glance — NEVER twist his face/eyes toward the far right!).
- His right arm reaches straight UP holding the silver-bladed sword angled slightly up-left (with NO white crescent slash trail — the slash has finished, only the crisp steel sword blade remains raised vertically/slightly up-left, matching Reference Image 2).
- His left arm is tucked naturally near his left side/hip.
- Behind his back, his EMPTY CRIMSON-RED SCABBARD (no sword hilt inside!) runs diagonally from upper-left (-X behind right shoulder) down-right (+X toward left hip, tip with round white-silver cap peeking at lower-right).
- Exact same pixel-art proportions, colors (vermilion-orange hair, pale tan skin, blue scarf, golden-orange vest/coat, dark green pants/sleeves, gold-trimmed brown boots), and crisp 1px dark pixel outline as Reference Image 1. Centered cleanly on solid #FF00FF magenta."""

PROMPT_ATK5_01 = """Create a crisp 2D Dragon Ball Z GBA/DS pixel-art sprite frame of the exact warrior character from Reference Image 1 (clean 1px dark outline, flat solid #FF00FF pure magenta background, NO shadow, NO blur) executing the EXACT airborne downward-forward diagonal sword slash shown in Reference Image 2:

CRITICAL ANATOMY FIX FOR RIGHT ARM, SHOULDER & HAND:
- Pay extreme attention to anatomical structure of BOTH arms and shoulders:
  1. His RIGHT SHOULDER (capped by the golden-orange shoulder pauldron) connects smoothly and solidly into his dark-green sleeved RIGHT UPPER ARM -> RIGHT FOREARM (with gold wrist cuff) -> BROWN GLOVED RIGHT HAND FIRMLY GRIPPING THE SWORD HILT & CROSSGUARD! No missing hand, no broken shoulder joint, no detached stub!
  2. His LEFT ARM extends cleanly/naturally for balance behind/beside his torso with a complete brown-gloved fist (clearly separated from the scabbard).
  3. BEHIND HIS BACK ONLY (strictly distinct from both arms!), his EMPTY CRIMSON-RED SCABBARD (empty mouth with white-silver collar at upper-left -X behind his right shoulder, tapering diagonally behind his back to the lower-right +X — NEVER draw the scabbard as a green arm or white ball!).
- Pose matches Reference Image 2: dynamic airborne diving slash facing right (+X), knees bent mid-air, vermilion-orange spiky mohawk, determined fierce face looking right-down along his slash, holding the silver sword diagonally down-right with a crisp sweeping white-silver crescent sword slash arc curving downward-right and up on the right side!
- Exact same pixel-art style, palette, head size, and crisp 1px dark pixel outline as Reference Image 1. Centered cleanly on solid #FF00FF magenta."""

PROMPT_ATK8_04 = """Create a crisp 2D Dragon Ball Z GBA/DS pixel-art sprite frame of the exact warrior character from Reference Image 1 (clean 1px dark outline, flat solid #FF00FF pure magenta background, NO shadow, NO blur) in the EXACT airborne follow-through pose shown in Reference Image 2 (the final recovery frame right after Reference Image 1):

CRITICAL ANATOMY FIX FOR HEAD, NECK, TORSO & ARMS CONNECTION:
- Keep the EXACT clean, coherent upper-body anatomy of Reference Image 1 (same head size, clear neck wrapped in the royal-blue scarf, proper broad shoulders with golden-orange pauldrons, solid orange vest & blue chest tunic):
  1. HEAD & NECK: Crisp vermilion-orange spiky mohawk, tan face looking right (+X), pointed elf ear with gold triangle earring, sitting squarely and naturally atop his neck & royal-blue scarf (NOT shifted off the chest!).
  2. RIGHT ARM (extended back-left / upper-left -X): Connects smoothly from his golden-orange right shoulder pauldron -> dark-green sleeve -> gold cuff -> brown-gloved right hand firmly holding the silver sword extended diagonally up-left (-X), matching Reference Image 1 & Reference Image 2 cleanly (NEVER emerging out of his ear or chin!).
  3. LEFT ARM (across/front-right side): Connects cleanly from his left shoulder -> dark-green sleeve -> brown-gloved left fist bent naturally at chest/waist height for airborne balance (NO phantom stick or weird rod across chest!).
  4. EMPTY CRIMSON-RED SCABBARD worn cleanly behind his back (upper-left -X behind right shoulder diagonally down-right +X with silver tip cap peeking at lower-right hip).
  5. LEGS & FX: Mid-air tucked legs (right leg slightly higher, left leg extended lower, matching Reference Image 2), with scattered dissipating bright cyan-blue pixel energy sparks trailing in a gentle curve below-right (fading out from Reference Image 1's cyan arc).
- Exact same pixel-art style, proportions, palette, and crisp 1px dark outline as Reference Image 1. Centered cleanly on solid #FF00FF magenta."""


def run_job(fid: str, ref1: pathlib.Path, ref2: pathlib.Path, prompt: str) -> Tuple[str, int, str]:
    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    GEN_DIR.mkdir(parents=True, exist_ok=True)
    pf = PROMPTS_DIR / f"{fid}.txt"
    pf.write_text(prompt.strip() + "\n", encoding="utf-8")
    od = GEN_DIR / fid
    if od.exists():
        shutil.rmtree(od)
    cmd = [
        sys.executable, str(ROUTE_MEDIA), "image", "--route", "codex-cli",
        "--prompt-file", str(pf),
        "--reference", str(ref1),
        "--reference", str(ref2),
        "--size", "1024x1024",
        "--out-dir", str(od),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return fid, proc.returncode, (proc.stdout + "\n" + proc.stderr).strip()


def measure_head_area(arr: np.ndarray) -> tuple[int, int, float, float]:
    vis = arr[:, :, 3] > 0
    r, g, b = arr[:, :, 0].astype(int), arr[:, :, 1].astype(int), arr[:, :, 2].astype(int)
    # Exclude cyan/blue FX and white slash
    hair = vis & (r > 160) & (r > g + 35) & (b < 75)
    skin = vis & (r > 185) & (g > 125) & (b > 80) & (r > b + 38)
    head = hair | skin
    # Keep upper 55% of body bbox so crimson scabbard doesn't pollute hair
    ys_all, _ = np.where(vis & ~((r > 200) & (g > 200) & (b > 200)) & ~((b - r) > 35))
    if len(ys_all) > 0:
        y_cut = int(ys_all.min() + 0.52 * (ys_all.max() - ys_all.min()))
        head[y_cut:, :] = False
    hys, hxs = np.where(head)
    if len(hxs) == 0:
        return 0, 0, 144.0, 150.0
    return int(head.sum()), int(hxs.max() - hxs.min() + 1), float(hxs.mean()), float(hys.mean())


def register_matching_peer(gen_png: pathlib.Path, peer_288: pathlib.Path, fid: str, allow_fx: bool = True, align_y1: int = 247, align_head_to_peer: bool = False) -> Image.Image:
    peer_arr = np.array(Image.open(peer_288).convert("RGBA"))
    p_harea, p_hw, p_hcx, p_hcy = measure_head_area(peer_arr)

    keyed = p1b.key_magenta_2stage(Image.open(gen_png), allow_fx=allow_fx)
    vis = keyed[:, :, 3] > 0
    ys, xs = np.where(vis)
    crop_arr = keyed[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    crop_im = Image.fromarray(crop_arr, mode="RGBA")

    # Search best scale so head_area matches peer_288's head_area (1-pass Nearest!)
    g_harea, g_hw, _, _ = measure_head_area(crop_arr)
    est_s = np.sqrt(max(1.0, float(p_harea)) / max(1.0, float(g_harea)))
    best_s = est_s
    best_err = 1e9
    for mult in np.linspace(0.86, 1.14, 29):
        s = est_s * mult
        nw = max(16, int(round(crop_im.width * s)))
        nh = max(16, int(round(crop_im.height * s)))
        if nw > 274 or nh > 270:
            continue
        test_arr = np.array(crop_im.resize((nw, nh), Image.Resampling.NEAREST))
        ha, hw, _, _ = measure_head_area(test_arr)
        err = abs(ha - p_harea) / max(1.0, float(p_harea)) + 0.5 * abs(hw - p_hw) / max(1.0, float(p_hw))
        if err < best_err:
            best_err = err
            best_s = s

    nw = max(16, min(274, int(round(crop_im.width * best_s))))
    nh = max(16, min(270, int(round(crop_im.height * best_s))))
    rarr = p1b.post_clean_resized(np.array(crop_im.resize((nw, nh), Image.Resampling.NEAREST), dtype=np.uint8), allow_fx=allow_fx)

    rmask = rarr[:, :, 3] > 0
    rys, rxs = np.where(rmask)
    ha, hw, hcx, hcy = measure_head_area(rarr)

    if align_head_to_peer:
        px = int(round(p_hcx - hcx))
        py = int(round(p_hcy - hcy))
    else:
        # Grounded or semi-airborne: align boots/body bottom to align_y1 and stance/core to peer's X!
        # Find body-only bottom (exclude cyan sparks)
        rr, rg, rb = rarr[:, :, 0].astype(int), rarr[:, :, 1].astype(int), rarr[:, :, 2].astype(int)
        body_m = rmask & ~((rb - rr) > 35) & ~((rr > 205) & (rg > 205) & (rb > 205))
        bys, bxs = np.where(body_m)
        ry1 = int(bys.max()) if len(bys) else int(rys.max())
        py = align_y1 - ry1
        px = int(round(p_hcx - hcx))

    px = max(2, min(CW - nw - 2, px))
    py = max(2, min(CH - nh - 2, py))
    canvas = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    canvas.paste(Image.fromarray(rarr, mode="RGBA"), (px, py))
    print(f"[{fid}] peer head=(area={p_harea}, w={p_hw}) -> got head=(area={ha}, w={hw}), sz={nw}x{nh}, paste=({px},{py})")
    return canvas


def main() -> int:
    # 1. Prepare clean 1024 refs
    make_1024_ref_from_rgba(Image.open(RAW_DIR / "atk2_03.png"), REFS_DIR / "ref1_atk2_03.png")
    crop_sheet_frame(TAP_DIR / "tấn công 2.png", 4, 5, REFS_DIR / "ref2_atk2_04_src.png")

    make_1024_ref_from_rgba(Image.open(RAW_DIR / "atk5_00.png"), REFS_DIR / "ref1_atk5_00.png")
    crop_sheet_frame(TAP_DIR / "tấn công 5.png", 1, 3, REFS_DIR / "ref2_atk5_01_src.png")

    make_1024_ref_from_rgba(Image.open(RAW_DIR / "atk8_03.png"), REFS_DIR / "ref1_atk8_03.png")
    crop_sheet_frame(TAP_DIR / "Tấn công 8.png", 4, 5, REFS_DIR / "ref2_atk8_04_src.png")

    jobs = [
        ("atk2_04", REFS_DIR / "ref1_atk2_03.png", REFS_DIR / "ref2_atk2_04_src.png", PROMPT_ATK2_04),
        ("atk5_01", REFS_DIR / "ref1_atk5_00.png", REFS_DIR / "ref2_atk5_01_src.png", PROMPT_ATK5_01),
        ("atk8_04", REFS_DIR / "ref1_atk8_03.png", REFS_DIR / "ref2_atk8_04_src.png", PROMPT_ATK8_04),
    ]
    print(f"Launching {len(jobs)} parallel Codex CLI whole-pose regenerations...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        futs = [ex.submit(run_job, *j) for j in jobs]
        for f in concurrent.futures.as_completed(futs):
            fid, rc, out = f.result()
            print(f"[GEN {fid}] rc={rc} | {out.splitlines()[-1] if out else ''}")
            if rc != 0:
                raise RuntimeError(f"Generation failed for {fid}: {out}")

    # 2. Register 1-pass Nearest matching peer head & stance
    REG_DIR.mkdir(parents=True, exist_ok=True)
    QA_DIR.mkdir(parents=True, exist_ok=True)

    im_a2 = register_matching_peer(GEN_DIR / "atk2_04" / "generated.png", RAW_DIR / "atk2_03.png", "atk2_04", allow_fx=True, align_y1=247, align_head_to_peer=False)
    im_a2.save(REG_DIR / "atk2_04.png")

    im_a5 = register_matching_peer(GEN_DIR / "atk5_01" / "generated.png", RAW_DIR / "atk5_00.png", "atk5_01", allow_fx=True, align_y1=247, align_head_to_peer=False)
    im_a5.save(REG_DIR / "atk5_01.png")

    im_a8 = register_matching_peer(GEN_DIR / "atk8_04" / "generated.png", RAW_DIR / "atk8_03.png", "atk8_04", allow_fx=True, align_y1=230, align_head_to_peer=True)
    im_a8.save(REG_DIR / "atk8_04.png")

    # 3. QC Gate
    canon_pal, _ = qc_gate.load_master_palette()
    for fid in ("atk2_04", "atk5_01", "atk8_04"):
        res = qc_gate.audit_frame(REG_DIR / f"{fid}.png", canon_pal, allow_fx_border=True, check_grounded_stance=False)
        print(f"[QC {fid}] pass={res['pass']} pal={res['pal_median_dist']} errors={res['errors']}")

    # 4. Render 3x before/after + neighbor comparison board!
    pairs = [
        ("atk2_03 (PEER)", RAW_DIR / "atk2_03.png", (76, 98, 224, 254)),
        ("atk2_04 BEFORE", RAW_DIR / "atk2_04.png", (76, 98, 224, 254)),
        ("atk2_04 AFTER", REG_DIR / "atk2_04.png", (76, 98, 224, 254)),
        ("atk5_00 (PEER)", RAW_DIR / "atk5_00.png", (76, 114, 224, 254)),
        ("atk5_01 BEFORE", RAW_DIR / "atk5_01.png", (76, 114, 224, 254)),
        ("atk5_01 AFTER", REG_DIR / "atk5_01.png", (76, 114, 224, 254)),
        ("atk8_03 (PEER)", RAW_DIR / "atk8_03.png", (46, 76, 240, 240)),
        ("atk8_04 BEFORE", RAW_DIR / "atk8_04.png", (46, 76, 240, 240)),
        ("atk8_04 AFTER", REG_DIR / "atk8_04.png", (46, 76, 240, 240)),
    ]
    cw, ch = 340, 340
    cols = 3
    rows = 3
    bd = Image.new("RGBA", (cols * cw, rows * (ch + 24)), (22, 26, 34, 255))
    dr = ImageDraw.Draw(bd)
    yy, xx = np.indices((ch, cw))
    chk = ((xx // 12) + (yy // 12)) % 2 == 0
    for idx, (lbl, p, box) in enumerate(pairs):
        r, c = divmod(idx, cols)
        x0, y0 = c * cw, r * (ch + 24)
        bg_a = np.zeros((ch, cw, 4), dtype=np.uint8)
        bg_a[chk] = [62, 68, 82, 255]
        bg_a[~chk] = [46, 50, 62, 255]
        bg = Image.fromarray(bg_a, "RGBA")
        im = Image.open(p).convert("RGBA").crop(box)
        sc = min((cw - 8) / im.width, (ch - 8) / im.height)
        rim = im.resize((int(im.width * sc), int(im.height * sc)), Image.Resampling.NEAREST)
        bg.alpha_composite(rim, ((cw - rim.width) // 2, (ch - rim.height) // 2))
        bd.paste(bg, (x0, y0 + 24))
        dr.rectangle([x0, y0, x0 + cw - 1, y0 + ch + 23], outline=(90, 100, 120, 255))
        dr.text((x0 + 6, y0 + 5), lbl, fill=(140, 255, 180, 255) if "AFTER" in lbl else (255, 220, 120, 255))
    out_qa = QA_DIR / "qa_attacks_v2_before_after.png"
    bd.save(out_qa)
    print("Saved QA board:", out_qa)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
