# HIẾN PHÁP DỰ ÁN DR7-STUDIO (`AGENTS.md`)

Hiến pháp tối cao ở root `DR7-Studio` (tự nạp bởi `agy` & `codex`). Mọi quyết định kỹ thuật, asset, test engine và preview phải tuân thủ tuyệt đối:

---

## Điều 1. Cấm Tuyệt Đối Bịa Đặt & Đoán Mò (Zero Hallucination / Evidence-Only)

1. **Cấm bịa code, API, tham số**: Chỉ dùng API, flag CLI, schema, hàm đã xác minh qua tài liệu nội bộ, `--help`, mã nguồn hoặc chạy kiểm thử.
2. **Cấm bịa kết quả test/QA**: Chỉ báo cáo `PASS`/`OK` khi lệnh trả về `exit code 0` và đã đọc log thực tế. Mọi `WARN`/`FAIL` phải trích nguyên số liệu, không che giấu.
3. **Cấm suy đoán thiếu bằng chứng**: Nhận định lỗi code hoặc ảnh (alpha, viền màu, lệch tâm, mất chi tiết, độ nét) phải kèm đo đạc cụ thể (`Canvas (x,y)` / `Atlas (x,y)`, `RGBA`, log, path).

---

## Điều 2. Cổng Rõ Ràng & Đồng Nhất Mẫu Chuẩn (Pre-Task Clarity Gate)

1. **Rà soát trước khi làm**: Xác nhận rõ 100% mục tiêu, logic, đầu vào/ra, hiệu năng, nền tảng trước khi code hoặc xử lý asset.
2. **Mơ hồ = Dừng & Hỏi Owner**: Còn điểm chưa rõ từ Owner, `state.json`, `skills.md` thì **BẮT BUỘC dừng, hỏi Owner** kèm phương án + ưu/nhược điểm; cấm đoán mò.
3. **Đồng nhất mẫu chuẩn**: Nhận 1 mẫu chuẩn thì mọi hoạt ảnh phải đồng nhất **kích thước, hình dạng, màu sắc**; không hiểu phải hỏi ngay.

---

## Điều 3. Kiến Trúc Lớp Duy Nhất (`Combined 1-Layer`) & Thông Số Kỹ Thuật Bóc Tách Atlas Bắt Buộc

1. **Cổng hỏi bắt buộc khi thiếu thông tin**: Khi Owner đính kèm/trỏ file ảnh hoặc atlas chưa rõ mục đích, chỉ được đo thông số thực tế (px, hàng/frame, màu nền, nhiễu/watermark, bố cục chiêu), rồi **BẮT BUỘC hỏi Owner** trước khi xử lý.
   - **1b. Ảnh sheet sẵn có (Exact Sheet Fidelity & Role Contract)**: Khi Owner đưa ảnh sheet sẵn mà không yêu cầu tạo ảnh thô/atlas mới, dù tăng độ nét, scale hay tách hoạt ảnh chi tiết vẫn bắt buộc nhân vật xuất ra **giống 100% bản gốc về cấu trúc lẫn màu sắc**, chỉ khác kích thước khi Owner yêu cầu. Luôn hỏi Owner nếu chưa báo: **(a) tên/ID nhân vật**, **(b) kích thước/scale**, **(c) tướng chính hay quái/boss** (`quái/boss` dùng AI điều khiển; `tướng chính` phải thêm nút sử dụng skill vật lý).
