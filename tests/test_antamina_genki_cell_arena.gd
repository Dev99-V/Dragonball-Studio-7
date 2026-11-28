extends SceneTree

var _fails: Array[String] = []


func _check(cond: bool, msg: String) -> void:
	if cond:
		print("[PASS] ", msg)
	else:
		print("[FAIL] ", msg)
		_fails.append(msg)


func _make_mock_remote(arena: Node2D, uid: String, x: float, y: float, pk_on: bool) -> Dictionary:
	var n := Node2D.new()
	n.name = "MockRemote_" + uid
	n.position = Vector2(x, y)
	arena.fighters_layer.add_child(n)
	return {
		"id": uid,
		"character_id": "songoku",
		"display_name": uid,
		"is_remote_player": true,
		"alive": true,
		"hp": 1000.0,
		"max_hp": 1000.0,
		"mana": 100.0,
		"max_mana": 100.0,
		"stamina": 100.0,
		"max_stamina": 100.0,
		"stun_timer_s": 0.0,
		"hard_stun_timer_s": 0.0,
		"hit_flash_s": 0.0,
		"hit_shake_s": 0.0,
		"scale_val": 2.0,
		"pk_tan_sat": pk_on,
		"node": n,
	}


func _step_sim(arena: Node2D, fm: Object, steps: int, dt: float = 1.0 / 60.0) -> void:
	for _i in range(steps):
		arena.step_player_movement(dt, 0, 0, false, false, false, Vector2.ZERO)
		fm.call(&"step", dt)
		if arena.player_node != null and arena.player_node.has_method(&"is_hero_tapion") and bool(arena.player_node.call(&"is_hero_tapion")):
			arena.player_node._process(dt)


