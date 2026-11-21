extends SceneTree

const UtilityAIScript := preload("res://scenes/UtilityAIController.gd")
const OverheadBarsDrawScript := preload("res://scenes/runtime/OverheadBarsDraw.gd")


func fail(msg: String) -> void:
	printerr("[FAIL] " + msg)
	quit(1)


func _init() -> void:
	call_deferred("run_test")


func run_test() -> void:
	if str(ProjectSettings.get_setting("application/run/main_scene", "")) != "res://scenes/AppStartup.tscn":
		fail("project.godot main_scene must be res://scenes/AppStartup.tscn")
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
	if arena == null or not arena.has_method("_get_walk_speed_px_per_s"):
		fail("ArenaSandbox failed to load script cleanly")
		return
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
	if arena.ground_y != 840.0 or absf(arena.walkable_min_x - (-240.0 + expected_trex_half_w)) > 1.0 or absf(arena.walkable_max_x - (6360.0 - expected_trex_half_w)) > 1.0:
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
	if absf(rendered_bg_size.x - 6600.0) > 0.5 or absf(rendered_bg_size.y - 1350.0) > 0.5:
		fail("Extended BackgroundSprite size mismatch: " + str(rendered_bg_size))
		return
	var terrain_body := arena.get_node_or_null("TerrainLayer/GroundFloorCollider") as StaticBody2D
	if terrain_body == null or terrain_body.get_child_count() != 5 or arena._ground_tilemap == null or arena._ground_tilemap.visible:
		fail("Review terrain must use five solid step colliders and no foreground tile overlay")
		return
	var foreground := arena.get_node_or_null("ReviewForegroundTrees") as Node2D
	var map_layer := arena.get_node_or_null("BackgroundLayer") as Node2D
	if foreground == null or foreground.get_child_count() != 3 or map_layer == null or not (map_layer.z_index < foreground.z_index and foreground.z_index < 0):
		fail("Review extension needs exactly three trees between map and fighters")
		return
	var expected_tree_min_h := [900.0, 1060.0, 1080.0]
	var expected_tree_bottom_y := [828.0, 888.0, 954.0]
	for tree_i in range(3):
		var tree_sprite := foreground.get_child(tree_i) as Sprite2D
		if tree_sprite == null or tree_sprite.texture.get_size().y < float(expected_tree_min_h[tree_i]):
			fail("Tree %d must include full planted roots and +30%% canopy (h >= %s)" % [tree_i, str(expected_tree_min_h[tree_i])])
			return
		var visual_bottom := tree_sprite.position.y + tree_sprite.texture.get_size().y * tree_sprite.scale.y
		if absf(visual_bottom - float(expected_tree_bottom_y[tree_i])) > 14.0:
			fail("Tree %d roots must plant into the rear ground rim near y=%s, got %s" % [tree_i, str(expected_tree_bottom_y[tree_i]), str(visual_bottom)])
			return
		if tree_i == 0 and (tree_sprite.position.x + 264.51 * tree_sprite.scale.x) >= arena.STEP_THREE_X:
			fail("First tree must stand on the left upper plateau before Step 3 cliff cut, trunk_x=%s" % str(tree_sprite.position.x + 264.51 * tree_sprite.scale.x))
			return
		var tree_left := tree_sprite.position.x
		var tree_right := tree_sprite.position.x + tree_sprite.texture.get_size().x * tree_sprite.scale.x
		if tree_left < arena.MAP_LEFT_X or tree_right > arena.MAP_RIGHT_X:
			fail("Tree %d canopy must fit inside map world bounds [%s, %s]: [%s, %s]" % [tree_i, str(arena.MAP_LEFT_X), str(arena.MAP_RIGHT_X), str(tree_left), str(tree_right)])
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
	if absf(arena.walkable_min_x - (-240.0 + expected_trex_half_w)) > 1.0 or absf(arena.walkable_max_x - (6360.0 - expected_trex_half_w)) > 1.0:
		fail("K70E T-rex world bounds mismatch: bounds=[%s,%s]" % [str(arena.walkable_min_x), str(arena.walkable_max_x)])
		return
	var camera := arena.get_node_or_null("ArenaCamera") as Camera2D
	if camera == null or arena.player_node == null:
		fail("Extended map requires player and Camera2D")
		return
	var original_player_x: float = float(arena.player_node.position.x)
	arena.player_node.position.x = 2800.0
	arena._update_follow_camera()
	if absf(camera.position.x - 2800.0) > 1.0 or absf(arena._ground_y_at(2800.0) - 840.0) > 0.1:
		fail("Camera must follow player through the flat map join")
		return
	if absf(arena._ground_y_at(3200.0) - 890.0) > 0.1:
		fail("Middle plateau (platform 2) must use walkable floor y=890")
		return
	if absf(arena._ground_y_at(4200.0) - 945.0) > 0.1:
		fail("Existing third plateau must retain shared world ground height y=945")
		return
	if absf(arena._ground_y_at(5200.0) - 975.0) > 0.1 or absf(arena._ground_y_at(6000.0) - 1030.0) > 0.1:
		fail("New descending plateaus must use walkable floor heights y=975 and y=1030")
		return
	if arena._can_cross_terrain_step(4741.0, 4739.0, 975.0) or not arena._can_cross_terrain_step(4741.0, 4739.0, 940.0):
		fail("Third step must block uphill walking and allow a high jump")
		return
	if not arena.terrain_blocks_segment(Vector2(5567.0, 1010.0), Vector2(5553.0, 1010.0)):
		fail("Skill projectile must hit the fourth step face")
		return
	for edge_case in [[4740.0, 945.0, 975.0], [5560.0, 975.0, 1030.0]]:
		var step_edge := float(edge_case[0])
		var upper_y := float(edge_case[1])
		var lower_y := float(edge_case[2])
		arena.player_node.position = Vector2(step_edge - 1.0, upper_y)
		arena.player_vy = 0.0
		arena._move_player_horizontal(2.0)
		var fall_result: Dictionary = arena.step_player_vertical_physics(1.0 / 60.0, false, false)
		if arena.player_node.position.x <= step_edge or float(fall_result["y"]) <= upper_y or float(fall_result["support_y"]) != lower_y:
			fail("Actor must fall on first tick beyond painted step edge %s: x=%s y=%s" % [str(step_edge), str(arena.player_node.position.x), str(fall_result["y"])])
			return
	if arena._can_cross_terrain_step(3696.0, 3694.0, 945.0) or not arena._can_cross_terrain_step(3696.0, 3694.0, 885.0):
		fail("Walking uphill must be blocked until the player jumps above the upper surface")
		return
	if not arena._can_cross_terrain_step(3694.0, 3696.0, 890.0):
		fail("Walking downhill must allow an automatic drop")
		return
	if not arena.terrain_blocks_segment(Vector2(3708.0, 940.0), Vector2(3682.0, 940.0)):
		fail("A skill projectile must hit the vertical step face")
		return
	arena.player_node.position = Vector2(2849.0, 840.0)
	arena.player_vy = 0.0
	arena._move_player_horizontal(3.0)
	for _fall_tick in range(30):
		arena.step_player_vertical_physics(1.0 / 60.0, false, false)
	if absf(arena.player_node.position.y - 890.0) > 1.0:
		fail("Walking off the first step must fall to the lower floor y=890")
		return
	arena._move_player_horizontal(-3.0)
	if arena.player_node.position.x < 2876.0:
		fail("Lower floor must block walking uphill before penetrating cliff base")
		return
	arena.step_player_vertical_physics(1.0 / 60.0, true, false)
	for _jump_tick in range(8):
		arena.step_player_vertical_physics(1.0 / 60.0, false, false)
	arena._move_player_horizontal(-40.0)
	if arena.player_node.position.x >= 2850.0:
		fail("A high enough jump must allow crossing back onto the upper floor")
		return
	# Verify Drum walking left against Step 4 & Step 3 painted cliff walls stops BEFORE entering the rock cut, and can still walk-jump up Step 4.
	arena.select_character("drum")
	await process_frame
	arena.player_node.position = Vector2(5720.0, 1030.0)
	arena.player_vy = 0.0
	for _wl in range(90):
		arena.step_player_movement(1.0 / 60.0, -1, 0, false, false, false, Vector2.ZERO)
	if arena.player_node.position.x < 5620.0:
		fail("Drum walking left against Step 4 cliff wall must stop cleanly outside cliff cut (>=5620), got x=%s" % str(arena.player_node.position.x))
		return
	for _wj in range(42):
		arena.step_player_movement(1.0 / 60.0, -1, 0, _wj == 0, false, false, Vector2.ZERO)
	if arena.player_node.position.x >= 5560.0 or arena.player_node.position.y > 980.0:
		fail("Drum must still be able to jump from Step 4 cliff stop onto upper floor, got pos=%s" % str(arena.player_node.position))
		return
	arena.player_node.position = Vector2(4910.0, 975.0)
	arena.player_vy = 0.0
	for _wl3 in range(90):
		arena.step_player_movement(1.0 / 60.0, -1, 0, false, false, false, Vector2.ZERO)
	if arena.player_node.position.x < 4815.0:
		fail("Drum walking left against Step 3 cliff wall must stop cleanly outside cliff cut (>=4815), got x=%s" % str(arena.player_node.position.x))
		return
	arena.select_character("t_rex")
	await process_frame
	arena.player_vy = 0.0
	arena.player_node.position.x = original_player_x
	arena._update_follow_camera()
	arena.player_node.position = Vector2(4200.0, 945.0)
	arena._update_follow_camera()
	arena._on_summon_button_pressed()
	if not arena.shenron_summon.active or absf(arena.shenron_summon.global_position.x + 960.0 - camera.position.x) > 1.0 or absf(arena.shenron_summon.global_position.y - 105.0) > 1.0:
		fail("Shenron ritual must center on the current camera and local ground")
		return
	arena.shenron_summon.dismiss()
	arena.player_node.position = Vector2(original_player_x, 840.0)
	arena._update_follow_camera()
	if bg_sprite.position.x > view_left + 1.0 or bg_sprite.position.x + bg_w < 960.0 + k70e_visible_w * 0.5 - 1.0:
		fail("K70E original background fails to cover the full width")
		return
	if arena._bg_left_ext != null and arena._bg_left_ext.visible or arena._bg_right_ext != null and arena._bg_right_ext.visible:
		fail("K70E must show the original image without wing inserts")
		return
	if absf(bg_sprite.scale.x * bg_sprite.texture.get_size().x / 6600.0 - bg_sprite.scale.y * bg_sprite.texture.get_size().y / 1350.0) > 0.001:
		fail("Extended background distorted the map aspect")
		return
	# Verify camera framing + zero uncovered strips + pan across ALL device profiles (including iPad & tall/wide screens)
	var bg_h := bg_sprite.texture.get_size().y * bg_sprite.scale.y
	var profiles_doc: Dictionary = load("res://scenes/runtime/DisplayPolicy.gd").load_device_profiles()
	for prof in profiles_doc.get("profiles", []):
		if not (prof is Dictionary):
			continue
		var pid_prof := str(prof.get("id", ""))
		for pp_mode in [false, true]:
			arena.pixel_perfect_enabled = pp_mode
			var prof_layout: Dictionary = arena.apply_device_profile(pid_prof)
			var vis_arr: Array = prof_layout.get("visible_logic_size", [1920.0, 1080.0])
			var eff_vis := Vector2(float(vis_arr[0]), float(vis_arr[1])) / camera.zoom
			if absf(camera.zoom.x - camera.zoom.y) > 0.0001:
				fail("Camera zoom must remain uniform on %s (pp=%s): %s" % [pid_prof, str(pp_mode), str(camera.zoom)])
				return
			for test_px in [-120.0, 2160.0, 4440.0]:
				arena.player_node.position = Vector2(test_px, arena._ground_y_at(test_px))
				arena._update_follow_camera()
				var c_left := camera.position.x - eff_vis.x * 0.5
				var c_right := camera.position.x + eff_vis.x * 0.5
				var c_top := camera.position.y - eff_vis.y * 0.5
				var c_bot := camera.position.y + eff_vis.y * 0.5
				if bg_sprite.position.x > c_left + 0.5 or bg_sprite.position.x + bg_w < c_right - 0.5 or bg_sprite.position.y > c_top + 0.5 or bg_sprite.position.y + bg_h < c_bot - 0.5:
					fail("Device %s (pp=%s) uncovered area at px=%s: cam=[%s..%s, %s..%s] bg=[%s..%s, %s..%s]" % [pid_prof, str(pp_mode), str(test_px), str(c_left), str(c_right), str(c_top), str(c_bot), str(bg_sprite.position.x), str(bg_sprite.position.x + bg_w), str(bg_sprite.position.y), str(bg_sprite.position.y + bg_h)])
					return
	# Also test giant/tall hypothetical viewport (e.g. 2732x2048 iPad Pro & 3840x2160 4K)
	for extra_sz in [Vector2i(2732, 2048), Vector2i(3840, 2160), Vector2i(3440, 1440)]:
		var ex_layout: Dictionary = arena.set_pixel_perfect_enabled(false, extra_sz)
		var ex_vis := Vector2(float(ex_layout["visible_logic_size"][0]), float(ex_layout["visible_logic_size"][1])) / camera.zoom
		arena.player_node.position = Vector2(3300.0, arena._ground_y_at(3300.0))
		arena._update_follow_camera()
		var ex_top := camera.position.y - ex_vis.y * 0.5
		var ex_bot := camera.position.y + ex_vis.y * 0.5
		if bg_sprite.position.y > ex_top + 0.5 or bg_sprite.position.y + bg_h < ex_bot - 0.5:
			fail("Large viewport %s left uncovered vertical area: top=%s bot=%s" % [str(extra_sz), str(ex_top), str(ex_bot)])
			return
	arena.pixel_perfect_enabled = false
	arena.apply_device_profile("ipad_10th")
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

	var finalized_count := 0
	for _re in arena.roster_characters:
		if _re is Dictionary and str(_re.get("faction", "")) != "review_demo" and str(_re.get("status", "")) != "human_test_pending":
			finalized_count += 1
	if finalized_count != 12:
		fail("Expected 12 finalized characters including Floating Camera and Son Goku, got " + str(finalized_count) + " (total=" + str(arena.roster_characters.size()) + ")")
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

	# 5) Chilopoda fires at <50 px and burrows at >=50 px.
	arena.select_character("chilopoda")
	await process_frame
	arena.set_character_scale(1.0)
	arena.set_utility_ai_enabled(true)
	arena.dummy_node.position = Vector2(1500.0, 840.0)
	arena.player_node.position = Vector2(1330.0, 840.0) # close (<50px gap since bw=160 -> 170-160=10px)
	var c_close: Dictionary = arena.step_utility_ai(0.016)
	if c_close.get("attack_clip", "") != "power_up":
		fail("Chilopoda close (<50px) must fire power_up, got " + str(c_close))
		return
	arena._ai_action_clip = ""; arena._ai_action_timer_s = 0.0; arena.ai_controller.cooldown_remaining = 0.0
	arena.player_node.position = Vector2(1200.0, 840.0) # far (300-160=140px >= 50px)
	var c_far: Dictionary = arena.step_utility_ai(0.016)
	if c_far.get("attack_clip", "") != "attack_light":
		fail("Chilopoda >=50px must use attack_light burrow, got " + str(c_far))
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
	var exp_drum_min := -240.0 + drum_half_w
	var exp_drum_max := 6360.0 - drum_half_w
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
	if drum_player.position.x <= 2050.0:
		fail("K70E Drum must walk past original screen right edge: x=%s" % str(drum_player.position.x))
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

	# Verify step-edge immediate drop, uphill blocking, AI step handling, and flight floor across ALL ground/flying archetypes
	for step_cid in ["drum", "t_rex", "spinosaurus", "chilopoda", "tasmanian_king_crab", "sarcosuchus", "dilophosaurus"]:
		arena.select_character(step_cid)
		await process_frame
		# 1. Walk off Step 1 (2850, 840 -> 890): must start falling on the VERY FIRST frame past edge!
		arena.player_node.position = Vector2(2848.0, 840.0)
		arena.player_vy = 0.0
		var fell_immediately := false
		for _t in range(12):
			arena.step_player_movement(1.0 / 60.0, 1)
			if arena.player_node.position.x >= 2850.0:
				if arena.player_node.position.y > 840.0:
					fell_immediately = true
				else:
					fail("%s hovered at step 1 edge x=%s y=%s" % [step_cid, str(arena.player_node.position.x), str(arena.player_node.position.y)])
					return
				break
		if not fell_immediately:
			fail("%s failed to step off and begin falling at step 1" % step_cid)
			return
		# Continue falling to Step 2 floor (890), then walk off Step 2 (3695 -> 945)
		for _t in range(40):
			arena.step_player_movement(1.0 / 60.0, 0)
		if absf(arena.player_node.position.y - 890.0) > 1.0:
			fail("%s did not land on Step 2 floor y=890, got y=%s" % [step_cid, str(arena.player_node.position.y)])
			return
		# Walking back left uphill into Step 1 wall must be blocked
		arena.player_node.position = Vector2(2880.0, 890.0)
		for _t in range(25):
			arena.step_player_movement(1.0 / 60.0, -1)
		if arena.player_node.position.x < 2850.0:
			fail("%s walked uphill through Step 1 wall to x=%s" % [step_cid, str(arena.player_node.position.x)])
			return
		# Walk off Step 2 (3695) -> must start falling immediately and land on y=945 (including after turning right)
		arena.player_node.position = Vector2(3693.0, 890.0)
		arena.player_vy = 0.0
		var fell_step2 := false
		for _t in range(120):
			await physics_frame
			arena.step_player_movement(1.0 / 60.0, 1)
			if arena.player_node.position.x >= 3695.0:
				if arena.player_node.position.y > 890.0:
					fell_step2 = true
				else:
					fail("%s hovered at step 2 edge x=%s y=%s" % [step_cid, str(arena.player_node.position.x), str(arena.player_node.position.y)])
					return
				break
		if not fell_step2:
			fail("%s failed to begin falling at step 2 (x=%s y=%s turning=%s)" % [step_cid, str(arena.player_node.position.x), str(arena.player_node.position.y), str(arena._is_fighter_turning(arena.player_node))])
			return
		for _t in range(45):
			arena.step_player_movement(1.0 / 60.0, 0)
		if absf(arena.player_node.position.y - 945.0) > 1.0:
			fail("%s did not land on Step 3 floor y=945, got y=%s" % [step_cid, str(arena.player_node.position.y)])
			return
	# Verify Drum teleport cannot tunnel uphill through Step 1 wall and falls if teleporting off Step 1
	arena.select_character("drum")
	await process_frame
	arena.step_player_movement(1.0 / 60.0, -1)
	arena.player_node.position = Vector2(2900.0, 890.0)
	arena._request_player_action("teleport")
	for _t in range(30):
		await physics_frame
		arena.step_player_movement(1.0 / 60.0, 0)
	if arena.player_node.position.x < 2850.0:
		fail("Drum teleport must be blocked by Step 1 cliff wall, got x=%s" % str(arena.player_node.position.x))
		return
	# Verify AI (Utility AI) across step edges: chasing downhill drops to y=890; chasing uphill stops at Step 1 wall
	arena.select_character("t_rex")
	await process_frame
	arena.select_enemy_character("spinosaurus", true)
	await process_frame
	arena.set_utility_ai_enabled(true)
	arena.ai_controller.reset_zone(3050.0, 2600.0, 3400.0)
	arena.dummy_node.position = Vector2(2842.0, 840.0)
	arena.enemy_vy = 0.0
	arena.player_node.position = Vector2(3270.0, 890.0)
	for _t in range(45):
		await physics_frame
		arena.step_utility_ai(1.0 / 60.0)
	if arena.dummy_node.position.x < 2850.0 or absf(arena.dummy_node.position.y - 890.0) > 1.0:
		fail("AI chasing downhill off Step 1 must drop cleanly to y=890, got " + str(arena.dummy_node.position))
		return
	arena.player_node.position = Vector2(2700.0, 840.0)
	for _t in range(30):
		await physics_frame
		arena.step_utility_ai(1.0 / 60.0)
	if arena.dummy_node.position.x < 2850.0:
		fail("AI chasing uphill from Step 2 must be blocked by Step 1 cliff wall, got " + str(arena.dummy_node.position))
		return
	arena.set_utility_ai_enabled(false)

	# Verify flying characters descend to lower step floor y=945 cleanly
	arena.select_character("floating_camera")
	await process_frame
	arena.player_node.position = Vector2(4100.0, 840.0)
	arena.step_flight_vertical(1.0, 5.0)
	if absf(arena.player_node.position.y - 945.0) > 0.5:
		fail("Flying character over Step 3 must descend to local floor y=945, got " + str(arena.player_node.position.y))
		return

	# Verify PixelRulerModal 1:1 world PX measurements across devices (FHD, K70E, iPad); ruler_button removed from Sân Tập HUD (Owner v10.6)
	if arena.ruler_button != null or arena.ruler_modal == null or arena.ruler_modal_visible:
		fail("Ruler button must be removed from Sân Tập HUD and hidden PixelRulerModal must initialize cleanly")
		return
	arena.select_character("drum")
	await process_frame
	arena.set_ruler_modal_visible(true)
	if not arena.ruler_modal_visible or not arena.ruler_modal.visible:
		fail("set_ruler_modal_visible(true) must open PixelRulerModal")
		return
	arena.player_node.position = Vector2(360.0, 840.0)
	arena.dummy_node.position = Vector2(1360.0, 840.0)
	var rm_k70e: Dictionary = {}
	arena.apply_device_profile("redmi_k70e")
	rm_k70e = arena.measure_player_enemy_distance()
	if absf(float(rm_k70e.get("dx_world_px", 0.0)) - 1000.0) > 0.5 or absf(float(rm_k70e.get("player_enemy_edge_gap", 0.0)) - 860.0) > 0.5:
		fail("Ruler K70E Drum 360<->1360 measurement mismatch: " + str(rm_k70e))
		return
	arena.apply_device_profile("ipad_10th")
	var rm_ipad: Dictionary = arena.measure_player_enemy_distance()
	if absf(float(rm_ipad.get("dx_world_px", 0.0)) - 1000.0) > 0.5 or absf(float(rm_ipad.get("player_enemy_edge_gap", 0.0)) - 860.0) > 0.5:
		fail("Ruler iPad Drum 360<->1360 must stay 1:1 world PX invariant: " + str(rm_ipad))
		return
	arena.set_ruler_modal_visible(false)
	arena.set_pixel_perfect_enabled(false, Vector2i(1920, 1080))

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

	# Field Mode verification: 7 ground + 7 flying monsters, Stamina/3s Mini-Stun, Drum Hero, Homing Orbs, 7s Respawns, Dragon Ball drops, Pointer & Pad Bindings
	arena.enable_field_mode(true, false)
	await process_frame
	var fm = arena.field_manager
	if fm == null or not fm.active or fm.slots.size() != 14:
		fail("Field mode must spawn 14 monster slots (7 ground + 7 flying)")
		return
	if arena.player_node != null or fm.player_spawned:
		fail("Hero Drum must start hidden when entering field mode")
		return
	var exp_ids := ["chilopoda", "spinosaurus", "tasmanian_king_crab", "t_rex", "sarcosuchus", "dilophosaurus", "spinosaurus", "bat_chiroptera", "pteranodon", "floating_camera", "bat_chiroptera", "pteranodon", "floating_camera", "bat_chiroptera"]
	var exp_hps := [1300.0, 1500.0, 1300.0, 1800.0, 1500.0, 1300.0, 1500.0, 900.0, 1000.0, 800.0, 900.0, 1000.0, 800.0, 900.0]
	for si in range(14):
		var s: Dictionary = fm.slots[si]
		if str(s["character_id"]) != exp_ids[si] or absf(float(s["max_hp"]) - exp_hps[si]) > 0.1:
			fail("Slot %d mismatch: got %s HP=%s, expected %s HP=%s" % [si, str(s["character_id"]), str(s["max_hp"]), exp_ids[si], str(exp_hps[si])])
			return

	# Spawn Drum explicitly for legacy Drum PowerUp orb + 1500 HP test
	arena.set_field_hero_visible(true, "drum")
	await process_frame
	if arena.player_node == null or not fm.player_spawned or absf(arena.player_node.position.x - (arena.walkable_min_x + 24.0)) > 2.0:
		fail("Drum must spawn at far left end of map")
		return
	if absf(fm.player_hp - 1500.0) > 0.1 or absf(fm.player_mana) > 0.1:
		fail("Drum must start at 1500 HP and 0 Mana")
		return

	# Drum melee deals 200 dmg, adds +20 Mana, reduces monster Stamina by 20 without HIT while Stamina > 0; breaks at 0 for 3s mini-stun
	var slot0: Dictionary = fm.slots[0]
	var m0 := slot0["node"] as Node2D
	arena.player_node.position = Vector2(m0.position.x - 40.0, m0.position.y)
	arena.player_facing_left = false
	arena.player_node.scale = Vector2(arena.char_scale, arena.char_scale)
	fm.pointer_kind = "enemy"
	fm.pointer_slot_id = str(slot0["id"])
	fm.apply_damage_to_slot(slot0, 200.0, 20.0)
	if absf(float(slot0["hp"]) - 1100.0) > 0.1 or absf(float(slot0["stamina"]) - 80.0) > 0.1 or float(slot0["stun_timer_s"]) > 0.0:
		fail("First hit must reduce HP 1300->1100 and Stamina 100->80 without mini-stun")
		return
	var m0_spr := m0.get_node_or_null("Sprite") as AnimatedSprite2D
	if m0_spr != null and m0_spr.animation == &"hit":
		fail("Monster must NOT play hit while Stamina > 0")
		return
	# 4 more stamina breaks -> 0 Stamina -> 3.0s attack-lock + 1 HIT clip per hit!
	for _k in range(4):
		fm.apply_damage_to_slot(slot0, 50.0, 20.0)
	if float(slot0["stamina"]) > 0.1 or absf(float(slot0["stun_timer_s"]) - 3.0) > 0.15 or float(slot0.get("hit_anim_timer_s", 0.0)) <= 0.0:
		fail("5th stamina hit must break poise to 0, start 3.0s stun lock, and trigger 1 HIT clip")
		return
	if m0_spr != null and m0_spr.animation != &"hit":
		fail("Monster must immediately play HIT animation when receiving damage with broken stamina, anim=%s" % str(m0_spr.animation))
		return
	# Wait past 1 hit clip (~0.8s = 50 frames) without attacking -> monster must resume normal movement (NOT stuck in hit), while still attack-locked!
	for _s1 in range(54):
		await physics_frame
		fm.step(1.0 / 60.0)
	if float(slot0.get("hit_anim_timer_s", 0.0)) > 0.0 or float(slot0["stun_timer_s"]) <= 0.5:
		fail("Single HIT clip must finish before 3.0s stun lock expires (hit_t=%s stun_t=%s)" % [str(slot0.get("hit_anim_timer_s", 0.0)), str(slot0["stun_timer_s"])])
		return
	if m0_spr != null and m0_spr.animation == &"hit":
		fail("When unattacked after single HIT clip ends, monster must move/idle normally instead of looping hit")
		return
	if not str(slot0.get("action_clip", "")).is_empty():
		fail("Broken-stamina monster must remain locked from attacking back during 3s window")
		return
	# Hitting once more while stamina broken triggers 1 more HIT clip and resets 3s lock (1 hit = 1 hit anim)
	fm.apply_damage_to_slot(slot0, 50.0, 20.0)
	if float(slot0.get("hit_anim_timer_s", 0.0)) <= 0.0 or (m0_spr != null and m0_spr.animation != &"hit"):
		fail("Follow-up hit during broken stamina must trigger 1 HIT clip")
		return
	# Step remaining 3.1s without hitting -> stun expires and Stamina refills to 100
	for _s2 in range(190):
		await physics_frame
		fm.step(1.0 / 60.0)
	if float(slot0["stun_timer_s"]) > 0.0 or absf(float(slot0["stamina"]) - 100.0) > 0.1:
		fail("Monster Stamina must refill to 100 after 3s attack-lock ends without hits")
		return

	# Check 100 Mana requirement for PowerUp orb (+50% speed = 1170 px/s) + homing 400 dmg + default powerup explosion (-20% scale = 0.68)
	fm.player_mana = 80.0
	if fm.request_player_power_up():
		fail("Drum power_up must fail when Mana < 100")
		return
	fm.player_mana = 100.0
	if not fm.request_player_power_up() or absf(fm.player_mana) > 0.1:
		fail("Drum power_up must succeed and consume 100 Mana")
		return
	fm._explosion_nodes.clear()
	fm.call("_spawn_homing_projectile", arena.player_node, "drum", "electric_orb_fx", arena.player_node.position, 2.5, slot0, true, 400.0, 20.0)
	if fm.homing_projectiles.is_empty() or absf(float(fm.homing_projectiles[fm.homing_projectiles.size() - 1]["speed"]) - 1170.0) > 1.0:
		fail("Drum skill projectile speed must be +50%% (1170 px/s)")
		return
	var pre_m0_hp: float = float(slot0["hp"])
	for _dp in range(180):
		fm.step(1.0 / 60.0)
		if float(slot0["hp"]) < pre_m0_hp - 0.1:
			break
	if float(slot0["hp"]) >= pre_m0_hp - 0.1 or fm._explosion_nodes.is_empty():
		fail("Drum power_up projectile must hit target and spawn default powerup explosion (exp=%d)" % fm._explosion_nodes.size())
		return
	var drum_exp := fm._explosion_nodes[0] as AnimatedSprite2D
	if drum_exp == null or absf(drum_exp.scale.x - 0.68) > 0.03:
		fail("Default explosion scale must be 0.68 (-20%% from 0.85), got %s" % (str(drum_exp.scale.x) if drum_exp != null else "null"))
		return
	fm.homing_projectiles.clear()
	fm._explosion_nodes.clear()
	# Test enemy projectile hitting Drum: subtracts HP, flashes Drum, and spawns small powerup explosion FX!
	var fcam_slot: Dictionary = fm.slots[9] # floating_camera (800 HP, 80 dmg)
	var pre_hp: float = float(fm.player_hp)
	fm._explosion_nodes.clear()
	fm.call("_spawn_homing_projectile", fcam_slot["node"], "floating_camera", "projectile_fx", Vector2(2000.0, 260.0), 1.8, {}, false, 80.0, 0.0)
	arena.player_node.position = Vector2(2620.0, 840.0)
	for _p in range(240):
		fm.step(1.0 / 60.0)
		if float(fm.player_hp) < pre_hp - 0.1:
			break
	if absf(fm.player_hp - (pre_hp - 80.0)) > 0.1 or float(fm.player_hit_flash_s) <= 0.0 or fm._explosion_nodes.is_empty():
		fail("Enemy projectile must hit Drum for 80 dmg (hp=%s->%s), trigger player hit flash (flash=%s), and spawn powerup explosion FX (exp=%d, proj=%d)" % [str(pre_hp), str(fm.player_hp), str(fm.player_hit_flash_s), fm._explosion_nodes.size(), fm.homing_projectiles.size()])
		return
	var d_spr := arena.player_node.get_node_or_null("Sprite") as AnimatedSprite2D
	if d_spr != null and d_spr.animation == &"hit":
		fail("Hero Drum must NEVER play HIT stagger animation")
		return

	# Hero Immortal & Monster Attack Range overlay toggles
	arena.set_show_monster_ranges(true)
	if not arena.show_monster_ranges_enabled or not bool(fm.show_monster_ranges):
		fail("set_show_monster_ranges(true) must enable monster range overlay")
		return
	arena.set_show_monster_ranges(false)

	var hp_before_imm: float = float(fm.player_hp)
	arena.set_hero_immortal(true)
	fm.apply_damage_to_player(5000.0)
	if fm.player_dead or absf(float(fm.player_hp) - hp_before_imm) > 0.1:
		fail("Immortal mode must prevent player HP loss and KO")
		return
	arena.set_hero_immortal(false)

	# Player 0 HP KO + 3s respawn at far left with 1500 HP
	fm.apply_damage_to_player(2000.0)
	if not fm.player_dead or fm.player_hp > 0.0:
		fail("Drum at 0 HP must enter KO state")
		return
	for _r in range(190):
		fm.step(1.0 / 60.0)
	if fm.player_dead or absf(fm.player_hp - 1500.0) > 0.1 or absf(arena.player_node.position.x - (arena.walkable_min_x + 24.0)) > 2.0:
		fail("Drum must respawn at far left with 1500 HP after 3s KO")
		return

	# 30%-gated Weighted Dragon Ball drops (gate < 30% -> roll star across 30/20/10/5/2/0.5/0.1) & Top Layer z_index == 50 + 1s unlock + pointer cycle
	var drop_cases := [
		[0.0, 0.0, 7],
		[15.0, 35.0, 6],
		[29.9, 55.0, 5],
		[10.0, 62.0, 4],
		[5.0, 66.0, 3],
		[1.0, 67.2, 2],
		[20.0, 67.55, 1],
		[30.0, 0.0, 0],
		[45.0, 10.0, 0],
		[80.0, 5.0, 0],
	]
	for dc in drop_cases:
		var rolled := int(fm.roll_dragon_ball_number(float(dc[0]), float(dc[1])))
		if rolled != int(dc[2]):
			fail("Dragon Ball roll mismatch at gate=%s star=%s: got %d expected %d" % [str(dc[0]), str(dc[1]), rolled, int(dc[2])])
			return
	var spawned_ball: Node2D = fm.roll_and_spawn_dragon_ball(Vector2(arena.player_node.position.x + 20.0, arena.player_node.position.y), 10.0, 0.0)
	if spawned_ball == null or arena._item_drop_layer.z_index <= arena.fighters_layer.z_index:
		fail("Dropped Dragon Ball layer z_index must exceed FightersLayer z_index")
		return
	if fm.call("_can_pickup_item", spawned_ball):
		fail("Dropped item must not be pickable before 1.0s drop completion")
		return
	for _b in range(66):
		arena.step_dropped_items(1.0 / 60.0)
		fm.step(1.0 / 60.0)
	if not fm.call("_can_pickup_item", spawned_ball):
		fail("Dropped item must become pickable after 1.0s")
		return
	var cyc: Dictionary = fm.cycle_target_pointer()
	if str(cyc.get("kind", "")) == "":
		fail("Target pointer cycle must select a valid candidate")
		return

	# Ground slot death -> 12s respawn with dilophosaurus alternation; flying slot -> bat/pteranodon/camera rotation
	var g_slot: Dictionary = fm.slots[1]
	fm.apply_damage_to_slot(g_slot, 2000.0, 20.0)
	if bool(g_slot["alive"]):
		fail("Ground slot 1 must die cleanly")
		return
	for _rg_early in range(430):
		fm.step(1.0 / 60.0)
	if bool(g_slot["alive"]):
		fail("Ground slot 1 must stay dead at 7.16s now that monster respawn is 12s")
		return
	for _rg in range(300):
		fm.step(1.0 / 60.0)
	if not bool(g_slot["alive"]) or str(g_slot["character_id"]) != "dilophosaurus" or absf(float(g_slot["max_hp"]) - 1300.0) > 0.1:
		fail("First ground respawn must alternate dilophosaurus HP=1300 after 12s, got %s" % str(g_slot.get("character_id", "")))
		return

	# MobileActionPad slot assignment check (no hard lock on 2..7, 1 & 8 locked)
	var pad_test = preload("res://scenes/runtime/MobileActionPad.gd").new()
	arena.add_child(pad_test)
	pad_test.configure_for_character("drum", PackedStringArray(["idle", "walk", "jump", "teleport", "attack_light", "power_up"]), false)
	if pad_test.get_slot_binding(1) != "attack_light" or pad_test.get_slot_binding(4) != "power_up" or pad_test.get_slot_binding(8) != "cycle_target":
		fail("MobileActionPad Drum default slots mismatch")
		return
	pad_test.set_slot_binding(5, "power_up")
	if pad_test.get_slot_binding(5) != "power_up":
		fail("MobileActionPad flexible slot 5 assignment failed")
		return
	if pad_test.safe_root == null or pad_test.find_child("WorldPositionMap", true, false) != null or pad_test.has_method("set_map_progress"):
		fail("WorldPositionMap mini-map must be removed per Owner request")
		return
	var btn1 := pad_test._slot_buttons.get(1) as Button
	var btn8 := pad_test._slot_buttons.get(8) as Button
	if btn1 == null or btn1.get_node_or_null("Visual") == null or btn8 == null or btn8.get_node_or_null("Visual") == null:
		fail("MobileActionPad buttons must attach custom vector visual overlays")
		return
	pad_test.queue_free()

	# Flying monster stability (no rapid left/right flipping in place), elliptical orbit, single 360-deg curved FX, and 360 flight vector
	var bat_slot: Dictionary = fm.slots[7] # bat_chiroptera
	var fcam_s: Dictionary = fm.slots[9] # floating_camera
	var bat_node := bat_slot["node"] as Node2D
	var fcam_node := fcam_s["node"] as Node2D
	var bat_pfx := bat_node.get_node_or_null("ProjectileFX") as Node2D
	if bat_pfx != null and (bat_pfx.scale.length() > 0.01 or bat_pfx.modulate.a > 0.01):
		fail("Field bat must hide legacy prefab ProjectileFX so only 1 FX fires, scale=%s mod=%s" % [str(bat_pfx.scale), str(bat_pfx.modulate)])
		return
	if not bool(fcam_node.get("external_projectile_managed")):
		fail("Field floating_camera must have external_projectile_managed=true")
		return

	bat_slot["cooldown_s"] = 2.0
	bat_slot["action_clip"] = ""
	bat_slot["turn_lock_s"] = 0.0
	bat_slot["orbit_phase"] = 0.8
	bat_node.position = Vector2(float(bat_slot["x_home"]), float(bat_slot["y_home"]))
	fcam_s["cooldown_s"] = 2.0
	fcam_s["action_clip"] = ""
	fcam_s["turn_lock_s"] = 0.0
	arena.player_node.position = Vector2(bat_node.position.x + 140.0, 840.0)
	for _warm in range(30):
		await physics_frame
		fm.step(1.0 / 60.0)
	var bat_flips := 0
	var prev_bat_left := bat_node.scale.x < 0.0
	var bat_min_y := bat_node.position.y
	var bat_max_y := bat_node.position.y
	var bat_min_x := bat_node.position.x
	var bat_max_x := bat_node.position.x
	for _fo in range(55):
		await physics_frame
		fm.step(1.0 / 60.0)
		var now_left := bat_node.scale.x < 0.0
		if now_left != prev_bat_left:
			bat_flips += 1
			prev_bat_left = now_left
		bat_min_y = minf(bat_min_y, bat_node.position.y)
		bat_max_y = maxf(bat_max_y, bat_node.position.y)
		bat_min_x = minf(bat_min_x, bat_node.position.x)
		bat_max_x = maxf(bat_max_x, bat_node.position.x)
	if bat_flips > 1:
		fail("Bat must NOT oscillate/turn repeatedly in place during cooldown aggro, flips=%d" % bat_flips)
		return
	if (bat_max_x - bat_min_x) < 10.0 or (bat_max_y - bat_min_y) < 3.0:
		fail("Flying monster must cruise smoothly along circular/elliptical 2D orbit (dx=%s, dy=%s)" % [str(bat_max_x - bat_min_x), str(bat_max_y - bat_min_y)])
		return

	# Check 360-degree projectile rotation: pointed sonic_screech_fx rotates smoothly toward target; spherical electric_orb_fx stays unrotated
	arena.set_hero_immortal(true)
	fm.homing_projectiles.clear()
	fm.call("_spawn_homing_projectile", bat_node, "bat_chiroptera", "sonic_screech_fx", bat_node.position, 2.0, {}, false, 100.0, 0.0)
	fm.step(1.0 / 60.0)
	if fm.homing_projectiles.is_empty():
		fail("Bat homing sonic_screech_fx must spawn")
		return
	var sonic_fx: AnimatedSprite2D = fm.homing_projectiles[0]["sprite"] as AnimatedSprite2D
	if absf(sonic_fx.rotation) < 0.1:
		fail("Pointed sonic_screech_fx firing downward at Drum must rotate toward 360-deg trajectory, rot=%s" % str(sonic_fx.rotation))
		return
	fm.homing_projectiles.clear()
	fm.call("_spawn_homing_projectile", arena.player_node, "drum", "electric_orb_fx", arena.player_node.position, 2.0, bat_slot, true, 400.0, 20.0)
	fm.step(1.0 / 60.0)
	if fm.homing_projectiles.is_empty():
		fail("Drum homing electric_orb_fx must spawn")
		return
	var orb_fx: AnimatedSprite2D = fm.homing_projectiles[0]["sprite"] as AnimatedSprite2D
	if absf(orb_fx.rotation) > 0.001:
		fail("Spherical electric_orb_fx must remain unrotated (rotation=0)")
		return
	arena.set_hero_immortal(false)

	# Verify exact non-box body silhouette & tâm thân (both Hero and Monsters),
	# calligraphic red "X" target animation, double-tap auto-attack, and Hero > Monster Z-layering!
	var trex_slot2: Dictionary = fm.slots[3] # t_rex (ground)
	var trex_node2 := trex_slot2["node"] as Node2D
	var trex_rect: Rect2 = arena.get_fighter_body_rect(trex_node2, "t_rex", float(trex_slot2["scale_val"]))
	var trex_core: Vector2 = arena.get_fighter_core_world_pos(trex_node2, "t_rex", float(trex_slot2["scale_val"]))
	var drum_core: Vector2 = arena.get_fighter_core_world_pos(arena.player_node, "drum", arena.char_scale)
	if not arena.silhouette_contains_point(trex_node2, "t_rex", float(trex_slot2["scale_val"]), trex_core, 0.0):
		fail("T-rex body silhouette must contain its tâm thân core")
		return
	if not arena.silhouette_contains_point(arena.player_node, "drum", arena.char_scale, drum_core, 0.0):
		fail("Drum body silhouette must contain its tâm thân core")
		return
	# Empty top-left corner of T-rex bounding box (above tail) must NOT count as solid body!
	var empty_corner := Vector2(trex_rect.position.x + 2.0, trex_rect.position.y + 2.0)
	if arena.silhouette_contains_point(trex_node2, "t_rex", float(trex_slot2["scale_val"]), empty_corner, 0.0):
		fail("Empty bounding-box corner above T-rex tail must NOT register as solid body hit")
		return

	# Layer priority: Monster (10) < Hero (20) < Boss (30) and overlapping layers allowed
	if trex_node2.z_index != arena.Z_LAYER_MONSTER or arena.player_node.z_index != arena.Z_LAYER_HERO or arena.player_node.z_index <= trex_node2.z_index:
		fail("Layer priority must place Hero (%d) above Monster (%d)" % [arena.player_node.z_index, trex_node2.z_index])
		return

	# Single tap -> selects T-rex & starts transient calligraphic red "X" animation (0.0 -> 0.28s) that later fades out
	if float(fm.pointer_x_visible_s) > 0.001:
		fail("Calligraphic red X must NOT stay visible before touch interaction")
		return
	var tap_res: Dictionary = fm.select_target_at_world_pos(trex_core)
	if not bool(tap_res.get("selected", false)) or fm.pointer_slot_id != str(trex_slot2["id"]) or float(fm.pointer_x_anim_s) > 0.001 or float(fm.pointer_x_visible_s) <= 0.5:
		fail("Single tap must target T-rex and show transient calligraphic red X, got %s" % str(tap_res))
		return
	# Wait 0.90s without further interaction -> calligraphic X must disappear automatically!
	for _xv in range(54):
		fm.step(1.0 / 60.0)
	if float(fm.pointer_x_visible_s) > 0.001:
		fail("Calligraphic red X must disappear after interaction ends, remaining=%s" % str(fm.pointer_x_visible_s))
		return
	# Re-tap then double-tap 260px away -> shows X again & triggers auto-approach attack!
	fm.select_target_at_world_pos(trex_core)
	for _dt_step in range(8):
		fm.step(1.0 / 60.0)
	var pre_trex_hp: float = float(trex_slot2["hp"])
	arena.player_node.position = Vector2(trex_rect.position.x - 260.0, trex_node2.position.y)
	arena.player_vy = 0.0
	fm.hit_impacts.clear()
	fm.floating_texts.clear()
	var dbl_res: Dictionary = fm.select_target_at_world_pos(trex_core)
	if not bool(dbl_res.get("double_tap_attack", false)) or not bool(fm.auto_approach_active) or float(fm.pointer_x_visible_s) <= 0.5:
		fail("Double-tap on target must show X and start auto-approach attack, got %s" % str(dbl_res))
		return
	for _aa in range(180):
		await physics_frame
		fm.step(1.0 / 60.0)
		if float(trex_slot2["hp"]) < pre_trex_hp:
			break
	if float(trex_slot2["hp"]) >= pre_trex_hp:
		fail("Double-tap auto-approach must walk close to target core and deal melee damage")
		return
	if fm.hit_impacts.is_empty() or fm.floating_texts.is_empty() or float(trex_slot2.get("hit_flash_s", 0.0)) <= 0.0:
		fail("Hit feedback FX (impact burst + damage popup + flash) must trigger on hit")
		return
	# Check -40% hit-flash contrast + +40% brightness lift (Owner human-test 2026-11-19) on monster & hero sprites
	var m_flash_spr := trex_node2.get_node_or_null("Sprite") as AnimatedSprite2D
	if m_flash_spr != null:
		fm.call("_apply_hit_flash_modulate", m_flash_spr, true, true, false)
		var m_on: Color = m_flash_spr.modulate
		fm.call("_apply_hit_flash_modulate", m_flash_spr, true, false, false)
		var m_off: Color = m_flash_spr.modulate
		if m_on.g < 0.65 or m_on.r < 1.0 or m_on.r > 1.36 or m_off.g < 0.95:
			fail("Monster hit-flash brightness (+40%%) out of expected bright range, on=%s off=%s" % [str(m_on), str(m_off)])
			return
	fm.apply_damage_to_player(10.0)
	fm.step(1.0 / 60.0)
	var h_flash_spr := arena.player_node.get_node_or_null("Sprite") as AnimatedSprite2D
	if h_flash_spr != null:
		fm.call("_apply_hit_flash_modulate", h_flash_spr, true, true, true)
		var h_on: Color = h_flash_spr.modulate
		fm.call("_apply_hit_flash_modulate", h_flash_spr, true, false, true)
		var h_off: Color = h_flash_spr.modulate
		if h_on.g < 0.62 or h_on.r < 1.0 or h_on.r > 1.36 or h_off.g < 0.95:
			fail("Hero hit-flash brightness (+40%%) out of expected bright range, on=%s off=%s" % [str(h_on), str(h_off)])
			return
	# Verify normal ("melee") and heavy ("heavy") collision impact FX metadata + clear duration separation
	fm.hit_impacts.clear()
	fm.call("_spawn_hit_impact_fx", Vector2(3100.0, 820.0), "melee", "-50", Color.YELLOW, Vector2(1.0, 0.0))
	fm.call("_spawn_hit_impact_fx", Vector2(3140.0, 820.0), "heavy", "-70", Color.ORANGE, Vector2(-1.0, 0.0))
	if fm.hit_impacts.size() != 2 or str(fm.hit_impacts[0]["kind"]) != "melee" or str(fm.hit_impacts[1]["kind"]) != "heavy" or float(fm.hit_impacts[1]["duration_s"]) <= float(fm.hit_impacts[0]["duration_s"]):
		fail("Normal & heavy collision FX must register distinct impact kinds and timings: %s" % str(fm.hit_impacts))
		return
	# Verify canonical default hit_impact SpriteFrames (Owner sample image copy 2.png + dissipation frames)
	var default_hit_sf: SpriteFrames = OverheadBarsDrawScript.DefaultHitImpactFrames
	if default_hit_sf == null or not default_hit_sf.has_animation(&"hit") or default_hit_sf.get_frame_count(&"hit") < 6:
		fail("Default hit_impact.tres must provide >=6 dissipation frames on animation 'hit'")
		return
	if absf(float(OverheadBarsDrawScript.DEFAULT_HIT_IMPACT_MELEE_SIZE_PX) - 144.0) > 1.0 or absf(float(OverheadBarsDrawScript.DEFAULT_HIT_IMPACT_HEAVY_SIZE_PX) - 216.0) > 1.0:
		fail("Default hit_impact sizes must match current melee (144px) and heavy (216px) footprints")
		return
	if arena._field_overlay_node == null or arena._field_overlay_node.texture_filter != CanvasItem.TEXTURE_FILTER_NEAREST:
		fail("FieldOverlayLayer must enforce TEXTURE_FILTER_NEAREST for crisp pixel hit_impact sprites")
		return
	if int(OverheadBarsDrawScript.FLOATING_DAMAGE_FONT_SIZE) != 24 or int(OverheadBarsDrawScript.FLOATING_DAMAGE_OUTLINE_SIZE) != 5:
		fail("Floating damage popup font must stay +20%% larger (24px, outline 5)")
		return

	# Normal attack 0.2s cooldown & anti-mash (no input queueing): finish clip, reject spam during 0.2s, allow after 0.2s
	for _wait_clip in range(60):
		await physics_frame
		arena.step_player_movement(1.0 / 60.0, 0)
		fm.step(1.0 / 60.0)
		if not arena._is_player_action_playing() and float(arena.player_light_cooldown_s) <= 0.0:
			break
	if not fm.request_player_primary_action():
		fail("First normal attack from ready state must succeed (playing=%s cd=%s dead=%s)" % [str(arena._is_player_action_playing()), str(arena.player_light_cooldown_s), str(fm.player_dead)])
		return
	if fm.request_player_primary_action() or arena.player_node.has_meta(&"_arena_queued_action"):
		fail("Mashing normal attack during active clip must be rejected without queueing")
		return
	for _finish_clip in range(60):
		await physics_frame
		arena.step_player_movement(1.0 / 60.0, 0)
		fm.step(1.0 / 60.0)
		if not arena._is_player_action_playing():
			break
	# One extra movement step transitions _player_light_clip_active -> 0.2s cooldown right when clip ends
	arena.step_player_movement(1.0 / 60.0, 0)
	if float(arena.player_light_cooldown_s) <= 0.14 or fm.request_player_primary_action():
		fail("Normal attack must enforce 0.2s recovery cooldown after finishing clip, cd=%s" % str(arena.player_light_cooldown_s))
		return
	for _cd_step in range(15):
		await physics_frame
		arena.step_player_movement(1.0 / 60.0, 0)
		fm.step(1.0 / 60.0)
	if float(arena.player_light_cooldown_s) > 0.001 or not fm.request_player_primary_action():
		fail("Normal attack must become ready again once 0.2s cooldown expires, cd=%s" % str(arena.player_light_cooldown_s))
		return

	# Skill-vs-Skill clash: player power_up orb cuts enemy projectile with clash FX + explosion
	fm.homing_projectiles.clear()
	fm.hit_impacts.clear()
	fm._explosion_nodes.clear()
	fm.call("_spawn_homing_projectile", arena.player_node, "drum", "electric_orb_fx", Vector2(3000.0, 760.0), 2.5, trex_slot2, true, 400.0, 20.0)
	fm.call("_spawn_homing_projectile", trex_node2, "t_rex", "fireball_fx", Vector2(3015.0, 760.0), 1.75, {}, false, 100.0, 0.0)
	fm.step(1.0 / 60.0)
	var saw_clash := false
	for imp in fm.hit_impacts:
		if str(imp.get("kind", "")) == "clash":
			saw_clash = true
			break
	if not saw_clash or fm._explosion_nodes.is_empty():
		fail("Colliding player & enemy skill projectiles must trigger a 'clash' impact + explosion FX")
		return

	# === BOSS MAP DRUM EVENT TESTS ===
	# 1) 5' initial timer must pause/reset while no Hero exists in map, then spawn after 300s with Hero present.
	arena.set_field_hero_visible(false)
	fm.start_field(false)
	for _nb in range(32):
		fm.step(10.0)
	if not fm.boss_slot.is_empty() or absf(fm.boss_spawn_timer_s - 300.0) > 0.1:
		fail("Boss Drum must NOT spawn or count down 5' timer when no Hero exists in map (timer=%.1f)" % fm.boss_spawn_timer_s)
		return
	arena.set_field_hero_visible(true)
	fm.set_player_immortal(false)
	for _hb in range(29):
		fm.step(10.0)
	fm.step(9.0)
	if not fm.boss_slot.is_empty() and bool(fm.boss_slot.get("alive", false)):
		fail("Boss Drum must not spawn before Hero reaches 300s (5') in map (timer=%.2f)" % fm.boss_spawn_timer_s)
		return
	fm.step(1.5)
	if fm.slots.size() != 14 or fm.boss_slot.is_empty() or not bool(fm.boss_slot.get("alive", false)):
		fail("Boss Drum must spawn after 5' with Hero while preserving 14 normal slots")
		return
	var bnode0 := fm.boss_slot.get("node") as Node2D
	if bnode0 == null or bnode0.name != "FieldBoss_drum" or bnode0.z_index != arena.Z_LAYER_BOSS or absf(bnode0.scale.y - 2.5) > 0.01:
		fail("Boss Drum visual identity/scale/z_index mismatch: name=%s z=%d scale=%s" % [str(bnode0.name if bnode0 else ""), int(bnode0.z_index if bnode0 else -1), str(bnode0.scale if bnode0 else Vector2.ZERO)])
		return
	if absf(float(fm.boss_slot["max_hp"]) - 5000.0) > 0.1 or absf(float(fm.boss_slot["max_stamina"]) - 200.0) > 0.1:
		fail("Boss Drum stats mismatch: hp=%.1f stam=%.1f" % [float(fm.boss_slot["max_hp"]), float(fm.boss_slot["max_stamina"])])
		return

	# 2) Entry Teleport from far random spawn (~5900px) -> right beside Hero + shoulder attack_light (120 dmg)
	fm.start_field(false)
	arena.set_field_hero_visible(true)
	fm.set_player_immortal(false)
	arena.player_node.position = Vector2(400.0, float(arena.call("_ground_y_at", 400.0)))
	var hp_before_boss: float = fm.player_hp
	var bs: Dictionary = fm.spawn_boss_drum(5900.0)
	if bs.is_empty() or str(bs.get("action_clip", "")) != "teleport":
		fail("Boss Drum spawn must immediately initiate entry 'teleport' clip toward Hero")
		return
	var bnode := bs["node"] as Node2D
	for _tp_f in range(36):
		fm.step(1.0 / 60.0)
	if absf(bnode.position.x - arena.player_node.position.x) > 360.0:
		fail("Boss Drum entry teleport must relocate from 5900px beside Hero (~400px), got x=%.1f" % bnode.position.x)
		return
	for _melee_f in range(36):
		fm.step(1.0 / 60.0)
	if absf(fm.player_hp - (hp_before_boss - 120.0)) > 0.1 and fm.player_hp > hp_before_boss - 119.0:
		fail("Boss Drum post-teleport light attack must deal 120 damage, hp before=%.1f after=%.1f" % [hp_before_boss, fm.player_hp])
		return

	# 3) UtilityAI ranged power_up (220 dmg) at 200..400px & global pursuit >400px
	fm.homing_projectiles.clear()
	var b_ai: UtilityAIController = bs["ai"] as UtilityAIController
	b_ai.cooldown_remaining = 0.0
	b_ai.set_meta(&"drum_phase", "engaged")
	bs["action_clip"] = ""
	bs["action_timer_s"] = 0.0
	arena.player_node.position = Vector2(bnode.position.x + 360.0, float(arena.call("_ground_y_at", bnode.position.x + 360.0)))
	fm.step(1.0 / 60.0)
	if str(bs.get("action_clip", "")) != "power_up":
		fail("Boss Drum UtilityAI at ~360px center distance must cast 'power_up', got '%s'" % str(bs.get("action_clip", "")))
		return
	var saw_boss_orb := false
	for _pw_f in range(60):
		fm.step(1.0 / 60.0)
		for pr in fm.homing_projectiles:
			if not bool(pr.get("is_player", true)) and absf(float(pr.get("damage", 0.0)) - 220.0) < 0.1:
				saw_boss_orb = true
	if not saw_boss_orb:
		fail("Boss Drum power_up must launch homing electric_orb_fx dealing 220 damage")
		return

	arena.player_node.position = Vector2(3300.0, float(arena.call("_ground_y_at", 3300.0)))
	bs["action_clip"] = ""
	bs["action_timer_s"] = 0.0
	fm._boss_teleport_chase_cd_s = 0.0
	for _ch_f in range(40):
		fm.step(1.0 / 60.0)
	if absf(bnode.position.x - arena.player_node.position.x) > 400.0:
		fail("Boss Drum must globally pursue & teleport to Hero at x=3300 (>400px away), got x=%.1f" % bnode.position.x)
		return

	# 4) Manual HUD Boss dropdown + summon button & Boss KO -> 100% Dragon Ball drop + 30' (1800s) respawn cooldown
	if arena.boss_selector == null or arena.boss_spawn_button == null or arena.boss_spawn_button.text != "⚡ Gọi Boss":
		fail("ArenaSandbox must expose BossSelectorDropdown and '⚡ Gọi Boss' button")
		return
	arena.enable_field_mode(true, true)
	var b_manual: Dictionary = arena.spawn_boss_drum_now()
	if b_manual.is_empty() or not bool(b_manual.get("alive", false)):
		fail("spawn_boss_drum_now() button helper must spawn alive Boss Drum")
		return
	await process_frame
	if "Boss Drum:" not in arena.hud_label.text:
		fail("HUD must show alive Boss Drum HP status, got '%s'" % arena.hud_label.text)
		return

	var drops_before: int = arena._dropped_item_nodes.size()
	fm.apply_damage_to_slot(fm.boss_slot, 5000.0, 20.0)
	if bool(fm.boss_slot.get("alive", true)) or absf(fm.boss_respawn_timer_s - 1800.0) > 0.1:
		fail("Defeated Boss Drum must set alive=false and 1800s (30') respawn timer (got %.1f)" % fm.boss_respawn_timer_s)
		return
	if arena._dropped_item_nodes.size() <= drops_before:
		fail("Defeated Boss Drum must drop Dragon Ball at 100%% rate")
		return
	for _cd30 in range(179):
		fm.step(10.0)
	if bool(fm.boss_slot.get("alive", false)):
		fail("Boss Drum must NOT respawn before 1800s (30') elapsed (rem=%.1f)" % fm.boss_respawn_timer_s)
		return
	fm.step(12.0)
	if not bool(fm.boss_slot.get("alive", false)):
		fail("Boss Drum must respawn once 1800s (30') elapsed with Hero in map")
		return

	# A1/A4/A9/A13 regression checks: no Boss Drum node leak, full-map Boss zone, Z-index order, 4-step ruler in Field Mode
	await process_frame
	var boss_nodes_count := 0
	for ch in arena.fighters_layer.get_children():
		if str(ch.name).begins_with("FieldBoss_drum"):
			boss_nodes_count += 1
	if boss_nodes_count != 1:
		fail("Boss Drum respawn must not leak orphan FieldBoss_drum nodes, count=%d" % boss_nodes_count)
		return
	var boss_ai_check = fm.boss_slot.get("ai")
	if boss_ai_check == null or (float(boss_ai_check.zone_max_x) - float(boss_ai_check.zone_min_x)) < 5000.0:
		fail("Boss Drum AI must patrol full map (unbounded_zone), got width=%.1f" % (float(boss_ai_check.zone_max_x) - float(boss_ai_check.zone_min_x) if boss_ai_check != null else -1.0))
		return
	if arena._item_drop_layer.z_index >= arena.shenron_summon.z_index or arena.shenron_summon.z_index >= arena._field_overlay_node.z_index:
		fail("Z-index layering mismatch: ItemDrops=%d Shenron=%d FieldOverlay=%d" % [arena._item_drop_layer.z_index, arena.shenron_summon.z_index, arena._field_overlay_node.z_index])
		return
	var step_edges: Array[float] = arena.call("_get_terrain_step_edges")
	if step_edges.size() != 4:
		fail("Extended 4-step map must expose 4 ruler step edges, got %s" % str(step_edges))
		return
	var field_ruler: Dictionary = arena.measure_player_enemy_distance()
	if not bool(field_ruler.get("has_b", false)):
		fail("measure_player_enemy_distance() must resolve active enemy in Field Mode")
		return

	for expected_clip in ["attack_light", "power_up"]:
		fm.start_field(false)
		arena.set_field_hero_visible(true)
		var chilopoda: Dictionary = fm.slots[0]
		var monster := chilopoda["node"] as Node2D
		var target_gap := 25.0 if expected_clip == "power_up" else 100.0
		arena.player_node.position = monster.position - Vector2(250.0, 0.0)
		arena.player_node.position.x += float(fm._compute_slot_edge_gap(chilopoda)) - target_gap
		var actual_gap := float(fm._compute_slot_edge_gap(chilopoda))
		chilopoda["combat_state"] = "combat"
		chilopoda["aggro_target_id"] = "local"
		chilopoda["cooldown_s"] = 0.0
		fm._step_slot(chilopoda, 1.0 / 60.0)
		if absf(actual_gap - target_gap) > 10.0 or str(chilopoda["action_clip"]) != expected_clip:
			fail("Field Chilopoda at %.1fpx (target %.1fpx): expected %s, got %s" % [actual_gap, target_gap, expected_clip, chilopoda["action_clip"]])
			return

	arena.enable_field_mode(false, false)
	await process_frame

	# A2 regression check: Drum KO clip must hold final frame instead of resetting back to idle
	arena.select_character("drum")
	await process_frame
	var drum_ko_spr := arena.player_node.get_node_or_null("Sprite") as AnimatedSprite2D
	if drum_ko_spr != null and drum_ko_spr.sprite_frames != null and drum_ko_spr.sprite_frames.has_animation(&"ko"):
		drum_ko_spr.play(&"ko")
		arena.player_node.call("_on_body_animation_finished")
		if drum_ko_spr.animation != &"ko":
			fail("Drum KO must remain on &'ko' after animation finishes, got %s" % str(drum_ko_spr.animation))
			return

	# Verify 360-degree continuous analog vector flight on flying character (Pteranodon) without affecting Drum
	arena.select_character("pteranodon")
	await process_frame
	var fly_start: Vector2 = arena.player_node.position
	var ang_vec := Vector2(cos(0.65), sin(0.65))
	for _fv in range(20):
		arena.step_player_movement(1.0 / 60.0, 1, 0, false, false, false, ang_vec)
	var fly_delta: Vector2 = arena.player_node.position - fly_start
	if fly_delta.x <= 15.0 or fly_delta.y <= 10.0:
		fail("Flying fighter must support smooth 360-degree multi-axis analog flight, delta=%s" % str(fly_delta))
		return

	# Batch 3 regression checks: I18nManager (5 locked locales, default en), WebSocketTransport + ZoneClientSync safety, dynamic extended_map & single-texture trees
	if arena.get_language_locale() != "en":
		fail("I18nManager must default strictly to 'en', got %s" % arena.get_language_locale())
		return
	if arena.set_language_locale("ja") or arena.get_language_locale() != "en":
		fail("I18nManager must reject unsupported locale 'ja'")
		return
	if not arena.set_language_locale("vi") or arena.get_language_locale() != "vi":
		fail("I18nManager must allow switching to 'vi' via Settings")
		return
	arena.set_language_locale("en")
	if arena._extended_step_configs.size() != 4 or absf(arena._map_left_x - (-240.0)) > 0.1 or absf(arena._map_right_x - 6360.0) > 0.1:
		fail("ArenaSandbox must load extended_map bounds and 4 steps dynamically from arena-stage.json")
		return
	if arena._foreground_trees != null and arena._foreground_trees.get_child_count() == 3:
		var t0_atlas: AtlasTexture = (arena._foreground_trees.get_child(0) as Sprite2D).texture as AtlasTexture
		var t1_atlas: AtlasTexture = (arena._foreground_trees.get_child(1) as Sprite2D).texture as AtlasTexture
		if t0_atlas == null or t1_atlas == null or t0_atlas.atlas != t1_atlas.atlas:
			fail("Foreground trees must reuse a single loaded Texture2D atlas instance")
			return
	var ws_script := preload("res://scenes/net/WebSocketTransport.gd")
	var zs_script := preload("res://scenes/net/ZoneClientSync.gd")
	var ws1 = ws_script.new()
	var ws2 = ws_script.new()
	var zs = zs_script.new()
	zs.attach_transport(ws1)
	zs.attach_transport(ws2)
	ws1.packet_received.emit({"op": "zone_snapshot", "tick": 77, "entities": [{"id": "stale"}]})
	if zs.entities_by_id.has("stale"):
		fail("ZoneClientSync.attach_transport must disconnect previous transport signals")
		return
	ws2.packet_received.emit({"op": "zone_snapshot", "tick": 88, "entities": "malformed_not_array"})
	if zs.last_snapshot_tick != -1:
		fail("ZoneClientSync must reject malformed non-Array entities without advancing last_snapshot_tick")
		return
	var disc_reasons: Array[String] = []
	ws2.disconnected.connect(func(r: String) -> void: disc_reasons.append(r))
	ws2._connecting = true
	ws2._was_open = false
	ws2.poll_events()
	if disc_reasons.is_empty() or disc_reasons[0] != "handshake_failed":
		fail("WebSocketTransport must emit disconnected('handshake_failed') when closed during connecting, got %s" % str(disc_reasons))
		return

	# Phase 1 regression checks (alpha-login-cloudflare-handoff.md):
	# (A) Drum Field Mode Mana & queued power_up overwritten by teleport / repeated input
	arena.enable_field_mode(true, false)
	arena.set_field_hero_visible(true, "drum")
	await process_frame
	var p1_fm = arena.field_manager
	var p1_spr := arena.player_node.get_node_or_null("Sprite") as AnimatedSprite2D
	if p1_fm == null or p1_spr == null:
		fail("Phase 1 regression: FieldCombatManager or Drum player sprite missing")
		return
	p1_fm.homing_projectiles.clear()
	# (A1) Idle power_up works normally and consumes 100 Mana once
	arena.call("_play_fighter_clip", arena.player_node, "idle")
	p1_fm._player_power_pending = false
	p1_fm.player_mana = 100.0
	if not p1_fm.request_player_power_up() or absf(p1_fm.player_mana) > 0.01 or String(p1_spr.animation) != "power_up":
		fail("Phase 1 (A1): Idle Drum power_up must start immediately and consume 100 Mana")
		return
	# (A2) Queued power_up during attack_light then overwritten by teleport -> Mana stays 100, no orb
	arena.call("_play_fighter_clip", arena.player_node, "idle")
	if arena.player_node.has_meta(&"_arena_queued_action"):
		arena.player_node.remove_meta(&"_arena_queued_action")
	p1_fm._player_power_pending = false
	p1_fm.player_mana = 100.0
	arena.player_light_cooldown_s = 0.0
	if not arena.call("_request_player_action", "attack_light"):
		fail("Phase 1 (A2): Failed to start attack_light")
		return
	# Repeated spam presses of power_up during attack_light must NOT deduct Mana while queued
	p1_fm.request_player_power_up()
	p1_fm.request_player_power_up()
	if absf(p1_fm.player_mana - 100.0) > 0.01 or String(arena.player_node.get_meta(&"_arena_queued_action", "")) != "power_up":
		fail("Phase 1 (A2): Queued power_up must keep Mana=100 until clip actually begins, got mana=%.1f" % p1_fm.player_mana)
		return
	# Overwrite queue with teleport before flush
	arena.call("_request_player_action", "teleport")
	p1_fm.call("_step_player_combat_hooks")
	if absf(p1_fm.player_mana - 100.0) > 0.01 or p1_fm._player_power_pending or String(arena.player_node.get_meta(&"_arena_queued_action", "")) != "teleport":
		fail("Phase 1 (A2): Overwriting queued power_up with teleport must preserve 100 Mana and clear pending")
		return
	# Flush queue -> teleport starts, Mana still 100, zero orbs spawned
	p1_spr.stop()
	arena.call("_flush_player_queued_action")
	if String(p1_spr.animation) != "teleport" or absf(p1_fm.player_mana - 100.0) > 0.01 or not p1_fm.homing_projectiles.is_empty():
		fail("Phase 1 (A2): After teleport flush, Mana must stay 100 and no orb spawned")
		return
	# (A3) Queued power_up during attack_light then waited -> starts on flush, deducts 100 Mana ONCE, launches orb at frame 10
	arena.call("_play_fighter_clip", arena.player_node, "idle")
	p1_fm._player_power_pending = false
	p1_fm.player_mana = 100.0
	arena.player_light_cooldown_s = 0.0
	arena.call("_request_player_action", "attack_light")
	p1_fm.request_player_power_up()
	p1_spr.stop()
	arena.call("_flush_player_queued_action")
	if String(p1_spr.animation) != "power_up" or absf(p1_fm.player_mana) > 0.01 or not p1_fm._player_power_pending:
		fail("Phase 1 (A3): Flushed queued power_up must start, consume 100 Mana once, and arm orb")
		return
	p1_spr.frame = 10
	p1_fm.call("_step_player_combat_hooks")
	if p1_fm.homing_projectiles.is_empty():
		fail("Phase 1 (A3): Flushed queued power_up must launch homing orb at frame 10")
		return
	p1_fm.homing_projectiles.clear()

	# (B) Continuous terrain_blocks_segment across steps (both directions, grazing, above-cliff, homing turn)
	if not arena.terrain_blocks_segment(Vector2(3000.0, 853.0), Vector2(2500.0, 811.0)):
		fail("Phase 1 (B): Diagonal probe (3000,853)->(2500,811) crosses Step 1 solid corner and must return true")
		return
	if not arena.terrain_blocks_segment(Vector2(2500.0, 811.0), Vector2(3000.0, 853.0)):
		fail("Phase 1 (B): Reverse diagonal probe (2500,811)->(3000,853) must also return true")
		return
	if not arena.terrain_blocks_segment(Vector2(3000.0, 853.0), Vector2(2847.5, 840.19)):
		fail("Phase 1 (B): Sub-segment into Step 1 floor must return true")
		return
	if not arena.terrain_blocks_segment(Vector2(2847.5, 840.19), Vector2(3000.0, 853.0)):
		fail("Phase 1 (B): Segment starting under Step 1 floor must return true")
		return
	if not arena.terrain_blocks_segment(Vector2(3000.0, 850.0), Vector2(2500.0, 830.0)):
		fail("Phase 1 (B): Grazing edge crossing Step 1 must return true")
		return
	if arena.terrain_blocks_segment(Vector2(3000.0, 852.0), Vector2(2500.0, 810.0)):
		fail("Phase 1 (B): Diagonal segment staying 0.6px above Step 1 corner must return false")
		return
	if arena.terrain_blocks_segment(Vector2(3000.0, 800.0), Vector2(2500.0, 800.0)):
		fail("Phase 1 (B): Horizontal segment flying cleanly over Step 1 cliff must return false")
		return
	# Homing projectile curving into Step 1 wall must terminate on terrain
	var p1_slot: Dictionary = p1_fm.slots[0]
	var p1_mnode := p1_slot["node"] as Node2D
	p1_slot["alive"] = true
	p1_slot["hp"] = 1000.0
	p1_mnode.position = Vector2(2700.0, 840.0)
	p1_fm.call("_spawn_homing_projectile", arena.player_node, "drum", "electric_orb_fx", Vector2(2920.0, 875.0), 2.0, p1_slot, true, 400.0, 20.0)
	var p1_blocked := false
	for _ht in range(40):
		p1_fm.call("_step_homing_projectiles", 1.0 / 60.0)
		if p1_fm.homing_projectiles.is_empty():
			p1_blocked = true
			break
	if not p1_blocked or float(p1_slot["hp"]) < 999.0:
		fail("Phase 1 (B): Homing orb steering across Step 1 cliff face must stop on terrain without damaging target behind wall (hp=%.1f)" % float(p1_slot["hp"]))
		return

	# === SON GOKU HERO PHASE 1 TESTS (Default Hero replacing Drum, Base<->SSJ1, 7-Step Combo, Stamina Teleport, Flight+Fly_Aura) ===
	arena.set_field_hero_visible(true)
	await process_frame
	if arena.active_character_id != "songoku" or arena.player_node == null or not bool(arena.player_node.call(&"is_hero_songoku")):
		fail("Default Hero must now be Son Goku ('songoku'), got %s" % arena.active_character_id)
		return
	var goku: Node2D = arena.player_node
	# 1) Starts in Base form: cannot attack, jump, or fly
	if bool(goku.get("is_ssj")) or bool(goku.call(&"can_attack")) or bool(goku.call(&"can_jump")) or bool(goku.call(&"can_fly")):
		fail("Son Goku must start in Base form with attacks/jump/fly locked")
		return
	var sg_slot: Dictionary = p1_fm.slots[0]
	var sg_mnode: Node2D = sg_slot["node"] as Node2D
	sg_slot["alive"] = true
	sg_slot["hp"] = 1000.0
	goku.position = Vector2(sg_mnode.position.x - 40.0, sg_mnode.position.y)
	p1_fm.pointer_kind = "enemy"
	p1_fm.pointer_slot_id = str(sg_slot["id"])
	if p1_fm.request_player_primary_action():
		fail("Son Goku in Base form must NOT attack enemies")
		return
	# 2) Transform to SSJ1 in Peace mode: invulnerable during transform, loops idle_ssj_aura until move/combat!
	arena._on_touch_action("transform_ssj")
	if not bool(goku.get("is_ssj")) or not bool(goku.call(&"can_attack")) or not bool(goku.call(&"can_fly")):
		fail("Transform SSJ1 must unlock attacks, jump, and flight")
		return
	if not bool(goku.call(&"is_transform_invulnerable")):
		fail("Son Goku must be invulnerable during transform_ssj animation")
		return
	var hp_before_invuln: float = p1_fm.player_hp
	p1_fm.apply_damage_to_player(120.0)
	if absf(p1_fm.player_hp - hp_before_invuln) > 0.1:
		fail("Damage during transform_ssj must be blocked (invulnerable)")
		return
	# Clear transform invulnerability after transform finishes -> loops idle_ssj_aura in Peace!
	goku.set("transform_invuln_s", 0.0)
	var g_spr: AnimatedSprite2D = goku.get_node("Sprite") as AnimatedSprite2D
	g_spr.play(&"idle_ssj_aura")
	p1_fm.set_player_immortal(false)
	if g_spr.sprite_frames.has_animation(&"fly_launch") or g_spr.sprite_frames.has_animation(&"idle_ssj"):
		fail("fly_launch (19) and redundant idle_ssj must BOTH be REMOVED from Songoku Hero SpriteFrames")
		return
	if not g_spr.sprite_frames.has_animation(&"idle_combat") or not g_spr.sprite_frames.has_animation(&"combat_enter"):
		fail("34 Combat Stance clips (combat_enter & idle_combat) must exist")
		return
	if String(goku.call(&"resolve_locomotion_clip", false, false)) != "idle_ssj_aura":
		fail("In SSJ1 Peace mode, standing clip must be idle_ssj_aura")
		return
	# Peace vs Combat state flags
	var peace_flags: Dictionary = goku.call(&"get_clip_state_flags")
	if not bool(peace_flags.get("peace", false)) or not bool(peace_flags.get("walk", false)) or bool(peace_flags.get("combat_move", true)):
		fail("Peace state flags must have walk=true, combat_move=false")
		return
	# Moving in Peace uses walk_ssj; stopping immediately returns to idle_ssj_aura!
	if String(goku.call(&"resolve_locomotion_clip", true, false)) != "walk_ssj":
		fail("Moving in SSJ1 Peace mode must use walk_ssj")
		return
	if String(goku.call(&"resolve_locomotion_clip", false, false)) != "idle_ssj_aura":
		fail("Stopping movement in SSJ1 Peace mode must return to idle_ssj_aura")
		return
	# Incoming attack switches Peace -> Combat, bridges via combat_enter, & shows red CHIẾN ĐẤU banner!
	p1_fm.apply_damage_to_player(50.0)
	if not bool(goku.call(&"is_in_combat")):
		fail("Being attacked must switch Son Goku from Peace to Combat state")
		return
	if arena.combat_banner_label == null or not arena.combat_banner_label.visible:
		fail("Peace -> Combat transition must show red 'CHIẾN ĐẤU' banner")
		return
	if String(g_spr.animation) != "combat_enter":
		fail("Peace -> Combat transition while standing in SSJ1 must play combat_enter bridge, got %s" % String(g_spr.animation))
		return
	var combat_flags: Dictionary = goku.call(&"get_clip_state_flags")
	if bool(combat_flags.get("walk", true)) or not bool(combat_flags.get("combat_move", false)):
		fail("Combat state flags must have walk=false, combat_move=true")
		return
	# Combat move exact v9 continuous dash + analog near-center brake (NO aura, NO hop-and-land):
	# Backward: #0 (400 px/s continuous) -> analog near center / release -> #1 brake cushion
	# Forward : #3 (500 px/s continuous) -> analog near center / release -> #2 brake cushion
	goku.call(&"reset_combat_move")
	if int(goku.call(&"step_combat_move_frame", 0.05, -1, 1.0)) != 0 or absf(float(goku.call(&"get_combat_move_speed_px_s")) - 400.0) > 0.1:
		fail("combat_move backward dash must hold Frame 0 at 400 px/s")
		return
	if int(goku.call(&"step_combat_move_frame", 0.25, -1, 1.0)) != 0 or float(goku.call(&"get_combat_move_hop_height_px")) < 4.0:
		fail("combat_move backward dash must stay on Frame 0 continuously with gentle low hover (4..14px)")
		return
	if int(goku.call(&"step_combat_move_frame", 0.05, -1, 0.30)) != 1 or not bool(goku.call(&"is_combat_move_braking")) or float(goku.call(&"get_combat_move_hop_height_px")) > 0.01:
		fail("combat_move backward pulling analog near center (0.30) must switch to Frame 1 brake cushion at 0px hover")
		return
	if int(goku.call(&"step_combat_move_frame", 0.05, 1, 1.0)) != 3 or absf(float(goku.call(&"get_combat_move_speed_px_s")) - 500.0) > 0.1:
		fail("combat_move forward dash must hold Frame 3 at 500 px/s")
		return
	if int(goku.call(&"step_combat_move_frame", 0.25, 1, 1.0)) != 3 or float(goku.call(&"get_combat_move_hop_height_px")) < 4.0:
		fail("combat_move forward dash must stay on Frame 3 continuously with gentle low hover")
		return
	if int(goku.call(&"step_combat_move_frame", 0.05, 1, 0.30)) != 2 or not bool(goku.call(&"is_combat_move_braking")):
		fail("combat_move forward pulling analog near center (0.30) must switch to Frame 2 brake cushion")
		return
	# Releasing analog to center finishes braking cushion after 120ms
	if int(goku.call(&"step_combat_move_frame", 0.04, 0, 0.0)) != 2 or not bool(goku.call(&"is_combat_move_braking")):
		fail("combat_move releasing analog must briefly hold Frame 2 brake cushion")
		return
	goku.call(&"step_combat_move_frame", 0.15, 0, 0.0)
	if bool(goku.call(&"is_combat_move_braking")):
		fail("combat_move brake cushion must end after 120ms")
		return
	goku.call(&"reset_combat_move")
	# Armor-break HIT reaction (08)
	p1_fm.apply_damage_to_player(30.0, Vector2(-99999.0, -99999.0), false, "armor_break")
	if String(g_spr.animation) != "hit":
		fail("Armor-break hit must play 'hit' clip, got %s" % String(g_spr.animation))
		return
	# 3) 7-Step Normal Combo sequence (10->11->12->13->14->17->15), new damage (10-20 / 50 / 60), per-frame hit list & persistence!
	var expected_combo: Array[String] = ["attack_light", "attack_2", "attack_3", "attack_4", "attack_5", "attack_6", "attack_7"]
	for ci in range(7):
		var cinfo: Dictionary = goku.call(&"pop_next_combo_attack")
		if str(cinfo.get("clip", "")) != expected_combo[ci]:
			fail("Combo step %d mismatch: got %s expected %s" % [ci, str(cinfo.get("clip", "")), expected_combo[ci]])
			return
		var cdmg: float = float(cinfo.get("damage", 0.0))
		if ci < 5 and (cdmg < 10.0 or cdmg > 20.0):
			fail("Light combo step %d damage must be in [10,20], got %.1f" % [ci, cdmg])
			return
		if ci >= 5 and absf(cdmg - 50.0) > 0.1:
			fail("Heavy combo step %d damage must be 50, got %.1f" % [ci, cdmg])
			return
		if ci == 5 and (not bool(cinfo.get("has_gold_slash_60", false)) or absf(float(cinfo.get("gold_slash_damage", 0.0)) - 60.0) > 0.1):
			fail("Attack 6 (file 17) penultimate golden slash frame must deal 60 damage")
			return
		if (cinfo.get("hit_frames", []) as Array).is_empty():
			fail("Combo step %d must expose per-frame hit_frames" % ci)
			return
		if ci == 2:
			# Use Teleport mid-combo -> combo_step MUST persist (NOT reset!)
			var saved_step: int = int(goku.get("combo_step"))
			arena._trigger_songoku_teleport(Vector2(1.0, 0.0))
			if int(goku.get("combo_step")) != saved_step:
				fail("Using Teleport skill mid-combo must NOT reset combo_step")
				return
	# Reset combo ONLY on KO/death
	goku.set("combo_step", 4)
	p1_fm.set_player_immortal(false)
	p1_fm.apply_damage_to_player(99999.0)
	if int(goku.get("combo_step")) != 0 or String(g_spr.animation) != "ko":
		fail("Son Goku combo_step must reset to 0 and play 'ko' upon KO/death")
		return
	p1_fm.player_dead = false
	p1_fm.player_hp = p1_fm.player_max_hp
	# 4) Stamina Teleport: max 100, static -75, dash -25 (100px), regen +5/s
	goku.set("stamina", 100.0)
	if not arena._trigger_songoku_teleport(Vector2.ZERO) or absf(float(goku.get("stamina")) - 25.0) > 0.1:
		fail("Static Teleport must consume 75 stamina (100 -> 25)")
		return
	if not arena._trigger_songoku_teleport(Vector2(1.0, 0.0)) or absf(float(goku.get("stamina"))) > 0.1:
		fail("Moving Directional Teleport must consume 25 stamina (25 -> 0)")
		return
	if arena._trigger_songoku_teleport(Vector2(1.0, 0.0)):
		fail("Teleport must fail when stamina < 25")
		return
	goku.call(&"step_hero_timers", 2.0, false, true, false, 0.0, false)
	if absf(float(goku.get("stamina")) - 10.0) > 0.15:
		fail("Stamina must regenerate +5/s (2.0s -> 10.0), got %.2f" % float(goku.get("stamina")))
		return
	# 5) 360° Jump (~100px apex, F0..F2 up / F3..F5 fall / F4 high-fall) + Hold Analog UP -> Fly_Aura (200px/s) -> 3s Fly_Prep -> Analog DOWN fast drop!
	g_spr.play(&"idle_combat")
	var start_gy: float = arena._ground_y_at(goku.position.x)
	goku.position.y = start_gy
	arena.player_vy = 0.0
	goku.set("flight_state", "ground")
	arena.step_player_movement(1.0 / 60.0, 0, 0, true, false, false, Vector2.ZERO)
	var min_jump_y: float = goku.position.y
	var saw_ascend_frame: bool = false
	var saw_fall4_frame: bool = false
	for _jf in range(45):
		arena.step_player_movement(1.0 / 60.0, 0, 0, false, false, false, Vector2.ZERO)
		min_jump_y = minf(min_jump_y, goku.position.y)
		if String(g_spr.animation) == "jump":
			if g_spr.frame >= 0 and g_spr.frame <= 2 and arena.player_vy < 0.0:
				saw_ascend_frame = true
			if g_spr.frame == 4 and arena.player_vy > 130.0:
				saw_fall4_frame = true
	var apex_h: float = start_gy - min_jump_y
	if apex_h < 88.0 or apex_h > 112.0:
		fail("Son Goku jump height must be ~100px, measured %.1fpx" % apex_h)
		return
	if not saw_ascend_frame or not saw_fall4_frame:
		fail("Jump must use F0..F2 ascending and F4 falling (asc=%s, fall4=%s)" % [str(saw_ascend_frame), str(saw_fall4_frame)])
		return
	# Jump + Hold Analog UP -> enters `flying` (`fly_aura`)
	goku.position.y = start_gy
	arena.player_vy = 0.0
	for _jfly in range(18):
		arena.step_player_movement(1.0 / 60.0, 1, -1, false, false, false, Vector2(0.55, -0.83))
	if str(goku.get("flight_state")) != "flying":
		fail("Jump + Hold Analog UP in SSJ1 must enter 'flying' (fly_aura), got %s" % str(goku.get("flight_state")))
		return
	arena.step_player_movement(1.0 / 60.0, 0, 0, false, false, false, Vector2.ZERO)
	if str(goku.get("flight_state")) != "hovering" or String(g_spr.animation) != "fly_prep":
		fail("Releasing movement mid-flight must enter 3s 'hovering' (fly_prep), got %s/%s" % [str(goku.get("flight_state")), String(g_spr.animation)])
		return
	# Air attack / teleport active (> 3.5s) MUST NOT auto-drop; ONLY idle fly_prep counts down 3s!
	goku.call(&"step_hero_timers", 3.5, false, false, false, 80.0, false, true)
	if str(goku.get("flight_state")) != "hovering" or absf(float(goku.get("hover_timer_s")) - 3.0) > 0.05:
		fail("Mid-air attack/teleport must NOT auto-drop after 3s (state=%s, hover_t=%.2f)" % [str(goku.get("flight_state")), float(goku.get("hover_timer_s"))])
		return
	# Pulling Analog DOWN while hovering immediately fast-drops without waiting 3s!
	arena.step_player_movement(1.0 / 60.0, 0, 1, false, true, false, Vector2(0.0, 0.90))
	if str(goku.get("flight_state")) != "falling" or arena.player_vy < 500.0:
		fail("Analog DOWN during fly_prep hover must immediately fast-drop (state=%s, vy=%.1f)" % [str(goku.get("flight_state")), arena.player_vy])
		return

	# === SON GOKU PHASE 1 v5/v6 REGRESSION UNIT TESTS (T1..T8 FULL COVERAGE!) ===
	# v6 T1: Verify Base Approved SHA-256 Lock file exists with all 24 Base frames!
	if not FileAccess.file_exists("res://assets/songoku/base_approved_lock.json"):
		fail("v6 T1: Missing immutable assets/songoku/base_approved_lock.json")
		return
	var base_lock_doc = JSON.parse_string(FileAccess.get_file_as_string("res://assets/songoku/base_approved_lock.json"))
	if not (base_lock_doc is Dictionary) or int(base_lock_doc.get("frame_count", 0)) != 24:
		fail("v6 T1: base_approved_lock.json must lock all 24 approved Base Goku frames")
		return

	# v9 Tuning: walk 200px/s, combat_move back=400px/s (#0->#1 brake) & fwd=500px/s (#3->#2 brake), fly_aura 400px/s, Orange KI 50 max (-5/s fly, +5/s regen), attack ~60ms/frame & 20ms combo link!
	if absf(float(goku.get("WALK_SPEED_PX_S")) - 200.0) > 0.1 or absf(float(goku.get("COMBAT_MOVE_BACK_SPEED_PX_S")) - 400.0) > 0.1 or absf(float(goku.get("COMBAT_MOVE_FWD_SPEED_PX_S")) - 500.0) > 0.1 or absf(float(goku.get("FLIGHT_SPEED_PX_S")) - 400.0) > 0.1 or absf(float(goku.get("COMBO_LINK_COOLDOWN_S")) - 0.02) > 0.005:
		fail("v9 Tuning: walk=200px/s, combat_move back=400px/s fwd=500px/s, fly_aura=400px/s, combo link=20ms required")
		return
	if absf(float(goku.get("KI_MAX")) - 50.0) > 0.1 or absf(float(goku.get("KI_FLY_DRAIN_PER_S")) - 5.0) > 0.1 or absf(float(goku.get("KI_REGEN_PER_S")) - 5.0) > 0.1:
		fail("v8 KI bar: max=50, fly drain=5/s, regen=5/s required")
		return
	if g_spr.sprite_frames.get_frame_count(&"idle") < 12:
		fail("v5 T7: idle_base must preserve full 01 warm-up animation sequence (>= 12 frames), got %d" % g_spr.sprite_frames.get_frame_count(&"idle"))
		return
	for atk_c in ["attack_light", "attack_2", "attack_3", "attack_4", "attack_5", "attack_6", "attack_7"]:
		var afps: float = maxf(1.0, g_spr.sprite_frames.get_animation_speed(StringName(atk_c)))
		var fdur_ms: float = (g_spr.sprite_frames.get_frame_duration(StringName(atk_c), 0) / afps) * 1000.0
		if fdur_ms < 58.0 or fdur_ms > 70.0:
			fail("v6 Tuning: %s frame duration must be ~60ms (4 ticks @60Hz = 66.7ms), got %.1fms" % [atk_c, fdur_ms])
			return
	# v9 Combat Move runtime test: continuous forward dash (#3 @ 500px/s, 0 hop), brake near center (#2), continuous back dash (#0 @ 400px/s, 0 hop), brake near center (#1)!
	goku.set("is_ssj", true)
	goku.call(&"enter_combat")
	goku.set("flight_state", "ground")
	goku.set("jump_land_hold_s", 0.0)
	goku.call(&"reset_combat_move")
	goku.position = Vector2(1800.0, arena._ground_y_at(1800.0))
	arena.player_facing_left = false
	goku.scale = Vector2(arena.char_scale, arena.char_scale)
	arena.player_vy = 0.0
	g_spr.play(&"idle_combat")
	var cm_start_x: float = goku.position.x
	for _cm_i in range(12):
		arena.step_player_movement(1.0 / 60.0, 1, 0, false, false, false, Vector2(1.0, 0.0))
	var cm_fwd_dx: float = goku.position.x - cm_start_x
	if String(g_spr.animation) != "combat_move" or g_spr.frame != 3 or (-g_spr.position.y * arena.char_scale) < 4.0 or absf(cm_fwd_dx - 100.0) > 12.0:
		fail("v10 combat_move: 200ms forward dash must hold Frame 3 at ~500px/s (~100px) with low hover (~10px) (dx=%.2f, frame=%d, y=%.2f, anim=%s)" % [cm_fwd_dx, g_spr.frame, g_spr.position.y, String(g_spr.animation)])
		return
	# Pull analog near center (0.28) -> Frame #2 brake cushion drops to floor (y=0)!
	arena.step_player_movement(1.0 / 60.0, 1, 0, false, false, false, Vector2(0.28, 0.0))
	if String(g_spr.animation) != "combat_move" or g_spr.frame != 2 or absf(g_spr.position.y) > 0.01:
		fail("v10 combat_move: pulling forward analog near center (0.28) must show Frame 2 brake at y=0, got anim=%s frame=%d y=%.2f" % [String(g_spr.animation), g_spr.frame, g_spr.position.y])
		return
	# Backward dash (facing right, moving left at -1.0 -> relative -1) -> Frame #0 @ 400px/s!
	goku.call(&"reset_combat_move")
	arena.player_facing_left = false
	goku.scale = Vector2(arena.char_scale, arena.char_scale)
	var cm_back_start: float = goku.position.x
	for _cm_b in range(12):
		# Simulate facing locked toward right enemy while retreating left
		goku.call(&"step_combat_move_frame", 1.0 / 60.0, -1, 1.0)
	if int(goku.get("combat_move_frame")) != 0 or absf(float(goku.call(&"get_combat_move_speed_px_s")) - 400.0) > 0.1:
		fail("v9 combat_move: backward dash must stay Frame 0 at 400px/s, got frame=%d spd=%.1f" % [int(goku.get("combat_move_frame")), float(goku.call(&"get_combat_move_speed_px_s"))])
		return
	goku.call(&"step_combat_move_frame", 1.0 / 60.0, -1, 0.25)
	if int(goku.get("combat_move_frame")) != 1:
		fail("v9 combat_move: backward analog near center must brake on Frame 1, got %d" % int(goku.get("combat_move_frame")))
		return
	goku.call(&"reset_combat_move")
	arena.step_player_movement(1.0 / 60.0, 0, 0, false, false, false, Vector2.ZERO)
	if absf(g_spr.position.y) > 0.01:
		fail("v9 combat_move: stopping combat_move must keep Sprite.position.y at 0.0, got %.2f" % g_spr.position.y)
		return

	# v8 Orange KI Flight Bar test: 50 max -> flying 2s drains 10 KI (40) -> flying 8.5s exhausts to 0 & forces falling -> cannot fly while exhausted -> grounded 1.2s regens +6 KI & unlocks flight!
	goku.set("is_ssj", true)
	goku.set("ki", 50.0)
	goku.set("ki_exhausted", false)
	goku.set("flight_state", "flying")
	goku.call(&"step_hero_timers", 2.0, true, false, false, 120.0, false, false)
	if absf(float(goku.get("ki")) - 40.0) > 0.15 or str(goku.get("flight_state")) != "flying":
		fail("v8 KI: 2s flying must drain 10 KI (50->40), got ki=%.2f state=%s" % [float(goku.get("ki")), str(goku.get("flight_state"))])
		return
	goku.call(&"step_hero_timers", 8.5, true, false, false, 120.0, false, false)
	if absf(float(goku.get("ki"))) > 0.01 or not bool(goku.get("ki_exhausted")) or str(goku.get("flight_state")) != "falling" or bool(goku.call(&"can_fly")):
		fail("v8 KI: exhausting 50 KI must drop to 0, set ki_exhausted=true, force falling & lock flight (ki=%.2f ex=%s st=%s)" % [float(goku.get("ki")), str(goku.get("ki_exhausted")), str(goku.get("flight_state"))])
		return
	# Recover on ground at +5 KI/s
	goku.set("flight_state", "ground")
	goku.call(&"step_hero_timers", 1.2, false, true, false, 0.0, false, false)
	if absf(float(goku.get("ki")) - 6.0) > 0.15 or bool(goku.get("ki_exhausted")) or not bool(goku.call(&"can_fly")):
		fail("v8 KI: grounded 1.2s must regen +6 KI (+5/s) & unlock flight (ki=%.2f ex=%s)" % [float(goku.get("ki")), str(goku.get("ki_exhausted"))])
		return

	# v10 Phase 2 Skills verification (05 Barrier 10s, 06 Recover 3s HP/Armor/KI, 26 Flurry Kick universal Stun, Atomic 12s CD, Kamehameha 250 MP)
	for req_p2 in ["barrier_cast", "energy_recover", "flurry_kick", "atomic_ground", "atomic_ground_up", "atomic_air_down", "kame_ground_horiz", "kame_ground_up", "kame_air_horiz", "kame_air_down"]:
		if not g_spr.sprite_frames.has_animation(StringName(req_p2)):
			fail("v10 Phase 2: Songoku bundle missing required clip '%s'" % req_p2)
			return
	goku.set("is_ssj", true)
	goku.set("barrier_cooldown_s", 0.0)
	goku.set("barrier_timer_s", 0.0)
	goku.set("recover_cooldown_s", 0.0)
	goku.set("atomic_cooldown_s", 0.0)
	goku.set("kame_cooldown_s", 0.0)
	goku.set("flurry_cooldown_s", 0.0)
	# 1) Barrier 10s blocks damage while Goku moves freely
	p1_fm.player_hp = 1000.0
	if not p1_fm.request_player_barrier() or not bool(goku.call(&"is_barrier_active")):
		fail("v10 Barrier: request_player_barrier must activate 10s shield")
		return
	p1_fm.apply_damage_to_player(200.0, goku.position, false, "player_hit")
	if absf(p1_fm.player_hp - 1000.0) > 0.1:
		fail("v10 Barrier: active 10s shield must block 100% incoming damage, got hp=%.1f" % p1_fm.player_hp)
		return
	goku.set("barrier_timer_s", 0.0)
	# 2) Energy Recover 3s: dedicated visible button (slot 10) + loops #2..#5 cleanly (wraps at #6 -> #2) + heals HP/Armor/Flight KI!
	if arena.mobile_pad != null:
		if str(arena.mobile_pad.get_slot_binding(10)) != "energy_recover":
			fail("v10.3 Energy Recover: dedicated MobileActionPad slot 10 must be bound to energy_recover, got '%s'" % str(arena.mobile_pad.get_slot_binding(10)))
			return
		var rec_btn: Button = arena.mobile_pad._slot_buttons.get(10) as Button
		if rec_btn == null or not rec_btn.visible:
			fail("v10.3 Energy Recover: dedicated button slot 10 must be visible for Son Goku")
			return
	p1_fm.player_hp = 600.0
	p1_fm.player_armor = 20.0
	goku.set("ki", 10.0)
	var rec_spr: AnimatedSprite2D = goku.get_node_or_null("Sprite") as AnimatedSprite2D
	if rec_spr != null:
		rec_spr.play(&"idle_combat")
	if not p1_fm.request_player_energy_recover():
		fail("v10 Recover: request_player_energy_recover failed")
		return
	if rec_spr != null:
		rec_spr.set_frame_and_progress(5, 0.0)
		p1_fm.step(0.02)
		if rec_spr.frame != 5:
			fail("v10.3 Recover Loop: frame #5 must play full duration without premature jump, got anim=%s frame=%d" % [String(rec_spr.animation), rec_spr.frame])
			return
		rec_spr.set_frame_and_progress(6, 0.0)
		p1_fm.step(0.02)
		if rec_spr.frame != 2:
			fail("v10.3 Recover Loop: entering #6 while recover_timer_s > 0.22 must wrap back to #2, got %d" % rec_spr.frame)
			return
	p1_fm.step(0.5)
	if p1_fm.player_hp <= 650.0 or p1_fm.player_armor <= 30.0 or float(goku.get("ki")) <= 15.0:
		fail("v10 Recover: 3s channel must restore HP, Armor & Flight KI (hp=%.1f arm=%.1f ki=%.1f)" % [p1_fm.player_hp, p1_fm.player_armor, float(goku.get("ki"))])
		return
	goku.set("recover_timer_s", 0.0)
	# 3) Universal Hard Stun (Flurry Kick applies to Boss & Monsters & Hero)
	var stun_slot: Dictionary = p1_fm.slots[0]
	p1_fm.apply_hard_stun_to_slot(stun_slot, 1.6)
	if float(stun_slot.get("hard_stun_timer_s", 0.0)) < 1.5:
		fail("v10 Flurry Stun: apply_hard_stun_to_slot must lock slot for >= 1.5s")
		return
	# 4) Atomic 12s CD (Sheet 21 exact 8 frames + 6 alternating homing bolts @ 2500px/s ignoring terrain) & Kamehameha 80 MP gate (2.0s charge + 3000px/s +20% size, immediate Column 2 fade on hit, ignoring terrain) targeting BOTH pointed ground & flying enemies!
	if absf(float(goku.get("ATOMIC_SPEED_PX_S")) - 2500.0) > 0.1 or int(goku.get("ATOMIC_BOLT_COUNT")) != 6 or absf(float(goku.get("KAME_MANA_COST")) - 80.0) > 0.1 or absf(float(goku.get("KAME_SPEED_PX_S")) - 3000.0) > 0.1 or absf(float(goku.get("KAME_CHARGE_DURATION_S")) - 2.0) > 0.05 or absf(float(goku.get("KAME_BEAM_SCALE_MUL")) - 1.2) > 0.01 or absf(float(goku.get("KAME_HOLD_S")) - 0.0) > 0.01:
		fail("v10.6 Tuning: Atomic=6 bolts@2500px/s, Kamehameha=80MP@3000px/s charge=2.0s scale=1.2x hold=0.0s required")
		return
	var atomic_spr: AnimatedSprite2D = goku.get_node_or_null("Sprite") as AnimatedSprite2D
	if atomic_spr != null:
		if atomic_spr.sprite_frames.get_frame_count(&"atomic_ground") != 8:
			fail("v10.6 Atomic: Sheet 21 atomic_ground must have exact 8 frames, got %d" % atomic_spr.sprite_frames.get_frame_count(&"atomic_ground"))
			return
		atomic_spr.play(&"idle_combat")
	if is_instance_valid(stun_slot.get("node")):
		var snode: Node2D = stun_slot.get("node") as Node2D
		snode.position = Vector2(goku.position.x + 1250.0, arena._ground_y_at(goku.position.x + 1250.0))
	p1_fm.pointer_kind = "enemy"
	p1_fm.pointer_slot_id = str(stun_slot.get("id", ""))
	if not p1_fm.request_player_atomic_blast() or absf(float(goku.get("atomic_cooldown_s")) - 12.0) > 0.2:
		fail("v10 Atomic: must trigger & set 12s cooldown, got %.2f" % float(goku.get("atomic_cooldown_s")))
		return
	if p1_fm.request_player_atomic_blast():
		fail("v10 Atomic: must reject recast while on 12s cooldown")
		return
	# Verify Atomic fires 6 curved bolts (#6 left x3 -> #7 right x3) @ 2500px/s with ignore_terrain=false (Điều 7.8) + >=30px muzzle clearance + Sheet 23 muzzle sparks!
	if atomic_spr != null:
		atomic_spr.frame = 6
		p1_fm.step(0.02)
		var bolts_after_1: int = int(p1_fm._hero_skill_projectiles.size())
		var first_bolt_ok: bool = bolts_after_1 >= 1 and absf(float(p1_fm._hero_skill_projectiles[0].get("speed", 0.0)) - 2500.0) <= 0.1 and (not bool(p1_fm._hero_skill_projectiles[0].get("ignore_terrain", true))) and str(p1_fm._hero_skill_projectiles[0].get("target", {}).get("id", "")) == p1_fm.pointer_slot_id
		for _step_a in range(8):
			p1_fm.step(0.065)
		var fire_log: Array = p1_fm._last_atomic_fire_log
		var frame_seq: Array[int] = []
		for ent_v in fire_log:
			var ent: Dictionary = ent_v as Dictionary
			frame_seq.append(int(ent.get("hand_frame", -1)))
			if float(ent.get("rear_gap_px", 0.0)) < 29.5:
				fail("v10.6+ Atomic: bolt spawn must keep >= 30px clearance outside muzzle flash tip, got %.2f" % float(ent.get("rear_gap_px", 0.0)))
				return
		if not first_bolt_ok or fire_log.size() != 6 or frame_seq != [6, 6, 6, 7, 7, 7] or not p1_fm._hero_atomic_pending_bolts.is_empty():
			fail("v10.6+ Atomic: must launch 6 curved bolts in [6,6,6,7,7,7] order (@2500px/s ignore_terrain=false) to pointed target (seq=%s pend=%d)" % [str(frame_seq), p1_fm._hero_atomic_pending_bolts.size()])
			return
		# Verify curved arc lateral deviation on bolt #0 vs chord
		var p_arc0: Dictionary = p1_fm._hero_skill_projectiles[0] if not p1_fm._hero_skill_projectiles.is_empty() else {}
		if not p_arc0.is_empty() and absf(float(p_arc0.get("arc_amp", 0.0))) < 20.0:
			fail("v10.6+ Atomic: bolts must follow curved arc (arc_amp > 20px)")
			return
		# Verify flipped-left 30px clearance too
		p1_fm._hero_skill_projectiles.clear()
		p1_fm._last_atomic_fire_log.clear()
		goku.scale = Vector2(-absf(goku.scale.x), goku.scale.y)
		p1_fm._spawn_atomic_bolt(goku, arena.char_scale, "ground_horiz", 6, 0)
		if p1_fm._last_atomic_fire_log.is_empty() or float(p1_fm._last_atomic_fire_log[0].get("rear_gap_px", 0.0)) < 29.5:
			fail("v10.6+ Atomic: flipped-left spawn must also keep >= 30px clearance outside muzzle tip")
			return
		goku.scale = Vector2(absf(goku.scale.x), goku.scale.y)

		# Verify atomic_air_down upgraded to 6 bolts [2,2,2,3,3,3] @ 1500px/s + muzzle flashes
		p1_fm._hero_skill_projectiles.clear()
		p1_fm._hero_atomic_muzzle_flashes.clear()
		p1_fm._last_atomic_fire_log.clear()
		p1_fm._hero_atomic_fired = false
		atomic_spr.play(&"atomic_air_down")
		atomic_spr.set_frame_and_progress(2, 0.0)
		p1_fm._step_hero_phase2_skills(0.0)
		for _step_air in range(6):
			p1_fm._step_hero_phase2_skills(0.071)
		var air_seq: Array[int] = []
		for ent_a in p1_fm._last_atomic_fire_log:
			air_seq.append(int((ent_a as Dictionary).get("hand_frame", -1)))
		if p1_fm._hero_skill_projectiles.size() != 6 or air_seq != [2, 2, 2, 3, 3, 3] or not p1_fm._hero_atomic_pending_bolts.is_empty() or p1_fm._hero_atomic_muzzle_flashes.is_empty():
			fail("v10.6+ Airborne Atomic must fire 6 bolts [2,2,2,3,3,3] with muzzle sparks (cnt=%d seq=%s)" % [p1_fm._hero_skill_projectiles.size(), str(air_seq)])
			return
		for bolt in p1_fm._hero_skill_projectiles:
			if not bool(bolt.get("air_down")) or float(bolt.get("speed")) != 1500.0 or bool(bolt.get("ignore_terrain", true)):
				fail("v10.6+ Airborne Atomic bolts must keep speed=1500px/s and ignore_terrain=false")
				return

		# Verify atomic_ground_up selects automatically when grounded pointing at flying target (dy < -65),
		# uses #6 as bridge (no premature fire), and fires 6 bolts from BOTH raised hands at #7 ([7,7,7,7,7,7])
		atomic_spr.play(&"idle_combat")
		p1_fm._hero_skill_projectiles.clear()
		p1_fm._last_atomic_fire_log.clear()
		goku.set("atomic_cooldown_s", 0.0)
		goku.set("flight_state", "ground")
		goku.position = Vector2(560.0, arena._ground_y_at(560.0))
		var up_fly_slot: Dictionary = {}
		for fsl_u in p1_fm.slots:
			var d_u: Dictionary = fsl_u as Dictionary
			if bool(d_u.get("alive", false)) and bool(d_u.get("is_flying", false)):
				up_fly_slot = d_u
				break
		if not up_fly_slot.is_empty():
			(up_fly_slot["node"] as Node2D).position = Vector2(880.0, 260.0)
			p1_fm.pointer_kind = "enemy"
			p1_fm.pointer_slot_id = str(up_fly_slot["id"])
			if not p1_fm.request_player_atomic_blast() or p1_fm._hero_atomic_mode != "ground_up" or String(atomic_spr.animation) != "atomic_ground_up":
				fail("v10.6+ Atomic Ground Up must trigger atomic_ground_up when grounded targeting flying enemy (mode=%s anim=%s)" % [p1_fm._hero_atomic_mode, String(atomic_spr.animation)])
				return
			atomic_spr.set_frame_and_progress(6, 0.0)
			p1_fm._step_hero_phase2_skills(0.0)
			if not p1_fm._last_atomic_fire_log.is_empty():
				fail("v10.6+ Atomic Ground Up frame #6 is bridge only and must not fire prematurely")
				return
			atomic_spr.set_frame_and_progress(7, 0.0)
			p1_fm._step_hero_phase2_skills(0.0)
			for _step_up in range(6):
				p1_fm._step_hero_phase2_skills(0.071)
			var up_seq: Array[int] = []
			for ent_u in p1_fm._last_atomic_fire_log:
				up_seq.append(int((ent_u as Dictionary).get("hand_frame", -1)))
			if up_seq != [7, 7, 7, 7, 7, 7]:
				fail("v10.6+ Atomic Ground Up must fire 6 bolts at 2-hands-raised frame #7 [7,7,7,7,7,7], got %s" % str(up_seq))
				return
			var up_h0: Vector2 = (p1_fm._last_atomic_fire_log[0] as Dictionary).get("hand_pos", Vector2.ZERO)
			var up_h3: Vector2 = (p1_fm._last_atomic_fire_log[3] as Dictionary).get("hand_pos", Vector2.ZERO)
			if up_h0.distance_to(up_h3) < 10.0:
				fail("v10.6+ Atomic Ground Up bolts 0..2 and 3..5 must fire from left and right raised palms separately")
				return
		p1_fm._hero_skill_projectiles.clear()
		atomic_spr.play(&"idle_combat")
	# Point specifically at a FLYING monster and verify Kamehameha 2.0s charge + 3000px/s +20% beam locks onto that flying target!
	var fly_kame_slot: Dictionary = {}
	for fsl_v in p1_fm.slots:
		var fsl: Dictionary = fsl_v as Dictionary
		if bool(fsl.get("alive", false)) and bool(fsl.get("is_flying", false)) and is_instance_valid(fsl.get("node")):
			fly_kame_slot = fsl
			break
	if not fly_kame_slot.is_empty():
		p1_fm.pointer_kind = "enemy"
		p1_fm.pointer_slot_id = str(fly_kame_slot.get("id", ""))
	p1_fm.player_mana = 70.0
	if p1_fm.request_player_kamehameha():
		fail("v10.1 Kamehameha: must require >= 80 Mana (rejected at 70 MP)")
		return
	p1_fm.player_mana = 100.0
	if not p1_fm.request_player_kamehameha() or absf(p1_fm.player_mana - 20.0) > 0.1:
		fail("v10.1 Kamehameha: must cast at 100 MP and consume exact 80 MP -> 20 MP, got %.1f" % p1_fm.player_mana)
		return
	if atomic_spr != null:
		if atomic_spr.sprite_frames.get_frame_count(&"kame_ground_horiz") != 7:
			fail("v10.6 Kamehameha: Sheet 28 kame_ground_horiz must have exact 7 frames, got %d" % atomic_spr.sprite_frames.get_frame_count(&"kame_ground_horiz"))
			return
		# Verify 2.0s charge holds before firing, then fires cleanly at ~2.0s!
		for _step_chg in range(18):
			p1_fm.step(0.10)
		if not p1_fm._hero_kame_beams.is_empty():
			fail("v10.6 Kamehameha: must charge for ~2.0s before firing (fired early at 1.80s!)")
			return
		p1_fm.step(0.12)
		p1_fm.step(0.12)
		if p1_fm._hero_kame_beams.is_empty() or absf(float(p1_fm._hero_kame_beams[0].get("speed", 0.0)) - 3000.0) > 0.1 or absf(float(p1_fm._hero_kame_beams[0].get("scale_mul", 0.0)) - 1.2) > 0.01 or absf(float(p1_fm._hero_kame_beams[0].get("hold_s", 99.0)) - 0.0) > 0.01 or absf(float(p1_fm._hero_kame_beams[0].get("fade_s", 0.0)) - 0.18) > 0.01 or bool(p1_fm._hero_kame_beams[0].get("ignore_terrain", true)):
			fail("v10.6+ Kamehameha: beam must fire after 2.0s charge at 3000px/s (+20% size, hold_s=0.0, fade_s=0.18) with Điều 7.8 terrain collision (ignore_terrain=false) (anim=%s beams=%d)" % [String(atomic_spr.animation), p1_fm._hero_kame_beams.size()])
			return
		if not fly_kame_slot.is_empty() and str(p1_fm._hero_kame_beams[0].get("target", {}).get("id", "")) != str(fly_kame_slot.get("id", "")):
			fail("v10.3 Kamehameha Pointer Lock: must aim directly at pointed flying target")
			return
		# Verify beam hits target and vanishes rapidly without any 1.0s hold!
		for _step_k in range(30):
			p1_fm.step(0.03)
		if not p1_fm._hero_kame_beams.is_empty():
			fail("v10.6 Kamehameha: beam must vanish immediately after target impact + 0.18s fade (no 1.0s hold), still active after 0.90s!")
			return
		atomic_spr.play(&"idle_combat")

	# 5) v10.2 Auto-Battle: KI exhaustion switches to ground target until KI full -> returns to flying + ranged skill priority on flying!
	var dec_air_kame: Dictionary = UtilityAIController.evaluate_hero_auto({
		"has_target": true, "is_songoku": true, "is_ssj": true, "is_busy": false,
		"player_pos": Vector2(1200.0, 700.0), "target_pos": Vector2(1400.0, 480.0),
		"edge_dist": 180.0, "v_gap": 180.0, "melee_range_px": 20.0,
		"stamina": 100.0, "mana": 100.0, "target_airborne": true,
		"is_airborne_flight": false, "can_fly": true, "can_light_attack": true,
		"can_kamehameha": true, "can_atomic": true,
	})
	var dec_air_atom: Dictionary = UtilityAIController.evaluate_hero_auto({
		"has_target": true, "is_songoku": true, "is_ssj": true, "is_busy": false,
		"player_pos": Vector2(1200.0, 700.0), "target_pos": Vector2(1400.0, 480.0),
		"edge_dist": 180.0, "v_gap": 180.0, "melee_range_px": 20.0,
		"stamina": 100.0, "mana": 30.0, "target_airborne": true,
		"is_airborne_flight": false, "can_fly": true, "can_light_attack": true,
		"can_kamehameha": false, "can_atomic": true,
	})
	if str(dec_air_kame.get("intent", "")) != "kamehameha" or str(dec_air_atom.get("intent", "")) != "atomic_blast":
		fail("v10.2 Auto Air Priority: expected kamehameha then atomic_blast on flying target, got %s / %s" % [str(dec_air_kame.get("intent", "")), str(dec_air_atom.get("intent", ""))])
		return
	var fly_slot_id: String = ""
	var gnd_slot_a: Dictionary = {}
	var gnd_slot_b: Dictionary = {}
	for sl_v in p1_fm.slots:
		var sl: Dictionary = sl_v as Dictionary
		if not bool(sl.get("alive", false)) or not is_instance_valid(sl.get("node")):
			continue
		if bool(sl.get("is_flying", false)) and fly_slot_id.is_empty():
			fly_slot_id = str(sl.get("id", ""))
		elif not bool(sl.get("is_flying", false)):
			if gnd_slot_a.is_empty():
				gnd_slot_a = sl
			elif gnd_slot_b.is_empty():
				gnd_slot_b = sl
	if not fly_slot_id.is_empty() and not gnd_slot_a.is_empty():
		p1_fm.reset_auto_battle_ki_lock()
		p1_fm.pointer_kind = "enemy"
		p1_fm.pointer_slot_id = fly_slot_id
		goku.set("is_ssj", true)
		goku.set("flight_state", "ground")
		goku.set("ki", 0.0)
		goku.set("ki_exhausted", true)
		p1_fm.player_mana = 0.0
		goku.set("atomic_cooldown_s", 12.0)
		p1_fm.step_hero_auto_battle(0.016)
		var sel_after_empty: Dictionary = p1_fm._find_slot_by_id(p1_fm.pointer_slot_id)
		if not bool(p1_fm._auto_ki_ground_lock) or bool(sel_after_empty.get("is_flying", true)):
			fail("v10.2 Auto KI Lock: exhausting KI must lock & switch immediately to ground target (lock=%s fly=%s)" % [str(p1_fm._auto_ki_ground_lock), str(sel_after_empty.get("is_flying", true))])
			return
		# Partial KI recovery (15/50 and 35/50) must STAY on ground target (zero yo-yo loop!)
		goku.set("ki_exhausted", false)
		goku.set("ki", 15.0)
		p1_fm.step_hero_auto_battle(0.016)
		goku.set("ki", 35.0)
		p1_fm.step_hero_auto_battle(0.016)
		var sel_mid_ki: Dictionary = p1_fm._find_slot_by_id(p1_fm.pointer_slot_id)
		if not bool(p1_fm._auto_ki_ground_lock) or bool(sel_mid_ki.get("is_flying", true)):
			fail("v10.2 Auto KI Hysteresis: partial KI (15..35/50) must NOT switch back to flying target (prevents yo-yo loop)")
			return
		# Full KI recovery (50/50) must unlock & automatically switch BACK to flying target!
		goku.set("ki", 50.0)
		p1_fm.step_hero_auto_battle(0.016)
		var sel_full_ki: Dictionary = p1_fm._find_slot_by_id(p1_fm.pointer_slot_id)
		if bool(p1_fm._auto_ki_ground_lock) or not bool(sel_full_ki.get("is_flying", false)):
			fail("v10.2 Auto KI Full Resume: full KI (50/50) must unlock & auto-return to flying target (lock=%s fly=%s)" % [str(p1_fm._auto_ki_ground_lock), str(sel_full_ki.get("is_flying", false))])
			return
		p1_fm.reset_auto_battle_ki_lock()

	# 6) v10.2 Flurry Kick (`26`): 30% slower (~0.783s), auto-lunges forward, +50px range (<=215px) stuns ALL enemies in range!
	if atomic_spr != null and not gnd_slot_a.is_empty() and not gnd_slot_b.is_empty():
		var flk_dur_s: float = arena._get_clip_duration_s(goku, "flurry_kick")
		if flk_dur_s < 0.74 or flk_dur_s > 0.84:
			fail("v10.2 Flurry Kick Speed: expected ~0.783s (-30%% speed), got %.3fs" % flk_dur_s)
			return
		atomic_spr.play(&"idle_combat")
		goku.set("flurry_cooldown_s", 0.0)
		goku.set("flight_state", "ground")
		var flk_start_x: float = 1200.0
		var flk_gy: float = arena._ground_y_at(flk_start_x)
		goku.position = Vector2(flk_start_x, flk_gy)
		goku.scale = Vector2(absf(goku.scale.x), goku.scale.y)
		var na: Node2D = gnd_slot_a.get("node") as Node2D
		var nb: Node2D = gnd_slot_b.get("node") as Node2D
		na.position = Vector2(flk_start_x + 120.0, arena._ground_y_at(flk_start_x + 120.0))
		nb.position = Vector2(flk_start_x + 200.0, arena._ground_y_at(flk_start_x + 200.0))
		gnd_slot_a["hard_stun_timer_s"] = 0.0
		gnd_slot_b["hard_stun_timer_s"] = 0.0
		p1_fm.pointer_slot_id = str(gnd_slot_a.get("id", ""))
		if not p1_fm.request_player_flurry_kick():
			fail("v10.2 Flurry Kick: request_player_flurry_kick failed")
			return
		for _fk_i in range(1, 6):
			atomic_spr.frame = _fk_i
			p1_fm.step(0.06)
		if goku.position.x <= flk_start_x + 40.0:
			fail("v10.2 Flurry Kick Lunge: Goku must lunge forward during kicks (start=%.1f end=%.1f)" % [flk_start_x, goku.position.x])
			return
		if float(gnd_slot_a.get("hard_stun_timer_s", 0.0)) < 1.2 or float(gnd_slot_b.get("hard_stun_timer_s", 0.0)) < 1.2:
			fail("v10.2 Flurry Kick AoE Stun: BOTH enemies within expanded +50px range must be stunned (a=%.2f b=%.2f)" % [float(gnd_slot_a.get("hard_stun_timer_s", 0.0)), float(gnd_slot_b.get("hard_stun_timer_s", 0.0))])
			return
		atomic_spr.play(&"idle_combat")
	goku.set("ki", 50.0)

	# v8 KO Ground Settle test: KO'd mid-air/hovering must clear Sprite.position.y & drop to ground via gravity!
	goku.position = Vector2(1800.0, arena._ground_y_at(1800.0) - 120.0)
	goku.set("flight_state", "flying")
	g_spr.position.y = -20.0
	p1_fm.set_player_immortal(false)
	p1_fm.player_dead = false
	p1_fm.player_hp = 10.0
	p1_fm.apply_damage_to_player(999.0)
	if not p1_fm.player_dead or absf(g_spr.position.y) > 0.01:
		fail("v8 KO: dying mid-air/combat_move must clear Sprite.position.y to 0.0 immediately")
		return
	for _ko_f in range(35):
		var sup_ko: float = arena.get_nearest_support_y_below(goku.position.x, goku.position.y)
		if goku.position.y < sup_ko - 0.5:
			arena._integrate_player_vertical(1.0 / 60.0, false)
	if absf(goku.position.y - arena._ground_y_at(1800.0)) > 1.5:
		fail("v8 KO: KO'd player must settle cleanly onto ground floor (y=%.1f vs ground=%.1f)" % [goku.position.y, arena._ground_y_at(1800.0)])
		return
	p1_fm.respawn_player_at_left()

	# v6 T3: Base Goku takes incoming hit -> AUTOMATICALLY activates SSJ1 (`transform_ssj`) + enters combat!
	p1_fm.start_field(true)
	p1_fm.set_player_immortal(false)
	p1_fm.player_hp = p1_fm.player_max_hp
	p1_fm.player_armor = p1_fm.player_max_armor
	p1_fm.player_armor_broken_timer_s = 0.0
	goku.call(&"reset_hero_state")
	g_spr.play(&"idle")
	p1_fm.apply_damage_to_player(20.0, Vector2(-99999.0, -99999.0), false, "melee")
	if not bool(goku.get("is_ssj")) or String(g_spr.animation) != "transform_ssj" or str(goku.get("game_state")) != "combat":
		fail("v6 T3: Base Goku taking damage must auto-activate SSJ1 (is_ssj=%s anim=%s state=%s)" % [str(goku.get("is_ssj")), String(g_spr.animation), str(goku.get("game_state"))])
		return

	# v6 T5: Player Armor Bar (100 max below Mana) drains on hit, breaks to 'hit' (08) STRICTLY ONCE at 0, does NOT re-trigger on subsequent hits while broken, and auto-refills after 3s!
	p1_fm.player_hp = p1_fm.player_max_hp
	p1_fm.player_armor = p1_fm.player_max_armor
	p1_fm.player_armor_broken_timer_s = 0.0
	goku.set("transform_invuln_s", 0.0)
	g_spr.play(&"idle_combat")
	for _arm_i in range(4):
		p1_fm.apply_damage_to_player(15.0, Vector2(-99999.0, -99999.0), false, "melee")
	if absf(p1_fm.player_armor - 20.0) > 0.1 or p1_fm.player_armor_broken_timer_s > 0.0 or String(g_spr.animation) == "hit":
		fail("v6 T5: 4 light hits must drain armor 100->20 without triggering hit (armor=%.1f, anim=%s)" % [p1_fm.player_armor, String(g_spr.animation)])
		return
	p1_fm.apply_damage_to_player(15.0, Vector2(-99999.0, -99999.0), false, "melee")
	if absf(p1_fm.player_armor) > 0.1 or absf(p1_fm.player_armor_broken_timer_s - 3.0) > 0.05 or String(g_spr.animation) != "hit":
		fail("v6 T5: 5th hit must break armor (0), start 3.0s timer & play 'hit' (08) ONCE (armor=%.1f, t=%.2f, anim=%s)" % [p1_fm.player_armor, p1_fm.player_armor_broken_timer_s, String(g_spr.animation)])
		return
	# Subsequent hit during broken-armor window MUST NOT re-trigger 'hit'!
	g_spr.play(&"idle_combat")
	p1_fm.apply_damage_to_player(15.0, Vector2(-99999.0, -99999.0), false, "skill")
	if String(g_spr.animation) == "hit":
		fail("v6 T5: Subsequent hits while armor is already broken MUST NOT re-trigger 'hit'!")
		return
	p1_fm.step(3.1)
	if absf(p1_fm.player_armor - 100.0) > 0.1 or p1_fm.player_armor_broken_timer_s > 0.0:
		fail("v6 T5: broken armor must auto-refill to 100 after 3s (armor=%.1f, t=%.2f)" % [p1_fm.player_armor, p1_fm.player_armor_broken_timer_s])
		return

	# v6 Tuning Melee Range (< 20px): normal attack misses at edge_gap=26px (>=20px) and hits at edge_gap=12px (<20px)!
	var rng_slot: Dictionary = p1_fm.slots[0]
	var rng_node: Node2D = rng_slot["node"] as Node2D
	p1_fm.pointer_kind = "enemy"
	p1_fm.pointer_slot_id = str(rng_slot["id"])
	goku.position = Vector2(rng_node.position.x - 260.0, rng_node.position.y)
	goku.position.x += float(p1_fm._compute_slot_edge_gap(rng_slot)) - 26.0
	var hp_before_26: float = float(rng_slot["hp"])
	p1_fm.call("_execute_player_melee_hit", "melee", 20.0, false)
	if absf(float(rng_slot["hp"]) - hp_before_26) > 0.1:
		fail("v6 Tuning: Hero normal melee at edge_gap=26px (>=20px) MUST miss, hp=%s/%s" % [str(rng_slot["hp"]), str(hp_before_26)])
		return
	goku.position.x += float(p1_fm._compute_slot_edge_gap(rng_slot)) - 12.0
	p1_fm.call("_execute_player_melee_hit", "melee", 20.0, false)
	if float(rng_slot["hp"]) >= hp_before_26 - 1.0:
		fail("v6 Tuning: Hero normal melee at edge_gap=12px (<20px) MUST hit!")
		return

	# v6 T6: Touch/normal attack on airborne flying monster automatically jumps & enters fly_aura!
	var fly_slot: Dictionary = p1_fm.slots[7] # f0 flying bat_chiroptera
	var fly_node: Node2D = fly_slot["node"] as Node2D
	p1_fm.pointer_kind = "enemy"
	p1_fm.pointer_slot_id = str(fly_slot["id"])
	goku.set("is_ssj", true)
	goku.set("flight_state", "ground")
	goku.position = Vector2(fly_node.position.x - 40.0, arena._ground_y_at(fly_node.position.x - 40.0))
	arena.player_vy = 0.0
	g_spr.play(&"idle_combat")
	var start_air_y: float = goku.position.y
	p1_fm.request_player_primary_action()
	if not p1_fm.auto_approach_active:
		fail("v6 T6: Attacking airborne monster from ground must activate auto-approach!")
		return
	var entered_air_flight := false
	for _af in range(28):
		p1_fm.call("_step_auto_approach", 1.0 / 60.0)
		if str(goku.get("flight_state")) == "flying":
			entered_air_flight = true
	if not entered_air_flight or goku.position.y >= start_air_y - 25.0:
		fail("v6 T6: Auto-approach to airborne monster must jump & enter fly_aura upward (flying=%s, dy=%.1f)" % [str(entered_air_flight), start_air_y - goku.position.y])
		return
	p1_fm.cancel_auto_approach()

	# v6 T7: AUTO toggle button + UtilityAIController.evaluate_hero_auto() (flying -> 1 teleport, 2 fly; close -> combo) + manual override disables AUTO!
	var u_air_tp: Dictionary = UtilityAIController.evaluate_hero_auto({
		"has_target": true, "is_songoku": true, "is_ssj": true, "is_busy": false,
		"player_pos": Vector2(400.0, 800.0), "target_pos": Vector2(450.0, 260.0),
		"edge_dist": 480.0, "v_gap": 450.0, "melee_range_px": 30.0,
		"stamina": 100.0, "mana": 0.0, "has_power_up": false, "target_airborne": true, "is_airborne_flight": false, "can_light_attack": true,
	})
	var u_air_fly: Dictionary = UtilityAIController.evaluate_hero_auto({
		"has_target": true, "is_songoku": true, "is_ssj": true, "is_busy": false,
		"player_pos": Vector2(400.0, 800.0), "target_pos": Vector2(450.0, 260.0),
		"edge_dist": 480.0, "v_gap": 450.0, "melee_range_px": 30.0,
		"stamina": 10.0, "mana": 0.0, "has_power_up": false, "target_airborne": true, "is_airborne_flight": false, "can_light_attack": true,
	})
	var u_close: Dictionary = UtilityAIController.evaluate_hero_auto({
		"has_target": true, "is_songoku": true, "is_ssj": true, "is_busy": false,
		"player_pos": Vector2(400.0, 800.0), "target_pos": Vector2(420.0, 800.0),
		"edge_dist": 18.0, "v_gap": 0.0, "melee_range_px": 30.0,
		"stamina": 50.0, "mana": 0.0, "has_power_up": false, "target_airborne": false, "is_airborne_flight": false, "can_light_attack": true,
	})
	if str(u_air_tp.get("intent", "")) != "teleport_static" or str(u_air_fly.get("intent", "")) != "fly_chase" or str(u_close.get("intent", "")) != "attack_combo":
		fail("v6 T7: Hero Utility AI mismatch: air_tp=%s air_fly=%s close=%s" % [str(u_air_tp.get("intent")), str(u_air_fly.get("intent")), str(u_close.get("intent"))])
		return
	arena.set_hero_auto_battle(true)
	if not arena.hero_auto_battle_enabled:
		fail("v6 T7: set_hero_auto_battle(true) must enable AUTO")
		return
	arena._on_mobile_pad_action(1, "attack_light")
	if arena.hero_auto_battle_enabled:
		fail("v6 T7: Manual action while AUTO is ON must immediately turn AUTO OFF (Owner A1)")
		return

	# v6 T8: Monster Peace vs Combat State Machine + Boss Exemption + Multi-player Flee Handoff!
	p1_fm.start_field(true)
	var peace_slot: Dictionary = p1_fm.slots[1] # g1 spinosaurus
	var peace_node: Node2D = peace_slot["node"] as Node2D
	if str(peace_slot.get("combat_state", "")) != "peace":
		fail("v6 T8: Fresh field monster must start in 'peace', got %s" % str(peace_slot.get("combat_state")))
		return
	goku.position = Vector2(peace_node.position.x - 40.0, peace_node.position.y)
	peace_slot["cooldown_s"] = 0.0
	if bool(p1_fm.call("_is_player_in_slot_aggro", peace_slot)):
		fail("v6 T8: Peaceful unprovoked monster MUST NOT aggro Hero walking beside it!")
		return
	# Attacking Boss Drum must NOT turn peaceful normal monsters into 'combat'!
	var b_v6: Dictionary = p1_fm.spawn_boss_drum(peace_node.position.x + 200.0)
	if str(b_v6.get("combat_state", "")) != "combat":
		fail("v6 T8: Boss Drum must ALWAYS be in 'combat' state!")
		return
	p1_fm.apply_damage_to_slot(b_v6, 100.0, 10.0)
	if str(peace_slot.get("combat_state", "")) != "peace":
		fail("v6 T8: Attacking Boss Drum must NOT provoke peaceful normal monsters!")
		return
	# Remote attacker 'remote_p1' provokes monster, monster commits 1 attack turn, 'remote_p1' flees -> finishes 1 turn, THEN stays 'combat' and aggros passing local Hero!
	p1_fm.apply_damage_to_slot(peace_slot, 50.0, 10.0, Vector2(-99999.0, -99999.0), "melee", false, Vector2.RIGHT, "remote_p1")
	if str(peace_slot.get("combat_state", "")) != "combat" or str(peace_slot.get("aggro_target_id", "")) != "remote_p1":
		fail("v6 T8: Damaged monster must enter 'combat' targeting attacker 'remote_p1'")
		return
	p1_fm.call("_start_slot_attack", peace_slot, "attack_light", 0.5)
	p1_fm.notify_attacker_fled("remote_p1")
	# Still finishing that 1 committed attack turn for remote_p1!
	if str(peace_slot.get("committed_target_id", "")) != "remote_p1":
		fail("v6 T8: Monster must finish its 1 committed turn against fleeing remote_p1 before switching!")
		return
	# Finish the committed attack turn -> now aggro_target_id clears, combat_state STAYS 'combat', and passing local Hero is IMMEDIATELY aggro'd!
	peace_slot["action_timer_s"] = 0.0
	p1_fm.call("_step_slot", peace_slot, 1.0 / 60.0)
	if str(peace_slot.get("combat_state", "")) != "combat" or not str(peace_slot.get("aggro_target_id", "")).is_empty() or not bool(p1_fm.call("_is_player_in_slot_aggro", peace_slot)):
		fail("v6 T8: After fleeing attacker's committed turn ends, provoked monster must stay 'combat' and aggro passing Hero!")
		return

	# T2: Persistent Target Pointer remains visible on locked enemy even after transient Red X fades out (>0.75s)!
	var cyc_res: Dictionary = p1_fm.cycle_target_pointer()
	if str(cyc_res.get("kind", "")) != "enemy" or str(cyc_res.get("slot_id", "")).is_empty():
		fail("v5 T2: cycle_pointer() must lock an enemy target, got %s" % str(cyc_res))
		return
	p1_fm.step(1.2)
	var ptr_info: Dictionary = p1_fm.get_active_target_pointer_info()
	if not bool(ptr_info.get("visible", false)) or not bool(ptr_info.get("persistent", false)) or str(ptr_info.get("kind", "")) != "enemy":
		fail("v5 T2: Target Pointer must stay persistently visible after 1.2s (got %s)" % str(ptr_info))
		return

	# T1: Monster freeze/no-counterattack regression checks (interrupted turn + out-of-zone provoke + airborne overhead anti-air!)
	var t_slot: Dictionary = p1_fm.slots[3] # g3 = t_rex (has turn clip + power_up)
	var t_node: Node2D = t_slot["node"] as Node2D
	t_node.set("_turn_pending", true)
	t_node.set("_turn_clip", &"turn")
	p1_fm.call("_trigger_slot_single_hit_anim", t_slot)
	if bool(arena.call("_is_fighter_turning", t_node)):
		fail("v5 T1: Interrupting a turning monster with hit must clear _turn_pending so it never freezes permanently!")
		return
	# Out-of-zone attack must provoke aggro instead of leaving monster unresponsive
	goku.position = Vector2(float(t_slot["zone_min_x"]) - 120.0, arena._ground_y_at(float(t_slot["zone_min_x"]) - 120.0))
	p1_fm.apply_damage_to_slot(t_slot, 25.0, 5.0)
	if not bool(p1_fm.call("_is_player_in_slot_aggro", t_slot)):
		fail("v5 T1: Monster damaged from outside its zone must become provoked and enter aggro!")
		return
	# Ground monster with player hovering directly overhead (>110px) must fire anti-air power_up instead of freezing in idle!
	t_slot["stun_timer_s"] = 0.0
	t_slot["hit_anim_timer_s"] = 0.0
	t_slot["cooldown_s"] = 0.0
	t_slot["action_clip"] = ""
	t_slot["action_timer_s"] = 0.0
	t_slot["turn_lock_s"] = 0.5
	goku.position = Vector2(t_node.position.x + 20.0, t_node.position.y - 165.0)
	p1_fm.call("_step_slot", t_slot, 1.0 / 60.0)
	if str(t_slot.get("action_clip", "")) != "power_up":
		fail("v5 T1: Ground monster with player hovering overhead must counterattack with 'power_up', got '%s'" % str(t_slot.get("action_clip", "")))
		return

	# v10.6+ regression: energy_recover must ONLY activate when grounded (rejected in jump/fly/fall) + MobileActionPad slot 10 disabled in air
	var MobilePadScriptV106 := preload("res://scenes/runtime/MobileActionPad.gd")
	var pad_v106 := MobilePadScriptV106.new() as Control
	root.add_child(pad_v106)
	pad_v106.configure_for_character("songoku", PackedStringArray(["idle_ssj", "energy_recover", "atomic_ground", "kame_ground_horiz", "barrier", "flurry_kick", "teleport"]), false)
	var gy_v106: float = arena._ground_y_at(600.0)
	goku.set("is_ssj", true)
	goku.set("recover_timer_s", 0.0)
	goku.set("recover_cooldown_s", 0.0)
	goku.position = Vector2(600.0, gy_v106 - 240.0)
	goku.set("flight_state", "flying")
	arena.set("player_vy", 0.0)
	if arena.is_player_grounded_for_recover():
		fail("v10.6+: is_player_grounded_for_recover must be false while flying")
		return
	if p1_fm.request_player_energy_recover() or goku.call("trigger_energy_recover", arena.is_player_grounded_for_recover()):
		fail("v10.6+: energy_recover must be rejected while flying")
		return
	if absf(goku.position.y - (gy_v106 - 240.0)) > 0.5 or str(goku.get("flight_state")) != "flying":
		fail("v10.6+: rejected energy_recover in flight must NOT force Goku onto the ground")
		return
	pad_v106.set_hero_stamina_and_state(100.0, 100.0, true, true, true, 0, 0.0, 0.0, 0.0, 0.0, 0.0, false)
	if not bool(pad_v106._slot_buttons[10].disabled):
		fail("v10.6+: MobileActionPad slot 10 (Hồi 3s) must be disabled while airborne")
		return
	goku.set("flight_state", "falling")
	if arena.is_player_grounded_for_recover() or p1_fm.request_player_energy_recover():
		fail("v10.6+: energy_recover must be rejected while falling")
		return
	goku.set("flight_state", "ground")
	goku.position = Vector2(600.0, gy_v106 - 48.0)
	arena.set("player_vy", -180.0)
	if arena.is_player_grounded_for_recover() or p1_fm.request_player_energy_recover():
		fail("v10.6+: energy_recover must be rejected while jumping")
		return
	goku.position = Vector2(600.0, gy_v106)
	arena.set("player_vy", 0.0)
	pad_v106.set_hero_stamina_and_state(100.0, 100.0, true, true, false, 0, 0.0, 0.0, 0.0, 0.0, 0.0, true)
	if bool(pad_v106._slot_buttons[10].disabled):
		fail("v10.6+: MobileActionPad slot 10 (Hồi 3s) must re-enable upon landing")
		return
	if not p1_fm.request_player_energy_recover():
		fail("v10.6+: energy_recover must succeed when grounded in SSJ1")
		return
	pad_v106.queue_free()

	# v10.6+ regression: Hero AI air->ground target switch must exit fly_prep/fly_aura (teleport or descend/land) instead of hovering until KI empties
	goku.set("recover_timer_s", 0.0)
	goku.set("recover_cooldown_s", 0.0)
	goku.get_node("Sprite").play(&"fly_aura")
	var gnd_slot_v106: Dictionary = p1_fm.slots[0]
	var gnd_node_v106: Node2D = gnd_slot_v106["node"] as Node2D
	gnd_slot_v106["alive"] = true
	gnd_slot_v106["hp"] = 500.0
	gnd_node_v106.position = Vector2(330.0, arena._ground_y_at(330.0))
	p1_fm.pointer_kind = "enemy"
	p1_fm.pointer_slot_id = str(gnd_slot_v106["id"])
	arena.set_hero_auto_battle(true)
	# Path A: low stamina (no teleport) -> diagonal descend + fast_drop -> land cleanly with KI preserved
	goku.set("ki", 50.0)
	goku.set("stamina", 10.0)
	goku.set("flight_state", "flying")
	goku.position = Vector2(600.0, 300.0)
	arena.set("player_vy", 0.0)
	var ai_desc_landed := false
	for _ai_i in range(180):
		await process_frame
		p1_fm.step_hero_auto_battle(1.0 / 60.0)
		if str(goku.get("flight_state")) == "ground" and goku.position.y >= arena._ground_y_at(goku.position.x) - 2.5:
			ai_desc_landed = true
			break
	if not ai_desc_landed or float(goku.get("ki")) <= 10.0:
		fail("v10.6+: Hero AI airborne->ground target must descend and land instead of fly_prep/fly_aura loop (fstate=%s y=%.1f ki=%.2f)" % [str(goku.get("flight_state")), goku.position.y, float(goku.get("ki"))])
		return
	# Path B: high stamina -> teleport_static relocates onto ground and clears flight_state
	goku.set("ki", 90.0)
	goku.set("stamina", 90.0)
	goku.set("flight_state", "flying")
	goku.position = Vector2(600.0, 300.0)
	goku.get_node("Sprite").play(&"fly_aura")
	var ai_tp_landed := false
	for _tp_i in range(60):
		await process_frame
		p1_fm.step_hero_auto_battle(1.0 / 60.0)
		arena._step_songoku_teleport_midclip()
		if str(goku.get("flight_state")) == "ground" and goku.position.y >= arena._ground_y_at(goku.position.x) - 2.5:
			ai_tp_landed = true
			break
	if not ai_tp_landed:
		fail("v10.6+: Hero AI teleport_static to ground target must land cleanly in flight_state='ground'")
		return
	# Path C: _step_auto_approach from air to ground target must descend & land
	arena.set_hero_auto_battle(false)
	goku.set("ki", 50.0)
	goku.set("stamina", 10.0)
	goku.set("flight_state", "flying")
	goku.position = Vector2(600.0, 300.0)
	arena.set("player_vy", 0.0)
	goku.get_node("Sprite").play(&"fly_aura")
	p1_fm.auto_approach_active = true
	p1_fm._auto_approach_kind = "enemy"
	p1_fm._auto_approach_slot_id = str(gnd_slot_v106["id"])
	p1_fm._auto_approach_timeout_s = 5.0
	var app_desc_landed := false
	for _ap_i in range(180):
		await process_frame
		if p1_fm.auto_approach_active:
			p1_fm._step_auto_approach(1.0 / 60.0)
		else:
			arena.step_player_movement(1.0 / 60.0, 0, 0, false, false, false, Vector2.ZERO)
		if str(goku.get("flight_state")) == "ground" and goku.position.y >= arena._ground_y_at(goku.position.x) - 2.5:
			app_desc_landed = true
			break
	if not app_desc_landed:
		fail("v10.6+: _step_auto_approach airborne->ground must descend and land (fstate=%s y=%.1f)" % [str(goku.get("flight_state")), goku.position.y])
		return
	# Path D: rapid target switching air <-> ground and invalidated target mid-approach must not stall or crash
	goku.set("flight_state", "flying")
	goku.position = Vector2(600.0, 300.0)
	arena.set_hero_auto_battle(true)
	if p1_fm.slots.size() >= 2:
		var slot_b: Dictionary = p1_fm.slots[1]
		p1_fm.pointer_slot_id = str(slot_b["id"])
		p1_fm.step_hero_auto_battle(1.0 / 60.0)
		p1_fm.pointer_slot_id = str(gnd_slot_v106["id"])
		p1_fm.step_hero_auto_battle(1.0 / 60.0)
	# Invalidate pointed target mid-chase
	gnd_slot_v106["alive"] = false
	var dec_dead: Dictionary = p1_fm.step_hero_auto_battle(1.0 / 60.0)
	if dec_dead.is_empty():
		fail("v10.6+: step_hero_auto_battle must return valid decision dictionary when pointed target becomes invalid mid-way")
		return
	gnd_slot_v106["alive"] = true
	arena.set_hero_auto_battle(false)

	# v10.6+ HUD & Sân Tập regression tests (Section 3 of docs/songoku-v10-6-upgrade-handoff.md)
	# 1) KI bar thickness reduced 40% (9.0 -> 5.4) & Shield-break icon radius equals Peace/Combat icon radius (7.5)
	if absf(OverheadBarsDrawScript.KI_BAR_WIDTH - 5.4) > 0.01 or absf(OverheadBarsDrawScript.STATE_ICON_RADIUS - 7.5) > 0.01:
		fail("v10.6+ HUD: KI_BAR_WIDTH must be 5.4 (60% of 9.0) and STATE_ICON_RADIUS must be 7.5")
		return
	# 2) Shield-break icon triggers ONLY when armor transitions >0 -> 0 (NOT when armor was already 0!)
	p1_fm.set_player_immortal(false)
	p1_fm.player_armor = 15.0
	p1_fm.player_armor_broken_timer_s = 0.0
	p1_fm.player_shield_break_icon_timer_s = 0.0
	p1_fm.apply_damage_to_player(10.0, goku.position, false, "heavy")
	if p1_fm.player_armor > 0.0 or p1_fm.player_shield_break_icon_timer_s <= 0.0:
		fail("v10.6+ HUD: Shield-break icon must trigger when hit drains armor >0 to 0")
		return
	# Now let icon timer expire while armor stays 0.0 -> another hit MUST NOT re-trigger shield-break icon!
	p1_fm.player_armor = 0.0
	p1_fm.player_armor_broken_timer_s = 0.0
	p1_fm.player_shield_break_icon_timer_s = 0.0
	p1_fm.apply_damage_to_player(10.0, goku.position, false, "heavy")
	if p1_fm.player_shield_break_icon_timer_s > 0.0:
		fail("v10.6+ HUD: Hit when armor is ALREADY 0 must NOT trigger shield-break icon")
		return
	# 3) Left cluster (Đăng xuất, Khu, Avatar, HeroSelectorDropdown) & Right cluster (removed Pixel/Thước/Tâm quái + Infinite Mana toggle)
	if arena.logout_button == null or arena.zone_selector == null or arena.hero_selector == null or arena.hero_avatar_panel == null:
		fail("v10.6+ HUD: Left cluster must include logout_button, zone_selector, hero_selector, and hero_avatar_panel")
		return
	if arena.hero_selector.item_count < 1:
		fail("v10.6+ HUD: hero_selector must populate playable heroes")
		return
	if arena.pixel_perfect_button != null or arena.ruler_button != null or arena.monster_range_button != null:
		fail("v10.6+ HUD: Pixel, Thước, and Tâm quái buttons must be removed from Sân Tập HUD")
		return
	if arena.infinite_mana_button == null or arena.infinite_mana_button.anchor_left < 0.9:
		fail("v10.6+ HUD: InfiniteManaButton must exist on the right cluster")
		return
	arena.set_infinite_mana_enabled(true)
	if not arena.infinite_mana_button.text.contains("BẬT") or absf(p1_fm.player_mana - p1_fm.player_max_mana) > 0.01:
		fail("v10.6+ HUD: Enabling Infinite Mana must show BẬT indicator and fill player_mana")
		return
	goku.set("kame_cooldown_s", 0.0)
	goku.set("flight_state", "ground")
	goku.position = Vector2(560.0, arena._ground_y_at(560.0))
	p1_fm.request_player_kamehameha()
	if absf(p1_fm.player_mana - p1_fm.player_max_mana) > 0.01:
		fail("v10.6+ HUD: Casting Kamehameha with Infinite Mana ON must keep mana full, got %.1f" % p1_fm.player_mana)
		return
	arena.set_infinite_mana_enabled(false)
	if not arena.infinite_mana_button.text.contains("TẮT"):
		fail("v10.6+ HUD: Disabling Infinite Mana must show TẮT indicator")
		return
	# 4) Boss dropdown summons same boss across TWO distinct maps (including map with NO fixed boss config)
	arena.set_sandbox_map_id("rocky_plateau")
	var b_map1: Dictionary = arena.spawn_selected_boss_now("drum")
	if b_map1.is_empty() or not bool(b_map1.get("alive", false)) or str(b_map1.get("map_id", "")) != "rocky_plateau":
		fail("v10.6+ HUD: Boss summon on map 1 (rocky_plateau) failed")
		return
	arena.set_sandbox_map_id("sandbox_unconfigured_plain", {"viewport": {"width": 1920, "height": 1080}, "gameplay": {"ground_y": 840.0}})
	var b_map2: Dictionary = arena.spawn_selected_boss_now("drum")
	if b_map2.is_empty() or not bool(b_map2.get("alive", false)) or str(b_map2.get("map_id", "")) != "sandbox_unconfigured_plain":
		fail("v10.6+ HUD: Boss summon on map 2 (without fixed boss config) failed")
		return
	arena.set_sandbox_map_id("rocky_plateau")
	# 5) Simultaneous multi-touch: holding Joystick while pressing skill button works independently
	var pad_mt := MobilePadScriptV106.new() as Control
	root.add_child(pad_mt)
	pad_mt.configure_for_character("songoku", PackedStringArray(["idle_ssj", "kame_ground_horiz", "atomic_ground", "energy_recover"]), false)
	pad_mt._analog_touch_idx = 0
	pad_mt.analog_vector = Vector2(0.85, 0.0)
	var mt_actions: Array[String] = []
	pad_mt.action_triggered.connect(func(_sid: int, act: String) -> void: mt_actions.append(act))
	pad_mt._on_slot_pressed(5)
	if pad_mt._analog_touch_idx != 0 or pad_mt.analog_vector.x < 0.8 or mt_actions.is_empty():
		fail("v10.6+ HUD: Holding Joystick while pressing skill button must preserve analog touch and emit skill action")
		return
	pad_mt.queue_free()

	# 6) Enemy/Boss flashing shield-break icon triggers ONLY when stamina drains >0 -> 0 (NOT when already 0)
	var sb_slot: Dictionary = p1_fm.slots[0]
	sb_slot["alive"] = true
	sb_slot["hp"] = 1000.0
	sb_slot["stamina"] = 20.0
	sb_slot["stun_timer_s"] = 0.0
	sb_slot["shield_break_icon_timer_s"] = 0.0
	p1_fm.apply_damage_to_slot(sb_slot, 10.0, 25.0)
	if float(sb_slot.get("shield_break_icon_timer_s", 0.0)) <= 0.0:
		fail("v10.6+ HUD: Monster shield-break icon must trigger when stamina drains >0 to 0")
		return
	sb_slot["stamina"] = 0.0
	sb_slot["stun_timer_s"] = 0.0
	sb_slot["shield_break_icon_timer_s"] = 0.0
	p1_fm.apply_damage_to_slot(sb_slot, 10.0, 25.0)
	if float(sb_slot.get("shield_break_icon_timer_s", 0.0)) > 0.0:
		fail("v10.6+ HUD: Monster hit when stamina is ALREADY 0 must NOT trigger shield-break icon")
		return

	# 7) Điều 7.8 terrain collision: Atomic bolt & Kamehameha beam stop when hitting solid terrain step wall (step edge ~2700..3000 -> floor 840 -> 890)
	p1_fm._hero_skill_projectiles.clear()
	p1_fm._hero_kame_beams.clear()
	p1_fm._hero_skill_projectiles.append({
		"pos": Vector2(2800.0, 875.0),
		"start_pos": Vector2(2800.0, 875.0),
		"end_pos": Vector2(2400.0, 875.0),
		"t_prog": 0.0,
		"arc_sign": 0.0,
		"arc_amp": 0.0,
		"dir": Vector2(-1.0, 0.0),
		"speed": 2500.0,
		"life_s": 1.0,
		"age_s": 0.0,
		"air_down": false,
		"mode": "ground_horiz",
		"damage": 55.0,
		"target": {},
		"ignore_terrain": false,
	})
	for _tb_i in range(20):
		p1_fm._step_hero_skill_projectiles_and_beams(0.016)
	if not p1_fm._hero_skill_projectiles.is_empty():
		fail("v10.6+ Điều 7.8: Atomic bolt fired into solid terrain step must stop/explode on terrain")
		return

	# 8) Online Vinh & Thái bug regression: remote peer snapshot with legacy "drum" MUST upgrade to songoku_hero_demo when local hero is Son Goku!
	p1_fm.sync_from_zone_snapshot({
		"uid_thai": {
			"id": "uid_thai",
			"kind": "player",
			"display_name": "Thái",
			"character_id": "drum",
			"x": 760.0,
			"y": arena._ground_y_at(760.0),
			"facing_left": true,
			"act": "idle_ssj",
			"hp": 1500.0,
			"max_hp": 1500.0,
			"mana": 50.0,
			"max_mana": 100.0,
			"alive": true,
		}
	}, {}, "uid_vinh")
	var r_thai: Dictionary = p1_fm.remote_player_slots.get("uid_thai", {})
	if r_thai.is_empty() or str(r_thai.get("character_id", "")) != "songoku":
		fail("v10.6+ Online Vinh/Thái fix: remote peer must render as 'songoku' (not legacy 'drum'), got '%s'" % str(r_thai.get("character_id", "")))
		return
	p1_fm.sync_from_zone_snapshot({}, {}, "uid_vinh")

	var verified_roster_count: int = arena.roster_characters.size()
	arena.queue_free()
	await process_frame
	print("[OK] Godot 4 ArenaSandbox 1920x1080 1:1 parity + Utility AI + Son Goku Phase 1 + %d characters PASSED!" % verified_roster_count)
	quit(0)
