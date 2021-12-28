import cv2
from time import perf_counter

cam = cv2.VideoCapture(0)
cam.read()
t = perf_counter()
for i in range(100):
    cam.read()
print(perf_counter() - t)
