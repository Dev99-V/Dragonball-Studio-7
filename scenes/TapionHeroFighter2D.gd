class_name TapionHeroFighter2D
extends SaiyanHeroFighter2D
## Playable Hero Controller — Tapion (Complete 47/47 Source Setup: Core + 10-Step Sword Combo + Ocarina & 4 Signature Skills):
## - Single-form Konatsian Hero (`is_ssj = true` always).
## - Peace State: `idle` (playing Ocarina flute) + independent rainbow musical aura (`PeaceAuraFX` @ z=-1) + `walk` (200 px/s).
## - Combat State: `combat_enter` -> `idle_combat` + `combat_move` (400 back / 500 fwd px/s + brake #1/#2).
## - 10-Step Sword Combo (`attack_light`..`attack_10` LOOP X2 + `atk10_impact_fx` ground slam).
## - Full Ocarina & 4 Signature Skills (`tapion_skills_fx.tres`):
##     1. `barrier` -> `barrier_cast` (9f) + active `BarrierDomeFX` (`barrier_dome_fx`)
##     2. `energy_recover` -> `energy_recover` (8f Ocarina white-cyan lightning aura, grounded)
##     3. `kentaima` -> `kentaima_cast` (4f) + flying `kentaima_wave_fx` crescent + `kentaima_impact_fx` (6f)
##     4. `mahasenko` -> `mahasenko_ground` (3f) / `mahasenko_air` (2f) + `mahasenko_hand_fx` + `mahasenko_beam_h_fx`/`mahasenko_beam_air_fx` + `mahasenko_impact_fx` (5f)
##     5. `antamina` -> `antamina_combo` (11f: charge + rings + flash + fire) + `antamina_stream_fx` (1->5) + `antamina_impact_fx` (4f)
##     6. `bukadai` -> `bukadai_rush` (6f high-speed slash dash) + `bukadai_vanish_fx` + `bukadai_flash_fx` + `bukadai_sphere_fx` (4f) + `bukadai_impact_fx` (3f)

const TAPION_COMBO_CLIPS: Array[String] = [
	"attack_light",  # 1. tấn công 1 (6f)
	"attack_2",      # 2. tấn công 2 (5f)
	"attack_3",      # 3. tấn công 3 (5f)
	"attack_4",      # 4. tấn công 4 (2f)
	"attack_5",      # 5. tấn công 5 (3f)
	"attack_6",      # 6. tấn công 6 (3f)
	"attack_7",      # 7. Tấn công 7 — kiếm khí xanh mặt đất (5f)
	"attack_8",      # 8. Tấn công 8 — kiếm khí xanh xoáy lên không (5f)
	"attack_9",      # 9. tấn công 9 — kiếm khí xanh chém đôi trên không (5f)
	"attack_10",     # 10. tấn công 10 (nặng) — LOOP X2 nhảy bổ kiếm cắm đất (8 steps)
]

const TAPION_COMBO_HIT_FRAMES := {
	"attack_light": [3],
	"attack_2": [1, 3],
	"attack_3": [1],
	"attack_4": [1],
	"attack_5": [1, 2],
	"attack_6": [1],
	"attack_7": [1, 2],
	"attack_8": [1, 2],
	"attack_9": [2, 3],
	"attack_10": [3, 6, 7],
}

const KENTAIMA_CD_S: float = 1.5
const MAHASENKO_CD_S: float = 1.5
const ANTAMINA_CD_S: float = 2.0
const BUKADAI_CD_S: float = 1.8

var kentaima_cooldown_s: float = 0.0
var mahasenko_cooldown_s: float = 0.0
var antamina_cooldown_s: float = 0.0
var bukadai_cooldown_s: float = 0.0

var _peace_aura_fx: AnimatedSprite2D = null
var _barrier_dome_fx: AnimatedSprite2D = null
var _hand_muzzle_fx: AnimatedSprite2D = null
var _ground_impact_fx: AnimatedSprite2D = null
var _skills_fx_frames: SpriteFrames = null

