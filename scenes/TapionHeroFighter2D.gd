class_name TapionHeroFighter2D
extends SaiyanHeroFighter2D
## Playable Hero Controller — Tapion (Complete 47/47 Source Setup: Core + 10-Step Sword Combo + Ocarina & 4 Signature Skills):
## - Single-form Konatsian Hero (`is_ssj = true` always).
## - Peace State: `idle` (playing Ocarina flute) + independent rainbow musical aura (`PeaceAuraFX` @ z=-1) + `walk` (200 px/s).
## - Combat State: `combat_enter` -> `idle_combat` + `combat_move` (400 back / 500 fwd px/s + brake #1/#2).
## - Flight Speed: +30% faster (`520 px/s` vs Goku's `400 px/s`).
## - 10-Step Sword Combo (`attack_light`..`attack_10` @ 60ms/frame + 40ms combo link + `atk10_impact_fx` under target feet @ top layer + mini-stun).
## - Full Ocarina & 4 Signature Skills (`tapion_skills_fx.tres`, ALL skills & explosions rendered on TOP layer z>=69):
##     1. `barrier` -> `barrier_cast` (9f) + multi-layer blue energy sphere `barrier_dome_fx` (Frame-8 reference)
##     2. `energy_recover` -> `energy_recover` (8f Ocarina white-cyan lightning aura @ 100ms/frame, grounded)
##     3. `kentaima` -> `kentaima_cast` (4f) + target-locked `kentaima_wave_fx` @ 2500px/s -> `kentaima_impact_fx` + 5s `Kentai` green-burn debuff & overhead icon
##     4. `mahasenko` -> `mahasenko_ground`/`mahasenko_air` + `mahasenko_hand_fx` (-30% again in v6) spaced 30px ahead of fingertips ->
##                       4 sequential alternating curved beams (-30%, left -> right -> left -> right, trailing cleanly 30px apart) @ 2500px/s -> `mahasenko_impact_fx`
##     5. `antamina` (100 MP, UNLIMITED RANGE) -> `antamina_combo` 3.0s charge (`#0..#2` prep -> clean `#3..#5` stance loop + detached 6-frame `antamina_charge_orb_fx` @ 80ms/frame playing `#0->#1` intro then looping `#2,#3,#4,#5`) ->
##                       firing loop across consistent `0,1,2` poses with white/yellow directional blast light reflection (`#6..#8` <-> `#3..#5`, ZERO pose flipping!) firing 5 rapid `antamina_stream_fx` @ 4000px/s (80 dmg/shot),
##                       or 7 shots (+30% = 104 dmg/shot, consumes 5 stacks) if target has 5 stacks of "Ấn ngục" (Suy yếu), -> `antamina_impact_fx` (100/110/120ms) -> `#9..#10` return to idle!
##                       Interruptible by Hard Stun or Armor Break (`hit`), NEVER loses "Ấn ngục" stacks; taking damage with armor intact does NOT cancel Antamina!
##     6. `bukadai` -> `bukadai_rush` teleport blitz directly onto locked target -> `bukadai_vanish_fx` + `bukadai_sphere_fx` + 2.0s stun;
##                     hitting a target afflicted by 5s `Kentai` procs +1 stack of "Ấn ngục" (up to 5 -> Suy yếu, multi-target, persists until Tapion dies/leaves zone/map)!

