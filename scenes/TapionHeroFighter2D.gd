class_name TapionHeroFighter2D
extends SaiyanHeroFighter2D
## Playable Hero Controller — Tapion (Complete 47/47 Source Setup: Core + 10-Step Sword Combo + Ocarina & 4 Signature Skills):
## - Single-form Konatsian Hero (`is_ssj = true` always).
## - Peace State: `idle` (playing Ocarina flute) + independent rainbow musical aura (`PeaceAuraFX` @ z=-1) + `walk` (200 px/s).
## - Combat State: `combat_enter` -> `idle_combat` + `combat_move` (400 back / 500 fwd px/s + brake #1/#2).
## - 10-Step Sword Combo (`attack_light`..`attack_10` LOOP X2 + `atk10_impact_fx` under target feet @ top layer + mini-stun).
## - Full Ocarina & 4 Signature Skills (`tapion_skills_fx.tres`, ALL skills & explosions rendered on TOP layer z>=69):
##     1. `barrier` -> `barrier_cast` (9f) + multi-layer blue energy sphere `barrier_dome_fx` (Frame-8 reference)
##     2. `energy_recover` -> `energy_recover` (8f Ocarina white-cyan lightning aura, grounded)
##     3. `kentaima` -> `kentaima_cast` (4f) + target-locked `kentaima_wave_fx` @ 2500px/s + 70% circular `kentaima_impact_fx` (6f)
##     4. `mahasenko` -> `mahasenko_ground`/`mahasenko_air` + `mahasenko_hand_fx` muzzle -> 2 simultaneous reversed growing beams
##                       (`mahasenko_beam_h_fx`/`mahasenko_beam_air_fx`) spawned 20px ahead of hand @ 2500px/s -> `mahasenko_impact_fx`
##     5. `antamina` (100 MP) -> `antamina_fire` 1.0s charge with spinning `antamina_flash_fx` orb at hand ->
##                       reverse muzzle `antamina_stream_rev_fx` (4->0) -> flying `antamina_stream_fx` (0->4) @ 3000px/s (1x size) -> `antamina_impact_fx`
##     6. `bukadai` -> `bukadai_rush` teleport blitz directly onto locked target -> `bukadai_vanish_fx` + `bukadai_sphere_fx` + 2.0s stun

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
const ANTAMINA_MANA_COST: float = 100.0
const ANTAMINA_CHARGE_S: float = 1.0
const BUKADAI_CD_S: float = 1.8
const BUKADAI_STUN_S: float = 2.0

const MAHASENKO_SPEED_PX_S: float = 2500.0
const KENTAIMA_SPEED_PX_S: float = 2500.0
const ANTAMINA_SPEED_PX_S: float = 3000.0
const MAHASENKO_HAND_CLEARANCE_PX: float = 20.0
const MAHA_BEAM_AIR_BASE_RAD: float = 0.581  # Measured PCA axis of maha_beam_air_00 (+33.3 deg)

# Always render skills & explosions on the topmost visual layer above Boss (30), Drops (45), Shenron (52), Overlay (65)!
const TOP_FX_PROJ_Z: int = 69
const TOP_FX_IMPACT_Z: int = 70

var kentaima_cooldown_s: float = 0.0
var mahasenko_cooldown_s: float = 0.0
var antamina_cooldown_s: float = 0.0
var bukadai_cooldown_s: float = 0.0

var _peace_aura_fx: AnimatedSprite2D = null
var _flight_aura_fx: AnimatedSprite2D = null
var _barrier_dome_fx: AnimatedSprite2D = null
var _hand_muzzle_fx: AnimatedSprite2D = null
var _ground_impact_fx: AnimatedSprite2D = null
var _skills_fx_frames: SpriteFrames = null

var _atk10_fx_stage: int = 0
var _atk10_stunned_slot: Dictionary = {}
var _skill_fx_fired_for_cast: bool = false
var _bukadai_dashed_for_cast: bool = false
var _locked_skill_target: Dictionary = {}

# Antamina 1.0s spinning hand orb charge state
var _antamina_charging: bool = false
var _antamina_charge_elapsed_s: float = 0.0
var _antamina_orb_node: AnimatedSprite2D = null

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