var _impact_fired_for_swing: bool = false
var _skill_fx_fired_for_cast: bool = false
var _bukadai_dashed_for_cast: bool = false
var _active_projectiles: Array[Dictionary] = []
var _oneshot_fx_nodes: Array[AnimatedSprite2D] = []


func _init() -> void:
	is_ssj = true


func _ready() -> void:
	super._ready()
	is_ssj = true
	_ensure_tapion_fx_nodes()


func _exit_tree() -> void:
	_clear_spawned_fx()


func _clear_spawned_fx() -> void:
	for pr in _active_projectiles:
		var n := pr.get("node") as Node2D
		if n != null and is_instance_valid(n):
			n.queue_free()
	_active_projectiles.clear()
	for fn in _oneshot_fx_nodes:
		if fn != null and is_instance_valid(fn):
			fn.queue_free()
	_oneshot_fx_nodes.clear()


func is_hero_tapion() -> bool:
	return true


func can_attack() -> bool:
	return true


func can_jump() -> bool:
	return true


func can_fly() -> bool:
	return (not ki_exhausted) and ki > 0.001


func get_hero_display_name() -> String:
	return "Tapion"


func reset_hero_state() -> void:
	super.reset_hero_state()
	is_ssj = true
	kentaima_cooldown_s = 0.0
	mahasenko_cooldown_s = 0.0
	antamina_cooldown_s = 0.0
	bukadai_cooldown_s = 0.0
	_impact_fired_for_swing = false
	_skill_fx_fired_for_cast = false
	_bukadai_dashed_for_cast = false
	_clear_spawned_fx()
	_update_peace_aura_visibility()
	_update_barrier_dome_visibility(0.0)


func trigger_transform_toggle() -> String:
	is_ssj = true
	return ""


func trigger_kentaima() -> bool:
	if kentaima_cooldown_s > 0.0:
		return false
	kentaima_cooldown_s = KENTAIMA_CD_S
	_skill_fx_fired_for_cast = false
	enter_combat()
	if is_airborne_flight():
		hover_timer_s = HOVER_TIMEOUT_S
	hero_state_changed.emit()
	return true


func trigger_mahasenko() -> bool:
	if mahasenko_cooldown_s > 0.0:
		return false
	mahasenko_cooldown_s = MAHASENKO_CD_S
	_skill_fx_fired_for_cast = false
	enter_combat()
	if is_airborne_flight():
		hover_timer_s = HOVER_TIMEOUT_S
	hero_state_changed.emit()
	return true


func trigger_antamina() -> bool:
	if antamina_cooldown_s > 0.0:
		return false
	antamina_cooldown_s = ANTAMINA_CD_S
	_skill_fx_fired_for_cast = false
	enter_combat()
	if is_airborne_flight():
		hover_timer_s = HOVER_TIMEOUT_S
	hero_state_changed.emit()
	return true


func trigger_bukadai() -> bool:
	if bukadai_cooldown_s > 0.0:
		return false
	bukadai_cooldown_s = BUKADAI_CD_S
	_skill_fx_fired_for_cast = false
	_bukadai_dashed_for_cast = false
	enter_combat()
	if is_airborne_flight():
		hover_timer_s = HOVER_TIMEOUT_S
	hero_state_changed.emit()
	return true


func get_clip_state_flags() -> Dictionary:
	var c := (game_state == "combat")
	return {
		"game_state": game_state,
		"peace": not c,
		"combat": c,
		"walk": not c,
		"walk_ssj": not c,
		"idle_ssj_aura": not c,
		"combat_move": c,
		"idle_combat": c,
		"attack": c,
	}


func get_current_combo_clip() -> String:
	return TAPION_COMBO_CLIPS[posmod(combo_step, TAPION_COMBO_CLIPS.size())]


