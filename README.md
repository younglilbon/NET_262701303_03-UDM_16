# NET_262701303_03-UDM_16

**Đồ án môn Lập trình mạng**  
Nhóm NET_262701303_03 · Đề tài UDM_16: **Game Caro trực tuyến**

## Danh sách thành viên

| STT | Họ và tên | MSSV |
| ---: | --- | ---: |
| 1 | Lê Văn Khải | 051206008834 |
| 2 | Trần Nguyễn Hoàng Minh | 083206001369 |
| 3 | Phạm Minh Hiếu | 054206004641 |
| 4 | Trần Quang Huy | 054206009272 |
| 5 | Trần Gia Khiêm | 054206009756 |
| 6 | Lê Minh Như | 077306006704 |

## Phân công công việc

| STT | Thành viên | Phần phụ trách | Công việc chính |
| ---: | --- | --- | --- |
| 1 | Lê Văn Khải | Network & Protocol    | Phân tích và xây dựng kết nối Socket Client–Server; thiết kế Protocol, Message và mã thông điệp; xử lý gửi/nhận dữ liệu, timeout, mất kết nối và lỗi mạng. |
| 2 | Trần Nguyễn Hoàng Minh | User & Lobby | Phân tích và xây dựng chức năng người chơi, đăng nhập, trạng thái Online/Offline, danh sách người chơi trực tuyến và lời mời đấu (gửi, chấp nhận hoặc từ chối). |
| 3 | Phạm Minh Hiếu | Room & Match | Phân tích và xây dựng chức năng tạo, tham gia, rời phòng; danh sách và trạng thái phòng; quản lý người chơi trong phòng, phân chia quân X/O và hỗ trợ người xem. |
| 4 | Trần Quang Huy | Game Engine | Xây dựng bàn cờ và xử lý nước đi, lượt chơi, kiểm tra nước đi hợp lệ, thời gian và kết quả thắng/thua/hòa. |
| 5 | Trần Gia Khiêm | Synchronization | Xây dựng trạng thái trận đấu, đồng bộ và phát thông tin bàn cờ giữa các Client; hỗ trợ người xem, kết nối lại và lưu lịch sử nước đi. |
| 6 | Lê Minh Như | GUI & Testing | Thiết kế giao diện đăng nhập, sảnh chờ, phòng đấu và bàn cờ; hiển thị trạng thái kết nối; lập và thực hiện kiểm thử chức năng, dữ liệu không hợp lệ và hiệu năng. |

Các thành viên cùng phối hợp tích hợp và kiểm thử toàn hệ thống; mỗi người chịu trách nhiệm kiểm thử, sửa lỗi trong phần việc của mình.

## Giới thiệu đề tài

Đề tài xây dựng trò chơi Caro trực tuyến theo mô hình **Client–Server**. Người chơi có thể kết nối qua mạng, đăng nhập, tạo hoặc tham gia phòng đấu và chơi theo lượt. Hệ thống đồng bộ trạng thái bàn cờ theo thời gian thực, đồng thời xử lý các tình huống mất kết nối.

### Thành phần hệ thống

- **Server:** Tiếp nhận kết nối, quản lý người chơi trực tuyến và các phòng đấu, đồng bộ trạng thái trận đấu giữa các Client, đồng thời kiểm tra tính hợp lệ của trò chơi.
- **Client:** Cung cấp giao diện để đăng nhập, xem sảnh chờ (Lobby), tạo hoặc tham gia phòng đấu, thực hiện nước đi và nhận kết quả.

### Chức năng chính

- Kết nối Client–Server, gửi và nhận thông điệp, xử lý lỗi mạng hoặc tình huống người chơi mất kết nối.
- Đăng nhập, quản lý trạng thái người chơi, xem danh sách người chơi trực tuyến và gửi hoặc nhận lời mời đấu.
- Tạo, tham gia hoặc rời phòng; quản lý trạng thái phòng và tự động phân chia quân X/O.
- Hiển thị bàn cờ, xác thực nước đi, đổi lượt và kiểm tra điều kiện thắng, thua hoặc hòa.
- Đồng bộ bàn cờ, gửi thông báo, hỗ trợ chế độ người xem (Spectator) và lưu lịch sử nước đi.
- Cung cấp giao diện (GUI) cho các màn hình đăng nhập, sảnh chờ, phòng đấu và bàn cờ.
