class_name MobileActionPad
extends Control
## Mobile Analog Stick (bottom-left) + Circular Skill Arc 1..8 (bottom-right, matching image copy 4.png)
## + Flexible Button Assignment Settings Modal (buttons 2..7 customizable; button 1 & 8 locked).

signal action_triggered(slot_id: int, action_id: String)
signal target_cycle_requested()
signal slot_binding_changed(slot_id: int, action_id: String)

const ACTION_LABELS := {
	"attack_light": "Đánh",
	"jump": "Nhảy",
	"teleport": "Tốc biến",
	"power_up": "Chưởng",
	"attack_heavy": "Đánh nặng",
	"pickup_items": "Nhặt",
	"empty": "Trống",
}

const ASSIGNABLE_ACTIONS := ["jump", "teleport", "power_up", "attack_heavy", "pickup_items", "empty"]

var analog_dir_x: int = 0
var analog_dir_y: int = 0
var analog_vector: Vector2 = Vector2.ZERO

var safe_root: MarginContainer = null
var _anchor_ctrl: Control = null
var _analog_ctrl: Control = null
var _buttons_root: Control = null
var _slot_buttons: Dictionary = {}
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

# Analog drag tracking
var _analog_touch_idx: int = -1
var _analog_mouse_down: bool = false
var _analog_radius: float = 64.0
var _knob_radius: float = 26.0


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


func _apply_circle_button_theme(btn: Button, accent: Color = Color(0.75, 0.88, 1.0, 0.50)) -> void:
	btn.add_theme_stylebox_override("normal", _make_circle_style(Color(0.06, 0.10, 0.18, 0.70), accent, 2))
	btn.add_theme_stylebox_override("hover", _make_circle_style(Color(0.10, 0.16, 0.28, 0.85), Color(0.45, 0.88, 1.0, 0.85), 2))
	btn.add_theme_stylebox_override("pressed", _make_circle_style(Color(0.16, 0.25, 0.42, 0.94), Color(1.0, 0.84, 0.25, 0.95), 3))
	btn.add_theme_stylebox_override("disabled", _make_circle_style(Color(0.06, 0.09, 0.14, 0.35), Color(0.50, 0.55, 0.65, 0.25), 1))
	btn.add_theme_font_size_override("font_size", 18)


func _build_ui() -> void:
	safe_root = MarginContainer.new()
	safe_root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	safe_root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(safe_root)

	_anchor_ctrl = Control.new()
	_anchor_ctrl.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_anchor_ctrl.mouse_filter = Control.MOUSE_FILTER_IGNORE
	safe_root.add_child(_anchor_ctrl)

	# Bottom-Left Virtual Analog Stick
	_analog_ctrl = _AnalogCanvas.new()
	_analog_ctrl.name = "AnalogStick"
	_analog_ctrl.anchor_left = 0.0
	_analog_ctrl.anchor_right = 0.0
	_analog_ctrl.anchor_top = 1.0
	_analog_ctrl.anchor_bottom = 1.0
	_analog_ctrl.offset_left = 26.0
	_analog_ctrl.offset_top = -182.0
	_analog_ctrl.offset_right = 186.0
	_analog_ctrl.offset_bottom = -22.0
	_analog_ctrl.mouse_filter = Control.MOUSE_FILTER_STOP
	_analog_ctrl.set("pad_owner", self)
	_anchor_ctrl.add_child(_analog_ctrl)

	# Bottom-Right Circular Button Cluster (matching image copy 4.png: 1 large + 2..7 arc + 8 target cycle)
	_buttons_root = Control.new()
	_buttons_root.name = "CircularSkillCluster"
	_buttons_root.anchor_left = 1.0
	_buttons_root.anchor_right = 1.0
	_buttons_root.anchor_top = 1.0
	_buttons_root.anchor_bottom = 1.0
	_buttons_root.offset_left = -380.0
	_buttons_root.offset_top = -290.0
	_buttons_root.offset_right = -18.0
	_buttons_root.offset_bottom = -14.0
	_buttons_root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_anchor_ctrl.add_child(_buttons_root)

	# Coordinates inside 362x276 cluster box (bottom-right)
	var layout_specs := {
		1: {"rect": Rect2(226, 146, 108, 108), "accent": Color(0.98, 0.78, 0.25, 0.85)},
		2: {"rect": Rect2(292, 74, 66, 66), "accent": Color(0.45, 0.90, 0.65, 0.75)},
		3: {"rect": Rect2(154, 206, 64, 64), "accent": Color(0.38, 0.82, 1.0, 0.78)},
		4: {"rect": Rect2(288, 2, 66, 66), "accent": Color(0.24, 0.72, 1.0, 0.82)},
		5: {"rect": Rect2(210, 48, 64, 64), "accent": Color(0.75, 0.85, 1.0, 0.65)},
		6: {"rect": Rect2(142, 114, 64, 64), "accent": Color(0.75, 0.85, 1.0, 0.65)},
		7: {"rect": Rect2(78, 192, 68, 68), "accent": Color(0.75, 0.85, 1.0, 0.65)},
		8: {"rect": Rect2(12, 196, 58, 58), "accent": Color(1.0, 0.42, 0.35, 0.85)},
	}
	for sid in [1, 2, 3, 4, 5, 6, 7, 8]:
		var spec: Dictionary = layout_specs[sid]
		var r: Rect2 = spec["rect"]
		var btn := Button.new()
		btn.name = "SkillCircle_%d" % sid
		btn.position = r.position
		btn.size = r.size
		btn.custom_minimum_size = r.size
		_apply_circle_button_theme(btn, spec["accent"])
		var cap_id := int(sid)
		btn.pressed.connect(func() -> void:
			_on_slot_pressed(cap_id)
		)
		_buttons_root.add_child(btn)
		_slot_buttons[sid] = btn

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
	return false


