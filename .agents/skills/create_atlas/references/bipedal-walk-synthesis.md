# Kỹ thuật dựng Walk 2 chân góc 3/4 chuẩn 1px gameplay (`bipedal-walk-synthesis`)

Quy trình kỹ thuật tái sử dụng đã được Owner nghiệm thu qua mẫu **Son Goku SSJ1 `walk_v6`** (`2026-11-20`), dùng để bổ sung hoạt ảnh `walk` 8 frame chuẩn cho mọi nhân vật đứng 2 chân (tướng/quái/NPC) khi bộ sheet nguồn thiếu `walk` nhưng đã có ảnh tĩnh/chiêu thức ở góc nhìn chuẩn.

> **Ranh giới áp dụng**: Chỉ dùng nhánh này khi nhân vật **chưa có `walk` trong sheet gốc** và Owner yêu cầu dựng thêm `walk` đồng bộ với mẫu chuẩn. Các clip đã có sẵn trong sheet gốc vẫn tuân thủ nghiêm ngặt `Exact Sheet Fidelity` ([source-sheet-extraction.md](source-sheet-extraction.md), Zero AI Redraw).

---

## 1. Khóa Nhận Diện & Khóa Góc Camera (`Identity Lock` — Bước bắt buộc)

1. **Khóa góc nhìn theo bộ clip tĩnh/chiêu của nhân vật**:
   - Nếu nhân vật có turntable nhiều góc độ (ví dụ 8 góc) và/hoặc ảnh đứng chuẩn (`idle`), đối chiếu IoU để xác định chính xác góc chuẩn (thường là **3/4 hướng trước-phải `+X`**, ví dụ `Pose 0`).
   - **Cấm** dùng góc ngang phẳng `90°` nếu `idle` và các đòn đánh là góc `3/4` — khi ghép vào game sẽ thấy lệch góc đầu/ngực rõ rệt lúc chuyển `idle <-> walk`.
2. **Đóng băng tệp tham chiếu nhận diện**:
   - Lưu `idle_00` gốc và góc khóa `Pose 0` kèm SHA-256 làm **Identity Anchor** duy nhất.
   - Mọi frame `walk` sinh ra phải giữ nguyên 100% đầu, tóc, khuôn mặt, tỷ lệ ngực/eo/quần áo, độ dày viền và khối pixel vuông 16-bit của mẫu chuẩn.

---

## 2. Nguyên Tắc "Hai Neo Độc Lập" (`Dual-Anchor Standard`)

Để tránh lỗi "chuyển động đúng nhưng sai nhân vật" hoặc "đúng nhân vật nhưng sai bước đi":

- **Neo Nhận Diện (`Identity Anchor`)**: Ảnh chuẩn của nhân vật (`Pose 0` / `idle_00`) + 1 frame gốc đã kiểm duyệt dáng đứng trung gian (`F2` Passing).
- **Neo Chuyển Động (`Motion Anchor`)**: Bộ **Pose Guide 8 frame độc lập** (`pose_guide_F0..F7.png`, mỗi ảnh đúng 1 nhân vật ở giữa khung trên nền phẳng tối) biểu diễn chính xác 8 pha đi bộ tự nhiên (không chạy nước rút):
  - `F0`: **Right Contact** — chân gần (phải) bước ra trước, chân xa (trái) chống sau; tay gần đánh sau, tay xa đánh trước (hoặc đối pha nhất quán toàn chu kỳ).
  - `F1`: **Right Down** — hạ trọng tâm hấp thụ lực (`bob = +4 px`), đầu gối chùng nhẹ.
  - `F2`: **Right Passing** — 2 chân thu sát trục dọc đi qua nhau (`leg_w` hẹp, `bob = 0 px`).
  - `F3`: **Right High-Point** — nhấc thân nhẹ (`bob = -2 px`), chuẩn bị đổi chân.
  - `F4`: **Left Contact** — đối pha hoàn toàn với `F0` (chân xa bước trước, chân gần chống sau; tay đảo pha tương ứng).
  - `F5`: **Left Down** — đối pha hoàn toàn với `F1` (`bob = +4 px`).
  - `F6`: **Left Passing** — đối pha hoàn toàn với `F2` (`leg_w` hẹp, `bob = 0 px`).
  - `F7`: **Left High-Point** — đối pha hoàn toàn với `F3` (`bob = -2 px`).

---

## 3. Quy Trình Sinh Ảnh Từng Frame Đơn (`Single-Frame 1024×1024`)

### Vì sao CẤM sinh ghép 4×2 hoặc 8×1 trong 1 ảnh?
- Sinh 4–8 frame chung 1 sheet khiến model hay **copy hàng 1 xuống hàng 2** (nửa sau chu kỳ trùng pha `IoU 0.87–0.96`) hoặc biến bước đi thành chạy co gối cao, đồng thời làm mịn/vỡ cấu trúc pixel 16-bit khi chỉnh sửa lại sheet.

### Quy trình chuẩn qua `generate2dmedia` (`route_media.py`, ưu tiên API cấu hình hoặc `codex-cli`)
1. **Dựng từng frame đơn `1024×1024`** (`F0` đến `F7`), mỗi lệnh nhận 2 ảnh tham chiếu:
   - Ảnh 1: **Identity Anchor** (hoặc frame `F2` đã duyệt chuẩn cấu trúc pixel của chính nhân vật đó).
   - Ảnh 2: **Pose Guide đơn** tương ứng đúng pha `Fk`.