func _clear_antamina_orb() -> void:
	_antamina_charging = false
	_antamina_charge_elapsed_s = 0.0
	if _antamina_orb_node != null and is_instance_valid(_antamina_orb_node):
		_antamina_orb_node.queue_free()
	_antamina_orb_node = null


func _clear_spawned_fx() -> void:
	_clear_antamina_orb()
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


func is_antamina_charging() -> bool:
	return _antamina_charging


func set_locked_skill_target(tgt: Dictionary) -> void:
	_locked_skill_target = tgt


func reset_hero_state() -> void:
	super.reset_hero_state()
	is_ssj = true
	kentaima_cooldown_s = 0.0
	mahasenko_cooldown_s = 0.0
	antamina_cooldown_s = 0.0
	bukadai_cooldown_s = 0.0
	_atk10_fx_stage = 0
	_atk10_stunned_slot = {}
	_skill_fx_fired_for_cast = false
	_bukadai_dashed_for_cast = false
	_locked_skill_target = {}
	_clear_spawned_fx()
	_update_peace_aura_visibility()
	_update_flight_aura_visibility()
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


func trigger_antamina(current_mana: float = 100.0) -> bool:
	if antamina_cooldown_s > 0.0 or current_mana + 0.001 < ANTAMINA_MANA_COST:
		return false
	antamina_cooldown_s = ANTAMINA_CD_S
	_skill_fx_fired_for_cast = false
	_clear_antamina_orb()
	_antamina_charging = true
	_antamina_charge_elapsed_s = 0.0
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
	_atk10_fx_stage = 0
	_atk10_stunned_slot = {}
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
	if _flight_aura_fx == null:
		_flight_aura_fx = get_node_or_null("FlightAuraFX") as AnimatedSprite2D
		if _flight_aura_fx != null and _skills_fx_frames == null and _flight_aura_fx.sprite_frames != null:
			_skills_fx_frames = _flight_aura_fx.sprite_frames
	if _barrier_dome_fx == null:
		_barrier_dome_fx = get_node_or_null("BarrierDomeFX") as AnimatedSprite2D
	if _hand_muzzle_fx == null:
		_hand_muzzle_fx = get_node_or_null("HandMuzzleFX") as AnimatedSprite2D
		if _hand_muzzle_fx != null:
			_hand_muzzle_fx.z_index = TOP_FX_IMPACT_Z
			if not _hand_muzzle_fx.animation_finished.is_connected(_on_hand_muzzle_finished):
				_hand_muzzle_fx.animation_finished.connect(_on_hand_muzzle_finished)
	if _ground_impact_fx == null:
		_ground_impact_fx = get_node_or_null("GroundImpactFX") as AnimatedSprite2D
		if _ground_impact_fx != null:
			_ground_impact_fx.top_level = true
			_ground_impact_fx.z_index = TOP_FX_IMPACT_Z
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


func _update_flight_aura_visibility() -> void:
	_ensure_tapion_fx_nodes()
	if _flight_aura_fx == null or sprite == null:
		return
	var show_fly_aura := sprite.visible and String(sprite.animation) == "fly_aura"
	if show_fly_aura:
		_flight_aura_fx.position = sprite.position
		if not _flight_aura_fx.visible:
			_flight_aura_fx.visible = true
		if not _flight_aura_fx.is_playing() or _flight_aura_fx.animation != &"fly_aura_fx":
			_flight_aura_fx.play(&"fly_aura_fx")
	else:
		if _flight_aura_fx.visible:
			_flight_aura_fx.visible = false
			_flight_aura_fx.stop()


func _update_barrier_dome_visibility(_delta: float) -> void:
	_ensure_tapion_fx_nodes()
	if _barrier_dome_fx == null or sprite == null:
		return
	# When active inside ArenaSandbox + FieldCombatManager, FieldCombatManager._draw_hero_phase2_fx_overlays()
	# renders Tapion's Frame-8 blue energy sphere centered on p_core (1:1 visible across ground/jump/fly/attack!).
	var arena := _find_arena_node()
	if arena != null and arena.get("field_manager") != null and bool(arena.get("field_manager").get("active")):
		_barrier_dome_fx.visible = false
		return
	var casting_barrier := String(sprite.animation) == "barrier_cast" and sprite.is_playing() and sprite.frame < 8
	if barrier_timer_s > 0.0 and not casting_barrier:
		_barrier_dome_fx.position = sprite.position
		_barrier_dome_fx.visible = true
		if _barrier_dome_fx.animation != &"barrier_dome_fx":
			_barrier_dome_fx.animation = &"barrier_dome_fx"
		_barrier_dome_fx.pause()
		if barrier_timer_s <= 0.25:
			_barrier_dome_fx.frame = 4
		else:
			var cyc := int(floor((BARRIER_DURATION_S - barrier_timer_s) * 10.0)) % 4
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


