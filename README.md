# LiveScreen Translator Pro

LiveScreen Translator Pro là ứng dụng Windows dùng PaddleOCR cục bộ để đọc chữ trên màn hình, dịch **offline Anh → Việt** ngay trên máy, rồi vẽ bản dịch bằng overlay trong suốt/click-through tại tọa độ chữ gốc. DeepL và Google chỉ là tùy chọn nâng cao.

Phiên bản hiện tại: **0.5.0**.

## Chức năng đã triển khai

- Chụp một hoặc tất cả màn hình bằng MSS/Qt; ảnh chỉ tồn tại trong RAM.
- Nhận thay đổi bằng frame differencing, dHash, region detection và debounce.
- Bỏ qua thay đổi nhỏ như con trỏ; đợi trang ổn định trước OCR.
- PaddleOCR 3.x chạy CPU, model PP-OCRv5 mobile/server, hỗ trợ English, Chinese, Japanese và Korean theo compatibility model.
- Group dòng OCR thành đoạn, giữ thứ tự và bounding box.
- Bộ dịch offline Anh → Việt được đóng gói sẵn, không cần tài khoản, API key hay Internet.
- Model OCR và dịch được nạp ở lần dịch đầu rồi giữ trong bộ nhớ; không nạp lại ở mỗi vòng quét.
- PaddleOCR luôn được khởi tạo và sử dụng trên cùng một thread native cố định để tránh crash Windows.
- Ứng dụng giữ worker đến khi Qt giao kết quả về UI và chờ inference kết thúc an toàn khi đóng.
- Nếu Windows GDI/BitBlt không chụp được màn hình, app tự chuyển sang backend Qt thay vì dừng pipeline.
- Dò chữ trên khung 960 px và nhận dạng theo batch để giảm độ trễ CPU; tọa độ overlay vẫn theo ảnh gốc.
- Sau lần quét đầu, OCR chỉ xử lý vùng màn hình vừa thay đổi và giữ nguyên overlay ở vùng còn lại.
- DeepL API và Google Cloud Translation API vẫn có thể chọn khi cần.
- Timeout, retry exponential backoff, xử lý rate limit, batch và giới hạn hàng đợi.
- SQLite cache/history/session/API usage với 5 bảng theo đặc tả.
- API key trong Windows Credential Manager; không lưu plaintext trong SQLite/log.
- Overlay đa màn hình, click-through, không chiếm focus, scale tọa độ physical/logical cho DPI.
- Khung overlay ánh xạ độc lập hai cạnh, giới hạn trong đúng màn hình để giảm sai lệch DPI.
- Overlay, cửa sổ chính và floating controller được loại khỏi screen capture bằng `WDA_EXCLUDEFROMCAPTURE`; overlay luôn ẩn trong vài mili-giây lúc chụp để backend Qt không OCR lại bản dịch.
- Kết quả đã xử lý được hiển thị ngay cả trên màn hình động; generation cũ bị hủy khi Pause/Stop và vùng thay đổi được cập nhật ở chu kỳ sau.
- Nút điều khiển đổi màu/chữ rõ ràng cho Đang dịch, Đang xử lý, Tạm dừng và Tiếp tục.
- Floating Controller, Pause/Resume, Clear Overlay và Force Retranslate.
- Bốn global Windows hotkey, có thông báo khi đăng ký bị xung đột.
- Danh sách process nhạy cảm được loại trừ; mặc định gồm 1Password, Bitwarden và KeePass.
- Lịch sử có tìm kiếm, sao chép, xóa, xuất TXT/JSON; cache có thể tắt/xóa.

## Yêu cầu

- Windows 10/11 64-bit.
- Bản phát hành trong `dist` không cần Python, API key hoặc kết nối mạng cho cấu hình mặc định.
- Chỉ cần Python 3.11/3.12 nếu chạy từ mã nguồn hoặc tự build.

Python 3.13 không được script tự động chọn vì tương thích wheel OCR/native chưa đồng đều.

## Cài đặt

