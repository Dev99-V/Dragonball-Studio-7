# Lộ Trình & TODO Hoàn Thiện Tướng Đầu Tiên — Son Goku (`Songoku/`)

> Cập nhật theo chốt Owner ngày `2026-11-20`.
> **Thứ tự triển khai**: Hoàn thiện & Owner Human Test **Đợt 1 (3 mục cốt lõi)** trước, sau đó mới giải đáp các câu hỏi còn lại và triển khai Đợt 2+.

---

## Đợt 1 — Đang Triển Khai (`review/songoku_hero_demo/`)
1. **Hệ thống dạng `Base` (tóc đen) ⇄ `SSJ1` (tóc vàng) & Biến hình**:
   - `Base`: chỉ di chuyển & tương tác (`idle_base` 14f từ `01`, `walk_base` 8f từ `walk_v6`), **khóa tấn công / skill chiến đấu** khi chưa biến hình.
   - Skill biến hình riêng (`transform_ssj`: `02` trái→phải 7f + `03` 1f nối → vào SSJ1 `04`; `detransform_base`: `02` phải→trái 7f).
   - `SSJ1`: `idle_ssj` (tĩnh không aura), `idle_ssj_aura` (`04` 4f), `walk_ssj` (`walk_v6` 8f đã nghiệm thu), `jump` (`07` 6f), `hit` (`08` 5f), `ko` (`09` 3f).
   - Thay thế **Drum** làm **Tướng mặc định của người chơi** (HUD + nút Hiện Tướng + Avatar [avatar_son-goku-ssj1.png](../../Songoku/avatar_son-goku-ssj1.png)); giữ **Drum** làm Boss/Quái AI; giữ hiệu ứng **bụi di chuyển & đáp đất** của Drum cho các tướng.
2. **Chuỗi Đánh Thường 7 Bước Liên Hoàn (`10`→`11`→`12`→`13`→`14`→`17`→`15`)**:
   - Đánh thường tuần tự đúng số thứ tự cuối tên file `1..7`: `10(1) → 11(2) → 12(3) → 13(4) → 14(5) → 17(6 - Heavy) → 15(7 - Heavy kết thúc)`.
   - Lưu trạng thái chuỗi combo khi xen kẽ dùng skill khác; **chỉ reset khi chết (`KO`) hoặc chuyển map mới**.
   - Sát thương:
     - Đòn nhẹ `1..5` (`10..14`): random `20..40` roll liên tục (`20` thường, `40` chí mạng).
     - Đòn nặng `6..7` (`17`, `15`): `80` dmg; riêng **frame vệt vàng kế cuối của `17`** gây **`90` dmg**.
