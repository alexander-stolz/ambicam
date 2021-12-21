# https://fastapi.tiangolo.com/advanced/custom-response/?h=stream#streamingresponse
# https://www.reddit.com/r/FastAPI/comments/lqximx/is_fastapi_capable_of_live_streaming_video/
from starlette.responses import RedirectResponse, Response, StreamingResponse
import uvicorn
from time import sleep
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from modules.colorgrabber import ColorGrabber
from modules.utils import config, save_config

app = FastAPI()
app.mount('/static', StaticFiles(directory='static'), name='static')


@app.get('/', response_class=HTMLResponse)
def root():
    color_grabber = ColorGrabber()
    if color_grabber.running:
        color_grabber.save_frame('static/frame.jpg')
        return open('templates/index.html').read()
    return 'not running'


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


@app.get('/stop')
def stop():
    ColorGrabber().stop()
    sleep(0.5)
    return {'running': ColorGrabber.running}


@app.get('/brightness/{brightness}')
def brightness(brightness: float):
    ColorGrabber().brightness = brightness
    config.brightness = ColorGrabber().brightness
    save_config()
    return RedirectResponse('/')


@app.get('/saturation/{sat}')
def saturation(sat: float):
    ColorGrabber().saturation = sat
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
def saturation_up():
    ColorGrabber().saturation -= 5
    config.saturation = ColorGrabber().saturation
    save_config()
    return RedirectResponse('/')


@app.get('/brightness_up')
def brightness_up():
    ColorGrabber().brightness += 5
    config.brightness = ColorGrabber().brightness
    save_config()
    return RedirectResponse('/')


@app.get('/brightness_down')
def brightness_up():
    ColorGrabber().brightness -= 5
    config.brightness = ColorGrabber().brightness
    save_config()
    return RedirectResponse('/')


@app.get('/dt')
def dt():
    return {'dt': ColorGrabber().tn.dt}


@app.get('/window')
def window(cmd: str):
    print(cmd)
    if cmd == 'll':
        config.window['x0'] -= 10
    if cmd == 'lr':
        config.window['x0'] += 10
    if cmd == 'rl':
        config.window['x1'] -= 10
    if cmd == 'rr':
        config.window['x1'] += 10
    if cmd == 'oo':
        config.window['y0'] -= 10
    if cmd == 'ou':
        config.window['y0'] += 10
    if cmd == 'uo':
        config.window['y1'] -= 10
    if cmd == 'uu':
        config.window['y1'] += 10
    save_config()
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
