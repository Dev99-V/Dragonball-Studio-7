class_name MobileActionPad
extends Control
## Mobile Analog Stick (bottom-left) + Circular Skill Arc 1..8 + World Position Mini-Map
## Styled cleanly after Owner HUD reference (image copy 8.png): dark frosted glass,
## crisp white double rings, neon-green attack & target reticle accents, vector icons,
## and flexible Button Assignment Settings Modal (buttons 2..7 customizable; 1 & 8 locked).

signal action_triggered(slot_id: int, action_id: String)
signal target_cycle_requested()
signal slot_binding_changed(slot_id: int, action_id: String)
signal auto_battle_toggled(enabled: bool)

const ACTION_LABELS := {
	"attack_light": "Đánh",
	"jump": "Nhảy",
	"teleport": "Tốc biến",
	"power_up": "Chưởng",
	"attack_heavy": "Đánh nặng",
	"pickup_items": "Nhặt",
	"transform_ssj": "Biến SSJ",
	"fly_toggle": "Bay",
	"barrier": "Khiên 10s",
	"energy_recover": "Gồng hồi",
	"flurry_kick": "Đá liên hoàn",
	"atomic_blast": "Atomic",
	"kamehameha": "Kamehameha",
	"empty": "Trống",
}

const SHORT_LABELS := {
	"attack_light": "ĐÁNH",
	"jump": "NHẢY",
	"teleport": "TỐC BIẾN",
	"power_up": "CHƯỞNG",
	"attack_heavy": "NẶNG",
	"pickup_items": "NHẶT",
	"transform_ssj": "SSJ1",
	"fly_toggle": "BAY",
	"barrier": "KHIÊN",
	"energy_recover": "HỒI 3S",
	"flurry_kick": "ĐÁ LH",
	"atomic_blast": "ATOMIC",
	"kamehameha": "KAME",
	"cycle_target": "TRỎ",
}

const ASSIGNABLE_ACTIONS := ["jump", "teleport", "transform_ssj", "flurry_kick", "atomic_blast", "kamehameha", "barrier", "energy_recover", "fly_toggle", "power_up", "attack_heavy", "pickup_items", "empty"]

var analog_dir_x: int = 0
var analog_dir_y: int = 0
var analog_vector: Vector2 = Vector2.ZERO

var safe_root: MarginContainer = null
var _anchor_ctrl: Control = null
var _analog_ctrl: Control = null
var _buttons_root: Control = null
var _auto_btn: Button = null
var _auto_visual: Control = null
var _auto_battle_enabled: bool = false
var _slot_buttons: Dictionary = {}
var _slot_visuals: Dictionary = {}
var _slot_bindings: Dictionary = {
	1: "attack_light",
	2: "jump",
	3: "teleport",
	4: "power_up",
	5: "empty",
	6: "empty",
	7: "empty",
	8: "cycle_target",
}
var _available_actions: PackedStringArray = PackedStringArray(["attack_light", "jump", "teleport", "power_up"])
var _settings_panel: PanelContainer = null
var _settings_rows: VBoxContainer = null
var _current_mana: float = 0.0
var _max_mana: float = 100.0
var _jump_enabled: bool = true
var _flight_mode: bool = false
var _pointer_kind: String = "enemy"
var _hero_stamina: float = 100.0
var _hero_max_stamina: float = 100.0
var _hero_is_songoku: bool = false
var _hero_is_ssj: bool = false
var _hero_can_attack: bool = true
var _hero_fly_active: bool = false
var _hero_combo_step: int = 0
var _hero_atomic_cd: float = 0.0
var _hero_barrier_active_s: float = 0.0
var _hero_barrier_cd: float = 0.0
var _hero_recover_cd: float = 0.0
var _hero_flurry_cd: float = 0.0
var _hero_on_ground: bool = true

# Analog drag tracking
var _analog_touch_idx: int = -1
var _analog_mouse_down: bool = false
var _analog_radius: float = 64.0
var _knob_radius: float = 27.0


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	_build_ui()


func _make_circle_style(bg_col: Color, border_col: Color, border_w: int = 2) -> StyleBoxFlat:
	var sb := StyleBoxFlat.new()
	sb.bg_color = bg_col
	sb.border_color = border_col
	sb.set_border_width_all(border_w)
	sb.set_corner_radius_all(999)
	return sb


func _apply_circle_button_theme(btn: Button, slot_id: int) -> void:
	var empty_sb := StyleBoxEmpty.new()
	btn.add_theme_stylebox_override("normal", empty_sb)
	btn.add_theme_stylebox_override("hover", empty_sb)
	btn.add_theme_stylebox_override("pressed", empty_sb)
	btn.add_theme_stylebox_override("disabled", empty_sb)
	btn.add_theme_stylebox_override("focus", empty_sb)
	btn.flat = true
	btn.text = ""
	btn.set_meta(&"slot_id", slot_id)