func _is_slot_alive(slot: Dictionary) -> bool:
	return (not slot.is_empty()) and bool(slot.get("alive", false)) and is_instance_valid(slot.get("node"))


func _resolve_active_target(prefer_locked: bool = true) -> Dictionary:
	if prefer_locked and _is_slot_alive(_locked_skill_target):
		return _locked_skill_target
	var arena := _find_arena_node()
	if arena == null:
		return {}
	var fm = arena.get("field_manager")
	if fm == null or not bool(fm.get("active")):
		return {}
	if fm.has_method(&"resolve_skill_target"):
		var t: Dictionary = fm.call(&"resolve_skill_target")
		if _is_slot_alive(t):
			return t
	var t2: Dictionary = fm.call(&"_resolve_player_attack_target", true)
	return t2 if _is_slot_alive(t2) else {}


func _get_slot_core_world(slot: Dictionary) -> Vector2:
	var arena := _find_arena_node()
	if arena != null and arena.get("field_manager") != null and _is_slot_alive(slot):
		return arena.get("field_manager").call(&"_get_slot_core_pos", slot) as Vector2
	if _is_slot_alive(slot):
		var sn := slot.get("node") as Node2D
		return sn.global_position + Vector2(0.0, -56.0)
	return global_position + Vector2(180.0 * (-1.0 if scale.x < 0.0 else 1.0), -64.0)


func _get_slot_feet_world(slot: Dictionary) -> Vector2:
	# Exact bottom-center feet position for BOTH flying monsters and ground monsters!
	var arena := _find_arena_node()
	if arena != null and arena.get("field_manager") != null and _is_slot_alive(slot):
		var fm = arena.get("field_manager")
		if fm.has_method(&"_get_slot_body_rect"):
			var r: Rect2 = fm.call(&"_get_slot_body_rect", slot)
			if r.size.x > 1.0 and r.size.y > 1.0:
				return Vector2(r.position.x + r.size.x * 0.5, r.end.y)
	if _is_slot_alive(slot):
		var sn := slot.get("node") as Node2D
		return sn.global_position
	return global_position


func _face_toward_x(tx: float) -> void:
	var dx := tx - global_position.x
	if absf(dx) <= 4.0:
		return
	var sc := absf(scale.y) if not is_zero_approx(scale.y) else 1.0
	var left := dx < 0.0
	scale = Vector2(-sc if left else sc, sc)
	var arena := _find_arena_node()
	if arena != null:
		arena.set("player_facing_left", left)


func _apply_oriented_transform(node: AnimatedSprite2D, dir_vec: Vector2, sc: float, base_angle_rad: float = 0.0) -> void:
	var d := dir_vec.normalized() if dir_vec.length() > 0.001 else Vector2(1.0, 0.0)
	if is_zero_approx(base_angle_rad):
		if d.x >= 0.0:
			node.scale = Vector2(sc, sc)
			node.rotation = d.angle()
		else:
			node.scale = Vector2(sc, -sc)
			node.rotation = d.angle()
	else:
		if d.x >= 0.0:
			node.scale = Vector2(sc, sc)
			node.rotation = d.angle() - base_angle_rad
		else:
			node.scale = Vector2(-sc, sc)
			node.rotation = d.angle() - (PI - base_angle_rad)


func _spawn_oneshot_fx(clip_name: StringName, world_pos: Vector2, facing_sign: float = 1.0, anchor_mode: String = "center", scale_mul: float = 1.0, aim_dir: Vector2 = Vector2.ZERO) -> AnimatedSprite2D:
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
	if aim_dir.length() > 0.01:
		_apply_oriented_transform(fx, aim_dir, sc, 0.0)
	else:
		fx.scale = Vector2(facing_sign * sc, sc)
	fx.z_index = TOP_FX_IMPACT_Z
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


