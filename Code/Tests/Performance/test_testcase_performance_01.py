import csv
import queue
import socket
import threading
import time
from pathlib import Path

from Code.Shared.Protocol.messages import encode_message, decode_message


HOST = "127.0.0.1"
PORT = 8888
PLAYER_X = "PF01_PlayerX"
PLAYER_O = "PF01_PlayerO"
ROOM_NAME = "TC_PF_01"
TURN_LIMIT_SECONDS = 600
TOTAL_MOVES = 100
WAIT_TIMEOUT_SECONDS = 15

RESULT_FILE = (
    Path(__file__).resolve().parent / "TC_PF_01_results.csv"
)


class TestClient:
    def __init__(self, username: str):
        self.username = username
        self.sock = socket.create_connection(
            (HOST, PORT), timeout=WAIT_TIMEOUT_SECONDS
        )
        self.sock.settimeout(None)
        self.reader = self.sock.makefile("rb")
        self.messages = queue.Queue()
        self.send_lock = threading.Lock()
        self.closed = False

        self.reader_thread = threading.Thread(
            target=self._read_loop,
            daemon=True,
        )
        self.reader_thread.start()

    def _read_loop(self):
        try:
            while True:
                raw = self.reader.readline(1_000_001)
                if not raw:
                    self.messages.put(
                        ({"type": "_CONNECTION_CLOSED"}, time.perf_counter_ns())
                    )
                    return

                received_ns = time.perf_counter_ns()
                try:
                    message = decode_message(raw)
                except Exception as exc:
                    self.messages.put(
                        (
                            {
                                "type": "_READ_ERROR",
                                "message": str(exc),
                            },
                            received_ns,
                        )
                    )
                    return

                self.messages.put((message, received_ns))
        except OSError as exc:
            self.messages.put(
                (
                    {
                        "type": "_READ_ERROR",
                        "message": str(exc),
                    },
                    time.perf_counter_ns(),
                )
            )

    def send(self, message: dict):
        payload = encode_message(message)
        with self.send_lock:
            self.sock.sendall(payload)

    def wait_for(self, predicate, description: str, timeout=WAIT_TIMEOUT_SECONDS):
        deadline = time.monotonic() + timeout

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(
                    f"{self.username}: het thoi gian cho {description}"
                )

            try:
                message, received_ns = self.messages.get(timeout=remaining)
            except queue.Empty:
                raise TimeoutError(
                    f"{self.username}: het thoi gian cho {description}"
                )

            msg_type = message.get("type")

            if msg_type == "ERROR":
                raise RuntimeError(
                    f"Server tra ERROR cho {self.username}: {message}"
                )
            if msg_type in ("_CONNECTION_CLOSED", "_READ_ERROR"):
                raise ConnectionError(
                    f"{self.username}: ket noi loi: {message}"
                )

            if predicate(message):
                return message, received_ns

    def wait_type(self, message_type: str):
        return self.wait_for(
            lambda message: message.get("type") == message_type,
            message_type,
        )[0]

    def wait_for_both_start_events(self, room_id: str):
        """Nhan ca ROOM_STARTED va snapshot, khong phu thuoc thu tu gui."""
        pending = {"ROOM_STARTED", "SYNC_FULL_STATE"}
        deadline = time.monotonic() + WAIT_TIMEOUT_SECONDS

        while pending:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(
                    f"{self.username}: het thoi gian cho su kien bat dau tran"
                )
            try:
                message, _ = self.messages.get(timeout=remaining)
            except queue.Empty:
                raise TimeoutError(
                    f"{self.username}: het thoi gian cho su kien bat dau tran"
                )

            msg_type = message.get("type")
            if msg_type == "ERROR":
                raise RuntimeError(
                    f"Server tra ERROR cho {self.username}: {message}"
                )
            if msg_type in ("_CONNECTION_CLOSED", "_READ_ERROR"):
                raise ConnectionError(
                    f"{self.username}: ket noi loi: {message}"
                )
            if msg_type == "ROOM_STARTED":
                pending.discard("ROOM_STARTED")
            elif (
                msg_type == "SYNC_FULL_STATE"
                and message.get("room_id") == room_id
            ):
                pending.discard("SYNC_FULL_STATE")

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass
        try:
            self.reader.close()
        except OSError:
            pass


def creates_five_in_a_row(board, row, col, symbol):
    """Kiem tra nuoc di co tao thanh 5 quan lien tiep hay khong."""
    directions = (
        (0, 1),   # ngang
        (1, 0),   # doc
        (1, 1),   # cheo xuong
        (1, -1),  # cheo len
    )
    size = len(board)

    for dr, dc in directions:
        count = 1

        for sign in (-1, 1):
            r = row + sign * dr
            c = col + sign * dc

            while (
                0 <= r < size
                and 0 <= c < size
                and board[r][c] == symbol
            ):
                count += 1
                r += sign * dr
                c += sign * dc

        if count >= 5:
            return True

    return False


