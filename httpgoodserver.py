import socket
import re

HOST = "localhost"
PORT = 8080

# 1. Socket establishment
connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
connection.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

# 2. Binding
connection.bind((HOST, PORT))

# 3. Listening
connection.listen(5)

print(f"Listening to port {PORT}")
while True:
    socket_connect, address = connection.accept()
    req =  socket_connect.recv(1000).decode()
    headers = req.split("\r\n")
    if len(headers) > 0:
        print(headers[0])
    first_header = headers[0].split()
    print(first_header)
    http_method = first_header[0]
    path = first_header[1]
    
    if http_method == 'GET':
        if path == '/':
            with open("ff.html", "r") as fin:
                content = fin.read()
            response = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: text/html; charset=utf-8\r\n"
                f"Content-Length: {len(content.encode())}\r\n"
                "\r\n"
                f"{content}"
            )
        elif path.startswith('/echo'):
            content = re.findall("[=][.+]", path)
            print(content)
            response = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: text/html; charset=utf-8\r\n"
                f"Content-Length: {len(content.encode())}\r\n"
                "\r\n"
                f"{content}"
            )
            
    else:
        response = 'HTTP/1.1 405 Method Not Allowed\r\n\r\nAllow: GET'
    socket_connect.sendall(response.encode())
    socket_connect.close()