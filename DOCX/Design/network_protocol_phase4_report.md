# ĐẶC TẢ KIẾN TRÚC MẠNG & GIAO THỨC TRUYỀN THÔNG (TV1)

**Đề tài:** Game Caro trực tuyến (UDM_16)  
**Thành viên phụ trách:** TV1 — Network & Protocol  
**Phiên bản:** Đồng bộ theo *Quyết định tích hợp v1.0*

---

## 1. Kiến trúc mạng Client–Server

Hệ thống sử dụng mô hình **TCP Client–Server tập trung (Authoritative Server)** trên cổng mặc định `8888`:

* **Phía Server (`Code/Server/Network/tcp_server.py`):**
  * Kế thừa `socketserver.ThreadingTCPServer` (`allow_reuse_address = True`, `daemon_threads = True`), mỗi kết nối Client được phục vụ bởi một luồng `_ClientHandler` độc lập.
  * Sử dụng `threading.Lock` riêng cho từng socket (`_send_locks`) để đảm bảo an toàn đa luồng khi nhiều sự kiện broadcast gửi đồng thời tới cùng một client; tự động thu hồi khóa khi ngắt kết nối.
  * Bắt ngoại lệ `OSError` độc lập trên từng socket để lỗi gửi tới một client không làm gián đoạn quá trình cập nhật trạng thái hoặc gửi tin tới các thành viên khác.
  * Đảm bảo sự kiện `application.disconnect(connection)` chỉ được kích hoạt **duy nhất một lần** cho mỗi kết nối mất.
* **Phía Client (`Code/Client/Network/tcp_client.py`):**
  * Quản lý kết nối TCP qua một luồng nền (`daemon=True`) đọc luồng byte liên tục từ server và chuyển message đã giải mã lên `CaroApp` (`app.py`).
  * Chuyển mọi tình huống mất kết nối hoặc EOF ngoài dự kiến từ server thành sự kiện `{"type": "CONNECTION_ERROR", "code": "CONNECTION_CLOSED", "message": ...}` để GUI cập nhật trạng thái ngay lập tức.
  * Hỗ trợ tự động đóng/reset sạch socket cũ khi người dùng kết nối lại sau lỗi đăng nhập.

---

## 2. Quy chuẩn đóng gói & phân tách gói tin (Framing)

* **Định dạng:** JSON mã hóa `UTF-8`, mỗi thông điệp là một JSON Object nằm trên **một dòng duy nhất**, kết thúc bằng ký tự xuống dòng `\n` (Newline-delimited JSON).
* **Bắt buộc:** Mọi gói tin hợp lệ phải có trường `"type"` kiểu chuỗi không rỗng.
* **Giới hạn kích thước:** Tối đa **`1.000.000` byte** (`MAX_MESSAGE_BYTES = 1_000_000`, tính cả ký tự `\n`).
* **Xử lý dòng TCP:** Phía nhận sử dụng `readline(MAX_MESSAGE_BYTES + 1)` để tự động ghép các gói tin bị phân mảnh (fragmented) và tách các gói tin dính chùm (coalesced) theo đúng ranh giới `\n`.

---

## 3. Danh mục thông điệp & Mã lỗi chuẩn

### 3.1. Thông điệp Client → Server
| `type` | Trường dữ liệu chính | Mô tả |
| :--- | :--- | :--- |
| `LOGIN` | `name: str` | Đăng nhập với tên 3–20 ký tự |
| `LOGOUT` | *(không)* | Đăng xuất và rời phòng hiện tại (nếu có) |
| `PLAYER_LIST` | *(không)* | Lấy danh sách người chơi đang kết nối |
| `INVITE` | `target: str` | Gửi lời mời đấu tới người chơi đang `ONLINE` |
| `INVITE_RESPONSE` | `invite_id: str, accepted: bool` | Phản hồi lời mời đấu |
| `CREATE_ROOM` | `name: str, time_limit: int` | Tạo phòng mới (thời gian lượt 5–600s, mặc định 30s) |
| `LIST_ROOMS` | `only_playing: bool` | Lấy danh sách phòng hiện có |
| `JOIN_ROOM` | `room_id: str` | Tham gia phòng với vai trò người chơi |
| `JOIN_AS_SPECTATOR` | `room_id: str` | Tham gia phòng với vai trò khán giả |
| `START_MATCH` | `room_id: str` | Chủ phòng bắt đầu ván đấu khi phòng ở trạng thái `READY` |
| `MOVE` | `row: int, col: int` | Gửi tọa độ nước đi (0–14) |
| `LEAVE_ROOM` | *(không)* | Rời khỏi phòng hiện tại |
| `REMATCH` | `room_id: str` | Yêu cầu chơi lại sau khi ván kết thúc |
| `REMATCH_RESPONSE` | `request_id: str, accepted: bool` | Phản hồi yêu cầu chơi lại |

### 3.2. Thông điệp Server → Client
* **Phiên & Sảnh chờ:** `LOGIN_RESULT`, `PLAYER_LIST`, `INVITE`, `INVITE_RESULT`
* **Phòng đấu:** `ROOM_LIST`, `ROOM_CREATED`, `ROOM_JOINED`, `ROOM_UPDATED`, `ROOM_STARTED`, `ROOM_LEFT`, `ROOM_CLOSED`
* **Đồng bộ trận đấu:** `SYNC_FULL_STATE`, `SYNC_MOVE`, `SPECTATOR_JOINED`, `SPECTATOR_LEFT`, `PLAYER_DISCONNECTED`, `PLAYER_RECONNECTED`, `MATCH_FINISHED`
* **Chơi lại & Lỗi:** `REMATCH_REQUEST`, `REMATCH_RESULT`, `ERROR`

### 3.3. Mã lỗi chuẩn (`ERROR.code`)
* **Lỗi tầng mạng & giao thức (TV1):** `INVALID_JSON`, `INVALID_MESSAGE`, `MESSAGE_TOO_LARGE`, `UNKNOWN_MESSAGE`, `LOGIN_REQUIRED`, `INVALID_ARGUMENT`
* **Lỗi nghiệp vụ (TV2–TV5):** `NAME_INVALID`, `NAME_TAKEN`, `ALREADY_LOGGED_IN`, `PLAYER_BUSY`, `INVITATION_NOT_FOUND`, `INVITATION_FORBIDDEN`, `ROOM_NOT_FOUND`, `ROOM_FULL`, `ALREADY_IN_ROOM`, `NOT_IN_ROOM`, `NOT_HOST`, `INVALID_STATE`, `SPECTATOR_FORBIDDEN`, `REMATCH_PENDING`, `REMATCH_NOT_FOUND`, `REMATCH_FORBIDDEN`, `GAME_PAUSED`, `NOT_YOUR_TURN`, `OUT_OF_BOUNDS`, `CELL_OCCUPIED`, `GAME_OVER`
