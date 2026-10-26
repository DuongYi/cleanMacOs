# ⚡ mclean (macOS Developer & AI Precision Cleaner)

> **Công cụ dọn rác, tối ưu & tự động hoá chuyên dụng cho lập trình viên Flutter, Mobile & AI trên macOS.**  
> Chắt lọc tinh hoa từ **tw93/Mole** (72.8k ⭐) và **PureMac** (7.4k ⭐).  
> Giải quyết triệt để vấn đề đầy ổ cứng mà **KHÔNG BAO GIỜ gây ra vòng lặp tải lại dữ liệu**.

---

## 🎯 Triết Lý 3 Tầng An Toàn (Surgical Precision)

| Tầng | Định nghĩa | Hành vi của mclean |
| :--- | :--- | :--- |
| 🟢 **Tier 1: 100% SAFE** | Rác thật (log cũ, file tạm, cache Gradle bản cũ > 30 ngày, build dự án đã lâu không đụng tới). | **Tự động dọn**. Xoá xong **mọi project vẫn chạy ngay lập tức** mà không tải lại 1 byte nào. |
| 🟡 **Tier 2: REVIEW** | Model AI (HuggingFace, Ollama), máy ảo iOS/Android nặng. | **Chỉ dọn khi bạn chọn** qua menu tương tác (`mclean interactive` hoặc `mclean`). |
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
- `mclean clean`: Dọn dẹp nhanh các mục `SAFE` mà không làm tải lại dữ liệu.
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
Dọn dẹp triệt để Docker build cache, dangling images và stopped containers:
```bash
mclean docker

# Deep clean (xoá toàn bộ container và image không dùng)
mclean docker --all
```

### 5. 🐘 Quét Tệp Siêu Nặng Thất Lạc (`mclean large-files`)
Rà soát nhanh các tệp lớn (video quay màn hình, checkpoint model AI `.safetensors`, `.onnx`, file nén lớn):
```bash
# Quét tệp >= 500 MB (mặc định)
mclean large-files

# Quét tệp >= 100 MB kèm chọn thao tác xem trong Finder hoặc xoá
mclean large-files --min-size 100 --interactive
```

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
Quét thư mục `~/Downloads` tìm các file `.dmg`, `.pkg`, `.iso` và các bản build `.apk`, `.ipa`, `.aab` cũ:
```bash
mclean installer --older-than 7
```

### 8. 🗑️ Dọn Thư Mục Build Dự Án Cũ (`mclean purge`)
Quét sâu các dự án Flutter, Node, Python và xoá `build/`, `.dart_tool/` của các dự án không đụng tới hơn 14 ngày:
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

## 🛡️ Tích Hợp Sẵn Process Guard

Trước khi dọn dẹp, `mclean` tự động phát hiện xem Xcode, Android Studio, Flutter, iOS Simulator, hay Ollama có đang mở không. Nếu đang chạy, công cụ sẽ cảnh báo để bảo vệ tiến trình của bạn không bị gián đoạn.