func spawn_teleport_streak_fx(origin_pos: Vector2, dest_pos: Vector2, is_vertical: bool = false) -> void:
	var facing_sign := -1.0 if scale.x < 0.0 else 1.0
	var sc := absf(scale.y) if not is_zero_approx(scale.y) else 1.0
	var clip_sn: StringName = &"tele_streak_v_fx" if is_vertical else &"tele_streak_h_fx"
	_spawn_oneshot_fx(clip_sn, origin_pos + Vector2(0.0, -64.0 * sc), facing_sign, "center")
	if origin_pos.distance_to(dest_pos) > 140.0:
		_spawn_oneshot_fx(clip_sn, dest_pos + Vector2(0.0, -64.0 * sc), facing_sign, "center")


func _spawn_homing_projectile(
	clip_name: StringName,
	impact_clip: StringName,
	impact_anchor: String,
	start_pos: Vector2,
	target_slot: Dictionary,
	fallback_dir: Vector2,
	speed_px_s: float,
	damage_val: float,
	net_action: String,
	arc_sign: float = 0.0,
	arc_amp: float = 0.0,
	base_angle_rad: float = 0.0,
	anchor_mode: String = "center",
	scale_mul: float = 1.0
) -> void:
	_ensure_tapion_fx_nodes()
	if _skills_fx_frames == null or not _skills_fx_frames.has_animation(clip_name):
		return
	var node := AnimatedSprite2D.new()
	node.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	node.sprite_frames = _skills_fx_frames
	node.centered = false
	if anchor_mode == "muzzle_left":
		node.offset = Vector2(-20.0, -176.0)
	else:
		node.offset = Vector2(-144.0, -176.0)
	var sc := (absf(scale.y) if not is_zero_approx(scale.y) else 1.0) * scale_mul
	var has_tgt := _is_slot_alive(target_slot)
	var end_pos: Vector2 = _get_slot_core_world(target_slot) if has_tgt else (start_pos + fallback_dir.normalized() * 920.0)
	var init_dir := (end_pos - start_pos).normalized() if end_pos.distance_to(start_pos) > 2.0 else fallback_dir.normalized()
	node.top_level = true
	node.global_position = start_pos
	_apply_oriented_transform(node, init_dir, sc, base_angle_rad)
	node.z_index = TOP_FX_PROJ_Z
	var host: Node = get_parent() if get_parent() != null else self
	host.add_child(node)
	node.play(clip_name)
	_active_projectiles.append({
		"node": node,
		"clip": String(clip_name),
		"impact_clip": impact_clip,
		"impact_anchor": impact_anchor,
		"net_action": net_action,
		"pos": start_pos,
		"start_pos": start_pos,
		"end_pos": end_pos,
		"dir": init_dir,
		"speed": speed_px_s,
		"t_prog": 0.0,
		"arc_sign": arc_sign,
		"arc_amp": arc_amp,
		"base_angle_rad": base_angle_rad,
		"scale_val": sc,
		"damage": damage_val,
		"target": target_slot,
		"age_s": 0.0,
		"max_age_s": 1.6,
	})