const TAPION_COMBO_CLIPS: Array[String] = [
	"attack_light",  # 1. tấn công 1 (6f @ 60ms)
	"attack_2",      # 2. tấn công 2 (5f @ 60ms)
	"attack_3",      # 3. tấn công 3 (5f @ 60ms)
	"attack_4",      # 4. tấn công 4 (2f @ 60ms)
	"attack_5",      # 5. tấn công 5 (3f @ 60ms)
	"attack_6",      # 6. tấn công 6 (3f @ 60ms)
	"attack_7",      # 7. Tấn công 7 — kiếm khí xanh mặt đất (5f @ 60ms)
	"attack_8",      # 8. Tấn công 8 — kiếm khí xanh xoáy lên không (5f @ 60ms)
	"attack_9",      # 9. tấn công 9 — kiếm khí xanh chém đôi trên không (5f @ 60ms)
	"attack_10",     # 10. tấn công 10 (nặng) — LOOP X2 nhảy bổ kiếm cắm đất (8 steps @ 60ms)
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

const TAPION_FLIGHT_SPEED_PX_S: float = 520.0       # +30% flight speed (400 * 1.30)
const TAPION_COMBO_LINK_COOLDOWN_S: float = 0.04    # 40ms gap between normal attack clips

const KENTAIMA_CD_S: float = 1.5
const KENTAIMA_DEBUFF_DURATION_S: float = 5.0
const MAHASENKO_CD_S: float = 1.5
const MAHASENKO_BOLT_COUNT: int = 4
const MAHASENKO_BOLT_TRAIL_DELAY_S: float = 0.074   # Cleanly separates each 70%-scaled trailing bolt by ~30px tail gap @ 2500px/s!
const ANTAMINA_CD_S: float = 2.0
const ANTAMINA_MANA_COST: float = 100.0
const ANTAMINA_CHARGE_S: float = 3.0
const ANTAMINA_PREP_S: float = 0.24
const ANTAMINA_ORB_FRAME_S: float = 0.08            # 80ms/frame: #0->#1 intro then continuous loop #2,#3,#4,#5!
const ANTAMINA_BODY_LOOP_STEP_S: float = 0.095
const ANTAMINA_BASE_SHOTS: int = 5
const ANTAMINA_WEAKENED_SHOTS: int = 7
const ANTAMINA_BASE_DMG: float = 80.0
const ANTAMINA_WEAKENED_DMG: float = 104.0          # +30% damage vs Weakened (5 stacks Ấn ngục)
const ANTAMINA_SHOT_INTERVAL_S: float = 0.14
const BUKADAI_CD_S: float = 1.8
const BUKADAI_STUN_S: float = 2.0

# Exact measured horizontal cast range matching red line in K70E 2460x1080 view (`image copy 3.png`: half-span = 1173.5px -> 1175px).
# Applies to Kentaima, Mahasenko & Bukadai (Antamina has UNLIMITED range!).
const TAPION_SKILL_MAX_RANGE_PX: float = 1175.0

const MAHASENKO_SPEED_PX_S: float = 2500.0
const KENTAIMA_SPEED_PX_S: float = 2500.0
const ANTAMINA_SPEED_PX_S: float = 4000.0
const MAHA_BEAM_AIR_BASE_RAD: float = 0.587  # Measured PCA axis of 70%-scaled maha_beam_air_00 (+33.63 deg)

# Exact measured fingertip hand offsets relative to Tapion anchor [144, 248]:
# - Ground Mahasenko (`maha_gnd_02` fingertips x=232 -> +88, +4px gap matching `image copy.png` yellow Rect(234,180) => (+92, -64))
# - Air Mahasenko (`maha_air_01` fingertips x=183 -> +39, +5px gap => (+44, -58))
# - Antamina (`antamina_combo` orb center (217, 186) => (+73.0, -62.0))
const MAHASENKO_GND_HAND_OFFSET := Vector2(92.0, -64.0)
const MAHASENKO_AIR_HAND_OFFSET := Vector2(44.0, -58.0)
const MAHASENKO_HAND_FX_CLEARANCE_PX: float = 30.0  # Exact half-width of -30% v6 `maha_hand_00` (60px) so ZERO pixels cover Tapion's hand!
const ANTAMINA_HAND_OFFSET := Vector2(73.0, -62.0)

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
var _antamina_charge_fx: AnimatedSprite2D = null
var _ground_impact_fx: AnimatedSprite2D = null
var _skills_fx_frames: SpriteFrames = null

var _atk10_fx_stage: int = 0
var _atk10_stunned_slot: Dictionary = {}
var _skill_fx_fired_for_cast: bool = false
var _bukadai_dashed_for_cast: bool = false
var _locked_skill_target: Dictionary = {}

# Sequential 4-bolt Mahasenko queue (left -> right -> left -> right, trailing 30px apart)
var _pending_mahasenko_bolts: Array[Dictionary] = []

# Antamina 2.0s charge (clean `#3..#5` loop + independent 60ms `antamina_charge_orb_fx`) -> 5/7-shot barrage (`#6..#8` lit <-> `#3..#5` clean, ZERO flip!) -> recovery (`#9..#10`)
var _antamina_phase: String = ""                    # "" | "charging" | "firing" | "ending"
var _antamina_charging: bool = false
var _antamina_charge_elapsed_s: float = 0.0
var _antamina_locked_facing_sign: float = 1.0
var _antamina_body_loop_idx: int = 0
var _antamina_shots_total: int = ANTAMINA_BASE_SHOTS
var _antamina_shots_fired: int = 0
var _antamina_shot_timer_s: float = 0.0
var _antamina_shot_dmg: float = ANTAMINA_BASE_DMG
var _antamina_used_weakened: bool = false
var _antamina_weakened_slot: Dictionary = {}

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


func _clear_antamina_state() -> void:
	_antamina_phase = ""
	_antamina_charging = false
	_antamina_charge_elapsed_s = 0.0
	_antamina_body_loop_idx = 0
	_antamina_shots_total = ANTAMINA_BASE_SHOTS
	_antamina_shots_fired = 0
	_antamina_shot_timer_s = 0.0
	_antamina_shot_dmg = ANTAMINA_BASE_DMG
	_antamina_used_weakened = false
	_antamina_weakened_slot = {}
	if _antamina_charge_fx != null and is_instance_valid(_antamina_charge_fx):
		_antamina_charge_fx.visible = false
		_antamina_charge_fx.stop()


func cancel_antamina_interrupt() -> void:
	## Called ONLY on Hard Stun (khống chế) or Armor Break (`hit`) or KO.
	## Cancels active Antamina immediately WITHOUT losing any target's "Ấn ngục" stacks!
	_clear_antamina_state()
	_pending_mahasenko_bolts.clear()
	_skill_fx_fired_for_cast = false
	_bukadai_dashed_for_cast = false


func _clear_spawned_fx() -> void:
	_clear_antamina_state()
	_pending_mahasenko_bolts.clear()
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


func get_flight_speed_px_s() -> float:
	return TAPION_FLIGHT_SPEED_PX_S


func get_combo_link_cooldown_s() -> float:
	return TAPION_COMBO_LINK_COOLDOWN_S


func can_attack() -> bool:
	return true


func can_jump() -> bool:
	return true


func can_fly() -> bool:
	return (not ki_exhausted) and ki > 0.001


func get_hero_display_name() -> String:
	return "Tapion"


func is_antamina_charging() -> bool:
	return _antamina_phase == "charging"


func is_antamina_active() -> bool:
	return not _antamina_phase.is_empty()


func lock_antamina_facing() -> void:
	_antamina_locked_facing_sign = -1.0 if scale.x < 0.0 else 1.0


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
	_update_antamina_charge_fx_visibility()


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
	_pending_mahasenko_bolts.clear()
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
	_clear_antamina_state()
	_antamina_phase = "charging"
	_antamina_charging = true
	_antamina_charge_elapsed_s = 0.0
	_antamina_locked_facing_sign = -1.0 if scale.x < 0.0 else 1.0
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
	if _antamina_charge_fx == null:
		_antamina_charge_fx = get_node_or_null("AntaminaChargeFX") as AnimatedSprite2D
		if _antamina_charge_fx == null and _skills_fx_frames != null:
			_antamina_charge_fx = AnimatedSprite2D.new()
			_antamina_charge_fx.name = "AntaminaChargeFX"
			add_child(_antamina_charge_fx)
		if _antamina_charge_fx != null:
			_antamina_charge_fx.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
			if _antamina_charge_fx.sprite_frames == null and _skills_fx_frames != null:
				_antamina_charge_fx.sprite_frames = _skills_fx_frames
			_antamina_charge_fx.centered = false
			_antamina_charge_fx.offset = Vector2(-144.0, -176.0)
			_antamina_charge_fx.position = ANTAMINA_HAND_OFFSET
			_antamina_charge_fx.z_index = TOP_FX_PROJ_Z
			_antamina_charge_fx.visible = false


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


func _update_antamina_charge_fx_visibility() -> void:
	_ensure_tapion_fx_nodes()
	if _antamina_charge_fx == null or sprite == null:
		return
	var show_orb := (
		_antamina_phase == "charging"
		and _antamina_charge_elapsed_s >= ANTAMINA_PREP_S
		and sprite.visible
		and String(sprite.animation) == "antamina_combo"
		and _antamina_charge_fx.sprite_frames != null
		and _antamina_charge_fx.sprite_frames.has_animation(&"antamina_charge_orb_fx")
	)
	if show_orb:
		_antamina_charge_fx.position = ANTAMINA_HAND_OFFSET
		_antamina_charge_fx.z_index = TOP_FX_PROJ_Z
		if not _antamina_charge_fx.visible:
			_antamina_charge_fx.visible = true
		if _antamina_charge_fx.animation != &"antamina_charge_orb_fx":
			_antamina_charge_fx.animation = &"antamina_charge_orb_fx"
		# Explicit 80ms/frame progression: plays intro #0 -> #1 once, then loops #2 -> #3 -> #4 -> #5 -> #2 continuously over 3.0s!
		var orb_t: float = maxf(0.0, _antamina_charge_elapsed_s - ANTAMINA_PREP_S)
		var raw_step: int = int(floor(orb_t / ANTAMINA_ORB_FRAME_S))
		var orb_f: int = raw_step if raw_step < 2 else (2 + ((raw_step - 2) % 4))
		var fc := _antamina_charge_fx.sprite_frames.get_frame_count(&"antamina_charge_orb_fx")
		if fc > 0:
			_antamina_charge_fx.pause()
			_antamina_charge_fx.set_frame_and_progress(clampi(orb_f, 0, fc - 1), 0.0)
	else:
		if _antamina_charge_fx.visible:
			_antamina_charge_fx.visible = false
		if _antamina_charge_fx.is_playing():
			_antamina_charge_fx.stop()


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
	scale_mul: float = 1.0,
	curve_mode: String = "",
	launch_facing: float = 1.0,
	caster_origin: Vector2 = Vector2.ZERO,
	caster_scale: float = 1.0
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
	var init_dir := fallback_dir.normalized() if curve_mode == "overhead_uturn" else ((end_pos - start_pos).normalized() if end_pos.distance_to(start_pos) > 2.0 else fallback_dir.normalized())
	node.top_level = true
	node.global_position = start_pos
	_apply_oriented_transform(node, init_dir, sc, base_angle_rad)
	node.z_index = TOP_FX_PROJ_Z
	var host: Node = get_parent() if get_parent() != null else self
	host.add_child(node)
	node.play(clip_name)
	var est_dist := start_pos.distance_to(end_pos)
	var max_age := maxf(1.6, est_dist / maxf(400.0, speed_px_s) + 0.9)
	if curve_mode == "overhead_uturn":
		max_age = maxf(2.4, max_age + 0.6)
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
		"max_age_s": max_age,
		"curve_mode": curve_mode,
		"launch_facing": launch_facing,
		"caster_origin": caster_origin,
		"caster_scale": caster_scale,
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

		var t_next: float = 0.0
		var new_p: Vector2 = old_p
		if str(pr.get("curve_mode", "")) == "overhead_uturn":
			# Antamina behind-target arc (Owner 2026-11-26): launches forward in front of Tapion,
			# curves smoothly UP OVER Tapion's head, then dives back to strike the enemy behind him!
			var lf: float = float(pr.get("launch_facing", 1.0))
			var c_orig: Vector2 = pr.get("caster_origin", start_p) as Vector2
			var c_sc: float = float(pr.get("caster_scale", 1.0))
			var p0: Vector2 = start_p
			var p1: Vector2 = p0 + Vector2(lf * (185.0 * c_sc), -80.0 * c_sc)
			var apex_y: float = minf(c_orig.y - 235.0 * c_sc, minf(p0.y - 145.0 * c_sc, end_p.y - 115.0 * c_sc))
			var p2: Vector2 = Vector2(c_orig.x - lf * (125.0 * c_sc), apex_y)
			var p3: Vector2 = end_p
			var est_len: float = maxf(180.0, (p0.distance_to(p1) + p1.distance_to(p2) + p2.distance_to(p3)) * 0.78)
			t_next = minf(1.0, float(pr.get("t_prog", 0.0)) + step_dist / est_len)
			pr["t_prog"] = t_next
			var u: float = 1.0 - t_next
			new_p = (u * u * u) * p0 + (3.0 * u * u * t_next) * p1 + (3.0 * u * t_next * t_next) * p2 + (t_next * t_next * t_next) * p3
		else:
			var chord: Vector2 = end_p - start_p
			var chord_len: float = maxf(48.0, chord.length())
			var chord_dir: Vector2 = chord / chord_len
			var perp: Vector2 = Vector2(-chord_dir.y, chord_dir.x)
			var arc_sign: float = float(pr.get("arc_sign", 0.0))
			var arc_amp: float = minf(float(pr.get("arc_amp", 0.0)), chord_len * 0.26)
			var ctrl_p: Vector2 = (start_p + end_p) * 0.5 + perp * (arc_sign * arc_amp)

			t_next = minf(1.0, float(pr.get("t_prog", 0.0)) + step_dist / maxf(64.0, chord_len * (1.05 if absf(arc_amp) > 1.0 else 1.0)))
			pr["t_prog"] = t_next
			var u: float = 1.0 - t_next
			new_p = (u * u) * start_p + (2.0 * u * t_next) * ctrl_p + (t_next * t_next) * end_p
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
				# Kentaima hit applies 5s `Kentai` green-burn debuff + overhead icon!
				if net_act == "kentaima" and _is_slot_alive(tgt) and fm.has_method(&"apply_kentai_debuff_to_slot"):
					fm.call(&"apply_kentai_debuff_to_slot", tgt, KENTAIMA_DEBUFF_DURATION_S)
			impact_p = _get_slot_feet_world(tgt) if impact_anchor == "ground" else end_p
		elif not has_tgt and fm_active:
			for s in fm.call(&"_get_combat_slots"):
				if not _is_slot_alive(s):
					continue
				if fm.has_method(&"can_attack_slot") and not bool(fm.call(&"can_attack_slot", s)):
					continue
				var sc_pos: Vector2 = fm.call(&"_get_slot_core_pos", s)
				if new_p.distance_to(sc_pos) <= maxf(76.0, step_dist * 0.6):
					var dmg_p2 := float(pr["damage"])
					var is_remote_p2: bool = bool(fm.call(&"_emit_slot_combat_action", net_act, s, global_position, dmg_p2, 0.45))
					if not (bool(fm.get("network_authoritative")) and is_remote_p2):
						fm.call(&"apply_damage_to_slot", s, dmg_p2, 28.0, sc_pos, "skill", false, dir_v)
					if net_act == "kentaima" and _is_slot_alive(s) and fm.has_method(&"apply_kentai_debuff_to_slot"):
						fm.call(&"apply_kentai_debuff_to_slot", s, KENTAIMA_DEBUFF_DURATION_S)
					hit_now = true
					impact_p = _get_slot_feet_world(s) if impact_anchor == "ground" else sc_pos
					break

		if hit_now or t_next >= 1.0 or float(pr["age_s"]) >= float(pr["max_age_s"]):
			_spawn_oneshot_fx(pr["impact_clip"] as StringName, impact_p, facing_sign, impact_anchor)
			node.queue_free()
			_active_projectiles.remove_at(i)


func _get_mahasenko_hand_pos(is_air_m: bool, facing_sign: float, sc: float) -> Vector2:
	var off := MAHASENKO_AIR_HAND_OFFSET if is_air_m else MAHASENKO_GND_HAND_OFFSET
	return global_position + Vector2(off.x * facing_sign * sc, off.y * sc)


func _launch_single_mahasenko_bolt(bolt_spec: Dictionary, sc: float) -> void:
	var is_air_m := bool(bolt_spec.get("is_air", false))
	var arc_sign := float(bolt_spec.get("arc_sign", -1.0))
	var tgt_m: Dictionary = _resolve_active_target(true)
	if not _is_slot_alive(tgt_m):
		tgt_m = bolt_spec.get("target", {})
	if _is_slot_alive(tgt_m):
		_face_toward_x(_get_slot_core_world(tgt_m).x)
	var facing_sign := -1.0 if scale.x < 0.0 else 1.0
	var hand_pos := _get_mahasenko_hand_pos(is_air_m, facing_sign, sc)
	var aim_dir := Vector2(0.76 * facing_sign, 0.65).normalized() if is_air_m else Vector2(facing_sign, 0.0)
	if _is_slot_alive(tgt_m):
		var dv_m := _get_slot_core_world(tgt_m) - hand_pos
		if dv_m.length() > 4.0:
			aim_dir = dv_m.normalized()
	var muzzle_pos := hand_pos + aim_dir * (MAHASENKO_HAND_FX_CLEARANCE_PX * sc)
	_spawn_oneshot_fx(&"mahasenko_hand_fx", muzzle_pos, facing_sign, "center", 1.0, aim_dir)
	var beam_clip: StringName = &"mahasenko_beam_air_fx" if is_air_m else &"mahasenko_beam_h_fx"
	var base_ang := MAHA_BEAM_AIR_BASE_RAD if is_air_m else 0.0
	var anchor_m := "center" if is_air_m else "muzzle_left"
	var b_start := hand_pos + (aim_dir * (30.0 * sc) if is_air_m else aim_dir * (6.0 * sc))
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
		arc_sign,
		56.0,
		base_ang,
		anchor_m
	)


