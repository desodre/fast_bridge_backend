import io
from fastapi import Depends
from fastapi import HTTPException

from app.dependencies import DeviceManager, get_device_manager
from app.model.adboutput import AdbResponse
from app.model.file_entry import FileManagerResponse
from app.controller.file_manager import list_files_by_path
from app.core import log


class DeviceService:
    def __init__(self, manager: DeviceManager) -> None:
        self._manager = manager

    def screenshot(self, serial: str, display_id: int = 0) -> bytes:
        device = self._manager.get_device(serial)
        pil_image = device.screenshot(display_id=display_id).convert('RGB')
        buf = io.BytesIO()
        pil_image.save(buf, format='JPEG')
        return buf.getvalue()

    def get_property(self, serial: str, prop: str) -> AdbResponse:
        try:
            device = self._manager.get_device(serial)
            output = device.shell(['getprop', prop])
            log.info(f"Getting {prop} from device {serial}")
            return AdbResponse(device_serial=serial, stdout=output.output, exit_code=output.exit_code)
        except Exception as e:
            raise HTTPException(status_code=505, detail=f"ADB erro {e}")

    def get_screen_info(self, serial: str) -> dict:
        device = self._manager.get_device(serial)
        w, h = device.window_size()
        log.info(f"Getting screen info from device {serial}")
        return {'width': w, 'height': h}

    def run_shell(self, serial: str, commands: list[str]) -> AdbResponse:
        try:
            device = self._manager.get_device(serial)
            output = device.shell(commands)
            return AdbResponse(device_serial=serial, stdout=output.output, exit_code=output.exit_code)
        except Exception as e:
            raise HTTPException(status_code=505, detail=f"ADB erro {e}")

    def get_window_dump(self, serial: str) -> str:
        device = self._manager.get_device(serial)
        log.info(f"Dumping window hierarchy for device {serial}")
        return device.dump_hierarchy()

    def send_keyevent(self, serial: str, keycode: int, repeat: int = 0, metastate: int = 0) -> None:
        device = self._manager.get_device(serial)
        log.info(f"Sending key event {keycode} to device {serial}")
        cmd = ['input', 'keyevent']
        if repeat > 0:
            cmd += ['--longpress'] + [str(keycode)] * repeat
        else:
            cmd.append(str(keycode))
        device.shell(cmd)

    def send_text(self, serial: str, text: str) -> None:
        device = self._manager.get_device(serial)
        log.info(f"Sending text to device {serial}")
        device.shell(['input', 'text', text])

    def send_touch(self, serial: str, x: int, y: int) -> None:
        device = self._manager.get_device(serial)
        log.info(f"Sending touch to device {serial} at ({x}, {y})")
        device.shell(['input', 'touchscreen', 'tap', str(x), str(y)])

    def list_files(self, serial: str, path: str | None) -> FileManagerResponse:
        device = self._manager.get_device(serial)
        log.info(f"Listing files in {path!r} on device {serial}")
        return list_files_by_path(device, path)


def get_device_service(manager: DeviceManager = Depends(get_device_manager)) -> DeviceService:
    return DeviceService(manager)
