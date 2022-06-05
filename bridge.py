"""
this is just a playground. use publish_port.py instead.
"""

# https://pyserial.readthedocs.io/en/latest/examples.html

import socket
import serial
from types import SimpleNamespace as ns

config = ns(
    in_connection=ns(
        port=50000,
        max_connections=1,
    ),
    out_connection=ns(
        port='/dev/ttyUSB0',
        baudrate=500000,
    ),
)

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(('', config.in_connection.port))
s.listen(config.in_connection.max_connections)

try:
    while True:
        in_connection, client_ip = s.accept()
        out_connection = serial.Serial(
            config.out_connection.port, config.out_connection.baudrate
        )
        while ...:
            data = in_connection.recv(1024)
            out_connection.write(data)
        out_connection.close()
finally:
    s.close()
