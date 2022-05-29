from copy import copy, deepcopy
import logging
from math import sqrt
import os
from random import gauss, randint
from typing import Iterable, List
import cv2
from time import sleep
from collections import defaultdict, deque
import threading
from numpy import array, linspace, average, zeros
from modules.servers import BridgeConnection, PrismatikConnection, DummyConnection
from modules.utils import config
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

    def get_color_correction(self, frame):
        if self._last_colors is None:
            return array([1, 1, 1])
        sent_colors = array([self._last_colors[i] for i, *_ in self.check_indices])
        seen_colors = array([frame[y][x] for _, y, x in self.check_indices])
        sent_weights = sum(sent_colors.T)
        seen_weights = sum(seen_colors.T)
        combined_weights = sent_weights * seen_weights
        sent_avg = average(sent_colors, weights=combined_weights, axis=0)
        seen_avg = average(seen_colors, weights=combined_weights, axis=0)
        if all(seen_avg):
            factors = sent_avg / seen_avg
            factors /= max(factors)
            weight = sum(combined_weights)
            if (
                not any(self.last_wb_weights)
                or weight / max(self.last_wb_weights) > 0.2
            ):
                self.last_wb_weights.append(weight)
                self.last_wb_corrections.append(factors)
                self.wb_correction = average(
                    self.last_wb_corrections,
                    weights=self.last_wb_weights,
                    axis=0,
                )
        return self.wb_correction

    def get_colors(self) -> Iterable[BGRColor]:
        frame = self.camera.get_frame()

        if config.blur:
            frame = cv2.GaussianBlur(frame, (config.blur, config.blur), 0)
        colors = array([frame[y][x] for y, x in self.indices])

        if self.auto_wb:
            wb_correction_ = self.get_color_correction(frame)
            if config.auto_wb:
                colors *= wb_correction_
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
        self._frame = None
        self._indices = None


class RainbowGrabber(ColorGrabber):
    _default_number_dots = 10

    class Color:
        # floats are alowed here to ensure smooth transitions. server.send_colors()
        # has to deal with int conversion.
        def __init__(self, b=0, g=0, r=0):
            self.values = [b, g, r]

        def __add__(self, other):
            ret = tuple(self.values[i] + other.values[i] for i in range(3))
            _max = max(ret)
            if _max > 255:
                ret = tuple(ret[i] / _max * 255 for i in range(3))
            return RainbowGrabber.Color(*ret)

        def __mul__(self, val):
            ret = tuple(self.values[i] * val for i in range(3))
            return RainbowGrabber.Color(*ret)

        def __gt__(self, other):
            return max(self.values) > max(other.values)

        def __getitem__(self, i):
            return self.values[i]

        def __str__(self):
            return str(self.values)

        def __repr__(self):
            return str(self.values)

        @property
        def max(self):
            return max(self.values)

    class Pixels:
        def __init__(self, num):
            self.colors = defaultdict(RainbowGrabber.Color)
            self.num = num

        def led_pos(self, pos):
            return pos % self.num

        def __setitem__(self, i, v):
            self.colors[self.led_pos(i)] = v

        def __getitem__(self, i):
            return self.colors[self.led_pos(i)]

        def __mul__(self, v):
            for i in self.colors:
                self.colors[i] *= v
            return self

        def __str__(self):
            return str(self.colors.items())

        def __repr__(self):
            return str(self.colors.items())

        def items(self):
            return self.colors.items()

        def values(self):
            return tuple(self.colors[i] for i in range(self.num))

        @property
        def max(self):
            return max(self.colors.values()).max

        @property
        def keys(self):
            return self.colors.keys()

    class Dot:
        _default_dot_width = 60
        _default_blur_width = 1
        _default_blur_factor = 0.8
        _default_fade_factor = 0.995

        def __init__(self, pos, color):
            num_leds = sum(_['leds'] for _ in config.leds)
            self.pixels = RainbowGrabber.Pixels(num_leds)

            width = gauss(self._default_dot_width, sqrt(self._default_dot_width))
            for i in range(pos - int(width / 2), pos + int(width / 2)):
                self.pixels[i] = color
            self.blur()

        def __getitem__(self, i):
            return self.pixels[i]

        @property
        def indices(self):
            return self.pixels.keys

        # @profile
        def blur(self):
            old_pixels = tuple(
                (i, RainbowGrabber.Color(*self.pixels[i].values)) for i in self.indices
            )
            for pos, col in old_pixels:
                for d_pos in range(self._default_blur_width):
                    self.pixels[pos - d_pos - 1] = (
                        self.pixels[pos - d_pos - 1] * (1 - self._default_blur_factor)
                        + col * self._default_blur_factor
                    )
                    self.pixels[pos + d_pos + 1] = (
                        self.pixels[pos + d_pos + 1] * (1 - self._default_blur_factor)
                        + col * self._default_blur_factor
                    )

        def fade(self):
            self.pixels *= self._default_fade_factor

        @property
        def dead(self):
            return self.pixels.max < 10

    def initialize(self):
        self.dots = []
        self.num_leds = sum(_['leds'] for _ in config.leds)
        for _ in range(self._default_number_dots):
            self.spawn_new_dot()

    def spawn_new_dot(self):
        _pos = randint(0, self.num_leds)
        _color = RainbowGrabber.Color(randint(0, 255), randint(0, 255), randint(0, 255))
        self.dots.append(self.Dot(_pos, _color))
        print(len(self.dots))

    def remove_dead_dots(self):
        for dot in self.dots[:]:
            if dot.dead:
                self.dots.remove(dot)

    def get_colors(self):
        if len(self.dots) < self._default_number_dots:
            self.spawn_new_dot()
        for dot in self.dots:
            dot.blur()
            dot.fade()
        self.remove_dead_dots()

        res = RainbowGrabber.Pixels(self.num_leds)
        for dot in self.dots:
            for i in dot.indices:
                res[i] += dot[i]
        sleep(0.03)
        return res.values()

    def teardown(self):
        # nothing to do here. let the GC do its job.
        pass
