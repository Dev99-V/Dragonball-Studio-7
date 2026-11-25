#!/usr/bin/env python3
"""
Surgical pixel-level polish for Tapion Wave 1-3 sword/scabbard frames after 2x checkerboard zoom audit:
1. `idle_02`: remove duplicate `-X` waist silver clasp so all 5 `idle` frames match 100%.
2. `recover_02`, `recover_07`, `barrier_08`: remove tiny floating white `+X` pommel remnant islands.
3. `barrier_05`: stamp crisp brown/silver `-X` sword hilt from `barrier_04` (aligned by head/ear) over cyan-tinted hilt.
4. `atk1_03`: replace duplicate `-X` hip silver cap with smooth orange coat + 1px dark outline.
5. `atk1_04`: remove floating `-X` gray wisp & white blob on coat/sash, restoring crisp blue sash + orange coat + 1px outline.
6. `atk2_03, atk2_04, atk7_02, atk7_03, atk7_04, atk8_00`: remove tiny stray speck on `atk2_03` and convert mistaken front yellow belt buckle + blue front tabard into canonical back-view dark waist sash + orange back coat skirt (matching `tapion/tấn công 2.png` #4/#5, `Tấn công 7.png` #3..#5, `Tấn công 8.png` #1).
7. `atk9_03`, `kenta_cast_00..03`: remove tiny disconnected `-X` orphan crumbs (`area <= 18`) and bridge 1px gap on `kenta_cast_00` `+X` scabbard tip.
"""
from __future__ import annotations

import pathlib
import sys
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

ROOT = pathlib.Path("/workspaces/Dragonball-Studio-7")
sys.path.insert(0, str(ROOT / "tools" / "pipeline"))
import qc_tapion_master_gate as qc_gate  # noqa: E402

W1_DIR = ROOT / "work" / "characters" / "tapion" / "sword_fix_w1" / "registered_288"
W2_DIR = ROOT / "work" / "characters" / "tapion" / "sword_fix_w2" / "registered_288"
W3_DIR = ROOT / "work" / "characters" / "tapion" / "sword_fix_w3" / "registered_288"
AUDIT_DIR = ROOT / "work" / "characters" / "tapion" / "sword_audit"

OUTLINE = np.array([15, 13, 18, 255], dtype=np.uint8)
ORANGE_HI = np.array([242, 146, 20, 255], dtype=np.uint8)
ORANGE_MID = np.array([218, 118, 14, 255], dtype=np.uint8)
ORANGE_SHD = np.array([168, 78, 12, 255], dtype=np.uint8)
BLUE_MID = np.array([25, 92, 200, 255], dtype=np.uint8)
BLUE_SHD = np.array([16, 56, 138, 255], dtype=np.uint8)
BELT_DARK = np.array([38, 52, 74, 255], dtype=np.uint8)
SCAB_RED = np.array([186, 30, 38, 255], dtype=np.uint8)


def load_rgba(p: pathlib.Path) -> np.ndarray:
    return np.array(Image.open(p).convert("RGBA"), dtype=np.uint8)


def save_rgba(arr: np.ndarray, p: pathlib.Path) -> None:
    Image.fromarray(arr, mode="RGBA").save(p)


def fix_idle_02() -> None:
    p = W1_DIR / "idle_02.png"
    arr = load_rgba(p)
    ref = load_rgba(W1_DIR / "idle_01.png")
    # In idle_02, the duplicate -X waist silver clasp sits around x=128..139, y=195..206.
    # Copy the clean -X waist/coat region from idle_01 (which has identical lower coat/legs!)
    # Verify alignment of boots between idle_01 and idle_02 first:
    for y in range(195, 208):
        for x in range(127, 141):
            r, g, b, a = [int(v) for v in arr[y, x]]
            # Replace silver/gray clasp & its inner dark ring with idle_01's clean orange coat / belt
            if a > 0 and ((r > 135 and g > 135 and b > 145) or (abs(r - g) < 22 and b > 90)):
                arr[y, x] = ref[y, x]
    # Also smooth the 1px black circle ring around that clasp using ref[194:208, 128:141]
    arr[195:207, 129:141] = ref[195:207, 129:141]
    save_rgba(arr, p)


