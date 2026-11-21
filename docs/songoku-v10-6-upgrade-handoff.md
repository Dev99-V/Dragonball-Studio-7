# Bàn giao nâng cấp Son Goku v10.6 và HUD Sân Tập

Phiên hiện tại dừng ở tài liệu bàn giao vì còn 3% quota. Mốc tiếp tục là ứng viên v10.6 trong working tree, dựa trên commit `8260ca0` (v10.5). `state.json` ghi `awaiting_owner_human_test`. Phản hồi dưới đây là các mục cần sửa trước lần duyệt tiếp theo.

## 1. Khôi phục và khóa phạm vi

- Chạy `./loop.sh status`, đọc `AGENTS.md`, `state.json` và `lerning.md`. Đọc `skills.md` trước khi xử lý atlas. Kiểm `git status` và chụp mốc v10.6 từ working tree, gồm các frame chưa được Git theo dõi. Dùng mốc này để so sánh trước/sau.
- Khóa theo tên clip, thứ tự và tên frame, SHA-256 của RGBA giải mã theo frame, timing, loop, sự kiện và anchor cho các clip ngoài yêu cầu. Áp dụng cả cho Human Test và frame cắt từ atlas Godot. Vị trí ô trong atlas có thể đổi khi repack.
- Giữ chuẩn **Combined 1-Layer**, atlas thân một trang tối đa 4096×4096, Nearest và tick 60 Hz. Dùng FX độc lập cho tia lửa và đạn. Giữ Son Goku trong roster Human Test đến khi Owner duyệt.

## 2. Hoạt ảnh và gameplay

| Hạng mục | Yêu cầu | Điều kiện nghiệm thu |
| --- | --- | --- |
| `kame_ground_up` frame #1 | Sửa đầu ở tư thế ngước nhìn theo nhận diện Son Goku trong các frame còn lại của clip. | Đối chiếu tóc, mặt, tỷ lệ đầu và hướng nhìn ở frame #0 → #1 → #2. |
| `kame_ground_horiz` và `kame_ground_up` | Căn mọi frame theo cùng điểm trụ chân và vị trí đứng trên mặt đất. Xác định xê dịch đến từ frame hay vị trí node trong runtime. | Đo điểm trụ theo tọa độ canvas và world qua các frame chuẩn bị, tụ lực, phóng và hồi thế. Kiểm ở tốc độ thật để thấy thân đứng vững, kể cả khi đổi hướng ngang. |
| `energy_recover` | Thêm tóc bay phấp phới trong 4 frame loop, lấy chuyển động tóc của `idle_ssj_aura` làm mẫu. Giữ điểm trụ và tư thế thân ổn định. | Xem từng frame, vòng lặp và điểm nối frame cuối về đầu trên ba nền. |
| Điều kiện dùng `energy_recover` | Chỉ cho phép kích hoạt khi nhân vật đang chạm mặt đất. Nút **Hồi 3s** ở trạng thái không khả dụng khi nhảy, đang bay hoặc đang rơi. Áp dụng cùng điều kiện ở logic nhận lệnh để cả nút cảm ứng và phím tắt đều tuân thủ. | Thử kích hoạt khi đứng đất, đang nhảy, đang bay, đang rơi và ngay sau khi tiếp đất. Lệnh trên không không bắt đầu clip, hiệu ứng hay hồi chỉ số và không ép nhân vật đáp đất. Sau khi tiếp đất, nút dùng được trở lại nếu đủ các điều kiện hiện hành. |
| `atomic_ground` | Thêm tia lửa vàng ở bàn tay phóng, theo cột đầu của sheet Atomic. Frame #6 tay trái phóng hết **3 viên**, sau đó frame #7 tay phải phóng tiếp **3 viên**. Điểm sinh đạn cách vùng bàn tay và tia lửa **30 px theo hướng phóng**. | Đo điểm sinh trong world và kiểm khi lật ngang. Ghi log thứ tự frame và thời điểm phóng của cả 6 viên. Ở frame sinh đạn, sprite đạn nằm ngoài silhouette bàn tay và tia lửa. |
| `atomic_air_down` | Nâng từ 4 lên **6 viên** như bản mặt đất. Đồng bộ tia vàng ở tay với thời điểm phóng. | Kiểm đủ đạn, hướng chưởng xuống và tia lửa khớp bàn tay qua từng lần phóng. |
| Atomic từ đất lên không | Thêm hướng chưởng khi đứng đất và chọn mục tiêu trên không, tham chiếu `kame_ground_up` cho tư thế và điều kiện chọn hướng. | Hướng nhìn, pose tay, tia lửa và đường đạn cùng hướng. Kiểm cả mục tiêu ở hai phía và chuyển mục tiêu đất ↔ không. |
| Quỹ đạo Atomic | Đổi đạn từ bay thẳng sang bay vòng cung, chạm mục tiêu và tới theo nhịp nối đuôi. Owner nói “2 lần bây tay trái” và yêu cầu trên mặt đất vẫn là 3 viên trái rồi 3 viên phải. | Chốt với Owner hai lượt/viên tay trái là hai viên cụ thể trong loạt hay hai lượt phóng, và đường cong áp dụng cho những viên hoặc biến thể nào. Kiểm điểm sinh, quỹ đạo và thứ tự tới bằng trace theo tick. |
| AI đổi từ mục tiêu trên không sang mục tiêu mặt đất | Khi nhân vật đang bay và Owner trỏ vào quái hay mục tiêu dưới đất, AI tự dịch chuyển hoặc tiếp cận mục tiêu mới. Sửa lỗi lặp `fly_prep` → `fly_aura` tới cạn mana mới rơi xuống đánh. | Tái hiện với mana còn đủ, đang đánh mục tiêu trên cao rồi đổi trỏ xuống mục tiêu đất. Trace ID mục tiêu, trạng thái bay, vị trí và mana. AI thoát vòng lặp và tiếp cận/đánh mục tiêu đất khi vẫn còn mana. Kiểm thêm đổi trỏ nhanh và mục tiêu mất hiệu lực giữa chừng. |

