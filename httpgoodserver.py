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

def response_build(http_status, content, content_type='text/html'):
    response= (
        f"HTTP/1.1 {http_status}\r\n"
        f"Content-Type: {content_type}; charset=utf-8\r\n"
        f"Content-Length: {len(content.encode())}\r\n"
        "\r\n"
        f"{content}"
    )
    return response

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
            response = response_build("200 OK", content)
            
        elif path.startswith('/echo'):
            check = re.findall("[=](.+)", path)
            content = check[0]
            response = response_build("200 OK", content)
            
    else:
        response = 'HTTP/1.1 405 Method Not Allowed\r\n\r\nAllow: GET'
    socket_connect.sendall(response.encode())
    socket_connect.close()