from abc import ABC, abstractmethod
from numpy import ndarray
from time import sleep
import cv2
from utils import config

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
        pass

    def disconnect(self):
        pass

    def get_frame(self):
        pass


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
