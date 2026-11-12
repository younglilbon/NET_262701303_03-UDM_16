# Tích hợp rời/đóng phòng — TV3

Phần này ghi hành vi đã triển khai, bổ sung cho `room_match_analysis.md`.
Chưa coi đây là nghiệm thu GUI/TCP thật hoặc toàn bộ phương án tích hợp 1.0.

## Luồng hiện tại

1. `ServerApplication._leave_room()` chụp thành viên và snapshot ván trước khi xóa.
2. Người chơi rời ván PLAYING/PAUSED: SyncManager chốt RESIGN một lần theo
   `match_id`; RoomManager chuyển trạng thái phòng rồi gỡ thành viên.
3. Dùng `removed_members` để dọn ánh xạ hoạt động và cập nhật PlayerStatus qua
   API PlayerManager. Người không còn kết nối luôn là OFFLINE.
4. Gỡ người chơi offline không còn quyền giữ chỗ sau kết thúc; khi không còn
   người chơi, giải phóng toàn bộ spectator và đóng trạng thái hoạt động.
5. Sau khi nhả khóa dữ liệu, gửi MATCH_FINISHED nếu có, ROOM_LEFT cho người chủ
   động rời, ROOM_UPDATED cho người còn lại hoặc ROOM_CLOSED/NO_PLAYERS cho các
   thành viên còn kết nối bị đưa ra. Cập nhật ROOM_LIST cho người ở lobby.
6. Spectator rời/mất kết nối không thay timer, lượt hoặc kết quả ván.

## API phối hợp

- TV2: `PlayerManager.connection_for(name)` và `set_status_by_name(name, status)`
  có khóa. Không sửa `Player.status` trực tiếp từ application.
- TV3: `RoomManager.leave_room()` và `detach_disconnected_player()` giữ các khóa
  kết quả cũ, thêm `remaining_members`, `removed_members` là danh sách độc lập.
  Bên gọi xác nhận offline trước khi detach; không dùng detach khi còn giữ chỗ
  reconnect. Detach không quyết định kết quả.
- TV5: `SyncManager.detach_member(room_id, username)` dọn người nhận/ánh xạ hoạt
  động/hạn reconnect; không sửa players đã ghi cho ván.
- TV5: `close_room(room_id)` hủy timer, dọn GameState và ánh xạ; giữ bản ghi chờ
  lưu trong RAM nếu lần ghi thất bại.
- Callback kết thúc hiện nhận **bốn tham số**:
  `on_match_finished(room_id, winner, reason, match_id)`. Application bỏ qua
  callback không thuộc ván hiện hành. Callback chạy sau khi nhả khóa SyncManager.
- `finish_and_save_match()` hỗ trợ `expected_match_id` và `notify_callback=False`
  cho luồng rời phòng đang tự điều phối việc dọn thành viên.

`Coordinator` dùng chung giữa application và SyncManager để tuần tự hóa chuyển
đổi liên module. Message được sao chép và xếp hàng trong chuyển đổi; gửi socket
và ghi lịch sử sau khi nhả khóa điều phối. Mỗi lỗi socket được xử lý riêng.
Lịch sử được chụp độc lập, bảo vệ bằng khóa ghi riêng và thay thế tệp qua tệp tạm;
chỉ đánh dấu đã lưu khi ghi thành công. Chưa có cơ chế tự động thử lưu lại hoặc
khôi phục hàng đợi sau khi server khởi động lại.

## Kiểm chứng và phần tiếp theo

Test bổ sung nằm trong `Code/Tests/Integration/test_server_application.py`:
đóng phòng nhiều spectator, RESIGN PLAYING/PAUSED, dọn offline sau FINISHED,
lỗi gửi từng socket, bảo toàn timer spectator, lưu thất bại khi đóng phòng,
I/O ngoài khóa, callback cũ, start/leave và kết thúc/leave đồng thời.
Các test dùng callback mạng giả và lịch sử trong thư mục tạm.

Còn cần TV6 xử lý ROOM_CLOSED và chỉ về lobby sau xác nhận server. Chưa hoàn
thiện spectator vào PAUSED/FINISHED, giữ thời gian còn lại khi resume,
BOTH_DISCONNECTED/ABORTED, rematch có chấp thuận hoặc toàn bộ trường match_id
trong protocol/GUI. Chưa nghiệm thu các phần đó bằng các test rời/đóng phòng.

## Cập nhật module độc lập ngày 12/11/2026

- `RoomManager.create_room()` kiểm tra mã phòng trong cùng khóa với thao tác
  lưu phòng và ánh xạ người–phòng; sinh lại nếu trùng. Test ép trùng nhiều lần
  xác nhận không mất chủ phòng, X/O, spectator hoặc cấu hình của phòng cũ.
- Bổ sung test cho `RoomManager.rematch()`: chỉ đổi X/O và trạng thái sang READY;
  giữ nguyên room_id, host, name, spectators, time_limit, created_at và ánh xạ.
  Phòng khác không đổi; chủ phòng cầm O vẫn có quyền bắt đầu. Gọi lặp khi READY
  hoặc gọi ở WAITING/READY/PLAYING trả INVALID_STATE và không sửa dữ liệu.
- Các test này xác minh API nội bộ. Không bổ sung lệnh REMATCH/REMATCH_RESPONSE,
  timeout yêu cầu hay GUI; không đánh dấu luồng chơi lại hai bên đồng ý đã xong.
- Sơ đồ trạng thái, tạo/vào, rời/reconnect và rematch hiện hành được nhúng
  trực tiếp trong [room_match_analysis.md](room_match_analysis.md).

Kiểm tra tại workspace ngày 12/11/2026: chạy cả sáu module unittest được README
hướng dẫn (Room, Game Engine, Protocol, GUI message handler, ServerApplication,
Synchronization), **70/70 test đạt**. `git diff --check` không báo lỗi khoảng trắng.
Kết quả áp dụng cho phiên bản workspace lúc kiểm tra. Sơ đồ
Mermaid được nhúng trong tài liệu; chưa xác minh hiển thị bằng trình render hoặc
xuất ảnh. Chưa nghiệm thu GUI thật trong lần cập nhật này.
