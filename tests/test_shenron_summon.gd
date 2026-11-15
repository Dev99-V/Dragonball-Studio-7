extends SceneTree
const Ritual := preload("res://scenes/ShenronSummon2D.gd")
func fail(message: String) -> void:
	printerr("[FAIL] " + message)
	quit(1)
func _init() -> void:
	call_deferred("run_test")
func run_test() -> void:
	var ritual := Ritual.new()
	ritual.manual_clock = true
	root.add_child(ritual)
	await process_frame
	if not ritual.start_from(Vector2(560, 650)):
		fail("Ritual start failed")
		return
	if ritual.start_from(Vector2.ZERO):
		fail("Duplicate call must not restart an active ritual")
		return
	for index in range(7):
		var before := ritual.sample_state(float(index * 18) - 1.0)
		var launched := ritual.sample_state(float(index * 18))
		if before["balls"][index]["visible"] or not launched["balls"][index]["visible"]:
			fail("Wrong numeric launch order at item " + str(index + 1))
			return
	var gathered := ritual.sample_state(162.0)
	for item in ritual.config["items"]:
		var index := int(item["number"]) - 1
		var off: Array = item["formation_offset_px"]
		var expected := Vector2(960.0 + float(off[0]), 540.0 + float(off[1]))
		if gathered["balls"][index]["position"].distance_to(expected) > 0.01:
			fail("Gather layout drift")
			return
	if ritual.sample_state(227.0)["ground_alpha"] != 0.0 or ritual.sample_state(300.0)["dragon_alpha"] != 0.0:
		fail("Ground/dragon appeared too early")
		return
	for at_tick in [230, 250]:
		if ritual.sample_state(float(at_tick))["flash_alpha"] != 1.0 or ritual.sample_state(float(at_tick))["ground_alpha"] != 0.0:
			fail("Flash must be fully white before ground appears")
			return
	for at_tick in [240, 258, 275]:
		if ritual.sample_state(float(at_tick))["flash_alpha"] != 0.0 or ritual.sample_state(float(at_tick))["ground_alpha"] != 0.0:
			fail("Two flashes need complete off intervals")
			return
	for at_tick in range(300, 600):
		if ritual.sample_state(float(at_tick))["glow_alpha"] < 0.78:
			fail("Ground aura must remain luminous while dragon is present")
			return
	ritual.seek_tick(330.0)
	if ritual.dissolve_material.get_shader_parameter("progress") != 0.5 or ritual.dragon.modulate.a != 1.0:
		fail("Reveal must use pixel threshold at full body alpha, not global fade")
		return
	if ritual.dissolve_material.get_shader_parameter("canvas_anchor") != Vector2(192.0, 240.0) or ritual.dissolve_material.get_shader_parameter("mask_size") != Vector2(96.0, 68.0) or ritual.dissolve_material.get_shader_parameter("cell_size") != 4.0:
		fail("Dissolve shader anchor/mask/cell contract parameters mismatch")
		return
	var partial_position := ritual.dragon.position
	ritual.seek_tick(360.0)
	if ritual.dissolve_material.get_shader_parameter("progress") != 1.0 or partial_position != ritual.dragon.position:
		fail("Dissolve must fill in place and finish fully visible")
		return
	var ready := ritual.sample_state(360.0)
	var ground: Rect2 = ready["ground_rect"]
	if ground.size.x != 144.0 or absf(ground.end.y - 840.0) > 0.01 or ritual.dragon.position.x != 960.0 or not ritual.dragon.visible:
		fail("Ground/dragon placement mismatch")
		return
	if ritual.dragon.scale != Vector2(2.76, 2.76) or ritual.dragon_sprite.texture_filter != CanvasItem.TEXTURE_FILTER_NEAREST:
		fail("Dragon scale/filter drift")
		return
	ritual.seek_tick(10000.0)
	if not ritual.active or not ritual.dragon.visible:
		fail("Summon must persist until dismissed")
		return
	ritual.dismiss()
	if ritual.active or ritual.dragon.visible or not ritual.start_from(Vector2(800, 600)):
		fail("Dismiss/replay failed")
		return
	var trace: Array = []
	ritual.origin = Vector2(560, 650)
	for at_tick in [0,18,27,54,108,162,210,219,228,230,240,246,250,258,275,276,288,300,330,360,408,10000]:
		var sample := ritual.sample_state(float(at_tick))
		var trace_balls: Array = []
		for ball in sample["balls"]:
			var pos: Vector2 = ball["position"]
			trace_balls.append({"number":ball["number"],"visible":ball["visible"],"alpha":ball["alpha"],"position":[pos.x,pos.y]})
		var rect: Rect2 = sample["ground_rect"]
		var dragon_pos: Vector2 = sample["dragon_position"]
		trace.append({"reveal_top":sample["reveal_top"],"flash_alpha":sample["flash_alpha"],"tick":at_tick,"phase":sample["phase"],"balls":trace_balls,"ground_rect":[rect.position.x,rect.position.y,rect.size.x,rect.size.y],"ground_alpha":sample["ground_alpha"],"glow_alpha":sample["glow_alpha"],"dragon_position":[dragon_pos.x,dragon_pos.y],"dragon_alpha":sample["dragon_alpha"],"dragon_frame":sample["dragon_frame"]})
	print("SHENRON_SUMMON_TRACE=" + JSON.stringify(trace))
	ritual.free()
	print("[OK] Summon: numeric1..7 flights, source layout, ground144px@840, Shenron2.76@center, persist/dismiss/replay")
	quit(0)
