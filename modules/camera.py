from abc import ABC, abstractmethod
from numpy import ndarray
from time import sleep
import cv2
from io import BytesIO
import numpy as np
from modules.utils import config


class AbstractCamera(ABC):
    @abstractmethod
    def connect(self) -> bool:
        pass

    @abstractmethod
    def disconnect(self):
        pass

    @abstractmethod
    def get_frame(self) -> ndarray:
        pass


class PiCamera(AbstractCamera):
    def connect(self):
        # should be installed by default on raspberry
        try:
            import picamera
        except ModuleNotFoundError:
            raise ModuleNotFoundError(
                'picamera not installed. '
                'try: sudo apt install python-picamera python3-picamera'
            )
        self.vid = picamera.PiCamera()
        self.vid.resolution = (config.resolution['width'], config.resolution['height'])
        self.vid.framerate = config.fps.get('capture', 30)
        self.vid.start_preview()
        sleep(2)
        g = self.vid.awb_gains
        self.vid.awb_mode = 'off'
        self.vid.awb_gains = g

    def disconnect(self):
        self.vid.close()

    def get_frame(self):
        with picamera.array.PiRGBArray(self.vid) as stream:
            self.vid.capture(stream, format='bgr')
            frame = stream.array
        return ndarray.astype(frame, dtype=float)


class Cv2Camera(AbstractCamera):
    _frame = None

    def connect(self):
        self.vid = cv2.VideoCapture(0)
        self.vid.set(cv2.CAP_PROP_FRAME_WIDTH, config.resolution['width'])
        self.vid.set(cv2.CAP_PROP_FRAME_HEIGHT, config.resolution['height'])
        self.vid.set(cv2.CAP_PROP_FPS, config.fps.get('capture', 30))
        return True

    def disconnect(self):
        self.vid.release()

    def get_frame(self):
        success, frame = self.vid.read()
        frame = ndarray.astype(frame, dtype=float)
        if success:
            self._frame = frame
        return self._frame
