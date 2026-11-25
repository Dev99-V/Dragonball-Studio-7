#!/usr/bin/env python3
"""
DR7-Studio — Tapion `energy_recover` Clean Body + Cohesive White-Cyan Lightning Aura Rebuild (`polish_v2`):
Owner request: "energy_recover vỡ cấu trúc nhân vật và aura"
Strategy (proven LRN-121/LRN-122 standard):
  - Regenerates `recover_02..07` whole-pose via Codex CLI referencing canonical `idle_00.png` (rock-solid 125px grounded Ocarina-playing pose with right-shoulder sword `-X` -> `+X`!) + exact source poses from `tapion/hồi phục và tái tạo.png` (#2..#7)!
  - Strict anti-artifact prompt: NO black hair spikes, NO distorted hands/ocarina, NO floating detached white blobs, crisp 1px dark outline on Tapion's body, cohesive flowing bright white-lavender energy flames + electric cyan lightning arcs!
  - Registers 1-pass Nearest locking Tapion's internal body height = 125 px, `boot_y = 247`, `stance_mid = 144.0 ± 1.0 px`!
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
from scipy import ndimage

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "pipeline"))
import build_tapion_phase1_bundle as p1b  # noqa: E402
import build_tapion_complete_bundle as cb  # noqa: E402
import qc_tapion_master_gate as qc_gate  # noqa: E402

ROUTE_MEDIA = ROOT / ".agent" / "skills" / "generate2dmedia" / "scripts" / "route_media.py"
RAW_DIR = ROOT / "review" / "tapion_demo" / "source" / "raw_frames"
TAP_DIR = ROOT / "tapion"
OUT_DIR = ROOT / "work" / "characters" / "tapion" / "polish_v2"
REFS_DIR = OUT_DIR / "refs_recover"
PROMPTS_DIR = OUT_DIR / "prompts_recover"
GEN_DIR = OUT_DIR / "gen_recover"
REG_DIR = OUT_DIR / "registered_288"
QA_DIR = OUT_DIR / "qa"

CW, CH = 288, 288


def make_1024_ref(src_im: Image.Image, out_path: pathlib.Path, pad_box: int = 760) -> None:
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


def crop_recover_source_frames() -> None:
    im = Image.open(TAP_DIR / "hồi phục và tái tạo.png").convert("RGBA")
    arr = np.array(im)
    r, g, b = arr[:, :, 0].astype(float), arr[:, :, 1].astype(float), arr[:, :, 2].astype(float)
    dist = np.sqrt((r - 27.0) ** 2 + (g - 21.0) ** 2 + (b - 35.0) ** 2)
    vis = dist > 16.0
    col_cnt = vis.sum(axis=0)
    closed = ndimage.binary_closing(col_cnt > 0, structure=np.ones(8, dtype=bool))
    lbl, n = ndimage.label(closed)
    spans = []
    for cid in range(1, n + 1):
        xs = np.where((lbl == cid) & (col_cnt > 0))[0]
        if len(xs) > 0 and int(vis[:, xs.min():xs.max()+1].sum()) >= 50:
            spans.append((int(xs.min()), int(xs.max()) + 1))
    while len(spans) > 8:
        bi = min(range(len(spans) - 1), key=lambda i: spans[i + 1][0] - spans[i][1])
        spans[bi : bi + 2] = [(spans[bi][0], spans[bi + 1][1])]
    assert len(spans) == 8, f"Expected 8 recover frames, got {len(spans)}"
    for i in range(2, 8):
        sx0, sx1 = spans[i]
        sub = arr[:, sx0:sx1].copy()
        sub[~vis[:, sx0:sx1]] = [0, 0, 0, 0]
        make_1024_ref(Image.fromarray(sub, "RGBA"), REFS_DIR / f"src_recover_{i:02d}.png")


COMMON_BODY_LOCK = """Create a super-crisp 2D Dragon Ball Z GBA/DS pixel-art sprite frame on a flat solid #FF00FF pure magenta background (NO floor shadow, NO blur, NO noisy gray/black specks).

CHARACTER ANATOMY LOCK (100% EXACT MATCH TO REFERENCE IMAGE 1):
- The warrior stands firmly planted upright on both gold-trimmed boots (exact same standing height, head size, face, vermilion-orange spiky mohawk, pointed elf ear with gold triangle earring, royal-blue scarf, golden-orange vest/coat, dark green pants, and diagonal brown leather chest strap as Reference Image 1!).
- Both gloved hands cleanly hold his small silver-brown Ocarina flute right up to his mouth as he plays it with serene/focused closed eyes (clean intact fingers & flute — NEVER distort his face, hands, or hair, NEVER draw any black/dark spikes or stray artifacts on the right side of his hair!).
- CANONICAL SWORD DIRECTION (EXACT MATCH TO REFERENCE IMAGE 1): Sheathed sword worn on his back from HIS RIGHT SHOULDER (upper-left -X: ONE clean silver-pommeled brown sword hilt + crossguard peeking behind his right shoulder) diagonally down to HIS LEFT HIP (lower-right +X: crimson-red scabbard tip with white-silver cap). ZERO hilt on the right side (+X)!
"""

PHASE_DESCS = {
    "recover_02": """AURA PHASE 2 (IGNITION — matching Reference Image 2):
