# ⚡ mclean (macOS Developer & AI Precision Cleaner)

> **Công cụ dọn rác & tối ưu chuyên dụng cho lập trình viên Flutter, Mobile & AI trên macOS.**  
> Chắt lọc tinh hoa từ **PureMac** (7.4k ⭐) & **tw93/Mole** (72.8k ⭐).  
> Giải quyết triệt để vấn đề đầy ổ cứng mà **KHÔNG BAO GIỜ gây ra vòng lặp tải lại dữ liệu**.

---

## 🎯 Điểm Khác Biệt & Triết Lý An Toàn

Hầu hết các công cụ dọn dẹp macOS thông thường thường xoá mù quáng các thư mục như `~/.gradle`, `~/.pub-cache` hay `~/.cache/huggingface`. Điều này dẫn đến thảm hoạ: vừa xoá xong, mở dự án lên lại phải chờ tải lại hàng chục gigabyte dữ liệu và build lại từ đầu.

**`mclean` áp dụng mô hình 3 Tầng An Toàn (Surgical Precision Safety Tiers):**

| Tầng | Định nghĩa | Hành vi của mclean |
| :--- | :--- | :--- |
| 🟢 **Tier 1: 100% SAFE** | Dữ liệu rác thật (log cũ, file tạm, cache Gradle bản cũ > 30 ngày, build dự án đã lâu không đụng tới). | **Tự động dọn** khi chạy lệnh `mclean clean`. Xoá xong **mọi project vẫn chạy ngay lập tức** mà không tải lại 1 byte nào. |
| 🟡 **Tier 2: REVIEW** | Model AI (HuggingFace, Ollama), máy ảo iOS/Android nặng. | **Chỉ dọn khi bạn chọn** qua giao diện Checkbox tương tác (`mclean interactive` hoặc `mclean ui`). |
| 🔴 **Tier 3: LOCKED** | Dữ liệu sống (package Dart `pub-cache/hosted`, Android AVD `userdata.img`, Gradle `modules-2`). | **Chặn vĩnh viễn**, không bao giờ xoá nhầm. |

---

## 🚀 Chạy Lệnh Toàn Cục (Global Command)

Lệnh `mclean` đã được liên kết sẵn vào hệ thống macOS. Bạn có thể mở Terminal bất kỳ và gõ:

```bash
mclean --help
mclean status
mclean scan
```

---

## 🛠️ Các Lệnh Chính Của `mclean`

### 1. `mclean ui` (🖥️ Dashboard Trực Quan Toàn Màn Hình)
Mở giao diện Dashboard TUI đồ hoạ ngay trong Terminal (dùng chuột click, phím mũi tên `↑/↓`, phím `Space` để tick chọn, `S` để quét, `C` để dọn, `Q` để thoát).
```bash
mclean ui
```

### 2. `mclean scan` (🔍 Báo Cáo Phân Tích Dung Lượng)
Quét toàn diện hệ thống (Xcode, Android, Flutter, AI, System) và hiển thị bảng phân tích màu sắc, phân loại rõ mục nào là `SAFE` (dọn ngay) và mục nào là `REVIEW` (cần chọn lọc).
```bash
mclean scan
```

### 3. `mclean clean` (🧹 Dọn Dẹp An Toàn)
Dọn dẹp các mục an toàn 100% (Tier 1 SAFE).
```bash
# Xem thử trước những file sẽ bị xoá (không xoá thật)
mclean clean --dry-run

# Dọn dẹp an toàn tất cả mục SAFE
mclean clean

# Chỉ dọn riêng một danh mục (xcode, android, ai, dev, system, trash)
mclean clean xcode
mclean clean android
mclean clean ai
```

### 4. `mclean interactive` (🎯 Chọn Lọc Từng Mục)
Mở menu checkbox chọn lọc từng Model AI (ví dụ: `stabilityai/sd-turbo` 2.4 GB) hoặc từng máy ảo iOS Simulator / Android AVD nặng hàng chục GB.
```bash
mclean interactive
```

### 5. `mclean optimize` (🚀 Tối Ưu Hệ Thống macOS - Cảm hứng từ tw93/Mole)
Thực hiện các tác vụ tinh chỉnh hệ thống chuyên sâu:
- **Chặn Finder tự động tạo file `.DS_Store` rác** lên ổ đĩa USB và ổ đĩa mạng.
- **Làm mới bộ nhớ đệm DNS** (Flush DNS Cache).
- **Làm mới QuickLook & Icon Cache** (sửa lỗi thumbnail, icon app bị trắng).
- **Dọn dẹp lịch sử theo dõi Quarantine** của macOS Gatekeeper.
```bash
mclean optimize
```

### 6. `mclean installer` (📦 Dọn File Cài Đặt & Mobile Builds Tồn Đọng)
Quét thư mục `~/Downloads` tìm các tệp cài đặt `.dmg`, `.pkg`, `.iso` và các bản build di động `.apk`, `.ipa`, `.aab` lớn đã tải về từ lâu:
```bash
mclean installer --dry-run
mclean installer --older-than 7
```

### 7. `mclean purge [path]` (🗑️ Dọn Thư Mục Build Cũ Của Dự Án)
Quét sâu vào các thư mục dự án để tìm và dọn dẹp các thư mục `build/`, `.dart_tool/`, `node_modules/`, `Pods/` của những dự án **đã không code trong hơn 14 ngày qua**:
```bash
# Quét các dự án trong thư mục Code/Projects
mclean purge ~/Projects

# Chỉ dọn các dự án không đụng tới hơn 30 ngày
mclean purge ~/Projects --older-than 30
```

### 8. `mclean analyze [path]` (📊 Phân Tích Dung Lượng Cục Bộ)
Trình khám phá dung lượng (Read-only Explorer), phân tích và sắp xếp các thư mục con theo thứ tự giảm dần từ nặng nhất đến nhẹ nhất mà không xoá bất cứ thứ gì:
```bash
mclean analyze ~
mclean analyze ~/Library
```

### 9. `mclean ignore` (🛡️ Danh Sách Bảo Vệ)
Bảo vệ các thư mục dự án quan trọng hoặc khách hàng bí mật để `mclean` không bao giờ quét vào:
```bash
mclean ignore list
mclean ignore add ~/Projects/production_app
mclean ignore remove ~/Projects/production_app
```

---

## 🛡️ Tích Hợp Tự Động Process Guard

Trước khi dọn dẹp, `mclean` tự động kiểm tra xem các phần mềm như Xcode, Android Studio, iOS Simulator, Flutter CLI, hay Ollama có đang mở không qua `psutil`. Nếu bạn đang build hoặc code, công cụ sẽ:
1. Phát hiện và cảnh báo PID của ứng dụng đang chạy.
2. Từ chối hoặc hỏi xác nhận để không làm crash tiến trình bạn đang làm việc.
