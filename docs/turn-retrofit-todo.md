# TODO turn cho nhân vật đã duyệt

Yêu cầu Owner2026-11-13. **Tiến độ hiện tại: 1/4 hoàn tất (`Bat - Chiroptera` Owner-approved `turn-v1 / v0.11.2`).** `T-rex`, `Pteranodon` và `Sarcosuchus` chờ thực hiện tuần tự sau Bat. King Crab không cần turn; các nhân vật không nằm dưới đây giữ nguyên theo chỉ dẫn Owner.

Owner nêu Bat,T-rex,dực long,cá sấu cần bổ sung/sửa turn. File có tên `turn` không đủ chứng minh đã đáp ứng mục tiêu; riêng Sarcosuchus đã có clip/contract nhưng vẫn cần audit hành vi/nhận diện hai chiều theo phản hồi Owner, không tự kết luận nguyên nhân khi chưa có bằng chứng.

Tham chiếu: [contract và score100điểm](art-standards/turn-contract.md). Mọi hàng ban đầu `pending`, score **chưa chấm**, không tự nhận0%hay100%giống. Thực hiện tuần tự và hoàn tất sửa/test/HumanTest từng nhân vật trước khi chuyển hàng kế tiếp.

| Thứ tự | Nhân vật | Trạng thái | Gate mở đầu | Score |
|---|---|---|---|---|
|1|Bat - Chiroptera|`owner_approved` (`PIPE-009` / `turn-v1` / `v0.11.2` — 5 pose turn phối cảnh + runtime 2 chiều/2 endpoint; `61/61` frame cũ bảo toàn)|Chilopoda Owner-approved|100/100 (`owner_approved: true`, `docs/characters/bat-chiroptera-turn-v1-qa.json`)|
|2|T-rex|`blocked_on_image_gen_quota` (`TURN-002` — snapshot trước sửa `snapshot-before/` + audit hoàn tất; `generate_image` `gemini-3.1-flash-image` trả `429 RESOURCE_EXHAUSTED` lúc `10:58:33Z`, reset `2026-11-13T14:42:06Z`; live `assets/t_rex/` giữ nguyên)|Bat turn hoàn tất và Owner-approved (`v0.11.2`)|Chưa chấm/100|
|3|Pteranodon / dực long|Chưa bắt đầu|T-rex turn hoàn tất và Owner-approved|Chưa chấm/100|
|4|Sarcosuchus / cá sấu|Chưa bắt đầu|Pteranodon turn hoàn tất và Owner-approved|Chưa chấm/100|

## Checklist thực hiện riêng cho từng nhân vật

- [x]1.Bat:khóa revision/receipt/master và tất cả frame/tick cũ; xem Spino turn; audit camera/cánh/near-far. Sinh wholebody turn (5 pose +68/+55/0/-55/-68, ticks [5,4,3,4,5]); sửa hốc trắng/viền trắng rìa theo phản hồi Owner; review identity từng pose. Test phải→trái/trái→phải và hai endpoint riêng, loop.sh/Godot/Rust/WASM/HTTP+ZIP parity exit0, 10/10 gate, Owner chốt ngày `2026-11-13T10:50:00+00:00`.
- [ ]2.T-rex:khóa revision/receipt/master và frame/tick cũ; audit đầu/hàm/đuôi, không sửa heavy đã duyệt. Wholebody turn có trọng lượng,không rigidturntable. Kiểm hai chiều/hai endpoint/clipseams; sửa/test/score và Ownerchốt trướcPteranodon.
- [ ]3.Pteranodon:khóa revision/receipt/master và frame/tick cũ; audit wingbeat/hoverphase/near-farwing và anchor bay. Wholebody aerial turn thật với phối cảnh/che khuất, không xoay/flipcard. Kiểm hai chiều/hai endpoint và nối bay; sửa/test/score và Ownerchốt trướcSarcosuchus.
- [ ]4.Sarcosuchus:khóa revision/receipt/master và frame/tick cũ; reproduce turnhiện tại/endpoint theo Owner, lưu log/frame/tọa độ lỗi. Audit bốnchân/thânthấp/hàm/đuôi; sửa artwork hoặc runtime đúng nguyênnhân. Kiểm hai chiều/hai endpoint/clipseams; sửa/test/score và Ownerchốt.

Mỗi nhân vật lưu một report10gate, nguồn pose/identitySHA, frozen-before, kết quả từng lần loop.sh, browser/Godottrace, ảnh/clip3nền, lỗi và số đo cụ thể. Các thay đổi nhận diện/timing mới cần biên nhận revision mới; không dùng biên nhận atlas cũ để nhận bản mới đã được duyệt.

Chỉ đạo Owner (2026-11-13T11:54:03Z): **Chốt duy nhất Bat (`1/4` turn retrofit hoàn tất, Owner-approved `PIPE-009 / v0.11.2`)**. Ba nhân vật còn lại (`T-rex`, `Pteranodon`, `Sarcosuchus`) ghi nhận vào TODO tạm hoãn chờ reset quota sinh ảnh (`gemini-3.1-flash-image` mở lại sau `2026-11-13T14:42:06Z`). T-rex đã chuẩn bị sẵn snapshot bất biến `work/characters/t_rex/turn-v1/snapshot-before/` (73 frame + baseline manifest) và sẽ tiếp tục ngay khi có quota. Pteranodon và Sarcosuchus tiếp tục tuần tự sau T-rex.

Hướng dẫn bàn giao cho agent khác: [AGY-TURN-HANDOFF.md](AGY-TURN-HANDOFF.md), gồm hiến pháp, nguồn mẫu, migration receipt/test, QA hai chiều và giới hạn5vòng.
