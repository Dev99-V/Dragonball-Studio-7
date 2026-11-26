class_name OverheadBarsDraw
extends RefCounted
## Draws crisp rounded pill HP / Mana / Stamina bars matching the Owner's reference sample,
## plus the animated Target Pointer chevron above the selected monster / item / NPC.

const FLOATING_DAMAGE_FONT_SIZE := 24
const FLOATING_DAMAGE_OUTLINE_SIZE := 5
const DefaultHitImpactFrames: SpriteFrames = preload("res://assets/fx/hit_impact/hit_impact.tres")
const DEFAULT_HIT_IMPACT_MELEE_SIZE_PX := 144.0
const DEFAULT_HIT_IMPACT_HEAVY_SIZE_PX := 216.0

static var _cached_sb_track: StyleBoxFlat = null
static var _cached_sb_fill: StyleBoxFlat = null


static func draw_pill_bar(canvas: CanvasItem, rect: Rect2, ratio: float, fill_color: Color, track_color: Color) -> void:
	var r := clampf(ratio, 0.0, 1.0)
	var radius_i := int(ceilf(rect.size.y * 0.5))
	if _cached_sb_track == null:
		_cached_sb_track = StyleBoxFlat.new()
	_cached_sb_track.bg_color = track_color
	_cached_sb_track.set_corner_radius_all(radius_i)
	canvas.draw_style_box(_cached_sb_track, rect)
	if r > 0.005:
		var fill_w := minf(rect.size.x, maxf(rect.size.y, rect.size.x * r))
		if _cached_sb_fill == null:
			_cached_sb_fill = StyleBoxFlat.new()
		_cached_sb_fill.bg_color = fill_color
		_cached_sb_fill.set_corner_radius_all(radius_i)
		canvas.draw_style_box(_cached_sb_fill, Rect2(rect.position, Vector2(fill_w, rect.size.y)))


static func draw_vertical_pill_bar(canvas: CanvasItem, rect: Rect2, ratio: float, fill_color: Color, track_color: Color) -> void:
	var r := clampf(ratio, 0.0, 1.0)
	var radius_i := int(ceilf(rect.size.x * 0.5))
	if _cached_sb_track == null:
		_cached_sb_track = StyleBoxFlat.new()
	_cached_sb_track.bg_color = track_color
	_cached_sb_track.set_corner_radius_all(radius_i)
	canvas.draw_style_box(_cached_sb_track, rect)
	if r > 0.005:
		var fill_h := minf(rect.size.y, maxf(rect.size.x * 0.7, rect.size.y * r))
		var fill_y := rect.position.y + (rect.size.y - fill_h)
		if _cached_sb_fill == null:
			_cached_sb_fill = StyleBoxFlat.new()
		_cached_sb_fill.bg_color = fill_color
		_cached_sb_fill.set_corner_radius_all(radius_i)
		canvas.draw_style_box(_cached_sb_fill, Rect2(rect.position.x, fill_y, rect.size.x, fill_h))


const KI_BAR_WIDTH := 5.4 # 60% of previous 9.0px thickness (-40% per Owner v10.6 HUD spec)
const STATE_ICON_RADIUS := 7.5 # Exact radius shared by Peace/Combat & Shield-Break badges


