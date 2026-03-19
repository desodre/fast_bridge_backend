import io
from starlette.websockets import WebSocket
import uiautomator2 as u2
import  adbutils
from fastapi import APIRouter, Path, Body, HTTPException, Response
from typing import Annotated

from app.controller.scrcpy import ScrcpyServer
from ..model import AdbResponse
from ..core import  log

router = APIRouter()

_connected_devices = {}

def get_cached_device(device_serial:str):
    global _connected_devices
    log.info(f"Getting device {device_serial}")

    if device_serial in _connected_devices:
        log.info(f"Device {device_serial} already connected")
        return _connected_devices[device_serial]

    log.info(f"Connecting to device {device_serial}")
    device = u2.connect(device_serial)
    _connected_devices[device_serial] = device
    return device


@router.get("/devices")
def get_all_devices():
    devices_list = adbutils.adb.device_list()
    log.info(f"Found {len(devices_list)} devices")
    return [device.info for device in devices_list]


@router.get("/device/{device_serial}/screenshot")
def get_device_screenshot(device_serial:str, display_id:int = 0):

    device = get_cached_device(device_serial)

    pil_image = device.screenshot(display_id = display_id).convert('RGB')
    buf = io.BytesIO() #basicamente aplicando 'hashing' da imagem
    pil_image.save(buf, format='JPEG')
    image_bytes = buf.getvalue()

    return Response(content=image_bytes,media_type="image/jpeg")

@router.get("/device/{device_serial}/prop/{shell_property}")
def get_property(device_serial:str, shell_property:str):
    try:
        device = get_cached_device(device_serial)
        output = device.shell(['getprop', shell_property])

        log.info(f'getting {shell_property} from device {device_serial}')
        return {
            'device_serial': device_serial,
            'stdout': output.output,
            'exit_code': output.exit_code
        }
    except Exception as e:
        raise HTTPException(status_code=505, detail=f'ADB erro {str(e)}')

@router.get('/device/{device_serial}/window_dump')
def get_device_window_dump(device_serial:str, format:str='xml'):
    device = get_cached_device(device_serial)

    xml_data = device.dump_hierarchy()
    log.info(f'dumping {format} dump to device {device_serial}')

    if format == 'xml':
        return Response(content=xml_data, media_type="text/xml")
    else:
        return HTTPException(status_code=505, detail=f'invalid format: {format}')


@router.post('/device/{device_serial}',response_model=AdbResponse)
def send_adb_shell(
    device_serial:Annotated[str, Path(title='Device serial')],
    commands:Annotated[list[str], Body(title='Commands args')]):

    try:
        device = get_cached_device(device_serial)
        output = device.shell(commands)

        return {
            'device_serial': device_serial,
            'stdout': output.output,
            'exit_code': output.exit_code
        }

    except Exception as e:
        raise HTTPException(status_code=505, detail=f'ADB erro {str(e)}')
    
    

@router.get('/device/{device_serial}/screen_info')
def get_device_screen_info(device_serial:str):
    device = get_cached_device(device_serial)
    screen_info = device.window_size()
    log.info(f'getting screen info from device {device_serial}')
    to_zip = ['width', 'height']
    screen_info = dict(zip(to_zip, screen_info))
    return screen_info


@router.post('/device/{device_serial}/input/keyevent')
def send_key_event(device_serial:str, keycode:int, repeat:int=0, metastate:int=0):
    device = get_cached_device(device_serial)
    log.info(f'sending key event {keycode} to device {device_serial}')
    device.shell(f'input keyevent {keycode} --repeat {repeat} --metastate {metastate}')
    return HTTPException(status_code=200, detail=f'Key event {keycode} sent to device {device_serial}')


@router.post('/device/{device_serial}/input/text')
def send_text(device_serial:str, text:str):
    device = get_cached_device(device_serial)
    device.shell(['input', 'text',  text])
    log.info(f'sending text {text} to device {device_serial}')
    return HTTPException(status_code=200, detail=f'Text {text} sent to device {device_serial}')


@router.post('/device/{device_serial}/input/touch')
def send_touch(device_serial:str, x:int, y:int):
    device = get_cached_device(device_serial)
    log.info(f'sending touch event to device {device_serial} at ({x}, {y})')
    device.shell(f'input touchscreen tap {x} {y}')
    return HTTPException(status_code=200, detail=f'Touch event sent to device {device_serial} at ({x}, {y})')


@router.websocket('/ws/device/{device_serial}/control')
async def control_device_websocket(websocket: WebSocket, device_serial:str):
    device = get_cached_device(device_serial)
    await websocket.accept()
    log.info(f'WebSocket connection accepted for device {device_serial}')
    try:
        device = adbutils.device(device_serial)
        server = ScrcpyServer(device)
        await server.handle_unified_websocket(websocket, device_serial)
    except Exception as e:
        log.error(f'Error in WebSocket connection for device {device_serial}: {str(e)}')
        await websocket.close(code=1011, reason=str(e))
