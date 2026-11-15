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
	if str(ProjectSettings.get_setting("display/window/stretch/aspect", "")) != "keep":
		fail("project.godot stretch/aspect must be keep")
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
	if not arena.has_method("get_stage_metrics"):
		fail("ArenaSandbox script failed to attach cleanly")
		return
	root.add_child(arena)
	await process_frame

	if arena.viewport_width != 1920 or arena.viewport_height != 1080:
		fail("ArenaSandbox viewport mismatch: %sx%s" % [str(arena.viewport_width), str(arena.viewport_height)])
		return
	if arena.ground_y != 840.0 or arena.walkable_min_x != 140.0 or arena.walkable_max_x != 1780.0:
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

	if arena.roster_characters.size() != 8:
		fail("Expected 8 characters in roster.json, got " + str(arena.roster_characters.size()))
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
		var expected_y := 250.0 if loc_kind == "flight" else 840.0
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

	arena.queue_free()
	await process_frame
	print("[OK] Godot 4 ArenaSandbox 1920x1080 1:1 parity + Utility AI + 8/8 characters PASSED!")
	quit(0)
