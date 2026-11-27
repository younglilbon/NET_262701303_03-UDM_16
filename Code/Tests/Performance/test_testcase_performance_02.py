"""TC_PF_02 - Load test: 50 rooms / 100 TCP clients.
Requires psutil for CPU/RAM measurements:
    python -m pip install psutil
"""

import csv
import os
import queue
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

try:
    import psutil
except ImportError:
    psutil = None

from Code.Shared.Protocol.messages import encode_message, decode_message

HOST = "127.0.0.1"
PORT = 8888
ROOM_COUNT = 50
CLIENTS_PER_ROOM = 2
TOTAL_CLIENTS = ROOM_COUNT * CLIENTS_PER_ROOM
WAIT_TIMEOUT_SECONDS = 30
WORKERS = 25
TURN_LIMIT_SECONDS = 600
BASE_DIR = Path(__file__).resolve().parent
ROOM_RESULT_FILE = BASE_DIR / "TC_PF_02_results.csv"
RESOURCE_RESULT_FILE = BASE_DIR / "TC_PF_02_resources.csv"


class LoadClient:
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
            target=self._read_loop, daemon=True
        )
        self.reader_thread.start()

    def _read_loop(self):
        try:
            while True:
                raw = self.reader.readline(1_000_001)
                if not raw:
                    self.messages.put(({"type": "_CONNECTION_CLOSED"}, time.perf_counter_ns()))
                    return
                received_ns = time.perf_counter_ns()
                try:
                    message = decode_message(raw)
                except Exception as exc:
                    self.messages.put(({
                        "type": "_READ_ERROR", "message": str(exc)
                    }, received_ns))
                    return
                self.messages.put((message, received_ns))
        except OSError as exc:
            if not self.closed:
                self.messages.put(({
                    "type": "_READ_ERROR", "message": str(exc)
                }, time.perf_counter_ns()))

    def send(self, message: dict):
        payload = encode_message(message)
        with self.send_lock:
            self.sock.sendall(payload)

    def wait_for(self, predicate, description: str, timeout=WAIT_TIMEOUT_SECONDS):
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"{self.username}: timeout khi cho {description}")
            try:
                message, received_ns = self.messages.get(timeout=remaining)
            except queue.Empty:
                raise TimeoutError(f"{self.username}: timeout khi cho {description}")
            msg_type = message.get("type")
            if msg_type in ("ERROR", "_READ_ERROR", "_CONNECTION_CLOSED"):
                raise RuntimeError(f"{self.username}: {message}")
            if predicate(message):
                return message, received_ns

    def login(self):
        self.send({"type": "LOGIN", "name": self.username})
        self.wait_for(
            lambda m: m.get("type") == "LOGIN_RESULT" and m.get("status") == "OK",
            "LOGIN_RESULT",
        )

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        if threading.current_thread() != self.reader_thread:
            self.reader_thread.join(timeout = 1)
        try: 
            self.reader.close()
        except (OSError, ValueError):
            pass
        try:
            self.sock.close()
        except OSError:
            pass