func _build_ui() -> void:
	safe_root = MarginContainer.new()
	safe_root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	safe_root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(safe_root)

	_anchor_ctrl = Control.new()
	_anchor_ctrl.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_anchor_ctrl.mouse_filter = Control.MOUSE_FILTER_IGNORE
	safe_root.add_child(_anchor_ctrl)

	# Bottom-Left Virtual Analog Stick (Region #1 of c5ebb08600d4cf82deaf6312bac7905a.jpg)
	_analog_ctrl = _AnalogCanvas.new()
	_analog_ctrl.name = "AnalogStick"
	_analog_ctrl.anchor_left = 0.0
	_analog_ctrl.anchor_right = 0.0
	_analog_ctrl.anchor_top = 1.0
	_analog_ctrl.anchor_bottom = 1.0
	_analog_ctrl.offset_left = 44.0
	_analog_ctrl.offset_top = -236.0
	_analog_ctrl.offset_right = 248.0
	_analog_ctrl.offset_bottom = -32.0
	_analog_ctrl.mouse_filter = Control.MOUSE_FILTER_STOP
	_analog_ctrl.set("pad_owner", self)
	_anchor_ctrl.add_child(_analog_ctrl)

	# Bottom-Right Honeycomb Skill Cluster (1:1 proportions from Region #2 of c5ebb08600d4cf82deaf6312bac7905a.jpg)
	_buttons_root = Control.new()
	_buttons_root.name = "CircularSkillCluster"
	_buttons_root.anchor_left = 1.0
	_buttons_root.anchor_right = 1.0
	_buttons_root.anchor_top = 1.0
	_buttons_root.anchor_bottom = 1.0
	_buttons_root.offset_left = -492.0
	_buttons_root.offset_top = -384.0
	_buttons_root.offset_right = -24.0
	_buttons_root.offset_bottom = -16.0
	_buttons_root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_anchor_ctrl.add_child(_buttons_root)

	# Measured 3-column honeycomb matching uploaded HUD reference Region #2 (box 468x368 anchored bottom-right):
	#   Col R (large): Slot 1 (B: Attack 122px bottom-right), Slot 5 (Y: Kamehameha 106px directly above B)
	#   Col M (core):  Slot 2 (RB: Teleport/Jump 92px top), Slot 4 (X: Atomic 94px center), Slot 3 (A: Flurry Kick 92px bottom)
	#   Col L (inner): Slot 6 (Barrier 84px upper-left), Slot 10 (Hồi 3s 88px lower-left, 75/150 style)
	#   Outer-Left:    Slot 7 (SSJ1 72px), Slot 9 (AUTO 62px), Slot 8 (TRỎ 62px)
	var layout_specs := {
		1: Rect2(326, 224, 122, 122),
		5: Rect2(340, 100, 106, 106),
		2: Rect2(226, 16, 92, 92),
		4: Rect2(210, 144, 94, 94),
		3: Rect2(204, 266, 92, 92),
		6: Rect2(106, 80, 84, 84),
		10: Rect2(92, 200, 88, 88),
		7: Rect2(10, 140, 72, 72),
		8: Rect2(14, 294, 62, 62),
	}
	for sid in [1, 2, 3, 4, 5, 6, 7, 8, 10]:
		var r: Rect2 = layout_specs[sid]
		var btn := Button.new()
		btn.name = "SkillCircle_%d" % sid
		btn.position = r.position
		btn.size = r.size
		btn.custom_minimum_size = r.size
		_apply_circle_button_theme(btn, int(sid))
		var vis := _SkillButtonVisual.new()
		vis.name = "Visual"
		vis.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		vis.mouse_filter = Control.MOUSE_FILTER_IGNORE
		vis.set("pad_owner", self)
		vis.set("owner_btn", btn)
		vis.set("slot_id", int(sid))
		btn.add_child(vis)
		var cap_id := int(sid)
		btn.pressed.connect(func() -> void:
			_on_slot_pressed(cap_id)
		)
		var redraw_fn := func() -> void:
			vis.queue_redraw()
		btn.button_down.connect(redraw_fn)
		btn.button_up.connect(redraw_fn)
		btn.mouse_entered.connect(redraw_fn)
		btn.mouse_exited.connect(redraw_fn)
		_buttons_root.add_child(btn)
		_slot_buttons[sid] = btn
		_slot_visuals[sid] = vis

	# Dedicated AUTO / TAY Battle Toggle Button (outer-left directly above TRỎ reticle, slot_id = 9)
	_auto_btn = Button.new()
	_auto_btn.name = "AutoBattleCircle"
	_auto_btn.position = Vector2(14, 224)
	_auto_btn.size = Vector2(62, 62)
	_auto_btn.custom_minimum_size = Vector2(62, 62)
	_apply_circle_button_theme(_auto_btn, 9)
	_auto_btn.tooltip_text = "Bật/Tắt Tự Động Đánh Quái (Utility AI)"
	_auto_visual = _SkillButtonVisual.new()
	_auto_visual.name = "Visual"
	_auto_visual.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_auto_visual.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_auto_visual.set("pad_owner", self)
	_auto_visual.set("owner_btn", _auto_btn)
	_auto_visual.set("slot_id", 9)
	_auto_btn.add_child(_auto_visual)
	_auto_btn.pressed.connect(func() -> void:
		_auto_battle_enabled = not _auto_battle_enabled
		_auto_visual.queue_redraw()
		auto_battle_toggled.emit(_auto_battle_enabled)
	)
	var redraw_auto := func() -> void:
		_auto_visual.queue_redraw()
	_auto_btn.button_down.connect(redraw_auto)
	_auto_btn.button_up.connect(redraw_auto)
	_auto_btn.mouse_entered.connect(redraw_auto)
	_auto_btn.mouse_exited.connect(redraw_auto)
	_buttons_root.add_child(_auto_btn)

	_build_settings_modal()
	_refresh_slot_buttons()


func _build_settings_modal() -> void:
	_settings_panel = PanelContainer.new()
	_settings_panel.name = "ButtonBindingSettingsModal"
	_settings_panel.anchor_left = 0.5
	_settings_panel.anchor_right = 0.5
	_settings_panel.anchor_top = 0.5
	_settings_panel.anchor_bottom = 0.5
	_settings_panel.offset_left = -250.0
	_settings_panel.offset_right = 250.0
	_settings_panel.offset_top = -190.0
	_settings_panel.offset_bottom = 190.0
	_settings_panel.visible = false
	_settings_panel.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(_settings_panel)

	var vbox := VBoxContainer.new()
	vbox.add_theme_constant_override("separation", 8)
	_settings_panel.add_child(vbox)

	var hdr := HBoxContainer.new()
	var title := Label.new()
	title.text = "⚙️ Cài đặt gán nút chiêu (2..7)"
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	hdr.add_child(title)
	var close_btn := Button.new()
	close_btn.text = "✕"
	close_btn.pressed.connect(func() -> void:
		_settings_panel.visible = false
	)
	hdr.add_child(close_btn)
	vbox.add_child(hdr)

	var lock_note := Label.new()
	lock_note.text = "Nút 1 (Đánh/Nhặt) & Nút 8 (Xoay Trỏ) cố định; nút 2..7 tùy chỉnh:"
	lock_note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	vbox.add_child(lock_note)

	_settings_rows = VBoxContainer.new()
	_settings_rows.add_theme_constant_override("separation", 6)
	vbox.add_child(_settings_rows)
	_rebuild_settings_rows()


func _rebuild_settings_rows() -> void:
	if _settings_rows == null:
		return
	for ch in _settings_rows.get_children():
		ch.queue_free()
	for sid in [2, 3, 4, 5, 6, 7]:
		var row := HBoxContainer.new()
		row.add_theme_constant_override("separation", 10)
		var lbl := Label.new()
		lbl.text = "Nút số %d:" % sid
		lbl.custom_minimum_size = Vector2(110.0, 0.0)
		row.add_child(lbl)

		var opt := OptionButton.new()
		opt.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		var cur_act := str(_slot_bindings.get(sid, "empty"))
		var sel_idx := 0
		var idx := 0
		for act_id in ASSIGNABLE_ACTIONS:
			if act_id != "empty" and act_id != "pickup_items" and not _available_actions.has(act_id):
				continue
			opt.add_item(str(ACTION_LABELS.get(act_id, act_id)), idx)
			opt.set_item_metadata(idx, act_id)
			if act_id == cur_act:
				sel_idx = idx
			idx += 1
		opt.select(sel_idx)
		var cap_sid := int(sid)
		opt.item_selected.connect(func(picked_idx: int) -> void:
			var act_name := str(opt.get_item_metadata(picked_idx))
			set_slot_binding(cap_sid, act_name)
		)
		row.add_child(opt)
		_settings_rows.add_child(row)


func toggle_settings_modal() -> void:
	if _settings_panel == null:
		return
	_settings_panel.visible = not _settings_panel.visible
	if _settings_panel.visible:
		_rebuild_settings_rows()


