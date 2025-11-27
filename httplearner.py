import socket
import re

mysock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
mysock.connect(('httpforever.com', 80))
get_demo = 'GET http://httpforever.com/ HTTP/1.0\n\n'.encode()
mysock.send(get_demo)

while True:
    data = mysock.recv(512)
    if (len(data) < 1):
        break
    print(data.decode())
mysock.close()