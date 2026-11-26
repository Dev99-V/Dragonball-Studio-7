class_name FieldCombatManager
extends Node
## Multi-monster Field Combat, Exact Body-Edge Interactions, Hit Feedback FX,
## Direct Touch Target Selection + Cycle Pointer, Auto-Approach Normal Attack,
## Stamina/Mini-Stun (3s), and 30%-Gated Weighted Dragon Ball Drops.

signal player_state_changed()
signal pointer_changed(kind: String)
signal combat_action_emitted(action_kind: String, target_id: String, target_kind: String, origin_pos: Vector2, facing_left: bool, damage: float)
signal player_pve_damage_emitted(damage: float, new_hp: float, alive: bool)
signal pk_mode_changed(enabled: bool)

const UtilityAIControllerScript := preload("res://scenes/UtilityAIController.gd")
const OverheadBarsDrawScript := preload("res://scenes/runtime/OverheadBarsDraw.gd")
const PowerupExplosionFrames := preload("res://assets/fx/powerup_explosion/powerup_explosion.tres")

const RESPAWN_MONSTER_DELAY_S := 12.0
const RESPAWN_PLAYER_DELAY_S := 3.0
const BOSS_DRUM_INITIAL_DELAY_S := 300.0 # 5 minutes after hero exists in map
const BOSS_DRUM_RESPAWN_DELAY_S := 1800.0 # 30 minutes cooldown after Boss Drum is defeated
const MINI_STUN_DURATION_S := 3.0
const STAMINA_PER_HIT := 20.0
const PLAYER_MAX_HP := 1500.0
const PLAYER_MAX_MANA := 100.0
const PLAYER_MAX_ARMOR := 100.0
const PLAYER_ARMOR_DMG_PER_HIT := 20.0
const PLAYER_ARMOR_BREAK_STUN_S := 3.0
const MONSTER_PROVOKED_DURATION_S := 5.0
const PLAYER_LIGHT_DMG := 200.0
const PLAYER_HEAVY_DMG := 320.0
const PLAYER_POWER_DMG := 400.0
const PLAYER_MANA_GAIN := 20.0
const ITEM_PICKUP_UNLOCK_S := 1.0
const ITEM_PICKUP_RANGE_PX := 140.0
const MELEE_STRIKE_EDGE_PX := 85.0
const HERO_MELEE_STRIKE_EDGE_PX := 20.0
const DRAGON_BALL_TOTAL_DROP_PCT := 30.0
const DOUBLE_TAP_WINDOW_S := 0.42
const Z_LAYER_FX := 68
const DRUM_SKILL_SPEED_PX_S := 1170.0
const MONSTER_SKILL_SPEED_PX_S := 780.0
const DEFAULT_EXPLOSION_SCALE := 0.68
const CLASH_EXPLOSION_SCALE := 0.58
const HIT_FLASH_BRIGHTNESS_MUL := 0.64
const HIT_FLASH_ALPHA_MUL := 0.80
const HIT_FLASH_CONTRAST_MUL := 0.60
const HIT_FLASH_BRIGHTNESS_BOOST := 1.40
const HIT_SHAKE_SCALE_MUL := 0.80
const POINTER_X_SHOW_DURATION_S := 0.75

# Gate: 30% total drop chance; once passed, roll star across original weights (30 / 20 / 10 / 5 / 2 / 0.5 / 0.1)
const DRAGON_BALL_DROP_TABLE := [
	{"ball": 7, "weight": 30.0},
	{"ball": 6, "weight": 20.0},
	{"ball": 5, "weight": 10.0},
	{"ball": 4, "weight": 5.0},
	{"ball": 3, "weight": 2.0},
	{"ball": 2, "weight": 0.5},
	{"ball": 1, "weight": 0.1},
]

const BOSS_DRUM_STATS := {"hp": 5000.0, "stamina": 200.0, "light_dmg": 120.0, "heavy_dmg": 120.0, "power_dmg": 220.0, "flying": false}

const BOSS_DROP_TABLE := [
	{"ball": 1, "weight": 8.0},
	{"ball": 2, "weight": 12.0},
	{"ball": 3, "weight": 18.0},
	{"ball": 4, "weight": 22.0},
	{"ball": 5, "weight": 20.0},
	{"ball": 6, "weight": 12.0},
	{"ball": 7, "weight": 8.0},
]

const MONSTER_STATS := {
	"chilopoda": {"hp": 1300.0, "light_dmg": 50.0, "heavy_dmg": 70.0, "power_dmg": 100.0, "flying": false},
	"spinosaurus": {"hp": 1500.0, "light_dmg": 50.0, "heavy_dmg": 70.0, "power_dmg": 100.0, "flying": false},
	"tasmanian_king_crab": {"hp": 1300.0, "light_dmg": 50.0, "heavy_dmg": 70.0, "power_dmg": 100.0, "flying": false},
	"t_rex": {"hp": 1800.0, "light_dmg": 50.0, "heavy_dmg": 70.0, "power_dmg": 100.0, "flying": false},
	"sarcosuchus": {"hp": 1500.0, "light_dmg": 50.0, "heavy_dmg": 70.0, "power_dmg": 100.0, "flying": false},
	"dilophosaurus": {"hp": 1300.0, "light_dmg": 50.0, "heavy_dmg": 70.0, "power_dmg": 100.0, "flying": false},
	"bat_chiroptera": {"hp": 900.0, "light_dmg": 70.0, "heavy_dmg": 70.0, "power_dmg": 100.0, "flying": true},
	"pteranodon": {"hp": 1000.0, "light_dmg": 70.0, "heavy_dmg": 70.0, "power_dmg": 100.0, "flying": true},
	"floating_camera": {"hp": 800.0, "light_dmg": 80.0, "heavy_dmg": 80.0, "power_dmg": 80.0, "flying": true},
}

const FLYING_ROTATION := ["bat_chiroptera", "pteranodon", "floating_camera"]

const SHIELD_BREAK_ICON_DURATION_S := 2.6

var arena: Node2D = null
var active: bool = false
var monsters_enabled: bool = true
var player_spawned: bool = false
var player_hp: float = PLAYER_MAX_HP
var player_max_hp: float = PLAYER_MAX_HP
var player_mana: float = 0.0
var player_max_mana: float = PLAYER_MAX_MANA
var player_infinite_mana: bool = false
var player_armor: float = PLAYER_MAX_ARMOR
var player_max_armor: float = PLAYER_MAX_ARMOR
var player_armor_broken_timer_s: float = 0.0
var player_shield_break_icon_timer_s: float = 0.0
var player_hard_stun_timer_s: float = 0.0
var player_dead: bool = false
var player_immortal: bool = false
var show_monster_ranges: bool = false
var player_respawn_timer_s: float = 0.0
var _player_melee_pending: bool = false
var _player_power_pending: bool = false
var _player_power_target: Dictionary = {}
var _player_combo_attack_info: Dictionary = {}
var _player_hit_frames_fired: Array[int] = []
var _player_gold_slash_pending: bool = false
var _base_lock_notice_cd_s: float = 0.0

# Phase 2 Son Goku & Tapion Active Skills & Independent FX Runtime
var _songoku_fx_frames: SpriteFrames = null
var _tapion_fx_frames: SpriteFrames = null
var _genki_fx_frames: SpriteFrames = null
var _hero_skill_projectiles: Array[Dictionary] = []   # Atomic bolts (23/25)
var _hero_kame_beams: Array[Dictionary] = []          # Kamehameha beams (31/32)
var _hero_flurry_hits_fired: Array[int] = []
var _hero_atomic_fired: bool = false
var _hero_atomic_air_down: bool = false
var _hero_atomic_mode: String = "ground_horiz"
var _hero_atomic_target: Dictionary = {}
var _hero_atomic_pending_bolts: Array[Dictionary] = []
var _hero_atomic_muzzle_flashes: Array[Dictionary] = []
var _last_atomic_fire_log: Array[Dictionary] = []
var _hero_kame_fired: bool = false
var _hero_kame_charging: bool = false
var _hero_kame_charge_elapsed_s: float = 0.0
var _hero_kame_mode: String = "ground_horiz"
var _hero_kame_target: Dictionary = {}
var _hero_barrier_burst_s: float = 0.0

# Son Goku Genki (Spirit Bomb) runtime constants & state (Owner 2026-11-26)
const GENKI_BASE_DAMAGE: float = 400.0
const GENKI_PER_PLAYER_BONUS: float = 5.0
const GENKI_MAX_CONTRIB_PLAYERS: int = 20
const GENKI_AOE_RADIUS_PX: float = 700.0
const GENKI_CHARGE_DURATION_S: float = 5.0
const GENKI_THROW_DURATION_S: float = 0.48
const GENKI_THROW_WINDUP_S: float = 0.12
const GENKI_THROW_RELEASE_S: float = 0.14
const GENKI_THROW_ARC_END_S: float = 0.28
const GENKI_MIN_LAND_OFFSET_PX: float = 50.0
const GENKI_MAX_LAND_OFFSET_PX: float = 200.0
const GENKI_DEFAULT_LAND_OFFSET_PX: float = 188.0
const GENKI_ORB_FLIGHT_SPEED_PX_S: float = 1064.0 # +40% faster flight speed (760 -> 1064 px/s, Owner 2026-11-26)
const GENKI_CHARGE_FRAME_S: float = 0.12          # 120ms/frame charge & body flutter loop
const GENKI_IMPACT_FRAME_S: float = 0.10          # 100ms/frame ground impact (Genki/9..12)
const GENKI_EXPLODE_FRAME_S: float = 0.12         # 120ms/frame explosion climax (Genki/13..16)
var _genki_phase: String = "" # "", "charging", "throwing"
var _genki_elapsed_s: float = 0.0
var _genki_throw_released: bool = false
var _genki_locked_facing_x: float = 1.0
var _genki_contrib_count: int = 0
var _genki_wisp_spawn_accum_s: float = 0.0
var _genki_cc_notice_cd_s: float = 0.0
var _genki_ambient_flash_s: float = 0.0
var _genki_ambient_flash_dur_s: float = 0.62
var _genki_ambient_flash_pos: Vector2 = Vector2.ZERO
var _genki_wisps: Array[Dictionary] = []
var _genki_projectiles: Array[Dictionary] = []
var _genki_explosions: Array[Dictionary] = []

var slots: Array[Dictionary] = []
var boss_slot: Dictionary = {}
var remote_player_slots: Dictionary = {}
var local_display_name: String = ""
var network_authoritative: bool = false
var _local_hp_grace_s: float = 0.0
var _local_mana_grace_s: float = 0.0
var _last_srv_local_hp: float = -1.0
var _last_srv_local_mana: float = -1.0
var _slot_local_hit_grace: Dictionary = {}
var boss_has_spawned_once: bool = false
var boss_spawn_timer_s: float = BOSS_DRUM_INITIAL_DELAY_S
var boss_respawn_timer_s: float = 0.0
var _boss_teleport_chase_cd_s: float = 0.0
var homing_projectiles: Array[Dictionary] = []
var _flying_rotation_idx: int = 0
var _sim_time_s: float = 0.0

var pointer_kind: String = "enemy"
var pointer_slot_id: String = ""
var pointer_item_node: Node2D = null
var pointer_pulse_s: float = 0.0
var pointer_x_anim_s: float = 0.28
var pointer_x_anim_dur_s: float = 0.28
var pointer_x_visible_s: float = 0.0
var pointer_x_double_tap_pulse_s: float = 0.0
var _last_tap_kind: String = ""
var _last_tap_slot_id: String = ""
var _last_tap_item: Node2D = null
var _last_tap_time_s: float = -99.0

const TAPION_SKILL_MAX_RANGE_PX := 1175.0 # Exact K70E 2460x1080 red-line horizontal cast radius (AGENTS.md Điều 7.7)

var pk_tan_sat_enabled: bool = false
var pk_special_mode_override: bool = false

var auto_approach_active: bool = false
var _auto_approach_kind: String = ""
var _auto_approach_slot_id: String = ""
var _auto_approach_item: Node2D = null
var _auto_approach_skill_action: String = ""
var _auto_approach_range_px: float = 0.0
var _auto_approach_timeout_s: float = 0.0

# Auto-Battle Flight KI hysteresis (Owner v10.2):
# When Flight KI hits 0 -> lock onto ground targets until KI recovers to full -> auto switch back to flying!
var _auto_ki_ground_lock: bool = false
var _auto_return_to_air_on_ki_full: bool = false

const FLURRY_KICK_LUNGE_SPEED_PX_S: float = 260.0
const FLURRY_KICK_RANGE_FWD_PX: float = 215.0
const FLURRY_KICK_RANGE_BACK_PX: float = 55.0
const FLURRY_KICK_RANGE_V_PX: float = 160.0

var player_hit_flash_s: float = 0.0
var player_hit_shake_s: float = 0.0
var hit_impacts: Array[Dictionary] = []
var floating_texts: Array[Dictionary] = []
var _explosion_nodes: Array[AnimatedSprite2D] = []
var _fx_frames_cache: Dictionary = {}


func setup(owner_arena: Node2D) -> void:
	arena = owner_arena


func _get_combat_slots() -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for s in slots:
		out.append(s)
	if not boss_slot.is_empty():
		out.append(boss_slot)
	for rp_val in remote_player_slots.values():
		if rp_val is Dictionary:
			out.append(rp_val)
	return out


static func _get_slot_stats(slot: Dictionary) -> Dictionary:
	if bool(slot.get("is_boss", false)):
		return BOSS_DRUM_STATS
	return MONSTER_STATS.get(str(slot.get("character_id", "")), {})


func reset_hero_combat_state(clear_marks: bool = true) -> void:
	## Resets all hero-scoped cast/skill/combat state cleanly on hero swap, hide, or map reset.
	_player_melee_pending = false
	_player_power_pending = false
	_player_power_target = {}
	_player_combo_attack_info = {}
	_player_hit_frames_fired.clear()
	_player_gold_slash_pending = false
	player_hard_stun_timer_s = 0.0
	player_armor_broken_timer_s = 0.0
	player_shield_break_icon_timer_s = 0.0
	_hero_skill_projectiles.clear()
	_hero_kame_beams.clear()
	_hero_flurry_hits_fired.clear()
	_hero_atomic_fired = false
	_hero_atomic_air_down = false
	_hero_atomic_mode = "ground_horiz"
	_hero_atomic_target = {}
	_hero_atomic_pending_bolts.clear()
	_hero_atomic_muzzle_flashes.clear()
	_hero_kame_fired = false
	_hero_kame_charging = false
	_hero_kame_charge_elapsed_s = 0.0
	_hero_kame_mode = "ground_horiz"
	_hero_kame_target = {}
	_hero_barrier_burst_s = 0.0
	_genki_phase = ""
	_genki_elapsed_s = 0.0
	_genki_throw_released = false
	_genki_contrib_count = 0
	_genki_wisp_spawn_accum_s = 0.0
	_genki_cc_notice_cd_s = 0.0
	_genki_ambient_flash_s = 0.0
	_genki_wisps.clear()
	_genki_projectiles.clear()
	_genki_explosions.clear()
	cancel_auto_approach()
	if clear_marks:
		clear_all_tapion_marks()


func clear_all() -> void:
	active = false
	reset_hero_combat_state(false)
	for s in _get_combat_slots():
		var n := s.get("node") as Node2D
		if n != null and is_instance_valid(n):
			n.queue_free()
	slots.clear()
	boss_slot = {}
	remote_player_slots.clear()
	_local_hp_grace_s = 0.0
	_local_mana_grace_s = 0.0
	_last_srv_local_hp = -1.0
	_last_srv_local_mana = -1.0
	_slot_local_hit_grace.clear()
	boss_has_spawned_once = false
	boss_spawn_timer_s = BOSS_DRUM_INITIAL_DELAY_S
	boss_respawn_timer_s = 0.0
	_boss_teleport_chase_cd_s = 0.0
	for pr in homing_projectiles:
		var sp := pr.get("sprite") as Node2D
		if sp != null and is_instance_valid(sp):
			sp.queue_free()
	homing_projectiles.clear()
	for ex in _explosion_nodes:
		if ex != null and is_instance_valid(ex):
			ex.queue_free()
	_explosion_nodes.clear()
	hit_impacts.clear()
	floating_texts.clear()
	player_hit_flash_s = 0.0
	player_hit_shake_s = 0.0
	pointer_pulse_s = 0.0
	pointer_x_anim_s = pointer_x_anim_dur_s
	pointer_x_visible_s = 0.0
	pointer_x_double_tap_pulse_s = 0.0
	_last_tap_kind = ""
	_last_tap_slot_id = ""
	_last_tap_item = null
	_last_tap_time_s = -99.0
	pointer_slot_id = ""
	pointer_item_node = null
	pointer_kind = "enemy"


func cancel_auto_approach() -> void:
	auto_approach_active = false
	_auto_approach_kind = ""
	_auto_approach_slot_id = ""
	_auto_approach_item = null
	_auto_approach_skill_action = ""
	_auto_approach_range_px = 0.0
	_auto_approach_timeout_s = 0.0


func set_pk_tan_sat_enabled(enabled: bool) -> void:
	if pk_tan_sat_enabled == enabled:
		return
	pk_tan_sat_enabled = enabled
	if not enabled and auto_approach_active and not _auto_approach_slot_id.is_empty():
		var ap_slot := _find_slot_by_id(_auto_approach_slot_id)
		if not ap_slot.is_empty() and not can_attack_slot(ap_slot):
			cancel_auto_approach()
	refresh_pointer_valid()
	pk_mode_changed.emit(pk_tan_sat_enabled)
	player_state_changed.emit()
	if arena != null:
		arena.queue_redraw()


func set_pk_special_mode_override(enabled: bool) -> void:
	if pk_special_mode_override == enabled:
		return
	pk_special_mode_override = enabled
	refresh_pointer_valid()
	player_state_changed.emit()
	if arena != null:
		arena.queue_redraw()


func is_remote_player_hostile(slot: Dictionary) -> bool:
	if slot.is_empty() or not bool(slot.get("is_remote_player", false)):
		return false
	return pk_tan_sat_enabled or pk_special_mode_override or bool(slot.get("pk_tan_sat", false))


func can_attack_slot(slot: Dictionary) -> bool:
	if slot.is_empty() or not bool(slot.get("alive", false)) or not is_instance_valid(slot.get("node")):
		return false
	if bool(slot.get("is_remote_player", false)):
		return is_remote_player_hostile(slot)
	return true


func is_target_in_tapion_skill_range(tgt: Dictionary, range_px: float = TAPION_SKILL_MAX_RANGE_PX) -> bool:
	if tgt.is_empty() or not can_attack_slot(tgt) or arena == null or arena.player_node == null:
		return false
	return absf(_get_slot_core_pos(tgt).x - _get_player_core_pos().x) <= range_px


func start_skill_auto_approach(action_name: String, tgt: Dictionary, range_px: float = TAPION_SKILL_MAX_RANGE_PX) -> void:
	if tgt.is_empty() or not can_attack_slot(tgt) or arena == null or arena.player_node == null:
		return
	var sid := str(tgt.get("id", ""))
	var already_same := auto_approach_active and _auto_approach_kind == "skill" and _auto_approach_slot_id == sid and _auto_approach_skill_action == action_name
	auto_approach_active = true
	_auto_approach_kind = "skill"
	_auto_approach_slot_id = sid
	_auto_approach_item = null
	_auto_approach_skill_action = action_name
	_auto_approach_range_px = range_px
	_auto_approach_timeout_s = 10.0
	if not already_same:
		floating_texts.append({
			"pos": arena.player_node.position + Vector2(0.0, -142.0),
			"text": "Ngoài tầm — tiến lại gần!",
			"color": Color(1.0, 0.86, 0.34, 1.0),
			"elapsed_s": 0.0,
			"duration_s": 0.85,
		})


func reset_auto_battle_ki_lock() -> void:
	_auto_ki_ground_lock = false
	_auto_return_to_air_on_ki_full = false


func start_field(spawn_player_immediately: bool = false, spawn_monsters: bool = true) -> void:
	clear_all()
	reset_auto_battle_ki_lock()
	active = true
	monsters_enabled = spawn_monsters
	player_spawned = spawn_player_immediately
	player_hp = PLAYER_MAX_HP
	player_max_hp = PLAYER_MAX_HP
	player_mana = 0.0
	player_max_mana = PLAYER_MAX_MANA
	player_armor = PLAYER_MAX_ARMOR
	player_max_armor = PLAYER_MAX_ARMOR
	player_armor_broken_timer_s = 0.0
	player_shield_break_icon_timer_s = 0.0
	player_hard_stun_timer_s = 0.0
	_hero_skill_projectiles.clear()
	_hero_kame_beams.clear()
	_hero_flurry_hits_fired.clear()
	_hero_atomic_fired = false
	_hero_atomic_mode = "ground_horiz"
	_hero_atomic_target = {}
	_hero_atomic_pending_bolts.clear()
	_hero_atomic_muzzle_flashes.clear()
	_last_atomic_fire_log.clear()
	_hero_kame_fired = false
	_hero_kame_charging = false
	_hero_kame_charge_elapsed_s = 0.0
	_hero_kame_target = {}
	_hero_barrier_burst_s = 0.0
	_genki_phase = ""
	_genki_elapsed_s = 0.0
	_genki_throw_released = false
	_genki_contrib_count = 0
	_genki_wisp_spawn_accum_s = 0.0
	_genki_cc_notice_cd_s = 0.0
	_genki_ambient_flash_s = 0.0
	_genki_wisps.clear()
	_genki_projectiles.clear()
	_genki_explosions.clear()
	if arena != null and arena.player_node != null and _is_hero_songoku_node(arena.player_node):
		player_max_mana = 100.0
		player_mana = 100.0
	player_dead = false
	player_respawn_timer_s = 0.0
	_flying_rotation_idx = 0

	if monsters_enabled:
		# 3 main-plateau slots and 1 ground monster on each of the 4 lower plateaus.
		var ground_defs := [
			{"id": "g0", "cid": "chilopoda", "x": 330.0, "zmin": -103.0, "zmax": 766.0},
			{"id": "g1", "cid": "spinosaurus", "x": 1160.0, "zmin": 730.0, "zmax": 1590.0},
			{"id": "g2", "cid": "tasmanian_king_crab", "x": 1990.0, "zmin": 1560.0, "zmax": 2430.0},
			{"id": "g3", "cid": "t_rex", "x": 3270.0, "zmin": 2900.0, "zmax": 3640.0},
			{"id": "g4", "cid": "sarcosuchus", "x": 4125.0, "zmin": 3750.0, "zmax": 4490.0},
			{"id": "g5", "cid": "dilophosaurus", "x": 5180.0, "zmin": 4790.0, "zmax": 5500.0},
			{"id": "g6", "cid": "spinosaurus", "x": 5960.0, "zmin": 5610.0, "zmax": 6310.0},
		]
		for gd in ground_defs:
			_create_and_spawn_slot(gd, false)

		# One flying monster above each ground slot and lower plateau.
		var flying_defs := [
			{"id": "f0", "cid": "bat_chiroptera", "x": 330.0, "y": 240.0, "zmin": -190.0, "zmax": 855.0},
			{"id": "f1", "cid": "pteranodon", "x": 1160.0, "y": 240.0, "zmin": 635.0, "zmax": 1685.0},
			{"id": "f2", "cid": "floating_camera", "x": 1990.0, "y": 240.0, "zmin": 1465.0, "zmax": 2515.0},
			{"id": "f3", "cid": "bat_chiroptera", "x": 3270.0, "y": 260.0, "zmin": 2745.0, "zmax": 3795.0},
			{"id": "f4", "cid": "pteranodon", "x": 4125.0, "y": 280.0, "zmin": 3600.0, "zmax": 4540.0},
			{"id": "f5", "cid": "floating_camera", "x": 5180.0, "y": 300.0, "zmin": 4740.0, "zmax": 5560.0},
			{"id": "f6", "cid": "bat_chiroptera", "x": 5960.0, "y": 320.0, "zmin": 5560.0, "zmax": 6360.0},
		]
		for fd in flying_defs:
			_create_and_spawn_slot(fd, true)

		_flying_rotation_idx = 1 # Continue Bat/Ptera/Camera rotation after 7 initial flying slots.
	refresh_pointer_valid()

	player_state_changed.emit()


func _create_and_spawn_slot(spec: Dictionary, is_flying: bool) -> void:
	var cid := str(spec["cid"])
	var slot := {
		"id": str(spec["id"]),
		"native_cid": cid,
		"character_id": cid,
		"is_flying": is_flying,
		"x_home": float(spec["x"]),
		"y_home": float(spec.get("y", arena.call("_ground_y_at", float(spec["x"])))),
		"zone_min_x": float(spec["zmin"]),
		"zone_max_x": float(spec["zmax"]),
		"respawn_toggle": false,
		"node": null,
		"alive": false,
		"hp": 1000.0,
		"max_hp": 1000.0,
		"stamina": 100.0,
		"max_stamina": 100.0,
		"stun_timer_s": 0.0,
		"hard_stun_timer_s": 0.0,
		"hit_anim_timer_s": 0.0,
		"respawn_timer_s": 0.0,
		"ko_hide_timer_s": 0.0,
		"cooldown_s": 0.0,
		"light_chain": 0,
		"action_clip": "",
		"action_timer_s": 0.0,
		"vy": 0.0,
		"scale_val": 1.75,
		"facing_left": true,
		"patrol_dir": 1 if (slots.size() % 2 == 0) else -1,
		"patrol_pause_s": 0.0,
		"power_released": false,
		"melee_hit_done": false,
		"has_heavy": false,
		"has_power_up": false,
		"light_clip": "attack_light",
		"locomotion_clip": "walk",
		"preserve_phase": false,
		"sideways_locked": false,
		"turn_boost_s": 0.0,
		"turn_elapsed_s": 0.0,
		"turn_duration_s": 0.0,
		"turn_prev_dir": 1,
		"turn_target_left": true,
		"turn_lock_s": 0.0,
		"has_turn_clip": false,
		"orbit_phase": float(slots.size()) * 1.35,
		"orbit_dir": 1.0 if (slots.size() % 2 == 0) else -1.0,
		"hit_flash_s": 0.0,
		"hit_shake_s": 0.0,
		"kentai_timer_s": 0.0,
		"an_nguc_stacks": 0,
		"_local_dead_time_s": -999.0,
		"combat_state": "peace",
		"aggro_target_id": "",
		"committed_target_id": "",
		"fled_attackers": [],
	}
	slots.append(slot)
	_spawn_slot_monster(slot, cid)


func _spawn_slot_monster(slot: Dictionary, cid: String) -> void:
	var old_n := slot.get("node") as Node2D
	if old_n != null and is_instance_valid(old_n):
		old_n.queue_free()
	var entry: Dictionary = arena.call("_find_character_entry_ro", cid)
	if entry.is_empty():
		return
	var prefab_path: String = str(arena.call("_resolve_prefab_path", entry))
	if prefab_path.is_empty() or not ResourceLoader.exists(prefab_path):
		return
	var packed := ResourceLoader.load(prefab_path) as PackedScene
	if packed == null:
		return
	var inst := packed.instantiate() as Node2D
	if inst == null:
		return
	var parent_layer: Node = arena.fighters_layer if arena.fighters_layer != null else arena
	parent_layer.add_child(inst)
	inst.name = "FieldMob_%s_%s" % [str(slot["id"]), cid]

	var is_boss := bool(slot.get("is_boss", false))
	var sc := float(slot.get("boss_scale", 2.5)) if is_boss else float(arena.call("_get_entry_default_scale", entry))
	var spawn_x := float(slot["x_home"])
	var spawn_y := float(slot["y_home"]) if bool(slot["is_flying"]) else float(arena.call("_ground_y_at", spawn_x))
	arena.call("_configure_fighter_instance", inst, spawn_x, spawn_y, true, sc)
	inst.z_index = int(arena.call("get_fighter_layer_z", cid, false))

	var caps: Dictionary = arena.call("_resolve_enemy_capabilities", entry, inst)
	slot["node"] = inst
	slot["character_id"] = cid
	var st: Dictionary = _get_slot_stats(slot)
	var max_hp := float(st.get("hp", 1300.0))
	var max_stam := float(st.get("stamina", 100.0))

	slot["alive"] = true
	slot["hp"] = max_hp
	slot["max_hp"] = max_hp
	slot["stamina"] = max_stam
	slot["max_stamina"] = max_stam
	slot["stun_timer_s"] = 0.0
	slot["hard_stun_timer_s"] = 0.0
	slot["shield_break_icon_timer_s"] = 0.0
	slot["hit_anim_timer_s"] = 0.0
	slot["respawn_timer_s"] = 0.0
	slot["ko_hide_timer_s"] = 0.0
	slot["cooldown_s"] = 0.25
	slot["light_chain"] = 0
	slot["action_clip"] = ""
	slot["action_timer_s"] = 0.0
	slot["vy"] = 0.0
	slot["scale_val"] = sc
	slot["facing_left"] = inst.scale.x < 0.0
	slot["power_released"] = false
	slot["melee_hit_done"] = false
	slot["teleport_relocated"] = false
	slot["has_heavy"] = bool(caps.get("has_heavy", false))
	slot["has_power_up"] = bool(caps.get("has_power_up", false))
	slot["light_clip"] = str(caps.get("light_clip", "attack_light"))
	slot["combat_state"] = "combat" if is_boss else "peace"
	slot["aggro_target_id"] = ""
	slot["committed_target_id"] = ""
	slot["fled_attackers"] = []
	slot["provoked_timer_s"] = 0.0
	slot["locomotion_clip"] = str(caps.get("locomotion_clip", "walk"))
	slot["preserve_phase"] = bool(caps.get("preserve_idle_walk_phase", false))
	slot["sideways_locked"] = bool(caps.get("sideways_locked", false))
	slot["has_turn_clip"] = bool(arena.call("_has_turn_clip", entry))
	slot["turn_lock_s"] = 0.0
	slot["hit_flash_s"] = 0.0
	slot["hit_shake_s"] = 0.0
	slot["kentai_timer_s"] = 0.0
	slot["an_nguc_stacks"] = 0
	slot["_local_dead_time_s"] = -999.0
	if is_boss:
		inst.name = "FieldBoss_drum"
		inst.z_index = int(arena.Z_LAYER_BOSS)

	# Disable legacy horizontal prefab ProjectileFX & Drum internal orb in Field Mode so only 1 clean 360-degree projectile fires
	if inst.get("external_projectile_managed") != null:
		inst.set("external_projectile_managed", true)
	if inst.get("external_orb_managed") != null:
		inst.set("external_orb_managed", true)
	var pfx := inst.get_node_or_null("ProjectileFX") as Node2D
	if pfx != null:
		pfx.visible = false
		pfx.modulate = Color(1.0, 1.0, 1.0, 0.0)
		pfx.scale = Vector2.ZERO
	var ffx := inst.get_node_or_null("FireballFX") as AnimatedSprite2D
	if ffx != null:
		ffx.visible = false
		ffx.modulate = Color(1.0, 1.0, 1.0, 0.0)
		ffx.sprite_frames = null


func step(delta: float) -> void:
	if not active or delta <= 0.0:
		return
	_sim_time_s += delta
	if _local_hp_grace_s > 0.0:
		_local_hp_grace_s = maxf(0.0, _local_hp_grace_s - delta)
	if _local_mana_grace_s > 0.0:
		_local_mana_grace_s = maxf(0.0, _local_mana_grace_s - delta)
	for gkey in _slot_local_hit_grace.keys():
		var rem := float(_slot_local_hit_grace[gkey]) - delta
		if rem <= 0.0:
			_slot_local_hit_grace.erase(gkey)
		else:
			_slot_local_hit_grace[gkey] = rem

	# 1. Player respawn, auto-approach, & pending attack/power release
	if player_spawned and player_dead:
		cancel_auto_approach()
		player_respawn_timer_s = maxf(0.0, player_respawn_timer_s - delta)
		if player_respawn_timer_s <= 0.0:
			respawn_player_at_left()
	elif player_spawned and arena.player_node != null:
		if player_infinite_mana and player_mana < player_max_mana:
			player_mana = player_max_mana
		if player_shield_break_icon_timer_s > 0.0:
			player_shield_break_icon_timer_s = maxf(0.0, player_shield_break_icon_timer_s - delta)
		if player_armor_broken_timer_s > 0.0:
			player_armor_broken_timer_s = maxf(0.0, player_armor_broken_timer_s - delta)
			if player_armor_broken_timer_s <= 0.0:
				player_armor = player_max_armor
				player_state_changed.emit()
		if player_hard_stun_timer_s > 0.0:
			player_hard_stun_timer_s = maxf(0.0, player_hard_stun_timer_s - delta)
			var pspr_st := arena.player_node.get_node_or_null("Sprite") as AnimatedSprite2D
			if pspr_st != null and pspr_st.sprite_frames != null and pspr_st.sprite_frames.has_animation(&"hit"):
				if String(pspr_st.animation) != "hit" or not pspr_st.is_playing():
					pspr_st.play(&"hit")
		_step_hero_phase2_skills(delta)
		_step_auto_approach(delta)
		_step_player_combat_hooks()

	# 2. Step Boss Map schedule + all active monster slots + Boss Drum
	for s_sb in _get_combat_slots():
		var sb_t: float = float(s_sb.get("shield_break_icon_timer_s", 0.0))
		if sb_t > 0.0:
			s_sb["shield_break_icon_timer_s"] = maxf(0.0, sb_t - delta)
		var kt_t: float = float(s_sb.get("kentai_timer_s", 0.0))
		if kt_t > 0.0:
			s_sb["kentai_timer_s"] = maxf(0.0, kt_t - delta)
	_step_boss_spawn_schedule(delta)
	for slot in slots:
		_step_slot(slot, delta)
	if not boss_slot.is_empty():
		_step_slot(boss_slot, delta)

	# 3. Step homing projectiles + Son Goku Phase 2 Atomic bolts & Kamehameha beams
	_step_homing_projectiles(delta)
	_step_hero_skill_projectiles_and_beams(delta)

	# 4. Apply hit flashes, shakes, pointer fade & impact/text timers immediately after combat updates
	_step_hit_visuals(delta)

	# 5. Tick dropped item ages (for 1s pickup delay) & prune collected item nodes to avoid leak
	for i in range(arena._dropped_item_nodes.size() - 1, -1, -1):
		var item_n := arena._dropped_item_nodes[i] as Node2D
		if item_n == null or not is_instance_valid(item_n):
			arena._dropped_item_nodes.remove_at(i)
			continue
		if str(item_n.get("lifecycle_state")) == "collected":
			arena._dropped_item_nodes.remove_at(i)
			item_n.queue_free()
			continue
		var age := float(item_n.get_meta(&"drop_age_s", 0.0)) + delta
		item_n.set_meta(&"drop_age_s", age)

	refresh_pointer_valid()