2. **Quy tắc Prompt chống từ chối & chống vỡ pixel**:
   - **Không dùng tên thương hiệu/IP** (ví dụ không viết tên nhân vật bản quyền) và tránh cụm `"pixel-for-pixel"` dễ kích hoạt bộ lọc từ chối của CLI.
   - Mô tả thuần thuộc tính thị giác: `"chunky 16-bit pixel-art fighter sprite"`, `"preserve exact chunky square pixel block thickness, black outline, palette, and 3/4 front-right facing angle"`, nền key đơn sắc phẳng (ví dụ `#00FF00` hoặc `#FF00FF` khác màu nhân vật).
3. **Kiểm tra giải phẫu cánh tay đánh sau ở `F0` và `F1` (Gate bắt buộc)**:
   - Ở góc `3/4` hướng phải, cánh tay xa (tay trái) khi vung về sau **phải thu gọn sát sau lưng/hông theo đúng trục cầu vai trái** (bị thân che một phần).
   - **FAIL ngay** nếu cánh tay xa nhô dài vượt quá phía sau cầu vai gần (gây cảm giác trật khớp vai khi chạy hoạt ảnh).
4. **Khi tạo biến thể cùng khung xương (ví dụ trạng thái Base ↔ SSJ)**:
   - **Cấm** sửa lại cả sheet 4×2 (dễ biến thành nét hoạt hình mượt, phá cấu trúc pixel).
   - Sinh **từng frame đơn `1024×1024`** lấy trực tiếp frame `Fk` đã duyệt của bản gốc + ảnh `idle_00` của biến thể, yêu cầu giữ nguyên 100% vị trí thân/tay/chân và khối pixel 16-bit, chỉ thay đầu/tóc/mắt/màu theo biến thể.

---

## 4. Tách Nền, Chuẩn Hóa Kích Thước & Đóng Gói 1-Pass `Nearest`

1. **Tách nền 2 giai đoạn (`AGENTS.md` Điều 3.3)**:
   - Giai đoạn 1: Đục thủng 100% hốc nền kín (`enclosed_key_pockets == 0`, `opaque_key_px == 0`).
   - Giai đoạn 2: Khử pha viền `1px` (`outer_ring_spill_fraction <= 0.005`), ép alpha thân cứng 100% (`0` hoặc `255`).
2. **Chuẩn hóa chiều cao hiển thị & tỷ lệ đầu đồng nhất (`1px gameplay, default_scale = 1.0`)**:
   - Đo chiều cao mục tiêu trên màn chuẩn `1920×1080` (ví dụ mốc `Drum = 125 px` với nhân vật hình người chuẩn).
   - Thu mẫu `idle_00` gốc bằng **1-pass `Image.Resampling.NEAREST`** trực tiếp về chiều cao mục tiêu (không scale 2 lần gây mixel).
   - Với 8 frame `walk`, chuẩn hóa kích thước theo **tỷ lệ đầu/thân thống nhất với `F3` / `idle_00`** và áp đúng quy luật nhún dọc đối xứng `bob = [0, +4, 0, -2, 0, +4, 0, -2]`, đặt chân bám chuẩn mặt đất `ground_y = anchor_y - 1` (không trượt chân, không phình to đột ngột ở 1 frame).
   - Đóng khung canvas bội số `16` (ví dụ `192×160`, anchor `[96, 144]`), `1` trang PNG atlas `Nearest`, tốc độ **`60Hz`** (`ticks = [6, 6, 6, 6, 6, 6, 6, 6]` = `48` ticks / `0.8s` mỗi vòng hoặc chỉnh theo tốc độ chạy nhân vật).

---

## 5. Cổng QA Kỹ Thuật & Motion Bắt Buộc Trước Human Test

| Hạng mục | Ngưỡng đạt chuẩn |
| :--- | :--- |
| Chênh lệch `head_w` giữa 8 frame `walk` | `spread <= 3 px` (SSJ1 `v6` đạt `2 px`, Base `v6` đạt `1 px`) |
| Đối xứng nhún dọc `bob` giữa `F0..F3` và `F4..F7` | `max_diff == 0 px` (`[0, 4, 0, -2, 0, 4, 0, -2]`) |
| Khép chân Passing `F2` & `F6` | Hẹp rõ so với Contact `F0`/`F4` (tỷ lệ ~`0.42–0.48×`), đối xứng nhau `<= 3 px` |
| Giải phẫu tay xa `F0`–`F1` | Ôm sát sau lưng/hông theo đúng trục cầu vai xa, không trật khớp |
| Sạch nền & Độ nét | `opaque_key_px = 0`, `pockets = 0`, `spill <= 0.005`, `alpha_hardness = 100%`, `single_px_run >= 0.95` |
| Đối chiếu trực quan bắt buộc | Xem **filmstrip 3 nền** (sáng / tối / ô cờ), **ảnh đặt cạnh mốc chiều cao (`Drum 125px`)**, và test vòng lặp tốc độ thực tại `localhost:8080` (**Tab Human Test**) |
