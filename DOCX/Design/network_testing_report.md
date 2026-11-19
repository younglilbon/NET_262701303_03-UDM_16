# BÁO CÁO KIỂM THỬ VÀ XỬ LÝ NGOẠI LỆ TẦNG MẠNG - TV1

**Tập tin liên quan:** `Code/Server/Network/tcp_server.py`, `Code/Client/Network/tcp_client.py`

### 1. Tổng quan mục tiêu và phạm vi kiểm thử trong giai đoạn 5
Trong giai đoạn này, nhiệm vụ trọng tâm của thành viên phụ trách tầng mạng (TV1) không phải là phát triển tính năng mới từ đầu, mà chuyển dịch sang giai đoạn kiểm định độ bền vững (robustness), khả năng chịu tải cục bộ và cơ chế xử lý ngoại lệ mạng. Mục tiêu là đảm bảo hạ tầng kết nối giữa Server và các Client hoạt động mượt mà, hạn chế tối đa các sự cố sập hệ thống (crash) do mất kết nối đột ngột hoặc do client gửi dữ liệu không đúng chuẩn định dạng đã thống nhất trong giao thức chung của nhóm.

### 2. Chi tiết các hạng mục đã triển khai, rà soát và kiểm định
1. **Xử lý ngoại lệ ngắt kết nối đột ngột (Connection Exception Management):**
   - Rà soát toàn bộ vòng lặp xử lý tiến trình kết nối tại module `tcp_server.py` và `_ClientHandler`.
   - Cấu hình các cơ chế bắt lỗi phần cứng và mạng tầng giao vận như `ConnectionResetError` và `BrokenPipeError`. 
   - Khi một client đột ngột ngắt kết nối ngang chừng (ví dụ người dùng tắt ứng dụng đột ngột hoặc bấm hủy tiến trình bằng lệnh `Ctrl + C` trên terminal), server không bị dừng đột ngột mà sẽ tự động kích hoạt phương thức `finish()`. Tại đây, hệ thống gọi hàm `disconnect(self.request)` để giải phóng tài nguyên socket và thu hồi bảng ánh xạ kết nối một cách sạch sẽ, không ảnh hưởng đến các client khác đang duy trì phiên chơi.

2. **Kiểm tra và xác thực định dạng thông điệp (Message Parsing & Ca kiểm thử T19):**
   - Kiểm tra kỹ lưỡng cơ chế giải mã chuỗi byte thành định dạng JSON dựa trên hàm `decode_message` và hằng số giới hạn dung lượng `MAX_MESSAGE_BYTES`.
   - Thiết lập các điều kiện chặn và trả về mã lỗi tiêu chuẩn (như `INVALID_JSON` hoặc `MESSAGE_TOO_LARGE`) khi phát hiện gói tin gửi đến bị sai cấu trúc cú pháp, thiếu ký tự kết thúc dòng `\n`, hoặc vượt quá kích thước cho phép. Điều này giúp ngăn chặn hoàn toàn các trường hợp gói tin rác hoặc dữ liệu lỗi làm gián đoạn luồng xử lý chính của server.

3. **Đảm bảo an toàn đa luồng và đồng bộ (Thread Safety):**
   - Duy trì và kiểm tra cơ chế khóa luồng `threading.Lock` trong quá trình truyền tải dữ liệu qua lại giữa các socket độc lập.
   - Cơ chế này giúp bảo vệ vùng nhớ và tiến trình gửi tin nhắn đồng thời, ngăn chặn triệt để tình trạng xung đột dữ liệu (data race) khi có nhiều client cùng gửi yêu cầu hoặc nhận phản hồi trong cùng một thời điểm.

### 3. Kết quả kiểm thử thực tế và đánh giá độ ổn định
- **Vận hành Server:** Khởi động thành công, lắng nghe và tiếp nhận kết nối ổn định trên cổng tiêu chuẩn `8888` (`0.0.0.0:8888`) mà không phát sinh lỗi ngoại lệ hay cảnh báo đỏ trên console.
- **Kịch bản ngắt kết nối thực tế:** Tiến hành mô phỏng ngắt kết nối client liên tục trong quá trình chạy thử nghiệm; hệ thống phản hồi chính xác, tự động dọn dẹp kết nối cũ và giữ vững trạng thái sẵn sàng cho các kết nối tiếp theo.
- **Kết luận:** Tầng mạng đã đạt yêu cầu kỹ thuật đề ra cho Giai đoạn 5, đảm bảo độ tin cậy và sẵn sàng tích hợp hoàn chỉnh cùng các module giao diện (GUI), quản lý phòng (Room) và đồng bộ trạng thái (Sync) của toàn bộ thành viên.