func pop_next_combo_attack() -> Dictionary:
	enter_combat()
	if is_airborne_flight():
		hover_timer_s = HOVER_TIMEOUT_S
	var idx := posmod(combo_step, TAPION_COMBO_CLIPS.size())
	var clip := TAPION_COMBO_CLIPS[idx]
	combo_step = (idx + 1) % TAPION_COMBO_CLIPS.size()
	var is_heavy := (idx >= 6)
	var is_finisher := (clip == "attack_10")
	var rolled := roll_strike_damage(is_heavy, is_finisher)
	var hit_frames: Array = TAPION_COMBO_HIT_FRAMES.get(clip, [1])
	_impact_fired_for_swing = false
	hero_state_changed.emit()
	return {
		"step_index": idx,
		"step_number": idx + 1,
		"clip": clip,
		"is_heavy": is_heavy,
		"damage": float(rolled["damage"]),
		"is_crit": bool(rolled["is_crit"]),
		"hit_frames": hit_frames.duplicate(),
		"has_gold_slash_60": false,
		"gold_slash_frame": 99,
		"gold_slash_damage": 60.0,
	}


func resolve_locomotion_clip(moving: bool, airborne: bool) -> StringName:
	if flight_state == "flying":
		return &"fly_aura"
	if flight_state == "hovering":
		return &"fly_prep"
	if airborne or flight_state == "falling" or jump_land_hold_s > 0.0:
		return &"jump"
	if moving:
		return &"combat_move" if game_state == "combat" else &"walk"
	if game_state == "combat":
		return &"idle_combat"
	return &"idle"


func _ensure_tapion_fx_nodes() -> void:
	if _peace_aura_fx == null:
		_peace_aura_fx = get_node_or_null("PeaceAuraFX") as AnimatedSprite2D
		if _peace_aura_fx != null and _peace_aura_fx.sprite_frames != null:
			_skills_fx_frames = _peace_aura_fx.sprite_frames
	if _barrier_dome_fx == null:
		_barrier_dome_fx = get_node_or_null("BarrierDomeFX") as AnimatedSprite2D
	if _hand_muzzle_fx == null:
		_hand_muzzle_fx = get_node_or_null("HandMuzzleFX") as AnimatedSprite2D
		if _hand_muzzle_fx != null and not _hand_muzzle_fx.animation_finished.is_connected(_on_hand_muzzle_finished):
			_hand_muzzle_fx.animation_finished.connect(_on_hand_muzzle_finished)
	if _ground_impact_fx == null:
		_ground_impact_fx = get_node_or_null("GroundImpactFX") as AnimatedSprite2D
		if _ground_impact_fx != null:
			_ground_impact_fx.top_level = true
			if _skills_fx_frames == null and _ground_impact_fx.sprite_frames != null:
				_skills_fx_frames = _ground_impact_fx.sprite_frames
			if not _ground_impact_fx.animation_finished.is_connected(_on_ground_impact_finished):
				_ground_impact_fx.animation_finished.connect(_on_ground_impact_finished)
	if _skills_fx_frames == null and ResourceLoader.exists("res://review/tapion_demo/fx_bundle/godot/tapion_skills_fx.tres"):
		_skills_fx_frames = load("res://review/tapion_demo/fx_bundle/godot/tapion_skills_fx.tres") as SpriteFrames


func _on_hand_muzzle_finished() -> void:
	if _hand_muzzle_fx != null:
		_hand_muzzle_fx.visible = false


func _on_ground_impact_finished() -> void:
	if _ground_impact_fx != null:
		_ground_impact_fx.visible = false


func _update_peace_aura_visibility() -> void:
	_ensure_tapion_fx_nodes()
	if _peace_aura_fx == null or sprite == null:
		return
	var show_aura := (game_state == "peace") and (flight_state == "ground") and String(sprite.animation) == "idle"
	if show_aura:
		if not _peace_aura_fx.visible:
			_peace_aura_fx.visible = true
		if not _peace_aura_fx.is_playing() or _peace_aura_fx.animation != &"peace_aura_fx":
			_peace_aura_fx.play(&"peace_aura_fx")
	else:
		if _peace_aura_fx.visible:
			_peace_aura_fx.visible = false
			_peace_aura_fx.stop()


