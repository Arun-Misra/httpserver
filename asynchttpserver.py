import asyncio
import re
import json
import datetime
import socket

HOST = "localhost"
PORT = 8080

json_data_store = {}
id_counter = 1

async def handle_client(reader, writer):
    global id_counter
    try:
        request_data = await reader.readuntil(b"\r\n\r\n")
        request_data += b"\r\n\r\n"
        header_text = request_data.decode()
        lines = header_text.split("\r\n")
        if not lines:
            return
        first_header = lines[0].split()
        if len(first_header) < 2:
            return
        http_method = first_header[0]
        path = first_header[1]
        headers = {}
        for line in lines[1:]:
            if not line:
                break
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip()] = v.strip()
        content_length = int(headers.get("Content-Length", 0))
        if content_length > 0:
            body_data = await reader.readexactly(content_length)
            body = body_data.decode()
        else:
            body = ""
        response = b""
        status = "404 Not Found"

        if http_method == 'GET':
            if path == '/':
                response = response_build("200 OK", "<h1>WELCOME TO MY SERVER</h1>")
                status = "200 OK"
            elif path.startswith('/echo'):
                check = re.findall("[=](.+)", path)
                if check:
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
                except ValueError:
                    response = response_build("400 Bad Request", {"error": "Invalid ID"}, "application/json")
                    status = "400 Bad Request"
        elif http_method == 'POST' and path == '/data':
            try:
                if not body:
                    raise ValueError("Empty body")
                obj = json.loads(body)
                obj["id"] = id_counter
                json_data_store[id_counter] = obj
                id_counter += 1
                response = response_build("200 OK", {"status": "success", "id": obj["id"]}, "application/json")
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
                    response = response_build("200 OK", {"status": "deleted"}, "application/json")
                    status = "200 OK"
                else:
                    response = response_build("404 Not Found", {"error": "Item not found"}, "application/json")
                    status = "404 Not Found"
            except ValueError:
                response = response_build("400 Bad Request", {"error": "Invalid ID"}, "application/json")
                status = "400 Bad Request"
        else:
            response = response_build("404 Not Found", "Route not found")
            status = "404 Not Found"

        print(f"[LOG] {http_method} {path} => {status}")
        writer.write(response)
        await writer.drain()
    except asyncio.IncompleteReadError:
        pass
    except Exception as e:
        print(f"Error handling client: {e}")
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except:
            pass

def response_build(http_status, content, content_type='text/html'):
    body_in_byte = content.encode() if isinstance(content, str) else json.dumps(content).encode()
    headers = (
        f"HTTP/1.1 {http_status}\r\n"
        f"Date: {datetime.datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')}\r\n"
        f"Content-Type: {content_type}; charset=utf-8\r\n"
        f"Content-Length: {len(body_in_byte)}\r\n"
        "\r\n"
    )
    return headers.encode() + body_in_byte

async def main():
    server = await asyncio.start_server(handle_client, HOST, PORT)
    print(f"Listening on {HOST}:{PORT}")
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())