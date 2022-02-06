#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import uvicorn
import os
from time import sleep
from collections import deque
from fastapi import FastAPI, Form, Request, status
from fastapi.responses import (
    HTMLResponse,
    RedirectResponse,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from modules.colorgrabber import ColorGrabber
from modules.utils import config, save_config

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG, filename='log.log', filemode='w')

# create static folder if not exists
if not os.path.exists('static'):
    os.mkdir('static')

app = FastAPI()
app.mount('/static', StaticFiles(directory='static'), name='static')
templates = Jinja2Templates(directory="templates")


@app.get('/', response_class=HTMLResponse)
def index(request: Request):
    color_grabber = ColorGrabber()
    if color_grabber.running:
        color_grabber.save_frame('static/frame.jpg')
        # return render_template('index.html', config=config)
        return templates.TemplateResponse(
            'index.html',
            {
                'request': request,
                'config': config,
            },
        )
    return 'not running'


@app.post('/colors')
def colors(
    red: float = Form(...),
    green: float = Form(...),
    blue: float = Form(...),
    brightness: float = Form(...),
):
    max_val = max(red, green, blue)
    config.colors = {
        'red': red / max_val,
        'green': green / max_val,
        'blue': blue / max_val,
        'brightness': brightness / 100,
    }
    save_config()
    return RedirectResponse('/', status_code=status.HTTP_303_SEE_OTHER)


@app.get('/colors/{cmd}')
def colors_cmd(cmd: str):
    new_colors = config.colors
    if cmd == 'red_up':
        new_colors['red'] += 0.05
    if cmd == 'red_down':
        new_colors['red'] -= 0.05
    if cmd == 'green_up':
        new_colors['green'] += 0.05
    if cmd == 'green_down':
        new_colors['green'] -= 0.05
    if cmd == 'blue_up':
        new_colors['blue'] += 0.05
    if cmd == 'blue_down':
        new_colors['blue'] -= 0.05
    if cmd == 'brightness_up':
        new_colors['brightness'] += 0.05
        new_colors['brightness'] = max(min(new_colors['brightness'], 1), 0)
    if cmd == 'brightness_down':
        new_colors['brightness'] -= 0.05
        new_colors['brightness'] = max(min(new_colors['brightness'], 1), 0)
    if cmd == 'auto_colors' and ColorGrabber().wb_correction is not None:
        new_colors['red'] *= ColorGrabber().wb_correction[0]
        new_colors['green'] *= ColorGrabber().wb_correction[1]
        new_colors['blue'] *= ColorGrabber().wb_correction[2]
    return colors(
        new_colors['red'],
        new_colors['green'],
        new_colors['blue'],
        new_colors['brightness'],
    )


@app.get('/stream')
async def stream():
    color_grabber = ColorGrabber()
    return StreamingResponse(
        color_grabber.stream(), media_type='multipart/x-mixed-replace; boundary=frame'
    )


@app.get('/start')
def start():
    color_grabber = ColorGrabber()
    return {'running': color_grabber.running}


@app.get('/start/force')
def force_start():
    ColorGrabber._instance = None
    color_grabber = ColorGrabber()
    return {'running': color_grabber.running}


@app.get('/stop')
def stop():
    ColorGrabber().stop()
    sleep(0.5)
    return {'running': ColorGrabber.running}


@app.get('/config')
def get_config():
    return config


@app.get('/logs')
def get_logs():
    return open('log.log', 'r').readlines()


@app.post('/config')
def post_config(data):
    save_config(data=data)
    return {'status': 'ok'}


@app.get('/smoothing/{val}')
def smoothing(val: float):
    config.smoothing = val
    save_config()
    return RedirectResponse('/')


@app.get('/smoothing_up')
def smoothing_up():
    config.smoothing += (1 - config.smoothing) * 0.15
    save_config()
    return RedirectResponse('/')


@app.get('/smoothing_down')
def smoothing_down():
    config.smoothing -= (1 - config.smoothing) * 0.15
    save_config()
    return RedirectResponse('/')


@app.get('/saturation/{val}')
def saturation(val: int):
    config.v4l2['saturation'] = val
    os.system(f'v4l2-ctl --set-ctrl=saturation={config.v4l2["saturation"]}')
    save_config()
    return RedirectResponse('/')


@app.get('/saturation_up')
def saturation_up():
    config.v4l2['saturation'] += 10
    os.system(f'v4l2-ctl --set-ctrl=saturation={config.v4l2["saturation"]}')
    save_config()
    return RedirectResponse('/')


@app.get('/saturation_down')
def saturation_down():
    config.v4l2['saturation'] -= 10
    os.system(f'v4l2-ctl --set-ctrl=saturation={config.v4l2["saturation"]}')
    save_config()
    return RedirectResponse('/')


@app.get('/dt')
def dt():
    return {'dt': ColorGrabber().tn.dt}


@app.get('/wb')
def wb():
    if ColorGrabber().wb_correction is None:
        return 'automatic white balance correction is disabled'
    return dict(
        red=ColorGrabber().wb_correction[0],
        green=ColorGrabber().wb_correction[1],
        blue=ColorGrabber().wb_correction[2],
    )


@app.get('/wb/queue/{val}')
def set_wb_frames(val: int):
    config.colors['queueSize'] = val
    save_config()
    ColorGrabber().last_wb_corrections = deque(
        maxlen=config.colors.get('queueSize', 30)
    )
    ColorGrabber().last_wb_weights = deque(maxlen=config.colors.get('queueSize', 30))
    return RedirectResponse('/')


@app.get('/wb/off')
def wb():
    ColorGrabber().auto_wb = False
    return RedirectResponse('/')


@app.get('/wb/on')
def wb():
    ColorGrabber().auto_wb = True
    return RedirectResponse('/')


@app.get('/window')
def window(cmd: str):
    print(cmd)
    if cmd == 'll':
        config.window['left'] -= 5
    if cmd == 'lr':
        config.window['left'] += 5
    if cmd == 'rl':
        config.window['right'] -= 5
    if cmd == 'rr':
        config.window['right'] += 5
    if cmd == 'oo':
        config.window['top'] -= 5
    if cmd == 'ou':
        config.window['top'] += 5
    if cmd == 'uo':
        config.window['bottom'] -= 5
    if cmd == 'uu':
        config.window['bottom'] += 5
    save_config()
    ColorGrabber().indices = None
    return RedirectResponse('/')


@app.get('/checkwindow')
def checkwindow(cmd: str):
    print(cmd)
    if cmd == 'll':
        config.checkWindow['left'] -= 5
    if cmd == 'lr':
        config.checkWindow['left'] += 5
    if cmd == 'rl':
        config.checkWindow['right'] -= 5
    if cmd == 'rr':
        config.checkWindow['right'] += 5
    if cmd == 'oo':
        config.checkWindow['top'] -= 5
    if cmd == 'ou':
        config.checkWindow['top'] += 5
    if cmd == 'uo':
        config.checkWindow['bottom'] -= 5
    if cmd == 'uu':
        config.checkWindow['bottom'] += 5
    save_config()
    ColorGrabber()._check_indices = None
    return RedirectResponse('/')


def serve():
    uvicorn.run(
        app,
        host=config.connection.get('host', '0.0.0.0'),
        port=config.connection.get('port', 5000),
        log_level='info',
    )


if __name__ == '__main__':
    serve()
