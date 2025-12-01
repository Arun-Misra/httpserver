import asyncio
import re
import json
import datetime
from typing import Dict, Any, Optional, Tuple
import logging
from concurrent.futures import ThreadPoolExecutor
import os

logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
HOST = "localhost"
PORT = 8080

STATUS_OK = "200 OK"
STATUS_CREATED = "201 Created"
STATUS_BAD_REQUEST = "400 Bad Request"
STATUS_NOT_FOUND = "404 Not Found"
STATUS_TIMEOUT = "408 Request Timeout"
STATUS_PAYLOAD_TOO_LARGE = "413 Payload Too Large"
STATUS_INTERNAL_ERROR = "500 Internal Server Error"

CONTENT_TYPE_HTML = "text/html"
CONTENT_TYPE_JSON = "application/json"
CONTENT_TYPE_TEXT = "text/plain"

# Concurrency limits - optimized for high performance
MAX_CONCURRENT = 15000
HEADER_TIMEOUT = 60.0
BODY_TIMEOUT = 60.0  
MAX_BODY = 2 * 1024 * 1024  # 2 MB

# Semaphore for concurrency control (will be created in event loop)
sem = None

# Thread pool for CPU-bound JSON operations
json_pool = ThreadPoolExecutor(max_workers=1000)

# Data store
json_data_store: Dict[int, Dict[str, Any]] = {}
id_counter = 1


def now_http_date() -> str:
    return datetime.datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')


async def async_json_loads(s: str):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(json_pool, json.loads, s)


async def async_json_dumps(obj):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(json_pool, json.dumps, obj)


class HTTPRequest:
    def __init__(self, method: str, path: str, headers: Dict[str, str], body: str):
        self.method = method
        self.path = path
        self.headers = headers
        self.body = body


class HTTPResponse:
    def __init__(self, status: str, content: Any, content_type: str = CONTENT_TYPE_HTML):
        self.status = status
        self.content = content
        self.content_type = content_type

    async def build(self) -> bytes:
        if isinstance(self.content, bytes):
            body_bytes = self.content
        elif isinstance(self.content, str):
            body_bytes = self.content.encode()
        else:
            # JSON-encode using thread pool
            json_str = await async_json_dumps(self.content)
            body_bytes = json_str.encode()
            self.content_type = CONTENT_TYPE_JSON
        
        headers = (
            f"HTTP/1.1 {self.status}\r\n"
            f"Date: {now_http_date()}\r\n"
            f"Content-Type: {self.content_type}; charset=utf-8\r\n"
            f"Content-Length: {len(body_bytes)}\r\n"
            f"Connection: keep-alive\r\n"
            "\r\n"
        )
        return headers.encode() + body_bytes


def percent_decode(s: str) -> str:
    s = s.replace('+', ' ')
    out = bytearray()
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == '%' and i + 2 < len(s):
            hexpart = s[i+1:i+3]
            try:
                out.append(int(hexpart, 16))
                i += 3
                continue
            except ValueError:
                pass
        out.extend(ch.encode('utf-8'))
        i += 1
    try:
        return out.decode('utf-8')
    except UnicodeDecodeError:
        return out.decode('utf-8', errors='replace')


def parse_path_and_query(raw_path: str) -> tuple[str, Dict[str, str]]:
    qpos = raw_path.find('?')
    if qpos == -1:
        return raw_path, {}
    
    path = raw_path[:qpos]
    query = raw_path[qpos+1:]
    params = {}
    
    if not query:
        return path, params
    
    for part in query.split('&'):
        if not part:
            continue
        if '=' in part:
            k, v = part.split('=', 1)
        else:
            k, v = part, ''
        params[percent_decode(k)] = percent_decode(v)
    
    return path, params


async def parse_request(reader: asyncio.StreamReader) -> Optional[HTTPRequest]:
    try:
        # Read headers with timeout
        try:
            header_bytes = await asyncio.wait_for(
                reader.readuntil(b"\r\n\r\n"),
                timeout=HEADER_TIMEOUT
            )
        except asyncio.TimeoutError:
            logger.error("Header read timeout")
            return None
        
        header_text = header_bytes.decode(errors='replace')
        lines = header_text.split("\r\n")
        
        if not lines:
            return None
        
        # Parse request line
        first_header = lines[0].split()
        if len(first_header) < 2:
            return None
        
        http_method = first_header[0]
        path = first_header[1]
        
        # Parse headers
        headers = {}
        for line in lines[1:]:
            if not line:
                break
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip()] = v.strip()
        
        # Validate Content-Length
        try:
            content_length = int(headers.get("Content-Length", 0))
        except ValueError:
            logger.error("Invalid Content-Length header")
            return None
        
        # Check size limit
        if content_length > MAX_BODY:
            logger.warning(f"Payload too large: {content_length} bytes")
            return None
        
        # Read body with timeout
        body = ""
        if content_length > 0:
            try:
                body_bytes = await asyncio.wait_for(
                    reader.readexactly(content_length),
                    timeout=BODY_TIMEOUT
                )
                body = body_bytes.decode('utf-8', errors='replace')
            except asyncio.TimeoutError:
                logger.error("Body read timeout")
                return None
        
        return HTTPRequest(http_method, path, headers, body)
    
    except asyncio.IncompleteReadError:
        return None
    except Exception as e:
        logger.error(f"Error parsing request: {e}")
        return None


# Route handlers
async def handle_root() -> HTTPResponse:
    return HTTPResponse(STATUS_OK, "<h1>WELCOME TO MY SERVER</h1>", CONTENT_TYPE_HTML)