Mở PowerShell tại thư mục dự án:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1 -Dev
```

Script tạo `.venv` riêng và không cài gì vào Python hệ thống. Model mặc định đã nằm trong dự án/bản phát hành.

## Chạy bản hoàn chỉnh

Cách dễ nhất là mở:

```text
dist\LiveScreenTranslatorPro\LiveScreenTranslatorPro.exe
```

Hoặc double-click `run.cmd`; file này sẽ ưu tiên mở bản EXE đã build. Không cần chạy `setup.ps1`, nhập API key hay cài thêm thành phần nào.

Khi phát triển từ mã nguồn, có thể dùng PowerShell:

```powershell
.\scripts\run.ps1
```

Cũng có thể chạy trực tiếp:

```powershell
.\.venv\Scripts\python.exe -m app.main
```

## Dịch offline và API tùy chọn

Ứng dụng mặc định chọn **Offline tích hợp** và cặp **English → Tiếng Việt**. Chỉ cần bấm **Bắt đầu dịch**.

Nếu muốn dùng dịch vụ online, trong ứng dụng:

1. Mở **Dịch thuật** và chọn DeepL hoặc Google Cloud Translation.
2. Nhập API key.
3. Chọn ngôn ngữ đích và bấm **Lưu cài đặt**.
4. Bấm **Kiểm tra kết nối**.

Key được ghi vào Windows Credential Manager. Có thể dùng biến môi trường thay thế:

```text
LST_DEEPL_API_KEY=...
LST_GOOGLE_API_KEY=...
```

Không đưa key thật vào `.env.example` hay bản phát hành.

## Sử dụng dịch màn hình

1. Giữ cấu hình mặc định English → Tiếng Việt.
2. Mở ebook/PDF/website cần đọc rồi bấm **Bắt đầu dịch**.
3. App chờ màn hình ổn định, OCR cục bộ, kiểm tra cache, dịch phần mới và cập nhật overlay.
4. Có thể cuộn/chuyển trang bình thường. Không cần bấm dịch lại mỗi trang.

Khi không có thay đổi, không có lượt OCR/dịch mới. Khi Pause/Stop, app ngừng chụp ngay và bỏ kết quả generation cũ.

Global hotkeys mặc định:

- `Ctrl+Alt+T`: Start/Stop.
- `Ctrl+Alt+P`: Pause/Resume.
- `Ctrl+Alt+R`: Force Retranslate.
- `Ctrl+Alt+H`: Ẩn/hiện translation overlay.

Có thể đổi chúng trong `.env` bằng `LST_HOTKEY_TOGGLE`, `LST_HOTKEY_PAUSE`, `LST_HOTKEY_RETRANSLATE`, `LST_HOTKEY_OVERLAY`.

## Quyền riêng tư

- App không tự Start khi mở.
- Ảnh chụp không được ghi xuống đĩa và không gửi tới provider.
- Ở chế độ mặc định, OCR và dịch đều chạy cục bộ, không gửi văn bản hay ảnh ra ngoài.
- Nếu chủ động chọn DeepL/Google, chỉ chuỗi OCR cần dịch được gửi tới provider đã chọn.
- Log không chứa ảnh, OCR text hay API key.
- Có thể tắt lưu lịch sử, tắt cache và xóa từng kho dữ liệu.
- Process trong “Ứng dụng loại trừ” được phát hiện qua foreground window và không bị capture/OCR.

## Test

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check app tests
```

Bộ test kiểm tra capture, change/scroll detection, cursor noise, OCR parser/layout, cache/history, provider order/network error, stale-page cancellation, DPI 150%, monitor tọa độ âm, overlay, hotkey parser, Pause/Resume và UI smoke test.

## Build EXE

```powershell
.\scripts\build.ps1
```

Script chạy test, đóng gói icon, model OCR English, model dịch Anh → Việt và các runtime native cần thiết rồi tạo:

```text
dist\LiveScreenTranslatorPro\LiveScreenTranslatorPro.exe
```

Có thể double-click file EXE trên để chạy bản đóng gói. Chế độ tự kiểm tra
không gọi API online, đồng thời kiểm tra OCR và dịch offline bằng lệnh:

```powershell
Start-Process .\dist\LiveScreenTranslatorPro\LiveScreenTranslatorPro.exe `
  -ArgumentList '--self-test', '.\build\self-test.json' -Wait
Get-Content .\build\self-test.json
```

Model OCR English mặc định và model dịch offline được nhúng trong thư mục phát hành. Ở lần dùng đầu, model OCR được tự sao chép vào thư mục dữ liệu cục bộ; không có thao tác cài đặt hoặc tải mạng. Không có API key cá nhân trong build.

## Dữ liệu cục bộ

```text
%LOCALAPPDATA%\LiveScreenTranslatorPro\
  livescreen.db
  settings.json
  logs\app.log
  models\
```

Các bảng SQLite:

- `translation_history`
- `translation_cache`
- `application_settings`
- `translation_sessions`
- `api_usage`

## Giới hạn còn lại

- Bộ dịch offline tích hợp hiện hỗ trợ English → Tiếng Việt. Các cặp khác cần chọn DeepL/Google và API key riêng.
- Cần API key cá nhân để chạy integration test trực tiếp với DeepL/Google; test tự động không phát sinh phí.
- oneDNN bị tắt trên PaddlePaddle 3.3.1/Windows vì lỗi runtime PIR; CPU inference ổn định nhưng chậm hơn cấu hình MKL tối ưu.
- Việc tái tạo nền ảnh phức tạp chỉ là ước lượng màu viền; fallback bán trong suốt được dùng khi nền không đồng nhất.
- Bản dịch dài có thể phải giảm font xuống 8px; chưa có bảng đọc mở rộng riêng.
- Mapping đa màn hình dựa trên thứ tự monitor Windows của MSS và Qt; đã có unit test cho DPI/tọa độ âm nhưng cần kiểm thử thêm trên cấu hình nhiều màn hình vật lý khác DPI.
- Request HTTP đang chạy không thể bị hệ điều hành hủy giữa socket call; app bỏ mọi kết quả cũ và kiểm tra màn hình trước khi gửi để giảm request thừa.