func _step_pending_mahasenko_bolts(delta: float, anim: String, sc: float) -> void:
	if _pending_mahasenko_bolts.is_empty():
		return
	for bi in range(_pending_mahasenko_bolts.size() - 1, -1, -1):
		var b: Dictionary = _pending_mahasenko_bolts[bi]
		b["delay_s"] = float(b.get("delay_s", 0.0)) - delta
		if float(b["delay_s"]) <= 0.0:
			_pending_mahasenko_bolts.remove_at(bi)
			_launch_single_mahasenko_bolt(b, sc)
	# Hold final outstretched hand pose cleanly until all 4 Mahasenko bolts have launched!
	if not _pending_mahasenko_bolts.is_empty() and sprite != null and (anim == "mahasenko_ground" or anim == "mahasenko_air"):
		var hold_f := 1 if anim == "mahasenko_air" else 2
		if sprite.frame >= hold_f:
			sprite.set_frame_and_progress(hold_f, 0.0)


func _fire_one_antamina_shot(sc: float) -> void:
	var tgt := _resolve_active_target(true)
	# NEVER rotate Tapion during Antamina charge/firing (Owner 2026-11-26):
	# keep initial locked facing; if enemy moved behind Tapion, beam shoots forward then arcs UP OVER Tapion's head!
	var facing_sign := _antamina_locked_facing_sign
	scale = Vector2(facing_sign * sc, sc)
	var hand_pos := global_position + Vector2(ANTAMINA_HAND_OFFSET.x * facing_sign * sc, ANTAMINA_HAND_OFFSET.y * sc)
	var fwd_dir := Vector2(facing_sign, 0.0)
	var aim_dir := fwd_dir
	var curve_mode := ""
	if _is_slot_alive(tgt):
		var tgt_core := _get_slot_core_world(tgt)
		var rel_x := (tgt_core.x - global_position.x) * facing_sign
		if rel_x < -16.0:
			curve_mode = "overhead_uturn"
			aim_dir = fwd_dir
		else:
			var dv := tgt_core - hand_pos
			if dv.length() > 4.0:
				aim_dir = dv.normalized()
	# Advance consistent 0->1->2 firing stance with crisp white/yellow directional light reflection per shot (ZERO pose flipping!)
	_antamina_body_loop_idx = posmod(_antamina_shots_fired - 1, 3)
	if sprite != null and String(sprite.animation) == "antamina_combo":
		sprite.set_frame_and_progress(6 + _antamina_body_loop_idx, 0.0)
		if not sprite.is_playing():
			sprite.play(&"antamina_combo")
	# 1) Hand muzzle burst = reverse antamina_stream_fx (4 -> 0) right at Tapion's hand!
	_spawn_oneshot_fx(&"antamina_stream_rev_fx", hand_pos, facing_sign, "muzzle_left", 1.0, aim_dir)
	# 2) Rapid flying Antamina beam @ 4000 px/s -> antamina_impact_fx (100/110/120ms)!
	var beam_start := hand_pos + aim_dir * (16.0 * sc)
	_spawn_homing_projectile(
		&"antamina_stream_fx",
		&"antamina_impact_fx",
		"ground",
		beam_start,
		tgt,
		aim_dir,
		ANTAMINA_SPEED_PX_S,
		_antamina_shot_dmg,
		"antamina",
		0.0,
		0.0,
		0.0,
		"muzzle_left",
		1.0,
		curve_mode,
		facing_sign,
		global_position,
		sc
	)