2. **Kiến trúc Lớp Chính Thức Duy Nhất — Gộp Chung 1 Lớp Nguyên Bản (`Combined 1-Layer`)**:
   - Toàn bộ nhân vật trong dự án **bắt buộc sử dụng duy nhất kiến trúc `combined_1layer` (`1 Quad / 1 Draw Call`)**: giữ nguyên thân nhân vật một sprite/lớp; các phần FX theo contract Owner dưới đây. `1 Quad / 1 Draw Call` chỉ nói phần thân khi tắt FX.
   - **Bãi bỏ vĩnh viễn hướng bóc tách đa lớp (`layered_3d_depth` / `Hướng 2`)** vì làm sai cấu trúc vẽ gốc của sprite 2D. Hệ thống kiểm thử (`./loop.sh check` và `test_character_bundles.gd`) tự động đánh `FAIL` nếu xuất hiện bất kỳ cấu hình `layered_3d_depth` nào.
   - **Cấm tuyệt đối dùng AI vẽ lại làm biến dạng chi tiết gốc (`Zero AI Redraw`)** khi bóc tách từ sheet của Owner.
   - **Quy tắc chung mới theo Owner**: Ki/aura phải xuất và điều khiển độc lập để dùng cùng nhiều hoạt ảnh thân, mặc định cho nhân vật có Ki; không hỏi lại. Thân không tách chi/cánh theo chiều sâu. Cùng atlas khi khả thi, contract/anchor/tick đồng bộ Godot và localhost; FX thêm sprite/quad và có chi phí riêng. Sheet đã gộp không tách an toàn thì báo giới hạn, không vẽ lại để nhận bảo toàn pixel.
3. **Thông Số Kỹ Thuật Bóc Tách, Tách Nền & Đăng Ký Tâm Chân Bắt Buộc (Chuẩn Khởi Đầu Studio từ `trunks_rage`)**:
   - **Phân tách cụm 2D theo mặt nạ sở hữu liên thông (`2D Component Ownership Masking`)**:
     - Cắt từng pose bằng nhãn liên thông 2D (`3×3` / `5×5` ownership mask) thay vì cắt hộp chữ nhật thô theo cột dọc, nhằm **ngăn chặn 100% mũi kiếm chéo hoặc tia lửa của pose kế bên lọt vào khung cắt**.
     - Loại bỏ sạch khung viền header/footer, chữ chú thích trên sheet (như nhãn `WIN`), dấu gạch ngang phân cách `-`, ảnh chân dung cắt ngang (`cut-in`), và vùng rìa giao thoa giữa hai hàng sát nhau (`extra_exclusions`).
     - Với các tia chưởng chia khúc trên sheet (như `Final Flash` gồm `Đầu | Thân | Ngọn` ngăn bởi vạch tối `1px`), bắt buộc khử vạch chia `1px` và ghép liền mạch vào đúng toạ độ bàn tay nhân vật; sắp xếp đúng thứ tự thời gian thực của chiêu thức.
   - **Tách nền 2 giai đoạn bảo toàn độ sắc Pixel Art (`Pocket-First Chroma Key + Edge Unmixing`)**:
     - **Giai đoạn 1**: Đục thủng 100% hốc nền kín kẹt giữa tay/chân/vỏ kiếm/hào quang (`enclosed_key_pockets == 0`, `opaque_key_px == 0`) bằng lan truyền hạt giống màu nền (`binary_propagation`) **trước** khi khử viền.
     - **Giai đoạn 2**: Khử pha màu trên viền biên `1px` (gồm cả viền pha màu nền trực tiếp lẫn viền vàng-pha-xanh `olive fringe` quanh hào quang sáng, chỉ số sạch viền `outer_ring_spill_fraction <= 0.005`), đồng thời giữ độ cứng biên pixel `alpha_hardness_pct >= 95%` (với pixel art) để không làm nhòe nét gốc.
   - **Chuẩn căn tâm gốc chống trượt chân (`Shared Row Ground Baseline + Dark-Outline/Torso Centroid`)**:
     - Trục ngang `X`: Căn theo trung vị viền tối của cơ thể / khăn choàng (`detect_body_center_x`) thay vì tâm hộp bao toàn ảnh, đảm bảo khi vung kiếm dài hoặc bắn chưởng xa cơ thể nhân vật đứng vững tuyệt đối tại `anchor_x`, không bị giật lùi.
     - Trục dọc `Y`: Căn theo đường mặt đất chung của từng hàng (`row_ground_y`) để giữ nguyên độ cao quỹ đạo nhảy/bay (`jump`, `ultimate`), riêng các frame gồng biến hình có tia lửa đâm xuống dưới đế giày phải căn theo đáy giày tối (`detect_boot_bottom_y`).
     - Kích thước khung Canvas nhân vật `[W, H]` bội số của `16` (chuẩn tham chiếu `trunks_rage`: `canvas_size_px = [320, 256]`, `foot_anchor_px = [96, 220]`, Godot `AnimatedSprite2D` đặt `centered = false`, `offset = Vector2(-anchor_x, -anchor_y)`).
   - **Chuẩn đóng gói Texture Atlas cho Engine**:
     - Đóng gói toàn bộ hoạt ảnh của 1 nhân vật lên **1 trang PNG Atlas duy nhất (`pages == 1`, kích thước tối đa `<= 4096 × 4096 px`)** để toàn bộ thực thể dùng chung nhân vật đó gộp gọn trong `1 Draw Call`.
     - Bắt buộc bật lọc mẫu **`Nearest` (`texture_filter = 1`)**, tốc độ chuẩn **`60Hz` ticks** trên `.tres` + `engine-export.json`, và đặt `.gdignore` trong `source/` & `clips/`.

