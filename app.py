from starlette.responses import RedirectResponse
import uvicorn
from time import sleep
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from utils import get_config
from main import ColorGrabber
import main

config = get_config()
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
def root():
    color_grabber = ColorGrabber()
    if color_grabber.running:
        color_grabber.save_frame('static/frame.jpg')
        return open('templates/index.html').read()
    return 'not running'


@app.get("/start")
def start():
    color_grabber = ColorGrabber()
    return {"running": color_grabber.running}


@app.get("/stop")
def stop():
    ColorGrabber().stop()
    sleep(0.5)
    return {"running": ColorGrabber.running}


@app.get("/window")
def window(cmd: str):
    print(cmd)
    if cmd == 'll':
        main.config.window['x0'] -= 10
    if cmd == 'lr':
        main.config.window['x0'] += 10
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
