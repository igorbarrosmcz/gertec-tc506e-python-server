import socket
import time


HOST = "127.0.0.1"
PORTA = 6502


print("Conectando ao servidor...")

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

s.connect((HOST, PORTA))

print("Conectado")

time.sleep(60)