def erase_white_pommel_ball(p: pathlib.Path, x0: int, x1: int, y0: int, y1: int) -> None:
    arr = load_rgba(p)
    vis = arr[:, :, 3] > 0
    lbl, n = ndimage.label(vis, structure=np.ones((3, 3), dtype=int))
    # Any disconnected small island inside [x0..x1, y0..y1] that contains bright neutral gray/white + dark outline
    for cid in range(1, n + 1):
        ys, xs = np.where(lbl == cid)
        if len(xs) <= 45 and xs.min() >= x0 and xs.max() <= x1 and ys.min() >= y0 and ys.max() <= y1:
            sub = arr[lbl == cid]
            # Pommel ball has dark outline pixels (r<60,g<60,b<80), unlike pure cyan sparks
            has_dark = ((sub[:, 0] < 65) & (sub[:, 1] < 65) & (sub[:, 2] < 85)).any()
            if has_dark:
                arr[lbl == cid] = [0, 0, 0, 0]
    save_rgba(arr, p)


def fix_barrier_05() -> None:
    p5 = W2_DIR / "barrier_05.png"
    p4 = W2_DIR / "barrier_04.png"
    a5 = load_rgba(p5)
    a4 = load_rgba(p4)
    # Align barrier_04 to barrier_05 using face skin centroid
    def face_center(arr: np.ndarray):
        v = arr[:, :, 3] > 0
        r, g, b = arr[:, :, 0].astype(int), arr[:, :, 1].astype(int), arr[:, :, 2].astype(int)
        f = v & (r > 195) & (g > 135) & (b > 95) & (r > b + 45)
        ys, xs = np.where(f)
        return int(round(xs.mean())), int(round(ys.mean()))

    fx4, fy4 = face_center(a4)
    fx5, fy5 = face_center(a5)
    dx, dy = fx5 - fx4, fy5 - fy4

    # Extract sword hilt pixels from barrier_04 in upper-left relative to face:
    # x in [fx4-30 .. fx4-9], y in [fy4-24 .. fy4+2]
    for y4 in range(max(0, fy4 - 24), min(288, fy4 + 3)):
        for x4 in range(max(0, fx4 - 30), min(288, fx4 - 8)):
            r, g, b, a = [int(v) for v in a4[y4, x4]]
            if a == 0:
                continue
            # Exclude blue dome pixels (b > r + 35 and b > 140) and hair (r > 175 and g < 95 and b < 45)
            is_blue_dome = (b > r + 30) and (b > 130)
            is_hair = (r > 165) and (b < 45) and (r > g + 45)
            if not is_blue_dome and not is_hair:
                y5, x5 = y4 + dy, x4 + dx
                if 0 <= y5 < 288 and 0 <= x5 < 288:
                    a5[y5, x5] = a4[y4, x4]
    save_rgba(a5, p5)


