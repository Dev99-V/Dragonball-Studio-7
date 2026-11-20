class_name SaiyanHeroFighter2D
extends CharacterFighter2D
## First Playable Hero Controller — Son Goku (Phase 1 v8):
## - Two Game States: "peace" (Hòa bình) vs "combat" (Chiến đấu) with explicit clip state filtering.
## - NO `idle_ssj`: SSJ1 Peace standing = `idle_ssj_aura` (always returns after moving in Peace);
##   Peace -> Combat bridges via `combat_enter` (34 F0..F3) -> `idle_combat` (34 F4..F7, standing martial-arts knee bounce).
## - Invulnerable during `transform_ssj`.
## - 7-Step Normal Combo (10->11->12->13->14->17->15), ~60ms/frame + 20ms combo link, per-frame hit impacts & damage:
##   Light = 10..20 (crit 20), Heavy = 50, attack_6 gold slash (#13) = 60.
## - Combat Move (`16`) Continuous Dash + Analog Brake (NO aura, NO hop-and-land):
##   Backward dash (`#0`): 400 px/s continuous retreat while analog pulled away past threshold (>= 0.55).
##   Forward  dash (`#3`): 500 px/s continuous advance while analog pushed toward past threshold (>= 0.55).
##   Brake cushions (`#1` back / `#2` fwd): triggered when pulling analog near center (0.08..0.55) or releasing to brake.
## - 360° Analog Jump (~100px height): F0..F2 up, F3..F5 fall/land, F4 universal high-fall.
## - Flight (SSJ1 only, 400 px/s, NO fly_launch): powered by Orange KI bar (50 max, -5 KI/s flying, +5 KI/s regen when grounded;
##   exhausting KI forces immediate fall until KI recovers). Jump + Hold Analog UP -> `fly_aura` -> Stop -> 3s `fly_prep`
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
const KI_MAX: float = 50.0
const KI_FLY_DRAIN_PER_S: float = 5.0
const KI_REGEN_PER_S: float = 5.0
const KI_MIN_TAKEOFF: float = 5.0
const BARRIER_DURATION_S: float = 10.0
const BARRIER_COOLDOWN_S: float = 16.0
const RECOVER_DURATION_S: float = 3.0
const RECOVER_COOLDOWN_S: float = 10.0
const FLURRY_KICK_COOLDOWN_S: float = 6.0
const FLURRY_KICK_STUN_S: float = 1.6
const FLURRY_KICK_LUNGE_SPEED_PX_S: float = 260.0
const FLURRY_KICK_RANGE_FWD_PX: float = 215.0
const FLURRY_KICK_RANGE_V_PX: float = 160.0
const FLURRY_KICK_SPEED_FACTOR: float = 0.70
const ATOMIC_COOLDOWN_S: float = 12.0
const ATOMIC_SPEED_PX_S: float = 1500.0
const ATOMIC_BOLT_COUNT: int = 4
const KAME_MANA_COST: float = 80.0
const KAME_SPEED_PX_S: float = 1800.0
const KAME_HOLD_S: float = 1.0
const KAME_FADE_S: float = 0.36
const KAME_CHARGE_SPEED_SCALE: float = 0.70
const HERO_MAX_MANA: float = 100.0
const TELEPORT_STATIC_COST: float = 75.0
const TELEPORT_DASH_COST: float = 25.0
const TELEPORT_DASH_DIST_PX: float = 100.0
const HOVER_TIMEOUT_S: float = 3.0
const COMBAT_TIMEOUT_S: float = 6.0
const WALK_SPEED_PX_S: float = 200.0
const COMBAT_MOVE_BACK_SPEED_PX_S: float = 400.0
const COMBAT_MOVE_FWD_SPEED_PX_S: float = 500.0
const COMBAT_MOVE_BRAKE_SPEED_PX_S: float = 120.0
const COMBAT_MOVE_ANALOG_DASH_THRESHOLD: float = 0.55
const COMBAT_MOVE_ANALOG_BRAKE_MIN: float = 0.08
const COMBAT_MOVE_BRAKE_HOLD_S: float = 0.12
const COMBAT_MOVE_SPEED_PX_S: float = COMBAT_MOVE_FWD_SPEED_PX_S
const COMBAT_MOVE_HOVER_Y_PX: float = 10.0
const COMBAT_MOVE_BOB_AMP_PX: float = 2.5
const COMBAT_MOVE_BOB_FREQ_RAD_S: float = 28.0
const FLIGHT_SPEED_PX_S: float = 400.0
const FAST_DROP_VY_PX_S: float = 520.0
const COMBO_LINK_COOLDOWN_S: float = 0.02 # 20ms fluid combo link between attack_light..attack_7 (Owner tuning)!
const JUMP_HEIGHT_PX: float = 100.0
const JUMP_GRAVITY_PX_S2: float = 2000.0
const JUMP_VELOCITY_PX_S: float = -632.4555 # sqrt(2 * 2000 * 100) = 100.0 px apex
const JUMP_TO_FLY_HOLD_S: float = 0.14
const JUMP_TO_FLY_MIN_ALT_PX: float = 32.0
const TRANSFORM_INVULN_DURATION_S: float = 0.85

