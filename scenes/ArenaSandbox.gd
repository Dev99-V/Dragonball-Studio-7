class_name ArenaSandbox
extends Node2D
## Official DR7-Studio 16:9 (1920x1080) Landscape Mobile Arena Scene.
## Reads `res://assets/maps/rocky_plateau/arena-stage.json` and `res://assets/roster.json`
## directly so Godot 4 builds (Editor, Headless, Android APK, iOS IPA) and localhost:8080
## maintain exact 1:1 coordinate, scale, and visual parity.

const STAGE_JSON_PATH := "res://assets/maps/rocky_plateau/arena-stage.json"
const ROSTER_JSON_PATH := "res://assets/roster.json"
const UtilityAIControllerScript := preload("res://scenes/UtilityAIController.gd")

@export var default_character_id: String = "t_rex"

var stage_config: Dictionary = {}
var roster_characters: Array = []
var active_character_id: String = ""
var char_scale: float = 1.75
var enemy_scale: float = 1.75
var ground_y: float = 840.0
var walkable_min_x: float = 140.0
var walkable_max_x: float = 1780.0
var viewport_width: int = 1920
var viewport_height: int = 1080
var player_spawn_x: float = 560.0
var dummy_spawn_x: float = 1360.0
var fly_min_y: float = 60.0
var fly_default_y: float = 250.0
var fly_vertical_speed_px_per_s: float = 240.0
var jump_velocity_px_per_s: float = -780.0
var gravity_px_per_s2: float = 2000.0
var show_grid_overlay: bool = true

var enemy_character_id: String = ""
var _enemy_pinned: bool = false
var player_node: Node2D = null
var dummy_node: Node2D = null
var player_vy: float = 0.0
var player_facing_left: bool = false
var enemy_facing_left: bool = true
var utility_ai_enabled: bool = false
var ai_controller = UtilityAIControllerScript.new()
var ai_last_decision: Dictionary = {}
var _ai_action_clip: String = ""
var _ai_action_timer_s: float = 0.0
var _player_turn_boost_s: float = 0.0
var _ai_turn_boost_s: float = 0.0
var _player_turn_elapsed_s: float = 0.0
var _player_turn_duration_s: float = 0.0
var _player_turn_prev_dir: int = 1
var _ai_turn_elapsed_s: float = 0.0
var _ai_turn_duration_s: float = 0.0
var _ai_turn_prev_dir: int = -1
var _ai_turn_target_left: bool = true
var _char_index: int = 0

@onready var background_sprite: Sprite2D = get_node_or_null("BackgroundLayer/BackgroundSprite")
@onready var fighters_layer: Node2D = get_node_or_null("FightersLayer")
@onready var hud_label: Label = get_node_or_null("HUDLayer/HudLabel")


func _ready() -> void:
	load_stage_and_roster()
	_apply_stage_layout()
	if not roster_characters.is_empty():
		var start_id := default_character_id
		if _find_character_entry(start_id).is_empty():
			start_id = str(roster_characters[0].get("character_id", ""))
		select_character(start_id)


func load_stage_and_roster() -> void:
	stage_config = _read_json_dict(STAGE_JSON_PATH)
	var vp: Dictionary = stage_config.get("viewport", {})
	viewport_width = int(vp.get("width", 1920))
	viewport_height = int(vp.get("height", 1080))
	var gp: Dictionary = stage_config.get("gameplay", {})
	ground_y = float(gp.get("ground_y", 840.0))
	var bounds: Array = gp.get("walkable_bounds_x", [140, 1780])
	if bounds.size() >= 2:
		walkable_min_x = float(bounds[0])
		walkable_max_x = float(bounds[1])
	player_spawn_x = float(gp.get("player_spawn_x", 560.0))
	dummy_spawn_x = float(gp.get("dummy_spawn_x", 1360.0))
	char_scale = float(gp.get("character_scale_default", 2.0))
	enemy_scale = char_scale
	var fl: Dictionary = gp.get("flight", {})
	fly_min_y = float(fl.get("min_y", 60.0))
	fly_default_y = float(fl.get("default_y", 250.0))
	fly_vertical_speed_px_per_s = float(fl.get("vertical_speed_px_per_s", 240.0))
	jump_velocity_px_per_s = float(gp.get("jump_velocity_px_per_s", -780.0))
	gravity_px_per_s2 = float(gp.get("gravity_px_per_s2", 2000.0))
	ai_controller.configure_from_stage(stage_config)

	var roster := _read_json_dict(ROSTER_JSON_PATH)
	var chars_variant: Variant = roster.get("characters", [])
	roster_characters = chars_variant if chars_variant is Array else []