static func draw_player_bars(canvas: CanvasItem, center_x: float, top_y: float, hp: float, max_hp: float, mana: float, max_mana: float, display_name: String = "", is_remote: bool = false, armor: float = -1.0, max_armor: float = 100.0, armor_broken: bool = false, ki: float = -1.0, max_ki: float = 50.0, ki_exhausted: bool = false, show_shield_break_icon: bool = false, shield_break_alpha: float = 1.0, is_hostile_enemy: bool = false, is_pk_flagged: bool = false) -> void:
	var bar_w := 124.0
	var hp_h := 16.0
	var mana_h := 9.0
	var gap := 4.0
	var has_armor := armor >= 0.0
	var armor_h := 8.0
	var armor_gap := 3.0
	var x0 := center_x - bar_w * 0.5
	var mana_bottom_y := top_y - (armor_h + armor_gap if has_armor else 0.0)
	var hp_rect := Rect2(x0, mana_bottom_y - hp_h - mana_h - gap, bar_w, hp_h)
	var mana_rect := Rect2(x0, mana_bottom_y - mana_h, bar_w, mana_h)
	var white_track := Color(0.98, 0.99, 1.0, 0.96)
	# Hostile PK remote players render with crimson enemy HP bar identical to monsters/bosses (Owner 2026-11-26)!
	var hp_col := Color(0.92, 0.15, 0.15, 1.0) if (is_remote and is_hostile_enemy) else (Color(0.12, 0.84, 0.98, 1.0) if is_remote else Color(0.0, 0.93, 0.04, 1.0))
	draw_pill_bar(canvas, hp_rect, hp / maxf(1.0, max_hp), hp_col, white_track)
	draw_pill_bar(canvas, mana_rect, mana / maxf(1.0, max_mana), Color(0.0, 0.68, 0.96, 1.0), white_track)
	if has_armor:
		var armor_rect := Rect2(x0, top_y - armor_h, bar_w, armor_h)
		var armor_fill := Color(0.98, 0.72, 0.18, 1.0) if armor_broken else Color(0.95, 0.96, 0.99, 0.98)
		var armor_track := Color(0.18, 0.22, 0.30, 0.85)
		draw_pill_bar(canvas, armor_rect, armor / maxf(1.0, max_armor), armor_fill, armor_track)
	if ki >= 0.0:
		# Orange vertical Flight KI bar directly to the right of HP / Mana / Armor bars (60% thickness = 5.4px)
		var ki_w := KI_BAR_WIDTH
		var ki_gap := 5.0
		var ki_top := hp_rect.position.y
		var ki_h := maxf(24.0, top_y - ki_top)
		var ki_rect := Rect2(x0 + bar_w + ki_gap, ki_top, ki_w, ki_h)
		var ki_fill := Color(0.95, 0.32, 0.08, 0.92) if ki_exhausted else Color(1.0, 0.56, 0.06, 1.0)
		var ki_track := Color(0.16, 0.20, 0.28, 0.88)
		draw_vertical_pill_bar(canvas, ki_rect, ki / maxf(1.0, max_ki), ki_fill, ki_track)
		canvas.draw_rect(ki_rect.grow(0.5), Color(0.04, 0.06, 0.10, 0.75), false, 1.0)
	if (is_remote and is_hostile_enemy) or is_pk_flagged:
		# Crimson crossed-swords PK/hostile indicator right below bar (identical to hostile enemy badge!)
		draw_monster_state_icon(canvas, Vector2(center_x, top_y + 10.0), true)
	if show_shield_break_icon and shield_break_alpha > 0.02:
		draw_shield_break_icon(canvas, Vector2(center_x, hp_rect.position.y - STATE_ICON_RADIUS - 3.0), shield_break_alpha)
	var font := ThemeDB.fallback_font
	if font != null:
		var txt := "%d/%d" % [int(ceilf(maxf(0.0, hp))), int(round(max_hp))]
		var hp_txt_y := hp_rect.position.y - (STATE_ICON_RADIUS * 2.0 + 7.0 if show_shield_break_icon else 4.0)
		canvas.draw_string(font, Vector2(x0 - 16.0, hp_txt_y), txt, HORIZONTAL_ALIGNMENT_CENTER, bar_w + 32.0, 15, Color(0.98, 1.0, 0.98, 0.98))
		if not display_name.is_empty():
			var name_pos := Vector2(x0 - 36.0, hp_txt_y - 20.0)
			var name_col := Color(1.0, 0.24, 0.24, 1.0) if ((is_remote and is_hostile_enemy) or is_pk_flagged) else (Color(0.42, 0.96, 1.0, 1.0) if is_remote else Color(1.0, 0.92, 0.36, 1.0))
			canvas.draw_string_outline(font, name_pos, display_name, HORIZONTAL_ALIGNMENT_CENTER, bar_w + 72.0, 18, 4, Color(0.03, 0.06, 0.12, 0.96))
			canvas.draw_string(font, name_pos, display_name, HORIZONTAL_ALIGNMENT_CENTER, bar_w + 72.0, 18, name_col)


