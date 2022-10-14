from datetime import datetime
import logging
from math import sqrt
import os
from random import gauss, randint
from typing import Iterable
import cv2
from time import sleep
from collections import deque
import threading
from numpy import apply_along_axis, array, convolve, linspace, average, zeros
from modules.servers import BridgeConnection, PrismatikConnection, DummyConnection
from modules.utils import config, TV
from abc import ABC, abstractmethod
from random import randint

if config.get('cameraInterface', 'cv2') == 'picamera':
    from modules.camera import PiCamera as Camera
else:
    from modules.camera import Cv2Camera as Camera


log = logging.getLogger(__name__)


class BGRColor:
    # just for type declaration
    bgr: Iterable = (0, 0, 0)


class ColorGrabber(ABC, threading.Thread):
    _instance = None
    running = False

    @abstractmethod
    def initialize(self):
        pass

    @abstractmethod
    def get_colors(self) -> Iterable[BGRColor]:
        pass

    @abstractmethod
    def teardown(self):
        pass

    def stop(self):
        self.running = False
        sleep(0.5)
        self.teardown()

    def __new__(cls, *args, **kwargs):
        if ColorGrabber._instance is None:
            log.debug("Creating new instance")
            ColorGrabber._instance = super(ColorGrabber, cls).__new__(
                cls, *args, **kwargs
            )
            super().__init__(ColorGrabber._instance)
            ColorGrabber._instance.connect_to_server()
            ColorGrabber._instance.initialize()
            ColorGrabber._instance.start()
            sleep(2)
        return ColorGrabber._instance

    def connect_to_server(self):
        log.debug("connect server")
        server_type = config.get('server', 'dummy')
        if server_type not in config and server_type != 'dummy':
            raise ValueError(f'Unknown server type: {server_type}')
        if server_type == 'prismatik':
            self.server = PrismatikConnection()
        elif server_type == 'bridge':
            self.server = BridgeConnection()
        else:
            self.server = DummyConnection()
        self.server.connect(**config.get(server_type, {}))

    def run(self):
        self.running = True
        try:
            while self.running:
                colors = self.get_colors()
                self.server.update_colors(colors)
        finally:
            self.running = False
            self.server.stop()
            ColorGrabber._instance = None
            log.debug('ColorGrabber stopped')


