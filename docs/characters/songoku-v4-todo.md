# Kế Hoạch Chia Nhỏ Task & Ngưỡng Kiểm Định — Son Goku Đợt 1 (`v4`)

> Mọi task làm **tuần tự từng bước**, đối chiếu **ngưỡng chuẩn `Walk` (`walk_base` & `walk_ssj`, `125 px`, bảng màu phẳng sạch 16-bit, viền sắc 1px, `0` hốc nền kín)** trước khi sang task tiếp theo.

---

## Danh Sách Task & Cổng QA Bắt Buộc

- [x] **T1 — Xóa 100% hốc nền đen kín (`enclosed_key_pockets == 0`) trên toàn bộ 100% frame** (`0 / 132` frame lỗi)
- [x] **T2 — Đồng bộ 100% Hình dạng, Bảng màu & Độ nét chuẩn `Walk` cho cả `Base` (`idle_base` 4f Codex CLI `1:1` `walk_base`) lẫn `SSJ1` (`02..34` sạch `BOX` + cân bằng bảng màu `walk_ssj`)**
- [x] **T3 — Xóa bỏ hoàn toàn `idle_ssj` thừa & Chuẩn hóa máy trạng thái `Hòa bình` ⇄ `Chiến đấu`** (`idle_ssj_aura` ⇄ `walk_ssj`; nối `combat_enter` → `idle_combat`)
- [x] **T4 — Bỏ hoàn toàn Drum tướng khi vừa vào map** (nhận diện thêm `*.app.github.dev` trong `AppStartup.gd` + nâng cấp mặc định session `"drum"` → `songoku_hero_demo`)
- [x] **T5 — Cập nhật Bay (`200 px/s` + Analog xuống hạ nhanh) & `combat_move` (`200 px/s`, loop `300ms / 80ms`)**
- [x] **T6 — Đánh thường `attack_light..attack_7`: Hit Impact + trừ sát thương TỪNG FRAME đánh trúng, giảm sát thương (`10..20` / `50` / `60`), nối đòn `100 ms`**
- [x] **T7 — Kiểm định toàn diện & Đồng bộ `1:1` Localhost ⇄ Godot Web** (`./loop.sh web-export`, `./loop.sh test`, HTTP 200 SHA-256 Parity)