func _step_boss_spawn_schedule(delta: float) -> void:
	if arena == null or not active or not monsters_enabled:
		return
	if not boss_slot.is_empty() and bool(boss_slot.get("alive", false)):
		boss_respawn_timer_s = 0.0
		return
	var hero_present := player_spawned and arena.player_node != null and is_instance_valid(arena.player_node)
	if not boss_has_spawned_once:
		if not hero_present:
			boss_spawn_timer_s = BOSS_DRUM_INITIAL_DELAY_S
			return
		if not player_dead:
			boss_spawn_timer_s = maxf(0.0, boss_spawn_timer_s - delta)
			if boss_spawn_timer_s <= 0.0:
				spawn_boss_drum()
		return
	if boss_respawn_timer_s > 0.0:
		boss_respawn_timer_s = maxf(0.0, boss_respawn_timer_s - delta)
	if boss_respawn_timer_s <= 0.0 and hero_present and not player_dead:
		spawn_boss_drum()


func _pick_random_boss_spawn_x(min_x: float, max_x: float) -> float:
	var lo := min_x + 40.0
	var hi := max_x - 40.0
	if hi <= lo:
		return (min_x + max_x) * 0.5
	return randf_range(lo, hi)


func set_player_infinite_mana(enabled: bool) -> void:
	player_infinite_mana = enabled
	if enabled:
		player_mana = player_max_mana
	player_state_changed.emit()


func spawn_boss_drum(forced_spawn_x: float = -999999.0) -> Dictionary:
	return spawn_boss("drum", forced_spawn_x)


func spawn_boss(boss_cid: String = "drum", forced_spawn_x: float = -999999.0) -> Dictionary:
	if arena == null:
		return {}
	var req_cid := boss_cid.strip_edges()
	if req_cid.is_empty():
		req_cid = "drum"
	var cur_map_id := str(arena.get("current_map_id")) if arena.get("current_map_id") != null else "rocky_plateau"
	if not boss_slot.is_empty() and bool(boss_slot.get("alive", false)) and is_instance_valid(boss_slot.get("node")):
		if str(boss_slot.get("character_id", "")) == req_cid and str(boss_slot.get("map_id", "")) == cur_map_id:
			# Never double-spawn identical live boss on same map; re-trigger entry teleport onto hero if desired.
			if player_spawned and not player_dead and arena.player_node != null:
				var existing_ai := boss_slot.get("ai") as UtilityAIController
				if existing_ai != null:
					existing_ai.set_meta(&"drum_engaged", true)
					existing_ai.set_meta(&"drum_phase", "post_teleport_light")
				if req_cid == "drum":
					_start_slot_attack(boss_slot, "teleport", 0.0)
			return boss_slot

	var boss_entry: Dictionary = arena.call("_find_character_entry_ro", req_cid)
	if boss_entry.is_empty():
		return {}
	var default_boss_scale := 2.5 if req_cid == "drum" else float(arena.call("_get_entry_default_scale", boss_entry)) * 1.25
	var boss_bounds: Vector2 = arena.call("_get_fighter_walk_bounds_x", boss_entry, default_boss_scale)
	var spawn_x := forced_spawn_x
	if spawn_x < -900000.0:
		spawn_x = _pick_random_boss_spawn_x(boss_bounds.x, boss_bounds.y)
	else:
		spawn_x = clampf(spawn_x, boss_bounds.x, boss_bounds.y)

	var ai := UtilityAIControllerScript.new()
	if arena.stage_config is Dictionary and not (arena.stage_config as Dictionary).is_empty():
		ai.configure_from_stage(arena.stage_config)
	ai.reset_zone((boss_bounds.x + boss_bounds.y) * 0.5, boss_bounds.x, boss_bounds.y, true)

	# Free any previous dead/stale Boss node before replacing boss_slot (prevents node leak).
	var stale_boss_node := boss_slot.get("node") as Node2D
	if stale_boss_node != null and is_instance_valid(stale_boss_node):
		if stale_boss_node.get_parent() != null:
			stale_boss_node.get_parent().remove_child(stale_boss_node)
		stale_boss_node.queue_free()

	var boss_label := str(boss_entry.get("display_name", req_cid.capitalize()))
	if req_cid == "drum":
		boss_label = "Drum"
	boss_slot = {
		"id": "boss_%s" % req_cid,
		"native_cid": req_cid,
		"character_id": req_cid,
		"display_name": boss_label,
		"map_id": cur_map_id,
		"is_flying": bool(arena.call("_is_flying_entry", boss_entry)),
		"is_boss": true,
		"boss_scale": default_boss_scale,
		"ai": ai,
		"x_home": spawn_x,
		"y_home": float(arena.call("_ground_y_at", spawn_x)),
		"zone_min_x": boss_bounds.x,
		"zone_max_x": boss_bounds.y,
		"respawn_toggle": false,
		"node": null,
		"alive": false,
		"hp": float(BOSS_DRUM_STATS["hp"]),
		"max_hp": float(BOSS_DRUM_STATS["hp"]),
		"stamina": float(BOSS_DRUM_STATS["stamina"]),
		"max_stamina": float(BOSS_DRUM_STATS["stamina"]),
		"stun_timer_s": 0.0,
		"hard_stun_timer_s": 0.0,
		"hit_anim_timer_s": 0.0,
		"respawn_timer_s": 0.0,
		"ko_hide_timer_s": 0.0,
		"cooldown_s": 0.0,
		"light_chain": 0,
		"action_clip": "",
		"action_timer_s": 0.0,
		"vy": 0.0,
		"scale_val": default_boss_scale,
		"facing_left": true,
		"patrol_dir": -1,
		"patrol_pause_s": 0.0,
		"power_released": false,
		"melee_hit_done": false,
		"teleport_relocated": false,
		"has_heavy": false,
		"has_power_up": true,
		"light_clip": "attack_light",
		"locomotion_clip": "walk",
		"preserve_phase": false,
		"sideways_locked": false,
		"turn_boost_s": 0.0,
		"turn_elapsed_s": 0.0,
		"turn_duration_s": 0.0,
		"turn_prev_dir": 1,
		"turn_target_left": true,
		"turn_lock_s": 0.0,
		"has_turn_clip": false,
		"orbit_phase": 0.0,
		"orbit_dir": -1.0,
		"hit_flash_s": 0.0,
		"hit_shake_s": 0.0,
		"kentai_timer_s": 0.0,
		"an_nguc_stacks": 0,
		"_local_dead_time_s": -999.0,
		"combat_state": "peace",
		"aggro_target_id": "",
		"committed_target_id": "",
		"fled_attackers": [],
	}
	_spawn_slot_monster(boss_slot, req_cid)
	boss_has_spawned_once = true
	boss_spawn_timer_s = 0.0
	boss_respawn_timer_s = 0.0
	_boss_teleport_chase_cd_s = 2.0

	if player_spawned and not player_dead and arena.player_node != null:
		var bnode := boss_slot.get("node") as Node2D
		if bnode != null:
			var want_left: bool = arena.player_node.position.x < bnode.position.x
			boss_slot["facing_left"] = want_left
			bnode.scale = Vector2(-2.5 if want_left else 2.5, 2.5)
		ai.set_meta(&"drum_engaged", true)
		ai.set_meta(&"drum_phase", "post_teleport_light")
		_start_slot_attack(boss_slot, "teleport", 0.0)
	refresh_pointer_valid()
	return boss_slot


func _execute_boss_teleport_relocation(slot: Dictionary) -> void:
	var mnode := slot.get("node") as Node2D
	if mnode == null or not is_instance_valid(mnode) or arena == null or arena.player_node == null:
		return
	var px: float = arena.player_node.position.x
	var hero_floor_y := float(arena.call("_ground_y_at", px))
	var p_rect := _get_player_body_rect()
	var b_rect := _get_slot_body_rect(slot)
	var pw := p_rect.size.x if p_rect.size.x > 0.0 else 44.0 * float(arena.char_scale)
	var bw := b_rect.size.x if b_rect.size.x > 0.0 else 56.0 * float(slot["scale_val"])
	var target_dist := (pw + bw) * 0.5 + 36.0
	var side := -1.0 if mnode.position.x <= px else 1.0
	var min_b := float(slot["zone_min_x"])
	var max_b := float(slot["zone_max_x"])
	var entry: Dictionary = arena.call("_find_character_entry_ro", str(slot["character_id"]))
	var dims: Vector2i = arena.call("_get_body_dims", entry)
	var half_w := (float(dims.x) * float(slot["scale_val"]) * 0.5) if dims.x > 0 else (56.0 * float(slot["scale_val"]))

	var primary_x := float(arena.call("_resolve_terrain_horizontal_move", px, px + side * target_dist, hero_floor_y, false, min_b, max_b, half_w))
	var chosen_x := primary_x
	if absf(primary_x - px) < maxf(24.0, target_dist * 0.45):
		var alt_x := float(arena.call("_resolve_terrain_horizontal_move", px, px - side * target_dist, hero_floor_y, false, min_b, max_b, half_w))
		if absf(alt_x - px) > absf(primary_x - px):
			chosen_x = alt_x
	mnode.position.x = chosen_x
	mnode.position.y = float(arena.call("_ground_y_at", chosen_x))
	slot["vy"] = 0.0
	var want_left := px < mnode.position.x
	var sc := float(slot["scale_val"])
	slot["facing_left"] = want_left
	mnode.scale = Vector2(-sc if want_left else sc, sc)


func _step_boss_drum_ai(slot: Dictionary, delta: float) -> void:
	var mnode := slot.get("node") as Node2D
	if mnode == null or not is_instance_valid(mnode):
		return
	_boss_teleport_chase_cd_s = maxf(0.0, _boss_teleport_chase_cd_s - delta)
	var ai := slot.get("ai") as UtilityAIController
	if ai != null:
		ai.tick_cooldown(delta)

	if not player_spawned or player_dead or arena.player_node == null or not is_instance_valid(arena.player_node):
		if ai != null and ai.has_method("reset_drum_state"):
			ai.reset_drum_state()
		_step_slot_patrol(slot, delta)
		return

	var can_counter_attack := float(slot["stun_timer_s"]) <= 0.0
	var px: float = arena.player_node.position.x
	var py: float = arena.player_node.position.y
	var self_rect := _get_slot_body_rect(slot)
	var target_rect := _get_player_body_rect()
	var res: Dictionary = {}
	if ai != null and can_counter_attack:
		res = ai.evaluate({
			"character_id": "drum",
			"is_flying": false,
			"is_stationary": false,
			"has_heavy": false,
			"has_power_up": true,
			"light_clip": "attack_light",
			"self_rect": self_rect,
			"target_rect": target_rect,
			"self_x": mnode.position.x,
			"target_x": px,
			"facing_left": mnode.scale.x < 0.0,
			"is_busy": false,
		})

	var dx_p := px - mnode.position.x
	if absf(dx_p) > 12.0:
		var want_left: bool = bool(res.get("desired_face_left", dx_p < 0.0))
		if (mnode.scale.x < 0.0) != want_left:
			var sc := float(slot["scale_val"])
			slot["facing_left"] = want_left
			mnode.scale = Vector2(-sc if want_left else sc, sc)

	var intent := str(res.get("intent", "idle"))
	var dy := absf(py - mnode.position.y)
	var edge_dist := float(res.get("edge_dist", _compute_slot_edge_gap(slot)))

	if can_counter_attack and intent == "attack":
		var clip := str(res.get("attack_clip", "attack_light"))
		if clip == "attack_light" and dy > 110.0 and _boss_teleport_chase_cd_s <= 0.0:
			if ai != null:
				ai.set_meta(&"drum_engaged", true)
				ai.set_meta(&"drum_phase", "post_teleport_light")
			_boss_teleport_chase_cd_s = 2.0
			_start_slot_attack(slot, "teleport", 0.0)
			return
		_start_slot_attack(slot, clip, 0.0)
		return
	elif intent == "wait_cooldown" or (not can_counter_attack and edge_dist <= 50.0):
		arena.call("_ensure_fighter_locomotion", mnode, "idle", bool(slot["preserve_phase"]))
		return

	# Hero moved past 400px UtilityAI engagement range or high vertical elevation: global map pursuit!
	if can_counter_attack and (_boss_teleport_chase_cd_s <= 0.0 or (dy > 110.0 and edge_dist >= 200.0)):
		if ai != null:
			ai.set_meta(&"drum_engaged", true)
			ai.set_meta(&"drum_phase", "post_teleport_light")
		_boss_teleport_chase_cd_s = 2.0
		_start_slot_attack(slot, "teleport", 0.0)
		return

	var move_dir := -1 if px < mnode.position.x else 1
	var entry: Dictionary = arena.call("_find_character_entry_ro", "drum")
	var spd := float(arena.call("_get_walk_speed_px_per_s", entry, float(slot["scale_val"])))
	var dims: Vector2i = arena.call("_get_body_dims", entry)
	var moved := float(arena.call("_move_node_horizontal", mnode, float(move_dir) * spd * delta, false, float(slot["zone_min_x"]), float(slot["zone_max_x"]), float(dims.x) * float(slot["scale_val"]) * 0.5))
	if absf(moved) < 0.5 and py < mnode.position.y - 24.0:
		var fl_y := float(arena.call("_ground_y_at", mnode.position.x))
		if mnode.position.y >= fl_y - 1.0:
			slot["vy"] = -740.0
	arena.call("_ensure_fighter_locomotion", mnode, "walk", bool(slot["preserve_phase"]))


func respawn_player_at_left() -> void:
	player_dead = false
	player_hp = player_max_hp
	player_mana = player_max_mana if player_infinite_mana else 0.0
	player_armor = player_max_armor
	player_armor_broken_timer_s = 0.0
	player_shield_break_icon_timer_s = 0.0
	player_hard_stun_timer_s = 0.0
	player_respawn_timer_s = 0.0
	_local_hp_grace_s = 0.45
	_local_mana_grace_s = 0.45
	player_pve_damage_emitted.emit(0.0, player_hp, true)
	player_hit_flash_s = 0.0
	player_hit_shake_s = 0.0
	_player_melee_pending = false
	_player_power_pending = false
	cancel_auto_approach()
	if arena.player_node != null:
		var left_x := float(arena.walkable_min_x) + 24.0
		arena.player_node.position = Vector2(left_x, float(arena.call("_ground_y_at", left_x)))
		arena.player_vy = 0.0
		arena.player_facing_left = false
		arena.player_node.scale = Vector2(arena.char_scale, arena.char_scale)
		var pspr := arena.player_node.get_node_or_null("Sprite") as AnimatedSprite2D
		if pspr != null:
			pspr.modulate = Color.WHITE
			pspr.position = Vector2.ZERO
		if _is_hero_songoku_node(arena.player_node):
			arena.player_node.set("flight_state", "ground")
			arena.player_node.set("hover_timer_s", 0.0)
			arena.player_node.set("ki", float(arena.player_node.get("max_ki")))
			arena.player_node.set("ki_exhausted", false)
			arena.player_node.call(&"step_combat_move_frame", 0.0, 0)
		arena.call("_play_fighter_clip", arena.player_node, "idle")
	player_state_changed.emit()


func _face_player_toward_x(target_x: float) -> void:
	var pnode := arena.player_node as Node2D
	if pnode == null:
		return
	# Lock Tapion's facing during entire Antamina charge/fire/end (Owner 2026-11-26)
	if pnode.has_method(&"is_antamina_active") and bool(pnode.call(&"is_antamina_active")):
		return
	var dx: float = target_x - pnode.position.x
	if absf(dx) <= 4.0:
		return
	var want_left: bool = dx < 0.0
	arena.player_facing_left = want_left
	var sc := float(arena.char_scale)
	pnode.scale = Vector2(-sc if want_left else sc, sc)


func _get_player_melee_strike_edge_px() -> float:
	if arena != null and _is_hero_songoku_node(arena.player_node):
		return HERO_MELEE_STRIKE_EDGE_PX
	return MELEE_STRIKE_EDGE_PX


func _is_slot_airborne_for_auto(s: Dictionary, p_core: Vector2) -> bool:
	if bool(s.get("is_flying", false)):
		return true
	return _get_slot_core_pos(s).y < p_core.y - 68.0


func _find_best_auto_target_filtered(require_flying: bool, require_ground: bool) -> Dictionary:
	if arena == null or arena.player_node == null:
		return {}
	var p_core: Vector2 = _get_player_core_pos()
	var best: Dictionary = {}
	var best_score: float = 9999999.0
	for s in _get_combat_slots():
		if not bool(s.get("alive", false)) or bool(s.get("is_remote_player", false)) or not is_instance_valid(s.get("node")):
			continue
		var is_air: bool = _is_slot_airborne_for_auto(s, p_core)
		if require_flying and not is_air:
			continue
		if require_ground and is_air:
			continue
		var d: float = p_core.distance_to(_get_slot_core_pos(s))
		var prio_bonus: float = 0.0
		if bool(s.get("is_boss", false)):
			prio_bonus = -180.0
		elif str(s.get("combat_state", "peace")) == "combat":
			prio_bonus = -120.0
		var score: float = d + prio_bonus
		if score < best_score:
			best_score = score
			best = s
	return best


func _update_auto_ki_lock(p_node: Node2D) -> void:
	if p_node == null or not _is_hero_songoku_node(p_node):
		return
	var cur_ki: float = float(p_node.get("ki"))
	var max_ki: float = maxf(1.0, float(p_node.get("max_ki")))
	var ki_ex: bool = bool(p_node.get("ki_exhausted"))
	var in_flight: bool = bool(p_node.call(&"is_airborne_flight"))
	if ki_ex or cur_ki <= 0.5:
		if not _auto_ki_ground_lock:
			_auto_ki_ground_lock = true
			if in_flight:
				_auto_return_to_air_on_ki_full = true
			elif pointer_kind == "enemy" and not pointer_slot_id.is_empty():
				var cur_ps: Dictionary = _find_slot_by_id(pointer_slot_id)
				if not cur_ps.is_empty() and _is_slot_airborne_for_auto(cur_ps, _get_player_core_pos()):
					_auto_return_to_air_on_ki_full = true
	elif _auto_ki_ground_lock and (not ki_ex) and cur_ki >= max_ki - 0.5:
		# Flight KI fully recovered: unlock air engagement & automatically return to flying target!
		_auto_ki_ground_lock = false
		if _auto_return_to_air_on_ki_full:
			_auto_return_to_air_on_ki_full = false
			var air_tgt: Dictionary = _find_best_auto_target_filtered(true, false)
			if not air_tgt.is_empty():
				pointer_kind = "enemy"
				pointer_slot_id = str(air_tgt.get("id", ""))
				pointer_item_node = null
				pointer_changed.emit(pointer_kind)


func _select_auto_battle_target() -> Dictionary:
	refresh_pointer_valid()
	if arena == null or arena.player_node == null:
		return {}
	var p_core: Vector2 = _get_player_core_pos()
	var best_ground: Dictionary = _find_best_auto_target_filtered(false, true)
	var force_ground: bool = _auto_ki_ground_lock and not best_ground.is_empty()

	if pointer_kind == "enemy" and not pointer_slot_id.is_empty():
		var ps: Dictionary = _find_slot_by_id(pointer_slot_id)
		if not ps.is_empty() and bool(ps.get("alive", false)) and not bool(ps.get("is_remote_player", false)) and is_instance_valid(ps.get("node")):
			var ps_air: bool = _is_slot_airborne_for_auto(ps, p_core)
			if not (force_ground and ps_air):
				return ps
			# KI exhausted while targeting flying enemy: remember to return to air once KI is full!
			_auto_return_to_air_on_ki_full = true

	var best: Dictionary = best_ground if force_ground else _find_best_auto_target_filtered(false, false)
	if not best.is_empty():
		pointer_kind = "enemy"
		pointer_slot_id = str(best.get("id", ""))
		pointer_item_node = null
		pointer_changed.emit(pointer_kind)
	return best


func step_hero_auto_battle(delta: float) -> Dictionary:
	## v10.2: Utility AI Auto-Battle controller for playable Hero (Son Goku / Heroes):
	## - Flight KI hysteresis: out of KI -> switch to ground targets until KI recovers to full -> auto switch back to flying!
	## - Flying monsters: prioritize ranged Ki blasts (Kamehameha -> Atomic) before flying/teleporting!
	if not active or not player_spawned or player_dead or arena == null or arena.player_node == null:
		return {"intent": "idle"}
	var p_node: Node2D = arena.player_node as Node2D
	_update_auto_ki_lock(p_node)
	var is_goku: bool = _is_hero_songoku_node(p_node)
	var is_tapion_auto: bool = p_node.has_method(&"is_hero_tapion") and bool(p_node.call(&"is_hero_tapion"))
	var is_busy: bool = bool(arena.call("_is_player_action_playing"))
	var goku_is_ssj: bool = bool(p_node.get("is_ssj")) if is_goku else true
	var hp_ratio: float = player_hp / maxf(1.0, player_max_hp)
	var can_barrier_auto: bool = is_goku and goku_is_ssj and float(p_node.get("barrier_timer_s")) <= 0.0 and float(p_node.get("barrier_cooldown_s")) <= 0.0
	var rec_cd_ok: bool = is_goku and goku_is_ssj and float(p_node.get("recover_timer_s")) <= 0.0 and float(p_node.get("recover_cooldown_s")) <= 0.0
	var grounded_for_rec: bool = bool(arena.call("is_player_grounded_for_recover"))
	var can_hp_recover_auto: bool = rec_cd_ok and grounded_for_rec
	var need_land_for_hp_rec: bool = rec_cd_ok and (not grounded_for_rec)

	var tgt: Dictionary = _select_auto_battle_target()
	if tgt.is_empty():
		if is_goku and goku_is_ssj and not is_busy:
			if hp_ratio < 0.10 and can_barrier_auto:
				arena.call("step_player_movement", delta, 0, 0, false, false, false, Vector2.ZERO)
				request_player_barrier()
				return {"intent": "barrier", "reason": "auto_low_hp_barrier"}
			if hp_ratio < 0.30 and can_hp_recover_auto:
				arena.call("step_player_movement", delta, 0, 0, false, false, false, Vector2.ZERO)
				request_player_energy_recover()
				return {"intent": "energy_recover", "reason": "auto_low_hp_recover"}
			if hp_ratio < 0.30 and need_land_for_hp_rec:
				if bool(p_node.call(&"is_airborne_flight")):
					p_node.call(&"trigger_fast_drop_from_flight")
				arena.call("step_player_movement", delta, 0, 1, false, true, false, Vector2(0.0, 1.0))
				return {"intent": "fast_drop", "reason": "auto_low_hp_land_to_recover"}
		arena.call("step_player_movement", delta, 0, 0, false, false, false, Vector2.ZERO)
		return {"intent": "idle"}
	var p_rect: Rect2 = _get_player_body_rect()
	var m_rect: Rect2 = _get_slot_body_rect(tgt)
	var p_core: Vector2 = _get_player_core_pos()
	var m_core: Vector2 = _get_slot_core_pos(tgt)
	var edge_gap: float = _compute_slot_edge_gap(tgt)
	var v_gap: float = maxf(0.0, maxf(p_rect.position.y - m_rect.end.y, m_rect.position.y - p_rect.end.y))
	var melee_r: float = _get_player_melee_strike_edge_px()
	var in_tapion_range: bool = absf(m_core.x - p_core.x) <= TAPION_SKILL_MAX_RANGE_PX
	var tap_can_maha: bool = is_tapion_auto and in_tapion_range and float(p_node.get("mahasenko_cooldown_s")) <= 0.0
	var tap_can_kentai: bool = is_tapion_auto and in_tapion_range and float(p_node.get("kentaima_cooldown_s")) <= 0.0
	var tap_can_anta: bool = is_tapion_auto and float(p_node.get("antamina_cooldown_s")) <= 0.0 and player_mana + 0.001 >= 100.0
	var can_kame: bool = tap_can_maha if is_tapion_auto else (is_goku and goku_is_ssj and player_mana + 0.001 >= 80.0 and float(p_node.get("kame_cooldown_s")) <= 0.0)
	var can_atomic: bool = (tap_can_kentai or tap_can_anta) if is_tapion_auto else (is_goku and goku_is_ssj and float(p_node.get("atomic_cooldown_s")) <= 0.0)
	var can_recover: bool = is_goku and goku_is_ssj and grounded_for_rec and float(p_node.get("recover_cooldown_s")) <= 0.0 and float(p_node.get("ki")) < float(p_node.get("max_ki")) - 5.0
	var can_fly_auto: bool = (bool(p_node.call(&"can_fly")) and (not _auto_ki_ground_lock)) if is_goku else false
	var dec: Dictionary = UtilityAIControllerScript.evaluate_hero_auto({
		"has_target": true,
		"is_songoku": is_goku,
		"is_ssj": goku_is_ssj,
		"is_busy": is_busy,
		"hp_ratio": hp_ratio,
		"can_barrier": can_barrier_auto,
		"can_hp_recover": can_hp_recover_auto,
		"need_land_for_hp_recover": need_land_for_hp_rec,
		"player_pos": p_core,
		"target_pos": m_core,
		"edge_dist": edge_gap,
		"v_gap": v_gap,
		"melee_range_px": melee_r,
		"stamina": float(p_node.get("stamina")) if is_goku else 0.0,
		"mana": player_mana,
		"has_power_up": bool(arena.call("_has_clip_name", p_node, &"power_up")),
		"can_kamehameha": can_kame,
		"can_atomic": can_atomic,
		"can_energy_recover": can_recover,
		"target_airborne": _is_slot_airborne_for_auto(tgt, p_core),
		"is_airborne_flight": bool(p_node.call(&"is_airborne_flight")) if is_goku else false,
		"can_fly": can_fly_auto,
		"can_light_attack": bool(arena.call("can_player_light_attack")),
	})
	var intent: String = str(dec.get("intent", "idle"))
	_face_player_toward_x(m_core.x)
	if intent == "transform_ssj":
		arena.call("_trigger_songoku_auto_transform_on_hit")
		arena.call("step_player_movement", delta, 0, 0, false, false, false, Vector2.ZERO)
	elif intent == "barrier":
		arena.call("step_player_movement", delta, 0, 0, false, false, false, Vector2.ZERO)
		request_player_barrier()
	elif intent == "kamehameha":
		arena.call("step_player_movement", delta, 0, 0, false, false, false, Vector2.ZERO)
		if is_tapion_auto:
			arena.call("_on_touch_action", "mahasenko")
		else:
			request_player_kamehameha()
	elif intent == "atomic_blast":
		arena.call("step_player_movement", delta, 0, 0, false, false, false, Vector2.ZERO)
		if is_tapion_auto:
			var tap_act := "kentaima" if tap_can_kentai else "antamina"
			arena.call("_on_touch_action", tap_act)
		else:
			request_player_atomic_blast()
	elif intent == "energy_recover":
		arena.call("step_player_movement", delta, 0, 0, false, false, false, Vector2.ZERO)
		request_player_energy_recover()
	elif intent == "teleport_static":
		arena.call("_trigger_songoku_teleport", Vector2.ZERO)
		arena.call("step_player_movement", delta, 0, 0, false, false, false, Vector2.ZERO)
	elif intent == "teleport_dash":
		var fvec: Vector2 = dec.get("fly_vec", Vector2.RIGHT)
		arena.call("_trigger_songoku_teleport", fvec)
		arena.call("step_player_movement", delta, 0, 0, false, false, false, Vector2.ZERO)
	elif intent == "power_up":
		request_player_power_up()
		arena.call("step_player_movement", delta, 0, 0, false, false, false, Vector2.ZERO)
	elif intent == "attack_combo":
		arena.call("step_player_movement", delta, 0, 0, false, false, false, Vector2.ZERO)
		request_player_primary_action()
	elif intent == "fast_drop":
		var fvec_drop: Vector2 = dec.get("fly_vec", Vector2(0.0, 1.0))
		var mdir_drop: int = int(dec.get("move_dir", 0))
		if is_goku and bool(p_node.call(&"is_airborne_flight")):
			p_node.call(&"trigger_fast_drop_from_flight")
		arena.call("step_player_movement", delta, mdir_drop, 1, false, true, false, fvec_drop)
	elif intent == "fly_chase":
		var fvec2: Vector2 = dec.get("fly_vec", Vector2(0.0, -1.0))
		var mdir: int = int(dec.get("move_dir", 0))
		var need_jump: bool = bool(dec.get("jump", false))
		var fly_y: int = -1 if fvec2.y < -0.15 else (1 if fvec2.y > 0.15 else 0)
		arena.call("step_player_movement", delta, mdir, fly_y, need_jump, false, false, fvec2)
	elif intent == "chase":
		var cdir: int = int(dec.get("move_dir", 0))
		var jreq: bool = false
		if cdir != 0 and not bool(arena.call("_can_cross_terrain_step", p_node.position.x, p_node.position.x + float(cdir) * 28.0, p_node.position.y, false)):
			jreq = true
		elif m_rect.end.y < p_rect.end.y - 24.0 and absf(m_core.x - p_core.x) < 160.0 and not _is_slot_airborne_for_auto(tgt, p_core):
			jreq = true
		arena.call("step_player_movement", delta, cdir, 0, jreq, false, false, Vector2(float(cdir), 0.0))
	else:
		arena.call("step_player_movement", delta, 0, 0, false, false, false, Vector2.ZERO)
	return dec