---

## Điều 4. Kiến Trúc Engine & Hạ Tầng Chính Thức Đã Chốt

- **Dự án**: Game 2D **Dragon Ball** (`DR7-Studio`).
- **Nền tảng phát hành mục tiêu**: Mobile (**Android `.apk` / `.aab`** và **iOS `.ipa`**).
- **Mục tiêu hiệu năng cốt lõi**: **60 FPS mượt tuyệt đối (`<= 16.67 ms/frame`) khi có hơn `2,000` người chơi / thực thể giao tranh theo thời gian thực (Real-time Mass Combat)**.
- **Kiến trúc Engine Chính Thức (ĐÃ CHỐT — Hybrid Godot 4 + Rust Core + Supabase)**:
  1. **Godot Engine 4 (Client Chính Thức)**: Đảm nhận Scene, Map, Camera, UI cảm ứng Mobile, Âm thanh, xuất gói cài đặt Android/iOS và vẽ hàng nghìn nhân vật 1 lớp bằng `MultiMeshInstance2D` (`1 Draw Call`).
  2. **Rust Core (`engines/rust_combat_sim`)**: Đảm nhận tính toán vật lý, va chạm lưới không gian `O(N) Spatial Hash`, máy trạng thái 60Hz và đóng gói buffer GPU/mạng siêu tốc (`~0.61 ms/frame` cho `2,000` thực thể — dưới `4%` quỹ frame 60FPS), tích hợp vào Godot qua **`GDExtension`** (Native Mobile), chạy trực tiếp trên Server combat và biên dịch ra **`WebAssembly` (`rust_combat_sim.wasm`)** cho trạm kiểm thử `localhost:8080`.
  3. **Supabase**: Đảm nhận Auth, PostgreSQL (Hồ sơ nhân vật, Trang bị, Bang hội), Storage kết hợp đồng bộ nhị phân theo vùng nhìn **Spatial AoI** cho bài toán `> 2,000` CCU.

---

## Điều 5. Vòng Lặp Kiểm Thử Engine Bắt Buộc & Đồng Bộ Tuyệt Đối 1:1 Với Localhost

