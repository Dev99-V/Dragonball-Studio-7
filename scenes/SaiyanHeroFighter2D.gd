class_name SaiyanHeroFighter2D
extends CharacterFighter2D
## First Playable Hero Controller — Son Goku (Phase 1 v4):
## - Two Game States: "peace" (Hòa bình) vs "combat" (Chiến đấu) with explicit clip state filtering.
## - NO `idle_ssj`: SSJ1 Peace standing = `idle_ssj_aura` (always returns after moving in Peace);
##   Peace -> Combat bridges via `combat_enter` (34 F0..F3) -> `idle_combat` (34 F4..F7).
## - Invulnerable during `transform_ssj`.
## - 7-Step Normal Combo (10->11->12->13->14->17->15), per-frame hit impacts & damage:
##   Light = 10..20 (crit 20), Heavy = 50, attack_6 gold slash (#13) = 60, 100ms combo link gap!
## - Combat Move (`16`, 200 px/s): Backward loops #0 (300ms) <-> #1 (80ms); Forward loops #3 (300ms) <-> #2 (80ms).
## - 360° Analog Jump (~100px height): F0..F2 up, F3..F5 fall/land, F4 universal high-fall.
## - Flight (SSJ1 only, 200 px/s, NO fly_launch): Jump + Hold Analog UP -> `fly_aura` -> Stop -> 3s `fly_prep`
##   -> Analog DOWN cancels hover/flight for immediate fast descent (`jump` F4) without waiting 3s!
## - 3-Mode Stamina Teleport (100 max, +5/s, -75 static / -25 directional 100px).

signal hero_state_changed()
signal combat_state_entered()

const COMBO_CLIPS: Array[String] = [
	"attack_light",  # 10. tấn công thường 1 (Light 10-20 per hit frame)
	"attack_2",      # 11. đánh thường 2 (Light 10-20 per hit frame)
	"attack_3",      # 12. đánh thường 3 (Light 10-20 per hit frame)
	"attack_4",      # 13. đánh thường 4 (Light 10-20 per hit frame)
	"attack_5",      # 14. đánh thường 5 (Light 10-20 per hit frame)
	"attack_6",      # 17. tấn công thường 6 (Heavy 50 per hit frame, penultimate gold slash #13 = 60!)
	"attack_7",      # 15. đánh thường 7 (Heavy finisher 50 per hit frame)
]

# Exact strike frames per clip so EVERY impact frame spawns hit_impact & subtracts damage immediately!
const COMBO_HIT_FRAMES := {
	"attack_light": [2, 5, 8, 10],
	"attack_2": [2],
	"attack_3": [2],
	"attack_4": [2, 5],
	"attack_5": [2, 5, 7],
	"attack_6": [2, 5, 8, 11],
	"attack_7": [2, 4],
}

const STAMINA_MAX: float = 100.0
const STAMINA_REGEN_PER_S: float = 5.0
const TELEPORT_STATIC_COST: float = 75.0
const TELEPORT_DASH_COST: float = 25.0
const TELEPORT_DASH_DIST_PX: float = 100.0
const HOVER_TIMEOUT_S: float = 3.0
const COMBAT_TIMEOUT_S: float = 6.0
const WALK_SPEED_PX_S: float = 200.0
const COMBAT_MOVE_SPEED_PX_S: float = 400.0
const COMBAT_MOVE_HOVER_Y_PX: float = 20.0
const FLIGHT_SPEED_PX_S: float = 400.0
const FAST_DROP_VY_PX_S: float = 520.0
const COMBO_LINK_COOLDOWN_S: float = 0.02 # 20ms fluid combo link between attack_light..attack_7 (Owner tuning)!
const JUMP_HEIGHT_PX: float = 100.0
const JUMP_GRAVITY_PX_S2: float = 2000.0
const JUMP_VELOCITY_PX_S: float = -632.4555 # sqrt(2 * 2000 * 100) = 100.0 px apex
const JUMP_TO_FLY_HOLD_S: float = 0.14
const JUMP_TO_FLY_MIN_ALT_PX: float = 32.0
const TRANSFORM_INVULN_DURATION_S: float = 0.85

