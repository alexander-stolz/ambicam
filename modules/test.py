from collections import defaultdict
from dataclasses import dataclass

from numpy import array

a = array([1.4, 3, 5.5], dtype=int)
print(a)


class Color:
    def __init__(self, r=0, g=0, b=0):
        self.color = array([r, g, b])

    def __str__(self):
        return f"{self.color}"

    def __gt__(self, other):
        return self.color.max() > other.color.max()


class Pixels:
    def __init__(self, num):
        self.arr = defaultdict(Color)
        self.num = num

    def led_pos(self, pos):
        return pos % self.num

    def __setitem__(self, i, v):
        self.arr[self.led_pos(i)] = v

    def __getitem__(self, i):
        return self.arr[self.led_pos(i)]

    @property
    def max(self):
        return max(self.arr.values())


a = Pixels(300)
a[5] = Color(1, 8, 7)
a[6] = Color(8, 5, 0)

print(a.max)