def fix_atk1_03_and_04() -> None:
    # 1. atk1_03: remove duplicate -X silver cap on orange coat waist (x=125..136, y=190..201)
    p3 = W3_DIR / "atk1_03.png"
    a3 = load_rgba(p3)
    for y in range(189, 202):
        for x in range(125, 136):
            r, g, b, a = [int(v) for v in a3[y, x]]
            if a == 0:
                continue
            # Silver/white/blueish-gray cap pixels -> orange coat
            if (r > 130 and g > 135 and b > 145) or (abs(r - g) < 25 and b > 95):
                a3[y, x] = ORANGE_HI if y < 196 else ORANGE_MID
    # Clean any orphaned inner dark outline ring inside the orange coat body (surrounded by orange/non-transparent)
    vis3 = a3[:, :, 3] > 0
    for y in range(190, 201):
        for x in range(126, 136):
            if not vis3[y, x]:
                continue
            # Check if all 4-neighbors are opaque
            if vis3[y - 1, x] and vis3[y + 1, x] and vis3[y, x - 1] and vis3[y, x + 1]:
                r, g, b, _ = [int(v) for v in a3[y, x]]
                if r < 65 and g < 65 and b < 75 and x <= 133:
                    a3[y, x] = ORANGE_MID
            else:
                # Exterior boundary pixel -> ensure crisp 1px dark outline
                a3[y, x] = OUTLINE
    save_rgba(a3, p3)

    # 2. atk1_04: erase floating gray wisp on -X (x=98..117, y=167..178) & fix white patch (x=117..128, y=176..193)
    p4 = W3_DIR / "atk1_04.png"
    a4 = load_rgba(p4)
    # Erase the thin gray wisp sticking left of x=116 in y=168..178
    for y in range(167, 179):
        for x in range(96, 117):
            r, g, b, a = [int(v) for v in a4[y, x]]
            if a > 0 and not (b > r + 35 and b > 110):  # preserve true blue scarf!
                a4[y, x] = [0, 0, 0, 0]
    # Also remove any disconnected island created by erasing the wisp
    v4 = a4[:, :, 3] > 0
    lbl, n = ndimage.label(v4, structure=np.ones((3, 3), dtype=int))
    if n > 1:
        main_c = int(np.argmax(ndimage.sum(v4, lbl, range(1, n + 1)))) + 1
        for cid in range(1, n + 1):
            if cid != main_c:
                a4[lbl == cid] = [0, 0, 0, 0]

    # Replace white/gray patch on -X sash/coat (x=116..131, y=172..195)
    for y in range(172, 195):
        for x in range(116, 131):
            r, g, b, a = [int(v) for v in a4[y, x]]
            if a == 0:
                continue
            is_white_gray = (r > 135 and g > 135 and b > 140) or (abs(r - g) < 22 and b > 100 and r > 100)
            if is_white_gray:
                # Upper part (y <= 183 and x <= 125) belongs to blue sash; lower/inner belongs to orange coat
                if y <= 183 and x <= 124:
                    a4[y, x] = BLUE_MID
                else:
                    a4[y, x] = ORANGE_HI if x >= 123 else ORANGE_MID

    # Ensure crisp 1px dark exterior outline on repaired region x=114..131, y=170..196
    v4 = a4[:, :, 3] > 0
    for y in range(170, 196):
        for x in range(114, 131):
            if v4[y, x] and not (v4[y - 1, x] and v4[y + 1, x] and v4[y, x - 1] and v4[y, x + 1]):
                a4[y, x] = OUTLINE
    save_rgba(a4, p4)