# Exact Owner Combat Move loop timings: Primary pose (#0 back / #3 fwd) = 90ms, Secondary bounce (#1 / #2) = 60ms
const COMBAT_MOVE_PRIMARY_HOLD_S: float = 0.09
const COMBAT_MOVE_LOOP_RETURN_S: float = 0.06

var is_ssj: bool = false
var game_state: String = "peace" # "peace" | "combat"
var in_combat: bool = false
var combat_timer_s: float = 0.0
var transform_invuln_s: float = 0.0
var combo_step: int = 0

var stamina: float = STAMINA_MAX
var max_stamina: float = STAMINA_MAX

# Flight state machine (NO fly_launch!): "ground" | "flying" | "hovering" | "falling"
var flight_state: String = "ground"
var hover_timer_s: float = 0.0
var jump_hold_up_s: float = 0.0
var jump_ascend_s: float = 0.0
var jump_land_hold_s: float = 0.0

# Combat Move (`16`) exact 300ms / 80ms loop state:
# Backward (-1): #0 (300ms) -> #1 (80ms) -> #0
# Forward  (+1): #3 (300ms) -> #2 (80ms) -> #3
var combat_move_frame: int = 3
var _combat_move_dir_last: int = 0
var _combat_move_phase: int = 0       # 0 = primary (#0 or #3 for 300ms), 1 = secondary (#1 or #2 for 80ms)
var _combat_move_phase_t: float = 0.0

# Armor-break HIT reaction tracking
var armor_hit_timer_s: float = 0.0

# Teleport mid-clip pending state
var pending_teleport_mode: String = ""   # "static" | "dash_ground" | "dash_air"
var pending_teleport_dir: Vector2 = Vector2.RIGHT
var pending_teleport_relocated: bool = false


func is_hero_songoku() -> bool:
	return true


func is_in_combat() -> bool:
	return game_state == "combat"


func is_transform_invulnerable() -> bool:
	if transform_invuln_s > 0.0:
		return true
	var spr := get_node_or_null("Sprite") as AnimatedSprite2D
	return spr != null and spr.is_playing() and String(spr.animation) == "transform_ssj"


func get_clip_state_flags() -> Dictionary:
	var c := (game_state == "combat")
	return {
		"game_state": game_state,
		"peace": not c,
		"combat": c,
		"walk": not c,
		"walk_ssj": (not c) and is_ssj,
		"idle_ssj_aura": (not c) and is_ssj,
		"combat_move": c and is_ssj,
		"idle_combat": c and is_ssj,
		"attack": c and is_ssj,
	}


func can_attack() -> bool:
	return is_ssj


func can_jump() -> bool:
	return is_ssj


func can_fly() -> bool:
	return is_ssj


func is_airborne_flight() -> bool:
	return flight_state == "flying" or flight_state == "hovering"


func enter_combat() -> bool:
	var transitioned := (game_state != "combat")
	game_state = "combat"
	in_combat = true
	combat_timer_s = COMBAT_TIMEOUT_S
	if transitioned:
		combat_state_entered.emit()
	hero_state_changed.emit()
	return transitioned


func mark_combat_engaged() -> void:
	enter_combat()


func on_player_moved() -> void:
	pass


func reset_combo() -> void:
	combo_step = 0
	hero_state_changed.emit()


func reset_hero_state() -> void:
	is_ssj = false
	game_state = "peace"
	in_combat = false
	combat_timer_s = 0.0
	transform_invuln_s = 0.0
	combo_step = 0
	stamina = STAMINA_MAX
	flight_state = "ground"
	hover_timer_s = 0.0
	jump_hold_up_s = 0.0
	jump_ascend_s = 0.0
	jump_land_hold_s = 0.0
	combat_move_frame = 3
	_combat_move_dir_last = 0
	_combat_move_phase = 0
	_combat_move_phase_t = 0.0
	armor_hit_timer_s = 0.0
	pending_teleport_mode = ""
	pending_teleport_relocated = false
	hero_state_changed.emit()


func get_current_combo_clip() -> String:
	return COMBO_CLIPS[posmod(combo_step, COMBO_CLIPS.size())]