func _update_barrier_dome_visibility(_delta: float) -> void:
	_ensure_tapion_fx_nodes()
	if _barrier_dome_fx == null or sprite == null:
		return
	var casting_barrier := String(sprite.animation) == "barrier_cast" and sprite.is_playing()
	if barrier_timer_s > 0.0 and not casting_barrier:
		_barrier_dome_fx.visible = true
		if _barrier_dome_fx.animation != &"barrier_dome_fx":
			_barrier_dome_fx.animation = &"barrier_dome_fx"
		_barrier_dome_fx.pause()
		if barrier_timer_s <= 0.25:
			_barrier_dome_fx.frame = 4
		else:
			var cyc := 1 + (int(floor((BARRIER_DURATION_S - barrier_timer_s) * 10.0)) % 3)
			_barrier_dome_fx.frame = cyc
	else:
		_barrier_dome_fx.visible = false


func _find_arena_node() -> Node2D:
	var p := get_parent()
	while p != null:
		if p.has_method(&"terrain_blocks_segment") and p.get("field_manager") != null:
			return p as Node2D
		p = p.get_parent()
	return null


func _spawn_oneshot_fx(clip_name: StringName, world_pos: Vector2, facing_sign: float = 1.0, anchor_mode: String = "center", scale_mul: float = 1.0) -> AnimatedSprite2D:
	_ensure_tapion_fx_nodes()
	if _skills_fx_frames == null or not _skills_fx_frames.has_animation(clip_name):
		return null
	var fx := AnimatedSprite2D.new()
	fx.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	fx.sprite_frames = _skills_fx_frames
	fx.centered = false
	if anchor_mode == "ground":
		fx.offset = Vector2(-144.0, -248.0)
	elif anchor_mode == "muzzle_left":
		fx.offset = Vector2(-20.0, -176.0)
	else:
		fx.offset = Vector2(-144.0, -176.0)
	var sc := (absf(scale.y) if not is_zero_approx(scale.y) else 1.0) * scale_mul
	fx.top_level = true
	fx.global_position = world_pos
	fx.scale = Vector2(facing_sign * sc, sc)
	fx.z_index = 26
	var host: Node = get_parent() if get_parent() != null else self
	host.add_child(fx)
	fx.play(clip_name)
	_oneshot_fx_nodes.append(fx)
	fx.animation_finished.connect(func() -> void:
		_oneshot_fx_nodes.erase(fx)
		if is_instance_valid(fx):
			fx.queue_free()
	)
	return fx


func _play_hand_muzzle_flash(rel_offset: Vector2) -> void:
	_ensure_tapion_fx_nodes()
	if _hand_muzzle_fx == null or _hand_muzzle_fx.sprite_frames == null:
		return
	if not _hand_muzzle_fx.sprite_frames.has_animation(&"mahasenko_hand_fx"):
		return
	_hand_muzzle_fx.position = rel_offset
	_hand_muzzle_fx.visible = true
	_hand_muzzle_fx.frame = 0
	_hand_muzzle_fx.play(&"mahasenko_hand_fx")