def fix_back_view_tunics() -> None:
    """Convert mistaken front yellow belt buckle + blue front tabard on back-turned slash poses
    (`atk2_03, atk2_04, atk7_02, atk7_03, atk7_04, atk8_00`) into canonical back-view dark waist sash + orange back coat!"""
    for fid in ("atk2_03", "atk2_04", "atk7_02", "atk7_03", "atk7_04", "atk8_00"):
        p = W3_DIR / f"{fid}.png"
        arr = load_rgba(p)
        vis = arr[:, :, 3] > 0

        # Remove tiny orphan speck on atk2_03 (area <= 15 on far left near boots)
        if fid == "atk2_03":
            lbl, n = ndimage.label(vis, structure=np.ones((3, 3), dtype=int))
            for cid in range(1, n + 1):
                ys, xs = np.where(lbl == cid)
                if len(xs) <= 16 and xs.max() < 120 and ys.min() > 220:
                    arr[lbl == cid] = [0, 0, 0, 0]

        # Locate the lower tunic skirt zone (y in 196..230, x in 132..162):
        # Preserve crimson scabbard (r > 130 and r > g + 45 and b < 95), silver scabbard cap, green pants (g > r + 10), and dark outlines!
        for y in range(197, 229):
            for x in range(134, 160):
                r, g, b, a = [int(v) for v in arr[y, x]]
                if a == 0:
                    continue
                # Preserve cyan slash FX!
                if (b - r > 35 and b > 175) or (r > 210 and g > 230 and b > 240):
                    continue
                # Preserve crimson scabbard!
                if r > 125 and r > g + 45 and b < 95:
                    continue
                # Yellow belt / buckle at waist (y in 198..207): bright yellow (r>195, g>145, b<70) -> dark back waist sash!
                if 198 <= y <= 207 and r > 185 and g > 135 and b < 80:
                    arr[y, x] = BELT_DARK
                # Blue front tabard below waist (y >= 205, b > r + 25 and b > 95) -> orange back tunic skirt!
                elif y >= 205 and b > r + 20 and b > 80:
                    arr[y, x] = ORANGE_HI if x < 149 else ORANGE_MID
                elif 198 <= y <= 204 and b > r + 20 and b > 80 and x >= 143:
                    arr[y, x] = BELT_DARK

        # Smooth internal vertical black tabard seam lines (x in 141..153, y in 207..223) surrounded by orange coat!
        for y in range(207, 223):
            for x in range(141, 154):
                r, g, b, a = [int(v) for v in arr[y, x]]
                if a > 0 and r < 55 and g < 55 and b < 65:
                    # Check left & right neighbors: if neither is transparent and neither is green pants nor crimson scabbard
                    lr = [arr[y, x - 1], arr[y, x + 1]]
                    if all(px[3] > 0 for px in lr):
                        is_orange_nbr = any(int(px[0]) > 160 and int(px[1]) > 70 and int(px[2]) < 50 for px in lr)
                        not_green_below = not (int(arr[y + 1, x, 1]) > int(arr[y + 1, x, 0]) + 8)
                        not_red_above = not (int(arr[y - 1, x, 0]) > 125 and int(arr[y - 1, x, 0]) > int(arr[y - 1, x, 1]) + 45)
                        if is_orange_nbr and not_green_below and not_red_above and y < 221:
                            arr[y, x] = ORANGE_MID if x < 150 else ORANGE_SHD

        save_rgba(arr, p)


def fix_stray_crumbs_and_kenta() -> None:
    # 1. atk9_03: remove 4px speck at (119..120, 234..235)
    p93 = W3_DIR / "atk9_03.png"
    a93 = load_rgba(p93)
    a93[233:237, 118:122] = [0, 0, 0, 0]
    save_rgba(a93, p93)

    # 2. kenta_cast_01, 02, 03: remove tiny disconnected crumbs on left side (x < 134, area <= 20)
    for fid in ("kenta_cast_01", "kenta_cast_02", "kenta_cast_03"):
        p = W3_DIR / f"{fid}.png"
        arr = load_rgba(p)
        vis = arr[:, :, 3] > 0
        lbl, n = ndimage.label(vis, structure=np.ones((3, 3), dtype=int))
        if n > 1:
            main_c = int(np.argmax(ndimage.sum(vis, lbl, range(1, n + 1)))) + 1
            for cid in range(1, n + 1):
                if cid == main_c:
                    continue
                ys, xs = np.where(lbl == cid)
                # Only drop non-cyan crumbs on -X side
                sub = arr[lbl == cid]
                is_cyan = ((sub[:, 2].astype(int) - sub[:, 0].astype(int)) > 40).any()
                if len(xs) <= 22 and xs.max() <= 133 and not is_cyan:
                    arr[lbl == cid] = [0, 0, 0, 0]
        save_rgba(arr, p)

    # 3. kenta_cast_00: bridge the 1-2px gap between +X coat (x~165) and silver scabbard cap (x=169..170, y=185..190)
    p0 = W3_DIR / "kenta_cast_00.png"
    a0 = load_rgba(p0)
    # Paint short diagonal crimson scabbard tip + 1px dark outline connecting (165, 183) -> (169, 188)
    for dx, dy in [(166, 184), (167, 185), (168, 186), (167, 186), (168, 187)]:
        a0[dy, dx] = SCAB_RED
    for dx, dy in [(166, 183), (167, 184), (168, 185), (169, 184), (165, 185), (166, 186), (167, 187), (168, 188)]:
        if a0[dy, dx, 3] == 0:
            a0[dy, dx] = OUTLINE
    save_rgba(a0, p0)


