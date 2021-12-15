class TelnetConnection:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.connection = None

    def connect(self):
        import telnetlib

        self.connection = telnetlib.Telnet(self.host, self.port)
        self.connection.write(b'lock\n')

    def disconnect(self):
        self.connection.write(b'unlock\n')
        self.connection.write(b'exit\n')
        self.connection.close()

    def send(self, command):
        self.connection.write(command.encode('ascii') + b'\n')
        return self.connection.read_until(b'\n').decode('ascii').strip()

    def send_colors(self, colors):
        cmd = (
            'setcolor:'
            + ';'.join(
                f'{n}-{c[0]},{c[1]},{c[2]}' for n, c in enumerate(colors, start=1)
            )
            + ';'
        )
        self.send(cmd)

    @property
    def colors(self):
        return

    @colors.setter
    def colors(self, colors):
        self.send_colors(colors)
