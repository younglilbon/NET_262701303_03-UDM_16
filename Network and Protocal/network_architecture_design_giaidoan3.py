import socket
import json
import threading

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

def xu_ly_client(conn, addr):
    print(f"[NEW CONNECTION] Đã kết nối với client: {addr}")
    conn.settimeout(60.0)
    try:
        while True:
            data = conn.recv(1024)
            if not data:
                break
            thong_diep = doc_thong_diep(data)
            print(f"Nhận từ {addr}: {thong_diep}")
            
            hanh_dong = thong_diep.get("action")
            if hanh_dong == "QUIT":
                phan_hoi = tao_thong_diep("QUIT_ACK", "Đã ngắt kết nối")
                conn.sendall(phan_hoi)
                break
            
            phan_hoi = tao_thong_diep("SERVER_RESPONSE", f"Đã xử lý action: {hanh_dong}")
            conn.sendall(phan_hoi)
    except socket.timeout:
        print(f"[TIMEOUT] Client {addr} quá thời gian chờ.")
    except Exception as e:
        print(f"[ERROR] Lỗi kết nối với {addr}: {e}")
    finally:
        conn.close()
        print(f"[DISCONNECT] Đã đóng kết nối với {addr}")

def chay_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5)
    print(f"Server đang lắng nghe tại {HOST}:{PORT}...")
    
    try:
        while True:
            conn, addr = server_socket.accept()
            thread = threading.Thread(target=xu_ly_client, args=(conn, addr))
            thread.daemon = True
            thread.start()
    except KeyboardInterrupt:
        print("\n[SERVER STOPPED] Đang dừng Server...")
    finally:
        server_socket.close()

def chay_client():
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.settimeout(10.0)
    try:
        client_socket.connect((HOST, PORT))
        print(f"Đã kết nối tới server {HOST}:{PORT}")
        
        goi_tin = tao_thong_diep("LOGIN", {"username": "ThanhVien1"})
        client_socket.sendall(goi_tin)
        
        data = client_socket.recv(1024)
        print(f"Nhận từ server: {doc_thong_diep(data)}")
        
        goi_tin_thoat = tao_thong_diep("QUIT", {})
        client_socket.sendall(goi_tin_thoat)
        
        data_thoat = client_socket.recv(1024)
        print(f"Nhận từ server: {doc_thong_diep(data_thoat)}")
        
    except socket.timeout:
        print("[TIMEOUT] Không thể kết nối hoặc phản hồi từ server quá lâu.")
    except Exception as e:
        print(f"[ERROR] Lỗi phía client: {e}")
    finally:
        client_socket.close()
        print("Đã đóng kết nối client.")

if __name__ == "__main__":
    print("=== MODULE NETWORK & PROTOCOL (GIAI ĐOẠN 3) ===")
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
        