static func draw_enemy_bars(canvas: CanvasItem, center_x: float, top_y: float, hp: float, max_hp: float, stamina: float, max_stamina: float, stunned: bool = false, label_txt: String = "", is_boss: bool = false, combat_state: String = "peace", show_shield_break_icon: bool = false, shield_break_alpha: float = 1.0) -> void:
	var bar_w := 152.0 if is_boss else 116.0
	var hp_h := 17.0 if is_boss else 14.0
	var stam_h := 9.0 if is_boss else 8.0
	var gap := 3.0
	var x0 := center_x - bar_w * 0.5
	var hp_rect := Rect2(x0, top_y - hp_h - stam_h - gap, bar_w, hp_h)
	var stam_rect := Rect2(x0, top_y - stam_h, bar_w, stam_h)
	var hp_col := Color(0.95, 0.08, 0.08, 1.0) if is_boss else Color(0.92, 0.15, 0.15, 1.0)
	draw_pill_bar(canvas, hp_rect, hp / maxf(1.0, max_hp), hp_col, Color(0.98, 0.99, 1.0, 0.95))
	var stam_fill := Color(0.98, 0.72, 0.18, 1.0) if stunned else Color(0.93, 0.94, 0.97, 0.96)
	var stam_track := Color(0.18, 0.22, 0.30, 0.85)
	draw_pill_bar(canvas, stam_rect, stamina / maxf(1.0, max_stamina), stam_fill, stam_track)
	if show_shield_break_icon and shield_break_alpha > 0.02:
		draw_shield_break_icon(canvas, Vector2(center_x, hp_rect.position.y - STATE_ICON_RADIUS - 3.0), shield_break_alpha)
	# Peace vs Combat state emblem directly below monster Armor/Stamina bar (Owner v6)!
	var is_combat := is_boss or (combat_state == "combat")
	var icon_c := Vector2(center_x, top_y + 10.0)
	draw_monster_state_icon(canvas, icon_c, is_combat)
	var font := ThemeDB.fallback_font
	if font != null:
		var lbl_offset_y := (STATE_ICON_RADIUS * 2.0 + 8.0) if show_shield_break_icon else 6.0
		if is_boss:
			var boss_name := label_txt if not label_txt.is_empty() else "Drum"
			if stunned:
				boss_name += " [STUN]"
			var name_pos := Vector2(x0 - 24.0, hp_rect.position.y - lbl_offset_y)
			canvas.draw_string_outline(font, name_pos, boss_name, HORIZONTAL_ALIGNMENT_CENTER, bar_w + 48.0, 18, 4, Color(0.05, 0.02, 0.03, 0.96))
			canvas.draw_string(font, name_pos, boss_name, HORIZONTAL_ALIGNMENT_CENTER, bar_w + 48.0, 18, Color(1.0, 0.14, 0.14, 1.0))
		else:
			var top_str := "%s %d" % [label_txt, int(ceilf(maxf(0.0, hp)))] if not label_txt.is_empty() else "%d/%d" % [int(ceilf(maxf(0.0, hp))), int(round(max_hp))]
			if stunned:
				top_str += " [STUN]"
			canvas.draw_string(font, Vector2(x0 - 24.0, hp_rect.position.y - (lbl_offset_y - 2.0)), top_str, HORIZONTAL_ALIGNMENT_CENTER, bar_w + 48.0, 14, Color(1.0, 0.94, 0.82, 0.98))


static func draw_shield_break_icon(canvas: CanvasItem, center: Vector2, alpha_mul: float = 1.0) -> void:
	## Cracked-shield emblem directly above HP bar, exact same size (r=7.5) as Peace/Combat state icon, flashes then fades!
	var a := clampf(alpha_mul, 0.0, 1.0)
	if a <= 0.01:
		return
	var r := STATE_ICON_RADIUS
	canvas.draw_circle(center, r + 1.4, Color(0.06, 0.07, 0.11, 0.90 * a))
	var ring_col := Color(1.0, 0.62, 0.16, 0.98 * a)
	var shield_col := Color(0.98, 0.84, 0.44, 0.96 * a)
	var crack_col := Color(0.18, 0.05, 0.02, 0.98 * a)
	canvas.draw_arc(center, r, 0.0, TAU, 20, ring_col, 1.8, true)
	# Left & right split halves of a shield silhouette
	var left_half := PackedVector2Array([
		center + Vector2(-4.4, -3.8),
		center + Vector2(-0.6, -4.4),
		center + Vector2(-1.4, -0.4),
		center + Vector2(-0.4, 2.2),
		center + Vector2(-1.0, 4.6),
		center + Vector2(-4.2, 1.4),
	])
	var right_half := PackedVector2Array([
		center + Vector2(0.8, -4.4),
		center + Vector2(4.4, -3.8),
		center + Vector2(4.2, 1.4),
		center + Vector2(1.0, 4.6),
		center + Vector2(1.6, 2.0),
		center + Vector2(0.5, -0.6),
	])
	canvas.draw_colored_polygon(left_half, shield_col)
	canvas.draw_colored_polygon(right_half, shield_col)
	# Jagged fracture crack down the middle
	var crack := PackedVector2Array([
		center + Vector2(0.2, -4.6),
		center + Vector2(-0.9, -0.8),
		center + Vector2(0.8, 1.4),
		center + Vector2(-0.2, 4.8),
	])
	canvas.draw_polyline(crack, crack_col, 1.7, true)


