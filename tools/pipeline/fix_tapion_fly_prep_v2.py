#!/usr/bin/env python3
"""
DR7-Studio — Tapion `fly_prep` Aura Polish (`polish_v2`):
Owner request: "fly_prep aura trắng xung quanh cho nhạt lại và mỏng hơn 50%."
- Preserves 100% opaque crisp Tapion hovering body (alpha == 255 on every body pixel + 1px dark body outline).
- Extracts the outer white shockwave aura from `fly_prep_00..03`, removes heavy black ink around the aura,
  contracts/thins its radial reach & stroke thickness by ~50% around Tapion's body contour,
  and applies airy pale translucent white alpha (45% core -> 22% outer spike tips, per Điều 7.2).
"""
from __future__ import annotations

import pathlib
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

ROOT = pathlib.Path(__file__).resolve().parents[2]
W2_REG = ROOT / "work" / "characters" / "tapion" / "sword_fix_w2" / "registered_288"
OUT_DIR = ROOT / "work" / "characters" / "tapion" / "polish_v2"
REG_DIR = OUT_DIR / "registered_288"
QA_DIR = OUT_DIR / "qa"

CW, CH = 288, 288


def extract_body_and_aura(arr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Separate Tapion's exact opaque hovering body (with 1px dark outline) from the outer white shockwave aura."""
    vis = arr[:, :, 3] > 0
    r = arr[:, :, 0].astype(int)
    g = arr[:, :, 1].astype(int)
    b = arr[:, :, 2].astype(int)

    # Pure white shockwave aura pixels & dark pixels
    is_white = vis & (r > 210) & (g > 210) & (b > 210)
    is_dark = vis & (r < 48) & (g < 48) & (b < 58)
    body_colored = vis & (~is_white) & (~is_dark)

    # Body interior includes tiny white eye-sclera / silver clasp / pommel pixels fully enclosed or touching colored body
    # Dilate body_colored by 2px to capture its 1px dark outline and enclosed white eye/silver highlights
    body_hull = ndimage.binary_fill_holes(ndimage.binary_closing(body_colored, structure=np.ones((3, 3))))
    # Keep dark outline pixels immediately adjacent (1px) to body_colored or body_hull
    body_1px = ndimage.binary_dilation(body_hull, structure=np.ones((3, 3)))
    body_mask = body_hull | (is_dark & body_1px)
    # Also include silver hilt pommel / white eye pixels inside body_hull (already covered by body_hull)
    # Exclude pure white outer shockwave pixels even if adjacent to body outline
    body_mask = body_mask & ~(is_white & ~body_hull)

    # Build clean body RGBA (100% opaque alpha=255)
    body = np.zeros_like(arr)
    body[body_mask] = arr[body_mask]
    body[body_mask, 3] = 255

    # Outer aura mask = pure white shockwave pixels OUTSIDE body_mask (NO heavy black aura ink!)
    aura_white_mask = is_white & ~body_mask
    return body, aura_white_mask


def thin_and_soften_aura(body: np.ndarray, aura_mask: np.ndarray, frame_idx: int) -> tuple[np.ndarray, dict]:
    """Contract radial reach & thin stroke width of outer white aura by ~50%, then apply soft pale translucent white."""
    body_mask = body[:, :, 3] > 0
    bys, bxs = np.where(body_mask)
    cx = 0.5 * (bxs.min() + bxs.max())
    cy = 0.5 * (bys.min() + bys.max())

    orig_aura_px = int(aura_mask.sum())
    dist_from_body = ndimage.distance_transform_edt(~body_mask)
    orig_max_r = float(dist_from_body[aura_mask].max()) if orig_aura_px else 0.0
    orig_mean_r = float(dist_from_body[aura_mask].mean()) if orig_aura_px else 0.0

    # Step 1: Radial contraction toward Tapion's body silhouette!
    yy, xx = np.indices((CH, CW), dtype=np.float32)
    dx = xx - cx
    dy = yy - cy
    rad = np.hypot(dx, dy)
    ux = np.where(rad > 1e-4, dx / np.maximum(rad, 1e-4), 0.0)
    uy = np.where(rad > 1e-4, dy / np.maximum(rad, 1e-4), 0.0)

    # Contract outer radial reach so aura thickness around body is ~50% thinner!
    pull = dist_from_body * 0.90
    src_x = np.clip(np.round(xx + ux * pull).astype(int), 0, CW - 1)
    src_y = np.clip(np.round(yy + uy * pull).astype(int), 0, CH - 1)
    contracted = aura_mask[src_y, src_x] & (~body_mask)

    # Step 2: Slim thick solid white blobs (especially frames 0 & 1) while preserving crisp anime spikes!
    dt_in = ndimage.distance_transform_edt(contracted)
    if frame_idx in (0, 1):
        eroded = ndimage.binary_erosion(contracted, structure=np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]]))
        bulky_edge = contracted & ~eroded & (ndimage.maximum_filter(dt_in, size=5) >= 2.8)
        thinned = contracted & ~bulky_edge
    else:
        eroded = ndimage.binary_erosion(contracted, structure=np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]]))
        bulky_edge = contracted & ~eroded & (ndimage.maximum_filter(dt_in, size=3) >= 2.4)
        thinned = contracted & ~bulky_edge

    # Drop tiny 1px isolated dust specks far from body
    lbl, n = ndimage.label(thinned, structure=np.ones((3, 3)))
    for cid in range(1, n + 1):
        c_m = lbl == cid
        if int(c_m.sum()) <= 1:
            thinned[c_m] = False

    new_aura_px = int(thinned.sum())
    new_max_r = float(dist_from_body[thinned].max()) if new_aura_px else 0.0
    new_mean_r = float(dist_from_body[thinned].mean()) if new_aura_px else 0.0

    # Step 3: Electric cyan-blue aura matching `fly_aura_fx` palette!
    # Palette sampled directly from `fly_aura_fx_00.png`:
    #   - Inner core near body (t < 0.25): pale ice-cyan [185, 250, 255]
    #   - Mid glow (0.25 <= t < 0.65): electric cyan [15, 241, 254]
    #   - Outer spike tips (t >= 0.65): vibrant azure-blue [24, 152, 255]
    # Soft VFX alpha (168/255 ≈ 66% near body -> 108/255 ≈ 42% at outer tips) keeps it airy,
    # 50% thinner, and clearly readable in vivid cyan-blue on dark, sky, AND rocky map backgrounds!
    # Body pixels remain 100% opaque (alpha=255).
    out = np.zeros((CH, CW, 4), dtype=np.uint8)
    max_d = max(1.0, new_max_r)
    t_rad = np.clip(dist_from_body / max_d, 0.0, 1.0)
    core_alpha = np.round(168.0 * (1.0 - 0.36 * t_rad)).astype(np.uint8)  # 168 -> 108

    # Smooth 3-stop cyan-blue gradient matching fly_aura_fx
    r_ch = np.where(t_rad < 0.35, 185.0 - (185.0 - 15.0) * (t_rad / 0.35), 15.0 + (24.0 - 15.0) * ((t_rad - 0.35) / 0.65))
    g_ch = np.where(t_rad < 0.35, 250.0 - (250.0 - 241.0) * (t_rad / 0.35), 241.0 - (241.0 - 148.0) * ((t_rad - 0.35) / 0.65))
    b_ch = np.full_like(t_rad, 255.0)

    out[thinned, 0] = np.clip(np.round(r_ch[thinned]), 0, 255).astype(np.uint8)
    out[thinned, 1] = np.clip(np.round(g_ch[thinned]), 0, 255).astype(np.uint8)
    out[thinned, 2] = np.clip(np.round(b_ch[thinned]), 0, 255).astype(np.uint8)
    out[thinned, 3] = core_alpha[thinned]

    # Composite 100% opaque Tapion body cleanly on top!
    out[body_mask] = body[body_mask]
    out[body_mask, 3] = 255

    metrics = {
        "orig_aura_px": orig_aura_px,
        "new_aura_core_px": new_aura_px,
        "area_ratio": round(new_aura_px / max(1, orig_aura_px), 3),
        "orig_max_r": round(orig_max_r, 1),
        "new_max_r": round(new_max_r, 1),
        "orig_mean_r": round(orig_mean_r, 1),
        "new_mean_r": round(new_mean_r, 1),
        "radius_ratio": round(new_mean_r / max(0.1, orig_mean_r), 3),
        "body_px": int(body_mask.sum()),
        "body_semi_alpha": int(((out[body_mask, 3] > 0) & (out[body_mask, 3] < 255)).sum()),
    }
    return out, metrics