var is_ssj: bool = false
var game_state: String = "peace" # "peace" | "combat"
var in_combat: bool = false
var combat_timer_s: float = 0.0
var transform_invuln_s: float = 0.0
var combo_step: int = 0

var stamina: float = STAMINA_MAX
var max_stamina: float = STAMINA_MAX
var ki: float = KI_MAX
var max_ki: float = KI_MAX
var ki_exhausted: bool = false

# Flight state machine (NO fly_launch!): "ground" | "flying" | "hovering" | "falling"
var flight_state: String = "ground"
var hover_timer_s: float = 0.0
var jump_hold_up_s: float = 0.0
var jump_ascend_s: float = 0.0
var jump_land_hold_s: float = 0.0

# Combat Move (`16`) Continuous Dash + Analog Brake state (NO aura, NO hop-and-land):
# Backward (-1): Dash #0 (400 px/s) -> Brake #1 (analog near center / release)
# Forward  (+1): Dash #3 (500 px/s) -> Brake #2 (analog near center / release)
var combat_move_frame: int = 3
var _combat_move_dir_last: int = 0
var _combat_move_braking: bool = false
var _combat_move_brake_timer_s: float = 0.0
var _combat_move_speed_cur: float = 0.0
var _combat_move_just_braked: bool = false
var _combat_move_dash_t: float = 0.0

# Armor-break HIT reaction tracking
var armor_hit_timer_s: float = 0.0

# Phase 2 Active Skill Timers & Buffs (Owner 2026-11-20):
var barrier_timer_s: float = 0.0        # Active LOOP 10S protective shield (moves/attacks freely!)
var barrier_cooldown_s: float = 0.0
var recover_timer_s: float = 0.0        # Active 3s energy recovery channel (HP + Armor + Flight KI)
var recover_cooldown_s: float = 0.0
var flurry_cooldown_s: float = 0.0      # Flurry kick cooldown (applies hard stun + yellow stars ring)
var atomic_cooldown_s: float = 0.0      # Atomic blast 12s cooldown
var kame_cooldown_s: float = 0.0        # Kamehameha brief recast lock (250 Mana gated)

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
	return is_ssj and (not ki_exhausted) and ki > 0.001


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
	ki = KI_MAX
	ki_exhausted = false
	flight_state = "ground"
	hover_timer_s = 0.0
	jump_hold_up_s = 0.0
	jump_ascend_s = 0.0
	jump_land_hold_s = 0.0
	combat_move_frame = 3
	_combat_move_dir_last = 0
	_combat_move_braking = false
	_combat_move_brake_timer_s = 0.0
	_combat_move_speed_cur = 0.0
	_combat_move_just_braked = false
	armor_hit_timer_s = 0.0
	barrier_timer_s = 0.0
	barrier_cooldown_s = 0.0
	recover_timer_s = 0.0
	recover_cooldown_s = 0.0
	flurry_cooldown_s = 0.0
	atomic_cooldown_s = 0.0
	kame_cooldown_s = 0.0
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
	var prev_ki := ki
	var prev_ki_ex := ki_exhausted
	if flight_state == "flying" or flight_state == "hovering":
		# Orange KI flight resource: drains 5 KI/s while flying/hovering; hitting 0 forces immediate fall!
		ki = maxf(0.0, ki - KI_FLY_DRAIN_PER_S * delta)
		if ki <= 0.0:
			ki = 0.0
			ki_exhausted = true
			flight_state = "falling"
			hover_timer_s = 0.0
	else:
		# Not flying: regenerates +5 KI/s up to 50 KI; clears exhausted gate once >= 5 KI (1s recovery)
		ki = minf(max_ki, ki + KI_REGEN_PER_S * delta)
		if ki_exhausted and ki >= KI_MIN_TAKEOFF:
			ki_exhausted = false
	if absf(stamina - prev_stam) > 0.001 or absf(ki - prev_ki) > 0.001 or ki_exhausted != prev_ki_ex:
		hero_state_changed.emit()

	if transform_invuln_s > 0.0:
		transform_invuln_s = maxf(0.0, transform_invuln_s - delta)
		var spr := get_node_or_null("Sprite") as AnimatedSprite2D
		if spr != null and String(spr.animation) != "transform_ssj":
			transform_invuln_s = 0.0

	if armor_hit_timer_s > 0.0:
		armor_hit_timer_s = maxf(0.0, armor_hit_timer_s - delta)

	if barrier_timer_s > 0.0:
		barrier_timer_s = maxf(0.0, barrier_timer_s - delta)
	if barrier_cooldown_s > 0.0:
		barrier_cooldown_s = maxf(0.0, barrier_cooldown_s - delta)
	if recover_timer_s > 0.0:
		recover_timer_s = maxf(0.0, recover_timer_s - delta)
	if recover_cooldown_s > 0.0:
		recover_cooldown_s = maxf(0.0, recover_cooldown_s - delta)
	if flurry_cooldown_s > 0.0:
		flurry_cooldown_s = maxf(0.0, flurry_cooldown_s - delta)
	if atomic_cooldown_s > 0.0:
		atomic_cooldown_s = maxf(0.0, atomic_cooldown_s - delta)
	if kame_cooldown_s > 0.0:
		kame_cooldown_s = maxf(0.0, kame_cooldown_s - delta)

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
			if can_fly() and holding_up and altitude_px >= JUMP_TO_FLY_MIN_ALT_PX:
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


