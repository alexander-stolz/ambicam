#!/usr/bin/env python
# -*- coding: utf-8 -*-

import uvicorn
from time import sleep
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

app = FastAPI()
app.mount('/static', StaticFiles(directory='static'), name='static')
templates = Jinja2Templates(directory="templates")


@app.get('/', response_class=HTMLResponse)
def root(request: Request):
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
    request: Request,
    red: float = Form(...),
    green: float = Form(...),
    blue: float = Form(...),
):
    config.colors = {
        'red': red / 100,
        'green': green / 100,
        'blue': blue / 100,
    }
    save_config()
    return RedirectResponse('/', status_code=status.HTTP_303_SEE_OTHER)


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


@app.post('/config')
def post_config(data):
    save_config(data=data)
    return {'status': 'ok'}


@app.get('/brightness/{val}')
def brightness(val: float):
    ColorGrabber().brightness = val
    config.brightness = ColorGrabber().brightness
    save_config()
    return RedirectResponse('/')


@app.get('/brightness_up')
def brightness_up():
    ColorGrabber().brightness += 5
    config.brightness = ColorGrabber().brightness
    save_config()
    return RedirectResponse('/')


@app.get('/brightness_down')
def brightness_down():
    ColorGrabber().brightness -= 5
    config.brightness = ColorGrabber().brightness
    save_config()
    return RedirectResponse('/')


@app.get('/saturation/{val}')
def saturation(val: float):
    ColorGrabber().saturation = val
    config.saturation = ColorGrabber().saturation
    save_config()
    return RedirectResponse('/')


@app.get('/saturation_up')
def saturation_up():
    ColorGrabber().saturation += 5
    config.saturation = ColorGrabber().saturation
    save_config()
    return RedirectResponse('/')


@app.get('/saturation_down')
def saturation_down():
    ColorGrabber().saturation -= 5
    config.saturation = ColorGrabber().saturation
    save_config()
    return RedirectResponse('/')


@app.get('/smoothing/{val}')
def saturation(val: float):
    config.smoothing = val
    save_config()
    return RedirectResponse('/')


@app.get('/smoothing_up')
def smoothing_up():
    config.smoothing += 0.05
    save_config()
    return RedirectResponse('/')


@app.get('/smoothing_down')
def smoothing_down():
    config.smoothing -= 0.05
    save_config()
    return RedirectResponse('/')


@app.get('/dt')
def dt():
    return {'dt': ColorGrabber().tn.dt}


@app.get('/window')
def window(cmd: str):
    print(cmd)
    if cmd == 'll':
        config.window['x0'] -= 5
    if cmd == 'lr':
        config.window['x0'] += 5
    if cmd == 'rl':
        config.window['x1'] -= 5
    if cmd == 'rr':
        config.window['x1'] += 5
    if cmd == 'oo':
        config.window['y0'] -= 5
    if cmd == 'ou':
        config.window['y0'] += 5
    if cmd == 'uo':
        config.window['y1'] -= 5
    if cmd == 'uu':
        config.window['y1'] += 5
    save_config()
    ColorGrabber().indices = None
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