func _step_auto_approach(delta: float) -> void:
	if not auto_approach_active or not player_spawned or player_dead or arena.player_node == null:
		cancel_auto_approach()
		return
	var pnode := arena.player_node as Node2D
	_auto_approach_timeout_s -= delta
	if _auto_approach_timeout_s <= 0.0:
		cancel_auto_approach()
		return

	if _auto_approach_kind == "item":
		if _auto_approach_item == null or not is_instance_valid(_auto_approach_item) or not _auto_approach_item.visible:
			cancel_auto_approach()
			return
		var st := str(_auto_approach_item.get("lifecycle_state"))
		if st == "collecting" or st == "collected" or st == "bag":
			cancel_auto_approach()
			return
		var dist: float = pnode.position.distance_to(_auto_approach_item.position)
		if dist <= ITEM_PICKUP_RANGE_PX and _can_pickup_item(_auto_approach_item):
			var target_item := _auto_approach_item
			cancel_auto_approach()
			_collect_single_item(target_item)
			arena.call("step_player_movement", delta, 0, 0, false, false, false, Vector2.ZERO)
			return
		var idx: float = _auto_approach_item.position.x - pnode.position.x
		var move_dir := -1 if idx < -6.0 else (1 if idx > 6.0 else 0)
		var jump_req := false
		if move_dir != 0 and not bool(arena.call("_can_cross_terrain_step", pnode.position.x, pnode.position.x + float(move_dir) * 28.0, pnode.position.y, false)):
			jump_req = true
		arena.call("step_player_movement", delta, move_dir, 0, jump_req, false, false, Vector2.ZERO)
		return

	if _auto_approach_kind == "skill":
		var tgt_s := _find_slot_by_id(_auto_approach_slot_id)
		if tgt_s.is_empty() or not can_attack_slot(tgt_s) or _auto_approach_skill_action.is_empty():
			cancel_auto_approach()
			return
		var m_core_s := _get_slot_core_pos(tgt_s)
		var p_core_s := _get_player_core_pos()
		var dx_s := m_core_s.x - p_core_s.x
		var stop_range := maxf(80.0, _auto_approach_range_px - 20.0)
		if absf(dx_s) <= stop_range:
			var queued_skill := _auto_approach_skill_action
			pointer_kind = "enemy"
			pointer_slot_id = str(tgt_s.get("id", ""))
			pointer_item_node = null
			_face_player_toward_x(m_core_s.x)
			cancel_auto_approach()
			arena.call("step_player_movement", delta, 0, 0, false, false, false, Vector2.ZERO)
			arena.call("_on_touch_action", queued_skill)
			return
		var move_dir_s := -1 if dx_s < -8.0 else (1 if dx_s > 8.0 else 0)
		var jump_req_s := false
		if move_dir_s != 0:
			if not bool(arena.call("_can_cross_terrain_step", pnode.position.x, pnode.position.x + float(move_dir_s) * 28.0, pnode.position.y, false)):
				jump_req_s = true
		var is_fly_s := _is_hero_songoku_node(pnode) and bool(pnode.call(&"is_airborne_flight"))
		arena.call("step_player_movement", delta, move_dir_s, 0, jump_req_s, false, false, Vector2(float(move_dir_s), 0.0) if is_fly_s else Vector2.ZERO)
		return

	if _auto_approach_kind == "enemy":
		var tgt := _find_slot_by_id(_auto_approach_slot_id)
		if tgt.is_empty() or not can_attack_slot(tgt):
			cancel_auto_approach()
			return
		var p_node := arena.player_node as Node2D
		var m_node := tgt["node"] as Node2D
		var p_rect := _get_player_body_rect()
		var m_rect := _get_slot_body_rect(tgt)
		var m_core := _get_slot_core_pos(tgt)
		var p_core := _get_player_core_pos()
		var edge_gap := _compute_slot_edge_gap(tgt)
		var v_gap := maxf(0.0, maxf(p_rect.position.y - m_rect.end.y, m_rect.position.y - p_rect.end.y))
		var melee_r := _get_player_melee_strike_edge_px()
		var approach_stop := minf(melee_r - 2.0, melee_r * 0.90) if _is_hero_songoku_node(p_node) else (melee_r * 0.72)
		var v_stop := 68.0 if _is_hero_songoku_node(p_node) else 85.0
		if edge_gap <= approach_stop and v_gap <= v_stop:
			_face_player_toward_x(m_core.x)
			arena.call("step_player_movement", delta, 0, 0, false, false, false, Vector2.ZERO)
			if bool(arena.call("can_player_light_attack")):
				cancel_auto_approach()
				if _is_hero_songoku_node(arena.player_node):
					if bool(arena.player_node.call(&"can_attack")):
						var ci: Dictionary = arena.player_node.call(&"pop_next_combo_attack")
						var cname := str(ci.get("clip", "attack_light"))
						if bool(arena.call("_request_player_action", cname)):
							_player_combo_attack_info = ci
							_player_hit_frames_fired.clear()
							_player_melee_pending = true
							_player_gold_slash_pending = bool(ci.get("has_gold_slash_60", false))
				elif bool(arena.call("_request_player_action", "attack_light")):
					_player_melee_pending = true
			return

		var p_entry: Dictionary = arena.call("_find_character_entry_ro", arena.active_character_id)
		var is_flying := bool(arena.call("_is_flying_entry", p_entry))
		var is_goku := _is_hero_songoku_node(p_node)
		var target_airborne := bool(tgt.get("is_flying", false)) or (m_core.y < p_core.y - 60.0)
		if is_goku and target_airborne:
			# v6 T6: Touch/normal attack on airborne monster automatically transforms (if Base), jumps & flies up (`fly_aura`)!
			if not bool(p_node.get("is_ssj")):
				arena.call("_trigger_songoku_auto_transform_on_hit")
				arena.call("step_player_movement", delta, 0, 0, false, false, false, Vector2.ZERO)
				return
			var to_air := m_core - p_core
			var air_vec := to_air.normalized() if to_air.length() > 1.0 else Vector2(0.0, -1.0)
			var air_dir := -1 if to_air.x < -8.0 else (1 if to_air.x > 8.0 else 0)
			var in_flight := bool(p_node.call(&"is_airborne_flight"))
			var goku_can_fly := bool(p_node.call(&"can_fly"))
			if not in_flight:
				if not goku_can_fly:
					# Out of KI: approach underneath and wait for KI regeneration
					arena.call("step_player_movement", delta, air_dir, 0, false, false, false, Vector2(float(air_dir), 0.0))
					return
				var launch_vec := Vector2(clampf(to_air.x / 140.0, -0.45, 0.45), -0.92).normalized()
				arena.call("step_player_movement", delta, air_dir, -1, true, false, false, launch_vec)
			else:
				var fly_y := -1 if air_vec.y < -0.15 else (1 if air_vec.y > 0.15 else 0)
				arena.call("step_player_movement", delta, air_dir, fly_y, false, false, false, air_vec)
			return
		elif is_goku and bool(p_node.call(&"is_airborne_flight")):
			var to_desc: Vector2 = m_core - p_core
			var desc_dir := -1 if to_desc.x < -8.0 else (1 if to_desc.x > 8.0 else 0)
			if absf(to_desc.x) <= 95.0 and to_desc.y >= -60.0:
				p_node.call(&"trigger_fast_drop_from_flight")
				arena.call("step_player_movement", delta, desc_dir, 1, false, true, false, Vector2(0.0, 1.0))
				return
			var desc_raw: Vector2 = to_desc.normalized() if to_desc.length() > 1.0 else Vector2(0.0, 1.0)
			var desc_vec: Vector2 = desc_raw if to_desc.y > 24.0 or to_desc.y < -60.0 else Vector2(desc_raw.x, maxf(desc_raw.y, 0.35)).normalized()
			var desc_fly_y := -1 if desc_vec.y < -0.15 else (1 if desc_vec.y > 0.15 else 0)
			arena.call("step_player_movement", delta, desc_dir, desc_fly_y, false, false, false, desc_vec)
			return
		if is_flying:
			var to_vec := m_core - p_core
			var avec := to_vec.normalized() if to_vec.length() > 1.0 else Vector2.ZERO
			var f_dir := -1 if avec.x < -0.18 else (1 if avec.x > 0.18 else 0)
			arena.call("step_player_movement", delta, f_dir, 0, false, false, false, avec)
			return

		var dx: float = m_core.x - p_core.x
		var move_dir := -1 if dx < -8.0 else (1 if dx > 8.0 else 0)
		var jump_req := false
		if absf(dx) <= 36.0 and v_gap > v_stop:
			if v_gap <= 190.0:
				jump_req = true
			else:
				# High flying target out of ground melee jump reach: stop cleanly underneath
				cancel_auto_approach()
				arena.call("step_player_movement", delta, 0, 0, false, false, false, Vector2.ZERO)
				return
		elif move_dir != 0:
			if not bool(arena.call("_can_cross_terrain_step", p_node.position.x, p_node.position.x + float(move_dir) * 28.0, p_node.position.y, false)):
				jump_req = true
			elif m_rect.end.y < p_rect.end.y - 24.0 and absf(dx) < 160.0:
				jump_req = true
		arena.call("step_player_movement", delta, move_dir, 0, jump_req, false, false, Vector2.ZERO)


func _is_hero_songoku_node(node: Node) -> bool:
	return node != null and node.has_method(&"is_hero_songoku") and bool(node.call(&"is_hero_songoku"))


func get_pointed_or_nearest_enemy_pos() -> Dictionary:
	refresh_pointer_valid()
	var tgt := _resolve_player_attack_target(true)
	if tgt.is_empty() or not bool(tgt.get("alive", false)):
		return {"valid": false}
	var mnode := tgt.get("node") as Node2D
	if mnode == null or not is_instance_valid(mnode):
		return {"valid": false}
	return {
		"valid": true,
		"pos": mnode.position,
		"core": _get_slot_core_pos(tgt),
		"slot_id": str(tgt.get("id", "")),
	}


func _step_player_combat_hooks() -> void:
	var pspr := arena.player_node.get_node_or_null("Sprite") as AnimatedSprite2D
	if pspr == null:
		return
	var queued_act := String(arena.player_node.get_meta(&"_arena_queued_action", ""))
	var is_goku := _is_hero_songoku_node(arena.player_node)
	if _player_melee_pending:
		var anim_str := String(pspr.animation)
		var is_melee_anim := (anim_str == "attack_light" or anim_str == "attack_heavy" or anim_str == "attack_nomal" or anim_str.begins_with("attack_"))
		var melee_queued := (queued_act == "attack_light" or queued_act == "attack_heavy" or queued_act == "attack_nomal" or queued_act.begins_with("attack_"))
		if is_goku and not _player_combo_attack_info.is_empty():
			var expected_clip := str(_player_combo_attack_info.get("clip", ""))
			if anim_str == expected_clip and pspr.is_playing():
				var hit_frames: Array = _player_combo_attack_info.get("hit_frames", [2])
				var is_heavy := bool(_player_combo_attack_info.get("is_heavy", false))
				var hk := "heavy" if is_heavy else "melee"
				var stamina_per_frame_hit := STAMINA_PER_HIT / maxf(1.0, float(hit_frames.size()))
				for hf_v in hit_frames:
					var hf := int(hf_v)
					if pspr.frame >= hf and not _player_hit_frames_fired.has(hf):
						_player_hit_frames_fired.append(hf)
						var rolled: Dictionary = arena.player_node.call(&"roll_strike_damage", is_heavy, false)
						_execute_player_melee_hit(hk, float(rolled.get("damage", 10.0)), bool(rolled.get("is_crit", false)), stamina_per_frame_hit)
				if _player_hit_frames_fired.size() >= hit_frames.size():
					_player_melee_pending = false
			elif anim_str != expected_clip and queued_act != expected_clip:
				_player_melee_pending = false
				_player_hit_frames_fired.clear()
		else:
			if is_melee_anim and pspr.frame >= 2:
				_player_melee_pending = false
				_execute_player_melee_hit("heavy" if anim_str == "attack_heavy" else "melee")
			elif not is_melee_anim and not melee_queued:
				_player_melee_pending = false
	# Special penultimate golden streak frame (#13) of attack_6 (file 17) -> 60 damage!
	if _player_gold_slash_pending:
		var anim_g := String(pspr.animation)
		if anim_g == "attack_6" and pspr.frame >= 13:
			_player_gold_slash_pending = false
			_execute_player_melee_hit("heavy", 60.0, true)
		elif anim_g != "attack_6" and queued_act != "attack_6":
			_player_gold_slash_pending = false
	if _player_power_pending:
		if String(pspr.animation) == "power_up" and pspr.frame >= 10:
			_player_power_pending = false
			_launch_player_homing_orb()
		elif String(pspr.animation) != "power_up" and queued_act != "power_up":
			_player_power_pending = false


func request_player_primary_action() -> bool:
	if not player_spawned or player_dead or arena.player_node == null:
		return false
	refresh_pointer_valid()

	if pointer_kind == "item" and pointer_item_node != null and is_instance_valid(pointer_item_node):
		if _can_pickup_item(pointer_item_node) and arena.player_node.position.distance_to(pointer_item_node.position) <= ITEM_PICKUP_RANGE_PX:
			cancel_auto_approach()
			return _collect_single_item(pointer_item_node)
		auto_approach_active = true
		_auto_approach_kind = "item"
		_auto_approach_slot_id = ""
		_auto_approach_item = pointer_item_node
		_auto_approach_timeout_s = 6.0
		return true
	if pointer_kind == "npc" and arena.shenron_summon != null and arena.shenron_summon.active:
		cancel_auto_approach()
		if arena.wish_panel != null:
			arena.wish_panel.visible = true
		return true

	# Base form of Son Goku: interactive movement only, cannot attack until transformed to SSJ1!
	var is_goku := _is_hero_songoku_node(arena.player_node)
	if is_goku and not bool(arena.player_node.call(&"can_attack")):
		# Still allow picking up nearby dropped items
		for item_n in arena._dropped_item_nodes:
			if is_instance_valid(item_n) and _can_pickup_item(item_n) and arena.player_node.position.distance_to(item_n.position) <= ITEM_PICKUP_RANGE_PX:
				cancel_auto_approach()
				return _collect_single_item(item_n)
		floating_texts.append({
			"pos": arena.player_node.position + Vector2(0.0, -138.0),
			"text": "Biến SSJ1 để tấn công!",
			"color": Color(1.0, 0.88, 0.30, 1.0),
			"elapsed_s": 0.0,
			"duration_s": 1.0,
		})
		return false

	if pointer_kind == "enemy" and not pointer_slot_id.is_empty():
		var pointed_tgt := _find_slot_by_id(pointer_slot_id)
		if not pointed_tgt.is_empty() and can_attack_slot(pointed_tgt):
			var p_rect := _get_player_body_rect()
			var m_rect := _get_slot_body_rect(pointed_tgt)
			var m_core := _get_slot_core_pos(pointed_tgt)
			var edge_gap := _compute_slot_edge_gap(pointed_tgt)
			var v_gap := maxf(0.0, maxf(p_rect.position.y - m_rect.end.y, m_rect.position.y - p_rect.end.y))
			var melee_r := _get_player_melee_strike_edge_px()
			var max_v := 68.0 if is_goku else 90.0
			if edge_gap >= melee_r or v_gap > max_v:
				# Must move closer (or jump & fly up for airborne targets!) before normal melee attack!
				auto_approach_active = true
				_auto_approach_kind = "enemy"
				_auto_approach_slot_id = pointer_slot_id
				_auto_approach_item = null
				_auto_approach_timeout_s = 8.0
				return true
			cancel_auto_approach()
			_face_player_toward_x(m_core.x)
	# If there's a ready item close by and no alive enemy within melee range, pick it up
	var nearest_enemy := _find_nearest_alive_slot_in_melee()
	if nearest_enemy.is_empty():
		for item_n in arena._dropped_item_nodes:
			if is_instance_valid(item_n) and _can_pickup_item(item_n) and arena.player_node.position.distance_to(item_n.position) <= ITEM_PICKUP_RANGE_PX:
				cancel_auto_approach()
				return _collect_single_item(item_n)

	if is_goku:
		if not bool(arena.call("can_player_light_attack")):
			return false
		var was_peace := not bool(arena.player_node.call(&"is_in_combat"))
		var combo_info: Dictionary = arena.player_node.call(&"pop_next_combo_attack")
		if was_peace and arena.has_method(&"trigger_combat_state_banner"):
			arena.call(&"trigger_combat_state_banner")
		var clip_name := str(combo_info.get("clip", "attack_light"))
		if bool(arena.call("_request_player_action", clip_name)):
			_player_combo_attack_info = combo_info
			_player_hit_frames_fired.clear()
			_player_melee_pending = true
			_player_gold_slash_pending = bool(combo_info.get("has_gold_slash_60", false))
			return true
		return false

	if bool(arena.call("_request_player_action", "attack_light")):
		_player_melee_pending = true
		return true
	return false


func request_player_heavy_action() -> bool:
	if not player_spawned or player_dead or arena.player_node == null:
		return false
	cancel_auto_approach()
	var tgt := _resolve_player_attack_target(false)
	if not tgt.is_empty():
		var m_core := _get_slot_core_pos(tgt)
		_face_player_toward_x(m_core.x)
	if bool(arena.call("_request_player_action", "attack_heavy")):
		_player_melee_pending = true
		return true
	return false


func request_player_power_up() -> bool:
	if not player_spawned or player_dead or arena.player_node == null:
		return false
	if player_mana < 100.0:
		return false
	cancel_auto_approach()
	var tgt := _resolve_player_attack_target(true)
	if tgt.is_empty():
		return false
	var mnode := tgt.get("node") as Node2D
	if mnode != null and is_instance_valid(mnode):
		_face_player_toward_x(mnode.position.x)
	if bool(arena.call("_request_player_action", "power_up")):
		var pspr := arena.player_node.get_node_or_null("Sprite") as AnimatedSprite2D
		var queued_act := String(arena.player_node.get_meta(&"_arena_queued_action", ""))
		var started_now := pspr != null and String(pspr.animation) == "power_up" and pspr.is_playing() and queued_act != "power_up"
		if started_now:
			if not player_infinite_mana:
				player_mana = maxf(0.0, player_mana - 100.0)
			_local_mana_grace_s = 0.85
			_player_power_pending = true
			_player_power_target = tgt
			player_state_changed.emit()
		return true
	return false


func _compute_contact_edge_point(rect_a: Rect2, rect_b: Rect2) -> Vector2:
	var cx_a := rect_a.position.x + rect_a.size.x * 0.5
	var cy_a := rect_a.position.y + rect_a.size.y * 0.45
	var hx := clampf(cx_a, rect_b.position.x, rect_b.end.x)
	var hy := clampf(cy_a, rect_b.position.y + 8.0, rect_b.end.y - 8.0)
	return Vector2(hx, hy)


func _emit_slot_combat_action(action_kind: String, tgt: Dictionary, origin_pos: Vector2, dmg: float, mana_grace_s: float = 0.45) -> bool:
	var is_remote_p := bool(tgt.get("is_remote_player", false))
	if is_remote_p and not is_remote_player_hostile(tgt):
		return true
	var tgt_id := str(tgt.get("user_id", tgt.get("id", ""))) if is_remote_p else str(tgt.get("id", ""))
	if mana_grace_s > 0.0:
		_local_mana_grace_s = maxf(_local_mana_grace_s, mana_grace_s)
	if not is_remote_p and not bool(tgt.get("is_boss", false)) and not tgt_id.is_empty():
		_slot_local_hit_grace[tgt_id] = maxf(float(_slot_local_hit_grace.get(tgt_id, 0.0)), 0.45)
	var face_l: bool = (arena != null and arena.player_node != null and arena.player_node.scale.x < 0.0)
	combat_action_emitted.emit(action_kind, tgt_id, "player" if is_remote_p else "monster", origin_pos, face_l, dmg)
	return is_remote_p


func _execute_player_melee_hit(hit_kind: String = "melee", damage_override: float = -1.0, is_crit_gold: bool = false, stamina_dmg_override: float = -1.0) -> void:
	var tgt := _resolve_player_attack_target(false)
	if tgt.is_empty() or not can_attack_slot(tgt):
		return
	var p_rect := _get_player_body_rect()
	var m_rect := _get_slot_body_rect(tgt)
	var edge := _compute_slot_edge_gap(tgt)
	var v_gap := maxf(0.0, maxf(p_rect.position.y - m_rect.end.y, m_rect.position.y - p_rect.end.y))
	var melee_r := _get_player_melee_strike_edge_px()
	if edge >= melee_r or v_gap > 90.0:
		return
	var p_core := _get_player_core_pos()
	var hit_pt: Vector2 = arena.call("compute_nearest_silhouette_point", tgt["node"], str(tgt["character_id"]), float(tgt["scale_val"]), p_core)
	var hit_dir := (hit_pt - p_core).normalized() if hit_pt.distance_to(p_core) > 1.0 else Vector2(-1.0 if arena.player_node.scale.x < 0.0 else 1.0, 0.0)
	var dmg := damage_override if damage_override > 0.0 else (PLAYER_HEAVY_DMG if hit_kind == "heavy" else PLAYER_LIGHT_DMG)
	var stam_dmg := stamina_dmg_override if stamina_dmg_override >= 0.0 else STAMINA_PER_HIT
	var net_action := "attack_heavy" if hit_kind == "heavy" else "attack_light"
	if _is_hero_songoku_node(arena.player_node):
		if is_crit_gold and absf(dmg - 60.0) < 0.5:
			net_action = "goku_gold_slash"
		elif hit_kind == "heavy":
			net_action = "goku_heavy"
		else:
			net_action = "goku_light"
	var is_remote_p := _emit_slot_combat_action(net_action, tgt, arena.player_node.position, dmg, 0.45)
	if network_authoritative and is_remote_p:
		_spawn_hit_impact_fx(hit_pt, hit_kind, "", Color(1.0, 0.92, 0.28, 1.0), hit_dir)
		player_mana = minf(player_max_mana, player_mana + PLAYER_MANA_GAIN)
		player_state_changed.emit()
		return
	apply_damage_to_slot(tgt, dmg, stam_dmg, hit_pt, hit_kind, false, hit_dir)
	if is_crit_gold:
		floating_texts.append({
			"pos": hit_pt + Vector2(0.0, -34.0),
			"text": "CRIT %d!" % int(round(dmg)),
			"color": Color(1.0, 0.90, 0.18, 1.0),
			"elapsed_s": 0.0,
			"duration_s": 0.85,
		})
	player_mana = minf(player_max_mana, player_mana + PLAYER_MANA_GAIN)
	player_state_changed.emit()


func _launch_player_homing_orb() -> void:
	var tgt := _player_power_target
	if tgt.is_empty() or not bool(tgt.get("alive", false)):
		tgt = _resolve_player_attack_target(true)
	if tgt.is_empty():
		return
	var dir_x: float = -1.0 if arena.player_node.scale.x < 0.0 else 1.0
	var start_pos: Vector2 = arena.player_node.position + Vector2(42.0 * dir_x * float(arena.char_scale), -28.0 * float(arena.char_scale))
	var cid: String = str(arena.active_character_id) if not str(arena.active_character_id).is_empty() else "drum"
	var fx_clip := _resolve_fx_clip_for_character(cid)
	if fx_clip.is_empty():
		fx_clip = "electric_orb_fx"
	_spawn_homing_projectile(arena.player_node, cid, fx_clip, start_pos, float(arena.char_scale), tgt, true, PLAYER_POWER_DMG, STAMINA_PER_HIT)


func _spawn_powerup_explosion(world_pos: Vector2, scale_val: float = 0.85) -> void:
	if arena == null or PowerupExplosionFrames == null:
		return
	var ex := AnimatedSprite2D.new()
	ex.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	ex.sprite_frames = PowerupExplosionFrames
	ex.centered = false
	ex.offset = Vector2(-40.0, -40.0)
	ex.scale = Vector2(scale_val, scale_val)
	ex.position = world_pos
	ex.z_index = Z_LAYER_FX
	var parent_layer: Node = arena.fighters_layer if arena.fighters_layer != null else arena
	parent_layer.add_child(ex)
	ex.play(&"explode")
	_explosion_nodes.append(ex)
	ex.animation_finished.connect(func() -> void:
		_explosion_nodes.erase(ex)
		if is_instance_valid(ex):
			ex.queue_free()
	)


func _resolve_custom_hit_impact_frames(attacker_cid: String) -> SpriteFrames:
	if attacker_cid.is_empty() or arena == null:
		return null
	var entry: Dictionary = arena.call("_find_character_entry_ro", attacker_cid)
	var rc: Dictionary = entry.get("render_contract", {}) if entry.get("render_contract", {}) is Dictionary else {}
	var custom_path := str(rc.get("custom_hit_impact_tres", "")).strip_edges()
	if custom_path.is_empty():
		return null
	var cache_key := "hit_impact:%s" % custom_path
	if _fx_frames_cache.has(cache_key):
		return _fx_frames_cache[cache_key] as SpriteFrames
	if ResourceLoader.exists(custom_path):
		var loaded := load(custom_path) as SpriteFrames
		if loaded != null:
			_fx_frames_cache[cache_key] = loaded
			return loaded
	return null


func _spawn_hit_impact_fx(world_pos: Vector2, kind: String, dmg_text: String, text_col: Color, impact_dir: Vector2 = Vector2.RIGHT, attacker_cid: String = "") -> void:
	var dur := 0.30 if kind == "heavy" else (0.24 if (kind == "melee" or kind == "skill" or kind == "stun" or kind == "clash") else 0.18)
	var d_norm := impact_dir.normalized() if impact_dir.length_squared() > 0.001 else Vector2.RIGHT
	var custom_frames: SpriteFrames = _resolve_custom_hit_impact_frames(attacker_cid)
	hit_impacts.append({"pos": world_pos, "kind": kind, "dir": d_norm, "elapsed_s": 0.0, "duration_s": dur, "custom_frames": custom_frames})
	if not dmg_text.is_empty():
		floating_texts.append({
			"pos": world_pos + Vector2(0.0, -16.0),
			"text": dmg_text,
			"color": text_col,
			"elapsed_s": 0.0,
			"duration_s": 0.60,
		})


static func _apply_hit_flash_modulate(spr: AnimatedSprite2D, flash_active: bool, blink: bool, is_hero: bool) -> void:
	if spr == null:
		return
	if not flash_active:
		spr.modulate = Color.WHITE
		return
	var base := Color(1.0, 0.24, 0.24, 1.0) if blink else Color(1.0, 0.94, 0.94, 0.72)
	if not is_hero:
		base = Color(1.0, 0.35, 0.28, 1.0) if blink else Color(1.0, 0.96, 0.75, 0.75)
	var raw_flash := Color(
		base.r * HIT_FLASH_BRIGHTNESS_MUL,
		base.g * HIT_FLASH_BRIGHTNESS_MUL,
		base.b * HIT_FLASH_BRIGHTNESS_MUL,
		base.a * HIT_FLASH_ALPHA_MUL
	)
	# Reduce hit-flash/blink contrast by 40%, then lift brightness by +40% (Owner human-test request 2026-11-19)
	# so heroes/monsters stay bright and visually legible instead of darkening on hit.
	var blended := Color.WHITE.lerp(raw_flash, HIT_FLASH_CONTRAST_MUL)
	spr.modulate = Color(
		minf(1.35, blended.r * HIT_FLASH_BRIGHTNESS_BOOST),
		minf(1.35, blended.g * HIT_FLASH_BRIGHTNESS_BOOST),
		minf(1.35, blended.b * HIT_FLASH_BRIGHTNESS_BOOST),
		blended.a
	)


func _step_hit_visuals(delta: float) -> void:
	if pointer_pulse_s > 0.0:
		pointer_pulse_s = maxf(0.0, pointer_pulse_s - delta)
	if pointer_x_anim_s < pointer_x_anim_dur_s:
		pointer_x_anim_s = minf(pointer_x_anim_dur_s, pointer_x_anim_s + delta)
	if pointer_x_visible_s > 0.0:
		pointer_x_visible_s = maxf(0.0, pointer_x_visible_s - delta)
	if pointer_x_double_tap_pulse_s > 0.0:
		pointer_x_double_tap_pulse_s = maxf(0.0, pointer_x_double_tap_pulse_s - delta)
	if player_hit_flash_s > 0.0 or player_hit_shake_s > 0.0:
		player_hit_flash_s = maxf(0.0, player_hit_flash_s - delta)
		player_hit_shake_s = maxf(0.0, player_hit_shake_s - delta)
		if arena.player_node != null and is_instance_valid(arena.player_node):
			var pspr := arena.player_node.get_node_or_null("Sprite") as AnimatedSprite2D
			if pspr != null:
				var pblink := int(floor(_sim_time_s * 30.0)) % 2 == 0
				_apply_hit_flash_modulate(pspr, player_hit_flash_s > 0.0, pblink, true)
				var shake_amp := (1.2 * HIT_SHAKE_SCALE_MUL) / maxf(1.0, float(arena.char_scale))
				pspr.position.x = sin(_sim_time_s * 75.0) * shake_amp if player_hit_shake_s > 0.0 else 0.0
	for s in _get_combat_slots():
		var hf := float(s.get("hit_flash_s", 0.0))
		var hs := float(s.get("hit_shake_s", 0.0))
		if hf > 0.0 or hs > 0.0:
			hf = maxf(0.0, hf - delta)
			hs = maxf(0.0, hs - delta)
			s["hit_flash_s"] = hf
			s["hit_shake_s"] = hs
			var mn := s.get("node") as Node2D
			if mn != null and is_instance_valid(mn):
				var mspr := mn.get_node_or_null("Sprite") as AnimatedSprite2D
				if mspr != null:
					var mblink := int(floor(_sim_time_s * 30.0)) % 2 == 0
					_apply_hit_flash_modulate(mspr, hf > 0.0, mblink, false)
					mspr.position.x = sin(_sim_time_s * 75.0) * (4.0 * HIT_SHAKE_SCALE_MUL) if hs > 0.0 else 0.0
	for i in range(hit_impacts.size() - 1, -1, -1):
		var imp: Dictionary = hit_impacts[i]
		imp["elapsed_s"] = float(imp["elapsed_s"]) + delta
		if float(imp["elapsed_s"]) >= float(imp["duration_s"]):
			hit_impacts.remove_at(i)
	for i in range(floating_texts.size() - 1, -1, -1):
		var ft: Dictionary = floating_texts[i]
		ft["elapsed_s"] = float(ft["elapsed_s"]) + delta
		ft["pos"] = (ft["pos"] as Vector2) + Vector2(0.0, -52.0 * delta)
		if float(ft["elapsed_s"]) >= float(ft["duration_s"]):
			floating_texts.remove_at(i)


func _trigger_slot_single_hit_anim(slot: Dictionary) -> void:
	slot["action_clip"] = ""
	slot["action_timer_s"] = 0.0
	var mnode := slot.get("node") as Node2D
	if mnode == null or not is_instance_valid(mnode):
		return
	if mnode.get("_turn_pending") != null:
		mnode.set("_turn_pending", false)
		mnode.set("_turn_clip", &"")
		if mnode.has_meta("_arena_turn_resume_clip"):
			mnode.set_meta("_arena_turn_resume_clip", "")
	var spr := mnode.get_node_or_null("Sprite") as AnimatedSprite2D
	if spr == null or spr.sprite_frames == null or not spr.sprite_frames.has_animation(&"hit"):
		return
	arena.call("_play_fighter_clip", mnode, "hit")
	spr.frame = 0
	spr.frame_progress = 0.0
	spr.play(&"hit")
	var hit_dur := float(arena.call("_get_clip_duration_s", mnode, "hit"))
	slot["hit_anim_timer_s"] = maxf(0.18, hit_dur)


func apply_damage_to_slot(slot: Dictionary, dmg: float, stamina_dmg: float = STAMINA_PER_HIT, hit_pos: Vector2 = Vector2(-99999.0, -99999.0), hit_kind: String = "melee", spawn_power_explosion: bool = false, impact_dir: Vector2 = Vector2.RIGHT, attacker_id: String = "local") -> void:
	if slot.is_empty() or not bool(slot.get("alive", false)):
		return
	if bool(slot.get("is_remote_player", false)) and not is_remote_player_hostile(slot):
		return
	if network_authoritative and bool(slot.get("is_remote_player", false)):
		var rfx_pos := hit_pos if hit_pos.x > -90000.0 else _get_slot_core_pos(slot)
		slot["hit_flash_s"] = 0.16
		slot["hit_shake_s"] = 0.10 * HIT_SHAKE_SCALE_MUL
		if spawn_power_explosion:
			_spawn_powerup_explosion(rfx_pos, DEFAULT_EXPLOSION_SCALE)
		_spawn_hit_impact_fx(rfx_pos, hit_kind, "", Color(0.40, 0.94, 1.0, 1.0), impact_dir)
		return
	var fx_pos := hit_pos if hit_pos.x > -90000.0 else _get_slot_core_pos(slot)
	var dmg_lbl := "-%d%s" % [int(round(dmg)), "!" if hit_kind == "skill" else ""]
	var dmg_col := Color(0.40, 0.94, 1.0, 1.0) if hit_kind == "skill" else (Color(1.0, 0.56, 0.22, 1.0) if hit_kind == "heavy" else Color(1.0, 0.92, 0.28, 1.0))
	slot["hit_flash_s"] = 0.16
	slot["hit_shake_s"] = 0.14 * HIT_SHAKE_SCALE_MUL
	slot["provoked_timer_s"] = MONSTER_PROVOKED_DURATION_S
	# v6 T8: Attacking a monster activates its Combat state (stays Combat until KO; Boss is always Combat)
	slot["combat_state"] = "combat"
	if not attacker_id.is_empty():
		slot["aggro_target_id"] = attacker_id
	if spawn_power_explosion:
		_spawn_powerup_explosion(fx_pos, DEFAULT_EXPLOSION_SCALE)

	slot["hp"] = maxf(0.0, float(slot["hp"]) - dmg)
	if float(slot["hp"]) <= 0.0:
		_spawn_hit_impact_fx(fx_pos, hit_kind, dmg_lbl, dmg_col, impact_dir)
		_kill_slot_monster(slot)
		return
	var broke_stun := false
	var prev_stam := float(slot["stamina"])
	if float(slot["stun_timer_s"]) <= 0.0 and prev_stam > 0.0:
		slot["stamina"] = maxf(0.0, prev_stam - stamina_dmg)
		if float(slot["stamina"]) <= 0.0:
			# Break white stamina -> 3s attack-lock window + flashing shield-break icon + 1 HIT clip!
			broke_stun = true
			slot["stun_timer_s"] = MINI_STUN_DURATION_S
			slot["shield_break_icon_timer_s"] = SHIELD_BREAK_ICON_DURATION_S
			_trigger_slot_single_hit_anim(slot)
	elif float(slot["stun_timer_s"]) > 0.0:
		# Broken stamina window active: 1 incoming hit = 1 HIT clip (0 hits when unattacked).
		_trigger_slot_single_hit_anim(slot)
	if broke_stun:
		var stun_kind := hit_kind if (hit_kind == "melee" or hit_kind == "heavy") else "stun"
		_spawn_hit_impact_fx(fx_pos, stun_kind, "%s CHOÁNG!" % dmg_lbl, Color(1.0, 0.68, 0.15, 1.0), impact_dir, str(arena.active_character_id) if arena != null else "")
	else:
		_spawn_hit_impact_fx(fx_pos, hit_kind, dmg_lbl, dmg_col, impact_dir, str(arena.active_character_id) if arena != null else "")


func set_player_immortal(enabled: bool) -> void:
	player_immortal = enabled
	if player_immortal and player_spawned and player_dead:
		player_dead = false
		player_respawn_timer_s = 0.0
		player_hp = player_max_hp
		if arena != null and arena.player_node != null:
			arena.call("_play_fighter_clip", arena.player_node, "idle")
	elif player_immortal and player_spawned and player_hp <= 0.0:
		player_hp = player_max_hp
	player_state_changed.emit()