func is_screen_point_over_pad(screen_pos: Vector2) -> bool:
	if not visible:
		return false
	if _settings_panel != null and is_instance_valid(_settings_panel) and _settings_panel.visible:
		if _settings_panel.get_global_rect().has_point(screen_pos):
			return true
	if _analog_ctrl != null and is_instance_valid(_analog_ctrl) and _analog_ctrl.visible:
		if _analog_ctrl.get_global_rect().has_point(screen_pos):
			return true
	for sid in _slot_buttons:
		var btn := _slot_buttons.get(sid) as Button
		if btn != null and is_instance_valid(btn) and btn.visible:
			if btn.get_global_rect().has_point(screen_pos):
				return true
	if _auto_btn != null and is_instance_valid(_auto_btn) and _auto_btn.visible:
		if _auto_btn.get_global_rect().has_point(screen_pos):
			return true
	return false


func set_auto_battle_enabled(enabled: bool) -> void:
	_auto_battle_enabled = enabled
	if _auto_btn != null and is_instance_valid(_auto_btn):
		_auto_btn.tooltip_text = "AUTO ĐANG BẬT (Bấm hoặc kéo Analog để tắt)" if enabled else "Bật Tự Động Đánh Quái (Utility AI)"
	if _auto_visual != null and is_instance_valid(_auto_visual):
		_auto_visual.queue_redraw()


var _configured_char_id: String = ""
var _custom_bindings_by_char: Dictionary = {}


func set_slot_binding(slot_id: int, action_id: String) -> void:
	if slot_id == 1 or slot_id == 8:
		return
	_slot_bindings[slot_id] = action_id
	if not _configured_char_id.is_empty():
		var saved: Dictionary = _custom_bindings_by_char.get(_configured_char_id, {})
		saved[slot_id] = action_id
		_custom_bindings_by_char[_configured_char_id] = saved
	_refresh_slot_buttons()
	slot_binding_changed.emit(slot_id, action_id)


func get_slot_binding(slot_id: int) -> String:
	return str(_slot_bindings.get(slot_id, "empty"))


func configure_for_character(char_id: String, available_clips: PackedStringArray, is_flying: bool) -> void:
	_configured_char_id = char_id
	_flight_mode = is_flying
	_hero_is_songoku = (char_id == "songoku" or char_id == "songoku_hero_demo")
	var avail := PackedStringArray(["attack_light"])
	if is_flying or available_clips.has("jump"):
		avail.append("jump")
	if available_clips.has("teleport"):
		avail.append("teleport")
	if available_clips.has("transform_ssj"):
		avail.append("transform_ssj")
	if available_clips.has("barrier_cast") or _hero_is_songoku:
		avail.append("barrier")
	if available_clips.has("energy_recover") or _hero_is_songoku:
		avail.append("energy_recover")
	if available_clips.has("flurry_kick") or _hero_is_songoku:
		avail.append("flurry_kick")
	if available_clips.has("atomic_ground") or _hero_is_songoku:
		avail.append("atomic_blast")
	if available_clips.has("kame_ground_horiz") or _hero_is_songoku:
		avail.append("kamehameha")
	if available_clips.has("fly_aura") or available_clips.has("fly_launch"):
		avail.append("fly_toggle")
	if available_clips.has("power_up"):
		avail.append("power_up")
	if available_clips.has("attack_heavy"):
		avail.append("attack_heavy")
	_available_actions = avail
	_jump_enabled = is_flying or available_clips.has("jump")

	# Default bindings per character
	_slot_bindings[1] = "attack_light"
	_slot_bindings[2] = "jump" if _jump_enabled else "empty"
	_slot_bindings[3] = "teleport" if avail.has("teleport") else ("attack_heavy" if avail.has("attack_heavy") else "empty")
	_slot_bindings[4] = "power_up" if avail.has("power_up") else "empty"
	_slot_bindings[5] = "attack_heavy" if (avail.has("attack_heavy") and _slot_bindings[3] != "attack_heavy") else "empty"
	_slot_bindings[6] = "empty"
	_slot_bindings[7] = "empty"
	_slot_bindings[8] = "cycle_target"
	_slot_bindings[10] = "empty"
	if _hero_is_songoku:
		# Full Phase 2 Hero Skill Arc (ALL skills directly visible on screen: 2..7 + dedicated slot 10 `energy_recover`!)
		_slot_bindings[2] = "transform_ssj"
		_slot_bindings[3] = "teleport"
		_slot_bindings[4] = "flurry_kick"
		_slot_bindings[5] = "atomic_blast"
		_slot_bindings[6] = "kamehameha"
		_slot_bindings[7] = "barrier"
		_slot_bindings[10] = "energy_recover"
	elif char_id == "drum":
		_slot_bindings[2] = "jump"
		_slot_bindings[3] = "teleport"
		_slot_bindings[4] = "power_up"
		_slot_bindings[5] = "empty"
	# Preserve user-customized slot bindings across hide/show hero toggles for the same character.
	var custom_saved: Variant = _custom_bindings_by_char.get(char_id, {})
	if custom_saved is Dictionary:
		for k in (custom_saved as Dictionary).keys():
			var sid := int(k)
			var act := str((custom_saved as Dictionary)[k])
			if sid >= 2 and sid <= 7 and (act == "empty" or act == "pickup_items" or avail.has(act)):
				_slot_bindings[sid] = act
	_rebuild_settings_rows()
	_refresh_slot_buttons()


func set_mana_and_pointer_state(mana: float, max_mana: float, pointer_kind: String) -> void:
	_current_mana = mana
	_max_mana = max_mana
	_pointer_kind = pointer_kind
	_refresh_slot_buttons()


func set_hero_stamina_and_state(stamina: float, max_stamina: float, is_ssj: bool, can_attack_now: bool, fly_active: bool, combo_step: int, atomic_cd: float = 0.0, barrier_s: float = 0.0, barrier_cd: float = 0.0, recover_cd: float = 0.0, flurry_cd: float = 0.0, on_ground: bool = true) -> void:
	_hero_stamina = stamina
	_hero_max_stamina = maxf(1.0, max_stamina)
	_hero_is_ssj = is_ssj
	_hero_can_attack = can_attack_now
	_hero_fly_active = fly_active
	_hero_combo_step = combo_step
	_hero_atomic_cd = atomic_cd
	_hero_barrier_active_s = barrier_s
	_hero_barrier_cd = barrier_cd
	_hero_recover_cd = recover_cd
	_hero_flurry_cd = flurry_cd
	_hero_on_ground = on_ground
	_refresh_slot_buttons()


func set_jump_available(enabled: bool, flight: bool = false) -> void:
	_jump_enabled = enabled
	_flight_mode = flight
	_refresh_slot_buttons()


