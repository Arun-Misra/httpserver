import socket
import re

mysock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
mysock.connect(('127.0.0.1', 9000))
get_demo = 'GET https//127.0.0.1 HTTP/1.1\r\n\r\n'.encode()
mysock.send(get_demo)

# while True:
data = mysock.recv(5124)
strr = data.decode()
print(strr)
mysock.close()