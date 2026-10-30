"""Linux only: lets the OpenHands container reach the AI engine, which listens on 127.0.0.1 only.
Listens on the Docker bridge address (e.g. 172.17.0.1:8081, not reachable from your network) and forwards to
127.0.0.1:8081. Only accepts connections from private Docker address ranges."""
import ipaddress
import socket
import sys
import threading

ALLOWED = [ipaddress.ip_network(n) for n in ("172.16.0.0/12", "10.0.0.0/8", "192.168.0.0/16")]


def pipe(a, b):
    try:
        while True:
            d = a.recv(65536)
            if not d:
                break
            b.sendall(d)
    except OSError:
        pass
    finally:
        for s in (a, b):
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass


def main():
    listen_ip, port = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 8081
    target = ("127.0.0.1", int(sys.argv[3]) if len(sys.argv) > 3 else port)
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((listen_ip, port))
    srv.listen(64)
    while True:
        c, addr = srv.accept()
        if not any(ipaddress.ip_address(addr[0]) in n for n in ALLOWED):
            c.close()
            continue
        try:
            u = socket.create_connection(target, timeout=10)
            u.settimeout(None)
        except OSError:
            c.close()
            continue
        threading.Thread(target=pipe, args=(c, u), daemon=True).start()
        threading.Thread(target=pipe, args=(u, c), daemon=True).start()


if __name__ == "__main__":
    main()