Nguồn tia lửa tay là [sheet Atomic gốc](<../Songoku/23. skill chưởng antomic  đầu - đuôi.png>).

Chốt thêm cách đo mốc 30 px nếu biên hình tia lửa thay đổi theo frame. Dùng Điều 7.8 làm chuẩn cho kiểm tra đường đạn qua bậc địa hình. Khi sửa quỹ đạo Atomic, rà cả kỳ vọng `ignore_terrain: true` hiện có trong runtime và test để xác định phần nào cần sửa trong phạm vi. Kamehameha cũng có khoản nợ va chạm tương tự đã ghi nhận trong phiên rà soát.

## 3. HUD và điều khiển Sân Tập

| Hạng mục | Yêu cầu |
| --- | --- |
| Icon vỡ khiên | Hiện ngay trên thanh máu khi đòn đánh làm cạn thanh giáp. Kích thước bằng icon trạng thái Chiến đấu và Hòa bình. Kiểm riêng trường hợp giáp đã bằng 0 trước khi trúng đòn. |
| Thanh Ki | Giảm độ dày **40%**, còn **60%** độ dày hiện tại. |
| Cụm trái | Giữ Đăng xuất, Khu và avatar ở bên trái. Thêm dropdown chọn tướng ngay cạnh cụm này. Tự chọn khi chỉ có một tướng và lấy danh sách tướng dùng được trong Sân Tập khi có thêm. |
| Cụm phải | Gom các nút điều khiển còn dùng về phía phải, cạnh cụm Gọi Shenron. Bỏ nút Pixel, Thước và Tâm quái khỏi HUD Sân Tập. Thêm công tắc **Vô hạn mana** ở góc phải, có chỉ báo bật/tắt. |
| Gọi boss | Dùng dropdown để chọn boss rồi gọi boss tại map người chơi đang đứng. Áp dụng cho Sân Tập, kể cả map chưa có cấu hình boss cố định. Kiểm gọi cùng một boss ở hai map. |
| Joystick và cụm skill | Tham chiếu đúng hai vùng khoanh xanh trong ảnh mẫu cho kích thước, phong cách icon và bố trí. Dùng kính mờ để nhìn rõ nền game, có phản hồi khi chạm và nhả nút. Vẽ icon vector đơn giản cho các nút skill hiện tại. Kamehameha dùng hình tia chưởng xanh dương với nền trong suốt. Các vùng gạch đỏ nằm ngoài phạm vi tham chiếu. |

Nguồn bố cục là [ảnh mẫu HUD](../c5ebb08600d4cf82deaf6312bac7905a.jpg). Kiểm thao tác giữ joystick đồng thời bấm skill, nút nằm trong Safe Area, và các công tắc thử nghiệm hoạt động trong Sân Tập.

## 4. Thứ tự làm và bàn giao

1. Ghi mốc v10.6, tái hiện xê dịch thân và vòng lặp bay, đo nguồn và chốt các điểm chưa rõ với Owner theo Điều 2. Tiếp tục các mục độc lập có đầu vào rõ.
2. Sửa clip và logic chiến đấu, chạy kiểm hồi quy và đối chiếu phạm vi. Chuẩn bị Human Test cho hoạt ảnh và gameplay trước, rồi làm HUD theo thứ tự Owner đã chọn.
3. Chạy `./loop.sh test` và `./loop.sh check`. Ghi exit code, cảnh báo thực tế, dữ liệu đo và số vòng sửa. Xem filmstrip trên nền sáng, tối và ô cờ. Phát ở tốc độ thật trong tab Human Test và kiểm gameplay trong Sân Tập Godot Web.
4. Xuất và đối chiếu SHA-256 của tài nguyên dùng chung trên localhost, Web, APK và IPA. Kiểm thực tế trên Redmi K70E, đối chiếu iOS và ghi phần còn chờ thiết bị. Cập nhật `state.json` theo tiến độ và ghi vào `skills.md` sau khi Owner nghiệm thu.