func apply_damage_to_player(dmg: float, hit_pos: Vector2 = Vector2(-99999.0, -99999.0), spawn_power_explosion: bool = false, hit_kind: String = "player_hit", impact_dir: Vector2 = Vector2.RIGHT, attacker_cid: String = "") -> void:
	if not player_spawned or player_dead:
		return
	# Invulnerable during `transform_ssj` animation through completion (Owner rule 2026-11-20)!
	if arena != null and arena.player_node != null and arena.player_node.has_method(&"is_transform_invulnerable") and bool(arena.player_node.call(&"is_transform_invulnerable")):
		return
	# Protective Barrier `LOOP 10S` (05): blocks 100% incoming damage while Goku moves/attacks freely!
	if arena != null and arena.player_node != null and arena.player_node.has_method(&"is_barrier_active") and bool(arena.player_node.call(&"is_barrier_active")):
		var b_pos := hit_pos if hit_pos.x > -90000.0 else _get_player_core_pos()
		floating_texts.append({
			"pos": b_pos + Vector2(0.0, -24.0),
			"text": "KHIÊN CHẶN!",
			"color": Color(1.0, 0.92, 0.24, 1.0),
			"elapsed_s": 0.0,
			"duration_s": 0.55,
		})
		return
	if player_immortal:
		return
	var fx_pos := hit_pos if hit_pos.x > -90000.0 else _get_player_core_pos()
	var genki_cc_immune: bool = (arena != null and arena.player_node != null and arena.player_node.has_method(&"is_genki_cc_immune") and bool(arena.player_node.call(&"is_genki_cc_immune")))
	player_hit_flash_s = 0.19
	player_hit_shake_s = 0.09 * HIT_SHAKE_SCALE_MUL
	var armor_broke_now := false
	var already_armor_broken := player_armor_broken_timer_s > 0.0
	var prev_armor := player_armor
	if (not genki_cc_immune) and prev_armor > 0.0 and not already_armor_broken:
		var armor_dmg := PLAYER_ARMOR_DMG_PER_HIT
		if hit_kind == "heavy" or hit_kind == "skill":
			armor_dmg = 35.0
		elif hit_kind == "armor_break" or hit_kind == "stun":
			armor_dmg = player_armor
		player_armor = maxf(0.0, player_armor - armor_dmg)
		if player_armor <= 0.0:
			armor_broke_now = true
			player_armor_broken_timer_s = PLAYER_ARMOR_BREAK_STUN_S
			player_shield_break_icon_timer_s = SHIELD_BREAK_ICON_DURATION_S
	var dmg_txt := "-%d VỠ GIÁP!" % int(round(dmg)) if armor_broke_now else "-%d" % int(round(dmg))
	var dmg_col := Color(1.0, 0.68, 0.15, 1.0) if armor_broke_now else Color(1.0, 0.28, 0.28, 1.0)
	_spawn_hit_impact_fx(fx_pos, hit_kind, dmg_txt, dmg_col, impact_dir, attacker_cid)
	if spawn_power_explosion:
		_spawn_powerup_explosion(fx_pos, DEFAULT_EXPLOSION_SCALE)
	# Any incoming attack transitions Son Goku Peace -> Combat AND auto-activates SSJ1 if currently Base (Owner v6 T3)!
	var auto_transformed_now := false
	if arena != null and arena.player_node != null and _is_hero_songoku_node(arena.player_node):
		var entered_combat := bool(arena.player_node.call(&"enter_combat"))
		if entered_combat:
			if arena.has_method(&"trigger_combat_state_banner"):
				arena.call(&"trigger_combat_state_banner")
		if not bool(arena.player_node.get("is_ssj")):
			if arena.has_method(&"_trigger_songoku_auto_transform_on_hit"):
				arena.call(&"_trigger_songoku_auto_transform_on_hit")
				auto_transformed_now = true
		elif entered_combat and not genki_cc_immune and not armor_broke_now and not already_armor_broken and not bool(arena.call("_is_player_action_playing")):
			arena.call("_play_fighter_clip", arena.player_node, "combat_enter")
	player_hp = maxf(0.0, player_hp - dmg)
	_local_hp_grace_s = 0.45
	if player_hp <= 0.0:
		player_dead = true
		player_respawn_timer_s = RESPAWN_PLAYER_DELAY_S
		_player_melee_pending = false
		_player_gold_slash_pending = false
		_player_power_pending = false
		cancel_auto_approach()
		cancel_genki_on_player_death()
		# Tapion death clears all Ấn ngục & Kentai stacks on targets in map!
		clear_all_tapion_marks()
		if arena.player_node != null:
			if arena.player_node.has_method(&"cancel_antamina_interrupt"):
				arena.player_node.call(&"cancel_antamina_interrupt")
			if arena.player_node.has_method(&"reset_combo"):
				arena.player_node.call(&"reset_combo")
			if _is_hero_songoku_node(arena.player_node):
				arena.player_node.set("flight_state", "falling")
				arena.player_node.set("hover_timer_s", 0.0)
				arena.player_node.call(&"step_combat_move_frame", 0.0, 0)
			var kspr := arena.player_node.get_node_or_null("Sprite") as AnimatedSprite2D
			if kspr != null:
				kspr.position.y = 0.0
			if arena.player_node.has_meta(&"_arena_queued_action"):
				arena.player_node.remove_meta(&"_arena_queued_action")
			arena.call("_play_fighter_clip", arena.player_node, "ko")
	elif (not genki_cc_immune) and (armor_broke_now or already_armor_broken) and not auto_transformed_now:
		# Broken-armor HIT reaction replays 1:1 in parallel with EVERY incoming hit while armor is broken (Owner 2026-11-26)!
		# Also cancels Tapion's active Antamina channel WITHOUT losing any target's "Ấn ngục" stacks!
		if arena != null and arena.player_node != null and _is_hero_songoku_node(arena.player_node):
			if arena.player_node.has_method(&"cancel_antamina_interrupt"):
				arena.player_node.call(&"cancel_antamina_interrupt")
			if arena.player_node.has_meta(&"_arena_queued_action"):
				arena.player_node.remove_meta(&"_arena_queued_action")
			_player_melee_pending = false
			_player_gold_slash_pending = false
			var hit_dur := float(arena.call("_get_clip_duration_s", arena.player_node, "hit"))
			arena.player_node.set("armor_hit_timer_s", maxf(0.24, hit_dur))
			var hspr := arena.player_node.get_node_or_null("Sprite") as AnimatedSprite2D
			if hspr != null and hspr.sprite_frames != null and hspr.sprite_frames.has_animation(&"hit"):
				arena.call("_play_fighter_clip", arena.player_node, "hit")
				hspr.frame = 0
				hspr.frame_progress = 0.0
				hspr.play(&"hit")
	player_pve_damage_emitted.emit(dmg, player_hp, not player_dead)
	player_state_changed.emit()


func _kill_slot_monster(slot: Dictionary) -> void:
	var is_boss := bool(slot.get("is_boss", false))
	slot["alive"] = false
	slot["stun_timer_s"] = 0.0
	slot["hard_stun_timer_s"] = 0.0
	slot["shield_break_icon_timer_s"] = 0.0
	slot["kentai_timer_s"] = 0.0
	slot["an_nguc_stacks"] = 0
	slot["_local_dead_time_s"] = _sim_time_s
	slot["action_clip"] = ""
	slot["action_timer_s"] = 0.0
	slot["respawn_timer_s"] = BOSS_DRUM_RESPAWN_DELAY_S if is_boss else RESPAWN_MONSTER_DELAY_S
	slot["ko_hide_timer_s"] = 0.75
	if is_boss:
		boss_respawn_timer_s = BOSS_DRUM_RESPAWN_DELAY_S
		boss_spawn_timer_s = 0.0
	if _auto_approach_slot_id == str(slot.get("id", "")):
		cancel_auto_approach()
	var mnode := slot.get("node") as Node2D
	var drop_pos := Vector2(float(slot["x_home"]), float(arena.call("_ground_y_at", float(slot["x_home"]))))
	if mnode != null and is_instance_valid(mnode):
		if mnode.get("_turn_pending") != null:
			mnode.set("_turn_pending", false)
			mnode.set("_turn_clip", &"")
			if mnode.has_meta("_arena_turn_resume_clip"):
				mnode.set_meta("_arena_turn_resume_clip", "")
		drop_pos = mnode.position
		arena.call("_play_fighter_clip", mnode, "ko")
	roll_and_spawn_dragon_ball(drop_pos, -1.0, -1.0, is_boss)
	refresh_pointer_valid()



func roll_dragon_ball_number(gate_roll_0_to_100: float = -1.0, star_roll_0_to_table: float = -1.0, is_boss: bool = false) -> int:
	if is_boss:
		var b_total := 0.0
		for row in BOSS_DROP_TABLE:
			b_total += float(row["weight"])
		var br := randf() * b_total if star_roll_0_to_table < 0.0 else star_roll_0_to_table
		var b_acc := 0.0
		for row in BOSS_DROP_TABLE:
			b_acc += float(row["weight"])
			if br < b_acc:
				return int(row["ball"])
		return int(BOSS_DROP_TABLE[BOSS_DROP_TABLE.size() - 1]["ball"])
	var gate := randf() * 100.0 if gate_roll_0_to_100 < 0.0 else gate_roll_0_to_100
	# First gate: 30% total chance to drop any Dragon Ball item
	if gate >= DRAGON_BALL_TOTAL_DROP_PCT:
		return 0
	# Passed 30% gate -> roll star using existing DRAGON_BALL_DROP_TABLE weights (sum = 67.6)
	var total_w := 0.0
	for row in DRAGON_BALL_DROP_TABLE:
		total_w += float(row["weight"])
	var r := randf() * total_w if star_roll_0_to_table < 0.0 else star_roll_0_to_table
	var acc := 0.0
	for row in DRAGON_BALL_DROP_TABLE:
		acc += float(row["weight"])
		if r < acc:
			return int(row["ball"])
	return int(DRAGON_BALL_DROP_TABLE[DRAGON_BALL_DROP_TABLE.size() - 1]["ball"])


func roll_and_spawn_dragon_ball(world_pos: Vector2, forced_gate_roll: float = -1.0, forced_star_roll: float = -1.0, is_boss: bool = false) -> Node2D:
	var ball_num := roll_dragon_ball_number(forced_gate_roll, forced_star_roll, is_boss)
	if ball_num <= 0:
		return null
	arena.item_drop_enabled = true
	arena.call("_sync_item_toggle_button")
	var layer: Node2D = arena.call("_ensure_item_drop_layer")
	layer.z_index = 45 # Above FightersLayer (10) & Boss (40), below Shenron (52) & FieldOverlayLayer (65)
	var floor_y := float(arena.call("_ground_y_at", world_pos.x))
	var px: float = arena.player_node.position.x if arena.player_node != null else world_pos.x - 40.0
	var roll_dir := -1.0 if px <= world_pos.x else 1.0
	var item := arena.DragonBallItemScene.instantiate() as Node2D
	item.set("ball_number", ball_num)
	item.set("ground_y_resolver", Callable(arena, "_ground_y_at"))
	item.z_index = 0
	item.set_meta(&"drop_age_s", 0.0)
	if item.has_signal("collected"):
		item.connect("collected", arena._on_dropped_item_collected)
	layer.add_child(item)
	item.call("start_drop_from", world_pos, floor_y, roll_dir, arena.item_drop_scale)
	arena._dropped_item_nodes.append(item)
	return item


func _can_pickup_item(item_n: Node2D) -> bool:
	if item_n == null or not is_instance_valid(item_n) or not item_n.visible:
		return false
	var st := str(item_n.get("lifecycle_state"))
	if st == "collecting" or st == "collected" or st == "bag":
		return false
	return float(item_n.get_meta(&"drop_age_s", 1.0)) >= ITEM_PICKUP_UNLOCK_S


func _collect_single_item(item_n: Node2D) -> bool:
	if arena.player_node == null or not _can_pickup_item(item_n):
		return false
	var p_entry: Dictionary = arena.call("_find_character_entry_ro", arena.active_character_id)
	var dims: Vector2i = arena.call("_get_body_dims", p_entry)
	var center_off_y := -maxf(28.0, float(dims.y) * arena.char_scale * 0.5)
	return bool(item_n.call("start_collect", arena.player_node, center_off_y, arena.player_node.position + Vector2(0.0, center_off_y)))


func _step_slot(slot: Dictionary, delta: float) -> void:
	var mnode := slot.get("node") as Node2D
	if not bool(slot["alive"]):
		if mnode != null and is_instance_valid(mnode):
			var hide_t := float(slot["ko_hide_timer_s"]) - delta
			slot["ko_hide_timer_s"] = hide_t
			if hide_t <= 0.0:
				mnode.visible = false
		if bool(slot.get("is_boss", false)):
			return
		# In authoritative online sessions, server controls monster respawn ONLY while WSS connection is live.
		# If connection dropped on a downloaded client, fall back cleanly to local respawn timer so monsters never stay dead forever!
		if network_authoritative and _is_authoritative_network_connected():
			return
		slot["respawn_timer_s"] = float(slot["respawn_timer_s"]) - delta
		if float(slot["respawn_timer_s"]) <= 0.0:
			var next_cid := ""
			if bool(slot["is_flying"]):
				next_cid = FLYING_ROTATION[_flying_rotation_idx % FLYING_ROTATION.size()]
				_flying_rotation_idx += 1
			else:
				slot["respawn_toggle"] = not bool(slot["respawn_toggle"])
				next_cid = "dilophosaurus" if bool(slot["respawn_toggle"]) else str(slot["native_cid"])
			_spawn_slot_monster(slot, next_cid)
		return

	if mnode == null or not is_instance_valid(mnode):
		return

	# Hard Stun (e.g. Flurry Kick `26`): applies to ALL bosses, monsters, and heroes!
	# Locks AI/movement/attacks, holds continuous `hit` pose, and renders golden rotating stun stars ring overhead.
	if float(slot.get("hard_stun_timer_s", 0.0)) > 0.0:
		slot["hard_stun_timer_s"] = maxf(0.0, float(slot.get("hard_stun_timer_s", 0.0)) - delta)
		slot["action_clip"] = ""
		slot["action_timer_s"] = 0.0
		var st_spr := mnode.get_node_or_null("Sprite") as AnimatedSprite2D
		if st_spr != null and st_spr.sprite_frames != null and st_spr.sprite_frames.has_animation(&"hit"):
			if String(st_spr.animation) != "hit" or not st_spr.is_playing():
				st_spr.play(&"hit")
		_step_slot_vertical(slot, delta)
		if float(slot.get("hard_stun_timer_s", 0.0)) <= 0.0:
			arena.call("_ensure_fighter_locomotion", mnode, "idle", bool(slot["preserve_phase"]))
		return

	# Broken-stamina attack-lock (3.0s) + single HIT clip per incoming damage (1 hit = 1 hit anim, normal movement when unattacked)
	if float(slot["stun_timer_s"]) > 0.0:
		slot["stun_timer_s"] = maxf(0.0, float(slot["stun_timer_s"]) - delta)
		if float(slot["stun_timer_s"]) <= 0.0:
			slot["stamina"] = float(slot["max_stamina"])

	if float(slot.get("hit_anim_timer_s", 0.0)) > 0.0:
		slot["hit_anim_timer_s"] = maxf(0.0, float(slot.get("hit_anim_timer_s", 0.0)) - delta)
		if float(slot["hit_anim_timer_s"]) > 0.0:
			_step_slot_vertical(slot, delta)
			return
		arena.call("_ensure_fighter_locomotion", mnode, "idle", bool(slot["preserve_phase"]))

	var can_counter_attack := float(slot["stun_timer_s"]) <= 0.0

	slot["cooldown_s"] = maxf(0.0, float(slot["cooldown_s"]) - delta)
	slot["turn_boost_s"] = maxf(0.0, float(slot["turn_boost_s"]) - delta)
	slot["turn_lock_s"] = maxf(0.0, float(slot["turn_lock_s"]) - delta)
	if float(slot.get("provoked_timer_s", 0.0)) > 0.0:
		slot["provoked_timer_s"] = maxf(0.0, float(slot.get("provoked_timer_s", 0.0)) - delta)
	if float(slot["action_timer_s"]) > 0.0:
		slot["action_timer_s"] = maxf(0.0, float(slot["action_timer_s"]) - delta)
	var spr := mnode.get_node_or_null("Sprite") as AnimatedSprite2D
	var turn_pending := bool(arena.call("_is_fighter_turning", mnode))
	if not turn_pending and not str(slot["action_clip"]).is_empty():
		var finished_early := spr != null and (String(spr.animation) != str(slot["action_clip"]) or not spr.is_playing())
		var expired := float(slot["action_timer_s"]) <= 0.0 or finished_early
		_step_slot_action_effects(slot, spr, expired)
		if expired:
			slot["action_clip"] = ""
			slot["action_timer_s"] = 0.0
			var comm_id := str(slot.get("committed_target_id", ""))
			slot["committed_target_id"] = ""
			var fled_arr: Array = slot.get("fled_attackers", [])
			if not comm_id.is_empty() and fled_arr.has(comm_id):
				fled_arr.erase(comm_id)
				if str(slot.get("aggro_target_id", "")) == comm_id:
					slot["aggro_target_id"] = ""

	if turn_pending or not str(slot["action_clip"]).is_empty():
		_step_slot_vertical(slot, delta)
		return

	if bool(slot.get("is_boss", false)):
		_step_boss_drum_ai(slot, delta)
		_step_slot_vertical(slot, delta)
		return

	var has_target := _is_player_in_slot_aggro(slot)
	if not has_target:
		if bool(slot["is_flying"]):
			_step_flying_orbit(slot, delta, false)
		else:
			_step_slot_patrol(slot, delta)
			_step_slot_vertical(slot, delta)
		return

	# Aggro behavior toward Player (Drum): deadband + turn_lock_s prevents rapid left/right flipping in place
	var px: float = arena.player_node.position.x
	var dx_to_player := px - mnode.position.x
	if absf(dx_to_player) > 26.0 and float(slot["turn_lock_s"]) <= 0.0:
		var desired_left: bool = dx_to_player < 0.0
		if not bool(slot["sideways_locked"]) and (mnode.scale.x < 0.0) != desired_left:
			_face_slot_toward(slot, desired_left)
			_step_slot_vertical(slot, delta)
			return

	var edge_gap := _compute_slot_edge_gap(slot)
	var cid := str(slot["character_id"])
	var is_fly := bool(slot["is_flying"])
	var dy_to_player := absf(arena.player_node.position.y - mnode.position.y)

	if cid == "chilopoda":
		var burrow := edge_gap >= float(arena.ai_controller.close_edge_px)
		if can_counter_attack and float(slot["cooldown_s"]) <= 0.0:
			_start_slot_attack(slot, str(slot["light_clip"]) if burrow else "power_up", 0.95 if burrow else 1.45)
		else:
			arena.call("_ensure_fighter_locomotion", mnode, "idle", bool(slot["preserve_phase"]))
	elif edge_gap <= 50.0 and dy_to_player <= 110.0:
		if can_counter_attack and float(slot["cooldown_s"]) <= 0.0:
			var use_heavy := bool(slot["has_heavy"]) and int(slot["light_chain"]) >= 2
			var clip := "attack_heavy" if use_heavy else str(slot["light_clip"])
			slot["light_chain"] = 0 if use_heavy else (int(slot["light_chain"]) + 1)
			_start_slot_attack(slot, clip, 0.95)
		else:
			arena.call("_ensure_fighter_locomotion", mnode, "idle", bool(slot["preserve_phase"]))
	elif is_fly:
		# Flying monsters stay aloft, cruise in smooth circular/elliptical orbits (without flipping against player facing), and fire downward
		var fx_clip := "attack_light" if cid == "floating_camera" else ("power_up" if bool(slot["has_power_up"]) else str(slot["light_clip"]))
		if can_counter_attack and float(slot["cooldown_s"]) <= 0.0:
			_start_slot_attack(slot, fx_clip, 1.35)
		else:
			_step_flying_orbit(slot, delta, true)
		return
	else:
		# Ground monster: outer aggro >= 200px OR player hovering directly overhead uses power_up anti-air!
		if can_counter_attack and (edge_gap >= 200.0 or dy_to_player > 110.0) and bool(slot["has_power_up"]):
			if float(slot["cooldown_s"]) <= 0.0:
				_start_slot_attack(slot, "power_up", 1.45)
			else:
				arena.call("_ensure_fighter_locomotion", mnode, "idle", bool(slot["preserve_phase"]))
		elif edge_gap > 50.0:
			var move_dir := -1 if px < mnode.position.x else 1
			var entry: Dictionary = arena.call("_find_character_entry_ro", cid)
			var spd := float(arena.call("_get_walk_speed_px_per_s", entry, float(slot["scale_val"])))
			var dims: Vector2i = arena.call("_get_body_dims", entry)
			arena.call("_move_node_horizontal", mnode, float(move_dir) * spd * delta, false, float(slot["zone_min_x"]), float(slot["zone_max_x"]), float(dims.x) * float(slot["scale_val"]) * 0.5)
			arena.call("_ensure_fighter_locomotion", mnode, str(slot["locomotion_clip"]), bool(slot["preserve_phase"]))
		else:
			arena.call("_ensure_fighter_locomotion", mnode, "idle", bool(slot["preserve_phase"]))

	_step_slot_vertical(slot, delta)


func _step_slot_patrol(slot: Dictionary, delta: float) -> void:
	var mnode := slot["node"] as Node2D
	if float(slot["patrol_pause_s"]) > 0.0:
		slot["patrol_pause_s"] = maxf(0.0, float(slot["patrol_pause_s"]) - delta)
		arena.call("_ensure_fighter_locomotion", mnode, "idle", bool(slot["preserve_phase"]))
		return
	var pmin := maxf(float(slot["zone_min_x"]) + 60.0, float(slot["x_home"]) - 180.0)
	var pmax := minf(float(slot["zone_max_x"]) - 60.0, float(slot["x_home"]) + 180.0)
	if pmax <= pmin:
		arena.call("_ensure_fighter_locomotion", mnode, "idle", bool(slot["preserve_phase"]))
		return
	var pdir := int(slot["patrol_dir"])
	var cid := str(slot["character_id"])
	var entry: Dictionary = arena.call("_find_character_entry_ro", cid)
	var spd := float(arena.call("_get_walk_speed_px_per_s", entry, float(slot["scale_val"]))) * 0.72
	var dims: Vector2i = arena.call("_get_body_dims", entry)
	var want_left := pdir < 0
	if not bool(slot["sideways_locked"]) and (mnode.scale.x < 0.0) != want_left:
		_face_slot_toward(slot, want_left)
		return
	arena.call("_move_node_horizontal", mnode, float(pdir) * spd * delta, bool(slot["is_flying"]), pmin, pmax, float(dims.x) * float(slot["scale_val"]) * 0.5)
	arena.call("_ensure_fighter_locomotion", mnode, str(slot["locomotion_clip"]), bool(slot["preserve_phase"]))
	if pdir > 0 and mnode.position.x >= pmax - 2.0:
		slot["patrol_dir"] = -1
		slot["patrol_pause_s"] = 0.75
	elif pdir < 0 and mnode.position.x <= pmin + 2.0:
		slot["patrol_dir"] = 1
		slot["patrol_pause_s"] = 0.75


func _step_flying_orbit(slot: Dictionary, delta: float, lock_facing_to_target: bool) -> void:
	var mnode := slot["node"] as Node2D
	var cid := str(slot["character_id"])
	var entry: Dictionary = arena.call("_find_character_entry_ro", cid)
	var spd := float(arena.call("_get_walk_speed_px_per_s", entry, float(slot["scale_val"])))
	var dims: Vector2i = arena.call("_get_body_dims", entry)
	var half_w := float(dims.x) * float(slot["scale_val"]) * 0.5
	var zmin := float(slot["zone_min_x"]) + maxf(60.0, half_w)
	var zmax := float(slot["zone_max_x"]) - maxf(60.0, half_w)
	var rx := clampf((zmax - zmin) * 0.34, 90.0, 220.0)
	var ry := 52.0
	var cx := clampf(float(slot["x_home"]), zmin, zmax)
	var cy := float(slot["y_home"])

	var angular_spd := clampf(spd / maxf(110.0, rx), 0.7, 1.55) * float(slot.get("orbit_dir", 1.0))
	var phase := fmod(float(slot.get("orbit_phase", 0.0)) + angular_spd * delta, TAU)
	slot["orbit_phase"] = phase

	var desired_x := clampf(cx + cos(phase) * rx, zmin, zmax)
	var desired_y := clampf(cy + sin(phase) * ry, float(arena.fly_min_y) + 28.0, cy + 56.0)
	var step_vec := Vector2(desired_x - mnode.position.x, desired_y - mnode.position.y)
	var max_step := maxf(120.0, spd * 1.15) * delta
	if step_vec.length() > max_step:
		step_vec = step_vec.normalized() * max_step

	if not lock_facing_to_target and not bool(slot["sideways_locked"]) and float(slot["turn_lock_s"]) <= 0.0:
		var vel_x := -sin(phase) * angular_spd * rx
		if absf(vel_x) > 12.0:
			var want_left := vel_x < 0.0
			if (mnode.scale.x < 0.0) != want_left:
				_face_slot_toward(slot, want_left)
				return

	arena.call("_move_node_horizontal", mnode, step_vec.x, true, float(slot["zone_min_x"]), float(slot["zone_max_x"]), half_w)
	mnode.position.y = clampf(mnode.position.y + step_vec.y, float(arena.fly_min_y), cy + 60.0)
	slot["vy"] = 0.0
	arena.call("_ensure_fighter_locomotion", mnode, str(slot["locomotion_clip"]), bool(slot["preserve_phase"]))


func _face_slot_toward(slot: Dictionary, want_left: bool) -> void:
	var mnode := slot["node"] as Node2D
	if (mnode.scale.x < 0.0) == want_left:
		return
	var sc := float(slot["scale_val"])
	slot["turn_lock_s"] = 0.42
	if bool(slot.get("has_turn_clip", false)) and mnode.has_method(&"set_facing_left"):
		mnode.set_meta("_arena_turn_resume_clip", str(slot["locomotion_clip"]))
		if bool(mnode.call(&"set_facing_left", want_left)):
			slot["facing_left"] = want_left
			return
	slot["facing_left"] = want_left
	mnode.scale = Vector2(-sc if want_left else sc, sc)


func _get_clamped_slot_target_pos(slot: Dictionary) -> Vector2:
	if arena == null or arena.player_node == null:
		return Vector2(float(slot.get("x_home", 0.0)), float(slot.get("y_home", 840.0)))
	var tx := clampf(arena.player_node.position.x, float(slot.get("zone_min_x", -240.0)), float(slot.get("zone_max_x", 6360.0)))
	var ty := float(arena.call("_ground_y_at", tx))
	return Vector2(tx, ty)


func _start_slot_attack(slot: Dictionary, clip: String, cd_s: float) -> void:
	var mnode := slot["node"] as Node2D
	var cid := str(slot["character_id"])
	if cid == "chilopoda" and mnode.has_method(&"set_combat_target_global") and arena.player_node != null:
		mnode.call(&"set_combat_target_global", _get_clamped_slot_target_pos(slot))
	elif cid == "dilophosaurus" and mnode.has_method(&"set_slash_target_global") and arena.player_node != null:
		mnode.call(&"set_slash_target_global", arena.player_node.position)
	if bool(arena.call("_play_fighter_clip", mnode, clip)):
		slot["action_clip"] = clip
		slot["action_timer_s"] = float(arena.call("_get_clip_duration_s", mnode, clip))
		slot["cooldown_s"] = cd_s
		slot["power_released"] = false
		slot["melee_hit_done"] = false
		slot["teleport_relocated"] = false
		slot["committed_target_id"] = str(slot.get("aggro_target_id", "local"))


func _step_slot_action_effects(slot: Dictionary, spr: AnimatedSprite2D, force_resolve: bool = false) -> void:
	var mnode := slot["node"] as Node2D
	var cid := str(slot["character_id"])
	var clip := str(slot["action_clip"])
	var st: Dictionary = _get_slot_stats(slot)
	if clip == "teleport":
		if not bool(slot.get("teleport_relocated", false)):
			var mid_reached := force_resolve or float(slot["action_timer_s"]) <= 0.17 or (spr != null and String(spr.animation) == "teleport" and spr.frame >= 2)
			if mid_reached:
				_execute_boss_teleport_relocation(slot)
				slot["teleport_relocated"] = true
		return
	if cid == "dilophosaurus" and clip == "power_up" and mnode.has_method(&"set_slash_target_global") and arena.player_node != null:
		mnode.call(&"set_slash_target_global", _get_player_core_pos())
	elif cid == "chilopoda" and clip == "power_up" and mnode.has_method(&"set_combat_target_global") and arena.player_node != null:
		mnode.call(&"set_combat_target_global", _get_clamped_slot_target_pos(slot))
	elif cid == "chilopoda" and clip == "attack_light":
		mnode.position.x = clampf(mnode.position.x, float(slot["zone_min_x"]), float(slot["zone_max_x"]))
		mnode.position.y = float(arena.call("_ground_y_at", mnode.position.x))
	var is_ranged_power := (clip == "power_up") or (cid == "floating_camera" and clip == "attack_light")
	if is_ranged_power and not bool(slot["power_released"]):
		var rel_frame := 2
		if cid == "chilopoda" or cid == "dilophosaurus":
			rel_frame = 3
		elif cid == "floating_camera":
			rel_frame = 1
		elif cid == "drum":
			rel_frame = 10
		if force_resolve or (spr != null and spr.frame >= rel_frame):
			slot["power_released"] = true
			if cid == "dilophosaurus":
				if arena.player_node != null and player_spawned and not player_dead:
					var m_core := _get_slot_core_pos(slot)
					var p_core := _get_player_core_pos()
					var blocked := bool(arena.call("terrain_blocks_segment", m_core, p_core))
					if not blocked and m_core.distance_to(p_core) <= 720.0:
						# Dilophosaurus keeps its dedicated 3-slash target FX without spawning the default explosion.
						apply_damage_to_player(float(st.get("power_dmg", 100.0)), p_core, false)
			else:
				_spawn_slot_homing_power(slot, float(st.get("power_dmg", 100.0)))
	elif clip in ["attack_light", "attack_heavy", "attack_nomal"] and not bool(slot["melee_hit_done"]):
		var melee_frame := 11 if cid == "chilopoda" else 2
		if force_resolve or (spr != null and spr.frame >= melee_frame):
			slot["melee_hit_done"] = true
			var p_rect := _get_player_body_rect()
			var m_rect := _get_slot_body_rect(slot)
			var edge := _compute_slot_edge_gap(slot)
			var v_gap := maxf(0.0, maxf(p_rect.position.y - m_rect.end.y, m_rect.position.y - p_rect.end.y))
			if edge <= 85.0 and arena.player_node != null and v_gap <= 95.0:
				var is_heavy := clip == "attack_heavy"
				var dmg := float(st.get("heavy_dmg", 70.0)) if is_heavy else float(st.get("light_dmg", 50.0))
				var m_core := _get_slot_core_pos(slot)
				var hit_pt: Vector2 = arena.call("compute_nearest_silhouette_point", arena.player_node, arena.active_character_id, arena.char_scale, m_core)
				var hit_dir := (hit_pt - m_core).normalized() if hit_pt.distance_to(m_core) > 1.0 else Vector2(-1.0 if mnode.scale.x < 0.0 else 1.0, 0.0)
				apply_damage_to_player(dmg, hit_pt, false, "heavy" if is_heavy else "melee", hit_dir, cid)


func _spawn_slot_homing_power(slot: Dictionary, dmg: float) -> void:
	var mnode := slot["node"] as Node2D
	var cid := str(slot["character_id"])
	var sc := float(slot["scale_val"])
	var dir_x := -1.0 if mnode.scale.x < 0.0 else 1.0
	var fx_clip := _resolve_fx_clip_for_character(cid)
	if fx_clip.is_empty():
		apply_damage_to_player(dmg)
		return
	var start_pos := mnode.position + (Vector2(dir_x * 42.0 * sc, -28.0 * sc) if cid == "drum" else Vector2(dir_x * 46.0 * sc, -48.0 * sc))
	_spawn_homing_projectile(mnode, cid, fx_clip, start_pos, sc, {}, false, dmg, 0.0)


func _resolve_fx_clip_for_character(cid: String) -> String:
	match cid:
		"t_rex", "spinosaurus", "chilopoda":
			return "fireball_fx"
		"tasmanian_king_crab":
			return "power_orb_projectile"
		"sarcosuchus":
			return "energy_blast_fx"
		"bat_chiroptera", "pteranodon":
			return "sonic_screech_fx"
		"floating_camera":
			return "projectile_fx"
		"drum":
			return "electric_orb_fx"
	return ""


func _spawn_homing_projectile(owner_node: Node2D, cid: String, fx_clip: String, start_pos: Vector2, sc: float, target_slot: Dictionary, is_player_attack: bool, dmg: float, stamina_dmg: float) -> void:
	var spr := owner_node.get_node_or_null("Sprite") as AnimatedSprite2D
	if spr == null or spr.sprite_frames == null or not spr.sprite_frames.has_animation(StringName(fx_clip)):
		if is_player_attack:
			apply_damage_to_slot(target_slot, dmg, stamina_dmg)
		else:
			apply_damage_to_player(dmg)
		return
	var entry: Dictionary = arena.call("_find_character_entry_ro", cid)
	var pivot_arr: Variant = entry.get("render_contract", {}).get("fx_pivot_px", [176.0, 128.0])
	var pivot := Vector2(float(pivot_arr[0]), float(pivot_arr[1])) if (pivot_arr is Array and pivot_arr.size() >= 2) else Vector2(64.0, 48.0)

	var cache_key := "%s:%s" % [cid, fx_clip]
	var cached_frames := _fx_frames_cache.get(cache_key) as SpriteFrames
	if cached_frames == null:
		cached_frames = spr.sprite_frames.duplicate() as SpriteFrames
		cached_frames.set_animation_loop(StringName(fx_clip), true)
		_fx_frames_cache[cache_key] = cached_frames
	var fx := AnimatedSprite2D.new()
	fx.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	fx.sprite_frames = cached_frames
	fx.centered = false
	fx.offset = -pivot
	fx.scale = Vector2(sc, sc)
	fx.position = start_pos
	fx.z_index = Z_LAYER_FX
	var parent_layer: Node = arena.fighters_layer if arena.fighters_layer != null else arena
	parent_layer.add_child(fx)
	fx.play(StringName(fx_clip))

	var rotate_sprite := fx_clip not in ["electric_orb_fx", "power_orb_projectile"]
	var speed := DRUM_SKILL_SPEED_PX_S if (is_player_attack or cid == "drum") else MONSTER_SKILL_SPEED_PX_S
	var init_dir := Vector2(1.0, 0.0)
	if is_player_attack and not target_slot.is_empty() and is_instance_valid(target_slot.get("node")):
		var tpos := _get_slot_core_pos(target_slot)
		if tpos.distance_to(start_pos) > 1.0:
			init_dir = (tpos - start_pos).normalized()
	elif not is_player_attack and arena.player_node != null:
		var tpos := _get_player_core_pos()
		if tpos.distance_to(start_pos) > 1.0:
			init_dir = (tpos - start_pos).normalized()
	else:
		init_dir = Vector2(-1.0 if owner_node.scale.x < 0.0 else 1.0, 0.0)

	if rotate_sprite:
		fx.rotation = init_dir.angle()
	else:
		fx.scale = Vector2(-sc if init_dir.x < 0.0 else sc, sc)

	homing_projectiles.append({
		"sprite": fx,
		"is_player": is_player_attack,
		"target_slot_id": str(target_slot.get("id", "")),
		"damage": dmg,
		"stamina_damage": stamina_dmg,
		"speed": speed,
		"vel": init_dir * speed,
		"rotate_sprite": rotate_sprite,
		"base_scale": sc,
	})