func _update_antamina_charge_and_fire(delta: float, anim: String, sc: float) -> void:
	if _antamina_phase.is_empty():
		_update_antamina_charge_fx_visibility()
		return
	if anim != "antamina_combo":
		_clear_antamina_state()
		return
	# Enforce locked facing throughout entire Antamina (charging -> firing -> ending)!
	scale = Vector2(_antamina_locked_facing_sign * sc, sc)
	var arena_lock := _find_arena_node()
	if arena_lock != null:
		arena_lock.set("player_facing_left", _antamina_locked_facing_sign < 0.0)
	var tgt := _resolve_active_target(true)

	# Phase 1: 2.0s Charge (`#0..#2` arm raise -> smooth orb-free `#3..#5` body loop + independent 60ms `antamina_charge_orb_fx`!)
	if _antamina_phase == "charging":
		_antamina_charge_elapsed_s += delta
		if _antamina_charge_elapsed_s < ANTAMINA_CHARGE_S:
			if sprite != null:
				var f_idx := 0
				if _antamina_charge_elapsed_s < 0.08:
					f_idx = 0
				elif _antamina_charge_elapsed_s < 0.16:
					f_idx = 1
				elif _antamina_charge_elapsed_s < ANTAMINA_PREP_S:
					f_idx = 2
				else:
					var cyc := int(floor((_antamina_charge_elapsed_s - ANTAMINA_PREP_S) / ANTAMINA_BODY_LOOP_STEP_S)) % 3
					f_idx = 3 + cyc
				sprite.set_frame_and_progress(f_idx, 0.0)
				if not sprite.is_playing():
					sprite.play(&"antamina_combo")
			_update_antamina_charge_fx_visibility()
			return

		# 2.0s Charge COMPLETE! Hide detached charge orb & check if target has 5 stacks of "Ấn ngục" (Suy yếu)!
		_antamina_charging = false
		_antamina_shots_total = ANTAMINA_BASE_SHOTS
		_antamina_shot_dmg = ANTAMINA_BASE_DMG
		_antamina_used_weakened = false
		_antamina_weakened_slot = {}
		if _is_slot_alive(tgt) and int(tgt.get("an_nguc_stacks", 0)) >= 5:
			_antamina_shots_total = ANTAMINA_WEAKENED_SHOTS
			_antamina_shot_dmg = ANTAMINA_WEAKENED_DMG
			_antamina_used_weakened = true
			_antamina_weakened_slot = tgt
		_antamina_phase = "firing"
		_antamina_shots_fired = 1
		_antamina_shot_timer_s = 0.0
		_skill_fx_fired_for_cast = true
		_update_antamina_charge_fx_visibility()
		_fire_one_antamina_shot(sc)
		return

	# Phase 2: Keep smooth 0->1->2 stance loop with white/yellow light reflection pulsing per shot (`#6..#8` <-> `#3..#5`, ZERO pose flip)!
	if _antamina_phase == "firing":
		_update_antamina_charge_fx_visibility()
		_antamina_shot_timer_s += delta
		if _antamina_shots_fired < _antamina_shots_total:
			if _antamina_shot_timer_s >= ANTAMINA_SHOT_INTERVAL_S:
				_antamina_shot_timer_s -= ANTAMINA_SHOT_INTERVAL_S
				_antamina_shots_fired += 1
				_fire_one_antamina_shot(sc)
			elif sprite != null:
				# Same pose index `_antamina_body_loop_idx` (0/1/2): bright white/yellow lit on launch -> matching clean pose between shots!
				var loop_f := (6 + _antamina_body_loop_idx) if _antamina_shot_timer_s < (ANTAMINA_SHOT_INTERVAL_S * 0.62) else (3 + _antamina_body_loop_idx)
				sprite.set_frame_and_progress(loop_f, 0.0)
				if not sprite.is_playing():
					sprite.play(&"antamina_combo")
			return

		# Wait for final shot's light flash hold, then consume 5 stacks (if Weakened) and play `#9..#10` end recovery!
		if _antamina_shot_timer_s < ANTAMINA_SHOT_INTERVAL_S:
			if sprite != null:
				var end_flash_f := (6 + _antamina_body_loop_idx) if _antamina_shot_timer_s < (ANTAMINA_SHOT_INTERVAL_S * 0.62) else (3 + _antamina_body_loop_idx)
				sprite.set_frame_and_progress(end_flash_f, 0.0)
				if not sprite.is_playing():
					sprite.play(&"antamina_combo")
			return

		if _antamina_used_weakened and _is_slot_alive(_antamina_weakened_slot):
			var arena := _find_arena_node()
			var fm = arena.get("field_manager") if arena != null else null
			if fm != null and fm.has_method(&"consume_an_nguc_weakened"):
				fm.call(&"consume_an_nguc_weakened", _antamina_weakened_slot)
		_antamina_phase = "ending"
		if sprite != null:
			sprite.set_frame_and_progress(9, 0.0)
			sprite.play(&"antamina_combo")
		return

	# Phase 3: End recovery frames (`#9 -> #10 -> idle_combat`)
	if _antamina_phase == "ending":
		_update_antamina_charge_fx_visibility()
		if sprite == null or not sprite.is_playing() or String(sprite.animation) != "antamina_combo":
			_clear_antamina_state()


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
			var tgt: Dictionary = {}
			if fm_active:
				tgt = fm.call(&"_resolve_player_attack_target", false)
				if not _is_slot_alive(tgt):
					var cand: Dictionary = _resolve_active_target(false)
					if _is_slot_alive(cand) and _get_slot_core_world(cand).distance_to(global_position + Vector2(0.0, -64.0 * sc)) <= 240.0 * sc:
						tgt = cand
			if fm_active and _is_slot_alive(tgt):
				_atk10_stunned_slot = tgt
				fm.call(&"apply_hard_stun_to_slot", tgt, 0.22)
			var want_stage := 2 if f >= 5 else 1
			if _atk10_fx_stage < want_stage:
				_atk10_fx_stage = want_stage
				var fx_pos := _get_slot_feet_world(tgt) if _is_slot_alive(tgt) else (global_position + Vector2(34.0 * facing_sign * sc, 0.0))
				_spawn_oneshot_fx(&"atk10_impact_fx", fx_pos, facing_sign, "ground", 1.0)
	else:
		if _atk10_fx_stage > 0:
			_atk10_fx_stage = 0
		if _is_slot_alive(_atk10_stunned_slot):
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

	# 2. Sequential 4-bolt Mahasenko trailing launcher
	_step_pending_mahasenko_bolts(delta, anim, sc)

	# 3. Antamina 2.0s charge (#0..#6) -> 5/7-shot rapid barrage loop (#7 @ 4000px/s) -> recovery (#8..#9)
	_update_antamina_charge_and_fire(delta, anim, sc)

	# 4. Kentaima target-locked crescent wave @ 2500px/s -> 70% circular kentaima_impact_fx + 5s Kentai burn!
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

	# 5. Mahasenko Ground/Air: 4 sequential alternating bolts (left -> right -> left -> right, trailing 30px apart) from fingertip point!
	elif (anim == "mahasenko_ground" or anim == "mahasenko_air") and sprite.is_playing():
		var is_air_m := (anim == "mahasenko_air")
		var trig_f := 1 if is_air_m else 2
		if sprite.frame >= trig_f and not _skill_fx_fired_for_cast:
			_skill_fx_fired_for_cast = true
			var tgt_m := _resolve_active_target(true)
			# Shot 0 fires immediately curving LEFT (-1.0); shots 1..3 trail 30px apart alternating RIGHT -> LEFT -> RIGHT!
			_launch_single_mahasenko_bolt({"is_air": is_air_m, "arc_sign": -1.0, "target": tgt_m}, sc)
			for k in range(1, MAHASENKO_BOLT_COUNT):
				var a_sign := -1.0 if (k % 2 == 0) else 1.0
				_pending_mahasenko_bolts.append({
					"delay_s": float(k) * MAHASENKO_BOLT_TRAIL_DELAY_S,
					"is_air": is_air_m,
					"arc_sign": a_sign,
					"target": tgt_m,
				})

	# 6. Bukadai teleport blitz onto locked target -> bukadai_sphere_fx + 2.0s hard stun + proc Ấn ngục (+1 stack if Kentai active)!
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
				# If target is afflicted by Kentai (5s), Bukadai procs +1 stack of "Ấn ngục" (5 stacks = Suy yếu)!
				if _is_slot_alive(tgt_b2) and fm.has_method(&"try_proc_an_nguc_on_slot"):
					fm.call(&"try_proc_an_nguc_on_slot", tgt_b2)
			_spawn_oneshot_fx(&"bukadai_sphere_fx", hit_core, -1.0 if scale.x < 0.0 else 1.0, "center")
	else:
		if anim not in ["kentaima_cast", "mahasenko_ground", "mahasenko_air", "antamina_fire", "antamina_combo", "bukadai_rush"]:
			_skill_fx_fired_for_cast = false
			_bukadai_dashed_for_cast = false
			if not _antamina_phase.is_empty():
				_clear_antamina_state()
