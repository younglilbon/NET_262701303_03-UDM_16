import socket
import json

HOST = '127.0.0.1'
PORT = 8888

def tao_thong_diep(hanh_dong, du_lieu):
    msg = {
        "action": hanh_dong,
        "data": du_lieu
    }
    return json.dumps(msg).encode('utf-8')

def doc_thong_diep(data_bytes):
    try:
        return json.loads(data_bytes.decode('utf-8'))
    except Exception:
        return None

if __name__ == "__main__":
    print("=== MODULE NETWORK & PROTOCOL ===")
    print(f"Server Address: {HOST}:{PORT}")
    print("Trạng thái: Sẵn sàng cấu hình Socket và xử lý gói tin.")