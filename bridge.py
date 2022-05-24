# https://pyserial.readthedocs.io/en/latest/examples.html

import socket
from types import SimpleNamespace as ns

config = ns(
    in_connections=ns(
        tcp=ns(
            port=50000,
            max_connections=2,
        ),
        serial=ns(
            port=50001,
            baudrate=115200,
        ),
    ),
    out_connection=ns(
        port=50002,
        address='/dev/ttyUSB0',
        baudrate=115200,
    ),
)

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(('', config.tcp.port))
s.listen(config.tcp.max_connections)

try:
    while True:
        connection, client_ip = s.accept()
        while True:
            data = connection.recv(1024)
finally:
    s.close()