func _read_json_dict(res_path: String) -> Dictionary:
	if not FileAccess.file_exists(res_path):
		return {}
	var txt := FileAccess.get_file_as_string(res_path)
	var parsed: Variant = JSON.parse_string(txt)
	return parsed if parsed is Dictionary else {}


func _load_texture_2d(res_path: String) -> Texture2D:
	if res_path.is_empty():
		return null
	if ResourceLoader.exists(res_path):
		var loaded := ResourceLoader.load(res_path)
		if loaded is Texture2D:
			return loaded
	if FileAccess.file_exists(res_path):
		var bytes := FileAccess.get_file_as_bytes(res_path)
		var img := Image.new()
		var lower := res_path.to_lower()
		var err := ERR_FILE_UNRECOGNIZED
		if lower.ends_with(".jpg") or lower.ends_with(".jpeg"):
			err = img.load_jpg_from_buffer(bytes)
		elif lower.ends_with(".png"):
			err = img.load_png_from_buffer(bytes)
		if err == OK:
			return ImageTexture.create_from_image(img)
	return null


func _apply_stage_layout() -> void:
	var map_cfg: Dictionary = stage_config.get("map", {})
	var bg_path := str(map_cfg.get("background_res_path", "res://assets/maps/rocky_plateau/rocky-plateau-bg.jpg"))
	var bg_tex := _load_texture_2d(bg_path)
	if background_sprite != null and bg_tex != null:
		background_sprite.texture = bg_tex
		background_sprite.centered = false
		background_sprite.position = Vector2.ZERO
		var tex_size := bg_tex.get_size()
		if tex_size.x > 0.0 and tex_size.y > 0.0:
			background_sprite.scale = Vector2(
				float(viewport_width) / tex_size.x,
				float(viewport_height) / tex_size.y
			)
	queue_redraw()


func _find_character_entry(char_id: String) -> Dictionary:
	for idx in range(roster_characters.size()):
		var entry: Variant = roster_characters[idx]
		if entry is Dictionary and str(entry.get("character_id", "")) == char_id:
			_char_index = idx
			return entry
	return {}


func _resolve_prefab_path(entry: Dictionary) -> String:
	var modes: Dictionary = entry.get("modes", {})
	var comb: Dictionary = modes.get("combined_1layer", {})
	return str(comb.get("godot_prefab", ""))


func select_character(char_id: String) -> bool:
	var entry := _find_character_entry(char_id)
	if entry.is_empty():
		return false
	var prefab_path := _resolve_prefab_path(entry)
	if prefab_path.is_empty() or not ResourceLoader.exists(prefab_path):
		return false
	var loaded_res: Resource = ResourceLoader.load(prefab_path)
	if not (loaded_res is PackedScene):
		return false
	var packed := loaded_res as PackedScene

	_clear_fighter(player_node)

	active_character_id = char_id
	player_facing_left = false
	player_vy = 0.0
	char_scale = _get_entry_default_scale(entry)
	_player_turn_boost_s = 0.0
	_player_turn_elapsed_s = 0.0
	_player_turn_duration_s = 0.0

	var p_inst: Node = packed.instantiate()
	if not (p_inst is Node2D):
		return false

	player_node = p_inst as Node2D
	var parent_layer: Node = fighters_layer if fighters_layer != null else self
	parent_layer.add_child(player_node)
	player_node.name = "PlayerFighter"
	var spawn_y := fly_default_y if _is_flying_entry(entry) else ground_y
	_configure_fighter_instance(player_node, player_spawn_x, spawn_y, false, char_scale)

	var target_enemy := enemy_character_id if (_enemy_pinned and not enemy_character_id.is_empty()) else char_id
	if not select_enemy_character(target_enemy, false):
		_clear_fighter(dummy_node)
		dummy_node = null
		return false
	_update_hud()
	return true


