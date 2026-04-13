from starlette.websockets import WebSocket
from fastapi import APIRouter, Path, Body, HTTPException, Response, Depends
from typing import Annotated
from app.controller.scrcpy import ScrcpyServer
from app.model import AdbResponse, FileManagerResponse
from app.services.device_service import DeviceService, get_device_service
from app.core import log
import adbutils


router = APIRouter()


@router.get("/devices")
def get_all_devices() -> list:
    devices_list = adbutils.adb.device_list()
    log.info(f"Found {len(devices_list)} devices")
    return [device.info for device in devices_list]


@router.get("/device/{device_serial}/screenshot")
def get_device_screenshot(
    device_serial: str,
    display_id: int = 0,
    svc: DeviceService = Depends(get_device_service),
) -> Response:
    image_bytes = svc.screenshot(device_serial, display_id)
    return Response(content=image_bytes, media_type="image/jpeg")


@router.get("/device/{device_serial}/prop/{shell_property}")
def get_property(
    device_serial: str,
    shell_property: str,
    svc: DeviceService = Depends(get_device_service),
) -> AdbResponse:
    return svc.get_property(device_serial, shell_property)


@router.get('/device/{device_serial}/window_dump')
def get_device_window_dump(
    device_serial: str,
    format: str = 'xml',
    svc: DeviceService = Depends(get_device_service),
) -> Response:
    if format != 'xml':
        raise HTTPException(status_code=400, detail=f"Invalid format: {format}")
    xml_data = svc.get_window_dump(device_serial)
    return Response(content=xml_data, media_type="text/xml")


@router.post('/device/{device_serial}', response_model=AdbResponse)
def send_adb_shell(
    device_serial: Annotated[str, Path(title='Device serial')],
    commands: Annotated[list[str], Body(title='Command args')],
    svc: DeviceService = Depends(get_device_service),
) -> AdbResponse:
    return svc.run_shell(device_serial, commands)


@router.get('/device/{device_serial}/screen_info')
def get_device_screen_info(
    device_serial: str,
    svc: DeviceService = Depends(get_device_service),
) -> dict:
    return svc.get_screen_info(device_serial)


@router.post('/device/{device_serial}/input/keyevent')
def send_key_event(
    device_serial: str,
    keycode: int,
    repeat: int = 0,
    metastate: int = 0,
    svc: DeviceService = Depends(get_device_service),
) -> dict:
    svc.send_keyevent(device_serial, keycode, repeat, metastate)
    return {'detail': f'Key event {keycode} sent to device {device_serial}'}


@router.put('/device/{device_serial}/input/text')
def send_text(
    device_serial: str,
    text: str,
    svc: DeviceService = Depends(get_device_service),
) -> dict:
    svc.send_text(device_serial, text)
    return {'detail': f'Text sent to device {device_serial}'}


@router.put('/device/{device_serial}/input/touch')
def send_touch(
    device_serial: str,
    x: int,
    y: int,
    svc: DeviceService = Depends(get_device_service),
) -> dict:
    svc.send_touch(device_serial, x, y)
    return {'detail': f'Touch event sent to device {device_serial} at ({x}, {y})'}


@router.get('/device/{device_serial}/file_manager', response_model=FileManagerResponse)
def get_file_manager(
    device_serial: str,
    path: str | None = None,
    svc: DeviceService = Depends(get_device_service),
) -> FileManagerResponse:
    return svc.list_files(device_serial, path)


@router.websocket('/ws/device/{device_serial}/control')
async def control_device_websocket(websocket: WebSocket, device_serial: str) -> None:
    await websocket.accept()
    log.info(f'WebSocket connection accepted for device {device_serial}')
    server = None
    try:
        device = adbutils.device(device_serial)
        server = ScrcpyServer(device)
        await server.handle_unified_websocket(websocket, device_serial)
    except Exception as e:
        log.error(f'Error in WebSocket connection for device {device_serial}: {e}')
        await websocket.close(code=1011, reason=str(e))
    finally:
        if server:
            server.close()