func _step_active_projectiles(delta: float) -> void:
	var arena := _find_arena_node()
	var fm = arena.get("field_manager") if arena != null else null
	var fm_active := fm != null and bool(fm.get("active"))
	for i in range(_active_projectiles.size() - 1, -1, -1):
		var pr: Dictionary = _active_projectiles[i]
		pr["age_s"] = float(pr["age_s"]) + delta
		var node := pr.get("node") as AnimatedSprite2D
		if node == null or not is_instance_valid(node):
			_active_projectiles.remove_at(i)
			continue

		var old_p: Vector2 = pr["pos"] as Vector2
		var dir_v: Vector2 = pr["dir"] as Vector2
		var tgt: Dictionary = pr.get("target", {})
		var has_tgt := _is_slot_alive(tgt)
		var spd: float = float(pr["speed"])
		var step_dist: float = spd * delta
		var start_p: Vector2 = pr["start_pos"] as Vector2
		var end_p: Vector2 = _get_slot_core_world(tgt) if has_tgt else (pr["end_pos"] as Vector2)
		pr["end_pos"] = end_p

		var chord: Vector2 = end_p - start_p
		var chord_len: float = maxf(48.0, chord.length())
		var chord_dir: Vector2 = chord / chord_len
		var perp: Vector2 = Vector2(-chord_dir.y, chord_dir.x)
		var arc_sign: float = float(pr.get("arc_sign", 0.0))
		var arc_amp: float = minf(float(pr.get("arc_amp", 0.0)), chord_len * 0.26)
		var ctrl_p: Vector2 = (start_p + end_p) * 0.5 + perp * (arc_sign * arc_amp)

		var t_next: float = minf(1.0, float(pr.get("t_prog", 0.0)) + step_dist / maxf(64.0, chord_len * (1.05 if absf(arc_amp) > 1.0 else 1.0)))
		pr["t_prog"] = t_next
		var u: float = 1.0 - t_next
		var new_p: Vector2 = (u * u) * start_p + (2.0 * u * t_next) * ctrl_p + (t_next * t_next) * end_p
		var seg: Vector2 = new_p - old_p
		if seg.length() > 0.5:
			dir_v = seg.normalized()
			pr["dir"] = dir_v
		pr["pos"] = new_p
		node.global_position = new_p
		_apply_oriented_transform(node, dir_v, float(pr.get("scale_val", 1.0)), float(pr.get("base_angle_rad", 0.0)))

		# Keep crescent wave crisp while flying
		if str(pr["clip"]) == "kentaima_wave_fx" and node.frame >= 3:
			node.frame = 1

		var hit_now := false
		var impact_p := new_p
		var net_act := str(pr.get("net_action", "kentaima"))
		var impact_anchor := str(pr.get("impact_anchor", "center"))
		var facing_sign := -1.0 if dir_v.x < 0.0 else 1.0

		# Điều 7.8: Solid terrain step/floor collision
		if arena != null and bool(arena.call(&"terrain_blocks_segment", old_p, new_p)):
			hit_now = true
			impact_p = new_p
		elif has_tgt and (t_next >= 0.98 or new_p.distance_to(end_p) <= maxf(60.0, step_dist + 22.0)):
			hit_now = true
			if fm_active:
				var dmg_p := float(pr["damage"])
				var is_remote_p: bool = bool(fm.call(&"_emit_slot_combat_action", net_act, tgt, global_position, dmg_p, 0.45))
				if not (bool(fm.get("network_authoritative")) and is_remote_p):
					fm.call(&"apply_damage_to_slot", tgt, dmg_p, 28.0, end_p, "skill", false, dir_v)
			impact_p = _get_slot_feet_world(tgt) if impact_anchor == "ground" else end_p
		elif not has_tgt and fm_active:
			for s in fm.call(&"_get_combat_slots"):
				if not _is_slot_alive(s):
					continue
				var sc_pos: Vector2 = fm.call(&"_get_slot_core_pos", s)
				if new_p.distance_to(sc_pos) <= maxf(76.0, step_dist * 0.6):
					var dmg_p2 := float(pr["damage"])
					var is_remote_p2: bool = bool(fm.call(&"_emit_slot_combat_action", net_act, s, global_position, dmg_p2, 0.45))
					if not (bool(fm.get("network_authoritative")) and is_remote_p2):
						fm.call(&"apply_damage_to_slot", s, dmg_p2, 28.0, sc_pos, "skill", false, dir_v)
					hit_now = true
					impact_p = _get_slot_feet_world(s) if impact_anchor == "ground" else sc_pos
					break

		if hit_now or t_next >= 1.0 or float(pr["age_s"]) >= float(pr["max_age_s"]):
			_spawn_oneshot_fx(pr["impact_clip"] as StringName, impact_p, facing_sign, impact_anchor)
			node.queue_free()
			_active_projectiles.remove_at(i)


