# ⚡ mclean (macOS Developer & AI Precision Cleaner)

> **Công cụ dọn rác, tối ưu & tự động hoá chuyên dụng cho lập trình viên Flutter, Mobile & AI trên macOS.**  
> Chắt lọc tinh hoa từ **tw93/Mole** (72.8k ⭐) và **PureMac** (7.4k ⭐).  
> Giải phóng ổ cứng mà **không ảnh hưởng công việc đang làm** và **không gây vòng lặp xoá rồi tải lại**.

---

## 🎯 Triết Lý 3 Tầng An Toàn (Surgical Precision)

| Tầng | Định nghĩa | Hành vi của mclean |
| :--- | :--- | :--- |
| 🟢 **Tier 1: SAFE** | Chỉ những thứ máy **tự tạo lại tại chỗ** hoặc **không còn ai dùng**: log, file tạm, cache IDE/Simulator, build của dự án không đụng tới > 14 ngày, bản Gradle không dự án nào tham chiếu **và** không chạy > 30 ngày, snapshot AVD không bật > 14 ngày. | **Tự động dọn**. Xoá xong không phải tải lại gì. |
| 🟡 **Tier 2: REVIEW** | Thứ xoá xong **phải tải lại khi cần**: cache npm/pip/uv/CocoaPods/SwiftPM/pub git, model AI (HuggingFace, Ollama), iOS DeviceSupport, máy ảo lâu không dùng, container Docker đã dừng, tệp nén trong Downloads. | **Chỉ dọn khi bạn chọn** qua menu tương tác (`mclean interactive` hoặc `mclean`). |
| 🔴 **Tier 3: LOCKED** | Dữ liệu sống (package Dart `pub-cache/hosted`, Android AVD `userdata.img`, Gradle `modules-2`). | **Chặn vĩnh viễn**, không bao giờ xoá nhầm. |

---

## 🚀 Khởi Động Nhanh

Lệnh `mclean` đã được liên kết sẵn vào hệ thống macOS. Bạn chỉ cần mở Terminal bất kỳ và gõ:

```bash
mclean
```
*(Nếu không truyền tham số, `mclean` sẽ tự động mở **Dashboard tương tác trực quan** với thanh tiến trình trực tiếp siêu mượt!)*

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
```

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

> 💡 Extension Java/Gradle của VS Code-based IDE (`redhat.java`, `vscjava.vscode-gradle`) tự import cả các project Android mẫu trong `~/.pub-cache` và tải Gradle wrapper riêng cho từng project. Nếu không làm Android native, tắt `java.import.gradle.enabled` và `gradle.autoDetect` trong workspace Flutter để tránh tải về hàng GB không cần thiết.