func _step_homing_projectiles(delta: float) -> void:
	# 1. Skill-vs-Skill Clash: Player power_up orb cuts through enemy projectiles with Ki clash spark
	var removed_enemy_indices: Array[int] = []
	for pi in range(homing_projectiles.size()):
		var ppr: Dictionary = homing_projectiles[pi]
		if not bool(ppr.get("is_player", false)):
			continue
		var pfx := ppr.get("sprite") as AnimatedSprite2D
		if pfx == null or not is_instance_valid(pfx):
			continue
		for ei in range(homing_projectiles.size()):
			if ei == pi or removed_enemy_indices.has(ei):
				continue
			var epr: Dictionary = homing_projectiles[ei]
			if bool(epr.get("is_player", false)):
				continue
			var efx := epr.get("sprite") as AnimatedSprite2D
			if efx == null or not is_instance_valid(efx):
				continue
			if pfx.position.distance_to(efx.position) <= 40.0:
				var mid := (pfx.position + efx.position) * 0.5
				_spawn_hit_impact_fx(mid, "clash", "VA CHẠM!", Color(1.0, 0.92, 0.35, 1.0))
				_spawn_powerup_explosion(mid, CLASH_EXPLOSION_SCALE)
				efx.queue_free()
				removed_enemy_indices.append(ei)
	removed_enemy_indices.sort()
	for ri in range(removed_enemy_indices.size() - 1, -1, -1):
		homing_projectiles.remove_at(removed_enemy_indices[ri])

	# 2. Step movement + exact non-box body silhouette impact + terrain wall stop
	for i in range(homing_projectiles.size() - 1, -1, -1):
		var pr: Dictionary = homing_projectiles[i]
		var fx := pr.get("sprite") as AnimatedSprite2D
		if fx == null or not is_instance_valid(fx):
			homing_projectiles.remove_at(i)
			continue
		var tgt_pos := fx.position
		var tgt_node: Node2D = null
		var tgt_cid := ""
		var tgt_sc := 1.0
		var valid_target := false
		var target_slot: Dictionary = {}
		if bool(pr["is_player"]):
			target_slot = _find_slot_by_id(str(pr["target_slot_id"]))
			if not target_slot.is_empty() and can_attack_slot(target_slot):
				tgt_node = target_slot["node"] as Node2D
				tgt_cid = str(target_slot["character_id"])
				tgt_sc = float(target_slot["scale_val"])
				tgt_pos = _get_slot_core_pos(target_slot)
				var fl_y := float(arena.call("_ground_y_at", tgt_pos.x))
				tgt_pos.y = minf(tgt_pos.y, fl_y - 24.0)
				valid_target = true
		else:
			if player_spawned and not player_dead and arena.player_node != null:
				tgt_node = arena.player_node as Node2D
				tgt_cid = str(arena.active_character_id)
				tgt_sc = float(arena.char_scale)
				tgt_pos = _get_player_core_pos()
				valid_target = true

		if not valid_target or tgt_node == null:
			fx.queue_free()
			homing_projectiles.remove_at(i)
			continue

		var to_vec := tgt_pos - fx.position
		var dist := to_vec.length()
		var speed := float(pr["speed"])
		var step_d := speed * delta
		var sc := float(pr["base_scale"])
		var proj_r := 14.0 * clampf(sc * 0.65, 0.7, 1.4)
		var proj_rect := Rect2(fx.position - Vector2(proj_r, proj_r), Vector2(proj_r * 2.0, proj_r * 2.0))
		var hits_sil := bool(arena.call("silhouette_intersects_rect", tgt_node, tgt_cid, tgt_sc, proj_rect))

		if hits_sil or dist <= maxf(16.0, step_d):
			var sil_hit: Vector2 = arena.call("compute_nearest_silhouette_point", tgt_node, tgt_cid, tgt_sc, fx.position)
			if bool(arena.call("terrain_blocks_segment", fx.position, sil_hit)):
				_spawn_hit_impact_fx(fx.position, "melee", "", Color.WHITE)
				_spawn_powerup_explosion(fx.position, CLASH_EXPLOSION_SCALE)
				fx.queue_free()
				homing_projectiles.remove_at(i)
				continue
			if bool(pr["is_player"]):
				_emit_slot_combat_action("power_up", target_slot, fx.position, float(pr["damage"]), 0.45)
				apply_damage_to_slot(target_slot, float(pr["damage"]), float(pr["stamina_damage"]), sil_hit, "skill", true)
			else:
				apply_damage_to_player(float(pr["damage"]), sil_hit, true)
			fx.queue_free()
			homing_projectiles.remove_at(i)
			continue

		# Smooth 360-degree steering arc toward exact body core (tâm thân)
		var vel: Vector2 = pr.get("vel", to_vec.normalized() * speed)
		var cur_dir := vel.normalized() if vel.length_squared() > 0.001 else to_vec.normalized()
		var desired_dir := to_vec / dist
		var ang_diff := cur_dir.angle_to(desired_dir)
		var turn_rate := 18.0 if dist <= 180.0 else 7.2
		var new_dir := cur_dir.rotated(clampf(ang_diff, -turn_rate * delta, turn_rate * delta)).normalized()
		var prev_pos := fx.position
		var next_pos := prev_pos + new_dir * step_d
		if bool(arena.call("terrain_blocks_segment", prev_pos, next_pos)):
			_spawn_hit_impact_fx(prev_pos, "melee", "", Color.WHITE)
			_spawn_powerup_explosion(prev_pos, CLASH_EXPLOSION_SCALE)
			fx.queue_free()
			homing_projectiles.remove_at(i)
			continue
		var sweep_rect := Rect2(
			Vector2(minf(prev_pos.x, next_pos.x), minf(prev_pos.y, next_pos.y)),
			Vector2(absf(next_pos.x - prev_pos.x), absf(next_pos.y - prev_pos.y))
		).grow(proj_r)
		if bool(arena.call("silhouette_intersects_rect", tgt_node, tgt_cid, tgt_sc, sweep_rect)):
			var sil_hit2: Vector2 = arena.call("compute_nearest_silhouette_point", tgt_node, tgt_cid, tgt_sc, next_pos)
			if bool(arena.call("terrain_blocks_segment", prev_pos, sil_hit2)):
				_spawn_hit_impact_fx(prev_pos, "melee", "", Color.WHITE)
				_spawn_powerup_explosion(prev_pos, CLASH_EXPLOSION_SCALE)
				fx.queue_free()
				homing_projectiles.remove_at(i)
				continue
			if bool(pr["is_player"]):
				_emit_slot_combat_action("power_up", target_slot, next_pos, float(pr["damage"]), 0.45)
				apply_damage_to_slot(target_slot, float(pr["damage"]), float(pr["stamina_damage"]), sil_hit2, "skill", true)
			else:
				apply_damage_to_player(float(pr["damage"]), sil_hit2, true)
			fx.queue_free()
			homing_projectiles.remove_at(i)
			continue

		pr["vel"] = new_dir * speed
		fx.position = next_pos
		if bool(pr.get("rotate_sprite", true)):
			fx.scale = Vector2(sc, sc)
			fx.rotation = new_dir.angle()
		else:
			fx.rotation = 0.0
			fx.scale = Vector2(-sc if new_dir.x < 0.0 else sc, sc)


func _step_slot_vertical(slot: Dictionary, delta: float) -> void:
	var mnode := slot.get("node") as Node2D
	if mnode == null or not is_instance_valid(mnode):
		return
	if bool(slot["is_flying"]):
		# Flying monsters stay restricted in the air (y_home ± 30), never dropping to ground
		mnode.position.y = clampf(mnode.position.y, float(arena.fly_min_y), float(slot["y_home"]) + 40.0)
		slot["vy"] = 0.0
		return
	var floor_y := float(arena.call("_ground_y_at", mnode.position.x))
	var vy := float(slot["vy"])
	if mnode.position.y < floor_y - 0.5 or vy < 0.0:
		vy = float(arena.gravity_px_per_s2) * delta if vy == 0.0 else (vy + float(arena.gravity_px_per_s2) * delta)
		var dy_step := maxf(2.0, vy * delta) if vy >= 0.0 else (vy * delta)
		mnode.position.y = minf(floor_y, mnode.position.y + dy_step)
		slot["vy"] = vy
	else:
		mnode.position.y = floor_y
		slot["vy"] = 0.0


func notify_attacker_fled(attacker_id: String) -> void:
	## v6 T8 Handoff Rule:
	## If another player (`attacker_id`) provoked a monster and fled/switched scenes:
	## - If the monster already committed an attack turn against `attacker_id`, it finishes that 1 turn first.
	## - Once finished (or immediately if idle), `aggro_target_id` clears while `combat_state` stays "combat",
	##   so any Hero walking past that already-provoked monster is automatically attacked!
	if attacker_id.is_empty():
		return
	for s in slots:
		if not bool(s.get("alive", false)) or str(s.get("combat_state", "peace")) != "combat":
			continue
		if str(s.get("aggro_target_id", "")) != attacker_id and str(s.get("committed_target_id", "")) != attacker_id:
			continue
		var in_committed_turn := (not str(s.get("action_clip", "")).is_empty()) and (str(s.get("committed_target_id", "")) == attacker_id)
		if in_committed_turn:
			var fled_arr: Array = s.get("fled_attackers", [])
			if not fled_arr.has(attacker_id):
				fled_arr.append(attacker_id)
				s["fled_attackers"] = fled_arr
		else:
			if str(s.get("aggro_target_id", "")) == attacker_id:
				s["aggro_target_id"] = ""


func _is_player_in_slot_aggro(slot: Dictionary) -> bool:
	if not player_spawned or player_dead or arena.player_node == null:
		return false
	# v6 T8: Normal monsters start in "peace" and NEVER attack unless provoked into "combat" (Boss is always "combat")!
	var is_boss := bool(slot.get("is_boss", false))
	if not is_boss and str(slot.get("combat_state", "peace")) != "combat":
		return false
	# If monster is currently locked onto a different active attacker (who hasn't finished fleeing yet), hold off on local hero
	var aggro_id := str(slot.get("aggro_target_id", ""))
	if not is_boss and not aggro_id.is_empty() and aggro_id != "local":
		return false
	var px: float = arena.player_node.position.x
	var py: float = arena.player_node.position.y
	var mnode := slot.get("node") as Node2D
	if mnode != null and is_instance_valid(mnode) and float(slot.get("provoked_timer_s", 0.0)) > 0.0:
		if absf(px - mnode.position.x) <= 920.0:
			return true
	if px < float(slot["zone_min_x"]) or px > float(slot["zone_max_x"]):
		return false
	if bool(slot["is_flying"]):
		return py <= float(arena.call("_ground_y_at", px)) + 40.0
	var my := mnode.position.y if (mnode != null and is_instance_valid(mnode)) else float(slot.get("y_home", 840.0))
	return absf(py - my) <= 220.0


func _get_player_body_rect() -> Rect2:
	if arena == null or arena.player_node == null or not is_instance_valid(arena.player_node):
		return Rect2()
	return arena.call("get_fighter_body_rect", arena.player_node, arena.active_character_id, arena.char_scale) as Rect2


func _get_slot_body_rect(slot: Dictionary) -> Rect2:
	if arena == null or slot.is_empty():
		return Rect2()
	var mnode := slot.get("node") as Node2D
	if mnode == null or not is_instance_valid(mnode):
		return Rect2()
	return arena.call("get_fighter_body_rect", mnode, str(slot["character_id"]), float(slot["scale_val"])) as Rect2


func _get_player_core_pos() -> Vector2:
	if arena == null or arena.player_node == null or not is_instance_valid(arena.player_node):
		return Vector2.ZERO
	return arena.call("get_fighter_core_world_pos", arena.player_node, arena.active_character_id, arena.char_scale) as Vector2


func _get_slot_core_pos(slot: Dictionary) -> Vector2:
	if arena == null or slot.is_empty():
		return Vector2.ZERO
	var mnode := slot.get("node") as Node2D
	if mnode == null or not is_instance_valid(mnode):
		return Vector2.ZERO
	return arena.call("get_fighter_core_world_pos", mnode, str(slot["character_id"]), float(slot["scale_val"])) as Vector2


func _compute_slot_edge_gap(slot: Dictionary) -> float:
	if arena.player_node == null or not bool(slot["alive"]) or slot["node"] == null:
		return 99999.0
	return float(arena.call("compute_silhouette_edge_gap", arena.player_node, arena.active_character_id, arena.char_scale, slot["node"], str(slot["character_id"]), float(slot["scale_val"])))


func _find_slot_by_id(sid: String) -> Dictionary:
	for s in _get_combat_slots():
		if str(s["id"]) == sid:
			return s
	return {}


func _find_nearest_alive_slot_in_melee() -> Dictionary:
	var best: Dictionary = {}
	var best_gap := MELEE_STRIKE_EDGE_PX
	for s in _get_combat_slots():
		if not can_attack_slot(s):
			continue
		var gap := _compute_slot_edge_gap(s)
		if gap <= best_gap:
			best_gap = gap
			best = s
	return best


func _resolve_player_attack_target(allow_far: bool) -> Dictionary:
	if pointer_kind == "enemy" and not pointer_slot_id.is_empty():
		var ps := _find_slot_by_id(pointer_slot_id)
		if not ps.is_empty() and can_attack_slot(ps):
			if allow_far or _compute_slot_edge_gap(ps) <= MELEE_STRIKE_EDGE_PX:
				return ps
	var best: Dictionary = {}
	var best_gap := 99999.0 if allow_far else MELEE_STRIKE_EDGE_PX
	for s in _get_combat_slots():
		if not can_attack_slot(s):
			continue
		var gap := _compute_slot_edge_gap(s)
		if gap <= best_gap:
			best_gap = gap
			best = s
	return best


func _gather_pointer_candidates() -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var ref_x: float = arena.player_node.position.x if (player_spawned and arena.player_node != null) else (arena._arena_camera.position.x if arena._arena_camera != null else 960.0)
	for s in _get_combat_slots():
		if can_attack_slot(s):
			var sn := s["node"] as Node2D
			out.append({"kind": "enemy", "id": str(s["id"]), "node": sn, "dist": absf(sn.position.x - ref_x)})
	for item_n in arena._dropped_item_nodes:
		if _can_pickup_item(item_n):
			out.append({"kind": "item", "id": "", "node": item_n, "dist": absf(item_n.position.x - ref_x)})
	if arena.shenron_summon != null and arena.shenron_summon.active:
		out.append({"kind": "npc", "id": "shenron", "node": arena.shenron_summon, "dist": 0.0})
	out.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return float(a["dist"]) < float(b["dist"]))
	return out


func refresh_pointer_valid() -> void:
	var cands := _gather_pointer_candidates()
	if cands.is_empty():
		pointer_kind = "enemy"
		pointer_slot_id = ""
		pointer_item_node = null
		pointer_changed.emit(pointer_kind)
		return
	for c in cands:
		if pointer_kind == "enemy" and str(c["kind"]) == "enemy" and str(c["id"]) == pointer_slot_id:
			return
		if pointer_kind == "item" and str(c["kind"]) == "item" and c["node"] == pointer_item_node:
			return
		if pointer_kind == "npc" and str(c["kind"]) == "npc":
			return
	var first := cands[0]
	pointer_kind = str(first["kind"])
	pointer_slot_id = str(first["id"])
	pointer_item_node = first["node"] as Node2D if pointer_kind == "item" else null
	pointer_changed.emit(pointer_kind)


func cycle_target_pointer() -> Dictionary:
	cancel_auto_approach()
	var cands := _gather_pointer_candidates()
	if cands.is_empty():
		pointer_kind = "enemy"
		pointer_slot_id = ""
		pointer_item_node = null
		pointer_changed.emit(pointer_kind)
		return {"kind": pointer_kind}
	var cur_idx := -1
	for i in range(cands.size()):
		var c := cands[i]
		if pointer_kind == str(c["kind"]):
			if pointer_kind == "enemy" and str(c["id"]) == pointer_slot_id:
				cur_idx = i
				break
			elif pointer_kind == "item" and c["node"] == pointer_item_node:
				cur_idx = i
				break
			elif pointer_kind == "npc":
				cur_idx = i
				break
	var next_c := cands[(cur_idx + 1) % cands.size()]
	pointer_kind = str(next_c["kind"])
	pointer_slot_id = str(next_c["id"])
	pointer_item_node = next_c["node"] as Node2D if pointer_kind == "item" else null
	pointer_pulse_s = 0.28
	pointer_x_anim_s = 0.0
	pointer_x_visible_s = POINTER_X_SHOW_DURATION_S if pointer_kind == "enemy" else 0.0
	pointer_changed.emit(pointer_kind)
	arena.queue_redraw()
	return {"kind": pointer_kind, "slot_id": pointer_slot_id}


func select_target_at_world_pos(world_pos: Vector2) -> Dictionary:
	var best_kind := ""
	var best_slot_id := ""
	var best_item: Node2D = null
	var best_dist := 999999.0

	for s in _get_combat_slots():
		if not can_attack_slot(s):
			continue
		var mnode := s["node"] as Node2D
		if bool(arena.call("silhouette_contains_point", mnode, str(s["character_id"]), float(s["scale_val"]), world_pos, 18.0)):
			var core := _get_slot_core_pos(s)
			var d := world_pos.distance_to(core)
			if d < best_dist:
				best_dist = d
				best_kind = "enemy"
				best_slot_id = str(s["id"])
				best_item = null

	for item_raw in arena._dropped_item_nodes:
		var item_n := item_raw as Node2D
		if item_n == null or not is_instance_valid(item_n) or not item_n.visible:
			continue
		var lst := str(item_n.get("lifecycle_state"))
		if lst == "collecting" or lst == "collected" or lst == "bag":
			continue
		var item_center: Vector2 = item_n.position + Vector2(0.0, -16.0 * maxf(1.0, item_n.scale.x))
		var idist: float = world_pos.distance_to(item_center)
		if idist <= 46.0 and idist < best_dist:
			best_dist = idist
			best_kind = "item"
			best_slot_id = ""
			best_item = item_n

	if best_kind.is_empty() and arena.shenron_summon != null and arena.shenron_summon.active:
		var sh_pos: Vector2 = arena.shenron_summon.position + Vector2(960.0, 420.0)
		if world_pos.distance_to(sh_pos) <= 180.0:
			best_kind = "npc"
			best_slot_id = "shenron"

	if best_kind.is_empty():
		return {"selected": false}

	var tap_dt: float = _sim_time_s - _last_tap_time_s
	var same_as_last_tap := (best_kind == _last_tap_kind) and (best_slot_id == _last_tap_slot_id) and (best_item == _last_tap_item) and (tap_dt >= 0.04 and tap_dt <= DOUBLE_TAP_WINDOW_S)
	var changed := (pointer_kind != best_kind) or (pointer_slot_id != best_slot_id) or (pointer_item_node != best_item)
	if changed:
		cancel_auto_approach()
	pointer_kind = best_kind
	pointer_slot_id = best_slot_id
	pointer_item_node = best_item
	pointer_pulse_s = 0.30
	pointer_x_anim_s = 0.0
	pointer_x_visible_s = POINTER_X_SHOW_DURATION_S if best_kind == "enemy" else 0.0
	_last_tap_kind = best_kind
	_last_tap_slot_id = best_slot_id
	_last_tap_item = best_item
	_last_tap_time_s = _sim_time_s

	var auto_attacked := false
	if same_as_last_tap and (best_kind == "enemy" or best_kind == "item"):
		if best_kind == "enemy":
			pointer_x_double_tap_pulse_s = 0.35
			pointer_x_visible_s = 0.80
		_last_tap_time_s = -99.0
		auto_attacked = request_player_primary_action()

	pointer_changed.emit(pointer_kind)
	arena.queue_redraw()
	return {"selected": true, "kind": pointer_kind, "slot_id": pointer_slot_id, "double_tap_attack": auto_attacked}


func get_active_target_pointer_info() -> Dictionary:
	refresh_pointer_valid()
	if pointer_kind == "enemy" and not pointer_slot_id.is_empty():
		var ps := _find_slot_by_id(pointer_slot_id)
		if not ps.is_empty() and bool(ps["alive"]) and is_instance_valid(ps["node"]):
			var m_rect := _get_slot_body_rect(ps)
			var e_cx := _get_slot_core_pos(ps).x
			var e_top := m_rect.position.y - 14.0
			return {
				"visible": true,
				"persistent": true,
				"kind": "enemy",
				"slot_id": pointer_slot_id,
				"tip_pos": Vector2(e_cx, e_top - 48.0),
			}
	elif pointer_kind == "item" and pointer_item_node != null and is_instance_valid(pointer_item_node):
		return {
			"visible": true,
			"persistent": true,
			"kind": "item",
			"slot_id": "",
			"tip_pos": pointer_item_node.position + Vector2(0.0, -44.0),
		}
	elif pointer_kind == "npc" and arena != null and arena.shenron_summon != null and arena.shenron_summon.active:
		return {
			"visible": true,
			"persistent": true,
			"kind": "npc",
			"slot_id": "shenron",
			"tip_pos": arena.shenron_summon.position + Vector2(960.0, 260.0),
		}
	return {"visible": false, "persistent": false, "kind": "", "slot_id": "", "tip_pos": Vector2.ZERO}


func draw_back_overlays(canvas: CanvasItem) -> void:
	if not active:
		return
	if player_spawned and not player_dead and arena != null and arena.player_node != null:
		_draw_hero_phase2_back_fx_overlays(canvas)


static func _shield_break_flash_alpha(timer_s: float) -> float:
	if timer_s <= 0.0:
		return 0.0
	var fade := clampf(timer_s / 0.45, 0.0, 1.0)
	var pulse := 0.26 + 0.74 * absf(sin(timer_s * 15.0))
	return clampf(fade * pulse, 0.0, 1.0)


func draw_overlays(canvas: CanvasItem) -> void:
	if not active:
		return
	if show_monster_ranges:
		_draw_monster_range_overlays(canvas)
	# 1. Player overhead Green HP + Blue Mana + White Armor bars + Orange vertical Flight KI bar (+ display name in Alpha session)
	if player_spawned and not player_dead and arena.player_node != null:
		var p_rect := _get_player_body_rect()
		var p_top: float = p_rect.position.y - 18.0
		var p_cx: float = _get_player_core_pos().x
		var p_ki := -1.0
		var p_max_ki := 50.0
		var p_ki_ex := false
		if _is_hero_songoku_node(arena.player_node):
			p_ki = float(arena.player_node.get("ki"))
			p_max_ki = float(arena.player_node.get("max_ki"))
			p_ki_ex = bool(arena.player_node.get("ki_exhausted"))
		OverheadBarsDrawScript.draw_player_bars(canvas, p_cx, p_top, player_hp, player_max_hp, player_mana, player_max_mana, local_display_name, false, player_armor, player_max_armor, player_armor_broken_timer_s > 0.0, p_ki, p_max_ki, p_ki_ex, player_shield_break_icon_timer_s > 0.0, _shield_break_flash_alpha(player_shield_break_icon_timer_s), false, pk_tan_sat_enabled)
		if player_hard_stun_timer_s > 0.0:
			OverheadBarsDrawScript.draw_stun_stars_ring(canvas, Vector2(p_cx, p_rect.position.y), _sim_time_s)
		_draw_hero_phase2_fx_overlays(canvas)
	_draw_hero_genki_world_fx(canvas)

	# 2. All alive monsters + Boss Drum + Remote Players (Vinh / Thái)
	for s in _get_combat_slots():
		if not bool(s["alive"]) or not is_instance_valid(s["node"]):
			continue
		var m_rect := _get_slot_body_rect(s)
		var e_top := m_rect.position.y - 14.0
		var e_cx := _get_slot_core_pos(s).x
		if bool(s.get("is_remote_player", false)):
			var rk_t := float(s.get("kentai_timer_s", 0.0))
			var ran_s := int(s.get("an_nguc_stacks", 0))
			if rk_t > 0.0:
				_draw_kentai_burn_on_rect(canvas, m_rect, e_cx * 0.013)
			var r_hostile := is_remote_player_hostile(s)
			var r_pk_flag := bool(s.get("pk_tan_sat", false))
			OverheadBarsDrawScript.draw_player_bars(
				canvas,
				e_cx,
				e_top - 4.0,
				float(s.get("hp", PLAYER_MAX_HP)),
				float(s.get("max_hp", PLAYER_MAX_HP)),
				float(s.get("mana", 0.0)),
				float(s.get("max_mana", PLAYER_MAX_MANA)),
				str(s.get("display_name", "")),
				true,
				-1.0,
				100.0,
				false,
				-1.0,
				50.0,
				false,
				false,
				0.0,
				r_hostile,
				r_pk_flag
			)
			if rk_t > 0.0 or ran_s > 0:
				OverheadBarsDrawScript.draw_tapion_mark_badges(canvas, e_cx, e_top - 78.0, rk_t, ran_s, _sim_time_s)
			continue
		var stunned := float(s["stun_timer_s"]) > 0.0 or float(s.get("hard_stun_timer_s", 0.0)) > 0.0
		var is_boss := bool(s.get("is_boss", false))
		var lbl := str(s.get("display_name", "Drum")) if is_boss else str(s["character_id"])
		var m_cstate := "combat" if is_boss else str(s.get("combat_state", "peace"))
		var sb_rem: float = float(s.get("shield_break_icon_timer_s", 0.0))
		var k_rem: float = float(s.get("kentai_timer_s", 0.0))
		var an_stacks: int = int(s.get("an_nguc_stacks", 0))
		if k_rem > 0.0:
			_draw_kentai_burn_on_rect(canvas, m_rect, e_cx * 0.013)
		OverheadBarsDrawScript.draw_enemy_bars(canvas, e_cx, e_top, float(s["hp"]), float(s["max_hp"]), float(s["stamina"]), float(s["max_stamina"]), stunned, lbl, is_boss, m_cstate, sb_rem > 0.0, _shield_break_flash_alpha(sb_rem))
		if k_rem > 0.0 or an_stacks > 0:
			var mark_y := e_top - (64.0 if sb_rem > 0.0 else 50.0)
			OverheadBarsDrawScript.draw_tapion_mark_badges(canvas, e_cx, mark_y, k_rem, an_stacks, _sim_time_s)
		if float(s.get("hard_stun_timer_s", 0.0)) > 0.0:
			OverheadBarsDrawScript.draw_stun_stars_ring(canvas, Vector2(e_cx, m_rect.position.y), _sim_time_s)

	# 3. Persistent Target Pointer UI (touch selection + TRỎ/Tab button) + brief Calligraphic Red "X" flash on enemy lock!
	var x_prog := clampf(pointer_x_anim_s / maxf(0.01, pointer_x_anim_dur_s), 0.0, 1.0)
	var x_boost := 1.0 + (pointer_x_double_tap_pulse_s / 0.35) * 0.35
	if pointer_kind == "enemy" and not pointer_slot_id.is_empty():
		var ps := _find_slot_by_id(pointer_slot_id)
		if not ps.is_empty() and bool(ps["alive"]) and is_instance_valid(ps["node"]):
			var m_rect := _get_slot_body_rect(ps)
			var s_core := _get_slot_core_pos(ps)
			var tip_pos := Vector2(s_core.x, m_rect.position.y - 62.0)
			OverheadBarsDrawScript.draw_target_pointer(canvas, tip_pos, _sim_time_s, "enemy")
			if pointer_x_visible_s > 0.0:
				var boost := x_boost * (1.15 if pointer_x_double_tap_pulse_s > 0.0 else 1.0)
				var x_fade := clampf(pointer_x_visible_s / 0.22, 0.0, 1.0)
				OverheadBarsDrawScript.draw_calligraphic_red_x(canvas, s_core, x_prog, _sim_time_s, boost, x_fade)
	elif pointer_kind == "item" and pointer_item_node != null and is_instance_valid(pointer_item_node):
		OverheadBarsDrawScript.draw_target_pointer(canvas, pointer_item_node.position + Vector2(0.0, -44.0), _sim_time_s, "item")
		if pointer_pulse_s > 0.0:
			var ir := Rect2(pointer_item_node.position - Vector2(20.0, 36.0), Vector2(40.0, 40.0))
			OverheadBarsDrawScript.draw_selection_ring(canvas, ir, pointer_pulse_s / 0.30, "item")
	elif pointer_kind == "npc" and arena.shenron_summon != null and arena.shenron_summon.active:
		OverheadBarsDrawScript.draw_target_pointer(canvas, arena.shenron_summon.position + Vector2(960.0, 260.0), _sim_time_s, "npc")

	# 4. Hit impact bursts & floating damage numbers
	for imp in hit_impacts:
		var prog := clampf(float(imp["elapsed_s"]) / maxf(0.01, float(imp["duration_s"])), 0.0, 1.0)
		var c_frames: SpriteFrames = imp.get("custom_frames", null) as SpriteFrames
		OverheadBarsDrawScript.draw_hit_impact(canvas, imp["pos"] as Vector2, prog, str(imp["kind"]), imp.get("dir", Vector2.RIGHT) as Vector2, c_frames)
	for ft in floating_texts:
		var fprog := clampf(float(ft["elapsed_s"]) / maxf(0.01, float(ft["duration_s"])), 0.0, 1.0)
		OverheadBarsDrawScript.draw_floating_damage(canvas, ft["pos"] as Vector2, str(ft["text"]), fprog, ft["color"] as Color)


func _draw_monster_range_overlays(canvas: CanvasItem) -> void:
	var font := ThemeDB.fallback_font
	if player_spawned and not player_dead and arena.player_node != null:
		var p_rects: Array = arena.call("get_fighter_silhouette_rects", arena.player_node, arena.active_character_id, arena.char_scale)
		for pr_r in p_rects:
			canvas.draw_rect(pr_r as Rect2, Color(0.20, 0.92, 1.0, 0.72), false, 1.5)
		var p_core := _get_player_core_pos()
		canvas.draw_line(p_core - Vector2(8.0, 0.0), p_core + Vector2(8.0, 0.0), Color(0.20, 1.0, 1.0, 0.98), 2.0)
		canvas.draw_line(p_core - Vector2(0.0, 8.0), p_core + Vector2(0.0, 8.0), Color(0.20, 1.0, 1.0, 0.98), 2.0)
	for s in _get_combat_slots():
		if not bool(s["alive"]) or not is_instance_valid(s["node"]) or bool(s.get("is_remote_player", false)):
			continue
		var mnode := s["node"] as Node2D
		var m_rect := _get_slot_body_rect(s)
		var cid := str(s["character_id"])
		var m_rects: Array = arena.call("get_fighter_silhouette_rects", mnode, cid, float(s["scale_val"]))
		for mr_r in m_rects:
			canvas.draw_rect(mr_r as Rect2, Color(1.0, 0.72, 0.25, 0.65), false, 1.5)
		var m_core := _get_slot_core_pos(s)
		canvas.draw_line(m_core - Vector2(8.0, 0.0), m_core + Vector2(8.0, 0.0), Color(1.0, 0.35, 0.25, 0.98), 2.0)
		canvas.draw_line(m_core - Vector2(0.0, 8.0), m_core + Vector2(0.0, 8.0), Color(1.0, 0.35, 0.25, 0.98), 2.0)
		var is_fly := bool(s["is_flying"])
		var zmin := float(s["zone_min_x"])
		var zmax := float(s["zone_max_x"])
		var floor_y := float(arena.call("_ground_y_at", mnode.position.x))
		if is_fly:
			var top_y := float(s["y_home"]) - 76.0
			var bot_y := float(arena.call("_ground_y_at", float(s["x_home"]))) + 40.0
			var air_rect := Rect2(zmin, top_y, zmax - zmin, maxf(120.0, bot_y - top_y))
			canvas.draw_rect(air_rect, Color(0.95, 0.22, 0.22, 0.08), true)
			canvas.draw_rect(air_rect, Color(1.0, 0.30, 0.30, 0.78), false, 2.5)
			canvas.draw_line(Vector2(zmin, top_y + 36.0), Vector2(zmax, top_y + 36.0), Color(1.0, 0.45, 0.45, 0.55), 1.5)
			if font != null:
				canvas.draw_string(font, Vector2(zmin + 10.0, top_y + 24.0), "[BAY] %s | Vùng [%d..%d] (%dpx)" % [cid, int(round(zmin)), int(round(zmax)), int(round(zmax - zmin))], HORIZONTAL_ALIGNMENT_LEFT, -1, 16, Color(1.0, 0.72, 0.72, 0.96))
		else:
			var g_top := floor_y - 220.0
			var g_rect := Rect2(zmin, g_top, zmax - zmin, 232.0)
			canvas.draw_rect(g_rect, Color(0.16, 0.88, 0.42, 0.09), true)
			canvas.draw_rect(g_rect, Color(0.24, 0.94, 0.48, 0.82), false, 2.5)
			# Melee <= 50px bracket around monster body edge
			var m_left := m_rect.position.x - 50.0
			var m_right := m_rect.end.x + 50.0
			var melee_rect := Rect2(m_left, floor_y - 120.0, m_right - m_left, 120.0)
			canvas.draw_rect(melee_rect, Color(1.0, 0.85, 0.20, 0.82), false, 2.0)
			# Outer PowerUp >= 200px markers
			var p_left := m_rect.position.x - 200.0
			var p_right := m_rect.end.x + 200.0
			canvas.draw_line(Vector2(p_left, floor_y - 150.0), Vector2(p_left, floor_y + 6.0), Color(0.22, 0.88, 1.0, 0.82), 2.0)
			canvas.draw_line(Vector2(p_right, floor_y - 150.0), Vector2(p_right, floor_y + 6.0), Color(0.22, 0.88, 1.0, 0.82), 2.0)
			if font != null:
				var info := "[ĐẤT] %s | [%d..%d] (%dpx) | Melee<=50 | Power>=200" % [cid, int(round(zmin)), int(round(zmax)), int(round(zmax - zmin))]
				if player_spawned and not player_dead and arena.player_node != null:
					info += " | edge=%dpx" % int(round(_compute_slot_edge_gap(s)))
				canvas.draw_string(font, Vector2(zmin + 10.0, floor_y + 28.0), info, HORIZONTAL_ALIGNMENT_LEFT, -1, 16, Color(0.70, 1.0, 0.78, 0.96))