func _update_antamina_charge_and_fire(delta: float, anim: String, sc: float) -> void:
	if not _antamina_charging:
		return
	if anim != "antamina_fire":
		_clear_antamina_orb()
		return
	var tgt := _resolve_active_target(true)
	if _is_slot_alive(tgt):
		_face_toward_x(_get_slot_core_world(tgt).x)
	var facing_sign := -1.0 if scale.x < 0.0 else 1.0
	var hand_pos := global_position + Vector2(54.0 * facing_sign * sc, -74.0 * sc)
	_antamina_charge_elapsed_s += delta

	# Keep Tapion in antamina_fire charging stance for the full 1.0s with spinning antamina_flash_fx orb at hand!
	if _antamina_charge_elapsed_s < ANTAMINA_CHARGE_S:
		if sprite != null:
			var f_idx := int(floor(_antamina_charge_elapsed_s * 10.0)) % 3
			sprite.set_frame_and_progress(f_idx, 0.0)
			if not sprite.is_playing():
				sprite.play(&"antamina_fire")
		if _antamina_orb_node == null or not is_instance_valid(_antamina_orb_node):
			_ensure_tapion_fx_nodes()
			if _skills_fx_frames != null and _skills_fx_frames.has_animation(&"antamina_flash_fx"):
				var orb := AnimatedSprite2D.new()
				orb.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
				orb.sprite_frames = _skills_fx_frames
				orb.centered = false
				orb.offset = Vector2(-144.0, -176.0)
				orb.top_level = true
				orb.scale = Vector2(sc, sc)
				orb.z_index = TOP_FX_IMPACT_Z
				var host: Node = get_parent() if get_parent() != null else self
				host.add_child(orb)
				orb.play(&"antamina_flash_fx")
				_antamina_orb_node = orb
		if _antamina_orb_node != null and is_instance_valid(_antamina_orb_node):
			_antamina_orb_node.global_position = hand_pos
			_antamina_orb_node.rotation += delta * 14.0
		return

	# Charge complete (1.0s): hide spinning orb -> fire reverse 4->0 hand muzzle -> launch 0->4 beam @ 3000px/s (1x size)!
	_clear_antamina_orb()
	_skill_fx_fired_for_cast = true
	if sprite != null:
		sprite.set_frame_and_progress(2, 0.0)
	var aim_dir := Vector2(facing_sign, 0.0)
	if _is_slot_alive(tgt):
		var dv := _get_slot_core_world(tgt) - hand_pos
		if dv.length() > 4.0:
			aim_dir = dv.normalized()
	# 1) Hand muzzle burst = reverse antamina_stream_fx (4 -> 0) right at Tapion's hand!
	_spawn_oneshot_fx(&"antamina_stream_rev_fx", hand_pos, facing_sign, "muzzle_left", 1.0, aim_dir)
	# 2) Flying Antamina beam = antamina_stream_fx (0 -> 4) @ 3000 px/s, original 1x size -> antamina_impact_fx!
	var beam_start := hand_pos + aim_dir * (20.0 * sc)
	_spawn_homing_projectile(
		&"antamina_stream_fx",
		&"antamina_impact_fx",
		"ground",
		beam_start,
		tgt,
		aim_dir,
		ANTAMINA_SPEED_PX_S,
		80.0,
		"antamina",
		0.0,
		0.0,
		0.0,
		"muzzle_left",
		1.0
	)


func _execute_bukadai_teleport_to_target(tgt: Dictionary, sc: float) -> void:
	if not _is_slot_alive(tgt):
		return
	var arena := _find_arena_node()
	var t_core := _get_slot_core_world(tgt)
	var t_feet := _get_slot_feet_world(tgt)
	var approach_sign := 1.0 if (t_core.x >= global_position.x) else -1.0
	var dest_x := t_core.x - approach_sign * 56.0 * sc
	if arena != null:
		var min_x := float(arena.get("walkable_min_x"))
		var max_x := float(arena.get("walkable_max_x"))
		dest_x = clampf(dest_x, min_x, max_x)
		var g_y := float(arena.call(&"_ground_y_at", dest_x))
		# Match flying target altitude seamlessly if enemy is airborne!
		if t_feet.y < g_y - 24.0:
			global_position = Vector2(dest_x, t_feet.y)
			flight_state = "hovering"
			hover_timer_s = HOVER_TIMEOUT_S
			arena.set("player_vy", 0.0)
		else:
			global_position = Vector2(dest_x, g_y)
			if flight_state == "flying" or flight_state == "hovering":
				flight_state = "ground"
			arena.set("player_vy", 0.0)
	else:
		global_position = Vector2(dest_x, t_feet.y)
	_face_toward_x(t_core.x)


