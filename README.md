# NET_262701303_03-UDM_16

**Đồ án môn Lập trình mạng**  
Nhóm NET_262701303_03 · Đề tài UDM_16: **Game Caro trực tuyến**

## Cấu trúc repository

Code/
├── Client/
│   ├── GUI/
│   ├── Game/
│   ├── Network/
│   └── Room/
├── Server/
│   ├── Network/
│   ├── User_Lobby/
│   ├── Room_Match/
│   ├── Game_Engine/
│   ├── Synchronization/
│   └── History/
├── Shared/
│   ├── Models/
│   └── Protocol/
└── Tests/
    ├── Unit/
    ├── Integration/
    └── Performance/

DOCX/

Extra/

PPTX/


### Thông tin và yêu cầu đề tài

| Nội dung | Chi tiết |
| --- | --- |
| Mã đề tài | UDM_16 |
| Số nhóm tối đa | 2 |
| Mô tả | Game Caro nhiều người chơi qua Server, hỗ trợ phòng đấu và đồng bộ trạng thái trận đấu. |

Các chức năng cần đáp ứng:

- Client kết nối Server và xem danh sách người chơi đang online.
- Người chơi gửi, chấp nhận hoặc từ chối lời mời thách đấu.
- Server quản lý nhiều trận đấu đồng thời trong các phòng riêng biệt.
- Server kiểm tra tính hợp lệ của nước đi và xác định kết quả thắng, thua hoặc hòa.
- Mỗi lượt có giới hạn thời gian; hết giờ được xử lý theo luật nhóm công bố.
- Người chơi có thể kết nối lại và tiếp tục trận đấu trong khoảng thời gian cho phép.
- Server lưu lịch sử và kết quả các trận đấu.
- Người dùng xem được danh sách trận đang diễn ra và tham gia phòng với vai trò khán giả.
- Khán giả vào giữa trận nhận trạng thái hiện tại, sau đó nhận cập nhật bàn cờ và thời gian theo thời gian thực.
- Server phân biệt người chơi và khán giả; khán giả chỉ được xem, không được đi nước hoặc thay đổi trạng thái trận đấu.
- Khán giả có thể rời phòng mà không ảnh hưởng đến trận đấu.

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