static func draw_monster_state_icon(canvas: CanvasItem, center: Vector2, in_combat: bool) -> void:
	## Crisp badge below Monster Armor bar:
	## - Peace  (in_combat=false): calm emerald-green emblem with leaf/peace crest
	## - Combat (in_combat=true) : blazing crimson emblem with crossed swords
	var r := STATE_ICON_RADIUS
	var bg := Color(0.06, 0.08, 0.12, 0.88)
	canvas.draw_circle(center, r + 1.4, bg)
	if in_combat:
		var red := Color(1.0, 0.22, 0.22, 0.98)
		var blade := Color(1.0, 0.92, 0.82, 0.98)
		canvas.draw_arc(center, r, 0.0, TAU, 20, red, 1.8, true)
		# Crossed swords silhouette inside badge
		canvas.draw_line(center + Vector2(-4.2, -4.2), center + Vector2(4.2, 4.2), blade, 1.8, true)
		canvas.draw_line(center + Vector2(4.2, -4.2), center + Vector2(-4.2, 4.2), blade, 1.8, true)
		canvas.draw_line(center + Vector2(-4.5, 2.2), center + Vector2(-2.0, 4.6), red, 1.6, true)
		canvas.draw_line(center + Vector2(4.5, 2.2), center + Vector2(2.0, 4.6), red, 1.6, true)
	else:
		var green := Color(0.20, 0.92, 0.56, 0.98)
		canvas.draw_arc(center, r, 0.0, TAU, 20, green, 1.8, true)
		# Calm peace leaf / shield dot inside badge
		var leaf := PackedVector2Array([
			center + Vector2(0.0, -4.5),
			center + Vector2(3.8, -0.5),
			center + Vector2(0.0, 4.5),
			center + Vector2(-3.8, -0.5),
		])
		canvas.draw_colored_polygon(leaf, green)


static func _draw_brush_stroke(canvas: CanvasItem, p0: Vector2, p1: Vector2, prog: float, base_w: float, col: Color, outline_col: Color) -> void:
	var t := clampf(prog, 0.0, 1.0)
	if t <= 0.01:
		return
	var steps := 10
	var dir := p1 - p0
	var len_px := dir.length()
	if len_px <= 0.5:
		return
	var perp := Vector2(-dir.y, dir.x) / len_px
	var cur_steps := maxi(1, int(ceilf(float(steps) * t)))
	for i in range(cur_steps):
		var s0 := float(i) / float(steps)
		var s1 := minf(t, float(i + 1) / float(steps))
		if s1 <= s0:
			continue
		var a := p0.lerp(p1, s0) + perp * (sin(s0 * PI) * 1.4)
		var b := p0.lerp(p1, s1) + perp * (sin(s1 * PI) * 1.4)
		# Calligraphic taper: thicker at head/belly, sharp brush tip at tail
		var w := base_w * (1.18 - 0.52 * s0)
		canvas.draw_line(a, b, outline_col, w + 3.2, true)
	for i in range(cur_steps):
		var s0 := float(i) / float(steps)
		var s1 := minf(t, float(i + 1) / float(steps))
		if s1 <= s0:
			continue
		var a := p0.lerp(p1, s0) + perp * (sin(s0 * PI) * 1.4)
		var b := p0.lerp(p1, s1) + perp * (sin(s1 * PI) * 1.4)
		var w := base_w * (1.18 - 0.52 * s0)
		canvas.draw_line(a, b, col, w, true)


static func draw_calligraphic_red_x(canvas: CanvasItem, center_pos: Vector2, anim_progress: float, bob_phase_s: float, scale_boost: float = 1.0, alpha_mul: float = 1.0) -> void:
	var amul := clampf(alpha_mul, 0.0, 1.0)
	if amul <= 0.01:
		return
	var p := clampf(anim_progress, 0.0, 1.0)
	var bob := sin(bob_phase_s * 6.0) * 3.0 if p >= 0.95 else 0.0
	var c := center_pos + Vector2(0.0, bob)
	var r := 16.0 * scale_boost
	var stroke1_prog := clampf(p / 0.48, 0.0, 1.0)
	var stroke2_prog := clampf((p - 0.48) / 0.48, 0.0, 1.0)
	var ink_col := Color(0.96, 0.10, 0.12, 0.98 * amul)
	var outline_col := Color(0.14, 0.02, 0.03, 0.95 * amul)
	_draw_brush_stroke(canvas, c + Vector2(-r, -r), c + Vector2(r, r), stroke1_prog, 5.2 * scale_boost, ink_col, outline_col)
	_draw_brush_stroke(canvas, c + Vector2(r, -r), c + Vector2(-r, r), stroke2_prog, 5.2 * scale_boost, ink_col, outline_col)