def render_comparison(before_list: list[Image.Image], after_list: list[Image.Image], out_path: pathlib.Path) -> None:
    box = (44, 88, 244, 268)  # 200x180 crop around Tapion
    sc = 2
    cw, ch = (box[2] - box[0]) * sc, (box[3] - box[1]) * sc
    bgs = [
        ("DARK", (24, 30, 44, 255)),
        ("LIGHT_SKY", (195, 220, 245, 255)),
        ("ROCKY_MAP", (148, 128, 102, 255)),
    ]
    rows = len(bgs) * 2
    cols = 4
    board = Image.new("RGBA", (cols * cw, rows * (ch + 22)), (18, 20, 26, 255))
    dr = ImageDraw.Draw(board)
    for bi, (bname, bcol) in enumerate(bgs):
        for kind_i, (kname, imgs) in enumerate([("BEFORE", before_list), ("AFTER (50% thinner + pale)", after_list)]):
            ri = bi * 2 + kind_i
            for ci, im in enumerate(imgs):
                x0, y0 = ci * cw, ri * (ch + 22)
                tile = Image.new("RGBA", (cw, ch), bcol)
                sub = im.crop(box).resize((cw, ch), Image.Resampling.NEAREST)
                tile.alpha_composite(sub)
                board.paste(tile, (x0, y0 + 22))
                dr.rectangle([x0, y0, x0 + cw - 1, y0 + ch + 21], outline=(80, 90, 110, 255))
                dr.text((x0 + 6, y0 + 4), f"{bname} | {kname} #{ci}", fill=(255, 230, 120, 255))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    board.save(out_path)


def main() -> int:
    REG_DIR.mkdir(parents=True, exist_ok=True)
    QA_DIR.mkdir(parents=True, exist_ok=True)
    before_imgs, after_imgs = [], []
    for i in range(4):
        src_p = W2_REG / f"fly_prep_{i:02d}.png"
        src_im = Image.open(src_p).convert("RGBA")
        before_imgs.append(src_im)
        arr = np.array(src_im, dtype=np.uint8)
        body, aura_m = extract_body_and_aura(arr)
        out_arr, m = thin_and_soften_aura(body, aura_m, i)
        out_im = Image.fromarray(out_arr, mode="RGBA")
        out_im.save(REG_DIR / f"fly_prep_{i:02d}.png")
        after_imgs.append(out_im)
        print(f"[fly_prep_{i:02d}] {m}")
    render_comparison(before_imgs, after_imgs, QA_DIR / "qa_fly_prep_before_after_3bg.png")
    print("Saved QA strip:", QA_DIR / "qa_fly_prep_before_after_3bg.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