func select_enemy_character(char_id: String, pin_enemy: bool = true) -> bool:
	var entry := _find_character_entry(char_id)
	if entry.is_empty():
		return false
	var prefab_path := _resolve_prefab_path(entry)
	if prefab_path.is_empty() or not ResourceLoader.exists(prefab_path):
		return false
	var loaded_res: Resource = ResourceLoader.load(prefab_path)
	if not (loaded_res is PackedScene):
		return false
	var packed := loaded_res as PackedScene

	_clear_fighter(dummy_node)
	var d_inst: Node = packed.instantiate()
	if not (d_inst is Node2D):
		return false

	enemy_character_id = char_id
	_enemy_pinned = pin_enemy
	enemy_facing_left = true
	enemy_scale = _get_entry_default_scale(entry)
	_ai_action_clip = ""
	_ai_action_timer_s = 0.0
	_ai_turn_boost_s = 0.0
	_ai_turn_elapsed_s = 0.0
	_ai_turn_duration_s = 0.0
	dummy_node = d_inst as Node2D
	var parent_layer: Node = fighters_layer if fighters_layer != null else self
	parent_layer.add_child(dummy_node)
	if player_node != null and dummy_node.get_index() > player_node.get_index():
		parent_layer.move_child(dummy_node, player_node.get_index())
	dummy_node.name = "SparringDummy"
	var enemy_spawn_y := fly_default_y if _is_flying_entry(entry) else ground_y
	_configure_fighter_instance(dummy_node, dummy_spawn_x, enemy_spawn_y, true, enemy_scale)
	enemy_facing_left = dummy_node.scale.x < 0.0
	ai_controller.reset_zone(dummy_spawn_x, walkable_min_x, walkable_max_x)
	ai_last_decision = {}
	_update_hud()
	queue_redraw()
	return true


func _clear_fighter(node: Node2D) -> void:
	if node != null and is_instance_valid(node):
		if node.get_parent() != null:
			node.get_parent().remove_child(node)
		node.queue_free()


func _configure_fighter_instance(fighter: Node2D, pos_x: float, pos_y: float, facing_left: bool, scale_override: float = -1.0) -> void:
	var sc := scale_override if scale_override > 0.0 else char_scale
	fighter.position = Vector2(pos_x, pos_y)
	fighter.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	fighter.scale = Vector2(-sc if facing_left else sc, sc)
	if fighter.has_method(&"spawn_with_facing"):
		fighter.call(&"spawn_with_facing", "left" if facing_left else "right")
	var spr := fighter.get_node_or_null("Sprite")
	if spr is AnimatedSprite2D:
		(spr as AnimatedSprite2D).texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
		(spr as AnimatedSprite2D).centered = false
		(spr as AnimatedSprite2D).play(&"idle")


func set_character_scale(new_scale: float) -> void:
	char_scale = clampf(snappedf(new_scale, 0.05), 0.5, 3.5)
	enemy_scale = char_scale
	if player_node != null:
		player_node.scale = Vector2(-char_scale if player_facing_left else char_scale, char_scale)
	if dummy_node != null:
		var dummy_left := dummy_node.scale.x < 0.0
		dummy_node.scale = Vector2(-enemy_scale if dummy_left else enemy_scale, enemy_scale)
	_update_hud()
	queue_redraw()


func set_utility_ai_enabled(enabled: bool) -> void:
	utility_ai_enabled = enabled
	_ai_action_clip = ""
	_ai_action_timer_s = 0.0
	ai_last_decision = {}
	if dummy_node != null:
		ai_controller.reset_zone(dummy_spawn_x, walkable_min_x, walkable_max_x)
		if not enabled:
			_play_fighter_clip(dummy_node, "idle")
	_update_hud()
	queue_redraw()


func _resolve_enemy_capabilities(entry: Dictionary, fighter: Node2D) -> Dictionary:
	var spr := fighter.get_node_or_null("Sprite") as AnimatedSprite2D
	var frames := spr.sprite_frames if spr != null else null
	var has_heavy := frames != null and frames.has_animation(&"attack_heavy")
	var light_clip := "attack_light"
	if frames != null and not frames.has_animation(&"attack_light") and frames.has_animation(&"attack_nomal"):
		light_clip = "attack_nomal"
	var loco_clip := "fly" if (frames != null and frames.has_animation(&"fly")) else "walk"
	return {
		"character_id": str(entry.get("character_id", enemy_character_id)),
		"is_flying": _is_flying_entry(entry),
		"sideways_locked": _is_sideways_locked(entry),
		"has_heavy": has_heavy,
		"light_clip": light_clip,
		"locomotion_clip": loco_clip,
	}