static func draw_target_pointer(canvas: CanvasItem, target_pos: Vector2, bob_phase_s: float, kind: String = "enemy") -> void:
	var bob := sin(bob_phase_s * 6.0) * 4.0
	var tip := target_pos + Vector2(0.0, bob)
	var col := Color(1.0, 0.26, 0.26, 0.98)
	if kind == "item":
		col = Color(1.0, 0.84, 0.18, 0.98)
	elif kind == "npc":
		col = Color(0.24, 0.92, 0.98, 0.98)
	var pts := PackedVector2Array([
		tip,
		tip + Vector2(-12.0, -16.0),
		tip + Vector2(12.0, -16.0),
	])
	canvas.draw_colored_polygon(pts, col)
	canvas.draw_polyline(PackedVector2Array([pts[0], pts[1], pts[2], pts[0]]), Color(0.04, 0.06, 0.10, 0.95), 2.0)


static func draw_selection_ring(canvas: CanvasItem, body_rect: Rect2, progress: float, kind: String = "enemy") -> void:
	var p := clampf(progress, 0.0, 1.0)
	var col := Color(1.0, 0.30, 0.30, p * 0.95)
	if kind == "item":
		col = Color(1.0, 0.86, 0.20, p * 0.95)
	elif kind == "npc":
		col = Color(0.28, 0.92, 1.0, p * 0.95)
	var grow_px := (1.0 - p) * 14.0
	var r := body_rect.grow(grow_px)
	canvas.draw_rect(r, col, false, 2.5)


static func draw_hit_impact(canvas: CanvasItem, pos: Vector2, progress: float, kind: String = "melee", impact_dir: Vector2 = Vector2.RIGHT, custom_frames: SpriteFrames = null) -> void:
	var p := clampf(progress, 0.0, 1.0)
	var inv := 1.0 - p

	if kind == "melee" or kind == "heavy":
		# Canonical default melee/heavy hit impact sprite FX (Owner sample `image copy 2.png` + 6 dissipation frames).
		# Applies to all heroes, monsters, and bosses unless a character explicitly supplies `custom_frames`.
		var frames: SpriteFrames = custom_frames if (custom_frames != null and custom_frames.has_animation(&"hit") and custom_frames.get_frame_count(&"hit") > 0) else DefaultHitImpactFrames
		if frames != null and frames.has_animation(&"hit"):
			var fc := frames.get_frame_count(&"hit")
			if fc > 0:
				var fi := clampi(int(floor(p * float(fc))), 0, fc - 1)
				var tex := frames.get_frame_texture(&"hit", fi)
				if tex != null:
					var draw_sz := DEFAULT_HIT_IMPACT_HEAVY_SIZE_PX if kind == "heavy" else DEFAULT_HIT_IMPACT_MELEE_SIZE_PX
					var half_sz := draw_sz * 0.5
					var flip_x := -1.0 if impact_dir.x < -0.05 else 1.0
					canvas.draw_set_transform(pos, 0.0, Vector2(flip_x, 1.0))
					canvas.draw_texture_rect(tex, Rect2(-half_sz, -half_sz, draw_sz, draw_sz), false, Color.WHITE)
					canvas.draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
					return
		return

	var outer_col := Color(1.0, 0.78, 0.20, inv * 0.95)
	var core_col := Color(1.0, 0.98, 0.86, inv)
	var max_r := 28.0
	if kind == "skill":
		outer_col = Color(0.28, 0.86, 1.0, inv * 0.95)
		max_r = 44.0
	elif kind == "stun":
		outer_col = Color(1.0, 0.62, 0.12, inv)
		max_r = 48.0
	elif kind == "clash":
		outer_col = Color(1.0, 0.90, 0.36, inv)
		max_r = 46.0
	elif kind == "player_hit":
		outer_col = Color(1.0, 0.24, 0.24, inv * 0.95)
		max_r = 32.0

	var radius := lerpf(8.0, max_r, p)
	# Reduce hit-impact glare contrast by an additional 40% (0.64 * 0.60 = 0.384 on flash overlay glare).
	var lum := 0.384
	outer_col = Color(outer_col.r * lum, outer_col.g * lum, outer_col.b * lum, outer_col.a * lum)
	core_col = Color(core_col.r * lum, core_col.g * lum, core_col.b * lum, core_col.a * lum)
	# Crisp pixel shockbox + diagonal star sparks (zero blur/ellipse)
	var box := Rect2(pos.x - radius, pos.y - radius, radius * 2.0, radius * 2.0)
	canvas.draw_rect(box, outer_col, false, 2.5)
	var core_sz := maxf(4.0, (1.0 - p * 0.7) * 14.0)
	canvas.draw_rect(Rect2(pos.x - core_sz * 0.5, pos.y - core_sz * 0.5, core_sz, core_sz), core_col, true)
	for dir_vec in [Vector2(1, 0), Vector2(-1, 0), Vector2(0, 1), Vector2(0, -1), Vector2(0.75, 0.75), Vector2(-0.75, 0.75), Vector2(0.75, -0.75), Vector2(-0.75, -0.75)]:
		var p0 := pos + (dir_vec as Vector2) * (radius * 0.45)
		var p1 := pos + (dir_vec as Vector2) * (radius * 1.25)
		canvas.draw_line(p0, p1, outer_col, 2.5)


