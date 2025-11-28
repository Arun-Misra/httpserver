import socket

def createServer():
    serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try :
        serversocket.bind(('localhost', 9000))
        serversocket.listen(5)
        while True:
            (clientsocket, address) = serversocket.accept()
            
            receive_data = clientsocket.recv(2000).decode()

            pieces = receive_data.split("\n")

            if len(pieces) > 0:
                print(pieces[0])
            data = "HTTP/1.1 200 OK\r\n"
            data += "Content-Type: text/html;charset = utf-8\r\n"
            data += "\r\n"
            data += "<html><body>Hello World</body><html>"
            clientsocket.sendall(data.encode())
            clientsocket.shutdown(socket.SHUT_WR)
    except KeyboardInterrupt:
        print("\nShutting down")

    except Exception as exc :
        print("Error:\n")
        print(exc)

    serversocket.close()

print("Access http://localhost:9000")
createServer()

        