func _get_clip_duration_s(fighter: Node2D, clip_name: String) -> float:
	var spr := fighter.get_node_or_null("Sprite") as AnimatedSprite2D
	if spr == null or spr.sprite_frames == null:
		return 0.5
	var sname := StringName(clip_name)
	if not spr.sprite_frames.has_animation(sname):
		return 0.5
	var count := spr.sprite_frames.get_frame_count(sname)
	var ticks := 0.0
	for i in range(count):
		ticks += spr.sprite_frames.get_frame_duration(sname, i)
	var fps := maxf(1.0, spr.sprite_frames.get_animation_speed(sname))
	return maxf(0.1, ticks / fps)


func _play_fighter_clip(fighter: Node2D, clip_name: String) -> bool:
	var sname := StringName(clip_name)
	if fighter.has_method(&"play_clip"):
		return bool(fighter.call(&"play_clip", sname))
	var spr := fighter.get_node_or_null("Sprite") as AnimatedSprite2D
	if spr != null and spr.sprite_frames != null and spr.sprite_frames.has_animation(sname):
		spr.play(sname)
		return true
	return false


func _ensure_fighter_locomotion(fighter: Node2D, clip_name: String) -> void:
	var spr := fighter.get_node_or_null("Sprite") as AnimatedSprite2D
	if spr != null and (spr.animation != StringName(clip_name) or not spr.is_playing()):
		_play_fighter_clip(fighter, clip_name)


func _find_character_entry_ro(char_id: String) -> Dictionary:
	for entry in roster_characters:
		if entry is Dictionary and str(entry.get("character_id", "")) == char_id:
			return entry
	return {}