func _spawn_skill_projectile(clip_name: StringName, impact_clip: StringName, impact_anchor: String, start_pos: Vector2, vel_vec: Vector2, facing_sign: float, max_dist: float, damage_val: float, stationary_stream: bool = false) -> void:
	_ensure_tapion_fx_nodes()
	if _skills_fx_frames == null or not _skills_fx_frames.has_animation(clip_name):
		return
	var node := AnimatedSprite2D.new()
	node.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	node.sprite_frames = _skills_fx_frames
	node.centered = false
	node.offset = Vector2(-20.0, -176.0) if stationary_stream else Vector2(-144.0, -176.0)
	var sc := absf(scale.y) if not is_zero_approx(scale.y) else 1.0
	node.top_level = true
	node.global_position = start_pos
	node.scale = Vector2(facing_sign * sc, sc)
	node.z_index = 25
	var host: Node = get_parent() if get_parent() != null else self
	host.add_child(node)
	node.play(clip_name)
	_active_projectiles.append({
		"node": node,
		"clip": String(clip_name),
		"impact_clip": impact_clip,
		"impact_anchor": impact_anchor,
		"pos": start_pos,
		"start_pos": start_pos,
		"vel": vel_vec,
		"facing_sign": facing_sign,
		"max_dist": max_dist,
		"damage": damage_val,
		"stationary": stationary_stream,
		"age_s": 0.0,
		"max_age_s": 0.42 if stationary_stream else 0.95,
		"hit_done": false,
	})


func _apply_demo_skill_hit_at(hit_pos: Vector2, radius_px: float, dmg: float, facing_sign: float, ground_snap_impact: bool = false) -> Vector2:
	var arena := _find_arena_node()
	if arena == null:
		return hit_pos
	var fm = arena.get("field_manager")
	if fm == null or not bool(fm.get("active")):
		return hit_pos
	var slots_arr: Array = fm.call(&"_get_combat_slots")
	for s in slots_arr:
		if not (s is Dictionary) or not bool(s.get("alive", false)) or not is_instance_valid(s.get("node")):
			continue
		var cpos: Vector2 = fm.call(&"_get_slot_core_pos", s)
		if cpos.distance_to(hit_pos) <= radius_px:
			fm.call(&"apply_damage_to_slot", s, dmg, 25.0, cpos, "skill", false, Vector2(facing_sign, 0.0))
			if ground_snap_impact:
				return Vector2(cpos.x, float(arena.call(&"_ground_y_at", cpos.x)))
			return cpos
	if ground_snap_impact:
		return Vector2(hit_pos.x, float(arena.call(&"_ground_y_at", hit_pos.x)))
	return hit_pos


func _step_active_projectiles(delta: float) -> void:
	var arena := _find_arena_node()
	for i in range(_active_projectiles.size() - 1, -1, -1):
		var pr: Dictionary = _active_projectiles[i]
		pr["age_s"] = float(pr["age_s"]) + delta
		var node := pr.get("node") as AnimatedSprite2D
		if node == null or not is_instance_valid(node):
			_active_projectiles.remove_at(i)
			continue
		var facing_sign: float = float(pr["facing_sign"])
		var stationary: bool = bool(pr["stationary"])
		if stationary:
			# Antamina stream / stationary beam: check hit along stream length (+240px ahead) once at mid-stream!
			if not bool(pr["hit_done"]) and float(pr["age_s"]) >= 0.14:
				pr["hit_done"] = true
				var tip_pos: Vector2 = (pr["start_pos"] as Vector2) + Vector2(facing_sign * 220.0, 0.0)
				var imp_pos := _apply_demo_skill_hit_at(tip_pos, 130.0, float(pr["damage"]), facing_sign, false)
				_spawn_oneshot_fx(pr["impact_clip"] as StringName, imp_pos, facing_sign, str(pr["impact_anchor"]))
			if float(pr["age_s"]) >= float(pr["max_age_s"]) or not node.is_playing():
				node.queue_free()
				_active_projectiles.remove_at(i)
			continue

		var old_p: Vector2 = pr["pos"] as Vector2
		var vel: Vector2 = pr["vel"] as Vector2
		var new_p: Vector2 = old_p + vel * delta
		pr["pos"] = new_p
		node.global_position = new_p

		# Keep flying crescent wave on main frames 1..2 while airborne
		if str(pr["clip"]) == "kentaima_wave_fx" and node.frame >= 3:
			node.frame = 1

		var hit_now := false
		var impact_p := new_p
		if arena != null and bool(arena.call(&"terrain_blocks_segment", old_p, new_p)):
			hit_now = true
			if str(pr["impact_anchor"]) == "ground":
				impact_p = Vector2(new_p.x, float(arena.call(&"_ground_y_at", new_p.x)))
		elif arena != null and arena.get("field_manager") != null and bool(arena.get("field_manager").get("active")):
			var fm = arena.get("field_manager")
			for s in fm.call(&"_get_combat_slots"):
				if not (s is Dictionary) or not bool(s.get("alive", false)) or not is_instance_valid(s.get("node")):
					continue
				var sc_pos: Vector2 = fm.call(&"_get_slot_core_pos", s)
				if new_p.distance_to(sc_pos) <= 78.0:
					fm.call(&"apply_damage_to_slot", s, float(pr["damage"]), 28.0, sc_pos, "skill", false, vel.normalized())
					hit_now = true
					impact_p = Vector2(sc_pos.x, float(arena.call(&"_ground_y_at", sc_pos.x))) if str(pr["impact_anchor"]) == "ground" else sc_pos
					break

		var dist_traveled := new_p.distance_to(pr["start_pos"] as Vector2)
		if hit_now or dist_traveled >= float(pr["max_dist"]) or float(pr["age_s"]) >= float(pr["max_age_s"]):
			if str(pr["impact_anchor"]) == "ground" and arena != null:
				impact_p = Vector2(impact_p.x, float(arena.call(&"_ground_y_at", impact_p.x)))
			_spawn_oneshot_fx(pr["impact_clip"] as StringName, impact_p, facing_sign, str(pr["impact_anchor"]))
			node.queue_free()
			_active_projectiles.remove_at(i)


