extends SceneTree

const UtilityAIScript := preload("res://scenes/UtilityAIController.gd")


func fail(msg: String) -> void:
	printerr("[FAIL] " + msg)
	quit(1)


func _init() -> void:
	call_deferred("run_test")


func run_test() -> void:
	if str(ProjectSettings.get_setting("application/run/main_scene", "")) != "res://scenes/ArenaSandbox.tscn":
		fail("project.godot main_scene must be res://scenes/ArenaSandbox.tscn")
		return
	if int(ProjectSettings.get_setting("display/window/size/viewport_width", 0)) != 1920:
		fail("project.godot viewport_width must be 1920")
		return
	if int(ProjectSettings.get_setting("display/window/size/viewport_height", 0)) != 1080:
		fail("project.godot viewport_height must be 1080")
		return
	if str(ProjectSettings.get_setting("display/window/stretch/mode", "")) != "canvas_items":
		fail("project.godot stretch/mode must be canvas_items")
		return
	if str(ProjectSettings.get_setting("display/window/stretch/aspect", "")) != "expand":
		fail("project.godot stretch/aspect must be expand (Owner D1 full-width phones)")
		return
	if str(ProjectSettings.get_setting("display/window/stretch/scale_mode", "")) != "fractional":
		fail("project.godot stretch/scale_mode must default to fractional (Owner D2)")
		return
	if str(ProjectSettings.get_setting("rendering/renderer/rendering_method", "")) != "gl_compatibility":
		fail("project.godot rendering_method must be gl_compatibility (Owner D3)")
		return
	if int(ProjectSettings.get_setting("display/window/handheld/orientation", -1)) != 0:
		fail("project.godot handheld/orientation must be 0 (Landscape)")
		return
	if int(ProjectSettings.get_setting("rendering/textures/canvas_textures/default_texture_filter", -1)) != 0:
		fail("project.godot default_texture_filter must be 0 (Nearest)")
		return

	var loaded_scene: Resource = ResourceLoader.load("res://scenes/ArenaSandbox.tscn")
	if not (loaded_scene is PackedScene):
		fail("Unable to load res://scenes/ArenaSandbox.tscn")
		return
	var packed := loaded_scene as PackedScene

	var arena := packed.instantiate()
	var stationary_entry := {"render_contract": {"locomotion": {"kind": "stationary", "speed_px_per_second": 123.0}}}
	if arena._get_walk_speed_px_per_s(stationary_entry) != 0.0:
		fail("Stationary entry must never fall back to walk speed")
		return
	var stationary_ai := UtilityAIScript.new()
	var stationary_decision := stationary_ai.evaluate({"is_stationary": true, "facing_left": true, "target_x": 9000.0})
	if stationary_decision["intent"] != "idle" or stationary_decision["move_dir"] != 0 or not stationary_decision["desired_face_left"]:
		fail("Stationary AI must idle and preserve facing outside its zone")
		return
	if not arena.has_method("get_stage_metrics"):
		fail("ArenaSandbox script failed to attach cleanly")
		return
	root.add_child(arena)
	await process_frame

	if arena.viewport_width != 1920 or arena.viewport_height != 1080:
		fail("ArenaSandbox viewport mismatch: %sx%s" % [str(arena.viewport_width), str(arena.viewport_height)])
		return
	if arena.show_grid_overlay:
		fail("ArenaSandbox show_grid_overlay must default to false (no yellow/blue boundary lines)")
		return
	var expected_trex_half_w := 187.0 * 1.75 * 0.5
	if arena.ground_y != 840.0 or absf(arena.walkable_min_x - expected_trex_half_w) > 1.0 or absf(arena.walkable_max_x - (1920.0 - expected_trex_half_w)) > 1.0:
		fail("ArenaSandbox gameplay bounds mismatch: ground=%s bounds=[%s,%s]" % [str(arena.ground_y), str(arena.walkable_min_x), str(arena.walkable_max_x)])
		return
	if absf(arena.char_scale - 1.75) > 0.001:
		fail("ArenaSandbox default scale must match t_rex 1.75, got " + str(arena.char_scale))
		return

	var bg_sprite := arena.get_node_or_null("BackgroundLayer/BackgroundSprite") as Sprite2D
	if bg_sprite == null or bg_sprite.texture == null:
		fail("Missing BackgroundSprite texture on ArenaSandbox")
		return
	var rendered_bg_size := bg_sprite.texture.get_size() * bg_sprite.scale
	if absf(rendered_bg_size.x - 1920.0) > 0.5 or absf(rendered_bg_size.y - 1080.0) > 0.5:
		fail("BackgroundSprite does not fill 1920x1080 exactly: " + str(rendered_bg_size))
		return

	# Verify DisplayPolicy D1/D2/D4 across Redmi K70E (2712x1220), 720p (<1080p guard), and 16:9 FHD
	var k70e_frac: Dictionary = arena.apply_device_profile("redmi_k70e")
	if absf(float(k70e_frac.get("visible_logic_size", [0.0, 0.0])[0]) - 2400.7869) > 1.5:
		fail("Redmi K70E horizontal expand width mismatch: " + str(k70e_frac))
		return
	var k70e_visible_w := float(k70e_frac["visible_logic_size"][0])
	var bg_w := bg_sprite.texture.get_size().x * bg_sprite.scale.x
	var view_left := 960.0 - k70e_visible_w * 0.5
	var view_right := 960.0 + k70e_visible_w * 0.5
	if absf(arena.walkable_min_x - (view_left + expected_trex_half_w)) > 1.0 or absf(arena.walkable_max_x - (view_right - expected_trex_half_w)) > 1.0:
		fail("K70E T-rex walkable bounds must fit full visible display width: bounds=[%s,%s] vis=[%s,%s]" % [str(arena.walkable_min_x), str(arena.walkable_max_x), str(view_left), str(view_right)])
		return
	if bg_sprite.position.x > view_left + 1.0 or bg_sprite.position.x + bg_w < 960.0 + k70e_visible_w * 0.5 - 1.0:
		fail("K70E original background fails to cover the full width")
		return
	if arena._bg_left_ext != null and arena._bg_left_ext.visible or arena._bg_right_ext != null and arena._bg_right_ext.visible:
		fail("K70E must show the original image without wing inserts")
		return
	if absf(bg_sprite.scale.x * bg_sprite.texture.get_size().x / 1920.0 - bg_sprite.scale.y * bg_sprite.texture.get_size().y / 1080.0) > 0.001:
		fail("Background cover distorted the original image aspect")
		return
	var ipad_layout: Dictionary = arena.apply_device_profile("ipad_10th")
	var ipad_h := float(ipad_layout["visible_logic_size"][1])
	var view_top := 540.0 - ipad_h * 0.5
	if bg_sprite.position.y > view_top + 1.0:
		fail("iPad has an uncovered strip above the original background")
		return
	if arena._ground_tilemap.get_cell_source_id(Vector2i(0, 11)) != 0:
		fail("iPad ground tiles do not reach the bottom of the expanded view")
		return
	var k70e_int: Dictionary = arena.set_pixel_perfect_enabled(true, Vector2i(2712, 1220), Rect2i(96, 0, 2568, 1184))
	if not bool(k70e_int.get("pixel_perfect_applied", false)) or absf(float(k70e_int.get("effective_scale", 0.0)) - 1.0) > 0.001:
		fail("Redmi K70E Pixel Perfect toggle must clamp scale to 1.0: " + str(k70e_int))
		return
	var hd720_guard: Dictionary = arena.set_pixel_perfect_enabled(true, Vector2i(1600, 720), Rect2i(52, 0, 1516, 696))
	if bool(hd720_guard.get("pixel_perfect_applied", true)) or not bool(hd720_guard.get("below_1080p_guard", false)):
		fail("720p (<1080px height) must guard against integer clipping and retain fractional: " + str(hd720_guard))
		return
	arena.set_pixel_perfect_enabled(false, Vector2i(1920, 1080))

	var stage_metrics_check: Dictionary = arena.get_stage_metrics()
	if str(stage_metrics_check.get("stretch_aspect", "")) != "expand" or str(stage_metrics_check.get("renderer", "")) != "gl_compatibility":
		fail("get_stage_metrics() missing D1/D3 display telemetry: " + str(stage_metrics_check))
		return

	if arena.roster_characters.size() != 11:
		fail("Expected 11 finalized characters including Floating Camera, got " + str(arena.roster_characters.size()))
		return

	for entry in arena.roster_characters:
		var cid := str(entry.get("character_id", ""))
		if not arena.select_character(cid):
			fail("ArenaSandbox failed to instantiate character: " + cid)
			return
		await process_frame
		if arena.player_node == null or arena.dummy_node == null:
			fail("Missing spawned player/dummy for " + cid)
			return
		var loc: Dictionary = entry.get("render_contract", {}).get("locomotion", {})
		var loc_kind := str(loc.get("kind", "ground"))
		var expected_scale := float(loc.get("default_scale", 2.0))
		var expected_y := float(loc.get("flight_default_y", 250.0)) if loc_kind == "flight" else 840.0
		if arena.player_node.position != Vector2(560.0, expected_y) or arena.dummy_node.position != Vector2(1360.0, expected_y):
			fail("Wrong spawn coordinates for %s: player=%s dummy=%s (expected y=%s)" % [cid, str(arena.player_node.position), str(arena.dummy_node.position), str(expected_y)])
			return
		if loc_kind == "flight":
			arena.step_flight_vertical(-1.0, 10.0)
			if arena.player_node.position.y != arena.fly_min_y:
				fail("Flight ceiling clamp failed for %s: got %s" % [cid, str(arena.player_node.position.y)])
				return
			arena.step_flight_vertical(1.0, 10.0)
			if arena.player_node.position.y != arena.ground_y:
				fail("Flight ground clamp failed for %s: got %s" % [cid, str(arena.player_node.position.y)])
				return
		if arena.player_node.scale != Vector2(expected_scale, expected_scale) or arena.dummy_node.scale != Vector2(-expected_scale, expected_scale):
			fail("Wrong calibrated Nearest scale %s for %s: player=%s dummy=%s" % [str(expected_scale), cid, str(arena.player_node.scale), str(arena.dummy_node.scale)])
			return
		var spr := arena.player_node.get_node_or_null("Sprite") as AnimatedSprite2D
		if spr == null or spr.texture_filter != CanvasItem.TEXTURE_FILTER_NEAREST or spr.centered:
			fail("Character Sprite filter/centered contract failed for " + cid)
			return
		var anchor_arr: Array = entry.get("map_sync_metrics", {}).get("foot_anchor_px", [])
		if anchor_arr.size() == 2:
			var expected_off := Vector2(-float(anchor_arr[0]), -float(anchor_arr[1]))
			if spr.offset != expected_off:
				fail("Offset mismatch for %s: %s != %s" % [cid, str(spr.offset), str(expected_off)])
				return

	# Idle-only stationary character uses the live 60Hz engine clock without AI movement.
	if not arena.select_character("bat_chiroptera"):
		fail("Bat must spawn for reverse-direction action test")
		return
	var bat_sprite := arena.player_node.get_node("Sprite") as AnimatedSprite2D
	if not arena._request_player_action("attack_light") or not arena._is_player_action_playing():
		fail("Player skill must remain active while the movement loop runs")
		return
	bat_sprite.play(&"idle")
	if not arena.player_node.set_facing_left(true):
		fail("Bat right-to-left turn failed")
		return
	if not arena._request_player_action("power_up") or str(arena.player_node.get_meta(&"_arena_queued_action", "")) != "power_up":
		fail("Skill pressed during reverse turn must queue")
		return
	arena.player_node._on_skill_finished(&"turn")
	if not arena.player_node.scale.x < 0.0:
		fail("Bat reverse turn did not commit left facing")
		return
	var queued := str(arena.player_node.get_meta(&"_arena_queued_action", ""))
	arena.player_node.remove_meta(&"_arena_queued_action")
	if not arena._request_player_action(queued) or str(bat_sprite.animation) != "power_up":
		fail("Queued skill failed after reverse turn")
		return
	if not arena.player_node.set_facing_left(false):
		fail("Bat left-to-right turn failed")
		return
	arena.player_node._on_skill_finished(&"turn")
	if arena.player_node.scale.x < 0.0:
		fail("Bat turn did not commit right facing")
		return
	if not arena.select_character("chilopoda"):
		fail("Chilopoda must spawn for no-jump test")
		return
	var before_jump_y: float = arena.player_node.position.y
	arena._on_touch_action("jump")
	if arena.player_vy != 0.0 or arena.player_node.position.y != before_jump_y:
		fail("Monster without jump clip must not jump")
		return
	if not arena.select_character("tasmanian_king_crab") or not arena._request_player_action("attack_light"):
		fail("Crab light button must resolve its authored attack_nomal clip")
		return
	var crab_sprite := arena.player_node.get_node("Sprite") as AnimatedSprite2D
	if crab_sprite.animation != &"attack_nomal":
		fail("Crab light button played wrong clip")
		return

	# Idle-only stationary character uses the live 60Hz engine clock without AI movement.
	arena.select_character("shenron")
	await process_frame
	var shenron_sprite := arena.player_node.get_node("Sprite") as AnimatedSprite2D
	var stationary_pos: Vector2 = arena.dummy_node.position
	arena.set_utility_ai_enabled(true)
	for tick in range(100):
		var decision: Dictionary = arena.step_utility_ai(1.0 / 60.0)
		if decision.get("intent", "") != "idle" or arena.dummy_node.position != stationary_pos:
			fail("Shenron stationary AI moved or attacked")
			return
	var seen_idle_frames := {}
	for tick in range(105):
		seen_idle_frames[shenron_sprite.frame] = true
		await physics_frame
	if seen_idle_frames.size() != 8 or shenron_sprite.animation != &"idle":
		fail("Shenron must play all eight idle poses on the Godot clock")
		return
	arena.set_utility_ai_enabled(false)

	# Verify runtime scale switching (including fractional 1.5x Nearest) preserves anchor & filter
	arena.select_character("t_rex")
	await process_frame
	arena.set_character_scale(1.5)
	if arena.player_node.scale != Vector2(1.5, 1.5) or arena.dummy_node.scale != Vector2(-1.5, 1.5):
		fail("Fractional scale 1.5x toggle failed")
		return
	arena.set_character_scale(3.0)
	if arena.player_node.scale != Vector2(3.0, 3.0) or arena.dummy_node.scale != Vector2(-3.0, 3.0):
		fail("Scale 3x toggle failed")
		return
	arena.set_character_scale(1.0)
	if arena.player_node.scale != Vector2(1.0, 1.0) or arena.dummy_node.scale != Vector2(-1.0, 1.0):
		fail("Scale 1x toggle failed")
		return
	arena.set_character_scale(2.0)

	# --- Utility AI Contract Verification (Shared 1:1 with arena-stage.json & Web) ---
	# 1) Pure body-edge distance verification
	var r_a: Rect2 = UtilityAIScript.compute_body_rect(1000.0, 840.0, 100.0, 100.0, 1.0)
	var r_b: Rect2 = UtilityAIScript.compute_body_rect(1140.0, 840.0, 100.0, 100.0, 1.0)
	if absf(UtilityAIScript.compute_edge_distance(r_a, r_b) - 40.0) > 0.01:
		fail("Expected body edge gap 40.0, got " + str(UtilityAIScript.compute_edge_distance(r_a, r_b)))
		return

	# 2) T-Rex heavy combo: Patrol -> Chase [50,200) -> Light1 -> 1s -> Light2 -> 1s -> Heavy (<200) -> Far >=200 PowerUp
	arena.select_character("t_rex")
	await process_frame
	arena.set_utility_ai_enabled(true)
	if arena.ai_controller.zone_max_x - arena.ai_controller.zone_min_x > 500.0:
		fail("Utility AI zone exceeds 500px")
		return
	var d_out: Dictionary = arena.step_utility_ai(0.016)
	if d_out.get("intent", "") != "patrol":
		fail("Expected patrol outside zone, got " + str(d_out))
		return
	# Move player inside zone at mid-range (~130px gap)
	arena.dummy_node.position.x = 1360.0
	arena.player_node.position = Vector2(1010.0, 840.0) # out of zone still (<1120) -> put inside zone
	arena.player_node.position = Vector2(1130.0, 840.0) # 1360 - 1130 = 230px center; t_rex bw=186*2=372? Let's place dummy at 1560 and player at 1130 or exact rects
	arena.ai_controller.reset_zone(1360.0, arena.walkable_min_x, arena.walkable_max_x)
	arena.dummy_node.position.x = 1520.0
	arena.player_node.position.x = 1130.0 # within [1120, 1600]; edge gap = 390 - 372 = 18px? Use direct controller + sandbox check
	# Wait: T-Rex body width at 2x is 186*2=372px! To test exact [50,200) and >=200 inside zone cleanly, temporarily use 1x scale!
	arena.set_character_scale(1.0)
	arena.dummy_node.position = Vector2(1500.0, 840.0)
	arena.player_node.position = Vector2(1200.0, 840.0) # edge gap = 300 - 186 = 114px in [50, 200)
	var d_chase: Dictionary = arena.step_utility_ai(0.016)
	if d_chase.get("intent", "") != "chase":
		fail("Expected chase at 114px edge gap, got " + str(d_chase))
		return

	# Close range (< 50px edge gap): Light 1 -> Cool -> Light 2 -> Cool -> Heavy (< 200px)
	arena.player_node.position = Vector2(1285.0, 840.0) # center gap 215 - 186 = 29px < 50
	var d_l1: Dictionary = arena.step_utility_ai(0.016)
	if d_l1.get("attack_clip", "") != "attack_light" or arena.ai_controller.light_chain_count != 1:
		fail("Expected Light 1, got " + str(d_l1))
		return
	# Advance past animation + 1s cooldown
	for _i in range(70):
		arena.step_utility_ai(1.0 / 60.0)
	# Ensure next trigger after cooldown fires Light 2 (or already fired inside loop -> chain == 2 or heavy cycled!)
	# Reset deterministically so each beat is asserted right on transition:
	arena.set_utility_ai_enabled(true)
	arena.dummy_node.position = Vector2(1500.0, 840.0)
	arena.player_node.position = Vector2(1285.0, 840.0)
	var b1: Dictionary = arena.step_utility_ai(0.016)
	if b1.get("attack_clip", "") != "attack_light":
		fail("Combo step 1 expected attack_light, got " + str(b1))
		return
	var b_cool: Dictionary = arena.step_utility_ai(0.016)
	if b_cool.get("intent", "") != "busy":
		fail("Combo step 1 immediate next frame must be busy, got " + str(b_cool))
		return
	arena._ai_action_clip = ""
	arena._ai_action_timer_s = 0.0
	arena.ai_controller.cooldown_remaining = 0.0
	var b2: Dictionary = arena.step_utility_ai(0.016)
	if b2.get("attack_clip", "") != "attack_light" or arena.ai_controller.light_chain_count != 2:
		fail("Combo step 2 expected attack_light chain=2, got " + str(b2))
		return
	arena._ai_action_clip = ""
	arena._ai_action_timer_s = 0.0
	arena.ai_controller.cooldown_remaining = 0.0
	arena.player_node.position = Vector2(1210.0, 840.0) # within zone [1120,1600], 290 - 186 = 104px (<200px, heavy follow-up valid!)
	var b3: Dictionary = arena.step_utility_ai(0.016)
	if b3.get("attack_clip", "") != "attack_heavy" or arena.ai_controller.light_chain_count != 0:
		fail("Combo step 3 (<200px after 2 lights) expected attack_heavy & reset, got " + str(b3))
		return

	# After 2 lights, target runs >= 200px inside zone -> PowerUp & resets light_chain_count!
	arena.set_utility_ai_enabled(true)
	arena.dummy_node.position = Vector2(1550.0, 840.0)
	arena.player_node.position = Vector2(1335.0, 840.0)
	arena.step_utility_ai(0.016)
	arena._ai_action_clip = ""; arena._ai_action_timer_s = 0.0; arena.ai_controller.cooldown_remaining = 0.0
	arena.step_utility_ai(0.016) # chain == 2
	arena._ai_action_clip = ""; arena._ai_action_timer_s = 0.0; arena.ai_controller.cooldown_remaining = 0.0
	arena.player_node.position = Vector2(1140.0, 840.0) # gap = 410 - 186 = 224px >= 200px inside zone [1120, 1600]
	var b_far: Dictionary = arena.step_utility_ai(0.016)
	if b_far.get("attack_clip", "") != "power_up" or arena.ai_controller.light_chain_count != 0:
		fail("Expected power_up and chain reset when target runs >=200px, got " + str(b_far))
		return

	# 3) Dilophosaurus has no attack_heavy -> stays on attack_light after 2 lights
	arena.select_character("dilophosaurus")
	await process_frame
	arena.set_character_scale(1.0)
	arena.set_utility_ai_enabled(true)
	arena.dummy_node.position = Vector2(1500.0, 840.0)
	arena.player_node.position = Vector2(1330.0, 840.0)
	arena.ai_controller.light_chain_count = 2
	var d_noheavy: Dictionary = arena.step_utility_ai(0.016)
	if d_noheavy.get("attack_clip", "") != "attack_light":
		fail("Non-heavy monster must fire attack_light instead of heavy, got " + str(d_noheavy))
		return

	# 4) Flying mob (bat_chiroptera): hover y=340, no chase at >=50px (fires power_up), close melee <50px fires attack_light
	arena.select_character("bat_chiroptera")
	await process_frame
	arena.set_character_scale(1.0)
	arena.set_utility_ai_enabled(true)
	if absf(arena.dummy_node.position.y - 250.0) > 0.5:
		fail("Flying enemy must spawn at fly_default_y=250, got " + str(arena.dummy_node.position.y))
		return
	arena.player_node.position = Vector2(1160.0, 840.0) # in zone horizontally, far in air-to-ground height -> ranged power_up
	var f_far: Dictionary = arena.step_utility_ai(0.016)
	if f_far.get("attack_clip", "") != "power_up" or int(f_far.get("move_dir", 9)) != 0:
		fail("Flying enemy at >=50px must not chase and must use power_up, got " + str(f_far))
		return
	arena._ai_action_clip = ""; arena._ai_action_timer_s = 0.0; arena.ai_controller.cooldown_remaining = 0.0
	arena.player_node.position = Vector2(1340.0, 250.0) # close in air (<50px) -> attack_light
	var f_close: Dictionary = arena.step_utility_ai(0.016)
	if f_close.get("attack_clip", "") != "attack_light":
		fail("Flying enemy at <50px must use attack_light, got " + str(f_close))
		return

	# 5) Chilopoda special rule: <50px -> power_up (laser), >=50px -> attack_light (burrow)
	arena.select_character("chilopoda")
	await process_frame
	arena.set_character_scale(1.0)
	arena.set_utility_ai_enabled(true)
	arena.dummy_node.position = Vector2(1500.0, 840.0)
	arena.player_node.position = Vector2(1330.0, 840.0) # close (<50px gap since bw=160 -> 170-160=10px)
	var c_close: Dictionary = arena.step_utility_ai(0.016)
	if c_close.get("attack_clip", "") != "power_up":
		fail("Chilopoda close (<50px) must fire power_up laser, got " + str(c_close))
		return
	arena._ai_action_clip = ""; arena._ai_action_timer_s = 0.0; arena.ai_controller.cooldown_remaining = 0.0
	arena.player_node.position = Vector2(1200.0, 840.0) # far (300-160=140px >= 50px)
	var c_far: Dictionary = arena.step_utility_ai(0.016)
	if c_far.get("attack_clip", "") != "attack_light":
		fail("Chilopoda >=50px must fire attack_light burrow, got " + str(c_far))
		return

	# 6) Tasmanian King Crab unlocked horizontal flip (no turn clip): faces enemy behind it before power_up
	arena.select_character("tasmanian_king_crab")
	await process_frame
	arena.set_character_scale(2.0)
	arena.set_utility_ai_enabled(true)
	if arena.dummy_node.scale.x >= 0.0:
		fail("Crab enemy should spawn facing left (-X) toward player, got scale.x=" + str(arena.dummy_node.scale.x))
		return
	# Player moves behind Crab inside zone [1120..1600] on +X side (edge gap 204px >= 200) -> Crab flips right (+X) and casts power_up
	arena.dummy_node.position = Vector2(1125.0, 840.0)
	arena.player_node.position = Vector2(1595.0, 840.0)
	var crab_behind_r: Dictionary = arena.step_utility_ai(0.016)
	if crab_behind_r.get("intent", "") != "attack" or crab_behind_r.get("attack_clip", "") != "power_up" or arena.dummy_node.scale.x <= 0.0:
		fail("Crab must flip right (+X) toward behind enemy before power_up, got res=%s scale.x=%s" % [str(crab_behind_r), str(arena.dummy_node.scale.x)])
		return
	# Now move Player behind Crab again inside zone on -X side (edge gap 202px >= 200) -> Crab flips left (-X) before attacking
	arena._ai_action_clip = ""; arena._ai_action_timer_s = 0.0; arena.ai_controller.cooldown_remaining = 0.0
	arena.dummy_node.position = Vector2(1590.0, 840.0)
	arena.player_node.position = Vector2(1122.0, 840.0)
	var crab_behind_l: Dictionary = arena.step_utility_ai(0.016)
	if crab_behind_l.get("intent", "") != "attack" or crab_behind_l.get("attack_clip", "") != "power_up" or arena.dummy_node.scale.x >= 0.0:
		fail("Crab must flip left (-X) toward behind enemy before power_up, got res=%s scale.x=%s" % [str(crab_behind_l), str(arena.dummy_node.scale.x)])
		return

	# Calibrated walk speeds, non-turn instant flip burst, and smooth walk->turn->walk mid-stride resume
	var expected_screen_speeds := {
		"chilopoda": 140.0,
		"bat_chiroptera": 115.0,
		"spinosaurus": 170.0,
		"t_rex": 120.0,
		"pteranodon": 140.0,
		"tasmanian_king_crab": 115.0,
		"sarcosuchus": 135.0,
		"dilophosaurus": 155.0,
		"drum": 140.0,
	}
	for cid in expected_screen_speeds.keys():
		arena.select_character(cid)
		var entry: Dictionary = arena._find_character_entry(cid)
		var spd: float = arena._get_walk_speed_px_per_s(entry)
		if absf(spd - float(expected_screen_speeds[cid])) > 0.2:
			fail("Calibrated screen speed mismatch for %s: got %f, expected %f (char_scale=%f)" % [cid, spd, float(expected_screen_speeds[cid]), arena.char_scale])
			return
	var ptero_entry: Dictionary = arena._find_character_entry("pteranodon")
	var crab_entry: Dictionary = arena._find_character_entry("tasmanian_king_crab")
	if absf(arena._get_turn_speed_multiplier(ptero_entry) - 1.2) > 0.001 or absf(arena._get_turn_speed_multiplier(crab_entry) - 1.3) > 0.001:
		fail("Instant-turn burst multiplier mismatch for pteranodon/crab")
		return
	if arena._turn_momentum_factor(0.02, 0.25, 1, -1) <= 0.0 or arena._turn_momentum_factor(0.22, 0.25, 1, -1) >= 0.0:
		fail("Turnaround momentum curve did not transition smoothly from +dir to -dir")
		return
	arena.select_character("bat_chiroptera")
	arena.player_node.play_clip(&"walk")
	arena.player_node.set_meta("_arena_turn_resume_clip", "walk")
	if not arena.player_node.move_in_direction(-1, &"walk") or not arena.player_node.is_turning():
		fail("Bat walk->turn did not trigger cleanly")
		return
	arena.player_node._on_skill_finished(&"turn")
	if arena.player_node.sprite.animation != &"walk" or arena.player_node.sprite.frame < 1:
		fail("Bat turn->walk stalled instead of resuming mid-stride: clip=%s frame=%d" % [str(arena.player_node.sprite.animation), arena.player_node.sprite.frame])
		return

	# 7) Drum AI: idle outside zone / >=400px; teleport (~50px) 50..200px; continuous attack_light every 0.2s <=50px;
	# power_up (11-frame Row 3 prep + Row 4-5 orb at frame 10) in 200..400px; walk clip present; no attack_heavy.
	arena.select_character("drum")
	await process_frame
	if absf(arena.char_scale - 2.5) > 0.001 or absf(arena.enemy_scale - 2.5) > 0.001:
		fail("Drum finalized default_scale must be 2.5, got char=%s enemy=%s" % [str(arena.char_scale), str(arena.enemy_scale)])
		return
	arena.set_utility_ai_enabled(true)
	if not arena.dummy_node.call(&"has_clip", "walk") or arena.dummy_node.call(&"has_clip", "attack_heavy"):
		fail("Drum must include bipedal walk clip and must NOT have separate attack_heavy")
		return
	arena.dummy_node.position = Vector2(1360.0, 840.0)
	arena.player_node.position = Vector2(560.0, 840.0)
	var drum_out: Dictionary = arena.step_utility_ai(1.0 / 60.0)
	if drum_out.get("intent", "") != "idle" or int(drum_out.get("move_dir", 9)) != 0:
		fail("Drum outside zone must remain stationary idle (never patrol), got " + str(drum_out))
		return
	# Enter zone [1120..1600] in 50..200px band -> triggers teleport (~50px) -> attack_light
	arena.player_node.position = Vector2(1150.0, 840.0)
	var drum_tp: Dictionary = arena.step_utility_ai(1.0 / 60.0)
	if drum_tp.get("intent", "") != "attack" or drum_tp.get("attack_clip", "") != "teleport":
		fail("Drum on 50..200px entry must trigger teleport, got " + str(drum_tp))
		return
	for _i in range(15):
		arena.step_utility_ai(1.0 / 60.0)
	var tp_edge_dist: float = absf(arena.dummy_node.position.x - arena.player_node.position.x) - ((56.0 * 2.5 + 56.0 * 2.5) * 0.5)
	if absf(tp_edge_dist - 50.0) > 6.0:
		fail("Drum teleport must land ~50px edge gap from target, got gap=" + str(tp_edge_dist))
		return
	var saw_light := false
	for _i in range(10):
		var d_step: Dictionary = arena.step_utility_ai(1.0 / 60.0)
		if d_step.get("attack_clip", "") == "attack_light":
			saw_light = true
			break
	if not saw_light:
		fail("Drum after teleport must immediately unleash attack_light (Row 2)")
		return
	# Complete first attack_light (~24 ticks = 0.4s), verify 0.2s cooldown before second continuous attack_light <= 50px
	for _i in range(26):
		arena.step_utility_ai(1.0 / 60.0)
	var light_cd_wait: Dictionary = arena.step_utility_ai(1.0 / 60.0)
	if light_cd_wait.get("attack_clip", "") == "attack_light":
		fail("Drum must wait 0.2s cooldown between continuous attack_light strikes")
		return
	var saw_second_light := false
	for _i in range(16):
		var d2: Dictionary = arena.step_utility_ai(1.0 / 60.0)
		if d2.get("attack_clip", "") == "attack_light":
			saw_second_light = true
			break
	if not saw_second_light:
		fail("Drum <=50px must strike attack_light continuously every 0.2s")
		return
	# Target retreats beyond melee into 200 < edge_dist < 400 -> power_up (11-frame Row 3+4+5 -> orb at frame 10)
	arena._ai_action_clip = ""; arena._ai_action_timer_s = 0.0; arena.ai_controller.cooldown_remaining = 0.0
	arena._enemy_orb_active = false; arena._enemy_orb_spawned_for_cast = false
	arena.dummy_node.position = Vector2(1360.0, 840.0)
	arena.player_node.position = Vector2(960.0, 840.0) # center gap=400, half-widths=112 -> edge_dist=288 in (200, 400)
	var pu_d: Dictionary = arena.step_utility_ai(1.0 / 60.0)
	if pu_d.get("intent", "") != "attack" or pu_d.get("attack_clip", "") != "power_up":
		fail("Drum at 200<edge_dist<400 must cast power_up, got " + str(pu_d))
		return
	var saw_drum_orb := false
	for _i in range(55):
		arena.step_utility_ai(1.0 / 60.0)
		if arena._enemy_orb_active:
			saw_drum_orb = true
			break
	if not saw_drum_orb:
		fail("Drum power_up release frame 10 must spawn independent electric_orb_fx projectile")
		return
	# Retreat >= 400px -> returns to stationary idle
	arena._ai_action_clip = ""; arena._ai_action_timer_s = 0.0; arena.ai_controller.cooldown_remaining = 0.0
	arena.player_node.position = Vector2(800.0, 840.0) # edge_dist = 448 >= 400
	var drum_far_idle: Dictionary = arena.step_utility_ai(1.0 / 60.0)
	if drum_far_idle.get("intent", "") != "idle" or int(drum_far_idle.get("move_dir", 9)) != 0:
		fail("Drum >=400px must return to stationary idle, got " + str(drum_far_idle))
		return

	# Verify Rocky Plateau Original JPG Backdrop + 1 Horizontal 32x32 TileMapLayer + Contact Shadow + Ground Dust FX (0 floating platforms)
	var metrics_ter: Dictionary = arena.get_stage_metrics()
	if not bool(metrics_ter.get("terrain_loaded", false)) or int(metrics_ter.get("platforms_count", -1)) != 0:
		fail("Terrain config & 0 floating platforms must load in ArenaSandbox: " + str(metrics_ter))
		return
	if arena.get_node_or_null("TerrainLayer/GroundTileMap") == null:
		fail("Missing TerrainLayer/GroundTileMap TileMapLayer node")
		return
	var bg_layer_node := arena.get_node_or_null("BackgroundLayer") as CanvasItem
	if bg_layer_node == null or not bg_layer_node.visible:
		fail("Original JPG BackgroundLayer must remain visible behind 1 horizontal ground tile ledge")
		return
	arena.select_character("t_rex")
	arena.player_node.position = Vector2(512.0, 840.0)
	arena.player_vy = 0.0
	var jump_res: Dictionary = arena.step_player_vertical_physics(1.0 / 60.0, true, false)
	if not bool(jump_res.get("jumped", false)) or arena._active_dust_fx.size() < 1:
		fail("Jump from ground must spawn pixel ground dust FX")
		return
	var peak_y := 840.0
	var landed_ground := false
	for _t in range(90):
		var st: Dictionary = arena.step_player_vertical_physics(1.0 / 60.0, false, false)
		peak_y = minf(peak_y, float(st.get("y", 840.0)))
		if _t > 5 and bool(st.get("on_ground", false)) and absf(float(st.get("y", 0.0)) - 840.0) < 0.5:
			landed_ground = true
			break
	if peak_y >= 760.0 or not landed_ground:
		fail("Player must arc above ground and land back on horizontal floor ground_y=840, peak=" + str(peak_y) + " y=" + str(arena.player_node.position.y))
		return
	var sh_on_ground: Dictionary = arena.compute_contact_shadow_params(512.0, 840.0, 56.0, true)
	var sh_in_air: Dictionary = arena.compute_contact_shadow_params(512.0, 700.0, 56.0, true)
	if float(sh_in_air["half_w"]) >= float(sh_on_ground["half_w"]):
		fail("Contact shadow must shrink with height above horizontal ground floor")
		return

	# Verify T-rex power_up spawns ProjectileFX (fireball_fx) synchronized with engine-export.json (origin [304,138] - anchor [176,224])
	arena.select_character("t_rex")
	await process_frame
	var trex_node: Node2D = arena.player_node
	var trex_pfx := trex_node.get_node_or_null("ProjectileFX") as AnimatedSprite2D
	if trex_pfx == null:
		fail("T-rex prefab must expose ProjectileFX for power_up fireball_fx")
		return
	if trex_pfx.visible or trex_pfx.position != Vector2(128.0, -86.0) or trex_pfx.offset != Vector2(-176.0, -128.0):
		fail("T-rex ProjectileFX geometry mismatch: vis=%s pos=%s offset=%s" % [str(trex_pfx.visible), str(trex_pfx.position), str(trex_pfx.offset)])
		return
	if not arena._request_player_action("power_up"):
		fail("T-rex player power_up request must succeed")
		return
	var trex_saw_fireball := false
	var trex_fireball_hid := false
	for _t in range(60):
		await physics_frame
		arena.step_player_movement(1.0 / 60.0, 0)
		if trex_pfx.visible and trex_pfx.animation == &"fireball_fx":
			trex_saw_fireball = true
		elif trex_saw_fireball and not trex_pfx.visible:
			trex_fireball_hid = true
			break
	if not trex_saw_fireball or not trex_fireball_hid:
		fail("T-rex power_up must emit fireball_fx on hit event and hide after finishing: saw=%s hid=%s" % [str(trex_saw_fireball), str(trex_fireball_hid)])
		return

	# Verify Drum Player can walk, turn cleanly without bool(null) crash, attack_light, power_up orb, and teleport
	arena.select_character("drum")
	await process_frame
	var drum_player: Node2D = arena.player_node
	if arena._is_fighter_turning(drum_player):
		fail("Drum player must report _is_fighter_turning == false")
		return
	var drum_x0 := drum_player.position.x
	for _t in range(10):
		arena.step_player_movement(1.0 / 60.0, 1)
	if drum_player.position.x <= drum_x0 + 10.0:
		fail("Drum player must walk right cleanly: x0=%s x1=%s" % [str(drum_x0), str(drum_player.position.x)])
		return
	var drum_peak_x := drum_player.position.x
	for _t in range(10):
		arena.step_player_movement(1.0 / 60.0, -1)
	if drum_player.position.x >= drum_peak_x - 10.0 or not arena.player_facing_left:
		fail("Drum player must walk left and flip cleanly: peak=%s x2=%s left=%s" % [str(drum_peak_x), str(drum_player.position.x), str(arena.player_facing_left)])
		return
	for _t in range(2):
		arena.step_player_movement(1.0 / 60.0, 0)
	if not arena._request_player_action("attack_light"):
		fail("Drum player attack_light must succeed")
		return
	var drum_spr := drum_player.get_node("Sprite") as AnimatedSprite2D
	if drum_spr.animation != &"attack_light":
		fail("Drum player Sprite must play attack_light, got " + str(drum_spr.animation))
		return
	for _t in range(45):
		await physics_frame
		arena.step_player_movement(1.0 / 60.0, 0)
		if not arena._is_player_action_playing():
			break
	if not arena._request_player_action("power_up"):
		fail("Drum player power_up must succeed")
		return
	var drum_cfx := drum_player.get_node_or_null("ChargeFX") as AnimatedSprite2D
	var drum_pfx := drum_player.get_node_or_null("ProjectileFX") as AnimatedSprite2D
	if drum_cfx == null or not drum_cfx.visible:
		fail("Drum player power_up must activate ChargeFX")
		return
	var drum_saw_orb := false
	var drum_orb_moved := false
	var orb_start_x := 0.0
	for _t in range(70):
		await physics_frame
		arena.step_player_movement(1.0 / 60.0, 0)
		if drum_pfx != null and drum_pfx.visible:
			if not drum_saw_orb:
				drum_saw_orb = true
				orb_start_x = drum_pfx.position.x
			elif absf(drum_pfx.position.x - orb_start_x) > 20.0:
				drum_orb_moved = true
				break
	if not drum_saw_orb or not drum_orb_moved:
		fail("Drum player power_up must release moving electric_orb_fx: saw=%s moved=%s" % [str(drum_saw_orb), str(drum_orb_moved)])
		return
	for _t in range(30):
		await physics_frame
		arena.step_player_movement(1.0 / 60.0, 0)
		if not arena._is_player_action_playing():
			break
	# Test Drum player teleport dash
	arena.step_player_movement(1.0 / 60.0, 1)
	drum_player.position.x = 500.0
	if not arena._request_player_action("teleport"):
		fail("Drum player teleport must succeed")
		return
	var tp_start_x := drum_player.position.x
	for _t in range(35):
		await physics_frame
		arena.step_player_movement(1.0 / 60.0, 0)
	if drum_player.position.x <= tp_start_x + 150.0:
		fail("Drum player teleport must relocate +120*char_scale forward: start=%s end=%s" % [str(tp_start_x), str(drum_player.position.x)])
		return
	# Verify Drum on K70E can walk all the way near visible edges [-240..+2160] without stopping at 140..1780
	var k70e_drum_layout: Dictionary = arena.apply_device_profile("redmi_k70e")
	var k70e_drum_vis_w := float(k70e_drum_layout.get("visible_logic_size", [2400.7869, 1080.0])[0])
	var drum_half_w := 56.0 * 2.5 * 0.5
	var exp_drum_min := (960.0 - k70e_drum_vis_w * 0.5) + drum_half_w
	var exp_drum_max := (960.0 + k70e_drum_vis_w * 0.5) - drum_half_w
	if absf(arena.walkable_min_x - exp_drum_min) > 1.0 or absf(arena.walkable_max_x - exp_drum_max) > 1.0:
		fail("K70E Drum walkable bounds mismatch: got=[%s,%s] exp=[%s,%s]" % [str(arena.walkable_min_x), str(arena.walkable_max_x), str(exp_drum_min), str(exp_drum_max)])
		return
	drum_player.position.x = 50.0
	for _t in range(180):
		arena.step_player_movement(1.0 / 60.0, -1)
	if drum_player.position.x >= -150.0 or absf(drum_player.position.x - arena.walkable_min_x) > 1.0:
		fail("K70E Drum must walk past old 140px wall right up to body-edge visible left bound: x=%s min=%s" % [str(drum_player.position.x), str(arena.walkable_min_x)])
		return
	drum_player.position.x = 1850.0
	for _t in range(180):
		arena.step_player_movement(1.0 / 60.0, 1)
	if drum_player.position.x <= 2050.0 or absf(drum_player.position.x - arena.walkable_max_x) > 1.0:
		fail("K70E Drum must walk past old 1780px wall right up to body-edge visible right bound: x=%s max=%s" % [str(drum_player.position.x), str(arena.walkable_max_x)])
		return
	arena.set_pixel_perfect_enabled(false, Vector2i(1920, 1080))

	# Verify Floating Camera 70x74 seamless idle<->walk phase continuity + ranged AI attack_light + projectile
	if not arena.select_character("floating_camera"):
		fail("Floating Camera must select in ArenaSandbox")
		return
	await process_frame
	var fc_dims: Vector2i = arena._get_body_dims(arena._find_character_entry_ro("floating_camera"))
	if fc_dims != Vector2i(70, 74):
		fail("Floating Camera body_only_bbox_px must be 70x74, got " + str(fc_dims))
		return
	var fc_spr := arena.player_node.get_node_or_null("Sprite") as AnimatedSprite2D
	arena.step_player_movement(1.0 / 60.0, 1)
	if fc_spr.animation != &"walk":
		fail("Floating Camera must enter walk when moving, got " + str(fc_spr.animation))
		return
	fc_spr.set_frame_and_progress(4, 0.35)
	arena.step_player_movement(1.0 / 60.0, 0)
	if fc_spr.animation != &"idle" or fc_spr.frame != 4:
		fail("Floating Camera stopping walk->idle must preserve phase frame=4 seamlessly, got anim=%s frame=%d" % [str(fc_spr.animation), fc_spr.frame])
		return
	arena.step_player_movement(1.0 / 60.0, 1)
	if fc_spr.animation != &"walk" or fc_spr.frame != 4:
		fail("Floating Camera resuming idle->walk must preserve phase frame=4 seamlessly, got anim=%s frame=%d" % [str(fc_spr.animation), fc_spr.frame])
		return
	arena.select_enemy_character("floating_camera", true)
	arena.set_utility_ai_enabled(true)
	arena.dummy_node.position = Vector2(1500.0, 300.0)
	arena.player_node.position = Vector2(1200.0, 300.0)
	var fc_ai_res: Dictionary = arena.step_utility_ai(1.0 / 60.0)
	if fc_ai_res.get("attack_clip", "") != "attack_light" or arena._ai_action_clip != "attack_light":
		fail("Floating Camera flying AI at >=50px without power_up must fire attack_light, got " + str(fc_ai_res))
		return
	arena.set_utility_ai_enabled(false)

	# Smoke test Player movement + power_up across every character in roster without script errors
	for ch_entry in arena.roster_characters:
		if not (ch_entry is Dictionary):
			continue
		var cid_smoke := str(ch_entry.get("character_id", ""))
		if cid_smoke.is_empty():
			continue
		arena.select_character(cid_smoke)
		await process_frame
		arena.step_player_movement(1.0 / 60.0, 1)
		if arena._has_clip_name(arena.player_node, &"power_up"):
			if not arena._request_player_action("power_up"):
				fail("Roster player power_up failed for " + cid_smoke)
				return

	var verified_roster_count: int = arena.roster_characters.size()
	arena.queue_free()
	await process_frame
	print("[OK] Godot 4 ArenaSandbox 1920x1080 1:1 parity + Utility AI + %d characters PASSED!" % verified_roster_count)
	quit(0)