func step_utility_ai(delta: float) -> Dictionary:
	if player_node == null or dummy_node == null:
		return {}
	ai_controller.tick_cooldown(delta)
	_ai_turn_boost_s = maxf(0.0, _ai_turn_boost_s - maxf(0.0, delta))
	if _ai_action_timer_s > 0.0:
		_ai_action_timer_s = maxf(0.0, _ai_action_timer_s - maxf(0.0, delta))
	var turn_pending_val: Variant = dummy_node.get("_turn_pending")
	var turn_pending := bool(turn_pending_val) if turn_pending_val != null else false
	var spr := dummy_node.get_node_or_null("Sprite") as AnimatedSprite2D
	if not turn_pending and not _ai_action_clip.is_empty():
		var clip_finished_early := spr != null and String(spr.animation) == _ai_action_clip and not spr.is_playing()
		if _ai_action_timer_s <= 0.0 or clip_finished_early:
			_ai_action_clip = ""
			_ai_action_timer_s = 0.0
	var is_busy := turn_pending or not _ai_action_clip.is_empty()

	var p_entry := _find_character_entry_ro(active_character_id)
	var e_entry := _find_character_entry_ro(enemy_character_id)
	if e_entry.is_empty():
		e_entry = p_entry
	var caps := _resolve_enemy_capabilities(e_entry, dummy_node)
	var p_dims := _get_body_dims(p_entry)
	var e_dims := _get_body_dims(e_entry)
	var pw := float(p_dims.x) if p_dims.x > 0 else 140.0
	var ph := float(p_dims.y) if p_dims.y > 0 else 140.0
	var ew := float(e_dims.x) if e_dims.x > 0 else 140.0
	var eh := float(e_dims.y) if e_dims.y > 0 else 140.0

	if turn_pending and str(caps["character_id"]) != "chilopoda" and _ai_turn_duration_s > 0.0:
		_ai_turn_elapsed_s += maxf(0.0, delta)
		var turn_mom := _turn_momentum_factor(_ai_turn_elapsed_s, _ai_turn_duration_s, _ai_turn_prev_dir, -1 if _ai_turn_target_left else 1)
		var turn_spd := _get_walk_speed_px_per_s(e_entry, enemy_scale) * turn_mom
		dummy_node.position.x = clampf(
			dummy_node.position.x + turn_spd * maxf(0.0, delta),
			ai_controller.zone_min_x,
			ai_controller.zone_max_x
		)

	var target_rect: Rect2 = UtilityAIControllerScript.compute_body_rect(player_node.position.x, player_node.position.y, pw, ph, char_scale)
	var self_rect: Rect2 = UtilityAIControllerScript.compute_body_rect(dummy_node.position.x, dummy_node.position.y, ew, eh, enemy_scale)

	var res := ai_controller.evaluate({
		"character_id": caps["character_id"],
		"is_flying": caps["is_flying"],
		"has_heavy": caps["has_heavy"],
		"light_clip": caps["light_clip"],
		"self_rect": self_rect,
		"target_rect": target_rect,
		"self_x": dummy_node.position.x,
		"target_x": player_node.position.x,
		"is_busy": is_busy,
	})

	if res.get("intent", "") == "busy":
		ai_last_decision = res
		return res

	var desired_left := bool(res.get("desired_face_left", enemy_facing_left))
	if not bool(caps["sideways_locked"]):
		var cur_left := dummy_node.scale.x < 0.0
		if cur_left != desired_left:
			var started_turn := false
			if dummy_node.has_method(&"set_facing_left") and _has_turn_clip(e_entry):
				dummy_node.set_meta("_arena_turn_resume_clip", str(caps["locomotion_clip"]))
				started_turn = bool(dummy_node.call(&"set_facing_left", desired_left))
			var now_pending_val: Variant = dummy_node.get("_turn_pending")
			if started_turn and now_pending_val != null and bool(now_pending_val):
				_ai_turn_prev_dir = -1 if cur_left else 1
				_ai_turn_target_left = desired_left
				_ai_turn_elapsed_s = 0.0
				_ai_turn_duration_s = _get_clip_duration_s(dummy_node, "turn")
				_ai_action_clip = "turn"
				_ai_action_timer_s = _ai_turn_duration_s
				ai_last_decision = res
				queue_redraw()
				return res
			# Prefabs without a perspective turn clip (e.g. Pteranodon, King Crab) reorient horizontally cleanly + burst boost
			enemy_facing_left = desired_left
			dummy_node.scale = Vector2(-enemy_scale if enemy_facing_left else enemy_scale, enemy_scale)
			_ai_turn_boost_s = 0.26

	var intent := str(res.get("intent", "idle"))
	if intent == "attack":
		var clip := str(res.get("attack_clip", caps["light_clip"]))
		if str(caps["character_id"]) == "chilopoda" and dummy_node.has_method(&"set_combat_target_global"):
			var clamped_tx := clampf(player_node.position.x, walkable_min_x, walkable_max_x)
			dummy_node.call(&"set_combat_target_global", Vector2(clamped_tx, ground_y))
		elif str(caps["character_id"]) == "dilophosaurus" and dummy_node.has_method(&"set_slash_target_global"):
			dummy_node.call(&"set_slash_target_global", player_node.position)
		if _play_fighter_clip(dummy_node, clip):
			_ai_action_clip = clip
			_ai_action_timer_s = _get_clip_duration_s(dummy_node, clip)
	elif intent == "patrol" or intent == "chase":
		var move_dir := int(res.get("move_dir", 0))
		if move_dir != 0:
			var boost := _get_turn_speed_multiplier(e_entry) if _ai_turn_boost_s > 0.0 else 1.0
			var spd := _get_walk_speed_px_per_s(e_entry, enemy_scale) * boost
			dummy_node.position.x = clampf(
				dummy_node.position.x + float(move_dir) * spd * delta,
				ai_controller.zone_min_x,
				ai_controller.zone_max_x
			)
			if bool(caps["is_flying"]):
				dummy_node.position.y = clampf(dummy_node.position.y, fly_min_y, ground_y)
			_ensure_fighter_locomotion(dummy_node, str(caps["locomotion_clip"]))
		else:
			_ensure_fighter_locomotion(dummy_node, "idle")
	elif intent == "wait_cooldown":
		_ensure_fighter_locomotion(dummy_node, "idle")

	enemy_facing_left = dummy_node.scale.x < 0.0
	ai_last_decision = res
	queue_redraw()
	return res


func _get_entry_default_scale(entry: Dictionary) -> float:
	var rc: Dictionary = entry.get("render_contract", {})
	var loc: Dictionary = rc.get("locomotion", {})
	if loc.has("default_scale") and float(loc.get("default_scale", 0.0)) > 0.0:
		return float(loc.get("default_scale", 2.0))
	var gp: Dictionary = stage_config.get("gameplay", {})
	return float(gp.get("character_scale_default", 2.0))


func _get_turn_speed_multiplier(entry: Dictionary) -> float:
	var rc: Dictionary = entry.get("render_contract", {})
	var turning: Variant = rc.get("turning", {})
	if turning is Dictionary and turning.has("turn_speed_multiplier"):
		return maxf(1.0, float(turning.get("turn_speed_multiplier", 1.0)))
	return 1.0


func _has_turn_clip(entry: Dictionary) -> bool:
	var rc: Dictionary = entry.get("render_contract", {})
	var turning: Variant = rc.get("turning", {})
	if turning is Dictionary:
		var clip_val: Variant = turning.get("clip", null)
		return clip_val != null and not str(clip_val).is_empty()
	return false


