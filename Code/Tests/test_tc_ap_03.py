import socket
import json

HOST = "127.0.0.1"
PORT = 8888

message = [
    {
        "type": "INVITE",
        "target": "bob"
    },
    {
        "type": "MOVE",
        "row": 0,
        "col": 0
    }
]
with socket.create_connection((HOST, PORT), timeout = 5) as sock:
    print("Đã kết nối Server, chưa đăng nhập.")

    reader = sock.makefile("rb")

    for message in message:
        payload = json.dumps(message).encode("utf-8") + b"\n"
        sock.sendall(payload)
        response = reader.readline()
        if not response:
            print("Server đóng kết nối.")
            break

        result = json.loads(response.decode("utf-8"))

        print("\n Thông điệp gửi:", message)
        print("Phản hồi Server:", result)

        if result.get("type") == "ERROR" and result.get("code") == "LOGIN_REQUIRED":
            print("PASS: Server từ chối thông điệp khi chưa đăng nhập.")
        else:
            print("CẦN KIỂM TRA: Phản hồi không đúng LOGIN_REQUIRED.")