def main() -> int:
    fix_idle_02()
    erase_white_pommel_ball(W2_DIR / "recover_02.png", 164, 178, 142, 158)
    erase_white_pommel_ball(W2_DIR / "recover_07.png", 162, 176, 148, 163)
    erase_white_pommel_ball(W2_DIR / "barrier_08.png", 161, 173, 149, 161)
    fix_barrier_05()
    fix_atk1_03_and_04()
    fix_back_view_tunics()
    fix_stray_crumbs_and_kenta()

    # Run QC gate on all touched files + render 3x verification strip!
    canon_pal, _ = qc_gate.load_master_palette()
    touched = [
        (W1_DIR / "idle_02.png", False, True),
        (W2_DIR / "recover_02.png", True, False),
        (W2_DIR / "recover_07.png", True, False),
        (W2_DIR / "barrier_05.png", True, False),
        (W2_DIR / "barrier_08.png", True, False),
        (W3_DIR / "atk1_03.png", True, False),
        (W3_DIR / "atk1_04.png", True, False),
        (W3_DIR / "atk2_03.png", True, False),
        (W3_DIR / "atk2_04.png", True, False),
        (W3_DIR / "atk7_02.png", True, False),
        (W3_DIR / "atk7_03.png", True, False),
        (W3_DIR / "atk7_04.png", True, False),
        (W3_DIR / "atk8_00.png", True, False),
        (W3_DIR / "atk9_03.png", True, False),
        (W3_DIR / "kenta_cast_00.png", True, False),
        (W3_DIR / "kenta_cast_01.png", True, False),
        (W3_DIR / "kenta_cast_02.png", True, False),
        (W3_DIR / "kenta_cast_03.png", True, False),
    ]
    for p, allow_fx, chk_gnd in touched:
        qc = qc_gate.audit_frame(p, canon_pal, allow_fx_border=allow_fx, check_grounded_stance=chk_gnd)
        print(f"[POLISH QC] {p.name:16s} pass={qc['pass']} errors={qc['errors']}")
        if not qc["pass"]:
            raise RuntimeError(f"Polish QC failed on {p.name}: {qc['errors']}")

    # Render 3x zoomed verification sheet of all 18 polished frames
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    cols = 6
    rows = 3
    box = (82, 102, 214, 254)
    sc = 2
    cw, ch = (box[2] - box[0]) * sc, (box[3] - box[1]) * sc
    sheet = Image.new("RGBA", (cols * cw, rows * (ch + 20)), (40, 44, 56, 255))
    dr = ImageDraw.Draw(sheet)
    for i, (p, _, _) in enumerate(touched):
        r, c = divmod(i, cols)
        x0, y0 = c * cw, r * (ch + 20)
        cell = np.zeros((ch, cw, 4), dtype=np.uint8)
        yy, xx = np.indices((ch, cw))
        chk = ((xx // 12) + (yy // 12)) % 2 == 0
        cell[chk] = [64, 70, 86, 255]
        cell[~chk] = [48, 53, 66, 255]
        cim = Image.fromarray(cell, "RGBA")
        cim.alpha_composite(Image.open(p).convert("RGBA").crop(box).resize((cw, ch), Image.NEAREST))
        sheet.paste(cim, (x0, y0 + 20))
        dr.text((x0 + 4, y0 + 4), p.stem, fill=(140, 255, 170, 255))
    out_sheet = AUDIT_DIR / "polish_18_verified.png"
    sheet.save(out_sheet)
    print("Saved", out_sheet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
