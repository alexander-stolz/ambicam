import logging
import os
import cv2
from time import sleep
from collections import deque
import threading
from numpy import array, linspace, average
from modules.telnet import TelnetConnection
from modules.utils import config

if config.get('cameraInterface', 'cv2') == 'picamera':
    from modules.camera import PiCamera as Camera
else:
    from modules.camera import Cv2Camera as Camera


log = logging.getLogger(__name__)


class ColorGrabber(threading.Thread):
    _frame = None
    _instance = None
    _indices = None
    _check_indices = None
    _last_colors = None
    running = False
    auto_wb = False
    wb_queue_size = 30
    wb_correction = array([1, 1, 1])
    last_wb_corrections = deque(maxlen=150)
    last_wb_weights = deque(maxlen=150)

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            print("Creating new instance")
            cls._instance = super(ColorGrabber, cls).__new__(cls, *args, **kwargs)
            super().__init__(cls._instance)
            cls._instance.connect_to_telnet()
            cls._instance.connect_to_camera()
            cls._instance.last_wb_corrections = deque(
                maxlen=config.colors.get('queueSize', 150)
            )
            cls._instance.last_wb_weights = deque(
                maxlen=config.colors.get('queueSize', 150)
            )
            cls._instance.start()
            for _ in range(10):
                print(_)
                if cls._instance._frame is None:
                    sleep(0.1)
                else:
                    break
        return cls._instance

    def connect_to_telnet(self):
        print("connect telnet")
        self.tn = TelnetConnection(config.telnet['host'], config.telnet['port'])
        self.tn.connect()

    def connect_to_camera(self):
        print("connect camera")
        for property, value in config.get('v4120', {}).items():
            os.system(f'v4l2-ctl --set-ctrl={property}={value}')
        self.camera = Camera()
        self.camera.connect()

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

    def get_colors(self, frame):
        colors = array([frame[y][x] for y, x in self.indices])
        if config.auto_wb:
            colors *= self.get_color_correction(frame)
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

    def run(self):
        self.running = True
        try:
            while self.running:
                frame = self.camera.get_frame()
                if config.blur:
                    frame = cv2.GaussianBlur(frame, (config.blur, config.blur), 0)
                colors = self.get_colors(frame)
                # color format: BGR
                self.tn.colors = colors
        finally:
            self.running = False
            self.camera.disconnect()
            self.tn.stop()
            ColorGrabber._instance = None
            self._frame = None
            self._indices = None

    def stop(self):
        self.running = False