func _refresh_slot_buttons() -> void:
	for sid in [1, 2, 3, 4, 5, 6, 7, 8, 10]:
		var btn := _slot_buttons.get(sid) as Button
		if btn == null:
			continue
		var vis := _slot_visuals.get(sid) as Control
		if sid == 8:
			btn.visible = true
			btn.disabled = false
			btn.tooltip_text = "Đổi mục tiêu (Tab)"
			if vis != null:
				vis.queue_redraw()
			continue
		var act := str(_slot_bindings.get(sid, "empty"))
		if sid >= 2 and act == "empty":
			btn.visible = false
			continue
		btn.visible = true
		if sid == 1:
			if _pointer_kind == "item":
				btn.tooltip_text = "Nhặt vật phẩm"
				btn.disabled = false
			elif _pointer_kind == "npc":
				btn.tooltip_text = "Nói chuyện"
				btn.disabled = false
			elif _hero_is_songoku and not _hero_can_attack:
				btn.tooltip_text = "Đang ở dạng Base — Biến SSJ1 để tấn công"
				btn.disabled = false
			else:
				btn.tooltip_text = "Đánh thường (Đòn %d/7)" % ((_hero_combo_step % 7) + 1) if _hero_is_songoku else "Đánh thường"
				btn.disabled = false
			if vis != null:
				vis.queue_redraw()
			continue
		var lbl := str(ACTION_LABELS.get(act, act))
		if act == "jump" and _flight_mode:
			lbl = "Bay lên"
		if act == "power_up":
			btn.tooltip_text = "%s (%d/%d MP)" % [lbl, int(floor(_current_mana)), int(round(_max_mana))]
			btn.disabled = _current_mana < 100.0
		elif act == "jump":
			btn.tooltip_text = lbl
			btn.disabled = (not _jump_enabled) or (_hero_is_songoku and not _hero_is_ssj)
		elif act == "fly_toggle":
			btn.tooltip_text = "Hạ cánh" if _hero_fly_active else "Bay lên (Fly_Aura)"
			btn.disabled = _hero_is_songoku and not _hero_is_ssj
		elif act == "transform_ssj":
			btn.tooltip_text = "Xả SSJ1 → Base" if _hero_is_ssj else "Biến hình SSJ1"
			btn.disabled = false
		elif act == "teleport":
			if _hero_is_songoku:
				btn.tooltip_text = "Dịch chuyển (TL %d/%d · Tĩnh -75 / Di chuyển -25)" % [int(floor(_hero_stamina)), int(round(_hero_max_stamina))]
				btn.disabled = (not _hero_is_ssj) or (_hero_stamina < 25.0)
			else:
				btn.tooltip_text = lbl
				btn.disabled = false
		elif act == "atomic_blast":
			btn.tooltip_text = "Atomic Blast (Hồi 12s)" if _hero_atomic_cd <= 0.0 else "Atomic Blast (%.1fs)" % _hero_atomic_cd
			btn.disabled = (not _hero_is_ssj) or _hero_atomic_cd > 0.0
		elif act == "kamehameha":
			btn.tooltip_text = "Kamehameha (80 MP · Hiện có %d)" % int(floor(_current_mana))
			btn.disabled = (not _hero_is_ssj) or (_current_mana < 80.0)
		elif act == "flurry_kick":
			btn.tooltip_text = "Đá liên hoàn (Choáng Boss/Quái/Tướng)" if _hero_flurry_cd <= 0.0 else "Đá liên hoàn (%.1fs)" % _hero_flurry_cd
			btn.disabled = (not _hero_is_ssj) or _hero_flurry_cd > 0.0
		elif act == "barrier":
			btn.tooltip_text = "Khiên 10s (Đang bật %.1fs)" % _hero_barrier_active_s if _hero_barrier_active_s > 0.0 else ("Khiên bảo vệ 10s" if _hero_barrier_cd <= 0.0 else "Khiên (%.1fs)" % _hero_barrier_cd)
			btn.disabled = (not _hero_is_ssj) or _hero_barrier_cd > 0.0
		elif act == "energy_recover":
			if not _hero_on_ground:
				btn.tooltip_text = "Gồng hồi 3s (Chỉ dùng khi đứng mặt đất)"
			elif _hero_recover_cd <= 0.0:
				btn.tooltip_text = "Gồng hồi 3s (Máu + Giáp + Khinh công)"
			else:
				btn.tooltip_text = "Gồng hồi (%.1fs)" % _hero_recover_cd
			btn.disabled = (not _hero_is_ssj) or (not _hero_on_ground) or _hero_recover_cd > 0.0
		else:
			btn.tooltip_text = lbl
			btn.disabled = false
		if vis != null:
			vis.queue_redraw()


func _on_slot_pressed(slot_id: int) -> void:
	if slot_id == 8:
		target_cycle_requested.emit()
		return
	var act := str(_slot_bindings.get(slot_id, "empty"))
	if act == "empty":
		return
	action_triggered.emit(slot_id, act)


func apply_safe_area(layout_info: Dictionary) -> void:
	if safe_root == null:
		return
	var insets: Dictionary = layout_info.get("safe_insets_logic", {})
	safe_root.add_theme_constant_override("margin_left", int(round(float(insets.get("left", 0.0)))))
	safe_root.add_theme_constant_override("margin_top", int(round(float(insets.get("top", 0.0)))))
	safe_root.add_theme_constant_override("margin_right", int(round(float(insets.get("right", 0.0)))))
	safe_root.add_theme_constant_override("margin_bottom", int(round(float(insets.get("bottom", 0.0)))))


func _update_analog_from_local(local_pos: Vector2) -> void:
	if _analog_ctrl == null:
		return
	var center := _analog_ctrl.size * 0.5
	var delta := local_pos - center
	var max_r := maxf(16.0, _analog_radius - _knob_radius * 0.4)
	if delta.length() > max_r:
		delta = delta.normalized() * max_r
	analog_vector = delta / max_r
	analog_dir_x = -1 if analog_vector.x < -0.22 else (1 if analog_vector.x > 0.22 else 0)
	analog_dir_y = -1 if analog_vector.y < -0.28 else (1 if analog_vector.y > 0.28 else 0)
	_analog_ctrl.queue_redraw()


func _reset_analog() -> void:
	_analog_touch_idx = -1
	_analog_mouse_down = false
	analog_vector = Vector2.ZERO
	analog_dir_x = 0
	analog_dir_y = 0
	if _analog_ctrl != null:
		_analog_ctrl.queue_redraw()


