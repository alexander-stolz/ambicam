import json
from types import SimpleNamespace
from time import sleep, perf_counter as time
import threading
from numpy import arange, array, linspace
from modules.utils import config


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
        if not config.telnet.get('host'):
            return
        import telnetlib

        self.connection = telnetlib.Telnet(self.host, self.port)
        self.connection.write(b'lock\n')
        self.start()

    def disconnect(self):
        self.running = False
        self.connection.write(b'unlock\n')
        self.connection.write(b'exit\n')
        self.connection.close()

    def send(self, command):
        self.connection.write(command.encode('ascii') + b'\n')
        # return self.connection.read_until(b'\n').decode('ascii').strip()

    def send_colors(self, colors):
        cmd = (
            'setcolor:'
            + ';'.join(
                f'{n}-{int(c[2])},{int(c[1])},{int(c[0])}'
                for n, c in enumerate(colors, start=1)
            )
            + ';'
        )
        t = time()
        self.send(cmd)
        return time() - t

    def run(self):
        self.running = True
        last_colors = None
        new_colors = None
        smoothing = int(config.fps.get('interpolation'))
        while self.running:
            if not self.new_colors:
                continue
            if not smoothing:
                self.send_colors(self.new_colors)
                self.new_colors = None
                continue
            _t = time()
            last_colors = new_colors or self.new_colors
            new_colors = self.new_colors
            self.new_colors = None
            colors_slope = (array(new_colors, float) - array(last_colors, float)) / (
                self.dt or 0.1
            )
            dt_1 = time() - _t
            for t in linspace(
                self.dt / smoothing,
                self.dt,
                smoothing,
            ):
                if self.new_colors:
                    print('zu früh: ', t)
                    break
                _colors = last_colors + colors_slope * t
                dt_2 = self.send_colors(_colors)
                _sleep = (self.dt - dt_1) / (smoothing + 1) - dt_2
                if _sleep > 0:
                    sleep(_sleep)
                else:
                    print('too much smoothing')
        self.disconnect()

    @property
    def colors(self):
        return self.new_colors

    @colors.setter
    def colors(self, colors):
        """
        colors: list of BGR colors
        """
        self.dt = 0.1 * (time() - self.last_time) + 0.9 * self.dt
        self.last_time = time()
        self.new_colors = colors
        # print('\r', self.dt, end='')

    def stop(self):
        self.running = False
