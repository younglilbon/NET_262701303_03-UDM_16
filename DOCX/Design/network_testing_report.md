# BÁO CÁO KIỂM THỬ TẦNG MẠNG & TỔNG KẾT GIAI ĐOẠN 5–6 (TV1)

**Phạm vi:** `Code/Shared/Protocol/messages.py`, `Code/Server/Network/tcp_server.py`, `Code/Client/Network/tcp_client.py`  
**Bộ kiểm thử:** `Code/Tests/Unit/test_protocol.py`, `Code/Tests/Integration/test_network_tcp.py`, `Code/Tests/Performance/test_network_load.py`

---

## 1. Bảng kết quả kiểm thử nghiệm thu

| Mã ca | Tình huống kiểm thử | File test thực thi | Kết quả mong đợi | Kết quả thực tế | Trạng thái |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **UT-01** | Mã hóa/giải mã Unicode, kiểm tra biên `1.000.000` byte, thiếu `type`, thiếu `\n`, JSON/UTF-8 lỗi | `Code/Tests/Unit/test_protocol.py` | Phân tách đúng mã lỗi `INVALID_JSON`, `INVALID_MESSAGE`, `MESSAGE_TOO_LARGE` | Toàn bộ 7 unit test chạy đạt, đúng mã lỗi | **ĐẠT** |
| **T19** | Gửi gói tin chia nhỏ từng mảnh (fragmented), gửi gộp nhiều gói (coalesced), gửi byte UTF-8/JSON hỏng, gửi gói > 1MB và ngắt kết nối đột ngột | `Code/Tests/Integration/test_network_tcp.py` | Server ghép/tách đúng dòng `\n`, trả lỗi đúng chuẩn, đóng kết nối vi phạm và không ảnh hưởng client khác | Client hợp lệ vẫn hoạt động bình thường, khóa gửi được giải phóng sạch | **ĐẠT** |
| **T13** | Nhập sai tên đăng nhập sau đó sửa lại; server đóng kết nối đột ngột | `Code/Tests/Integration/test_network_tcp.py` | Client thử kết nối/đăng nhập lại được; nhận `CONNECTION_ERROR` khi server đóng kết nối | Đăng nhập lại thành công; nhận đủ sự kiện mất kết nối | **ĐẠT** |
| **T22** | Chạy đồng thời **3 phòng, 6 người chơi và 2 khán giả** qua TCP thật | `Code/Tests/Performance/test_network_load.py` | Các phòng hoạt động độc lập, không lẫn bàn cờ/lượt, độ trễ thấp | Đồng bộ chính xác 100% nước đi tới từng phòng và khán giả | **ĐẠT** |

---

## 2. Lệnh chạy kiểm thử xác nhận

Chạy lần lượt các lệnh sau tại thư mục gốc dự án (`NET_262701303_03-UDM_16`):

```bash
python -m unittest Code/Tests/Unit/test_protocol.py -v
python -m unittest Code/Tests/Integration/test_network_tcp.py -v
python -m unittest Code/Tests/Performance/test_network_load.py -v
