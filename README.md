# ⚡ mclean (macOS Developer & AI Precision Cleaner)

> **Công cụ dọn rác, tối ưu & tự động hoá chuyên dụng cho lập trình viên Flutter, Mobile & AI trên macOS.**  
> Lấy cảm hứng từ [tw93/Mole](https://github.com/tw93/Mole) và PureMac.  
> Giải phóng ổ cứng mà **không ảnh hưởng công việc đang làm** và **không gây vòng lặp xoá rồi tải lại**.

---

## 🎯 Triết Lý 3 Tầng An Toàn (Surgical Precision)

| Tầng | Định nghĩa | Hành vi của mclean |
| :--- | :--- | :--- |
| 🟢 **Tier 1: SAFE** | Chỉ những thứ máy **tự tạo lại tại chỗ** hoặc **không còn ai dùng**: log, file tạm, cache IDE/Simulator, build của dự án không đụng tới > 14 ngày, bản Gradle không dự án nào tham chiếu **và** không chạy > 30 ngày, snapshot AVD không bật > 14 ngày. | **Tự động dọn**. Xoá xong không phải tải lại gì. |
| 🟡 **Tier 2: REVIEW** | Thứ xoá xong **phải tải lại khi cần**: cache npm/pip/uv/CocoaPods/SwiftPM/pub git, model AI (HuggingFace, Ollama), iOS DeviceSupport, máy ảo lâu không dùng, container Docker đã dừng, tệp nén trong Downloads. | **Chỉ dọn khi bạn chọn** qua menu tương tác (`mclean interactive` hoặc `mclean`). |
| 🔴 **Tier 3: LOCKED** | Dữ liệu sống (package Dart `pub-cache/hosted`, Android AVD `userdata.img`, Gradle `modules-2`). | **Chặn vĩnh viễn**, không bao giờ xoá nhầm. |

---

## 🚀 Cài Đặt & Khởi Động Nhanh

Yêu cầu: macOS và Python 3.9 trở lên (Python có sẵn của macOS là đủ).

**Một lệnh duy nhất** (tự tải về `~/.mclean`, cài thư viện, thêm lệnh `mclean` vào PATH, rồi hỏi có bật lịch tự động không):
```bash
curl -fsSL https://raw.githubusercontent.com/DuongYi/cleanMacOs/main/install.sh | bash
```

| Việc cần làm | Lệnh |
| :--- | :--- |
| Cập nhật bản mới | `mclean update` |
| Gỡ cài đặt (tắt lịch chạy ngầm, xoá lệnh và `~/.mclean`; giữ cấu hình) | `curl -fsSL https://raw.githubusercontent.com/DuongYi/cleanMacOs/main/install.sh \| bash -s -- --uninstall` |
| Cài từ bản clone có sẵn (dùng luôn thư mục đó) | `git clone https://github.com/DuongYi/cleanMacOs.git && cd cleanMacOs && ./install.sh` |
| Cài bằng pipx | `pipx install git+https://github.com/DuongYi/cleanMacOs.git` (cập nhật: `pipx upgrade mac-dev-cleaner`) |

Sau đó:
```bash
mclean            # Dashboard tương tác
mclean doctor     # kiểm tra máy có gì khiến cache bị tải lại không
mclean clean -n   # xem trước những gì sẽ được dọn (dry-run)
```

> ⚠️ mclean xoá dữ liệu thật. Mục SAFE được thiết kế để xoá xong không phải tải lại, nhưng hãy chạy `mclean scan` hoặc `--dry-run` trước để biết chính xác những gì sẽ bị xoá trên máy bạn.

---

## 🛠️ Bộ Lệnh Toàn Diện Của `mclean`

### 1. 🖥️ Dashboard & Tương Tác
- `mclean`: Mở Dashboard tương tác tổng hợp (10 tính năng nhanh trong 1 màn hình).
- `mclean scan`: Quét toàn diện hệ thống với thanh tiến trình đồ hoạ và bảng phân tích màu sắc.
- `mclean clean [xcode|android|flutter|ai|dev|system|trash]`: Dọn nhanh các mục `SAFE` mà không làm tải lại dữ liệu. Mục mà ứng dụng đang mở dùng tới luôn được bỏ qua, kể cả với `--force`.
- `mclean interactive` (hoặc `mclean clean -i`): Menu Checkbox duyệt chọn từng Model AI và máy ảo.

### 2. ⏱️ Tự Động Hoá & Lịch Ngầm (`mclean schedule`)
Đăng ký macOS `LaunchAgent` tự động chạy ngầm:
```bash
# Xem trạng thái lịch hiện tại
mclean schedule

# Kích hoạt lịch dọn tự động mỗi sáng Thứ Hai lúc 09:00 (kèm thông báo macOS)
mclean schedule --install

# Huỷ bỏ lịch chạy ngầm
mclean schedule --remove

# Cảnh báo khi ổ sắp đầy: kiểm tra mỗi 3 giờ, báo tối đa 1 lần/ngày, KHÔNG tự xoá gì
mclean schedule --alert-on
mclean schedule --alert-off

# Kiểm tra ngay (không cần lịch)
mclean check-space
```
Lịch tự động chỉ dọn mục SAFE và luôn bỏ qua mục mà ứng dụng đang mở dùng tới.

### 3. 📜 Nhật Ký & Thống Kê Tiết Kiệm (`mclean history`)
Theo dõi tổng số GB mà bạn đã giải phóng được từ trước đến nay:
```bash
# Xem tổng dung lượng đã cứu sống và danh sách các lần dọn gần nhất
mclean history

# Xoá lịch sử
mclean history --clear
```

### 4. 🐳 Dọn Dẹp Docker & Containers (`mclean docker`)
Mặc định chỉ dọn dangling images và build cache không dùng hơn 30 ngày, nên các lần build sau vẫn nhanh:
```bash
mclean docker

# Deep clean: xoá cả container đã dừng và MỌI image không dùng (phải pull lại khi cần)
mclean docker --all
```

### 5. 🐘 Quét Tệp Siêu Nặng Thất Lạc (`mclean large-files`)
Rà soát nhanh các tệp lớn (video quay màn hình, checkpoint model AI `.safetensors`, `.onnx`, file nén lớn):
```bash
# Quét tệp >= 500 MB (mặc định)
mclean large-files

# Quét tệp >= 100 MB kèm chọn thao tác xem trong Finder hoặc dọn
mclean large-files --min-size 100 --interactive
```
Khi dọn tệp của bạn (ở đây và ở `mclean installer`), bạn chọn **chuyển vào Thùng rác** (khôi phục được) hoặc **xoá vĩnh viễn**.

### 6. 🚀 Tối Ưu Hệ Thống macOS (`mclean optimize`)
Thực hiện các tinh chỉnh hệ thống chuyên sâu (chuẩn tw93/Mole):
- Chặn Finder tự động tạo file ẩn `.DS_Store` rác trên USB và ổ đĩa mạng.
- Làm mới bộ nhớ đệm DNS (Flush DNS Cache).
- Làm mới QuickLook & Icon Thumbnail Cache.
- Dọn dẹp lịch sử Quarantine của Apple Gatekeeper.
```bash
mclean optimize
```

### 7. 📦 Dọn Tệp Cài Đặt & Mobile Builds (`mclean installer`)
Quét thư mục `~/Downloads` tìm các file `.dmg`, `.pkg`, `.iso`, bản build `.apk`, `.ipa`, `.aab` và tệp nén lớn. Bạn chọn từng tệp; chỉ bộ cài cũ hơn số ngày chỉ định được chọn sẵn, tệp nén không bao giờ được chọn sẵn:
```bash
mclean installer --older-than 7
```

### 8. 🗑️ Dọn Thư Mục Build Dự Án Cũ (`mclean purge`)
Quét các dự án không có hoạt động (sửa code, build, `pub get`, git) hơn 14 ngày rồi cho bạn chọn từng mục: `build/` và `.dart_tool/flutter_build/` của Flutter (SAFE, chọn sẵn, giữ `package_config.json` nên mở lại không cần `pub get`), `node_modules` và `Pods` (REVIEW, không chọn sẵn):
```bash
mclean purge ~/Projects --older-than 14
```

### 9. 📊 Trình Khám Phá Dung Lượng (`mclean analyze`)
Phân tích và sắp xếp các thư mục con theo dung lượng giảm dần (Read-only Explorer):
```bash
mclean analyze ~
```

### 10. 🛡️ Danh Sách Bảo Vệ (`mclean ignore`)
Bảo vệ các thư mục dự án bí mật của công ty hoặc khách hàng:
```bash
mclean ignore list
mclean ignore add ~/Projects/my_important_project
mclean ignore remove ~/Projects/my_important_project
```

---

### 11. ⚙️ Cấu Hình (`mclean config`)
Các ngưỡng và thư mục dự án lưu ở `~/.config/mclean/config.json`:
```bash
mclean config                              # xem toàn bộ thiết lập
mclean config set inactive_days 30         # coi dự án là "cũ" sau 30 ngày
mclean config set low_disk_percent 10      # cảnh báo khi trống dưới 10%
mclean config add-root ~/Projects          # thêm thư mục dự án để quét
mclean config remove-root ~/Desktop
mclean config reset                        # về mặc định
```

### 12. 🩺 Kiểm Tra Sức Khoẻ (`mclean doctor`)
Kiểm tra lịch chạy ngầm, quyền truy cập của Terminal và job nền, lần dọn tự động gần nhất, và **phát hiện IDE đang tự tải lại Gradle** (extension Java/Gradle đi theo `ios/.symlinks` vào `~/.pub-cache`), kèm đoạn setting cần thêm:
```bash
mclean doctor
```

Trong `mclean interactive`, các mục được **nhóm theo loại** (nhóm lớn nhất lên đầu), kèm "dùng lần cuối" và mô tả của mục đang chọn.

---

## 🔎 Những Gì `mclean` Quét

| Khu vực | SAFE (tự dọn) | REVIEW (bạn chọn) |
| :--- | :--- | :--- |
| Xcode & Simulator | DerivedData của dự án không build > 14 ngày, cache Xcode/Simulator/Previews, simulator không còn khả dụng | DeviceSupport theo từng phiên bản OS, simulator không bật > 30 ngày, runtime Simulator không dùng > 30 ngày, cache CocoaPods/SwiftPM |
| Android | Gradle wrapper/cache không dự án nào khai báo **và** không chạy > 30 ngày, log daemon > 7 ngày, snapshot AVD không bật > 14 ngày, system image x86 trên Apple Silicon | System image không AVD nào dùng, NDK không dự án/Flutter SDK/plugin nào khai báo (luôn giữ bản mới nhất) |
| Flutter | `build/` và `.dart_tool/flutter_build/` của dự án không hoạt động > 14 ngày | Cache git của pub |
| AI & Python | Cache IDE (VS Code, Cursor), kernel PyTorch, log Ollama/LM Studio, `uv cache prune` | Model HuggingFace/Ollama, cache pip, toàn bộ cache uv |
| Dự án lâu không đụng tới (> 14 ngày) | — | `node_modules`, `Pods` (khôi phục bằng `npm install` / `pod install`) |
| Trình duyệt | — | Cache Chrome, Cốc Cốc, Brave, Edge, Firefox (giữ nguyên đăng nhập, lịch sử; bỏ qua khi trình duyệt đang mở) |
| Hệ thống | Log ứng dụng, crash report, Thùng rác, `brew cleanup`, `pnpm store prune` | Cache npm/Yarn/Bun |

---

## 🧪 Phát Triển & Kiểm Thử

```bash
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest
```
Test chạy hoàn toàn trong thư mục tạm và không đụng tới cấu hình hay lịch sử thật trong `~/.config/mclean`.

---

## 🛡️ Tích Hợp Sẵn Process Guard

Trước khi dọn, `mclean` kiểm tra Xcode, iOS Simulator, Android Studio/Emulator, Gradle Daemon, Flutter/Dart, VS Code, Cursor, Ollama và LM Studio. Mục nào ứng dụng đang mở dùng tới sẽ **được bỏ qua**, không bị xoá, ở mọi chế độ (kể cả `--force` và lịch tự động). Bản Gradle mà một daemon đang chạy cũng không bao giờ bị đề xuất.

> 💡 Extension Java/Gradle của VS Code-based IDE (`redhat.java`, `vscjava.vscode-gradle`) tự import cả các project Android mẫu trong `~/.pub-cache` và tải Gradle wrapper riêng cho từng project. Chạy `mclean doctor` để biết IDE nào đang làm vậy và đoạn setting cần thêm (`java.import.exclusions`, `gradle.autoDetect`).

---

## 📄 Giấy Phép

[MIT](LICENSE) © 2026 Duong Yi