1. **Vòng lặp Tự Kiểm Thử & Tự Sửa Trên Engine (`Engine Verification Loop`)**:
   - Mọi kết quả dựng hoạt ảnh từ atlas **bắt buộc phải chạy kiểm thử tự động đầy đủ trên cả Godot 4 Headless (`test_character_bundles.gd`) và Rust Core (`cargo test` + WASM build)** (kiểm tra nạp texture/atlas, số frame, thời lượng tick `60Hz`, `offset == -anchor_px`, lọc `Nearest`, không hốc màu nền).
   - **FAIL/sai thông số**: Phân tích → sửa → chạy `./loop.sh test`, tối đa **5 vòng cho mỗi vấn đề**. Hết 5 vòng chưa sửa được phải dừng sửa vấn đề đó, báo Owner kèm lỗi, bằng chứng và các cách đã thử; không chạy vòng 6 hoặc bàn giao bản lỗi.
   - **Cổng chất lượng chuyển động và liên kết cơ thể (bắt buộc, áp dụng toàn dự án)**: kiểm thử texture/tick/hash không chứng nhận hoạt ảnh tự nhiên. Sau setup atlas, chỉ cần frame phát bị xé/cắt rời cơ thể, hở khớp, mất kết nối cơ quan, lộ mảng vá, biến dạng tỷ lệ hoặc xuyên/chồng bộ phận sai giải phẫu thì **kết quả hoạt ảnh = `FAIL`**, dù mọi unit test kỹ thuật exit0. Báo đúng `technical_checks` và `motion_quality` riêng; không dùng technical PASS để che motion FAIL. Kiểm tra cả từng frame, nối frame liên tiếp, nối vòng, phát ở tốc độ thực trên nền sáng/tối/ô cờ; lưu clip/frame/Canvas/Atlas/ảnh lỗi và kết quả kiểm tra. Thiếu bằng chứng trực quan là `pending`, không phải PASS; Owner báo lỗi cấu trúc thì hạ gate thành FAIL cho đến khi sửa được kiểm chứng.
   - **Tạo chuyển động từ master tĩnh**: tạo nhiều pose toàn thân liên tục theo skill, giữ cơ quan liên kết, đúng giải phẫu, nhận diện và tỷ lệ. **Cấm cắt xé ảnh tĩnh thành mảnh thân/chi/đầu rồi xoay, kéo, vá hoặc ghép giả chuyển động** hay lấp alpha/tăng FPS che cơ thể rách. Cắt nguyên frame hoàn chỉnh khỏi sheet vẫn được phép; giữ Zero AI Redraw và thân `combined_1layer`. Khi dùng imagegen, sinh toàn bộ nhân vật từng keyframe, review chuỗi trước đóng atlas; không mượn khớp/mask nhân vật khác.
2. **Đồng bộ Tuyệt đối 100% Giữa Engine và Localhost (`Zero-Drift Engine ⇄ Localhost Parity`)**:
   - Sau pass Engine, phục vụ lên `localhost:8080` **đồng bộ 1:1** cho **Human Test**. Godot 4, Rust Core và `localhost:8080` đọc **cùng 1 nguồn** (`assets/roster.json`, PNG atlas, `Rect2(x, y, w, h)` trong `.tres`, tick `60Hz`, `anchor_px`); `./loop.sh check` đối soát **SHA-256** & `[W, H]`.
3. **Chỉ lưu Nhân vật Đã Hoàn Thiện trên Danh sách Nhân vật**:
   - Tuyệt đối không lưu trữ rác, nhân vật test cũ hoặc các bản nháp lỗi trong `assets/`, `scenes/` hay `roster.json`.

---

## Điều 6. Phân Biệt Rạch Ròi Giữa `skills.md` (Quy Trình Nghiệp Vụ) & `.agents/skills/` (Skill Công Cụ Asset)

Agent tuyệt đối **KHÔNG ĐƯỢC NHẦM LẪN** hai khái niệm sau:

| Thành phần | Bản chất | Khi nào SỬ DỤNG | Khi nào CẬP NHẬT |
|---|---|---|---|
| **`.agents/skills/*`** (`.agent/skills/*`: `generate2dsprite`, `video2dsprite`, `generate2dmap`, `generate2dmedia`, `codeart2d`) | **Skill Công Cụ Kỹ Thuật**: Script xử lý ảnh, `build_animation_clips.py`, `export_engine.py`. | Bên trong bước kỹ thuật đóng gói clip 60Hz, filmstrip và `.tres` / PNG atlas. | Thư viện sẵn; không ghi nhật ký quy trình Owner. |
| **`skills.md`** (root dự án) | **Quy Trình Nghiệp Vụ Dự Án (`Owner Atlas -> Final Animation Pipeline`)**: Nhận atlas -> tách 1 lớp -> pass Engine -> 1:1 localhost. | Đọc **ngay đầu task khi nhận ảnh/atlas từ Owner**. | Khởi tạo **TRỐNG**. Chỉ ghi sau khi hoàn tất quy trình và **Owner nghiệm thu Human Test OK**. |

