# Changelog

## 0.3.0 — 2026-10-26

### Tính năng mới
- Cài bằng một lệnh: `curl -fsSL https://raw.githubusercontent.com/DuongYi/cleanMacOs/main/install.sh | bash`. Script kiểm tra macOS/git/Python, cài vào `~/.mclean`, thêm `mclean` vào PATH, hỏi có bật lịch tự động và cảnh báo ổ đầy không. Chạy lại để cập nhật, thêm `--uninstall` để gỡ.
- `./install.sh` trong một bản clone có sẵn thì dùng luôn thư mục đó.
- `mclean update`: tải bản mới và cài lại thư viện.

## 0.2.0 — 2026-10-26

Nguyên tắc mới cho mục SAFE: chỉ dọn thứ **tự tạo lại tại máy** hoặc **không còn ai dùng**, và **không bao giờ đụng vào thứ mà ứng dụng đang mở dùng tới**. Mọi thứ xoá xong phải tải lại đều chuyển sang REVIEW (bạn tự chọn).

### Sửa lỗi
- Lệnh installer từng xoá cả tệp mới tải và mọi tệp nén trên 50 MB trong Downloads; giờ bạn chọn từng tệp, tệp nén không bao giờ được chọn sẵn.
- Dự án Flutter đang làm bị coi là "không hoạt động" vì chỉ xét file ngay trong `lib/`; giờ xét toàn bộ mã nguồn, lần build, `pub get` và git.
- "Giữ 2 bản Gradle mới nhất" xoá cả bản đang được dùng, gây vòng tải lại; giờ chỉ xoá bản không dự án nào khai báo, không daemon nào chạy và không dùng trong 30 ngày.
- Process Guard bị bỏ qua khi dọn toàn bộ và khi chạy theo lịch; giờ áp dụng ở mọi chế độ, nhận diện thêm Gradle Daemon, VS Code, Cursor và trình duyệt.
- Dọn Thùng rác không xoá gì nhưng vẫn báo thành công.
- Dung lượng "đã giải phóng" là số ước tính; giờ là số đo thật.
- Snapshot AVD không bao giờ dọn được vì bị blacklist chặn; dữ liệu `userdata`/`sdcard` vẫn luôn được bảo vệ.
- Blacklist không chặn thư mục cha (`~`, `~/.gradle/caches`…).
- File plist của lịch tự động sai cú pháp XML.
- Lọc danh mục theo chuỗi con (`clean ai` dọn nhầm "unavailable simulator").
- Tên model Ollama mất namespace; báo dung lượng gấp đôi do thư mục log lồng nhau.

### Tính năng mới
- `mclean doctor`: kiểm tra lịch chạy ngầm, quyền truy cập, và phát hiện IDE (extension Java/Gradle) đang tự tải lại Gradle qua `ios/.symlinks` → `~/.pub-cache`, kèm đoạn setting cần thêm.
- `mclean config`: chỉnh ngưỡng ngày, cỡ tối thiểu và thư mục dự án trong `~/.config/mclean/config.json`.
- Cảnh báo ổ đầy: `mclean check-space` và `mclean schedule --alert-on` (chỉ báo, không xoá).
- Quét Android SDK: system image không AVD nào dùng, image x86 trên Apple Silicon, NDK không ai khai báo.
- Runtime iOS Simulator lâu không dùng, DerivedData và DeviceSupport theo từng dự án/phiên bản.
- `node_modules`, `Pods` của dự án cũ và cache trình duyệt (Chrome, Cốc Cốc, Brave, Edge, Firefox) ở mức REVIEW.
- Danh sách chọn nhóm theo loại, kèm "dùng lần cuối".
- Tệp của bạn (installer, large-files) có thể chuyển vào Thùng rác thay vì xoá vĩnh viễn.
- Dùng lệnh dọn có sẵn của từng công cụ: `brew cleanup`, `uv cache prune`, `pnpm store prune`; Docker chỉ dọn build cache không dùng quá 30 ngày.
- Giao diện và mô tả tiếng Việt.

### Khác
- Hỗ trợ Python 3.9 (bản có sẵn của macOS).
- 42 test `pytest`, CI trên macOS; giấy phép MIT.
- Gỡ `.venv`, `__pycache__`, `egg-info` khỏi git; xoá `tui.py` không dùng.

## 0.1.0

Bản đầu tiên.
