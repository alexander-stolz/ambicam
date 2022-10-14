import json
import subprocess
import threading
from time import sleep


class AttrDict(dict):
    def __init__(self, *args, **kwargs):
        self.update(*args, **kwargs)

    def __getattr__(self, attr):
        attr = self.get(attr)
        return attr

    def __setattr__(self, key, value):
        self.__setitem__(key, value)

    def __setitem__(self, key, value):
        super(AttrDict, self).__setitem__(key, value)
        self.__dict__.update({key: value})

    def __delattr__(self, item):
        self.__delitem__(item)

    def __delitem__(self, key):
        super(AttrDict, self).__delitem__(key)

    def __getstate__(self):
        return self.__dict__

    def __setstate__(self, d):
        self.__dict__.update(d)

    def to_json(self):
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)


class TV(threading.Thread):
    _is_on = None

    def __init__(self, host=None, dt=60):
        super().__init__()
        self.host = host
        self.dt = dt
        if host is None:
            # if tv:host not in config -> always return True
            self._is_on = True
            return
        self.start()

    def ping(self):
        self._is_on = subprocess.call(['ping', '-c', '1', '-w1', self.host]) == 0
        return self._is_on

    def run(self):
        self.running = True
        while self.running:
            self.ping()
            sleep(self.dt)

    def stop(self):
        self.running = False

    @property
    def is_on(self):
        if self._is_on is None:
            self.ping()
        if self._is_on:
            self.dt = 30
            return True
        self.dt = 2
        return False


def get_config(filename='config.json'):
    with open(filename) as f:
        config = json.load(f, object_hook=AttrDict)
    return config


def save_config(data=None, filename='config.json'):
    data = data or config
    with open(filename, 'w') as f:
        json.dump(config, f, indent=4)


config = get_config()