**Kỷ luật trực quan**: Trước Human Test, xem trực tiếp từng dải `filmstrip-*.png` trên 3 nền (**sáng, tối, ô cờ**) để triệt sạch chữ thừa, vạch cắt hoặc lấn hàng.

## Điều 7. Chuẩn Bộ Hoạt Ảnh Nhân Vật, Thước Đo Map & Giao Tiếp Toạ Độ Trên UI Test

1. **Điều kiện Kiểm thử Bộ Hoạt Ảnh Nhân Vật (`Character Animation Completeness Gate`)**:
   - Bộ clip tham chiếu chiến đấu cốt lõi gồm: `idle`, `walk`, `run`, `jump`, `guard`, `attack_light`, `attack_heavy`, `power_up`, `aura_loop`, `hit`, `ko`, `win` (cùng các kỹ năng đặc trưng từng tướng như kiếm khí, chưởng lực, tốc biến, chiêu cuối).
   - Hệ thống kiểm thử (`./loop.sh check` và UI `localhost:8080`) kiểm tra danh sách clip của mỗi nhân vật và phát cảnh báo nhắc nhở (`WARN`) rõ ràng nếu nhân vật mới chỉ có một phần hoạt ảnh.
   - **Owner chốt phạm vi chung**: không tạo `guard` và `win` cho bất kỳ nhân vật nào; không hỏi lại. Giữ WARN tham chiếu nếu có và ghi lý do Owner loại, không tạo clip giả.
2. **Thông số Kích thước Nhân vật, Mốc Chuẩn Pixel Art & Phong Cách Chung Mặc Định**:
   - **Mốc độ nét chung — T-rex đã nâng cấp (Owner chốt mốc 2026-11-12)**:
     - Nhân vật tạo tiếp theo phải đối chiếu [ảnh T-rex cố định](docs/art-standards/t-rex-sharpness-reference.png) và [thông số/phương pháp](docs/art-standards/character-pixel-sharpness.json): **1px gameplay, Nearest**, alpha thân100%; VFX được alpha mềm. Thay chuẩn100texel/2×/16màu/201.3 cũ; kích thước riêng từng nhân vật vẫn giữ.
     - Mẫu idle0: canvas384×256,bbox186×134,anchor[176,224],Sobel **245.516**. Đo bằng `python3 tools/art/measure_pixel_sharpness.py <frame.png>`; xem1×/zoom nguyên lần trên3nền. Không ép scalar/dung sai tự đặt, blur/sharpen/LUT/dither để chạy theo số; đo key/pocket/spill theo nền nguồn.
     - Mốc này chốt độ nét, không chốt atlas/hoạt ảnh T-rex đang demo. Xé cấu trúc/hở khớp/lật ảnh giả xoay vẫn FAIL; không tự sửa nhân vật đã duyệt ngoài phạm vi Owner.
   - **Thẩm mỹ mặc định**: Quái thú/sinh vật mang phong cách **"Hung tợn"** (răng nanh/cưa nhọn, mắt sắt dữ, móng vuốt bén, màu đậm sẫm) trừ khi Owner chỉ định riêng.
   - Mọi nhân vật trong `roster.json` công bố đầy đủ: `canvas_size_px` (`[W, H]`), `foot_anchor_px` (`[ax, ay]`), `body_only_bbox_px`, `full_fx_bbox_px`, `reference_ppu_64` (`64 PPU`, tile `32×32 px`), `pixel_sharpness_metrics` (`texel_scale_ratio`, `edge_acutance_sobel`, `alpha_hardness_pct`, `opaque_key_px == 0`, `enclosed_key_pockets == 0`, `outer_ring_spill_fraction`).
3. **Giao Tiếp Toạ Độ (`Owner ⇄ Agent Coordinate Protocol`)**: UI `localhost:8080` hỗ trợ `[W, H]` động, `frame scrubber`, thước X/Y, `RGBA`, và khoanh `Rect(x, y, w, h)` xuất `[DR7-EDIT-SPEC]`.