func reset_combat_move() -> void:
	_combat_move_dir_last = 0
	_combat_move_braking = false
	_combat_move_brake_timer_s = 0.0
	_combat_move_speed_cur = 0.0
	_combat_move_just_braked = false
	_combat_move_dash_t = 0.0


func step_combat_move_frame(delta: float, move_rel_dir: int, analog_mag: float = 1.0) -> int:
	## Exact Owner v10 continuous dash + analog near-center brake for `combat_move` (`16`, NO aura):
	## - Backward (`move_rel_dir < 0`):
	##     Full Dash (`analog_mag >= 0.55`): holds Frame #0 continuously at 400 px/s with low dynamic glide hover (~10 +/- 2.5px) + wind streaks.
	##     Brake (`0.08 <= analog_mag < 0.55` or release to center): drops to floor on Frame #1 (braking cushion).
	## - Forward  (`move_rel_dir > 0`):
	##     Full Dash (`analog_mag >= 0.55`): holds Frame #3 continuously at 500 px/s with low dynamic glide hover (~10 +/- 2.5px) + wind streaks.
	##     Brake (`0.08 <= analog_mag < 0.55` or release to center): drops to floor on Frame #2 (braking cushion).
	_combat_move_just_braked = false
	var dt := maxf(0.0, delta)
	var mag := clampf(analog_mag, 0.0, 1.0)
	if move_rel_dir != 0 and mag >= COMBAT_MOVE_ANALOG_DASH_THRESHOLD:
		var sgn := -1 if move_rel_dir < 0 else 1
		if _combat_move_dir_last != sgn or _combat_move_braking:
			_combat_move_dash_t = 0.0
		_combat_move_dir_last = sgn
		_combat_move_braking = false
		_combat_move_brake_timer_s = 0.0
		_combat_move_dash_t += dt
		_combat_move_speed_cur = COMBAT_MOVE_BACK_SPEED_PX_S if sgn < 0 else COMBAT_MOVE_FWD_SPEED_PX_S
		combat_move_frame = 0 if sgn < 0 else 3
		return combat_move_frame

	if move_rel_dir != 0 and mag >= COMBAT_MOVE_ANALOG_BRAKE_MIN:
		var sgn := -1 if move_rel_dir < 0 else 1
		if not _combat_move_braking and _combat_move_dir_last != 0:
			_combat_move_just_braked = true
		_combat_move_dir_last = sgn
		_combat_move_braking = true
		_combat_move_dash_t = 0.0
		_combat_move_brake_timer_s = COMBAT_MOVE_BRAKE_HOLD_S
		var frac := clampf((mag - COMBAT_MOVE_ANALOG_BRAKE_MIN) / maxf(0.01, COMBAT_MOVE_ANALOG_DASH_THRESHOLD - COMBAT_MOVE_ANALOG_BRAKE_MIN), 0.0, 1.0)
		_combat_move_speed_cur = lerpf(25.0, COMBAT_MOVE_BRAKE_SPEED_PX_S, frac)
		combat_move_frame = 1 if sgn < 0 else 2
		return combat_move_frame

	# Analog returned to deadzone / center: play crisp braking cushion (#1 back / #2 fwd) if we were dashing!
	if _combat_move_dir_last != 0:
		if dt <= 0.0 and not _combat_move_braking:
			# Explicit reset_combat_move style call step_combat_move_frame(0.0, 0)
			reset_combat_move()
			return combat_move_frame
		if not _combat_move_braking:
			_combat_move_braking = true
			_combat_move_dash_t = 0.0
			_combat_move_brake_timer_s = COMBAT_MOVE_BRAKE_HOLD_S
			_combat_move_just_braked = true
		_combat_move_brake_timer_s = maxf(0.0, _combat_move_brake_timer_s - dt)
		combat_move_frame = 1 if _combat_move_dir_last < 0 else 2
		if _combat_move_brake_timer_s > 0.0:
			var remain := _combat_move_brake_timer_s / maxf(0.001, COMBAT_MOVE_BRAKE_HOLD_S)
			_combat_move_speed_cur = COMBAT_MOVE_BRAKE_SPEED_PX_S * remain
			return combat_move_frame
		reset_combat_move()
		return combat_move_frame

	_combat_move_speed_cur = 0.0
	_combat_move_dash_t = 0.0
	return combat_move_frame