func roll_strike_damage(is_heavy: bool, is_gold_slash: bool = false) -> Dictionary:
	## Owner v4 damage table:
	## - Light strike: random continuous 10..20 (10 normal, 20 crit!)
	## - Heavy strike: 50; penultimate gold slash frame (#13 of attack_6) = 60!
	if is_gold_slash:
		return {"damage": 60.0, "is_crit": true}
	if is_heavy:
		return {"damage": 50.0, "is_crit": false}
	var rolled := randi_range(10, 20)
	return {"damage": float(rolled), "is_crit": (rolled == 20)}


func pop_next_combo_attack() -> Dictionary:
	enter_combat()
	if is_airborne_flight():
		hover_timer_s = HOVER_TIMEOUT_S
	var idx := posmod(combo_step, COMBO_CLIPS.size())
	var clip := COMBO_CLIPS[idx]
	combo_step = (idx + 1) % COMBO_CLIPS.size()
	var is_heavy := (idx >= 5)
	var rolled := roll_strike_damage(is_heavy, false)
	var hit_frames: Array = COMBO_HIT_FRAMES.get(clip, [2])
	hero_state_changed.emit()
	return {
		"step_index": idx,
		"step_number": idx + 1,
		"clip": clip,
		"is_heavy": is_heavy,
		"damage": float(rolled["damage"]),
		"is_crit": bool(rolled["is_crit"]),
		"hit_frames": hit_frames.duplicate(),
		"has_gold_slash_60": (clip == "attack_6"),
		"gold_slash_frame": 13,
		"gold_slash_damage": 60.0,
	}


func trigger_transform_toggle() -> String:
	if not is_ssj:
		is_ssj = true
		transform_invuln_s = TRANSFORM_INVULN_DURATION_S
		hero_state_changed.emit()
		return "transform_ssj"
	else:
		is_ssj = false
		transform_invuln_s = 0.0
		if is_airborne_flight():
			flight_state = "falling"
			hover_timer_s = 0.0
		hero_state_changed.emit()
		return "detransform_base"


func trigger_fast_drop_from_flight() -> bool:
	if is_airborne_flight():
		flight_state = "falling"
		hover_timer_s = 0.0
		hero_state_changed.emit()
		return true
	return false


func step_hero_timers(delta: float, has_move_input: bool, on_ground: bool, holding_up: bool = false, altitude_px: float = 0.0, holding_down: bool = false, is_air_action_active: bool = false) -> void:
	if delta <= 0.0:
		return
	var prev_stam := stamina
	stamina = minf(max_stamina, stamina + STAMINA_REGEN_PER_S * delta)
	if absf(stamina - prev_stam) > 0.001:
		hero_state_changed.emit()

	if transform_invuln_s > 0.0:
		transform_invuln_s = maxf(0.0, transform_invuln_s - delta)
		var spr := get_node_or_null("Sprite") as AnimatedSprite2D
		if spr != null and String(spr.animation) != "transform_ssj":
			transform_invuln_s = 0.0

	if armor_hit_timer_s > 0.0:
		armor_hit_timer_s = maxf(0.0, armor_hit_timer_s - delta)

	if jump_land_hold_s > 0.0:
		jump_land_hold_s = maxf(0.0, jump_land_hold_s - delta)

	if game_state == "combat":
		combat_timer_s = maxf(0.0, combat_timer_s - delta)
		if combat_timer_s <= 0.0:
			game_state = "peace"
			in_combat = false
			hero_state_changed.emit()

	# Jump + Hold Analog UP -> Fly_Aura (SSJ1 ONLY; Base cannot enter fly_aura!)
	if flight_state == "ground":
		if on_ground:
			jump_hold_up_s = 0.0
			jump_ascend_s = 0.0
		else:
			jump_ascend_s += delta
			if is_ssj and holding_up and altitude_px >= JUMP_TO_FLY_MIN_ALT_PX:
				jump_hold_up_s += delta
				if jump_hold_up_s >= JUMP_TO_FLY_HOLD_S:
					flight_state = "flying"
					hover_timer_s = HOVER_TIMEOUT_S
					jump_hold_up_s = 0.0
					hero_state_changed.emit()
			else:
				jump_hold_up_s = maxf(0.0, jump_hold_up_s - delta * 2.0)
	elif flight_state == "flying":
		hover_timer_s = HOVER_TIMEOUT_S
		if not is_ssj:
			flight_state = "falling"
			hover_timer_s = 0.0
			hero_state_changed.emit()
		elif not has_move_input and not is_air_action_active:
			flight_state = "hovering"
			hover_timer_s = HOVER_TIMEOUT_S
			hero_state_changed.emit()
	elif flight_state == "hovering":
		if not is_ssj:
			flight_state = "falling"
			hover_timer_s = 0.0
			hero_state_changed.emit()
		elif holding_down and not is_air_action_active:
			# Owner v4 rule: pulling analog DOWN during fly_prep immediately fast-drops without waiting!
			flight_state = "falling"
			hover_timer_s = 0.0
			hero_state_changed.emit()
		elif is_air_action_active:
			# Owner supplement: attacking / teleporting mid-air NEVER auto-drops after 3s!
			hover_timer_s = HOVER_TIMEOUT_S
		elif has_move_input:
			flight_state = "flying"
			hover_timer_s = HOVER_TIMEOUT_S
			hero_state_changed.emit()
		else:
			# ONLY idle `fly_prep` counts down 3s before auto-dropping!
			hover_timer_s = maxf(0.0, hover_timer_s - delta)
			if hover_timer_s <= 0.0:
				flight_state = "falling"
				hero_state_changed.emit()
	elif flight_state == "falling":
		if on_ground:
			flight_state = "ground"
			jump_land_hold_s = 0.09
			hero_state_changed.emit()


