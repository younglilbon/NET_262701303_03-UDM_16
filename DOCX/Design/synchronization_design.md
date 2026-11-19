# TÀI LIỆU THIẾT KẾ ĐỒNG BỘ HÓA (TV5 - SYNCHRONIZATION)

## 1. Mô hình trạng thái trận đấu (`GameState`)
- `room_id`: Mã phòng đấu.
- `status`: Trạng thái trận (`WAITING`, `PLAYING`, `PAUSED`, `FINISHED`).
- `players`: Dictionary lưu tên người chơi `{"X": player_x, "O": player_o}`.
- `spectators`: Tập hợp (`set`) lưu danh sách khán giả đang xem phòng.
- `board`: Ma trận 2 chiều `15x15` lưu trạng thái quân cờ (`""`, `"X"`, `"O"`).

## 2. Sơ đồ luồng đồng bộ nước đi và Khán giả
```mermaid
sequenceDiagram
    autonumber
    actor PX as Client X
    actor PO as Client O
    actor SP as Client Khán Giả
    participant SV as Server (SyncManager - TV5)

    PX->>SV: Gửi nước đi (row=2, col=2)
    SV->>SV: Cập nhật GameState & đổi lượt sang O
    SV->>PX: Broadcast SYNC_MOVE 
    SV->>PO: Broadcast SYNC_MOVE 

    Note over SP,SV: Khán giả vào giữa trận
    SP->>SV: Yêu cầu xem phòng
    SV->>SP: Gửi riêng SYNC_FULL_STATE (Toàn bộ bàn cờ hiện tại)
    SV->>PX: Broadcast SPECTATOR_JOINED
```

## 3. Luồng xử lý Mất kết nối và Kết nối lại (Reconnect)
```mermaid
sequenceDiagram
    autonumber
    actor PX as Client X
    actor PO as Client O (Mất mạng)
    participant SV as Server (TV5)

    PO--xSV: Ngắt kết nối đột ngột
    SV->>SV: Chuyển trạng thái phòng sang PAUSED (Đếm ngược)
    SV->>PX: Gửi PLAYER_DISCONNECTED (Tạm dừng chờ PO)

    PO->>SV: Kết nối lại trong thời gian cho phép
    SV->>PO: Gửi riêng SYNC_FULL_STATE (Khôi phục bàn cờ)
    SV->>PX: Broadcast PLAYER_RECONNECTED (Tiếp tục)
```