func _step_attack_10_fx_and_ministun(anim: String, facing_sign: float, sc: float) -> void:
	var arena := _find_arena_node()
	var fm = arena.get("field_manager") if arena != null else null
	var fm_active := fm != null and bool(fm.get("active"))
	if anim == "attack_10" and sprite != null and sprite.is_playing():
		var f := sprite.frame
		if f >= 2 and f <= 7:
			# Resolve current target being attacked (pointed/nearest alive enemy within attack vicinity)
			var tgt: Dictionary = {}
			if fm_active:
				tgt = fm.call(&"_resolve_player_attack_target", false)
				if not _is_slot_alive(tgt):
					var cand: Dictionary = _resolve_active_target(false)
					if _is_slot_alive(cand) and _get_slot_core_world(cand).distance_to(global_position + Vector2(0.0, -64.0 * sc)) <= 240.0 * sc:
						tgt = cand
			# Continuous mini-stun WITHOUT requiring armor break for the entire duration until attack_10 ends!
			if fm_active and _is_slot_alive(tgt):
				_atk10_stunned_slot = tgt
				fm.call(&"apply_hard_stun_to_slot", tgt, 0.22)
			# Spawn atk10_impact_fx on TOP layer directly under the attacked target's feet (ground OR flying!)
			var want_stage := 2 if f >= 5 else 1
			if _atk10_fx_stage < want_stage:
				_atk10_fx_stage = want_stage
				var fx_pos := _get_slot_feet_world(tgt) if _is_slot_alive(tgt) else (global_position + Vector2(34.0 * facing_sign * sc, 0.0))
				_spawn_oneshot_fx(&"atk10_impact_fx", fx_pos, facing_sign, "ground", 1.0)
	else:
		if _atk10_fx_stage > 0:
			_atk10_fx_stage = 0
		if _is_slot_alive(_atk10_stunned_slot):
			# Release attack_10 mini-stun cleanly as soon as attack_10 ends (unless a longer stun like Bukadai 2s is active)
			var cur_hs := float(_atk10_stunned_slot.get("hard_stun_timer_s", 0.0))
			if cur_hs > 0.0 and cur_hs <= 0.25:
				_atk10_stunned_slot["hard_stun_timer_s"] = 0.0
			_atk10_stunned_slot = {}


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
	_update_flight_aura_visibility()
	_update_barrier_dome_visibility(delta)
	_step_active_projectiles(delta)

	if sprite == null:
		return
	var anim := String(sprite.animation)
	var facing_sign := -1.0 if scale.x < 0.0 else 1.0
	var sc := absf(scale.y) if not is_zero_approx(scale.y) else 1.0

	# 1. Attack 10 top-layer feet impact (ground + flying) & continuous mini-stun until skill ends
	_step_attack_10_fx_and_ministun(anim, facing_sign, sc)

	# 2. Antamina 1.0s spinning hand orb charge -> 4->0 reverse hand burst -> 0->4 3000px/s beam -> antamina_impact_fx
	_update_antamina_charge_and_fire(delta, anim, sc)

	# 3. Kentaima target-locked crescent wave @ 2500px/s -> 70% circular kentaima_impact_fx on top layer!
	if anim == "kentaima_cast" and sprite.is_playing():
		if sprite.frame >= 2 and not _skill_fx_fired_for_cast:
			_skill_fx_fired_for_cast = true
			var tgt_k := _resolve_active_target(true)
			if _is_slot_alive(tgt_k):
				_face_toward_x(_get_slot_core_world(tgt_k).x)
				facing_sign = -1.0 if scale.x < 0.0 else 1.0
			var w_start := global_position + Vector2(66.0 * facing_sign * sc, -74.0 * sc)
			_spawn_homing_projectile(
				&"kentaima_wave_fx",
				&"kentaima_impact_fx",
				"center",
				w_start,
				tgt_k,
				Vector2(facing_sign, 0.0),
				KENTAIMA_SPEED_PX_S,
				60.0,
				"kentaima"
			)

	# 4. Mahasenko Ground/Air: mahasenko_hand_fx at hand -> 2 simultaneous reversed growing beams 20px ahead @ 2500px/s -> mahasenko_impact_fx!
	elif (anim == "mahasenko_ground" or anim == "mahasenko_air") and sprite.is_playing():
		var is_air_m := (anim == "mahasenko_air")
		var trig_f := 1 if is_air_m else 2
		if sprite.frame >= trig_f and not _skill_fx_fired_for_cast:
			_skill_fx_fired_for_cast = true
			var tgt_m := _resolve_active_target(true)
			if _is_slot_alive(tgt_m):
				_face_toward_x(_get_slot_core_world(tgt_m).x)
				facing_sign = -1.0 if scale.x < 0.0 else 1.0
			var hand_pos := global_position + (Vector2(42.0 * facing_sign * sc, -64.0 * sc) if is_air_m else Vector2(54.0 * facing_sign * sc, -74.0 * sc))
			var aim_dir := Vector2(0.76 * facing_sign, 0.65).normalized() if is_air_m else Vector2(facing_sign, 0.0)
			if _is_slot_alive(tgt_m):
				var dv_m := _get_slot_core_world(tgt_m) - hand_pos
				if dv_m.length() > 4.0:
					aim_dir = dv_m.normalized()
			# Muzzle flash right at Tapion's hand (top layer!)
			_spawn_oneshot_fx(&"mahasenko_hand_fx", hand_pos, facing_sign, "center", 1.0, aim_dir)
			# Spawn 2 simultaneous beams 20px ahead of hand (Goku Antomic technique!) converging on locked target!
			var proj_start := hand_pos + aim_dir * (MAHASENKO_HAND_CLEARANCE_PX * sc)
			var beam_clip: StringName = &"mahasenko_beam_air_fx" if is_air_m else &"mahasenko_beam_h_fx"
			var base_ang := MAHA_BEAM_AIR_BASE_RAD if is_air_m else 0.0
			for twin_i in range(2):
				var a_sign := -1.0 if twin_i == 0 else 1.0
				var perp := Vector2(-aim_dir.y, aim_dir.x)
				var b_start := proj_start + perp * (a_sign * 10.0 * sc)
				_spawn_homing_projectile(
					beam_clip,
					&"mahasenko_impact_fx",
					"center",
					b_start,
					tgt_m,
					aim_dir,
					MAHASENKO_SPEED_PX_S,
					65.0,
					"mahasenko",
					a_sign,
					56.0,
					base_ang
				)

	# 5. Bukadai teleport blitz onto locked target -> bukadai_sphere_fx + 2.0s hard stun!
	elif anim == "bukadai_rush" and sprite.is_playing():
		if sprite.frame >= 1 and not _bukadai_dashed_for_cast:
			_bukadai_dashed_for_cast = true
			var origin_pos := global_position + Vector2(0.0, -64.0 * sc)
			_spawn_oneshot_fx(&"bukadai_vanish_fx", origin_pos, facing_sign, "center")
			var tgt_b := _resolve_active_target(true)
			if _is_slot_alive(tgt_b):
				_execute_bukadai_teleport_to_target(tgt_b, sc)
		if sprite.frame >= 3 and not _skill_fx_fired_for_cast:
			_skill_fx_fired_for_cast = true
			var tgt_b2 := _resolve_active_target(true)
			var arena := _find_arena_node()
			var fm = arena.get("field_manager") if arena != null else null
			var fm_active := fm != null and bool(fm.get("active"))
			var hit_core := _get_slot_core_world(tgt_b2) if _is_slot_alive(tgt_b2) else (global_position + Vector2(54.0 * facing_sign * sc, -68.0 * sc))
			if fm_active and _is_slot_alive(tgt_b2):
				var is_remote_b: bool = bool(fm.call(&"_emit_slot_combat_action", "bukadai", tgt_b2, global_position, 85.0, 0.45))
				if not (bool(fm.get("network_authoritative")) and is_remote_b):
					fm.call(&"apply_damage_to_slot", tgt_b2, 85.0, 35.0, hit_core, "skill", false, Vector2(-1.0 if scale.x < 0.0 else 1.0, 0.0))
				fm.call(&"apply_hard_stun_to_slot", tgt_b2, BUKADAI_STUN_S)
			_spawn_oneshot_fx(&"bukadai_sphere_fx", hit_core, -1.0 if scale.x < 0.0 else 1.0, "center")
	else:
		if anim not in ["kentaima_cast", "mahasenko_ground", "mahasenko_air", "antamina_fire", "antamina_combo", "bukadai_rush"]:
			_skill_fx_fired_for_cast = false
			_bukadai_dashed_for_cast = false
			if _antamina_charging:
				_clear_antamina_orb()