func _turn_momentum_factor(elapsed_s: float, duration_s: float, prev_dir: int, target_dir: int) -> float:
	if duration_s <= 0.0:
		return float(target_dir)
	var p := clampf(elapsed_s / duration_s, 0.0, 1.0)
	if p < 0.38:
		return float(prev_dir) * (1.0 - p / 0.38) * 0.45
	return float(target_dir) * ((p - 0.38) / 0.62)


func _has_clip_name(fighter: Node2D, clip_name: StringName) -> bool:
	var spr := fighter.get_node_or_null("Sprite") as AnimatedSprite2D
	return spr != null and spr.sprite_frames != null and spr.sprite_frames.has_animation(clip_name)


func _is_sideways_locked(entry: Dictionary) -> bool:
	var rc: Dictionary = entry.get("render_contract", {})
	var loc: Dictionary = rc.get("locomotion", {})
	return bool(loc.get("sideways_strafe", false) or loc.get("lock_spawn_facing", false) or not loc.get("allow_turn_or_flip", true))


func _is_flying_entry(entry: Dictionary) -> bool:
	var rc: Dictionary = entry.get("render_contract", {})
	var loc: Dictionary = rc.get("locomotion", {})
	return str(loc.get("kind", "ground")) == "flight"


func _get_body_dims(entry: Dictionary) -> Vector2i:
	var m: Dictionary = entry.get("map_sync_metrics", {})
	var bbox: Variant = m.get("body_only_bbox_px", null)
	if bbox is Dictionary:
		return Vector2i(int(bbox.get("w", 0)), int(bbox.get("h", 0)))
	if bbox is Array and bbox.size() >= 2:
		return Vector2i(int(bbox[0]), int(bbox[1]))
	return Vector2i.ZERO


func _get_walk_speed_px_per_s(entry: Dictionary, scale_override: float = -1.0) -> float:
	var sc := scale_override if scale_override > 0.0 else char_scale
	var rc: Dictionary = entry.get("render_contract", {})
	var loc: Dictionary = rc.get("locomotion", {})
	if loc.has("speed_px_per_second") and float(loc.get("speed_px_per_second", 0.0)) > 0.0:
		return float(loc.get("speed_px_per_second", 135.0)) * sc
	var patrol: Variant = loc.get("patrol", {})
	if patrol is Dictionary and patrol.has("speed_px_per_second"):
		return float(patrol.get("speed_px_per_second", 135.0)) * sc
	return 270.0 * (sc / 2.0)


func step_flight_vertical(fly_dir_y: float, delta: float) -> float:
	if player_node == null:
		return fly_default_y
	player_node.position.y = clampf(
		player_node.position.y + fly_dir_y * fly_vertical_speed_px_per_s * (char_scale / 2.0) * delta,
		fly_min_y,
		ground_y
	)
	player_vy = 0.0
	return player_node.position.y