func step_combat_move_frame(delta: float, move_rel_dir: int) -> int:
	## Exact Owner v4 loop timing for `combat_move` (`16`):
	## - Backward (`move_rel_dir < 0`): #0 (300ms) -> #1 (80ms) -> #0 (300ms) -> #1 (80ms)
	## - Forward  (`move_rel_dir > 0`): #3 (300ms) -> #2 (80ms) -> #3 (300ms) -> #2 (80ms)
	if move_rel_dir == 0:
		_combat_move_dir_last = 0
		_combat_move_phase = 0
		_combat_move_phase_t = 0.0
		return combat_move_frame
	var sgn := -1 if move_rel_dir < 0 else 1
	if sgn != _combat_move_dir_last:
		_combat_move_dir_last = sgn
		_combat_move_phase = 0
		_combat_move_phase_t = 0.0
	else:
		_combat_move_phase_t += delta
		var dur := COMBAT_MOVE_PRIMARY_HOLD_S if _combat_move_phase == 0 else COMBAT_MOVE_LOOP_RETURN_S
		if _combat_move_phase_t >= dur:
			_combat_move_phase_t -= dur
			_combat_move_phase = 1 - _combat_move_phase
	if sgn < 0:
		combat_move_frame = 0 if _combat_move_phase == 0 else 1
	else:
		combat_move_frame = 3 if _combat_move_phase == 0 else 2
	return combat_move_frame


func resolve_jump_pose_frame(vy: float, on_ground: bool) -> int:
	## Exact jump frame mapping (`07`):
	## F0..F2: crouch & ascending upward; F3: apex/start fall;
	## F4: universal falling pose (from jump apex OR high altitude/flight/fast-drop);
	## F5: landing frame before returning to idle.
	if on_ground and jump_land_hold_s > 0.0:
		return 5
	if flight_state == "falling":
		return 4
	if vy < -90.0:
		if jump_ascend_s < 0.055:
			return 0
		elif jump_ascend_s < 0.13:
			return 1
		return 2
	if vy < 130.0:
		return 3
	return 4


func try_consume_stamina(cost: float) -> bool:
	if stamina + 0.001 < cost:
		return false
	stamina = maxf(0.0, stamina - cost)
	hero_state_changed.emit()
	return true


func resolve_locomotion_clip(moving: bool, airborne: bool) -> StringName:
	if flight_state == "flying":
		return &"fly_aura"
	if flight_state == "hovering":
		return &"fly_prep"
	if not is_ssj:
		return &"walk" if moving else &"idle"
	if airborne or flight_state == "falling" or jump_land_hold_s > 0.0:
		return &"jump"
	if moving:
		return &"combat_move" if game_state == "combat" else &"walk_ssj"
	# NO idle_ssj! Peace SSJ1 standing ALWAYS returns to `idle_ssj_aura`; Combat standing = `idle_combat`!
	if game_state == "combat":
		return &"idle_combat"
	return &"idle_ssj_aura"
