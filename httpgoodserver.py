import socket
import re
import json

HOST = "localhost"
PORT = 8080

json_data_store = {}
id = 1

# 1. Socket establishment
connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
connection.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

# 2. Binding
connection.bind((HOST, PORT))

# 3. Listening
connection.listen(5)

print(f"Listening to port {PORT}")

def response_build(http_status, content, content_type='text/html'):
    body_in_byte = content.encode() if isinstance(content, str) else json.dumps(content).encode()
    headers= (
        f"HTTP/1.1 {http_status}\r\n"
        f"Content-Type: {content_type}; charset=utf-8\r\n"
        f"Content-Length: {len(body_in_byte)}\r\n"
        "\r\n"
        # f"{body_in_byte}"
    )
    return headers.encode() + body_in_byte

while True:
    socket_connect, address = connection.accept()
    request =  socket_connect.recv(1000).decode()
    lines = request.split("\r\n")
    first_header = lines[0].split()
    http_method = first_header[0]
    path = first_header[1]
    headers = {}
    i = 1
    while lines[i]:
        k, v = lines[i].split(":", 1)
        headers[k.strip()] = v.strip()
        i += 1
    body = "\r\n".join(lines[i+1:])

    
    if  http_method == 'GET'and path == '/' :
        # with open("ff.html", "r") as fin:
        #     content = fin.read()
        response = response_build("200 OK", "<h1>WELCOME TO MY SERVER</h1>")

    elif http_method == 'GET' and path.startswith('/echo'):
        check = re.findall("[=](.+)", path)
        content = check[0]
        response = response_build("200 OK", content)
        
    elif http_method == 'POST' and path == '/data':
        object = json.loads(body)
        object["id"] = id
        json_data_store[id] = object
        id+=1
        response = response_build("200 OK", {"status": "success", "id": object["id"]}, "application/json")
            
    else:
        response = 'HTTP/1.1 405 Method Not Allowed\r\n\r\nAllow: GET'
    socket_connect.sendall(response)
    socket_connect.close()