static func draw_floating_damage(canvas: CanvasItem, pos: Vector2, text_str: String, progress: float, color: Color) -> void:
	var font := ThemeDB.fallback_font
	if font == null or text_str.is_empty():
		return
	var alpha := clampf(1.0 - maxf(0.0, progress - 0.35) / 0.65, 0.0, 1.0)
	var col := Color(color.r, color.g, color.b, alpha)
	var outline := Color(0.03, 0.04, 0.08, alpha * 0.96)
	var draw_pos := Vector2(pos.x - 72.0, pos.y)
	canvas.draw_string_outline(font, draw_pos, text_str, HORIZONTAL_ALIGNMENT_CENTER, 144.0, FLOATING_DAMAGE_FONT_SIZE, FLOATING_DAMAGE_OUTLINE_SIZE, outline)
	canvas.draw_string(font, draw_pos, text_str, HORIZONTAL_ALIGNMENT_CENTER, 144.0, FLOATING_DAMAGE_FONT_SIZE, col)


static func draw_dash_wind_streaks(canvas: CanvasItem, foot_pos: Vector2, body_h_px: float, move_dir_x: int, dash_time_s: float) -> void:
	## Crisp pixel-art wind slipstream streaks in FRONT of and TRAILING BEHIND Goku during `combat_move` dash (NO aura!).
	## Gives lively high-speed air-cut motion so dashing never feels like a frozen static image.
	if move_dir_x == 0:
		return
	var dir_f := 1.0 if move_dir_x > 0 else -1.0
	var cy := foot_pos.y - body_h_px * 0.50
	var streak_col_hi := Color(0.96, 0.99, 1.0, 0.88)
	var streak_col_mid := Color(0.80, 0.93, 1.0, 0.65)
	var streak_col_soft := Color(0.72, 0.88, 0.98, 0.42)

	# 4 trailing wind lines behind the dash direction (continuous 60Hz phase scroll!)
	for i in range(4):
		var phase := fposmod(dash_time_s * (7.2 + float(i) * 1.4) + float(i) * 0.31, 1.0)
		var y_off := (-0.36 + float(i) * 0.24) * body_h_px
		var tail_dist := 18.0 + phase * 62.0
		var seg_len := lerpf(44.0, 14.0, phase)
		var x_start := foot_pos.x - dir_f * tail_dist
		var x_end := x_start - dir_f * seg_len
		var rx := minf(x_start, x_end)
		var rw := absf(x_end - x_start)
		var alpha := (1.0 - phase) * 0.90
		var col := streak_col_hi if (i % 2 == 0) else streak_col_mid
		col.a *= alpha
		var thickness := 3.0 if (i % 2 == 0) else 2.0
		canvas.draw_rect(Rect2(roundf(rx), roundf(cy + y_off), roundf(rw), thickness), col, true)

	# 3 leading air-cut streaks in FRONT of the dash direction (cutting through the air ahead!)
	for j in range(3):
		var phase_f := fposmod(dash_time_s * (8.5 + float(j) * 1.6) + float(j) * 0.37, 1.0)
		var y_off_f := (-0.28 + float(j) * 0.26) * body_h_px
		var lead_dist := 24.0 + (1.0 - phase_f) * 36.0
		var seg_len_f := lerpf(28.0, 10.0, phase_f)
		var x_front := foot_pos.x + dir_f * lead_dist
		var x_back := x_front - dir_f * seg_len_f
		var rx_f := minf(x_front, x_back)
		var rw_f := absf(x_front - x_back)
		var col_f := streak_col_mid if j == 1 else streak_col_soft
		col_f.a *= maxf(0.15, 1.0 - absf(phase_f - 0.5) * 1.4)
		canvas.draw_rect(Rect2(roundf(rx_f), roundf(cy + y_off_f), roundf(rw_f), 2.0), col_f, true)