func _physics_process(delta: float) -> void:
	if Engine.is_editor_hint() or DisplayServer.get_name() == "headless":
		return
	if player_node == null:
		return

	var entry := _find_character_entry(active_character_id)
	var is_flying := _is_flying_entry(entry)

	var dir := 0
	if Input.is_key_pressed(KEY_D) or Input.is_key_pressed(KEY_RIGHT):
		dir += 1
	if Input.is_key_pressed(KEY_A) or Input.is_key_pressed(KEY_LEFT):
		dir -= 1
	var is_run := Input.is_key_pressed(KEY_SHIFT)

	var fly_dir_y := 0
	if is_flying:
		if Input.is_key_pressed(KEY_W) or Input.is_key_pressed(KEY_UP):
			fly_dir_y -= 1
		if Input.is_key_pressed(KEY_S) or Input.is_key_pressed(KEY_DOWN):
			fly_dir_y += 1
		step_flight_vertical(float(fly_dir_y), delta)
	else:
		if (Input.is_key_pressed(KEY_W) or Input.is_key_pressed(KEY_SPACE) or Input.is_key_pressed(KEY_UP)) and player_node.position.y >= ground_y - 1.0:
			player_vy = jump_velocity_px_per_s

		player_node.position.y += player_vy * delta
		if player_node.position.y < ground_y:
			player_vy += gravity_px_per_s2 * delta
		else:
			player_node.position.y = ground_y
			player_vy = 0.0

	var sideways_locked := _is_sideways_locked(entry)
	var walk_speed := _get_walk_speed_px_per_s(entry)
	var base_speed := walk_speed * 1.6 if is_run else walk_speed
	_player_turn_boost_s = maxf(0.0, _player_turn_boost_s - delta)
	var turning_now: bool = bool(player_node.get("_turn_pending")) if player_node.get("_turn_pending") != null else false

	if not sideways_locked and not turning_now and dir != 0:
		var want_left := dir < 0
		if want_left != player_facing_left:
			if _has_turn_clip(entry) and player_node.has_method(&"set_facing_left"):
				var resume_name := "run" if is_run else ("fly" if (is_flying and _has_clip_name(player_node, &"fly")) else "walk")
				player_node.set_meta("_arena_turn_resume_clip", resume_name)
				var turn_clip_name := str(entry.get("render_contract", {}).get("turning", {}).get("clip", "turn"))
				var prev_dir_val := -1 if player_facing_left else 1
				if bool(player_node.call(&"set_facing_left", want_left)) and bool(player_node.get("_turn_pending")):
					_player_turn_prev_dir = prev_dir_val
					_player_turn_elapsed_s = 0.0
					_player_turn_duration_s = _get_clip_duration_s(player_node, turn_clip_name)
					turning_now = true
			if not turning_now:
				player_facing_left = want_left
				player_node.scale = Vector2(-char_scale if player_facing_left else char_scale, char_scale)
				_player_turn_boost_s = 0.26

	if turning_now:
		if active_character_id != "chilopoda" and _player_turn_duration_s > 0.0:
			_player_turn_elapsed_s += delta
			var tgt_left_v: Variant = player_node.get("_turn_target_left")
			var tgt_dir := -1 if (bool(tgt_left_v) if tgt_left_v != null else (dir < 0)) else 1
			var mom := _turn_momentum_factor(_player_turn_elapsed_s, _player_turn_duration_s, _player_turn_prev_dir, tgt_dir)
			player_node.position.x = clampf(player_node.position.x + base_speed * mom * delta, walkable_min_x, walkable_max_x)
	else:
		player_facing_left = player_node.scale.x < 0.0
		var p_boost := _get_turn_speed_multiplier(entry) if _player_turn_boost_s > 0.0 else 1.0
		player_node.position.x = clampf(
			player_node.position.x + float(dir) * base_speed * p_boost * delta,
			walkable_min_x,
			walkable_max_x
		)

		var spr := player_node.get_node_or_null("Sprite")
		if spr is AnimatedSprite2D:
			var aspr := spr as AnimatedSprite2D
			var target_clip := &"idle"
			if not is_flying and player_node.position.y < ground_y - 2.0 and aspr.sprite_frames != null and aspr.sprite_frames.has_animation(&"jump"):
				target_clip = &"jump"
			elif (dir != 0 or fly_dir_y != 0) and aspr.sprite_frames != null:
				if is_run and aspr.sprite_frames.has_animation(&"run"):
					target_clip = &"run"
				elif aspr.sprite_frames.has_animation(&"walk"):
					target_clip = &"walk"
				elif aspr.sprite_frames.has_animation(&"fly"):
					target_clip = &"fly"
			if aspr.animation != target_clip or not aspr.is_playing():
				aspr.play(target_clip)

	if utility_ai_enabled:
		step_utility_ai(delta)

	_update_hud()


func _unhandled_input(event: InputEvent) -> void:
	if not (event is InputEventKey):
		return
	var kev := event as InputEventKey
	if not kev.pressed or kev.echo:
		return
	if kev.keycode == KEY_1:
		set_character_scale(1.0)
	elif kev.keycode == KEY_2:
		set_character_scale(2.0)
	elif kev.keycode == KEY_3:
		set_character_scale(3.0)
	elif kev.keycode == KEY_MINUS or kev.keycode == KEY_BRACKETLEFT:
		set_character_scale(char_scale - 0.05)
	elif kev.keycode == KEY_EQUAL or kev.keycode == KEY_BRACKETRIGHT:
		set_character_scale(char_scale + 0.05)
	elif kev.keycode == KEY_G:
		show_grid_overlay = not show_grid_overlay
		queue_redraw()
	elif kev.keycode == KEY_Q or kev.keycode == KEY_TAB:
		if not roster_characters.is_empty():
			_char_index = (_char_index + 1) % roster_characters.size()
			var next_id := str(roster_characters[_char_index].get("character_id", ""))
			if not next_id.is_empty():
				select_character(next_id)


