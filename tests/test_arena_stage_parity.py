import http.server
import io
import json
import pathlib
import sys
import threading
import unittest
import urllib.error
import urllib.request
import zipfile

import numpy as np
from PIL import Image

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools" / "preview"))
import server as preview_server  # noqa: E402


class ArenaStageParityTests(unittest.TestCase):
    def test_stage_spec_map_bezel_and_godot_settings_match_1_to_1(self) -> None:
        stage_path = REPO_ROOT / "assets" / "maps" / "rocky_plateau" / "arena-stage.json"
        self.assertTrue(stage_path.is_file(), f"Missing {stage_path}")
        stage = json.loads(stage_path.read_text(encoding="utf-8"))

        vp = stage["viewport"]
        self.assertEqual((vp["width"], vp["height"]), (1920, 1080))
        self.assertEqual(vp["aspect_ratio"], "16:9")
        self.assertEqual(vp["orientation"], "landscape")
        self.assertEqual(vp["stretch_mode"], "canvas_items")
        self.assertEqual(vp["stretch_aspect"], "keep")
        self.assertEqual(vp["handheld_orientation_code"], 0)

        gp = stage["gameplay"]
        self.assertEqual(gp["ground_y"], 840)
        self.assertEqual(gp["walkable_bounds_x"], [140, 1780])
        self.assertEqual(gp["player_spawn_x"], 560)
        self.assertEqual(gp["dummy_spawn_x"], 1360)
        self.assertEqual(gp["character_scale_default"], 2)
        self.assertEqual(gp["character_scale_options"], [1, 2, 3])
        self.assertEqual(gp["character_scale_min"], 0.5)
        self.assertEqual(gp["character_scale_max"], 3.0)
        self.assertFalse(gp["screen_shake_enabled"])
        self.assertFalse(gp["ground_shadow_ellipse_enabled"])
        self.assertEqual(gp["burrow_dust_scale_default"], 2.65)
        self.assertEqual(gp["burrow_dust_scale_options"], [1, 1.5, 2.25, 2.65])
        self.assertEqual(gp["flight"]["min_y"], 60)
        self.assertEqual(gp["flight"]["max_y"], 840)
        self.assertEqual(gp["flight"]["default_y"], 250)
        self.assertEqual(gp["flight"]["middle_offset_px"], -290)
        self.assertEqual(gp["texture_filter"], "nearest")

        # Verify sample background image dimensions & hash
        map_path = REPO_ROOT / stage["map"]["background_path"]
        self.assertTrue(map_path.is_file())
        with Image.open(map_path) as map_img:
            self.assertEqual(list(map_img.size), stage["map"]["source_size_px"])
            self.assertEqual(map_img.mode, "RGB")

        # Verify phone frame transparent opening is exact 1920 x 1080
        bezel_path = REPO_ROOT / stage["phone_bezel"]["repo_path"]
        self.assertTrue(bezel_path.is_file())
        with Image.open(bezel_path) as bz:
            self.assertEqual(list(bz.size), stage["phone_bezel"]["image_size_px"])
            self.assertEqual(bz.mode, "RGBA")
            arr = np.array(bz)[:, :, 3]
        hx, hy, hw, hh = stage["phone_bezel"]["screen_hole_px"]
        self.assertEqual((hw, hh), (1920, 1080))
        mid_row = arr[hy + hh // 2, :]
        mid_col = arr[:, hx + hw // 2]
        self.assertEqual(int(np.where(mid_row[: arr.shape[1] // 2] > 0)[0].max()) + 1, hx)
        self.assertEqual(int(np.where(mid_row[arr.shape[1] // 2 :] > 0)[0].min()) + arr.shape[1] // 2 - 1, hx + hw - 1)
        self.assertEqual(int(np.where(mid_col[: arr.shape[0] // 2] > 0)[0].max()) + 1, hy)
        self.assertEqual(int(np.where(mid_col[arr.shape[0] // 2 :] > 0)[0].min()) + arr.shape[0] // 2 - 1, hy + hh - 1)
        self.assertTrue(np.all(arr[hy : hy + hh, hx + 120 : hx + hw - 120] == 0))
        self.assertTrue(np.all(arr[hy + 120 : hy + hh - 120, hx : hx + hw] == 0))

        # Server parity + Godot ZIP
        parity = preview_server.verify_engine_localhost_parity()
        self.assertTrue(parity["ok"], parity)
        self.assertEqual(parity["checked_bundles"], len(json.loads((REPO_ROOT / "assets/roster.json").read_text())["characters"]))
        self.assertEqual(parity["finalized_characters"], len(json.loads((REPO_ROOT / "assets/roster.json").read_text())["characters"]))

        zf = zipfile.ZipFile(io.BytesIO(preview_server.build_godot_zip_bytes()))
        names = set(zf.namelist())
        for req in (
            "project.godot",
            "scenes/ArenaSandbox.tscn",
            "scenes/ArenaSandbox.gd",
            "scenes/UtilityAIController.gd",
            "assets/maps/rocky_plateau/arena-stage.json",
            "assets/maps/rocky_plateau/rocky-plateau-bg.jpg",
        ):
            self.assertIn(req, names)

        stage_uai = payload_stage["gameplay"].get("utility_ai", {}) if "payload_stage" in locals() else json.loads(
            zf.read("assets/maps/rocky_plateau/arena-stage.json").decode("utf-8")
        )["gameplay"].get("utility_ai", {})
        self.assertEqual(stage_uai.get("close_edge_px"), 50)
        self.assertEqual(stage_uai.get("mid_max_edge_px"), 200)
        self.assertEqual(stage_uai.get("heavy_max_edge_px"), 200)
        self.assertEqual(stage_uai.get("attack_cooldown_s"), 1.0)
        self.assertEqual(stage_uai.get("light_hits_before_heavy"), 2)
        self.assertEqual(stage_uai.get("zone_width_max_px"), 500)
        self.assertEqual(stage_uai.get("special_roles", {}).get("chilopoda"), "burrow_far_laser_close")
        self.assertEqual(stage_uai.get("special_roles", {}).get("flight"), "hover_no_chase_ranged_far_melee_close")

    def test_http_server_serves_map_jpg_bezel_png_and_arena_stage_json(self) -> None:
        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), preview_server.PreviewHandler)
        port = httpd.server_address[1]
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/bundles", timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                payload = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(payload["parity"]["ok"])
            self.assertEqual(payload["arena_stage"]["viewport"]["width"], 1920)
            self.assertEqual(payload["arena_stage"]["viewport"]["height"], 1080)

            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/assets/maps/rocky_plateau/rocky-plateau-bg.jpg", timeout=5
            ) as resp:
                self.assertEqual(resp.status, 200)
                self.assertEqual(resp.headers.get("Content-Type"), "image/jpeg")
                self.assertEqual(len(resp.read()), 174816)

            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/preview-assets/phone-frame-landscape-16x9.png", timeout=5
            ) as resp:
                self.assertEqual(resp.status, 200)
                self.assertEqual(resp.headers.get("Content-Type"), "image/png")
                self.assertEqual(len(resp.read()), 44372)

            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/preview-assets/../../AGENTS.md", timeout=5)
            self.assertEqual(ctx.exception.code, 404)
            ctx.exception.close()
        finally:
            httpd.shutdown()
            httpd.server_close()


if __name__ == "__main__":
    unittest.main()