class CameraGrabber(ColorGrabber):
    _frame = None
    _indices = None
    _check_indices = None
    _last_colors = None
    auto_wb = False
    is_paused = False
    wb_queue_size = 30
    wb_correction = array([1, 1, 1])
    last_wb_corrections = deque(maxlen=150)
    last_wb_weights = deque(maxlen=150)

    def initialize(self):
        log.debug('connect camera')
        for property, value in config.get('v4120', {}).items():
            os.system(f'v4l2-ctl --set-ctrl={property}={value}')
        self.camera = Camera()
        self.camera.connect()
        self.is_paused = False
        self.tv = TV(host=config.tv.host, dt=1)
        self.last_wb_corrections = deque(maxlen=config.colors.get('queueSize', 150))
        self.last_wb_weights = deque(maxlen=config.colors.get('queueSize', 150))

    @property
    def frame(self):
        if not self.running:
            return
        frame = cv2.rectangle(
            self._frame,
            (config.window['left'], config.window['top']),
            (config.window['right'], config.window['bottom']),
            (0, 0, 255),
            2,
        )
        if self.auto_wb:
            frame = cv2.rectangle(
                self._frame,
                (config.checkWindow['left'], config.checkWindow['top']),
                (config.checkWindow['right'], config.checkWindow['bottom']),
                (255, 0, 0),
                2,
            )
        return frame

    @frame.setter
    def frame(self, frame):
        self._frame = frame

    def save_frame(self, filepath):
        if self.is_paused:
            return
        cv2.imwrite(filepath, self.frame)

    def stream(self):
        while self.running:
            ret, buffer = cv2.imencode('.jpg', self.frame)
            frame = buffer.tobytes()
            yield b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame + b'\r\n'
            sleep(0.3)

    @property
    def indices(self):
        if self._indices is not None:
            return self._indices

        indices = []
        check_indices = []
        self.auto_wb = False

        idx = -1
        for side in config.leds:
            if side['side'] in ('top', 'bottom'):
                for x in linspace(
                    (
                        config.window['left']
                        + side['from']
                        * (config.window['right'] - config.window['left'])
                    ),
                    (
                        config.window['left']
                        + side['to'] * (config.window['right'] - config.window['left'])
                    ),
                    int(side['leds']),
                ):
                    idx += 1
                    indices.append([int(config.window[side['side']]), int(x)])
                    if side.get('check'):
                        self.auto_wb = True
                        check_indices.append(
                            [idx, int(config.checkWindow[side['side']]), int(x)]
                        )

            if side['side'] in ('left', 'right'):
                for y in linspace(
                    (
                        config.window['top']
                        + side['from']
                        * (config.window['bottom'] - config.window['top'])
                    ),
                    (
                        config.window['top']
                        + side['to'] * (config.window['bottom'] - config.window['top'])
                    ),
                    int(side['leds']),
                ):
                    idx += 1
                    indices.append([int(y), int(config.window[side['side']])])
                    if side.get('check'):
                        self.auto_wb = True
                        check_indices.append(
                            [idx, int(y), int(config.checkWindow[side['side']])]
                        )

        self._indices = indices
        self._check_indices = check_indices
        return self._indices

    @property
    def check_indices(self):
        if self._check_indices is not None:
            return self._check_indices

        # re create all indices
        self._indices = None
        self.indices

        return self._check_indices

    @indices.setter
    def indices(self, indices):
        self._indices = indices

    def get_colors(self) -> Iterable[BGRColor]:
        # turn camera on if tv is on, else turn off and wait.
        if not self.tv.is_on:
            if not self.is_paused:
                log.debug(
                    '[%s] tv is off. disconnect camera.',
                    datetime.now().strftime('%H:%M:%S'),
                )
                self.camera.disconnect()
                self.is_paused = True
            sleep(1)
            return [(0, 0, 0)] * len(self.indices)
        elif self.is_paused:
            log.debug(
                '[%s] tv is on. reconnect camera.',
                datetime.now().strftime('%H:%M:%S'),
            )
            self.camera.connect()
            while self.camera.get_frame() is None:
                sleep(1)
            self.is_paused = False

        frame = self.camera.get_frame()
        colors = array([frame[y][x] for y, x in self.indices])

        if config.colors is not None:
            weights = array([config.colors.get(c, 1) for c in ['blue', 'green', 'red']])
            weights = weights / weights.max() * config.colors.get('brightness', 1)
            colors *= weights
        if config.smoothing and (self._last_colors is not None):
            colors = (
                config.smoothing * self._last_colors + (1 - config.smoothing) * colors
            )
        self._last_colors = colors
        self.frame = frame
        return colors

    def teardown(self):
        self.camera.disconnect()
        self.tv.stop()
        self._frame = None
        self._indices = None


class RainbowGrabber(ColorGrabber):
    _default_number_dots = 10
    _default_dot_width = 60
    # _default_blur_factor = 0.8

    def initialize(self):
        self.dots = []
        self.num_leds = sum(_['leds'] for _ in config.leds)
        for _ in range(self._default_number_dots):
            self.spawn_new_dot()
        self.blur_and_fade_dots()
        self.res = sum(self.dots) / len(self.dots) / 10

    def spawn_new_dot(self):
        dot = zeros((self.num_leds, 3), dtype=int)
        _color = array([randint(0, 255), randint(0, 255), randint(0, 255)]) * 10
        _pos = randint(0, self.num_leds)
        _width = gauss(self._default_dot_width, sqrt(self._default_dot_width))
        _min_idx = max(0, _pos - int(_width / 2))
        _max_idx = min(self.num_leds, _pos + int(_width / 2))
        for i in range(_min_idx, _max_idx):
            dot[i] = _color
        self.dots.append(dot)

    def remove_dead_dots(self):
        kill = []
        for i, dot in enumerate(self.dots):
            if dot.max() < 100:
                kill.append(i)
        for i in reversed(kill):
            del self.dots[i]

    def blur_and_fade_dots(self):
        # kernel = array([0.1, 0.79, 0.1])
        kernel = array([0.44, 0.24, 0.1, 0.24, 0.44])
        kernel /= sum(kernel) * 1.005
        for i, dot in enumerate(self.dots):
            self.dots[i] = apply_along_axis(
                lambda x: convolve(x, kernel, mode='same'), 0, dot
            )

    def get_colors(self):
        if len(self.dots) < self._default_number_dots:
            self.spawn_new_dot()

        self.blur_and_fade_dots()
        self.remove_dead_dots()

        res = 0.1 * sum(self.dots) / len(self.dots) + 0.9 * self.res
        self.res = res

        sleep(0.03)
        return res / 10

    def teardown(self):
        # nothing to do here. let the GC do its job.
        pass
