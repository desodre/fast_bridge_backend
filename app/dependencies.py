import uiautomator2 as u2
from app.core import log


class DeviceManager:
    """Manages uiautomator2 device connections, reusing instances per serial."""

    def __init__(self) -> None:
        self._devices: dict[str, u2.Device] = {}

    def get_device(self, serial: str) -> u2.Device:
        if serial not in self._devices:
            log.info(f"Connecting to device {serial}")
            self._devices[serial] = u2.connect(serial)
        else:
            log.info(f"Reusing cached connection for device {serial}")
        return self._devices[serial]


_device_manager = DeviceManager()


def get_device_manager() -> DeviceManager:
    return _device_manager
