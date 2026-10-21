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

def chay_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((HOST, PORT))
    server_socket.listen(1)
    print(f"Server đang lắng nghe tại {HOST}:{PORT}...")
    
    conn, addr = server_socket.accept()
    print(f"Đã kết nối với client từ: {addr}")
    
    while True:
        data = conn.recv(1024)
        if not data:
            break
        thong_diep = doc_thong_diep(data)
        print(f"Nhận từ client: {thong_diep}")
        
        phan_hoi = tao_thong_diep("SERVER_RESPONSE", "Đã nhận dữ liệu thành công")
        conn.sendall(phan_hoi)
        
    conn.close()
    server_socket.close()

def chay_client():
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((HOST, PORT))
    print(f"Đã kết nối tới server {HOST}:{PORT}")
    
    goi_tin = tao_thong_diep("LOGIN", {"username": "ThanhVien1"})
    client_socket.sendall(goi_tin)
    
    data = client_socket.recv(1024)
    print(f"Nhận từ server: {doc_thong_diep(data)}")
    
    client_socket.close()

if __name__ == "__main__":
    print("=== MODULE NETWORK & PROTOCOL ===")
    print(f"Server Address: {HOST}:{PORT}")
    print("Chọn chế độ chạy:")
    print("1. Server")
    print("2. Client")
    lua_chon = input("Nhập lựa chọn (1 hoặc 2): ")
    
    if lua_chon == "1":
        chay_server()
    elif lua_chon == "2":
        chay_client()
    else:
        print("Lựa chọn không hợp lệ!")
        