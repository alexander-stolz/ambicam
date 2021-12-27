import json
from types import SimpleNamespace


class AttrDict(dict):
    def __init__(self, *args, **kwargs):
        self.update(*args, **kwargs)

    def __getattr__(self, attr):
        attr = self.get(attr)
        # if isinstance(attr, dict):
        #     return AttrDict(attr)
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


def get_config(filename='config.json'):
    with open(filename) as f:
        config = json.load(f)
    return AttrDict(**config)


def save_config(data=None, filename='config.json'):
    data = data or config
    with open(filename, 'w') as f:
        json.dump(config, f, indent=4)


config = get_config()
