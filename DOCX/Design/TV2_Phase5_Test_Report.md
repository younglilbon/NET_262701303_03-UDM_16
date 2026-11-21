# BÁO CÁO GIAI ĐOẠN 5 — TV2 USER & LOBBY

## 1. Phạm vi TV2
Giai đoạn 5 kiểm tra phần danh tính người chơi, danh sách trực tuyến và lời mời đấu do TV2 phụ trách:

- Đăng nhập, kiểm tra tên hợp lệ và danh sách người chơi trực tuyến.
- Trạng thái `ONLINE`, `INVITE_PENDING`, `IN_ROOM` và `OFFLINE`.
- Gửi lời mời qua TCP; người nhận chấp nhận hoặc từ chối lời mời.
- Chấp nhận lời mời tạo/lập trận; từ chối hoặc hủy khôi phục người chơi về lobby.
- Bảo vệ người chơi đang chờ lời mời khỏi tạo hoặc tham gia phòng khác.

## 2. Cách chạy

```powershell
python Code/Tests/run_tv2_phase5_tests.py
```

Hoặc sử dụng unittest discovery:

```powershell
python -m unittest discover -s Code/Tests -t . -v
```

## 3. Kết quả xác minh

Ngày kiểm thử: 21/11/2026.

- Phạm vi báo cáo gồm đúng 6 testcase TV2 thuộc unit test và kiểm thử TCP.
- Bộ test TV2 được chạy độc lập bằng runner dành riêng.
- Lời mời: server gửi kết quả `INVITE_RESULT` cho cả hai bên; khi chấp nhận tạo phòng và bắt đầu trận, khi từ chối khôi phục cả hai về lobby.
- Giao diện người mời: hiển thị popup và thanh trạng thái khi đối phương từ chối.
- Danh sách trực tuyến và trạng thái người chơi được kiểm thử qua unit test và TCP socket integration.

## 4. Checklist nghiệm thu Giai đoạn 5 của TV2

- [x] Hai người đăng nhập và xem cùng danh sách người chơi trực tuyến.
- [x] Tên người chơi hợp lệ, duy nhất và không phân biệt hoa thường.
- [x] Gửi lời mời qua TCP đến người chơi đang online.
- [x] Chấp nhận lời mời chuyển hai người vào trận.
- [x] Từ chối lời mời trả cả hai người về lobby.
- [x] Hiển thị thông báo khi người được mời từ chối ở phía người gửi.
- [x] Người đang chờ lời mời không thể tạo hoặc tham gia phòng.
- [x] Trạng thái lobby được khôi phục sau khi từ chối hoặc hủy lời mời.
- [x] Chạy bộ test TV2 bằng một lệnh duy nhất.