def choose_safe_move(board, symbol):
    """Chon o trong dau tien khong lam tran dau ket thuc som."""
    size = len(board)

    for row in range(size):
        for col in range(size):
            if board[row][col] != "":
                continue

            board[row][col] = symbol
            wins = creates_five_in_a_row(board, row, col, symbol)
            board[row][col] = ""

            if not wins:
                return row, col

    raise RuntimeError("Khong tim duoc nuoc di an toan tren ban co.")


def prepare_match(client_x, client_o):
    # Dang nhap hai client
    client_x.send({"type": "LOGIN", "name": PLAYER_X})
    client_o.send({"type": "LOGIN", "name": PLAYER_O})

    login_x = client_x.wait_type("LOGIN_RESULT")
    login_o = client_o.wait_type("LOGIN_RESULT")

    if login_x.get("status") != "OK" or login_o.get("status") != "OK":
        raise RuntimeError(
            f"Dang nhap khong thanh cong: X={login_x}, O={login_o}"
        )

    client_x.send({
        "type": "CREATE_ROOM",
        "name": ROOM_NAME,
        "time_limit": TURN_LIMIT_SECONDS,
    })
    created = client_x.wait_type("ROOM_CREATED")
    room = created.get("room", {})
    room_id = room.get("room_id")

    if not room_id:
        raise RuntimeError(
            f"ROOM_CREATED khong co room_id hop le: {created}"
        )

    client_o.send({
        "type": "JOIN_ROOM",
        "room_id": room_id,
    })
    client_o.wait_type("ROOM_JOINED")

    client_x.send({
        "type": "START_MATCH",
        "room_id": room_id,
    })

    for client in (client_x, client_o):
        client.wait_for_both_start_events(room_id)

    return room_id


def main():
    client_x = None
    client_o = None
    samples = []

    try:
        print(f"Ket noi Server {HOST}:{PORT} ...")
        client_x = TestClient(PLAYER_X)
        client_o = TestClient(PLAYER_O)

        room_id = prepare_match(client_x, client_o)
        print(f"Da tao tran. Room ID: {room_id}")
        print(f"Bat dau do {TOTAL_MOVES} nuoc di ...")

        board = [["" for _ in range(15)] for _ in range(15)]

        for move_number in range(1, TOTAL_MOVES + 1):
            symbol = "X" if move_number % 2 == 1 else "O"
            sender = client_x if symbol == "X" else client_o
            receiver = client_o if symbol == "X" else client_x

            row, col = choose_safe_move(board, symbol)
            board[row][col] = symbol

            t1_ns = time.perf_counter_ns()
            sender.send({
                "type": "MOVE",
                "row": row,
                "col": col,
            })

            expected_move_number = move_number
            _, t2_ns = receiver.wait_for(
                lambda msg: (
                    msg.get("type") == "SYNC_MOVE"
                    and msg.get("room_id") == room_id
                    and isinstance(msg.get("move"), dict)
                    and msg["move"].get("move_number") == expected_move_number
                    and msg["move"].get("row") == row
                    and msg["move"].get("col") == col
                    and msg["move"].get("symbol") == symbol
                ),
                f"SYNC_MOVE move_number={move_number}",
            )

            latency_ms = (t2_ns - t1_ns) / 1_000_000
            samples.append({
                "move_number": move_number,
                "sender": sender.username,
                "receiver": receiver.username,
                "symbol": symbol,
                "row": row,
                "col": col,
                "latency_ms": f"{latency_ms:.3f}",
            })

            if move_number % 10 == 0:
                print(
                    f"Da do {move_number}/{TOTAL_MOVES} nuoc - "
                    f"mau gan nhat: {latency_ms:.3f} ms"
                )

        latencies = [float(item["latency_ms"]) for item in samples]
        average_ms = sum(latencies) / len(latencies)
        min_ms = min(latencies)
        max_ms = max(latencies)

        with RESULT_FILE.open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=[
                    "move_number",
                    "sender",
                    "receiver",
                    "symbol",
                    "row",
                    "col",
                    "latency_ms",
                ],
            )
            writer.writeheader()
            writer.writerows(samples)

        print("\n========== KET QUA TC_PF_01 ==========")
        print(f"So mau do duoc : {len(samples)}")
        print(f"Trung binh     : {average_ms:.3f} ms")
        print(f"Nho nhat       : {min_ms:.3f} ms")
        print(f"Lon nhat       : {max_ms:.3f} ms")
        print(f"Nguong tham khao: 100 ms")
        print(
            "Danh gia theo nguong: "
            + ("DAT" if average_ms < 100 else "KHONG DAT")
        )
        print(f"CSV             : {RESULT_FILE}")

    except Exception as exc:
        print(f"\nKIEM THU THAT BAI / KHONG HOAN TAT: {exc}")
        print("Khong ket luan PASS neu chua thu du 100 mau.")
        raise

    finally:
        if client_x is not None:
            client_x.close()
        if client_o is not None:
            client_o.close()


if __name__ == "__main__":
    main()