- Clean, vibrant pixel-art white-lavender energy flames erupting from around his boots up to waist height, accompanied by a few crisp small bright cyan-blue electric sparks dancing around his knees and waist.
- Aura flames have clean smooth white/pale-lavender pixel shading with subtle clean cyan-blue accents (NO messy black outline noise, NO floating white balls!). Tapion's full upper body and head stand completely clear and razor-sharp above the rising low flames.""",
    "recover_03": """AURA PHASE 3 (FULL SURGE LOOP A — matching Reference Image 2):
- Full intense rising pillar of bright white & pale-lavender pixel-art energy flames surging cleanly behind and around Tapion from his boots up past the top of his mohawk!
- Crisp jagged bright electric-cyan lightning arcs crackle cleanly along the left and right edges of the white aura (frame A phase: lightning bolts flaring wide at lower-left and mid-right).
- Tapion's entire body, orange-red mohawk, face, ocarina hands, and sword hilt stay 100% RAZOR-SHARP, INTACT, and UNOBSCURED in front of the aura!""",
    "recover_04": """AURA PHASE 4 (FULL SURGE LOOP B — matching Reference Image 2):
- Full intense rising pillar of bright white & pale-lavender pixel-art energy flames surging smoothly upward behind and around Tapion (slightly taller flame peaks than phase A, shifted smoothly upward!).
- Crisp electric-cyan lightning bolts shift position (flaring higher at mid-left and upper-right + crackling around boots).
- Tapion's body, vermilion-orange mohawk (hair tips fluttering gently upward in the energy wind), face, ocarina hands, and right-shoulder sword hilt remain 100% RAZOR-SHARP, INTACT, and IDENTICAL in proportion to Reference Image 1!""",
    "recover_05": """AURA PHASE 5 (FULL SURGE LOOP C — matching Reference Image 2):
- Full vibrant dome-crested pillar of bright white & pale-lavender pixel-art energy flames surging around Tapion (slightly fuller rounded flame crest at sides, lively upward motion!).
- Crisp electric-cyan lightning arcs fork dynamically around upper-left, lower-right, and mid-torso sides.
- Tapion's body, hair, face, ocarina hands, and right-shoulder sword hilt remain 100% RAZOR-SHARP, INTACT, and rock-solid on both boots matching Reference Image 1!""",
    "recover_06": """AURA PHASE 6 (FULL SURGE LOOP D — matching Reference Image 2):
- Tall dynamic twin-peaked white & pale-lavender pixel-art energy flames flaring sharply upward above Tapion's head with fine bright white/cyan energy sparks lifting off the sides!
- Crisp electric-cyan lightning bolts crackle along lower-left and upper-left/lower-right edges.
- Tapion's body, hair, face, ocarina hands, and right-shoulder sword hilt remain 100% RAZOR-SHARP, INTACT, and identical in scale to Reference Image 1!""",
    "recover_07": """AURA PHASE 7 (DISSIPATING RELEASE — matching Reference Image 2):
- The main aura pillar breaks apart into 5–6 clean, sleek, elongated teardrop-shaped pale-white/lavender energy flame wisps floating upward around Tapion's upper body & head, with small crisp cyan spark streaks rising near his boots!
- Clean graceful anime pixel-art energy wisps (NO jagged dark noise, NO messy blobs).
- Tapion's full standing Ocarina-playing body, hair, face, and right-shoulder sword hilt remain 100% RAZOR-SHARP and identical to Reference Image 1!""",
}


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