func sync_from_zone_snapshot(players_by_id: Dictionary, monsters_by_id: Dictionary, local_uid: String) -> void:
	if arena == null or not active:
		return
	var seen_remote := {}
	for uid_key in players_by_id.keys():
		var pdata: Dictionary = players_by_id[uid_key]
		var uid := str(pdata.get("id", uid_key))
		if uid.is_empty():
			continue
		if uid == local_uid:
			if pdata.has("hp"):
				var srv_hp := clampf(float(pdata["hp"]), 0.0, player_max_hp)
				var hp_changed := _last_srv_local_hp < 0.0 or absf(srv_hp - _last_srv_local_hp) > 0.01
				_last_srv_local_hp = srv_hp
				if _local_hp_grace_s <= 0.0 and hp_changed:
					player_hp = srv_hp
			if pdata.has("mana"):
				var srv_mana := clampf(float(pdata["mana"]), 0.0, player_max_mana)
				var mana_changed := _last_srv_local_mana < 0.0 or absf(srv_mana - _last_srv_local_mana) > 0.01
				_last_srv_local_mana = srv_mana
				if _local_mana_grace_s <= 0.0 and mana_changed:
					player_mana = srv_mana
			if pdata.has("display_name") and not str(pdata["display_name"]).is_empty():
				local_display_name = str(pdata["display_name"])
			if pdata.has("alive") and _local_hp_grace_s <= 0.0:
				var alive_srv := bool(pdata["alive"])
				if not alive_srv and not player_dead and player_hp <= 0.0:
					player_dead = true
					player_respawn_timer_s = RESPAWN_PLAYER_DELAY_S
					cancel_genki_on_player_death()
					clear_all_tapion_marks()
					if arena.player_node != null:
						if arena.player_node.has_method(&"cancel_antamina_interrupt"):
							arena.player_node.call(&"cancel_antamina_interrupt")
						if _is_hero_songoku_node(arena.player_node):
							arena.player_node.set("flight_state", "falling")
							arena.player_node.set("hover_timer_s", 0.0)
							arena.player_node.call(&"step_combat_move_frame", 0.0, 0)
						var kspr2 := arena.player_node.get_node_or_null("Sprite") as AnimatedSprite2D
						if kspr2 != null:
							kspr2.position.y = 0.0
						arena.call("_play_fighter_clip", arena.player_node, "ko")
				elif alive_srv and player_dead and _last_srv_local_hp >= player_max_hp - 0.1:
					player_dead = false
					player_respawn_timer_s = 0.0
					player_armor = player_max_armor
					player_armor_broken_timer_s = 0.0
					player_shield_break_icon_timer_s = 0.0
					player_hard_stun_timer_s = 0.0
					player_hit_flash_s = 0.0
					player_hit_shake_s = 0.0
					if arena.player_node != null:
						arena.player_node.position = Vector2(float(pdata.get("x", arena.player_node.position.x)), float(pdata.get("y", arena.player_node.position.y)))
						var pspr_r := arena.player_node.get_node_or_null("Sprite") as AnimatedSprite2D
						if pspr_r != null:
							pspr_r.modulate = Color.WHITE
							pspr_r.position = Vector2.ZERO
						if _is_hero_songoku_node(arena.player_node):
							arena.player_node.set("flight_state", "ground")
							arena.player_node.set("hover_timer_s", 0.0)
							arena.player_node.set("ki", float(arena.player_node.get("max_ki")))
							arena.player_node.set("ki_exhausted", false)
							arena.player_node.call(&"step_combat_move_frame", 0.0, 0)
						arena.call("_play_fighter_clip", arena.player_node, "idle")
			player_state_changed.emit()
			continue

		seen_remote[uid] = true
		var rslot: Dictionary = remote_player_slots.get(uid, {})
		var cid := str(pdata.get("character_id", "")).strip_edges()
		# Online Vinh/Thái fix: upgrade legacy "drum"/empty remote character_id to Son Goku on live runtime (or when local hero is Son Goku), while preserving headless legacy 2-Drum E2E!
		var has_goku_entry: bool = not (arena.call("_find_character_entry_ro", "songoku") as Dictionary).is_empty()
		if has_goku_entry and (cid.is_empty() or cid == "drum" or cid == "songoku_hero_demo") and (DisplayServer.get_name() != "headless" or str(arena.active_character_id) == "songoku"):
			cid = "songoku"
		if cid.is_empty():
			cid = "drum"
		if (not rslot.is_empty()) and str(rslot.get("character_id", "")) != cid:
			var old_rnode := rslot.get("node") as Node2D
			if old_rnode != null and is_instance_valid(old_rnode):
				old_rnode.queue_free()
			remote_player_slots.erase(uid)
			rslot = {}
		if rslot.is_empty() or not is_instance_valid(rslot.get("node")):
			rslot = _spawn_remote_player_slot(uid, cid, pdata)
			if rslot.is_empty():
				continue
			remote_player_slots[uid] = rslot
		rslot["display_name"] = str(pdata.get("display_name", uid))
		rslot["hp"] = float(pdata.get("hp", PLAYER_MAX_HP))
		rslot["max_hp"] = float(pdata.get("max_hp", PLAYER_MAX_HP))
		rslot["mana"] = float(pdata.get("mana", 0.0))
		rslot["max_mana"] = float(pdata.get("max_mana", PLAYER_MAX_MANA))
		rslot["alive"] = bool(pdata.get("alive", true))
		var prev_rpk := bool(rslot.get("pk_tan_sat", false))
		var next_rpk := bool(pdata.get("pk_tan_sat", false))
		rslot["pk_tan_sat"] = next_rpk
		if prev_rpk != next_rpk:
			refresh_pointer_valid()
			arena.queue_redraw()
		rslot["target_pos"] = Vector2(float(pdata.get("x", 560.0)), float(pdata.get("y", arena.ground_y)))
		rslot["facing_left"] = bool(pdata.get("facing_left", false))
		var act := str(pdata.get("act", "idle"))
		if not act.is_empty():
			rslot["remote_act"] = act
		var rnode := rslot.get("node") as Node2D
		if rnode != null and is_instance_valid(rnode):
			rnode.visible = true
			var sc := float(rslot.get("scale_val", 2.0))
			rnode.scale = Vector2(-sc if bool(rslot["facing_left"]) else sc, sc)
			var rspr := rnode.get_node_or_null("Sprite") as AnimatedSprite2D
			if rspr != null and rspr.sprite_frames != null:
				var desired := act if rspr.sprite_frames.has_animation(StringName(act)) else "idle"
				if not bool(rslot["alive"]) and rspr.sprite_frames.has_animation(&"ko"):
					desired = "ko"
				if String(rspr.animation) != desired or not rspr.is_playing():
					arena.call("_play_fighter_clip", rnode, desired)

	for existing_uid in remote_player_slots.keys():
		if not seen_remote.has(existing_uid):
			var old_slot: Dictionary = remote_player_slots[existing_uid]
			var old_node := old_slot.get("node") as Node2D
			if old_node != null and is_instance_valid(old_node):
				old_node.queue_free()
			remote_player_slots.erase(existing_uid)

	for mid_key in monsters_by_id.keys():
		var mdata: Dictionary = monsters_by_id[mid_key]
		var mid := str(mdata.get("id", mid_key))
		var slot := _find_slot_by_id(mid)
		if slot.is_empty():
			continue
		var prev_srv_alive: bool = bool(slot.get("_last_srv_alive", true))
		var prev_srv_hp: float = float(slot.get("_last_srv_hp", -1.0))
		var srv_alive: bool = bool(mdata.get("alive", true))
		var srv_hp: float = clampf(float(mdata.get("hp", slot.get("hp", 1000.0))), 0.0, float(slot.get("max_hp", 1500.0)))
		var explicit_respawn: bool = srv_alive and not prev_srv_alive
		if float(_slot_local_hit_grace.get(mid, 0.0)) > 0.0 and not explicit_respawn:
			# Preserve server death state during grace without swallowing an upcoming false->true respawn transition!
			if not srv_alive:
				slot["_last_srv_alive"] = false
				slot["_last_srv_hp"] = srv_hp
			continue
		slot["_last_srv_alive"] = srv_alive
		slot["_last_srv_hp"] = srv_hp
		var hp_changed := prev_srv_hp < 0.0 or absf(srv_hp - prev_srv_hp) > 0.01
		if hp_changed and bool(slot.get("alive", false)):
			slot["hp"] = srv_hp
		if not srv_alive and bool(slot.get("alive", false)):
			slot["hp"] = 0.0
			_kill_slot_monster(slot)
		elif srv_alive and not bool(slot.get("alive", false)):
			var dead_age_s := _sim_time_s - float(slot.get("_local_dead_time_s", _sim_time_s))
			# Resurrect immediately on explicit server false->true transition, OR self-heal after full 12s
			# if local kill desynced from server (prevents monsters staying permanently dead on downloaded clients!).
			if explicit_respawn or dead_age_s >= RESPAWN_MONSTER_DELAY_S:
				_reset_slot_for_server_respawn(slot, srv_hp, str(mdata.get("character_id", "")))


func _is_authoritative_network_connected() -> bool:
	if arena == null:
		return false
	var tr: Variant = arena.get("net_transport")
	if tr == null:
		return false
	return bool(tr.get("is_connected_state"))


func _reset_slot_for_server_respawn(slot: Dictionary, srv_hp: float, srv_cid: String = "") -> void:
	if slot.is_empty():
		return
	var target_cid := srv_cid.strip_edges()
	if not target_cid.is_empty() and target_cid != str(slot.get("character_id", "")):
		_spawn_slot_monster(slot, target_cid)
		slot["hp"] = clampf(srv_hp, 0.0, float(slot.get("max_hp", srv_hp)))
		refresh_pointer_valid()
		return
	var is_boss := bool(slot.get("is_boss", false))
	var max_hp := float(slot.get("max_hp", maxf(1.0, srv_hp)))
	var max_stam := float(slot.get("max_stamina", 100.0))
	slot["alive"] = true
	slot["hp"] = clampf(srv_hp, 0.0, max_hp)
	slot["stamina"] = max_stam
	slot["stun_timer_s"] = 0.0
	slot["hard_stun_timer_s"] = 0.0
	slot["hit_anim_timer_s"] = 0.0
	slot["shield_break_icon_timer_s"] = 0.0
	slot["kentai_timer_s"] = 0.0
	slot["an_nguc_stacks"] = 0
	slot["_local_dead_time_s"] = -999.0
	slot["respawn_timer_s"] = 0.0
	slot["ko_hide_timer_s"] = 0.0
	slot["cooldown_s"] = 0.25
	slot["light_chain"] = 0
	slot["action_clip"] = ""
	slot["action_timer_s"] = 0.0
	slot["vy"] = 0.0
	slot["power_released"] = false
	slot["melee_hit_done"] = false
	slot["teleport_relocated"] = false
	slot["combat_state"] = "combat" if is_boss else "peace"
	slot["aggro_target_id"] = ""
	slot["committed_target_id"] = ""
	slot["fled_attackers"] = []
	slot["provoked_timer_s"] = 0.0
	slot["turn_lock_s"] = 0.0
	slot["hit_flash_s"] = 0.0
	slot["hit_shake_s"] = 0.0
	var mn := slot.get("node") as Node2D
	if mn != null and is_instance_valid(mn):
		mn.visible = true
		var home_x := float(slot.get("x_home", mn.position.x))
		var home_y := float(slot.get("y_home", mn.position.y)) if bool(slot.get("is_flying", false)) else float(arena.call("_ground_y_at", home_x))
		mn.position = Vector2(home_x, home_y)
		if mn.get("_turn_pending") != null:
			mn.set("_turn_pending", false)
			mn.set("_turn_clip", &"")
			if mn.has_meta("_arena_turn_resume_clip"):
				mn.set_meta("_arena_turn_resume_clip", "")
		var mspr := mn.get_node_or_null("Sprite") as AnimatedSprite2D
		if mspr != null:
			mspr.modulate = Color.WHITE
			mspr.position = Vector2.ZERO
		arena.call("_play_fighter_clip", mn, "idle")
	refresh_pointer_valid()


func _spawn_remote_player_slot(uid: String, cid: String, pdata: Dictionary) -> Dictionary:
	var entry: Dictionary = arena.call("_find_character_entry_ro", cid)
	if entry.is_empty():
		entry = arena.call("_find_character_entry_ro", "drum")
		cid = "drum"
	if entry.is_empty():
		return {}
	var prefab_path := str(arena.call("_resolve_prefab_path", entry))
	if prefab_path.is_empty() or not ResourceLoader.exists(prefab_path):
		return {}
	var packed := ResourceLoader.load(prefab_path) as PackedScene
	if packed == null:
		return {}
	var inst := packed.instantiate() as Node2D
	if inst == null:
		return {}
	var parent_layer: Node = arena.fighters_layer if arena.fighters_layer != null else arena
	parent_layer.add_child(inst)
	inst.name = "RemotePlayer_%s" % uid.replace(":", "_")
	var sc := float(arena.call("_get_entry_default_scale", entry))
	var px := float(pdata.get("x", 640.0))
	var py := float(pdata.get("y", arena.call("_ground_y_at", px)))
	var f_left := bool(pdata.get("facing_left", false))
	if inst.get("external_orb_managed") != null:
		inst.set("external_orb_managed", true)
	arena.call("_configure_fighter_instance", inst, px, py, f_left, sc)
	inst.z_index = int(arena.call("get_fighter_layer_z", cid, false)) + 2
	return {
		"id": "player:" + uid,
		"user_id": uid,
		"is_remote_player": true,
		"is_boss": false,
		"is_flying": false,
		"character_id": cid,
		"display_name": str(pdata.get("display_name", uid)),
		"node": inst,
		"scale_val": sc,
		"hp": float(pdata.get("hp", PLAYER_MAX_HP)),
		"max_hp": float(pdata.get("max_hp", PLAYER_MAX_HP)),
		"mana": float(pdata.get("mana", 0.0)),
		"max_mana": float(pdata.get("max_mana", PLAYER_MAX_MANA)),
		"stamina": 100.0,
		"max_stamina": 100.0,
		"stun_timer_s": 0.0,
		"alive": bool(pdata.get("alive", true)),
		"pk_tan_sat": bool(pdata.get("pk_tan_sat", false)),
		"facing_left": f_left,
		"target_pos": Vector2(px, py),
		"hit_flash_s": 0.0,
		"hit_shake_s": 0.0,
		"kentai_timer_s": 0.0,
		"an_nguc_stacks": 0,
		"remote_act": str(pdata.get("act", "idle")),
	}


func step_remote_players(delta: float) -> void:
	if delta <= 0.0:
		return
	var alpha := clampf(delta * 16.0, 0.0, 1.0)
	for rp_val in remote_player_slots.values():
		if not (rp_val is Dictionary):
			continue
		var rslot: Dictionary = rp_val
		var rnode := rslot.get("node") as Node2D
		if rnode == null or not is_instance_valid(rnode):
			continue
		var tgt_pos: Vector2 = rslot.get("target_pos", rnode.position)
		if rnode.position.distance_to(tgt_pos) > 360.0:
			rnode.position = tgt_pos
		else:
			rnode.position = rnode.position.lerp(tgt_pos, alpha)


func apply_network_combat_event(ev: Dictionary, local_uid: String) -> void:
	if arena == null or not active:
		return
	var action := str(ev.get("action", "attack_light"))
	var attacker_id := str(ev.get("attacker_id", ""))
	var target_id := str(ev.get("target_id", ""))
	var target_kind := str(ev.get("target_kind", "player"))
	var dmg := float(ev.get("damage", 0.0))
	var hit_kind := "melee"
	if action == "power_up":
		hit_kind = "skill"
	elif action in ["attack_heavy", "goku_heavy", "goku_gold_slash", "atomic_blast", "kamehameha", "genki"]:
		hit_kind = "heavy"

	if attacker_id == local_uid and ev.has("attacker_mana"):
		_last_srv_local_mana = clampf(float(ev["attacker_mana"]), 0.0, player_max_mana)
		if _local_mana_grace_s <= 0.0:
			player_mana = _last_srv_local_mana
			player_state_changed.emit()

	if target_kind == "player" and target_id == local_uid and player_spawned and arena.player_node != null:
		var fx_pos := _get_player_core_pos()
		player_hit_flash_s = 0.19
		player_hit_shake_s = 0.09 * HIT_SHAKE_SCALE_MUL
		_spawn_hit_impact_fx(fx_pos, hit_kind, "-%d" % int(round(dmg)), Color(1.0, 0.30, 0.28, 1.0), Vector2.RIGHT)
		if action == "power_up":
			_spawn_powerup_explosion(fx_pos, DEFAULT_EXPLOSION_SCALE)
		elif action in ["atomic_blast", "kamehameha"]:
			_spawn_skill_explosion_33(fx_pos, 1.2 if action == "kamehameha" else 1.05)
		elif action == "genki":
			_spawn_genki_explosion_fx(fx_pos, 1.0)
		elif action == "flurry_kick":
			apply_hard_stun_to_player(1.6)
		elif action == "bukadai":
			apply_hard_stun_to_player(2.0)
		if ev.has("target_hp"):
			player_hp = clampf(float(ev["target_hp"]), 0.0, player_max_hp)
			_last_srv_local_hp = player_hp
			if player_hp <= 0.0 and not player_dead:
				player_dead = true
				player_respawn_timer_s = RESPAWN_PLAYER_DELAY_S
				cancel_genki_on_player_death()
				clear_all_tapion_marks()
				if arena.player_node != null:
					if arena.player_node.has_method(&"cancel_antamina_interrupt"):
						arena.player_node.call(&"cancel_antamina_interrupt")
					if _is_hero_songoku_node(arena.player_node):
						arena.player_node.set("flight_state", "falling")
						arena.player_node.set("hover_timer_s", 0.0)
						arena.player_node.call(&"step_combat_move_frame", 0.0, 0)
					var kspr3 := arena.player_node.get_node_or_null("Sprite") as AnimatedSprite2D
					if kspr3 != null:
						kspr3.position.y = 0.0
					arena.call("_play_fighter_clip", arena.player_node, "ko")
		player_state_changed.emit()
		return

	var tgt_slot: Dictionary = remote_player_slots.get(target_id, {}) if target_kind == "player" else _find_slot_by_id(target_id)
	if not tgt_slot.is_empty() and is_instance_valid(tgt_slot.get("node")):
		if target_kind == "monster" and attacker_id == local_uid:
			# Local client already applied monster damage, hit flash, and floating text on impact.
			if ev.has("target_hp"):
				tgt_slot["_last_srv_hp"] = maxf(0.0, float(ev["target_hp"]))
			if ev.has("target_alive"):
				tgt_slot["_last_srv_alive"] = bool(ev["target_alive"])
			return
		var fx_pos2 := _get_slot_core_pos(tgt_slot)
		tgt_slot["hit_flash_s"] = 0.16
		tgt_slot["hit_shake_s"] = 0.12 * HIT_SHAKE_SCALE_MUL
		if ev.has("target_hp"):
			tgt_slot["hp"] = maxf(0.0, float(ev["target_hp"]))
			tgt_slot["_last_srv_hp"] = float(tgt_slot["hp"])
		var dmg_col := Color(0.40, 0.94, 1.0, 1.0) if hit_kind == "skill" else Color(1.0, 0.92, 0.28, 1.0)
		_spawn_hit_impact_fx(fx_pos2, hit_kind, "-%d" % int(round(dmg)) if dmg > 0.0 else "", dmg_col, Vector2.RIGHT)
		if action == "power_up" and attacker_id != local_uid:
			_spawn_powerup_explosion(fx_pos2, DEFAULT_EXPLOSION_SCALE)
		elif action in ["atomic_blast", "kamehameha"] and attacker_id != local_uid:
			_spawn_skill_explosion_33(fx_pos2, 1.2 if action == "kamehameha" else 1.05)
		elif action == "genki" and attacker_id != local_uid:
			_spawn_genki_explosion_fx(fx_pos2, 1.0)
		if float(tgt_slot.get("hp", 1.0)) <= 0.0 and not bool(tgt_slot.get("is_remote_player", false)) and bool(tgt_slot.get("alive", false)):
			tgt_slot["_last_srv_alive"] = false
			_kill_slot_monster(tgt_slot)


# ==============================================================================
# PHASE 2 SON GOKU SKILLS (05 Barrier, 06 Energy Recover, 26 Flurry Kick Stun,
# 21/23/24/25 Atomic Blast 12s CD, 27..32 Kamehameha 250 MP, 33 Explosion FX)
# ==============================================================================

func _get_songoku_fx_frames() -> SpriteFrames:
	if _songoku_fx_frames != null:
		return _songoku_fx_frames
	var fx_path := "res://assets/fx/songoku_skills_fx/songoku_skills_fx.tres"
	if ResourceLoader.exists(fx_path):
		_songoku_fx_frames = load(fx_path) as SpriteFrames
	return _songoku_fx_frames


func _get_tapion_fx_frames() -> SpriteFrames:
	if _tapion_fx_frames != null:
		return _tapion_fx_frames
	var fx_path := "res://assets/fx/tapion_skills_fx/tapion_skills_fx.tres"
	if ResourceLoader.exists(fx_path):
		_tapion_fx_frames = load(fx_path) as SpriteFrames
	return _tapion_fx_frames


func _get_genki_fx_frames() -> SpriteFrames:
	if _genki_fx_frames != null:
		return _genki_fx_frames
	var fx_path := "res://assets/fx/genki_fx/genki_fx.tres"
	if ResourceLoader.exists(fx_path):
		_genki_fx_frames = load(fx_path) as SpriteFrames
	return _genki_fx_frames


func _spawn_skill_explosion_33(world_pos: Vector2, scale_val: float = 1.0) -> void:
	if arena == null:
		return
	var fx_sf := _get_songoku_fx_frames()
	if fx_sf == null or not fx_sf.has_animation(&"skill_explosion_fx"):
		_spawn_powerup_explosion(world_pos, scale_val * 0.75)
		return
	var ex := AnimatedSprite2D.new()
	ex.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	ex.sprite_frames = fx_sf
	ex.centered = true
	ex.scale = Vector2(scale_val, scale_val)
	ex.position = world_pos
	ex.z_index = Z_LAYER_FX + 2
	var parent_layer: Node = arena.fighters_layer if arena.fighters_layer != null else arena
	parent_layer.add_child(ex)
	ex.play(&"skill_explosion_fx")
	_explosion_nodes.append(ex)
	ex.animation_finished.connect(func() -> void:
		_explosion_nodes.erase(ex)
		if is_instance_valid(ex):
			ex.queue_free()
	)


func apply_hard_stun_to_slot(slot: Dictionary, duration_s: float) -> void:
	if slot.is_empty() or not bool(slot.get("alive", false)):
		return
	if bool(slot.get("is_remote_player", false)) and not is_remote_player_hostile(slot):
		return
	slot["hard_stun_timer_s"] = maxf(float(slot.get("hard_stun_timer_s", 0.0)), duration_s)
	slot["action_clip"] = ""
	slot["action_timer_s"] = 0.0
	var mnode := slot.get("node") as Node2D
	if mnode != null and is_instance_valid(mnode):
		if mnode.get("_turn_pending") != null:
			mnode.set("_turn_pending", false)
			mnode.set("_turn_clip", &"")
		var spr := mnode.get_node_or_null("Sprite") as AnimatedSprite2D
		if spr != null and spr.sprite_frames != null and spr.sprite_frames.has_animation(&"hit"):
			spr.play(&"hit")


func apply_hard_stun_to_player(duration_s: float) -> void:
	if not player_spawned or player_dead:
		return
	if arena != null and arena.player_node != null and arena.player_node.has_method(&"is_barrier_active") and bool(arena.player_node.call(&"is_barrier_active")):
		return
	# Goku Genki (Spirit Bomb): immune to ALL adverse status effects/CC during charge & throw, while still taking HP damage!
	if arena != null and arena.player_node != null and arena.player_node.has_method(&"is_genki_cc_immune") and bool(arena.player_node.call(&"is_genki_cc_immune")):
		if _genki_cc_notice_cd_s <= 0.0:
			_genki_cc_notice_cd_s = 0.65
			floating_texts.append({
				"pos": _get_player_core_pos() + Vector2(0.0, -30.0),
				"text": "MIỄN KHỐNG CHẾ!",
				"color": Color(0.45, 0.92, 1.0, 1.0),
				"elapsed_s": 0.0,
				"duration_s": 0.55,
			})
		return
	player_hard_stun_timer_s = maxf(player_hard_stun_timer_s, duration_s)
	if arena != null and arena.player_node != null:
		# Crowd control cancels active Antamina channel WITHOUT losing any target's "Ấn ngục" stacks!
		if arena.player_node.has_method(&"cancel_antamina_interrupt"):
			arena.player_node.call(&"cancel_antamina_interrupt")
		var pspr := arena.player_node.get_node_or_null("Sprite") as AnimatedSprite2D
		if pspr != null and pspr.sprite_frames != null and pspr.sprite_frames.has_animation(&"hit"):
			pspr.play(&"hit")


func apply_kentai_debuff_to_slot(slot: Dictionary, duration_s: float = 5.0) -> void:
	if slot.is_empty() or not bool(slot.get("alive", false)):
		return
	if bool(slot.get("is_remote_player", false)) and not is_remote_player_hostile(slot):
		return
	slot["kentai_timer_s"] = maxf(float(slot.get("kentai_timer_s", 0.0)), duration_s)
	var pos := _get_slot_core_pos(slot)
	floating_texts.append({
		"pos": pos + Vector2(0.0, -34.0),
		"text": "KENTAI 5s",
		"color": Color(0.24, 1.0, 0.58, 1.0),
		"elapsed_s": 0.0,
		"duration_s": 0.65,
	})


func try_proc_an_nguc_on_slot(slot: Dictionary) -> int:
	if slot.is_empty() or not bool(slot.get("alive", false)):
		return 0
	if float(slot.get("kentai_timer_s", 0.0)) <= 0.0:
		return int(slot.get("an_nguc_stacks", 0))
	slot["kentai_timer_s"] = 0.0
	var next_stacks := mini(5, int(slot.get("an_nguc_stacks", 0)) + 1)
	slot["an_nguc_stacks"] = next_stacks
	var pos := _get_slot_core_pos(slot)
	var txt := "SUY YẾU! (5/5)" if next_stacks >= 5 else "ẤN NGỤC %d/5" % next_stacks
	var col := Color(1.0, 0.84, 0.24, 1.0) if next_stacks >= 5 else Color(0.88, 0.42, 1.0, 1.0)
	floating_texts.append({
		"pos": pos + Vector2(0.0, -44.0),
		"text": txt,
		"color": col,
		"elapsed_s": 0.0,
		"duration_s": 0.90 if next_stacks >= 5 else 0.72,
	})
	return next_stacks


func consume_an_nguc_weakened(slot: Dictionary) -> void:
	if slot.is_empty():
		return
	slot["an_nguc_stacks"] = 0


func clear_all_tapion_marks() -> void:
	## Clears Kentai & Ấn ngục stacks on ALL targets (called ONLY on Tapion death, zone switch, or leaving map!).
	for s in _get_combat_slots():
		s["kentai_timer_s"] = 0.0
		s["an_nguc_stacks"] = 0


func request_player_barrier() -> bool:
	if not player_spawned or player_dead or arena == null or arena.player_node == null:
		return false
	if not _is_hero_songoku_node(arena.player_node):
		return false
	if not bool(arena.player_node.call(&"trigger_barrier")):
		return false
	_hero_barrier_burst_s = 0.34
	arena.call("_request_player_action", "barrier_cast")
	player_state_changed.emit()
	return true


func request_player_energy_recover() -> bool:
	if not player_spawned or player_dead or arena == null or arena.player_node == null:
		return false
	if not _is_hero_songoku_node(arena.player_node):
		return false
	var on_ground_r: bool = bool(arena.call("is_player_grounded_for_recover"))
	if not on_ground_r:
		return false
	if not bool(arena.player_node.call(&"trigger_energy_recover", on_ground_r)):
		return false
	arena.set("player_vy", 0.0)
	arena.call("_request_player_action", "energy_recover")
	player_state_changed.emit()
	return true


func resolve_skill_target() -> Dictionary:
	refresh_pointer_valid()
	return _resolve_player_attack_target(true)


func request_player_flurry_kick() -> bool:
	if not player_spawned or player_dead or arena == null or arena.player_node == null:
		return false
	if not _is_hero_songoku_node(arena.player_node):
		return false
	if arena.player_node.has_method(&"is_hero_tapion") and bool(arena.player_node.call(&"is_hero_tapion")):
		return false
	var tgt := resolve_skill_target()
	if tgt.is_empty():
		return false
	if not bool(arena.player_node.call(&"trigger_flurry_kick")):
		return false
	_hero_flurry_hits_fired.clear()
	_face_player_toward_x(_get_slot_core_pos(tgt).x)
	arena.call("_request_player_action", "flurry_kick")
	player_state_changed.emit()
	return true


func request_player_atomic_blast() -> bool:
	if not player_spawned or player_dead or arena == null or arena.player_node == null:
		return false
	if not _is_hero_songoku_node(arena.player_node):
		return false
	if arena.player_node.has_method(&"is_hero_tapion") and bool(arena.player_node.call(&"is_hero_tapion")):
		return false
	var tgt: Dictionary = resolve_skill_target()
	if tgt.is_empty():
		return false
	if not bool(arena.player_node.call(&"trigger_atomic_blast")):
		return false
	_hero_atomic_fired = false
	_hero_atomic_pending_bolts.clear()
	_last_atomic_fire_log.clear()
	_hero_atomic_target = tgt
	var dy_tgt := 0.0
	var tcore := _get_slot_core_pos(tgt)
	_face_player_toward_x(tcore.x)
	dy_tgt = tcore.y - _get_player_core_pos().y
	var sup_y: float = float(arena.call("get_nearest_support_y_below", arena.player_node.position.x, arena.player_node.position.y))
	var pnode_a: Node2D = arena.player_node as Node2D
	var airborne: bool = bool(pnode_a.call(&"is_airborne_flight")) or (pnode_a.position.y < sup_y - 18.0)
	_hero_atomic_air_down = airborne
	var clip := "atomic_ground"
	if airborne:
		_hero_atomic_mode = "air_down"
		clip = "atomic_air_down"
	elif dy_tgt < -65.0:
		_hero_atomic_mode = "ground_up"
		clip = "atomic_ground_up"
	else:
		_hero_atomic_mode = "ground_horiz"
		clip = "atomic_ground"
	arena.call("_request_player_action", clip)
	player_state_changed.emit()
	return true


func request_player_kamehameha() -> bool:
	if not player_spawned or player_dead or arena == null or arena.player_node == null:
		return false
	if not _is_hero_songoku_node(arena.player_node):
		return false
	if arena.player_node.has_method(&"is_hero_tapion") and bool(arena.player_node.call(&"is_hero_tapion")):
		return false
	var tgt: Dictionary = resolve_skill_target()
	if tgt.is_empty():
		return false
	if player_mana + 0.001 < 80.0:
		return false
	if not bool(arena.player_node.call(&"trigger_kamehameha", player_mana)):
		return false
	if not player_infinite_mana:
		player_mana = maxf(0.0, player_mana - 80.0)
	_local_mana_grace_s = maxf(_local_mana_grace_s, 2.4)
	combat_action_emitted.emit("kamehameha_cast", "", "self", arena.player_node.position, arena.player_node.scale.x < 0.0, 0.0)
	_hero_kame_fired = false
	_hero_kame_charging = true
	_hero_kame_charge_elapsed_s = 0.0
	_hero_kame_target = tgt
	var dy_tgt := 0.0
	var tcore := _get_slot_core_pos(tgt)
	_face_player_toward_x(tcore.x)
	dy_tgt = tcore.y - _get_player_core_pos().y
	var pnode_k: Node2D = arena.player_node as Node2D
	var sup_y: float = float(arena.call("get_nearest_support_y_below", pnode_k.position.x, pnode_k.position.y))
	var airborne: bool = bool(pnode_k.call(&"is_airborne_flight")) or (pnode_k.position.y < sup_y - 18.0)
	var clip := "kame_ground_horiz"
	if airborne:
		if dy_tgt > 65.0:
			_hero_kame_mode = "air_down"
			clip = "kame_air_down"
		else:
			_hero_kame_mode = "air_horiz"
			clip = "kame_air_horiz"
	else:
		if dy_tgt < -65.0:
			_hero_kame_mode = "ground_up"
			clip = "kame_ground_up"
		else:
			_hero_kame_mode = "ground_horiz"
			clip = "kame_ground_horiz"
	arena.call("_request_player_action", clip)
	player_state_changed.emit()
	return true


func count_genki_contributing_players() -> Array[Dictionary]:
	## Returns up to 20 alive other players in the map (NEVER counts monsters or Boss Drum; STILL counts hostile PK players!).
	var out: Array[Dictionary] = []
	for rp_val in remote_player_slots.values():
		var rp: Dictionary = rp_val as Dictionary
		if rp.is_empty():
			continue
		if not bool(rp.get("alive", true)):
			continue
		var rnode := rp.get("node") as Node2D
		if rnode == null or not is_instance_valid(rnode):
			continue
		out.append(rp)
		if out.size() >= GENKI_MAX_CONTRIB_PLAYERS:
			break
	return out


func get_genki_contributing_player_count() -> int:
	return mini(GENKI_MAX_CONTRIB_PLAYERS, count_genki_contributing_players().size())


func get_genki_current_damage() -> float:
	var n_contrib: int = _genki_contrib_count if not _genki_phase.is_empty() else get_genki_contributing_player_count()
	return GENKI_BASE_DAMAGE + float(mini(GENKI_MAX_CONTRIB_PLAYERS, maxi(0, n_contrib))) * GENKI_PER_PLAYER_BONUS