4. **Khóa hướng nhìn nhân vật trên Map 2D (`Movement / Facing Contract`)**:
   - Trước khi sinh bộ atlas theo hướng, ghi rõ trong hồ sơ nhân vật: kiểu nhìn map/camera, tập hướng cần vẽ, hướng di chuyển trên map, hướng thân/mặt, và hướng tác động vũ khí. Không dùng từ “trước/sau” khi chưa xác định nó là trái/phải trên màn hình hay mặt trước/lưng nhân vật.
   - Không mặc định map 2D đồng nghĩa với nhìn ngang, top-down hoặc 4/8 hướng. Khi Owner chưa nêu rõ ánh xạ, hỏi trước phần sinh frame phụ thuộc hướng.
   - Lật ngang chỉ đổi trái/phải; không tạo được mặt lưng từ mặt trước. Không dùng flip dọc để giả lập đổi hướng lên/xuống. Các hướng phải giữ cùng nhận diện, tỷ lệ, anchor và thiết kế vũ khí; kiểm tra chi tiết bất đối xứng khi dùng mirror.
   - Tách vector di chuyển khỏi hướng nhìn khi có lùi/strafe hoặc đánh theo mục tiêu. Với mỗi clip, ghi rõ nhân vật quay về đâu, chân di chuyển thế nào và búa/vũ khí đánh về đâu; không tự suy hướng mặt chỉ từ vị trí trong atlas.
   - **Xoay người, quật đuôi và đổi hướng phải có trọng lượng thật**: tạo các pose chuyển tiếp phù hợp trục xoay/góc camera, có thay đổi phối cảnh và che khuất đúng thứ tự, đầu/ngực/hông/chân/đuôi chuyển động liên tục, tiếp đất và trọng tâm hợp lý. Cấm dùng flip_h, xoay quad hoặc thu ngang một tấm ảnh như các frame của hành động xoay; mirror chỉ chọn bộ hướng trái/phải sau khi có chuyển tiếp hợp lệ, không thay thế hoạt ảnh quay đầu/quay thân. Timing60Hz phải tách lấy đà → tăng tốc vung/tác động → giảm tốc/hồi thế, ghi tick và kiểm tra tốc độ thực; không rải đều tick khiến xoay như lật bìa ảnh. Với Spinosaurus, pha vung đuôi `attack_heavy` phải nhanh hơn bản bị Owner loại; tăng tốc đơn thuần mà vẫn lật ảnh hoặc xé cơ thể vẫn FAIL. Không áp cứng tốc độ đó cho mọi sinh vật; thiết kế theo cơ thể và lực tác động.

---

**Chu kỳ di chuyển và tái sử dụng walk/run — Owner 2026-11-12**:
- Walk phải là một vòng tiến pha liên tục `0→1→…→N−1→0` (bộ8frame: `0→7→0`), đủ hai nhịp chân đối nhau. Không dùng ping-pong, phát ngược `7→1`, bỏ frame ở biên hoặc nhánh loop riêng để chữa dáng đi sai.
- Không đưa hai frame trùng hoặc gần trùng pha chuyển động vào chu kỳ; đặc biệt frame cuối phải là pha trước frame đầu, không sao lại tư thế đầu để “đóng vòng”. Lấy mẫu `[0,360°)` không lấy cả0°và360°. Kiểm tra mọi cặp trùng pixel, so thêm tư thế/chân và cadence ở biên cuối→đầu; khác màu vài pixel không đủ chứng minh pose khác. Hai chân phải đổi vai trò chân trụ/chân vung, tránh lò cò. Sai nhịp tiếp đất = motion FAIL dù hash frame khác nhau.
- **Run phải có dáng chạy riêng** (Owner làm rõ 2026-11-12, thay thế hướng dẫn run=walk tăng tốc trước đó): walk chỉ là tiền đề tham khảo nhận diện, giải phẫu và nhịp chân. Không dùng lại toàn bộ frame/rect walk rồi tăng playback để nhận là run. Tạo pose chạy toàn thân riêng: sải dài, trọng tâm/chúi thân, pha đẩy chân/thu chân/tiếp đất phù hợp; vòng0..N−1→0 liên tục (8pose:0..7→0; thêm pose thì cập nhậtN), không ping-pong. Không áp cứng tỷ lệ duration0.5 giữa hai clip. Review cadence và biên cuối→đầu của run độc lập; tốc độ map tách khỏi tốc độ frame.
- Turn bắt buộc trong atlas mới; ngoại lệ Owner: King Crab. Xoay phối cảnh thật hoặc cơ chế Owner chốt, giữ nhận diện master, kiểm riêng trái→phải và phải→trái; nối walk→turn→walk ở hai đầu đường/giới hạn trên Godot/localhost, không lật ảnh giả xoay. Sửa/test theo giới hạn 5 vòng; giữ nguyên heavy đã duyệt.

