import json
from types import SimpleNamespace
from time import sleep, time
import threading
from numpy import arange, array


def get_config(filename='config.json'):
    with open(filename) as f:
        config = json.load(f)
    return SimpleNamespace(**config)


class TelnetConnection(threading.Thread):
    def __init__(self, host, port):
        super().__init__()
        self.host = host
        self.port = port
        self.connection = None
        self.last_time = None
        self.dt = 0.1
        self.last_time = time()
        self.new_colors = None

    def connect(self):
        import telnetlib

        self.connection = telnetlib.Telnet(self.host, self.port)
        self.connection.write(b'lock\n')
        self.start()

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
                f'{n}-{int(c[0])},{int(c[1])},{int(c[2])}'
                for n, c in enumerate(colors, start=1)
            )
            + ';'
        )
        print(self.send(cmd))

    def run(self):
        self.running = True
        last_colors = None
        new_colors = None
        while self.running:
            if not self.new_colors:
                continue
            last_colors = last_colors or self.new_colors
            new_colors = self.new_colors
            self.new_colors = None
            color_steep = (array(new_colors) - array(last_colors)) / (self.dt or 0.1)
            for t in arange(0, self.dt, config.fps.get('output_dt')):
                if self.new_colors:
                    break
                _colors = last_colors + color_steep * t
                self.send_colors(_colors)
                sleep(config.fps.get('output_dt'))
        self.disconnect()

    @property
    def colors(self):
        return

    @colors.setter
    def colors(self, colors):
        self.dt = 0.1 * (time() - self.last_time) + 0.9 * self.dt
        self.last_time = time()
        self.new_colors = colors
        print(self.dt)

    def stop(self):
        self.running = False


config = get_config()