class _AnalogCanvas extends Control:
	var pad_owner = null

	func _gui_input(event: InputEvent) -> void:
		if pad_owner == null:
			return
		if event is InputEventScreenTouch:
			var st := event as InputEventScreenTouch
			if st.pressed and pad_owner._analog_touch_idx == -1:
				pad_owner._analog_touch_idx = st.index
				pad_owner._update_analog_from_local(st.position)
				accept_event()
			elif not st.pressed and st.index == pad_owner._analog_touch_idx:
				pad_owner._reset_analog()
				accept_event()
		elif event is InputEventScreenDrag:
			var sd := event as InputEventScreenDrag
			if sd.index == pad_owner._analog_touch_idx:
				pad_owner._update_analog_from_local(sd.position)
				accept_event()
		elif event is InputEventMouseButton:
			var mb := event as InputEventMouseButton
			# Ignore touch-emulated mouse events or any mouse input while a real touch finger owns the analog stick (multi-touch fix for Android & iOS).
			if mb.device == InputEvent.DEVICE_ID_EMULATION or pad_owner._analog_touch_idx != -1:
				return
			if mb.button_index == MOUSE_BUTTON_LEFT:
				if mb.pressed:
					pad_owner._analog_mouse_down = true
					pad_owner._update_analog_from_local(mb.position)
				else:
					pad_owner._reset_analog()
				accept_event()
		elif event is InputEventMouseMotion and pad_owner._analog_mouse_down:
			var mm := event as InputEventMouseMotion
			if mm.device == InputEvent.DEVICE_ID_EMULATION or pad_owner._analog_touch_idx != -1:
				return
			pad_owner._update_analog_from_local(mm.position)
			accept_event()

	func _draw() -> void:
		if pad_owner == null:
			return
		var center := size * 0.5
		var base_r := minf(size.x, size.y) * 0.45
		pad_owner._analog_radius = base_r
		var active_drag: bool = pad_owner.analog_vector.length() > 0.08 or pad_owner._analog_touch_idx != -1 or pad_owner._analog_mouse_down
		# Frosted translucent glass joystick referencing green region #1 of c5ebb08600d4cf82deaf6312bac7905a.jpg
		draw_circle(center, base_r, Color(0.86, 0.92, 0.98, 0.18 if active_drag else 0.12))
		draw_circle(center, base_r * 0.82, Color(0.08, 0.12, 0.18, 0.24 if active_drag else 0.18))
		draw_arc(center, base_r, 0.0, TAU, 56, Color(0.96, 0.98, 1.0, 0.68 if active_drag else 0.48), 2.0, true)
		draw_arc(center, base_r * 0.82, 0.0, TAU, 48, Color(0.95, 0.98, 1.0, 0.26), 1.0, true)
		# Subtle frosted glass specular highlight on top-left rim
		draw_arc(center, base_r - 2.0, -PI * 0.82, -PI * 0.26, 20, Color(1.0, 1.0, 1.0, 0.34), 1.6, true)
		var knob_pos: Vector2 = center + pad_owner.analog_vector * (base_r - pad_owner._knob_radius * 0.4)
		var knob_r: float = pad_owner._knob_radius * (0.94 if active_drag else 0.86)
		draw_circle(knob_pos, knob_r, Color(0.92, 0.97, 1.0, 0.36 if active_drag else 0.22))
		draw_arc(knob_pos, knob_r, 0.0, TAU, 36, Color(0.45, 0.96, 1.0, 0.92) if active_drag else Color(0.96, 0.98, 1.0, 0.72), 2.2, true)