3. **Di Chuyển Chiến Đấu (`16`), Dịch Chuyển 2 Chế Độ + Thể Lực `100` (`20`) & Cơ Chế Bay + `Fly_Aura` (`18`, `19`)**:
   - `walk_v6` (`170 px/s`) dùng khi không chiến đấu tại mặt đất; vào trạng thái chiến đấu tự động chuyển sang **`16` (`combat_move`, `190 px/s`)** điều khiển bằng analog.
   - **Độ nét, Chuẩn hóa kích thước & 2 Trạng thái Hòa bình ⇄ Chiến đấu (`v3`)**:
     - Toàn bộ 25 clip khóa chuẩn kích thước 1:1 (`125px`) & độ nét 1px theo `walk_v6`; sửa sạch lỗ tóc trắng Base `01`, sạch hốc nền kín `02` F3-F5, khóa `0.0px` chân chạm đất `04` (`idle_ssj_aura`) đúng tỷ lệ `125px`.
     - **2 trạng thái game (`Hòa bình` ⇄ `Chiến đấu`)**: mặc định `Hòa bình` (`walk=true, combat_move=false, idle_ssj_aura=true`); trong lúc `transform_ssj` bất tử không bị tấn công, biến xong loop `idle_ssj_aura` đến khi di chuyển/tấn công/bị đánh; khi bị tấn công hoặc chủ động bấm Đánh (SSJ1) chuyển sang `Chiến đấu` (chớp chữ đỏ `"CHIẾN ĐẤU"` ở giữa màn hình `0.55s`, bật `combat_move=true, walk=false, idle_combat` từ `34`, `attack_1..7`); hết giao tranh `6s` tự về `Hòa bình`.
     - **`jump` (`07`) 360° analog (~`100px`)**: `F0..F2` thu người nhảy lên (hỗ trợ xéo 360°), `F3..F5` rơi xuống, riêng **`F4`** dùng cho mọi trạng thái rơi từ trên cao → tiếp đất `F5` → về `idle`.
     - **`combat_move` (`16`)**: lùi analog = `F0`, tiến analog = `F3`, `F1..F2` là khung chuyển tiếp mượt theo analog; `HIT` (`08`) khi bị đánh vỡ giáp, `KO` (`09`) khi hết máu.
   - **Dịch chuyển (`20`)** + Thể lực tối đa **`100`**, hồi **`+5/s`**, vẽ **vòng thanh thể lực xoay trực tiếp quanh nút Dịch chuyển**:
     - **(a) Đứng tĩnh + bấm Dịch chuyển**: tiêu tốn **`75`** thể lực, dùng 3 frame cụm trái (`0..2`), dịch chuyển áp sát địch đang trỏ.
     - **(b) Đang di chuyển (analog) + bấm Dịch chuyển**: tiêu tốn **`25`** thể lực, dịch chuyển **`100 px`** theo đúng hướng analog (trước/sau/trên/dưới); dùng **3 frame hàng trên** khi ở mặt đất, **3 frame hàng dưới** khi đang lơ lửng trên không.
   - **Cơ chế Bay v3 (BỎ `fly_launch` `19`; Nhảy + giữ Analog lên → `fly_aura`, khóa ở Base)**:
     - Vào bay: chỉ ở **SSJ1**, kích hoạt `jump` và giữ analog lên cao → tự động vào **`fly_aura`** (4 frame nằm ngang song song mặt đất, đủ 2 chân, tóc phấp phới + hào quang sao chổi động).
     - Dừng bay trên không → **`fly_prep`** v3 (4 frame lơ lửng nhún nhẹ + tóc phấp phới + hào quang vàng bùng lên) trong `3s`; nếu di chuyển tiếp nối lại `fly_aura`, hết `3s` rơi xuống bằng `jump` Frame `4` → tiếp đất `F5` → về `idle`/`idle_combat`.

---

## TODO — Các Mục Chờ Hoàn Thiện Ở Đợt Sau (Sau Khi Owner Human Test Đợt 1)
- [ ] **Setup nhảy & bay cho `Base` (tóc đen)** và hoàn thiện cơ chế bay lơ lửng cho cả `Base` & `SSJ1`.
- [ ] **`05. skill vòng tròn bảo vệ .png`**: Skill Khiên bảo vệ (`LOOP 10S`, hiệu ứng phòng thủ/giảm sát thương).
- [ ] **`06.Gồng phục hồi nặng lượng.png`**: Skill Gồng hồi Ki/Năng lượng (vòng lặp `3s` + xả khí).
- [ ] **`21`, `23`, `24`, `25` (Chưởng Antomic / Ki Blast vàng)**: Bắn ngang mặt đất (`21`+`23`) & bắn chéo từ trên không (`24`+`25`); xác nhận lại số `22` có thiếu file hay nhảy số.
- [ ] **`26. skill đá liên hoàn.png`**: Skill Đá liên hoàn lướt vệt sáng vàng.
- [ ] **`27`, `28`, `29`, `30`, `31`, `32` (Kamehameha 4 hướng)**: Đất ngang (`28`), đất chéo lên (`29`), không ngang (`30`), không chéo xuống (`27`), nối mảnh tia (`31`, `32` + lật dọc chéo xuống).
- [ ] **Reset combo khi chuyển map mới** (tích hợp khi mở rộng hệ thống chuyển cảnh đa map).
- [ ] **Chốt chính thức `assets/songoku/`**: Sau khi Owner nghiệm thu toàn bộ Human Test (cả Localhost, Godot Web và APK K70E), promote từ `review/` sang `assets/songoku/` + `assets/roster.json`, cập nhật `skills.md` và dọn sạch `/work` & `review/`.