func is_genki_active() -> bool:
	return not _genki_phase.is_empty()


func cancel_genki_on_player_death() -> void:
	## Owner rule 2026-11-26: if Goku dies during Genki charge/throw, Genki is immediately lost.
	_genki_phase = ""
	_genki_elapsed_s = 0.0
	_genki_throw_released = false
	_genki_contrib_count = 0
	_genki_wisp_spawn_accum_s = 0.0
	_genki_wisps.clear()
	_genki_projectiles.clear()
	if arena != null and arena.player_node != null and arena.player_node.has_method(&"cancel_genki_on_death"):
		arena.player_node.call(&"cancel_genki_on_death")


func request_player_genki() -> bool:
	if not player_spawned or player_dead or arena == null or arena.player_node == null:
		return false
	if not _is_hero_songoku_node(arena.player_node):
		return false
	if arena.player_node.has_method(&"is_hero_tapion") and bool(arena.player_node.call(&"is_hero_tapion")):
		return false
	if not _genki_phase.is_empty():
		return false
	# Air-only requirement (Owner 2026-11-26)
	var airborne_ok: bool = arena.has_method(&"is_player_airborne_for_genki") and bool(arena.call(&"is_player_airborne_for_genki"))
	if not airborne_ok:
		floating_texts.append({
			"pos": _get_player_core_pos() + Vector2(0.0, -34.0),
			"text": "CHỈ DÙNG TRÊN KHÔNG!",
			"color": Color(0.45, 0.92, 1.0, 1.0),
			"elapsed_s": 0.0,
			"duration_s": 0.70,
		})
		return false
	var eff_mana: float = 100.0 if player_infinite_mana else player_mana
	if eff_mana + 0.001 < 100.0:
		return false
	if not arena.player_node.has_method(&"trigger_genki") or not bool(arena.player_node.call(&"trigger_genki", eff_mana, true)):
		return false
	if not player_infinite_mana:
		player_mana = maxf(0.0, player_mana - 100.0)
	_local_mana_grace_s = maxf(_local_mana_grace_s, 2.4)
	cancel_auto_approach()
	_genki_phase = "charging"
	_genki_elapsed_s = 0.0
	_genki_throw_released = false
	_genki_locked_facing_x = -1.0 if arena.player_node.scale.x < 0.0 else 1.0
	_genki_contrib_count = get_genki_contributing_player_count()
	_genki_wisp_spawn_accum_s = 0.0
	_genki_wisps.clear()
	combat_action_emitted.emit("genki_cast", "", "self", arena.player_node.position, _genki_locked_facing_x < 0.0, 0.0)
	arena.call("_request_player_action", "genki_cast")
	player_state_changed.emit()
	return true


func _get_atomic_hand_world_pos(goku: Node2D, c_sc: float, mode: String, hand_frame: int, bolt_idx: int = 0) -> Vector2:
	var face_x: float = -1.0 if goku.scale.x < 0.0 else 1.0
	var rel := Vector2(85.0 * face_x, -74.0)
	if mode == "ground_up":
		# Frame #7 (agu_07): both hands raised to sky — left palm (+19, -108) for bolts 0..2, right palm (+39, -105) for bolts 3..5
		rel = Vector2(19.0 * face_x, -108.0) if bolt_idx < 3 else Vector2(39.0 * face_x, -105.0)
	elif mode == "air_down":
		rel = Vector2(57.0 * face_x, -28.0) if hand_frame == 2 else Vector2(49.0 * face_x, -41.0)
	else:
		rel = Vector2(64.0 * face_x, -74.0) if hand_frame == 6 else Vector2(59.0 * face_x, -75.0)
	return goku.position + rel * c_sc


func _spawn_atomic_bolt(goku: Node2D, c_sc: float, mode: String, hand_frame: int, bolt_idx: int) -> void:
	# Always honor LIVE pointed target first; fallback to locked cast target.
	var tgt: Dictionary = _resolve_player_attack_target(true)
	if tgt.is_empty() or not bool(tgt.get("alive", false)) or not is_instance_valid(tgt.get("node")):
		tgt = _hero_atomic_target
	if not tgt.is_empty() and bool(tgt.get("alive", false)) and is_instance_valid(tgt.get("node")):
		_face_player_toward_x(_get_slot_core_pos(tgt).x)
	var face_x: float = -1.0 if goku.scale.x < 0.0 else 1.0
	var hand_pos: Vector2 = _get_atomic_hand_world_pos(goku, c_sc, mode, hand_frame, bolt_idx)
	var dir_vec: Vector2 = Vector2(face_x, 0.0)
	if mode == "air_down":
		dir_vec = Vector2(face_x * 0.72, 0.69).normalized()
	elif mode == "ground_up":
		dir_vec = Vector2(face_x * 0.74, -0.67).normalized()
	if not tgt.is_empty() and bool(tgt.get("alive", false)) and is_instance_valid(tgt.get("node")):
		var dv: Vector2 = _get_slot_core_pos(tgt) - hand_pos
		if dv.length() > 4.0:
			dir_vec = dv.normalized()
	# PA A: Sheet 23 yellow hand muzzle flash + fixed 30 px clearance outside largest frame-2 muzzle tip (138/256)
	var muzzle_draw_sz: float = 92.0 * c_sc
	var muzzle_max_len: float = (138.0 / 256.0) * muzzle_draw_sz
	var muzzle_tip: Vector2 = hand_pos + dir_vec * muzzle_max_len
	var bolt_half_len: float = 28.0 * c_sc
	var spawn_pos: Vector2 = muzzle_tip + dir_vec * (30.0 + bolt_half_len)
	_hero_atomic_muzzle_flashes.append({
		"pos": hand_pos,
		"dir": dir_vec,
		"age_s": 0.0,
		"duration_s": 0.13,
		"size": muzzle_draw_sz,
		"hand_frame": hand_frame,
		"mode": mode,
	})
	# PA A: Curved quadratic Bezier arcs (3 alternating curves per hand converging tail-to-tail onto target)
	var local_i: int = bolt_idx % 3
	var arc_sign: float = -1.0 if local_i == 0 else (0.35 if local_i == 1 else 1.0)
	var arc_amp: float = 92.0 if local_i == 0 else (36.0 if local_i == 1 else 88.0)
	var end_pos: Vector2 = _get_slot_core_pos(tgt) if (not tgt.is_empty() and bool(tgt.get("alive", false)) and is_instance_valid(tgt.get("node"))) else (spawn_pos + dir_vec * 960.0)
	_hero_skill_projectiles.append({
		"pos": spawn_pos,
		"start_pos": spawn_pos,
		"end_pos": end_pos,
		"t_prog": 0.0,
		"arc_sign": arc_sign,
		"arc_amp": arc_amp,
		"dir": dir_vec,
		"speed": 1500.0 if mode == "air_down" else 2500.0,
		"life_s": 1.8,
		"age_s": 0.0,
		"air_down": mode == "air_down",
		"mode": mode,
		"hand_frame": hand_frame,
		"bolt_idx": bolt_idx,
		"damage": 55.0,
		"target": tgt,
		"ignore_terrain": false,
	})
	_last_atomic_fire_log.append({
		"bolt_idx": bolt_idx,
		"mode": mode,
		"hand_frame": hand_frame,
		"hand_pos": hand_pos,
		"muzzle_tip": muzzle_tip,
		"spawn_pos": spawn_pos,
		"rear_gap_px": spawn_pos.distance_to(muzzle_tip) - bolt_half_len,
		"arc_sign": arc_sign,
		"arc_amp": arc_amp,
		"time_s": _sim_time_s,
	})


func _fire_hero_kame_beam(goku: Node2D, c_sc: float) -> void:
	_hero_kame_fired = true
	_hero_kame_charging = false
	var tgt: Dictionary = _resolve_player_attack_target(true)
	if tgt.is_empty() or not bool(tgt.get("alive", false)) or not is_instance_valid(tgt.get("node")):
		tgt = _hero_kame_target
	if not tgt.is_empty() and bool(tgt.get("alive", false)) and is_instance_valid(tgt.get("node")):
		_face_player_toward_x(_get_slot_core_pos(tgt).x)
	var face_x: float = -1.0 if goku.scale.x < 0.0 else 1.0
	var hand_pos: Vector2 = goku.position + Vector2(44.0 * face_x * c_sc, -64.0 * c_sc)
	var dir_vec: Vector2 = Vector2(face_x, 0.0)
	if _hero_kame_mode == "ground_up":
		dir_vec = Vector2(face_x * 0.75, -0.66).normalized()
	elif _hero_kame_mode == "air_down":
		dir_vec = Vector2(face_x * 0.75, 0.66).normalized()
	var max_len: float = 950.0
	if not tgt.is_empty():
		var dv_k: Vector2 = _get_slot_core_pos(tgt) - hand_pos
		if dv_k.length() > 8.0:
			dir_vec = dv_k.normalized()
			max_len = maxf(dv_k.length() + 36.0, 180.0)
	_hero_kame_beams.append({
		"start": hand_pos,
		"dir": dir_vec,
		"speed": 3000.0,
		"cur_len": 56.0,
		"max_len": max_len,
		"mode": _hero_kame_mode,
		"age_s": 0.0,
		"hold_s": 0.0,
		"fade_s": 0.18,
		"fade_age_s": 0.0,
		"fading": false,
		"duration_s": 0.18,
		"scale_mul": 1.20,
		"target": tgt,
		"hit_ids": [],
		"damage": 360.0,
		"ignore_terrain": false,
	})


func _get_kame_hand_center(goku: Node2D, c_sc: float, anim: String) -> Vector2:
	var face_kx: float = -1.0 if goku.scale.x < 0.0 else 1.0
	if anim == "kame_air_horiz" or anim == "kame_air_down":
		return goku.position + Vector2(-12.0 * face_kx * c_sc, -68.0 * c_sc)
	return goku.position + Vector2(-16.0 * face_kx * c_sc, -52.0 * c_sc)


func _step_hero_phase2_skills(delta: float) -> void:
	if arena == null or arena.player_node == null or not _is_hero_songoku_node(arena.player_node):
		return
	if _hero_barrier_burst_s > 0.0:
		_hero_barrier_burst_s = maxf(0.0, _hero_barrier_burst_s - delta)
	var goku: Node2D = arena.player_node as Node2D
	var c_sc: float = float(arena.char_scale)
	var pspr := goku.get_node_or_null("Sprite") as AnimatedSprite2D
	if pspr == null:
		return
	var anim := String(pspr.animation)
	var frame := pspr.frame

	# 1. Energy Recovery (`06`, 3.0s): loops #2 -> #3 -> #4 -> #5 -> #2... (or Tapion #3..#14 -> #3) cleanly for full 3s while restoring HP + Armor + Flight KI!
	var is_tapion_p2: bool = goku.has_method(&"is_hero_tapion") and bool(goku.call(&"is_hero_tapion"))
	var rec_rem := float(goku.get("recover_timer_s"))
	if rec_rem > 0.0:
		player_hp = minf(player_max_hp, player_hp + 350.0 * delta)
		player_armor = minf(player_max_armor, player_armor + 40.0 * delta)
		player_armor_broken_timer_s = 0.0
		var cur_ki := float(goku.get("ki"))
		var max_ki := float(goku.get("max_ki"))
		goku.set("ki", minf(max_ki, cur_ki + 20.0 * delta))
		goku.set("ki_exhausted", false)
		if anim == "energy_recover" and rec_rem > 0.22:
			if is_tapion_p2:
				if frame >= 15:
					pspr.set_frame_and_progress(3, 0.0)
			elif frame >= 6:
				pspr.set_frame_and_progress(2, 0.0)
		player_state_changed.emit()

	# Tapion handles all offensive signature skills inside TapionHeroFighter2D; never advance Goku-only Phase 2 skills on Tapion.
	if is_tapion_p2:
		return

	# 2. Flurry Kick (`26`, v10.2): auto-lunges forward, 30% slower kicks, +50px expanded AoE range (215x160px), stuns ALL enemies in range!
	if anim == "flurry_kick" and pspr.is_playing():
		var face_x: float = -1.0 if goku.scale.x < 0.0 else 1.0
		var is_air_f: bool = bool(goku.call(&"is_airborne_flight"))
		var lunge_spd: float = FLURRY_KICK_LUNGE_SPEED_PX_S if frame <= 6 else 80.0
		arena.call("_move_player_horizontal", face_x * lunge_spd * delta, is_air_f)
		var hit_frames: Array[int] = [1, 2, 3, 4, 5, 6, 7]
		for hf in hit_frames:
			if frame >= hf and not _hero_flurry_hits_fired.has(hf):
				_hero_flurry_hits_fired.append(hf)
				var p_core: Vector2 = _get_player_core_pos()
				for s in _get_combat_slots():
					if not can_attack_slot(s):
						continue
					var s_core: Vector2 = _get_slot_core_pos(s)
					var dx: float = (s_core.x - p_core.x) * face_x
					var dy: float = absf(s_core.y - p_core.y)
					if dx >= -FLURRY_KICK_RANGE_BACK_PX and dx <= FLURRY_KICK_RANGE_FWD_PX and dy <= FLURRY_KICK_RANGE_V_PX:
						_emit_slot_combat_action("flurry_kick", s, goku.position, 30.0, 0.45)
						apply_damage_to_slot(s, 30.0, 14.0, s_core, "melee", false, Vector2(face_x, 0.0))
						apply_hard_stun_to_slot(s, 1.6)
						player_mana = minf(player_max_mana, player_mana + 8.0)
						player_state_changed.emit()

	# 3. Atomic Blast: 3 bolts on left hand (#6 / #2) -> then 3 bolts on right hand (#7 / #3), with Sheet 23 muzzle sparks!
	for mfi in range(_hero_atomic_muzzle_flashes.size() - 1, -1, -1):
		var mf: Dictionary = _hero_atomic_muzzle_flashes[mfi]
		mf["age_s"] = float(mf.get("age_s", 0.0)) + delta
		if float(mf["age_s"]) >= float(mf.get("duration_s", 0.13)):
			_hero_atomic_muzzle_flashes.remove_at(mfi)

	for bi in range(_hero_atomic_pending_bolts.size() - 1, -1, -1):
		var pb: Dictionary = _hero_atomic_pending_bolts[bi]
		pb["delay_s"] = float(pb.get("delay_s", 0.0)) - delta
		if float(pb["delay_s"]) <= 0.0:
			var p_mode: String = str(pb.get("mode", _hero_atomic_mode))
			var h_frame: int = int(pb.get("hand_frame", 6))
			var b_idx: int = int(pb.get("bolt_idx", 0))
			_hero_atomic_pending_bolts.remove_at(bi)
			if anim in ["atomic_ground", "atomic_ground_up", "atomic_air_down"]:
				pspr.set_frame_and_progress(h_frame, 0.0)
			_spawn_atomic_bolt(goku, c_sc, p_mode, h_frame, b_idx)

	if anim in ["atomic_ground", "atomic_ground_up", "atomic_air_down"] and pspr.is_playing() and not _hero_atomic_fired:
		var release_f: int = 2 if anim == "atomic_air_down" else (7 if anim == "atomic_ground_up" else 6)
		if frame >= release_f:
			_hero_atomic_fired = true
			var f_left: int = 2 if anim == "atomic_air_down" else (7 if anim == "atomic_ground_up" else 6)
			var f_right: int = 3 if anim == "atomic_air_down" else 7
			var mode_s: String = "air_down" if anim == "atomic_air_down" else ("ground_up" if anim == "atomic_ground_up" else "ground_horiz")
			pspr.set_frame_and_progress(f_left, 0.0)
			_spawn_atomic_bolt(goku, c_sc, mode_s, f_left, 0)
			_hero_atomic_pending_bolts.append({"delay_s": 0.070, "mode": mode_s, "hand_frame": f_left, "bolt_idx": 1})
			_hero_atomic_pending_bolts.append({"delay_s": 0.140, "mode": mode_s, "hand_frame": f_left, "bolt_idx": 2})
			_hero_atomic_pending_bolts.append({"delay_s": 0.220, "mode": mode_s, "hand_frame": f_right, "bolt_idx": 3})
			_hero_atomic_pending_bolts.append({"delay_s": 0.290, "mode": mode_s, "hand_frame": f_right, "bolt_idx": 4})
			_hero_atomic_pending_bolts.append({"delay_s": 0.360, "mode": mode_s, "hand_frame": f_right, "bolt_idx": 5})

	# 4. Kamehameha (`28` 7-frame / `29/30/27` 6-frame): ~2.0s charge (0.0..0.34s gather #0->#1, 0.34..2.0s pulsing #2->#3->#4 with Sheet 28 rings+6 rays & cyan reflection) -> fire at #5!
	# Single seamless beam @ 3000 px/s (+20% size, NO 1.0s hold!), vanishes immediately via Sheet 31 Column 2 top->bottom fade upon hitting target, ignoring terrain!
	if anim in ["kame_ground_horiz", "kame_ground_up", "kame_air_horiz", "kame_air_down"] and pspr.is_playing() and not _hero_kame_fired:
		if frame >= 5:
			_fire_hero_kame_beam(goku, c_sc)
		elif _hero_kame_charging:
			_hero_kame_charge_elapsed_s += delta
			var charge_dur: float = 2.0
			if _hero_kame_charge_elapsed_s < 0.16:
				pspr.set_frame_and_progress(0, 0.0)
			elif _hero_kame_charge_elapsed_s < 0.34:
				pspr.set_frame_and_progress(1, 0.0)
			elif _hero_kame_charge_elapsed_s < charge_dur:
				# 4 crisp contracting/flaring pulse cycles (#2 -> #3 -> #4) over 1.66s, ending on peak shouting #4!
				var phase_t: float = (_hero_kame_charge_elapsed_s - 0.34) / maxf(0.01, charge_dur - 0.34)
				var step_i: int = mini(11, int(floor(phase_t * 12.0)))
				var charge_f: int = 2 + (step_i % 3)
				pspr.set_frame_and_progress(charge_f, 0.0)
			else:
				pspr.set_frame_and_progress(5, 0.0)
				_fire_hero_kame_beam(goku, c_sc)
	elif _hero_kame_charging and anim not in ["kame_ground_horiz", "kame_ground_up", "kame_air_horiz", "kame_air_down"]:
		_hero_kame_charging = false
		_hero_kame_charge_elapsed_s = 0.0

	# 5. Son Goku Genki (Spirit Bomb): 5.0s mid-air overhead charge + cyan wisps from up to 20 players + downward ground throw (50..200px ahead)!
	_step_hero_genki_cast(delta, goku, pspr, c_sc)


func _step_hero_skill_projectiles_and_beams(delta: float) -> void:
	# Atomic Blast curved quadratic Bezier bolts with AGENTS.md Điều 7.8 solid terrain collision (ignore_terrain=false)
	for i in range(_hero_skill_projectiles.size() - 1, -1, -1):
		var pr: Dictionary = _hero_skill_projectiles[i]
		pr["age_s"] = float(pr["age_s"]) + delta
		var old_p: Vector2 = pr["pos"] as Vector2
		var dir_v: Vector2 = pr["dir"] as Vector2
		var tgt: Dictionary = pr.get("target", {})
		var spd: float = float(pr["speed"])
		var step_dist: float = spd * delta
		var hit_done := false
		var has_live_tgt: bool = (not tgt.is_empty()) and can_attack_slot(tgt)
		var start_p_arc: Vector2 = pr.get("start_pos", old_p) as Vector2
		var end_p_arc: Vector2 = _get_slot_core_pos(tgt) if has_live_tgt else (pr.get("end_pos", old_p + dir_v * 900.0) as Vector2)
		pr["end_pos"] = end_p_arc
		var chord: Vector2 = end_p_arc - start_p_arc
		var chord_len: float = maxf(64.0, chord.length())
		var chord_dir: Vector2 = chord / chord_len
		var perp: Vector2 = Vector2(-chord_dir.y, chord_dir.x)
		var arc_sign: float = float(pr.get("arc_sign", 0.0))
		var arc_amp: float = minf(float(pr.get("arc_amp", 0.0)), chord_len * 0.28)
		var ctrl_p: Vector2 = (start_p_arc + end_p_arc) * 0.5 + perp * (arc_sign * arc_amp)
		var t_next: float = minf(1.0, float(pr.get("t_prog", 0.0)) + step_dist / maxf(80.0, chord_len * 1.06))
		pr["t_prog"] = t_next
		var u: float = 1.0 - t_next
		var new_p: Vector2 = (u * u) * start_p_arc + (2.0 * u * t_next) * ctrl_p + (t_next * t_next) * end_p_arc
		var seg_d: Vector2 = new_p - old_p
		if seg_d.length() > 0.5:
			dir_v = seg_d.normalized()
			pr["dir"] = dir_v
		# Điều 7.8: Stop & explode when hitting solid terrain step/floor
		if (not bool(pr.get("ignore_terrain", false))) and arena != null and bool(arena.call("terrain_blocks_segment", old_p, new_p)):
			pr["pos"] = new_p
			_spawn_skill_explosion_33(new_p, 0.85)
			_hero_skill_projectiles.remove_at(i)
			continue
		pr["pos"] = new_p
		if has_live_tgt:
			if t_next >= 0.985 or new_p.distance_to(end_p_arc) <= maxf(58.0, step_dist + 20.0):
				pr["pos"] = end_p_arc
				var orig_a1: Vector2 = arena.player_node.position if (arena != null and arena.player_node != null) else end_p_arc
				_emit_slot_combat_action("atomic_blast", tgt, orig_a1, float(pr["damage"]), 0.45)
				apply_damage_to_slot(tgt, float(pr["damage"]), 24.0, end_p_arc, "heavy", false, dir_v)
				_spawn_skill_explosion_33(end_p_arc, 1.05)
				hit_done = true
		else:
			for s in _get_combat_slots():
				if not can_attack_slot(s):
					continue
				var sc: Vector2 = _get_slot_core_pos(s)
				if new_p.distance_to(sc) <= 72.0:
					var orig_a2: Vector2 = arena.player_node.position if (arena != null and arena.player_node != null) else sc
					_emit_slot_combat_action("atomic_blast", s, orig_a2, float(pr["damage"]), 0.45)
					apply_damage_to_slot(s, float(pr["damage"]), 24.0, sc, "heavy", false, dir_v)
					_spawn_skill_explosion_33(sc, 1.05)
					hit_done = true
					break
		if hit_done or t_next >= 1.0 or float(pr["age_s"]) >= float(pr["life_s"]):
			_hero_skill_projectiles.remove_at(i)

	# Kamehameha beams: 3000 px/s beam-head flight (+20% size) with Điều 7.8 solid terrain collision (ignore_terrain=false)
	for j in range(_hero_kame_beams.size() - 1, -1, -1):
		var bm: Dictionary = _hero_kame_beams[j]
		bm["age_s"] = float(bm["age_s"]) + delta
		var start_p: Vector2 = bm["start"] as Vector2
		var dir_v: Vector2 = bm["dir"] as Vector2
		var max_len: float = float(bm.get("max_len", 950.0))
		var tgt_k: Dictionary = bm.get("target", {})
		var is_fading: bool = bool(bm.get("fading", false))
		if not is_fading:
			if not tgt_k.is_empty() and bool(tgt_k.get("alive", false)) and is_instance_valid(tgt_k.get("node")):
				var tc: Vector2 = _get_slot_core_pos(tgt_k)
				var dv: Vector2 = tc - start_p
				if dv.length() > 8.0:
					dir_v = dv.normalized()
					bm["dir"] = dir_v
					max_len = maxf(dv.length() + 36.0, 180.0)
					bm["max_len"] = max_len
			var prev_len: float = float(bm.get("cur_len", 48.0))
			var cur_len: float = minf(max_len, prev_len + float(bm.get("speed", 3000.0)) * delta)
			var prev_tip: Vector2 = start_p + dir_v * prev_len
			var next_tip: Vector2 = start_p + dir_v * cur_len
			if (not bool(bm.get("ignore_terrain", false))) and arena != null and bool(arena.call("terrain_blocks_segment", prev_tip, next_tip)):
				bm["cur_len"] = cur_len
				bm["terrain_blocked"] = true
				bm["fading"] = true
				bm["fade_age_s"] = 0.0
				_spawn_skill_explosion_33(next_tip, 1.05)
				continue
			bm["cur_len"] = cur_len
			var hit_ids: Array = bm.get("hit_ids", [])
			var target_impacted: bool = false
			for s in _get_combat_slots():
				if not can_attack_slot(s):
					continue
				var sid := str(s.get("id", ""))
				if hit_ids.has(sid):
					continue
				var sc: Vector2 = _get_slot_core_pos(s)
				var rel: Vector2 = sc - start_p
				var proj: float = rel.dot(dir_v)
				var perp: float = absf(rel.x * (-dir_v.y) + rel.y * dir_v.x)
				var is_locked_tgt: bool = (not tgt_k.is_empty()) and str(tgt_k.get("id", "")) == sid
				if proj >= -20.0 and proj <= cur_len + 32.0 and (is_locked_tgt or perp <= 95.0):
					hit_ids.append(sid)
					var orig_k: Vector2 = arena.player_node.position if (arena != null and arena.player_node != null) else start_p
					_emit_slot_combat_action("kamehameha", s, orig_k, float(bm["damage"]), 0.45)
					apply_damage_to_slot(s, float(bm["damage"]), 60.0, sc, "heavy", false, dir_v)
					_spawn_skill_explosion_33(sc, 1.2)
					if is_locked_tgt or tgt_k.is_empty():
						target_impacted = true
			bm["hit_ids"] = hit_ids
			if target_impacted or cur_len >= max_len - 1.0:
				bm["fading"] = true
				bm["fade_age_s"] = 0.0
		else:
			bm["fade_age_s"] = float(bm.get("fade_age_s", 0.0)) + delta
			if float(bm["fade_age_s"]) >= float(bm.get("fade_s", 0.18)):
				_hero_kame_beams.remove_at(j)

	_step_hero_genki_projectiles_and_explosions(delta)


func _draw_hero_phase2_back_fx_overlays(canvas: CanvasItem) -> void:
	## Draws exact Sheet 28 contracting dark shockwave circle + concentric cyan/white rings + 6 flaring radial rays BEHIND Goku so his blue-lit face stays 100% crisp!
	if arena == null or arena.player_node == null or not _is_hero_songoku_node(arena.player_node):
		return
	var fx_sf := _get_songoku_fx_frames()
	if fx_sf == null or not fx_sf.has_animation(&"kame_charge_fx"):
		return
	var goku: Node2D = arena.player_node as Node2D
	var pspr := goku.get_node_or_null("Sprite") as AnimatedSprite2D
	if pspr == null or not pspr.is_playing():
		return
	var an := String(pspr.animation)
	if an not in ["kame_ground_horiz", "kame_ground_up", "kame_air_horiz", "kame_air_down"]:
		return
	var f_k: int = pspr.frame
	if f_k < 2 or f_k > 4:
		return
	var cfc := fx_sf.get_frame_count(&"kame_charge_fx")
	if cfc <= 0:
		return
	var stage_i: int = clampi(f_k - 2, 0, cfc - 1)
	var ctex := fx_sf.get_frame_texture(&"kame_charge_fx", stage_i)
	if ctex == null:
		return
	var c_sc: float = float(arena.char_scale)
	var hand_c: Vector2 = _get_kame_hand_center(goku, c_sc, an)
	# Exact Sheet 28 ratio (323px dark ring for 147px Goku -> 264px for 120px Goku)
	var csz: float = 264.0 * c_sc
	var face_kx: float = -1.0 if goku.scale.x < 0.0 else 1.0
	# Subtle rhythmic rotation around Goku's hands while keeping exact 6-ray progressive contraction!
	var rot_a: float = sin(_sim_time_s * 5.0) * 0.14 * face_kx
	canvas.draw_set_transform(hand_c, rot_a, Vector2(face_kx, 1.0))
	canvas.draw_texture_rect(ctex, Rect2(-csz * 0.5, -csz * 0.5, csz, csz), false, Color.WHITE)
	canvas.draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)


func _draw_hero_phase2_fx_overlays(canvas: CanvasItem) -> void:
	if arena == null or arena.player_node == null or not _is_hero_songoku_node(arena.player_node):
		return
	var fx_sf := _get_songoku_fx_frames()
	if fx_sf == null:
		return
	var goku: Node2D = arena.player_node as Node2D
	var is_tapion_ov: bool = goku.has_method(&"is_hero_tapion") and bool(goku.call(&"is_hero_tapion"))
	var c_sc: float = float(arena.char_scale)
	var p_core: Vector2 = _get_player_core_pos()

	# 1. Protective Barrier FX (05): burst sphere -> LOOP 10S rotating shield while Hero moves/fights freely!
	#    Goku: golden `barrier_burst_fx` -> `barrier_loop_fx` (178px centered on p_core).
	#    Tapion: electric-blue hollow `barrier_dome_fx` (204px -> exact ~153px ring diameter centered on p_core,
	#    matching Goku's protective ring framing & 100% visible across ground/jump/fly/attack!).
	var b_rem := float(goku.get("barrier_timer_s"))
	if b_rem > 0.0:
		if is_tapion_ov:
			var pspr_b := goku.get_node_or_null("Sprite") as AnimatedSprite2D
			var casting_bar := pspr_b != null and String(pspr_b.animation) == "barrier_cast" and pspr_b.is_playing() and pspr_b.frame < 8
			if not casting_bar:
				var tfx := _get_tapion_fx_frames()
				if tfx != null and tfx.has_animation(&"barrier_dome_fx"):
					var tfc := tfx.get_frame_count(&"barrier_dome_fx")
					if tfc > 0:
						var tfi := (tfc - 1) if (b_rem <= 0.25 and tfc >= 5) else (int(floor(_sim_time_s * 10.0)) % maxi(1, mini(4, tfc)))
						var ttex := tfx.get_frame_texture(&"barrier_dome_fx", tfi)
						if ttex != null:
							var tsz: float = 228.0 * c_sc
							canvas.draw_texture_rect(ttex, Rect2(p_core - Vector2(tsz * 0.5, tsz * 0.5), Vector2(tsz, tsz)), false, Color.WHITE)
		else:
			var b_clip := &"barrier_burst_fx" if _hero_barrier_burst_s > 0.0 else &"barrier_loop_fx"
			if fx_sf.has_animation(b_clip):
				var fc := fx_sf.get_frame_count(b_clip)
				if fc > 0:
					var fi := int(floor(_sim_time_s * (15.0 if _hero_barrier_burst_s > 0.0 else 8.0))) % fc
					var tex := fx_sf.get_frame_texture(b_clip, fi)
					if tex != null:
						var sz: float = 178.0 * c_sc
						canvas.draw_texture_rect(tex, Rect2(p_core - Vector2(sz * 0.5, sz * 0.5), Vector2(sz, sz)), false, Color.WHITE)

	# 2. Kamehameha FRONT hand VFX (Sheet 28 exact pixel gather on #0..#1 + blazing front core orb on #2..#4, while rings+rays render BEHIND Goku!)
	var pspr := goku.get_node_or_null("Sprite") as AnimatedSprite2D
	if pspr != null and pspr.is_playing():
		var an := String(pspr.animation)
		if an in ["kame_ground_horiz", "kame_ground_up", "kame_air_horiz", "kame_air_down"]:
			var f_k: int = pspr.frame
			var face_kx: float = -1.0 if goku.scale.x < 0.0 else 1.0
			var hand_c: Vector2 = _get_kame_hand_center(goku, c_sc, an)
			if f_k >= 0 and f_k <= 1 and fx_sf.has_animation(&"kame_gather_fx"):
				var gfc := fx_sf.get_frame_count(&"kame_gather_fx")
				if gfc > 0:
					var gtex := fx_sf.get_frame_texture(&"kame_gather_fx", clampi(f_k, 0, gfc - 1))
					if gtex != null:
						var gsz: float = 148.0 * c_sc
						canvas.draw_set_transform(hand_c, 0.0, Vector2(face_kx, 1.0))
						canvas.draw_texture_rect(gtex, Rect2(-gsz * 0.5, -gsz * 0.5, gsz, gsz), false, Color.WHITE)
						canvas.draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
			elif f_k >= 2 and f_k <= 4 and fx_sf.has_animation(&"kame_orb_front_fx"):
				var ofc := fx_sf.get_frame_count(&"kame_orb_front_fx")
				if ofc > 0:
					var o_stage: int = clampi(f_k - 2, 0, ofc - 1)
					var otex := fx_sf.get_frame_texture(&"kame_orb_front_fx", o_stage)
					if otex != null:
						var osz: float = 264.0 * c_sc
						canvas.draw_set_transform(hand_c, 0.0, Vector2(face_kx, 1.0))
						canvas.draw_texture_rect(otex, Rect2(-osz * 0.5, -osz * 0.5, osz, osz), false, Color.WHITE)
						canvas.draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)

	# 3a. Sheet 23 Yellow Hand Muzzle Sparks (clean 3-frame unclipped flash synced to firing hand & launch angle!)
	if fx_sf.has_animation(&"atomic_fx_muzzle"):
		var mfc: int = fx_sf.get_frame_count(&"atomic_fx_muzzle")
		if mfc > 0:
			for mf in _hero_atomic_muzzle_flashes:
				var m_age: float = float(mf.get("age_s", 0.0))
				var m_dur: float = maxf(0.01, float(mf.get("duration_s", 0.13)))
				var mfi: int = clampi(int(floor((m_age / m_dur) * float(mfc))), 0, mfc - 1)
				var mtex := fx_sf.get_frame_texture(&"atomic_fx_muzzle", mfi)
				if mtex != null:
					var mpos: Vector2 = mf["pos"] as Vector2
					var mdir: Vector2 = mf["dir"] as Vector2
					var msz: float = float(mf.get("size", 92.0 * c_sc))
					canvas.draw_set_transform(mpos, mdir.angle(), Vector2.ONE)
					canvas.draw_texture_rect(mtex, Rect2(-64.0 / 256.0 * msz, -0.5 * msz, msz, msz), false, Color.WHITE)
					canvas.draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)

	# 3b. Active Atomic Blast 6x curved homing bolts (rotated along live curved tangent, ZERO blink!)
	for pr in _hero_skill_projectiles:
		if fx_sf.has_animation(&"atomic_fx_horiz"):
			var pfc: int = fx_sf.get_frame_count(&"atomic_fx_horiz")
			if pfc > 0:
				# Skip tiny muzzle spark frame #0 (`atomic_horiz_00` = 831px) so in-flight bolts ONLY cycle full blazing frames #1..#2 (`5500px`) with ZERO blink!
				var pfi: int = (1 + int(floor(float(pr["age_s"]) * 18.0)) % maxi(1, pfc - 1)) if pfc > 1 else 0
				var ptex := fx_sf.get_frame_texture(&"atomic_fx_horiz", clampi(pfi, 0, pfc - 1))
				if ptex != null:
					var ppos: Vector2 = pr["pos"] as Vector2
					var dvec: Vector2 = pr["dir"] as Vector2
					var psz: float = 128.0 * c_sc
					canvas.draw_set_transform(ppos, dvec.angle(), Vector2.ONE)
					canvas.draw_texture_rect(ptex, Rect2(-psz * 0.5, -psz * 0.5, psz, psz), false, Color.WHITE)
					canvas.draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)

	# 4. Active Kamehameha seamless multi-segment beam (Sheet 31 Col 1 cycling layers @ 3000 px/s, +20% size -> Col 2 top->bottom shrink fade!)
	for bm in _hero_kame_beams:
		var age: float = float(bm["age_s"])
		var is_fading: bool = bool(bm.get("fading", false))
		var fade_s: float = float(bm.get("fade_s", 0.18))
		var fade_age: float = float(bm.get("fade_age_s", 0.0))
		var start_p: Vector2 = bm["start"] as Vector2
		var dir_v: Vector2 = bm["dir"] as Vector2
		var b_len: float = maxf(64.0, float(bm.get("cur_len", 64.0)))
		var beam_mul: float = float(bm.get("scale_mul", 1.20))
		var ang: float = dir_v.angle()
		canvas.draw_set_transform(start_p, ang, Vector2.ONE)
		if (not is_fading) and fx_sf.has_animation(&"kame_h_orig") and fx_sf.has_animation(&"kame_h_mid") and fx_sf.has_animation(&"kame_h_head"):
			# 3-frame multi-layer cycling energy surge (Sheet 31 Col 1: 24 Hz cycling + per-segment layer offset to avoid static sliding!)
			var fi: int = int(floor(age * 24.0)) % 3
			var t_orig := fx_sf.get_frame_texture(&"kame_h_orig", fi)
			var t_head := fx_sf.get_frame_texture(&"kame_h_head", fi)
			var bh: float = 128.0 * beam_mul * c_sc
			var cell_sc: float = bh / 256.0
			var cap_w: float = 180.0 * cell_sc
			var pad_l: float = 76.0 * cell_sc
			var tile_w: float = 256.0 * cell_sc
			var orig_end: float = cap_w
			var head_x: float = maxf(orig_end - 2.0, b_len - cap_w)
			# 4a) Seamless tiled middle shaft cycling across the 3 Sheet 31 rows per tile!
			if head_x > orig_end - 1.0:
				var span: float = head_x - orig_end + 4.0
				if span <= tile_w:
					var t_mid0 := fx_sf.get_frame_texture(&"kame_h_mid", fi)
					if t_mid0 != null:
						canvas.draw_texture_rect(t_mid0, Rect2(orig_end - 2.0, -bh * 0.5, span, bh), false, Color.WHITE)
				else:
					var cx: float = orig_end - 2.0
					var limit_x: float = head_x + 2.0
					var tile_idx: int = 0
					while cx + tile_w < limit_x:
						var t_mid_i := fx_sf.get_frame_texture(&"kame_h_mid", (fi + tile_idx) % 3)
						if t_mid_i != null:
							canvas.draw_texture_rect(t_mid_i, Rect2(cx, -bh * 0.5, tile_w, bh), false, Color.WHITE)
						cx += tile_w - 1.0
						tile_idx += 1
					var t_mid_last := fx_sf.get_frame_texture(&"kame_h_mid", (fi + tile_idx) % 3)
					if t_mid_last != null:
						canvas.draw_texture_rect(t_mid_last, Rect2(limit_x - tile_w, -bh * 0.5, tile_w, bh), false, Color.WHITE)
			# 4b) Origin sphere flush at start_p
			if t_orig != null:
				canvas.draw_texture_rect(t_orig, Rect2(-pad_l, -bh * 0.5, tile_w, bh), false, Color.WHITE)
			# 4c) Front impact head flush at head_x
			if t_head != null:
				canvas.draw_texture_rect(t_head, Rect2(head_x, -bh * 0.5, tile_w, bh), false, Color.WHITE)
		elif fx_sf.has_animation(&"kame_h_fade"):
			# Sheet 31 Column 2 (top -> middle -> bottom shrinking beam: frames 0 -> 1 -> 2, +20% size matching Column 1!)
			var fade_prog: float = clampf(fade_age / maxf(0.01, fade_s), 0.0, 0.999)
			var f_idx: int = clampi(int(floor(fade_prog * 3.0)), 0, 2)
			var t_fade := fx_sf.get_frame_texture(&"kame_h_fade", f_idx)
			if t_fade != null:
				var fh: float = 128.0 * beam_mul * c_sc
				canvas.draw_texture_rect(t_fade, Rect2(0.0, -fh * 0.5, b_len, fh), false, Color.WHITE)
		canvas.draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)

	# 5. Son Goku Genki overhead Spirit Bomb, blue top-down reflection on Goku, and incoming cyan energy wisps from players!
	_draw_hero_genki_charge_and_reflection(canvas, goku, c_sc)