class _SkillButtonVisual extends Control:
	var pad_owner = null
	var owner_btn: Button = null
	var slot_id: int = 1

	func _draw() -> void:
		if pad_owner == null or owner_btn == null:
			return
		var center := size * 0.5
		var pressed_now := owner_btn.button_pressed
		var hovered_now := owner_btn.is_hovered()
		var disabled_now := owner_btn.disabled
		# Tactile press scale feedback (shrinks subtly on touch/press, restores on release)
		var r := minf(size.x, size.y) * (0.435 if pressed_now else 0.47)
		var alpha_mul := 0.36 if disabled_now else 1.0
		var font := ThemeDB.fallback_font

		if slot_id == 9:
			# Frosted glass AUTO / TAY toggle button
			var is_on: bool = bool(pad_owner._auto_battle_enabled)
			var bg_c := Color(0.16, 0.46, 0.32, 0.52 if pressed_now else 0.42) if is_on else Color(0.10, 0.14, 0.22, 0.44 if pressed_now else 0.30)
			var ring_c := Color(0.35, 0.98, 0.62, 0.95) if is_on else Color(0.94, 0.97, 1.0, 0.66)
			draw_circle(center, r * 0.92, bg_c)
			draw_arc(center, r * 0.92, -PI * 0.85, -PI * 0.22, 18, Color(1.0, 1.0, 1.0, 0.32), 1.4, true)
			draw_arc(center, r * 0.92, 0.0, TAU, 36, ring_c, 2.6 if is_on else 1.8, true)
			if is_on:
				draw_arc(center, r * 0.72, -PI * 0.75, PI * 0.25, 18, Color(1.0, 0.90, 0.32, 0.92), 2.2, true)
				draw_arc(center, r * 0.72, PI * 0.25, PI * 1.25, 18, Color(0.28, 0.98, 0.62, 0.92), 2.2, true)
			if font != null:
				draw_string(font, Vector2(center.x - 24.0, center.y + 4.0), "AUTO", HORIZONTAL_ALIGNMENT_CENTER, 48.0, 12, Color(1.0, 0.97, 0.50, 1.0) if is_on else Color(0.95, 0.98, 1.0, 0.94))
				draw_string(font, Vector2(center.x - 24.0, size.y - 6.0), "BẬT" if is_on else "TAY", HORIZONTAL_ALIGNMENT_CENTER, 48.0, 9, ring_c)
			return

		if slot_id == 8:
			# Frosted glass target reticle button
			var col_g := Color(0.32, 0.98, 0.62, (0.98 if pressed_now else 0.92) * alpha_mul)
			draw_circle(center, r * 0.90, Color(0.14, 0.20, 0.28, (0.50 if pressed_now else (0.38 if hovered_now else 0.28)) * alpha_mul))
			draw_arc(center, r * 0.90, 0.0, TAU, 36, Color(0.94, 0.98, 1.0, 0.56 * alpha_mul), 1.6, true)
			for q in range(4):
				var a0 := float(q) * PI * 0.5 + 0.20
				var a1 := float(q + 1) * PI * 0.5 - 0.20
				draw_arc(center, r * 0.70, a0, a1, 12, col_g, 2.4, true)
			for dir_v in [Vector2(1, 0), Vector2(-1, 0), Vector2(0, 1), Vector2(0, -1)]:
				draw_line(center + dir_v * (r * 0.46), center + dir_v * (r * 0.84), col_g, 2.2, true)
			draw_circle(center, 3.0, col_g)
			if font != null:
				draw_string(font, Vector2(center.x - 16.0, size.y - 5.0), "TRỎ", HORIZONTAL_ALIGNMENT_CENTER, 32.0, 10, Color(0.96, 0.99, 1.0, alpha_mul))
			return

		var act := str(pad_owner._slot_bindings.get(slot_id, "empty"))
		# Frosted translucent glass base disc (green region #2 style from c5ebb08600d4cf82deaf6312bac7905a.jpg)
		var glass_bg := Color(0.86, 0.94, 1.0, 0.34) if pressed_now else (Color(0.22, 0.30, 0.42, 0.38) if hovered_now else Color(0.10, 0.14, 0.22, 0.30))
		glass_bg.a *= alpha_mul
		draw_circle(center, r, glass_bg)
		# Inner frosted sheen + crisp thin glass rim
		draw_circle(center, r * 0.86, Color(0.94, 0.98, 1.0, (0.14 if pressed_now else 0.07) * alpha_mul))
		draw_arc(center, r, 0.0, TAU, 48, Color(0.96, 0.98, 1.0, (0.94 if pressed_now else 0.68) * alpha_mul), 2.4 if pressed_now else 1.8, true)
		draw_arc(center, r * 0.88, -PI * 0.84, -PI * 0.20, 22, Color(1.0, 1.0, 1.0, 0.40 * alpha_mul), 1.4, true)

		if slot_id == 1:
			# Primary large frosted glass attack/interact circle
			var accent_main := Color(0.96, 0.98, 1.0, 0.96 * alpha_mul)
			if pad_owner._pointer_kind == "item":
				accent_main = Color(0.40, 0.92, 1.0, 0.96 * alpha_mul)
			elif pad_owner._pointer_kind == "npc":
				accent_main = Color(1.0, 0.88, 0.40, 0.96 * alpha_mul)
			for q in range(4):
				var a0 := float(q) * PI * 0.5 + 0.26
				var a1 := float(q + 1) * PI * 0.5 - 0.26
				draw_arc(center, r * 0.72, a0, a1, 14, Color(accent_main.r, accent_main.g, accent_main.b, 0.65 * alpha_mul), 2.2, true)
			if pad_owner._pointer_kind == "item":
				_draw_pickup_icon(center + Vector2(0.0, -5.0), r * 0.36, accent_main)
				if font != null:
					draw_string(font, Vector2(center.x - 28.0, center.y + r * 0.54), "NHẶT", HORIZONTAL_ALIGNMENT_CENTER, 56.0, 11, Color(0.96, 0.99, 1.0, 0.95))
			elif pad_owner._pointer_kind == "npc":
				_draw_talk_icon(center + Vector2(0.0, -5.0), r * 0.34, accent_main)
				if font != null:
					draw_string(font, Vector2(center.x - 32.0, center.y + r * 0.54), "N.CHUYỆN", HORIZONTAL_ALIGNMENT_CENTER, 64.0, 10, Color(0.96, 0.99, 1.0, 0.95))
			else:
				var locked_base: bool = bool(pad_owner._hero_is_songoku) and not bool(pad_owner._hero_can_attack)
				var fist_col := Color(0.68, 0.72, 0.78, 0.58) if locked_base else accent_main
				_draw_fist_icon(center + Vector2(0.0, -6.0), r * 0.34, fist_col)
				if font != null:
					var atk_txt := "KHÓA" if locked_base else ("ĐÁNH %d/7" % ((int(pad_owner._hero_combo_step) % 7) + 1) if bool(pad_owner._hero_is_songoku) else "ĐÁNH")
					draw_string(font, Vector2(center.x - 34.0, center.y + r * 0.54), atk_txt, HORIZONTAL_ALIGNMENT_CENTER, 68.0, 11, Color(0.96, 0.99, 1.0, 0.95))
			return

		# Secondary skill buttons: crisp minimalist vector icons on frosted glass
		var icon_col := Color(0.96, 0.99, 1.0, 0.96 * alpha_mul)
		var accent_col := Color(0.36, 0.90, 1.0, 0.96 * alpha_mul)
		var short_lbl := str(SHORT_LABELS.get(act, act.to_upper()))
		if act == "jump":
			if pad_owner._flight_mode:
				short_lbl = "BAY"
			_draw_jump_icon(center + Vector2(0.0, -6.0), r * 0.42, icon_col)
		elif act == "teleport":
			if bool(pad_owner._hero_is_songoku):
				var s_ratio: float = clampf(float(pad_owner._hero_stamina) / maxf(1.0, float(pad_owner._hero_max_stamina)), 0.0, 1.0)
				draw_arc(center, r * 0.94, 0.0, TAU, 36, Color(0.20, 0.28, 0.36, 0.42), 3.0, true)
				if s_ratio > 0.005:
					var s_col := Color(0.34, 0.98, 0.68, 0.95) if float(pad_owner._hero_stamina) >= 75.0 else (Color(0.36, 0.88, 1.0, 0.92) if float(pad_owner._hero_stamina) >= 25.0 else Color(1.0, 0.60, 0.24, 0.90))
					draw_arc(center, r * 0.94, -PI * 0.5, -PI * 0.5 + TAU * s_ratio, 36, s_col, 3.2, true)
				short_lbl = "TL %d" % int(floor(float(pad_owner._hero_stamina)))
			_draw_dash_icon(center + Vector2(0.0, -7.0), r * 0.40, icon_col, accent_col)
		elif act == "transform_ssj":
			var ssj_gold := Color(1.0, 0.88, 0.28, 0.98 * alpha_mul)
			if bool(pad_owner._hero_is_ssj):
				draw_arc(center, r * 0.94, 0.0, TAU, 36, ssj_gold, 2.8, true)
				short_lbl = "XẢ SSJ"
			else:
				short_lbl = "SSJ1"
			_draw_ssj_bolt_icon(center + Vector2(0.0, -7.0), r * 0.42, ssj_gold)
		elif act == "fly_toggle":
			var fly_col := Color(1.0, 0.92, 0.36, 0.98 * alpha_mul) if bool(pad_owner._hero_fly_active) else icon_col
			if bool(pad_owner._hero_fly_active):
				draw_arc(center, r * 0.94, 0.0, TAU, 36, fly_col, 2.8, true)
				short_lbl = "HẠ"
			else:
				short_lbl = "BAY"
			_draw_jump_icon(center + Vector2(0.0, -6.0), r * 0.42, fly_col)
		elif act == "power_up":
			var ratio: float = clampf(pad_owner._current_mana / maxf(1.0, pad_owner._max_mana), 0.0, 1.0)
			if ratio > 0.01:
				draw_arc(center, r * 0.94, -PI * 0.5, -PI * 0.5 + TAU * ratio, 36, Color(0.28, 0.88, 1.0, 0.95 if ratio >= 1.0 else 0.68), 3.0, true)
			_draw_ki_icon(center + Vector2(0.0, -8.0), r * 0.36, accent_col if ratio >= 1.0 else icon_col)
			short_lbl = "%d/%d" % [int(floor(pad_owner._current_mana)), int(round(pad_owner._max_mana))]
		elif act == "attack_heavy":
			_draw_heavy_icon(center + Vector2(0.0, -6.0), r * 0.40, Color(1.0, 0.82, 0.36, 0.96 * alpha_mul))
		elif act == "atomic_blast":
			var cd_a: float = float(pad_owner._hero_atomic_cd)
			var ready_a: float = clampf(1.0 - cd_a / 12.0, 0.0, 1.0)
			var gold_a := Color(1.0, 0.86, 0.20, 0.98 * alpha_mul)
			draw_arc(center, r * 0.94, -PI * 0.5, -PI * 0.5 + TAU * ready_a, 36, gold_a, 3.0, true)
			_draw_atomic_orbs_icon(center + Vector2(0.0, -7.0), r * 0.42, gold_a)
			short_lbl = ("%ds" % int(ceilf(cd_a))) if cd_a > 0.05 else "ATOMIC"
		elif act == "kamehameha":
			var mp_ratio: float = clampf(pad_owner._current_mana / 80.0, 0.0, 1.0)
			var blue_k := Color(0.18, 0.72, 1.0, 0.98 * alpha_mul)
			draw_arc(center, r * 0.94, -PI * 0.5, -PI * 0.5 + TAU * mp_ratio, 36, blue_k if mp_ratio >= 1.0 else Color(0.24, 0.66, 0.96, 0.62), 3.0, true)
			# Dedicated blue Kamehameha beam icon on transparent frosted glass disc (Owner v10.6 HUD spec)
			_draw_kame_beam_icon(center + Vector2(0.0, -7.0), r * 0.48, blue_k, alpha_mul)
			short_lbl = "KAME" if mp_ratio >= 1.0 else "%d/80" % int(floor(pad_owner._current_mana))
		elif act == "flurry_kick":
			var cd_f: float = float(pad_owner._hero_flurry_cd)
			var ready_f: float = clampf(1.0 - cd_f / 6.0, 0.0, 1.0)
			var amber_f := Color(1.0, 0.74, 0.24, 0.98 * alpha_mul)
			draw_arc(center, r * 0.94, -PI * 0.5, -PI * 0.5 + TAU * ready_f, 36, amber_f, 2.8, true)
			_draw_flurry_kick_icon(center + Vector2(0.0, -6.0), r * 0.42, amber_f)
			short_lbl = ("%ds" % int(ceilf(cd_f))) if cd_f > 0.05 else "ĐÁ LH"
		elif act == "barrier":
			var act_b: float = float(pad_owner._hero_barrier_active_s)
			var cd_b: float = float(pad_owner._hero_barrier_cd)
			var col_b := Color(1.0, 0.92, 0.34, 0.98 * alpha_mul) if act_b > 0.0 else Color(0.46, 0.92, 1.0, 0.95 * alpha_mul)
			var ring_r: float = clampf(act_b / 10.0, 0.0, 1.0) if act_b > 0.0 else clampf(1.0 - cd_b / 16.0, 0.0, 1.0)
			draw_arc(center, r * 0.94, -PI * 0.5, -PI * 0.5 + TAU * ring_r, 36, col_b, 2.8, true)
			_draw_shield_icon(center + Vector2(0.0, -6.0), r * 0.40, col_b)
			short_lbl = ("%.0fs" % ceilf(act_b)) if act_b > 0.05 else (("%ds" % int(ceilf(cd_b))) if cd_b > 0.05 else "KHIÊN")
		elif act == "energy_recover":
			var cd_r: float = float(pad_owner._hero_recover_cd)
			var green_r := Color(0.32, 0.98, 0.56, 0.98 * alpha_mul)
			draw_arc(center, r * 0.94, -PI * 0.5, -PI * 0.5 + TAU * clampf(1.0 - cd_r / 10.0, 0.0, 1.0), 36, green_r, 2.8, true)
			_draw_recover_icon(center + Vector2(0.0, -7.0), r * 0.40, green_r)
			short_lbl = ("%ds" % int(ceilf(cd_r))) if cd_r > 0.05 else "HỒI 3S"
		elif act == "pickup_items":
			_draw_pickup_icon(center + Vector2(0.0, -6.0), r * 0.40, accent_col)

		if font != null:
			draw_string(font, Vector2(center.x - 30.0, center.y + r * 0.66), short_lbl, HORIZONTAL_ALIGNMENT_CENTER, 60.0, 10, Color(0.96, 0.99, 1.0, 0.95 * alpha_mul))

	func _draw_kame_beam_icon(c: Vector2, s: float, col: Color, alpha_mul: float) -> void:
		# Crisp transparent-background blue Kamehameha wave beam (origin orb + horizontal flaring blue energy stream + bright white core)
		var orig := c + Vector2(-s * 0.72, 0.0)
		var tip := c + Vector2(s * 0.88, 0.0)
		var outer_beam := PackedVector2Array([
			orig + Vector2(0.0, -s * 0.24),
			tip + Vector2(-s * 0.14, -s * 0.46),
			tip + Vector2(s * 0.08, 0.0),
			tip + Vector2(-s * 0.14, s * 0.46),
			orig + Vector2(0.0, s * 0.24),
		])
		draw_colored_polygon(outer_beam, Color(0.12, 0.58, 1.0, 0.72 * alpha_mul))
		var core_beam := PackedVector2Array([
			orig + Vector2(0.0, -s * 0.11),
			tip + Vector2(-s * 0.10, -s * 0.20),
			tip + Vector2(s * 0.05, 0.0),
			tip + Vector2(-s * 0.10, s * 0.20),
			orig + Vector2(0.0, s * 0.11),
		])
		draw_colored_polygon(core_beam, Color(0.84, 0.97, 1.0, 0.96 * alpha_mul))
		draw_circle(orig, s * 0.30, Color(0.22, 0.76, 1.0, 0.85 * alpha_mul))
		draw_circle(orig, s * 0.16, Color(1.0, 1.0, 1.0, 0.98 * alpha_mul))
		draw_arc(orig, s * 0.42, -PI * 0.58, PI * 0.58, 14, col, 1.8, true)

	func _draw_atomic_orbs_icon(c: Vector2, s: float, col: Color) -> void:
		for off_v in [Vector2(-0.52, -0.22), Vector2(0.0, -0.40), Vector2(0.54, -0.10), Vector2(-0.18, 0.34), Vector2(0.42, 0.36)]:
			var off: Vector2 = off_v as Vector2
			var p: Vector2 = c + off * s
			draw_circle(p, s * 0.19, Color(col.r, col.g, col.b, col.a * 0.55))
			draw_circle(p, s * 0.10, Color(1.0, 1.0, 0.92, col.a))
			draw_line(p - Vector2(s * 0.26, 0.0), p, Color(col.r, col.g, col.b, col.a * 0.85), 1.6, true)

	func _draw_ssj_bolt_icon(c: Vector2, s: float, col: Color) -> void:
		var bolt := PackedVector2Array([
			c + Vector2(s * 0.14, -s * 0.72),
			c + Vector2(-s * 0.38, s * 0.06),
			c + Vector2(s * 0.02, s * 0.06),
			c + Vector2(-s * 0.18, s * 0.74),
			c + Vector2(s * 0.42, -s * 0.08),
			c + Vector2(0.0, -s * 0.08),
		])
		draw_colored_polygon(bolt, col)

	func _draw_flurry_kick_icon(c: Vector2, s: float, col: Color) -> void:
		for i in range(3):
			var off_y := (float(i) - 1.0) * s * 0.34
			draw_arc(c + Vector2(-s * 0.18, off_y), s * 0.52, -PI * 0.35, PI * 0.30, 12, col, 2.2, true)
		draw_line(c + Vector2(-s * 0.55, s * 0.36), c + Vector2(s * 0.55, -s * 0.36), Color(1.0, 0.96, 0.86, col.a), 2.4, true)

	func _draw_shield_icon(c: Vector2, s: float, col: Color) -> void:
		var pts := PackedVector2Array([
			c + Vector2(0.0, -s * 0.76),
			c + Vector2(s * 0.64, -s * 0.48),
			c + Vector2(s * 0.56, s * 0.22),
			c + Vector2(0.0, s * 0.76),
			c + Vector2(-s * 0.56, s * 0.22),
			c + Vector2(-s * 0.64, -s * 0.48),
		])
		draw_colored_polygon(pts, Color(col.r, col.g, col.b, col.a * 0.24))
		draw_polyline(pts + PackedVector2Array([pts[0]]), col, 2.2, true)

	func _draw_recover_icon(c: Vector2, s: float, col: Color) -> void:
		draw_line(c + Vector2(0.0, -s * 0.56), c + Vector2(0.0, s * 0.56), col, 3.0, true)
		draw_line(c + Vector2(-s * 0.56, 0.0), c + Vector2(s * 0.56, 0.0), col, 3.0, true)
		draw_arc(c, s * 0.76, -PI * 0.82, -PI * 0.18, 12, Color(col.r, col.g, col.b, col.a * 0.75), 1.8, true)

	func _draw_fist_icon(c: Vector2, s: float, col: Color) -> void:
		# Stylized angled fist outline (inspired by primary green attack icon in image copy 8.png)
		var pts := PackedVector2Array([
			c + Vector2(-s * 0.65, s * 0.25),
			c + Vector2(-s * 0.72, -s * 0.25),
			c + Vector2(-s * 0.25, -s * 0.78),
			c + Vector2(s * 0.55, -s * 0.60),
			c + Vector2(s * 0.78, -s * 0.05),
			c + Vector2(s * 0.42, s * 0.68),
			c + Vector2(-s * 0.35, s * 0.68),
		])
		draw_polyline(pts + PackedVector2Array([pts[0]]), col, 2.4, true)
		for k in [-0.25, 0.08, 0.40]:
			draw_line(c + Vector2(s * k - s * 0.12, -s * 0.42), c + Vector2(s * k + s * 0.10, -s * 0.05), col, 2.0, true)

	func _draw_jump_icon(c: Vector2, s: float, col: Color) -> void:
		draw_arc(c + Vector2(0.0, s * 0.85), s * 0.95, PI * 1.18, PI * 1.82, 16, Color(col.r, col.g, col.b, col.a * 0.55), 2.0, true)
		draw_circle(c + Vector2(s * 0.12, -s * 0.52), s * 0.20, col)
		draw_line(c + Vector2(s * 0.05, -s * 0.30), c + Vector2(-s * 0.10, s * 0.14), col, 2.8, true)
		draw_line(c + Vector2(-s * 0.38, -s * 0.16), c + Vector2(s * 0.42, -s * 0.26), col, 2.2, true)
		draw_line(c + Vector2(-s * 0.10, s * 0.14), c + Vector2(-s * 0.42, s * 0.44), col, 2.4, true)
		draw_line(c + Vector2(-s * 0.10, s * 0.14), c + Vector2(s * 0.32, s * 0.32), col, 2.4, true)

	func _draw_dash_icon(c: Vector2, s: float, col: Color, portal_col: Color) -> void:
		draw_arc(c + Vector2(s * 0.34, 0.0), s * 0.62, -PI * 0.46, PI * 0.46, 18, portal_col, 2.6, true)
		for sy in [-0.36, -0.10, 0.16]:
			draw_line(c + Vector2(-s * 0.82, s * sy), c + Vector2(-s * 0.36, s * sy), col, 1.8, true)
		draw_circle(c + Vector2(s * 0.08, -s * 0.44), s * 0.18, col)
		draw_line(c + Vector2(0.0, -s * 0.22), c + Vector2(-s * 0.18, s * 0.18), col, 2.6, true)
		draw_line(c + Vector2(-s * 0.18, s * 0.18), c + Vector2(s * 0.24, s * 0.44), col, 2.2, true)

	func _draw_ki_icon(c: Vector2, s: float, col: Color) -> void:
		draw_circle(c, s * 0.48, Color(col.r, col.g, col.b, col.a * 0.30))
		draw_arc(c, s * 0.48, 0.0, TAU, 24, col, 2.2, true)
		draw_circle(c, s * 0.22, Color(1.0, 1.0, 1.0, col.a))
		for a in [0.0, PI * 0.5, PI, PI * 1.5, PI * 0.25, PI * 0.75, PI * 1.25, PI * 1.75]:
			var dv := Vector2(cos(a), sin(a))
			draw_line(c + dv * (s * 0.62), c + dv * (s * 0.92), col, 1.8, true)

	func _draw_heavy_icon(c: Vector2, s: float, col: Color) -> void:
		draw_line(c + Vector2(-s * 0.62, -s * 0.52), c + Vector2(s * 0.56, s * 0.44), col, 3.0, true)
		draw_line(c + Vector2(s * 0.48, -s * 0.48), c + Vector2(-s * 0.52, s * 0.48), col, 2.2, true)
		draw_arc(c, s * 0.68, -PI * 0.2, PI * 0.7, 16, col, 2.0, true)

	func _draw_pickup_icon(c: Vector2, s: float, col: Color) -> void:
		draw_circle(c + Vector2(0.0, s * 0.16), s * 0.38, Color(1.0, 0.74, 0.18, col.a * 0.85))
		draw_arc(c + Vector2(0.0, s * 0.16), s * 0.38, 0.0, TAU, 20, col, 2.0, true)
		draw_line(c + Vector2(0.0, -s * 0.72), c + Vector2(0.0, -s * 0.24), col, 2.2, true)
		draw_line(c + Vector2(-s * 0.24, -s * 0.48), c + Vector2(0.0, -s * 0.72), col, 2.2, true)
		draw_line(c + Vector2(s * 0.24, -s * 0.48), c + Vector2(0.0, -s * 0.72), col, 2.2, true)

	func _draw_talk_icon(c: Vector2, s: float, col: Color) -> void:
		draw_rect(Rect2(c.x - s * 0.65, c.y - s * 0.45, s * 1.30, s * 0.82), Color(col.r, col.g, col.b, 0.22), true)
		draw_rect(Rect2(c.x - s * 0.65, c.y - s * 0.45, s * 1.30, s * 0.82), col, false, 2.0)