func _initialize() -> void:
	var scene: PackedScene = load("res://scenes/ArenaSandbox.tscn")
	var arena := scene.instantiate() as Node2D
	root.add_child(arena)
	await process_frame
	arena.enable_field_mode(true, false)
	await process_frame
	var fm: Object = arena.get("field_manager")
	_check(fm != null, "FieldCombatManager initialized")

	# Verify MobileActionPad Slot 11 directly (touch HUD skips creation under headless DisplayServer)
	var PadScript: Script = load("res://scenes/runtime/MobileActionPad.gd")
	var pad: Control = PadScript.new()
	root.add_child(pad)
	pad.call(&"configure_for_character", "tapion", PackedStringArray(["kentaima_cast", "antamina_combo"]), false)
	var slot11_tap := str((pad.get("_slot_bindings") as Dictionary).get(11, ""))
	_check(slot11_tap == "empty", "Tapion Slot 11 is empty (NOT genki; got: %s)" % slot11_tap)
	pad.call(&"configure_for_character", "songoku", PackedStringArray(["genki_cast", "kame_ground_horiz"]), false)
	var slot11_goku := str((pad.get("_slot_bindings") as Dictionary).get(11, ""))
	_check(slot11_goku == "genki", "Son Goku Slot 11 bound to genki (got: %s)" % slot11_goku)
	pad.call(&"set_hero_genki_state", 0.0, false)
	_check(not bool(pad.get("_hero_airborne_for_genki")), "Slot 11 Genki marked not ready when grounded")
	pad.call(&"set_hero_genki_state", 0.0, true)
	_check(bool(pad.get("_hero_airborne_for_genki")), "Slot 11 Genki marked ready when airborne")
	pad.queue_free()

	# =========================================================================
	# PART 1: TAPION (OFFICIAL) ANTAMINA LOCKED FACING + OVERHEAD U-TURN ARC
	# =========================================================================
	arena.set_field_hero_visible(true, "tapion")
	await process_frame
	var tapion: Node2D = arena.player_node
	_check(tapion != null and bool(tapion.call(&"is_hero_tapion")), "Official Tapion active hero selected")

	var tspr := tapion.get_node_or_null("Sprite") as AnimatedSprite2D
	_check(tspr != null and tspr.sprite_frames != null and tspr.sprite_frames.get_animation_names().size() == 30, "Tapion pruned to exact 30 active body clips (got %d)" % (tspr.sprite_frames.get_animation_names().size() if (tspr != null and tspr.sprite_frames != null) else -1))
	for pruned_clip in [&"turntable_360", &"antamina_charge", &"antamina_rings", &"antamina_fire"]:
		_check(tspr != null and tspr.sprite_frames != null and not tspr.sprite_frames.has_animation(pruned_clip), "Pruned unused Tapion body clip absent: %s" % String(pruned_clip))

	var slots_arr: Array = fm.get("slots")
	_check(slots_arr.size() >= 3, "Field slots spawned (%d)" % slots_arr.size())
	var tgt_slot: Dictionary = slots_arr[0]
	var tgt_node: Node2D = tgt_slot["node"]
	var gy_800: float = float(arena.call(&"get_nearest_support_y_below", 800.0, 200.0))
	var gy_400: float = float(arena.call(&"get_nearest_support_y_below", 400.0, 200.0))
	var gy_1350: float = float(arena.call(&"get_nearest_support_y_below", 1350.0, 200.0))

	# Test 1A: Enemy starts LEFT -> Tapion locks facing LEFT -> enemy crosses RIGHT behind Tapion!
	tapion.position = Vector2(800.0, gy_800)
	tapion.scale = Vector2(absf(tapion.scale.x), tapion.scale.y) # Initially facing RIGHT before cast
	tgt_slot["alive"] = true
	tgt_slot["hp"] = 1000.0
	tgt_slot["max_hp"] = 1000.0
	tgt_node.position = Vector2(400.0, gy_400)
	fm.set("pointer_kind", "enemy")
	fm.set("pointer_slot_id", str(tgt_slot["id"]))
	fm.set("player_mana", 100.0)
	fm.set("player_infinite_mana", false)
	tapion.set("antamina_cooldown_s", 0.0)

	arena.call(&"_on_touch_action", "antamina")
	_check(bool(tapion.call(&"is_antamina_active")), "Antamina started charging")
	_check(tapion.scale.x < 0.0, "Tapion faced LEFT toward enemy at cast start (scale.x=%.2f)" % tapion.scale.x)

	# Step 1.0s into charge (still facing LEFT)
	var rotated_during_cast := false
	for _i in range(60):
		arena.step_player_movement(1.0 / 60.0, 0)
		fm.call(&"step", 1.0 / 60.0)
		tapion._process(1.0 / 60.0)
		if tapion.scale.x >= 0.0:
			rotated_during_cast = true

	# Teleport enemy BEHIND Tapion to the RIGHT (x = 1350)!
	tgt_node.position = Vector2(1350.0, gy_1350)
	var hp_before_uturn: float = float(tgt_slot["hp"])
	var saw_uturn_mode := false
	var min_proj_x := 99999.0
	var min_proj_y := 99999.0
	var max_proj_x := -99999.0

	# Step 5.0s (remaining 2.0s charge + 2.6s firing + ending)
	for _i in range(300):
		tgt_node.position = Vector2(1350.0, gy_1350) # Keep enemy on right behind Tapion
		arena.step_player_movement(1.0 / 60.0, 0)
		fm.call(&"step", 1.0 / 60.0)
		tapion._process(1.0 / 60.0)
		if bool(tapion.call(&"is_antamina_active")) and tapion.scale.x >= 0.0:
			rotated_during_cast = true
		var projs: Array = tapion.get("_active_projectiles")
		for pr in projs:
			if str(pr.get("curve_mode", "")) == "overhead_uturn":
				saw_uturn_mode = true
				var ppos: Vector2 = pr["pos"]
				min_proj_x = minf(min_proj_x, ppos.x)
				max_proj_x = maxf(max_proj_x, ppos.x)
				min_proj_y = minf(min_proj_y, ppos.y)

	var hp_after_uturn: float = float(tgt_slot["hp"])
	_check(not rotated_during_cast, "Tapion NEVER rotated during entire Antamina charge/fire/end when enemy crossed behind")
	_check(saw_uturn_mode, "Antamina spawned overhead_uturn Bezier beam when enemy crossed behind")
	_check(min_proj_x < tapion.position.x - 15.0, "U-turn beam launched FORWARD in front of Tapion (min_x=%.1f < %.1f)" % [min_proj_x, tapion.position.x - 15.0])
	_check(min_proj_y < tapion.position.y - 140.0, "U-turn beam curved HIGH OVER Tapion's head (min_y=%.1f < %.1f)" % [min_proj_y, tapion.position.y - 140.0])
	_check(hp_after_uturn < hp_before_uturn, "U-turn beam looped back behind Tapion and hit enemy (hp %.1f -> %.1f)" % [hp_before_uturn, hp_after_uturn])

	# =========================================================================
	# PART 2: SON GOKU GENKI (ASSETS, AIR-ONLY GATE, SLOT 11 HUD)
	# =========================================================================
	arena.set_field_hero_visible(true, "songoku")
	await process_frame
	var goku: Node2D = arena.player_node
	_check(goku != null and not (goku.has_method(&"is_hero_tapion") and bool(goku.call(&"is_hero_tapion"))), "Son Goku active hero selected")

	var gspr := goku.get_node_or_null("Sprite") as AnimatedSprite2D
	_check(gspr != null and gspr.sprite_frames != null and gspr.sprite_frames.has_animation(&"genki_cast"), "Goku SpriteFrames has genki_cast animation")
	_check(gspr != null and gspr.sprite_frames.get_frame_count(&"genki_cast") == 10, "Goku genki_cast has 10 whole-pose frames (incl. 4 overhead flutter loop frames; got %d)" % (gspr.sprite_frames.get_frame_count(&"genki_cast") if gspr != null else -1))

	var tfx := load("res://assets/fx/tapion_skills_fx/tapion_skills_fx.tres") as SpriteFrames
	_check(tfx != null and tfx.get_animation_names().size() == 19, "Official Tapion FX has exact 19 active clips (got %d)" % (tfx.get_animation_names().size() if tfx != null else -1))
	_check(tfx != null and not tfx.has_animation(&"antamina_flash_fx"), "Pruned unused antamina_flash_fx absent from tapion_skills_fx.tres")
	_check(tfx != null and tfx.has_animation(&"kentai_burn_fx") and tfx.get_frame_count(&"kentai_burn_fx") == 6, "Tapion FX has 6-frame looping kentai_burn_fx")

	var gfx := load("res://assets/fx/genki_fx/genki_fx.tres") as SpriteFrames
	_check(gfx != null and gfx.has_animation(&"genki_charge_fx") and gfx.has_animation(&"genki_charge_hold_fx") and gfx.has_animation(&"genki_fly_fx") and gfx.has_animation(&"genki_impact_fx") and gfx.has_animation(&"genki_explode_fx"), "Dedicated genki_fx.tres loads with all 5 clips")
	_check(gfx != null and gfx.get_frame_count(&"genki_charge_fx") == 12 and gfx.get_frame_count(&"genki_charge_hold_fx") == 4 and gfx.get_frame_count(&"genki_fly_fx") == 4 and gfx.get_frame_count(&"genki_impact_fx") == 4 and gfx.get_frame_count(&"genki_explode_fx") == 4, "genki_fx frame counts exact (12 smooth charge + 4 ray-ring hold + 4 fly + 4 impact + 4 explode)")
	_check(absf(float(fm.get("GENKI_ORB_FLIGHT_SPEED_PX_S")) - 1064.0) < 0.1, "Genki flight speed increased +40%% to 1064 px/s")

	var amb_layer := arena.get("_field_ambient_flash_node") as Node2D
	_check(amb_layer != null and amb_layer.z_index == 5, "Ambient flash layer z_index=5 (strictly above bg/trees -10/-20 and below monsters 10 / heroes 20)")

	# Transform Goku to SSJ1 on ground
	goku.set("is_ssj", true)
	goku.set("flight_state", "ground")
	goku.set("ki", 50.0)
	goku.set("genki_cooldown_s", 0.0)
	var gy_900: float = float(arena.call(&"get_nearest_support_y_below", 900.0, 200.0))
	goku.position = Vector2(900.0, gy_900)
	arena.set("player_vy", 0.0)
	fm.set("player_mana", 100.0)
	fm.set("player_hp", 1000.0)
	fm.set("player_dead", false)

	_check(not bool(arena.call(&"is_player_airborne_for_genki")), "Grounded Goku is NOT airborne for Genki")
	_check(not bool(fm.call(&"request_player_genki")), "Genki cast REJECTED while grounded")

	# =========================================================================
	# PART 3: PLAYER CONTRIBUTION COUNT (CAP 20, INCL. PK HOSTILE, EXCL. MONSTERS/BOSS)
	# =========================================================================
	var remotes: Dictionary = fm.get("remote_player_slots")
	remotes.clear()
	remotes["p1"] = _make_mock_remote(arena, "p1", 1180.0, gy_900, false)
	remotes["p2"] = _make_mock_remote(arena, "p2", 1240.0, gy_900, true)
	remotes["p3"] = _make_mock_remote(arena, "p3", 2200.0, gy_900, false)
	remotes["p4"] = _make_mock_remote(arena, "p4", 2300.0, gy_900, true)
	_check(int(fm.call(&"get_genki_contributing_player_count")) == 4, "Contrib count = 4 (counts peaceful + PK hostile players, excludes monsters/boss; got %d)" % int(fm.call(&"get_genki_contributing_player_count")))
	_check(absf(float(fm.call(&"get_genki_current_damage")) - 420.0) < 0.01, "Genki dmg with 4 players = 420 (got %.1f)" % float(fm.call(&"get_genki_current_damage")))

	# Add 20 extra players (24 total) -> MUST cap at 20 (500 dmg)
	for k in range(5, 25):
		var uid := "p%d" % k
		remotes[uid] = _make_mock_remote(arena, uid, 2350.0, gy_900, false)
	_check(int(fm.call(&"get_genki_contributing_player_count")) == 20, "Contrib count CAPPED at 20 with 24 players (got %d)" % int(fm.call(&"get_genki_contributing_player_count")))
	_check(absf(float(fm.call(&"get_genki_current_damage")) - 500.0) < 0.01, "Genki max dmg capped at 500 (got %.1f)" % float(fm.call(&"get_genki_current_damage")))
	# Remove extras back to 4 players
	for k in range(5, 25):
		var uid := "p%d" % k
		var n_rm: Node2D = remotes[uid]["node"]
		if is_instance_valid(n_rm):
			n_rm.queue_free()
		remotes.erase(uid)

	# =========================================================================
	# PART 4: AIRBORNE CAST + 5S CHARGE + BLUE WISPS + CC IMMUNITY + DEATH LOSS
	# =========================================================================
	goku.position = Vector2(900.0, gy_900 - 220.0)
	goku.scale = Vector2(absf(goku.scale.x), goku.scale.y)
	goku.set("flight_state", "hovering")
	goku.set("hover_timer_s", 3.0)
	goku.set("ki", 40.0)
	fm.set("player_mana", 100.0)
	fm.set("player_hp", 1000.0)
	fm.set("player_armor", 10.0)
	fm.set("player_armor_broken_timer_s", 0.0)
	fm.set("player_hard_stun_timer_s", 0.0)

	_check(bool(arena.call(&"is_player_airborne_for_genki")), "Mid-air SSJ1 Goku IS airborne for Genki")
	_check(bool(fm.call(&"request_player_genki")), "Genki cast ACCEPTED while mid-air SSJ1")
	_check(absf(float(fm.get("player_mana"))) < 0.01, "Genki consumed 100 MP")
	_check(bool(goku.get("genki_casting")), "goku.genki_casting = true")

	var start_y: float = goku.position.y
	var start_ki: float = float(goku.get("ki"))
	var seen_hold_frames: Dictionary = {}
	for _hi in range(90):
		arena.step_player_movement(1.0 / 60.0, 0)
		fm.call(&"step", 1.0 / 60.0)
		if String(gspr.animation) == "genki_cast" and gspr.frame >= 3 and gspr.frame <= 6:
			seen_hold_frames[gspr.frame] = true
	_check(absf(goku.position.y - start_y) < 1.0, "Goku stayed suspended mid-air during charge (dy=%.2f)" % absf(goku.position.y - start_y))
	_check(absf(float(goku.get("ki")) - start_ki) < 0.01, "Flight KI paused during Genki charge (ki=%.2f)" % float(goku.get("ki")))
	_check(seen_hold_frames.size() == 4, "Goku cycles ALL 4 fluttering overhead loop frames (#3..#6) @ 120ms during 5s charge (seen=%s)" % str(seen_hold_frames.keys()))
	_check((fm.get("_genki_wisps") as Array).size() > 0, "Continuous cyan energy wisps flying from players (%d active)" % (fm.get("_genki_wisps") as Array).size())

	# Test CC Immunity + Still Takes HP Damage
	var hp_pre_hit: float = float(fm.get("player_hp"))
	fm.call(&"apply_hard_stun_to_player", 2.5)
	_check(float(fm.get("player_hard_stun_timer_s")) == 0.0 and str(fm.get("_genki_phase")) == "charging", "Genki IMMUNE to hard stun")

	fm.call(&"apply_damage_to_player", 120.0, goku.position, false, "armor_break")
	_check(absf(float(fm.get("player_hp")) - (hp_pre_hit - 120.0)) < 0.1, "Goku STILL takes HP damage during Genki (%.1f -> %.1f)" % [hp_pre_hit, float(fm.get("player_hp"))])
	_check(float(fm.get("player_armor_broken_timer_s")) == 0.0 and str(fm.get("_genki_phase")) == "charging" and String(gspr.animation) == "genki_cast", "Goku IMMUNE to armor-break stun/hit interrupt during Genki")

	# Test Death Cancels Genki!
	fm.call(&"apply_damage_to_player", 9999.0, goku.position, false, "heavy")
	_check(bool(fm.get("player_dead")), "Goku died from lethal damage")
	_check(str(fm.get("_genki_phase")) == "" and not bool(goku.get("genki_casting")) and (fm.get("_genki_wisps") as Array).is_empty(), "Death immediately cancelled & lost Genki")

	# =========================================================================
	# PART 5: GROUND THROW (50..200PX AHEAD, IGNORES POINTED TARGET) + 700PX AOE + PK GATING
	# =========================================================================
	fm.call(&"respawn_player_at_left")
	goku.set("is_ssj", true)
	goku.set("genki_cooldown_s", 0.0)
	goku.set("flight_state", "hovering")
	goku.set("hover_timer_s", 3.0)
	goku.set("ki", 50.0)
	goku.position = Vector2(900.0, gy_900 - 220.0)
	goku.scale = Vector2(absf(goku.scale.x), goku.scale.y) # Facing RIGHT
	fm.set("player_mana", 100.0)
	fm.set("player_hp", 1000.0)
	fm.set("pk_tan_sat_enabled", false)
	fm.set("pk_special_mode_override", false)

	# Position 3 monsters: m_behind (pointed, behind Goku >700px away), m_in_range (inside 700px), m_far (>700px away)
	var m_behind: Dictionary = slots_arr[0]
	var m_in_range: Dictionary = slots_arr[1]
	var m_far: Dictionary = slots_arr[2]
	m_behind["alive"] = true; m_behind["hp"] = 1000.0; m_behind["max_hp"] = 1000.0; (m_behind["node"] as Node2D).position = Vector2(120.0, float(arena.call(&"get_nearest_support_y_below", 120.0, 200.0)))
	m_in_range["alive"] = true; m_in_range["hp"] = 1000.0; m_in_range["max_hp"] = 1000.0; (m_in_range["node"] as Node2D).position = Vector2(1520.0, float(arena.call(&"get_nearest_support_y_below", 1520.0, 200.0)))
	m_far["alive"] = true; m_far["hp"] = 1000.0; m_far["max_hp"] = 1000.0; (m_far["node"] as Node2D).position = Vector2(1960.0, float(arena.call(&"get_nearest_support_y_below", 1960.0, 200.0)))
	# Point at m_behind to prove throw NEVER aims at pointed target!
	fm.set("pointer_kind", "enemy")
	fm.set("pointer_slot_id", str(m_behind["id"]))

	# Reset remote player HP (p1 peaceful inside 700px, p2 PK hostile inside 700px)
	remotes["p1"]["hp"] = 1000.0; (remotes["p1"]["node"] as Node2D).position = Vector2(1200.0, gy_900)
	remotes["p2"]["hp"] = 1000.0; (remotes["p2"]["node"] as Node2D).position = Vector2(1260.0, gy_900)

	_check(bool(fm.call(&"request_player_genki")), "Second Genki cast started (facing RIGHT, pointed target behind at x=120)")

	var captured_land_pos := Vector2(-1.0, -1.0)
	var saw_throw_frame_7 := false
	var saw_throw_frame_8 := false
	var saw_throw_frame_9 := false
	var saw_explosion := false
	var saw_micro_shake := false
	var saw_ambient_flash := false
	# Step 7.2s (5.0s charge + 0.48s throw + flight + 0.40s impact + 0.48s explosion + settle)
	for _i in range(440):
		# Pin monsters so AI doesn't wander out of test positions
		(m_behind["node"] as Node2D).position.x = 120.0
		(m_in_range["node"] as Node2D).position.x = 1520.0
		(m_far["node"] as Node2D).position.x = 1960.0
		arena.step_player_movement(1.0 / 60.0, 0)
		fm.call(&"step", 1.0 / 60.0)
		if String(gspr.animation) == "genki_cast":
			if gspr.frame == 7:
				saw_throw_frame_7 = true
			elif gspr.frame == 8:
				saw_throw_frame_8 = true
			elif gspr.frame == 9:
				saw_throw_frame_9 = true
		var gprojs: Array = fm.get("_genki_projectiles")
		if captured_land_pos.x < 0.0 and gprojs.size() > 0:
			captured_land_pos = gprojs[0]["land_pos"]
		if (fm.get("_genki_explosions") as Array).size() > 0:
			saw_explosion = true
		if float(arena.get("_camera_shake_timer_s")) > 0.0:
			saw_micro_shake = true
		if float(fm.get("_genki_ambient_flash_s")) > 0.0:
			saw_ambient_flash = true

	_check(saw_throw_frame_7 and saw_throw_frame_8 and saw_throw_frame_9, "Goku played exact 3-frame throw (#7 wind-up -> #8 downward arc hurl -> #9 crouched follow-through)")
	_check(saw_micro_shake, "Genki impact frames 11..12 triggered light camera micro-shake")
	_check(saw_ambient_flash, "Genki impact frames 11..12 triggered under-entity ambient brightening flash")
	_check(float(arena.get("_camera_shake_timer_s")) <= 0.001, "Camera micro-shake decayed cleanly back to zero")
	_check(not bool(goku.get("genki_casting")), "goku.genki_casting cleared after throw")
	var land_dx: float = captured_land_pos.x - 900.0
	var expected_land_y: float = float(arena.call(&"get_nearest_support_y_below", captured_land_pos.x, gy_900 - 220.0))
	_check(land_dx >= 50.0 and land_dx <= 200.0, "Genki landed strictly in front within [50, 200]px ignoring pointed target behind (dx=%.1fpx)" % land_dx)
	_check(absf(captured_land_pos.y - expected_land_y) < 2.0, "Genki impacted exact terrain ground surface (y=%.1f vs %.1f)" % [captured_land_pos.y, expected_land_y])
	_check(saw_explosion, "Genki ground detonation explosion spawned")

	# Verify exact 700px AoE damage = 420 (400 base + 4*5) & PK Tàn Sát gating
	_check(absf(float(m_in_range["hp"]) - 580.0) < 0.5, "Monster inside 700px took exact 420 dmg (hp=%.1f)" % float(m_in_range["hp"]))
	_check(absf(float(m_far["hp"]) - 1000.0) < 0.5, "Monster outside 700px took 0 dmg (hp=%.1f)" % float(m_far["hp"]))
	_check(absf(float(m_behind["hp"]) - 1000.0) < 0.5, "Pointed monster behind (>700px) took 0 dmg (hp=%.1f)" % float(m_behind["hp"]))
	_check(absf(float(remotes["p1"]["hp"]) - 1000.0) < 0.5, "Peaceful remote player inside 700px (PK OFF) took 0 dmg (hp=%.1f)" % float(remotes["p1"]["hp"]))
	_check(absf(float(remotes["p2"]["hp"]) - 580.0) < 0.5, "Hostile PK remote player inside 700px took exact 420 dmg (hp=%.1f)" % float(remotes["p2"]["hp"]))

	# =========================================================================
	# PART 6: AUTO-BATTLE AI SURVIVAL RULES (HP < 30% HEAL, HP < 10% BARRIER)
	# =========================================================================
	goku.position = Vector2(900.0, gy_900)
	goku.set("flight_state", "ground")
	goku.set("is_ssj", true)
	goku.set("barrier_timer_s", 0.0)
	goku.set("barrier_cooldown_s", 0.0)
	goku.set("recover_timer_s", 0.0)
	goku.set("recover_cooldown_s", 0.0)
	arena.set("player_vy", 0.0)
	if gspr != null:
		gspr.play(&"idle_combat")

	# 6A: HP = 80% -> normal combat (NO barrier / NO recover)
	fm.set("player_hp", 800.0)
	var dec_80: Dictionary = fm.call(&"step_hero_auto_battle", 1.0 / 60.0)
	_check(str(dec_80.get("intent", "")) != "barrier" and str(dec_80.get("intent", "")) != "energy_recover", "Auto-Battle at 80%% HP uses normal combat (intent=%s)" % str(dec_80.get("intent", "")))

	# 6B: HP = 25% (< 30%) grounded -> triggers energy_recover!
	if gspr != null:
		gspr.play(&"idle_combat")
	fm.set("player_hp", 250.0)
	var dec_25: Dictionary = fm.call(&"step_hero_auto_battle", 1.0 / 60.0)
	_check(str(dec_25.get("intent", "")) == "energy_recover" and float(goku.get("recover_timer_s")) > 0.0, "Auto-Battle at 25%% HP (<30%%) auto-casts energy_recover (intent=%s)" % str(dec_25.get("intent", "")))

	# 6C: HP = 8% (< 10%) -> triggers barrier FIRST!
	goku.set("recover_timer_s", 0.0)
	goku.set("recover_cooldown_s", 0.0)
	goku.set("barrier_timer_s", 0.0)
	goku.set("barrier_cooldown_s", 0.0)
	if gspr != null:
		gspr.play(&"idle_combat")
	fm.set("player_hp", 80.0)
	var dec_8: Dictionary = fm.call(&"step_hero_auto_battle", 1.0 / 60.0)
	_check(str(dec_8.get("intent", "")) == "barrier" and float(goku.get("barrier_timer_s")) > 0.0, "Auto-Battle at 8%% HP (<10%%) auto-activates protective barrier (intent=%s)" % str(dec_8.get("intent", "")))

	# =========================================================================
	# PART 7: CELL ARENA 1-VIEW SOLO PVP MAP (RED-LINE FLOOR, TOPMOST PILLARS, NO MONSTERS, UI TOGGLE)
	# =========================================================================
	var map_btn: Button = arena.get("map_switch_button") as Button
	_check(map_btn != null, "Quick MapSwitchButton exists on ArenaSandbox HUD (NO transition header)")
	_check(bool(arena.call(&"switch_map", "cell_arena")), "switch_map('cell_arena') succeeded")
	await process_frame
	_check(str(arena.get("current_map_id")) == "cell_arena", "current_map_id == 'cell_arena'")
	_check(bool(arena.get("_fixed_single_view_map")), "Cell Arena is fixed 1-view map")
	_check(absf(float(arena.get("_map_left_x"))) < 0.1 and absf(float(arena.get("_map_right_x")) - 2400.0) < 0.1, "Cell Arena exact K70E 1-view width 0..2400")
	_check((fm.get("slots") as Array).size() == 0, "Cell Arena Solo PvP spawns ZERO monsters (slots=%d)" % (fm.get("slots") as Array).size())

	# Check exact red-line floor_profile interpolation at left apron, center ring, and right apron!
	var gy_left: float = float(arena.call(&"_ground_y_at", 100.0))
	var gy_ring: float = float(arena.call(&"_ground_y_at", 1200.0))
	var gy_right: float = float(arena.call(&"_ground_y_at", 2300.0))
	_check(absf(gy_left - 981.1) < 1.0, "Cell Arena left apron red-line floor y=%.1f (expected 981.1)" % gy_left)
	_check(absf(gy_ring - 935.2) < 1.0, "Cell Arena center ring red-line floor y=%.1f (expected 935.2)" % gy_ring)
	_check(absf(gy_right - 977.4) < 1.0, "Cell Arena right apron red-line floor y=%.1f (expected 977.4)" % gy_right)

	# Check solid red-line floor blocks skills aiming below floor AND 2 foreground pillars are z_index=80 with ZERO collision!
	_check(bool(arena.call(&"terrain_blocks_segment", Vector2(1200.0, 800.0), Vector2(1200.0, 960.0))), "Red-line floor blocks downward projectile cleanly")
	_check(not bool(arena.call(&"terrain_blocks_segment", Vector2(200.0, 600.0), Vector2(400.0, 600.0))), "Left foreground pillar does NOT block skills/projectiles")
	_check(not bool(arena.call(&"terrain_blocks_segment", Vector2(2050.0, 600.0), Vector2(2250.0, 600.0))), "Right foreground pillar does NOT block skills/projectiles")
	var pil_sp: Sprite2D = arena.get("_foreground_pillars") as Sprite2D
	_check(pil_sp != null and pil_sp.visible and pil_sp.z_index == 80, "2 front metallic pillars mounted on topmost world layer z_index=80 (visible=%s, z=%d)" % [str(pil_sp != null and pil_sp.visible), pil_sp.z_index if pil_sp != null else -1])

	# Verify K70E (2712x1220 -> 2400.8x1080 logic) fixed 1-view camera does NOT scroll when player walks across the ring!
	arena.call(&"apply_device_profile", "redmi_k70e")
	var cam: Camera2D = arena.get("_arena_camera") as Camera2D
	var p_ca: Node2D = arena.player_node
	p_ca.position = Vector2(300.0, float(arena.call(&"_ground_y_at", 300.0)))
	arena.call(&"_update_follow_camera")
	var cam_x_left: float = cam.position.x if cam != null else -1.0
	p_ca.position = Vector2(2100.0, float(arena.call(&"_ground_y_at", 2100.0)))
	arena.call(&"_update_follow_camera")
	var cam_x_right: float = cam.position.x if cam != null else -1.0
	_check(absf(cam_x_left - 1200.0) < 1.0 and absf(cam_x_right - 1200.0) < 1.0, "K70E 1-view camera locked at center x=1200 with ZERO scrolling (left=%.1f, right=%.1f)" % [cam_x_left, cam_x_right])

	# Verify switching back to rocky_plateau restores full 4-step map & 14 monsters cleanly!
	_check(bool(arena.call(&"switch_map", "rocky_plateau")), "switch_map('rocky_plateau') restored cleanly")
	await process_frame
	_check(str(arena.get("current_map_id")) == "rocky_plateau" and not bool(arena.get("_fixed_single_view_map")), "Back on rocky_plateau extended map")
	_check((fm.get("slots") as Array).size() == 14, "Rocky Plateau restored all 14 field monsters (slots=%d)" % (fm.get("slots") as Array).size())
	_check(pil_sp == null or not pil_sp.visible, "Cell Arena foreground pillars hidden on Rocky Plateau")

	# =========================================================================
	# PART 8: QA SUBAGENT REGRESSION LOCK (BUGS #1, #2, #3, #4, #7, #8)
	# =========================================================================
	# 8.1: Hero switch mid-Genki / mid-Atomic / mid-Kamehameha clears ALL hero combat state (Bug #1)
	arena.set_field_hero_visible(true, "songoku")
	await process_frame
	var g_qa: Node2D = arena.player_node
	g_qa.set("is_ssj", true)
	g_qa.set("flight_state", "hovering")
	g_qa.set("hover_timer_s", 3.0)
	g_qa.set("ki", 50.0)
	g_qa.set("genki_cooldown_s", 0.0)
	var gy_qa: float = float(arena.call(&"get_nearest_support_y_below", 900.0, 200.0))
	g_qa.position = Vector2(900.0, gy_qa - 220.0)
	fm.set("player_mana", 100.0)
	_check(bool(fm.call(&"request_player_genki")), "QA-8.1: Goku started Genki before hero switch")
	arena.set_field_hero_visible(true, "tapion")
	await process_frame
	_check(str(fm.get("_genki_phase")) == "" and (fm.get("_genki_wisps") as Array).is_empty() and (fm.get("_hero_atomic_pending_bolts") as Array).is_empty() and not bool(fm.get("_hero_kame_charging")), "QA-8.1: Switching Goku -> Tapion mid-Genki resets all Goku skill state cleanly")

	# 8.2: Remote online Tapion NEVER runs local combat/facing logic (Bug #2)
	arena.set_field_hero_visible(true, "songoku")
	await process_frame
	arena.set("player_facing_left", false)
	var tap_prefab: PackedScene = load("res://scenes/TapionHero.tscn")
	var remote_tap := tap_prefab.instantiate() as Node2D
	remote_tap.position = Vector2(1200.0, gy_qa)
	arena.fighters_layer.add_child(remote_tap)
	var s0_qa: Dictionary = (fm.get("slots") as Array)[0]
	s0_qa["alive"] = true
	s0_qa["hp"] = 1500.0
	var hp_before_remote := float(s0_qa["hp"])
	var rspr := remote_tap.get_node_or_null("Sprite") as AnimatedSprite2D
	if rspr != null:
		rspr.play(&"kentaima_cast")
		rspr.frame = 2
	for _ri in range(10):
		remote_tap._process(1.0 / 60.0)
	_check(absf(float(s0_qa["hp"]) - hp_before_remote) < 0.01 and not bool(arena.get("player_facing_left")), "QA-8.2: Remote Tapion never damages local slots or hijacks local player_facing_left")
	remote_tap.queue_free()

	# 8.3: Airborne Auto-Battle <30% HP stays in fast_drop until grounded and triggers energy_recover (Bug #3)
	arena.set_field_hero_visible(true, "tapion")
	await process_frame
	var t_qa: Node2D = arena.player_node
	t_qa.position = Vector2(900.0, gy_qa - 220.0)
	t_qa.set("flight_state", "hovering")
	t_qa.set("hover_timer_s", 3.0)
	t_qa.set("recover_timer_s", 0.0)
	t_qa.set("recover_cooldown_s", 0.0)
	t_qa.set("mahasenko_cooldown_s", 9.0)
	t_qa.set("kentaima_cooldown_s", 9.0)
	t_qa.set("antamina_cooldown_s", 9.0)
	fm.set("player_hp", 250.0)
	fm.set("player_mana", 0.0)
	var recovered_after_drop := false
	for _di in range(120):
		var dec_drop: Dictionary = fm.call(&"step_hero_auto_battle", 1.0 / 60.0)
		if str(dec_drop.get("intent", "")) == "energy_recover" or float(t_qa.get("recover_timer_s")) > 0.0:
			recovered_after_drop = true
			break
	_check(recovered_after_drop, "QA-8.3: Airborne Tapion at 25%% HP completes fast_drop continuously and casts energy_recover")

	# 8.4: Field mode keyboard 3/Q do NOT mutate hero scale or swap hero to monster (Bug #4)
	var orig_sc_qa: float = float(arena.get("char_scale"))
	var ev3 := InputEventKey.new()
	ev3.keycode = KEY_3
	ev3.pressed = true
	arena._unhandled_input(ev3)
	var evq := InputEventKey.new()
	evq.keycode = KEY_Q
	evq.pressed = true
	arena._unhandled_input(evq)
	_check(absf(float(arena.get("char_scale")) - orig_sc_qa) < 0.001 and str(arena.get("active_character_id")) == "tapion", "QA-8.4: Field mode ignores legacy sandbox 3/Q scale & monster-swap hotkeys")

	# 8.5: Hide/Show Hero preserves Tapion & clears micro-shake cleanly (Bug #7)
	arena.call(&"trigger_camera_micro_shake", 5.0, 0.25)
	arena.set_field_hero_visible(false)
	_check(float(arena.get("_camera_shake_timer_s")) == 0.0, "QA-8.5a: Hiding hero resets active camera micro-shake immediately")
	arena.set_field_hero_visible(true)
	await process_frame
	_check(str(arena.get("active_character_id")) == "tapion" and bool(arena.player_node.call(&"is_hero_tapion")), "QA-8.5b: Re-showing hero preserves active Tapion instead of resetting to Son Goku")

	# 8.6: Mobile HUD hit-test covers pk_toggle_button & map_switch_button (Bug #8)
	var pk_btn := arena.get("pk_toggle_button") as Control
	var mp_btn := arena.get("map_switch_button") as Control
	if pk_btn != null and pk_btn.visible:
		_check(bool(arena.call(&"_is_point_over_hud_controls", pk_btn.get_global_rect().get_center())), "QA-8.6a: pk_toggle_button blocks touch target passthrough")
	if mp_btn != null and mp_btn.visible:
		_check(bool(arena.call(&"_is_point_over_hud_controls", mp_btn.get_global_rect().get_center())), "QA-8.6b: map_switch_button blocks touch target passthrough")

	# =========================================================================
	# PART 9: NÚI TEINAN (TERMINAL LEFT) <-> SƯỜN NÚI TEINAN (80% WIDTH, 6 STEPS, FROSTED HEADER, PINE & FLORA)
	# =========================================================================
	_check(bool(arena.call(&"switch_map", "rocky_plateau")), "9.1: switch_map('rocky_plateau') ready")
	await process_frame
	arena.set_field_hero_visible(true, "songoku")
	await process_frame
	var t_st_init: Dictionary = arena.call(&"get_map_transition_state")
	_check(str(t_st_init.get("current_display_name", "")) == "Núi Teinan", "9.1b: rocky_plateau display_name is 'Núi Teinan' (got '%s')" % str(t_st_init.get("current_display_name", "")))

	# Terminal Left check on Núi Teinan: standing at leftmost walkable bound must NOT show any transition header!
	var p_tn: Node2D = arena.player_node
	var min_wx_tn: float = float(arena.get("walkable_min_x"))
	var max_wx_tn: float = float(arena.get("walkable_max_x"))
	p_tn.position = Vector2(min_wx_tn + 10.0, float(arena.call(&"_ground_y_at", min_wx_tn + 10.0)))
	arena.call(&"_update_map_transition_header")
	var t_st_left: Dictionary = arena.call(&"get_map_transition_state")
	_check(not bool(t_st_left.get("header_visible", true)), "9.2: Núi Teinan is terminal on left -> NO left transition header")

	# Verify Son Goku preserves SSJ1 across map switches (Owner A4)!
	p_tn.set("is_ssj", true)
	# Verify NO early trigger when hero is 65px away from the slim 26px right portal (body has NOT touched frosted glass!)
	p_tn.position = Vector2(max_wx_tn - 65.0, float(arena.call(&"_ground_y_at", max_wx_tn - 65.0)))
	arena.set("_map_transition_cooldown_s", 0.0)
	arena.call(&"_update_map_transition_header")
	var t_st_far: Dictionary = arena.call(&"get_map_transition_state")
	_check(not bool(t_st_far.get("portal_touching", true)), "9.2b: Character 65px away from slim 26px portal MUST NOT trigger early transition")

	# Right end of Núi Teinan -> Physically touching slim 26px frosted-glass portal auto-switches to Sườn núi Teinan at (-140, 515) AND preserves SSJ1!
	p_tn.position = Vector2(max_wx_tn, float(arena.call(&"_ground_y_at", max_wx_tn)))
	arena.set("_map_transition_cooldown_s", 0.0)
	arena.call(&"_update_map_transition_header")
	var t_st_right: Dictionary = arena.call(&"get_map_transition_state")
	_check(bool(t_st_right.get("portal_layer_visible", false)) and bool(t_st_right.get("portal_touching", false)) and absf(float(t_st_right.get("portal_width_px", 0.0)) - 26.0) < 0.5 and str(t_st_right.get("side", "")) == "right" and str(t_st_right.get("target_map_id", "")) == "teinan_slope" and str(t_st_right.get("target_display_name", "")) == "Sườn núi Teinan", "9.3: Physically touching slim 26px frosted-glass portal at right end of Núi Teinan detects 'Sườn núi Teinan'")

	# Walk character right (+1) into the frosted-glass portal -> automatic character-touch transition preserving Goku SSJ1!
	arena.call(&"step_player_movement", 0.1, 1)
	await process_frame
	var ts_w: float = float(arena.get("_map_right_x")) - float(arena.get("_map_left_x"))
	var ts_h: float = float(arena.get("_map_bottom_y")) - float(arena.get("_map_top_y"))
	_check(str(arena.get("current_map_id")) == "teinan_slope" and absf(ts_w - 4800.0) < 0.5 and absf(ts_h - 1350.0) < 0.5, "9.4: Character touching right frosted-glass portal auto-transitioned to Sườn núi Teinan (4800x1350)")
	var p_ts: Node2D = arena.player_node
	_check(absf(p_ts.position.x - (-140.0)) < 15.0 and absf(p_ts.position.y - 515.0) < 2.0 and not bool(arena.get("player_facing_left")) and bool(p_ts.get("is_ssj")), "9.5: Spawned at (-140, 515) AND preserved Son Goku SSJ1 state across map switch (got %.1f, %.1f, ssj=%s)" % [p_ts.position.x, p_ts.position.y, str(p_ts.get("is_ssj"))])
	_check((fm.get("slots") as Array).size() == 0, "9.6: Sườn núi Teinan demo has 0 monsters configured")

	var fg_trees_node := arena.get("_foreground_trees") as Node2D
	_check(fg_trees_node != null and fg_trees_node.z_index == -15 and fg_trees_node.get_child_count() >= 1 and (fg_trees_node.get_child(0) as Node2D).scale.is_equal_approx(Vector2.ONE), "9.7: Mounted 1:1 native pine canopy overhang at z=-15 (above waterfall z=-16, below characters z=10..20, 0%% downscale shimmer)")

	# Bidirectional step verification across Owner v6 blocking hill & organic boulder/turf profile:
	# (a) First tick crossing downward Step 1 (drop_x = 110: 515 -> 575) MUST begin falling!
	p_ts.position = Vector2(109.0, 515.0)
	arena.set("player_vy", 0.0)
	p_ts.position.x = 114.0
	var v_drop1: Dictionary = arena.call(&"_integrate_player_vertical", 1.0 / 60.0, false)
	_check(p_ts.position.y > 515.0 and float(arena.get("player_vy")) > 0.0 and not bool(v_drop1.get("landed", true)), "9.8a: Crossing downward Step 1 (x=110, 515->575) immediately starts gravity fall on tick 1")

	# (b) Walking right on Courtyard (y=768) into Step 4 organic cục đất rise (x=1425, y=672) blocks ground walk, while normal jump clears it!
	var res_blocked_r: float = float(arena.call(&"_resolve_terrain_horizontal_move", 1380.0, 1480.0, 768.0, false, -216.0, 4536.0, 40.0))
	var res_jump_r: float = float(arena.call(&"_resolve_terrain_horizontal_move", 1380.0, 1480.0, 665.0, false, -216.0, 4536.0, 40.0))
	_check(res_blocked_r < 1425.0 and absf(res_jump_r - 1480.0) < 0.5, "9.8b: Step 4 cục đất rise (x=1425, 768->672) blocks ground walk (%.1f) and allows jump (%.1f)" % [res_blocked_r, res_jump_r])

	# (c) Blocking hill approach (785 -> 678 -> 570 -> 682 -> 792, each <= 112px) blocks unjumped walk both ways & allows normal jump!
	var res_mesa_blk: float = float(arena.call(&"_resolve_terrain_horizontal_move", 3420.0, 3550.0, 678.0, false, -216.0, 4536.0, 40.0))
	var res_mesa_jmp: float = float(arena.call(&"_resolve_terrain_horizontal_move", 3420.0, 3550.0, 562.0, false, -216.0, 4536.0, 40.0))
	var res_right_blk: float = float(arena.call(&"_resolve_terrain_horizontal_move", 4340.0, 4210.0, 792.0, false, -216.0, 4536.0, 40.0))
	var res_right_jmp: float = float(arena.call(&"_resolve_terrain_horizontal_move", 4340.0, 4210.0, 675.0, false, -216.0, 4536.0, 40.0))
	_check(res_mesa_blk < 3485.0 and absf(res_mesa_jmp - 3550.0) < 0.5 and res_right_blk > 4265.0 and absf(res_right_jmp - 4210.0) < 0.5, "9.8c: Blocking hill steps (3485 & 4265) block ground walk and allow normal jump in both directions")

	# (d) Projectile LOS blocked by both left boulder cliff and raised organic mesa face!
	_check(bool(arena.call(&"terrain_blocks_segment", Vector2(360.0, 710.0), Vector2(210.0, 710.0))), "9.8d: Projectile blocked by left boulder face")
	_check(bool(arena.call(&"terrain_blocks_segment", Vector2(3400.0, 625.0), Vector2(3580.0, 625.0))), "9.8e: Projectile blocked by Step 9 organic mesa face")

	# (e) Widened 740px Pebble-Rich River [2205..2945] + Standalone .tres WaterfallRiverCompleteAsset (-20% speed tpf=5) + intact 13f Splash!
	var w_init: Dictionary = arena.call(&"get_interactive_water_metrics")
	var river_bed_y: float = float(arena.call(&"_ground_y_at", 2593.0))
	_check(bool(w_init.get("enabled", false)) and absf(float(w_init.get("width_px", 0.0)) - 740.0) < 0.1 and absf(river_bed_y - 895.0) < 0.1, "9.10a: Widened 740px pebble-rich river ford [2205..2945] has walkable stone floor y=895 (got %.1f)" % river_bed_y)
	_check(bool(w_init.get("standalone_tres_mounted", false)) and bool(w_init.get("waterfall_mounted", false)) and bool(w_init.get("ankle_rim_mounted", false)) and int(w_init.get("waterfall_z_index", 0)) == -16 and int(w_init.get("ankle_rim_z_index", 0)) >= 31, "9.10b: Standalone waterfall_river.tres asset (-16) & ankle wave strip (>=31) mounted")
	_check(absf(float(arena.call(&"get_water_wade_sink_px", 2593.0, 895.0)) - 6.0) < 0.1 and absf(float(arena.call(&"get_water_wade_sink_px", 2593.0, 800.0))) < 0.01 and absf(float(arena.call(&"get_water_wade_sink_px", 3100.0, 785.0))) < 0.01 and absf(float(arena.call(&"get_water_speed_multiplier", 2593.0, 895.0)) - 1.0) < 0.01, "9.10c: Grounded wading sinks ~6px in [2205..2945], 0px airborne/dry, and preserves 100%% walk speed")
	p_ts.position = Vector2(2593.0, 895.0)
	for _wi in range(18):
		arena.call(&"step_interactive_water", 1.0 / 60.0)
	var w_stepped: Dictionary = arena.call(&"get_interactive_water_metrics")
	_check(int(w_stepped.get("waterfall_frame", 0)) > 0 and int(w_stepped.get("ankle_rim_frame", 0)) > 0 and int(w_stepped.get("active_splash_count", 0)) >= 1, "9.10d: 60Hz standalone waterfall_river.tres (-20%% speed) & ankle wave frames advance and plunge zone spawns splashes")
	_check(bool(arena.call(&"notify_projectile_terrain_impact", Vector2(2680.0, 895.0), 1.35)) and not bool(arena.call(&"notify_projectile_terrain_impact", Vector2(3120.0, 785.0), 1.35)), "9.10e: Projectile/skill impacts inside river zone trigger intact 13-frame water splash plumes + ripples")

	# (e2) Verify Shenron summon layer sits strictly ABOVE HP/Mana FieldOverlayLayer (z=65) AND HUDLayer (layer=1)!
	var sh_parent_layer := arena.shenron_summon.get_parent() as CanvasLayer
	var main_hud_layer := arena.get_node_or_null("HUDLayer") as CanvasLayer
	var sh_ctrl_layer := arena.wish_panel.get_parent() as CanvasLayer
	_check(arena.shenron_summon.z_index > arena._field_overlay_node.z_index and sh_parent_layer != null and sh_parent_layer.follow_viewport_enabled and main_hud_layer != null and sh_parent_layer.layer > main_hud_layer.layer and sh_ctrl_layer != null and sh_ctrl_layer.layer > sh_parent_layer.layer, "9.10f: Shenron layer (CanvasLayer=%d, z=%d) renders strictly above HP/Mana FieldOverlay (z=%d) and HUDLayer (CanvasLayer=%d)" % [sh_parent_layer.layer if sh_parent_layer != null else -1, arena.shenron_summon.z_index, arena._field_overlay_node.z_index, main_hud_layer.layer if main_hud_layer != null else -1])

	# (f) Right end of Sườn núi Teinan (wy=792): physically touching slim 26px portal displays pending Map 3 notice!
	var max_wx_ts: float = float(arena.get("walkable_max_x"))
	p_ts.position = Vector2(max_wx_ts, float(arena.call(&"_ground_y_at", max_wx_ts)))
	arena.set("_map_transition_cooldown_s", 0.0)
	arena.call(&"step_player_movement", 0.05, 1)
	var t_st_pend: Dictionary = arena.call(&"get_map_transition_state")
	_check(str(arena.get("current_map_id")) == "teinan_slope" and absf(p_ts.position.y - 792.0) < 2.0 and absf(float(t_st_pend.get("portal_width_px", 0.0)) - 26.0) < 0.5 and bool(t_st_pend.get("pending_next_map", false)) and float(arena.get("_wish_notice_timer_s")) > 0.0, "9.9a: Physically touching slim 26px right portal at wy=792 displays pending Map 3 notice without leaving map")

	# (g) Walking left (-1) to physically touch slim 26px left portal auto-returns to Núi Teinan AND preserves Son Goku SSJ1!
	var min_wx_ts: float = float(arena.get("walkable_min_x"))
	p_ts.position = Vector2(min_wx_ts, float(arena.call(&"_ground_y_at", min_wx_ts)))
	arena.set("_map_transition_cooldown_s", 0.0)
	arena.call(&"step_player_movement", 0.05, -1)
	await process_frame
	var w_after_leave: Dictionary = arena.call(&"get_interactive_water_metrics")
	_check(str(arena.get("current_map_id")) == "rocky_plateau" and arena.player_node.position.x > 5500.0 and bool(arena.get("player_facing_left")) and bool(arena.player_node.get("is_ssj")) and (fm.get("slots") as Array).size() == 14 and not bool(w_after_leave.get("enabled", true)) and not bool(w_after_leave.get("standalone_tres_mounted", true)), "9.9b: Physically touching slim left portal auto-returned to Núi Teinan facing left preserving Goku SSJ1, 14 monsters & freed water nodes")

	if _fails.is_empty():
		print("=== ALL TAPION, GENKI & CELL ARENA CHECKS PASSED ===")
		quit(0)
	else:
		print("=== FAILED CHECKS (%d) ===" % _fails.size())
		for f in _fails:
			print("  - ", f)
		quit(1)