func _draw_kentai_burn_on_rect(canvas: CanvasItem, body_rect: Rect2, phase_seed: float = 0.0) -> void:
	## Refined crisp micro pixel-art green flame+smoke burn points (~10-14px each) burning directly ON the
	## victim's body silhouette and disappearing organically by staggered density (Owner 2026-11-26).
	if body_rect.size.x < 4.0 or body_rect.size.y < 4.0:
		return
	var tfx := _get_tapion_fx_frames()
	if tfx != null and tfx.has_animation(&"kentai_burn_fx"):
		var fc: int = tfx.get_frame_count(&"kentai_burn_fx")
		if fc > 0:
			# 7 organic burn sites strictly inside body_rect (avoiding empty outer halo) with staggered cycle phases
			# so individual ~10px micro-flames ignite, flicker, puff dark-green smoke, and vanish naturally by density!
			const BURN_POINTS := [
				[0.34, 0.28, 0.00, 1.00],
				[0.64, 0.34, 0.31, 0.92],
				[0.48, 0.48, 0.62, 1.08],
				[0.28, 0.56, 0.17, 0.88],
				[0.68, 0.60, 0.78, 0.96],
				[0.42, 0.72, 0.45, 0.90],
				[0.56, 0.22, 0.89, 0.85],
			]
			# Subtle pixel-art ~10-14px flame sprite (24px canvas tile -> ~10-13px crisp visible flame core!)
			var base_tile: float = clampf(minf(body_rect.size.x, body_rect.size.y) * 0.24, 18.0, 26.0)
			for bp in BURN_POINTS:
				var u: float = float(bp[0])
				var v: float = float(bp[1])
				var p_off: float = float(bp[2])
				var sz_mul: float = float(bp[3])
				# Cycle with natural staggered off-duty density window (active 74% of cycle, rests 26% before re-igniting)
				var cycle: float = fposmod(_sim_time_s * 1.45 + phase_seed * 0.37 + p_off, 1.0)
				if cycle >= 0.74:
					continue
				var life: float = cycle / 0.74
				var fi: int = clampi(int(floor(life * float(fc))), 0, fc - 1)
				var tex := tfx.get_frame_texture(&"kentai_burn_fx", fi)
				if tex == null:
					continue
				var tile_px: float = roundf(base_tile * sz_mul)
				# Gentle organic rise as flame burns -> turns to dark-green smoke -> disappears
				var rise_y: float = -life * 6.0
				var sway_x: float = sin((_sim_time_s * 6.0) + p_off * 12.0) * 1.8
				var px: float = roundf(body_rect.position.x + body_rect.size.x * u + sway_x - tile_px * 0.5)
				var py: float = roundf(body_rect.position.y + body_rect.size.y * v + rise_y - tile_px * 0.58)
				var alpha_f: float = 0.96 if life < 0.78 else clampf((1.0 - life) / 0.22, 0.0, 0.96)
				canvas.draw_texture_rect(tex, Rect2(Vector2(px, py), Vector2(tile_px, tile_px)), false, Color(1.0, 1.0, 1.0, alpha_f))
			return
	OverheadBarsDrawScript.draw_kentai_green_burn_fx(canvas, body_rect, _sim_time_s)


func draw_ambient_flash_overlays(canvas: CanvasItem) -> void:
	## Soft luminous whole-area ambient flash rendered on z_index=5 (ABOVE map/trees, BELOW all characters/monsters/bosses!)
	## Triggered on Genki impact frames 11..12 -> explosion 13..16 so every fighter being hit remains 100% clear and visible!
	if not active or _genki_ambient_flash_s <= 0.0:
		return
	var dur: float = maxf(0.05, _genki_ambient_flash_dur_s)
	var prog: float = clampf(1.0 - (_genki_ambient_flash_s / dur), 0.0, 1.0)
	# Quick smooth lift over first 18% (frames 11..12), soft sustained glow through 13..15, smooth fade-out at 16
	var env: float = clampf(prog / 0.18, 0.0, 1.0) if prog < 0.18 else clampf(1.0 - ((prog - 0.18) / 0.82), 0.0, 1.0)
	var area_alpha: float = 0.24 * env
	var bloom_alpha: float = 0.28 * env
	# Cover full world/camera span generously
	var rect := Rect2(-400.0, -400.0, 8200.0, 2400.0)
	canvas.draw_rect(rect, Color(0.76, 0.95, 1.0, area_alpha), true)
	# Soft radial atmospheric glow behind characters centered at impact zone
	canvas.draw_circle(_genki_ambient_flash_pos, 720.0, Color(0.56, 0.92, 1.0, bloom_alpha * 0.55))
	canvas.draw_circle(_genki_ambient_flash_pos, 420.0, Color(0.88, 0.98, 1.0, bloom_alpha * 0.70))


func _get_genki_orb_pos(goku: Node2D, c_sc: float) -> Vector2:
	# Elevated directly above Goku's raised hands matching Owner's reference (image copy 4.png)
	return goku.position + Vector2(0.0, -210.0 * c_sc)


func _step_hero_genki_cast(delta: float, goku: Node2D, pspr: AnimatedSprite2D, c_sc: float) -> void:
	if _genki_cc_notice_cd_s > 0.0:
		_genki_cc_notice_cd_s = maxf(0.0, _genki_cc_notice_cd_s - delta)
	# Advance active cyan energy wisps toward the overhead Genki orb
	var orb_now: Vector2 = _get_genki_orb_pos(goku, c_sc)
	for wi in range(_genki_wisps.size() - 1, -1, -1):
		var w: Dictionary = _genki_wisps[wi]
		w["age_s"] = float(w.get("age_s", 0.0)) + delta
		w["end_pos"] = orb_now
		if float(w["age_s"]) >= float(w.get("dur_s", 0.65)):
			_genki_wisps.remove_at(wi)

	if _genki_phase.is_empty():
		return
	if player_dead or goku == null or not is_instance_valid(goku):
		cancel_genki_on_player_death()
		return

	# Keep Goku locked to his initial Genki facing direction & suspended in mid-air
	goku.scale.x = absf(goku.scale.x) * _genki_locked_facing_x
	if arena != null:
		arena.player_facing_left = _genki_locked_facing_x < 0.0

	if _genki_phase == "charging":
		_genki_elapsed_s += delta
		var contribs: Array[Dictionary] = count_genki_contributing_players()
		_genki_contrib_count = mini(GENKI_MAX_CONTRIB_PLAYERS, contribs.size())

		# 10-frame genki_cast (Owner image copy 4.png + 4 fluttering overhead loop frames @ 120ms):
		# #0 ready -> #1 arms raising -> #2 arms overhead -> loop #3..#6 (hair/gi/sash fluttering @ 120ms!) for full 5.0s!
		if pspr != null and pspr.sprite_frames != null and pspr.sprite_frames.has_animation(&"genki_cast"):
			if String(pspr.animation) != "genki_cast" or not pspr.is_playing():
				pspr.play(&"genki_cast")
			var fc_g: int = pspr.sprite_frames.get_frame_count(&"genki_cast")
			var target_f: int = 2
			if _genki_elapsed_s < 0.12:
				target_f = 0
			elif _genki_elapsed_s < 0.24:
				target_f = 1
			elif _genki_elapsed_s < 0.36 or fc_g < 10:
				target_f = 2
			else:
				var hold_idx: int = int(floor((_genki_elapsed_s - 0.36) / GENKI_CHARGE_FRAME_S)) % 4
				target_f = 3 + hold_idx
			pspr.set_frame_and_progress(clampi(target_f, 0, maxi(0, fc_g - 1)), 0.0)

		# Continuously emit bright cyan energy streaks from every contributing player (up to 20, incl. PK hostile, excl. monsters/boss!)
		_genki_wisp_spawn_accum_s += delta
		if _genki_wisp_spawn_accum_s >= 0.11:
			_genki_wisp_spawn_accum_s = 0.0
			for ci in range(contribs.size()):
				var rp: Dictionary = contribs[ci]
				var rp_core: Vector2 = _get_slot_core_pos(rp)
				var jitter := Vector2(
					sin(_sim_time_s * 17.3 + float(ci) * 2.1) * 22.0,
					cos(_sim_time_s * 13.7 + float(ci) * 1.7) * 18.0 - 16.0
				)
				var start_p: Vector2 = rp_core + jitter
				var mid_p: Vector2 = (start_p + orb_now) * 0.5 + Vector2(0.0, -90.0 - 35.0 * absf(sin(float(ci) * 1.3 + _sim_time_s * 2.0)))
				_genki_wisps.append({
					"start_pos": start_p,
					"ctrl_pos": mid_p,
					"end_pos": orb_now,
					"age_s": 0.0,
					"dur_s": 0.58 + 0.08 * fposmod(float(ci) * 0.37 + _sim_time_s, 1.0),
					"from_player": true,
				})
			# Cap wisp buffer safely for mobile 60 FPS
			while _genki_wisps.size() > 96:
				_genki_wisps.remove_at(0)

		if _genki_elapsed_s >= GENKI_CHARGE_DURATION_S:
			_genki_phase = "throwing"
			_genki_elapsed_s = 0.0
			_genki_throw_released = false
			if pspr != null and pspr.sprite_frames != null and pspr.sprite_frames.has_animation(&"genki_cast"):
				var fc_g2: int = pspr.sprite_frames.get_frame_count(&"genki_cast")
				pspr.set_frame_and_progress(7 if fc_g2 >= 10 else 3, 0.0)

	elif _genki_phase == "throwing":
		_genki_elapsed_s += delta
		# Exact 3-frame throw choreography from image copy 4.png:
		# #7 wind-up lunge -> #8 downward hurl + sweeping motion arc (releases orb!) -> #9 crouched follow-through!
		if pspr != null and pspr.sprite_frames != null and pspr.sprite_frames.has_animation(&"genki_cast"):
			if String(pspr.animation) != "genki_cast" or not pspr.is_playing():
				pspr.play(&"genki_cast")
			var fc_t: int = pspr.sprite_frames.get_frame_count(&"genki_cast")
			var base_throw: int = 7 if fc_t >= 10 else 3
			var throw_f: int = base_throw
			if _genki_elapsed_s >= GENKI_THROW_ARC_END_S:
				throw_f = base_throw + 2
			elif _genki_elapsed_s >= GENKI_THROW_WINDUP_S:
				throw_f = base_throw + 1
			pspr.set_frame_and_progress(clampi(throw_f, 0, maxi(0, fc_t - 1)), 0.0)

		if (not _genki_throw_released) and _genki_elapsed_s >= GENKI_THROW_RELEASE_S:
			_genki_throw_released = true
			_launch_genki_orb(goku, c_sc)

		if _genki_elapsed_s >= GENKI_THROW_DURATION_S:
			_genki_phase = ""
			_genki_elapsed_s = 0.0
			_genki_throw_released = false
			goku.set("genki_casting", false)
			if pspr != null:
				if pspr.sprite_frames != null and pspr.sprite_frames.has_animation(&"fly_prep"):
					pspr.play(&"fly_prep")
				else:
					pspr.stop()


func _launch_genki_orb(goku: Node2D, c_sc: float) -> void:
	## Throws Genki downward in front of Goku (50..200px ahead onto ground), NEVER aiming at pointed target!
	var face_x: float = _genki_locked_facing_x
	var start_pos: Vector2 = goku.position + Vector2(face_x * 56.0, -142.0 * c_sc)
	var desired_land_x: float = goku.position.x + face_x * GENKI_DEFAULT_LAND_OFFSET_PX
	var min_x: float = float(arena.walkable_min_x) + 32.0 if arena != null else desired_land_x - 500.0
	var max_x: float = float(arena.walkable_max_x) - 32.0 if arena != null else desired_land_x + 500.0
	var land_x: float = clampf(desired_land_x, min_x, max_x)
	# Ensure landing offset stays in front within [50, 200] px whenever map bounds allow
	var dx_ahead: float = (land_x - goku.position.x) * face_x
	if dx_ahead < GENKI_MIN_LAND_OFFSET_PX:
		land_x = clampf(goku.position.x + face_x * GENKI_MIN_LAND_OFFSET_PX, min_x, max_x)
	elif dx_ahead > GENKI_MAX_LAND_OFFSET_PX:
		land_x = clampf(goku.position.x + face_x * GENKI_MAX_LAND_OFFSET_PX, min_x, max_x)
	var land_y: float = goku.position.y + 180.0
	if arena != null and arena.has_method(&"get_nearest_support_y_below"):
		land_y = float(arena.call(&"get_nearest_support_y_below", land_x, goku.position.y))
	var land_pos := Vector2(land_x, land_y)
	var final_dmg: float = GENKI_BASE_DAMAGE + float(mini(GENKI_MAX_CONTRIB_PLAYERS, maxi(0, _genki_contrib_count))) * GENKI_PER_PLAYER_BONUS
	var dist_total: float = maxf(64.0, start_pos.distance_to(land_pos))
	_genki_projectiles.append({
		"start_pos": start_pos,
		"pos": start_pos,
		"land_pos": land_pos,
		"caster_x": goku.position.x,
		"face_x": face_x,
		"t": 0.0,
		"dur_s": maxf(0.12, dist_total / GENKI_ORB_FLIGHT_SPEED_PX_S),
		"age_s": 0.0,
		"damage": final_dmg,
		"contrib_count": _genki_contrib_count,
		"scale_mul": 1.0 + 0.012 * float(_genki_contrib_count),
	})


func _spawn_genki_explosion_fx(ground_pos: Vector2, scale_val: float = 1.0) -> void:
	# Exact 2-stage ground contact sequence (Owner 2026-11-26):
	# - Impact buildup `Genki/9..12` (4 * 100ms = 0.40s); at frame 11 onset (0.20s) -> micro-shake + under-entity ambient flash!
	# - Fiery explosion climax `Genki/13..16` (4 * 120ms = 0.48s) -> total 0.88s!
	_genki_explosions.append({
		"pos": ground_pos,
		"age_s": 0.0,
		"impact_dur_s": 4.0 * GENKI_IMPACT_FRAME_S,
		"explode_dur_s": 4.0 * GENKI_EXPLODE_FRAME_S,
		"dur_s": 4.0 * GENKI_IMPACT_FRAME_S + 4.0 * GENKI_EXPLODE_FRAME_S,
		"scale_val": scale_val,
		"shake_flash_fired": false,
	})


func _detonate_genki_orb(proj: Dictionary) -> void:
	var impact_pos: Vector2 = proj.get("land_pos", proj.get("pos", Vector2.ZERO)) as Vector2
	var dmg: float = float(proj.get("damage", GENKI_BASE_DAMAGE))
	var contrib_n: int = int(proj.get("contrib_count", 0))
	_spawn_genki_explosion_fx(impact_pos, float(proj.get("scale_mul", 1.0)))
	floating_texts.append({
		"pos": impact_pos + Vector2(0.0, -110.0),
		"text": "GENKI %d!" % int(round(dmg)) if contrib_n <= 0 else "GENKI %d (+%dP)!" % [int(round(dmg)), contrib_n],
		"color": Color(0.42, 0.94, 1.0, 1.0),
		"elapsed_s": 0.0,
		"duration_s": 0.95,
	})
	# Deal 700px AoE damage to ALL attackable enemies in radius (respecting PK Tàn Sát for remote players!)
	for s in _get_combat_slots():
		if not can_attack_slot(s):
			continue
		var s_core: Vector2 = _get_slot_core_pos(s)
		if s_core.distance_to(impact_pos) <= GENKI_AOE_RADIUS_PX:
			var dir_v: Vector2 = (s_core - impact_pos).normalized() if s_core.distance_to(impact_pos) > 1.0 else Vector2.RIGHT
			_emit_slot_combat_action("genki", s, impact_pos, dmg, 0.55)
			apply_damage_to_slot(s, dmg, 80.0, s_core, "heavy", false, dir_v)


func _step_hero_genki_projectiles_and_explosions(delta: float) -> void:
	if _genki_ambient_flash_s > 0.0:
		_genki_ambient_flash_s = maxf(0.0, _genki_ambient_flash_s - delta)

	for i in range(_genki_projectiles.size() - 1, -1, -1):
		var pr: Dictionary = _genki_projectiles[i]
		pr["age_s"] = float(pr.get("age_s", 0.0)) + delta
		var dur_s: float = maxf(0.05, float(pr.get("dur_s", 0.25)))
		var t_next: float = minf(1.0, float(pr["age_s"]) / dur_s)
		pr["t"] = t_next
		var sp: Vector2 = pr["start_pos"] as Vector2
		var lp: Vector2 = pr["land_pos"] as Vector2
		pr["pos"] = sp.lerp(lp, t_next)
		if t_next >= 1.0:
			_genki_projectiles.remove_at(i)
			_detonate_genki_orb(pr)

	for ei in range(_genki_explosions.size() - 1, -1, -1):
		var ex: Dictionary = _genki_explosions[ei]
		ex["age_s"] = float(ex.get("age_s", 0.0)) + delta
		# Trigger subtle camera micro-shake + under-entity ambient brightening right at Genki frames 11..12 onset (0.20s)!
		if (not bool(ex.get("shake_flash_fired", false))) and float(ex["age_s"]) >= 2.0 * GENKI_IMPACT_FRAME_S:
			ex["shake_flash_fired"] = true
			_genki_ambient_flash_dur_s = 0.62
			_genki_ambient_flash_s = 0.62
			_genki_ambient_flash_pos = ex["pos"] as Vector2
			if arena != null and arena.has_method(&"trigger_camera_micro_shake"):
				arena.call(&"trigger_camera_micro_shake", 5.5, 0.45)
		if float(ex["age_s"]) >= float(ex.get("dur_s", 0.88)):
			_genki_explosions.remove_at(ei)


func _draw_hero_genki_charge_and_reflection(canvas: CanvasItem, goku: Node2D, c_sc: float) -> void:
	if _genki_phase.is_empty() and _genki_wisps.is_empty():
		return
	var orb_pos: Vector2 = _get_genki_orb_pos(goku, c_sc)

	# 1. Blue top-down light reflection cast from the overhead Genki sphere onto Goku's hair, arms & body
	if not _genki_phase.is_empty():
		var light_strength: float = clampf(_genki_elapsed_s / 0.85, 0.25, 1.0) if _genki_phase == "charging" else clampf(1.0 - _genki_elapsed_s / GENKI_THROW_DURATION_S, 0.0, 1.0)
		var pulse: float = 0.88 + 0.12 * sin(_sim_time_s * 14.0)
		var a_cone: float = 0.17 * light_strength * pulse
		var p_rect: Rect2 = _get_player_body_rect()
		var p_cx: float = goku.position.x
		var p_head_y: float = p_rect.position.y + p_rect.size.y * 0.18
		var p_body_y: float = p_rect.position.y + p_rect.size.y * 0.62
		var cone_pts := PackedVector2Array([
			orb_pos + Vector2(-34.0 * c_sc, 28.0 * c_sc),
			orb_pos + Vector2(34.0 * c_sc, 28.0 * c_sc),
			Vector2(p_cx + 48.0 * c_sc, p_body_y),
			Vector2(p_cx - 48.0 * c_sc, p_body_y),
		])
		var cone_cols := PackedColorArray([
			Color(0.32, 0.88, 1.0, a_cone * 1.15),
			Color(0.32, 0.88, 1.0, a_cone * 1.15),
			Color(0.18, 0.72, 1.0, 0.0),
			Color(0.18, 0.72, 1.0, 0.0),
		])
		canvas.draw_polygon(cone_pts, cone_cols)
		canvas.draw_circle(Vector2(p_cx, p_head_y), 34.0 * c_sc, Color(0.38, 0.92, 1.0, 0.16 * light_strength * pulse))
		canvas.draw_circle(Vector2(p_cx, p_head_y - 10.0 * c_sc), 20.0 * c_sc, Color(0.68, 0.97, 1.0, 0.18 * light_strength * pulse))

	# 2. Continuous cyan energy wisps/streaks flying from contributing players into the overhead Genki sphere
	for w in _genki_wisps:
		var t_w: float = clampf(float(w.get("age_s", 0.0)) / maxf(0.01, float(w.get("dur_s", 0.6))), 0.0, 1.0)
		var sp: Vector2 = w["start_pos"] as Vector2
		var cp: Vector2 = w["ctrl_pos"] as Vector2
		var ep: Vector2 = w["end_pos"] as Vector2
		var u: float = 1.0 - t_w
		var head_p: Vector2 = (u * u) * sp + (2.0 * u * t_w) * cp + (t_w * t_w) * ep
		var t_tail: float = maxf(0.0, t_w - 0.16)
		var ut: float = 1.0 - t_tail
		var tail_p: Vector2 = (ut * ut) * sp + (2.0 * ut * t_tail) * cp + (t_tail * t_tail) * ep
		var alpha_w: float = sin(t_w * PI) * 0.95
		canvas.draw_line(tail_p, head_p, Color(0.24, 0.86, 1.0, alpha_w * 0.85), 5.0, true)
		canvas.draw_line(tail_p.lerp(head_p, 0.45), head_p, Color(0.84, 0.98, 1.0, alpha_w), 2.5, true)
		canvas.draw_circle(head_p, 5.5, Color(0.36, 0.92, 1.0, alpha_w * 0.65))
		canvas.draw_circle(head_p, 2.8, Color(0.92, 1.0, 1.0, alpha_w))

	# 3. Overhead Genki Spirit Bomb (`genki_charge_fx` 10f: Genki/1..6 + 4 bridges @ 120ms -> `genki_charge_hold_fx` 6..6c @ 120ms!)
	#    STRICTLY NEVER shows flight frames 7/8 above Goku's hands!
	if _genki_phase == "charging" or (_genki_phase == "throwing" and not _genki_throw_released):
		var gfx := _get_genki_fx_frames()
		if gfx != null:
			var orb_tex: Texture2D = null
			var draw_pos: Vector2 = orb_pos
			var scale_mul: float = 1.0
			var hold_clip: StringName = &"genki_charge_hold_fx" if gfx.has_animation(&"genki_charge_hold_fx") else &"genki_orb_loop_fx"
			if _genki_phase == "charging":
				var cfc: int = gfx.get_frame_count(&"genki_charge_fx") if gfx.has_animation(&"genki_charge_fx") else 0
				# Spread formation smoothly at 120ms cadence across first 1.2s (or 2.4s if >=10 frames: 120ms per frame = 1.20s exact!)
				var form_dur_s: float = float(cfc) * GENKI_CHARGE_FRAME_S
				if cfc > 0 and _genki_elapsed_s < form_dur_s:
					var cfi: int = clampi(int(floor(_genki_elapsed_s / GENKI_CHARGE_FRAME_S)), 0, cfc - 1)
					orb_tex = gfx.get_frame_texture(&"genki_charge_fx", cfi)
					scale_mul = 0.86 + 0.14 * clampf(_genki_elapsed_s / maxf(0.1, form_dur_s), 0.0, 1.0)
				elif gfx.has_animation(hold_clip):
					var lfc: int = gfx.get_frame_count(hold_clip)
					var lfi: int = int(floor(maxf(0.0, _genki_elapsed_s - form_dur_s) / GENKI_CHARGE_FRAME_S)) % maxi(1, lfc)
					orb_tex = gfx.get_frame_texture(hold_clip, lfi)
					var charge_grow: float = clampf((_genki_elapsed_s - form_dur_s) / maxf(0.1, GENKI_CHARGE_DURATION_S - form_dur_s), 0.0, 1.0)
					scale_mul = 1.00 + 0.22 * charge_grow + 0.012 * float(_genki_contrib_count)
			else:
				var t_rel: float = clampf(_genki_elapsed_s / GENKI_THROW_RELEASE_S, 0.0, 1.0)
				draw_pos = orb_pos.lerp(goku.position + Vector2(_genki_locked_facing_x * 56.0, -142.0 * c_sc), t_rel)
				scale_mul = 1.22 + 0.012 * float(_genki_contrib_count)
				if gfx.has_animation(hold_clip):
					var lfc2: int = gfx.get_frame_count(hold_clip)
					orb_tex = gfx.get_frame_texture(hold_clip, int(floor(_sim_time_s / GENKI_CHARGE_FRAME_S)) % maxi(1, lfc2))
			if orb_tex != null:
				var osz: float = 198.0 * c_sc * scale_mul
				canvas.draw_texture_rect(orb_tex, Rect2(draw_pos - Vector2(osz * 0.5, osz * 0.5), Vector2(osz, osz)), false, Color.WHITE)


func _draw_hero_genki_world_fx(canvas: CanvasItem) -> void:
	if _genki_projectiles.is_empty() and _genki_explosions.is_empty():
		return
	var gfx := _get_genki_fx_frames()
	var c_sc: float = float(arena.char_scale) if arena != null else 2.0

	# 1. Flying Genki Spirit Bomb (`genki_fly_fx` 4 frames: 7 -> 7b -> 8 -> 8b @ 80ms, +40% flight speed!)
	var fly_clip: StringName = &"genki_fly_fx" if (gfx != null and gfx.has_animation(&"genki_fly_fx")) else &"genki_orb_loop_fx"
	for pr in _genki_projectiles:
		var ppos: Vector2 = pr["pos"] as Vector2
		var sc_m: float = float(pr.get("scale_mul", 1.0))
		if gfx != null and gfx.has_animation(fly_clip):
			var lfc: int = gfx.get_frame_count(fly_clip)
			var lfi: int = int(floor(float(pr.get("age_s", 0.0)) * 12.5)) % maxi(1, lfc)
			var otex := gfx.get_frame_texture(fly_clip, lfi)
			if otex != null:
				var osz: float = 204.0 * c_sc * sc_m
				canvas.draw_texture_rect(otex, Rect2(ppos - Vector2(osz * 0.5, osz * 0.5), Vector2(osz, osz)), false, Color.WHITE)
		else:
			canvas.draw_circle(ppos, 64.0 * sc_m, Color(0.32, 0.88, 1.0, 0.85))

	# 2. Ground-anchored 2-stage Detonation:
	#    - Stage A (`genki_impact_fx`, Genki/9..12 @ 100ms/frame) -> micro-shake & ambient flash at 11..12!
	#    - Stage B (`genki_explode_fx`, Genki/13..16 @ 120ms/frame exact!)
	for ex in _genki_explosions:
		var epos: Vector2 = ex["pos"] as Vector2
		var age_e: float = float(ex.get("age_s", 0.0))
		var imp_dur: float = float(ex.get("impact_dur_s", 4.0 * GENKI_IMPACT_FRAME_S))
		var exp_dur: float = float(ex.get("explode_dur_s", 4.0 * GENKI_EXPLODE_FRAME_S))
		var tot_dur: float = maxf(0.05, float(ex.get("dur_s", imp_dur + exp_dur)))
		var prog: float = clampf(age_e / tot_dur, 0.0, 0.999)
		var ring_r: float = lerpf(70.0, GENKI_AOE_RADIUS_PX, pow(prog, 0.55))
		var ring_a: float = clampf(1.0 - prog, 0.0, 1.0) * 0.55
		canvas.draw_arc(epos, ring_r, PI, TAU, 48, Color(0.45, 0.94, 1.0, ring_a), 4.0, true)
		if gfx != null:
			var etex: Texture2D = null
			if age_e < imp_dur and gfx.has_animation(&"genki_impact_fx"):
				var ifc: int = gfx.get_frame_count(&"genki_impact_fx")
				var ifi: int = clampi(int(floor(age_e / GENKI_IMPACT_FRAME_S)), 0, maxi(0, ifc - 1))
				etex = gfx.get_frame_texture(&"genki_impact_fx", ifi)
			elif gfx.has_animation(&"genki_explode_fx"):
				var efc: int = gfx.get_frame_count(&"genki_explode_fx")
				var e_age: float = maxf(0.0, age_e - imp_dur) if gfx.has_animation(&"genki_impact_fx") else age_e
				var efi: int = clampi(int(floor(e_age / GENKI_EXPLODE_FRAME_S)), 0, maxi(0, efc - 1))
				etex = gfx.get_frame_texture(&"genki_explode_fx", efi)
			if etex != null:
				var esz: float = 360.0 * c_sc * float(ex.get("scale_val", 1.0))
				var ground_ratio: float = 352.0 / 384.0
				canvas.draw_texture_rect(etex, Rect2(epos.x - esz * 0.5, epos.y - esz * ground_ratio, esz, esz), false, Color.WHITE)