5. **Chuẩn Bắt Buộc Cho Mọi Item Game (`assets/items/` — Cổng Đủ Điều Kiện Chốt)**:
   - Mọi item game sau khi build chỉ đủ điều kiện chốt khi đạt đủ **4 yếu tố** đồng bộ 1:1 Godot ⇄ Localhost (`60Hz Nearest`, 1 PNG atlas, alpha thân 100% `0/255`, `.gdignore` cho `source/` & `clips/`):
     - **Icon trong Balo**: Chỉ hiển thị **icon tĩnh nguyên bản** (`bag` mode), **BẮT BUỘC ẩn hoàn toàn hiệu ứng** tránh loạn thị giác.
     - **Hiệu ứng quét sáng chéo toàn thân (`diagonal_body_sheen`)**: Dải sáng quét chéo toàn bộ thân item (nằm gọn trong silhouette item), chỉ bật khi item nằm chờ trên map.
     - **Hoạt ảnh rơi khi quái chết (`drop_physics`)**: Nhảy nhẹ lên `10px` → rơi chạm đất `ground_y` → lăn nhẹ `10px` trên đất rồi mới bắt đầu hiệu ứng quét sáng chéo.
     - **Hoạt ảnh thu vào người Player & Sân Tập (`pickup_physics`)**: Khi người chơi chọn nhặt → tắt hiệu ứng quét sáng, item bay hướng vào thân người nhặt và **thu nhỏ dần** đến khi chạm người rồi vào balo; Sân Tập bắt buộc có **nút ẩn/hiện item** (cùng nút test rơi & nhặt). Thiếu bất kỳ yếu tố nào = chưa đủ điều kiện chốt (`./loop.sh check` đánh `FAIL`).

## Điều 8. Tiêu Chuẩn Developer (Unit Test, CI/CD, Versioning) & Bộ Nhớ Bắt Buộc (`./loop.sh`)

1. **Unit Test, CI/CD & SemVer**:
   - Mọi module xử lý dữ liệu, Godot prefab/bundle, Rust WASM/combat core và giao diện 2 Tab phải có kiểm thử tự động chạy qua `./loop.sh test` (`exit 0`) và tích hợp CI (`.github/workflows/ci.yml`).
   - Phiên bản nguồn duy nhất tại `VERSION` theo chuẩn `MAJOR.MINOR.PATCH`, đồng bộ chặt với `state.json`, `project.godot` và `engines/rust_combat_sim/Cargo.toml`.
2. **Quy tắc Đọc / Ghi Hệ Thống Bộ Nhớ (`./loop.sh`)**:
   - **`AGENTS.md` & `state.json` (BẮT BUỘC MỌI PHIÊN)**: Chạy `./loop.sh status` ngay khi vào phiên; cập nhật `state.json` ngay sau mỗi task để chống mất ngữ cảnh khi đứt kết nối.
   - **`skills.md` (ĐỌC TRƯỚC KHI NHẬN XỬ LÝ ATLAS)**: Chỉ ghi vào sau khi Owner nghiệm thu Human Test thành công.
   - **`lerning.md` (ĐỌC TRƯỚC KHI CODE / SỬA ASSET)**: Đọc để tránh lặp lại lỗi kỹ thuật cũ; ghi bổ sung ngay sau khi gặp lỗi mới và đã sửa xong có kiểm chứng.
