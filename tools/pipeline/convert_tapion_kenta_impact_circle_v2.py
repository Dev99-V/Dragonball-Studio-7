#!/usr/bin/env python3
"""
DR7-Studio — Convert `kentaima_impact_fx` (`kenta_impact_00..05`) from flat-bottom half-dome
into a crisp 1px DBZ pixel-art FULL 360° CIRCULAR ENERGY EXPLOSION (`polish_v2`):
Owner request:
  "riêng kentaima_impact_fx chỉ có hoạt ảnh nữa cầu tròn anh cần em convert về chuẩn vùng nổ tròn
   để khi va chạm vào người 1 cách tự nhiên."
  (Plus sharpness upgrade matching all 9 FX clips!)

Generates all 6 phases (`kenta_impact_00..05`) via Codex CLI in parallel referencing `tapion/hit impact kentaima.png`
for the exact cyan-white-cobalt-black energy plasma color & 6-stage burst -> turbulent cloud -> dissipation sequence,
then keys magenta 2-stage + crisp pixel-art quantization + centers cleanly at `(144, 176)` on `288x288`!
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
import sharpen_tapion_9fx_v2 as fxsharp  # noqa: E402

ROUTE_MEDIA = ROOT / ".agent" / "skills" / "generate2dmedia" / "scripts" / "route_media.py"
P2_FX_RAW = ROOT / "work" / "characters" / "tapion" / "phase2" / "fx_slices"
OLD_FX_REG = ROOT / "review" / "tapion_demo" / "fx_source" / "raw_frames"
OUT_DIR = ROOT / "work" / "characters" / "tapion" / "polish_v2"
REFS_DIR = OUT_DIR / "refs_kenta_circle"
PROMPTS_DIR = OUT_DIR / "prompts_kenta_circle"
GEN_DIR = OUT_DIR / "gen_kenta_circle"
FX_REG_DIR = OUT_DIR / "fx_registered_288"
QA_DIR = OUT_DIR / "qa"

CW, CH = 288, 288

PAL_KENTA_IMPACT = np.array([
    [255, 255, 255],  # blinding white plasma core
    [214, 252, 255],  # ice white-cyan
    [118, 238, 255],  # bright electric cyan
    [36, 202, 255],   # vivid cyan-blue
    [18, 146, 242],   # azure plasma
    [14, 88, 204],    # deep royal blue
    [12, 46, 128],    # dark cobalt smoke
    [14, 24, 58],     # dark navy shadow / crisp rim
    [12, 16, 28],     # crisp pixel outline / dark soot
], dtype=np.float32)

COMMON_KENTA_PROMPT = """Create a RAZOR-SHARP 2D Dragon Ball Z GBA/DS pixel-art hit-impact explosion sprite frame on a flat solid #FF00FF pure magenta background (NO floor line, NO ground cutoff, NO blur, NO gradient halo, NO character, NO text!).