func is_combat_move_dashing() -> bool:
	return _combat_move_dir_last != 0 and not _combat_move_braking


func is_combat_move_braking() -> bool:
	return _combat_move_braking and _combat_move_dir_last != 0


func get_combat_move_brake_rel_dir() -> int:
	return _combat_move_dir_last if _combat_move_braking else 0


func get_combat_move_dash_rel_dir() -> int:
	return _combat_move_dir_last if is_combat_move_dashing() else 0


func get_combat_move_dash_time_s() -> float:
	return _combat_move_dash_t


func get_combat_move_hop_height_px() -> float:
	if not is_combat_move_dashing():
		return 0.0
	return maxf(4.0, COMBAT_MOVE_HOVER_Y_PX + sin(_combat_move_dash_t * COMBAT_MOVE_BOB_FREQ_RAD_S) * COMBAT_MOVE_BOB_AMP_PX)


func get_combat_move_speed_px_s() -> float:
	return _combat_move_speed_cur


func consume_combat_move_just_landed() -> bool:
	var v := _combat_move_just_braked
	_combat_move_just_braked = false
	return v


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


func is_barrier_active() -> bool:
	return barrier_timer_s > 0.0


func trigger_barrier() -> bool:
	if not is_ssj or barrier_cooldown_s > 0.0:
		return false
	barrier_timer_s = BARRIER_DURATION_S
	barrier_cooldown_s = BARRIER_COOLDOWN_S
	enter_combat()
	hero_state_changed.emit()
	return true


func trigger_energy_recover() -> bool:
	if not is_ssj or recover_cooldown_s > 0.0:
		return false
	recover_timer_s = RECOVER_DURATION_S
	recover_cooldown_s = RECOVER_COOLDOWN_S
	flight_state = "ground"
	hover_timer_s = 0.0
	hero_state_changed.emit()
	return true


func trigger_flurry_kick() -> bool:
	if not is_ssj or flurry_cooldown_s > 0.0:
		return false
	flurry_cooldown_s = FLURRY_KICK_COOLDOWN_S
	enter_combat()
	if is_airborne_flight():
		hover_timer_s = HOVER_TIMEOUT_S
	hero_state_changed.emit()
	return true


func trigger_atomic_blast() -> bool:
	if not is_ssj or atomic_cooldown_s > 0.0:
		return false
	atomic_cooldown_s = ATOMIC_COOLDOWN_S
	enter_combat()
	if is_airborne_flight():
		hover_timer_s = HOVER_TIMEOUT_S
	hero_state_changed.emit()
	return true


func trigger_kamehameha(current_mana: float) -> bool:
	if not is_ssj or kame_cooldown_s > 0.0 or current_mana + 0.001 < KAME_MANA_COST:
		return false
	kame_cooldown_s = 1.5
	enter_combat()
	if is_airborne_flight():
		hover_timer_s = HOVER_TIMEOUT_S
	hero_state_changed.emit()
	return true


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
