import json
from types import SimpleNamespace


def get_config(filename='config.json'):
    with open(filename) as f:
        config = json.load(f)
    return SimpleNamespace(**config)