class ResourceMonitor:
    def __init__(self):
        self.samples = []
        self.stop_event = threading.Event()
        self.thread = None
        self.server_pid = None
        self.process = None
        self.error = None

    def _find_server_process(self):
        if psutil is None:
            return
        try:
            for conn in psutil.net_connections(kind="tcp"):
                if conn.status == psutil.CONN_LISTEN and conn.laddr and conn.laddr.port == PORT:
                    if conn.pid:
                        self.server_pid = conn.pid
                        self.process = psutil.Process(conn.pid)
                        return
        except (psutil.AccessDenied, OSError) as exc:
            self.error = f"Khong doc duoc PID Server: {exc}"

    def start(self):
        if psutil is None:
            raise RuntimeError(
                "Chua co psutil de do CPU/RAM. Hay chay: python -m pip install psutil"
            )
        self._find_server_process()
        psutil.cpu_percent(interval=None)
        if self.process:
            try:
                self.process.cpu_percent(interval=None)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                self.process = None
        self.thread = threading.Thread(target=self._sample_loop, daemon=True)
        self.thread.start()

    def _sample_loop(self):
        while not self.stop_event.wait(0.25):
            now = time.strftime("%Y-%m-%d %H:%M:%S")
            row = {
                "timestamp": now,
                "system_cpu_percent": "",
                "system_ram_percent": "",
                "system_ram_used_mb": "",
                "server_pid": self.server_pid or "",
                "server_cpu_percent": "",
                "server_rss_mb": "",
            }
            try:
                vm = psutil.virtual_memory()
                row["system_cpu_percent"] = round(psutil.cpu_percent(interval=None), 2)
                row["system_ram_percent"] = round(vm.percent, 2)
                row["system_ram_used_mb"] = round((vm.total - vm.available) / (1024 * 1024), 2)
            except Exception as exc:
                self.error = str(exc)
            if self.process:
                try:
                    row["server_cpu_percent"] = round(self.process.cpu_percent(interval=None), 2)
                    row["server_rss_mb"] = round(self.process.memory_info().rss / (1024 * 1024), 2)
                except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
                    self.error = f"Khong lay duoc tai nguyen Server: {exc}"
                    self.process = None
            self.samples.append(row)

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=3)
        if self.samples:
            with RESOURCE_RESULT_FILE.open("w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=list(self.samples[0].keys()))
                writer.writeheader()
                writer.writerows(self.samples)


def create_and_start_room(room_index, client_x, client_o):
    started = time.perf_counter()
    client_x.send({
        "type": "CREATE_ROOM",
        "name": f"PF02_Room_{room_index:02d}",
        "time_limit": TURN_LIMIT_SECONDS,
    })
    created, _ = client_x.wait_for(lambda m: m.get("type") == "ROOM_CREATED", "ROOM_CREATED")
    room = created.get("room", {})
    room_id = room.get("room_id")
    if not room_id:
        raise RuntimeError(f"Phong {room_index}: ROOM_CREATED khong co room_id")

    client_o.send({"type": "JOIN_ROOM", "room_id": room_id})
    client_o.wait_for(
        lambda m: m.get("type") == "ROOM_JOINED" and m.get("room", {}).get("room_id") == room_id,
        f"ROOM_JOINED {room_id}",
    )

    client_x.send({"type": "START_MATCH", "room_id": room_id})
    # Wait for both notifications without assuming their arrival order.
    for client in (client_x, client_o):
        received_types = set()
        while received_types != {"ROOM_STARTED", "SYNC_FULL_STATE"}:
            message, _ = client.wait_for(
                lambda m: (
                    m.get("room_id") == room_id
                    and m.get("type") in {"ROOM_STARTED", "SYNC_FULL_STATE"}
                ),
                f"ROOM_STARTED + SYNC_FULL_STATE {room_id}",
            )
            received_types.add(message.get("type"))

    client_x.send({"type": "MOVE", "row": 0, "col": 0})
    move, _ = client_o.wait_for(
        lambda m: (
            m.get("type") == "SYNC_MOVE"
            and m.get("room_id") == room_id
            and isinstance(m.get("move"), dict)
            and m["move"].get("row") == 0
            and m["move"].get("col") == 0
        ),
        f"SYNC_MOVE {room_id}",
    )
    elapsed = (time.perf_counter() - started) * 1000
    return {
        "room_number": room_index,
        "room_id": room_id,
        "client_x": client_x.username,
        "client_o": client_o.username,
        "room_started": "YES",
        "first_move_broadcast": "YES",
        "operation_time_ms": f"{elapsed:.3f}",
        "status": "PASS",
        "error": "",
    }

def main():
    if psutil is None:
        print("Thieu thu vien psutil. Cai dat bang lenh: python -m pip install psutil")
        raise SystemExit(2)

    run_id = str(time.time_ns())[-6:]
    clients = []
    results = []
    monitor = ResourceMonitor()
    errors = []

    print(f"Ket noi Server {HOST}:{PORT} ...")
    try:
        monitor.start()
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            futures = {
                pool.submit(LoadClient, f"PF2X{run_id}{i:02d}"): (i, "X")
                for i in range(ROOM_COUNT)
            }
            futures.update({
                pool.submit(LoadClient, f"PF2O{run_id}{i:02d}"): (i, "O")
                for i in range(ROOM_COUNT)
            })
            made = {}
            for future in as_completed(futures):
                idx, side = futures[future]
                try:
                    client = future.result()
                    clients.append(client)
                    made[(idx, side)] = client
                except Exception as exc:
                    errors.append(f"Tao ket noi client {idx}-{side}: {exc}")

        if len(clients) != TOTAL_CLIENTS:
            print("\n CHI TIET LOI KHI TAO CLIENT:")
            for error in errors:
                print("-", error)
            print(f"\n Tao thanh cong: {len(clients)}/{TOTAL_CLIENTS}")
            raise RuntimeError(
                f"Chi tao duoc {len(clients)}/{TOTAL_CLIENTS} TCP client"
            )
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            futures = {pool.submit(c.login): c.username for c in clients}
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as exc:
                    errors.append(f"Login {futures[future]}: {exc}")
        if errors:
            raise RuntimeError("Co loi trong giai doan ket noi/dang nhap: " + " | ".join(errors[:5]))
        print(f"Dang nhap thanh cong {len(clients)}/{TOTAL_CLIENTS} client.")

        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            futures = {
                pool.submit(
                    create_and_start_room,
                    i + 1,
                    made[(i, "X")],
                    made[(i, "O")],
                ): i + 1
                for i in range(ROOM_COUNT)
            }
            for future in as_completed(futures):
                room_number = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                    if len(results) % 5 == 0 or len(results) == ROOM_COUNT:
                        print(f"Da khoi tao va kiem tra {len(results)}/{ROOM_COUNT} phong.")
                except Exception as exc:
                    results.append({
                        "room_number": room_number,
                        "room_id": "",
                        "client_x": made[(room_number - 1, "X")].username,
                        "client_o": made[(room_number - 1, "O")].username,
                        "room_started": "NO",
                        "first_move_broadcast": "NO",
                        "operation_time_ms": "",
                        "status": "FAIL",
                        "error": str(exc),
                    })

        results.sort(key=lambda r: r["room_number"])
        with ROOM_RESULT_FILE.open("w", newline="", encoding="utf-8-sig") as f:
            fields = [
                "room_number", "room_id", "client_x", "client_o",
                "room_started", "first_move_broadcast", "operation_time_ms",
                "status", "error",
            ]
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(results)

        passed_rooms = sum(1 for r in results if r["status"] == "PASS")
        print("Giu 100 client va 50 phong hoat dong trong 3 giay de lay mau CPU/RAM ...")
        time.sleep(3)
        monitor.stop()
        print("\n========== KET QUA TC_PF_02 ==========")
        print(f"TCP clients connected : {len(clients)}/{TOTAL_CLIENTS}")
        print(f"Clients logged in     : {len(clients)}/{TOTAL_CLIENTS if not errors else '100 (kiem tra log)'}")
        print(f"Rooms created/started : {passed_rooms}/{ROOM_COUNT}")
        print(f"First-move broadcasts : {passed_rooms}/{ROOM_COUNT}")
        print(f"Resource samples      : {len(monitor.samples)}")
        if monitor.samples:
            cpu_values = [r["system_cpu_percent"] for r in monitor.samples if r["system_cpu_percent"] != ""]
            ram_values = [r["system_ram_percent"] for r in monitor.samples if r["system_ram_percent"] != ""]
            server_cpu = [r["server_cpu_percent"] for r in monitor.samples if r["server_cpu_percent"] != ""]
            server_ram = [r["server_rss_mb"] for r in monitor.samples if r["server_rss_mb"] != ""]
            if cpu_values:
                print(f"System CPU avg/max    : {sum(cpu_values)/len(cpu_values):.2f}% / {max(cpu_values):.2f}%")
            if ram_values:
                print(f"System RAM avg/max    : {sum(ram_values)/len(ram_values):.2f}% / {max(ram_values):.2f}%")
            if server_cpu:
                print(f"Server CPU avg/max    : {sum(server_cpu)/len(server_cpu):.2f}% / {max(server_cpu):.2f}%")
            if server_ram:
                print(f"Server RAM avg/max    : {sum(server_ram)/len(server_ram):.2f} / {max(server_ram):.2f} MB")
            else:
                print("Server PID/RAM        : Chua doc duoc tien trinh Server; xem CSV de biet pham vi do.")
        if monitor.error:
            print(f"Resource note         : {monitor.error}")
        passed = (
            len(clients) == TOTAL_CLIENTS
            and passed_rooms == ROOM_COUNT
            and not errors
            and len(monitor.samples) > 0
        )
        print(f"Danh gia ky thuat      : {'DAT cac buoc chuc nang' if passed else 'KHONG DAT / CHUA HOAN TAT'}")
        print("Luu y: CPU/RAM can doi chieu nguong chap nhan do nhom/giang vien quy dinh.")
        print(f"Room CSV              : {ROOM_RESULT_FILE}")
        print(f"Resource CSV          : {RESOURCE_RESULT_FILE}")
        if not passed:
            raise RuntimeError("Chua dat du cac dieu kien kiem tra 100 client/50 phong.")

    except Exception as exc:
        print(f"\nKIEM THU THAT BAI / KHONG HOAN TAT: {exc}")
        print("Khong ket luan PASS neu chua xac nhan du 100 client va 50 phong.")
        raise
    finally:
        monitor.stop()
        try:
            with ThreadPoolExecutor(max_workers=WORKERS) as pool:
                futures = []
                for i in range(ROOM_COUNT):
                    pair = [c for c in clients if c.username.startswith((f"PF2X{run_id}{i:02d}", f"PF2O{run_id}{i:02d}"))]
                    for client in pair:
                        futures.append(pool.submit(client.send, {"type": "LEAVE_ROOM"}))
                for future in futures:
                    try:
                        future.result(timeout=5)
                    except Exception:
                        pass
        except Exception:
            pass
        for client in clients:
            client.close()


if __name__ == "__main__":
    main()