async def handle_echo(params: Dict[str, str]) -> HTTPResponse:
    msg = params.get('message') or params.get('msg') or ""
    if not msg:
        return HTTPResponse(
            STATUS_BAD_REQUEST,
            {"error": "Missing message parameter"},
            CONTENT_TYPE_JSON
        )
    return HTTPResponse(STATUS_OK, msg, CONTENT_TYPE_TEXT)


async def handle_get_all_data() -> HTTPResponse:
    if json_data_store:
        return HTTPResponse(STATUS_OK, list(json_data_store.values()), CONTENT_TYPE_JSON)
    return HTTPResponse(STATUS_OK, [], CONTENT_TYPE_JSON)


async def handle_get_data_by_id(item_id: int) -> HTTPResponse:
    if item_id in json_data_store:
        return HTTPResponse(STATUS_OK, json_data_store[item_id], CONTENT_TYPE_JSON)
    return HTTPResponse(
        STATUS_NOT_FOUND,
        {"error": "Item not found"},
        CONTENT_TYPE_JSON
    )


async def handle_create_data(body: str) -> HTTPResponse:
    global id_counter
    
    try:
        if not body:
            raise ValueError("Empty body")
        
        # Parse JSON in thread pool
        obj = await async_json_loads(body)
        
        # Store without modifying original object
        json_data_store[id_counter] = obj
        current_id = id_counter
        id_counter += 1
        
        return HTTPResponse(
            STATUS_CREATED,
            {"status": "success", "index": current_id},
            CONTENT_TYPE_JSON
        )
    
    except json.JSONDecodeError as e:
        logger.error(f"JSON Decode Error: {e}")
        return HTTPResponse(
            STATUS_BAD_REQUEST,
            {"error": "Invalid JSON payload"},
            CONTENT_TYPE_JSON
        )
    except ValueError as e:
        logger.error(f"Value Error: {e}")
        return HTTPResponse(
            STATUS_BAD_REQUEST,
            {"error": str(e)},
            CONTENT_TYPE_JSON
        )


async def handle_delete_data(item_id: int) -> HTTPResponse:
    if item_id in json_data_store:
        json_data_store.pop(item_id)
        return HTTPResponse(STATUS_OK, {"status": "deleted"}, CONTENT_TYPE_JSON)
    return HTTPResponse(
        STATUS_NOT_FOUND,
        {"error": "Item not found"},
        CONTENT_TYPE_JSON
    )


async def route_request(request: HTTPRequest) -> HTTPResponse:
    method = request.method
    raw_path = request.path
    
    # Parse path and query parameters
    path, params = parse_path_and_query(raw_path)
    
    # GET routes
    if method == 'GET':
        if path == '/':
            return await handle_root()
        elif path.startswith('/echo'):
            return await handle_echo(params)
        elif path == '/data':
            return await handle_get_all_data()
        elif path.startswith('/data/'):
            try:
                item_id = int(path.split("/")[-1])
                return await handle_get_data_by_id(item_id)
            except ValueError:
                return HTTPResponse(
                    STATUS_BAD_REQUEST,
                    {"error": "Invalid ID"},
                    CONTENT_TYPE_JSON
                )
    
    # POST routes
    elif method == 'POST' and path == '/data':
        return await handle_create_data(request.body)
    
    # DELETE routes
    elif method == 'DELETE' and path.startswith('/data/'):
        try:
            item_id = int(path.split("/")[-1])
            return await handle_delete_data(item_id)
        except ValueError:
            return HTTPResponse(
                STATUS_BAD_REQUEST,
                {"error": "Invalid ID"},
                CONTENT_TYPE_JSON
            )
    
    # Route not found
    return HTTPResponse(STATUS_NOT_FOUND, "Route not found")


async def _handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    try:
        # Parse request
        request = await parse_request(reader)
        if not request:
            # Send appropriate error response
            response = HTTPResponse(
                STATUS_BAD_REQUEST,
                {"error": "Invalid request"},
                CONTENT_TYPE_JSON
            )
            writer.write(await response.build())
            await writer.drain()
            return
        
        # Route and handle request
        response = await route_request(request)
        
        # Send response
        writer.write(await response.build())
        await writer.drain()
    
    except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, OSError):
        # Client disconnected or connection error - silent fail
        pass
    except Exception as e:
        # Unexpected error - try to send 500 response
        logger.error(f"Error handling client: {e}")
        try:
            error_response = HTTPResponse(
                STATUS_INTERNAL_ERROR,
                {"error": "Internal server error"},
                CONTENT_TYPE_JSON
            )
            writer.write(await error_response.build())
            await writer.drain()
        except Exception:
            pass
    
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    async with sem:
        await _handle_client(reader, writer)


async def main():
    global sem
    # Create semaphore inside event loop
    sem = asyncio.Semaphore(MAX_CONCURRENT)
    
    server = await asyncio.start_server(
        handle_client,
        HOST,
        PORT,
        backlog=10000  # Increased backlog for high connection rate
    )
    
    logger.error(f"Server listening on {HOST}:{PORT}")
    logger.error(f"Max concurrent connections: {MAX_CONCURRENT}")
    logger.error(f"Thread pool workers: {json_pool._max_workers}")
    logger.error(f"Max body size: {MAX_BODY / (1024 * 1024):.1f} MB")
    
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.error("Server stopped by user")
    finally:
        json_pool.shutdown(wait=True)