static func draw_stun_stars_ring(canvas: CanvasItem, head_top_pos: Vector2, time_s: float) -> void:
	## Golden rotating stun ring + 3 pixel stars hovering above any stunned Hero, Monster, or Boss (skills.md & Owner #4)!
	var c := head_top_pos + Vector2(0.0, -14.0)
	var rx := 22.0
	var ry := 7.0
	canvas.draw_arc(c, rx * 0.86, 0.0, TAU, 24, Color(1.0, 0.86, 0.22, 0.45), 1.5, false)
	for i in range(3):
		var ang := time_s * 5.8 + float(i) * (TAU / 3.0)
		var sx := c.x + cos(ang) * rx
		var sy := c.y + sin(ang) * ry
		var depth_sc := lerpf(0.72, 1.15, (sin(ang) + 1.0) * 0.5)
		var sz := roundf(5.0 * depth_sc)
		canvas.draw_rect(Rect2(roundf(sx - sz * 0.5) - 1.0, roundf(sy - sz * 0.5) - 1.0, sz + 2.0, sz + 2.0), Color(0.10, 0.06, 0.02, 0.92), true)
		canvas.draw_rect(Rect2(roundf(sx - sz * 0.5), roundf(sy - sz * 0.5), sz, sz), Color(1.0, 0.90, 0.22, 1.0), true)
		canvas.draw_rect(Rect2(roundf(sx - 1.0), roundf(sy - sz * 0.85), 2.0, sz * 1.7), Color(1.0, 0.98, 0.70, 0.95), true)
		canvas.draw_rect(Rect2(roundf(sx - sz * 0.85), roundf(sy - 1.0), sz * 1.7, 2.0), Color(1.0, 0.98, 0.70, 0.95), true)


static func draw_kentai_green_burn_fx(canvas: CanvasItem, body_rect: Rect2, time_s: float) -> void:
	## Subtle pixel-art emerald-green flame wisps burning lightly on a target afflicted by Kentaima's 5s Kentai mark!
	if body_rect.size.x < 4.0 or body_rect.size.y < 4.0:
		return
	var col_outer := Color(0.10, 0.92, 0.46, 0.86)
	var col_mid := Color(0.42, 1.0, 0.68, 0.92)
	var col_core := Color(0.88, 1.0, 0.94, 0.96)
	# 5 lightweight rising pixel flame wisps distributed subtly across target silhouette
	for i in range(5):
		var phase := fposmod(time_s * (2.6 + float(i) * 0.35) + float(i) * 0.29, 1.0)
		var x_frac := 0.22 + float(i) * 0.14
		var sway := sin(time_s * 9.0 + float(i) * 1.7) * 2.5
		var fx := roundf(body_rect.position.x + body_rect.size.x * x_frac + sway)
		var fy := roundf(body_rect.end.y - body_rect.size.y * (0.18 + phase * 0.68))
		var fade := 1.0 - maxf(0.0, (phase - 0.55) / 0.45)
		if fade <= 0.05:
			continue
		var s := 4.0 if phase < 0.55 else 3.0
		var c1 := Color(col_outer.r, col_outer.g, col_outer.b, col_outer.a * fade)
		var c2 := Color(col_mid.r, col_mid.g, col_mid.b, col_mid.a * fade)
		var c3 := Color(col_core.r, col_core.g, col_core.b, col_core.a * fade)
		# Crisp pixel teardrop flame (3 stacked pixel blocks)
		canvas.draw_rect(Rect2(fx - s * 0.5, fy, s, s), c1, true)
		canvas.draw_rect(Rect2(fx - (s - 1.0) * 0.5, fy - s + 1.0, s - 1.0, s), c2, true)
		canvas.draw_rect(Rect2(fx - 1.0, fy - s - 2.0, 2.0, 2.0), c3, true)


