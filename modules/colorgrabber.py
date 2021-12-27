import cv2
from time import sleep
from numpy import arange, array, linspace
import threading
from modules.telnet import TelnetConnection
from modules.utils import config


class ColorGrabber(threading.Thread):
    _frame = None
    _instance = None
    _indices = None
    running = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            print("Creating new instance")
            cls._instance = super(ColorGrabber, cls).__new__(cls, *args, **kwargs)
            super().__init__(cls._instance)
            cls._instance.connect_to_telnet()
            cls._instance.connect_to_camera()
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
        self.vid = cv2.VideoCapture(0)
        self.vid.set(cv2.CAP_PROP_FRAME_WIDTH, config.resolution['width'])
        self.vid.set(cv2.CAP_PROP_FRAME_HEIGHT, config.resolution['height'])
        self.vid.set(cv2.CAP_PROP_FPS, config.fps.get('capture', 30))

    @property
    def brightness(self):
        return self.vid.get(cv2.CAP_PROP_BRIGHTNESS)

    @brightness.setter
    def brightness(self, value):
        self.vid.set(cv2.CAP_PROP_BRIGHTNESS, value)

    @property
    def saturation(self):
        return self.vid.get(cv2.CAP_PROP_SATURATION)

    @saturation.setter
    def saturation(self, value):
        self.vid.set(cv2.CAP_PROP_SATURATION, value)

    @property
    def frame(self):
        if not self.running:
            return
        frame = cv2.rectangle(
            self._frame,
            (config.window['x0'], config.window['y0']),
            (config.window['x1'], config.window['y1']),
            (0, 0, 255),
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
        for x in linspace(
            (config.window['x0'] + config.window['x1']) / 2,
            config.window['x1'],
            int(config.lights['bottom'] / 2),
        ):
            indices.append([int(config.window['y1']), int(x)])

        for y in linspace(
            config.window['y1'], config.window['y0'], config.lights['right']
        ):
            indices.append([int(y), int(config.window['x1'])])

        for x in linspace(
            config.window['x1'], config.window['x0'], config.lights['top']
        ):
            indices.append([int(config.window['y0']), int(x)])

        for y in linspace(
            config.window['y0'], config.window['y1'], config.lights['left']
        ):
            indices.append([int(y), int(config.window['x0'])])

        for x in linspace(
            config.window['x0'],
            (config.window['x0'] + config.window['x1']) / 2,
            int(config.lights['bottom'] / 2),
        ):
            indices.append([int(config.window['y1']), int(x)])

        self._indices = indices
        return self._indices

    @indices.setter
    def indices(self, indices):
        self._indices = indices

    def get_colors(self, frame):
        colors = [frame[y][x] for y, x in self.indices]
        self.frame = frame
        return colors

    def run(self):
        self.running = True
        try:
            while self.running:
                success, frame = self.vid.read()
                if not success:
                    sleep(0.1)
                    continue
                if config.blur:
                    frame = cv2.GaussianBlur(frame, (config.blur, config.blur), 0)
                if config.smoothing and (self._frame is not None):
                    frame = (
                        config.smoothing * self._frame + (1 - config.smoothing) * frame
                    )
                colors = self.get_colors(frame)
                # color format: BGR
                self.tn.colors = colors
        finally:
            self.running = False
            self.vid.release()
            cv2.destroyAllWindows()
            self.tn.stop()
            ColorGrabber._instance = None
            self._frame = None
            self._indices = None

    def stop(self):
        self.running = False