func set_slot_binding(slot_id: int, action_id: String) -> void:
	if slot_id == 1 or slot_id == 8:
		return
	_slot_bindings[slot_id] = action_id
	_refresh_slot_buttons()
	slot_binding_changed.emit(slot_id, action_id)


func get_slot_binding(slot_id: int) -> String:
	return str(_slot_bindings.get(slot_id, "empty"))


func configure_for_character(char_id: String, available_clips: PackedStringArray, is_flying: bool) -> void:
	_flight_mode = is_flying
	var avail := PackedStringArray(["attack_light"])
	if is_flying or available_clips.has("jump"):
		avail.append("jump")
	if available_clips.has("teleport"):
		avail.append("teleport")
	if available_clips.has("power_up"):
		avail.append("power_up")
	if available_clips.has("attack_heavy"):
		avail.append("attack_heavy")
	_available_actions = avail
	_jump_enabled = is_flying or available_clips.has("jump")

	# Default bindings per character (Drum: 1=Đánh, 2=Nhảy, 3=Tốc biến, 4=Chưởng Orb, 5..7=empty)
	_slot_bindings[1] = "attack_light"
	_slot_bindings[2] = "jump" if _jump_enabled else "empty"
	_slot_bindings[3] = "teleport" if avail.has("teleport") else ("attack_heavy" if avail.has("attack_heavy") else "empty")
	_slot_bindings[4] = "power_up" if avail.has("power_up") else "empty"
	_slot_bindings[5] = "attack_heavy" if (avail.has("attack_heavy") and _slot_bindings[3] != "attack_heavy") else "empty"
	_slot_bindings[6] = "empty"
	_slot_bindings[7] = "empty"
	_slot_bindings[8] = "cycle_target"
	if char_id == "drum":
		_slot_bindings[2] = "jump"
		_slot_bindings[3] = "teleport"
		_slot_bindings[4] = "power_up"
		_slot_bindings[5] = "empty"
	_rebuild_settings_rows()
	_refresh_slot_buttons()


func set_mana_and_pointer_state(mana: float, max_mana: float, pointer_kind: String) -> void:
	_current_mana = mana
	_max_mana = max_mana
	_pointer_kind = pointer_kind
	_refresh_slot_buttons()


func set_jump_available(enabled: bool, flight: bool = false) -> void:
	_jump_enabled = enabled
	_flight_mode = flight
	_refresh_slot_buttons()


func _refresh_slot_buttons() -> void:
	for sid in [1, 2, 3, 4, 5, 6, 7, 8]:
		var btn := _slot_buttons.get(sid) as Button
		if btn == null:
			continue
		if sid == 8:
			btn.visible = true
			btn.text = "🎯\nTrỏ"
			continue
		var act := str(_slot_bindings.get(sid, "empty"))
		if sid >= 5 and act == "empty":
			btn.visible = false
			continue
		if sid >= 2 and sid <= 4 and act == "empty":
			btn.visible = false
			continue
		btn.visible = true
		if sid == 1:
			if _pointer_kind == "item":
				btn.text = "1\nNhặt"
			elif _pointer_kind == "npc":
				btn.text = "1\nN.Chuyện"
			else:
				btn.text = "1\nĐánh"
			btn.disabled = false
			continue
		var lbl := str(ACTION_LABELS.get(act, act))
		if act == "jump" and _flight_mode:
			lbl = "Bay lên"
		if act == "power_up":
			btn.text = "%d\n%s\n(%d/%d)" % [sid, lbl, int(floor(_current_mana)), int(round(_max_mana))]
			btn.disabled = _current_mana < 100.0
		elif act == "jump":
			btn.text = "%d\n%s" % [sid, lbl]
			btn.disabled = not _jump_enabled
		else:
			btn.text = "%d\n%s" % [sid, lbl]
			btn.disabled = false


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
			if mb.button_index == MOUSE_BUTTON_LEFT:
				if mb.pressed:
					pad_owner._analog_mouse_down = true
					pad_owner._update_analog_from_local(mb.position)
				else:
					pad_owner._reset_analog()
				accept_event()
		elif event is InputEventMouseMotion and pad_owner._analog_mouse_down:
			pad_owner._update_analog_from_local((event as InputEventMouseMotion).position)
			accept_event()

	func _draw() -> void:
		if pad_owner == null:
			return
		var center := size * 0.5
		var base_r := minf(size.x, size.y) * 0.44
		pad_owner._analog_radius = base_r
		draw_circle(center, base_r, Color(0.06, 0.10, 0.18, 0.62))
		draw_arc(center, base_r, 0.0, TAU, 48, Color(0.76, 0.88, 1.0, 0.45), 2.5)
		draw_arc(center, base_r * 0.45, 0.0, TAU, 32, Color(0.76, 0.88, 1.0, 0.18), 1.5)
		var knob_pos: Vector2 = center + pad_owner.analog_vector * (base_r - pad_owner._knob_radius * 0.4)
		draw_circle(knob_pos, pad_owner._knob_radius, Color(0.24, 0.72, 0.98, 0.84))
		draw_arc(knob_pos, pad_owner._knob_radius, 0.0, TAU, 32, Color(0.92, 0.98, 1.0, 0.85), 2.0)
