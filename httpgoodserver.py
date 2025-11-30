import socket
import re
import json
import datetime

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
        f"Date: {datetime.datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')}\r\n"
        f"Content-Type: {content_type}; charset=utf-8\r\n"
        f"Content-Length: {len(body_in_byte)}\r\n"
        "\r\n"
        # f"{body_in_byte}"
    )
    return headers.encode() + body_in_byte

while True:
    socket_connect, address = connection.accept()
    request_data = b""
    while b"\r\n\r\n" not in request_data:
        chunk = socket_connect.recv(1024)
        if not chunk:
            break
        request_data += chunk    

    request = request_data.decode()
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
    header_end = request_data.find(b"\r\n\r\n") + 4
    content_length = int(headers.get("Content-Length", 0))
    body_data = request_data[header_end:]
    while len(body_data) < content_length:
        chunk = socket_connect.recv(content_length - len(body_data))
        if not chunk:
            break
        body_data += chunk
    
    body = body_data.decode() if body_data else ""

     
     
    if http_method == 'GET':
        if path == '/':
            # with open("ff.html", "r") as fin:
            # content = fin.read()
            response = response_build("200 OK", "<h1>WELCOME TO MY SERVER</h1>")
            status = "200 OK"
        elif path.startswith('/echo'):
            check = re.findall("[=](.+)", path)
            content = check[0]
            response = response_build("200 OK", content)
            status = "200 OK"
        elif path == '/data':
            if json_data_store:
                response = response_build("200 OK", list(json_data_store.values()), "application/json")
                status = "200 OK"
            else:
                response = response_build("404 Not Found", {"error": "Item not found"}, "application/json")
                status = "404 Not Found"
        elif path.startswith('/data/'):
            try:
                item = int(path.split("/")[-1])
                if item in json_data_store:
                    response = response_build("200 OK", json_data_store[item], "application/json")
                    status = "200 OK"
                else:
                    response = response_build("404 Not Found", {"error": "Item not found"}, "application/json")
                    status = "404 Not Found"
            except:
                response = response_build("400 Bad Request", {"error": "Invalid ID"}, "application/json")
                status = "400 Bad Request"
    elif http_method == 'POST' and path == '/data':
        try:
            if not body:
                raise ValueError("Empty body")
            object = json.loads(body)
            object["id"] = id
            json_data_store[id] = object
            id+=1
            response = response_build("200 OK", {"status": "success", "id": object["id"]}, "application/json")
            status = "200 OK"
        except json.JSONDecodeError as e:
            print(f"[ERROR] JSON Decode Error: {e}")
            response = response_build("400 Bad Request", {"error": "Invalid JSON payload"}, "application/json")
            status = "400 Bad Request"
        except ValueError as e:
            print(f"[ERROR] Value Error: {e}")
            response = response_build("400 Bad Request", {"error": str(e)}, "application/json")
            status = "400 Bad Request"
    
    elif http_method == 'DELETE' and path.startswith('/data/'):
        try:
            item = int(path.split("/")[-1])
            if item in json_data_store:
                json_data_store.pop(item)
                response = response_build("200 OK",{"status":"deleted"}, "application/json")
                status = "200 OK"
            else:
                response = response_build("404 Not Found", {"error": "Item not found"}, "application/json")
                status = "404 Not Found"
        except:
            response = response_build("400 Bad Request", {"error": "Invalid ID"}, "application/json")
            status = "400 Bad Request"
    else:
        response = response_build("404 Not Found", "Route not found")
        status = "404 Not Found"
    print(f"[LOG] {http_method} {path} => {status}")
    socket_connect.sendall(response)
    socket_connect.close()