static func draw_tapion_mark_badges(canvas: CanvasItem, center_x: float, badge_y: float, kentai_timer_s: float, an_nguc_stacks: int, time_s: float) -> void:
	## Overhead badges for Tapion's combo system:
	## - Kentai (5s): emerald-green flame badge + radial remaining-time arc.
	## - Ấn ngục (1..5 stacks): crimson-violet seal emblem with crisp stack count; at 5 stacks pulses gold-magenta "SUY YẾU"!
	var has_kentai := kentai_timer_s > 0.0
	var has_seal := an_nguc_stacks > 0
	if not has_kentai and not has_seal:
		return
	var r := 9.0
	var font := ThemeDB.fallback_font
	var k_pos := Vector2(center_x - 14.0, badge_y) if (has_kentai and has_seal) else Vector2(center_x, badge_y)
	var s_pos := Vector2(center_x + 14.0, badge_y) if (has_kentai and has_seal) else Vector2(center_x, badge_y)

	if has_kentai:
		var frac := clampf(kentai_timer_s / 5.0, 0.0, 1.0)
		canvas.draw_circle(k_pos, r + 1.6, Color(0.04, 0.09, 0.08, 0.92))
		canvas.draw_arc(k_pos, r, 0.0, TAU, 20, Color(0.10, 0.34, 0.24, 0.72), 2.0, true)
		canvas.draw_arc(k_pos, r, -PI * 0.5, -PI * 0.5 + TAU * frac, 20, Color(0.18, 1.0, 0.58, 0.98), 2.2, true)
		# Emerald flame glyph inside badge
		var flame_pts := PackedVector2Array([
			k_pos + Vector2(0.0, -5.8),
			k_pos + Vector2(3.8, -0.4),
			k_pos + Vector2(2.6, 4.4),
			k_pos + Vector2(0.0, 5.4),
			k_pos + Vector2(-2.6, 4.4),
			k_pos + Vector2(-3.8, -0.4),
		])
		canvas.draw_colored_polygon(flame_pts, Color(0.18, 0.96, 0.54, 0.98))
		var inner_pts := PackedVector2Array([
			k_pos + Vector2(0.0, -2.4),
			k_pos + Vector2(1.8, 1.2),
			k_pos + Vector2(0.0, 3.6),
			k_pos + Vector2(-1.8, 1.2),
		])
		canvas.draw_colored_polygon(inner_pts, Color(0.88, 1.0, 0.94, 0.98))

	if has_seal:
		var weakened := an_nguc_stacks >= 5
		var pulse := 0.5 + 0.5 * sin(time_s * 10.0)
		var outer_r := r + (1.8 if weakened else 1.2)
		canvas.draw_circle(s_pos, outer_r + 1.4, Color(0.10, 0.03, 0.14, 0.94))
		var ring_c := Color(1.0, lerpf(0.28, 0.86, pulse), 0.16, 1.0) if weakened else Color(0.86, 0.28, 1.0, 0.98)
		var fill_c := Color(0.46, 0.08, 0.22, 0.96) if weakened else Color(0.24, 0.07, 0.34, 0.95)
		canvas.draw_circle(s_pos, r - 0.6, fill_c)
		canvas.draw_arc(s_pos, r, 0.0, TAU, 24, ring_c, 2.4 if weakened else 1.8, true)
		if weakened:
			canvas.draw_arc(s_pos, r + 3.0, 0.0, TAU, 24, Color(1.0, 0.88, 0.24, 0.55 + 0.40 * pulse), 1.4, true)
		if font != null:
			var stk_txt := "%d" % mini(5, an_nguc_stacks)
			var txt_col := Color(1.0, 0.95, 0.42, 1.0) if weakened else Color(1.0, 0.86, 1.0, 1.0)
			canvas.draw_string_outline(font, s_pos + Vector2(-8.0, 4.5), stk_txt, HORIZONTAL_ALIGNMENT_CENTER, 16.0, 13, 3, Color(0.04, 0.02, 0.06, 0.98))
			canvas.draw_string(font, s_pos + Vector2(-8.0, 4.5), stk_txt, HORIZONTAL_ALIGNMENT_CENTER, 16.0, 13, txt_col)
			if weakened:
				var wpos := Vector2(s_pos.x - 42.0, s_pos.y - r - 6.0)
				canvas.draw_string_outline(font, wpos, "SUY YẾU", HORIZONTAL_ALIGNMENT_CENTER, 84.0, 11, 3, Color(0.08, 0.01, 0.04, 0.98))
				canvas.draw_string(font, wpos, "SUY YẾU", HORIZONTAL_ALIGNMENT_CENTER, 84.0, 11, Color(1.0, 0.84, 0.24, 1.0))