CRITICAL SHAPE REQUIREMENT — FULL 360-DEGREE CIRCULAR MID-AIR EXPLOSION:
- Reference Image 1 shows the original cyan-blue energy impact style, BUT Reference Image 1 was cut flat at the bottom as a half-dome.
- You MUST convert it into a COMPLETE, SYMMETRICALLY BALANCED FULL 360-DEGREE ROUND CIRCULAR ENERGY EXPLOSION (billowing outward equally in ALL directions: top, bottom, left, right — ZERO flat horizontal bottom edge!) so it explodes naturally in mid-air or on a character's body on impact!
- Crisp classic DBZ pixel art with clean stepped cel-color clusters (pure white core -> bright electric cyan -> vivid azure blue -> deep cobalt -> crisp dark navy/black pixel rim), sharp 1px edges, ZERO blurry glow!"""

PHASE_PROMPTS = {
    "kenta_impact_00": (
        104,
        "STAGE 1 of 6 (INITIAL FLASH): Compact, intense round circular burst of blazing white plasma core surrounded by crisp bright electric-cyan spiky billow puffs expanding equally in all 360 degrees (small dense energetic sphere, ~38% of full blast size).",
    ),
    "kenta_impact_01": (
        156,
        "STAGE 2 of 6 (RAPID EXPANSION): Medium-large circular cyan-blue plasma explosion expanding uniformly in 360 degrees: huge blazing pure-white central flash core surrounded by turbulent bright cyan and vivid azure billowing energy clouds with jagged electric edges radiating all around.",
    ),
    "kenta_impact_02": (
        196,
        "STAGE 3 of 6 (PEAK DETONATION): Full maximum-size round 360-degree circular billowing energy explosion! Bright white inner burst pockets breaking through thick churning electric-cyan and vivid blue cloud puffs around the entire circle, crisp dark cobalt-navy pixel rim around the billowing outer contour.",
    ),
    "kenta_impact_03": (
        200,
        "STAGE 4 of 6 (CHURNING PLASMA CLOUD): Full round 360-degree circular billowing cyan-blue energy blast cloud cooling slightly from peak: bright cyan glowing core pockets framed by swirling vivid blue and dark cobalt-navy shadowed smoke billows uniformly around the full circle.",
    ),
    "kenta_impact_04": (
        196,
        "STAGE 5 of 6 (BREAKING SMOKE RING): Full circular 360-degree dissipating dark-blue & electric-cyan turbulent pixel smoke explosion breaking apart into dramatic swirling clumps with bright cyan crevices glowing inside dark cobalt/navy pixel smoke clouds, small gaps starting to open inside.",
    ),
    "kenta_impact_05": (
        188,
        "STAGE 6 of 6 (FINAL DISSIPATION): Circular 360-degree ring of wispy fading dark-navy, cobalt-blue, and faint cyan pixel smoke puffs & tiny glowing embers dispersing outward around the full circle with open transparent gaps in the center and between wisps.",
    ),
}


def make_ref_1024(src_p: pathlib.Path, out_p: pathlib.Path) -> None:
    im = Image.open(src_p).convert("RGBA")
    arr = np.array(im)
    vis = arr[:, :, 3] > 0
    ys, xs = np.where(vis)
    crop = Image.fromarray(arr[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1], "RGBA")
    sc = min(700.0 / max(1, crop.width), 700.0 / max(1, crop.height))
    up = crop.resize((max(1, int(round(crop.width * sc))), max(1, int(round(crop.height * sc)))), Image.Resampling.NEAREST)
    canvas = Image.new("RGBA", (1024, 1024), (255, 0, 255, 255))
    canvas.alpha_composite(up, ((1024 - up.width) // 2, (1024 - up.height) // 2))
    out_p.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out_p)


def run_job(fid: str, ref_p: pathlib.Path, prompt: str) -> Tuple[str, int, str]:
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
        "--reference", str(ref_p),
        "--size", "1024x1024",
        "--out-dir", str(od),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return fid, proc.returncode, (proc.stdout + "\n" + proc.stderr).strip()


def register_circular_explosion(fid: str, gen_png: pathlib.Path, target_diam: int) -> Image.Image:
    keyed = p1b.key_magenta_2stage(Image.open(gen_png), allow_fx=True)
    vis = keyed[:, :, 3] > 0
    ys, xs = np.where(vis)
    crop = Image.fromarray(keyed[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1], mode="RGBA")
    sc = float(target_diam) / max(1.0, float(max(crop.width, crop.height)))
    nw = max(16, min(256, int(round(crop.width * sc))))
    nh = max(16, min(256, int(round(crop.height * sc))))
    # Crisp 1-pass Nearest + strip any stray magenta/pink + snap to crisp cyan-blue plasma cel palette!
    rim = crop.resize((nw, nh), Image.Resampling.NEAREST)
    rarr = p1b.post_clean_resized(np.array(rim, dtype=np.uint8), allow_fx=True)
    rvis = rarr[:, :, 3] > 0
    # Snap strictly to PAL_KENTA_IMPACT so sharpness & color palette are razor-crisp pixel art!
    fg = rarr[rvis, :3].astype(np.float32)
    w_vec = np.array([2.0, 3.5, 2.5], dtype=np.float32)
    d2 = (((fg[:, None, :] - PAL_KENTA_IMPACT[None, :, :]) ** 2) * w_vec[None, None, :]).sum(axis=2)
    rarr[rvis, :3] = PAL_KENTA_IMPACT[np.argmin(d2, axis=1)].astype(np.uint8)
    rarr[rvis, 3] = 255
    return fxsharp.place_on_288(Image.fromarray(rarr, mode="RGBA"), mode="center", ref_y=176)


def main() -> int:
    jobs = []
    for i in range(6):
        fid = f"kenta_impact_{i:02d}"
        ref_p = REFS_DIR / f"ref_{fid}.png"
        make_ref_1024(P2_FX_RAW / f"{fid}.png", ref_p)
        _, phase_txt = PHASE_PROMPTS[fid]
        jobs.append((fid, ref_p, COMMON_KENTA_PROMPT + "\n\n" + phase_txt))

    print("Launching 6 parallel Codex CLI jobs to convert kentaima_impact_fx to full 360 circular explosions...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        futs = [ex.submit(run_job, *j) for j in jobs]
        for f in concurrent.futures.as_completed(futs):
            fid, rc, out = f.result()
            print(f"[GEN {fid}] rc={rc} | {out.splitlines()[-1] if out else ''}")
            if rc != 0:
                raise RuntimeError(f"Failed generating {fid}: {out}")

    FX_REG_DIR.mkdir(parents=True, exist_ok=True)
    QA_DIR.mkdir(parents=True, exist_ok=True)
    for i in range(6):
        fid = f"kenta_impact_{i:02d}"
        td, _ = PHASE_PROMPTS[fid]
        im = register_circular_explosion(fid, GEN_DIR / fid / "generated.png", td)
        out_p = FX_REG_DIR / f"{fid}.png"
        im.save(out_p)
        old_sob, old_uc = fxsharp.measure_sharpness(np.array(Image.open(OLD_FX_REG / f"{fid}.png").convert("RGBA")))
        new_sob, new_uc = fxsharp.measure_sharpness(np.array(im))
        arr = np.array(im)
        ys, xs = np.where(arr[:, :, 3] > 0)
        bw, bh = int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)
        print(f"[{fid}] aspect={bw}x{bh} (ratio={bw/max(1,bh):.2f}) | Sobel {old_sob} -> {new_sob} | colors {old_uc} -> {new_uc}")

    # Render BEFORE (half-dome) vs AFTER (full circular) 6-frame QA strip!
    cw, ch = 220, 220
    bd = Image.new("RGBA", (6 * cw, 2 * (ch + 24)), (18, 22, 30, 255))
    dr = ImageDraw.Draw(bd)
    yy, xx = np.indices((ch, cw))
    chk = ((xx // 12) + (yy // 12)) % 2 == 0
    for ri, (tag, base_dir) in enumerate([("BEFORE (Half-Dome Blurry)", OLD_FX_REG), ("AFTER (Full 360 Circle Crisp)", FX_REG_DIR)]):
        for i in range(6):
            p = base_dir / f"kenta_impact_{i:02d}.png"
            im = Image.open(p).convert("RGBA").crop((34, 66, 254, 286))
            bg_a = np.zeros((ch, cw, 4), dtype=np.uint8)
            bg_a[chk] = [56, 62, 76, 255]
            bg_a[~chk] = [42, 46, 58, 255]
            bg = Image.fromarray(bg_a, "RGBA")
            bg.alpha_composite(im)
            x0, y0 = i * cw, ri * (ch + 24)
            bd.paste(bg, (x0, y0 + 24))
            dr.rectangle([x0, y0, x0 + cw - 1, y0 + ch + 23], outline=(90, 100, 120, 255))
            dr.text((x0 + 4, y0 + 5), f"{tag[:16]} #{i}", fill=(130, 255, 170, 255) if ri == 1 else (255, 200, 110, 255))
    out_qa = QA_DIR / "qa_kentaima_impact_circle_6f.png"
    bd.save(out_qa)
    print("Saved QA:", out_qa)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
