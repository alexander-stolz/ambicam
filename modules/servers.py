from abc import ABC, abstractmethod
from hashlib import new
import logging
from time import sleep, perf_counter as time
import threading
from typing import List, Tuple
from numpy import array, linspace
from modules.utils import config


log = logging.getLogger()


class Connection(ABC, threading.Thread):
    @abstractmethod
    def connect(self, **kwargs):
        "kwargs from config"
        # < connection logic >
        self.start()

    @abstractmethod
    def disconnect(self):
        self.running = False
        # < disconnect logic >

    @abstractmethod
    def send_colors(self, colors):
        pass

    def __init__(self):
        super().__init__()
        self.connection = None
        self.last_time = None
        self.dt = 0.1
        self.last_time = time()
        self.new_colors = None
        self.last_command = ''

    def run(self):
        self.running = True
        last_colors = None
        new_colors = None
        smoothing = int(config.fps.get('interpolation'))
        while self.running:
            if self.new_colors is None:
                sleep(0.01)
                continue
            if not smoothing:
                self.send_colors(self.new_colors)
                last_colors = self.new_colors
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
                    log.warning('too early! t = %s', t)
                    break
                _colors = last_colors + colors_slope * t
                dt_2 = self.send_colors(_colors)
                _sleep = (self.dt - dt_1) / (smoothing + 1) - dt_2
                if _sleep > 0:
                    sleep(_sleep)
                else:
                    log.warning('too much smoothing')
        self.send_colors([[0, 0, 0]] * sum(_['leds'] for _ in config.leds))
        self.disconnect()

    def stop(self):
        self.running = False

    def update_colors(self, bgr_colors: List[Tuple[int, int, int]]):
        self.dt = 0.1 * (time() - self.last_time) + 0.9 * self.dt
        self.last_time = time()
        self.new_colors = bgr_colors[:]


class DummyConnection(Connection):
    def connect(self, **kwargs):
        print('connect')
        self.start()

    def disconnect(self):
        print('disconnect')

    def send_colors(self, colors):
        print(colors)


class BridgeConnection(Connection):
    def __init__(self):
        super().__init__()

    def connect(self, **kwargs):
        import socket

        self.host = kwargs.get('host')
        self.port = kwargs.get('port')

        self.connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connection.connect((self.host, self.port))
        self.start()

    def disconnect(self):
        self.running = False
        self.connection.close()

    def send_colors(self, colors):
        num = len(colors) - 1
        hi = num >> 8
        lo = num & 0xFF
        checksum = hi ^ lo ^ 0x55
        try:
            header = b'Ada' + bytes([hi, lo, checksum])
        except ValueError:
            log.error(
                'ValueError: num: %s hi: %s lo: %s checksum: %s', num, hi, lo, checksum
            )
            return 0
        payload = bytes(
            int(item) for color in colors for item in (color[1], color[2], color[0])
        )
        self.connection.send(header + payload)
        sleep(0.04)


class PrismatikConnection(Connection):
    def __init__(self):
        super().__init__()

    def connect(self, **kwargs):
        import telnetlib

        self.host = kwargs.get('host')
        self.port = kwargs.get('port')

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

    def send_colors(self, colors):
        cmd = (
            'setcolor:'
            + ';'.join(
                f'{n}-{int(c[2])},{int(c[1])},{int(c[0])}'
                for n, c in enumerate(colors, start=1)
            )
            + ';'
        )
        if cmd == self.last_command:
            return 0
        self.last_command = cmd
        t = time()
        self.send(cmd)
        return time() - t