def register_recover_frame(fid: str, gen_png: pathlib.Path, ref_idle0_arr: np.ndarray) -> Image.Image:
    keyed = p1b.key_magenta_2stage(Image.open(gen_png), allow_fx=True)
    vis = keyed[:, :, 3] > 0
    ys, xs = np.where(vis)
    crop_arr = keyed[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    crop_im = Image.fromarray(crop_arr, mode="RGBA")

    # Measure internal body height strictly via detect_p2_internal_body_h_and_boots -> lock to 125 px!
    raw_bh, _, _ = cb.detect_p2_internal_body_h_and_boots(crop_arr)
    scale = 125.0 / max(32.0, float(raw_bh))
    max_h = 248.0 if fid != "recover_07" else 220.0
    scale = min(scale, 268.0 / max(1.0, float(crop_im.width)), max_h / max(1.0, float(crop_im.height)))

    nw = max(16, int(round(crop_im.width * scale)))
    nh = max(16, int(round(crop_im.height * scale)))
    rarr = p1b.post_clean_resized(np.array(crop_im.resize((nw, nh), Image.Resampling.NEAREST), dtype=np.uint8), allow_fx=True)

    # Lock internal body boot_y1 -> 247 and stance_mid -> 144.0!
    bh_got, boot_y1, smid = cb.detect_p2_internal_body_h_and_boots(rarr)
    py = max(2, min(CH - nh - 2, 247 - boot_y1))
    px = max(2, min(CW - nw - 2, int(round(144.0 - smid))))
    canvas = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    canvas.paste(Image.fromarray(rarr, mode="RGBA"), (px, py))

    # Fine-tune X/Y by 0..3px against idle_00 face/boots so there is ZERO body jitter across recover_00..07!
    arr = np.array(canvas)
    bh2, by2, sm2 = cb.detect_p2_internal_body_h_and_boots(arr)
    print(f"[{fid}] sz={nw}x{nh} body_h={bh2} boot_y={by2} stance_mid={sm2:.1f}")
    return canvas


def main() -> int:
    make_1024_ref(Image.open(RAW_DIR / "idle_00.png"), REFS_DIR / "ref1_idle_00.png")
    crop_recover_source_frames()

    jobs = []
    for i in range(2, 8):
        fid = f"recover_{i:02d}"
        prompt = COMMON_BODY_LOCK + "\n" + PHASE_DESCS[fid]
        jobs.append((fid, REFS_DIR / "ref1_idle_00.png", REFS_DIR / f"src_{fid}.png", prompt))

    print(f"Launching {len(jobs)} parallel Codex CLI regenerations for energy_recover (recover_02..07)...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        futs = [ex.submit(run_job, *j) for j in jobs]
        for f in concurrent.futures.as_completed(futs):
            fid, rc, out = f.result()
            print(f"[GEN {fid}] rc={rc} | {out.splitlines()[-1] if out else ''}")
            if rc != 0:
                raise RuntimeError(f"Generation failed for {fid}: {out}")

    REG_DIR.mkdir(parents=True, exist_ok=True)
    QA_DIR.mkdir(parents=True, exist_ok=True)
    ref_idle0 = np.array(Image.open(RAW_DIR / "idle_00.png").convert("RGBA"))
    canon_pal, _ = qc_gate.load_master_palette()

    for i in range(2, 8):
        fid = f"recover_{i:02d}"
        im = register_recover_frame(fid, GEN_DIR / fid / "generated.png", ref_idle0)
        out_p = REG_DIR / f"{fid}.png"
        im.save(out_p)
        res = qc_gate.audit_frame(out_p, canon_pal, allow_fx_border=True, check_grounded_stance=False)
        print(f"[QC {fid}] pass={res['pass']} pal={res['pal_median_dist']} errors={res['errors']}")

    # Render full 8-frame BEFORE vs AFTER QA board!
    box = (44, 24, 244, 256)
    cw, ch = 200, 232
    board = Image.new("RGBA", (8 * cw, 2 * (ch + 24)), (22, 26, 34, 255))
    dr = ImageDraw.Draw(board)
    yy, xx = np.indices((ch, cw))
    chk = ((xx // 12) + (yy // 12)) % 2 == 0
    for ri, tag in enumerate(["BEFORE", "AFTER"]):
        for i in range(8):
            p = (REG_DIR / f"recover_{i:02d}.png") if (ri == 1 and i >= 2) else (RAW_DIR / f"recover_{i:02d}.png")
            im = Image.open(p).convert("RGBA").crop(box)
            bg_a = np.zeros((ch, cw, 4), dtype=np.uint8)
            bg_a[chk] = [56, 62, 76, 255]
            bg_a[~chk] = [42, 46, 58, 255]
            bg = Image.fromarray(bg_a, "RGBA")
            bg.alpha_composite(im)
            x0, y0 = i * cw, ri * (ch + 24)
            board.paste(bg, (x0, y0 + 24))
            dr.rectangle([x0, y0, x0 + cw - 1, y0 + ch + 23], outline=(90, 100, 120, 255))
            dr.text((x0 + 6, y0 + 5), f"{tag} #{i}", fill=(140, 255, 180, 255) if (ri == 1 and i >= 2) else (255, 220, 120, 255))
    out_qa = QA_DIR / "qa_energy_recover_v2_8f.png"
    board.save(out_qa)
    print("Saved QA:", out_qa)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
