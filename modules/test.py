from collections import defaultdict
from dataclasses import dataclass

from numpy import array
import numpy as np


a = np.zeros((8, 3), dtype=np.int)

a[1] = np.array([1, 2, 1])
a[2] = np.array([1, 1, 1])
a[3] = np.array([3, 3, 3])
a[4] = np.array([3, 3, 3])
a[5] = np.array([1, 1, 1])
a[6] = np.array([1, 1, 1])

kernel = np.array([0.1, 0.9, 0.1])
a = np.apply_along_axis(lambda x: np.convolve(x, kernel, mode='same'), 0, a)

print(a)
