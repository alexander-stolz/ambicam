import cv2
from time import sleep
from numpy import arange, array, linspace
from modules.utils import get_config
from modules.telnet import TelnetConnection
import threading

config = get_config()


class ColorGrabber(threading.Thread):
    _frame = None
    running = False
    _instance = None

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

    def get_colors(self, frame, show=True):
        colors = []
        for y in linspace(
            config.window['y1'], config.window['y0'], config.ligths['left']
        ):
            colors.append(frame[int(y), int(config.window['x0'])])
            if show:
                frame = cv2.rectangle(
                    frame,
                    (config.window['x0'] - 5, int(y) - 5),
                    (config.window['x0'] + 5, int(y + 5)),
                    colors[-1].tolist(),
                    10,
                )
        for x in linspace(
            config.window['x0'], config.window['x1'], config.ligths['top']
        ):
            colors.append(frame[int(config.window['y0']), int(x)])
            if show:
                frame = cv2.rectangle(
                    frame,
                    (int(x) - 5, config.window['y0'] - 5),
                    (int(x) + 5, config.window['y0'] + 5),
                    colors[-1].tolist(),
                    10,
                )
        for y in linspace(
            config.window['y0'], config.window['y1'], config.ligths['right']
        ):
            colors.append(frame[int(y), int(config.window['x1'])])
            if show:
                frame = cv2.rectangle(
                    frame,
                    (config.window['x1'] - 5, int(y) - 5),
                    (config.window['x1'] + 5, int(y + 5)),
                    colors[-1].tolist(),
                    10,
                )
        for x in linspace(
            config.window['x1'], config.window['x0'], config.ligths['bottom']
        ):
            colors.append(frame[int(config.window['y1']), int(x)])
            if show:
                frame = cv2.rectangle(
                    frame,
                    (int(x) - 5, config.window['y1'] - 5),
                    (int(x) + 5, config.window['y1'] + 5),
                    colors[-1].tolist(),
                    10,
                )
        self.frame = frame
        return colors

    def run(self):
        self.running = True
        try:
            while self.running:
                _, frame = self.vid.read()
                frame_blured = cv2.GaussianBlur(frame, (config.blur, config.blur), 0)
                colors = self.get_colors(frame_blured)
                self.tn.colors = colors
                sleep(config.fps.get('capture_dt'))
        finally:
            self.running = False
            self.vid.release()
            cv2.destroyAllWindows()
            self.tn.disconnect()
            ColorGrabber._instance = None
            self._frame = None

    def stop(self):
        self.running = False