func _draw() -> void:
	if not show_grid_overlay:
		return
	# Subtle 64px ruler ticks along ground line y = 840 and walkable bounds [140, 1780]
	draw_line(Vector2(walkable_min_x, ground_y), Vector2(walkable_max_x, ground_y), Color(0.98, 0.80, 0.08, 0.65), 2.0)
	draw_line(Vector2(walkable_min_x, ground_y - 120.0), Vector2(walkable_min_x, ground_y + 24.0), Color(0.22, 0.74, 0.97, 0.55), 2.0)
	draw_line(Vector2(walkable_max_x, ground_y - 120.0), Vector2(walkable_max_x, ground_y + 24.0), Color(0.22, 0.74, 0.97, 0.55), 2.0)
	if utility_ai_enabled:
		var zy := ground_y + 12.0
		draw_line(Vector2(ai_controller.zone_min_x, zy), Vector2(ai_controller.zone_max_x, zy), Color(0.96, 0.62, 0.04, 0.90), 3.0)
		draw_line(Vector2(ai_controller.zone_min_x, zy - 16.0), Vector2(ai_controller.zone_min_x, zy + 8.0), Color(0.96, 0.62, 0.04, 0.90), 2.0)
		draw_line(Vector2(ai_controller.zone_max_x, zy - 16.0), Vector2(ai_controller.zone_max_x, zy + 8.0), Color(0.96, 0.62, 0.04, 0.90), 2.0)


func _update_hud() -> void:
	if hud_label == null:
		return
	var entry := _find_character_entry(active_character_id)
	var dims := _get_body_dims(entry)
	var scaled_w := int(round(float(dims.x) * char_scale))
	var scaled_h := int(round(float(dims.y) * char_scale))
	var pct_h := (float(scaled_h) / float(viewport_height) * 100.0) if viewport_height > 0 else 0.0
	var spd := int(round(_get_walk_speed_px_per_s(entry)))
	var px := int(round(player_node.position.x)) if player_node != null else int(player_spawn_x)
	var py := int(round(player_node.position.y)) if player_node != null else int(ground_y)
	var ai_txt := ""
	if utility_ai_enabled:
		var edge_d := int(round(float(ai_last_decision.get("edge_dist", -1.0))))
		ai_txt = " | AI[%s]: %s gap=%dpx chain=%d/%d zone=[%d..%d]" % [
			enemy_character_id,
			str(ai_controller.last_reason),
			edge_d,
			ai_controller.light_chain_count,
			ai_controller.light_hits_before_heavy,
			int(round(ai_controller.zone_min_x)),
			int(round(ai_controller.zone_max_x)),
		]
	hud_label.text = "%dx%d (16:9) | %s | %.2fx Nearest (%dx%dpx, %.1f%% 1080p) | Speed: %d px/s | Pos: (%d, %d) | [1/2/3/-/+] Scale%s" % [
		viewport_width, viewport_height, active_character_id, char_scale, scaled_w, scaled_h, pct_h, spd, px, py, ai_txt
	]


func get_stage_metrics() -> Dictionary:
	return {
		"viewport_width": viewport_width,
		"viewport_height": viewport_height,
		"ground_y": ground_y,
		"fly_min_y": fly_min_y,
		"fly_default_y": fly_default_y,
		"walkable_min_x": walkable_min_x,
		"walkable_max_x": walkable_max_x,
		"player_spawn_x": player_spawn_x,
		"dummy_spawn_x": dummy_spawn_x,
		"char_scale": char_scale,
		"enemy_scale": enemy_scale,
		"active_character_id": active_character_id,
		"enemy_character_id": enemy_character_id,
		"player_position": [player_node.position.x, player_node.position.y] if player_node != null else [0.0, 0.0],
		"dummy_position": [dummy_node.position.x, dummy_node.position.y] if dummy_node != null else [0.0, 0.0],
		"utility_ai": {
			"enabled": utility_ai_enabled,
			"enemy_character_id": enemy_character_id,
			"zone_min_x": ai_controller.zone_min_x,
			"zone_max_x": ai_controller.zone_max_x,
			"light_chain_count": ai_controller.light_chain_count,
			"cooldown_remaining": ai_controller.cooldown_remaining,
			"last_intent": ai_controller.last_intent,
			"last_reason": ai_controller.last_reason,
			"last_attack_clip": str(ai_last_decision.get("attack_clip", "")),
			"last_edge_dist": float(ai_last_decision.get("edge_dist", -1.0)),
		},
	}