func _process(delta: float) -> void:
	if kentaima_cooldown_s > 0.0:
		kentaima_cooldown_s = maxf(0.0, kentaima_cooldown_s - delta)
	if mahasenko_cooldown_s > 0.0:
		mahasenko_cooldown_s = maxf(0.0, mahasenko_cooldown_s - delta)
	if antamina_cooldown_s > 0.0:
		antamina_cooldown_s = maxf(0.0, antamina_cooldown_s - delta)
	if bukadai_cooldown_s > 0.0:
		bukadai_cooldown_s = maxf(0.0, bukadai_cooldown_s - delta)

	_update_peace_aura_visibility()
	_update_barrier_dome_visibility(delta)
	_step_active_projectiles(delta)

	if sprite == null:
		return
	var anim := String(sprite.animation)
	var facing_sign := -1.0 if scale.x < 0.0 else 1.0
	var sc := absf(scale.y) if not is_zero_approx(scale.y) else 1.0

	# 1. Attack 10 ground slam plume
	if anim == "attack_10":
		if sprite.frame >= 7 and not _impact_fired_for_swing:
			_impact_fired_for_swing = true
			_spawn_atk10_ground_impact()
	elif _impact_fired_for_swing:
		_impact_fired_for_swing = false

	# 2. Kentaima crescent blade wave
	if anim == "kentaima_cast" and sprite.is_playing():
		if sprite.frame >= 2 and not _skill_fx_fired_for_cast:
			_skill_fx_fired_for_cast = true
			var w_start := global_position + Vector2(66.0 * facing_sign * sc, -74.0 * sc)
			_spawn_skill_projectile(&"kentaima_wave_fx", &"kentaima_impact_fx", "ground", w_start, Vector2(1050.0 * facing_sign, 0.0), facing_sign, 680.0, 60.0, false)
	# 3. Mahasenko Ground horizontal beam
	elif anim == "mahasenko_ground" and sprite.is_playing():
		if sprite.frame >= 2 and not _skill_fx_fired_for_cast:
			_skill_fx_fired_for_cast = true
			_play_hand_muzzle_flash(Vector2(54.0, -74.0))
			var m_start := global_position + Vector2(62.0 * facing_sign * sc, -74.0 * sc)
			_spawn_skill_projectile(&"mahasenko_beam_h_fx", &"mahasenko_impact_fx", "center", m_start, Vector2(1380.0 * facing_sign, 0.0), facing_sign, 720.0, 65.0, false)
	# 4. Mahasenko Air diagonal beam
	elif anim == "mahasenko_air" and sprite.is_playing():
		if sprite.frame >= 1 and not _skill_fx_fired_for_cast:
			_skill_fx_fired_for_cast = true
			_play_hand_muzzle_flash(Vector2(42.0, -64.0))
			var a_start := global_position + Vector2(48.0 * facing_sign * sc, -58.0 * sc)
			var diag_dir := Vector2(0.76 * facing_sign, 0.65).normalized()
			_spawn_skill_projectile(&"mahasenko_beam_air_fx", &"mahasenko_impact_fx", "center", a_start, diag_dir * 1320.0, facing_sign, 720.0, 65.0, false)
	# 5. Antamina multi-phase charge -> concentric rings -> 1..5 yellow stream
	elif anim == "antamina_combo" and sprite.is_playing():
		if sprite.frame >= 8 and not _skill_fx_fired_for_cast:
			_skill_fx_fired_for_cast = true
			var s_start := global_position + Vector2(44.0 * facing_sign * sc, -74.0 * sc)
			_spawn_skill_projectile(&"antamina_stream_fx", &"antamina_impact_fx", "center", s_start, Vector2.ZERO, facing_sign, 280.0, 80.0, true)
	# 6. Bukadai high-speed sword dash -> connector spark -> electric yellow sphere + ground dust dome
	elif anim == "bukadai_rush" and sprite.is_playing():
		if sprite.frame >= 3 and not _bukadai_dashed_for_cast:
			_bukadai_dashed_for_cast = true
			var origin_pos := global_position + Vector2(0.0, -64.0 * sc)
			_spawn_oneshot_fx(&"bukadai_vanish_fx", origin_pos, facing_sign, "center")
			var arena := _find_arena_node()
			if arena != null and arena.has_method(&"_move_player_horizontal"):
				arena.call(&"_move_player_horizontal", 210.0 * facing_sign, is_airborne_flight())
			else:
				global_position.x += 210.0 * facing_sign
			var flash_pos := global_position + Vector2(46.0 * facing_sign * sc, -68.0 * sc)
			_spawn_oneshot_fx(&"bukadai_flash_fx", flash_pos, facing_sign, "center")
		if sprite.frame >= 4 and not _skill_fx_fired_for_cast:
			_skill_fx_fired_for_cast = true
			var target_pos := global_position + Vector2(54.0 * facing_sign * sc, -68.0 * sc)
			var ground_hit := _apply_demo_skill_hit_at(target_pos, 135.0, 85.0, facing_sign, true)
			_spawn_oneshot_fx(&"bukadai_sphere_fx", ground_hit + Vector2(0.0, -72.0 * sc), facing_sign, "center")
			_spawn_oneshot_fx(&"bukadai_impact_fx", ground_hit, facing_sign, "ground")
	else:
		if anim not in ["kentaima_cast", "mahasenko_ground", "mahasenko_air", "antamina_combo", "bukadai_rush"]:
			_skill_fx_fired_for_cast = false
			_bukadai_dashed_for_cast = false


func _spawn_atk10_ground_impact() -> void:
	_ensure_tapion_fx_nodes()
	if _ground_impact_fx == null or _ground_impact_fx.sprite_frames == null:
		return
	if not _ground_impact_fx.sprite_frames.has_animation(&"atk10_impact_fx"):
		return
	var facing_sign := -1.0 if scale.x < 0.0 else 1.0
	var sc := absf(scale.y) if not is_zero_approx(scale.y) else 1.0
	_ground_impact_fx.global_position = global_position + Vector2(34.0 * facing_sign * sc, 0.0)
	_ground_impact_fx.scale = Vector2(facing_sign * sc, sc)
	_ground_impact_fx.visible = true
	_ground_impact_fx.frame = 0
	_ground_impact_fx.play(&"atk10_impact_fx")
